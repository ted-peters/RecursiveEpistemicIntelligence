"""Explicit evidence operations, separated from the inquiry adapter.

All trusted operations require REI_REVIEW_KEY_HEX in the process environment.
Review signing is intentionally an explicit human/operator command, not an LLM tool.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets

from .evidence import EvidenceLedger, EvidenceError
from .graph import EpistemicGraph, utc_now
from .models import EdgeKind, Node, NodeKind, Provenance, SourceKind, Validation
from .review import ReviewIssuer, TrustedReviewer, VerificationBoundary, ReviewError, ReviewReceipt
from .models import require_utc


def add_evidence_commands(commands: argparse._SubParsersAction) -> None:
    commands.add_parser('review-key', help='generate new random review key (print once; store securely)')
    demo = commands.add_parser('evidence-demo', help='ephemeral offline signed evidence demonstration')
    demo.add_argument('--ledger', type=Path, help='persist demo; requires REVIEW KEY environment')
    initialize = commands.add_parser('evidence-init', help='create evidence ledger for an existing graph')
    initialize.add_argument('graph', type=Path)
    initialize.add_argument('ledger', type=Path)
    submit = commands.add_parser('evidence-submit', help='ingest original bytes and a pending evidence link')
    submit.add_argument('ledger', type=Path)
    submit.add_argument('--submission-id', required=True)
    submit.add_argument('--evidence-id', required=True)
    submit.add_argument('--claim', required=True)
    submit.add_argument('--text', required=True, help='plain-language evidence statement')
    submit.add_argument('--artifact', required=True, type=Path, help='original artifact to SHA-256 hash')
    submit.add_argument('--polarity', required=True, choices=('supports','attacks'))
    submit.add_argument('--source-id', required=True)
    submit.add_argument('--source-kind', required=True, choices=('human','external','model','system'))
    submit.add_argument('--source-group', required=True)
    submit.add_argument('--reference', required=True, help='original URL, DOI, or local reference')
    submit.add_argument('--observed-at', default=None, help='UTC ISO8601 source time; default now')
    review = commands.add_parser('evidence-review', help='signed approve/reject/revoke; operator ONLY')
    review.add_argument('ledger', type=Path)
    review.add_argument('submission_id')
    review.add_argument('--decision', required=True, choices=('verified','rejected','revoked'))
    review.add_argument('--reason', required=True, help='reviewer explanation / evidence-check record')
    sign = commands.add_parser('evidence-sign', help='sign a review as an independent reviewer; no ledger mutation')
    sign.add_argument('ledger', type=Path)
    sign.add_argument('submission_id')
    sign.add_argument('--decision', required=True, choices=('verified','rejected','revoked'))
    sign.add_argument('--reason', required=True)
    sign.add_argument('--receipt', type=Path, required=True)
    accept = commands.add_parser('evidence-accept', help='verify signed receipt against trusted key, then append')
    accept.add_argument('ledger', type=Path)
    accept.add_argument('receipt', type=Path)
    check = commands.add_parser('evidence-check-artifact', help='confirm source artifact bytes match submitted SHA-256')
    check.add_argument('ledger', type=Path)
    check.add_argument('submission_id')
    check.add_argument('artifact', type=Path)
    assessment = commands.add_parser('evidence-assess', help='authenticate all reviews and assess evidence')
    assessment.add_argument('ledger', type=Path)
    assessment.add_argument('claim_id')
    verify = commands.add_parser('evidence-verify', help='replay and authenticate the evidence log')
    verify.add_argument('ledger', type=Path)
    verify.add_argument('--expected-head', help='previously saved external audit head for comparison')
    verify.add_argument('--expected-graph-head', help='previously saved graph head for comparison')


def _credentials() -> tuple[ReviewIssuer, VerificationBoundary]:
    secret_hex = os.environ.get('REI_REVIEW_KEY_HEX', '')
    if not secret_hex:
        raise ReviewError('REI_REVIEW_KEY_HEX required; run review-key once and securely store key')
    try:
        if len(secret_hex) < 64 or len(secret_hex) % 2 != 0:
            raise ValueError('length')
        secret = bytes.fromhex(secret_hex)
    except ValueError as exc:
        raise ReviewError('REI_REVIEW_KEY_HEX must be at least 64 hexadecimal digits') from exc
    key_id = os.environ.get('REI_REVIEW_KEY_ID', 'local-review-v1')
    reviewer_id = os.environ.get('REI_REVIEWER_ID', 'local-reviewer')
    return (ReviewIssuer(key_id, reviewer_id, secret),
            VerificationBoundary({key_id: TrustedReviewer(reviewer_id, secret)}))


def handle_evidence_command(args: argparse.Namespace) -> dict:
    command = args.command
    if command == 'review-key':
        return {'key_hex': secrets.token_hex(32), 'warning':
                'Secret grants signing authority. Store outside the repository and never expose to an LLM.'}
    if command == 'evidence-demo':
        if args.ledger is not None:
            issuer, boundary = _credentials()
        else:
            key = secrets.token_bytes(32)
            issuer = ReviewIssuer('demo-ephemeral', 'independent-demo-reviewer', key)
            boundary = VerificationBoundary({'demo-ephemeral': TrustedReviewer('independent-demo-reviewer', key)})
        graph = EpistemicGraph()
        now = utc_now()
        graph.add_node(Node('claim', NodeKind.CLAIM,
                            'A verified evidence statement can have competing support and opposition.',
                            Provenance('demo-question', SourceKind.HUMAN, 'demo-query', 'demo', now), now))
        ledger = EvidenceLedger(graph, boundary)
        for sid, polarity in (('observed-support', EdgeKind.SUPPORTS),
                              ('observed-attack', EdgeKind.ATTACKS)):
            ledger.submit(submission_id=sid, evidence_id='evidence-'+sid,
                          claim_id='claim', text='Illustrative '+sid,
                          artifact_bytes=('EXAMPLE ONLY: '+sid).encode(),
                          provenance=Provenance(sid, SourceKind.EXTERNAL,
                                                sid, 'fixture:'+sid, now), polarity=polarity)
            ledger.issue_and_accept(issuer, sid, Validation.VERIFIED,
                                    'Demonstration approval only; not an external fact check')
        assessment = ledger.assess('claim')
        if args.ledger is not None:
            ledger.save(args.ledger)
        return {'mode':'synthetic-fixture', 'assessment': assessment.to_dict(),
                'audit_head': ledger.audit_head, 'graph_audit_head':graph.audit_head,
                'saved_ledger': str(args.ledger) if args.ledger is not None else None,
                'key_persisted': False, 'fact_checked': False}
    issuer, boundary = _credentials()
    if command == 'evidence-init':
        graph = EpistemicGraph.load(args.graph)
        ledger = EvidenceLedger(graph, boundary)
        ledger.save(args.ledger)
        return {'ledger_path': str(args.ledger), 'graph_audit_head':graph.audit_head,
                'evidence_audit_head':ledger.audit_head, 'reviewed':0}
    ledger = EvidenceLedger.load(args.ledger, boundary)
    if command == 'evidence-submit':
        original = args.artifact.read_bytes()
        provenance = Provenance(source_id=args.source_id, source_kind=SourceKind(args.source_kind),
                                source_group=args.source_group, reference=args.reference,
                                observed_at=args.observed_at or utc_now())
        submission = ledger.submit(submission_id=args.submission_id,
                                   evidence_id=args.evidence_id, claim_id=args.claim,
                                   text=args.text, artifact_bytes=original,
                                   provenance=provenance, polarity=EdgeKind(args.polarity))
        ledger.save(args.ledger)
        return {'submission':submission.to_dict(), 'status':'pending',
                'audit_head':ledger.audit_head, 'graph_audit_head':ledger.graph.audit_head}
    if command == 'evidence-check-artifact':
        from hashlib import sha256
        match = next((s for s in ledger.submissions if s.submission_id == args.submission_id),None)
        if match is None:
            raise EvidenceError('unknown submission')
        actual = sha256(args.artifact.read_bytes()).hexdigest()
        if actual != match.artifact_sha256:
            raise EvidenceError('source artifact SHA-256 mismatch')
        return {'matches':True, 'submission_id':match.submission_id,
                'artifact_sha256':actual,
                'warning':'Matching bytes do not establish a source document is authentic or its claims true.'}
    if command == 'evidence-sign':
        existing = next((s for s in ledger.submissions if s.submission_id == args.submission_id),None)
        if existing is None:
            raise ReviewError('unknown submission')
        prior = [r for r in ledger.review_receipts if r.submission_id == args.submission_id]
        issued_at = utc_now()
        receipt = issuer.issue(submission_id=args.submission_id,
                               subject_digest=ledger.subject_digest(args.submission_id),
                               decision=Validation(args.decision),reason=args.reason,
                               issued_at=issued_at, decision_index=len(prior)+1,
                               prior_signature=prior[-1].signature if prior else '0'*64)
        # Validate locally with the same admission policy, without mutating ledger.
        ledger._validate_receipt(receipt)
        args.receipt.write_text(json.dumps(receipt.to_dict(),sort_keys=True,indent=2)+'\n',encoding='utf-8')
        return {'receipt_path':str(args.receipt), 'signature':receipt.signature,
                'ledger_not_modified':True}
    if command == 'evidence-accept':
        receipt = ReviewReceipt.from_dict(json.loads(args.receipt.read_text(encoding='utf-8')))
        ledger.accept(receipt)
        ledger.save(args.ledger)
        return {'accepted':True, 'submission_id':receipt.submission_id,
                'decision':receipt.decision.value, 'audit_head':ledger.audit_head}
    if command == 'evidence-review':
        receipt = ledger.issue_and_accept(issuer,args.submission_id,
                                          Validation(args.decision),args.reason)
        ledger.save(args.ledger)
        return {'review': receipt.to_dict(), 'audit_head':ledger.audit_head,
                'graph_audit_head':ledger.graph.audit_head}
    if command == 'evidence-assess':
        return {'assessment': ledger.assess(args.claim_id).to_dict(),
                'audit_head':ledger.audit_head, 'graph_audit_head':ledger.graph.audit_head}
    if command == 'evidence-verify':
        if args.expected_head and args.expected_head != ledger.audit_head:
            raise EvidenceError('evidence audit head mismatched trusted external anchor')
        if args.expected_graph_head and args.expected_graph_head != ledger.graph.audit_head:
            raise EvidenceError('graph audit head mismatched trusted external anchor')
        return {'verified_receipts':len(ledger.review_receipts),
                'submissions':len(ledger.submissions), 'valid': True,
                'audit_head':ledger.audit_head, 'graph_audit_head':ledger.graph.audit_head,
                'warning':'Review authenticity does not prove that the evidence is factually correct.'}
    raise EvidenceError('unknown evidence command')
