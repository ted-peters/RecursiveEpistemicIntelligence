"""REI-0.6 deterministic, explainable and evidence-retractable belief revision.

This is an *information-status propagation* engine, not a truth oracle.
Only signed, currently admissible evidence from the 0.5 ledger can enter direct
assessments. Signed reviewer-authorized Horn-style rules can propagate **defeasible**
positive/negative support through an acyclic graph. A disputed premise blocks a
rule (strict skeptical policy); no contradictions are treated as arbitrary proof.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Iterable
from hashlib import sha256
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .models import canonical_json, digest, EvidenceState, NodeKind, require_utc
from .evidence import EvidenceLedger
from .durable import EvidenceDatabase
from .review import Ed25519ReviewIssuer, Ed25519TrustedReviewer, VerificationBoundary

DOMAIN = b'REI-0.6-INFERENCE-RULE\x00'
SCHEMA = 'rei0.revision.v1'
RULE_SCHEMA = 'rei0.inference-rule.v1'
JOURNAL_SCHEMA = 'rei0.revision-journal.v1'


class RevisionError(ValueError):
    """Invalid inference rule, graph, or revision trace."""


def _word(value: str, name: str, maxlen: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maxlen:
        raise RevisionError(f'{name} must be a nonempty string <= {maxlen} characters')
    return value


@dataclass(frozen=True)
class InferenceRule:
    """A reviewer-signed *permission to infer*, not verified empirical truth."""
    rule_id: str
    premises: tuple[str, ...]
    conclusion: str
    polarity: str
    method_version: str
    key_id: str
    reviewer_id: str
    issued_at: str
    rationale: str
    signature: str

    def __post_init__(self) -> None:
        for field in ('rule_id','conclusion','method_version','key_id','reviewer_id'):
            _word(getattr(self,field),field,256)
        _word(self.rationale,'rationale',2000)
        require_utc(self.issued_at)
        if not isinstance(self.premises,tuple) or not (1 <= len(self.premises) <= 32):
            raise RevisionError('1-32 premises required')
        for premise in self.premises:
            _word(premise,'premise',256)
        if len(set(self.premises)) != len(self.premises) or tuple(sorted(self.premises)) != self.premises:
            raise RevisionError('premises must be sorted and unique')
        if self.conclusion in self.premises:
            raise RevisionError('rule cannot depend on itself')
        if self.polarity not in ('supports','attacks'):
            raise RevisionError('rule polarity must be supports or attacks')
        if not isinstance(self.signature,str) or len(self.signature)!=128 or any(
            char not in '0123456789abcdef' for char in self.signature
        ):
            raise RevisionError('Ed25519 rule signature must be 128 lowercase hex digits')

    def statement(self) -> dict[str, Any]:
        return {'schema_version':RULE_SCHEMA, 'rule_id':self.rule_id,
                'premises':list(self.premises), 'conclusion':self.conclusion,
                'polarity':self.polarity,'method_version':self.method_version,
                'key_id':self.key_id,'reviewer_id':self.reviewer_id,
                'issued_at':self.issued_at,'rationale':self.rationale}

    def to_dict(self) -> dict[str, Any]:
        return {**self.statement(), 'signature':self.signature}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> 'InferenceRule':
        keys = {'schema_version','rule_id','premises','conclusion','polarity',
                'method_version','key_id','reviewer_id','issued_at','rationale','signature'}
        if not isinstance(value,dict) or set(value)!=keys or value['schema_version']!=RULE_SCHEMA:
            raise RevisionError('invalid inference rule schema')
        if not isinstance(value['premises'],list):
            raise RevisionError('premises must be an array')
        try:
            rule=cls(rule_id=value['rule_id'],premises=tuple(value['premises']),
                     conclusion=value['conclusion'],polarity=value['polarity'],
                     method_version=value['method_version'],key_id=value['key_id'],
                     reviewer_id=value['reviewer_id'],issued_at=value['issued_at'],
                     rationale=value['rationale'],signature=value['signature'])
        except (TypeError,KeyError,ValueError) as exc:
            raise RevisionError(f'invalid rule: {exc}') from exc
        if rule.to_dict()!=value:
            raise RevisionError('rule serialization must be canonical')
        return rule


def sign_inference_rule(*, issuer: Ed25519ReviewIssuer, rule_id: str,
                        premises: Iterable[str], conclusion: str, polarity: str,
                        method_version: str, rationale: str, issued_at: str) -> InferenceRule:
    """OFFLINE trusted operator only. Never expose this signer to the AI/service."""
    if not isinstance(issuer,Ed25519ReviewIssuer):
        raise RevisionError('Ed25519 offline issuer required')
    try:
        canonical=tuple(sorted(premises))
    except (TypeError,ValueError) as exc:
        raise RevisionError('rule premises must be sortable claim ID strings') from exc
    blank=InferenceRule(rule_id,canonical,conclusion,polarity,method_version,
                        issuer.key_id,issuer.reviewer_id,issued_at,rationale,'0'*128)
    private=Ed25519PrivateKey.from_private_bytes(issuer.private_key_bytes())
    sig=private.sign(DOMAIN+canonical_json(blank.statement()).encode('utf-8')).hex()
    return InferenceRule.from_dict({**blank.statement(),'signature':sig})


class RuleAuthority:
    """Public-key-only verification; rejects symmetric keys and unauthorized rules."""
    def __init__(self, reviewers: Mapping[str,Ed25519TrustedReviewer]):
        if not isinstance(reviewers,Mapping):
            raise RevisionError('public-key reviewer registry required')
        if any(not isinstance(v,Ed25519TrustedReviewer) for v in reviewers.values()):
            raise RevisionError('inference rules require asymmetric public-key trust')
        self._reviewers=dict(reviewers)

    @classmethod
    def from_boundary(cls,boundary: VerificationBoundary)->'RuleAuthority':
        if not isinstance(boundary,VerificationBoundary):
            raise RevisionError('VerificationBoundary required')
        # Both modules are trusted verifier code; do not expose this registry to LLM tools.
        public={k:v for k,v in boundary._reviewers.items()
                if isinstance(v,Ed25519TrustedReviewer)}
        return cls(public)

    def verify(self,rule: InferenceRule)->None:
        if not isinstance(rule,InferenceRule):
            raise RevisionError('signed inference rule required')
        reviewer=self._reviewers.get(rule.key_id)
        if reviewer is None or reviewer.reviewer_id!=rule.reviewer_id or not reviewer.can_verify:
            raise RevisionError('rule reviewer is untrusted or not authorized')
        try:
            Ed25519PublicKey.from_public_bytes(reviewer.public_key).verify(
                bytes.fromhex(rule.signature), DOMAIN+canonical_json(rule.statement()).encode('utf-8'))
        except (InvalidSignature,ValueError) as exc:
            raise RevisionError('inference rule signature invalid') from exc


def _order(rules: tuple[InferenceRule,...], claim_ids: set[str]) -> tuple[str,...]:
    """Topological order on signed rule dependencies; reject cyclic justifications."""
    indegree={c:0 for c in claim_ids}; dependents:dict[str,set[str]]={c:set() for c in claim_ids}
    for rule in rules:
        if rule.conclusion not in claim_ids or any(p not in claim_ids for p in rule.premises):
            raise RevisionError('rule references unknown or non-claim node')
        for p in rule.premises:
            if rule.conclusion not in dependents[p]:
                dependents[p].add(rule.conclusion)
                indegree[rule.conclusion]+=1
    ready=sorted(c for c in indegree if indegree[c]==0)
    result=[]
    while ready:
        current=ready.pop(0);result.append(current)
        for child in sorted(dependents[current]):
            indegree[child]-=1
            if indegree[child]==0:
                ready.append(child)
                ready.sort()
    if len(result)!=len(claim_ids):
        raise RevisionError('circular rule dependencies are forbidden')
    return tuple(result)


class RevisionEngine:
    """Recompute from signed evidence each time; never caches revoked evidence credit."""
    def __init__(self, ledger: EvidenceLedger, rules: Iterable[InferenceRule],
                 authority: RuleAuthority, *, max_claims:int=10000, max_rules:int=5000):
        if not isinstance(ledger,EvidenceLedger):
            raise RevisionError('authenticated EvidenceLedger required')
        if not isinstance(authority,RuleAuthority):
            raise RevisionError('independent RuleAuthority required')
        if (type(max_claims)!=int or not 1<=max_claims<=100000 or
                type(max_rules)!=int or not 0<=max_rules<=100000):
            raise RevisionError('invalid bounded processing limits')
        self.ledger=ledger;self.authority=authority
        self.rules=tuple(sorted(rules,key=lambda r:r.rule_id))
        if len(self.rules)>max_rules:
            raise RevisionError('rule budget exceeded')
        if len({r.rule_id for r in self.rules})!=len(self.rules):
            raise RevisionError('duplicate rule ID')
        self.claim_ids={id for id,n in ledger.graph.nodes.items()
                        if n.kind in (NodeKind.CLAIM,NodeKind.ARGUMENT,NodeKind.METHOD_CLAIM)}
        if len(self.claim_ids)>max_claims:
            raise RevisionError('claim budget exceeded')
        for rule in self.rules:
            authority.verify(rule)
            if rule.method_version!=ledger.graph.method_version:
                raise RevisionError('rule method version mismatch')
        self.order=_order(self.rules,self.claim_ids)
        self.fingerprint=digest([r.to_dict() for r in self.rules])

    @classmethod
    def from_database(cls, db: EvidenceDatabase, rules: Iterable[InferenceRule],
                      authority: RuleAuthority) -> 'RevisionEngine':
        if not isinstance(db,EvidenceDatabase):
            raise RevisionError('EvidenceDatabase required')
        db.check()
        ledger,_=db._state()  # already fully replay/receipt verified by EvidenceDatabase
        return cls(ledger,rules,authority)

    def evaluate(self)->dict[str,Any]:
        rules_by_target:dict[str,list[InferenceRule]]={c:[] for c in self.claim_ids}
        for rule in self.rules:
            rules_by_target[rule.conclusion].append(rule)
        states={}
        for cid in self.order:
            direct=self.ledger.assess(cid)  # authenticated 0.5 reviews ONLY
            positive=[];negative=[]; blocked=[]
            for rule in rules_by_target[cid]:
                # Conservative policy: BOTH, ATTACK_ONLY or NEITHER premise blocks rule.
                unsatisfied=[p for p in rule.premises
                             if states[p]['state']!='SUPPORT_ONLY']
                if unsatisfied:
                    blocked.append({'rule_id':rule.rule_id,'premises':unsatisfied,
                                    'reason':'premise_not_unopposed_supported'})
                elif rule.polarity=='supports':
                    positive.append(rule.rule_id)
                else:
                    negative.append(rule.rule_id)
            state=EvidenceState.from_bits(
                bool(direct.support_evidence or positive),
                bool(direct.attack_evidence or negative))
            states[cid]={
                'claim_id':cid,'claim':self.ledger.graph.nodes[cid].text,
                'state':state.value,'direct_state':direct.state.value,
                'support_evidence':list(direct.support_evidence),
                'attack_evidence':list(direct.attack_evidence),
                'support_sources':list(direct.support_sources),
                'attack_sources':list(direct.attack_sources),
                'derived_support_rules':positive,
                'derived_attack_rules':negative,
                'blocked_rules':blocked,
                'method_version':direct.method_version,
                'confidence':None,
            }
        return {'schema_version':SCHEMA,
                'graph_audit_head':self.ledger.graph.audit_head,
                'evidence_audit_head':self.ledger.audit_head,
                'method_version':self.ledger.graph.method_version,
                'rule_set_hash':self.fingerprint,
                'rules':[r.to_dict() for r in self.rules],
                'assessments':{cid:states[cid] for cid in sorted(states)},
                'warnings':['Information status is not truth or calibrated probability.',
                            'Signed rules authorize defeasible propagation, not logical certainty.']}


def _changes(old:dict[str,Any] | None,new:dict[str,Any])->list[dict[str,Any]]:
    before=(old or {}).get('assessments',{})
    after=new['assessments']
    output=[]
    for cid in sorted(set(before)|set(after)):
        a=before.get(cid);b=after.get(cid)
        if a==b:
            continue
        changes={}
        for field in ('state','direct_state','support_evidence','attack_evidence',
                      'support_sources','attack_sources','derived_support_rules',
                      'derived_attack_rules','blocked_rules'):
            av=a.get(field) if a else None;bv=b.get(field) if b else None
            if av!=bv:
                changes[field]={'before':av,'after':bv}
        output.append({'claim_id':cid,'from':a['state'] if a else None,
                       'to':b['state'] if b else None,'changes':changes})
    return output


class RevisionJournal:
    """Append-only hash-chained assessments; compare against external trusted anchors."""
    def __init__(self):
        self._events:list[dict[str,Any]]=[]

    @property
    def audit_head(self)->str:
        return self._events[-1]['event_hash'] if self._events else '0'*64

    @property
    def events(self)->tuple[dict[str,Any],...]:
        return tuple(json.loads(json.dumps(e)) for e in self._events)

    @property
    def latest(self)->dict[str,Any] | None:
        return json.loads(json.dumps(self._events[-1]['payload']['report'])) if self._events else None

    def record(self,report:dict[str,Any])->dict[str,Any]:
        _validate_report(report)
        prior=self.latest
        if prior==report:
            return {'recorded':False,'audit_head':self.audit_head,'changes':[]}
        changes=_changes(prior,report)
        payload={'report':json.loads(json.dumps(report)), 'changes':changes}
        event={'sequence':len(self._events)+1, 'previous_hash':self.audit_head,
               'kind':'revision_assessment','payload':payload}
        event['event_hash']=digest(event)
        self._events.append(event)
        return {'recorded':True,'audit_head':self.audit_head,'sequence':len(self._events),
                'changes':changes}

    def to_dict(self)->dict[str,Any]:
        return {'schema_version':JOURNAL_SCHEMA,'events':list(self.events)}

    @classmethod
    def from_dict(cls,value:dict[str,Any],*,expected_head:str|None=None)->'RevisionJournal':
        if not isinstance(value,dict) or set(value)!={'schema_version','events'} or \
           value['schema_version']!=JOURNAL_SCHEMA or not isinstance(value['events'],list):
            raise RevisionError('invalid revision journal schema')
        result=cls()
        for i,event in enumerate(value['events'],1):
            if not isinstance(event,dict) or set(event)!={'sequence','previous_hash','kind','payload','event_hash'}:
                raise RevisionError('malformed journal event')
            if (type(event['sequence'])!=int or event['sequence']!=i or
                event['previous_hash']!=result.audit_head or
                event['kind']!='revision_assessment'):
                raise RevisionError('invalid journal event sequence')
            if digest({k:event[k] for k in ('sequence','previous_hash','kind','payload')})!=event['event_hash']:
                raise RevisionError('invalid journal event digest')
            p=event['payload']
            if not isinstance(p,dict) or set(p)!={'report','changes'}:
                raise RevisionError('invalid journal event payload')
            _validate_report(p['report'])
            if p['changes']!=_changes(result.latest,p['report']):
                raise RevisionError('revision explanation differs from replay')
            result._events.append(json.loads(json.dumps(event)))
        if expected_head is not None and expected_head!=result.audit_head:
            raise RevisionError('journal does not match externally anchored audit head')
        return result


def _validate_report(report:dict[str,Any])->None:
    expected={'schema_version','graph_audit_head','evidence_audit_head',
              'method_version','rule_set_hash','rules','assessments','warnings'}
    if not isinstance(report,dict) or set(report)!=expected or report['schema_version']!=SCHEMA:
        raise RevisionError('invalid revision report schema')
    if not isinstance(report['assessments'],dict) or not isinstance(report['warnings'],list) or \
       not all(isinstance(w,str) for w in report['warnings']):
        raise RevisionError('malformed assessments or warnings')
    for field in ('graph_audit_head','evidence_audit_head','rule_set_hash'):
        value=report[field]
        if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
            raise RevisionError('invalid report digest')
    if not isinstance(report['rules'],list):
        raise RevisionError('invalid report rule list')
    rules=[InferenceRule.from_dict(r) for r in report['rules']]
    if len({r.rule_id for r in rules})!=len(rules) or \
       [r.rule_id for r in rules]!=sorted(r.rule_id for r in rules) or \
       digest(report['rules'])!=report['rule_set_hash']:
        raise RevisionError('report rule set has changed')
    if not isinstance(report['method_version'],str) or not report['method_version'] or \
       any(r.method_version!=report['method_version'] for r in rules):
        raise RevisionError('report method version mismatch')
    valid_ids=set(report['assessments'])
    _order(tuple(rules),valid_ids)
    by_target={cid:[] for cid in valid_ids}
    for r in rules:by_target[r.conclusion].append(r)
    fields={'claim_id','claim','state','direct_state','support_evidence',
            'attack_evidence','support_sources','attack_sources','derived_support_rules',
            'derived_attack_rules','blocked_rules','method_version','confidence'}
    for cid,rec in report['assessments'].items():
        if not isinstance(cid,str) or not isinstance(rec,dict) or set(rec)!=fields or rec['claim_id']!=cid:
            raise RevisionError('invalid assessment structure')
        if not isinstance(rec['claim'],str) or not rec['claim'] or \
           rec['method_version']!=report['method_version'] or rec['confidence'] is not None:
            raise RevisionError('invalid claim metadata or confidence')
        for key in ('support_evidence','attack_evidence','support_sources',
                    'attack_sources','derived_support_rules','derived_attack_rules'):
            v=rec[key]
            if not isinstance(v,list) or len(set(str(x) for x in v))!=len(v) or \
               not all(isinstance(x,str) and x for x in v):
                raise RevisionError('invalid claim evidence or rule identifiers')
        if not isinstance(rec['blocked_rules'],list):
            raise RevisionError('malformed blocked rules')
        for b in rec['blocked_rules']:
            if not isinstance(b,dict) or set(b)!={'rule_id','premises','reason'} or \
               not isinstance(b['premises'],list) or b['reason']!='premise_not_unopposed_supported':
                raise RevisionError('malformed blocked rule record')
        if rec['state']!=EvidenceState.from_bits(
            bool(rec['support_evidence'] or rec['derived_support_rules']),
            bool(rec['attack_evidence'] or rec['derived_attack_rules'])).value or \
           rec['direct_state']!=EvidenceState.from_bits(
            bool(rec['support_evidence']),bool(rec['attack_evidence'])).value:
            raise RevisionError('reported status inconsistent with evidence and rules')
        expected_positive=[r.rule_id for r in by_target[cid] if r.rule_id in rec['derived_support_rules']]
        expected_negative=[r.rule_id for r in by_target[cid] if r.rule_id in rec['derived_attack_rules']]
        expected_blocked=[r.rule_id for r in by_target[cid] if r.rule_id not in
                          rec['derived_support_rules']+rec['derived_attack_rules']]
        if expected_positive!=rec['derived_support_rules'] or expected_negative!=rec['derived_attack_rules'] or \
           expected_blocked!=[b['rule_id'] for b in rec['blocked_rules']]:
            raise RevisionError('report omits or invents rule activations')
        for b in rec['blocked_rules']:
            rule=next(r for r in by_target[cid] if r.rule_id==b['rule_id'])
            if b['premises']!=[p for p in rule.premises
                if report['assessments'][p]['state']!='SUPPORT_ONLY']:
                raise RevisionError('blocked rule premises inconsistent with report')
        for r in by_target[cid]:
            if r.rule_id in rec['derived_support_rules']+rec['derived_attack_rules'] and \
               any(report['assessments'][p]['state']!='SUPPORT_ONLY' for p in r.premises):
                raise RevisionError('rule activated with unsatisfied premises')
