"""Reproducible REI Challenge 5 exploratory tasks.

Keys are objective for the *synthetic worlds described in each prompt*.
They do not establish real-world truth or constitute independent human review.
"""
from __future__ import annotations
import json, random
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SEED=20261111
STATES=('NEITHER','SUPPORT_ONLY','ATTACK_ONLY','BOTH')

def pack(cases, keys):
    return ({'schema':'rei0.benchmark.cases.v1','cases':cases},
            {'schema':'rei0.benchmark.keys.v1','answers':keys})

def _truth_horn(facts, edges, target):
    universe='ABCD'
    # Truth-table semantics, not proof by constructing a path.
    valid=[]
    for bits in range(16):
        values={v:bool(bits & (1<<i)) for i,v in enumerate(universe)}
        if all(values[f] for f in facts) and all(not values[a] or values[b] for a,b in edges):
            valid.append(values)
    assert valid
    return all(row[target] for row in valid)

def _evidence_label(events):
    # Ledger reduction: last document event decides whether the doc is live.
    accepted={}
    for event in events:
        if event[0]=='ACCEPT': accepted[event[1]]=(event[2],event[3])
        elif event[0]=='REVOKE': accepted.pop(event[1],None)
        elif event[0]=='PENDING': pass
        else: raise ValueError(event)
    supporting={origin for origin, side in accepted.values() if side=='SUPPORT'}
    attacking={origin for origin, side in accepted.values() if side=='ATTACK'}
    s,a=bool(supporting),bool(attacking)
    return 'BOTH' if s and a else 'SUPPORT_ONLY' if s else 'ATTACK_ONLY' if a else 'NEITHER'

def _dependency_label(s, direct):
    pos=(s[0]=='SUPPORT_ONLY' and s[1]=='SUPPORT_ONLY') or direct[0]
    neg=(s[2]=='SUPPORT_ONLY' and s[3]=='SUPPORT_ONLY') or direct[1]
    return 'BOTH' if pos and neg else 'SUPPORT_ONLY' if pos else 'ATTACK_ONLY' if neg else 'NEITHER'

def generate(seed=SEED, prefix='eval', n_each=12):
    """n_each must be a multiple of four; 5 categories x n_each tasks."""
    if n_each%4: raise ValueError('need n_each divisible by four')
    rng=random.Random(seed)
    cases=[]; keys=[]
    def add(cat, question, context, answer=None):
        cid=f'C5-{prefix}-{cat}-{sum(c["category"]==cat for c in cases)+1:02}'
        cases.append({'id':cid,'category':cat,'question':question,'context':context})
        keys.append({'case_id':cid,'acceptable':[] if answer is None else [str(answer)],'unanswerable':answer is None})
    # Exact arithmetic: significant intermediate terms and signs, but no floating ambiguity.
    for i in range(n_each):
        a,b,c,d,e,f=(rng.randint(17,91),rng.randint(4,19),rng.randint(8,53),
                     rng.randint(3,26),rng.randint(2,9),rng.randint(1,37))
        sign=(-1 if i%3==0 else 1)
        result=(a*b-c+sign*d)*e-f
        add('arithmetic',f'Compute (({a} × {b} − {c} {"−" if sign<0 else "+"} {d}) × {e}) − {f}. Return the integer only.',
            'All arithmetic operations are over integers; observe the parentheses.',result)
    # Formal entailment: labels determined by exhaustive four-variable truth-table enumeration.
    counts={'ENTAILED':0,'NOT_ENTAILED':0}; attempts=0
    while sum(counts.values())<n_each:
        attempts+=1
        if attempts>20000: raise RuntimeError('logic balancing failed')
        possible=[(a,b) for a in 'ABCD' for b in 'ABCD' if a!=b]
        edges=rng.sample(possible,rng.randint(2,4))
        facts=rng.sample(list('ABCD'),rng.randint(1,2))
        target=rng.choice(list('ABCD'))
        entailed=_truth_horn(facts,edges,target)
        label='ENTAILED' if entailed else 'NOT_ENTAILED'
        if counts[label]>=n_each//2:continue
        counts[label]+=1
        factline=', '.join(f'{f} is TRUE' for f in facts)
        rules='; '.join(f'if {a} is TRUE then {b} is TRUE' for a,b in edges)
        add('logic',f'Is {target} logically entailed by the facts and rules? Reply ENTAILED or NOT_ENTAILED.',
            f'Facts: {factline}. Rules: {rules}. No converse rules are assumed. Other propositions may be true or false; use all models consistent with the facts and rules.',label)
    # Four-state evidence semantics: accepted, pending, repeated origin, and revoked documents.
    target_states=list(STATES)*(n_each//4)
    rng.shuffle(target_states)
    for target in target_states:
        positive=target in ('SUPPORT_ONLY','BOTH');negative=target in ('ATTACK_ONLY','BOTH')
        events=[]; docnum=0
        def submit(origin,side,kind='ACCEPT'):
            nonlocal docnum
            docnum+=1
            events.append((kind,f'D{docnum}',origin,side))
            return f'D{docnum}'
        # Decoy reports always carry PENDING reviews and never count.
        submit('S-PENDING','SUPPORT','PENDING')
        # Include apparently persuasive but subsequently revoked evidence.
        d=submit('S-REVOKED','SUPPORT');events.append(('REVOKE',d))
        if positive:
            origin=f'S-POS-{rng.randint(1,100)}'
            submit(origin,'SUPPORT')
            if rng.choice([True,False]):submit(origin,'SUPPORT')  # duplicated source, not extra study
        if negative:
            origin=f'S-NEG-{rng.randint(1,100)}'
            submit(origin,'ATTACK')
            if rng.choice([True,False]):submit(origin,'ATTACK')
        submit('S-PENDING2','ATTACK','PENDING')
        # PENDING and REVOKE appear in temporal order; accepts are not silently reactivated.
        lines=[]
        for event in events:
            if event[0]=='REVOKE':lines.append(f'REVOKE document {event[1]}')
            else:lines.append(f'{event[0]} document {event[1]}, origin {event[2]}, side {event[3]}')
        assert _evidence_label(events)==target
        add('evidence', 'What is the final four-state information status of claim P? Reply only NEITHER, SUPPORT_ONLY, ATTACK_ONLY, or BOTH.',
            'Each ACCEPT document counts only while not REVOKED. PENDING does not count. Documents sharing an origin are not independent studies. Any valid positive and negative evidence yields BOTH, regardless of the number of copies. Interpret records in chronological order:\n'+'\n'.join(lines),target)
    # Defeasible inference: only unopposed supporting premises activate the explicit rule.
    desired=list(STATES)*(n_each//4)
    rng.shuffle(desired)
    for want in desired:
        for attempt in range(20000):
            statuses=[rng.choice(STATES) for _ in range(4)]
            direct=[rng.choice((False,True)) for _ in range(2)]
            if _dependency_label(statuses,direct)==want:break
        else:raise RuntimeError('dependency balancing failed')
        add('dependency','What is Q\'s resulting information status after evaluating only the listed rules? Reply NEITHER, SUPPORT_ONLY, ATTACK_ONLY, or BOTH.',
            f'Premises: P1={statuses[0]}, P2={statuses[1]}, P3={statuses[2]}, P4={statuses[3]}. '
            'Authorized positive rule: if P1 and P2 are both SUPPORT_ONLY, derive SUPPORT for Q. '
            'Authorized negative rule: if P3 and P4 are both SUPPORT_ONLY, derive ATTACK for Q. '
            f'Direct recorded evidence for Q: {"SUPPORT" if direct[0] else "no support"}; {"ATTACK" if direct[1] else "no attack"}. '
            'A disputed BOTH premise blocks its rule. Combine direct and derived evidence without explosion.',want)
    # Controlled abstention cases: oracle verifies at least two distinct solutions.
    for i in range(n_each):
        if i%2==0:
            total=rng.randint(15,72)
            context=f'Two integers x and y are positive, x + y = {total}. No other equations or measurements are available.'
            question='What is the exact value of x? If not uniquely determined, return a null answer.'
        else:
            offset=rng.randint(2,20)
            context=f'Sensors X and Y are linked by X = Y + {offset}. No numeric value of either X or Y is recorded.'
            question='What is the exact numeric value of Y? If not uniquely determined, return a null answer.'
        add('insufficient_information',question,context,None)
    assert len(cases)==5*n_each
    ids=[c['id'] for c in cases]
    assert len(set(ids))==len(ids)
    return pack(cases,keys)

def write_files():
    outputs={'calibration':generate(SEED+10,'cal',4),'evaluation':generate(SEED+99,'eval',12)}
    for kind,(cases,keys) in outputs.items():
        p=ROOT/f'{kind}_cases.json'
        q=ROOT/f'{kind}_keys_PRIVATE.json'
        p.write_text(json.dumps(cases,indent=2,ensure_ascii=False,sort_keys=True)+'\n')
        q.write_text(json.dumps(keys,indent=2,ensure_ascii=False,sort_keys=True)+'\n')
    return outputs

if __name__=='__main__':
    outputs=write_files()
    print(', '.join(f'{k}: {len(v[0]["cases"])}' for k,v in outputs.items()))
