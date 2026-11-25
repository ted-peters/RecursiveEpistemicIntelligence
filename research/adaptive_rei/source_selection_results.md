# Selecting the source of an answer

Nine fresh passages each have two questions. Labels and reference lines were fixed before inference. Whole-passage accuracy requires two correct verdicts. The candidate uses one numbered-passage JSON call and requires a valid reference for a decisive verdict.

| Mode | Both correct / 9 | Answers correct / 18 | Fresh tokens |
|---|---:|---:|---:|
| Conventional | 2 | 9 | 1,815 |
| Budgeted REI | 5 | 14 | 1,872 |
| Report/event REI | 3 | 11 | 1,371 |
| Source selection | 2 | 9 | 1,976 |

The candidate matched the reference line (or 0 for unknown) on 8/18. It cited an inventory to confirm an actual tree species and a form to confirm an artwork's actual status, although neither passage supplied direct confirmation. On the previously seen witnessed delivery it answered all three paraphrases correctly, and on the dispatch entry two of three. These diagnostics are separate from the nine fresh pairs.

Keep source selection experimental. A citation is inspectable but can support a different proposition. The required citation, JSON format and prompt changed together, so their effects cannot be attributed separately. Run python3 research/adaptive_rei/source_selection_trial.py with the local Ollama model to repeat this test.
