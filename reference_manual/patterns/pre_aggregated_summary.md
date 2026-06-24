---
title: "Pattern — Pre-aggregated summary (a rollup you must not re-aggregate)"
part_of: reference_manual/patterns
status: prototype
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (illustrative shop scenario).
---

# Pattern — Pre-aggregated summary

## Initial state — what you're handed

A summary table that is **already aggregated** to a monthly grain:

```sql
CREATE TABLE monthly_sales_summary (
  month VARCHAR, product_id VARCHAR,
  total_amount DECIMAL(14,2),   -- SUM of line amounts that month
  order_count  INTEGER          -- COUNT of orders that month
);
```

| month | product_id | total_amount | order_count |
| --- | --- | --- | --- |
| 2026-01 | P-100 | 4800.00 | 220 |
| 2026-02 | P-100 | 5040.00 | 240 |

**Why this is dangerous.** Each row is a `SUM`, not a sale. `AVG(total_amount)` is the *average of monthly
sums* (≈ "average month"), **not** the average sale value. Joining this to the detail fact and summing
**double-counts**. And you cannot decompose below the month — the detail isn't here.

## The question, and the answer

> **The question:** *At what grain is this already aggregated, and what may I (not) do with it?*
>
> **The answer:** *Grain = (month, product). It's additive ACROSS its grain (sum across months/products), but
> non-decomposable BELOW it, and must never be UNIONed/joined with the detail. Declare the grain + a
> "pre-aggregated" guarantee; the additivity guard treats sub-grain axes as non-aggregable.*

## The pattern (the structured entry)

```yaml
pattern: pre_aggregated_summary
also_known_as: [summary table, aggregate fact, rollup table, pre-aggregation]
tradition: dimensional
constellation: >
  A table already aggregated to a grain coarser than the detail fact. Additive across its own grain, but
  non-decomposable below it, and double-counting if mixed with the detail.
prior_art:
  relational: >
    A summary table; that it's pre-aggregated (and at what grain) is undocumented, so AVG-of-sums and
    detail-mixing happen silently.
  dimensional: >
    An aggregate fact / summary navigator — well understood; the "don't re-aggregate below grain, don't mix
    with detail" rules are tribal / engine-specific.
  rdf: >
    Not idiomatic; would be a derived dataset.
mac_expression: >
  A `measure` with an explicitly declared GRAIN + a `guarantee` that it is pre-aggregated at that grain. The
  [`additivity_guard`](../canon/additivity_guard.md) is reused with sub-grain axes marked `non_aggregable`
  (you may sum across months and products; you may NOT split a month, nor AVG the sums as if they were
  sales). A separate rule forbids UNION/JOIN with the detail fact. No new structure.
why_better: >
  The grain and the "already summed" fact become explicit, so an agent sums across the grain correctly,
  computes a real average (SUM/SUM, or goes to detail) instead of averaging sums, and never double-counts by
  mixing summary with detail.
projects_to:
  rdf: "a derived dataset annotated with its grain"
  graph: "an aggregate node with a grain property"
  relational: "the aggregate fact + a summary-navigation rule"
antipattern: >
  `AVG(total_amount)` as "average sale" (it's average-of-sums); joining summary to detail and summing
  (double-counts); querying below the declared grain (the detail isn't there).
status: scattered   # grain + guarantee + reused additivity_guard express it; the grain bound is the fact to state
canon_ref: [canon/additivity_guard.md, CONCEPT_SPEC.md §6 (grounding.grain, guarantee), MODELLERS_COOKBOOK.md C6]
```

## The determinism border

| Behaviour | Kind | How |
| --- | --- | --- |
| The summary's grain + "pre-aggregated" fact | **skeleton** | declared `grain` + a `guarantee` |
| No decomposition below grain; correct cross-grain sums | **canon-backed** (reused) | [`additivity_guard`](../canon/additivity_guard.md), sub-grain axes `non_aggregable` |
| Don't mix with the detail fact | **canon-able / rule** | a no-UNION-with-detail rule |
| interpretative remainder | **minimal** | the grain decides |

## The footgun, concretely

```sql
-- GUESS: "average sale value" from the summary
SELECT AVG(total_amount) FROM monthly_sales_summary WHERE product_id = 'P-100';
-- (4800 + 5040) / 2 = 4920 — that's the average MONTH, not the average sale  ❌
-- GROUNDED: a real average is SUM/SUM (or go to detail); never AVG the pre-summed column
SELECT SUM(total_amount) / SUM(order_count) AS avg_order_value
FROM monthly_sales_summary WHERE product_id = 'P-100';   ✅
```
