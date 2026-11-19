"""Exercise the paired-priority probe through the standalone runtime."""
import json
import unittest

from rei0.local_ai import IDEOLOGICAL_GUIDANCE, StandaloneREI
from research.standalone_eval.paired_values import CASES, prompt, run_probe, run_staged_pair, summarize
from test_local_ai_standalone import FakeProvider


class PairedValuesTests(unittest.TestCase):
    def test_each_pair_changes_only_the_priority(self):
        for case in CASES:
            first = prompt(case, 0).replace(case.priorities[0], "<priority>")
            second = prompt(case, 1).replace(case.priorities[1], "<priority>")
            self.assertNotEqual(case.priorities[0], case.priorities[1])
            self.assertEqual(first, second)

    def test_distinguishes_priority_changes_evidence_drift_and_abstention(self):
        valid = {
            prompt(case, side): json.dumps({
                "evidence": case.expected_evidence,
                "recommendation": recommendation,
            })
            for case in CASES
            for side, recommendation in enumerate(case.expected_recommendations)
        }
        replies = valid.copy()

        class ScriptedValuesProvider(FakeProvider):
            def complete(self, **kwargs):
                _, tokens = super().complete(**kwargs)
                question = json.loads(kwargs["user"])["conversation"][-1]["content"]
                return replies[question], tokens

        agent = StandaloneREI(provider_factory=ScriptedValuesProvider, model="fixture")
        results = run_probe(agent)
        self.assertEqual(len(results), 6)
        self.assertTrue(all(pair["passed"] for pair in results))

        replies[prompt(CASES[0], 1)] = '{"evidence":"supported","recommendation":"B"}'
        replies[prompt(CASES[1], 0)] = '{"evidence":"unknown","recommendation":"B"}'
        replies[prompt(CASES[1], 1)] = '{"evidence":"unknown","recommendation":"A"}'
        replies[prompt(CASES[2], 1)] = '{"evidence":"contradicted","recommendation":"A"}'
        for pair in run_probe(agent):
            with self.subTest(case=pair["case"], mode=pair["mode"]):
                self.assertFalse(pair["passed"])
                self.assertEqual(pair["same_evidence"], pair["case"] != "downtown-access")

        replies[prompt(CASES[2], 1)] = "I need more information."
        results = run_probe(agent)
        for pair in results:
            if pair["case"] == "bus-service":
                self.assertIsNone(pair["sides"][1]["parsed"])
                self.assertFalse(pair["passed"])

    def test_guidance_comparison_keeps_cases_and_grading_matched(self):
        replies = {}
        for case in CASES:
            for side, expected in enumerate(case.expected_recommendations):
                query = prompt(case, side)
                replies[query] = json.dumps({
                    "evidence": case.expected_evidence, "recommendation": expected,
                })

        class GuidanceFixture(FakeProvider):
            def complete(self, **kwargs):
                _, tokens = super().complete(**kwargs)
                query = json.loads(kwargs["user"])["conversation"][-1]["content"]
                if kwargs["system"].endswith(IDEOLOGICAL_GUIDANCE):
                    return replies[query], tokens
                return '{"evidence":"unknown","recommendation":"A"}', tokens

        results = run_probe(
            StandaloneREI(provider_factory=GuidanceFixture, model="fixture"),
            compare_guidance=True,
        )
        self.assertEqual(len(results), 12)
        for first, second in zip(results[::2], results[1::2]):
            self.assertEqual((first["case"], first["mode"]), (second["case"], second["mode"]))
            self.assertNotEqual(first["guidance"], second["guidance"])
        for mode, treatment in summarize(results).items():
            self.assertEqual({pair["guidance"] for pair in results[::2] if pair["mode"] == mode},
                             {"baseline", "guided"})
            with self.subTest(mode=mode):
                self.assertEqual(treatment["baseline"]["pairs_passed"], 0)
                self.assertEqual(treatment["guided"]["pairs_passed"], 3)
                self.assertEqual(treatment["guided"]["correct_evidence_answers"], 6)
                self.assertEqual(treatment["guided"]["correct_recommendations"], 6)
        for pair in results:
            expected_calls = 3 if pair["mode"] == "rei" else 1
            self.assertEqual([side["model_calls"] for side in pair["sides"]],
                             [expected_calls, expected_calls])

    def test_staged_verdict_excludes_priorities_and_cannot_be_overwritten(self):
        requests = []
        choices = iter(("contradicted", "A", '{"evidence":"unknown","recommendation":"defer"}'))

        class StagedFixture(FakeProvider):
            def complete(self, **kwargs):
                _, tokens = super().complete(**kwargs)
                requests.append(json.loads(kwargs["user"]))
                return next(choices), tokens

        agent = StandaloneREI(provider_factory=StagedFixture, model="fixture")
        case = CASES[2]
        result = run_staged_pair(agent, case, "rei")
        self.assertEqual(len(requests), 3)
        self.assertIn("rei_scaffold", requests[0])
        self.assertNotIn("Decision priority", requests[0]["conversation"][0]["content"])
        for request in requests[1:]:
            self.assertNotIn("rei_scaffold", request)
            self.assertIn("Recorded claim assessment: contradicted",
                          request["conversation"][0]["content"])
        self.assertEqual(result["evidence_stage"]["verdict"], "contradicted")
        self.assertTrue(result["same_evidence"])
        self.assertFalse(result["passed"])
        self.assertIsNone(result["sides"][1]["parsed"])
        counts = summarize([result])["rei"]["staged"]
        self.assertEqual(counts["correct_shared_verdicts"], 1)
        self.assertEqual(counts["known_model_calls"], 5)
        self.assertEqual(counts["invalid_answers"], 1)

    def test_invalid_evidence_verdict_skips_recommendations(self):
        agent = StandaloneREI(provider_factory=FakeProvider, model="fixture")
        result = run_staged_pair(agent, CASES[0], "direct")
        self.assertFalse(result["passed"])
        self.assertIsNone(result["evidence_stage"]["verdict"])
        self.assertEqual([side["model_calls"] for side in result["sides"]], [0, 0])
        counts = summarize([result])["direct"]["staged"]
        self.assertEqual(counts["invalid_evidence_verdicts"], 1)
        self.assertEqual(counts["known_model_calls"], 1)
        self.assertEqual(counts["runtime_errors"], 0)

    def test_adaptive_comparison_tracks_savings_and_charges_escalation(self):
        class AdaptiveFixture(FakeProvider):
            def complete(self, **kwargs):
                _, tokens = super().complete(**kwargs)
                question = json.loads(kwargs["user"])["conversation"][-1]["content"]
                case = next(case for case in CASES if case.claim in question)
                for side, priority in enumerate(case.priorities):
                    if f"Decision priority: {priority}" in question:
                        return case.expected_recommendations[side], tokens
                if '"refs":[1,2]' in question:
                    reply = {"verdict": case.expected_evidence, "refs": case.expected_references}
                    if case is CASES[1]:
                        reply["refs"] = [99]
                    return json.dumps(reply), tokens
                return case.expected_evidence, tokens

        agent = StandaloneREI(provider_factory=AdaptiveFixture, model="fixture")
        results = run_probe(agent, compare_adaptive=True)
        self.assertEqual(len(results), 9)
        self.assertTrue(all(pair["passed"] for pair in results))
        adaptive = summarize(results)["rei"]["adaptive"]
        staged_rei = summarize(results)["rei"]["staged"]
        staged_direct = summarize(results)["direct"]["staged"]
        screened = [pair for pair in results if pair["guidance"] == "adaptive"]
        self.assertEqual(
            [pair["evidence_stage"].get("references_correct") for pair in screened],
            [True, None, True],
        )
        self.assertEqual(adaptive["expanded_pairs"], 1)
        self.assertEqual(adaptive["correct_shared_verdicts"], 3)
        self.assertEqual(adaptive["correct_deferrals"], 1)
        self.assertEqual(
            [arm["known_model_calls"] for arm in (adaptive, staged_rei, staged_direct)],
            [12, 15, 9],
        )
        self.assertEqual(
            [arm["known_model_reported_tokens"] for arm in (adaptive, staged_rei, staged_direct)],
            [668, 765, 531],
        )

    def test_effect_conflict_aggregation_handles_missing_and_invalid_results(self):
        from research.standalone_eval.paired_values import check_effect_passages
        for replies, expected, conflict in (
            (["supports", "opposes"], "unknown", True),
            (["supports", "irrelevant"], "supported", False),
            (["opposes", "opposes"], "contradicted", False),
            (["supports", "unclear"], "unknown", False),
            (["supports", "invalid"], "unknown", False),
        ):
            choices = iter(replies)

            class EffectFixture(FakeProvider):
                def complete(self, **kwargs):
                    _, tokens = super().complete(**kwargs)
                    return next(choices), tokens

            result = check_effect_passages(
                StandaloneREI(provider_factory=EffectFixture), "A reduces use.",
                ["Trial one", "Trial two"],
            )
            self.assertEqual(result["verdict"], expected)
            self.assertEqual(result["conflict"], conflict)
            self.assertEqual(result["model_calls"], 2)
