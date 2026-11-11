"""REI-0.8 repeated-trial, split-isolated experimental evaluation.

The offline fixture is a *pipeline test*, never empirical evidence. Adaptive
confidence thresholds are fitted only to the calibration split; they cannot
edit model outputs or certify evidence. All key-based scoring is evaluator-side.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import random
from typing import Any, Callable

from .benchmark import (ARMS, BenchmarkError, FixtureProvider, Limits, grade,
                        load_study, normalize, run_benchmark, summarize, verify_report)
from .models import digest

STUDY_SCHEMA = 'rei0.study.report.v1'
THRESHOLDS = (0.0, 0.25, 0.5, 0.75, 0.9, 1.0)


@dataclass(frozen=True)
class StudyConfig:
    repetitions: int = 3
    seed: int = 19
    max_total_calls: int = 1000
    bootstrap_repetitions: int = 1000
    min_calibration_coverage: float = 0.5

    def __post_init__(self):
        for name, low, high in (('repetitions', 1, 30), ('seed', 0, 2**31 - 1),
                                ('max_total_calls', 1, 1000000),
                                ('bootstrap_repetitions', 100, 5000)):
            v = getattr(self, name)
            if type(v) is not int or not low <= v <= high:
                raise BenchmarkError(f'{name} must be integer in [{low}, {high}]')
        v = self.min_calibration_coverage
        if type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 1:
            raise BenchmarkError('min_calibration_coverage must be finite in [0,1]')


def validate_splits(cal_cases: dict, cal_keys: dict,
                    eval_cases: dict, eval_keys: dict) -> tuple:
    cc, ck = load_study(cal_cases, cal_keys)
    ec, ek = load_study(eval_cases, eval_keys)
    ids_c = {c.id for c in cc}
    ids_e = {c.id for c in ec}
    if ids_c & ids_e:
        raise BenchmarkError('calibration and evaluation case IDs must be disjoint')
    prompts_c = {normalize(c.prompt()) for c in cc}
    prompts_e = {normalize(c.prompt()) for c in ec}
    if prompts_c & prompts_e:
        raise BenchmarkError('identical prompts across splits are forbidden')
    # No semantic/near-duplicate or model-pretraining leakage is detectable here.
    return cc, ck, ec, ek


def _trial_seed(seed: int, phase: str, trial: int) -> int:
    # Stable across Python processes/versions; fit range of v0.7 run_benchmark seed.
    return int(sha256(f'{seed}|{phase}|{trial}|rei0.8'.encode()).hexdigest()[:7], 16)


def _gather(trial_reports: list[dict], phase: str) -> list[dict]:
    rows = []
    for record in trial_reports:
        if record['phase'] == phase:
            for outcome in record['report']['outcomes']:
                rows.append({**outcome, 'trial': record['trial']})
    return rows


def apply_threshold(outcome: dict, threshold: float) -> dict:
    """Post-process decisions, never evidence or errors; never score inside this function."""
    out = dict(outcome)
    if out['error'] is None and out['answer'] is not None:
        conf = out['confidence']
        if (conf is None and threshold > 0) or (conf is not None and conf < threshold):
            out['answer'] = None
            out['confidence'] = None
            out['policy_abstained'] = True
        else:
            out['policy_abstained'] = False
    else:
        out['policy_abstained'] = False
    return out


def _fit_policies(cal_rows: list[dict], cal_keys: dict, *, coverage: float) -> dict:
    policies = {}
    for arm in ARMS:
        rows = [o for o in cal_rows if o['arm'] == arm]
        answerable = [o for o in rows if not cal_keys[o['case_id']].unanswerable]
        scored = []
        for th in THRESHOLDS:
            transformed = [apply_threshold(o, th) for o in rows]
            selected = sum(o['answer'] is not None and o['error'] is None
                           for o in transformed if not cal_keys[o['case_id']].unanswerable)
            observed_coverage = selected / len(answerable) if answerable else 1.0
            accuracy = sum(grade(o, cal_keys[o['case_id']])['correct'] for o in transformed) / len(transformed)
            scored.append({'threshold': th, 'calibration_success': accuracy,
                           'calibration_answerable_coverage': observed_coverage,
                           'eligible': observed_coverage >= coverage})
        eligible = [s for s in scored if s['eligible']]
        # A weak provider may never reach the requested coverage; preserve
        # the experiment and record the constraint violation explicitly.
        if eligible:
            best = min(eligible, key=lambda x: (-x['calibration_success'], x['threshold']))
        else:
            best = scored[0]  # unachievable: no extra confidence-based abstention

        policies[arm] = {'threshold': best['threshold'],
                         'calibration_success': best['calibration_success'],
                         'calibration_answerable_coverage': best['calibration_answerable_coverage'],
                         'candidates': scored, 'fitted_rows': len(rows),
                         'coverage_constraint_met': bool(eligible)}
    return policies


def _apply_policies(rows: list[dict], policies: dict) -> list[dict]:
    return [apply_threshold(r, policies[r['arm']]['threshold']) for r in rows]


def _cluster_comparison(rows: list[dict], keys: dict, seed: int, repetitions: int) -> dict:
    """Bootstrap over cases, not individual repeated draws of the same case."""
    index = {(o['case_id'], o['trial'], o['arm']): o for o in rows}
    cases = sorted(keys)
    trials = sorted({o['trial'] for o in rows})
    if len(index) != len(rows) or len(rows) != len(cases) * len(trials) * len(ARMS):
        raise BenchmarkError('invalid repeated trial matrix')
    result = {}
    for comparator in ARMS[:-1]:
        case_diffs, exact_pairs = [], 0
        for case_id in cases:
            diffs = []
            for trial in trials:
                a = index[(case_id, trial, 'rei')]
                b = index[(case_id, trial, comparator)]
                diffs.append(int(grade(a, keys[case_id])['correct']) -
                             int(grade(b, keys[case_id])['correct']))
                if a['model_calls'] == b['model_calls'] and a['reported_tokens'] == b['reported_tokens']:
                    exact_pairs += 1
            case_diffs.append(sum(diffs) / len(diffs))
        rng = random.Random(f'rei0.8|{seed}|{comparator}|case-bootstrap')
        draws = sorted(sum(rng.choice(case_diffs) for _ in case_diffs) / len(case_diffs)
                       for _ in range(repetitions))
        result[f'rei_minus_{comparator}'] = {
            'mean_paired_success_difference': sum(case_diffs) / len(case_diffs),
            'case_cluster_bootstrap_95pct': [draws[int(repetitions * .025)],
                draws[min(repetitions - 1, int(repetitions * .975))]],
            'distinct_cases': len(cases), 'trials_per_case': len(trials),
            'exact_reported_usage_matched_case_trials': exact_pairs,
            'total_case_trials': len(cases) * len(trials),
            'bootstrap_repetitions': repetitions,
        }
    return result


def _analysis(trial_reports: list[dict], cal_keys: dict, eval_keys: dict,
              eval_cases: tuple, config: StudyConfig) -> tuple[dict, dict]:
    cal_rows, eval_rows = _gather(trial_reports, 'calibration'), _gather(trial_reports, 'evaluation')
    policies = _fit_policies(cal_rows, cal_keys, coverage=config.min_calibration_coverage)
    tuned_rows = _apply_policies(eval_rows, policies)
    raw_summary = summarize(eval_rows, eval_keys)
    tuned_summary = summarize(tuned_rows, eval_keys)
    resource = {
        arm: {'calls': raw_summary[arm]['total_model_calls'],
              'provider_reported_tokens': raw_summary[arm]['total_reported_tokens'],
              'mean_calls_per_case_trial': raw_summary[arm]['total_model_calls'] / raw_summary[arm]['cases'],
              'mean_reported_tokens_per_case_trial': raw_summary[arm]['total_reported_tokens'] / raw_summary[arm]['cases']}
        for arm in ARMS
    }
    cat_for_id = {c.id: c.category for c in eval_cases}
    categories = {}
    for category in sorted(set(cat_for_id.values())):
        categories[category] = {}
        for arm in ARMS:
            subset = [r for r in eval_rows if r['arm'] == arm and cat_for_id[r['case_id']] == category]
            categories[category][arm] = {'case_trials': len(subset),
                'raw_success': sum(grade(r, eval_keys[r['case_id']])['correct'] for r in subset) / len(subset),
                'adapted_success': sum(grade(apply_threshold(r, policies[arm]['threshold']),
                                                eval_keys[r['case_id']])['correct'] for r in subset) / len(subset)}
    stability = {}
    for arm in ARMS:
        rows = [r for r in eval_rows if r['arm'] == arm]
        distinct = {}
        for case_id in sorted(eval_keys):
            answers = [r['answer'] if r['error'] is None else '__FAILED__'
                       for r in rows if r['case_id'] == case_id]
            distinct[case_id] = len(set(normalize(v) if v is not None else '__ABSTAIN__' for v in answers))
        stability[arm] = {'distinct_responses_per_case': distinct,
                          'fraction_of_cases_with_identical_responses_across_trials':
                              sum(n == 1 for n in distinct.values()) / len(distinct)}
    return policies, {
        'raw_evaluation': raw_summary,
        'adapted_evaluation': tuned_summary,
        'raw_paired': _cluster_comparison(eval_rows, eval_keys, config.seed,
                                          config.bootstrap_repetitions),
        'adapted_paired': _cluster_comparison(tuned_rows, eval_keys, config.seed,
                                              config.bootstrap_repetitions),
        'resource_accounting': resource,
        'category_breakdown': categories,
        'response_stability': stability,
        'evaluation_policy_abstentions': {
            arm: sum(r['policy_abstained'] for r in tuned_rows if r['arm'] == arm)
            for arm in ARMS},
    }


WARNINGS = [
    'Scripted fixture repetitions are identical mock responses, NOT independent stochastic model trials or evidence of model advantage.',
    'Live external evaluations require real credentials, preregistration, independently held-out data and replication; no live calls are shipped.',
    'Threshold adaptation uses calibration labels only, changes answer/abstention decisions and DOES NOT train model weights or validate facts.',
    'Same maximum per-arm budget does not imply equal actual calls, tokens, latency, cost or compute; see resource accounting.',
    'Case-cluster bootstrap uncertainty is descriptive, not a guarantee of generalization; repeated trials on one case are correlated.',
    'Exact string-match grading, model contamination, hidden data overlap and biased task selection can distort observed performance.',
    'Hash verification/regrading is not authenticated model execution; anchor the report hash independently.',
]


def run_study(cal_cases_doc: dict, cal_keys_doc: dict,
              eval_cases_doc: dict, eval_keys_doc: dict,
              provider_factory: Callable[[], Any], *, limits: Limits = Limits(),
              config: StudyConfig = StudyConfig()) -> dict:
    cc, ck, ec, ek = validate_splits(cal_cases_doc, cal_keys_doc, eval_cases_doc, eval_keys_doc)
    worst_case_calls = (len(cc) + len(ec)) * len(ARMS) * config.repetitions * limits.max_calls
    if worst_case_calls > config.max_total_calls:
        raise BenchmarkError(f'preflight maximum model calls {worst_case_calls} exceeds study cap '
                             f'{config.max_total_calls}; reduce dataset/trials or raise explicitly')
    records = []
    fingerprint = None
    mode = None
    for phase, cases_doc, keys_doc in (('calibration', cal_cases_doc, cal_keys_doc),
                                        ('evaluation', eval_cases_doc, eval_keys_doc)):
        for t in range(config.repetitions):
            provider = provider_factory()
            if not hasattr(provider, 'fingerprint') or not isinstance(provider.fingerprint, str):
                raise BenchmarkError('provider must declare a stable fingerprint')
            if fingerprint is None:
                fingerprint, mode = provider.fingerprint, provider.kind
            if provider.fingerprint != fingerprint or provider.kind != mode:
                raise BenchmarkError('different providers across trials violate the study design')
            seed = _trial_seed(config.seed, phase, t)
            report = run_benchmark(cases_doc, keys_doc, provider, limits=limits, seed=seed)
            records.append({'phase': phase, 'trial': t, 'report': report})
    policy, analysis = _analysis(records, ck, ek, ec, config)
    doc = {'schema': STUDY_SCHEMA,
           'mode': mode, 'provider_fingerprint': fingerprint,
           'calibration_case_digest': digest(cal_cases_doc),
           'calibration_key_digest': digest(cal_keys_doc),
           'evaluation_case_digest': digest(eval_cases_doc),
           'evaluation_key_digest': digest(eval_keys_doc),
           'config': asdict(config), 'budgets': asdict(limits),
           'trial_reports': records,
           'adaptive_policy': {'by_arm': policy, 'trained_on_calibration_only': True,
                               'candidate_thresholds': list(THRESHOLDS),
                               'tie_break': 'lowest_threshold',
                               'rule': 'abstain if confidence below learned threshold; missing confidence abstains only when threshold > 0'},
           'analysis': analysis, 'warnings': WARNINGS}
    return {**doc, 'report_sha256': digest(doc)}


def verify_study(report: dict, cal_cases_doc: dict, cal_keys_doc: dict,
                 eval_cases_doc: dict, eval_keys_doc: dict) -> dict:
    if not isinstance(report, dict) or 'report_sha256' not in report:
        raise BenchmarkError('study report hash missing')
    core = {k: v for k, v in report.items() if k != 'report_sha256'}
    if digest(core) != report['report_sha256']:
        raise BenchmarkError('study report hash mismatch')
    if core.get('schema') != STUDY_SCHEMA:
        raise BenchmarkError('study schema mismatch')
    cc, ck, ec, ek = validate_splits(cal_cases_doc, cal_keys_doc, eval_cases_doc, eval_keys_doc)
    for field, source in (('calibration_case_digest', cal_cases_doc),
                          ('calibration_key_digest', cal_keys_doc),
                          ('evaluation_case_digest', eval_cases_doc),
                          ('evaluation_key_digest', eval_keys_doc)):
        if core.get(field) != digest(source):
            raise BenchmarkError(f'{field} mismatch')
    try:
        cfg = StudyConfig(**core['config'])
        limits = Limits(**core['budgets'])
        records = core['trial_reports']
        if not isinstance(records, list) or len(records) != 2*cfg.repetitions:
            raise BenchmarkError('wrong number of study reports')
        expected = {(phase, t) for phase in ('calibration', 'evaluation') for t in range(cfg.repetitions)}
        observed = set()
        for record in records:
            phase, t, inner = record['phase'], record['trial'], record['report']
            pair = (phase, t)
            if type(t) is not int or pair not in expected or pair in observed:
                raise BenchmarkError('duplicate, missing or unexpected trial')
            observed.add(pair)
            cd, kd = (cal_cases_doc, cal_keys_doc) if phase == 'calibration' else (eval_cases_doc, eval_keys_doc)
            verify_report(inner, cd, kd)
            if (inner['seed'] != _trial_seed(cfg.seed, phase, t) or
                inner['provider_fingerprint'] != core['provider_fingerprint'] or
                inner['mode'] != core['mode'] or inner['budgets'] != asdict(limits)):
                raise BenchmarkError('subreport experiment provenance mismatch')
        if observed != expected:
            raise BenchmarkError('missing trial report')
        expected_policy, expected_analysis = _analysis(records, ck, ek, ec, cfg)
        if (core['adaptive_policy'] != {
                'by_arm': expected_policy, 'trained_on_calibration_only': True,
                'candidate_thresholds': list(THRESHOLDS), 'tie_break': 'lowest_threshold',
                'rule': 'abstain if confidence below learned threshold; missing confidence abstains only when threshold > 0'} or
            core['analysis'] != expected_analysis or core['warnings'] != WARNINGS):
            raise BenchmarkError('study analysis or adaptive policy failed independent regrading')
        actual = (len(cc)+len(ec))*len(ARMS)*cfg.repetitions*limits.max_calls
        if actual > cfg.max_total_calls:
            raise BenchmarkError('study call cap exceeded by configuration')
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        if isinstance(exc, BenchmarkError):
            raise
        raise BenchmarkError('malformed study report') from exc
    return {'valid': True, 'report_sha256': report['report_sha256'],
            'calibration_cases': len(cc), 'evaluation_cases': len(ec),
            'repetitions': cfg.repetitions, 'subreports_verified': len(records),
            'warning': 'Independent regrading and hashes, NOT proof of authentic provider execution'}
