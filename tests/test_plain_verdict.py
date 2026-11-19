import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

EXPERIMENT = Path(__file__).resolve().parents[1] / "research" / "adaptive_rei"
with patch.object(sys, "path", [str(EXPERIMENT), *sys.path]):
    import plain_verdict


class PlainVerdictTests(unittest.TestCase):
    def test_meter_and_parse_the_entire_response(self):
        for raw, expected in (("YES.\n", "yes"), ("uncertain", "uncertain"),
                              ("yes or no", None), ("no because", None), ("", None)):
            reply = json.dumps({"response": raw, "eval_count": 5, "prompt_eval_count": 99})
            with self.subTest(raw=raw), patch("urllib.request.urlopen",
                                              return_value=io.BytesIO(reply.encode())):
                self.assertEqual(plain_verdict.decide("http://localhost", "test", "Did it rain?"),
                                 ({"answer": expected}, 104))

    def test_graph_still_avoids_a_model_call(self):
        passage = "Did the gate open? The log says it did. The notice copied the log."
        with patch("urllib.request.urlopen", side_effect=AssertionError):
            self.assertEqual(plain_verdict.decide("", "", passage), ({"answer": "yes"}, 0))
