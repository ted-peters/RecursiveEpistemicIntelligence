# Matching a measurement to its subject

On PR 72's 64 reused prompts the updated single-fact mode scored 59/64 against 41/64. Correct abstentions for other objects rose from 4/16 to 15/16. Other-property controls remained at 13/16. Standard wording rose from 26/32 to 32/32 and paraphrases from 15/32 to 27/32. On 12 new explicit-alias controls the score rose from 4/12 to 12/12. Across both sets model tokens fell from 5,918 to 1,835.

The rule recognizes a limited set of measurement constructions and accepts an explicitly stated alias. A recognized measurement with compatible units attached to a different subject supplies a gap. Each graph keeps the passage. Unsupported constructions can still be misclassified by the model. The 12 alias controls were authored for this syntax and frozen before inference.

Reproduce by running measurement_subject_trial.py with each checkout root. Both arms used the same pinned Llama digest and question strings. Sixteen focused unit tests passed.
