"""Browser-based, deterministic REI evidence graph demonstration.

This is an exercise of original REI-1.0 graph code, not a trained language model.
Every evidence record and review approval is FICTIONAL and scripted.
"""
from __future__ import annotations
from rei0.demo import build_demo
from rei0.graph import EpistemicGraph
from rei0.models import Edge, EdgeKind, Node, NodeKind, Provenance, SourceKind, Validation

TIME = "2026-11-11T00:00:00Z"
STAGES = (
    "Three positive reports submitted, all pending review",
    "Three positive reports approved, but all cite the same original study",
    "An independent opposing report is approved",
    "The original supporting study is revoked",
    "A new, independent positive study is approved",
    "The opposing study is revoked",
)
DESCRIPTIONS = {
    "NEITHER": "No admissible evidence has been approved.",
    "SUPPORT_ONLY": "Recorded support, without currently admitted opposition. This is not proof.",
    "ATTACK_ONLY": "Recorded opposition, without currently admitted support. This is not proof.",
    "BOTH": "Admissible supporting and opposing evidence coexist. The conflict remains unresolved.",
}

def source(source_id: str, group: str | None = None) -> Provenance:
    return Provenance(source_id=source_id, source_kind=SourceKind.EXTERNAL,
                      source_group=group or source_id, reference=f"synthetic://{source_id}",
                      observed_at=TIME)

def history(stage: int) -> dict:
    step = max(1, min(6, int(stage)))
    graph = EpistemicGraph(method_version="rei-1.0-public-demo", clock=lambda: TIME)
    graph.add_node(Node("durability", NodeKind.CLAIM, "The fictional prototype passed durability trials.",
                        source("synthetic-analyst"), TIME))
    inputs = (
        ("pos-a", "original-study", EdgeKind.SUPPORTS),
        ("pos-b", "original-study", EdgeKind.SUPPORTS),
        ("pos-c", "original-study", EdgeKind.SUPPORTS),
        ("neg-a", "independent-negative-study", EdgeKind.ATTACKS),
        ("pos-new", "independent-new-positive-study", EdgeKind.SUPPORTS),
    )
    for src, group, relation in inputs:
        graph.add_node(Node(src, NodeKind.EVIDENCE, f"Fictional report: {src}",
                            source(src, group), TIME))
        graph.add_edge(Edge(f"edge-{src}", src, "durability", relation,
                            source("synthetic-analyst"), graph.method_version, TIME))
    if step >= 2:
        for src in ("pos-a", "pos-b", "pos-c"):
            graph.set_validation("node", src, Validation.VERIFIED,
                                 verified_by="scripted-demo", reason="Fictional review approval")
            graph.set_validation("edge", f"edge-{src}", Validation.VERIFIED,
                                 verified_by="scripted-demo", reason="Fictional review approval")
    if step >= 3:
        graph.set_validation("node", "neg-a", Validation.VERIFIED,
                             verified_by="scripted-demo", reason="Fictional review approval")
        graph.set_validation("edge", "edge-neg-a", Validation.VERIFIED,
                             verified_by="scripted-demo", reason="Fictional review approval")
    if step >= 4:
        for src in ("pos-a", "pos-b", "pos-c"):
            graph.set_validation("node", src, Validation.REVOKED,
                                 verified_by="scripted-demo", reason="Fictional evidence revoked")
    if step >= 5:
        graph.set_validation("node", "pos-new", Validation.VERIFIED,
                             verified_by="scripted-demo", reason="Fictional review approval")
        graph.set_validation("edge", "edge-pos-new", Validation.VERIFIED,
                             verified_by="scripted-demo", reason="Fictional review approval")
    if step >= 6:
        graph.set_validation("node", "neg-a", Validation.REVOKED,
                             verified_by="scripted-demo", reason="Fictional evidence revoked")
    assessment = graph.assess("durability")
    rebuilt = EpistemicGraph.from_dict(graph.to_dict())
    assert rebuilt.assess("durability").to_dict() == assessment.to_dict()
    return {
        "stage": step,
        "event": STAGES[step - 1],
        "state": assessment.state.value,
        "description": DESCRIPTIONS[assessment.state.value],
        "positive_groups": len(assessment.support_sources),
        "negative_groups": len(assessment.attack_sources),
        "source_groups_supporting": list(assessment.support_sources),
        "source_groups_opposing": list(assessment.attack_sources),
        "ignored_edges": [{"id": ident, "reason": why} for ident, why in assessment.ignored_edges],
        "audit_events": len(graph.events),
        "audit_replays": True,
        "confidence": assessment.confidence,
        "fictional": True,
    }

def example(name: str) -> dict:
    if name not in ("unassessed", "supported", "opposed", "disputed", "isolated"):
        raise ValueError("Unknown demonstration claim")
    graph = build_demo()
    assessment = graph.assess(name)
    return {"name": name, "state": assessment.state.value,
            "description": DESCRIPTIONS[assessment.state.value],
            "assessment": assessment.to_dict(), "fictional": True}
