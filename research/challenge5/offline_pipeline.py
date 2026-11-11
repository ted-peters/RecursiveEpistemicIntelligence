"""Exercises all 60 cases x four arms WITHOUT running a language model.

The null responder intentionally abstains on every question. This is a
software integration check, not an AI accuracy comparison.
"""
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'REI-1.0'))
from rei0.benchmark import read_json,run_benchmark,verify_report,Limits
from rei0.inquiry import ModelTurn

class NullProvider:
    kind='synthetic_all_abstain_integration_only'
    fingerprint='REI-C5-OFFLINE-NULL-ENGINE-NOT-A-MODEL'
    def respond(self,*,case_id,arm,stage,context,max_output_tokens,timeout):
        if stage in ('draft','final'):
            payload={'answer':None,'confidence':None,'rationale':'SYNTHETIC all-abstain test, not a model prediction.'}
        elif stage=='critique':payload={'critique':'Synthetic testing turn.'}
        elif stage=='initial':payload={'claim':'A provisional claim (synthetic).',
                                       'questions':[{'text':'What would justify this claim?','priority':5}]}
        elif stage=='expand':payload={'reasons':['A synthetic placeholder reason.'],
                                      'objections':['A synthetic placeholder objection.'],
                                      'followups':[],'note':'Not evidence.'}
        else:raise ValueError(stage)
        return ModelTurn(payload, 9)

def main():
    c=read_json(ROOT/'challenge/evaluation_cases.json')
    k=read_json(ROOT/'challenge/evaluation_keys_PRIVATE.json')
    report=run_benchmark(c,k,NullProvider(),limits=Limits(max_calls=4,max_tokens=4000,max_seconds=30,steps=2),seed=20261111)
    verification=verify_report(report,c,k)
    assert verification['valid']
    assert len(report['outcomes'])==240
    assert all(x['error'] is None for x in report['outcomes']),str([x for x in report['outcomes'] if x['error']][:3])
    assert all(x['answer'] is None for x in report['outcomes'])
    assert all(x['reasoning'].get('evidence_state')=='NEITHER' for x in report['outcomes'] if x['arm']=='rei')
    path=ROOT/'results/SYNTHETIC_ONLY_pipeline.json'
    path.write_text(json.dumps({'warning':'INTEGRATION TEST ONLY. DO NOT INTERPRET 20% ABSTENTION SUCCESS AS MODEL ACCURACY.',
                                 'schema':'rei-challenge5.offline-pipeline.v1',
                                 'verification':verification,'cases':60,'arms':4,'model_calls_to_external_services':0,
                                 'verified_evidence_awarded':0,'scoring_mode':report['mode']},indent=2)+'\n')
    print('PASS: 240 synthetic trial records, complete four-arm benchmark and independent regrading; zero external model calls')

if __name__=='__main__':main()
