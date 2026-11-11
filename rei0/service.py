"""REI-0.4 local verification service over filesystem-protected Unix sockets.

The service accepts untrusted PENDING submissions and already-signed external
review receipts. There is deliberately NO sign, approve, or set-validation RPC.
No TCP listener, shell commands, dynamic code loading, or LLM access.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import socketserver
import sqlite3
from typing import Any

from .durable import DurableError, EvidenceDatabase
from .evidence import EvidenceError
from .graph import GraphError
from .review import ReviewError, VerificationBoundary
from .models import canonical_json
from .sources import SourceError, SecureSourceFetcher, canonical_source_url

MAX_REQUEST_BYTES = 3_100_000
MAX_RESPONSE_BYTES = 1_000_000


class ServiceError(ValueError):
    """Local verification service protocol or transport error."""


def dispatch(db: EvidenceDatabase, request: dict[str, Any],
             fetcher: SecureSourceFetcher | None = None) -> dict[str, Any]:
    if not isinstance(request, dict) or set(request) - {
        'op', 'body', 'request_id', 'expected_revision'
    } or not isinstance(request.get('op'),str):
        raise ServiceError('invalid request schema')
    op = request['op']
    body = request.get('body', {})
    if not isinstance(body,dict):
        raise ServiceError('body must be an object')
    if op == 'source-retrieve':
        if set(request) != {'op','body','request_id'} or set(body) != {'retrieval_id','url'}:
            raise ServiceError('source retrieval needs retrieval_id, URL and request_id')
        if fetcher is None: raise ServiceError('network source retrieval is disabled')
        # Idempotent before making a new external request.
        try:
            prior = db.source_metadata(body['retrieval_id'])
        except SourceError:
            prior = None
        if prior is not None:
            wanted,_ = canonical_source_url(body['url'],fetcher.allowed_hosts)
            if prior['url'] != wanted: raise ServiceError('retrieval ID reused for different URL')
            return prior
        capture = fetcher.fetch(body['url'])
        return db.source_store(body['retrieval_id'],capture)
    if op in ('submit','submit_source','accept'):
        if op == 'submit_source' and set(body) != {
            'retrieval_id','submission_id','evidence_id','claim_id','text','polarity'}:
            raise ServiceError('invalid source submission request')
        if set(request) - {'op','body','request_id','expected_revision'} or \
           'request_id' not in request:
            raise ServiceError('mutations require request_id')
        return db.apply(op,body,request['request_id'],
                        expected_revision=request.get('expected_revision'))
    if set(request) != {'op','body'}:
        raise ServiceError('read request must contain op and body only')
    if op == 'status':
        if body: raise ServiceError('status takes no parameters')
        return db.status()
    if op == 'assess':
        if set(body) != {'claim_id'}: raise ServiceError('assess needs claim_id')
        return db.assess(body['claim_id'])
    if op == 'source-info':
        if set(body) != {'retrieval_id'}: raise ServiceError('source-info needs retrieval_id')
        return db.source_metadata(body['retrieval_id'])
    if op == 'challenge':
        if set(body) != {'submission_id'}: raise ServiceError('challenge needs submission_id')
        return db.challenge(body['submission_id'])
    if op == 'verify':
        if set(body) - {'expected_head','expected_graph_head','expected_source_head'}:
            raise ServiceError('unsupported verify arguments')
        return db.check(expected_head=body.get('expected_head'),
                        expected_graph_head=body.get('expected_graph_head'),
                        expected_source_head=body.get('expected_source_head'))
    raise ServiceError('unrecognized operation; signing is never available over RPC')


class _RequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.request.settimeout(15)
        try:
            raw = self.rfile.readline(MAX_REQUEST_BYTES + 1)
            if not raw or len(raw) > MAX_REQUEST_BYTES or not raw.endswith(b'\n'):
                raise ServiceError('request missing, oversized, or not newline terminated')
            request = json.loads(raw.decode('utf-8'))
            result = dispatch(self.server.db, request, self.server.fetcher)
            response = {'ok':True,'result':result}
        except (ServiceError, DurableError, EvidenceError, GraphError,
                ReviewError, SourceError, sqlite3.Error, ValueError, TypeError, KeyError, UnicodeError,
                json.JSONDecodeError, OSError) as exc:
            response = {'ok':False,'error':str(exc)[:400]}
        encoded = canonical_json(response).encode('utf-8')+b'\n'
        if len(encoded) > MAX_RESPONSE_BYTES:
            encoded = b'{"ok":false,"error":"response exceeds limit"}\n'
        try:
            self.wfile.write(encoded)
        except OSError:
            pass


class VerificationServer(socketserver.UnixStreamServer):
    allow_reuse_address = False
    def __init__(self, socket_path: str | Path, db: EvidenceDatabase,
                 fetcher: SecureSourceFetcher | None = None):
        if not hasattr(socketserver, 'UnixStreamServer'):
            raise ServiceError('Unix-domain sockets are not available on this platform')
        self.socket_path = Path(socket_path)
        if self.socket_path.exists() or self.socket_path.is_symlink():
            raise ServiceError('socket path already exists; will not unlink it')
        self.socket_path.parent.mkdir(parents=True,exist_ok=True)
        self.db = db
        self.fetcher = fetcher
        old_mask = os.umask(0o077)
        try:
            super().__init__(str(self.socket_path),_RequestHandler)
            os.chmod(self.socket_path,0o600)
            self._socket_inode = self.socket_path.lstat().st_ino
        finally:
            os.umask(old_mask)

    def server_close(self) -> None:
        super().server_close()
        # Only remove an owned socket inode; don't clobber a replaced file.
        try:
            st = self.socket_path.lstat()
            import stat
            if stat.S_ISSOCK(st.st_mode) and st.st_ino == self._socket_inode:
                self.socket_path.unlink()
        except FileNotFoundError:
            pass


def call_service(socket_path: str | Path, op: str, body: dict[str, Any] | None = None,
                 *, request_id: str | None = None,
                 expected_revision: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {'op':op,'body':body or {}}
    if request_id is not None:
        payload['request_id']=request_id
    if expected_revision is not None:
        payload['expected_revision']=expected_revision
    encoded = canonical_json(payload).encode('utf-8')+b'\n'
    if len(encoded) > MAX_REQUEST_BYTES:
        raise ServiceError('request exceeds service limit')
    try:
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
            sock.settimeout(15)
            sock.connect(str(socket_path))
            sock.sendall(encoded)
            reply = bytearray()
            while b'\n' not in reply:
                block = sock.recv(8192)
                if not block: break
                reply.extend(block)
                if len(reply) > MAX_RESPONSE_BYTES: raise ServiceError('reply exceeds limit')
        result = json.loads(bytes(reply).decode('utf-8'))
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise ServiceError(f'service unavailable or returned invalid response: {exc}') from exc
    if not isinstance(result,dict) or set(result) not in ({'ok','result'},{'ok','error'}):
        raise ServiceError('invalid response schema')
    if result['ok'] is not True:
        raise ServiceError(str(result.get('error','service failed')))
    return result['result']
