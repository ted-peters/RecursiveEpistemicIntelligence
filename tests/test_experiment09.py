"""REI-0.9 frozen design, preregistration, adjudication, replay and CLI regression tests."""
from __future__ import annotations
import copy
from dataclasses import replace
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from rei0.benchmark import BenchmarkError, FixtureProvider, Limits, LiveProvider, read_json
from rei0.study import StudyConfig
from rei0.models import digest
from rei0.experiment09 import (
    AnalysisPlan, ADJUDICATION_SCHEMA, create_preregistration, fixture_identity, live_identity,
    synthetic_adjudications, validate_adjudications, verify_preregistration,
    run_preregistered, verify_experiment)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT/'rei0'/'data'
INPUTS = tuple(read_json(DATA/f'study_{phase}_{part}.json') for phase in ('calibration','evaluation') for part in ('cases','keys'))
FIXTURE = read_json(DATA/'benchmark_fixture.json')
MANIFEST = synthetic_adjudications(INPUTS[1],INPUTS[3])
CONFIG=StudyConfig(repetitions=2,bootstrap_repetitions=100)
STAMP='2026-11-10T20:00:00Z'


def prereg(inputs=INPUTS, adjudications=MANIFEST, identity=None, config=CONFIG, plan=AnalysisPlan()):
    return create_preregistration(*inputs, adjudications, identity or fixture_identity(FIXTURE),
        study_id='REI09-test', config=config, plan=plan, registered_at=STAMP)


def run_once(reg=None, inputs=INPUTS, adjudications=MANIFEST, checkpoint=None, factory=None):
    return run_preregistered(reg or prereg(),inputs,adjudications,
        factory or (lambda:FixtureProvider(copy.deepcopy(FIXTURE))),checkpoint=checkpoint)


class PreregistrationTests(unittest.TestCase):
    def test_full_preregistration_checks(self):
        p=prereg()
        cfg,limits,plan=verify_preregistration(p,*INPUTS,MANIFEST)
        self.assertEqual(cfg.repetitions,2)
        self.assertEqual(plan.comparator,'baseline')
        self.assertEqual(p['dataset_digests']['adjudications'],digest(MANIFEST))

    def test_reproducible_with_frozen_stamp(self):
        self.assertEqual(prereg(),prereg())

    def test_invalid_registration_timestamp_fails(self):
        for stamp in ('yesterday','2026-11-10T10:00:00'):
            with self.subTest(stamp=stamp),self.assertRaises(BenchmarkError):
                create_preregistration(*INPUTS,MANIFEST,fixture_identity(FIXTURE),study_id='x',registered_at=stamp)

    def test_implementation_is_frozen(self):
        p = prereg()
        self.assertEqual(len(p['implementation_sha256']), 64)
        modified = copy.deepcopy(p)
        modified['implementation_sha256'] = '0'*64
        modified['preregistration_sha256'] = digest({k:v for k,v in modified.items() if k!='preregistration_sha256'})
        with self.assertRaises(BenchmarkError):
            verify_preregistration(modified,*INPUTS,MANIFEST)

    def test_tampering_with_plan_detected(self):
        p=prereg();p['analysis_plan']['comparator']='self_critique'
        with self.assertRaises(BenchmarkError):verify_preregistration(p,*INPUTS,MANIFEST)

    def test_rehashed_tampering_still_detected(self):
        p=prereg();p['registered_hypothesis']='a new retrospective hypothesis'
        p['preregistration_sha256']=digest({k:v for k,v in p.items() if k!='preregistration_sha256'})
        with self.assertRaises(BenchmarkError):verify_preregistration(p,*INPUTS,MANIFEST)

    def test_different_eval_keys_rejected(self):
        data=copy.deepcopy(INPUTS);data[3]['answers'][0]['acceptable']=['made-up']
        with self.assertRaises(BenchmarkError):verify_preregistration(prereg(),*data,MANIFEST)

    def test_different_eval_cases_rejected(self):
        data=copy.deepcopy(INPUTS);data[2]['cases'][0]['question']='changed'
        with self.assertRaises(BenchmarkError):verify_preregistration(prereg(),*data,MANIFEST)

    def test_hash_alone_cannot_validate_label_truth(self):
        self.assertIn('fixture',prereg()['provider']['mode'])
        self.assertIn('not authenticated',prereg()['gate'])

    def test_false_claim_of_real_model_fingerprint_rejected(self):
        ident=live_identity('test-model')
        ident['fingerprint']='forged'
        with self.assertRaises(BenchmarkError):prereg(identity=ident)

    def test_unknown_provider_type_rejected(self):
        ident=fixture_identity(FIXTURE);ident['mode']='self_verified'
        with self.assertRaises(BenchmarkError):prereg(identity=ident)

    def test_allow_live_model_freeze_without_api_key(self):
        with patch.dict('os.environ',{},clear=True):
            p=prereg(identity=live_identity('mock-id'))
        self.assertEqual(p['provider']['mode'],'live_external_model')

    def test_live_model_identity_differs_by_endpoint(self):
        a=live_identity('model-1');b=live_identity('model-1','https://other.example/v1/chat/completions')
        self.assertNotEqual(a['fingerprint'],b['fingerprint'])

    def test_limits_and_plan_validation(self):
        for kwargs in ({'relative_token_tolerance':float('nan')},{'relative_token_tolerance':-0.1},
                       {'confirmatory_min_evaluation_cases':True},{'comparator':'rei'},
                       {'primary_metric':'custom'}):
            with self.subTest(kwargs=kwargs),self.assertRaises(BenchmarkError):AnalysisPlan(**kwargs)

    def test_preflight_prevents_live_costs(self):
        entered=[]
        config=StudyConfig(repetitions=2,max_total_calls=10,bootstrap_repetitions=100)
        with self.assertRaises(BenchmarkError):prereg(config=config)
        self.assertEqual(entered,[])


class AdjudicationTests(unittest.TestCase):
    def test_cover_and_validate(self):
        self.assertEqual(validate_adjudications(MANIFEST,INPUTS[1],INPUTS[3])['schema'],ADJUDICATION_SCHEMA)

    def test_missing_review_rejected(self):
        a=copy.deepcopy(MANIFEST);a['records'].pop()
        with self.assertRaises(BenchmarkError):validate_adjudications(a,INPUTS[1],INPUTS[3])

    def test_author_cannot_review_self(self):
        a=copy.deepcopy(MANIFEST);a['records'][0]['reviewer']=a['records'][0]['curator'].upper()
        with self.assertRaises(BenchmarkError):validate_adjudications(a,INPUTS[1],INPUTS[3])

    def test_forged_record_label_digest_rejected(self):
        a=copy.deepcopy(MANIFEST);a['records'][0]['key_sha256']='0'*64
        with self.assertRaises(BenchmarkError):validate_adjudications(a,INPUTS[1],INPUTS[3])

    def test_no_unreviewed_placeholder(self):
        a=copy.deepcopy(MANIFEST);a['records'][0]['reference']=''
        with self.assertRaises(BenchmarkError):validate_adjudications(a,INPUTS[1],INPUTS[3])

    def test_same_source_not_asserted_truth(self):
        a=copy.deepcopy(MANIFEST)
        self.assertTrue(all('SYNTHETIC' in x['reference'] for x in a['records']))


class ExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg=prereg()
        cls.report=run_once(cls.reg)

    def test_end_to_end_regrade(self):
        r=verify_experiment(self.report,INPUTS,MANIFEST)
        self.assertTrue(r['valid'])
        self.assertEqual(r['mode'],'scripted_fixture_not_empirical')

    def test_same_inputs_same_report(self):
        self.assertEqual(self.report,run_once(self.reg))

    def test_report_has_no_keys(self):
        dump=json.dumps(self.report)
        self.assertNotIn('"acceptable"',dump)

    def test_detect_outer_report_modification(self):
        r=copy.deepcopy(self.report);r['interpretation']='proven performance'
        with self.assertRaises(BenchmarkError):verify_experiment(r,INPUTS,MANIFEST)

    def test_rehashed_report_with_modified_primary_fails(self):
        r=copy.deepcopy(self.report)
        r['resource_comparability']['observed_rei_minus_comparator']=999
        r['report_sha256']=digest({k:v for k,v in r.items() if k!='report_sha256'})
        with self.assertRaises(BenchmarkError):verify_experiment(r,INPUTS,MANIFEST)

    def test_rehashed_subreport_corruption_fails(self):
        r=copy.deepcopy(self.report)
        r['study_report']['trial_reports'][0]['report']['outcomes'][0]['answer']='definitely wrong'
        r['report_sha256']=digest({k:v for k,v in r.items() if k!='report_sha256'})
        with self.assertRaises(BenchmarkError):verify_experiment(r,INPUTS,MANIFEST)

    def test_resource_comparison_is_not_fake_equal_compute(self):
        x=self.report['resource_comparability']
        self.assertEqual(x['actual_usage_status'],'imbalanced')
        self.assertFalse(x['confirmatory_design_eligible'])
        self.assertLess(x['exact_usage_pairs'],x['all_pairs'])

    def test_four_arm_trial_matrix_retained(self):
        x=self.report['study_report']
        self.assertEqual(len(x['trial_reports']),4)
        for r in x['trial_reports']:
            self.assertEqual(len(r['report']['outcomes']),4*4)

    def test_wrong_provider_rejected_before_first_trial(self):
        called=[]
        class WrongProvider:
            kind='scripted_fixture_not_empirical'
            fingerprint='wrong'
            def respond(self,**kw):called.append(kw)
        with self.assertRaisesRegex(BenchmarkError,'identity'):
            run_once(self.reg,factory=lambda:WrongProvider())
        self.assertEqual(called,[])

    def test_checkpoint_resume_replays_identical_report(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'cp.json'
            first=run_once(self.reg,checkpoint=path)
            self.assertEqual(first,self.report)
            second=run_once(self.reg,checkpoint=path,
                factory=lambda:self.fail('provider should not be invoked after completed checkpoint'))
            self.assertEqual(first,second)

    def test_checkpoint_partial_resume(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'cp.json'
            count=[]
            def interrupted(_):
                count.append(1)
                if len(count)==2:raise RuntimeError('power outage simulation after saving trial two')
            with self.assertRaises(RuntimeError):
                run_preregistered(self.reg,INPUTS,MANIFEST,
                    lambda:FixtureProvider(FIXTURE),checkpoint=path,on_completed_trial=interrupted)
            cp=json.loads(path.read_text())
            self.assertEqual(len(cp['records']),2)
            resumed=run_once(self.reg,checkpoint=path)
            self.assertEqual(resumed,self.report)

    def test_checkpoint_hash_tampering_detected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'cp.json'
            run_once(self.reg,checkpoint=path)
            cp=json.loads(path.read_text());cp['records'][0]['phase']='evaluation'
            path.write_text(json.dumps(cp))
            with self.assertRaises(BenchmarkError):run_once(self.reg,checkpoint=path)

    def test_checkpoint_rehashed_bad_order_detected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'cp.json'
            run_once(self.reg,checkpoint=path)
            cp=json.loads(path.read_text());cp['records'][0],cp['records'][1]=cp['records'][1],cp['records'][0]
            cp['checkpoint_sha256']=digest({k:v for k,v in cp.items() if k!='checkpoint_sha256'})
            path.write_text(json.dumps(cp))
            with self.assertRaises(BenchmarkError):run_once(self.reg,checkpoint=path)

    def test_checkpoint_bound_to_study(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'cp.json'
            run_once(self.reg,checkpoint=path)
            different=prereg(plan=AnalysisPlan(comparator='self_critique'))
            with self.assertRaises(BenchmarkError):run_once(different,checkpoint=path)


class CliTests(unittest.TestCase):
    @staticmethod
    def cli(*argv):
        return subprocess.run([sys.executable,'-m','rei0',*map(str,argv)],
            cwd=ROOT,text=True,capture_output=True,timeout=90)

    def test_demo_and_verify(self):
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)
            r=self.cli('experiment-demo','--output-dir',output)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertTrue((output/'preregistration.json').exists())
            args=[]
            for phase in ('calibration','evaluation'):
                for key in ('cases','keys'):
                    args.extend(['--'+phase+'-'+key,DATA/f'study_{phase}_{key}.json'])
            v=self.cli('experiment-verify',*args,'--adjudications',output/'adjudications.json',
                       '--report',output/'experiment_report.json')
            self.assertEqual(v.returncode,0,v.stderr)
            self.assertTrue(json.loads(v.stdout)['valid'])

    def test_adjudication_template_not_automatically_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'template.json'
            r=self.cli('experiment-adjudication-template','--calibration-keys',DATA/'study_calibration_keys.json',
                '--evaluation-keys',DATA/'study_evaluation_keys.json','--output',target)
            self.assertEqual(r.returncode,0,r.stderr)
            a=read_json(target)
            with self.assertRaises(BenchmarkError):validate_adjudications(a,INPUTS[1],INPUTS[3])

    def test_live_without_explicit_cost_ack_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            args=['experiment-preregister']
            for phase in ('calibration','evaluation'):
                for key in ('cases','keys'):
                    args.extend(['--'+phase+'-'+key,DATA/f'study_{phase}_{key}.json'])
            manifest=Path(d)/'adjudications.json';manifest.write_text(json.dumps(MANIFEST))
            args.extend(['--adjudications',manifest,'--output',Path(d)/'p.json',
                         '--study-id','bad-live','--live','--model','example'])
            r=self.cli(*args)
            self.assertNotEqual(r.returncode,0)
            self.assertIn('acknowledge-live-costs',r.stderr)


if __name__=='__main__':unittest.main()
