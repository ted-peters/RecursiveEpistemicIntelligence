# REI Challenge 6 — first real-model exploratory pilot results

> **Outcome:** REI did **not** beat the strongest conventional comparator (self-critique) in this six-case pilot. This is not a causal proof that REI is inferior, nor evidence that it generally beats a single-pass model.

**Execution:** GitHub Actions [completed run #43070384244](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43070384244), November 11, 2026. The run downloaded one SHA-256-pinned open-weight Qwen3-4B-Instruct-2507 Q4_K_M model and executed all arms through a local llama.cpp inference server; no scripted provider predictions. The run produced an archived JSON report, and the inherited verifier regraded 24 case-arm outcomes. A successful verification checks internal report consistency, not the scientific independence of the experiment.

## Primary observations

| Arm | Correct / 6 | Reported model calls | Total reported tokens | Failed runs |
|---|---:|---:|---:|---:|
| `baseline` | 2 / 6 | 6 | 1545 | 1 |
| `self_critique` | 4 / 6 | 16 | 7568 | 1 |
| `fixed_depth` | 1 / 6 | 12 | 5222 | 4 |
| `rei` | 3 / 6 | 14 | 7972 | 3 |

**Interpretation:** REI achieved 3/6 vs the single-pass 2/6, but self-critique led with 4/6 and used 7,568 reported tokens versus REI's 7,972. REI used over five times as many tokens as single-pass (7,972 vs 1,545). There were **zero case pairs with exactly matched actual token use**, so the comparison is not compute-matched. Reported failed runs count as failures, not successful abstentions.

## Per-case answers (correct = ✓, otherwise ✗)

| Case | Type | Gold | Baseline | Self-critique | Fixed depth | REI |
|---|---|---|---|---|---|---|
| c6-01-arith | arithmetic | 703 | ✗ 19 | ✓ 703 | ✓ 703 | ✓ 703 |
| c6-02-arith | arithmetic | 294 | ✓ 294 | ✓ 294 | ✗ ERROR | ✓ 294 |
| c6-03-logic | logic | NOT_ENTAILED | ✗ ENTAILED | ✓ NOT_ENTAILED | ✗ ERROR | ✓ NOT_ENTAILED |
| c6-04-logic | logic | ENTAILED | ✓ ENTAILED | ✓ ENTAILED | ✗ ERROR | ✗ ERROR |
| c6-05-evidence | evidence | BOTH | ✗ SUPPORT_ONLY | ✗ ABSTAIN | ✗ SUPPORT_ONLY | ✗ ERROR |
| c6-06-unknown | unanswerable | ABSTAIN | ✗ ERROR | ✗ ERROR | ✗ ERROR | ✗ ERROR |

## Paired uncertainty

The inherited case-level bootstrap gave the following **exploratory** differences in percentage points (REI minus comparator; six cases and 1,000 resamples):

| Comparison | Difference | Nominal 95% bootstrap interval |
|---|---:|---|
| `rei_minus_baseline` | +16.7 pp | -33.3 to +66.7 pp |
| `rei_minus_self_critique` | -16.7 pp | -50.0 to +0.0 pp |
| `rei_minus_fixed_depth` | +33.3 pp | +0.0 to +66.7 pp |

The small, non-independent six-case dataset makes these intervals unstable; they should **not** be used as evidence of statistical significance or as a definitive ranking. The self-critique comparison does not establish a REI win.

## Failure analysis

- Baseline got the arithmetic warehouse question wrong (`19` instead of `703`) even though its rationale eventually mentions the correct multiplication, indicating output/reasoning inconsistency.
- Fixed-depth often failed because the model generated an invalid question priority (not an integer 0–10) or malformed reasons, rather than reaching a correct final response.
- REI failed on the second logic problem, the conflicting-evidence problem and the unknown-card problem due to invalid or out-of-budget intermediate model outputs, including malformed question priority. These are implementation/model-protocol limitations that matter in practice.
- None of the four methods earned a success on the unanswerable card case: the ordinary/self-critique methods generated null answers with invalid confidence, and fixed-depth/REI raised other errors.
- The open-weight model is only 4B parameters; stronger conventional LMs and compute-matched methods could change the ranking.

## Audit and design caveats

1. Six hand-authored public tasks, one seed, no blind independent custody of test answers; original key file was not passed to the model prompts, but the overall task set is unblinded.
2. The model and source were common across arms, but method prompts were not arm-blind (the old request schema includes arm names). Equal **ceilings** on calls are not equal consumed inference.
3. This primarily measures REI's bounded recursive inquiry prompt/scheduling with **provisional** model-authored reasons, not independently verified external evidence, authenticated source provenance, or a general-purpose trained REI model.
4. The model/provider checksum and run log are useful reproducibility records, not an external third-party attestation.
5. There were differences in failure rates and malformed JSON. The practical outcome includes these errors. Comparing only completed answers would bias the result.
6. A subsequent three-case technical smoke test is a separate, overlapping subset and is **not** an independent replication.

## Reproducibility

- [Raw GitHub Actions run and downloadable `challenge6-open-weight-pilot` artifact](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43070384244)
- Model digest: `85e4a5b7b8ef0e48af0e8658f5aaab9c2324c76c1641493f4d1e25fce54b18b9`
- llama.cpp commit: `3b4d6ab3f79651935fba1dd93732f29022a7f5f5`
- Inherited report SHA-256: `6415f4c946736ff18da557246650dad007e4fdb65896dacbd6b0f7dc94a78b76`
- **Next controlled experiment:** much larger independently authored dynamic evidence timelines, genuine blinded evaluation, strong model, compute-matched self-critique, provider traces, and independent grading. State an REI superiority claim only if the replicated, prespecified effect is demonstrably positive.