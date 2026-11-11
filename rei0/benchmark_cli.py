"""REI-0.7 benchmark operator commands. Live inference is always explicit."""
from __future__ import annotations

import argparse
from importlib.resources import files
import json
from pathlib import Path
import sys

from .benchmark import (BenchmarkError, FixtureProvider, LiveProvider, Limits,
                        read_json, run_benchmark, verify_report)

COMMANDS = frozenset(('benchmark-demo', 'benchmark-run', 'benchmark-verify'))


def _args(argv):
    parser = argparse.ArgumentParser(prog='rei0', description='REI-0.7 paired reproducible benchmarks')
    commands = parser.add_subparsers(dest='command', required=True)
    demo = commands.add_parser('benchmark-demo', help='offline synthetic fixture; NOT an empirical model comparison')
    demo.add_argument('--output', type=Path)
    demo.add_argument('--seed', type=int, default=7)
    run = commands.add_parser('benchmark-run', help='run four arms using fixtures or an explicitly enabled HTTPS model')
    run.add_argument('--cases', type=Path, required=True, help='public questions JSON')
    run.add_argument('--keys', type=Path, required=True, help='held-out grading keys JSON (never sent to provider)')
    source = run.add_mutually_exclusive_group(required=True)
    source.add_argument('--fixture', type=Path, help='offline stage responses JSON')
    source.add_argument('--live', action='store_true', help='call external model; may incur charges')
    run.add_argument('--model', help='required if --live')
    run.add_argument('--endpoint', default='https://api.openai.com/v1/chat/completions')
    run.add_argument('--output', type=Path, required=True)
    run.add_argument('--seed', type=int, default=7)
    run.add_argument('--max-calls', type=int, default=4)
    run.add_argument('--max-tokens', type=int, default=4000)
    run.add_argument('--max-output-tokens', type=int, default=384)
    run.add_argument('--max-seconds', type=float, default=30)
    run.add_argument('--steps', type=int, default=2)
    verify = commands.add_parser('benchmark-verify', help='recompute grades and verify report checksums')
    verify.add_argument('--report', type=Path, required=True)
    verify.add_argument('--cases', type=Path, required=True)
    verify.add_argument('--keys', type=Path, required=True)
    return parser, parser.parse_args(argv)


def main_benchmark(argv=None):
    parser, args = _args(argv)
    try:
        if args.command == 'benchmark-verify':
            payload = verify_report(read_json(args.report), read_json(args.cases), read_json(args.keys))
        else:
            if args.command == 'benchmark-demo':
                data = files('rei0').joinpath('data')
                cases_doc = json.loads(data.joinpath('benchmark_cases.json').read_text(encoding='utf-8'))
                keys_doc = json.loads(data.joinpath('benchmark_keys.json').read_text(encoding='utf-8'))
                provider = FixtureProvider(json.loads(data.joinpath('benchmark_fixture.json').read_text(encoding='utf-8')))
                limits = Limits()
            else:
                cases_doc, keys_doc = read_json(args.cases), read_json(args.keys)
                if args.live:
                    if not args.model:
                        raise BenchmarkError('--model is required with --live')
                    provider = LiveProvider(args.model, endpoint=args.endpoint)
                else:
                    if args.model:
                        raise BenchmarkError('--model only applies to --live')
                    provider = FixtureProvider(read_json(args.fixture))
                limits = Limits(max_calls=args.max_calls, max_tokens=args.max_tokens,
                                max_output_tokens=args.max_output_tokens,
                                max_seconds=args.max_seconds, steps=args.steps)
            payload = run_benchmark(cases_doc, keys_doc, provider, limits=limits, seed=args.seed)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(payload if args.command=='benchmark-verify' else {
            'schema': payload['schema'], 'mode': payload['mode'], 'cases': len(cases_doc['cases']),
            'summary': payload['summary'], 'paired_comparisons': payload['paired_comparisons'],
            'report_sha256': payload['report_sha256'],
            'output': str(args.output) if args.output else None,
            'warning': payload['warnings'][0],
        }, indent=2, sort_keys=True))
        return 0
    except (BenchmarkError, ValueError, TypeError, KeyError, OSError) as exc:
        parser.exit(2, f'REI-0.7 benchmark error: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main_benchmark())
