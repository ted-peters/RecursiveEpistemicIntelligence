"""Operator/CLI interfaces for REI-0.4; signing is OFFLINE, never a service RPC."""
from __future__ import annotations

import argparse
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import signal
import stat
import tempfile
import threading
import uuid
from typing import Any

from .durable import EvidenceDatabase, DurableError
from .graph import EpistemicGraph, utc_now
from .models import Node, NodeKind, Provenance, SourceKind, Validation, EdgeKind
from .review import (ReviewIssuer, TrustedReviewer, VerificationBoundary, ReviewError,
                     Ed25519ReviewIssuer, Ed25519TrustedReviewer)
from .service import VerificationServer, call_service, ServiceError
from .sources import SecureSourceFetcher, SourceError
from .source_store import SourceRepository

SERVICE_COMMANDS = frozenset({
    'service-keygen','service-init','service-import','service-serve','service-status',
    'service-submit','service-challenge','operator-sign','service-accept',
    'service-assess','service-verify','service-demo','service-keygen-ed25519',
    'source-retrieve','source-info','source-submit','source-export','source-demo'
})


def _write_new(path: Path, content: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(content,f,ensure_ascii=False,sort_keys=True,indent=2)
            f.write('\n')
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _secret_file(path: Path) -> dict[str,Any]:
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or (os.name != 'nt' and st.st_mode & 0o077):
        raise ReviewError('secret config must be regular file with owner-only permissions (chmod 600)')
    if os.name != 'nt' and st.st_uid != os.geteuid():
        raise ReviewError('secret config is not owned by current user')
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value,dict):
        raise ReviewError('malformed secret config')
    return value


def load_trust(path: Path) -> VerificationBoundary:
    value = _secret_file(path)
    if not isinstance(value,dict) or set(value) != {'schema_version','reviewers'}:
        raise ReviewError('invalid trust configuration')
    if not isinstance(value['reviewers'],list) or not value['reviewers']:
        raise ReviewError('trust config must contain reviewers')
    reviewers = {}
    for r in value['reviewers']:
        if not isinstance(r,dict) or not isinstance(r.get('key_id'),str):
            raise ReviewError('invalid reviewer record')
        if r['key_id'] in reviewers:
            raise ReviewError('duplicate trusted key')
        if value['schema_version'] == 'rei0.trust.v1':
            if set(r) != {'key_id','reviewer_id','secret_hex','can_verify','can_revoke'}:
                raise ReviewError('invalid reviewer record')
            record = TrustedReviewer(r['reviewer_id'],bytes.fromhex(r['secret_hex']),
                                     r['can_verify'],r['can_revoke'])
        elif value['schema_version'] == 'rei0.trust.v2':
            if set(r) != {'key_id','reviewer_id','public_hex','can_verify','can_revoke'}:
                raise ReviewError('invalid reviewer record')
            record = Ed25519TrustedReviewer(r['reviewer_id'],bytes.fromhex(r['public_hex']),
                                            r['can_verify'],r['can_revoke'])
        else:
            raise ReviewError('unsupported trust configuration')
        reviewers[r['key_id']] = record
    return VerificationBoundary(reviewers)


def load_signer(path: Path) -> ReviewIssuer | Ed25519ReviewIssuer:
    value = _secret_file(path)
    if value.get('schema_version') == 'rei0.signer.v1' and set(value) == {
        'schema_version','key_id','reviewer_id','secret_hex'}:
        return ReviewIssuer(value['key_id'],value['reviewer_id'],bytes.fromhex(value['secret_hex']))
    if value.get('schema_version') == 'rei0.signer.v2' and set(value) == {
        'schema_version','key_id','reviewer_id','private_hex'}:
        return Ed25519ReviewIssuer(value['key_id'],value['reviewer_id'],
                                   bytes.fromhex(value['private_hex']))
    raise ReviewError('invalid offline signer configuration')


def sign_challenge(challenge: dict[str,Any], signer: ReviewIssuer | Ed25519ReviewIssuer,
                   decision: Validation, reason: str, *, artifact: bytes | None = None) -> dict:
    keys = {'schema_version','revision','submission_id','subject_digest','decision_index',
            'prior_signature','current_status','artifact_sha256','artifact_available',
            'evidence_text','provenance','claim','polarity'}
    if not isinstance(challenge,dict) or set(challenge) != keys or \
       challenge['schema_version'] != 'rei0.challenge.v1':
        raise ReviewError('invalid challenge structure')
    if decision == Validation.VERIFIED:
        if artifact is None:
            raise ReviewError('a locally inspected original artifact is required for verified review')
        if sha256(artifact).hexdigest() != challenge['artifact_sha256']:
            raise ReviewError('reviewed artifact bytes do not match submission hash')
    if decision in (Validation.VERIFIED, Validation.REJECTED) and challenge['current_status'] != 'pending':
        raise ReviewError('review decision requires pending submission')
    if decision == Validation.REVOKED and challenge['current_status'] != 'verified':
        raise ReviewError('revocation requires previously verified submission')
    receipt = signer.issue(submission_id=challenge['submission_id'],
                          subject_digest=challenge['subject_digest'], decision=decision,
                          reason=reason, issued_at=utc_now(),
                          decision_index=challenge['decision_index'],
                          prior_signature=challenge['prior_signature'])
    return receipt.to_dict()


def add_args(parser: argparse.ArgumentParser) -> None:
    cmds = parser.add_subparsers(dest='command',required=True)
    k = cmds.add_parser('service-keygen',help='make distinct 0600 signer and verifier configs')
    k.add_argument('--trust',type=Path,required=True)
    k.add_argument('--signer',type=Path,required=True)
    k.add_argument('--key-id',default='local-reviewer-v1')
    k.add_argument('--reviewer-id',default='human-reviewer')
    ed = cmds.add_parser('service-keygen-ed25519',help='create offline private signer and public-only trust config')
    ed.add_argument('--trust',type=Path,required=True)
    ed.add_argument('--signer',type=Path,required=True)
    ed.add_argument('--key-id',default='ed25519-reviewer-v1')
    ed.add_argument('--reviewer-id',default='human-reviewer')
    init = cmds.add_parser('service-init',help='initialize durable store from graph JSON')
    init.add_argument('graph',type=Path); init.add_argument('database',type=Path)
    init.add_argument('--trust',type=Path,required=True)
    imp = cmds.add_parser('service-import',help='import REI-0.3 signed ledger JSON')
    imp.add_argument('ledger',type=Path); imp.add_argument('database',type=Path)
    imp.add_argument('--trust',type=Path,required=True)
    srv = cmds.add_parser('service-serve',help='run local verifier over Unix socket, no signing API')
    srv.add_argument('database',type=Path); srv.add_argument('--socket',type=Path,required=True)
    srv.add_argument('--trust',type=Path,required=True)
    srv.add_argument('--source-host',action='append',default=[],help='exact allowed HTTPS host, repeatable; disabled by default')
    for name in ('service-status','service-submit','service-challenge','service-accept',
                 'service-assess','service-verify'):
        p = cmds.add_parser(name)
        p.add_argument('--socket',type=Path,required=True)
        if name == 'service-submit':
            p.add_argument('--submission-id',required=True)
            p.add_argument('--evidence-id',required=True)
            p.add_argument('--claim',required=True)
            p.add_argument('--text',required=True)
            p.add_argument('--artifact',type=Path,required=True)
            p.add_argument('--polarity',choices=['supports','attacks'],required=True)
            p.add_argument('--source-id',required=True)
            p.add_argument('--source-kind',choices=['external','human','model','system'],required=True)
            p.add_argument('--source-group',required=True)
            p.add_argument('--reference',required=True)
            p.add_argument('--request-id',default=None)
            p.add_argument('--expected-revision',type=int)
        elif name == 'service-challenge':
            p.add_argument('--submission-id',required=True)
            p.add_argument('--output',type=Path)
        elif name == 'service-accept':
            p.add_argument('--receipt',type=Path,required=True)
            p.add_argument('--request-id',default=None)
            p.add_argument('--expected-revision',type=int)
        elif name == 'service-assess':
            p.add_argument('--claim',required=True)
        elif name == 'service-verify':
            p.add_argument('--expected-head')
            p.add_argument('--expected-graph-head')
            p.add_argument('--expected-source-head')
    sign = cmds.add_parser('operator-sign',help='OFFLINE human review; not available via service')
    sign.add_argument('--challenge',type=Path,required=True)
    sign.add_argument('--signer',type=Path,required=True)
    sign.add_argument('--decision',choices=['verified','rejected','revoked'],required=True)
    sign.add_argument('--reason',required=True)
    sign.add_argument('--artifact',type=Path)
    sign.add_argument('--output',type=Path,required=True)
    sr = cmds.add_parser('source-retrieve',help='opt-in bounded HTTPS source capture')
    sr.add_argument('--socket',type=Path,required=True)
    sr.add_argument('--retrieval-id',required=True)
    sr.add_argument('--url',required=True)
    sr.add_argument('--request-id')
    si = cmds.add_parser('source-info',help='inspect captured source metadata')
    si.add_argument('--socket',type=Path,required=True)
    si.add_argument('--retrieval-id',required=True)
    sx = cmds.add_parser('source-export',help='offline export of captured original bytes, requires DB access')
    sx.add_argument('--database',type=Path,required=True)
    sx.add_argument('--trust',type=Path,required=True)
    sx.add_argument('--retrieval-id',required=True)
    sx.add_argument('--output',type=Path,required=True)
    ss = cmds.add_parser('source-submit',help='submit exact excerpt linked to stored source')
    ss.add_argument('--socket',type=Path,required=True)
    ss.add_argument('--retrieval-id',required=True)
    ss.add_argument('--submission-id',required=True)
    ss.add_argument('--evidence-id',required=True)
    ss.add_argument('--claim',required=True)
    ss.add_argument('--text',required=True)
    ss.add_argument('--polarity',choices=['supports','attacks'],required=True)
    ss.add_argument('--request-id')
    ss.add_argument('--expected-revision',type=int)
    cmds.add_parser('service-demo',help='fully offline synthetic end-to-end service example')
    cmds.add_parser('source-demo',help='fully offline synthetic HTTPS capture + Ed25519 review')


def _run(args: argparse.Namespace) -> dict[str,Any]:
    c = args.command
    if c == 'service-keygen-ed25519':
        if args.signer.resolve() == args.trust.resolve() or args.signer.exists() or args.trust.exists():
            raise ReviewError('key paths must be distinct and must not exist')
        signer = Ed25519ReviewIssuer.generate(args.key_id, args.reviewer_id)
        _write_new(args.signer, {'schema_version':'rei0.signer.v2',
                   'key_id':args.key_id,'reviewer_id':args.reviewer_id,
                   'private_hex':signer.private_key_bytes().hex()})
        try:
            _write_new(args.trust, {'schema_version':'rei0.trust.v2','reviewers':[
                {'key_id':args.key_id,'reviewer_id':args.reviewer_id,
                 'public_hex':signer.public_key_bytes().hex(),
                 'can_verify':True,'can_revoke':True}]})
        except Exception:
            args.signer.unlink(missing_ok=True)
            raise
        return {'created':True,'algorithm':'Ed25519','signer':str(args.signer),
                'trust':str(args.trust),'verifier_contains_private_key':False}
    if c == 'service-keygen':
        if args.signer.resolve() == args.trust.resolve():
            raise ReviewError('trust and signer files must be different')
        if args.signer.exists() or args.trust.exists():
            raise ReviewError('refusing to overwrite secret files')
        key = secrets.token_hex(32)
        _write_new(args.signer,{'schema_version':'rei0.signer.v1','key_id':args.key_id,
                                'reviewer_id':args.reviewer_id,'secret_hex':key})
        try:
            _write_new(args.trust,{'schema_version':'rei0.trust.v1','reviewers':[
                {'key_id':args.key_id,'reviewer_id':args.reviewer_id,
                 'secret_hex':key,'can_verify':True,'can_revoke':True}]})
        except Exception:
            args.signer.unlink(missing_ok=True)
            raise
        return {'created':True,'signer':str(args.signer),'trust':str(args.trust),
                'warning':'Keep both secrets out of LLM/tool environments. Use OS isolation.'}
    if c in ('service-init','service-import'):
        boundary = load_trust(args.trust)
        if c == 'service-init':
            graph = EpistemicGraph.load(args.graph)
            db = EvidenceDatabase.initialize(args.database,graph,boundary)
        else:
            document = json.loads(args.ledger.read_text(encoding='utf-8'))
            db = EvidenceDatabase.import_legacy(args.database,document,boundary)
        try: return db.check()
        finally: db.close()
    if c == 'service-serve':
        db = EvidenceDatabase(args.database,load_trust(args.trust))
        try:
            with VerificationServer(args.socket,db,
                    SecureSourceFetcher(set(args.source_host)) if args.source_host else None) as server:
                print(json.dumps({'listening':str(args.socket),'signing_endpoint':False}),flush=True)
                def stop_signal(_signum, _frame):
                    raise KeyboardInterrupt
                previous = signal.signal(signal.SIGTERM, stop_signal)
                try:
                    try:
                        server.serve_forever(poll_interval=0.1)
                    except KeyboardInterrupt:
                        pass
                finally:
                    signal.signal(signal.SIGTERM,previous)
        finally: db.close()
        return {'stopped':True}
    if c == 'operator-sign':
        challenge = json.loads(args.challenge.read_text(encoding='utf-8'))
        artifact = args.artifact.read_bytes() if args.artifact else None
        receipt = sign_challenge(challenge,load_signer(args.signer),
                                 Validation(args.decision),args.reason,artifact=artifact)
        _write_new(args.output,receipt)
        return {'receipt':str(args.output),'submission_id':receipt['submission_id'],
                'ledger_modified':False}
    if c == 'service-demo':
        return service_demo()
    if c == 'source-demo':
        return source_demo()
    if c == 'source-export':
        with EvidenceDatabase(args.database,load_trust(args.trust)) as db:
            metadata, artifact = SourceRepository(db.conn).get(args.retrieval_id)
            if sha256(artifact).hexdigest()!=metadata['artifact_sha256']:
                raise SourceError('stored source content digest mismatch')
            fd = os.open(args.output,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            try:
                with os.fdopen(fd,'wb') as file: file.write(artifact)
            except Exception:
                args.output.unlink(missing_ok=True)
                raise
            return {'exported':str(args.output),'sha256':metadata['artifact_sha256'],
                    'bytes':len(artifact),'warning':'Inspect source independently; bytes do not prove factual truth'}
    socket_path = args.socket
    if c == 'source-retrieve':
        return call_service(socket_path,'source-retrieve',
            {'retrieval_id':args.retrieval_id,'url':args.url},
            request_id=args.request_id or str(uuid.uuid4()))
    if c == 'source-info':
        return call_service(socket_path,'source-info',{'retrieval_id':args.retrieval_id})
    if c == 'source-submit':
        return call_service(socket_path,'submit_source',
            {'retrieval_id':args.retrieval_id,'submission_id':args.submission_id,
             'evidence_id':args.evidence_id,'claim_id':args.claim,
             'text':args.text,'polarity':args.polarity},
            request_id=args.request_id or str(uuid.uuid4()),
            expected_revision=args.expected_revision)
    if c == 'service-status': return call_service(socket_path,'status')
    if c == 'service-assess': return call_service(socket_path,'assess',{'claim_id':args.claim})
    if c == 'service-verify':
        body={}
        if args.expected_head: body['expected_head']=args.expected_head
        if args.expected_graph_head: body['expected_graph_head']=args.expected_graph_head
        if args.expected_source_head: body['expected_source_head']=args.expected_source_head
        return call_service(socket_path,'verify',body)
    if c == 'service-challenge':
        result = call_service(socket_path,'challenge',{'submission_id':args.submission_id})
        if args.output:
            _write_new(args.output,result)
        return result
    if c == 'service-submit':
        original = args.artifact.read_bytes()
        if len(original) > 2_000_000:
            raise DurableError('artifact exceeds max size of 2MB')
        body = {'submission_id':args.submission_id,'evidence_id':args.evidence_id,
                'claim_id':args.claim,'text':args.text,
                'artifact_b64':base64.b64encode(original).decode('ascii'),
                'polarity':args.polarity,
                'provenance':Provenance(args.source_id,SourceKind(args.source_kind),
                    args.source_group,args.reference,utc_now()).to_dict()}
        return call_service(socket_path,'submit',body,request_id=args.request_id or str(uuid.uuid4()),
                            expected_revision=args.expected_revision)
    if c == 'service-accept':
        receipt=json.loads(args.receipt.read_text(encoding='utf-8'))
        return call_service(socket_path,'accept',{'receipt':receipt},
                            request_id=args.request_id or str(uuid.uuid4()),
                            expected_revision=args.expected_revision)
    raise ServiceError('unknown service command')


def service_demo() -> dict[str,Any]:
    """One-process synthetic demonstration only. NOT the deployed trust boundary."""
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        secret=secrets.token_bytes(32)
        issuer=ReviewIssuer('demo','demo-independent-reviewer',secret)
        boundary=VerificationBoundary({'demo':TrustedReviewer('demo-independent-reviewer',secret)})
        graph=EpistemicGraph()
        at=utc_now()
        graph.add_node(Node('claim',NodeKind.CLAIM,'Synthetic example proposition',
                    Provenance('question',SourceKind.HUMAN,'question','fixture:question',at),at))
        with EvidenceDatabase.initialize(root/'store.sqlite',graph,boundary) as db:
            with VerificationServer(root/'verification.sock',db) as server:
                thread=threading.Thread(target=server.serve_forever,daemon=True)
                thread.start()
                try:
                    artifact=b'SYNTHETIC ONLY: observation A'
                    body={'submission_id':'demo-submission','evidence_id':'evidence-A',
                          'claim_id':'claim','text':'Synthetic support statement',
                          'artifact_b64':base64.b64encode(artifact).decode('ascii'),
                          'polarity':'supports','provenance':Provenance('external-demo',SourceKind.EXTERNAL,
                           'source-A','fixture:synthetic',at).to_dict()}
                    pending=call_service(root/'verification.sock','submit',body,request_id='demo-request')
                    challenge=call_service(root/'verification.sock','challenge',
                                           {'submission_id':'demo-submission'})
                    receipt=sign_challenge(challenge,issuer,Validation.VERIFIED,
                         'Synthetic training example, not an external fact-check',artifact=artifact)
                    accepted=call_service(root/'verification.sock','accept',
                                          {'receipt':receipt},request_id='demo-review')
                    assessment=call_service(root/'verification.sock','assess',{'claim_id':'claim'})
                    valid=call_service(root/'verification.sock','verify')
                    return {'scenario':'synthetic-only','pending':pending['status'],
                            'accepted':accepted['accepted'],
                            'state':assessment['assessment']['state'],
                            'revision':valid['revision'],'audit_verified':valid['valid'],
                            'warning':'Demo signs in same process for convenience; deploy signer separately.'}
                finally:
                    server.shutdown(); thread.join(timeout=5)


def source_demo() -> dict[str,Any]:
    """Synthetic fixture: exercises source capture and asymmetric receipt; no internet."""
    import socket
    from .review import Ed25519ReviewIssuer, Ed25519TrustedReviewer
    from .sources import SecureSourceFetcher
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        issuer=Ed25519ReviewIssuer.generate('demo-ed-key','independent-demo-reviewer')
        boundary=VerificationBoundary({'demo-ed-key':Ed25519TrustedReviewer(
            'independent-demo-reviewer',issuer.public_key_bytes())})
        at=utc_now()
        graph=EpistemicGraph()
        graph.add_node(Node('claim',NodeKind.CLAIM,'Synthetic publication contains an observation',
            Provenance('questioner',SourceKind.HUMAN,'question','fixture:question',at),at))
        artifact=b'SYNTHETIC PUBLICATION: The observation was 18 C.'
        def dns(*args,**kwargs):
            return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443))]
        def transport(*args):
            return (200,{'content-type':'text/plain','content-length':str(len(artifact))},
                    artifact,'a'*64)
        fetcher=SecureSourceFetcher({'demo.example.org'},resolver=dns,transport=transport)
        with EvidenceDatabase.initialize(root/'evidence.sqlite',graph,boundary) as db:
            with VerificationServer(root/'verifier.sock',db,fetcher) as server:
                thread=threading.Thread(target=server.serve_forever,daemon=True)
                thread.start()
                try:
                    retrieved=call_service(root/'verifier.sock','source-retrieve',
                      {'retrieval_id':'r1','url':'https://demo.example.org/publication.txt'},
                      request_id='demo-retrieve')
                    pending=call_service(root/'verifier.sock','submit_source',{
                      'retrieval_id':'r1','submission_id':'s1','evidence_id':'e1',
                      'claim_id':'claim','text':'The observation was 18 C.',
                      'polarity':'supports'},request_id='demo-submit')
                    challenge=call_service(root/'verifier.sock','challenge',{'submission_id':'s1'})
                    receipt=sign_challenge(challenge,issuer,Validation.VERIFIED,
                      'Manually reviewed synthetic fixture',artifact=artifact)
                    accepted=call_service(root/'verifier.sock','accept',{'receipt':receipt},
                      request_id='demo-approve')
                    state=call_service(root/'verifier.sock','assess',{'claim_id':'claim'})
                    report=call_service(root/'verifier.sock','verify')
                    return {'scenario':'synthetic-offline-no-network',
                      'retrieval_id':retrieved['retrieval_id'],
                      'artifact_sha256':retrieved['artifact_sha256'],
                      'receipt_scheme':receipt['schema_version'],
                      'review_accepted':accepted['accepted'],
                      'claim_status':state['assessment']['state'],
                      'source_audit_head':report['source_audit_head'],
                      'source_captures':report['source_captures'],
                      'warning':'Synthetic retrieval. TLS and factual authenticity not tested against live website.'}
                finally:
                    server.shutdown();thread.join(timeout=5)


def main_service(argv: list[str]) -> int:
    parser=argparse.ArgumentParser(prog='rei0',description='REI-0.5 independent source and evidence verifier')
    add_args(parser)
    args=parser.parse_args(argv)
    try:
        result=_run(args)
    except (DurableError, ReviewError, SourceError, ServiceError, ValueError, TypeError,
            OSError,KeyError,json.JSONDecodeError) as exc:
        parser.exit(2,f'REI-0.5 error: {exc}\n')
    print(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False))
    return 0
