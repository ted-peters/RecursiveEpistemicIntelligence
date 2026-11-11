import unittest
from rei0 import Node, NodeKind, Provenance, SourceKind, Edge, EdgeKind, EpistemicGraph, GraphError
from conftest_helpers import TIME, graph, node, prov


class SchemaTests(unittest.TestCase):
    def test_empty_source_rejected(self):
        with self.assertRaises(ValueError):
            Provenance("", SourceKind.EXTERNAL, "g", "doc", TIME)

    def test_timestamp_requires_utc(self):
        with self.assertRaises(ValueError):
            Provenance("source", SourceKind.EXTERNAL, "grp", "doc", "2026-11-10")

    def test_node_text_required(self):
        with self.assertRaises(ValueError):
            Node("p", NodeKind.CLAIM, " ", prov("p"), TIME)

    def test_assess_unknown_claim_rejected(self):
        with self.assertRaises(GraphError):
            graph().assess("missing")

    def test_non_claim_assessment_rejected(self):
        g = graph()
        node(g, "e", NodeKind.EVIDENCE)
        with self.assertRaises(GraphError):
            g.assess("e")

    def test_duplicate_self_rejected(self):
        g = graph()
        node(g, "e", NodeKind.EVIDENCE)
        with self.assertRaises(GraphError):
            g.add_edge(Edge("dup", "e", "e", EdgeKind.DUPLICATES, prov("link"), g.method_version, TIME))


if __name__ == "__main__":
    unittest.main()
