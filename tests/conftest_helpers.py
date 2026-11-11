"""Deterministic test fixtures without external dependencies."""

from rei0 import (Edge, EdgeKind, EpistemicGraph, Node, NodeKind, Provenance,
                  SourceKind, Validation)

TIME = "2026-11-10T00:00:00Z"


def prov(source: str, group: str | None = None, kind: SourceKind = SourceKind.HUMAN) -> Provenance:
    return Provenance(source, kind, group or source, f"test://{source}", TIME)


def graph() -> EpistemicGraph:
    return EpistemicGraph(clock=lambda: TIME)


def node(g: EpistemicGraph, identifier: str, kind: NodeKind = NodeKind.CLAIM,
         group: str | None = None, source_kind: SourceKind = SourceKind.EXTERNAL) -> None:
    g.add_node(Node(identifier, kind, f"Content for {identifier}",
                    prov(identifier, group, source_kind), TIME))


def link(g: EpistemicGraph, identifier: str, source: str, target: str,
         kind: EdgeKind = EdgeKind.SUPPORTS, verify: bool = False) -> None:
    g.add_edge(Edge(identifier, source, target, kind, prov("linker"), g.method_version, TIME))
    if verify:
        g.set_validation("edge", identifier, Validation.VERIFIED, verified_by="reviewer", reason="tested")


def approve(g: EpistemicGraph, identifier: str, entity: str = "node") -> None:
    g.set_validation(entity, identifier, Validation.VERIFIED, verified_by="reviewer", reason="tested")
