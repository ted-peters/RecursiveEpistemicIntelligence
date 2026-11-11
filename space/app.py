"""Hugging Face Space: synthetic, bounded REI-1.0 graph demonstration.

There are no LLM calls, no external retrieval, no uploads, and no reviewer keys.
The graph logic itself comes from the preserved REI-1.0 source files.
"""
from __future__ import annotations

import gradio as gr
from rei0.demo import build_demo
from rei0.graph import EpistemicGraph
from rei0.models import Edge, EdgeKind, Node, NodeKind, Provenance, SourceKind, Validation

TIME = "2026-11-11T00:00:00Z"
STAGES = [
    "1 · Three positive reports submitted (pending)",
    "2 · Positive reports approved (one original study)",
    "3 · Independent contradictory study approved",
    "4 · Original positive study revoked",
    "5 · New independent positive study approved",
    "6 · Contradictory study revoked",
]

def _source(source: str, group: str | None = None) -> Provenance:
    return Provenance(source_id=source, source_kind=SourceKind.EXTERNAL,
                      source_group=group or source, reference=f"synthetic://{source}",
                      observed_at=TIME)

def make_history(stage: int) -> dict:
    """Compute an example snapshot using REI's real typed graph and state logic."""
    step = max(1, min(6, int(stage)))
    graph = EpistemicGraph(method_version="rei-1.0-demo", clock=lambda: TIME)
    graph.add_node(Node("durability", NodeKind.CLAIM,
                        "The fictional prototype passed its durability trial.",
                        _source("synthetic-analyst"), TIME))
    inputs = [("pos-a", "study-original", EdgeKind.SUPPORTS),
              ("pos-b", "study-original", EdgeKind.SUPPORTS),
              ("pos-c", "study-original", EdgeKind.SUPPORTS),
              ("neg-a", "study-independent-negative", EdgeKind.ATTACKS),
              ("pos-new", "study-new-positive", EdgeKind.SUPPORTS)]
    for src, group, relation in inputs:
        graph.add_node(Node(src, NodeKind.EVIDENCE, f"Synthetic report: {src}",
                            _source(src, group), TIME))
        graph.add_edge(Edge("edge-" + src, src, "durability", relation,
                            _source("synthetic-analyst"), graph.method_version, TIME))
    if step >= 2:
        for src in ["pos-a", "pos-b", "pos-c"]:
            graph.set_validation("node", src, Validation.VERIFIED,
                                 verified_by="demo-operator", reason="Synthetic demonstration approval")
            graph.set_validation("edge", "edge-" + src, Validation.VERIFIED,
                                 verified_by="demo-operator", reason="Synthetic demonstration approval")
    if step >= 3:
        graph.set_validation("node", "neg-a", Validation.VERIFIED,
                             verified_by="demo-operator", reason="Synthetic demonstration approval")
        graph.set_validation("edge", "edge-neg-a", Validation.VERIFIED,
                             verified_by="demo-operator", reason="Synthetic demonstration approval")
    if step >= 4:
        for src in ["pos-a", "pos-b", "pos-c"]:
            graph.set_validation("node", src, Validation.REVOKED,
                                 verified_by="demo-operator", reason="Synthetic review revocation")
    if step >= 5:
        graph.set_validation("node", "pos-new", Validation.VERIFIED,
                             verified_by="demo-operator", reason="Synthetic demonstration approval")
        graph.set_validation("edge", "edge-pos-new", Validation.VERIFIED,
                             verified_by="demo-operator", reason="Synthetic demonstration approval")
    if step >= 6:
        graph.set_validation("node", "neg-a", Validation.REVOKED,
                             verified_by="demo-operator", reason="Synthetic review revocation")
    assessment = graph.assess("durability")
    replayed = EpistemicGraph.from_dict(graph.to_dict())
    assert replayed.assess("durability").to_dict() == assessment.to_dict()
    return {
        "stage": step, "label": STAGES[step - 1],
        "state": assessment.state.value,
        "independent_positive_groups": len(assessment.support_sources),
        "independent_negative_groups": len(assessment.attack_sources),
        "supporting_source_groups": list(assessment.support_sources),
        "opposing_source_groups": list(assessment.attack_sources),
        "ignored_edges": [dict(edge_id=e, reason=r) for e, r in assessment.ignored_edges],
        "audit_events": len(graph.events),
        "audit_chain_replays": True,
        "confidence": assessment.confidence,
        "warning": "FICTIONAL DATA. Approvals are scripted example labels, NOT authenticated factual verification.",
    }

def state_description(state: str) -> str:
    return {
      "NEITHER": "No admissible evidence has been approved.",
      "SUPPORT_ONLY": "Recorded support without currently admitted opposing evidence (not proof).",
      "ATTACK_ONLY": "Recorded opposition without currently admitted support (not proof).",
      "BOTH": "Admissible support and opposition coexist. REI preserves the conflict.",
    }[state]

def run_history(stage: int):
    data = make_history(stage)
    return f"### {data['state']}\n{state_description(data['state'])}", data

def assess_demo(claim_name: str):
    graph = build_demo()
    assessment = graph.assess(claim_name)
    return (f"### {assessment.state.value}\n{state_description(assessment.state.value)}",
            assessment.to_dict())

with gr.Blocks(title="REI — Epistemic Intelligence Research Demo") as demo:
    gr.Markdown("# 🧠 Recursive Epistemic Intelligence (REI)")
    gr.Markdown("**Research demonstration — not a trained AI chatbot.** Interact with the original REI-1.0 graph logic using entirely fictional evidence. No network calls or private keys.")
    with gr.Tab("Evidence that changes"):
        gr.Markdown("### An unfolding investigation\nEach step introduces new fictional evidence or retracts earlier evidence. Source dependence is explicitly represented.")
        step = gr.Slider(1, 6, value=3, step=1, label="Stage of investigation")
        summary = gr.Markdown()
        data = gr.JSON(label="Detailed audit snapshot")
        step.change(run_history, inputs=step, outputs=[summary, data])
        demo.load(lambda: run_history(3), inputs=None, outputs=[summary, data])
        gr.Markdown("**Evidence status ≠ truth.** A public demo cannot authenticate a real-world study. The source grouping is supplied as metadata, not independently discovered.")
    with gr.Tab("Four evidence states"):
        claim = gr.Dropdown(choices=["unassessed", "supported", "opposed", "disputed", "isolated"], value="disputed", label="Example claim")
        label = gr.Markdown()
        details = gr.JSON(label="Graph assessment")
        claim.change(assess_demo, inputs=claim, outputs=[label, details])
        demo.load(lambda: assess_demo("disputed"), inputs=None, outputs=[label, details])
    with gr.Tab("Research status"):
        gr.Markdown("""### What is implemented?
- Typed epistemic graph and open-ended questions
- Four-state, provenance-aware evidence tracking
- Source group deduplication when dependence is declared
- Auditable belief changes and evidence revocation

### What is *not* established?
- REI has not been proved more accurate than conventional AI.
- These examples use scripted approvals, not independently validated sources.
- A standalone model is not trained or hosted here.
- An independently conducted, budget-matched AI-versus-AI test is still pending.

The full REI-1.0 research project contains additional inquiry and verification modules that are intentionally excluded from this public interactive demo.
""")

if __name__ == "__main__":
    demo.launch()
