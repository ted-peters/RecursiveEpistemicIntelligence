"""REI-0.7: bounded, reproducible, paired answer benchmarks.

No model text is treated as verified evidence. Answer keys are held by the
grader only. The bundled scripted fixture tests the experiment pipeline, not
real model ability. Hashes are tamper-evident only with an external anchor.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import random
import time
from typing import Any, Mapping
from urllib.parse import urlparse
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError

from .adapters import SYSTEM_INITIAL, SYSTEM_EXPAND, _NoRedirect
from .inquiry import (ExpansionDraft, InitialDraft, InquiryEngine,
                      InquiryError, InquiryLimits, ModelTurn)
from .models import digest, canonical_json

ARMS = ('baseline', 'self_critique', 'fixed_depth', 'rei')
CASE_SCHEMA = 'rei0.benchmark.cases.v1'
KEY_SCHEMA = 'rei0.benchmark.keys.v1'
FIXTURE_SCHEMA = 'rei0.benchmark.fixture.v1'
REPORT_SCHEMA = 'rei0.benchmark.report.v1'
FIXED_CLOCK = '2026-11-10T00:00:00Z'  # deterministic example graph timestamps


class BenchmarkError(ValueError):
    """Benchmark schema, budget, model, or grade failure."""


def _object(value: Any, required: set[str], optional: set[str] = frozenset()) -> dict:
    if not isinstance(value, dict) or set(value) - (required | optional) or not required <= set(value):
        raise BenchmarkError(f'expected exact fields {sorted(required)} (optional {sorted(optional)})')
    return value


def _text(v: Any, field: str, maximum: int = 3000) -> str:
    if not isinstance(v, str) or not v.strip() or len(v) > maximum:
        raise BenchmarkError(f'{field} must be nonblank text <= {maximum} characters')
    return v.strip()


def _integer(v: Any, name: str, min_value: int, max_value: int) -> int:
    if type(v) is not int or not min_value <= v <= max_value:
        raise BenchmarkError(f'{name} must be an integer in [{min_value}, {max_value}]')
    return v


def read_json(path: str | Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkError('cannot read JSON input') from exc
    if not isinstance(data, dict):
        raise BenchmarkError('JSON document must be an object')
    return data


@dataclass(frozen=True)
class Case:
    id: str
    question: str
    context: str
    category: str

    @classmethod
    def from_dict(cls, raw: dict) -> 'Case':
        _object(raw, {'id', 'question', 'context', 'category'})
        return cls(_text(raw['id'], 'case ID', 80),
                   _text(raw['question'], 'question'),
                   raw['context'] if isinstance(raw['context'], str) and len(raw['context']) <= 3000 else
                   _raise('context must be text <= 3000 characters'),
                   _text(raw['category'], 'category', 80))

    def prompt(self) -> str:
        return self.question + (f'\nContext:\n{self.context}' if self.context else '')


def _raise(msg: str):
    raise BenchmarkError(msg)


@dataclass(frozen=True)
class Key:
    case_id: str
    acceptable: tuple[str, ...]
    unanswerable: bool

    @classmethod
    def from_dict(cls, raw: dict) -> 'Key':
        _object(raw, {'case_id', 'acceptable', 'unanswerable'})
        if type(raw['unanswerable']) is not bool:
            raise BenchmarkError('unanswerable must be boolean')
        values = raw['acceptable']
        if not isinstance(values, list) or (not raw['unanswerable'] and not values) or len(values) > 20:
            raise BenchmarkError('acceptable answers must be a list with 1-20 entries for answerable cases')
        if raw['unanswerable'] and values:
            raise BenchmarkError('unanswerable cases must have no acceptable answers')
        normalized = tuple(_text(x, 'acceptable answer', 200) for x in values)
        if len(set(normalize(x) for x in normalized)) != len(normalized):
            raise BenchmarkError('duplicate acceptable answers')
        return cls(_text(raw['case_id'], 'case ID', 80), normalized, raw['unanswerable'])


def normalize(value: str) -> str:
    return ' '.join(value.strip().casefold().split())


def load_study(cases_doc: dict, keys_doc: dict) -> tuple[tuple[Case, ...], dict[str, Key]]:
    _object(cases_doc, {'schema', 'cases'})
    _object(keys_doc, {'schema', 'answers'})
    if cases_doc['schema'] != CASE_SCHEMA or keys_doc['schema'] != KEY_SCHEMA:
        raise BenchmarkError('unsupported dataset schema')
    if not isinstance(cases_doc['cases'], list) or not 1 <= len(cases_doc['cases']) <= 10000:
        raise BenchmarkError('benchmark must have 1-10000 cases')
    if not isinstance(keys_doc['answers'], list):
        raise BenchmarkError('answer keys must be a list')
    cases = tuple(Case.from_dict(c) for c in cases_doc['cases'])
    keys_list = [Key.from_dict(k) for k in keys_doc['answers']]
    if len({c.id for c in cases}) != len(cases) or len({k.case_id for k in keys_list}) != len(keys_list):
        raise BenchmarkError('duplicate case or answer ID')
    keys = {k.case_id: k for k in keys_list}
    if set(keys) != {c.id for c in cases}:
        raise BenchmarkError('public cases and held-out answer keys do not match')
    return cases, keys


@dataclass(frozen=True)
class Limits:
    max_calls: int = 4
    max_tokens: int = 4000
    max_seconds: float = 30.0
    max_output_tokens: int = 384
    steps: int = 2

    def __post_init__(self):
        _integer(self.max_calls, 'max_calls', 1, 20)
        _integer(self.max_tokens, 'max_tokens', 1, 1000000)
        _integer(self.max_output_tokens, 'max_output_tokens', 1, 4096)
        _integer(self.steps, 'steps', 0, 12)
        if type(self.max_seconds) not in (float, int) or not math.isfinite(self.max_seconds) or not 0 < self.max_seconds <= 3600:
            raise BenchmarkError('invalid time budget')


class FixtureProvider:
    """Synthetic recorded stage turns. No calls to the network."""
    kind = 'scripted_fixture_not_empirical'

    def __init__(self, document: dict):
        _object(document, {'schema', 'records'})
        if document['schema'] != FIXTURE_SCHEMA or not isinstance(document['records'], list):
            raise BenchmarkError('invalid fixture schema')
        self.records = {}
        self.indices = {}
        for row in document['records']:
            _object(row, {'case_id', 'arm', 'turns'})
            cid = _text(row['case_id'], 'case ID', 80)
            arm = row['arm']
            if arm not in ARMS or not isinstance(row['turns'], list):
                raise BenchmarkError('invalid fixture arm or turn list')
            pair = (cid, arm)
            if pair in self.records:
                raise BenchmarkError('duplicate fixture record')
            turns = []
            for turn in row['turns']:
                _object(turn, {'stage', 'payload', 'tokens_used'})
                if turn['stage'] not in ('initial', 'expand', 'draft', 'critique', 'final'):
                    raise BenchmarkError('invalid fixture stage')
                turns.append((turn['stage'], ModelTurn(turn['payload'], turn['tokens_used'])))
            self.records[pair] = turns
            self.indices[pair] = 0
        self.fingerprint = digest(document)

    def respond(self, *, case_id: str, arm: str, stage: str, context: dict,
                max_output_tokens: int, timeout: float) -> ModelTurn:
        pair = (case_id, arm)
        steps = self.records.get(pair)
        i = self.indices.get(pair, 0)
        if steps is None or i >= len(steps):
            raise BenchmarkError('fixture exhausted')
        expected_stage, response = steps[i]
        if expected_stage != stage:
            raise BenchmarkError(f'fixture stage mismatch: expected {expected_stage}, received {stage}')
        self.indices[pair] += 1
        return response


_STAGE_SYSTEM = {
    'draft': 'Produce a single provisional answer. Return ONLY JSON: {"answer":string|null,"confidence":number|null,"rationale":string}. A null answer means abstain. Confidence is the probability this answer is correct. Do not claim evidence is verified.',
    'final': 'Answer the question, considering any supplied prior work. Return ONLY JSON: {"answer":string|null,"confidence":number|null,"rationale":string}. Use null answer when insufficient information; confidence means probability the answer is correct. Do not invent verification.',
    'critique': 'Critically inspect the draft for errors, faulty assumptions and missing evidence. Return ONLY JSON: {"critique":string}. No extra fields.',
    'initial': SYSTEM_INITIAL,
    'expand': SYSTEM_EXPAND,
}


class LiveProvider:
    """Explicit opt-in, JSON-only HTTPS adapter. Never runs tools or receives answer keys.

    Only provider-reported total_tokens are accepted: no guessed token counts.
    """
    kind = 'live_external_model'

    def __init__(self, model: str, endpoint: str = 'https://api.openai.com/v1/chat/completions',
                 key_env: str = 'REI_LLM_API_KEY'):
        self.model = _text(model, 'model ID', 120)
        p = urlparse(endpoint)
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.fragment:
            raise BenchmarkError('HTTPS endpoint required without user info or fragment')
        self.endpoint = endpoint
        if not key_env.isidentifier():
            raise BenchmarkError('invalid API key environment variable name')
        self.key_env = key_env
        self.fingerprint = digest({'model': self.model, 'endpoint': self.endpoint, 'api': 'chat-completions'})

    def respond(self, *, case_id: str, arm: str, stage: str, context: dict,
                max_output_tokens: int, timeout: float) -> ModelTurn:
        key = os.environ.get(self.key_env)
        if not key:
            raise BenchmarkError(f'API key environment variable {self.key_env} is missing')
        messages = [{'role': 'system', 'content': _STAGE_SYSTEM[stage]},
                    {'role': 'user', 'content': json.dumps({'stage':stage, 'arm':arm,
                     'context':context}, ensure_ascii=False, sort_keys=True)}]
        payload = {'model': self.model, 'messages': messages, 'response_format': {'type': 'json_object'},
                   'max_completion_tokens': max_output_tokens}
        request = Request(self.endpoint, data=json.dumps(payload).encode('utf-8'),
                          headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                          method='POST')
        try:
            with build_opener(_NoRedirect).open(request, timeout=timeout) as response:
                raw = response.read(65537)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise BenchmarkError(f'HTTPS model call failed ({type(exc).__name__})') from None
        if len(raw) > 65536:
            raise BenchmarkError('model response exceeds 65536 bytes')
        try:
            doc = json.loads(raw.decode('utf-8'))
            result = json.loads(doc['choices'][0]['message']['content'])
            tokens = doc['usage']['total_tokens']
            if type(tokens) is not int or tokens < 0:
                raise ValueError('invalid model token usage')
            return ModelTurn(result, tokens)
        except (ValueError, TypeError, KeyError, IndexError, UnicodeDecodeError) as exc:
            raise BenchmarkError('malformed model JSON or missing exact token usage') from exc


def _validate_stage(stage: str, payload: dict) -> dict:
    if stage in ('initial', 'expand'):
        try:
            InitialDraft.parse(payload) if stage == 'initial' else ExpansionDraft.parse(payload)
        except InquiryError as exc:
            raise BenchmarkError(str(exc)) from exc
        return payload
    if stage == 'critique':
        _object(payload, {'critique'})
        _text(payload['critique'], 'critique', 2000)
        return payload
    if stage in ('draft', 'final'):
        _object(payload, {'answer', 'confidence', 'rationale'})
        answer = payload['answer']
        if answer is not None:
            _text(answer, 'answer', 500)
        confidence = payload['confidence']
        if confidence is not None and (type(confidence) not in (int, float) or
                                       not math.isfinite(confidence) or not 0 <= confidence <= 1):
            raise BenchmarkError('confidence must be null or a finite number from 0 to 1')
        if answer is None and confidence is not None:
            raise BenchmarkError('abstentions must report null confidence')
        _text(payload['rationale'], 'rationale', 2000)
        return payload
    raise BenchmarkError('unknown model stage')


class Meter:
    def __init__(self, provider, case: Case, arm: str, limits: Limits, *, monotonic=time.monotonic):
        self.provider, self.case, self.arm, self.limits = provider, case, arm, limits
        self.monotonic = monotonic
        self.start = monotonic()
        self.calls = 0
        self.tokens = 0
        self.trace: list[dict[str, Any]] = []

    def call(self, stage: str, context: dict, *, max_output_tokens: int | None = None,
             timeout: float | None = None) -> ModelTurn:
        if self.calls >= self.limits.max_calls:
            raise BenchmarkError('model call budget exhausted')
        remaining = self.limits.max_tokens - self.tokens
        if remaining <= 0:
            raise BenchmarkError('token budget exhausted')
        seconds = self.limits.max_seconds - (self.monotonic() - self.start)
        if seconds <= 0:
            raise BenchmarkError('time budget exhausted')
        cap = min(self.limits.max_output_tokens, remaining,
                  max_output_tokens if max_output_tokens is not None else self.limits.max_output_tokens)
        effective_time = min(seconds, timeout if timeout is not None else seconds)
        if cap < 1 or effective_time <= 0:
            raise BenchmarkError('budget exhausted before model call')
        # Charge even failed model turns; avoid free retries that bias arms.
        self.calls += 1
        try:
            turn = self.provider.respond(case_id=self.case.id, arm=self.arm, stage=stage,
                                         context=context, max_output_tokens=cap, timeout=effective_time)
            if not isinstance(turn, ModelTurn):
                raise BenchmarkError('provider must return ModelTurn')
            self.tokens += turn.tokens_used
            self.trace.append({'stage': stage, 'tokens_used': turn.tokens_used,
                               'payload_sha256': digest(turn.payload)})
            if self.tokens > self.limits.max_tokens:
                raise BenchmarkError('model reported token overrun')
            if self.monotonic() - self.start > self.limits.max_seconds:
                raise BenchmarkError('time budget exceeded by model response')
            _validate_stage(stage, turn.payload)
            return turn
        except (BenchmarkError, InquiryError, OSError, TypeError, ValueError) as exc:
            self.trace.append({'stage': stage, 'error': type(exc).__name__})
            raise BenchmarkError(str(exc)) from exc


class InquiryBridge:
    name = 'rei0.7-benchmark-inquiry'
    def __init__(self, meter: Meter):
        self.meter = meter

    def initial(self, question: str, *, max_output_tokens: int, timeout: float) -> ModelTurn:
        return self.meter.call('initial', {'question': question}, max_output_tokens=max_output_tokens, timeout=timeout)

    def expand(self, context: dict, *, ordinal: int, max_output_tokens: int, timeout: float) -> ModelTurn:
        return self.meter.call('expand', {'ordinal': ordinal, 'context': context},
                               max_output_tokens=max_output_tokens, timeout=timeout)


def _run_arm(case: Case, arm: str, meter: Meter, limits: Limits) -> tuple[dict | None, dict]:
    """Return final response and non-authoritative, auditable reasoning metadata."""
    question = case.prompt()
    if arm == 'baseline':
        final = meter.call('final', {'question': question}).payload
        return final, {'algorithm': 'single_pass'}
    if arm == 'self_critique':
        draft = meter.call('draft', {'question': question}).payload
        critique = meter.call('critique', {'question': question, 'draft': draft}).payload
        final = meter.call('final', {'question': question, 'draft': draft,
                                     'critique': critique['critique']}).payload
        return final, {'algorithm': 'draft_critique_revise'}
    if arm == 'fixed_depth':
        initial = InitialDraft.parse(meter.call('initial', {'question': question}).payload)
        queue = [q.text for q in initial.questions]
        history = []
        for ordinal in range(limits.steps):
            if not queue:
                break
            challenge = queue.pop(0)  # fixed FIFO, no epistemic graph or priority scheduling
            context = {'question': question, 'claim': initial.claim,
                       'challenge': challenge, 'history': history, 'ordinal': ordinal}
            expansion = ExpansionDraft.parse(meter.call('expand', context).payload)
            history.append({'challenge': challenge, 'reasons': list(expansion.reasons),
                            'objections': list(expansion.objections)})
            queue.extend(q.text for q in expansion.followups)
        final = meter.call('final', {'question': question, 'claim': initial.claim,
                                     'history': history, 'unresolved': queue}).payload
        return final, {'algorithm': 'fifo_fixed_depth', 'steps': len(history),
                       'unresolved_questions': len(queue)}
    if arm == 'rei':
        # Keep at least one request for final synthesis. The graph assesses model
        # arguments as NEITHER; REI does not launder them into verified evidence.
        inquiry_limits = InquiryLimits(max_steps=limits.steps, max_depth=max(1, limits.steps + 1),
                       max_model_calls=max(1, limits.max_calls - 1),
                       max_tokens=limits.max_tokens, max_seconds=limits.max_seconds,
                       max_output_tokens=limits.max_output_tokens)
        session = InquiryEngine(InquiryBridge(meter), inquiry_limits,
                                clock=lambda: FIXED_CLOCK,
                                monotonic=meter.monotonic).run(question)
        data = session.report()
        if data['evidence_assessment']['state'] != 'NEITHER':
            raise BenchmarkError('model text illegally acquired verified evidence credit')
        # The model may synthesize an answer; this is still a provisional claim.
        if session.stop_reason in ('model_error', 'reported_token_overrun', 'time_budget'):
            raise BenchmarkError(f'inquiry stopped on invalid or over-budget model output: {session.stop_reason}')
        final = meter.call('final', {'question': question, 'inquiry_report': data}).payload
        return final, {'algorithm': 'priority_epistemic_graph', 'steps': session.steps,
                       'unresolved_questions': len(session.queue),
                       'stop_reason': session.stop_reason, 'graph_audit_head': session.graph.audit_head,
                       'evidence_state': data['evidence_assessment']['state']}
    raise BenchmarkError('unknown benchmark arm')


def grade(outcome: dict, key: Key) -> dict:
    answered = outcome['answer'] is not None
    if outcome['error'] is not None:
        return {'correct': False, 'answered': answered, 'answerable': not key.unanswerable}
    accurate = (not answered) if key.unanswerable else (
        answered and normalize(outcome['answer']) in {normalize(v) for v in key.acceptable})
    return {'correct': bool(accurate), 'answered': answered,
            'answerable': not key.unanswerable}


def summarize(outcomes: list[dict], keys: Mapping[str, Key]) -> dict:
    by_arm = {}
    for arm in ARMS:
        rows = [o for o in outcomes if o['arm'] == arm]
        denom = len(rows)
        if not denom:
            raise BenchmarkError('missing benchmark arm')
        graded = [(o, grade(o, keys[o['case_id']])) for o in rows]
        answerable = [(o, g) for o, g in graded if g['answerable']]
        selected = [(o, g) for o, g in answerable if g['answered']]
        unanswerable = [(o, g) for o, g in graded if not g['answerable']]
        with_confidence = [(o, g) for o, g in graded if o['answer'] is not None and o['confidence'] is not None]
        by_arm[arm] = {
            'cases': denom,
            'overall_success': sum(g['correct'] for _, g in graded) / denom,
            'answerable_accuracy': sum(g['correct'] for _, g in answerable) / len(answerable) if answerable else None,
            'selective_accuracy': sum(g['correct'] for _, g in selected) / len(selected) if selected else None,
            'coverage_answerable': len(selected) / len(answerable) if answerable else None,
            'abstention_rate': sum(not g['answered'] for _, g in graded) / denom,
            'false_answer_rate_unanswerable': sum(g['answered'] for _, g in unanswerable) / len(unanswerable) if unanswerable else None,
            'brier_on_answered_with_confidence': sum((o['confidence'] - int(g['correct']))**2 for o,g in with_confidence) / len(with_confidence) if with_confidence else None,
            'confidence_sample_count': len(with_confidence),
            'total_model_calls': sum(o['model_calls'] for o in rows),
            'total_reported_tokens': sum(o['reported_tokens'] for o in rows),
            'failed_runs': sum(o['error'] is not None for o in rows),
        }
    return by_arm


def paired_intervals(outcomes: list[dict], keys: Mapping[str, Key], *, seed: int,
                     repetitions: int = 1000) -> dict:
    by_pair = {(o['case_id'], o['arm']): grade(o, keys[o['case_id']])['correct']
               for o in outcomes}
    ids = sorted(keys)
    result = {}
    for arm in ARMS[:-1]:
        diffs = [int(by_pair[(cid, 'rei')]) - int(by_pair[(cid, arm)]) for cid in ids]
        mean = sum(diffs) / len(diffs)
        rng = random.Random(f'{seed}:{arm}:rei:paired-bootstrap-v1')
        draws = sorted(sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(repetitions))
        matched = [cid for cid in ids if next(o for o in outcomes if o['case_id'] == cid and o['arm'] == arm)['reported_tokens'] ==
                   next(o for o in outcomes if o['case_id'] == cid and o['arm'] == 'rei')['reported_tokens'] and
                   next(o for o in outcomes if o['case_id'] == cid and o['arm'] == arm)['model_calls'] ==
                   next(o for o in outcomes if o['case_id'] == cid and o['arm'] == 'rei')['model_calls']]
        result[f'rei_minus_{arm}'] = {'paired_mean_difference': mean,
            'exact_reported_usage_matched_pairs': len(matched),
            'difference_on_exact_usage_matched_pairs':
                sum(int(by_pair[(cid, 'rei')]) - int(by_pair[(cid, arm)]) for cid in matched) / len(matched)
                if matched else None,
            'bootstrap_95_percent_interval': [draws[int(.025 * repetitions)],
                draws[min(repetitions - 1, int(.975 * repetitions))]],
            'pairs': len(diffs), 'repetitions': repetitions}
    return result


def run_benchmark(cases_doc: dict, keys_doc: dict, provider, *, limits: Limits = Limits(),
                  seed: int = 7) -> dict:
    _integer(seed, 'seed', 0, 2**31 - 1)
    cases, keys = load_study(cases_doc, keys_doc)
    if not hasattr(provider, 'respond') or not hasattr(provider, 'kind'):
        raise BenchmarkError('provider must implement respond() and kind')
    tasks = [(c, arm) for c in cases for arm in ARMS]
    random.Random(seed).shuffle(tasks)
    outcomes = []
    for case, arm in tasks:
        meter = Meter(provider, case, arm, limits)
        output = None
        details = {}
        error = None
        try:
            final, details = _run_arm(case, arm, meter, limits)
            output = final
        except (BenchmarkError, InquiryError, OSError, ValueError, TypeError, KeyError) as exc:
            error = f'{type(exc).__name__}: {str(exc)[:150]}'
        outcomes.append({'case_id': case.id, 'arm': arm,
                         'answer': output['answer'] if output else None,
                         'confidence': output['confidence'] if output else None,
                         'rationale': output['rationale'] if output else None,
                         'error': error, 'model_calls': meter.calls,
                         'reported_tokens': meter.tokens, 'trace': meter.trace,
                         'reasoning': details})
    # Canonical report order independent of randomized execution schedule.
    outcomes.sort(key=lambda x: (x['case_id'], ARMS.index(x['arm'])))
    report = {'schema': REPORT_SCHEMA, 'mode': provider.kind,
              'provider_fingerprint': provider.fingerprint,
              'case_set_digest': digest(cases_doc), 'answer_key_digest': digest(keys_doc),
              'seed': seed, 'budgets': asdict(limits), 'outcomes': outcomes,
              'summary': summarize(outcomes, keys),
              'paired_comparisons': paired_intervals(outcomes, keys, seed=seed),
              'warnings': [
                  'Scripted fixture results are synthetic integration tests, not evidence of comparative AI ability.'
                  if provider.kind == FixtureProvider.kind else
                  'Live results require provider identity, model versions, and independent replication.',
                  'Identical maximum budgets do not imply identical consumed tokens or model calls.',
                  'Exact-match reference grading cannot assess all valid semantic paraphrases.',
                  'All model-generated arguments remain provisional; no independent source verification is performed by this benchmark.',
                  'Report checksum is not an authenticated signature; preserve its hash externally.'
              ]}
    return {**report, 'report_sha256': digest(report)}


def verify_report(report: dict, cases_doc: dict, keys_doc: dict) -> dict:
    if not isinstance(report, dict) or 'report_sha256' not in report:
        raise BenchmarkError('report checksum missing')
    payload = {k:v for k,v in report.items() if k != 'report_sha256'}
    if report['report_sha256'] != digest(payload):
        raise BenchmarkError('benchmark report checksum invalid')
    if payload.get('schema') != REPORT_SCHEMA or payload.get('case_set_digest') != digest(cases_doc) or payload.get('answer_key_digest') != digest(keys_doc):
        raise BenchmarkError('benchmark dataset or answer key digest mismatch')
    cases, keys = load_study(cases_doc, keys_doc)
    outcomes = payload.get('outcomes')
    if not isinstance(outcomes, list) or len(outcomes) != len(cases)*len(ARMS):
        raise BenchmarkError('report has missing or extra outcomes')
    pairs = [(o['case_id'], o['arm']) for o in outcomes]
    if len(set(pairs)) != len(pairs) or set(pairs) != {(c.id,a) for c in cases for a in ARMS}:
        raise BenchmarkError('report outcome case/arm pairs invalid')
    if payload['summary'] != summarize(outcomes, keys):
        raise BenchmarkError('report metrics differ from recorded outcomes')
    if payload['paired_comparisons'] != paired_intervals(outcomes, keys, seed=payload['seed']):
        raise BenchmarkError('report paired comparisons mismatch')
    return {'valid': True, 'report_sha256': report['report_sha256'], 'case_count': len(cases),
            'outcome_count': len(outcomes), 'warning': 'Checksum/regrading check, not authenticated model-run attestation'}
