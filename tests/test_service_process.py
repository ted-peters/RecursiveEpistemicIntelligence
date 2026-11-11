"""Cross-process end-to-end CLI test: reviewer signing is NOT an RPC."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from rei0.graph import EpistemicGraph,utc_now
from rei0.models import Node,NodeKind,Provenance,SourceKind

ROOT=Path(__file__).resolve().parents[1]


class ProcessWorkflowTests(unittest.TestCase):
    def run_cli(self, *args):
        cmd=[sys.executable,'-m','rei0',*map(str,args)]
        out=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=30)
        if out.returncode: raise AssertionError(f'CLI failed {cmd}: {out.stderr}\n{out.stdout}')
        return json.loads(out.stdout)

    @unittest.skipUnless(hasattr(__import__('socket'),'AF_UNIX'),'requires Unix sockets')
    def test_independent_process_submit_sign_accept_revoke(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            trust,signer=root/'trust.json',root/'signer.json'
            db,sock=root/'state.db',root/'api.sock'
            graph_file=root/'graph.json'
            original=root/'observation.txt'
            original.write_text('synthetic verified evidence',encoding='utf-8')
            graph=EpistemicGraph(); now=utc_now()
            graph.add_node(Node('claim',NodeKind.CLAIM,'Provisional claim',
                Provenance('question',SourceKind.HUMAN,'question','fixture:question',now),now))
            graph.save(graph_file)
            self.assertTrue(self.run_cli('service-keygen','--trust',trust,'--signer',signer)['created'])
            self.assertTrue(self.run_cli('service-init',graph_file,db,'--trust',trust)['valid'])
            proc=subprocess.Popen([sys.executable,'-m','rei0','service-serve',str(db),
                '--socket',str(sock),'--trust',str(trust)],
                cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                deadline=time.monotonic()+8
                while not sock.exists() and proc.poll() is None and time.monotonic()<deadline:
                    time.sleep(.05)
                self.assertTrue(sock.exists(),'service failed to start')
                self.assertEqual(self.run_cli('service-status','--socket',sock)['revision'],0)
                pending=self.run_cli('service-submit','--socket',sock,
                    '--submission-id','s1','--evidence-id','e1','--claim','claim',
                    '--text','A synthetic observation','--artifact',original,'--polarity','supports',
                    '--source-id','external-one','--source-kind','external','--source-group','group1',
                    '--reference','fixture:observation')
                self.assertEqual(pending['status'],'pending')
                self.assertEqual(self.run_cli('service-assess','--socket',sock,'--claim','claim')['assessment']['state'],
                                 'NEITHER')
                challenge=root/'challenge.json'; receipt=root/'receipt.json'
                self.run_cli('service-challenge','--socket',sock,'--submission-id','s1','--output',challenge)
                signer_result=self.run_cli('operator-sign','--challenge',challenge,'--signer',signer,
                    '--decision','verified','--reason','independently inspected synthetic fixture',
                    '--artifact',original,'--output',receipt)
                self.assertTrue(signer_result['ledger_modified'] is False)
                self.run_cli('service-accept','--socket',sock,'--receipt',receipt)
                self.assertEqual(self.run_cli('service-assess','--socket',sock,'--claim','claim')['assessment']['state'],
                                 'SUPPORT_ONLY')
                new_challenge=root/'revoke-challenge.json'; revoke=root/'revoke.json'
                self.run_cli('service-challenge','--socket',sock,'--submission-id','s1',
                             '--output',new_challenge)
                self.run_cli('operator-sign','--challenge',new_challenge,'--signer',signer,
                    '--decision','revoked','--reason','synthetic source withdrawn','--output',revoke)
                self.run_cli('service-accept','--socket',sock,'--receipt',revoke)
                self.assertEqual(self.run_cli('service-assess','--socket',sock,'--claim','claim')['assessment']['state'],
                                 'NEITHER')
                report=self.run_cli('service-verify','--socket',sock)
                self.assertTrue(report['valid'])
                self.assertEqual(report['reviews'],2)
                self.assertEqual(report['original_artifacts_unavailable'],[])
            finally:
                proc.terminate()
                try:proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill();proc.communicate(timeout=5)
            self.assertFalse(sock.exists(),'service did not clean socket after SIGTERM')


if __name__=='__main__':unittest.main()
