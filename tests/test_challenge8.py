"""No-model unit tests for structured output protocol and 24-case graph oracle."""
from __future__ import annotations

import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from rei0.benchmark import load_study
from rei0.inquiry import InitialDraft, ExpansionDraft
from research.challenge8.structured_provider import (
    StructuredLocalProvider, stage_schema, MODEL_ALIAS, EXPECTED_MODEL_SHA256,
)
from research.challenge8.generate_scaled import generate, direct_trace, rei_trace
from research.challenge8.run_structured import main

ROOT = Path(__file__).resolve().parents[1] / "research" / "challenge8"


class Challenge8Tests(unittest.TestCase):
    def test_all_stages_have_exact_typed_json_contracts(self):
        for stage in ("initial", "expand", "draft", "critique", "final"):
            schema = stage_schema(stage)
            self.assertEqual(schema["type"], "object")
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(set(schema["required"]), set(schema["properties"]))
        p = stage_schema("initial")["properties"]["questions"]["items"]["properties"]["priority"]
        self.assertEqual(p["type"], "integer")
        self.assertEqual((p["minimum"],p["maximum"]),(0,10))
        self.assertEqual(stage_schema("draft"), stage_schema("final"))
        with self.assertRaises(ValueError):stage_schema("fake")

    def test_constrained_objects_are_valid_under_original_parsers(self):
        draft={"claim":"Claim P is provisional","questions":[{"text":"Was the source revoked?","target":"claim","priority":6}]}
        expand={"reasons":["An audit event is recorded"],"objections":[],"followups":[],"note":"Check source history"}
        self.assertEqual(InitialDraft.parse(draft).questions[0].priority,6)
        self.assertEqual(ExpansionDraft.parse(expand).note,"Check source history")

    def test_provider_uses_same_schema_policy_for_every_arm(self):
        seen=[]
        def respond(req,timeout):
            data=json.loads(req.data)
            seen.append(data)
            val={"answer":"BOTH","confidence":0.8,"rationale":"Synthetic evidence"}
            result={"choices":[{"message":{"content":json.dumps(val)},"finish_reason":"stop"}],
                    "usage":{"total_tokens":135}}
            return io.BytesIO(json.dumps(result).encode())
        p=StructuredLocalProvider("sha","commit")
        with patch("urllib.request.urlopen",side_effect=respond):
            for arm in ("baseline","self_critique","fixed_depth","rei"):
                turn=p.respond(case_id="case",arm=arm,stage="final",context={"question":"X"},
                               max_output_tokens=320,timeout=12)
                self.assertEqual(turn.tokens_used,135)
        self.assertEqual(len(seen),4)
        assert all(x["response_format"]["type"]=="json_schema" for x in seen)
        self.assertEqual(len({json.dumps(x["response_format"],sort_keys=True) for x in seen}),1)
        self.assertTrue(all(a["status"]=="parsed" for a in p.attempts))

    def test_failed_server_json_keeps_reported_attempt_tokens(self):
        payload={"choices":[{"message":{"content":"{ incomplete"},"finish_reason":"stop"}],
                 "usage":{"total_tokens":417}}
        p=StructuredLocalProvider("sha","commit")
        with patch("urllib.request.urlopen",return_value=io.BytesIO(json.dumps(payload).encode())):
            with self.assertRaisesRegex(ValueError,"structured model request failed"):
                p.respond(case_id="case",arm="rei",stage="expand",context={},
                          max_output_tokens=320,timeout=12)
        self.assertEqual(p.attempts[0]["reported_tokens_even_if_failed"],417)
        self.assertEqual(p.attempts[0]["error_type"],"JSONDecodeError")
        self.assertEqual(p.attempts[0]["status"],"failed")

    def test_scaled_synthetic_set_is_balanced_and_reproducible(self):
        cases, keys, audit=generate()
        parsed,keymap=load_study(cases,keys)
        self.assertEqual(len(parsed),24)
        self.assertEqual(len(audit["traces"]),24)
        counts={}
        for key in keymap.values():
            counts[key.acceptable[0]]=counts.get(key.acceptable[0],0)+1
        self.assertEqual(counts,{"NEITHER":6,"SUPPORT_ONLY":6,"ATTACK_ONLY":6,"BOTH":6})
        for name, expected in (("scaled_cases.json",cases),("scaled_keys.json",keys),("scaled_audit.json",audit)):
            self.assertEqual(json.loads((ROOT/name).read_text()),expected)
        self.assertEqual(generate(),(cases,keys,audit))

    def test_original_rei_and_ledger_check_every_event(self):
        cases,keys,audit=generate()
        checkpoints=0
        for a in audit["traces"]:
            ledger=direct_trace(a["events"])
            graph=rei_trace(a["events"])
            self.assertEqual(ledger,graph)
            self.assertEqual(ledger,a["states_after_each_event"])
            checkpoints+=len(graph)
        self.assertGreaterEqual(checkpoints,180)

    def test_sharding_parameter_fails_closed(self):
        with self.assertRaises(SystemExit):
            main(["--model-file","/no/file","--engine-commit","sample",
                  "--cases",str(ROOT/"scaled_cases.json"),"--keys",str(ROOT/"scaled_keys.json"),
                  "--shard-index","6","--shard-count","6"])


if __name__=="__main__":unittest.main()