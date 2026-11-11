"""REI-0.4 transactional evidence store (SQLite, no network and no signer).

The REI-0.3 ledger is the canonical, replay-validated logical state. Its
snapshot, relational audit mirror, and content-addressed original bytes are
written in one SQLite transaction. Signing is NEVER exposed by this module.
"""
from __future__ import annotations

import base64
import binascii
import json
from hashlib import sha256
from pathlib import Path
import os
import stat
import sqlite3
from typing import Any

from .evidence import EvidenceLedger, EvidenceError
from .graph import EpistemicGraph
from .models import EdgeKind, Provenance, SourceKind, canonical_json, digest
from .review import ReviewReceipt, VerificationBoundary
from .source_store import SourceRepository
from .sources import SourceError
from urllib.parse import urlsplit


class DurableError(ValueError):
    """Malformed, inconsistent, stale, or unauthorized durable operation."""


SCHEMA = 'rei0.sqlite.v1'
DDL = '''
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE ledger_snapshot (
 id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL CHECK(revision>=0),
 document TEXT NOT NULL, audit_head TEXT NOT NULL, graph_head TEXT NOT NULL);
CREATE TABLE evidence_events (
 sequence INTEGER PRIMARY KEY, previous_hash TEXT NOT NULL,
 event_hash TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE evidence_submissions (
 submission_id TEXT PRIMARY KEY, evidence_id TEXT NOT NULL UNIQUE,
 link_id TEXT NOT NULL UNIQUE, claim_id TEXT NOT NULL,
 artifact_sha256 TEXT NOT NULL, submitted_at TEXT NOT NULL);
CREATE TABLE evidence_reviews (
 submission_id TEXT NOT NULL, decision_index INTEGER NOT NULL,
 signature TEXT NOT NULL UNIQUE, receipt TEXT NOT NULL,
 PRIMARY KEY(submission_id,decision_index),
 FOREIGN KEY(submission_id) REFERENCES evidence_submissions(submission_id));
CREATE TABLE artifacts (
 sha256 TEXT PRIMARY KEY, payload BLOB NOT NULL,
 size_bytes INTEGER NOT NULL CHECK(size_bytes>0 AND size_bytes<=2000000));
CREATE TABLE legacy_artifact_gaps (
 submission_id TEXT PRIMARY KEY, artifact_sha256 TEXT NOT NULL,
 FOREIGN KEY(submission_id) REFERENCES evidence_submissions(submission_id));
CREATE TABLE requests (
 request_id TEXT PRIMARY KEY, request_digest TEXT NOT NULL, response TEXT NOT NULL);
'''


def _json(value: Any) -> str:
    return canonical_json(value)


def _strict_keys(value: Any, keys: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise DurableError('unexpected or missing request fields')
    return value


class EvidenceDatabase:
    """SQLite atomic writer with replay-verified ledger and relational mirrors.

    All writes use BEGIN IMMEDIATE. Revision numbers and request IDs protect
    concurrent/stale and retried writes. This is not a tamper-proof database:
    keep a trusted *external* audit head for rollback detection.
    """

    def __init__(self, path: str | Path, boundary: VerificationBoundary):
        self.path = Path(path)
        if not self.path.is_file():
            raise DurableError('database does not exist; initialize it first')
        if not isinstance(boundary, VerificationBoundary):
            raise DurableError('independent verification boundary required')
        if os.name != 'nt':
            st = self.path.lstat()
            if not stat.S_ISREG(st.st_mode) or st.st_mode & 0o077 or st.st_uid != os.geteuid():
                raise DurableError('database must be owner-only regular file (chmod 600)')
        self.boundary = boundary
        self.conn = sqlite3.connect(str(self.path), timeout=15, isolation_level=None, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._configure()
        SourceRepository(self.conn).setup()
        self.check()

    def _configure(self) -> None:
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.execute('PRAGMA busy_timeout=15000')
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.execute('PRAGMA synchronous=FULL')

    @classmethod
    def initialize(cls, path: str | Path, graph: EpistemicGraph,
                   boundary: VerificationBoundary) -> 'EvidenceDatabase':
        if not isinstance(graph, EpistemicGraph):
            raise DurableError('validated graph required')
        return cls._create(path, EvidenceLedger(EpistemicGraph.from_dict(graph.to_dict()), boundary), boundary, legacy=False)

    @classmethod
    def import_legacy(cls, path: str | Path, original: dict[str, Any],
                      boundary: VerificationBoundary) -> 'EvidenceDatabase':
        """Import verified REI-0.3 JSON. Artifact BYTES weren't in old JSON.

        Imported evidence retains signed approval, but artifacts are marked as
        unavailable, never fabricated. Use archive originals for a later recovery.
        """
        ledger = EvidenceLedger.from_dict(original, boundary)
        return cls._create(path, ledger, boundary, legacy=True)

    @classmethod
    def _create(cls, path: str | Path, ledger: EvidenceLedger,
                boundary: VerificationBoundary, *, legacy: bool) -> 'EvidenceDatabase':
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            os.close(fd)
        except FileExistsError as exc:
            raise DurableError('refusing to overwrite an existing database') from exc
        old_mask = os.umask(0o077)
        try:
            conn = sqlite3.connect(str(path), isolation_level=None)
        finally:
            os.umask(old_mask)
        try:
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=FULL')
            conn.execute('BEGIN IMMEDIATE')
            try:
                conn.executescript(DDL)  # sqlite executescript commits; begin again for data
                conn.execute('BEGIN IMMEDIATE')
                conn.execute('INSERT INTO metadata VALUES (?,?)', ('schema', SCHEMA))
                conn.execute('INSERT INTO ledger_snapshot VALUES (1,?,?,?,?)',
                             (0, _json(ledger.to_dict()), ledger.audit_head, ledger.graph.audit_head))
                cls._insert_mirror(conn, ledger)
                if legacy:
                    for sub in ledger.submissions:
                        conn.execute('INSERT INTO legacy_artifact_gaps VALUES (?,?)',
                                     (sub.submission_id,sub.artifact_sha256))
                conn.execute('COMMIT')
            except Exception:
                if conn.in_transaction:
                    conn.execute('ROLLBACK')
                raise
        finally:
            conn.close()
        return cls(path, boundary)

    @staticmethod
    def _insert_mirror(conn: sqlite3.Connection, ledger: EvidenceLedger) -> None:
        for event in ledger.events:
            conn.execute('INSERT INTO evidence_events VALUES (?,?,?,?,?)',
                         (event['sequence'], event['previous_hash'], event['event_hash'],
                          event['kind'], _json(event['payload'])))
        for sub in ledger.submissions:
            conn.execute('INSERT INTO evidence_submissions VALUES (?,?,?,?,?,?)',
                         (sub.submission_id, sub.evidence_id, sub.link_id, sub.claim_id,
                          sub.artifact_sha256, sub.submitted_at))
        for receipt in ledger.review_receipts:
            conn.execute('INSERT INTO evidence_reviews VALUES (?,?,?,?)',
                         (receipt.submission_id, receipt.decision_index,
                          receipt.signature, _json(receipt.to_dict())))

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> 'EvidenceDatabase':
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _state(self) -> tuple[EvidenceLedger, int]:
        version = self.conn.execute('SELECT value FROM metadata WHERE key=?', ('schema',)).fetchone()
        if version is None or version[0] != SCHEMA:
            raise DurableError('unsupported database schema')
        row = self.conn.execute('SELECT * FROM ledger_snapshot WHERE id=1').fetchone()
        if row is None:
            raise DurableError('ledger snapshot is missing')
        ledger = EvidenceLedger.from_dict(json.loads(row['document']), self.boundary)
        if ledger.audit_head != row['audit_head'] or ledger.graph.audit_head != row['graph_head']:
            raise DurableError('stored audit heads do not match replayed ledger')
        self._check_mirror(ledger)
        SourceRepository(self.conn).validate(ledger=ledger)
        return ledger, int(row['revision'])

    def _check_mirror(self, ledger: EvidenceLedger) -> None:
        events = [(e['sequence'], e['previous_hash'], e['event_hash'],e['kind'],_json(e['payload']))
                  for e in ledger.events]
        rows = [tuple(r) for r in self.conn.execute(
            'SELECT sequence, previous_hash,event_hash,kind,payload FROM evidence_events ORDER BY sequence')]
        if events != rows:
            raise DurableError('evidence audit mirror does not match signed event replay')
        subs = [(s.submission_id,s.evidence_id,s.link_id,s.claim_id,s.artifact_sha256,s.submitted_at)
                for s in ledger.submissions]
        rows = [tuple(r) for r in self.conn.execute('SELECT * FROM evidence_submissions ORDER BY submission_id')]
        if subs != rows:
            raise DurableError('evidence submission mirror mismatch')
        receipts = sorted([(r.submission_id,r.decision_index,r.signature,_json(r.to_dict()))
                          for r in ledger.review_receipts])
        rows = [tuple(r) for r in self.conn.execute(
            'SELECT submission_id,decision_index,signature,receipt FROM evidence_reviews '
            'ORDER BY submission_id,decision_index')]
        if receipts != rows:
            raise DurableError('review receipt mirror mismatch')
        for row in self.conn.execute('SELECT sha256,payload,size_bytes FROM artifacts'):
            data = bytes(row['payload'])
            if len(data) != row['size_bytes'] or sha256(data).hexdigest() != row['sha256']:
                raise DurableError('original artifact integrity mismatch')
        gaps = {r['submission_id']:r['artifact_sha256'] for r in self.conn.execute(
            'SELECT submission_id,artifact_sha256 FROM legacy_artifact_gaps')}
        indexed = {s.submission_id:s.artifact_sha256 for s in ledger.submissions}
        if any(indexed.get(sid) != artifact for sid,artifact in gaps.items()):
            raise DurableError('legacy artifact exception does not match imported submission')
        for submission in ledger.submissions:
            available = self.conn.execute('SELECT 1 FROM artifacts WHERE sha256=?',
                                          (submission.artifact_sha256,)).fetchone()
            if not available and submission.submission_id not in gaps:
                raise DurableError('original artifact bytes unexpectedly missing')
        # Every stored artifact must belong to at least one submission; legacy
        # submissions may have no original bytes, but cannot invent a blob.
        referenced = {s.artifact_sha256 for s in ledger.submissions}
        for row in self.conn.execute('SELECT sha256 FROM artifacts'):
            if row[0] not in referenced:
                raise DurableError('unreferenced artifact in database')

    def check(self, *, expected_head: str | None = None,
              expected_graph_head: str | None = None,
              expected_source_head: str | None = None) -> dict[str, Any]:
        result = self.conn.execute('PRAGMA integrity_check').fetchone()
        if not result or result[0] != 'ok':
            raise DurableError('SQLite integrity check failed')
        ledger, revision = self._state()
        if expected_head is not None and expected_head != ledger.audit_head:
            raise DurableError('audit head does not match externally trusted anchor')
        if expected_graph_head is not None and expected_graph_head != ledger.graph.audit_head:
            raise DurableError('graph head does not match externally trusted anchor')
        missing = [s.submission_id for s in ledger.submissions if not self.conn.execute(
            'SELECT 1 FROM artifacts WHERE sha256=?', (s.artifact_sha256,)).fetchone()]
        source_report = SourceRepository(self.conn).validate(expected_head=expected_source_head, ledger=ledger)
        return {'valid': True, **source_report, 'schema': SCHEMA, 'revision':revision,
                'submissions':len(ledger.submissions), 'reviews':len(ledger.review_receipts),
                'evidence_audit_head':ledger.audit_head,
                'graph_audit_head':ledger.graph.audit_head,
                'original_artifacts_unavailable':missing,
                'warning':'Authenticated reviews do not establish factual truth.'}

    def status(self) -> dict[str, Any]:
        ledger, revision = self._state()
        return {'revision': revision, 'submissions':len(ledger.submissions),
                'reviews':len(ledger.review_receipts), 'evidence_audit_head':ledger.audit_head,
                'graph_audit_head':ledger.graph.audit_head}

    def assess(self, claim_id: str) -> dict[str, Any]:
        ledger, revision = self._state()
        return {'revision': revision, 'assessment':ledger.assess(claim_id).to_dict()}

    def challenge(self, submission_id: str) -> dict[str, Any]:
        ledger, revision = self._state()
        s = next((s for s in ledger.submissions if s.submission_id == submission_id), None)
        if s is None:
            raise DurableError('unknown submission')
        receipts = [r for r in ledger.review_receipts if r.submission_id == submission_id]
        node = ledger.graph.nodes[s.evidence_id]
        return {'schema_version':'rei0.challenge.v1', 'revision':revision,
                'submission_id':s.submission_id, 'subject_digest':ledger.subject_digest(submission_id),
                'decision_index':len(receipts)+1,
                'prior_signature':receipts[-1].signature if receipts else '0'*64,
                'current_status':receipts[-1].decision.value if receipts else 'pending',
                'artifact_sha256':s.artifact_sha256,
                'artifact_available': bool(self.conn.execute(
                    'SELECT 1 FROM artifacts WHERE sha256=?',(s.artifact_sha256,)).fetchone()),
                'evidence_text':node.text, 'provenance':node.provenance.to_dict(),
                'claim':ledger.graph.nodes[s.claim_id].text,
                'polarity':ledger.graph.edges[s.link_id].kind.value}

    def source_store(self, retrieval_id: str, capture) -> dict[str, Any]:
        repo = SourceRepository(self.conn)
        repo.validate()
        result = repo.store(retrieval_id,capture)
        repo.validate()
        return result

    def source_metadata(self, retrieval_id: str) -> dict[str, Any]:
        return SourceRepository(self.conn).get_metadata(retrieval_id)

    def apply(self, op: str, body: dict[str, Any], request_id: str,
              *, expected_revision: int | None = None) -> dict[str, Any]:
        if op not in ('submit','submit_source','accept') or not isinstance(body, dict):
            raise DurableError('only submit, submit_source and accept are permitted mutations')
        if not isinstance(request_id,str) or not (1 <= len(request_id) <= 128):
            raise DurableError('request_id required, max 128 characters')
        request_hash = digest({'op':op,'body':body, 'expected_revision': expected_revision})
        self.conn.execute('BEGIN IMMEDIATE')
        try:
            old = self.conn.execute('SELECT request_digest,response FROM requests WHERE request_id=?',
                                    (request_id,)).fetchone()
            if old is not None:
                if old['request_digest'] != request_hash:
                    raise DurableError('request ID reused with different content')
                result = json.loads(old['response'])
                self.conn.execute('COMMIT')
                return result
            ledger, revision = self._state()
            if expected_revision is not None and (type(expected_revision) is not int or
                                                   expected_revision != revision):
                raise DurableError('stale expected revision')
            previous_events = len(ledger.events)
            if op == 'submit_source':
                _strict_keys(body, {'retrieval_id','submission_id','evidence_id',
                                    'claim_id','text','polarity'})
                metadata, artifact = SourceRepository(self.conn).get(body['retrieval_id'])
                # For text formats, require the asserted quotation to occur in
                # captured bytes; semantic relevance still requires human review.
                if metadata['content_type'] != 'application/pdf':
                    try: content = artifact.decode('utf-8')
                    except UnicodeError as exc: raise SourceError('source text is not UTF-8') from exc
                    if not isinstance(body['text'],str) or body['text'] not in content:
                        raise SourceError('asserted text is not an exact source excerpt')
                import urllib.parse
                source_provenance = Provenance(
                    'retrieval:'+body['retrieval_id'], SourceKind.EXTERNAL,
                    urlsplit(metadata['url']).hostname,metadata['url'],metadata['retrieved_at'])
                link_retrieval_id = body['retrieval_id']
                body = {'submission_id':body['submission_id'],
                        'evidence_id':body['evidence_id'],'claim_id':body['claim_id'],
                        'text':body['text'],'polarity':body['polarity'],
                        'artifact_b64':base64.b64encode(artifact).decode('ascii'),
                        'provenance':source_provenance.to_dict()}
            else:
                link_retrieval_id = None
            if op in ('submit','submit_source'):
                _strict_keys(body, {'submission_id','evidence_id','claim_id','text','artifact_b64',
                                    'provenance','polarity'})
                if not isinstance(body['artifact_b64'],str) or len(body['artifact_b64']) > 2_670_000:
                    raise DurableError('artifact exceeds encoded size limit')
                try:
                    artifact = base64.b64decode(body['artifact_b64'], validate=True)
                except (binascii.Error, ValueError) as exc:
                    raise DurableError('invalid artifact base64') from exc
                provenance = Provenance.from_dict(body['provenance'])
                if op == 'submit' and provenance.source_id.startswith('retrieval:'):
                    raise DurableError('retrieval: provenance prefix reserved for verified source captures')
                submission = ledger.submit(submission_id=body['submission_id'],
                    evidence_id=body['evidence_id'], claim_id=body['claim_id'],
                    text=body['text'], artifact_bytes=artifact, provenance=provenance,
                    polarity=EdgeKind(body['polarity']))
                artifact_hash = sha256(artifact).hexdigest()
                self.conn.execute('INSERT OR IGNORE INTO artifacts VALUES (?,?,?)',
                                  (artifact_hash, sqlite3.Binary(artifact),len(artifact)))
                result = {'submission':submission.to_dict(), 'status':'pending'}
                if link_retrieval_id is not None:
                    result['retrieval_id'] = link_retrieval_id
                self.conn.execute('INSERT INTO evidence_submissions VALUES (?,?,?,?,?,?)',
                                  tuple(submission.to_dict()[k] for k in (
                                      'submission_id','evidence_id','link_id','claim_id',
                                      'artifact_sha256','submitted_at')))
                if link_retrieval_id is not None:
                    self.conn.execute('INSERT INTO source_links VALUES (?,?)',
                                      (submission.submission_id,link_retrieval_id))
            else:
                _strict_keys(body, {'receipt'})
                receipt = ReviewReceipt.from_dict(body['receipt'])
                ledger.accept(receipt)
                self.conn.execute('INSERT INTO evidence_reviews VALUES (?,?,?,?)',
                    (receipt.submission_id,receipt.decision_index,receipt.signature,
                     _json(receipt.to_dict())))
                result = {'accepted':True, 'submission_id':receipt.submission_id,
                          'decision':receipt.decision.value}
            for event in ledger.events[previous_events:]:
                self.conn.execute('INSERT INTO evidence_events VALUES (?,?,?,?,?)',
                     (event['sequence'],event['previous_hash'],event['event_hash'],
                      event['kind'],_json(event['payload'])))
            self.conn.execute('UPDATE ledger_snapshot SET revision=?,document=?,audit_head=?,graph_head=? WHERE id=1',
                (revision+1,_json(ledger.to_dict()),ledger.audit_head,ledger.graph.audit_head))
            result.update({'revision':revision+1,'evidence_audit_head':ledger.audit_head,
                           'graph_audit_head':ledger.graph.audit_head})
            self.conn.execute('INSERT INTO requests VALUES (?,?,?)',
                              (request_id,request_hash,_json(result)))
            self.conn.execute('COMMIT')
            return result
        except Exception:
            if self.conn.in_transaction:
                self.conn.execute('ROLLBACK')
            raise
