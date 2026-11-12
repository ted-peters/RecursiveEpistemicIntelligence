"""Challenge 9: paired evidence-revision *development* trial.

Two arms see the same signed-review public docket and use the same underlying
schema-constrained model. REI 1.2 alone selects whether to spend an additional
inquiry call; its controller's aggregate state is NEVER placed in the final
model prompt. This is a nonblind public development comparison, not a test of
real-world source truth or general AI superiority.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import random
import time
from typing import Any

from rei0.adaptive_engine import AdaptiveInquiryEngine
from rei0.authenticated_adaptive import AuthenticatedAdaptiveController
from rei0.benchmark import (
    BenchmarkError, Case as BenchmarkCase, Limits, Meter, InquiryBridge,
    _validate_stage,
)
from rei0.inquiry import InitialDraft, InquiryLimits, InquirySession, PendingQuestion
from rei0.models import (
    Edge, EdgeKind, Node, NodeKind, Provenance, SourceKind, digest,
)
from .interventions import (
    Case as DevelopmentCase, STAMP, STATES, generate_cases, replay_case,
)

ARMS = ("self_critique", "rei12")
SCHEMA = "rei.challenge9.paired_development.v1"
DEFAULT_LIMITS = Limits(
    max_calls=3, max_tokens=2600, max_seconds=140,
    max_output_tokens=320, steps=1,
)
QUESTION = (
    "Using ONLY the signed-review status of each independent source group, "
    "what is the current evidence state of fictional proposition P? "
    "Reply with exactly NEITHER, SUPPORT_ONLY, ATTACK_ONLY, or BOTH. "
    "PENDING, REVOKED and model-origin items do not count. "
    "Duplicated observations from one origin count once. "
    "A review signature authenticates admission, NOT objective truth."
)


def _model_case(source: DevelopmentCase, public: dict) -> BenchmarkCase:
    # The state label, independent oracle, and signed private key are absent.
    context = json.dumps(public, sort_keys=True, ensure_ascii=False)
    if len(context) > 3000:
        raise BenchmarkError("public docket too large")
    return BenchmarkCase(source.id, QUESTION, context, "signed_evidence_revision")


def _provisional_work(initial: InitialDraft, session: InquirySession) -> dict[str, Any]:
    """Never send private review keys or the controller's gold-equivalent state."""
    return {
        "initial_claim": initial.claim,
        "arguments": [n.text for n in session.graph.nodes.values()
                      if n.kind == NodeKind.ARGUMENT],
        "objections": [n.text for n in session.graph.nodes.values()
                       if n.kind == NodeKind.OBJECTION],
        "unresolved": [session.graph.nodes[q.id].text for q in session.queue],
        "investigated_steps": session.steps,
        "stop_reason": session.stop_reason,
    }


def _seed_inquiry(case: BenchmarkCase, ledger, initial: InitialDraft,
                  meter: Meter) -> InquirySession:
    """Seed the exact signed graph with provisional model questions.

    The model's proposed claim is never relabeled as independently verified:
    it is kept only as provisional reasoning text. Evidence receipts were
    created before model inference by the fixture authority, and the signer
    itself is not retained or accessible through the provider.
    """
    graph = ledger.graph
    if graph.method_version != "rei-0.2" or "P" not in graph.nodes:
        raise BenchmarkError("signed evidence graph cannot seed the inquiry")
    provenance = Provenance(
        "model-proposal", SourceKind.MODEL, "model-proposal",
        "model-output://challenge9/questions", STAMP,
    )
    queue = []
    for order, drafted in enumerate(initial.questions):
        qid = f"open_question-{1000 + order}"
        eid = f"question-link-{1000 + order}"
        graph.add_node(Node(qid, NodeKind.OPEN_QUESTION,
                            drafted.text, provenance, STAMP))
        graph.add_edge(Edge(eid, qid, "P", EdgeKind.QUESTIONS,
                            provenance, graph.method_version, STAMP))
        queue.append(PendingQuestion(qid, "P", 0, drafted.priority, order))
    return InquirySession(
        question=case.prompt(), root_id="P", graph=graph,
        queue=queue, next_id=2000, next_order=len(queue),
        steps=0, model_calls=1, tokens_used=meter.tokens,
        trace=[{
            "event": "challenge9_trusted_seed",
            "questions_created": len(queue),
            "initial_claim_is_provisional": True,
            "initial_tokens": meter.tokens,
            "signed_review_ledger_head": ledger.audit_head,
        }],
        stop_reason="seeded",
    )


def _run_one(case: DevelopmentCase, arm: str, provider, limits: Limits) -> dict:
    if arm not in ARMS:
        raise BenchmarkError("unknown challenge9 arm")
    # No reference key enters the model calls. Signer is ephemeral inside the
    # synthetic dossier builder; ledger accepts only authenticated receipts.
    audit, ledger = replay_case(case, return_ledger=True, inquiry_graph=True)
    common = _model_case(case, audit["public_docket"])
    meter = Meter(provider, common, arm, limits)
    output, error, method = None, None, {}
    started = time.monotonic()
    try:
        if arm == "self_critique":
            draft = meter.call("draft", {"question": common.prompt()}).payload
            critique = meter.call("critique", {
                "question": common.prompt(), "draft": draft,
            }).payload
            output = meter.call("final", {
                "question": common.prompt(),
                "trusted_docket": audit["public_docket"],
                "draft": draft, "critique": critique["critique"],
            }).payload
            method = {"algorithm": "draft_critique_revise"}
        else:
            initial = InitialDraft.parse(meter.call("initial", {
                "question": common.prompt(),
            }).payload)
            session = _seed_inquiry(common, ledger, initial, meter)
            ctrl = AuthenticatedAdaptiveController(
                ledger, min_score=22, reserve_tokens=320,
            )
            bridge = InquiryBridge(meter)
            engine = AdaptiveInquiryEngine(
                bridge,
                InquiryLimits(
                    max_steps=1, max_depth=2,
                    max_model_calls=limits.max_calls - 1,
                    max_tokens=limits.max_tokens,
                    max_seconds=limits.max_seconds,
                    max_output_tokens=limits.max_output_tokens,
                ),
                controller=ctrl,
                clock=lambda: STAMP, monotonic=meter.monotonic,
            )
            # After _seed_inquiry, the only possible model calls are
            # expansion and final. The independent graph and signed ledger
            # are shared by exact object identity.
            session = engine.run(resume=session)
            if session.stop_reason in (
                "model_error", "reported_token_overrun", "time_budget",
            ):
                raise BenchmarkError("adaptive inquiry stopped due to model failure")
            output = meter.call("final", {
                "question": common.prompt(),
                "trusted_docket": audit["public_docket"],
                "provisional_work": _provisional_work(initial, session),
            }).payload
            method = {
                "algorithm": "signed_review_selective_recursion",
                "steps": session.steps,
                "stop_reason": session.stop_reason,
                "trusted_ledger_head": ledger.audit_head,
                "graph_audit_head": session.graph.audit_head,
            }
    except (BenchmarkError, ValueError, TypeError, KeyError, OSError) as exc:
        error = f"{type(exc).__name__}: {str(exc)[:140]}"
    return {
        "case_id": case.id, "arm": arm,
        "answer": output["answer"] if output else None,
        "confidence": output["confidence"] if output else None,
        "rationale": output["rationale"] if output else None,
        "error": error, "model_calls": meter.calls,
        "meter_reported_tokens": meter.tokens,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "trace": meter.trace, "method": method,
    }


def _summary(outcomes: list[dict], cases: tuple[DevelopmentCase, ...]) -> dict:
    key = {c.id: c.expected for c in cases}
    summary = {}
    for arm in ARMS:
        rows = [x for x in outcomes if x["arm"] == arm]
        if len(rows) != len(cases):
            raise BenchmarkError("missing arm outcomes")
        correct = sum(
            x["error"] is None and x["answer"] == key[x["case_id"]]
            for x in rows
        )
        summary[arm] = {
            "correct": correct, "cases": len(rows),
            "accuracy": correct / len(rows),
            "failed": sum(x["error"] is not None for x in rows),
            "abstained": sum(x["error"] is None and x["answer"] is None
                             for x in rows),
            "model_calls": sum(x["model_calls"] for x in rows),
            "meter_reported_tokens": sum(x["meter_reported_tokens"] for x in rows),
            "total_elapsed_seconds": round(sum(x["elapsed_seconds"] for x in rows), 3),
        }
    ids = sorted(key)
    paired = []
    discordant = {"rei_only_correct":0,"self_critique_only_correct":0}
    for cid in ids:
        a = next(x for x in outcomes if x["case_id"] == cid and x["arm"] == "rei12")
        b = next(x for x in outcomes if x["case_id"] == cid and x["arm"] == "self_critique")
        ac = a["error"] is None and a["answer"] == key[cid]
        bc = b["error"] is None and b["answer"] == key[cid]
        paired.append(int(ac)-int(bc))
        if ac and not bc:
            discordant["rei_only_correct"] += 1
        if bc and not ac:
            discordant["self_critique_only_correct"] += 1
    return {
        "arms": summary,
        "primary_rei_minus_self_critique": {
            "paired_accuracy_difference": sum(paired)/len(paired),
            "cases": len(paired),
            **discordant,
            "compute_matched": False,
        },
    }


def run_trial(provider, *, seed: int = 20261111,
              count: int = 4, limits: Limits = DEFAULT_LIMITS) -> dict:
    """Only invokes a live model when the caller supplies a live provider."""
    cases = generate_cases(seed=seed, count=count)
    if not hasattr(provider, "kind") or not hasattr(provider, "respond"):
        raise BenchmarkError("provider must implement respond and declare kind")
    tasks = [(case, arm) for case in cases for arm in ARMS]
    random.Random(seed).shuffle(tasks)
    results = [_run_one(case, arm, provider, limits) for case, arm in tasks]
    results.sort(key=lambda row:(row["case_id"], ARMS.index(row["arm"])))
    calculated = _summary(results, cases)
    attempts = getattr(provider, "attempts", None)
    attempt_metrics = None
    if isinstance(attempts, list):
        attempt_metrics = {}
        for arm in ARMS:
            rows = [x for x in attempts if x["arm"] == arm]
            known = [x["reported_tokens_even_if_failed"] for x in rows
                     if x.get("reported_tokens_even_if_failed") is not None]
            attempt_metrics[arm] = {
                "attempts": len(rows),
                "server_reported_tokens_including_failed_parses": sum(known),
                "unknown_usage_calls": len(rows) - len(known),
                "provider_failed_calls": sum(x["status"] == "failed" for x in rows),
            }
    payload = {
        "schema": SCHEMA,
        "mode": provider.kind,
        "model_fingerprint": getattr(provider, "fingerprint", None),
        "study_kind": "public_nonblind_signed_review_development_not_compute_matched",
        "seed": seed, "case_count": count,
        "case_set_digest": digest([{"id":c.id, "events": list(c.events)} for c in cases]),
        "key_digest": digest({c.id:c.expected for c in cases}),
        "budgets": asdict(limits),
        "outcomes": results,
        "summary": calculated,
        "attempt_usage": attempt_metrics,
        "warnings": [
            "These are PUBLIC synthetic development cases, not a blind independent holdout.",
            "Both arms receive the same signed-status docket, but use different reasoning protocols.",
            "Equal budget ceilings do not mean identical consumed tokens or elapsed time.",
            "Unknown provider token consumption is not free computation.",
            "Signed review receipts authenticate admissions, not objective source truth.",
            "Case IDs and public source generator may permit task familiarity or leakage.",
            "A successful software audit does not establish model capability or superiority.",
        ],
    }
    return {**payload, "report_sha256": digest(payload)}


def verify_trial(report: dict, *, seed: int, count: int) -> dict:
    cases = generate_cases(seed=seed, count=count)
    if not isinstance(report, dict):
        raise BenchmarkError("report must be JSON object")
    payload = {k:v for k,v in report.items() if k != "report_sha256"}
    if digest(payload) != report.get("report_sha256"):
        raise BenchmarkError("report checksum mismatch")
    if report.get("schema") != SCHEMA or report.get("seed") != seed or report.get("case_count") != count:
        raise BenchmarkError("report schema or run parameters differ")
    if report.get("case_set_digest") != digest(
        [{"id":c.id,"events":list(c.events)} for c in cases]
    ) or report.get("key_digest") != digest({c.id:c.expected for c in cases}):
        raise BenchmarkError("dataset digest differs")
    rows = report.get("outcomes")
    if not isinstance(rows, list) or len(rows) != len(cases)*len(ARMS):
        raise BenchmarkError("incomplete paired outcome report")
    expected = {(c.id,arm) for c in cases for arm in ARMS}
    if {(r["case_id"],r["arm"]) for r in rows} != expected:
        raise BenchmarkError("missing or unknown case/arm pair")
    if len({(r["case_id"],r["arm"]) for r in rows}) != len(rows):
        raise BenchmarkError("duplicate outcome pair")
    if _summary(rows,cases) != report.get("summary"):
        raise BenchmarkError("graded summary differs from recorded answers")
    return {
        "valid":True,"cases":count,"outcomes":len(rows),
        "report_sha256":report["report_sha256"],
        "warning":"Consistency check only; not authenticated inference attestation",
    }
