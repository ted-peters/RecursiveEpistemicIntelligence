"""Opt-in REI Challenge 5 four-arm runner. Never calls a model without consent and credentials."""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
REI=HERE.parent/'REI-1.0'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_manifest():
    manifest=json.loads((HERE/'FROZEN_PROTOCOL.json').read_text())
    for name,expected in manifest['locked_file_hashes'].items():
        path=HERE.parent/name
        if sha(path)!=expected: raise RuntimeError('Frozen file differs: '+name)
    return manifest

def main():
    ap=argparse.ArgumentParser(description='Controlled comparison: baseline, self critique, fixed depth, REI')
    ap.add_argument('--phase',choices=['calibration','evaluation'],default='calibration')
    ap.add_argument('--model',required=True)
    ap.add_argument('--repetitions',type=int,default=1)
    ap.add_argument('--endpoint',default='https://api.openai.com/v1/chat/completions')
    ap.add_argument('--acknowledge-costs',action='store_true')
    ap.add_argument('--output-dir',type=Path,default=HERE.parent/'results')
    args=ap.parse_args()
    if not args.acknowledge_costs:ap.error('Explicit --acknowledge-costs is required for ANY external model call')
    if not os.getenv('REI_LLM_API_KEY'):ap.error('REI_LLM_API_KEY missing; no provider calls attempted')
    if args.repetitions<1 or args.repetitions>10:ap.error('repetitions must be 1..10')
    manifest=verify_manifest()
    public=HERE/f'{args.phase}_cases.json'; keys=HERE/f'{args.phase}_keys_PRIVATE.json'
    args.output_dir.mkdir(exist_ok=True,parents=True)
    env=dict(os.environ)
    env['PYTHONPATH']=str(REI)+(os.pathsep+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    for r in range(args.repetitions):
        target=args.output_dir/f'{args.phase}_trial_{r+1:02}.json'
        if target.exists():raise SystemExit('Refusing to overwrite completed result: '+str(target))
        command=[sys.executable,'-m','rei0','benchmark-run','--cases',str(public),'--keys',str(keys),
                 '--live','--model',args.model,'--endpoint',args.endpoint,'--max-calls','4',
                 '--max-tokens','4000','--max-output-tokens','384','--max-seconds','30',
                 '--steps','2','--seed',str(manifest['random_seed']+r),'--output',str(target)]
        subprocess.run(command,check=True,env=env,cwd=REI)
        subprocess.run([sys.executable,'-m','rei0','benchmark-verify','--report',str(target),
                        '--cases',str(public),'--keys',str(keys)],check=True,env=env,cwd=REI)
    print('Model-run records written. Analyze them independently using analyze.py.')

if __name__=='__main__':main()
