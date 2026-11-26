# Deterministic clock comparison for isolated time fields

Six fresh scenarios each crossed equivalent and different times with supporting and contradicting observations. Eight prior scenarios and six fallback controls were scored separately. A bounded parser compared two isolated clock expressions within the same implied day and time zone. Unrecognized pairs used the existing model time gate. All arms saw the same passage for model decisions, and identical direction calls were charged to each arm using them.

| Set | Parsed pairs | One-step correct (tokens) | Model time gate correct (tokens) | Normalized correct (tokens) |
|---|---:|---:|---:|---:|
| Fresh | 24/24 | 6/24 (2,380) | 14/24 (2,696) | 21/24 (1,018) |
| Prior | 16/32 | 15/32 (3,130) | 20/32 (3,551) | 25/32 (2,361) |
| Context controls | 0/6 | 4/6 (566) | 5/6 (749) | 5/6 (749) |

All 12 fresh wrong-time observations were rejected. Three matching-time observations were misclassified by the model direction step. In the fallback set, the model treated bare “eight” as establishing 8 p.m. The parser's input fields were supplied by the trial generator; extraction from full prose, date handling, and time zone conversion remain outside the measured scope. Token totals measure model input and output. The fresh result covers six deliberately supported expression families. Run clock_normalization_trial.py using the project Ollama model to reproduce.
