# Evidence direction and time wording

Six constructed scenarios cross supporting and contradicting observations with exact, equivalent, and genuinely different times. The quoted sentence was supplied directly to isolate the verification step. All 36 paired cases were fixed before inference.

| Verification decision | Existing verifier | Three-label verifier |
|---|---:|---:|
| Keep supporting evidence, exact time | 6/6 | 6/6 |
| Keep contradicting evidence, exact time | 4/6 | 6/6 |
| Keep supporting evidence, equivalent time | 5/6 | 6/6 |
| Keep contradicting evidence, equivalent time | 3/6 | 6/6 |
| Reject evidence from a different time | 12/12 | 8/12 |
| Correct keep/reject | 30/36 | 32/36 |
| Model tokens | 3,356 | 3,398 |

For the three-label verifier, either supports or contradicts counts as keeping a citation. Exact three-label classification scored 31/36; one equivalent-time observation was retained with the wrong direction. The existing verifier accepted fewer contradictions even with identical time wording. In the cabinet case it rejected “shut” both at noon and at midday, although either observation settles whether the cabinet was open. The three-label verifier correctly recognized both contradictions, but it also treated a shut cabinet at dawn as contradicting an open cabinet at noon.

Keep the new prompt experimental. This measures an isolated component on one model, with six underlying questions. [Completed run](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/runs/45870747886)
