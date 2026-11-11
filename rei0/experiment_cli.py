"""Preregistered REI-0.9 study commands; live inference always explicit opt-in."""
from __future__ import annotations
import argparse
from importlib.resources import files
import json
from pathlib import Path

from .benchmark import BenchmarkError, FixtureProvider, LiveProvider, read_json
from .experiment09 import (AnalysisPlan, create_preregistration,
    fixture_identity, live_identity, synthetic_adjudications,
    run_preregistered, verify_experiment, verify_preregistration)
from .study import StudyConfig
from .benchmark import Limits

EXPERIMENT_COMMANDS = frozenset({'experiment-demo', 'experiment-adjudication-template',
    'experiment-preregister', 'experiment-run', 'experiment-verify'})


def _inputs(p):
    for field in ('calibration-cases','calibration-keys','evaluation-cases','evaluation-keys'):
        p.add_argument('--'+field, type=Path, required=True)


def _get_inputs(a):
    return tuple(read_json(getattr(a,name)) for name in (
        'calibration_cases','calibration_keys','evaluation_cases','evaluation_keys'))


def _write(path, doc):
    if path:
        p=Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n', encoding='utf-8')


def _provider_args(p, *, require=False):
    g=p.add_mutually_exclusive_group(required=require)
    g.add_argument('--fixture',type=Path,help='scripted offline fixture; cannot validate AI ability')
    g.add_argument('--live',action='store_true',help='allow real HTTPS provider calls and costs')
    p.add_argument('--model', help='model ID (required with --live)')
    p.add_argument('--endpoint',default='https://api.openai.com/v1/chat/completions')
    p.add_argument('--acknowledge-live-costs',action='store_true')


def _source(a):
    if a.live:
        if not a.acknowledge_live_costs or not a.model:
            raise BenchmarkError('--live requires --model and --acknowledge-live-costs')
        identity=live_identity(a.model,a.endpoint)
        factory=lambda:LiveProvider(a.model,endpoint=a.endpoint)
    elif a.fixture is not None:
        if a.acknowledge_live_costs or a.model:
            raise BenchmarkError('--model/--acknowledge-live-costs require --live')
        doc=read_json(a.fixture)
        identity=fixture_identity(doc)
        factory=lambda:FixtureProvider(doc)
    else:
        raise BenchmarkError('choose --fixture or --live')
    return identity, factory


def _create_args(p):
    p.add_argument('--study-id',required=True)
    p.add_argument('--repetitions',type=int,default=3)
    p.add_argument('--seed',type=int,default=19)
    p.add_argument('--max-total-calls',type=int,default=1000)
    p.add_argument('--bootstrap-repetitions',type=int,default=1000)
    p.add_argument('--min-calibration-coverage',type=float,default=0.5)
    p.add_argument('--max-calls',type=int,default=4)
    p.add_argument('--max-tokens',type=int,default=4000)
    p.add_argument('--max-output-tokens',type=int,default=384)
    p.add_argument('--max-seconds',type=float,default=30)
    p.add_argument('--steps',type=int,default=2)
    p.add_argument('--comparator',choices=('baseline','self_critique','fixed_depth'),default='baseline')
    p.add_argument('--relative-token-tolerance',type=float,default=0.1)
    p.add_argument('--confirmatory-min-cases',type=int,default=30)


def _parser():
    p=argparse.ArgumentParser(prog='rei0',description='REI-0.9 frozen and replayable empirical experiment protocol')
    sub=p.add_subparsers(dest='cmd',required=True)
    demo=sub.add_parser('experiment-demo',help='entirely synthetic four-arm engineering demo')
    demo.add_argument('--output-dir',type=Path,default=Path('rei09_demo'))
    template=sub.add_parser('experiment-adjudication-template',help='blank reviewer declarations; complete offline')
    template.add_argument('--calibration-keys',type=Path,required=True)
    template.add_argument('--evaluation-keys',type=Path,required=True)
    template.add_argument('--output',type=Path,required=True)
    register=sub.add_parser('experiment-preregister',help='freeze the protocol BEFORE any held-out evaluation')
    _inputs(register)
    register.add_argument('--adjudications',type=Path,required=True)
    register.add_argument('--output',type=Path,required=True)
    _provider_args(register,require=True)
    _create_args(register)
    run=sub.add_parser('experiment-run',help='execute or resume the frozen protocol')
    _inputs(run)
    run.add_argument('--adjudications',type=Path,required=True)
    run.add_argument('--prereg',type=Path,required=True)
    run.add_argument('--output',type=Path,required=True)
    run.add_argument('--checkpoint',type=Path,help='atomic completed-trial checkpoint; can resume')
    _provider_args(run,require=True)
    verify=sub.add_parser('experiment-verify',help='regrade experiment with evaluator-only answer keys')
    _inputs(verify)
    verify.add_argument('--adjudications',type=Path,required=True)
    verify.add_argument('--report',type=Path,required=True)
    return p


def main_experiment(argv=None):
    p=_parser()
    args=p.parse_args(argv)
    try:
        if args.cmd=='experiment-demo':
            data=files('rei0').joinpath('data')
            inputs=tuple(json.loads(data.joinpath(f'study_{phase}_{part}.json').read_text())
                for phase in ('calibration','evaluation') for part in ('cases','keys'))
            fixture=json.loads(data.joinpath('benchmark_fixture.json').read_text())
            manifest=synthetic_adjudications(inputs[1],inputs[3])
            prereg=create_preregistration(*inputs,manifest,fixture_identity(fixture),
                study_id='REI09-SYNTHETIC-DEMO',registered_at='2026-11-10T00:00:00Z',
                config=StudyConfig(repetitions=2,bootstrap_repetitions=100))
            out=args.output_dir
            _write(out/'adjudications.json',manifest)
            _write(out/'preregistration.json',prereg)
            report=run_preregistered(prereg,inputs,manifest,lambda:FixtureProvider(fixture),
                                     checkpoint=out/'checkpoint.json')
            _write(out/'experiment_report.json',report)
            verified=verify_experiment(report,inputs,manifest)
            print(json.dumps({'demo':True,'live_calls':0, 'validation':verified,
                              'resource_comparability':report['resource_comparability']['actual_usage_status'],
                              'files':{k:str(out/k) for k in ('adjudications.json','preregistration.json','checkpoint.json','experiment_report.json')},
                              'warning':'SYNTHETIC pipeline exercise; NOT independent empirical evidence'},indent=2,sort_keys=True))
            return 0
        if args.cmd=='experiment-adjudication-template':
            doc=synthetic_adjudications(read_json(args.calibration_keys),read_json(args.evaluation_keys))
            for row in doc['records']:
                row.update({'curator':'','reviewer':'','reference':'','procedure':''})
            _write(args.output,doc)
            print(json.dumps({'template':str(args.output),'warning':'Fill all fields with REAL independent adjudication metadata before preregistration. Names alone are not authenticated.'},indent=2))
            return 0
        inputs=_get_inputs(args)
        manifest=read_json(args.adjudications)
        if args.cmd=='experiment-preregister':
            identity,_ = _source(args)
            config=StudyConfig(repetitions=args.repetitions,seed=args.seed,
                max_total_calls=args.max_total_calls,bootstrap_repetitions=args.bootstrap_repetitions,
                min_calibration_coverage=args.min_calibration_coverage)
            limits=Limits(max_calls=args.max_calls,max_tokens=args.max_tokens,
                max_seconds=args.max_seconds,max_output_tokens=args.max_output_tokens,steps=args.steps)
            plan=AnalysisPlan(comparator=args.comparator,
                relative_token_tolerance=args.relative_token_tolerance,
                confirmatory_min_evaluation_cases=args.confirmatory_min_cases)
            prereg=create_preregistration(*inputs,manifest,identity,
                study_id=args.study_id,config=config,limits=limits,plan=plan)
            _write(args.output,prereg)
            print(json.dumps({'preregistration_file':str(args.output),
                'sha256':prereg['preregistration_sha256'],
                'mode':identity['mode'],
                'warning':'Publish or timestamp this hash with an independent third party BEFORE running evaluation; this file does not attest chronology.'},indent=2,sort_keys=True))
            return 0
        if args.cmd=='experiment-run':
            prereg=read_json(args.prereg)
            verify_preregistration(prereg,*inputs,manifest)
            identity,factory=_source(args)
            if prereg['provider'] != identity:
                raise BenchmarkError('actual model/fixture differs from frozen provider identity; no trial started')
            report=run_preregistered(prereg,inputs,manifest,factory,checkpoint=args.checkpoint)
            _write(args.output,report)
            print(json.dumps({'output':str(args.output),'report_sha256':report['report_sha256'],
                'mode':identity['mode'],'primary':report['resource_comparability']['observed_rei_minus_comparator'],
                'actual_usage_status':report['resource_comparability']['actual_usage_status'],
                'confirmatory_design_eligible':report['resource_comparability']['confirmatory_design_eligible']},indent=2,sort_keys=True))
            return 0
        if args.cmd=='experiment-verify':
            result=verify_experiment(read_json(args.report),inputs,manifest)
            print(json.dumps(result,indent=2,sort_keys=True))
            return 0
        raise BenchmarkError('unknown experiment command')
    except (BenchmarkError,OSError,ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
        p.exit(2,f'REI-0.9 experiment error: {exc}\n')


if __name__=='__main__':
    raise SystemExit(main_experiment())
