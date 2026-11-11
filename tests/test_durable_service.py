"""Deterministic REI-0.4 transactional, authentication, migration and RPC tests."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from rei0.durable import DurableError, EvidenceDatabase
from rei0.evidence import EvidenceLedger
from rei0.graph import EpistemicGraph, utc_now
from rei0.models import EdgeKind, Node, NodeKind, Provenance, SourceKind, Validation
from rei0.review import ReviewIssuer, TrustedReviewer, VerificationBoundary, ReviewError
from rei0.service import VerificationServer, call_service, ServiceError, dispatch
from rei0.service_cli import load_signer, load_trust, sign_challenge, _write_new


class DurableFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.secret=b'K'*32
        self.issuer=ReviewIssuer('rkey','reviewer',self.secret)
        self.boundary=VerificationBoundary({'rkey':TrustedReviewer('reviewer',self.secret)})
        self.graph=EpistemicGraph()
        self.now=utc_now()
        self.graph.add_node(Node('claim', NodeKind.CLAIM, 'The example is supported',
              Provenance('original-question',SourceKind.HUMAN,'question','fixture:question',self.now),self.now))
        self.path=self.root/'test.db'
        self.db=EvidenceDatabase.initialize(self.path,self.graph,self.boundary)
        self.addCleanup(self.db.close)

    def body(self, sid='s1', polarity='supports', *, source='external-one', artifact=b'ORIGINAL A',
             source_group=None, source_kind='external'):
        return {'submission_id':sid,'evidence_id':'e-'+sid,'claim_id':'claim',
                'text':'observation '+sid,'artifact_b64':base64.b64encode(artifact).decode('ascii'),
                'polarity':polarity,'provenance':Provenance(source,SourceKind(source_kind),
                 source_group or source, 'fixture:'+sid,self.now).to_dict()}

    def submit(self, sid='s1', polarity='supports', **kwargs):
        return self.db.apply('submit',self.body(sid,polarity,**kwargs),'submit-'+sid)

    def sign(self, sid='s1', decision=Validation.VERIFIED, artifact=b'ORIGINAL A'):
        challenge=self.db.challenge(sid)
        return sign_challenge(challenge,self.issuer,decision,'human-reviewed synthetic fixture',
                              artifact=artifact).copy()

    def accept(self, sid='s1', decision=Validation.VERIFIED, artifact=b'ORIGINAL A'):
        return self.db.apply('accept',{'receipt':self.sign(sid,decision,artifact)},'accept-'+sid+'-'+decision.value)


class EvidenceDatabaseTests(DurableFixture):
    def test_schema_and_permissions(self):
        self.assertEqual(self.db.check()['schema'],'rei0.sqlite.v1')
        if os.name != 'nt': self.assertEqual(self.path.stat().st_mode & 0o077,0)

    def test_pending_has_no_evidence_credit(self):
        self.submit()
        self.assertEqual(self.db.assess('claim')['assessment']['state'],'NEITHER')

    def test_verified_support_requires_signature(self):
        self.submit();self.accept()
        self.assertEqual(self.db.assess('claim')['assessment']['state'],'SUPPORT_ONLY')

    def test_attacks_only(self):
        self.submit(polarity='attacks');self.accept()
        self.assertEqual(self.db.assess('claim')['assessment']['state'],'ATTACK_ONLY')

    def test_conflict_both(self):
        self.submit();self.accept()
        self.submit('s2','attacks',source='source-two',artifact=b'ORIGINAL B')
        self.accept('s2',artifact=b'ORIGINAL B')
        self.assertEqual(self.db.assess('claim')['assessment']['state'],'BOTH')

    def test_revocation_removes_credit_but_preserves_audit(self):
        self.submit();self.accept();self.accept(decision=Validation.REVOKED)
        self.assertEqual(self.db.assess('claim')['assessment']['state'],'NEITHER')
        self.assertEqual(self.db.check()['reviews'],2)

    def test_rejected_record_remains(self):
        self.submit();self.accept(decision=Validation.REJECTED)
        self.assertEqual(self.db.check()['reviews'],1)
        self.assertEqual(self.db.assess('claim')['assessment']['state'],'NEITHER')

    def test_unchanged_idempotent_retry(self):
        body=self.body()
        first=self.db.apply('submit',body,'unique-123',expected_revision=0)
        second=self.db.apply('submit',body,'unique-123',expected_revision=0)
        self.assertEqual(first,second)
        self.assertEqual(self.db.status()['revision'],1)

    def test_reused_id_different_request_rejected(self):
        self.db.apply('submit',self.body(),'unique-id')
        with self.assertRaises(DurableError):
            self.db.apply('submit',self.body('another'),'unique-id')
        self.assertEqual(self.db.status()['revision'],1)

    def test_stale_revision_rejected(self):
        self.submit()
        with self.assertRaises(DurableError):
            self.db.apply('submit',self.body('s2'),'other',expected_revision=0)
        self.assertEqual(self.db.status()['submissions'],1)

    def test_failed_write_is_rolled_back(self):
        with self.assertRaises(ValueError):
            self.db.apply('submit',self.body(polarity='depends_on'),'bad')
        self.assertEqual(self.db.status()['revision'],0)
        self.assertEqual(self.db.check()['submissions'],0)

    def test_sqlite_constraint_failure_is_atomic(self):
        self.db.conn.execute('CREATE TRIGGER block_events BEFORE INSERT ON evidence_events '
                             'BEGIN SELECT RAISE(ABORT,"blocked by test"); END')
        with self.assertRaises(sqlite3.DatabaseError): self.submit()
        self.assertEqual(self.db.check()['submissions'],0)
        self.assertEqual(self.db.status()['revision'],0)

    def test_signed_receipt_forgery_rejected(self):
        self.submit();receipt=self.sign()
        receipt['signature']='0'*64
        with self.assertRaises(ReviewError):
            self.db.apply('accept',{'receipt':receipt},'forgery')
        self.assertEqual(self.db.check()['reviews'],0)

    def test_wrong_claim_or_provenance_rejected(self):
        self.submit();receipt=self.sign();receipt['subject_digest']='a'*64
        with self.assertRaises(ReviewError):
            self.db.apply('accept',{'receipt':receipt},'tampered-receipt')

    def test_model_source_cannot_be_verified(self):
        self.submit(source_kind='model')
        with self.assertRaises(ReviewError):self.accept()
        self.assertEqual(self.db.check()['reviews'],0)

    def test_self_review_fails(self):
        self.submit(source='reviewer')
        with self.assertRaises(ReviewError):self.accept()

    def test_same_source_independent_credit_deduplicated(self):
        self.submit();self.accept()
        self.submit('s2',source_group='external-one',source='external-one',artifact=b'B')
        self.accept('s2',artifact=b'B')
        self.assertEqual(len(self.db.assess('claim')['assessment']['support_sources']),1)

    def test_original_bytes_stored_content_addressed(self):
        self.submit()
        rows=self.db.conn.execute('SELECT sha256,payload,size_bytes FROM artifacts').fetchall()
        self.assertEqual(len(rows),1)
        self.assertEqual(bytes(rows[0]['payload']),b'ORIGINAL A')
        self.assertEqual(rows[0]['size_bytes'],len(b'ORIGINAL A'))

    def test_missing_new_artifact_detected(self):
        self.submit();self.db.conn.execute('DELETE FROM artifacts')
        with self.assertRaises(DurableError): self.db.check()

    def test_modified_original_detected(self):
        self.submit();self.db.conn.execute('UPDATE artifacts SET payload=?',(b'TAMPERED!',))
        with self.assertRaises(DurableError): self.db.check()

    def test_modified_event_mirror_detected(self):
        self.submit();self.db.conn.execute('UPDATE evidence_events SET kind=? WHERE sequence=1',('faked',))
        with self.assertRaises(DurableError):self.db.status()

    def test_modified_submission_mirror_detected(self):
        self.submit();self.db.conn.execute('UPDATE evidence_submissions SET claim_id=?',('tampered',))
        with self.assertRaises(DurableError):self.db.status()

    def test_modified_receipt_mirror_detected(self):
        self.submit();self.accept()
        self.db.conn.execute('UPDATE evidence_reviews SET signature=?',('0'*64,))
        with self.assertRaises(DurableError):self.db.status()

    def test_rollback_anchor_detected(self):
        self.submit()
        with self.assertRaises(DurableError):self.db.check(expected_head='0'*64)
        self.assertTrue(self.db.check(expected_head=self.db.status()['evidence_audit_head'])['valid'])

    def test_persistence_reopen_and_verify(self):
        self.submit();self.accept();head=self.db.status()['evidence_audit_head']
        with EvidenceDatabase(self.path,self.boundary) as db2:
            self.assertEqual(db2.check(expected_head=head)['reviews'],1)
            self.assertEqual(db2.assess('claim')['assessment']['state'],'SUPPORT_ONLY')

    def test_multiple_handles_stale_write_guard(self):
        with EvidenceDatabase(self.path,self.boundary) as another:
            self.submit()
            with self.assertRaises(DurableError):
                another.apply('submit',self.body('s2'),'parallel',expected_revision=0)

    def test_legacy_empty_round_trip(self):
        original=EvidenceLedger(self.graph,self.boundary).to_dict()
        with EvidenceDatabase.import_legacy(self.root/'legacy.db',original,self.boundary) as migrated:
            self.assertEqual(migrated.check()['submissions'],0)

    def test_legacy_review_retained_and_missing_artifact_flagged(self):
        self.submit();self.accept()
        original=json.loads(self.db.conn.execute('SELECT document FROM ledger_snapshot').fetchone()[0])
        with EvidenceDatabase.import_legacy(self.root/'legacy.db',original,self.boundary) as migrated:
            self.assertEqual(migrated.check()['original_artifacts_unavailable'],['s1'])
            self.assertEqual(migrated.assess('claim')['assessment']['state'],'SUPPORT_ONLY')

    def test_legacy_modified_receipt_is_rejected(self):
        self.submit();self.accept()
        original=json.loads(self.db.conn.execute('SELECT document FROM ledger_snapshot').fetchone()[0])
        for event in original['events']:
            if event['kind']=='reviewed':event['payload']['reason']='altered'
        with self.assertRaises((ReviewError,ValueError)):
            EvidenceDatabase.import_legacy(self.root/'legacy.db',original,self.boundary)

    def test_forbidden_mutation_operation(self):
        with self.assertRaises(DurableError):
            self.db.apply('sign',{},'no-signing-allowed')


class VerificationServiceTests(DurableFixture):
    def setUp(self):
        super().setUp()
        self.socket=self.root/'verifier.sock'
        self.server=VerificationServer(self.socket,self.db)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self.finish)

    def finish(self):
        self.server.shutdown();self.thread.join(timeout=5);self.server.server_close()

    def test_socket_permissions(self):
        if os.name != 'nt': self.assertEqual(self.socket.stat().st_mode & 0o077,0)

    def test_service_refuses_existing_socket(self):
        with self.assertRaises(ServiceError):VerificationServer(self.socket,self.db)

    def test_no_signing_api(self):
        with self.assertRaises(ServiceError):call_service(self.socket,'sign',{})

    def test_exact_request_fields(self):
        with self.assertRaises(ServiceError):
            call_service(self.socket,'status',{'secret':'please'})

    def test_full_rpc_verified_in_two_steps(self):
        call_service(self.socket,'submit',self.body(),request_id='rpc-submit')
        c=call_service(self.socket,'challenge',{'submission_id':'s1'})
        self.assertTrue(c['artifact_available'])
        signed=sign_challenge(c,self.issuer,Validation.VERIFIED,'synthetic',artifact=b'ORIGINAL A')
        call_service(self.socket,'accept',{'receipt':signed},request_id='rpc-accept')
        out=call_service(self.socket,'assess',{'claim_id':'claim'})
        self.assertEqual(out['assessment']['state'],'SUPPORT_ONLY')
        self.assertEqual(call_service(self.socket,'verify')['reviews'],1)

    def test_socket_malformed_payload_fails_closed(self):
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
            sock.connect(str(self.socket));sock.sendall(b'{"op":\n')
            response=json.loads(sock.recv(1024))
            self.assertFalse(response['ok'])

    def test_socket_failed_write_does_not_corrupt(self):
        with self.assertRaises(ServiceError):
            call_service(self.socket,'submit',{'bogus':1},request_id='bad')
        self.assertEqual(call_service(self.socket,'status')['revision'],0)

    def test_operator_requires_original_for_verified(self):
        call_service(self.socket,'submit',self.body(),request_id='submission')
        c=call_service(self.socket,'challenge',{'submission_id':'s1'})
        with self.assertRaises(ReviewError):
            sign_challenge(c,self.issuer,Validation.VERIFIED,'reason')
        with self.assertRaises(ReviewError):
            sign_challenge(c,self.issuer,Validation.VERIFIED,'reason',artifact=b'WRONG')


class CredentialTests(unittest.TestCase):
    def test_key_files(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'signer.json'
            _write_new(p,{'schema_version':'rei0.signer.v1','key_id':'key','reviewer_id':'operator',
                          'secret_hex':('aa'*32)})
            self.assertEqual(load_signer(p).key_id,'key')
            if os.name != 'nt':
                os.chmod(p,0o644)
                with self.assertRaises(ReviewError):load_signer(p)

    def test_trust_file_owner_only(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'trust.json'
            _write_new(path,{'schema_version':'rei0.trust.v1','reviewers':[
                {'key_id':'key','reviewer_id':'operator','secret_hex':'aa'*32,
                 'can_verify':True,'can_revoke':True}]})
            self.assertIsInstance(load_trust(path),VerificationBoundary)
            with self.assertRaises(FileExistsError):_write_new(path,{'x':1})


if __name__ == '__main__':unittest.main()
