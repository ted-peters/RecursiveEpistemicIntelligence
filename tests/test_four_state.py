import unittest

from rei0 import EdgeKind, EvidenceState, NodeKind, SourceKind, Validation
from conftest_helpers import approve, graph, link, node


class FourStateTests(unittest.TestCase):
    def setUp(self):
        self.g = graph()
        for name in ("none", "positive", "negative", "conflict", "unrelated"):
            node(self.g, name)
        node(self.g, "e1", NodeKind.EVIDENCE)
        node(self.g, "e2", NodeKind.EVIDENCE)
        approve(self.g, "e1")
        approve(self.g, "e2")

    def test_neither(self):
        self.assertEqual(self.g.assess("none").state, EvidenceState.NEITHER)
        self.assertIsNone(self.g.assess("none").confidence)

    def test_support_only(self):
        link(self.g, "s", "e1", "positive", verify=True)
        result = self.g.assess("positive")
        self.assertEqual(result.state, EvidenceState.SUPPORT_ONLY)
        self.assertEqual(result.support_evidence, ("e1",))

    def test_attack_only(self):
        link(self.g, "a", "e1", "negative", EdgeKind.ATTACKS, verify=True)
        self.assertEqual(self.g.assess("negative").state, EvidenceState.ATTACK_ONLY)

    def test_both_and_isolation(self):
        link(self.g, "s", "e1", "conflict", verify=True)
        link(self.g, "a", "e2", "conflict", EdgeKind.ATTACKS, verify=True)
        self.assertEqual(self.g.assess("conflict").state, EvidenceState.BOTH)
        self.assertEqual(self.g.assess("unrelated").state, EvidenceState.NEITHER)

    def test_only_verified_evidence_and_edges_count(self):
        link(self.g, "s", "e1", "positive")
        self.assertEqual(self.g.assess("positive").state, EvidenceState.NEITHER)
        self.assertIn(("s", "edge_not_verified"), self.g.assess("positive").ignored_edges)
        approve(self.g, "s", "edge")
        self.assertEqual(self.g.assess("positive").state, EvidenceState.SUPPORT_ONLY)
        node(self.g, "e3", NodeKind.EVIDENCE)
        link(self.g, "s3", "e3", "negative", verify=True)
        self.assertEqual(self.g.assess("negative").state, EvidenceState.NEITHER)

    def test_model_generated_evidence_excluded_even_if_declared_verified(self):
        node(self.g, "synthetic", NodeKind.EVIDENCE, source_kind=SourceKind.MODEL)
        approve(self.g, "synthetic")
        link(self.g, "s", "synthetic", "positive", verify=True)
        result = self.g.assess("positive")
        self.assertEqual(result.state, EvidenceState.NEITHER)
        self.assertIn(("s", "model_output_not_external_evidence"), result.ignored_edges)

    def test_revocation_removes_support_without_erasing_history(self):
        link(self.g, "s", "e1", "positive", verify=True)
        before = len(self.g.events)
        self.g.set_validation("node", "e1", Validation.REVOKED,
                              verified_by="reviewer", reason="retracted")
        self.assertEqual(self.g.assess("positive").state, EvidenceState.NEITHER)
        self.assertEqual(len(self.g.events), before + 1)

    def test_argument_support_is_not_automatically_evidence(self):
        node(self.g, "premise", NodeKind.CLAIM)
        link(self.g, "s", "premise", "positive", verify=True)
        self.assertEqual(self.g.assess("positive").state, EvidenceState.NEITHER)
        self.assertIn(("s", "argument_not_independent_evidence"), self.g.assess("positive").ignored_edges)


if __name__ == "__main__":
    unittest.main()
