"""Fresh-process CLI workflow, with review secret only in the subprocess env."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from rei0 import EpistemicGraph, Node, NodeKind, Provenance, SourceKind

T = '2026-11-10T19:30:00Z'
ROOT = Path(__file__).resolve().parent.parent

class EvidenceCLITests(unittest.TestCase):
    def invoke(self, *args, succeed=True):
        env={**os.environ, 'REI_REVIEW_KEY_HEX':'ab'*32,
             'REI_REVIEW_KEY_ID':'unit-key','REI_REVIEWER_ID':'independent'}
        result=subprocess.run([sys.executable,'-m','rei0',*map(str,args)],cwd=ROOT,
                              env=env,capture_output=True,text=True)
        if succeed:
            self.assertEqual(result.returncode,0,result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode,0)
        return result.stderr

    def test_full_authenticated_pipeline_and_external_anchor(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            graph=EpistemicGraph(clock=lambda:T)
            graph.add_node(Node('claim',NodeKind.CLAIM,'Test the claim',
                                Provenance('researcher',SourceKind.HUMAN,'prompt','local',T),T))
            graph.save(root/'graph.json')
            (root/'original.txt').write_text('source bytes original',encoding='utf-8')
            self.invoke('evidence-init',root/'graph.json',root/'ledger.json')
            ingest=self.invoke('evidence-submit',root/'ledger.json',
                               '--submission-id','submission-1','--evidence-id','source-node',
                               '--claim','claim','--text','the source reports a test result',
                               '--artifact',root/'original.txt','--polarity','supports',
                               '--source-id','test-source','--source-kind','external',
                               '--source-group','study-A','--reference','doi:example.test',
                               '--observed-at',T)
            self.assertEqual(ingest['status'],'pending')
            self.assertEqual(self.invoke('evidence-assess',root/'ledger.json','claim')['assessment']['state'],'NEITHER')
            signed=self.invoke('evidence-sign',root/'ledger.json','submission-1',
                               '--decision','verified','--reason','human reviewed original',
                               '--receipt',root/'receipt.json')
            self.assertTrue(signed['ledger_not_modified'])
            self.assertEqual(self.invoke('evidence-assess',root/'ledger.json','claim')['assessment']['state'],'NEITHER')
            self.invoke('evidence-accept',root/'ledger.json',root/'receipt.json')
            self.assertEqual(self.invoke('evidence-assess',root/'ledger.json','claim')['assessment']['state'],'SUPPORT_ONLY')
            verification=self.invoke('evidence-verify',root/'ledger.json')
            self.assertEqual(verification['verified_receipts'],1)
            self.invoke('evidence-verify',root/'ledger.json',
                        '--expected-head',verification['audit_head'],
                        '--expected-graph-head',verification['graph_audit_head'])
            self.assertTrue(self.invoke('evidence-check-artifact',root/'ledger.json',
                                        'submission-1',root/'original.txt')['matches'])
            (root/'original.txt').write_text('modified bytes',encoding='utf-8')
            self.assertIn('mismatch',self.invoke('evidence-check-artifact',root/'ledger.json',
                                               'submission-1',root/'original.txt',succeed=False))
            self.assertIn('anchor',self.invoke('evidence-verify',root/'ledger.json',
                                             '--expected-head','0'*64,succeed=False))
            self.invoke('evidence-review',root/'ledger.json','submission-1',
                        '--decision','revoked','--reason','review withdrawn')
            self.assertEqual(self.invoke('evidence-assess',root/'ledger.json','claim')['assessment']['state'],'NEITHER')

    def test_no_review_key_fails_closed(self):
        env={k:v for k,v in os.environ.items() if k not in ('REI_REVIEW_KEY_HEX',)}
        result=subprocess.run([sys.executable,'-m','rei0','evidence-demo','--ledger','any.json'],
                              cwd=ROOT,env=env,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('REI_REVIEW_KEY_HEX required',result.stderr)

    def test_ephemeral_demo_does_not_persist_key(self):
        output=self.invoke('evidence-demo')
        self.assertEqual(output['assessment']['state'],'BOTH')
        self.assertFalse(output['fact_checked'])
        self.assertFalse(output['key_persisted'])

if __name__ == '__main__': unittest.main()
