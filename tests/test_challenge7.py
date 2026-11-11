"""Checks REI-vs-strong-ledger dynamic oracle and benchmark study custody."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research.challenge7.build_cases import generate, ledger_trace, graph_trace
from rei0.benchmark import load_study

HOME=ROOT/"research"/"challenge7"


class Challenge7Tests(unittest.TestCase):
    def setUp(self):
        self.episodes=json.loads((HOME/"episodes.json").read_text())["episodes"]

    def test_deterministic_rebuild_matches_checked_in_datasets(self):
        generated=generate()
        for name,expect in zip(("cases.json","keys.json","oracle_traces.json"),generated):
            self.assertEqual(json.loads((HOME/name).read_text()),expect)

    def test_each_incremental_state_agrees_with_strong_conventional_ledger(self):
        checkpoints=0
        for ep in self.episodes:
            ledger=ledger_trace(ep["events"])
            rei=graph_trace(ep["events"])
            self.assertEqual(rei,ledger,ep["id"])
            checkpoints+=len(rei)
        self.assertEqual(checkpoints,24)

    def test_revisions_and_duplicate_sources_not_counted_as_independent(self):
        p={e["id"]:e for e in self.episodes}
        self.assertEqual([x["state"] for x in ledger_trace(p["c7-01-duplicate-then-revoke"]["events"])],
                         ["SUPPORT_ONLY","SUPPORT_ONLY","BOTH","SUPPORT_ONLY"])
        self.assertEqual([x["state"] for x in ledger_trace(p["c7-05-revoke-one-duplicate"]["events"])],
                         ["SUPPORT_ONLY","SUPPORT_ONLY","SUPPORT_ONLY"])

    def test_four_information_states_represented_and_keys_are_consistent(self):
        cases=json.loads((HOME/"cases.json").read_text())
        keys=json.loads((HOME/"keys.json").read_text())
        parsed,answers=load_study(cases,keys)
        self.assertEqual(len(parsed),6)
        self.assertEqual(len(answers),6)
        self.assertEqual({a.acceptable[0] for a in answers.values()},
                         {"NEITHER","SUPPORT_ONLY","ATTACK_ONLY","BOTH"})
        for c in parsed:
            self.assertNotIn("ground_truth",c.context)
            self.assertNotIn("expected_answer",c.context)
            self.assertGreaterEqual(c.context.count("\n"),3)

    def test_invalid_event_operations_fail_closed(self):
        base=[{"op":"ACCEPT","doc":"D1","origin":"S1","side":"SUPPORT"}]
        with self.assertRaises(ValueError):
            ledger_trace(base+[{'op':'APPROVE','doc':'D1'}])
        with self.assertRaises(ValueError):
            ledger_trace(base+[{'op':'REVOKE','doc':'D2'}])
        with self.assertRaises(ValueError):
            ledger_trace(base+base)


if __name__=="__main__":
    unittest.main()