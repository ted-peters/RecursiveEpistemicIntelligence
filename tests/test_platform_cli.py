"""Real subprocess CLI integration checks for REI-1.0."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent


def invoke(*args):
    return subprocess.run([sys.executable,'-m','rei0',*map(str,args)],
        cwd=ROOT,encoding='utf-8',text=True,capture_output=True,timeout=35)


class CLIPlatformTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws=Path(self.tmp.name)/'rei.sqlite'

    def test_offline_platform_demo(self):
        r=invoke('platform-demo','--workspace',self.ws)
        self.assertEqual(r.returncode,0,r.stderr)
        doc=json.loads(r.stdout)
        self.assertEqual(doc['live_calls'],0)
        self.assertEqual(doc['integrity']['artifacts'],2)
        check=invoke('platform-verify','--workspace',self.ws)
        self.assertEqual(check.returncode,0,check.stderr)
        self.assertTrue(json.loads(check.stdout)['valid'])

    def test_init_then_list_then_report(self):
        r=invoke('platform-init','--workspace',self.ws)
        self.assertEqual(r.returncode,0,r.stderr)
        r=invoke('platform-list','--workspace',self.ws)
        self.assertEqual(json.loads(r.stdout)['artifacts'],[])
        report=Path(self.tmp.name)/'summary.json'
        r=invoke('platform-report','--workspace',self.ws,'--output',report)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertTrue(report.exists())
        self.assertIn('integrity',json.loads(report.read_text()))

    def test_import_graph_from_legacy_example(self):
        self.assertEqual(invoke('platform-init','--workspace',self.ws).returncode,0)
        r=invoke('platform-import','--workspace',self.ws,'--kind','graph',
                 '--file',ROOT/'examples'/'inquiry_graph.json')
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(json.loads(r.stdout)['summary']['open_questions'],2)

    def test_import_experiment_from_legacy_example(self):
        self.assertEqual(invoke('platform-init','--workspace',self.ws).returncode,0)
        data=ROOT/'rei0'/'data'
        args=['platform-import','--workspace',self.ws,'--kind','experiment',
              '--file',ROOT/'examples'/'experiment09_demo_report.json',
              '--adjudications',ROOT/'examples'/'experiment09_SYNTHETIC_adjudications.json']
        for phase in ('calibration','evaluation'):
            for part in ('cases','keys'):
                args.extend([f'--{phase}-{part}',data/f'study_{phase}_{part}.json'])
        r=invoke(*args)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(json.loads(r.stdout)['summary']['evaluation_cases'],4)

    def test_missing_experiment_keys_rejected(self):
        self.assertEqual(invoke('platform-init','--workspace',self.ws).returncode,0)
        r=invoke('platform-import','--workspace',self.ws,'--kind','experiment',
                 '--file',ROOT/'examples'/'experiment09_demo_report.json')
        self.assertEqual(r.returncode,2)
        self.assertIn('requires',r.stderr)

    def test_workspace_anchor_guard(self):
        r=invoke('platform-demo','--workspace',self.ws)
        self.assertEqual(r.returncode,0,r.stderr)
        good=json.loads(r.stdout)['integrity']['audit_head']
        self.assertEqual(invoke('platform-verify','--workspace',self.ws,'--expected-head',good).returncode,0)
        self.assertEqual(invoke('platform-verify','--workspace',self.ws,'--expected-head','f'*64).returncode,2)

    def test_frozen_offline_run_import_and_resume(self):
        data=ROOT/'rei0'/'data'
        self.assertEqual(invoke('platform-init','--workspace',self.ws).returncode,0)
        output=Path(self.tmp.name)/'result.json'
        checkpoint=Path(self.tmp.name)/'checkpoint.json'
        args=['platform-run','--workspace',self.ws,
              '--prereg',ROOT/'examples'/'experiment09_preregistration.json',
              '--report',output,'--checkpoint',checkpoint,
              '--adjudications',ROOT/'examples'/'experiment09_SYNTHETIC_adjudications.json',
              '--fixture',data/'benchmark_fixture.json']
        for phase in ('calibration','evaluation'):
            for part in ('cases','keys'):
                args.extend([f'--{phase}-{part}',data/f'study_{phase}_{part}.json'])
        r=invoke(*args)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertTrue(output.exists())
        self.assertTrue(checkpoint.exists())
        self.assertEqual(json.loads(r.stdout)['provider_mode'],'scripted_fixture_not_empirical')
        self.assertEqual(json.loads(invoke('platform-verify','--workspace',self.ws).stdout)['artifacts'],1)
        second=invoke(*args)
        self.assertEqual(second.returncode,0,second.stderr)
        self.assertEqual(json.loads(invoke('platform-verify','--workspace',self.ws).stdout)['events'],1)

    def test_no_inadvertent_live_run_without_ack(self):
        # Missing required opt-in must stop before any external request.
        data=ROOT/'rei0'/'data'
        self.assertEqual(invoke('platform-init','--workspace',self.ws).returncode,0)
        args=['platform-run','--workspace',self.ws,
              '--prereg',ROOT/'examples'/'experiment09_preregistration.json',
              '--report',Path(self.tmp.name)/'live.json',
              '--adjudications',ROOT/'examples'/'experiment09_SYNTHETIC_adjudications.json',
              '--live','--model','never-call-me']
        for phase in ('calibration','evaluation'):
            for part in ('cases','keys'):
                args.extend([f'--{phase}-{part}',data/f'study_{phase}_{part}.json'])
        r=invoke(*args)
        self.assertEqual(r.returncode,2)
        self.assertFalse((Path(self.tmp.name)/'live.json').exists())
        self.assertEqual(json.loads(invoke('platform-verify','--workspace',self.ws).stdout)['artifacts'],0)

if __name__=='__main__':unittest.main()
