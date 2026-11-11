import unittest
from rei0 import CycleError, EdgeKind, GraphError, NodeKind
from conftest_helpers import graph, link, node


class CircularityTests(unittest.TestCase):
    def setUp(self):
        self.g = graph()
        for name in "ABCD":
            node(self.g, name)

    def test_direct_cycle_rejected(self):
        link(self.g, "ab", "A", "B")
        before = len(self.g.events)
        with self.assertRaises(CycleError):
            link(self.g, "ba", "B", "A")
        self.assertEqual(before, len(self.g.events))

    def test_three_node_cycle_rejected(self):
        link(self.g, "ab", "A", "B")
        link(self.g, "bc", "B", "C")
        with self.assertRaises(CycleError):
            link(self.g, "ca", "C", "A")

    def test_mixed_support_and_dependency_cycle_rejected(self):
        link(self.g, "ab", "A", "B")
        # B depends on A already via A supports B. A depends on B closes a cycle.
        with self.assertRaises(CycleError):
            link(self.g, "ad", "A", "B", EdgeKind.DEPENDS_ON)

    def test_self_support_rejected(self):
        with self.assertRaises(CycleError):
            link(self.g, "aa", "A", "A")

    def test_attack_cycle_does_not_claim_positive_justification(self):
        link(self.g, "ab", "A", "B", EdgeKind.ATTACKS)
        link(self.g, "ba", "B", "A", EdgeKind.ATTACKS)
        self.assertEqual(self.g.assess("A").support_sources, ())

    def test_wrong_type_rejected(self):
        node(self.g, "e", NodeKind.EVIDENCE)
        with self.assertRaises(GraphError):
            link(self.g, "wrong", "A", "e", EdgeKind.SUPPORTS)

    def test_missing_endpoint_rejected(self):
        with self.assertRaises(GraphError):
            link(self.g, "wrong", "A", "not-found")

    def test_id_collision_rejected(self):
        with self.assertRaises(GraphError):
            node(self.g, "A")


if __name__ == "__main__":
    unittest.main()
