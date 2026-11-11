"""Case-clustered analysis. Analysis code does not run any external models."""
from __future__ import annotations
import argparse, json, random, math, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'REI-1.0'))
from rei0.benchmark import verify_report, load_study, grade, ARMS


def analyze(reports:list[dict],cases:dict,keys:dict, *,bootstrap_seed=1299,draws=3000):
    if not reports:raise ValueError('no reports')
    cases_parsed, parsed_keys=load_study(cases,keys)
    ids=sorted(parsed_keys)
    for report in reports:
        verify_report(report,cases,keys)
        if report['mode']!='live_external_model':
            raise ValueError('Synthetic reports cannot establish comparative model accuracy')
    provider=set(r['provider_fingerprint'] for r in reports)
    if len(provider)!=1:raise ValueError('Different provider fingerprints across trials')
    trials=[]
    for r in reports:
        row={(o['case_id'],o['arm']):o for o in r['outcomes']}
        trials.append(row)
    per_case={cid:{arm:[int(grade(row[(cid,arm)],parsed_keys[cid])['correct']) for row in trials]
                    for arm in ARMS} for cid in ids}
    m=len(trials)
    success={arm:sum(sum(per_case[c][arm]) for c in ids)/(len(ids)*m) for arm in ARMS}
    calls={arm:sum(row[(cid,arm)]['model_calls'] for row in trials for cid in ids) for arm in ARMS}
    tokens={arm:sum(row[(cid,arm)]['reported_tokens'] for row in trials for cid in ids) for arm in ARMS}
    def delta(cid,other):return (sum(per_case[cid]['rei'])-sum(per_case[cid][other]))/m
    rng=random.Random(bootstrap_seed)
    comparisons={}
    for other in ('self_critique','baseline','fixed_depth'):
        diffs=[delta(cid,other) for cid in ids]
        sims=sorted(sum(rng.choice(diffs) for _ in ids)/len(ids) for _ in range(draws))
        other_tokens=tokens[other]
        token_ratio=tokens['rei']/other_tokens if other_tokens else None
        call_ratio=calls['rei']/calls[other] if calls[other] else None
        comparisons['rei_minus_'+other]={
            'mean_success_difference':sum(diffs)/len(diffs),
            'cluster_bootstrap_95_interval':[sims[int(.025*draws)],sims[int(.975*draws)]],
            'relative_tokens_rei_over_other':token_ratio,
            'relative_calls_rei_over_other':call_ratio,
            'threshold_screening_only':bool(sims[int(.025*draws)]>0 and sum(diffs)/len(diffs)>=.05
                    and token_ratio is not None and .9<=token_ratio<=1.1),
        }
    return {'status':'LIVE_MODEL_DATA_ANALYZED_NOT_INDEPENDENTLY_ATTESTED',
            'case_count':len(ids),'trial_repetitions':m,'total_case_arm_trials':len(ids)*m*len(ARMS),
            'success_rates':success,'reported_tokens':tokens,'model_calls':calls,
            'comparisons':comparisons,'primary_comparison':'rei_minus_self_critique',
            'warnings':['Token parity is only one resource measure; quality-per-cost still needs scrutiny.',
                        'Confidence intervals account for repeated trials sharing a case, not necessarily model drift.',
                        'Provider identity and experimental timing require independent attestation.',
                        'Even passing screening thresholds is not confirmatory evidence without externally preregistered validation.']}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('reports',nargs='+',type=Path)
    p.add_argument('--phase',choices=('calibration','evaluation'),required=True)
    p.add_argument('--output',type=Path,default=ROOT/'results'/'analysis.json')
    a=p.parse_args()
    c=json.loads((ROOT/'challenge'/f'{a.phase}_cases.json').read_text())
    k=json.loads((ROOT/'challenge'/f'{a.phase}_keys_PRIVATE.json').read_text())
    reports=[json.loads(f.read_text()) for f in a.reports]
    output=analyze(reports,c,k)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(output,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':output['status'],'primary':output['comparisons']['rei_minus_self_critique']},indent=2))

if __name__=='__main__':main()
