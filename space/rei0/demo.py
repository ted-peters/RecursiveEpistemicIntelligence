"""Reproducible hand-authored demonstration of all four evidence states."""

from .graph import EpistemicGraph
from .models import Edge, EdgeKind, Node, NodeKind, Provenance, SourceKind, Validation

FIXED_TIME = "2026-11-10T00:00:00Z"


def origin(source: str, group: str | None = None, kind: SourceKind = SourceKind.HUMAN) -> Provenance:
    return Provenance(source_id=source, source_kind=kind, source_group=group or source,
                      reference=f"demo://{source}", observed_at=FIXED_TIME)


def build_demo() -> EpistemicGraph:
    graph = EpistemicGraph(clock=lambda: FIXED_TIME)
    examples = {
        "unassessed": "No admissible evidence has been recorded.",
        "supported": "The first indicator favors the hypothesis.",
        "opposed": "The second indicator contradicts the hypothesis.",
        "disputed": "Two distinct observations disagree about the hypothesis.",
        "isolated": "An unrelated claim is unaffected by the dispute.",
    }
    for cid, statement in examples.items():
        graph.add_node(Node(cid, NodeKind.CLAIM, statement, origin("analyst"), FIXED_TIME))
    for eid, statement, group, kind in [
        ("observation-a", "Observation A supports the hypothesis.", "study-a", SourceKind.EXTERNAL),
        ("observation-a-copy", "A republished copy of observation A.", "study-a", SourceKind.EXTERNAL),
        ("observation-b", "Observation B contradicts the hypothesis.", "study-b", SourceKind.EXTERNAL),
        ("model-suggestion", "A model asserts that the claim is true.", "synthetic", SourceKind.MODEL),
    ]:
        graph.add_node(Node(eid, NodeKind.EVIDENCE, statement, origin(eid, group, kind), FIXED_TIME))
        graph.set_validation("node", eid, Validation.VERIFIED,
                             verified_by="reviewer:example", reason="Scripted demo approval; not real-world validation")
    for edge_id, src, tgt, kind in [
        ("s1", "observation-a", "supported", EdgeKind.SUPPORTS),
        ("a1", "observation-b", "opposed", EdgeKind.ATTACKS),
        ("s2", "observation-a", "disputed", EdgeKind.SUPPORTS),
        ("s3", "observation-a-copy", "disputed", EdgeKind.SUPPORTS),
        ("a2", "observation-b", "disputed", EdgeKind.ATTACKS),
        ("m1", "model-suggestion", "isolated", EdgeKind.SUPPORTS),
    ]:
        graph.add_edge(Edge(edge_id, src, tgt, kind, origin("analyst"), graph.method_version, FIXED_TIME))
        graph.set_validation("edge", edge_id, Validation.VERIFIED,
                             verified_by="reviewer:example", reason="Scripted demo relation approval")
    graph.add_node(Node("open-1", NodeKind.OPEN_QUESTION,
                        "Are observation A and observation B independently reliable?",
                        origin("analyst"), FIXED_TIME))
    return graph


def report(graph: EpistemicGraph) -> dict:
    return {
        "method_version": graph.method_version,
        "assessments": [graph.assess(cid).to_dict() for cid in sorted(graph.nodes)
                        if graph.nodes[cid].kind == NodeKind.CLAIM],
        "open_questions": [{"id": q.id, "question": q.text} for q in graph.open_questions()],
        "audit_event_count": len(graph.events),
        "audit_head": graph.audit_head,
        "notice": "Scripted approval metadata is not independent verification of real-world facts.",
    }
