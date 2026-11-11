"""REI-0.7 deterministic benchmarking and boundary regression tests."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from rei0.benchmark import (BenchmarkError, Case, Key, Limits, FixtureProvider, LiveProvider,
                            Meter, _validate_stage, grade, load_study, normalize,
                            paired_intervals, read_json, run_benchmark, summarize, verify_report)

ROOT = Path(__file__).resolve().parent.parent
CASES = read_json(ROOT/'rei0/data/benchmark_cases.json')
KEYS = read_json(ROOT/'rei0/data/benchmark_keys.json')
FIXTURE = read_json(ROOT/'rei0/data/benchmark_fixture.json')


def run_once(seed=7, cases=CASES, keys=KEYS, fixture=FIXTURE, limits=Limits()):
    return run_benchmark(cases, keys, FixtureProvider(copy.deepcopy(fixture)), limits=limits, seed=seed)


class DatasetContractTests(unittest.TestCase):
    def test_offline_dataset_has_eight_items(self):
        cases, keys = load_study(CASES, KEYS)
        self.assertEqual(len(cases), 8)
        self.assertEqual(set(c.id for c in cases), set(keys))

    def test_held_out_answers_never_appear_as_dataset_fields(self):
        for case in CASES['cases']:
            self.assertEqual(set(case), {'id','question','context','category'})
            self.assertNotIn('acceptable', case)

    def test_reject_label_leak_field(self):
        corrupted = copy.deepcopy(CASES)
        corrupted['cases'][0]['acceptable'] = ['21']
        with self.assertRaises(BenchmarkError): load_study(corrupted, KEYS)

    def test_reject_duplicate_case(self):
        corrupted = copy.deepcopy(CASES)
        corrupted['cases'].append(copy.deepcopy(corrupted['cases'][0]))
        with self.assertRaises(BenchmarkError): load_study(corrupted, KEYS)

    def test_reject_duplicate_key(self):
        corrupted = copy.deepcopy(KEYS)
        corrupted['answers'].append(copy.deepcopy(corrupted['answers'][0]))
        with self.assertRaises(BenchmarkError): load_study(CASES, corrupted)

    def test_reject_missing_key(self):
        corrupted = copy.deepcopy(KEYS)
        corrupted['answers'].pop()
        with self.assertRaises(BenchmarkError): load_study(CASES, corrupted)

    def test_unanswerable_must_not_have_answer(self):
        corrupted = copy.deepcopy(KEYS)
        row = next(k for k in corrupted['answers'] if k['unanswerable'])
        row['acceptable'] = ['a guess']
        with self.assertRaises(BenchmarkError): load_study(CASES, corrupted)

    def test_answerable_needs_references(self):
        corrupted = copy.deepcopy(KEYS)
        corrupted['answers'][0]['acceptable'] = []
        with self.assertRaises(BenchmarkError): load_study(CASES, corrupted)

    def test_normalization_is_strict_and_deterministic(self):
        self.assertEqual(normalize('  YeS   '), 'yes')
        self.assertNotEqual(normalize('4'), normalize('four'))

    def test_confidence_boolean_forbidden(self):
        payload = {'answer':'4','confidence':True,'rationale':'r'}
        with self.assertRaises(BenchmarkError): _validate_stage('final', payload)

    def test_confidence_nan_forbidden(self):
        with self.assertRaises(BenchmarkError): _validate_stage('final', {'answer':'4','confidence':float('nan'),'rationale':'r'})

    def test_unbounded_confidence_forbidden(self):
        for v in (-0.1, 1.1, float('inf')):
            with self.subTest(v=v), self.assertRaises(BenchmarkError):
                _validate_stage('final', {'answer':'4','confidence':v,'rationale':'r'})

    def test_abstention_cannot_have_confidence(self):
        with self.assertRaises(BenchmarkError):
            _validate_stage('final', {'answer':None,'confidence':0.8,'rationale':'r'})

    def test_no_self_approval_fields(self):
        with self.assertRaises(BenchmarkError):
            _validate_stage('final', {'answer':'4','confidence':.6,'rationale':'r','verified':True})
        with self.assertRaises(BenchmarkError):
            _validate_stage('initial', {'claim':'a','questions':[{'text':'why'}], 'verified':True})

    def test_limits_reject_bools_and_nonfinite(self):
        for values in ({'max_calls':True}, {'max_tokens':0}, {'max_seconds':float('nan')},
                       {'steps':13}, {'max_output_tokens':0}):
            with self.subTest(values=values), self.assertRaises(BenchmarkError):
                Limits(**values)

    def test_fixture_rejects_duplicate_pairs(self):
        corrupted = copy.deepcopy(FIXTURE)
        corrupted['records'].append(copy.deepcopy(corrupted['records'][0]))
        with self.assertRaises(BenchmarkError): FixtureProvider(corrupted)

    def test_fixture_rejects_unknown_stage(self):
        corrupted = copy.deepcopy(FIXTURE)
        corrupted['records'][0]['turns'][0]['stage'] = 'approve_my_evidence'
        with self.assertRaises(BenchmarkError): FixtureProvider(corrupted)


class ScoringTests(unittest.TestCase):
    def test_reference_aliases(self):
        key = Key('x', ('yes','affirmative'), False)
        result = grade({'answer':'  YES ','error':None}, key)
        self.assertTrue(result['correct'])

    def test_unanswerable_abstention_is_correct(self):
        self.assertTrue(grade({'answer':None,'error':None}, Key('x',(),True))['correct'])

    def test_failure_is_not_credited_as_correct_abstention(self):
        self.assertFalse(grade({'answer':None,'error':'timeout'}, Key('x',(),True))['correct'])

    def test_guess_on_unanswerable_is_error(self):
        self.assertFalse(grade({'answer':'12 C','error':None}, Key('x',(),True))['correct'])

    def test_metrics_consistent(self):
        result = run_once()
        self.assertEqual(len(result['outcomes']), 32)
        self.assertEqual(result['summary']['rei']['cases'], 8)
        self.assertGreater(result['summary']['rei']['total_model_calls'], result['summary']['baseline']['total_model_calls'])
        self.assertEqual(result['summary']['rei']['false_answer_rate_unanswerable'], 0.0)

    def test_brier_formula_and_missing_confidence(self):
        cases, keys = load_study(CASES, KEYS)
        outcomes = run_once()['outcomes']
        self.assertEqual(summarize(outcomes, keys)['rei']['confidence_sample_count'], 6)
        self.assertIsInstance(summarize(outcomes, keys)['rei']['brier_on_answered_with_confidence'], float)

    def test_paired_bootstrap_reproducible(self):
        _, keys = load_study(CASES, KEYS)
        outcomes = run_once()['outcomes']
        self.assertEqual(paired_intervals(outcomes, keys, seed=7), paired_intervals(outcomes, keys, seed=7))
        self.assertEqual(paired_intervals(outcomes, keys, seed=7)['rei_minus_fixed_depth']['exact_reported_usage_matched_pairs'], 8)


class PipelineTests(unittest.TestCase):
    def test_full_run_deterministic_seed(self):
        self.assertEqual(run_once(), run_once())

    def test_rei_records_graph_and_provisional_status(self):
        r = run_once()
        for row in r['outcomes']:
            if row['arm']=='rei':
                self.assertIsNone(row['error'])
                self.assertEqual(row['reasoning']['evidence_state'], 'NEITHER')
                self.assertEqual(row['model_calls'], 4)
                self.assertEqual(len(row['reasoning']['graph_audit_head']),64)

    def test_all_arms_use_expected_calls(self):
        result = run_once()
        by_arm = {arm: {r['model_calls'] for r in result['outcomes'] if r['arm']==arm}
                  for arm in ('baseline','self_critique','fixed_depth','rei')}
        self.assertEqual(by_arm, {'baseline':{1},'self_critique':{3},'fixed_depth':{4},'rei':{4}})

    def test_fixture_is_not_empirical(self):
        r = run_once()
        self.assertEqual(r['mode'],'scripted_fixture_not_empirical')
        self.assertIn('synthetic',r['warnings'][0].lower())

    def test_limited_budget_does_not_crash_study(self):
        r = run_once(limits=Limits(max_calls=1,max_tokens=4000,steps=2))
        self.assertGreater(r['summary']['rei']['failed_runs'],0)
        self.assertEqual(r['summary']['baseline']['failed_runs'],0)
        self.assertEqual(len(r['outcomes']),32)

    def test_token_overrun_counted_as_failure(self):
        r = run_once(limits=Limits(max_tokens=10))
        self.assertEqual(r['summary']['baseline']['failed_runs'],8)
        self.assertEqual(r['summary']['baseline']['total_model_calls'],8)
        self.assertEqual(r['summary']['baseline']['total_reported_tokens'],168)

    def test_fixture_stage_mismatch_is_error(self):
        corrupt = copy.deepcopy(FIXTURE)
        first = next(r for r in corrupt['records'] if r['arm']=='baseline')
        first['turns'][0]['stage']='draft'
        r = run_once(fixture=corrupt)
        self.assertEqual(r['summary']['baseline']['failed_runs'],1)

    def test_invalid_model_payload_cannot_self_verify(self):
        corrupt = copy.deepcopy(FIXTURE)
        record = next(r for r in corrupt['records'] if r['arm']=='rei')
        record['turns'][0]['payload']['verified']=True
        r = run_once(fixture=corrupt)
        row = next(o for o in r['outcomes'] if o['case_id']==record['case_id'] and o['arm']=='rei')
        self.assertIsNotNone(row['error'])
        self.assertIsNone(row['answer'])

    def test_stage_context_contains_no_key_structure(self):
        class Spy:
            kind='scripted_fixture_not_empirical'
            fingerprint='spy'
            def __init__(self):
                self.inner=FixtureProvider(FIXTURE)
                self.contexts=[]
            def respond(self, **kwargs):
                self.contexts.append(kwargs['context'])
                return self.inner.respond(**kwargs)
        spy=Spy()
        run_benchmark(CASES,KEYS,spy)
        serial=json.dumps(spy.contexts)
        self.assertNotIn('acceptable',serial)
        self.assertNotIn('unanswerable',serial)
        self.assertNotIn('benchmark.keys',serial)

    def test_shuffled_schedule_same_scores(self):
        r1,r2=run_once(seed=4),run_once(seed=11)
        self.assertEqual(r1['summary'],r2['summary'])
        self.assertNotEqual(r1['seed'],r2['seed'])

    def test_report_regrade_and_checksum(self):
        r=run_once()
        self.assertTrue(verify_report(r,CASES,KEYS)['valid'])

    def test_report_tampering_detected(self):
        r=run_once()
        r['outcomes'][0]['answer']='999999'
        with self.assertRaises(BenchmarkError):verify_report(r,CASES,KEYS)

    def test_answer_key_change_detected(self):
        r=run_once()
        keys=copy.deepcopy(KEYS)
        keys['answers'][0]['acceptable']=['wrong']
        with self.assertRaises(BenchmarkError):verify_report(r,CASES,keys)

    def test_regrade_rejects_rehashed_metric_forgery(self):
        from rei0.models import digest
        r=run_once()
        r['summary']['baseline']['overall_success']=1.0
        payload={k:v for k,v in r.items() if k!='report_sha256'}
        r['report_sha256']=digest(payload)
        with self.assertRaises(BenchmarkError):verify_report(r,CASES,KEYS)

    def test_no_network_needed_for_offline(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('network called')):
            self.assertEqual(run_once()['summary']['rei']['failed_runs'],0)

    def test_live_provider_needs_https(self):
        for url in ('http://example.com/api','https://user:pass@example.com/api','file:///tmp/model'):
            with self.subTest(url=url),self.assertRaises(BenchmarkError):
                LiveProvider('foo',url)

    def test_live_provider_requires_key_without_request(self):
        p=LiveProvider('model-1')
        with patch.dict('os.environ',{'REI_LLM_API_KEY':''}):
            with self.assertRaises(BenchmarkError):
                p.respond(case_id='c',arm='baseline',stage='final',context={},max_output_tokens=128,timeout=2)

    def test_fixture_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as td:
            report=Path(td)/'benchmark.json'
            cmd=[sys.executable,'-m','rei0','benchmark-demo','--output',str(report)]
            out=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=90)
            self.assertEqual(out.returncode,0,out.stderr)
            self.assertTrue(report.exists())
            verify=subprocess.run([sys.executable,'-m','rei0','benchmark-verify','--report',str(report),
                                   '--cases',str(ROOT/'rei0/data/benchmark_cases.json'),
                                   '--keys',str(ROOT/'rei0/data/benchmark_keys.json')],
                                  cwd=ROOT,capture_output=True,text=True,timeout=90)
            self.assertEqual(verify.returncode,0,verify.stderr)
            self.assertTrue(json.loads(verify.stdout)['valid'])


if __name__ == '__main__':
    unittest.main()
