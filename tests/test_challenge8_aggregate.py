"""Offline audit tests. Synthetic fixtures are not evidence of AI performance."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from rei0.benchmark import Limits, ModelTurn, run_benchmark
from research.challenge8.aggregate import AggregateError, aggregate_shards, subset
from research.challenge8.generate_scaled import generate


class RecordedFixtureProvider:
    """Exercise the REAL benchmark stages with deterministic fake inference."""
    kind = "live_local_model_schema_constrained_all_arms"
    fingerprint = "synthetic-fixture-not-real-inference"

    def __init__(self, fail_pair=None):
        self.attempts = []
        self.fail_pair = fail_pair
        self.failed_once = False

    def respond(self, *, case_id, arm, stage, context, max_output_tokens, timeout):
        failed = (self.fail_pair == (case_id, arm) and not self.failed_once)
        if failed:
            self.failed_once = True
        self.attempts.append({
            "case_id": case_id, "arm": arm, "stage": stage,
            "reported_tokens_even_if_failed": None if failed else 10,
            "status": "failed" if failed else "parsed", "finish_reason": None if failed else "stop",
        })
        if failed:
            raise TimeoutError("synthetic timeout")
        if stage == "initial":
            payload = {"claim": "Unverified claim", "questions": [
                {"text": "Could this report be revoked?", "target": "claim", "priority": 6}]}
        elif stage == "expand":
            payload = {"reasons": ["A fictional report exists"], "objections": [],
                       "followups": [], "note": "Still unverified"}
        elif stage == "critique":
            payload = {"critique": "Check the event ordering"}
        else:
            payload = {"answer": "NEITHER", "confidence": 0.5,
                       "rationale": "A scripted fixture output; not model reasoning"}
        return ModelTurn(payload, 10)


def build_fixture(directory: Path, fail_pair=None):
    full_cases, full_keys, _ = generate()
    paths = []
    for idx in range(6):
        cases, keys = subset(full_cases, full_keys, idx, 6)
        provider = RecordedFixtureProvider(fail_pair)
        report = run_benchmark(cases, keys, provider,
                               limits=Limits(max_calls=3, max_tokens=2600,
                                             max_seconds=140, max_output_tokens=320, steps=1),
                               seed=24011)
        attempt_rows = provider.attempts
        usage = {}
        for arm in ("baseline", "self_critique", "fixed_depth", "rei"):
            rows = [a for a in attempt_rows if a["arm"] == arm]
            usage[arm] = {
                "attempted_calls": len(rows),
                "server_reported_tokens_including_failed_parses": sum(
                    a["reported_tokens_even_if_failed"] or 0 for a in rows),
                "calls_with_unknown_tokens": sum(a["reported_tokens_even_if_failed"] is None for a in rows),
                "calls_with_provider_error": sum(a["status"] == "failed" for a in rows),
            }
        env = {
            "experiment_run_id": "synthetic-fixture-one-run",
            "model": "synthetic-fixture", "model_sha256": "not-real-model-sha",
            "llama_cpp_commit": "not-real-engine", "method": "test-mode",
            "constraints": {"max_calls":3, "max_tokens":2600,"max_seconds":140,
                            "max_output_tokens":320, "steps":1},
            "study": "synthetic fixture no intelligence claim", "shard_index": idx,
            "shard_count": 6, "case_count": len(cases["cases"]),
            "calls_attempted": len(attempt_rows),
            "measured_attempt_tokens_including_parse_failures": sum(
                a["reported_tokens_even_if_failed"] or 0 for a in attempt_rows),
            "attempts_with_unknown_tokens": sum(
                a["reported_tokens_even_if_failed"] is None for a in attempt_rows),
            "attempts": attempt_rows, "attempt_usage_by_arm": usage,
        }
        path = directory / f"shard-{idx}.json"
        path.write_text(json.dumps({"report": report, "environment": env}), encoding="utf-8")
        paths.append(path)
    return paths, full_cases, full_keys


class Challenge8AggregateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.paths, self.cases, self.keys = build_fixture(self.directory)

    def check(self, paths=None):
        return aggregate_shards(self.paths if paths is None else paths, self.cases, self.keys)

    def mutate(self, index, fn):
        path = self.paths[index]
        doc = json.loads(path.read_text())
        fn(doc)
        path.write_text(json.dumps(doc))

    def test_complete_balanced_synthetic_set_is_independently_regraded(self):
        result = self.check(list(reversed(self.paths)))
        self.assertEqual(result["case_count"], 24)
        self.assertEqual(len(result["verified_shards"]), 6)
        self.assertEqual(result["primary_comparison"]["cases"], 24)
        self.assertEqual(set(result["by_arm"]), {"baseline", "self_critique", "fixed_depth", "rei"})
        self.assertTrue(result["usage_complete"])
        self.assertFalse(result["compute_matched"])

    def test_missing_or_duplicate_shard_rejected(self):
        with self.assertRaises(AggregateError):
            self.check(self.paths[:-1])
        with self.assertRaises(AggregateError):
            self.check(self.paths[:-1] + [self.paths[0]])

    def test_model_drift_rejected(self):
        self.mutate(2, lambda doc: doc["environment"].update(model_sha256="different"))
        with self.assertRaisesRegex(AggregateError, "settings differ"):
            self.check()

    def test_mixed_workflow_runs_rejected(self):
        self.mutate(3, lambda doc: doc["environment"].update(experiment_run_id="different-run"))
        with self.assertRaisesRegex(AggregateError, "settings differ"):
            self.check()

    def test_tampered_score_rejected_by_inherited_report_verifier(self):
        self.mutate(1, lambda doc: doc["report"]["outcomes"][0].update(answer="tampered"))
        with self.assertRaises(ValueError):
            self.check()

    def test_false_attempt_total_rejected(self):
        self.mutate(4, lambda doc: doc["environment"].update(calls_attempted=10000))
        with self.assertRaisesRegex(AggregateError, "attempt count"):
            self.check()

    def test_unknown_tokens_are_not_reported_as_complete(self):
        with tempfile.TemporaryDirectory() as d:
            paths, cases, keys = build_fixture(Path(d), fail_pair=("c8-01-timeline", "rei"))
            result = aggregate_shards(paths, cases, keys)
            self.assertFalse(result["usage_complete"])
            self.assertGreater(result["by_arm"]["rei"]["unknown_token_calls"], 0)
            self.assertGreater(result["by_arm"]["rei"]["failed_cases"], 0)


if __name__ == "__main__":
    unittest.main()
