"""REI-1.0 local research workspace.

Only artifacts accepted through their existing deterministic replay validators can
be imported. Workspace hashes protect local consistency; they are NOT signatures,
trusted timestamps, evidence of a provider execution, or proof of factual truth.
Private grading keys are NEVER placed in this database.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Any

from .models import canonical_json, digest, NodeKind
from .graph import EpistemicGraph
from .revision import RevisionJournal
from .experiment09 import verify_experiment, EXPERIMENT_SCHEMA

WORKSPACE_SCHEMA = 'rei0.platform.workspace.v1'
ZERO_HASH = '0' * 64
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024


class PlatformError(ValueError):
    pass


def read_document(path: str | Path) -> dict:
    try:
        path = Path(path)
        if path.stat().st_size > MAX_ARTIFACT_BYTES:
            raise PlatformError('artifact exceeds 32 MiB import limit')
        document = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PlatformError(f'cannot load document: {path}') from exc
    if not isinstance(document, dict):
        raise PlatformError('artifact must be a JSON object')
    return document


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _summary_graph(document: dict, *, expected_head: str | None = None) -> dict:
    graph = EpistemicGraph.from_dict(document)  # comprehensive event replay
    if expected_head is not None and graph.audit_head != expected_head:
        raise PlatformError('graph does not match independently retained audit head')
    counts = Counter(n.kind.value for n in graph.nodes.values())
    return {'type': 'epistemic_graph', 'audit_head': graph.audit_head,
            'nodes': len(graph.nodes), 'edges': len(graph.edges),
            'open_questions': len(graph.open_questions()),
            'node_types': dict(sorted(counts.items())), 'method_version': graph.method_version,
            'validation_level': 'graph_event_replay_only',
            'warning': 'Graph validation flags and claims do not independently establish factual truth.'}


def _summary_revision(document: dict, *, expected_head: str | None = None) -> dict:
    journal = RevisionJournal.from_dict(document, expected_head=expected_head)
    latest = journal.latest
    if latest is None:
        states = {}
    else:
        states = dict(Counter(a['state'] for a in latest['assessments'].values()))
    return {'type': 'revision_journal', 'audit_head': journal.audit_head,
            'revision_events': len(journal.events), 'state_counts': states,
            'claims_assessed': len(latest['assessments']) if latest else 0,
            'validation_level': 'journal_event_replay_only',
            'warning': 'Journal integrity does not independently authenticate source evidence or rule signatures.'}


def _summary_experiment(document: dict, inputs: tuple[dict, dict, dict, dict],
                        adjudications: dict) -> dict:
    status = verify_experiment(document, inputs, adjudications)
    study = document['study_report']
    analysis = study['analysis']
    results = {}
    for arm in ('baseline', 'self_critique', 'fixed_depth', 'rei'):
        rec = analysis['raw_evaluation'][arm]
        results[arm] = {'overall_success': rec['overall_success'],
                        'abstention_rate': rec['abstention_rate'],
                        'total_model_calls': rec['total_model_calls'],
                        'total_reported_tokens': rec['total_reported_tokens']}
    prereg = document['preregistration']
    mode = status['mode']
    return {'type': 'preregistered_experiment',
            'study_id': prereg['study_id'],
            'provider_mode': mode, 'model': prereg['provider']['model'],
            'evaluation_cases': status['evaluation_cases'],
            'preregistration_sha256': status['preregistration_sha256'],
            'report_sha256': status['report_sha256'],
            'resource_comparability': status['actual_usage_status'],
            'confirmatory_design_eligible': document['resource_comparability']['confirmatory_design_eligible'],
            'results': results,
            'dataset_digests': prereg['dataset_digests'],
            'validation_level': 'independently_regraded_at_import',
            'warning': ('Synthetic fixtures are integration tests, not empirical findings.'
                        if mode != 'live_external_model' else
                        'Regrading does not authenticate remote execution, evidence quality, or reviewer identity.')}


def validate_artifact(kind: str, document: dict, *, inputs: tuple | None = None,
                      adjudications: dict | None = None,
                      expected_head: str | None = None) -> dict:
    if kind == 'graph':
        return _summary_graph(document, expected_head=expected_head)
    if kind == 'revision':
        return _summary_revision(document, expected_head=expected_head)
    if kind == 'experiment':
        if inputs is None or len(inputs) != 4 or adjudications is None:
            raise PlatformError('experiment import requires four input documents and adjudication manifest')
        if expected_head is not None:
            raise PlatformError('expected-head applies only to graph and revision journals')
        return _summary_experiment(document, inputs, adjudications)
    raise PlatformError('unsupported artifact type')


class ResearchWorkspace:
    """Local, single-file SQLite workspace. Write-once records, hashed append-only ledger."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    @classmethod
    def initialize(cls, path: str | Path) -> 'ResearchWorkspace':
        ws = cls(path)
        if ws.path.exists():
            raise PlatformError('workspace already exists; refusing to overwrite')
        ws.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(ws.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        try:
            with ws._connection() as db:
                db.executescript('''
                    CREATE TABLE config (name TEXT PRIMARY KEY, value TEXT NOT NULL);
                    INSERT INTO config(name,value) VALUES ('schema','rei0.platform.workspace.v1');
                    CREATE TABLE artifacts (
                        id TEXT PRIMARY KEY, kind TEXT NOT NULL,
                        payload TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
                        summary TEXT NOT NULL, summary_sha256 TEXT NOT NULL,
                        imported_at TEXT NOT NULL
                    );
                    CREATE TABLE events (
                        sequence INTEGER PRIMARY KEY, previous_hash TEXT NOT NULL,
                        event_body TEXT NOT NULL, event_hash TEXT NOT NULL,
                        artifact_id TEXT NOT NULL UNIQUE REFERENCES artifacts(id)
                    );
                    CREATE TRIGGER artifacts_no_update BEFORE UPDATE ON artifacts
                        BEGIN SELECT RAISE(ABORT,'artifacts are immutable'); END;
                    CREATE TRIGGER artifacts_no_delete BEFORE DELETE ON artifacts
                        BEGIN SELECT RAISE(ABORT,'artifacts are immutable'); END;
                    CREATE TRIGGER events_no_update BEFORE UPDATE ON events
                        BEGIN SELECT RAISE(ABORT,'audit events are immutable'); END;
                    CREATE TRIGGER events_no_delete BEFORE DELETE ON events
                        BEGIN SELECT RAISE(ABORT,'audit events are immutable'); END;
                ''')
        except BaseException:
            ws.path.unlink(missing_ok=True)
            raise
        return ws

    @contextmanager
    def _connection(self, *, readonly: bool = False):
        if not self.path.is_file():
            raise PlatformError('workspace does not exist; run platform-init first')
        if readonly:
            db = sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True, timeout=10)
        else:
            db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=10000')
        if not readonly:
            db.execute('PRAGMA journal_mode=WAL')
        try:
            yield db
        finally:
            db.close()

    @staticmethod
    def _check_schema(db: sqlite3.Connection) -> None:
        try:
            row = db.execute("SELECT value FROM config WHERE name='schema'").fetchone()
        except sqlite3.DatabaseError as exc:
            raise PlatformError('invalid workspace database') from exc
        if not row or row[0] != WORKSPACE_SCHEMA:
            raise PlatformError('unsupported workspace schema')

    def ingest(self, kind: str, document: dict, *, inputs: tuple | None = None,
               adjudications: dict | None = None, expected_head: str | None = None) -> dict:
        """Validate BEFORE transaction. Insertion + audit record commit atomically."""
        summary = validate_artifact(kind, document, inputs=inputs,
                                    adjudications=adjudications, expected_head=expected_head)
        raw = canonical_json(document)
        if len(raw.encode('utf-8')) > MAX_ARTIFACT_BYTES:
            raise PlatformError('artifact exceeds 32 MiB import limit')
        payload_hash = digest(document)
        summary_raw = canonical_json(summary)
        summary_hash = digest(summary)
        entry_id = kind + '-' + payload_hash[:32]
        now = _timestamp()
        with self._connection() as db:
            self._check_schema(db)
            db.execute('BEGIN IMMEDIATE')
            try:
                existing = db.execute('SELECT payload_sha256,summary_sha256 FROM artifacts WHERE id=?',
                                      (entry_id,)).fetchone()
                if existing:
                    if existing != (payload_hash, summary_hash):
                        raise PlatformError('artifact identity collision or altered validation')
                    db.execute('COMMIT')
                    return {'id':entry_id,'imported':False,'summary':summary}
                prior = db.execute('SELECT sequence,event_hash FROM events ORDER BY sequence DESC LIMIT 1').fetchone()
                seq = (prior[0] + 1) if prior else 1
                prev = prior[1] if prior else ZERO_HASH
                body = {'sequence':seq,'previous_hash':prev,'action':'validated_import',
                        'artifact_id':entry_id,'kind':kind,'payload_sha256':payload_hash,
                        'summary_sha256':summary_hash,'imported_at':now}
                db.execute('INSERT INTO artifacts VALUES (?,?,?,?,?,?,?)',
                           (entry_id,kind,raw,payload_hash,summary_raw,summary_hash,now))
                db.execute('INSERT INTO events VALUES (?,?,?,?,?)',
                           (seq,prev,canonical_json(body),digest(body),entry_id))
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise
        return {'id':entry_id,'imported':True,'summary':summary}

    def entries(self) -> list[dict]:
        with self._connection(readonly=True) as db:
            self._check_schema(db)
            rows = db.execute('SELECT id,kind,summary,imported_at FROM artifacts ORDER BY imported_at,id').fetchall()
        return [{'id':row[0],'kind':row[1],'summary':json.loads(row[2]),'imported_at':row[3]}
                for row in rows]

    def get(self, entry_id: str) -> dict:
        with self._connection(readonly=True) as db:
            self._check_schema(db)
            row = db.execute('SELECT kind,payload,summary,imported_at FROM artifacts WHERE id=?',
                             (entry_id,)).fetchone()
        if row is None:
            raise PlatformError('artifact not found')
        return {'id':entry_id,'kind':row[0], 'document':json.loads(row[1]),
                'summary':json.loads(row[2]), 'imported_at':row[3]}

    def verify(self, *, expected_head: str | None = None) -> dict:
        """Recheck persisted hashes + replay graph/journal; experiment grades require private keys to rerun."""
        with self._connection(readonly=True) as db:
            self._check_schema(db)
            entries = db.execute('SELECT id,kind,payload,payload_sha256,summary,summary_sha256,imported_at FROM artifacts').fetchall()
            events = db.execute('SELECT sequence,previous_hash,event_body,event_hash,artifact_id FROM events ORDER BY sequence').fetchall()
        artifacts = {}
        for entry_id,kind,payload,payload_hash,summary,summary_hash,imported_at in entries:
            try:
                doc, summ = json.loads(payload),json.loads(summary)
                if (digest(doc) != payload_hash or canonical_json(doc) != payload or
                    digest(summ) != summary_hash or canonical_json(summ) != summary or
                    entry_id != kind + '-' + payload_hash[:32] or
                    kind not in ('experiment','graph','revision')):
                    raise PlatformError('artifact hash or canonical content mismatch')
                if kind == 'graph':
                    checked = _summary_graph(doc)
                    if checked != summ:
                        raise PlatformError('graph replay summary differs')
                elif kind == 'revision':
                    checked = _summary_revision(doc)
                    if checked != summ:
                        raise PlatformError('revision replay summary differs')
                else:
                    if doc.get('schema') != EXPERIMENT_SCHEMA or doc.get('report_sha256') != summ['report_sha256']:
                        raise PlatformError('experiment report schema/hash mismatch')
                    if digest({k:v for k,v in doc.items() if k != 'report_sha256'}) != doc['report_sha256']:
                        raise PlatformError('experiment content hash mismatch')
                artifacts[entry_id] = (kind,payload_hash,summary_hash,imported_at)
            except (TypeError,KeyError,ValueError,AttributeError,IndexError) as exc:
                raise PlatformError(f'corrupted artifact: {entry_id}') from exc
        seen = set()
        head = ZERO_HASH
        for seq,prev,body_raw,event_hash,aid in events:
            try:
                body=json.loads(body_raw)
                if (seq != len(seen)+1 or prev != head or body_raw != canonical_json(body)
                    or digest(body) != event_hash or body['sequence'] != seq
                    or body['previous_hash'] != prev or body['artifact_id'] != aid
                    or body['action'] != 'validated_import' or aid in seen or aid not in artifacts):
                    raise PlatformError('audit chain malformed or inconsistent')
                k,ph,sh,when=artifacts[aid]
                if (body['kind'],body['payload_sha256'],body['summary_sha256'],body['imported_at']) != (k,ph,sh,when):
                    raise PlatformError('audit record does not match artifact')
            except (KeyError,ValueError,TypeError) as exc:
                raise PlatformError('malformed audit event') from exc
            seen.add(aid)
            head=event_hash
        if seen != set(artifacts):
            raise PlatformError('some artifacts have no audit events')
        if expected_head is not None and expected_head != head:
            raise PlatformError('workspace head differs from independently retained anchor')
        return {'valid':True,'artifacts':len(artifacts),'events':len(events),
                'audit_head':head,'validation':'local_hashes_and_graph_or_journal_replay',
                'limitation':'Experiment grading was rechecked at import; repeat independent grading with original held-out keys. Hashes are not trusted timestamps.'}

    def overview(self) -> dict:
        entries=self.entries()
        status=self.verify()
        return {'schema':WORKSPACE_SCHEMA,'integrity':status,
                'counts':dict(Counter(e['kind'] for e in entries)),
                'artifacts':entries,
                'limitations':['Offline demos do not establish AI superiority',
                               'No raw prompts or private grading keys are displayed',
                               'This dashboard is a local read-only research summary']}
