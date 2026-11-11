"""Transactional, append-only source-capture ledger for REI-0.5.

The source event head should be anchored outside SQLite. A database administrator
can rewrite the database, so internal hashes alone do not prevent rollback.
"""
from __future__ import annotations

from hashlib import sha256
import json
import sqlite3
from typing import Any

from .models import canonical_json, digest
from .sources import FetchedSource, SourceError

ZERO = '0'*64

DDL = '''
CREATE TABLE IF NOT EXISTS source_records (
  retrieval_id TEXT PRIMARY KEY, metadata_json TEXT NOT NULL,
  content_sha256 TEXT NOT NULL, metadata_digest TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_blobs (
  content_sha256 TEXT PRIMARY KEY, content BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS source_events (
  seq INTEGER PRIMARY KEY, previous_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL UNIQUE, retrieval_id TEXT NOT NULL UNIQUE,
  metadata_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_links (
  submission_id TEXT PRIMARY KEY, retrieval_id TEXT NOT NULL,
  FOREIGN KEY(submission_id) REFERENCES evidence_submissions(submission_id),
  FOREIGN KEY(retrieval_id) REFERENCES source_records(retrieval_id));
CREATE TABLE IF NOT EXISTS source_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
'''


class SourceRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.conn = connection

    def setup(self) -> None:
        self.conn.executescript(DDL)
        self.conn.execute('INSERT OR IGNORE INTO source_meta VALUES (?,?)',('audit_head',ZERO))

    def get(self,retrieval_id: str) -> tuple[dict[str,Any],bytes]:
        row = self.conn.execute('''SELECT r.metadata_json,r.metadata_digest,r.content_sha256,b.content FROM source_records r
              JOIN source_blobs b ON r.content_sha256=b.content_sha256
              WHERE retrieval_id=?''',(retrieval_id,)).fetchone()
        if row is None: raise SourceError('unknown source capture')
        metadata=json.loads(row['metadata_json'])
        payload=bytes(row['content'])
        if (digest(metadata)!=row['metadata_digest'] or
            sha256(payload).hexdigest()!=row['content_sha256'] or
            metadata.get('artifact_sha256')!=row['content_sha256']):
            raise SourceError('source metadata or bytes have been altered')
        return metadata,payload

    def get_metadata(self,retrieval_id: str) -> dict[str,Any]:
        record, _ = self.get(retrieval_id)
        return record

    def store(self,retrieval_id: str, capture: FetchedSource) -> dict:
        if not isinstance(retrieval_id,str) or not (1<=len(retrieval_id)<=128) or not all(
             c.isalnum() or c in '-_.' for c in retrieval_id) or not isinstance(capture,FetchedSource):
            raise SourceError('invalid retrieval ID or source capture')
        metadata = {'retrieval_id':retrieval_id, **capture.metadata()}
        # All hashes/records/events are committed or rolled back together.
        self.conn.execute('BEGIN IMMEDIATE')
        try:
            existing = self.conn.execute('SELECT metadata_json FROM source_records WHERE retrieval_id=?',
                                         (retrieval_id,)).fetchone()
            if existing:
                if json.loads(existing[0]) != metadata:
                    raise SourceError('retrieval ID already used for different source content')
                self.conn.execute('COMMIT')
                return metadata
            content_hash = sha256(capture.content).hexdigest()
            self.conn.execute('INSERT OR IGNORE INTO source_blobs VALUES (?,?)',
                (content_hash,sqlite3.Binary(capture.content)))
            self.conn.execute('INSERT INTO source_records VALUES (?,?,?,?)',
                (retrieval_id,canonical_json(metadata),content_hash,digest(metadata)))
            head = self.conn.execute('SELECT value FROM source_meta WHERE key=?',
                                     ('audit_head',)).fetchone()[0]
            seq = self.conn.execute('SELECT COUNT(*) FROM source_events').fetchone()[0]+1
            new_head = digest({'previous_hash':head,'seq':seq,'metadata':metadata})
            self.conn.execute('INSERT INTO source_events VALUES (?,?,?,?,?)',
                (seq,head,new_head,retrieval_id,canonical_json(metadata)))
            self.conn.execute('UPDATE source_meta SET value=? WHERE key=?',(new_head,'audit_head'))
            self.conn.execute('COMMIT')
            return metadata
        except Exception:
            if self.conn.in_transaction: self.conn.execute('ROLLBACK')
            raise

    def validate(self, *, expected_head: str | None = None, ledger=None) -> dict:
        try:
            rows = list(self.conn.execute('SELECT * FROM source_events ORDER BY seq'))
            head = ZERO
            for n,row in enumerate(rows,1):
                meta = json.loads(row['metadata_json'])
                if (row['seq'] != n or row['previous_hash'] != head or
                    row['event_hash'] != digest({'previous_hash':head,'seq':n,'metadata':meta})):
                    raise SourceError('source audit chain mismatch')
                stored = self.conn.execute('SELECT metadata_json,content_sha256,metadata_digest '
                                           'FROM source_records WHERE retrieval_id=?',
                                           (row['retrieval_id'],)).fetchone()
                if (stored is None or stored['metadata_json'] != canonical_json(meta) or
                    stored['metadata_digest'] != digest(meta) or
                    stored['content_sha256'] != meta['artifact_sha256']):
                    raise SourceError('source metadata mismatch')
                head = row['event_hash']
            saved = self.conn.execute('SELECT value FROM source_meta WHERE key=?',
                                       ('audit_head',)).fetchone()
            if saved is None or saved[0]!=head or (expected_head is not None and expected_head!=head):
                raise SourceError('source audit head mismatch')
            records = self.conn.execute('SELECT COUNT(*) FROM source_records').fetchone()[0]
            if records != len(rows): raise SourceError('source records missing event')
            referenced=set()
            for row in self.conn.execute('SELECT content_sha256 FROM source_records'):
                referenced.add(row[0])
            for row in self.conn.execute('SELECT content_sha256,content FROM source_blobs'):
                data=bytes(row['content'])
                if sha256(data).hexdigest()!=row['content_sha256'] or row['content_sha256'] not in referenced:
                    raise SourceError('source content integrity mismatch')
                referenced.remove(row['content_sha256'])
            if referenced: raise SourceError('source content missing')
            for row in self.conn.execute('''SELECT s.retrieval_id,s.submission_id,r.content_sha256,
                   es.artifact_sha256 FROM source_links s
                   LEFT JOIN source_records r ON r.retrieval_id=s.retrieval_id
                   LEFT JOIN evidence_submissions es ON es.submission_id=s.submission_id'''):
                if row['content_sha256'] is None or row['artifact_sha256']!=row['content_sha256']:
                    raise SourceError('source submission binding mismatch')
            if ledger is not None:
                from urllib.parse import urlsplit
                links={r['submission_id']:r['retrieval_id'] for r in self.conn.execute(
                    'SELECT submission_id,retrieval_id FROM source_links')}
                for sub in ledger.submissions:
                    provenance=ledger.graph.nodes[sub.evidence_id].provenance
                    captured=provenance.source_id.startswith('retrieval:')
                    if captured != (sub.submission_id in links):
                        raise SourceError('source link and evidence provenance disagree')
                    if captured:
                        rid=links[sub.submission_id]
                        meta=self.get_metadata(rid)
                        if (provenance.source_id != 'retrieval:'+rid or
                            provenance.source_kind.value != 'external' or
                            provenance.reference != meta['url'] or
                            provenance.observed_at != meta['retrieved_at'] or
                            provenance.source_group != urlsplit(meta['url']).hostname):
                            raise SourceError('source provenance does not match captured metadata')
            return {'source_audit_head':head,'source_captures':records,
                    'source_linked_submissions':self.conn.execute('SELECT COUNT(*) FROM source_links').fetchone()[0]}
        except (KeyError, TypeError, ValueError, sqlite3.Error) as exc:
            if isinstance(exc, SourceError): raise
            raise SourceError('source registry integrity validation failed') from exc
