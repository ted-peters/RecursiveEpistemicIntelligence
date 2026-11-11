"""REI-0.8 deterministic repeated-study and calibration-boundary tests."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from rei0.benchmark import (ARMS, BenchmarkError, FixtureProvider, Limits,
                            grade, read_json)
from rei0.models import digest
from rei0.study import (StudyConfig, STUDY_SCHEMA, THRESHOLDS, _analysis,
                        _cluster_comparison, _fit_policies, _trial_seed,
                        apply_threshold, run_study, validate_splits, verify_study)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'rei0' / 'data'
CC = read_json(DATA/'study_calibration_cases.json')
CK = read_json(DATA/'study_calibration_keys.json')
EC = read_json(DATA/'study_evaluation_cases.json')
EK = read_json(DATA/'study_evaluation_keys.json')
FIXTURE = read_json(DATA/'benchmark_fixture.json')
INPUTS = (CC, CK, EC, EK)
CONFIG = StudyConfig(repetitions=2, seed=19, bootstrap_repetitions=100)


def run_once(inputs=INPUTS, config=CONFIG, factory=None, limits=Limits()):
    return run_study(*inputs, factory or (lambda: FixtureProvider(copy.deepcopy(FIXTURE))),
                     limits=limits, config=config)


class SplitTests(unittest.TestCase):
    def test_demo_is_disjoint_and_both_categories_covered(self):
        cc, _, ec, _ = validate_splits(*INPUTS)
        self.assertEqual(len(cc), 4)
        self.assertEqual(len(ec), 4)
        self.assertFalse({c.id for c in cc} & {c.id for c in ec})

    def test_overlap_id_forbidden(self):
        cc, ck, ec, ek = [copy.deepcopy(d) for d in INPUTS]
        ec['cases'][0]['id'] = cc['cases'][0]['id']
        ek['answers'][0]['case_id'] = ck['answers'][0]['case_id']
        with self.assertRaisesRegex(BenchmarkError, 'IDs'):
            validate_splits(cc, ck, ec, ek)

    def test_duplicate_prompt_different_id_forbidden(self):
        cc, ck, ec, ek = [copy.deepcopy(d) for d in INPUTS]
        ec['cases'][0]['question'] = cc['cases'][0]['question']
        ec['cases'][0]['context'] = cc['cases'][0]['context']
        with self.assertRaisesRegex(BenchmarkError, 'prompts'):
            validate_splits(cc, ck, ec, ek)

    def test_no_label_fields_allowed_in_public_cases(self):
        inputs = [copy.deepcopy(d) for d in INPUTS]
        inputs[2]['cases'][0]['acceptable'] = ['guess']
        with self.assertRaises(BenchmarkError):
            validate_splits(*inputs)

    def test_key_mismatch_forbidden(self):
        inputs = [copy.deepcopy(d) for d in INPUTS]
        inputs[3]['answers'][0]['case_id'] = 'missing'
        with self.assertRaises(BenchmarkError):
            validate_splits(*inputs)

    def test_bounded_config_fails_bool_and_negative(self):
        for kwargs in ({'repetitions':True},{'seed':-1},{'max_total_calls':0},
                       {'bootstrap_repetitions':99},{'min_calibration_coverage':float('nan')},
                       {'min_calibration_coverage':1.2},{'repetitions':31}):
            with self.subTest(kwargs=kwargs), self.assertRaises(BenchmarkError):
                StudyConfig(**kwargs)

    def test_call_ceiling_enforced_before_external_model(self):
        visited=[]
        with self.assertRaisesRegex(BenchmarkError,'preflight'):
            run_once(config=StudyConfig(repetitions=2,max_total_calls=100,bootstrap_repetitions=100),
                     factory=lambda: visited.append(True))
        self.assertEqual(visited, [])


class AdaptationTests(unittest.TestCase):
    def test_low_confidence_abstains(self):
        x={'answer':'wrong','confidence':0.2,'error':None,'arm':'rei'}
        y=apply_threshold(x,0.5)
        self.assertEqual(y['answer'],None)
        self.assertIsNone(y['confidence'])
        self.assertEqual(x['answer'],'wrong')
        self.assertTrue(y['policy_abstained'])

    def test_high_confidence_preserved(self):
        x={'answer':'ok','confidence':0.95,'error':None}
        self.assertEqual(apply_threshold(x,0.5)['answer'],'ok')

    def test_missing_confidence_rejected_only_at_positive_threshold(self):
        x={'answer':'ok','confidence':None,'error':None}
        self.assertEqual(apply_threshold(x,0)['answer'],'ok')
        self.assertIsNone(apply_threshold(x,0.1)['answer'])

    def test_failed_run_cannot_become_valid_abstention(self):
        from rei0.benchmark import Key
        x={'answer':None,'confidence':None,'error':'bad provider'}
        self.assertFalse(grade(apply_threshold(x,.9),Key('x',(),True))['correct'])

    def test_fits_on_only_the_supplied_calibration_rows(self):
        from rei0.benchmark import Key
        keys={'a':Key('a',('yes',),False),'b':Key('b',(),True)}
        rows=[]
        for arm in ARMS:
            rows += [{'case_id':'a','arm':arm,'answer':'yes','confidence':.9,'error':None},
                     {'case_id':'b','arm':arm,'answer':'no','confidence':.1,'error':None}]
        policy=_fit_policies(rows,keys,coverage=.5)
        self.assertEqual({p['threshold'] for p in policy.values()}, {0.25})
        self.assertTrue(all(p['coverage_constraint_met'] for p in policy.values()))
        self.assertTrue(all(p['calibration_success'] == 1 for p in policy.values()))

    def test_unreachable_coverage_degrades_without_changing_history(self):
        from rei0.benchmark import Key
        keys={'a':Key('a',('yes',),False)}
        rows=[{'case_id':'a','arm':arm,'answer':None,'confidence':None,'error':None} for arm in ARMS]
        policies=_fit_policies(rows,keys,coverage=1)
        self.assertTrue(all(p['threshold']==0 for p in policies.values()))
        self.assertTrue(all(not p['coverage_constraint_met'] for p in policies.values()))

    def test_tie_break_prefers_lowest_threshold(self):
        from rei0.benchmark import Key
        keys={'a':Key('a',('yes',),False)}
        rows=[{'case_id':'a','arm':arm,'answer':'yes','confidence':1.0,'error':None} for arm in ARMS]
        p=_fit_policies(rows,keys,coverage=0)
        self.assertEqual({x['threshold'] for x in p.values()}, {0})


class ReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=run_once()

    def test_schema_and_repetitions(self):
        self.assertEqual(self.report['schema'],STUDY_SCHEMA)
        self.assertEqual(len(self.report['trial_reports']),4)
        self.assertEqual(self.report['mode'],'scripted_fixture_not_empirical')

    def test_independent_regrading(self):
        r=verify_study(self.report,*INPUTS)
        self.assertTrue(r['valid'])
        self.assertEqual(r['subreports_verified'],4)

    def test_deterministic_reproducibility(self):
        self.assertEqual(self.report, run_once())

    def test_calibration_vs_eval_case_ids_disjoint(self):
        entries=self.report['trial_reports']
        a={x['case_id'] for e in entries if e['phase']=='calibration' for x in e['report']['outcomes']}
        b={x['case_id'] for e in entries if e['phase']=='evaluation' for x in e['report']['outcomes']}
        self.assertFalse(a&b)

    def test_there_are_two_seeds_per_phase(self):
        entries=self.report['trial_reports']
        self.assertEqual(len({(e['phase'],e['report']['seed']) for e in entries}),4)
        for e in entries:
            self.assertEqual(e['report']['seed'],_trial_seed(19,e['phase'],e['trial']))

    def test_all_rei_model_arguments_remain_provisional(self):
        entries=self.report['trial_reports']
        for e in entries:
            for outcome in e['report']['outcomes']:
                if outcome['arm']=='rei':
                    self.assertEqual(outcome['reasoning']['evidence_state'],'NEITHER')

    def test_all_arms_report_usage(self):
        res=self.report['analysis']['resource_accounting']
        self.assertEqual(set(res),set(ARMS))
        self.assertGreater(res['rei']['calls'],res['baseline']['calls'])

    def test_repeated_trials_not_incorrectly_bootstrapped_as_independent_cases(self):
        pair=self.report['analysis']['raw_paired']['rei_minus_fixed_depth']
        self.assertEqual(pair['distinct_cases'],4)
        self.assertEqual(pair['trials_per_case'],2)
        self.assertEqual(pair['total_case_trials'],8)
        self.assertEqual(pair['bootstrap_repetitions'],100)

    def test_category_breakdown_reports_without_fabricating_semantic_grades(self):
        categories=self.report['analysis']['category_breakdown']
        self.assertIn('arithmetic',categories)
        for cat, arms in categories.items():
            for arm, item in arms.items():
                self.assertLessEqual(item['raw_success'],1)
                self.assertGreaterEqual(item['adapted_success'],0)

    def test_response_stability_exposes_identical_scripted_replays(self):
        v=self.report['analysis']['response_stability']
        self.assertEqual(v['rei']['fraction_of_cases_with_identical_responses_across_trials'],1.0)

    def test_policy_unchanged_when_evaluation_labels_change(self):
        ek=copy.deepcopy(EK)
        ek['answers'][0]['acceptable']=['an unrelated answer']
        new=run_once((CC,CK,EC,ek))
        self.assertEqual(new['adaptive_policy'],self.report['adaptive_policy'])
        self.assertNotEqual(new['evaluation_key_digest'],self.report['evaluation_key_digest'])

    def test_edited_study_hash_rejected(self):
        bad=copy.deepcopy(self.report)
        bad['analysis']['raw_evaluation']['rei']['overall_success']=0
        with self.assertRaisesRegex(BenchmarkError,'hash mismatch'):
            verify_study(bad,*INPUTS)

    def test_recomputed_hash_still_rejects_falsified_metrics(self):
        bad=copy.deepcopy(self.report)
        bad['analysis']['raw_evaluation']['rei']['overall_success']=0
        bad['report_sha256']=digest({k:v for k,v in bad.items() if k!='report_sha256'})
        with self.assertRaisesRegex(BenchmarkError,'analysis|regrading'):
            verify_study(bad,*INPUTS)

    def test_recomputed_inner_hash_still_rejects_falsified_trial(self):
        bad=copy.deepcopy(self.report)
        inner=bad['trial_reports'][0]['report']
        inner['summary']['rei']['overall_success']=0
        inner['report_sha256']=digest({k:v for k,v in inner.items() if k!='report_sha256'})
        bad['report_sha256']=digest({k:v for k,v in bad.items() if k!='report_sha256'})
        with self.assertRaises(BenchmarkError):
            verify_study(bad,*INPUTS)

    def test_missing_trial_with_rehashed_outer_rejected(self):
        bad=copy.deepcopy(self.report)
        bad['trial_reports'].pop()
        bad['report_sha256']=digest({k:v for k,v in bad.items() if k!='report_sha256'})
        with self.assertRaisesRegex(BenchmarkError,'wrong number'):
            verify_study(bad,*INPUTS)

    def test_duplicate_trial_with_rehashed_outer_rejected(self):
        bad=copy.deepcopy(self.report)
        bad['trial_reports'][1]=copy.deepcopy(bad['trial_reports'][0])
        bad['report_sha256']=digest({k:v for k,v in bad.items() if k!='report_sha256'})
        with self.assertRaisesRegex(BenchmarkError,'duplicate'):
            verify_study(bad,*INPUTS)

    def test_mismatched_keys_rejected(self):
        modified=copy.deepcopy(EK)
        modified['answers'][0]['acceptable']=['wrong']
        with self.assertRaisesRegex(BenchmarkError,'evaluation_key_digest'):
            verify_study(self.report,CC,CK,EC,modified)

    def test_provider_fingerprint_change_rejected(self):
        bad=copy.deepcopy(self.report)
        bad['trial_reports'][0]['report']['provider_fingerprint']='spoofed'
        inner=bad['trial_reports'][0]['report']
        inner['report_sha256']=digest({k:v for k,v in inner.items() if k!='report_sha256'})
        bad['report_sha256']=digest({k:v for k,v in bad.items() if k!='report_sha256'})
        with self.assertRaisesRegex(BenchmarkError,'provenance'):
            verify_study(bad,*INPUTS)

    def test_detect_provider_identity_switch_during_run(self):
        counter=[0]
        def factory():
            x=FixtureProvider(FIXTURE)
            counter[0]+=1
            x.fingerprint=f'{counter[0]}'
            return x
        with self.assertRaisesRegex(BenchmarkError,'different providers'):
            run_once(factory=factory)

    def test_failed_budgeted_runs_not_false_abstentions(self):
        report=run_once(limits=Limits(max_calls=1),
                        config=StudyConfig(repetitions=1,max_total_calls=100,bootstrap_repetitions=100))
        rows=[o for x in report['trial_reports'] if x['phase']=='evaluation' for o in x['report']['outcomes']]
        self.assertTrue(any(o['error'] for o in rows if o['arm']=='rei'))
        self.assertTrue(any(o['error'] for o in rows if o['arm']=='self_critique'))
        verify_study(report,*INPUTS)


class CLITests(unittest.TestCase):
    def _call(self,*arguments):
        return subprocess.run([sys.executable,'-m','rei0',*arguments],cwd=ROOT,
                              text=True,capture_output=True,timeout=40)

    def test_demo_and_verify_subprocess(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'study.json'
            demo=self._call('study-demo','--output',str(path),'--repetitions','1')
            self.assertEqual(demo.returncode,0,demo.stderr)
            self.assertTrue(path.is_file())
            validate=self._call('study-verify','--report',str(path),
                '--calibration-cases',str(DATA/'study_calibration_cases.json'),
                '--calibration-keys',str(DATA/'study_calibration_keys.json'),
                '--evaluation-cases',str(DATA/'study_evaluation_cases.json'),
                '--evaluation-keys',str(DATA/'study_evaluation_keys.json'))
            self.assertEqual(validate.returncode,0,validate.stderr)
            self.assertTrue(json.loads(validate.stdout)['valid'])

    def test_live_requires_explicit_cost_ack_without_network(self):
        p=self._call('study-run','--live','--model','test-model',
            '--calibration-cases',str(DATA/'study_calibration_cases.json'),
            '--calibration-keys',str(DATA/'study_calibration_keys.json'),
            '--evaluation-cases',str(DATA/'study_evaluation_cases.json'),
            '--evaluation-keys',str(DATA/'study_evaluation_keys.json'))
        self.assertEqual(p.returncode,2)
        self.assertIn('--acknowledge-live-costs',p.stderr)

    def test_fixture_and_model_cannot_both_be_used(self):
        p=self._call('study-run','--fixture',str(DATA/'benchmark_fixture.json'),
            '--model','test-model',
            '--calibration-cases',str(DATA/'study_calibration_cases.json'),
            '--calibration-keys',str(DATA/'study_calibration_keys.json'),
            '--evaluation-cases',str(DATA/'study_evaluation_cases.json'),
            '--evaluation-keys',str(DATA/'study_evaluation_keys.json'))
        self.assertEqual(p.returncode,2)
        self.assertIn('--model',p.stderr)


if __name__=='__main__':
    unittest.main()
