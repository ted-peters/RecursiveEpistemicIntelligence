"""Operator CLI for repeated paired REI studies. Live calls are explicit opt-in."""
from __future__ import annotations

import argparse
from importlib.resources import files
import json
from pathlib import Path

from .benchmark import BenchmarkError, FixtureProvider, LiveProvider, Limits, read_json
from .study import StudyConfig, run_study, verify_study

COMMANDS = frozenset({'study-demo','study-run','study-verify'})


def _add_inputs(parser):
    for key in ('calibration-cases','calibration-keys','evaluation-cases','evaluation-keys'):
        parser.add_argument('--'+key, type=Path, required=True)


def _args(argv):
    p = argparse.ArgumentParser(prog='rei0', description='REI-0.8 repeated-trial study runner')
    commands = p.add_subparsers(dest='command', required=True)
    demo = commands.add_parser('study-demo', help='entirely synthetic demo; NOT a real-model study')
    demo.add_argument('--output', type=Path)
    demo.add_argument('--repetitions', type=int, default=2)
    demo.add_argument('--seed', type=int, default=19)
    run = commands.add_parser('study-run', help='paired repeated-trial evaluation with disjoint splits')
    _add_inputs(run)
    source = run.add_mutually_exclusive_group(required=True)
    source.add_argument('--fixture', type=Path, help='synthetic JSON scripted responses')
    source.add_argument('--live', action='store_true', help='explicit external HTTPS model inference')
    run.add_argument('--acknowledge-live-costs', action='store_true', help='required with --live')
    run.add_argument('--model', help='external model ID; required with --live')
    run.add_argument('--endpoint', default='https://api.openai.com/v1/chat/completions')
    run.add_argument('--output', type=Path)
    run.add_argument('--repetitions', type=int, default=3)
    run.add_argument('--seed', type=int, default=19)
    run.add_argument('--max-total-calls', type=int, default=1000)
    run.add_argument('--bootstrap-repetitions', type=int, default=1000)
    run.add_argument('--min-calibration-coverage', type=float, default=0.5)
    run.add_argument('--max-calls', type=int, default=4)
    run.add_argument('--max-tokens', type=int, default=4000)
    run.add_argument('--max-output-tokens', type=int, default=384)
    run.add_argument('--max-seconds', type=float, default=30)
    run.add_argument('--steps', type=int, default=2)
    verify = commands.add_parser('study-verify', help='regrade repeated trials with held-out keys')
    _add_inputs(verify)
    verify.add_argument('--report', type=Path, required=True)
    return p, p.parse_args(argv)


def _inputs(args):
    return tuple(read_json(getattr(args, key)) for key in (
        'calibration_cases','calibration_keys','evaluation_cases','evaluation_keys'))


def main_study(argv=None):
    p, args = _args(argv)
    try:
        if args.command == 'study-verify':
            result = verify_study(read_json(args.report), *_inputs(args))
            print(json.dumps(result, sort_keys=True, indent=2))
            return 0
        if args.command == 'study-demo':
            data = files('rei0').joinpath('data')
            inputs = tuple(json.loads(data.joinpath(f'study_{phase}_{part}.json').read_text())
                           for phase in ('calibration', 'evaluation') for part in ('cases', 'keys'))
            fixture_doc = json.loads(data.joinpath('benchmark_fixture.json').read_text())
            factory = lambda: FixtureProvider(fixture_doc)
            limits, config = Limits(), StudyConfig(repetitions=args.repetitions, seed=args.seed)
        else:
            inputs = _inputs(args)
            config = StudyConfig(repetitions=args.repetitions, seed=args.seed,
                max_total_calls=args.max_total_calls,
                bootstrap_repetitions=args.bootstrap_repetitions,
                min_calibration_coverage=args.min_calibration_coverage)
            limits = Limits(max_calls=args.max_calls, max_tokens=args.max_tokens,
                            max_output_tokens=args.max_output_tokens,
                            max_seconds=args.max_seconds, steps=args.steps)
            if args.live:
                if not args.acknowledge_live_costs or not args.model:
                    raise BenchmarkError('--live requires --model and --acknowledge-live-costs')
                model, endpoint = args.model, args.endpoint
                factory = lambda: LiveProvider(model, endpoint=endpoint)
            else:
                if args.model or args.acknowledge_live_costs:
                    raise BenchmarkError('--model/--acknowledge-live-costs require --live')
                fixture_doc = read_json(args.fixture)
                factory = lambda: FixtureProvider(fixture_doc)
        result = run_study(*inputs, factory, limits=limits, config=config)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
        print(json.dumps({'schema':result['schema'], 'mode':result['mode'],
                          'calibration_cases':len(inputs[0]['cases']),
                          'evaluation_cases':len(inputs[2]['cases']),
                          'repetitions':config.repetitions,
                          'raw_evaluation':result['analysis']['raw_evaluation'],
                          'adapted_evaluation':result['analysis']['adapted_evaluation'],
                          'paired':result['analysis']['raw_paired'],
                          'adaptive_thresholds':{a:p['threshold'] for a,p in result['adaptive_policy']['by_arm'].items()},
                          'output':str(args.output) if args.output else None,
                          'report_sha256':result['report_sha256'],
                          'warning':result['warnings'][0]}, sort_keys=True, indent=2))
        return 0
    except (BenchmarkError, TypeError, KeyError, ValueError, OSError) as exc:
        p.exit(2,f'REI-0.8 study error: {exc}\n')


if __name__=='__main__':
    raise SystemExit(main_study())
