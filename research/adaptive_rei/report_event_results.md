# Distinguishing a report from an event

Ten new passages each have three related questions. Before inference we required more completely correct fresh passages than budgeted REI at or below its total fresh token count. The previous eight passages are a regression set. The experimental decoder uses one short response, places the question last, and explicitly distinguishes reports from events. The comparison measures these changes together.

| Mode | Fresh complete / 10 | Fresh answers / 30 | Fresh tokens | Prior complete / 8 | Prior answers / 24 | Prior tokens |
|---|---:|---:|---:|---:|---:|---:|
| Conventional | 2 | 18 | 3,074 | 3 | 18 | 2,522 |
| Budgeted REI | 3 | 22 | 3,057 | 4 | 19 | 2,902 |
| Plain verdict | 2 | 21 | 1,912 | 1 | 16 | 1,589 |
| Report/event prompt | 4 | 20 | 2,352 | 6 | 22 | 1,940 |

The candidate met the preset criterion by one fresh passage and used 23.1% fewer tokens than budgeted REI. It also lost two individual fresh answers overall. It returned an unrecognized response on one question in each suite, scored incorrect. Keep it experimental. On the original dispatch question it correctly recognized the return entry. An informal rephrased CLI check yielded uncertain, indicating sensitivity to wording. The fresh set is small, constructed, and evaluated on one model.

Run python3 research/adaptive_rei/report_event_trial.py to reproduce the paired trial. Use --report-event 'QUESTION? EVIDENCE' with adaptive_rei_benchmark.py for one case. Per-question scores and token counts are in results/report_event_trial.json.
