"""Deterministic 24-case synthetic timeline generator; public DEV SET, not blind.

The expected four-state answer is independently computed both by a direct
provenance ledger and the original REI-1.0 graph. No model is used to grade.
"""
from __future__ import annotations

import json
from pathlib import Path
import random
from rei0.graph import EpistemicGraph
from rei0.models import Edge, EdgeKind, Node, NodeKind, Provenance, SourceKind, Validation

HOME = Path(__file__).resolve().parent
STAMP = "2026-11-11T00:00:00Z"
STATES = ("NEITHER", "SUPPORT_ONLY", "ATTACK_ONLY", "BOTH")


def direct_trace(events: list[dict]) -> list[str]:
    ledger = {}
    trace = []
    for e in events:
        op, doc = e["op"], e["doc"]
        if op in ("ACCEPT", "PENDING"):
            if doc in ledger or set(e) != {"op", "doc", "origin", "side"}:
                raise ValueError("illegal document creation")
            if e["side"] not in ("SUPPORT", "ATTACK"):
                raise ValueError("invalid polarity")
            ledger[doc] = dict(origin=e["origin"], side=e["side"],
                               active=op=="ACCEPT", status=op)
        elif op in ("REVOKE", "APPROVE"):
            if doc not in ledger or set(e) != {"op", "doc"}:
                raise ValueError("unknown or malformed mutation")
            item = ledger[doc]
            if op=="REVOKE" and item["status"]=="ACCEPT":
                item.update(active=False,status="REVOKED")
            elif op=="APPROVE" and item["status"]=="PENDING":
                item.update(active=True,status="ACCEPT")
            else:
                raise ValueError("illegal status transition")
        else:
            raise ValueError("invalid operation")
        plus = {r["origin"] for r in ledger.values() if r["active"] and r["side"]=="SUPPORT"}
        minus = {r["origin"] for r in ledger.values() if r["active"] and r["side"]=="ATTACK"}
        trace.append({(False,False):"NEITHER",(True,False):"SUPPORT_ONLY",
                      (False,True):"ATTACK_ONLY",(True,True):"BOTH"}[(bool(plus),bool(minus))])
    return trace


def rei_trace(events: list[dict]) -> list[str]:
    def prov(doc, group):
        return Provenance(source_id=doc,source_kind=SourceKind.EXTERNAL,
                          source_group=group,reference="synthetic://"+doc,observed_at=STAMP)
    graph=EpistemicGraph(method_version="challenge8-scaled",clock=lambda: STAMP)
    graph.add_node(Node("P",NodeKind.CLAIM,"Fictional claim P",prov("owner","owner"),STAMP))
    trace=[]
    for event in events:
        op,doc=event["op"],event["doc"]
        if op in ("ACCEPT","PENDING"):
            graph.add_node(Node(doc,NodeKind.EVIDENCE,"Fictional report "+doc,
                                prov(doc,event["origin"]),STAMP))
            graph.add_edge(Edge("e-"+doc,doc,"P",EdgeKind.SUPPORTS if event["side"]=="SUPPORT"
                                else EdgeKind.ATTACKS,prov("analyst","analyst"),graph.method_version,STAMP))
            if op=="ACCEPT":
                graph.set_validation("node",doc,Validation.VERIFIED,verified_by="script",reason="synthetic")
                graph.set_validation("edge","e-"+doc,Validation.VERIFIED,verified_by="script",reason="synthetic")
        elif op == "APPROVE":
            graph.set_validation("node",doc,Validation.VERIFIED,verified_by="script",reason="synthetic")
            graph.set_validation("edge","e-"+doc,Validation.VERIFIED,verified_by="script",reason="synthetic")
        elif op == "REVOKE":
            graph.set_validation("node",doc,Validation.REVOKED,verified_by="script",reason="synthetic")
        trace.append(graph.assess("P").state.value)
    restored=EpistemicGraph.from_dict(graph.to_dict())
    assert restored.assess("P").state == graph.assess("P").state
    return trace


def render(e):
    if e["op"] in ("PENDING","ACCEPT"):
        return f"{e['op']} report {e['doc']} from origin {e['origin']} on side {e['side']}"
    return f"{e['op']} report {e['doc']}"


def generate(seed=20261111):
    rand=random.Random(seed)
    cases=[]; keys=[]; audits=[]
    for i in range(24):
        target=STATES[i % 4]
        events=[]
        base=[
            {"op":"ACCEPT","doc":"D1","origin":f"study-{i:02d}-alpha","side":"SUPPORT"},
            {"op":"ACCEPT","doc":"D2","origin":f"study-{i:02d}-alpha","side":"SUPPORT"},
            {"op":"ACCEPT","doc":"D3","origin":f"study-{i:02d}-beta","side":"ATTACK"},
            {"op":"PENDING","doc":"D4","origin":f"study-{i:02d}-gamma","side":"ATTACK"},
            {"op":"PENDING","doc":"D5","origin":f"study-{i:02d}-delta","side":"SUPPORT"},
        ]
        rand.shuffle(base)
        events.extend(base)
        approvals=[{"op":"APPROVE","doc":doc} for doc in ("D4","D5") if rand.random()<0.7]
        rand.shuffle(approvals)
        events.extend(approvals)
        # One duplicate is always revoked. This should NOT erase its original source.
        events.append({"op":"REVOKE","doc":"D2"})
        live={e["doc"]:dict(status=e["op"],side=e["side"]) for e in base}
        for a in approvals:live[a["doc"]]["status"]="ACCEPT"
        live["D2"]["status"]="REVOKED"
        want_s=target in ("SUPPORT_ONLY","BOTH")
        want_a=target in ("ATTACK_ONLY","BOTH")
        revoke=[]
        for doc,row in live.items():
            if row["status"]=="ACCEPT" and ((row["side"]=="SUPPORT" and not want_s)
                or (row["side"]=="ATTACK" and not want_a)):
                revoke.append({"op":"REVOKE","doc":doc})
        rand.shuffle(revoke)
        events.extend(revoke)
        direct=direct_trace(events)
        actual=rei_trace(events)
        if direct!=actual or direct[-1]!=target:
            raise AssertionError(f"incorrect oracle: {i}: {direct} != {actual} target {target}")
        cid=f"c8-{i+1:02d}-timeline"
        context=("Fictional chronological records for claim P. PENDING evidence does not count. "
                 "ACCEPT/APPROVE activate a report; REVOKE deactivates only that report. "
                 "Same-origin reports are duplicated observations of one source. "
                 "The state is NEITHER (neither side active), SUPPORT_ONLY (only support), "
                 "ATTACK_ONLY (only opposition), or BOTH (support and opposition). "
                 "Determine the status after ALL events, not after an earlier line.\n"
                 +"\n".join(f"{j}. {render(e)}" for j,e in enumerate(events,1)))
        cases.append({"id":cid,"category":"revision_timeline","context":context,
                      "question":"What is the FINAL recorded evidence state of P? Answer exactly NEITHER, SUPPORT_ONLY, ATTACK_ONLY, or BOTH."})
        keys.append({"case_id":cid,"acceptable":[target],"unanswerable":False})
        audits.append({"case_id":cid,"events":events,"states_after_each_event":direct,
                       "matches_original_rei_graph": True})
    return ({"schema":"rei0.benchmark.cases.v1","cases":cases},
            {"schema":"rei0.benchmark.keys.v1","answers":keys},
            {"schema":"rei.challenge8.oracle.v1","traces":audits})


def main():
    c,k,a=generate()
    for filename,payload in (("scaled_cases.json",c),("scaled_keys.json",k),("scaled_audit.json",a)):
        format_options = {"separators": (",", ":")} if filename=="scaled_audit.json" else {"indent": 2}
        (HOME/filename).write_text(json.dumps(payload,ensure_ascii=False,**format_options)+"\n")
    print("Generated",len(c["cases"]),"synthetic cases; 24/24 graph and conventional ledger checks pass")


if __name__=="__main__":main()