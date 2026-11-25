# Reviewing record-based confirmations

Eight new constructed scenarios each supplied four matched questions or evidence variants. The rubric requires uncertainty about an actual event or property when the only evidence is an unverified record assertion. A question about the record's contents can be answered from the record itself. This rubric tests a particular audit standard. It does not measure the ordinary reliability of real records.

| Fresh mode | Unchecked / 8 | Corroborated / 8 | Contradicted / 8 | Record contents / 8 | Correct / 32 | Tokens |
|---|---:|---:|---:|---:|---:|---:|
| Conventional | 0 | 8 | 4 | 7 | 19 | 3,027 |
| Budgeted REI | 0 | 8 | 8 | 7 | 23 | 1,799 |
| Selective yes review | 2 | 8 | 8 | 7 | 25 | 2,848 |

The gate used document terms in a citation, or in the only evidence sentence when there was no citation, and excluded questions containing those terms. All eight extra calls were on unchecked records. False confirmations fell from eight to six; no correct verdict changed. The gain cost 1,049 tokens. On the 18 previously seen source-selection questions the gate never fired. Budgeted REI and selective review both scored 14/18; budgeted REI already answered the actual pear-tree question correctly.

The eight families share wording and structure. The gate cannot reliably identify evidence provenance from keywords alone. Keep this as a research trial. Run python3 research/adaptive_rei/record_yes_trial.py with the project's local Ollama model. Per-question costs, reviews and verdicts are in results/record_yes_trial.json.
