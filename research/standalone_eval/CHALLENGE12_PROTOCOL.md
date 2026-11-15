# Challenge 12 — Adaptive REI vs conventional reasoning (PUBLIC development study)

**Status:** Preregistered task set and analysis code. Do not replace or silently
edit cases after the first real-model run; append a new version and distinguish
development tasks from truly unseen tasks in future studies.

## Why this study

The local REI application works on Apple Silicon and the real-model
[adaptive smoke](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43662076430)
passed. The earlier six public questions resulted in **6/6 correct** for both
Direct and full REI: Direct used **6 model calls and 2,241 tokens**, whereas REI
used **24 calls and 15,638 tokens**
([independently graded run](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43653923859)).
Neither test established a general accuracy advantage for REI.

Challenge 12 asks: **Does Adaptive reduce the inference cost of an REI-enabled
assistant while retaining objective accuracy? Does full REI outperform a
conventional multi-step self-critique baseline at a similar model-call budget?**

## Public, fixed case set

[challenge12_cases.json](challenge12_cases.json) contains **12 hand-authored,
fully public, objectively keyed four-choice questions**: six straightforward
bounded questions and six explicitly investigative questions, alternated in
the file. Domains include conditional probability, Simpson's paradox,
percentages, logical entailment, a median, retesting/causal confounding,
dependency of republished evidence, and expected value.

These are **not** hidden, blinded, broadly representative, or statistically
adequately powered. They are a research-development benchmark. We freeze
them **before** the Qwen comparisons and track the case-file digest. Every
case must run in all four arms, regardless of outcome. The answer keys,
case IDs, styles and source metadata are excluded from model prompts.

## Four arms — same Ollama model, same question

| Arm | Mechanism | Calls per completed case |
|---|---|---|
| **Direct** | Original Qwen direct response with no graph | Exactly 1 |
| **Adaptive** | REI local router: bounded tasks use Direct; explicit investigations use selective REI graph | 1 to 4 |
| **Full REI** | Original bounded `InquiryEngine` plus synthesis | 2 to 4 |
| **Self-critique** | Conventional draft -> critique -> independent check -> revise | Exactly 4 |

All generated answers use the same Ollama model with temperature 0. No
real-world tools, browsing, evidence verification, or user data are involved.

The **conventional self-critique baseline** is intentionally implemented
outside REI. It asks the same Qwen model for an answer, a skeptical review,
an independent reasoning check and final revision. Each call is measured
using Ollama's server-reported prompt + completion tokens. The self-critique
review itself is not independent empirical evidence. Its prompts are public.

**Important compute caveat:** 4 calls does NOT mean compute-matched. Full
REI and conventional critique may use different token counts, context
lengths and wall times. Reports therefore include all actual call,
reported-token and latency totals; no arm is given free computation. The
adaptive router itself makes **zero** model calls.

## Execution and scoring rules

1. The case file and protocol are frozen before all real-model trials.
2. The same case text, option lines, and answer-format instruction are
   presented to each arm. Investigative questions receive the **same**
   explicit `Investigate...` prefix under all four modes; it is not a
   secret prompt that only Adaptive sees.
3. To reduce systematic warm-model order effects, the arm order rotates
   across the 12 cases, with every mode appearing in all four positions.
   This does **not** eliminate order effects or make results randomized.
4. Report a final unambiguous `Answer: X` line with one A–D option.
   Other answers, missing outputs, invalid format or generation errors
   count as incorrect. No LLM judge may rewrite or rescue them.
5. Independently recompute correctness from frozen case keys, answer
   extraction, all raw reported model attempts, token sums, and per-arm
   graph evidence status. Each full report is checked by a content digest,
   which is **not** a cryptographic provenance signature.
6. Group the 12 cases into three index-modulo shards of four questions
   each for real-model testing. Require exactly one completed report for
   each shard before computing aggregate scores; missing data must never
   silently disappear.
7. Aggregate: number correct / 12, invalid-output count, failed-request
   count, total model calls, server-reported tokens, unknown-usage model
   calls, measured end-to-end elapsed seconds. Include per-case answer
   correctness and discordant pairs (Adaptive correct/Direct wrong and
   the reverse). A result is not proof of statistical significance.
8. The exact Ollama model digest and pinned Ollama binary version are
   recorded per shard. Tags alone are not assumed immutable.

## Reproduce offline and on an Apple Silicon Mac

From the repository root (Python 3.10+; the Mac launcher can set this up):

```bash
# No real model calls. Fake-only scorer and integration:
python -m unittest discover -s tests -p test_challenge12_quality.py -v
python -m research.standalone_eval.challenge12_quality \
  --kind fixture --shards 1 --shard-index 0 \
  --output /tmp/rei-challenge12-fixture.json
python -m research.standalone_eval.challenge12_quality \
  --verify-only --output /tmp/rei-challenge12-fixture.json

# Full, genuine Ollama trial: downloads no model automatically;
# requires Ollama and qwen3:4b-instruct already available locally.
python -m research.standalone_eval.challenge12_quality \
  --kind live --shards 1 --shard-index 0 \
  --output /tmp/rei-challenge12-real.json
python -m research.standalone_eval.challenge12_quality \
  --verify-only --output /tmp/rei-challenge12-real.json
```

The real trial can take considerable time on a CPU, and all four arms will
use the same model for fair prompting. GitHub's one-off CI benchmark runs
three independent shard jobs and archives all raw results with exact
model identities for independent audit.

## What would count as meaningful progress?

- **Engineering:** Adaptive really routes inexpensive tasks to one call,
  respects the bounded inquiry budget on investigative tasks, and preserves
  full audit trails.
- **Quality preservation:** Adaptive makes no more mistakes than Direct
  on this fixed study while using fewer model calls/tokens/seconds than
  always-on full REI. Any such result is **limited to these 12 cases**.
- **Strong-baseline challenge:** Compare Full REI with four-call conventional
  self-critique, report correctness **and** token/wall cost. A single-case
  win is not meaningful proof of REI's distinct value.
- **Future validity:** Run larger independently authored or sequestered
  tasks, several model seeds and orders, varied model sizes, calibrated
  uncertainty and held-out trials with controlled equal token budgets,
  rather than tuning to this development set.

**Always report negative results.** If Direct wins on accuracy or
efficiency, retain the original outputs and say so. REI's model-authored
arguments cannot establish external facts without independent evidence.
