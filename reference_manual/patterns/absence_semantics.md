---
title: "Pattern — Absence semantics (what a missing row means)"
part_of: reference_manual/patterns
status: prototype
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (illustrative shop scenario).
---

# Pattern — Absence semantics

## Initial state — what you're handed

A sparse daily-sales fact: a row exists only when there is something to record.

```sql
CREATE TABLE daily_sales (
  sale_date  DATE,
  store_id   VARCHAR,
  product_id VARCHAR,
  units      INTEGER
);
```

| sale_date | store_id | product_id | units |
| --- | --- | --- | --- |
| 2026-03-02 | S1 | P-100 | 4 |
| 2026-03-03 | S1 | P-100 | 6 |
| *(no row)* | S1 | P-100 | — |
| *(no rows at all)* | S2 | P-100 | — |

**Why this is dangerous.** The **absence** of a row is information — but *ambiguous* information. The missing
2026-03-04 row for S1 could mean **genuine zero** (open, sold none) or **not-loaded** (the store's feed
failed). The total absence for S2/P-100 could mean **genuine zero** (S2 sold none) or
**structurally-untracked** (S2 doesn't carry P-100). `AVG(units)` over the rows that exist, or "which stores
had zero sales?", silently commits to *one* of these readings — and **no `SELECT` can recover which is
true**, because the fact is about the world, not the rows.

## The question, and the answer

> **The question** (what the data can't tell you): *What does a missing row mean — genuine zero, not-loaded,
> or structurally-untracked?*
>
> **The answer** (the fact we supply): *It cannot be read from the data; `null_semantics` **declares** it per
> concept. Then the behaviour follows deterministically — genuine-zero → densify to the full grid and
> `COALESCE` 0; not-loaded → exclude and flag (never impute 0); structurally-untracked → drop from the
> denominator.*

## The pattern (the structured entry)

```yaml
pattern: absence_semantics
also_known_as: [null semantics, anomaly of absence, missing-vs-zero, sparse fact, densification]
tradition: cross-cutting   # dimensional sparse-fact/densification + relational NULL semantics + RDF open-world
constellation: >
  A fact table is SPARSE, so the absence of a row carries meaning — but ambiguously: it may mean a genuine
  zero, a not-yet-loaded cell, or a not-applicable (structurally-untracked) cell. Averages, zero-counts and
  coverage all depend on which.
prior_art:
  relational: >
    Absence has no declared meaning; the analyst guesses. `AVG` over present rows silently EXCLUDES absent
    days; `LEFT JOIN ... COALESCE(0)` silently IMPUTES zero. Both are choices, neither documented.
  dimensional: >
    "Sparse facts" and "densification": you may densify against a date×store grid to get zeros — but whether
    to densify, and where, is tribal, and the not-loaded-vs-zero distinction is rarely modelled at all.
  rdf: >
    Open-world by default — absence means "unknown", never "zero/false". The opposite default from
    relational, and equally silent about which the modeller actually meant.
mac_expression: >
  `semantics.null_semantics` DECLARES, per concept, what an absent row means: `genuine_zero` /
  `not_loaded` / `structurally_untracked`. The query behaviour then follows deterministically — genuine_zero
  → densify against the complete grid and COALESCE 0; not_loaded → exclude AND flag incompleteness (never
  impute 0); structurally_untracked → exclude from the denominator. The skeleton flag decides; a canon
  executes.
why_better: >
  The meaning of absence — which relational leaves undocumented and RDF fixes to "unknown" — becomes an
  explicit, per-concept, agent-readable fact. AVG, coverage and zero-queries are then computed the one
  correct way, instead of silently guessed; and "not-loaded" is never fabricated into a zero.
projects_to:
  rdf: "an explicit closed-world / default-value annotation (overriding the open-world default)"
  graph: "a default-value property on the node/edge"
  relational: "a densification spec against a grid + a load-completeness flag"
antipattern: >
  `AVG` over present rows when absence means zero (overstates); `COALESCE 0` when absence means not-loaded
  (understates / fabricates data); treating structurally-untracked cells as zero (pollutes denominators).
status: scattered   # semantics.null_semantics exists; never named as a pattern, and the densify/exclude behaviour was not canonized
canon_ref: [CONCEPT_SPEC.md §6 (semantics.null_semantics), FRAMEWORK.md §5 (semantics)]
```

## The determinism border

Per [AUTHORING.md](../AUTHORING.md) A4 — another case where a **skeleton flag decides** and a canon executes:

| Behaviour | Kind | How |
| --- | --- | --- |
| Which meaning a missing row has | **skeleton** | `semantics.null_semantics` (declared, not guessed) |
| `genuine_zero` → densify to the grid + `COALESCE 0` | **canon-backed** | [`densify`](../canon/densify.md) |
| `structurally_untracked` → drop from the denominator | **canon-backed** | [`exclusion_filter`](../canon/exclusion_filter.md) (restrict the grid) |
| `not_loaded` → exclude **and flag** (never impute 0) | **partly canon / data** | exclude + a completeness caveat (the *register* edge of [`impurity_disposition`](impurity_disposition.md)) |
| interpretative remainder | **minimal** | once `null_semantics` is declared, the behaviour follows |

```yaml
semantics:
  null_semantics: genuine_zero      # the skeleton fact that decides everything below
  realized_by:
    udf: densify
    params: { fact: daily_sales, measure: units, keys: [sale_date, store_id, product_id],
              grid: "SELECT d.sale_date, sp.store_id, sp.product_id FROM calendar d CROSS JOIN store_product sp" }
```

## The footgun, concretely

```sql
-- Q: "Average daily units of P-100 at store S1 in March?"
-- GUESS (plausible, and wrong): averages only the days that HAVE rows
SELECT AVG(units) FROM daily_sales
WHERE store_id='S1' AND product_id='P-100' AND sale_date BETWEEN DATE '2026-03-01' AND DATE '2026-03-31';
-- (4 + 6) / 2 = 5.0  — but if absence means genuine zero, the real denominator is 31, not 2  ❌
```

```sql
-- GROUNDED (null_semantics = genuine_zero): densify to the full grid, COALESCE absent days to 0, then AVG
SELECT AVG(units) FROM (
  SELECT g.sale_date, COALESCE(f.units, 0) AS units
  FROM (SELECT sale_date FROM calendar WHERE sale_date BETWEEN DATE '2026-03-01' AND DATE '2026-03-31') g
  LEFT JOIN daily_sales f
    ON f.sale_date = g.sale_date AND f.store_id='S1' AND f.product_id='P-100'
);                                  -- (4 + 6 + 0×29) / 31 ≈ 0.32  ✅  (and if it were not_loaded, we'd refuse to impute)
```

Same query, two answers differing ~15×. The difference is one declared fact — *what a missing row means* —
that the data could not provide and `null_semantics` does.
