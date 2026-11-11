"""REI-1.0 integrated research workspace and local dashboard regression tests."""
import copy
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from rei0.experiment09 import (create_preregistration, fixture_identity, run_preregistered,
    synthetic_adjudications)
from rei0.benchmark import FixtureProvider, BenchmarkError
from rei0.graph import EpistemicGraph
from rei0.models import Node, NodeKind, Provenance, SourceKind, digest
from rei0.platform import (PlatformError, ResearchWorkspace, read_document, validate_artifact)
from rei0.platform_web import render_dashboard, serve
from rei0.revision import RevisionJournal
from rei0.study import StudyConfig

ROOT=Path(__file__).resolve().parent.parent
DATA=ROOT/'rei0'/'data'


def fixture():
    inputs=tuple(read_document(DATA/f'study_{phase}_{part}.json')
                 for phase in ('calibration','evaluation') for part in ('cases','keys'))
    doc=read_document(DATA/'benchmark_fixture.json')
    adjudications=synthetic_adjudications(inputs[1],inputs[3])
    prereg=create_preregistration(*inputs,adjudications,fixture_identity(doc),
        study_id='REI10-TEST',registered_at='2026-11-10T00:00:00Z',
        config=StudyConfig(repetitions=1,bootstrap_repetitions=100))
    report=run_preregistered(prereg,inputs,adjudications,lambda:FixtureProvider(doc))
    return report,inputs,adjudications


def graph():
    g=EpistemicGraph(method_version='test-1.0')
    at='2026-11-10T00:00:00Z'
    p=Provenance('test',SourceKind.SYSTEM,'test','synthetic',at)
    g.add_node(Node('c1',NodeKind.CLAIM,'test claim',p,at))
    return g


class PlatformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report,cls.inputs,cls.adjudications=fixture()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'workspace.db'
        self.ws=ResearchWorkspace.initialize(self.path)

    def test_empty_workspace_valid(self):
        self.assertEqual(self.ws.verify()['artifacts'],0)
        self.assertEqual(self.ws.verify()['audit_head'],'0'*64)

    def test_exclusive_init_does_not_clobber_existing(self):
        with self.assertRaises(PlatformError): ResearchWorkspace.initialize(self.path)
        self.assertEqual(self.ws.verify()['artifacts'],0)

    def test_created_file_private(self):
        self.assertEqual(self.path.stat().st_mode & 0o777,0o600)

    def test_graph_import_and_replay(self):
        r=self.ws.ingest('graph',graph().to_dict())
        self.assertTrue(r['imported'])
        self.assertEqual(r['summary']['nodes'],1)
        self.assertEqual(self.ws.verify()['events'],1)

    def test_graph_reimport_idempotent(self):
        doc=graph().to_dict()
        first=self.ws.ingest('graph',doc)
        other=self.ws.ingest('graph',doc)
        self.assertFalse(other['imported'])
        self.assertEqual(first['id'],other['id'])
        self.assertEqual(self.ws.verify()['events'],1)

    def test_graph_invalid_audit_chain_rejected(self):
        doc=graph().to_dict();doc['events'][0]['payload']['text']='fake'
        with self.assertRaises(ValueError): self.ws.ingest('graph',doc)
        self.assertEqual(self.ws.verify()['events'],0)

    def test_external_anchor_graph(self):
        doc=graph().to_dict()
        self.assertTrue(self.ws.ingest('graph',doc,expected_head=EpistemicGraph.from_dict(doc).audit_head)['imported'])
        with self.assertRaises(PlatformError): self.ws.ingest('graph',doc,expected_head='f'*64)

    def test_experiment_regraded_on_import(self):
        out=self.ws.ingest('experiment',self.report,inputs=self.inputs,adjudications=self.adjudications)
        self.assertEqual(out['summary']['validation_level'],'independently_regraded_at_import')
        self.assertFalse(out['summary']['confirmatory_design_eligible'])
        self.assertIn('Synthetic fixtures',out['summary']['warning'])
        self.assertEqual(len(out['summary']['results']),4)

    def test_experiment_requires_private_keys_at_import(self):
        with self.assertRaises(PlatformError):self.ws.ingest('experiment',self.report)
        self.assertEqual(self.ws.verify()['events'],0)

    def test_experiment_wrong_grading_key_rejected(self):
        inputs=list(copy.deepcopy(self.inputs))
        inputs[3]['answers'][0]['answer']='wrong'
        with self.assertRaises((BenchmarkError,ValueError,KeyError)):
            self.ws.ingest('experiment',self.report,inputs=tuple(inputs),adjudications=self.adjudications)
        self.assertEqual(self.ws.verify()['events'],0)

    def test_experiment_forged_metrics_rejected(self):
        doc=copy.deepcopy(self.report)
        doc['study_report']['analysis']['raw_evaluation']['rei']['overall_success']=1.0
        doc['report_sha256']=digest({k:v for k,v in doc.items() if k!='report_sha256'})
        with self.assertRaises((BenchmarkError,ValueError)):
            self.ws.ingest('experiment',doc,inputs=self.inputs,adjudications=self.adjudications)

    def test_experiment_wrong_reviewer_manifest_rejected(self):
        adj=copy.deepcopy(self.adjudications)
        adj['records'][0]['reviewer']=adj['records'][0]['curator']
        with self.assertRaises((BenchmarkError,ValueError)):
            self.ws.ingest('experiment',self.report,inputs=self.inputs,adjudications=adj)

    def test_experiment_model_identity_and_usage_visible(self):
        s=self.ws.ingest('experiment',self.report,inputs=self.inputs,adjudications=self.adjudications)['summary']
        self.assertEqual(s['resource_comparability'],'imbalanced')
        self.assertEqual(s['provider_mode'],'scripted_fixture_not_empirical')

    def test_graph_and_experiment_in_one_workspace(self):
        self.ws.ingest('graph',graph().to_dict())
        self.ws.ingest('experiment',self.report,inputs=self.inputs,adjudications=self.adjudications)
        self.assertEqual(self.ws.overview()['counts'],{'graph':1,'experiment':1})

    def test_revision_journal_roundtrip(self):
        j=RevisionJournal()
        out=self.ws.ingest('revision',j.to_dict(),expected_head=j.audit_head)
        self.assertEqual(out['summary']['revision_events'],0)
        self.assertEqual(self.ws.verify()['artifacts'],1)

    def test_revision_anchor_mismatch(self):
        with self.assertRaises(ValueError):
            self.ws.ingest('revision',RevisionJournal().to_dict(),expected_head='f'*64)

    def test_tampered_payload_detected(self):
        self.ws.ingest('graph',graph().to_dict())
        with sqlite3.connect(self.path) as db:
            db.execute('DROP TRIGGER artifacts_no_update')
            db.execute('UPDATE artifacts SET payload=?',('{}',))
        with self.assertRaises(PlatformError):self.ws.verify()

    def test_tampered_summary_detected(self):
        self.ws.ingest('graph',graph().to_dict())
        with sqlite3.connect(self.path) as db:
            db.execute('DROP TRIGGER artifacts_no_update')
            db.execute('UPDATE artifacts SET summary=?',('{}',))
        with self.assertRaises(PlatformError):self.ws.verify()

    def test_write_once_trigger(self):
        self.ws.ingest('graph',graph().to_dict())
        with self.assertRaises(sqlite3.DatabaseError):
            with sqlite3.connect(self.path) as db:db.execute('DELETE FROM artifacts')

    def test_tampered_audit_detected(self):
        self.ws.ingest('graph',graph().to_dict())
        with sqlite3.connect(self.path) as db:
            db.execute('DROP TRIGGER events_no_update')
            db.execute("UPDATE events SET previous_hash=?",('9'*64,))
        with self.assertRaises(PlatformError):self.ws.verify()

    def test_external_workspace_anchor(self):
        head=self.ws.verify()['audit_head']
        self.assertTrue(self.ws.verify(expected_head=head)['valid'])
        with self.assertRaises(PlatformError):self.ws.verify(expected_head='f'*64)

    def test_redacted_dashboard_excludes_raw_graph_claim(self):
        g=graph(); self.ws.ingest('graph',g.to_dict())
        html=render_dashboard(self.ws.overview())
        self.assertIn('REI 1.0',html)
        self.assertNotIn('test claim',html)
        self.assertNotIn('synthetic:not-factual',html)

    def test_no_raw_answer_keys_in_summary(self):
        self.ws.ingest('experiment',self.report,inputs=self.inputs,adjudications=self.adjudications)
        summary=self.ws.overview()
        self.assertNotIn('answers',json.dumps(summary))
        self.assertNotIn('reviewer',json.dumps(summary))

    def test_read_document_limit_and_invalid_json(self):
        p=Path(self.tmp.name)/'bad.json';p.write_text('not json')
        with self.assertRaises(PlatformError):read_document(p)
        p.write_text('[]')
        with self.assertRaises(PlatformError):read_document(p)

    def test_unrecognized_artifact_type(self):
        with self.assertRaises(PlatformError):validate_artifact('unknown',{})

    def test_api_read_only_localhost(self):
        self.ws.ingest('graph',graph().to_dict())
        server=serve(self.path,0)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
        c.request('GET','/api/summary',headers={'Host':'127.0.0.1'})
        r=c.getresponse();data=r.read()
        self.assertEqual(r.status,200)
        self.assertIn('no-store',r.getheader('Cache-Control'))
        self.assertEqual(json.loads(data)['integrity']['artifacts'],1)
        c.request('POST','/',body=b'{}',headers={'Host':'127.0.0.1'})
        self.assertEqual(c.getresponse().status,405)
        c.request('GET','/',headers={'Host':'evil.example'})
        self.assertEqual(c.getresponse().status,403)
        c.request('GET','/file.json',headers={'Host':'127.0.0.1'})
        self.assertEqual(c.getresponse().status,404)
        c.close()


if __name__=='__main__':
    unittest.main()
