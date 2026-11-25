# Maintenance-record audit pilot

Fourteen fixed questions cover six short evidence packets paraphrased from three published New York City Comptroller audits. The packets and scoring key were committed before inference. Each model saw only the question and evidence. Expected answers were assigned for this pilot from the supplied evidence. They are not independent auditors' labels on original work orders. Related questions share passages, so this is a feasibility check.

| Measure | Conventional single-pass | REI budgeted review |
| --- | ---: | ---: |
| Correct answers | 10/14 | 13/14 |
| False confirmations (yes on no or uncertain) | 0/9 | 0/9 |
| Missed supported claims | 2/5 | 0/5 |
| Correctly retained uncertainty | 4/5 | 4/5 |
| Model input and output tokens | 1,523 | 1,950 |

Both modes inferred that some spot checks never happened from a mismatch between the database and ride cards. Missing corroboration leaves the actual number unknown. In contrast, REI correctly recognized that a record of late completion still establishes completion.

REI returned a citation on three claims. On one, the cited sentence established the verdict by itself. On two, the sentence needed another line of context to identify the population or resolve “those same rides.” The scoring key lists all lines required for a standalone explanation. The conventional prompt requests only a verdict. No independent reviewer participated, so reviewer time and citation usefulness in actual audits remain unmeasured.

Run `python3 research/adaptive_rei/maintenance_audit_trial.py` with Qwen3 4B installed in local Ollama. The results file includes the model digest, every verdict, token count and returned citation. The cases file includes the original audit URL for each packet.
