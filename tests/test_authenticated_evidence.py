"""REI-0.3 deterministic authenticated ingestion and review tests."""
from __future__ import annotations

import copy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from rei0 import (EdgeKind, EpistemicGraph, EvidenceLedger, EvidenceError,
                  EvidenceState, Node, NodeKind, Provenance, SourceKind,
                  Validation, ReviewIssuer, TrustedReviewer, VerificationBoundary,
                  ReviewError, ReviewReceipt)
from rei0.models import digest

T = '2026-11-10T19:30:00Z'
KEY = b'\xA1'*32

def make_case(max_nodes=100, max_edges=100):
    issuer=ReviewIssuer('review-key-1','independent-reviewer',KEY)
    boundary=VerificationBoundary({'review-key-1':TrustedReviewer('independent-reviewer',KEY)})
    g=EpistemicGraph(clock=lambda:T, max_nodes=max_nodes, max_edges=max_edges)
    g.add_node(Node('c',NodeKind.CLAIM,'The original claim',
                    Provenance('questioner',SourceKind.HUMAN,'question','prompt',T),T))
    return EvidenceLedger(g,boundary,clock=lambda:T),issuer,boundary

def add(ledger, submission='s1', source='study-1', group='study-1', kind=SourceKind.EXTERNAL,
        polarity=EdgeKind.SUPPORTS, artifact=b'original material', text='Observation A', reference=None):
    return ledger.submit(submission_id=submission,evidence_id='e:'+submission, claim_id='c',
                         text=text, artifact_bytes=artifact,
                         provenance=Provenance(source,kind,group,reference or 'doi:'+source,T),
                         polarity=polarity)

class AuthenticatedEvidenceTests(unittest.TestCase):
    def test_pending_neither(self):
        ledger,issuer,_=make_case(); add(ledger)
        self.assertEqual(ledger.assess('c').state,EvidenceState.NEITHER)
        self.assertEqual(ledger.graph.assess('c').state,EvidenceState.NEITHER)

    def test_review_moves_to_support_only(self):
        ledger,issuer,_=make_case(); add(ledger)
        r=ledger.issue_and_accept(issuer,'s1',Validation.VERIFIED,'checked artifact and source')
        self.assertEqual(len(r.signature),64)
        self.assertEqual(ledger.assess('c').state,EvidenceState.SUPPORT_ONLY)
        # Do not let the old unauthenticated graph assess treat review receipts as native validation flags.
        self.assertEqual(ledger.graph.assess('c').state,EvidenceState.NEITHER)

    def test_all_four_states(self):
        ledger,issuer,_=make_case()
        self.assertEqual(ledger.assess('c').state,EvidenceState.NEITHER)
        add(ledger); ledger.issue_and_accept(issuer,'s1',Validation.VERIFIED,'approved')
        self.assertEqual(ledger.assess('c').state,EvidenceState.SUPPORT_ONLY)
        add(ledger,'s2','independent','independent',polarity=EdgeKind.ATTACKS,artifact=b'different material',text='Counter-observation')
        ledger.issue_and_accept(issuer,'s2',Validation.VERIFIED,'approved')
        self.assertEqual(ledger.assess('c').state,EvidenceState.BOTH)
        ledger.issue_and_accept(issuer,'s1',Validation.REVOKED,'withdrawn')
        self.assertEqual(ledger.assess('c').state,EvidenceState.ATTACK_ONLY)

    def test_revoke_returns_neither(self):
        ledger,issuer,_=make_case(); add(ledger)
        ledger.issue_and_accept(issuer,'s1',Validation.VERIFIED,'accepted')
        ledger.issue_and_accept(issuer,'s1',Validation.REVOKED,'retracted')
        self.assertEqual(ledger.assess('c').state,EvidenceState.NEITHER)
        self.assertEqual([x.decision for x in ledger.review_receipts],
                         [Validation.VERIFIED,Validation.REVOKED])

    def test_rejected_does_not_count(self):
        ledger,issuer,_=make_case(); add(ledger)
        ledger.issue_and_accept(issuer,'s1',Validation.REJECTED,'non-verifiable')
        self.assertEqual(ledger.assess('c').state,EvidenceState.NEITHER)

    def test_rejected_cannot_be_revoked_or_verified(self):
        ledger,issuer,_=make_case(); add(ledger)
        ledger.issue_and_accept(issuer,'s1',Validation.REJECTED,'wrong source')
        for decision in (Validation.VERIFIED, Validation.REVOKED):
            with self.assertRaises(ReviewError):
                ledger.issue_and_accept(issuer,'s1',decision,'wrong second review')

    def test_review_cannot_be_approved_twice(self):
        ledger,issuer,_=make_case(); add(ledger)
        ledger.issue_and_accept(issuer,'s1',Validation.VERIFIED,'approved')
        with self.assertRaises(ReviewError):
            ledger.issue_and_accept(issuer,'s1',Validation.VERIFIED,'again')

    def test_source_cannot_self_review(self):
        ledger,_,boundary=make_case()
        add(ledger,source='independent-reviewer')
        issuer=ReviewIssuer('review-key-1','independent-reviewer',KEY)
        with self.assertRaisesRegex(ReviewError,'own submission'):
            ledger.issue_and_accept(issuer,'s1',Validation.VERIFIED,'approved')

    def test_model_source_cannot_be_verified(self):
        ledger,issuer,_=make_case(); add(ledger,kind=SourceKind.MODEL)
        with self.assertRaisesRegex(ReviewError,'model-generated'):
            ledger.issue_and_accept(issuer,'s1',Validation.VERIFIED,'attempted laundering')
        self.assertEqual(ledger.assess('c').state,EvidenceState.NEITHER)

    def test_legacy_caller_declared_verification_has_no_trusted_effect(self):
        ledger,_,_=make_case(); s=add(ledger)
        ledger.graph.set_validation('node',s.evidence_id,Validation.VERIFIED,
                                    verified_by='caller',reason='unsafe old mechanism')
        ledger.graph.set_validation('edge',s.link_id,Validation.VERIFIED,
                                    verified_by='caller',reason='unsafe old mechanism')
        self.assertEqual(ledger.graph.assess('c').state,EvidenceState.SUPPORT_ONLY)
        self.assertEqual(ledger.assess('c').state,EvidenceState.NEITHER)

    def test_wrong_signature_rejected(self):
        ledger,issuer,_=make_case();add(ledger)
        signed=issuer.issue(submission_id='s1',subject_digest=ledger.subject_digest('s1'),
                             decision=Validation.VERIFIED,reason='approved',issued_at=T,
                             decision_index=1,prior_signature='0'*64)
        data=signed.to_dict(); data['signature']='f'*64
        with self.assertRaisesRegex(ReviewError,'authentication'):
            ledger.accept(ReviewReceipt.from_dict(data))

    def test_signed_subject_cannot_be_rebound_to_other_claim(self):
        ledger,issuer,_=make_case();add(ledger)
        r=ledger.issue_and_accept(issuer,'s1',Validation.VERIFIED,'approved')
        doc=ledger.to_dict()
        # New claim cannot substitute for signed target without breaking signature.
        doc['events'][0]['payload']['claim_id']='different'
        # Recomputing the unkeyed event hash is not enough to forge an authenticated review.
        doc['events'][0]['event_hash']=digest({k:doc['events'][0][k] for k in ('sequence','previous_hash','kind','payload')})
        with self.assertRaises((ReviewError,EvidenceError)):
            EvidenceLedger.from_dict(doc,ledger._boundary)

    def test_tampered_review_rationale_rehashed_is_rejected(self):
        ledger,issuer,boundary=make_case();add(ledger)
        ledger.issue_and_accept(issuer,'s1',Validation.VERIFIED,'verified original')
        doc=ledger.to_dict(); doc['events'][1]['payload']['reason']='fabricated decision'
        doc['events'][1]['event_hash']=digest({k:doc['events'][1][k] for k in ('sequence','previous_hash','kind','payload')})
        with self.assertRaisesRegex(ReviewError,'authentication'):
            EvidenceLedger.from_dict(doc,boundary)

    def test_replay_tampered_graph_claim_fails(self):
        ledger,issuer,boundary=make_case();add(ledger)
        ledger.issue_and_accept(issuer,'s1',Validation.VERIFIED,'approved')
        doc=ledger.to_dict();graph=doc['graph']
        # Alter original claim and recompute complete graph hash chain.
        prev='0'*64
        for rec in graph['events']:
            if rec['kind']=='add_node' and rec['payload']['id']=='c':
                rec['payload']['text']='Changed claim!'
            rec['previous_hash']=prev
            rec['event_hash']=digest({k:rec[k] for k in ('sequence','previous_hash','kind','payload')})
            prev=rec['event_hash']
        with self.assertRaisesRegex(ReviewError,'subject'):
            EvidenceLedger.from_dict(doc,boundary)

    def test_unregistered_key_fails_closed(self):
        ledger,issuer,boundary=make_case();add(ledger)
        ledger.issue_and_accept(issuer,'s1',Validation.VERIFIED,'checked')
        wrong=VerificationBoundary({'other':TrustedReviewer('other-person',b'Z'*32)})
        with self.assertRaisesRegex(ReviewError,'untrusted signing key'):
            EvidenceLedger.from_dict(ledger.to_dict(),wrong)

    def test_wrong_key_same_identity_fails(self):
        ledger,issuer,boundary=make_case();add(ledger)
        ledger.issue_and_accept(issuer,'s1',Validation.VERIFIED,'checked')
        wrong=VerificationBoundary({'review-key-1':TrustedReviewer('independent-reviewer',b'Z'*32)})
        with self.assertRaisesRegex(ReviewError,'authentication'):
            EvidenceLedger.from_dict(ledger.to_dict(),wrong)

    def test_reviewer_id_mismatch(self):
        ledger,issuer,_=make_case();add(ledger)
        other=ReviewIssuer('review-key-1','pretend-reviewer',KEY)
        with self.assertRaisesRegex(ReviewError,'reviewer ID'):
            ledger.issue_and_accept(other,'s1',Validation.VERIFIED,'not permitted')

    def test_no_verification_permission(self):
        ledger,issuer,_=make_case();add(ledger)
        boundary=VerificationBoundary({'review-key-1':TrustedReviewer('independent-reviewer',KEY,can_verify=False)})
        ledger._boundary=boundary
        with self.assertRaisesRegex(ReviewError,'permission'):
            ledger.issue_and_accept(issuer,'s1',Validation.VERIFIED,'approved')

    def test_no_revocation_permission(self):
        ledger,issuer,_=make_case();add(ledger)
        ledger.issue_and_accept(issuer,'s1',Validation.VERIFIED,'approved')
        ledger._boundary=VerificationBoundary({'review-key-1':TrustedReviewer('independent-reviewer',KEY,can_revoke=False)})
        with self.assertRaisesRegex(ReviewError,'revocation permission'):
            ledger.issue_and_accept(issuer,'s1',Validation.REVOKED,'prohibited')

    def test_replay_stale_receipt_fails(self):
        ledger,issuer,_=make_case();add(ledger)
        r=ledger.issue_and_accept(issuer,'s1',Validation.VERIFIED,'first')
        with self.assertRaisesRegex(ReviewError,'sequence'):
            ledger.accept(r)

    def test_review_time_cannot_precede_submission(self):
        ledger,issuer,_=make_case(); add(ledger)
        receipt=issuer.issue(submission_id='s1',subject_digest=ledger.subject_digest('s1'),
                             decision=Validation.VERIFIED,reason='checked',
                             issued_at='2026-11-09T19:30:00Z',decision_index=1,
                             prior_signature='0'*64)
        with self.assertRaisesRegex(ReviewError,'precedes evidence'):
            ledger.accept(receipt)

    def test_revocation_time_must_follow_previous_review(self):
        ledger,issuer,_=make_case(); add(ledger)
        r=ledger.issue_and_accept(issuer,'s1',Validation.VERIFIED,'approved')
        receipt=issuer.issue(submission_id='s1',subject_digest=ledger.subject_digest('s1'),
                             decision=Validation.REVOKED,reason='withdrawn',
                             issued_at='2026-11-09T19:30:00Z',decision_index=2,
                             prior_signature=r.signature)
        with self.assertRaisesRegex(ReviewError,'precedes'):
            ledger.accept(receipt)

    def test_roundtrip_exact_stable_and_replay(self):
        ledger,issuer,boundary=make_case();add(ledger)
        ledger.issue_and_accept(issuer,'s1',Validation.VERIFIED,'checked')
        a=EvidenceLedger.from_dict(ledger.to_dict(),boundary,clock=lambda:T)
        self.assertEqual(a.to_dict(),ledger.to_dict())
        self.assertEqual(a.assess('c'),ledger.assess('c'))
        self.assertEqual(a.audit_head,ledger.audit_head)

    def test_graph_cycle_detector_preserved(self):
        ledger,_,_=make_case();add(ledger)
        self.assertEqual(len(ledger.graph.nodes),2)
        self.assertEqual(len(ledger.graph.edges),1)

    def test_source_group_deduplication(self):
        ledger,issuer,_=make_case()
        add(ledger);add(ledger,'s2','different-source','study-1',artifact=b'different',text='Second observation')
        for sid in ('s1','s2'): ledger.issue_and_accept(issuer,sid,Validation.VERIFIED,'checked')
        result=ledger.assess('c')
        self.assertEqual(len(result.support_sources),1)
        self.assertIn('dependent_or_duplicate_source',[reason for _,reason in result.ignored_edges])

    def test_exact_artifact_deduplication_across_groups(self):
        ledger,issuer,_=make_case()
        add(ledger);add(ledger,'s2','other','other',artifact=b'original material',text='Different rephrasing')
        for sid in ('s1','s2'):ledger.issue_and_accept(issuer,sid,Validation.VERIFIED,'checked')
        self.assertEqual(len(ledger.assess('c').support_sources),1)

    def test_exact_text_deduplication_across_groups(self):
        ledger,issuer,_=make_case()
        add(ledger);add(ledger,'s2','other','other',artifact=b'other',text='Observation A')
        for sid in ('s1','s2'):ledger.issue_and_accept(issuer,sid,Validation.VERIFIED,'checked')
        self.assertEqual(len(ledger.assess('c').support_sources),1)

    def test_reference_deduplication_across_groups(self):
        ledger,issuer,_=make_case()
        add(ledger,reference='doi:identical');add(ledger,'s2','other','other',artifact=b'other',text='Different',reference='doi:identical')
        for sid in ('s1','s2'):ledger.issue_and_accept(issuer,sid,Validation.VERIFIED,'checked')
        self.assertEqual(len(ledger.assess('c').support_sources),1)

    def test_distinct_supports_count_independent(self):
        ledger,issuer,_=make_case()
        add(ledger);add(ledger,'s2','other','other',artifact=b'other',text='Different')
        for sid in ('s1','s2'):ledger.issue_and_accept(issuer,sid,Validation.VERIFIED,'checked')
        self.assertEqual(len(ledger.assess('c').support_sources),2)

    def test_invalid_artifact_and_fields_do_not_mutate(self):
        ledger,_,_=make_case()
        for value in (b'',b'z'*2_000_001,'not bytes'):
            with self.assertRaises(EvidenceError):
                add(ledger, artifact=value)
        self.assertEqual(len(ledger.graph.nodes),1)
        self.assertEqual(len(ledger.events),0)

    def test_invalid_graph_budget_no_partial_node(self):
        ledger,_,_=make_case(max_nodes=1)
        with self.assertRaises(EvidenceError):add(ledger)
        self.assertEqual(len(ledger.graph.nodes),1)
        self.assertEqual(len(ledger.graph.events),1)

    def test_duplicate_submission_rejected_without_mutation(self):
        ledger,_,_=make_case();add(ledger)
        original=ledger.to_dict()
        with self.assertRaises(EvidenceError):add(ledger)
        self.assertEqual(ledger.to_dict(),original)

    def test_event_hash_tamper_rejected(self):
        ledger,_,boundary=make_case();add(ledger)
        doc=ledger.to_dict();doc['events'][0]['payload']['artifact_sha256']='f'*64
        with self.assertRaisesRegex(EvidenceError,'hash'):
            EvidenceLedger.from_dict(doc,boundary)

    def test_secret_requirements(self):
        with self.assertRaises(ReviewError):ReviewIssuer('k','reviewer',b'bad')
        with self.assertRaises(ReviewError):VerificationBoundary({})

    def test_invalid_review_payload_keys(self):
        ledger,issuer,_=make_case();add(ledger)
        r=issuer.issue(submission_id='s1',subject_digest=ledger.subject_digest('s1'),
                       decision=Validation.VERIFIED,reason='checked',issued_at=T,
                       decision_index=1,prior_signature='0'*64)
        value=r.to_dict();value['grants_admin']=True
        with self.assertRaises(ReviewError):ReviewReceipt.from_dict(value)

    def test_signed_revoke_changes_state_after_roundtrip(self):
        ledger,issuer,boundary=make_case();add(ledger)
        ledger.issue_and_accept(issuer,'s1',Validation.VERIFIED,'checked')
        ledger.issue_and_accept(issuer,'s1',Validation.REVOKED,'wrong original')
        a=EvidenceLedger.from_dict(ledger.to_dict(),boundary)
        self.assertEqual(a.assess('c').state,EvidenceState.NEITHER)

    def test_artifact_hash_matches_original_bytes(self):
        ledger,_,_=make_case();s=add(ledger)
        self.assertEqual(s.artifact_sha256,sha256(b'original material').hexdigest())

    def test_serialized_ledger_contains_no_review_secret(self):
        ledger,issuer,_=make_case();add(ledger)
        ledger.issue_and_accept(issuer,'s1',Validation.VERIFIED,'checked')
        self.assertNotIn(KEY.hex(),json.dumps(ledger.to_dict()))

if __name__ == '__main__':
    unittest.main()
