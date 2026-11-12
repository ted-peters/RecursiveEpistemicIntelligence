# Challenge 10 — Stop Recalculating Signed Evidence with a Language Model

**Research status:** software-engineering improvement + independent retrospective of
a previously completed, real-model pilot. This is **not a new live LLM study**,
a new blind holdout, or evidence that REI is superior.

## What the four-case real-model Challenge 9 pilot actually showed

Pinned real run: [Qwen3 4B, GitHub Actions #43144658284](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43144658284).
The experiment completed, the raw JSON artifact was uploaded, and its checksum
and independent grading passed.

| Metric | Self-critique | REI 1.2 |
|---|---:|---:|
| Exact-match recorded-status answers | **1/4** | **1/4** |
| Failed model cases | 0 | 0 |
| Attempted model calls | 12 | 9 |
| Total server-reported tokens | 8,207 | 6,455 |
| Sum of elapsed inference seconds | 360.574 | 278.233 |
| Unknown token usage | 0 | 0 |

REI used **1,752 fewer reported tokens** (21.35% below self-critique) and
three fewer calls; the difference in correct answers was zero. These are
descriptive observations from **four public, synthetic cases**, without
independently matched consumed compute or any replication.

### The actual case-level mistakes

| Case | Reference signed evidence state | Self-critique final | REI 1.2 final |
|---|---|---|---|
| c9-01 | NEITHER | NEITHER ✓ | NEITHER ✓ |
| c9-02 | SUPPORT_ONLY | NEITHER | NEITHER |
| c9-03 | ATTACK_ONLY | NEITHER | NEITHER |
| c9-04 | BOTH | SUPPORT_ONLY | NEITHER |

Both systems correctly recognized the case without active support or
opposition, but often treated active signed evidence as absent. REI ran one
additional recursive expansion on c9-04 and **still did not correct the final
state**. This is a concrete model-behavior failure, not an execution failure:
both arms returned well-formed answers with no provider-reported errors.

Importantly, neither system had to *infer truth*: the required answer was a
precisely defined four-valued **review-admission state**. This is a
mechanical accounting task. A generic LLM should not be the final authority
for this kind of deterministic calculation.

## Challenge 10 implementation

The new `rei0/signed_state_decision.py` exports:

- `resolve_signed_state(ledger, claim_id)`: checks signed review receipts,
  deduplicated source groups and revocations via the original
  `EvidenceLedger.assess()`, and returns a compact auditable four-valued
  recorded status. It **does not call a model**, trust unsafe graph labels,
  or declare that a proposition is objectively true.
- `audit_model_proposal(proposal, decision)`: records whether a model's
  provisional four-state answer agrees, contradicts, is invalid or abstains.
  A model never becomes a signing or evidence-verification authority through
  this function.

`research/challenge10/diagnose.py` independently regrades the exact original
Challenge 9 model outputs and compares them with the **same deterministic
status tool given to both methods**. The model's original answers are left
untouched. On these synthetic, mechanically defined cases, the same
authenticated tool should resolve 4/4 for *either* method. That is a property
of the task and tool, **not a live measured gain in LLM intelligence**.

`tests/test_challenge10_tool_parity.py` checks all four recorded states,
forged graph labels, contradictory signed evidence, revocations, model
proposal disagreement, invalid trusted inputs, wrong review keys and replay
integrity.

## Reproducing the independent retrospective

The GitHub workflow
`.github/workflows/challenge10-diagnose.yml` runs on the development
branch. It retrieves the archived **real** Challenge 9 report via read-only
GitHub Actions permissions, checks the pinned source SHA-256 and run ID,
performs an offline independent regrade, applies the same trusted deterministic
resolver to both methods, and archives the original unchanged raw report
alongside the new diagnostic JSON. No model downloads, inference server or
paid API calls occur.

Manual local reproduction (with a downloaded artifact or its raw JSON):

```bash
python -m pip install .
python -m unittest discover -s tests -p test_challenge10_tool_parity.py -v
python -m research.challenge10.diagnose \
  --input challenge9_fourcase_paired_live.zip \
  --output challenge10-results/diagnostic.json --count 4
```

The original raw artifact is linked from the [Challenge 9 successful GitHub
run](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/43144658284).
The untrusted file checksum alone is not authenticated provenance; the
diagnostic workflow independently checks the pinned original run and report
checksum.

## Why this is a meaningful design distinction

The trusted evidence ledger must decide **what has been reviewed, accepted,
rejected or revoked**. The LLM may explain *what the evidence means*, discuss
conflicts, assess assumptions, propose new falsification questions, or
communicate uncertainty, but cannot silently override the deterministic
admission state. Conventional AI has exactly the same signed-state resolver
available. REI cannot claim a benefit from tools withheld from its comparator.

**Next scientific question:** Can adaptive recursion help when *the next
verification question*, relevance of evidence, causal interpretation, or
decision under incomplete knowledge is actually uncertain—not when the task
is simply tallying VERIFIED and REVOKED statuses? A strong fair experiment
must use new held-out tasks, multiple seeds, a capable matched conventional
tool-using baseline, independent grading, and consumed-compute accounting.
