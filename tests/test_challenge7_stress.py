"""Seeded stress parity test: original REI graph versus provenance-aware ledger."""
import hashlib
import json
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research.challenge7.build_cases import ledger_trace,graph_trace


class SeededDynamicRevisionStressTests(unittest.TestCase):
    def test_400_random_histories_4053_checkpoints_match(self):
        rng=random.Random(7182026)
        history_hashes=[]
        total=0
        counts={x:0 for x in ('NEITHER','SUPPORT_ONLY','ATTACK_ONLY','BOTH')}
        for i in range(400):
            events=[]
            state={}
            j=1
            for _ in range(rng.randint(5,16)):
                can_approve=[d for d,s in state.items() if s=='PENDING']
                can_revoke=[d for d,s in state.items() if s=='VERIFIED']
                choice=rng.random()
                if choice<0.25 and can_approve:
                    d=rng.choice(can_approve)
                    events.append({'op':'APPROVE','doc':d})
                    state[d]='VERIFIED'
                elif choice<0.58 and can_revoke:
                    d=rng.choice(can_revoke)
                    events.append({'op':'REVOKE','doc':d})
                    state[d]='REVOKED'
                else:
                    d=f'D{j}'
                    j+=1
                    op=rng.choice(['ACCEPT','PENDING'])
                    events.append({'op':op,'doc':d,'origin':f'S{rng.randint(1,5)}',
                                   'side':rng.choice(['SUPPORT','ATTACK'])})
                    state[d]='VERIFIED' if op=='ACCEPT' else 'PENDING'
            convention=ledger_trace(events)
            rei=graph_trace(events)
            self.assertEqual(rei,convention,f'ledger mismatch at history {i}')
            total+=len(rei)
            for record in rei: counts[record['state']]+=1
            history_hashes.append(hashlib.sha256(json.dumps(events,sort_keys=True).encode()).hexdigest())
        self.assertEqual(total,4053)
        self.assertEqual(counts,{'NEITHER':1274,'SUPPORT_ONLY':971,'ATTACK_ONLY':947,'BOTH':861})
        self.assertEqual(hashlib.sha256(''.join(history_hashes).encode()).hexdigest(),
            'bc61c8e50b3d4eb7601ee159eafc91aa74344a5edf8e1f15fd6e5061c94521f5')


if __name__=='__main__': unittest.main()