"""REI-0.5 real Unix socket protocol with injectable offline source transport."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest

from rei0.durable import EvidenceDatabase
from rei0.graph import EpistemicGraph, utc_now
from rei0.models import Node, NodeKind, Provenance, SourceKind
from rei0.review import Ed25519ReviewIssuer, Ed25519TrustedReviewer, VerificationBoundary
from rei0.service import VerificationServer,call_service,ServiceError
from rei0.sources import SecureSourceFetcher
from rei0.service_cli import source_demo, _run, add_args, load_signer, load_trust


class SourceRPCTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        g=EpistemicGraph();t=utc_now()
        g.add_node(Node('c',NodeKind.CLAIM,'A published observation',
            Provenance('user',SourceKind.HUMAN,'question','fixture:question',t),t))
        issuer=Ed25519ReviewIssuer.generate('ed','reviewer')
        self.boundary=VerificationBoundary({'ed':Ed25519TrustedReviewer(
            'reviewer',issuer.public_key_bytes())})
        self.db=EvidenceDatabase.initialize(self.root/'db.sqlite',g,self.boundary)
        self.addCleanup(self.db.close)
        self.b=b'A published observation in a source document.'
        self.fetcher=SecureSourceFetcher({'paper.example.org'},
            resolver=lambda *args, **kwargs:[(socket.AF_INET,1,1,'',('93.184.216.34',443))],
            transport=lambda *args:(200,{'content-type':'text/plain'},self.b,'f'*64))
    def serve(self,fetcher):
        srv=VerificationServer(self.root/'svc.sock',self.db,fetcher)
        thread=threading.Thread(target=srv.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(lambda:(srv.shutdown(),thread.join(timeout=3),srv.server_close()))
        return self.root/'svc.sock'
    def test_source_protocol_through_socket(self):
        socket_path=self.serve(self.fetcher)
        meta=call_service(socket_path,'source-retrieve',
          {'retrieval_id':'p1','url':'https://paper.example.org/original'},request_id='r1')
        self.assertEqual(meta['artifact_sha256'],hashlib.sha256(self.b).hexdigest())
        self.assertEqual(call_service(socket_path,'source-info',{'retrieval_id':'p1'}),meta)
        submission=call_service(socket_path,'submit_source',{
          'retrieval_id':'p1','submission_id':'s1','evidence_id':'e1','claim_id':'c',
          'text':'A published observation','polarity':'supports'},request_id='s1')
        self.assertEqual(submission['status'],'pending')
        status=call_service(socket_path,'verify')
        self.assertEqual(status['source_captures'],1)
        with self.assertRaises(ServiceError):
            call_service(socket_path,'verify',{'expected_source_head':'0'*64})
        self.assertEqual(call_service(socket_path,'verify',
          {'expected_source_head':status['source_audit_head']})['source_captures'],1)
    def test_source_retrieval_disabled(self):
        path=self.serve(None)
        with self.assertRaises(ServiceError):
            call_service(path,'source-retrieve',{
                'retrieval_id':'p1','url':'https://paper.example.org/original'},request_id='x')
    def test_forged_source_field_rejected(self):
        path=self.serve(self.fetcher)
        with self.assertRaises(ServiceError):
            call_service(path,'submit_source',{'retrieval_id':'x','submission_id':'s',
                 'evidence_id':'e','claim_id':'c','text':'fake','polarity':'supports',
                 'artifact_b64':'hacked'},request_id='s1')
    def test_signing_rpc_absent(self):
        path=self.serve(self.fetcher)
        with self.assertRaises(ServiceError):
            call_service(path,'sign',{})
    def test_public_export_offline_after_capture(self):
        path=self.serve(self.fetcher)
        call_service(path,'source-retrieve',{
          'retrieval_id':'p1','url':'https://paper.example.org/original'},request_id='r1')
        issuer=Ed25519ReviewIssuer.generate('public-test','reviewer')
        # Offline artifact export reads verified bytes; no signing endpoint.
        trust=self.root/'public.json'
        trust.write_text(json.dumps({'schema_version':'rei0.trust.v2','reviewers':[
          {'key_id':'ed','reviewer_id':'reviewer','public_hex':list(
             self.boundary._reviewers.values())[0].public_key.hex(),
           'can_verify':True,'can_revoke':True}]}))
        trust.chmod(0o600)
        out=self.root/'original.txt'
        parser=argparse.ArgumentParser();add_args(parser)
        result=_run(parser.parse_args(['source-export','--database',str(self.db.path),
                '--trust',str(trust),'--retrieval-id','p1','--output',str(out)]))
        self.assertEqual(out.read_bytes(),self.b)
        self.assertEqual(result['sha256'],hashlib.sha256(self.b).hexdigest())
        with self.assertRaises(FileExistsError):
            _run(parser.parse_args(['source-export','--database',str(self.db.path),
               '--trust',str(trust),'--retrieval-id','p1','--output',str(out)]))
    def test_synthetic_demo(self):
        data=source_demo()
        self.assertEqual(data['claim_status'],'SUPPORT_ONLY')
        self.assertEqual(data['receipt_scheme'],'rei0.review.v2')
        self.assertEqual(data['scenario'],'synthetic-offline-no-network')
