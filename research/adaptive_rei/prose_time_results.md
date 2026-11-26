# Extracting times before comparing observations

Sixteen constructed passages mix event times with filing, scheduling, or other-item times. Eight clear-clock cases and eight context controls were labeled before inference. The primary extraction measure requires both expected time phrases (ignoring case and trailing periods). The full-passage relation verifier provides the baseline and fallback.

| Mode | Correct verdicts | Clock comparisons used | Model tokens |
|---|---:|---:|---:|
| Full-passage verifier | 5/16 | 0 | 1,699 |
| First extraction trial | 5/16 | 0 | 3,637 |
| Post-hoc structured extraction | 7/16 | 5 | 3,432 |

The original extractor returned differently named fields on all cases. The follow-up used the same prompt, inputs and scoring but constrained JSON field names. Both spans were correct in 9/16 cases (5/8 clear clocks and 4/8 controls). The five deterministic comparisons corrected two erroneous verdicts without introducing a regression. Some extractions returned whole sentences. On an exact-time question one dropped the qualifier “exactly.” A conservative whole-passage guard or unsupported expression prevented deterministic comparison on every context control; the fallback itself scored 2/8 there.

These small, same-set follow-up results do not establish deployment performance. If testing further, enumerate candidate time spans in the text first and select among them while retaining neighboring qualifiers. Run prose_time_trial.py with local Ollama, then repeat with --structured. Both result files retain the extracted strings, reference spans, routing choices and costs.
