# Capacity versus current contents

The candidate distinguishes an exact full-container measurement from a current amount and from an amount with explicit room left. It compares normalized volumes, records the observation kind and passes the quoted evidence through the existing single-fact evaluator. The implementation was frozen before the separate AI author's questions were used. That author received the capacity test specification without project history, examples, code or results.

| Set | Previous REI | Candidate | Correct contradictions before → after | Definite answers on inconclusive cases before → after |
|---|---:|---:|---:|---:|
| PR 77 questions, now used for development | 14/30 | 16/30 | 2/10 → 4/10 | 6/10 → 6/10 |
| New independently authored capacity questions | 8/18 | 8/18 | 0/6 → 0/6 | 2/6 → 2/6 |

The candidate routed all six development jug prompts through its exact reader and got all six correct. It routed zero holdout questions through that reader. All 18 verdicts matched the previous version. For example, both systems missed the contradiction between a capacity of at least 1.5 liters and a jug already full after 1.4 liters. Forms involving narrated pours, pronouns and multiple observations remain challenging. The fresh test did not meet the contradiction-recognition milestone.

Each arm used identical inputs and the same pinned local Llama 3.2 1B. Model tokens fell from 3,334 to 2,658 on the development questions and stayed at 1,995 on the new questions. Both sets were retained as scored; no tuning followed the holdout. Twenty-four focused tests passed. Replay with capacity_transfer_trial.py and each checkout root.
