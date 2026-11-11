# Challenge 6: A real-model exploratory REI head-to-head

This is **the first planned real inference pilot**, not a fabricated fixture result. It uses the untouched REI-1.0 `rei0.benchmark` engine to run four arms with the same downloaded model and explicitly recorded *provider-reported* token usage.

**Model:** Qwen3-4B-Instruct-2507, quantized Q4_K_M (third-party GGUF mirror by `fzhnk`, Apache-2.0 original model). Exactly pinned file SHA-256: `85e4a5b7b8ef0e48af0e8658f5aaab9c2324c76c1641493f4d1e25fce54b18b9`. Downloaded on a short-lived GitHub Actions CPU runner. No external model API, tokens, keys, or billed inference calls. The open-source runtime is `llama.cpp` release tag `b12242`, engine commit recorded in the output. See [source](https://huggingface.co/fzhnk/qwen3-4b-instruct-2507-gguf).

**Dataset:** six manually specified, objective-answer questions on two arithmetic problems, two logical entailments, a duplicate-and-contradictory evidence assessment, and one insufficient-information case. Keys are included for auditability but are **not shown to the models**; this is *not* a blind independent held-out study. Questions were authored after the design of REI and can favor or disadvantage different arms. It is inappropriate to interpret this pilot as definitive empirical evidence.

**Arms:** `baseline` (one model call), `self_critique` (draft/critique/final), `fixed_depth` (first-question FIFO and final), and `rei` (the real REI-1.0 priority-scheduled, typed epistemic inquiry graph followed by synthesis). All four use the *same model*, identical system stage prompts defined in inherited `rei0.benchmark`, deterministic temperature zero, at most three model calls, maximum 2,600 reported tokens, 140 s per pair, 320 output tokens/call, and at most one expansion step. **Actual model use is not matched**; compare tokens and calls, not just accuracy.

**No authenticated evidence:** Model-written reasons stay provisional and the REI evidence state is `NEITHER` unless independently reviewed. Thus this is a test of recursive inquiry prompting and graph scheduling, not REI's real-world evidence verification.

**Scoring:** The inherited benchmark records answer strings or explicit `null` abstention, model errors, reported usage, and exact-match correctness. Invalid model JSON or unmet strict schemas count as *failures*, not as correct abstentions. Includes case-level paired bootstrap intervals. REI's benchmark and report validator are left unchanged.

**Execution:** GitHub Actions workflow `.github/workflows/challenge6-open-model.yml` runs on pushes to its experiment branch (or manually). No local user action required. Download `challenge6-open-weight-pilot` workflow artifact after a completed successful run. The artifact includes the JSON outcome record, input cases, and reference keys. The PR should not be merged on the strength of a dry run or a failed API response.

**Research limit:** A 4B model on six handpicked tasks is weaker evidence than a frontier-class, independently graded, multi-seed, cost-matched evaluation. A REI win here would be encouraging, not proof of superior intelligence. A loss would be diagnostic, not conclusive either.
