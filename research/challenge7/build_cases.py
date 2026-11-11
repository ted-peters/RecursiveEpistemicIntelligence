"""Challenge 7: independently calculate ledger and REI graph states per event.

This generator does not call any model. The public test questions are not blind.
The strong conventional baseline is an event-sourced provenance-aware ledger,
not a strawman vote counter. Its direct-state parity with REI is expected.
"""
from __future__ import annotations

import json
from pathlib import Path

from rei0.graph import EpistemicGraph
from rei0.models import Edge, EdgeKind, Node, NodeKind, Provenance, SourceKind, Validation

HERE = Path(__file__).resolve().parent
STAMP = "2026-11-11T00:00:00Z"


def state_from_bits(support: bool, attack: bool) -> str:
    return {(False, False): "NEITHER", (True, False): "SUPPORT_ONLY",
            (False, True): "ATTACK_ONLY", (True, True): "BOTH"}[(bool(support), bool(attack))]


def ledger_trace(events: list[dict]) -> list[dict]:
    records = {}
    trace = []
    for e in events:
        op, doc = e["op"], e["doc"]
        if op in ("PENDING", "ACCEPT"):
            if doc in records or set(e) != {"op", "doc", "origin", "side"}:
                raise ValueError("invalid new observation")
            if e["side"] not in ("SUPPORT", "ATTACK"):
                raise ValueError("unsupported polarity")
            records[doc] = {"origin": e["origin"], "side": e["side"],
                            "status": "VERIFIED" if op == "ACCEPT" else "PENDING"}
        else:
            if set(e) != {"op", "doc"} or doc not in records:
                raise ValueError("invalid existing observation")
            current = records[doc]
            if (op == "APPROVE" and current["status"] == "PENDING"):
                current["status"] = "VERIFIED"
            elif op == "REVOKE" and current["status"] == "VERIFIED":
                current["status"] = "REVOKED"
            else:
                raise ValueError("illegal evidence transition")
        positives = {r["origin"] for r in records.values() if r["status"] == "VERIFIED" and r["side"] == "SUPPORT"}
        negatives = {r["origin"] for r in records.values() if r["status"] == "VERIFIED" and r["side"] == "ATTACK"}
        trace.append({"state": state_from_bits(bool(positives), bool(negatives)),
                      "supporting_origins": sorted(positives), "opposing_origins": sorted(negatives)})
    return trace


def graph_trace(events: list[dict]) -> list[dict]:
    def prov(src: str, origin: str) -> Provenance:
        return Provenance(source_id=src, source_kind=SourceKind.EXTERNAL,
                          source_group=origin, reference=f"synthetic://{src}", observed_at=STAMP)
    graph = EpistemicGraph(method_version="challenge7", clock=lambda: STAMP)
    graph.add_node(Node("claim", NodeKind.CLAIM, "Synthetic claim P", prov("analyst", "analyst"), STAMP))
    trace=[]
    for e in events:
        op, doc = e["op"], e["doc"]
        if op in ("PENDING", "ACCEPT"):
            graph.add_node(Node(doc, NodeKind.EVIDENCE, f"Synthetic evidence {doc}", prov(doc,e["origin"]), STAMP))
            relation=EdgeKind.SUPPORTS if e["side"] == "SUPPORT" else EdgeKind.ATTACKS
            graph.add_edge(Edge("edge-"+doc, doc, "claim", relation, prov("analyst", "analyst"), graph.method_version, STAMP))
            if op == "ACCEPT":
                graph.set_validation("node",doc,Validation.VERIFIED,verified_by="reviewer",reason="synthetic approval")
                graph.set_validation("edge","edge-"+doc,Validation.VERIFIED,verified_by="reviewer",reason="synthetic relation approval")
        elif op == "APPROVE":
            graph.set_validation("node",doc,Validation.VERIFIED,verified_by="reviewer",reason="synthetic approval")
            graph.set_validation("edge","edge-"+doc,Validation.VERIFIED,verified_by="reviewer",reason="synthetic relation approval")
        elif op == "REVOKE":
            graph.set_validation("node",doc,Validation.REVOKED,verified_by="reviewer",reason="synthetic revocation")
        a=graph.assess("claim")
        trace.append({"state":a.state.value,"supporting_origins":sorted(a.support_sources),
                      "opposing_origins":sorted(a.attack_sources)})
    assert EpistemicGraph.from_dict(graph.to_dict()).assess("claim").state == graph.assess("claim").state
    return trace


def render_event(e: dict) -> str:
    if e["op"] in ("PENDING", "ACCEPT"):
        return f"{e['op']} report {e['doc']} from origin {e['origin']} on side {e['side']}"
    return f"{e['op']} report {e['doc']}"


def generate() -> tuple[dict, dict, dict]:
    original=json.loads((HERE/"episodes.json").read_text())
    if original["schema"]!="rei.challenge7.episodes.v1" or len(original["episodes"])!=6:
        raise ValueError("unexpected episode definition")
    cases=[]; answers=[]; audit=[]
    for ep in original["episodes"]:
        rows=ledger_trace(ep["events"])
        graphrows=graph_trace(ep["events"])
        if rows!=graphrows:
            raise AssertionError(f"REI and conventional ledger disagree: {ep['id']}")
        context=("Synthetic evidence records for claim P; use the rules exactly. "
                 "PENDING does not count; ACCEPT and APPROVE make a report active; "
                 "REVOKE removes only that report. Reports with the same origin are duplicate views "
                 "of one source, not additional independent sources. One active SUPPORT and one active ATTACK "
                 "produce BOTH even if many duplicate reports exist. Report the state at the END, "
                 "not the state before the last event.\n"+
                 "\n".join(f"{i}. {render_event(e)}" for i,e in enumerate(ep["events"],1)))
        cases.append({"id":ep["id"],"category":"revision_timeline", "context":context,
                      "question":"What is the FINAL recorded four-state evidence status of claim P? Reply EXACTLY one of NEITHER, SUPPORT_ONLY, ATTACK_ONLY, BOTH."})
        answers.append({"case_id":ep["id"],"acceptable":[rows[-1]["state"]],"unanswerable":False})
        audit.append({"case_id":ep["id"],"states_after_each_event":[x["state"] for x in rows],
                      "states_checked_against_original_rei_graph":True})
    return ({"schema":"rei0.benchmark.cases.v1","cases":cases},
            {"schema":"rei0.benchmark.keys.v1","answers":answers},
            {"schema":"rei.challenge7.oracle.v1","traces":audit})


def main() -> None:
    cases, keys, audit=generate()
    for name,payload in (("cases.json",cases),("keys.json",keys),("oracle_traces.json",audit)):
        (HERE/name).write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("Generated",len(cases["cases"]),"new dynamic cases; verified all event checkpoints against original REI graph")


if __name__=="__main__":
    main()