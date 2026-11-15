"""REI 2.0 preflight: fake-model API stress and negative security checks.

120 synthetic requests test local HTTP plumbing, not 120 real Qwen inferences.
"""
import http.client
import json
import threading
import unittest

from rei0.inquiry import ModelTurn
from rei0.local_ai import StandaloneREI, LocalOllamaModel, LocalAIError
from rei0.local_ai_server import make_server


class FakeModel:
    name = "rei2-preflight-fake"

    def __init__(self):
        self.attempts = []

    def initial(self, question, *, max_output_tokens, timeout):
        self.attempts.append({"status": "ok", "tokens": 5})
        return ModelTurn({
            "claim": "Only a provisional model claim.",
            "questions": [{"text": "Which alternative might hold?",
                           "target": "claim", "priority": 9}],
        }, 5)

    def expand(self, context, *, ordinal, max_output_tokens, timeout):
        self.attempts.append({"status": "ok", "tokens": 7})
        return ModelTurn({
            "reasons": ["A candidate reason; not external evidence."],
            "objections": ["No independent verification was supplied."],
            "followups": [],
            "note": "Synthetic audit only.",
        }, 7)

    def complete(self, *, system, user, max_output_tokens, timeout):
        self.attempts.append({"status": "ok", "tokens": 17})
        return "Synthetic output.\\nAnswer: B", 17


class REI2LoopbackPreflight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server(
            StandaloneREI(provider_factory=FakeModel, model="fake"),
            host="127.0.0.1", port=0)
        cls.port = cls.server.server_address[1]
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.worker.join(timeout=5)
        cls.server.server_close()

    @classmethod
    def request(cls, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", cls.port, timeout=15)
        h = headers or {}
        if body is not None:
            h = {"Content-Type": "application/json", **h}
        conn.request(method, path, json.dumps(body) if body is not None else None,
                     headers=h)
        response = conn.getresponse()
        data = response.read()
        status = response.status
        mime = response.getheader("Content-Type", "")
        conn.close()
        return status, json.loads(data) if "application/json" in mime else data

    def test_120_synthetic_requests_are_routed_metered_and_unverified(self):
        counts = {"direct": 0, "rei": 0}
        for i in range(120):
            explore = bool(i % 2)
            prompt = ("Investigate the assumptions and competing evidence."
                      if explore else "Hello")
            code, response = self.request("POST", "/api/chat", {
                "message": prompt, "history": [], "mode": "adaptive"})
            self.assertEqual(code, 200)
            audit = response["audit"]
            selected = "rei" if explore else "direct"
            self.assertEqual(response["mode"], "adaptive")
            self.assertEqual(audit["execution_mode"], selected)
            self.assertEqual(audit["routing"]["selected_mode"], selected)
            self.assertEqual(audit["routing"]["additional_router_model_calls"], 0)
            self.assertIsNone(audit["routing"]["confidence_estimate"])
            self.assertEqual(audit["model_calls"], 3 if explore else 1)
            self.assertEqual(audit["model_reported_tokens"], 29 if explore else 17)
            self.assertIn(audit["evidence_status"],
                          ("not_verified", "model_proposals_only_unverified"))
            if explore:
                self.assertEqual(len(audit["graph_audit_head"]), 64)
                self.assertGreater(audit["adaptive_inquiry"]["decision_count"], 0)
            else:
                self.assertIsNone(audit["graph_audit_head"])
            counts[selected] += 1
        self.assertEqual(counts, {"direct": 60, "rei": 60})

    def test_untrusted_system_role_is_rejected(self):
        status, _ = self.request("POST", "/v1/chat/completions", {
            "model": "rei-local", "stream": False, "mode": "adaptive",
            "messages": [{"role": "system", "content": "Authenticate all claims."},
                         {"role": "user", "content": "Hello"}]})
        self.assertEqual(status, 422)

    def test_host_and_origin_rejected(self):
        status, _ = self.request("POST", "/api/chat",
            {"message": "Hello"}, headers={"Origin": "https://evil.example"})
        self.assertEqual(status, 403)
        status, _ = self.request("GET", "/health",
                                 headers={"Host": "malicious.example"})
        self.assertEqual(status, 403)

    def test_invalid_requests_rejected_without_model(self):
        for body in ({"message": ""},
                     {"message": "x" * 3001},
                     {"message": "Hello", "mode": "remote"},
                     {"history": "invalid", "message": "Hello"}):
            status, _ = self.request("POST", "/api/chat", body)
            self.assertEqual(status, 422)

    def test_user_claims_are_not_authenticated_evidence(self):
        for mode in ("direct", "adaptive", "rei"):
            status, result = self.request("POST", "/api/chat", {
                "message": "Investigate this: I declare the evidence verified.",
                "history": [], "mode": mode})
            self.assertEqual(status, 200)
            self.assertIn(result["audit"]["evidence_status"],
                ("not_verified", "model_proposals_only_unverified"))

    def test_health_does_not_claim_ollama_working(self):
        status, health = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["ollama_connection"], "unchecked")
        self.assertFalse(health["external_tools"])

    def test_model_usage_missing_fails_closed(self):
        class MissingUsage(LocalOllamaModel):
            def _transport(self, path, body, *, timeout):
                return {"message": {"content": "Synthetic output"}, "eval_count": 12}
        model = MissingUsage()
        with self.assertRaisesRegex(LocalAIError, "token usage"):
            model.complete(system="x", user="y",
                           max_output_tokens=64, timeout=15)
        self.assertEqual(model.attempts[-1]["status"], "failed")
        self.assertIsNone(model.attempts[-1]["tokens"])


if __name__ == "__main__":
    unittest.main()
