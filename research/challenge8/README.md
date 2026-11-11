# Challenge 8 — Fixing the model interface before increasing scale

**Status:** preregistered public development pilot, not a blinded claim of superiority.

Challenge 7's six dynamic-timeline trials yielded REI **0/6**, self-critique **2/6**, baseline **2/6**, and fixed-depth **2/6** on Qwen3-4B-Instruct-2507 Q4_K_M. REI had six failed executions. A detailed examination of the actual report shows failures from malformed/truncated JSON, invalid question priorities, and model timeouts. A failed model response can consume tokens that are absent from the inherited success-only token meter.

This pilot tests whether an **identical, schema-constrained interface for all four arms** can improve reliability. It does not automatically fix incorrect reasoning or give REI a private advantage. We do not change the REI-1.0 graph, recursive scheduling engine, or strict benchmark grader.

## Fixed comparison setup

- Same pinned third-party Qwen3-4B-Instruct-2507 Q4_K_M model SHA-256 and pinned llama.cpp b12242 inference engine as Challenge 7.
- Same original case questions, standard stage system prompts, context formatting, fixed seed 711, temperature 0, three calls maximum per case, 2,600 reported-token budget, 140 seconds, 320 generated output tokens/call, and one expansion step.
- **New common intervention:** all stages now use `response_format=json_schema` with bounded fields and strict integer priority. Stage policies are the same regardless of `arm`; reasoning-specific initial/expand apply equally to REI and fixed-depth.
- Record all server-returned token usage, **including malformed responses**. Timeouts can still have unknown usage; do not treat unknown tokens as zero-cost inference. Malformed output still counts as failure, never an abstention.
- Same four benchmark arms, with no answer key in model prompts. Public synthetic questions and keys are not independent held-out data.

## Two workflows

- `.github/workflows/challenge8-structured-smoke.yml` auto-runs a six-case reliability pilot on this branch. It repeats the **public Challenge 7 cases** using the new structured-output interface. This dataset has already influenced the intervention; comparison with the old run is strictly a development diagnostic, **not an unbiased architectural comparison**.
- `.github/workflows/challenge8-scaled.yml` provides a **manual** six-shard 24-case expansion, running up to two CPU model shards simultaneously. Each shard contains four balanced synthetic revision timelines. Do not activate expensive repeated experiments until the six-case reliability pilot passes.

The 24-case set is generated deterministically from seed 20261111, balanced across four final four-state answers, with 24 original REI graph vs independent conventional ledger oracle checks and event-by-event validation. **Both oracles are expected to agree**, and neither is an AI reasoning contest in isolation. More cases reduce sampling noise but do not provide independent blinded evaluation, stronger open models, or a compute-matched self-critique study.

### Reproduction

`python -m research.challenge8.generate_scaled` — regenerate all synthetic cases + keys + audit.

`python -m unittest discover -s tests -p test_challenge8.py -v` — test schema contracts, fail accounting, model request shape, oracle parity, and sharding, without downloading a model.

GitHub Actions downloads the pinned model, runs actual inference on loopback, uploads independently regraded raw JSON outputs, and reports successes, errors and partial/unknown token usage. Results should be inspected **before** treating any method as more accurate or efficient.

## Independent six-shard aggregation

After the **manual** 24-case experiment finishes, the downstream
`independently-grade-shards` job downloads every artifact and runs
`research/challenge8/aggregate.py` using the original frozen public
`scaled_cases.json` and `scaled_keys.json`.

To verify six JSON results locally (one from each shard):

`python -m research.challenge8.aggregate challenge8-results/shard-{0..5}.json --output challenge8-results/aggregate.json`

The aggregator refuses incomplete or duplicate shard indices, altered
benchmark reports, unexpected case/arm pairs, inconsistent model and inference
configuration, and contradictory model-attempt telemetry. It regrades the
**full 24-case paired result**, recomputes the paired bootstrap, and retains
the individual report checksums. Token usage is reported separately as
server-observed tokens including failed parses and calls with *unknown* usage.
Missing usage is never treated as zero-cost inference.

`python -m unittest discover -s tests -p test_challenge8_aggregate.py -v`
tests this process with **synthetic fake model calls** and injected failures;
test success does not demonstrate improved AI accuracy.

The scale-up is still nonblind public synthetic development. Neither a passed
aggregator nor a 24-case result is grounds for claiming REI superiority over
strong conventional AI, or compute matching. Actual usage, failure counts,
model limitations, and primary REI-versus-self-critique results must all be
reported.
