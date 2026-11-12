"""Challenge 9: an independent, *synthetic* signed-evidence intervention harness.

This evaluates evidence-admission correctness, not language-model reasoning.
A separate reference reducer computes the expected states from the event
semantics. The REI EvidenceLedger must match at every checkpoint. Reviews are
signed with a new ephemeral Ed25519 key, NEVER provided to any model or saved.
The development cases and their expected results are public, not blind data.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import random
from typing import Any

from rei0.evidence import EvidenceLedger
from rei0.graph import EpistemicGraph
from rei0.models import (
    EdgeKind, Node, NodeKind, Provenance, SourceKind, Validation, digest,
)
from rei0.review import (
    Ed25519ReviewIssuer, Ed25519TrustedReviewer, VerificationBoundary,
)

SCHEMA = "rei.challenge9.signed_interventions.v1"
REPORT_SCHEMA = "rei.challenge9.intervention_audit.v1"
STAMP = "2026-11-11T00:00:00Z"
STATES = ("NEITHER", "SUPPORT_ONLY", "ATTACK_ONLY", "BOTH")
POLARITIES = {"SUPPORT": EdgeKind.SUPPORTS, "ATTACK": EdgeKind.ATTACKS}


class Challenge9Error(ValueError):
    """Malformed development event, mismatched reference, or failed review."""


@dataclass(frozen=True)
class Case:
    id: str
    expected: str
    events: tuple[dict[str, Any], ...]


def generate_cases(seed: int = 20261111, count: int = 12) -> tuple[Case, ...]:
    """Generate 3 cases per final state by default; no LLM is consulted."""
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise Challenge9Error("invalid seed")
    if type(count) is not int or count < 4 or count > 100 or count % 4:
        raise Challenge9Error("count must be divisible by four, from 4 to 100")
    rng = random.Random(seed)
    cases = []
    for i in range(count):
        target = STATES[i % 4]
        prefix = f"c9-{i+1:02d}"
        records = [
            {"op": "SUBMIT", "doc": "A", "origin": prefix+"-alpha",
             "side": "SUPPORT", "kind": "external"},
            {"op": "SUBMIT", "doc": "B", "origin": prefix+"-alpha",
             "side": "SUPPORT", "kind": "external"},
            {"op": "SUBMIT", "doc": "C", "origin": prefix+"-beta",
             "side": "ATTACK", "kind": "external"},
            {"op": "SUBMIT", "doc": "D", "origin": prefix+"-gamma",
             "side": "ATTACK", "kind": "external"},
            {"op": "SUBMIT", "doc": "M", "origin": prefix+"-model",
             "side": "SUPPORT", "kind": "model"},
        ]
        rng.shuffle(records)
        events = records + [
            {"op": "VERIFY", "doc": "A"},
            {"op": "VERIFY", "doc": "B"},
            {"op": "VERIFY", "doc": "C"},
            # Forged review assertions are deliberately NOT trusted decisions.
            {"op": "FORGE", "doc": "D"},
            {"op": "FORGE", "doc": "M"},
            {"op": "REVOKE", "doc": "B"},
        ]
        updates = []
        if target in ("NEITHER", "ATTACK_ONLY"):
            updates.append({"op": "REVOKE", "doc": "A"})
        if target in ("NEITHER", "SUPPORT_ONLY"):
            updates.append({"op": "REVOKE", "doc": "C"})
        rng.shuffle(updates)
        events.extend(updates)
        assert oracle_trace(events)[-1] == target
        cases.append(Case(prefix, target, tuple(events)))
    return tuple(cases)


def oracle_trace(events: list[dict] | tuple[dict, ...]) -> list[str]:
    """Pure reference reducer independent of REI's graph and crypto code."""
    docs: dict[str, dict] = {}
    trace = []
    for event in events:
        if not isinstance(event, dict):
            raise Challenge9Error("event must be object")
        op, doc = event.get("op"), event.get("doc")
        if not isinstance(doc, str) or not doc:
            raise Challenge9Error("invalid document ID")
        if op == "SUBMIT":
            if set(event) != {"op", "doc", "origin", "side", "kind"} or doc in docs:
                raise Challenge9Error("invalid or duplicate submission")
            if event["side"] not in POLARITIES or event["kind"] not in ("external", "model"):
                raise Challenge9Error("invalid side or origin kind")
            if not isinstance(event["origin"], str) or not event["origin"]:
                raise Challenge9Error("invalid source group")
            docs[doc] = {"side": event["side"], "origin": event["origin"],
                         "kind": event["kind"], "status": "PENDING"}
        elif op in ("VERIFY", "REVOKE", "FORGE"):
            if set(event) != {"op", "doc"} or doc not in docs:
                raise Challenge9Error("mutation on missing document")
            row = docs[doc]
            if op == "VERIFY":
                if row["status"] != "PENDING" or row["kind"] == "model":
                    raise Challenge9Error("cannot approve missing, reviewed or model document")
                row["status"] = "VERIFIED"
            elif op == "REVOKE":
                if row["status"] != "VERIFIED":
                    raise Challenge9Error("only signed-verification can be revoked")
                row["status"] = "REVOKED"
            else:
                if row["status"] != "PENDING":
                    raise Challenge9Error("forgery fixture must target pending evidence")
                # A forged string is an event in a log, not a review decision.
        else:
            raise Challenge9Error("unrecognized event operation")
        support = {r["origin"] for r in docs.values()
                   if r["status"] == "VERIFIED" and r["side"] == "SUPPORT"}
        attack = {r["origin"] for r in docs.values()
                  if r["status"] == "VERIFIED" and r["side"] == "ATTACK"}
        trace.append({
            (False, False): "NEITHER", (True, False): "SUPPORT_ONLY",
            (False, True): "ATTACK_ONLY", (True, True): "BOTH",
        }[(bool(support), bool(attack))])
    return trace


def public_docket(ledger: EvidenceLedger) -> dict[str, Any]:
    """A shared, sanitized evidence view for future *both-arm* model trials.

    It deliberately excludes the aggregate evidence-state label, the oracle,
    model answer keys, private signing keys and cryptographic key material.
    """
    ledger.assess("P")  # Signature verification fails closed.
    status = {r.submission_id: "PENDING" for r in ledger.submissions}
    for receipt in ledger.review_receipts:
        status[receipt.submission_id] = receipt.decision.value.upper()
    rows = []
    for submission in ledger.submissions:
        n = ledger.graph.nodes[submission.evidence_id]
        edge = ledger.graph.edges[submission.link_id]
        rows.append({
            "id": submission.submission_id,
            "origin_group": n.provenance.source_group,
            "source_kind": n.provenance.source_kind.value,
            "side": "SUPPORT" if edge.kind == EdgeKind.SUPPORTS else "ATTACK",
            "signed_review_status": status[submission.submission_id],
        })
    return {
        "claim": "Fictional proposition P",
        "review_policy": "Only current trusted signed reviews count; group duplicates by origin.",
        "evidence": sorted(rows, key=lambda x: x["id"]),
    }


def replay_case(case: Case, *, return_ledger: bool = False,
                inquiry_graph: bool = False):
    """Run a synthetic case; optionally return its PUBLIC-VERIFIER-only ledger.

    An ephemeral private signer is used only while constructing the fixture.
    No private key or signer object is returned to the model trial.
    """
    if not isinstance(case, Case) or case.expected not in STATES:
        raise Challenge9Error("invalid synthetic case")
    expected = oracle_trace(case.events)
    if expected[-1] != case.expected:
        raise Challenge9Error("case oracle and declared final state disagree")
    signer = Ed25519ReviewIssuer.generate("challenge9-ephemeral", "independent-fixture-reviewer")
    boundary = VerificationBoundary({
        "challenge9-ephemeral": Ed25519TrustedReviewer(
            "independent-fixture-reviewer", signer.public_key_bytes()),
    })
    graph = EpistemicGraph("rei-0.2" if inquiry_graph else "challenge9-signed-development",
                           max_nodes=64, max_edges=64, clock=lambda: STAMP)
    graph.add_node(Node("P", NodeKind.CLAIM, "Fictional proposition P",
                        Provenance("author", SourceKind.HUMAN, "question",
                                   "synthetic://challenge9/claim", STAMP), STAMP))
    ledger = EvidenceLedger(graph, boundary, clock=lambda: STAMP)
    observed: list[str] = []
    forged: int = 0
    for index, event in enumerate(case.events):
        op, doc = event["op"], event["doc"]
        if op == "SUBMIT":
            ledger.submit(
                submission_id=doc, evidence_id="e:" + doc, claim_id="P",
                text="Fictional report " + case.id + " " + doc,
                artifact_bytes=("synthetic artifact "+case.id+" "+doc).encode("utf-8"),
                provenance=Provenance(
                    case.id + ":" + doc,
                    SourceKind.EXTERNAL if event["kind"] == "external" else SourceKind.MODEL,
                    event["origin"], "synthetic://" + case.id + "/" + doc, STAMP,
                ), polarity=POLARITIES[event["side"]],
            )
        elif op in ("VERIFY", "REVOKE"):
            history = [r for r in ledger.review_receipts if r.submission_id == doc]
            receipt = signer.issue(
                submission_id=doc, subject_digest=ledger.subject_digest(doc),
                decision=Validation.VERIFIED if op == "VERIFY" else Validation.REVOKED,
                reason="synthetic fixture reviewed, not factual authentication",
                issued_at=STAMP, decision_index=len(history)+1,
                prior_signature=history[-1].signature if history else "0"*64,
            )
            ledger.accept(receipt)
        elif op == "FORGE":
            # Intentionally exercise unsafe legacy labels, which must not
            # influence the signed ledger's trusted evidence assessment.
            forged += 1
            graph.set_validation("node", "e:" + doc, Validation.VERIFIED,
                                 verified_by="untrusted-label", reason="synthetic forgery")
            graph.set_validation("edge", "evidence-link:e:" + doc,
                                 Validation.VERIFIED, verified_by="untrusted-label",
                                 reason="synthetic forgery")
        else:
            raise Challenge9Error("invalid operation")
        actual = ledger.assess("P").state.value
        if actual != expected[index]:
            raise Challenge9Error("signed ledger disagrees with independent oracle")
        observed.append(actual)

    restored = EvidenceLedger.from_dict(ledger.to_dict(), boundary, clock=lambda: STAMP)
    if restored.assess("P").state.value != case.expected:
        raise Challenge9Error("signed replay and original state differ")
    public = public_docket(restored)
    if "expected" in json.dumps(public).lower() or "oracle" in json.dumps(public).lower():
        raise Challenge9Error("public docket contains prohibited fields")
    result = {
        "case_id": case.id,
        "events": len(case.events),
        "forged_assertions": forged,
        "signed_receipts": len(restored.review_receipts),
        "states": observed,
        "final_state": observed[-1],
        "unsafe_legacy_graph_state": restored.graph.assess("P").state.value,
        "public_docket": public,
        "signed_audit_head": restored.audit_head,
        "graph_audit_head": restored.graph.audit_head,
    }
    return (result, restored) if return_ledger else result


def audit(seed: int = 20261111, count: int = 12) -> dict[str, Any]:
    cases = generate_cases(seed=seed, count=count)
    results = [replay_case(c) for c in cases]
    counts = Counter(r["final_state"] for r in results)
    summary = {
        "cases": count,
        "signed_checkpoints_validated": sum(r["events"] for r in results),
        "signed_receipts": sum(r["signed_receipts"] for r in results),
        "forged_review_assertions_ignored": sum(r["forged_assertions"] for r in results),
        "final_state_counts": {s: counts[s] for s in STATES},
        "independent_oracle_agreement": count,
        "legacy_graph_disagrees_with_signed_ledger": sum(
            r["unsafe_legacy_graph_state"] != r["final_state"] for r in results),
        "live_model_inference_calls": 0,
    }
    payload = {
        "schema": REPORT_SCHEMA,
        "study_kind": "public_synthetic_software_validation_not_blinded_model_performance",
        "seed": seed,
        "case_set_digest": digest([{"id":c.id, "events": list(c.events)} for c in cases]),
        "summary": summary,
        # Avoid publishing ephemeral signer seeds or using hashes as authenticity proof.
        "warnings": [
            "Ephemeral Ed25519 signatures attest synthetic review decisions, not factual truth.",
            "The original REI graph's unauthenticated validation labels are intentionally untrusted.",
            "No language model was tested; no accuracy/cost advantage is established.",
            "All development cases are public and are not a blind model holdout.",
            "Review signatures and audit heads require external trust anchors in production.",
        ],
    }
    return {**payload, "report_sha256": digest(payload)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seed", type=int, default=20261111)
    p.add_argument("--count", type=int, default=12)
    p.add_argument("--output", type=Path)
    args = p.parse_args(argv)
    result = audit(args.seed, args.count)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
