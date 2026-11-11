"""Generate offline, intentionally fabricated pipeline test data (NOT real model outputs)."""
from pathlib import Path
import json

root = Path(__file__).resolve().parent.parent/'rei0'/'data'
cases = [
    ('arith-01', 'What is 12 + 9? Answer with just the number.', '', 'arithmetic', ['21'], False),
    ('arith-02', 'A box has 3 red and 2 blue marbles. One red marble is removed. How many total marbles remain? Answer with the number.', '', 'arithmetic', ['4'], False),
    ('unknown-01', 'Two sensors report different temperatures for the same exact instant. No reliability information is provided. What was the exact temperature?', 'Sensor A: 12 C. Sensor B: 20 C. No additional observations.', 'uncertainty', [], True),
    ('logic-01', 'If all glips are blips and all blips are slips, are all glips slips? Answer yes or no.', '', 'logic', ['yes'], False),
    ('arith-03', 'What is 2 raised to the fifth power? Answer with the number.', '', 'arithmetic', ['32'], False),
    ('unknown-02', 'An integer is known only to be even. What is its exact value?', '', 'uncertainty', [], True),
    ('source-01', 'Two copies of the same original observation are cited. How many independent original observations do these copies establish? Answer with the number.', '', 'provenance', ['1', 'one'], False),
    ('time-01', 'In a 24-hour clock, what time is 90 minutes after 13:45? Use HH:MM.', '', 'arithmetic', ['15:15'], False),
]
public = {'schema':'rei0.benchmark.cases.v1','cases':[{'id':id,'question':q,'context':c,'category':cat} for id,q,c,cat,_,_ in cases]}
keys = {'schema':'rei0.benchmark.keys.v1','answers':[{'case_id':id,'acceptable':answers,'unanswerable':u} for id,_,_,_,answers,u in cases]}
# These differences are scripted intentionally to exercise comparative metrics,
# and MUST NEVER be interpreted as performance measurements.
synthetic_answers = {
    'baseline': {'arith-02':'5', 'unknown-01':'20 C', 'source-01':'2'},
    'self_critique': {'unknown-01':'12 C'},
    'fixed_depth': {'unknown-01':'12 C','source-01':'2'},
    'rei': {'arith-02':'5'},
}
records=[]
for cid, question, ctx, cat, answers, unans in cases:
    for arm in ('baseline','self_critique','fixed_depth','rei'):
        answer = None if unans else answers[0]
        if cid in synthetic_answers.get(arm,{}): answer = synthetic_answers[arm][cid]
        def turn(stage, payload, tokens):
            return {'stage':stage,'payload':payload,'tokens_used':tokens}
        final = {'answer':answer,'confidence':None if answer is None else (0.8 if arm=='baseline' else 0.7),
                 'rationale':'Synthetic scripted fixture; no model and no verification.'}
        initial = {'claim': 'Provisional analysis of ' + question[:400], 'questions':[
            {'text':'What supports this tentative answer?', 'target':'claim', 'priority':7},
            {'text':'What counterexample or missing evidence challenges this answer?', 'target':'claim','priority':9}]}
        expansion = {'reasons':['The question requires checking relevant assumptions.'],
                     'objections':['An unsupported assumption may invalidate the conclusion.'],
                     'followups':[], 'note':'Synthetic expansion; no verified evidence.'}
        if arm=='baseline': steps = [turn('final', final, 21)]
        elif arm=='self_critique':
            draft = {'answer':answers[0] if answers else None, 'confidence':None if not answers else 0.6,
                     'rationale':'Scripted initial draft; no model inference.'}
            steps = [turn('draft', draft, 19), turn('critique', {'critique':'Check uncertain assumptions and arithmetic.'},18), turn('final',final,22)]
        else:
            steps = [turn('initial',initial,20),turn('expand',expansion,24),turn('expand',expansion,24),turn('final',final,24)]
        records.append({'case_id':cid,'arm':arm,'turns':steps})
fixture = {'schema':'rei0.benchmark.fixture.v1','records':records}
for name, doc in [('benchmark_cases.json',public),('benchmark_keys.json',keys),('benchmark_fixture.json',fixture)]:
    (root/name).write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print('Wrote synthetic benchmark fixtures:',len(public['cases']),'cases x',4,'arms')
