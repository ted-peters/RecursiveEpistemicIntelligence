import copy
import unittest

from rei0 import Edge, EdgeKind, EpistemicGraph, EvidenceState, GraphError, NodeKind, Validation
from rei0.demo import build_demo, report
from rei0.models import digest
from conftest_helpers import TIME, approve, graph, link, node, prov


class ProvenanceAndAuditTests(unittest.TestCase):
    def test_repeated_source_group_not_independent(self):
        g = graph()
        node(g, "p")
        node(g, "e1", NodeKind.EVIDENCE, group="original-report")
        node(g, "e2", NodeKind.EVIDENCE, group="original-report")
        for e in ("e1", "e2"):
            approve(g, e)
            link(g, f"s-{e}", e, "p", verify=True)
        result = g.assess("p")
        self.assertEqual(result.state, EvidenceState.SUPPORT_ONLY)
        self.assertEqual(len(result.support_sources), 1)
        self.assertEqual(len(result.support_evidence), 1)
        self.assertEqual(len(result.ignored_edges), 1)

    def test_verified_duplicate_relation_merges_distinct_groups(self):
        g = graph()
        node(g, "p")
        node(g, "e1", NodeKind.EVIDENCE, group="a")
        node(g, "e2", NodeKind.EVIDENCE, group="b")
        for e in ("e1", "e2"):
            approve(g, e)
            link(g, f"s-{e}", e, "p", verify=True)
        self.assertEqual(len(g.assess("p").support_sources), 2)
        link(g, "dup", "e1", "e2", EdgeKind.DUPLICATES, verify=True)
        self.assertEqual(len(g.assess("p").support_sources), 1)

    def test_pending_duplicate_does_not_merge(self):
        g = graph()
        node(g, "p")
        for e, grp in (("e1", "a"), ("e2", "b")):
            node(g, e, NodeKind.EVIDENCE, group=grp)
            approve(g, e)
            link(g, f"s-{e}", e, "p", verify=True)
        link(g, "pending-dup", "e1", "e2", EdgeKind.DUPLICATES)
        self.assertEqual(len(g.assess("p").support_sources), 2)

    def test_provenance_fingerprint_stable(self):
        self.assertEqual(prov("source").fingerprint, prov("source").fingerprint)
        self.assertNotEqual(prov("source").fingerprint, prov("other").fingerprint)

    def test_demo_all_four_states_and_determinism(self):
        one, two = build_demo(), build_demo()
        self.assertEqual(one.to_dict(), two.to_dict())
        values = {row["claim_id"]: row["state"] for row in report(one)["assessments"]}
        self.assertEqual(values, {"unassessed": "NEITHER", "supported": "SUPPORT_ONLY",
                                  "opposed": "ATTACK_ONLY", "disputed": "BOTH", "isolated": "NEITHER"})
        self.assertEqual(len(one.assess("disputed").support_sources), 1)
        self.assertEqual(one.assess("isolated").support_sources, ())

    def test_event_replay_reconstructs_state(self):
        original = build_demo()
        reconstructed = EpistemicGraph.from_dict(original.to_dict())
        self.assertEqual(original.to_dict(), reconstructed.to_dict())
        self.assertEqual(original.assess("disputed"), reconstructed.assess("disputed"))
        self.assertEqual(original.audit_head, reconstructed.audit_head)
        self.assertTrue(all(len(event["event_hash"]) == 64 for event in original.events))

    def test_event_log_does_not_expose_mutable_data(self):
        g = build_demo()
        external = g.events
        external[0]["payload"]["text"] = "forged content"
        self.assertNotEqual(g.events[0]["payload"]["text"], "forged content")

    def test_audit_tamper_detected(self):
        doc = build_demo().to_dict()
        doc["events"][0]["payload"]["text"] = "altered"
        with self.assertRaises(GraphError):
            EpistemicGraph.from_dict(doc)

    def test_replay_checks_graph_semantics_even_with_rehashed_event(self):
        doc = build_demo().to_dict()
        first = doc["events"][0]
        first["payload"]["validation"] = "verified"
        first["payload"]["verified_by"] = "fabricator"
        prev = "0" * 64
        for i, event in enumerate(doc["events"], 1):
            event["sequence"], event["previous_hash"] = i, prev
            event["event_hash"] = digest({k: event[k] for k in ("sequence", "previous_hash", "kind", "payload")})
            prev = event["event_hash"]
        with self.assertRaises(GraphError):
            EpistemicGraph.from_dict(doc)

    def test_invalid_verification_transition_rejected_without_event(self):
        g = graph()
        node(g, "p")
        before = len(g.events)
        with self.assertRaises(GraphError):
            g.set_validation("node", "p", Validation.REVOKED,
                             verified_by="reviewer", reason="invalid move")
        self.assertEqual(before, len(g.events))

    def test_source_cannot_self_verify(self):
        g = graph()
        node(g, "e", NodeKind.EVIDENCE)
        with self.assertRaises(GraphError):
            g.set_validation("node", "e", Validation.VERIFIED,
                             verified_by="e", reason="self-approved")

    def test_method_version_mismatch_rejected(self):
        g = graph()
        node(g, "p")
        node(g, "e", NodeKind.EVIDENCE)
        bad_edge = Edge("bad", "e", "p", EdgeKind.SUPPORTS, prov("link"), "MISMATCH", TIME)
        with self.assertRaises(GraphError):
            g.add_edge(bad_edge)

    def test_operational_configuration_is_read_only_by_public_setters(self):
        g = graph()
        with self.assertRaises(AttributeError):
            g.method_version = "unauthorized-version"
        with self.assertRaises(AttributeError):
            g.max_nodes = 1_000_000
        with self.assertRaises(AttributeError):
            g.max_edges = 1_000_000

    def test_revoked_duplicate_link_restores_separate_sources(self):
        g = graph()
        node(g, "p")
        for eid, source in (("e1", "study-1"), ("e2", "study-2")):
            node(g, eid, NodeKind.EVIDENCE, group=source)
            approve(g, eid)
            link(g, f"s-{eid}", eid, "p", verify=True)
        link(g, "dup", "e1", "e2", EdgeKind.DUPLICATES, verify=True)
        self.assertEqual(len(g.assess("p").support_sources), 1)
        g.set_validation("edge", "dup", Validation.REVOKED,
                         verified_by="reviewer", reason="duplicate assessment retracted")
        self.assertEqual(len(g.assess("p").support_sources), 2)

    def test_node_limit_enforced(self):
        g = EpistemicGraph(max_nodes=1, clock=lambda: TIME)
        node(g, "p")
        with self.assertRaises(GraphError):
            node(g, "q")

    def test_from_dict_rejects_incompatible_schema(self):
        data = build_demo().to_dict()
        data["schema_version"] = "bad.schema"
        with self.assertRaises(GraphError):
            EpistemicGraph.from_dict(data)


if __name__ == "__main__":
    unittest.main()
