"""REI-0.6: independent signed rule approval, defeasible propagation, revocation."""
import argparse
import json
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from rei0.graph import EpistemicGraph
from rei0.models import Node,NodeKind,Provenance,SourceKind,Validation,EdgeKind,digest
from rei0.review import (Ed25519ReviewIssuer,Ed25519TrustedReviewer,VerificationBoundary,
                         TrustedReviewer,ReviewIssuer,ReviewError)
from rei0.evidence import EvidenceLedger
from rei0.durable import EvidenceDatabase
from rei0.revision import (InferenceRule,RuleAuthority,RevisionEngine,RevisionJournal,
                           RevisionError,sign_inference_rule)
from rei0.revision_cli import run_revision

AT='2026-11-10T21:00:00Z'


class BaseRevision(unittest.TestCase):
    def setUp(self):
        self.issuer=Ed25519ReviewIssuer.generate('reviewer-key','auditor')
        self.boundary=VerificationBoundary({'reviewer-key':Ed25519TrustedReviewer(
            'auditor',self.issuer.public_key_bytes())})
        self.authority=RuleAuthority.from_boundary(self.boundary)
        self.graph=EpistemicGraph('m-2026',clock=lambda:AT)
        provenance=Provenance('user',SourceKind.HUMAN,'user','fixture:question',AT)
        for cid in ('a','b','c','d'):
            self.graph.add_node(Node(cid,NodeKind.CLAIM,'Hypothesis '+cid,provenance,AT))
        self.ledger=EvidenceLedger(self.graph,self.boundary,clock=lambda:AT)
        self.n=0

    def evidence(self,claim='a',polarity=EdgeKind.SUPPORTS,source='sensor-A',approve=True):
        self.n+=1
        sid=f'sub-{self.n}'
        p=Provenance(source,SourceKind.EXTERNAL,source,'fixture:'+source,AT)
        self.ledger.submit(submission_id=sid,evidence_id=f'ev-{self.n}',claim_id=claim,
            text=f'Synthetic record {self.n}',artifact_bytes=f'artifact-{self.n}'.encode(),
            provenance=p,polarity=polarity)
        if approve:
            self.review(sid,Validation.VERIFIED)
        return sid

    def review(self,sid,decision):
        previous=[r for r in self.ledger.review_receipts if r.submission_id==sid]
        r=self.issuer.issue(submission_id=sid,subject_digest=self.ledger.subject_digest(sid),
            decision=decision,reason='Reviewed synthetic fixture',issued_at=AT,
            decision_index=len(previous)+1,
            prior_signature=previous[-1].signature if previous else '0'*64)
        self.ledger.accept(r)

    def rule(self,rid='r1',premises=('a',),conclusion='b',polarity='supports'):
        return sign_inference_rule(issuer=self.issuer,rule_id=rid,premises=premises,
            conclusion=conclusion,polarity=polarity,method_version=self.graph.method_version,
            rationale='Human-reviewed conditional assumption',issued_at=AT)

    def run_revision(self,rules=None):
        return RevisionEngine(self.ledger,rules or [],self.authority).evaluate()


class RevisionTests(BaseRevision):
    def test_direct_neither_and_signed_support(self):
        self.assertEqual(self.run_revision()['assessments']['a']['state'],'NEITHER')
        self.evidence()
        out=self.run_revision()['assessments']
        self.assertEqual(out['a']['state'],'SUPPORT_ONLY')
        self.assertEqual(out['b']['state'],'NEITHER')
        self.assertEqual(out['a']['confidence'],None)

    def test_pending_evidence_does_not_count(self):
        self.evidence(approve=False)
        self.assertEqual(self.run_revision()['assessments']['a']['state'],'NEITHER')

    def test_signed_authorized_rule_propagates_support(self):
        self.evidence()
        state=self.run_revision([self.rule()])['assessments']['b']
        self.assertEqual(state['state'],'SUPPORT_ONLY')
        self.assertEqual(state['direct_state'],'NEITHER')
        self.assertEqual(state['derived_support_rules'],['r1'])
        self.assertEqual(state['support_evidence'],[])

    def test_support_chain(self):
        self.evidence()
        rules=[self.rule(),self.rule('r2',('b',),'c')]
        out=self.run_revision(rules)['assessments']
        self.assertEqual(out['c']['state'],'SUPPORT_ONLY')
        self.assertEqual(out['c']['derived_support_rules'],['r2'])

    def test_conjunctive_premises(self):
        self.evidence('a')
        rule=self.rule('r',('a','c'),'b')
        self.assertEqual(self.run_revision([rule])['assessments']['b']['state'],'NEITHER')
        self.evidence('c',source='sensor-C')
        self.assertEqual(self.run_revision([rule])['assessments']['b']['state'],'SUPPORT_ONLY')

    def test_both_blocks_downstream_inference(self):
        pos=self.evidence()
        neg=self.evidence(polarity=EdgeKind.ATTACKS,source='sensor-B')
        state=self.run_revision([self.rule()])['assessments']
        self.assertEqual(state['a']['state'],'BOTH')
        self.assertEqual(state['b']['state'],'NEITHER')
        self.assertEqual(state['b']['blocked_rules'][0]['premises'],['a'])
        self.review(neg,Validation.REVOKED)
        state=self.run_revision([self.rule()])['assessments']
        self.assertEqual(state['a']['state'],'SUPPORT_ONLY')
        self.assertEqual(state['b']['state'],'SUPPORT_ONLY')
        self.review(pos,Validation.REVOKED)
        state=self.run_revision([self.rule()])['assessments']
        self.assertEqual(state['a']['state'],'NEITHER')
        self.assertEqual(state['b']['state'],'NEITHER')

    def test_rejected_and_revoked_stay_out(self):
        self.evidence(approve=False)
        sid='sub-1';self.review(sid,Validation.REJECTED)
        self.assertEqual(self.run_revision()['assessments']['a']['state'],'NEITHER')

    def test_direct_attack_and_derived_support_yield_both(self):
        self.evidence('a')
        self.evidence('b',EdgeKind.ATTACKS,'sensor-B')
        state=self.run_revision([self.rule()])['assessments']['b']
        self.assertEqual(state['state'],'BOTH')
        self.assertEqual(state['direct_state'],'ATTACK_ONLY')

    def test_signed_attack_rule(self):
        self.evidence()
        state=self.run_revision([self.rule(polarity='attacks')])['assessments']['b']
        self.assertEqual(state['state'],'ATTACK_ONLY')
        self.assertEqual(state['derived_attack_rules'],['r1'])

    def test_attack_premise_does_not_support_rule(self):
        self.evidence(polarity=EdgeKind.ATTACKS)
        self.assertEqual(self.run_revision([self.rule()])['assessments']['b']['state'],'NEITHER')

    def test_isolated_contradiction_cannot_explode(self):
        self.evidence('a')
        self.evidence('a',EdgeKind.ATTACKS,'sensor-B')
        out=self.run_revision([self.rule()])['assessments']
        self.assertEqual(out['a']['state'],'BOTH')
        self.assertEqual(out['c']['state'],'NEITHER')
        self.assertEqual(out['d']['state'],'NEITHER')

    def test_unauthorized_method_or_tampered_rule_rejected(self):
        rule=self.rule()
        wrong=InferenceRule.from_dict({**rule.to_dict(),'rationale':'Unreviewed replacement'})
        with self.assertRaises(RevisionError):self.run_revision([wrong])
        with self.assertRaises(RevisionError):self.run_revision([replace(rule,method_version='other')])
        other=Ed25519ReviewIssuer.generate('reviewer-key','auditor')
        forged=sign_inference_rule(issuer=other,rule_id='r1',premises=['a'],conclusion='b',
            polarity='supports',method_version='m-2026',rationale='other',issued_at=AT)
        with self.assertRaises(RevisionError):self.run_revision([forged])

    def test_symmetric_rule_authority_rejected(self):
        with self.assertRaises(RevisionError):
            RuleAuthority({'legacy':TrustedReviewer('auditor',b'0'*32)})

    def test_cycle_detection_direct_and_indirect(self):
        with self.assertRaises(RevisionError):self.run_revision([
            self.rule('r1',('a',),'b'),self.rule('r2',('b',),'a')])
        with self.assertRaises(RevisionError):self.run_revision([
            self.rule('r1',('a',),'b'),self.rule('r2',('b',),'c'),self.rule('r3',('c',),'a')])

    def test_duplicate_rule_rejected(self):
        r=self.rule()
        with self.assertRaises(RevisionError):self.run_revision([r,r])

    def test_unknown_premise_rejected(self):
        with self.assertRaises(RevisionError):self.run_revision([
            self.rule('r1',('unknown',),'b')])

    def test_rule_budgets(self):
        with self.assertRaises(RevisionError):
            RevisionEngine(self.ledger,[self.rule()],self.authority,max_rules=0)
        with self.assertRaises(RevisionError):
            RevisionEngine(self.ledger,[],self.authority,max_claims=1)

    def test_rule_serialization_strict(self):
        r=self.rule();self.assertEqual(InferenceRule.from_dict(r.to_dict()),r)
        for change in ({'unexpected':True},{'premises':['b','a']},{'signature':'0'*128}):
            d=r.to_dict();d.update(change)
            if change=={'signature':'0'*128}:
                with self.assertRaises(RevisionError):self.authority.verify(InferenceRule.from_dict(d))
            else:
                with self.assertRaises(RevisionError):InferenceRule.from_dict(d)

    def test_duplicate_evidence_source_not_double_counted(self):
        self.evidence(source='sensor-A')
        self.evidence(source='sensor-A')
        out=self.run_revision()['assessments']['a']
        self.assertEqual(out['state'],'SUPPORT_ONLY')
        self.assertEqual(len(out['support_evidence']),1)

    def test_trusted_ledger_excludes_model_generated_data(self):
        self.n+=1
        prov=Provenance('model',SourceKind.MODEL,'model','fixture:model',AT)
        self.ledger.submit(submission_id='fake',evidence_id='fake-ev',claim_id='a',
            text='Language model says so',artifact_bytes=b'fake',provenance=prov,
            polarity=EdgeKind.SUPPORTS)
        with self.assertRaises(ReviewError):self.review('fake',Validation.VERIFIED)
        self.assertEqual(self.run_revision()['assessments']['a']['state'],'NEITHER')

    def test_journal_replay_diffs_and_noop(self):
        journal=RevisionJournal();r=self.rule()
        initial=self.run_revision([r])
        self.assertTrue(journal.record(initial)['recorded'])
        self.assertFalse(journal.record(initial)['recorded'])
        self.evidence()
        changed=self.run_revision([r])
        transition=journal.record(changed)
        self.assertEqual(len(transition['changes']),2)
        self.assertEqual(transition['changes'][0]['claim_id'],'a')
        self.assertEqual(transition['changes'][1]['claim_id'],'b')
        replay=RevisionJournal.from_dict(journal.to_dict(),expected_head=journal.audit_head)
        self.assertEqual(replay.latest,changed)

    def test_journal_integrity_and_external_anchor(self):
        journal=RevisionJournal();journal.record(self.run_revision())
        data=journal.to_dict()
        data['events'][0]['payload']['report']['assessments']['a']['state']='BOTH'
        with self.assertRaises(RevisionError):RevisionJournal.from_dict(data)
        original=journal.to_dict()
        with self.assertRaises(RevisionError):RevisionJournal.from_dict(original,expected_head='0'*64)

    def test_journal_tampered_explanation_even_with_hash_rejected(self):
        journal=RevisionJournal();journal.record(self.run_revision())
        self.evidence();journal.record(self.run_revision())
        obj=journal.to_dict()
        obj['events'][1]['payload']['changes']=[]
        obj['events'][1]['event_hash']=digest({k:obj['events'][1][k]
            for k in ('sequence','previous_hash','kind','payload')})
        with self.assertRaises(RevisionError):RevisionJournal.from_dict(obj)

    def test_database_legacy_migration_compatible(self):
        self.evidence()
        with tempfile.TemporaryDirectory() as d:
            with EvidenceDatabase.import_legacy(Path(d)/'evidence.sqlite',
                         self.ledger.to_dict(),self.boundary) as db:
                report=RevisionEngine.from_database(db,[self.rule()],self.authority).evaluate()
                self.assertEqual(report['assessments']['b']['state'],'SUPPORT_ONLY')
                self.assertEqual(db.check()['reviews'],1)

    def test_durable_db_accept_and_revoke_propagates(self):
        import base64
        from rei0.graph import utc_now
        with tempfile.TemporaryDirectory() as td:
            with EvidenceDatabase.initialize(Path(td)/'ledger.sqlite',self.graph,self.boundary) as db:
                def submit(n,polarity):
                    body={'submission_id':f's{n}','evidence_id':f'e{n}',
                        'claim_id':'a','text':f'Synthetic {n}',
                        'artifact_b64':base64.b64encode(f'artifact-{n}'.encode()).decode(),
                        'provenance':Provenance(f'source-{n}',SourceKind.EXTERNAL,
                            f'source-{n}',f'fixture:{n}',AT).to_dict(),
                        'polarity':polarity}
                    db.apply('submit',body,f'submit-{n}')
                    ch=db.challenge(f's{n}')
                    receipt=self.issuer.issue(submission_id=f's{n}',
                        subject_digest=ch['subject_digest'],decision=Validation.VERIFIED,
                        reason='Checked fixture',issued_at=utc_now(),
                        decision_index=ch['decision_index'],prior_signature=ch['prior_signature'])
                    db.apply('accept',{'receipt':receipt.to_dict()},f'accept-{n}')
                signed=[self.rule()]
                submit(1,'supports')
                first=RevisionEngine.from_database(db,signed,self.authority).evaluate()
                self.assertEqual(first['assessments']['b']['state'],'SUPPORT_ONLY')
                submit(2,'attacks')
                second=RevisionEngine.from_database(db,signed,self.authority).evaluate()
                self.assertEqual(second['assessments']['a']['state'],'BOTH')
                self.assertEqual(second['assessments']['b']['state'],'NEITHER')
                ch=db.challenge('s2')
                revoke=self.issuer.issue(submission_id='s2',
                    subject_digest=ch['subject_digest'],decision=Validation.REVOKED,
                    reason='Retracted synthetic source',issued_at=utc_now(),
                    decision_index=ch['decision_index'],prior_signature=ch['prior_signature'])
                db.apply('accept',{'receipt':revoke.to_dict()},'revoke-2')
                third=RevisionEngine.from_database(db,signed,self.authority).evaluate()
                self.assertEqual(third['assessments']['b']['state'],'SUPPORT_ONLY')
                j=RevisionJournal()
                for snapshot in (first,second,third):j.record(snapshot)
                self.assertEqual(len(j.events),3)
                self.assertEqual(j.events[1]['payload']['changes'][0]['to'],'BOTH')
                self.assertTrue(db.check()['valid'])

    def test_legacy_hmac_direct_only_evidence_compatible(self):
        key=b'legacy-secret-key-32-bytes-minimum!!!!'
        issuer=ReviewIssuer('old','legacy-auditor',key)
        boundary=VerificationBoundary({'old':TrustedReviewer('legacy-auditor',key)})
        graph=EpistemicGraph(clock=lambda:AT)
        p=Provenance('user',SourceKind.HUMAN,'user','fixture:question',AT)
        graph.add_node(Node('claim',NodeKind.CLAIM,'Legacy claim',p,AT))
        ledger=EvidenceLedger(graph,boundary,clock=lambda:AT)
        ep=Provenance('external',SourceKind.EXTERNAL,'external','fixture:data',AT)
        ledger.submit(submission_id='sub',evidence_id='ev',claim_id='claim',text='Data',
                      artifact_bytes=b'record',provenance=ep,polarity=EdgeKind.SUPPORTS)
        receipt=issuer.issue(submission_id='sub',subject_digest=ledger.subject_digest('sub'),
             decision=Validation.VERIFIED,reason='Legacy review',issued_at=AT,
             decision_index=1,prior_signature='0'*64)
        ledger.accept(receipt)
        result=RevisionEngine(ledger,[],RuleAuthority.from_boundary(boundary)).evaluate()
        self.assertEqual(result['assessments']['claim']['state'],'SUPPORT_ONLY')

    def test_rule_reordering_deterministic(self):
        self.evidence()
        x=self.rule('rule-x',('a',),'c')
        y=self.rule('rule-y',('a',),'b')
        self.assertEqual(self.run_revision([x,y]),self.run_revision([y,x]))

    def test_rule_change_is_recorded_even_without_status_change(self):
        j=RevisionJournal();j.record(self.run_revision())
        r=self.rule()
        update=j.record(self.run_revision([r]))
        self.assertTrue(update['recorded'])
        self.assertEqual(len(update['changes']),1)
        self.assertEqual(update['changes'][0]['from'],'NEITHER')
        self.assertEqual(update['changes'][0]['to'],'NEITHER')
        self.assertIn('blocked_rules',update['changes'][0]['changes'])


class RevisionCLITests(BaseRevision):
    def test_offline_rule_sign_and_saved_db_evaluation(self):
        self.evidence()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/'signer.json').write_text(json.dumps({
                'schema_version':'rei0.signer.v2','key_id':'reviewer-key',
                'reviewer_id':'auditor','private_hex':self.issuer.private_key_bytes().hex()}))
            (root/'trust.json').write_text(json.dumps({'schema_version':'rei0.trust.v2',
                'reviewers':[{'key_id':'reviewer-key','reviewer_id':'auditor',
                    'public_hex':self.issuer.public_key_bytes().hex(),
                    'can_verify':True,'can_revoke':True}]}))
            (root/'signer.json').chmod(0o600)
            (root/'trust.json').chmod(0o600)
            (root/'unsigned.json').write_text(json.dumps({
                'rule_id':'r1','premises':['a'],'conclusion':'b','polarity':'supports',
                'method_version':'m-2026','rationale':'Operator approved',
                'issued_at':AT}))
            args=argparse.Namespace(command='revision-rule-sign',signer=root/'signer.json',
                rule=root/'unsigned.json',output=root/'rule.json')
            out=run_revision(args);self.assertTrue(out['signed'])
            signed=json.loads((root/'rule.json').read_text())
            (root/'rules.json').write_text(json.dumps([signed]))
            with EvidenceDatabase.import_legacy(root/'evidence.sqlite',self.ledger.to_dict(),
                    self.boundary) as db:
                pass
            assess=argparse.Namespace(command='revision-assess',database=root/'evidence.sqlite',
                trust=root/'trust.json',rules=root/'rules.json',journal=root/'journal.json',
                expected_journal_head=None,expected_rule_set_hash=None)
            output=run_revision(assess)
            self.assertEqual(output['report']['assessments']['b']['state'],'SUPPORT_ONLY')
            self.assertTrue(output['transition']['recorded'])
            output2=run_revision(assess)
            self.assertFalse(output2['transition']['recorded'])
            head=output['transition']['audit_head']
            check=run_revision(argparse.Namespace(command='revision-verify',
                journal=root/'journal.json',expected_head=head))
            self.assertEqual(check['revision_events'],1)
            verified=run_revision(argparse.Namespace(command='revision-verify',
                journal=root/'journal.json',expected_head=head,trust=root/'trust.json'))
            self.assertTrue(verified['rule_signatures_verified'])
            bad=Ed25519ReviewIssuer.generate('reviewer-key','auditor')
            (root/'wrong-trust.json').write_text(json.dumps({
                'schema_version':'rei0.trust.v2','reviewers':[{
                  'key_id':'reviewer-key','reviewer_id':'auditor',
                  'public_hex':bad.public_key_bytes().hex(),
                  'can_verify':True,'can_revoke':True}]}))
            (root/'wrong-trust.json').chmod(0o600)
            with self.assertRaises(RevisionError):run_revision(argparse.Namespace(
                command='revision-verify',journal=root/'journal.json',
                expected_head=head,trust=root/'wrong-trust.json'))
            assess.expected_rule_set_hash='0'*64
            with self.assertRaises(RevisionError):run_revision(assess)
            assess.expected_rule_set_hash=None
            assess.expected_evidence_head='0'*64
            with self.assertRaises(ValueError):run_revision(assess)


if __name__=='__main__':unittest.main()
