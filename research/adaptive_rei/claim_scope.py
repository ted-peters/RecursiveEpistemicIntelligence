"""Experimental one-call verdict from an explicit claim and evidence comparison."""
from adaptive_rei_benchmark import predict

INSTRUCTION = (
    "Use the passage only. Return JSON in this order: target (what the question asks, "
    "under ten words), established (what the evidence establishes, under fifteen words), "
    "relation (supports, contradicts, or unresolved). Match subject, time and scope. "
    "A record can prove what was documented without proving what happened. "
    "An observed event can establish what happened without proving it was documented. "
    "If both yes and no are compatible with the facts, use unresolved."
)


def decide(url, model, passage):
    result, tokens = predict(url, model, INSTRUCTION, passage, max_tokens=120)
    answer = {"supports": "yes", "contradicts": "no", "unresolved": "uncertain"}.get(result.get("relation")) if isinstance(result.get("relation"), str) else None
    return {"target": result.get("target"), "established": result.get("established"),
            "relation": result.get("relation"), "answer": answer}, tokens
