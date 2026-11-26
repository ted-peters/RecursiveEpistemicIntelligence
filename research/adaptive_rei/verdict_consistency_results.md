# Does reviewing a denial against its stated reason help?

Six fresh scenarios each have missing evidence, evidence of omission or contradiction, and evidence of completion or support. The 18 earlier mixed-task questions are reported separately. The review sees the first-pass fact and original question/passage. Only a first-pass no with a stated reason is eligible to become uncertain. All reviewed arms pay for the first pass and the review.

| Model and set | First pass correct (tokens) | Reviewed (tokens) | Two permitted review outputs enforced (tokens) |
|---|---:|---:|---:|
| Qwen3 4B, fresh | 18/18 (1,956) | 18/18 (2,594) | 18/18 (2,594) |
| Qwen3 4B, prior | 15/18 (1,943) | 13/18 (2,782) | 13/18 (2,782) |
| Llama 3.2 1B, fresh | 10/18 (2,318) | 10/18 (3,043) | 7/18 (3,045) |
| Llama 3.2 1B, prior | 10/18 (2,447) | 10/18 (3,152) | 9/18 (3,152) |

In the frozen run Llama returned no on all twelve review calls across the two suites. These out-of-contract decisions preserved the initial verdict. In a post-hoc diagnostic we constrained both models to keep or uncertain using the exact same first passes. Llama then corrected one unsupported denial on fresh cases but weakened four justified denials. Qwen's original timestamp and gold errors persisted on the prior set; its review weakened the pencil-capacity and journal questions. Qwen's fresh first pass left no error to fix. The controls are authored and share six scenario families. Retain the first-pass approach for further testing and leave the review experimental.

Run verdict_consistency_trial.py with both pinned models in local Ollama; save its output to results/verdict_consistency_trial.json before running verdict_consistency_format_check.py.
