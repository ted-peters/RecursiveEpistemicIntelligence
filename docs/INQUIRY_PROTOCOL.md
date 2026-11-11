# REI-0.2 — Inquiry Protocol and Checkpoint Contract

## Intent

This document specifies the bounded recursion layer built on REI-0 v0.1. It is a computational approximation to philosophical justificatory openness, **not** an implementation of actual infinite computation.

## Model output schemas (exact keys)

Initial generation:

```json
{
  "claim": "Provisional proposition, <= 800 characters",
  "questions": [
    {"text": "Why trust this premise?", "target": "claim", "priority": 8}
  ]
}
```

- `questions`: 1–4 items, `text` at most 400 characters, target `claim` only.
- `priority`: integer 0–10, default 5; this is an *untrusted* scheduling suggestion.

Challenge expansion:

```json
{
  "reasons": ["A tentative reason, not externally verified evidence"],
  "objections": ["An objection to the currently targeted proposition"],
  "followups": [
    {"text": "Why is that reason adequate?", "target": "reason", "priority": 9}
  ],
  "note": "Brief account of what this expansion attempted"
}
```

- `reasons` and `objections`: 0–3 strings each, 600-character maximum per item.
- `followups`: 0–4 items. The `target` is either the challenged `claim` (meaning current target) or the **first new** `reason` created in that expansion.
- `note`: non-empty string at most 600 characters.
- Unknown top-level or nested keys, wrong types, out-of-range numeric fields, invalid references, and excessive list sizes are rejected; code is never executed.
- A payload containing no reasons, objections, or followups stops with `no_progress` and does not mark the question explored.

## Model adapter interface

```python
initial(question: str, *, max_output_tokens: int, timeout: float) -> ModelTurn
expand(context: dict, *, ordinal: int, max_output_tokens: int, timeout: float) -> ModelTurn
```

`ModelTurn` contains `payload: dict` and `tokens_used: nonnegative int`. Scripted fixtures supply explicit token counts. The HTTPS adapter uses provider-reported `total_tokens` when present and otherwise accounts for at least the requested output cap. Actual provider billing may differ. No model is allowed to grant verification authority to its own output.

## Graph mapping

| Model artifact | Node | Relation | Admissibility |
|---|---|---|---|
| Initial proposition | `claim` | root | pending, model-origin |
| Supporting argument | `argument` | `supports` -> current claim/argument | pending, model-origin |
| Objection | `objection` | `attacks` -> current claim/argument | pending, model-origin |
| Recursive question | `open_question` | `questions` -> current claim/argument | pending, model-origin |

`questions` is a new typed edge, and `explore_question` is a new event that marks investigation without asserting final resolution. `open_questions()` excludes investigated workflow tasks but retains deeper or otherwise unprocessed questions. The cycle detector still applies only to justificatory dependency (`supports` and `depends_on`) relations. The evidence ledger still ignores model-origin arguments and objections.

## Controller and stopping

The controller sorts *eligible* open questions by descending priority, then increasing depth, then insertion order. A challenge is eligible only if `depth < max_depth`. The generated followups have `depth = parent_depth + 1`.

- `frontier_exhausted`: no pending question remains in the current work queue.
- `step_budget`: `steps >= max_steps` while questions remain.
- `depth_budget`: remaining questions are all at or beyond the configured depth limit.
- `model_call_budget`: maximum provider/script calls reached, counting the initial call.
- `token_budget`: no remaining reported-token allowance before a model call.
- `reported_token_overrun`: provider/script reported more tokens than remaining; discard response, keep question open.
- `time_budget`: remaining time expired before or after a call; discard late response, keep question open.
- `graph_budget` or `question_budget`: projected addition exceeds a configured bound; do not incorporate that expansion.
- `model_error`: invalid JSON payload, scripted exhaustion, or provider error; keep question open and emit error type, not provider response bodies.
- `no_progress`: model provided no examinable content; keep question open.

When any nonempty frontier survives, this is a **suspension**, not a philosophical determination that its claims are fully justified. `frontier_exhausted` similarly means only that the current finite generation process has no additional work to schedule.

## Checkpoint format

`rei0.inquiry.v1` checkpoints store:

- Root input and generated claim identifier;
- Full replayable graph events and method version;
- Pending question IDs, targets, depths, priorities, and insertion order;
- Cumulative step, model-call, token, and ID counters;
- Trace events and stop reason;
- SHA-256 checksum over the canonical JSON payload.

On load, the graph event chain is replayed, the checksum recomputed, and the queue checked against the graph's unresolved questions, including question-target relation existence. The checkpoint is **not cryptographically authenticated**. Anyone with full file access can replace the file and recompute both hashes. For adversarial deployments, use signed records and an independent trust boundary.

## Deterministic replay

The `ScriptedAdapter` returns `responses[ordinal]`, where `ordinal` is the cumulative number of successful investigated questions. With an identical script, limits, and fixed injected UTC clock, stopping and resuming yields the same graph and checkpoint state as one uninterrupted execution. The CLI uses real UTC timestamps; it does not claim bit-for-bit reproducibility across different wall-clock invocations.

## Non-goals for v0.2

This release has no web search, real-world evidence authentication, independent critic grading, method-version promotion, protected evaluation sets, calibrated confidence scores, or safe autonomous tool access. Model-produced content is deliberately never promoted to evidence by this engine.
