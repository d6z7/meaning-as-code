<!-- The running record of LEG C measurements (PIPELINE_TESTING.md §5). Append, never rewrite:
     a number that changes without its predecessor visible is not a measurement, it is a claim. -->

# LEG C — RESULTS

## 2026-09-24 · Stage 4 · **C1 EXPRESSIVENESS**

**Reachable: 74.0 % of 9 568 third-party questions over 171 databases.**

Instrument `benchmark/encodability.py` (self-test 23 of 23). Corpora pinned by revision:

| corpus | rev | sha256 | questions | DBs |
|---|---|---|---|---|
| `birdsql/bird_sql_dev_20251106` | `3c11fb19` | `ffd80183…` | 1 534 | 11 |
| `xlangai/spider` validation | `0c350918` | `c3e2a463…` | 1 034 | 20 |
| `xlangai/spider` train | `0c350918` | `cb4b6815…` | 7 000 | 140 |

### The number

| | BIRD dev | Spider dev | Spider train | **all** |
|---|---|---|---|---|
| encodable — the Intent's own fields | 60.2 % | 70.6 % | 71.9 % | **69.8 %** |
| declarable — + a measure a bundle declares | 9.6 % | 3.0 % | 3.2 % | **4.2 %** |
| **reachable** | **69.8 %** | **73.6 %** | **75.0 %** | **74.0 %** |
| blocked — real grammar gaps | 30.2 % | 26.4 % | 25.0 % | **26.0 %** |

**Against the pre-registered rule (PIPELINE_TESTING §8.3): 74.0 % lands in the 70–90 % band —
*"the gap list IS the roadmap; close the top three, re-run stage 4, then continue."*** Leg C
continues. **BIRD alone is 69.8 %, a hair under the stop line**, and that is recorded rather than
rounded away: the hardest corpus is borderline, and the difficulty split says why — *challenging*
questions are 17.8 % encodable against *simple* at 75.6 %.

### The roadmap — ranked by what each feature costs ON ITS OWN

`sole` counts questions blocked by that feature **and nothing else**, so the column is additive.

| feature | sole | appears | unlocks | cumulative reachable |
|---|---|---|---|---|
| `having` | 460 | 479 | +4.8 % | 78.8 % |
| `set_operation` (INTERSECT/UNION) | 353 | 370 | +3.7 % | 82.5 % |
| `disjunctive_filter` (OR) | 244 | 276 | +2.6 % | 85.0 % |
| `multiple_measures` | 208 | 267 | +2.2 % | 87.2 % |
| `string_match` (LIKE) | 205 | 226 | +2.1 % | **89.4 %** |
| `multi_key_ordering` | 60 | 97 | +0.6 % | 90.0 % |
| `null_test` | 24 | 126 | +0.3 % | 90.3 % |

**Five features take us from 74 % to 89 %.** None is a research problem; four are small.

**And the trap the `sole` column exists to expose: `subquery` appears 714 times and is the sole
blocker 7 times.** Ranked by raw frequency it looks like the largest gap in the corpus. It is
almost worthless to fix, because a subquery nearly always arrives with a HAVING or a set operation
beside it. A frequency histogram alone would have sent the roadmap in exactly the wrong direction.

### What this does and does not say

* It measures whether a query of the gold SQL's **shape** maps onto `Intent`. Gold is one
  implementation of one interpretation, and is often written more elaborately than the question
  needs — so **74 % is a lower bound on expressiveness**, and the blocker histogram is the sound
  part of the output.
* `declarable` (4.2 %) is an **upper** bound in the other direction: it asserts a rule template
  *could* carry the measure, which only a real bundle confirms (stage 7). A rule is fixed SQL, so
  a conditional whose branch depends on a value named in the question may not be reachable.
* It says nothing about whether the LLM would *produce* the right Intent (C2), or the planner the
  right SQL (C3). Different stages, different instruments.
* `string_match` is partly misfiled as a grammar gap: in MAC a name resolves to a code through a
  **register**, offline. Some of those 205 are a bundle's missing register, not a missing operator.

### Corrections made to the instrument while producing this number

Recorded because each one changed the headline, and the self-test caught all four.

1. **CTE detection never fired.** sqlglot 30 renamed `args["with"]` → `"with_"`; every CTE passed
   as encodable. Node search now, not arg names.
2. **`unsupported_operator` was a catch-all**, double-counting `Is` (102) and `Like` (38) that
   already had their own categories. It read as the single largest gap at 146 on BIRD; the
   distinct residue is 26.
3. **`EXCEPT` was counted as a set-operation gap.** It is the anti-join `exists` already covers —
   31 Spider dev questions moved from blocked to declarable.
4. **The whole classifier measured the wrong system.** The first cut called column arithmetic and
   `CASE WHEN` aggregation grammar gaps. MAC never asks the Intent to carry a measure's
   arithmetic — a bundle DECLARES the measure and the Intent names it. That is the `declarable`
   bucket, and adding it moved BIRD by 9.6 points.
