"""REI-0.5 offline source policy, provenance, isolation and tamper tests."""
from __future__ import annotations
import json
import socket
import tempfile
import unittest
from pathlib import Path

from rei0.sources import (SecureSourceFetcher, FetchedSource, SourceError,
                          canonical_source_url, checked_public_addresses)
from rei0.durable import EvidenceDatabase
from rei0.review import Ed25519ReviewIssuer, Ed25519TrustedReviewer, VerificationBoundary, ReviewError
from rei0.graph import EpistemicGraph, utc_now
from rei0.models import Provenance, Node, NodeKind, SourceKind, Validation
from rei0.service import dispatch, ServiceError
from rei0.service_cli import sign_challenge

HOST='research.example.org'
URL=f'https://{HOST}/publication.html'
DATA=b'<html>Observed temperature was 18 C.</html>'
CERT='a'*64
PUBLIC_IP='93.184.216.34'


def fake_dns(*args, **kwargs):
    return [(socket.AF_INET,socket.SOCK_STREAM,6,'',(PUBLIC_IP,443))]


def transport(url, host, ip, timeout):
    assert host == HOST and ip == PUBLIC_IP
    return (200,{'content-type':'text/html','content-length':str(len(DATA))},DATA,CERT)


class URLPolicyTests(unittest.TestCase):
    def setUp(self): self.f=SecureSourceFetcher({HOST},resolver=fake_dns,transport=transport)
    def test_successful_capture_metadata(self):
        capture=self.f.fetch(URL)
        self.assertEqual(capture.content,DATA)
        self.assertEqual(capture.tls_cert_sha256,CERT)
        self.assertEqual(capture.metadata()['size_bytes'],len(DATA))
    def test_requires_allowlist(self):
        with self.assertRaises(SourceError): SecureSourceFetcher(set())
        with self.assertRaises(SourceError): self.f.fetch('https://other.example.org/')
    def test_http_and_userinfo_rejected(self):
        for url in ('http://'+HOST+'/',f'https://user:pwd@{HOST}/',
                    f'https://{HOST}:444/',f'https://{HOST}/#fragment',
                    f'https://{HOST}/\nX'):
            with self.subTest(url=url),self.assertRaises(SourceError): self.f.fetch(url)
    def test_dns_private_rejected(self):
        for address in ('127.0.0.1','10.0.0.2','192.168.1.1','169.254.2.1','::1'):
            with self.subTest(address=address):
                def resolver(*args, **kwargs):
                    return [(socket.AF_INET,0,0,'',(address,443))]
                f=SecureSourceFetcher({HOST},resolver=resolver,transport=transport)
                with self.assertRaises(SourceError):f.fetch(URL)
    def test_dns_mixed_address_rejected(self):
        def mixed(*args,**kwargs):
            return fake_dns()+[(socket.AF_INET,0,0,'',('127.0.0.1',443))]
        with self.assertRaises(SourceError):
            SecureSourceFetcher({HOST},resolver=mixed,transport=transport).fetch(URL)
    def test_redirect_rejected(self):
        f=SecureSourceFetcher({HOST},resolver=fake_dns,
             transport=lambda *args:(302,{'location':'https://evil.com'},b'redirect',CERT))
        with self.assertRaises(SourceError):f.fetch(URL)
    def test_oversized_rejected(self):
        f=SecureSourceFetcher({HOST},resolver=fake_dns,
            transport=lambda *args:(200,{'content-type':'text/html'},b'A'*2_000_001,CERT))
        with self.assertRaises(SourceError): f.fetch(URL)
    def test_compression_rejected(self):
        f=SecureSourceFetcher({HOST},resolver=fake_dns,
            transport=lambda *args:(200,{'content-type':'text/html','content-encoding':'gzip'},b'A',CERT))
        with self.assertRaises(SourceError): f.fetch(URL)
    def test_unsupported_media_rejected(self):
        f=SecureSourceFetcher({HOST},resolver=fake_dns,
            transport=lambda *args:(200,{'content-type':'application/octet-stream'},b'A',CERT))
        with self.assertRaises(SourceError): f.fetch(URL)
    def test_content_length_mismatch(self):
        f=SecureSourceFetcher({HOST},resolver=fake_dns,
            transport=lambda *args:(200,{'content-type':'text/html','content-length':'999'},b'A',CERT))
        with self.assertRaises(SourceError): f.fetch(URL)


class CapturedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.signer=Ed25519ReviewIssuer.generate('ed-key','different-reviewer')
        trusted=Ed25519TrustedReviewer('different-reviewer',self.signer.public_key_bytes())
        self.boundary=VerificationBoundary({'ed-key':trusted})
        g=EpistemicGraph();t=utc_now()
        g.add_node(Node('c',NodeKind.CLAIM,'Temperature is 18 C',
                        Provenance('questioner',SourceKind.HUMAN,'questions','fixture:question',t),t))
        self.db=EvidenceDatabase.initialize(Path(self.temp.name)/'db.sqlite',g,self.boundary)
        self.addCleanup(self.db.close)
        self.f=SecureSourceFetcher({HOST},resolver=fake_dns,transport=transport)
    def grab(self):
        return dispatch(self.db,{'op':'source-retrieve','body':{'retrieval_id':'r1','url':URL},
                                 'request_id':'request-r1'},self.f)
    def submit(self, text='Observed temperature was 18 C.'):
        return dispatch(self.db,{'op':'submit_source','body':{
            'retrieval_id':'r1','submission_id':'s1','evidence_id':'e1','claim_id':'c',
            'text':text,'polarity':'supports'},'request_id':'submit-r1'})
    def test_retrieval_disabled_by_default(self):
        with self.assertRaises(ServiceError):
            dispatch(self.db,{'op':'source-retrieve','body':{'retrieval_id':'r1','url':URL},
                              'request_id':'x'})
    def test_complete_asymmetric_workflow(self):
        meta=self.grab()
        self.assertEqual(self.db.check()['source_captures'],1)
        self.assertEqual(meta['url'],URL)
        self.submit()
        self.assertEqual(self.db.assess('c')['assessment']['state'],'NEITHER')
        ch=self.db.challenge('s1')
        receipt=sign_challenge(ch,self.signer,Validation.VERIFIED,'Reviewed original data',artifact=DATA)
        self.db.apply('accept',{'receipt':receipt},'approve')
        self.assertEqual(self.db.assess('c')['assessment']['state'],'SUPPORT_ONLY')
        self.assertEqual(len(receipt['signature']),128)
        self.assertEqual(self.db.check()['source_linked_submissions'],1)
        self.assertEqual(self.db.check()['source_captures'],1)
        self.assertEqual(self.db.source_metadata('r1')['artifact_sha256'],ch['artifact_sha256'])
        # Reopen from the public-key-only verifier, not from signer secret.
        self.db.close()
        self.db=EvidenceDatabase(Path(self.temp.name)/'db.sqlite',self.boundary)
        self.assertTrue(self.db.check()['valid'])
        revocation=sign_challenge(self.db.challenge('s1'),self.signer,Validation.REVOKED,'Withdrawn')
        self.db.apply('accept',{'receipt':revocation},'revoke')
        self.assertEqual(self.db.assess('c')['assessment']['state'],'NEITHER')
    def test_source_excerpt_must_be_in_bytes(self):
        self.grab()
        with self.assertRaises(SourceError): self.submit('19 C')
        self.assertEqual(self.db.check()['submissions'],0)
    def test_source_cannot_be_substituted_by_client(self):
        self.grab()
        body={'retrieval_id':'r1','submission_id':'s1','evidence_id':'e1',
              'claim_id':'c','text':'Observed temperature was 18 C.',
              'polarity':'supports','artifact_b64':'ZXZpbA=='}
        with self.assertRaises(ServiceError):
            dispatch(self.db,{'op':'submit_source','body':body,'request_id':'bad'})
    def test_duplicate_retrieval_id_idempotent(self):
        first=self.grab();second=self.grab()
        self.assertEqual(first,second)
        self.assertEqual(self.db.check()['source_captures'],1)
        with self.assertRaises(ServiceError):
            dispatch(self.db,{'op':'source-retrieve','body':{
                'retrieval_id':'r1','url':'https://'+HOST+'/other'},'request_id':'z'},self.f)
    def test_source_event_tampering(self):
        self.grab()
        self.db.conn.execute('UPDATE source_events SET event_hash=?',('0'*64,))
        with self.assertRaises(SourceError):self.db.check()
    def test_source_blob_tampering(self):
        self.grab()
        self.db.conn.execute('UPDATE source_blobs SET content=?',(b'bad',))
        with self.assertRaises(SourceError):self.db.check()
    def test_source_anchor_rejects_mismatch(self):
        self.grab()
        with self.assertRaises(SourceError):self.db.check(expected_source_head='0'*64)
    def test_source_record_metadata_tampering(self):
        self.grab()
        self.db.conn.execute('UPDATE source_records SET metadata_digest=?',('a'*64,))
        with self.assertRaises(SourceError):self.db.check()
    def test_source_submission_link_tampering(self):
        self.grab();self.submit()
        from rei0.sources import FetchedSource
        self.db.source_store('r2',FetchedSource(URL,'2026-11-10T19:00:00Z',
          'text/html', PUBLIC_IP,CERT,b'<html>Different content</html>'))
        self.db.conn.execute('UPDATE source_links SET retrieval_id=?',('r2',))
        with self.assertRaises(SourceError):self.db.check()
    def test_deleted_source_link_detected(self):
        self.grab();self.submit()
        self.db.conn.execute('DELETE FROM source_links')
        with self.assertRaises(SourceError):self.db.check()

    def test_legacy_submission_cannot_spoof_retrieval_namespace(self):
        import base64
        from rei0.models import Provenance
        self.grab()
        body={'submission_id':'fake','evidence_id':'efake','claim_id':'c',
              'text':'claimed source','artifact_b64':base64.b64encode(DATA).decode(),
              'polarity':'supports','provenance':Provenance(
                'retrieval:r1',SourceKind.EXTERNAL,HOST,URL,'2026-11-10T19:00:00Z').to_dict()}
        from rei0.durable import DurableError
        with self.assertRaises(DurableError):self.db.apply('submit',body,'fake-req')

    def test_replayed_request_preserves_state(self):
        self.grab();body={'retrieval_id':'r1','submission_id':'s1','evidence_id':'e1',
                         'claim_id':'c','text':'Observed temperature was 18 C.','polarity':'supports'}
        req={'op':'submit_source','body':body,'request_id':'submit-r1'}
        a=dispatch(self.db,req);b=dispatch(self.db,req)
        self.assertEqual(a,b);self.assertEqual(self.db.status()['revision'],1)
