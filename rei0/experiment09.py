"""REI-0.9 frozen, resumable comparative experiments.

The experiment wrapper is a procedural guardrail, NOT trusted timestamping,
provider attestation, ground-truth validation, or a proof of causal advantage.
A completed trial is checkpointed atomically. A crash DURING a trial can result
in repeated external requests and costs on resume; this is disclosed to users.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Callable, Any

from .benchmark import (ARMS, BenchmarkError, Limits, FixtureProvider, LiveProvider,
                        grade, run_benchmark, verify_report)
from .models import digest
from .study import (StudyConfig, STUDY_SCHEMA, THRESHOLDS, WARNINGS, _analysis,
                    _trial_seed, validate_splits, verify_study)

PREREG_SCHEMA = 'rei0.preregistration.v1'
ADJUDICATION_SCHEMA = 'rei0.adjudications.v1'
CHECKPOINT_SCHEMA = 'rei0.experiment.checkpoint.v1'
EXPERIMENT_SCHEMA = 'rei0.experiment.report.v1'


def _exact(data: Any, fields: set[str], what: str) -> dict:
    if not isinstance(data, dict) or set(data) != fields:
        raise BenchmarkError(f'{what} requires exactly {sorted(fields)}')
    return data


def _nonempty(value: Any, name: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise BenchmarkError(f'{name} must be non-empty text of length <= {maximum}')
    return value


def _document_hash(document: dict) -> str:
    return digest(document)


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _implementation_digest() -> str:
    """Freeze the experiment's locally installed execution rules, not documentation.

    This fingerprints code bytes; it is NOT an independently trusted build
    attestation or a guarantee about the external model version.
    """
    root = Path(__file__).resolve().parent
    names = ('benchmark.py', 'study.py', 'experiment09.py', 'inquiry.py',
             'adapters.py', 'models.py', 'revision.py', 'review.py')
    from hashlib import sha256
    h = sha256()
    for name in names:
        payload = (root / name).read_bytes()
        h.update(name.encode('ascii') + b'\0' + len(payload).to_bytes(8, 'big') + payload)
    return h.hexdigest()


@dataclass(frozen=True)
class AnalysisPlan:
    comparator: str = 'baseline'
    primary_metric: str = 'overall_success'
    relative_token_tolerance: float = 0.1
    confirmatory_min_evaluation_cases: int = 30

    def __post_init__(self):
        if self.comparator not in ARMS[:-1] or self.primary_metric != 'overall_success':
            raise BenchmarkError('unsupported prespecified comparator or primary metric')
        tolerance = self.relative_token_tolerance
        if type(tolerance) not in (float, int) or not math.isfinite(tolerance) or not 0 <= tolerance <= 1:
            raise BenchmarkError('relative_token_tolerance must be finite in [0,1]')
        if (type(self.confirmatory_min_evaluation_cases) is not int or
                not 2 <= self.confirmatory_min_evaluation_cases <= 10000):
            raise BenchmarkError('invalid confirmatory minimum case count')


def fixture_identity(document: dict) -> dict:
    provider = FixtureProvider(document)  # schema validation
    return {'mode': provider.kind, 'fingerprint': provider.fingerprint,
            'model': None, 'endpoint': None}


def live_identity(model: str, endpoint: str = 'https://api.openai.com/v1/chat/completions') -> dict:
    provider = LiveProvider(model, endpoint=endpoint)  # NO network or credentials read
    return {'mode': provider.kind, 'fingerprint': provider.fingerprint,
            'model': provider.model, 'endpoint': provider.endpoint}


def _identity(identity: dict) -> dict:
    _exact(identity, {'mode', 'fingerprint', 'model', 'endpoint'}, 'provider identity')
    if identity['mode'] == FixtureProvider.kind:
        if identity['model'] is not None or identity['endpoint'] is not None:
            raise BenchmarkError('fixture identity must not include a live model/endpoint')
    elif identity['mode'] == LiveProvider.kind:
        actual = live_identity(identity['model'], identity['endpoint'])
        if actual != identity:
            raise BenchmarkError('live identity fingerprint mismatch')
    else:
        raise BenchmarkError('provider mode is not permitted')
    _nonempty(identity['fingerprint'], 'provider fingerprint', 128)
    return identity


def _key_digest_map(keys_doc: dict) -> dict[str, str]:
    return {k['case_id']: _document_hash(k) for k in keys_doc['answers']}


def validate_adjudications(manifest: dict, cal_keys_doc: dict, eval_keys_doc: dict) -> dict:
    """Checks declared independence & label binding, NOT reviewer identity/truth.

    No model can inspect this evaluator-only manifest unless the operator leaks it.
    """
    _exact(manifest, {'schema', 'records'}, 'adjudication manifest')
    if manifest['schema'] != ADJUDICATION_SCHEMA or not isinstance(manifest['records'], list):
        raise BenchmarkError('invalid adjudication manifest')
    expected = {**_key_digest_map(cal_keys_doc), **_key_digest_map(eval_keys_doc)}
    seen = set()
    for item in manifest['records']:
        _exact(item, {'case_id', 'key_sha256', 'curator', 'reviewer', 'reference', 'procedure'}, 'adjudication record')
        cid = _nonempty(item['case_id'], 'case_id', 80)
        if cid not in expected or cid in seen:
            raise BenchmarkError('adjudication IDs must be unique and cover the cases')
        seen.add(cid)
        if item['key_sha256'] != expected[cid]:
            raise BenchmarkError('adjudication key digest mismatch')
        curator = _nonempty(item['curator'], 'curator', 120)
        reviewer = _nonempty(item['reviewer'], 'reviewer', 120)
        if curator.casefold() == reviewer.casefold():
            raise BenchmarkError('reviewer must differ from curator')
        _nonempty(item['reference'], 'source reference')
        _nonempty(item['procedure'], 'review procedure')
    if seen != set(expected):
        raise BenchmarkError('incomplete adjudication manifest')
    return manifest


def synthetic_adjudications(cal_keys_doc: dict, eval_keys_doc: dict) -> dict:
    """For offline engineering tests ONLY: invented labels cannot verify facts."""
    return {'schema': ADJUDICATION_SCHEMA,
            'records': [{'case_id': cid, 'key_sha256': d,
                         'curator': 'synthetic-fixture-author', 'reviewer': 'synthetic-fixture-reviewer',
                         'reference': 'SYNTHETIC FIXTURE — no external corroboration',
                         'procedure': 'synthetic pipeline exercise, NOT independent fact verification'}
                        for cid, d in sorted({**_key_digest_map(cal_keys_doc),
                                               **_key_digest_map(eval_keys_doc)}.items())]}


def create_preregistration(cal_cases: dict, cal_keys: dict, eval_cases: dict, eval_keys: dict,
                           adjudications: dict, identity: dict, *,
                           study_id: str, config: StudyConfig = StudyConfig(),
                           limits: Limits = Limits(), plan: AnalysisPlan = AnalysisPlan(),
                           registered_at: str | None = None) -> dict:
    cc, _, ec, _ = validate_splits(cal_cases, cal_keys, eval_cases, eval_keys)
    validate_adjudications(adjudications, cal_keys, eval_keys)
    identity = _identity(identity)
    _nonempty(study_id, 'study ID', 100)
    if (len(cc) + len(ec))*len(ARMS)*config.repetitions*limits.max_calls > config.max_total_calls:
        raise BenchmarkError('preflight maximum live calls exceeds registered total call cap')
    date = registered_at or _stamp()
    _nonempty(date, 'registration timestamp', 100)
    try:
        parsed = datetime.fromisoformat(date.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('timezone required')
    except ValueError as exc:
        raise BenchmarkError('registration timestamp must be timezone-aware ISO8601') from exc
    core = {'schema': PREREG_SCHEMA, 'study_id': study_id,
            'registered_at': date, 'provider': identity,
            'implementation_sha256': _implementation_digest(),
            'dataset_digests': {'calibration_cases': digest(cal_cases),
                                'calibration_keys': digest(cal_keys),
                                'evaluation_cases': digest(eval_cases),
                                'evaluation_keys': digest(eval_keys),
                                'adjudications': digest(adjudications)},
            'study_config': asdict(config), 'limits': asdict(limits),
            'analysis_plan': asdict(plan),
            'registered_hypothesis': 'REI overall success differs from prespecified comparator, measured per case and repeated trial at fixed ceilings.',
            'gate': 'No confirmatory advantage when actual resource use is imbalanced; no claim from scripted fixtures; independent label manifest is declarative, not authenticated.',
            'precommit_note': 'SHA-256 is not proof of when registration occurred. Publish or timestamp the hash with an independent third party BEFORE evaluation.'}
    return {**core, 'preregistration_sha256': digest(core)}


def verify_preregistration(prereg: dict, cal_cases: dict, cal_keys: dict,
                           eval_cases: dict, eval_keys: dict, adjudications: dict) -> tuple[StudyConfig, Limits, AnalysisPlan]:
    _exact(prereg, {'schema','study_id','registered_at','provider','implementation_sha256','dataset_digests',
                    'study_config','limits','analysis_plan','registered_hypothesis','gate',
                    'precommit_note','preregistration_sha256'}, 'preregistration')
    if prereg['schema'] != PREREG_SCHEMA or digest({k:v for k,v in prereg.items() if k!='preregistration_sha256'}) != prereg['preregistration_sha256']:
        raise BenchmarkError('preregistration schema/hash mismatch')
    try:
        cfg = StudyConfig(**prereg['study_config'])
        lim = Limits(**prereg['limits'])
        plan = AnalysisPlan(**prereg['analysis_plan'])
        reconstituted = create_preregistration(cal_cases, cal_keys, eval_cases, eval_keys, adjudications,
            prereg['provider'], study_id=prereg['study_id'], config=cfg, limits=lim,
            plan=plan, registered_at=prereg['registered_at'])
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise BenchmarkError('malformed or invalid frozen experiment') from exc
    if reconstituted != prereg:
        raise BenchmarkError('frozen preregistration does not match inputs or original plan')
    return cfg, lim, plan


def _atomic_json(path: str | Path, doc: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=target.parent,
                                         prefix='.rei09-', suffix='.tmp', delete=False) as f:
            temp_path = Path(f.name)
            json.dump(doc, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, target)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def _read_checkpoint(checkpoint: str | Path, prereg: dict, inputs: tuple, config: StudyConfig,
                     limits: Limits) -> list[dict]:
    path = Path(checkpoint)
    if not path.exists():
        return []
    try:
        cp = json.loads(path.read_text('utf-8'))
        _exact(cp, {'schema','preregistration_sha256','records','checkpoint_sha256'}, 'checkpoint')
        core = {k:v for k,v in cp.items() if k != 'checkpoint_sha256'}
        if cp['schema'] != CHECKPOINT_SCHEMA or cp['checkpoint_sha256'] != digest(core) or cp['preregistration_sha256'] != prereg['preregistration_sha256']:
            raise BenchmarkError('checkpoint hash or preregistration binding mismatch')
        if not isinstance(cp['records'], list) or len(cp['records']) > config.repetitions * 2:
            raise BenchmarkError('invalid checkpoint record count')
        expected = [(phase,t) for phase in ('calibration','evaluation') for t in range(config.repetitions)]
        for i, record in enumerate(cp['records']):
            if not isinstance(record, dict) or set(record) != {'phase','trial','report'} or (record['phase'],record['trial']) != expected[i]:
                raise BenchmarkError('checkpoint trial order mismatch')
            c, k = inputs[:2] if record['phase']=='calibration' else inputs[2:]
            verify_report(record['report'], c, k)
            if (record['report']['seed'] != _trial_seed(config.seed,record['phase'],record['trial']) or
                record['report']['mode'] != prereg['provider']['mode'] or
                record['report']['provider_fingerprint'] != prereg['provider']['fingerprint'] or
                record['report']['budgets'] != asdict(limits)):
                raise BenchmarkError('checkpoint trial provenance mismatch')
        return cp['records']
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, BenchmarkError):
            raise
        raise BenchmarkError('malformed checkpoint') from exc


def _checkpoint(path: str | Path | None, prereg: dict, records: list[dict]) -> None:
    if path is None:
        return
    core = {'schema': CHECKPOINT_SCHEMA,
            'preregistration_sha256': prereg['preregistration_sha256'],
            'records': records}
    _atomic_json(path, {**core, 'checkpoint_sha256': digest(core)})


def _build_study(inputs: tuple, records: list[dict], prereg: dict,
                 config: StudyConfig, limits: Limits) -> dict:
    _, cal_keys_doc, eval_cases_doc, eval_keys_doc = inputs
    _, cal_keys, eval_cases, eval_keys = validate_splits(*inputs)
    policy, analysis = _analysis(records, cal_keys, eval_keys, eval_cases, config)
    doc = {'schema': STUDY_SCHEMA, 'mode': prereg['provider']['mode'],
           'provider_fingerprint': prereg['provider']['fingerprint'],
           'calibration_case_digest': digest(inputs[0]), 'calibration_key_digest': digest(cal_keys_doc),
           'evaluation_case_digest': digest(eval_cases_doc), 'evaluation_key_digest': digest(eval_keys_doc),
           'config': asdict(config), 'budgets': asdict(limits), 'trial_reports': records,
           'adaptive_policy': {'by_arm': policy, 'trained_on_calibration_only': True,
                               'candidate_thresholds': list(THRESHOLDS), 'tie_break':'lowest_threshold',
                               'rule':'abstain if confidence below learned threshold; missing confidence abstains only when threshold > 0'},
           'analysis': analysis, 'warnings': WARNINGS}
    return {**doc, 'report_sha256': digest(doc)}


def _matched_analysis(study: dict, inputs: tuple, plan: AnalysisPlan) -> dict:
    from .benchmark import load_study
    _, evaluation_keys = load_study(inputs[2], inputs[3])
    rows = {}
    for rec in study['trial_reports']:
        if rec['phase'] == 'evaluation':
            for o in rec['report']['outcomes']:
                rows[(o['case_id'],rec['trial'],o['arm'])] = o
    comparator = plan.comparator
    pairs = []
    for cid in sorted(evaluation_keys):
        for t in range(study['config']['repetitions']):
            x = rows[(cid,t,'rei')]
            y = rows[(cid,t,comparator)]
            xcalls, ycalls = x['model_calls'], y['model_calls']
            xtok, ytok = x['reported_tokens'], y['reported_tokens']
            calls_match = xcalls == ycalls
            tokens_match = (xtok == ytok)
            approximate_match = calls_match and (abs(xtok - ytok) /
                max(xtok,ytok,1) <= plan.relative_token_tolerance)
            pairs.append({'case_id':cid,'trial':t,
                          'rei_correct':bool(grade(x, evaluation_keys[cid])['correct']),
                          'comparator_correct':bool(grade(y, evaluation_keys[cid])['correct']),
                          'rei_calls':xcalls, 'comparator_calls':ycalls,
                          'rei_reported_tokens':xtok, 'comparator_reported_tokens':ytok,
                          'calls_match':calls_match, 'exact_usage_match':calls_match and tokens_match,
                          'within_preregistered_tolerance':approximate_match})
    exact = [p for p in pairs if p['exact_usage_match']]
    approximate = [p for p in pairs if p['within_preregistered_tolerance']]
    def difference(selection):
        return (sum(int(p['rei_correct'])-int(p['comparator_correct']) for p in selection)/len(selection)
                if selection else None)
    all_exact = len(exact) == len(pairs)
    all_approx = len(approximate) == len(pairs)
    cases_count = len(evaluation_keys)
    return {'primary_comparator': comparator,'primary_metric':'overall_success',
            'all_pairs':len(pairs),'case_count':cases_count,
            'observed_rei_minus_comparator':difference(pairs),
            'exact_usage_pairs':len(exact),
            'tolerance_matched_pairs':len(approximate),
            'exact_usage_subset_difference_exploratory': difference(exact),
            'tolerance_subset_difference_exploratory': difference(approximate),
            'actual_usage_status': ('exactly_matched' if all_exact else
                                    'within_tolerance' if all_approx else 'imbalanced'),
            'confirmatory_design_eligible': bool(all_approx and
                cases_count >= plan.confirmatory_min_evaluation_cases and
                study['mode'] == LiveProvider.kind),
            'preregistered_min_cases':plan.confirmatory_min_evaluation_cases,
            'warning': 'Usage-matched subsets are post-selection/exploratory; predeclared call/token ceilings are not equal actual compute. Matching does not remove other confounding.',
            'pairs':pairs}


def _experiment_document(prereg: dict, inputs: tuple, records: list[dict],
                         config: StudyConfig, limits: Limits, plan: AnalysisPlan) -> dict:
    study = _build_study(inputs, records, prereg, config, limits)
    fairness = _matched_analysis(study, inputs, plan)
    base = {'schema':EXPERIMENT_SCHEMA, 'preregistration':prereg,
            'study_report':study,'resource_comparability':fairness,
            'interpretation': ('Scripted evaluations are engineering checks, not empirical validation.'
                               if prereg['provider']['mode'] == FixtureProvider.kind else
                               'Recorded live outcomes require external provider attestations and independent replication before empirical claims.'),
            'provenance_warning':'Hashes can detect modification only relative to a trusted external anchor; provider calls and reviewer identities are not cryptographically attested.'}
    return {**base,'report_sha256':digest(base)}


def run_preregistered(prereg: dict, inputs: tuple, adjudications: dict,
                      provider_factory: Callable[[], Any], *, checkpoint: str | Path | None = None,
                      on_completed_trial: Callable[[dict], None] | None = None) -> dict:
    config, limits, plan = verify_preregistration(prereg, *inputs, adjudications)
    records = _read_checkpoint(checkpoint, prereg, inputs, config, limits) if checkpoint else []
    expected = [(phase,t) for phase in ('calibration','evaluation') for t in range(config.repetitions)]
    for phase,t in expected[len(records):]:
        provider = provider_factory()
        if (getattr(provider, 'fingerprint',None) != prereg['provider']['fingerprint'] or
                getattr(provider,'kind',None) != prereg['provider']['mode']):
            raise BenchmarkError('provider identity differs from preregistration; no trial started')
        c,k = inputs[:2] if phase == 'calibration' else inputs[2:]
        report = run_benchmark(c,k,provider,limits=limits,seed=_trial_seed(config.seed,phase,t))
        record = {'phase':phase,'trial':t,'report':report}
        records.append(record)
        _checkpoint(checkpoint,prereg,records)
        if on_completed_trial:
            on_completed_trial({'phase':phase,'trial':t,'model_calls':sum(o['model_calls'] for o in report['outcomes'])})
    result = _experiment_document(prereg, inputs, records, config, limits, plan)
    verify_experiment(result, inputs, adjudications)
    return result


def verify_experiment(report: dict, inputs: tuple, adjudications: dict) -> dict:
    _exact(report, {'schema','preregistration','study_report','resource_comparability',
                    'interpretation','provenance_warning','report_sha256'}, 'experiment report')
    core = {k:v for k,v in report.items() if k != 'report_sha256'}
    if report['schema'] != EXPERIMENT_SCHEMA or digest(core) != report['report_sha256']:
        raise BenchmarkError('experiment report schema/hash mismatch')
    prereg = report['preregistration']
    config, limits, plan = verify_preregistration(prereg,*inputs,adjudications)
    verify_study(report['study_report'], *inputs)
    records = report['study_report']['trial_reports']
    # Force recalculation from raw trials, including fitted policy & resource analyses.
    expected = _experiment_document(prereg, inputs, records, config, limits, plan)
    if expected != report:
        raise BenchmarkError('report metrics/interpretation deviate from preregistration')
    return {'valid':True, 'preregistration_sha256':prereg['preregistration_sha256'],
            'report_sha256':report['report_sha256'],
            'mode':prereg['provider']['mode'],
            'evaluation_cases':len(inputs[2]['cases']),
            'actual_usage_status':report['resource_comparability']['actual_usage_status'],
            'warning':'Regrading is not external attestation of trial execution or source truth'}


__all__ = ['AnalysisPlan','ADJUDICATION_SCHEMA','PREREG_SCHEMA','EXPERIMENT_SCHEMA',
           'create_preregistration','fixture_identity','live_identity','synthetic_adjudications',
           'validate_adjudications','verify_preregistration','run_preregistered','verify_experiment']
