# Preview of REI Challenge 5

**No answers are shown here.** These are synthetic reasoning tasks, not real-world empirical reports.

There are 12 evaluation items in each of five categories. The excerpt below shows the kind of problem REI and the baselines receive.

## Arithmetic

**Question:** Compute ((87 × 13 − 38 − 18) × 5) − 10. Return the integer only.

**Context:**

```text
All arithmetic operations are over integers; observe the parentheses.
```

## Logic

**Question:** Is B logically entailed by the facts and rules? Reply ENTAILED or NOT_ENTAILED.

**Context:**

```text
Facts: B is TRUE. Rules: if C is TRUE then D is TRUE; if A is TRUE then D is TRUE; if C is TRUE then B is TRUE. No converse rules are assumed. Other propositions may be true or false; use all models consistent with the facts and rules.
```

## Evidence

**Question:** What is the final four-state information status of claim P? Reply only NEITHER, SUPPORT_ONLY, ATTACK_ONLY, or BOTH.

**Context:**

```text
Each ACCEPT document counts only while not REVOKED. PENDING does not count. Documents sharing an origin are not independent studies. Any valid positive and negative evidence yields BOTH, regardless of the number of copies. Interpret records in chronological order:
PENDING document D1, origin S-PENDING, side SUPPORT
ACCEPT document D2, origin S-REVOKED, side SUPPORT
REVOKE document D2
ACCEPT document D3, origin S-POS-63, side SUPPORT
ACCEPT document D4, origin S-NEG-76, side ATTACK
PENDING document D5, origin S-PENDING2, side ATTACK
```

## Dependency

**Question:** What is Q's resulting information status after evaluating only the listed rules? Reply NEITHER, SUPPORT_ONLY, ATTACK_ONLY, or BOTH.

**Context:**

```text
Premises: P1=NEITHER, P2=ATTACK_ONLY, P3=NEITHER, P4=ATTACK_ONLY. Authorized positive rule: if P1 and P2 are both SUPPORT_ONLY, derive SUPPORT for Q. Authorized negative rule: if P3 and P4 are both SUPPORT_ONLY, derive ATTACK for Q. Direct recorded evidence for Q: SUPPORT; ATTACK. A disputed BOTH premise blocks its rule. Combine direct and derived evidence without explosion.
```

## Insufficient Information

**Question:** What is the exact value of x? If not uniquely determined, return a null answer.

**Context:**

```text
Two integers x and y are positive, x + y = 30. No other equations or measurements are available.
```

