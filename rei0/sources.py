"""Bounded, pinned-IP HTTPS retrieval. Content provenance is NOT factual truth.

Production fetcher: exact hostname allowlist; reject localhost/private addresses,
userinfo, IP literals, non-443 ports, redirects, compression, and oversized bodies.
Resolve once; connect to a validated IP but verify TLS for the original hostname.
External network access is opt-in at the service, never exposed to the LLM adapter.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import http.client
import ipaddress
import socket
import ssl
import time
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from .models import canonical_json, require_utc

MAX_SOURCE_BYTES = 2_000_000
ALLOWED_MIME = frozenset({'text/plain','text/html','text/xml','application/xml',
                          'application/json','application/pdf'})


class SourceError(ValueError):
    """Source URL, transport, provenance or content failed a verification gate."""


def canonical_source_url(url: str, allowed_hosts: frozenset[str]) -> tuple[str,str]:
    if not isinstance(url,str) or len(url)>2048 or any(ord(c)<33 or ord(c)==127 for c in url):
        raise SourceError('invalid source URL')
    try: parts = urlsplit(url)
    except ValueError as exc: raise SourceError('invalid source URL') from exc
    if (parts.scheme != 'https' or not parts.hostname or parts.username is not None or
        parts.password is not None or parts.fragment or parts.port not in (None,443)):
        raise SourceError('source must be a direct HTTPS URL without credentials or fragments')
    host = parts.hostname.lower().rstrip('.')
    if not allowed_hosts or host not in allowed_hosts:
        raise SourceError('source hostname is not explicitly allowlisted')
    try:
        ipaddress.ip_address(host)
        raise SourceError('literal IP addresses are not permitted')
    except ValueError as exc:
        if str(exc) == 'literal IP addresses are not permitted': raise
    if not host.isascii() or '..' in host or host.startswith('-') or '.' not in host:
        raise SourceError('invalid hostname')
    return urlunsplit(('https',host,parts.path or '/',parts.query,'')),host


def checked_public_addresses(host: str, resolver: Callable | None = None) -> list[str]:
    lookup = resolver or socket.getaddrinfo
    try: answers = lookup(host,443,type=socket.SOCK_STREAM)
    except OSError as exc: raise SourceError('DNS resolution failed') from exc
    ips = []
    for row in answers:
        try: ip = ipaddress.ip_address(row[4][0])
        except (ValueError,IndexError,TypeError) as exc:
            raise SourceError('DNS returned invalid address') from exc
        if not ip.is_global:
            raise SourceError('DNS returned non-public address')
        if str(ip) not in ips: ips.append(str(ip))
    if not ips: raise SourceError('DNS returned no addresses')
    return ips


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host: str, pinned_ip: str, timeout: float):
        super().__init__(host,443,timeout=timeout,context=ssl.create_default_context())
        self._pinned_ip = pinned_ip

    def connect(self) -> None:
        raw = socket.create_connection((self._pinned_ip,443),self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw,server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def _network_fetch(url: str, host: str, pinned_ip: str, timeout: float):
    """Fetch with a wall-clock read deadline and no redirect/proxy handling."""
    parts = urlsplit(url)
    connection = _PinnedHTTPS(host,pinned_ip,timeout)
    deadline = time.monotonic() + timeout
    try:
        connection.request('GET',(parts.path or '/')+('?' + parts.query if parts.query else ''),
            headers={'User-Agent':'REI-0.5-SourceVerifier/0.5',
                     'Accept':'text/plain, text/html, application/json, application/pdf',
                     'Accept-Encoding':'identity','Connection':'close'})
        cert = connection.sock.getpeercert(binary_form=True)
        if not cert: raise SourceError('peer certificate missing')
        response = connection.getresponse()
        pairs = response.getheaders()
        for sensitive in ('content-length','content-type','content-encoding'):
            if sum(k.lower()==sensitive for k,v in pairs)>1:
                raise SourceError('ambiguous duplicate response header')
        headers = {k.lower():v for k,v in pairs}
        chunks=[]
        total=0
        while total <= MAX_SOURCE_BYTES:
            remaining=deadline-time.monotonic()
            if remaining <= 0: raise SourceError('source retrieval deadline exceeded')
            if connection.sock is not None:connection.sock.settimeout(remaining)
            chunk = response.read1(min(65536,MAX_SOURCE_BYTES+1-total))
            if not chunk:break
            total += len(chunk)
            chunks.append(chunk)
        return response.status,headers,b''.join(chunks),sha256(cert).hexdigest()
    finally:
        connection.close()


@dataclass(frozen=True)
class FetchedSource:
    url: str
    retrieved_at: str
    content_type: str
    pinned_ip: str
    tls_cert_sha256: str
    content: bytes

    def __post_init__(self) -> None:
        require_utc(self.retrieved_at)
        if not isinstance(self.content,bytes) or not (1<=len(self.content)<=MAX_SOURCE_BYTES):
            raise SourceError('source content must be 1-2000000 bytes')
        if self.content_type not in ALLOWED_MIME:
            raise SourceError('source content type is not approved')
        if not isinstance(self.tls_cert_sha256,str) or len(self.tls_cert_sha256)!=64 or any(
            c not in '0123456789abcdef' for c in self.tls_cert_sha256):
            raise SourceError('TLS certificate hash must be SHA-256 hex')
        if not ipaddress.ip_address(self.pinned_ip).is_global:
            raise SourceError('pinned IP must be globally routable')

    def metadata(self) -> dict:
        return {'schema_version':'rei0.source.v1','url':self.url,
                'retrieved_at':self.retrieved_at,'content_type':self.content_type,
                'pinned_ip':self.pinned_ip,'tls_cert_sha256':self.tls_cert_sha256,
                'artifact_sha256':sha256(self.content).hexdigest(),
                'size_bytes':len(self.content)}


class SecureSourceFetcher:
    """Use an operator-controlled allowlist. `transport` and `resolver` are for isolated tests."""
    def __init__(self, allowed_hosts: set[str] | frozenset[str], *, timeout: float = 8,
                 resolver: Callable | None = None, transport: Callable | None = None):
        if not allowed_hosts or not all(isinstance(h,str) and h == h.lower() and
                                        '.' in h and h.isascii() for h in allowed_hosts):
            raise SourceError('explicit lowercase hostname allowlist required')
        if not (0 < timeout <= 20): raise SourceError('timeout must be in (0,20]')
        self.allowed_hosts = frozenset(allowed_hosts)
        self.timeout = timeout
        self._resolver = resolver
        self._transport = transport or _network_fetch

    def fetch(self,url: str) -> FetchedSource:
        canonical,host = canonical_source_url(url,self.allowed_hosts)
        pinned_ip = checked_public_addresses(host,self._resolver)[0]
        try:
            status,headers,body,cert_hash = self._transport(canonical,host,pinned_ip,self.timeout)
        except (OSError,ssl.SSLError,http.client.HTTPException) as exc:
            raise SourceError('HTTPS retrieval failed') from exc
        if status != 200:
            raise SourceError(f'only HTTP 200 is accepted (received {status}); redirects rejected')
        if not isinstance(headers,dict) or not isinstance(body,bytes):
            raise SourceError('malformed HTTPS response')
        if headers.get('content-encoding','identity').lower() != 'identity':
            raise SourceError('compressed responses are not permitted')
        media = headers.get('content-type','').split(';',1)[0].strip().lower()
        if media not in ALLOWED_MIME:
            raise SourceError('unsupported source content type')
        length = headers.get('content-length')
        if length is not None:
            if not length.isdigit() or int(length)>MAX_SOURCE_BYTES:
                raise SourceError('declared source size is invalid or oversized')
            if int(length)!=len(body): raise SourceError('source body length mismatch')
        return FetchedSource(canonical,datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
                             media,pinned_ip,cert_hash,body)
