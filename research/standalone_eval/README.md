# Standalone REI — Direct vs inquiry: public development quality gate

**Purpose:** The REI standalone application already passes a real Ollama + Qwen
smoke test, but a working model does not establish that its REI inquiry
scaffold improves answers. This first *quality gate* compares end-user
objective answers from the very same local open-weight model with and without
the REI recursive inquiry controller.

## Frozen protocol (before real inference)

- Six public, manually authored, unambiguous, multiple-choice prompts in
  [cases.json](cases.json), with one correct A/B/C/D choice each. The
  questions cover conditional probability, logical implication, a median,
  causal evidence, percentage arithmetic and digital signature semantics.
  This is **not an independent blinded benchmark** or a representative
  distribution of real work. The cases are frozen before running real Qwen.
- Both modes use the **identical local Qwen3 4B model tag**, at zero
  sampling temperature; the exact Ollama digest seen at run time is
  archived because registry tags can change.
- Direct mode uses one model call, giving it the user question as a
  conversation. REI mode invokes the actual bounded recursive
  `InquiryEngine`, builds a provisional challenge/objection graph, then
  has the same model synthesize a final reply. The final answer is
  scored by the exact same rule.
- Only the user-visible question and common formatting instruction are
  passed into either mode. The hidden answer key, case ID, domain and
  summary metrics **never** enter the model context.
- Both arms are tested for **all six cases**. To reduce order bias, the
  first arm alternates: direct first on even-numbered cases, REI first on
  odd-numbered cases. It is not a randomized multi-seed robustness test.
- Require the final, nonblank output line to be exactly `Answer: X`, where
  X is a single letter A–D, optionally with a trailing period. Unparseable
  format counts as incorrect. No language-model judge is involved.
- Always report per-arm correctness, invalid final-answer format counts,
  actual failed requests, model calls, **server-reported** total tokens,
  missing-usage calls and measured elapsed wall time. Failed requests
  count as incorrect; if a failed request consumed unreported tokens,
  the report marks those calls as unknown instead of inventing zero cost.
- An independent grader reopens the frozen keys, reconstructs paired
  order, checks case-set and report hashes, recomputes answer grades,
  re-aggregates model token accounting, and refuses mismatches.
- The fixture mode merely tests this machinery with a scripted fake and
  is never an AI performance result. The live mode genuinely calls Ollama.

## Limitations and interpretation

Six easy multiple-choice questions cannot establish broad reasoning
superiority. Both methods may achieve 6/6, in which case the simpler
Direct mode is substantially more efficient. Conversely, a REI win on
one or two examples would be exploratory and not statistically persuasive.

**This comparison is NOT compute-matched.** REI is permitted up to three
inquiry calls plus one synthesis call per question; Direct receives one
call. It is impossible to attribute performance differences exclusively
to the recursive graph without equally budgeted self-critique and a
stronger conventional reasoning-controller baseline. REI's graph nodes
remain unverified, and the evaluator does not check natural-language
explanation quality, real citations or complex multi-turn performance.

This is one reliability and regression gate for a standalone REI-powered
application. It does not prove an independently trained REI foundation
model or autonomous capability.

## Reproduction

From the research branch, with Python 3.10+ and REI installed:

```bash
python -m unittest discover -s tests -p test_standalone_quality_gate.py -v

# FAKE fixture — no model call; checks scorer, pair ordering and report replay:
python -m research.standalone_eval.paired_quality \
  --kind fixture --count 6 --output /tmp/rei-quality-fixture.json
python -m research.standalone_eval.paired_quality \
  --count 6 --verify-only --output /tmp/rei-quality-fixture.json

# REAL inference — Ollama and qwen3:4b-instruct must already be installed:
python -m research.standalone_eval.paired_quality \
  --kind live --count 6 --model qwen3:4b-instruct \
  --output /tmp/rei-quality-real.json
python -m research.standalone_eval.paired_quality \
  --count 6 --verify-only --output /tmp/rei-quality-real.json
```

Offline quality and full REI regression CI:
[standalone-quality-gates.yml](../../.github/workflows/standalone-quality-gates.yml).

The real model run uses a separate **one-time** isolated branch workflow
`.github/workflows/rei-quality-sixcase-real-once.yml`; running this
software does not silently schedule repeat model downloads.

## Next research gates

After this initial pass, add a larger held-out task set, consistent
answer/evidence format, multiple order/seed replications, equal-budget
conventional self-critique and tool-using strong Bayesian planners,
plus end-user evaluation under an explicit model-call/latency budget.
Only then investigate whether the REI scaffold contributes a distinct,
reproducible benefit.
