"""REI-1.0 integrated research workspace CLI. No live calls without explicit consent."""
from __future__ import annotations

import argparse
from importlib.resources import files
import json
import os
from pathlib import Path
import tempfile

from .benchmark import FixtureProvider, LiveProvider, BenchmarkError
from .experiment09 import (create_preregistration, fixture_identity,
                           run_preregistered, synthetic_adjudications,
                           verify_preregistration)
from .graph import EpistemicGraph, GraphError
from .models import Node, NodeKind, Provenance, SourceKind
from .platform import PlatformError, ResearchWorkspace, read_document
from .platform_web import serve
from .revision import RevisionError
from .study import StudyConfig

PLATFORM_COMMANDS = frozenset({
    'platform-init','platform-import','platform-list','platform-verify',
    'platform-report','platform-serve','platform-demo','platform-run'
})


def _write_json(path: str | Path, data: dict) -> None:
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.rei-platform-', suffix='.tmp', dir=path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(data,stream,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp): os.unlink(temp)


def _dataset_args(parser):
    for name in ('calibration-cases','calibration-keys','evaluation-cases','evaluation-keys','adjudications'):
        parser.add_argument('--'+name,type=Path)


def _datasets(args):
    names=('calibration_cases','calibration_keys','evaluation_cases','evaluation_keys','adjudications')
    if not all(getattr(args,name,None) for name in names):
        raise PlatformError('experiment requires --calibration-cases, --calibration-keys, --evaluation-cases, --evaluation-keys, --adjudications')
    docs=[read_document(getattr(args,name)) for name in names]
    return tuple(docs[:4]),docs[4]


def _parser():
    p=argparse.ArgumentParser(prog='rei0',description='REI-1.0 integrated local research platform')
    sub=p.add_subparsers(dest='command',required=True)
    init=sub.add_parser('platform-init',help='initialize a new write-once research workspace')
    init.add_argument('--workspace',type=Path,required=True)
    imp=sub.add_parser('platform-import',help='validate then import a research artifact')
    imp.add_argument('--workspace',type=Path,required=True)
    imp.add_argument('--kind',required=True,choices=('experiment','graph','revision'))
    imp.add_argument('--file',type=Path,required=True)
    imp.add_argument('--expected-head',help='independently stored graph/revision audit head')
    _dataset_args(imp)
    for cmd in ('platform-list','platform-verify','platform-report','platform-serve'):
        subp=sub.add_parser(cmd)
        subp.add_argument('--workspace',type=Path,required=True)
        if cmd == 'platform-verify':
            subp.add_argument('--expected-head',help='independently stored workspace audit head')
        if cmd == 'platform-report':
            subp.add_argument('--output',type=Path,help='save redacted summary JSON')
        if cmd == 'platform-serve':
            subp.add_argument('--port',type=int,default=8787)
    demo=sub.add_parser('platform-demo',help='offline integrated experimental/graph workspace demo')
    demo.add_argument('--workspace',type=Path,required=True)
    run=sub.add_parser('platform-run',help='run frozen 0.9 experiment then import independently regraded result')
    run.add_argument('--workspace',type=Path,required=True)
    run.add_argument('--prereg',type=Path,required=True)
    run.add_argument('--report',type=Path,required=True)
    run.add_argument('--checkpoint',type=Path)
    _dataset_args(run)
    mode=run.add_mutually_exclusive_group(required=True)
    mode.add_argument('--fixture',type=Path,help='synthetic scripted integration run')
    mode.add_argument('--live',action='store_true',help='permit real provider calls and potential charges')
    run.add_argument('--model',help='provider model ID required for live')
    run.add_argument('--endpoint',default='https://api.openai.com/v1/chat/completions')
    run.add_argument('--acknowledge-live-costs',action='store_true')
    return p


def _demo(ws: ResearchWorkspace) -> dict:
    data=files('rei0').joinpath('data')
    inputs=tuple(json.loads(data.joinpath(f'study_{phase}_{part}.json').read_text())
                 for phase in ('calibration','evaluation') for part in ('cases','keys'))
    fixture=json.loads(data.joinpath('benchmark_fixture.json').read_text())
    adjudications=synthetic_adjudications(inputs[1],inputs[3])
    prereg=create_preregistration(*inputs, adjudications, fixture_identity(fixture),
          study_id='REI10-SYNTHETIC-WORKSPACE', registered_at='2026-11-10T00:00:00Z',
          config=StudyConfig(repetitions=1,bootstrap_repetitions=100))
    report=run_preregistered(prereg,inputs,adjudications,lambda:FixtureProvider(fixture))
    experiment=ws.ingest('experiment',report,inputs=inputs,adjudications=adjudications)
    at='2026-11-10T00:00:00Z'
    g=EpistemicGraph(method_version='rei-1.0-demo')
    prov=Provenance('synthetic-demo',SourceKind.SYSTEM,'demo','synthetic:not-factual',at)
    g.add_node(Node('initial-claim',NodeKind.CLAIM,
                    'A synthetic question is open to further justification.',prov,at))
    graph=ws.ingest('graph',g.to_dict())
    return {'demo':True,'live_calls':0,'synthetic_only':True,
            'experiment':experiment['id'],'graph':graph['id'], 'workspace':str(ws.path),
            'integrity':ws.verify(), 'warning':'Synthetic integration test. No live AI performance has been measured.'}


def main_platform(argv=None) -> int:
    parser=_parser()
    a=parser.parse_args(argv)
    try:
        if a.command=='platform-init':
            ws=ResearchWorkspace.initialize(a.workspace)
            result={'created':str(ws.path),'integrity':ws.verify()}
        elif a.command=='platform-demo':
            if not a.workspace.exists():
                ResearchWorkspace.initialize(a.workspace)
            result=_demo(ResearchWorkspace(a.workspace))
        elif a.command=='platform-import':
            inputs, adjudications = _datasets(a) if a.kind=='experiment' else (None,None)
            result=ResearchWorkspace(a.workspace).ingest(
                a.kind,read_document(a.file),inputs=inputs,adjudications=adjudications,
                expected_head=a.expected_head)
        elif a.command=='platform-verify':
            result=ResearchWorkspace(a.workspace).verify(expected_head=a.expected_head)
        elif a.command=='platform-list':
            result={'artifacts':ResearchWorkspace(a.workspace).entries()}
        elif a.command=='platform-report':
            result=ResearchWorkspace(a.workspace).overview()
            if a.output:
                _write_json(a.output,result)
        elif a.command=='platform-serve':
            server=serve(a.workspace,a.port)
            print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}/',
                              'read_only':True,'bind':'127.0.0.1','workspace':str(a.workspace)}),flush=True)
            try: server.serve_forever()
            finally: server.server_close()
            return 0
        elif a.command=='platform-run':
            inputs,adjudications=_datasets(a)
            prereg=read_document(a.prereg)
            verify_preregistration(prereg,*inputs,adjudications)
            if a.live:
                if not a.model or not a.acknowledge_live_costs:
                    raise PlatformError('--live requires --model and --acknowledge-live-costs')
                provider=LiveProvider(a.model,endpoint=a.endpoint)
                factory=lambda:LiveProvider(a.model,endpoint=a.endpoint)
            else:
                if a.model or a.acknowledge_live_costs:
                    raise PlatformError('--model/--acknowledge-live-costs require --live')
                fixture=read_document(a.fixture)
                provider=FixtureProvider(fixture)
                factory=lambda:FixtureProvider(fixture)
            if (prereg['provider']['mode'] != provider.kind or
                prereg['provider']['fingerprint'] != provider.fingerprint):
                raise PlatformError('provider differs from frozen preregistration')
            if prereg['provider']['mode'] == 'live_external_model' and (
                prereg['provider']['endpoint'] != provider.endpoint or
                prereg['provider']['model'] != provider.model):
                raise PlatformError('live provider identity differs from frozen preregistration')
            report=run_preregistered(prereg,inputs,adjudications,factory,checkpoint=a.checkpoint)
            saved=ResearchWorkspace(a.workspace).ingest('experiment',report,inputs=inputs,adjudications=adjudications)
            _write_json(a.report,report)
            result={'artifact_id':saved['id'],'report':str(a.report),
                    'provider_mode':provider.kind, 'summary':saved['summary'],
                    'warning':'Provider responses and reviewer identities are not remotely attested.'}
        else:
            raise PlatformError('unsupported command')
    except (PlatformError,BenchmarkError,GraphError,RevisionError,OSError,ValueError,
            TypeError,KeyError,json.JSONDecodeError) as exc:
        parser.exit(2,f'REI-1.0 platform error: {exc}\n')
    print(json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False))
    return 0

if __name__=='__main__':
    raise SystemExit(main_platform())
