<!-- The running record of COMPOSITION measurements (PIPELINE_TESTING.md §3.3, stage 5).
     Append, never rewrite. Leg C's own results live in benchmark/RESULTS.md — different subject,
     different leg, and they are not the same fact. -->

# PLANNER INVARIANTS — RESULTS

## 2026-09-24 (later) · both reds FIXED

```
151 checks, 0 RED          self-test 6 of 6 (seeded mutants)
  collapse_reduces      1 of 1     held
  complement           37 of 37    held
  filter_monotone     113 of 113   held
```

Fixed in `mac-platform` — `FilterOp.NE` now renders `IS DISTINCT FROM`, and
`reporting_cycle()` reads the declared `params.natural_key` before falling back to
`cell_key`. Verified against anchors derived from the data by two routes, neither the engine:

| | before | after | anchor |
|---|---|---|---|
| RC05 how many stores | 67 | 67 | 67 |
| STORE-07 have closed | 8 | 8 | 8 |
| **STORE-02 not closed** | **6** | **59** | 59 |
| **STORE-03 restructured** | **6** | **0** | 0 |

### The self-test had to be rebuilt, and the reason is a general one

It asserted that the two recorded defects still reproduced. It passed while they existed and
**failed the day they were fixed** — an instrument must never depend on its subject being broken.
It now seeds the decision directly (`complement_verdict`, `collapse_verdict` are pure), so it keeps
proving it can reject forever. The historical numbers survive as seeded cases.

### And the harness itself reported a false green

Mid-fix, a typo raised `AttributeError` inside the planner on every `Store` probe. `run_intent`
caught it, every invariant returned "not applicable", and the report read **`0 RED` with the checks
simply absent** — while the planner was crashing. A vanished check looks like a passing one at a
glance. Crashes are now surfaced separately and fail the self-test outright.

---

## 2026-09-24 · Stage 5 · **C3 SOUNDNESS**

`invariants/planner_invariants.py`, against `mac-ontology-contoso` and its local DuckDB.
**Self-test: both recorded defects reproduced.**

```
151 checks, 3 RED
  collapse_reduces      0 of 1      held
  complement           35 of 37     held
  filter_monotone     113 of 113    held
```

### The three reds, and both were already known

| invariant | finding |
|---|---|
| `collapse_reduces` | `Store`: the collapse kept **74 of 74** rows — it ran and collapsed nothing |
| `complement` | `Store/StoreStatus='Closed'`: eq 8 + ne 6 = 14 against a population of 67 — **53 instances are neither** |
| `complement` | `Store/StoreStatus='Restructured'`: the same defect from the other value |

**Nothing new was found, and that is the point of this run.** The instrument was built against two
defects already on record, and its job today was to prove it can reject. It can. Every green it
reports from here is worth something; before today none would have been.

**No false positives after the direction fix** (below): 35 of 37 complement checks held, and the
2 that failed are the known defect seen from two values.

### `collapse_reduces` has a denominator of ONE

0 of 1. Only one relation in this bundle declares a snapshot collapse, so this invariant is
currently a check on a single subject. It generalises the moment a second bundle — or a Leg A
synthetic SCD-2 bundle — declares one, which is stage 8. Quoting "0 of 1 held" without that
sentence would be the zero-denominator mistake this estate keeps finding.

### Corrections made while building it

**1. TLP as published does not detect this.** Recorded in full at PIPELINE_TESTING.md §3.3.
Classic ternary logic partitioning checks `p / NOT p / p IS NULL` against the unpartitioned query,
and on the planner's emitted SQL that **passes**: 7 + 8 + 59 = 74. SQL is consistent with itself.
The defect is a translation — the Intent's `ne` is not SQL's `<>` — so the ternary idea had to be
re-aimed at the Intent's operator semantics instead of the DBMS's.

**2. The two directions of the complement check are not the same finding.** The first version
reported both as red and produced dozens of false positives on one-to-many terms:

```
Continent/Country='CA':  eq 1 + ne 3 = 4   against a population of 3
```

A continent contains `CA` **and** other countries, so it is counted in both halves. The subject is
multi-valued on the term and the partition claim does not apply.

```
OVER  (eq + ne > population)   multi-valued term        -> NOT APPLICABLE, skip
UNDER (eq + ne < population)   instances fell out of both -> THE DEFECT
```

Only under-count is claimed. That is what makes the check sound without needing a per-term
atomicity declaration.

**3. `--limit` truncated the enumeration alphabetically before `Store`**, so the self-test failed
for the right reason on its first run: it had been relying on a derived enumeration reaching the
known defects by luck. It now targets them directly, and the derived enumeration is what finds the
*unknown* ones.

### What this does not say

* It is COMPOSITION only — whether the machinery computes what the meaning says. It says nothing
  about whether the meaning was right (that is TRUTH, and anchors do it) or whether the LLM built
  the right Intent (RECOGNITION, still unmeasured).
* Three invariants of the seven named in PIPELINE_TESTING.md §3.3 are built. `slice_totality`,
  `filter_order_invariance`, `limit_prefix` and `collapse_idempotence` are not.
* The probe enumeration is derived from countable concepts × their grounding columns, capped by
  `--limit`. It is not exhaustive over the bundle.
