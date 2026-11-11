"""Run from repository root: python -m examples.quick_example"""

from rei0 import (Edge, EdgeKind, EpistemicGraph, Node, NodeKind,
                  Provenance, SourceKind, Validation)

NOW = "2026-11-10T00:00:00Z"


def provenance(source_id, group):
    return Provenance(source_id=source_id, source_kind=SourceKind.HUMAN,
                      source_group=group, reference=f"example://{source_id}", observed_at=NOW)


def main():
    graph = EpistemicGraph(clock=lambda: NOW)
    graph.add_node(Node("hypothesis", NodeKind.CLAIM, "The lamp is lit.",
                        provenance("investigator", "investigator"), NOW))
    graph.add_node(Node("reading", NodeKind.EVIDENCE, "A light sensor reading indicates light.",
                        provenance("sensor-01", "sensor-01"), NOW))
    graph.add_edge(Edge("link", "reading", "hypothesis", EdgeKind.SUPPORTS,
                        provenance("investigator", "investigator"), graph.method_version, NOW))

    print("Before reviewed evidence:", graph.assess("hypothesis").state.value)
    graph.set_validation("node", "reading", Validation.VERIFIED,
                         verified_by="reviewer-01", reason="Example review, not a real source check")
    graph.set_validation("edge", "link", Validation.VERIFIED,
                         verified_by="reviewer-01", reason="Example relation review")
    print("After reviewed evidence: ", graph.assess("hypothesis").state.value)
    print("Audit events:", len(graph.events))


if __name__ == "__main__":
    main()
