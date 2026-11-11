"""REI-0.6 operator CLI; signing occurs only in an explicit offline command."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import os
import tempfile

from .durable import EvidenceDatabase
from .graph import EpistemicGraph
from .models import Node,NodeKind,Provenance,SourceKind,Validation,EdgeKind
from .review import Ed25519ReviewIssuer,Ed25519TrustedReviewer,VerificationBoundary
from .service_cli import load_trust,load_signer
from .revision import (InferenceRule,RuleAuthority,RevisionEngine,RevisionJournal,
                       RevisionError,sign_inference_rule)

REVISION_COMMANDS=frozenset({'revision-demo','revision-rule-sign',
    'revision-assess','revision-verify'})


def _load_json(path:Path):
    return json.loads(path.read_text(encoding='utf-8'))


def _atomic_json(path:Path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(dir=str(path.parent),prefix='.rei-revision-',suffix='.tmp')
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as file:
            json.dump(value,file,indent=2,sort_keys=True,ensure_ascii=False)
            file.write('\n');file.flush();os.fsync(file.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)


def add_revision_args(parser:argparse.ArgumentParser):
    cmds=parser.add_subparsers(dest='command',required=True)
    cmds.add_parser('revision-demo',help='offline signed evidence -> dispute -> revocation demonstration')
    sign=cmds.add_parser('revision-rule-sign',help='OFFLINE authorize a conditional inference with Ed25519')
    sign.add_argument('--signer',type=Path,required=True)
    sign.add_argument('--rule',type=Path,required=True,help='unsigned rule specification JSON')
    sign.add_argument('--output',type=Path,required=True)
    assess=cmds.add_parser('revision-assess',help='assess signed evidence DB with signed rules')
    assess.add_argument('--database',type=Path,required=True)
    assess.add_argument('--trust',type=Path,required=True)
    assess.add_argument('--rules',type=Path,required=True,help='JSON list of signed inference rules')
    assess.add_argument('--journal',type=Path)
    assess.add_argument('--expected-journal-head')
    assess.add_argument('--expected-rule-set-hash')
    assess.add_argument('--expected-evidence-head',help='trusted REI-0.5 evidence audit head')
    assess.add_argument('--expected-graph-head',help='trusted graph audit head')
    assess.add_argument('--expected-source-head',help='trusted source archive audit head')
    verify=cmds.add_parser('revision-verify',help='verify revision journal chain')
    verify.add_argument('--journal',type=Path,required=True)
    verify.add_argument('--expected-head')
    verify.add_argument('--trust',type=Path,help='public reviewer keys for additional rule-signature checks')


def _demo():
    from .graph import utc_now
    at='2026-11-10T21:00:00Z'
    issuer=Ed25519ReviewIssuer.generate('revision-demo-key','independent-reviewer')
    boundary=VerificationBoundary({'revision-demo-key':Ed25519TrustedReviewer(
        'independent-reviewer',issuer.public_key_bytes())})
    g=EpistemicGraph(method_version='rei-0.6')
    p=Provenance('requester',SourceKind.HUMAN,'requester','fixture:user-question',at)
    for id,text in [('premise','The observed indicator was positive'),
                    ('conclusion','The dependent hypothesis is provisionally supported')]:
        g.add_node(Node(id,NodeKind.CLAIM,text,p,at))
    from .evidence import EvidenceLedger
    ledger=EvidenceLedger(g,boundary,clock=lambda:at)
    provs=[Provenance('sensor-A',SourceKind.EXTERNAL,'sensor-A','fixture:A',at),
           Provenance('sensor-B',SourceKind.EXTERNAL,'sensor-B','fixture:B',at)]
    for pos,pol in enumerate((EdgeKind.SUPPORTS,EdgeKind.ATTACKS),1):
        sid=f'submission-{pos}'
        ledger.submit(submission_id=sid,evidence_id=f'evidence-{pos}',claim_id='premise',
            text=f'Synthetic observation {pos}',artifact_bytes=f'synthetic-{pos}'.encode(),
            provenance=provs[pos-1],polarity=pol)
    def review(sid,decision,index,previous):
        r=issuer.issue(submission_id=sid,subject_digest=ledger.subject_digest(sid),
            decision=decision,reason='Fixture-only reviewed observation',issued_at=at,
            decision_index=index,prior_signature=previous)
        ledger.accept(r)
        return r.signature
    review('submission-1',Validation.VERIFIED,1,'0'*64)
    rule=sign_inference_rule(issuer=issuer,rule_id='synthetic-conditional',premises=['premise'],
        conclusion='conclusion',polarity='supports',method_version=g.method_version,
        rationale='Synthetic conditional relation for demonstration only',issued_at=at)
    authority=RuleAuthority.from_boundary(boundary)
    journal=RevisionJournal()
    initial=RevisionEngine(ledger,[rule],authority).evaluate()
    journal.record(initial)
    review('submission-2',Validation.VERIFIED,1,'0'*64)
    disputed=RevisionEngine(ledger,[rule],authority).evaluate()
    journal.record(disputed)
    last_sig=ledger.review_receipts[-1].signature  # submission-2 is last in sorted order
    review('submission-2',Validation.REVOKED,2,last_sig)
    recovered=RevisionEngine(ledger,[rule],authority).evaluate()
    journal.record(recovered)
    return {'scenario':'synthetic-only',
            'premise_states':[initial['assessments']['premise']['state'],
                               disputed['assessments']['premise']['state'],
                               recovered['assessments']['premise']['state']],
            'derived_states':[initial['assessments']['conclusion']['state'],
                              disputed['assessments']['conclusion']['state'],
                              recovered['assessments']['conclusion']['state']],
            'revision_events':len(journal.events),'journal_audit_head':journal.audit_head,
            'journal_replay_valid':RevisionJournal.from_dict(
                journal.to_dict(),expected_head=journal.audit_head).audit_head==journal.audit_head,
            'warning':'Synthetic signed review demonstrates information updates; not a truth test.'}


def run_revision(args:argparse.Namespace):
    c=args.command
    if c=='revision-demo':return _demo()
    if c=='revision-rule-sign':
        issuer=load_signer(args.signer)
        if not isinstance(issuer,Ed25519ReviewIssuer):
            raise RevisionError('asymmetric signer required for inference rules')
        data=_load_json(args.rule)
        fields={'rule_id','premises','conclusion','polarity','method_version','rationale','issued_at'}
        if not isinstance(data,dict) or set(data)!=fields:
            raise RevisionError('unexpected unsigned rule fields')
        signed=sign_inference_rule(issuer=issuer,**data)
        if args.output.exists():
            raise RevisionError('refusing to overwrite signed inference rule')
        _atomic_json(args.output,signed.to_dict())
        return {'signed':True,'rule_id':signed.rule_id,'output':str(args.output)}
    if c=='revision-verify':
        journal=RevisionJournal.from_dict(_load_json(args.journal),expected_head=args.expected_head)
        sig_verified=False
        if getattr(args,'trust',None):
            authority=RuleAuthority.from_boundary(load_trust(args.trust))
            for e in journal.events:
                for item in e['payload']['report']['rules']:
                    authority.verify(InferenceRule.from_dict(item))
            sig_verified=True
        return {'valid':True,'revision_events':len(journal.events),'audit_head':journal.audit_head,
                'rule_signatures_verified':sig_verified}
    if c=='revision-assess':
        trust=load_trust(args.trust)
        raw=_load_json(args.rules)
        if not isinstance(raw,list):raise RevisionError('rules document must be a JSON array')
        rules=[InferenceRule.from_dict(r) for r in raw]
        with EvidenceDatabase(args.database,trust) as db:
            db.check(expected_head=getattr(args,'expected_evidence_head',None),
                     expected_graph_head=getattr(args,'expected_graph_head',None),
                     expected_source_head=getattr(args,'expected_source_head',None))
            report=RevisionEngine.from_database(db,rules,
                      RuleAuthority.from_boundary(trust)).evaluate()
        if args.expected_rule_set_hash and report['rule_set_hash']!=args.expected_rule_set_hash:
            raise RevisionError('rule set changed relative to trusted anchor')
        result={'report':report}
        if args.journal:
            journal=RevisionJournal.from_dict(_load_json(args.journal),
                expected_head=args.expected_journal_head) if args.journal.exists() else RevisionJournal()
            if args.expected_journal_head and journal.audit_head!=args.expected_journal_head:
                raise RevisionError('missing or stale external journal anchor')
            transition=journal.record(report)
            _atomic_json(args.journal,journal.to_dict())
            result['transition']=transition
        elif args.expected_journal_head:
            raise RevisionError('expected journal head requires --journal')
        return result
    raise RevisionError('unknown revision command')


def main_revision(argv:list[str])->int:
    parser=argparse.ArgumentParser(prog='rei0',description='REI-0.6 evidence-based belief revision')
    add_revision_args(parser)
    args=parser.parse_args(argv)
    try:payload=run_revision(args)
    except (RevisionError,ValueError,OSError,KeyError,TypeError) as e:
        parser.exit(2,f'REI revision error: {e}\n')
    print(json.dumps(payload,sort_keys=True,indent=2,ensure_ascii=False))
    return 0
