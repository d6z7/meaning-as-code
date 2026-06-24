---
title: "Pattern — Tracking vintage (actual / plan / budget as an orthogonal axis)"
part_of: reference_manual/patterns
status: prototype
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (illustrative shop scenario).
---

# Pattern — Tracking vintage

## Initial state — what you're handed

The shop's sales fact carries several co-existing "versions" of the same number — what actually happened,
what was planned, what was budgeted — in one `scenario` column:

```sql
CREATE TABLE sales_fact (
  month       DATE,
  product_id  VARCHAR,
  scenario    VARCHAR,        -- ACTUAL | PLAN | BUDGET
  amount      DECIMAL(12,2)
);
```

| month | product_id | scenario | amount |
| --- | --- | --- | --- |
| 2026-03 | P-100 | ACTUAL | 1200 |
| 2026-03 | P-100 | PLAN | 1000 |
| 2026-03 | P-100 | BUDGET | 1100 |
| 2026-12 | P-100 | PLAN | 1500 |
| 2026-12 | P-100 | BUDGET | 1400 |

**Why this is dangerous.** The first three rows are **the same cell, measured three ways** — they must never
be summed (that triples March). And PLAN/BUDGET extend into the **future**, where no ACTUAL exists yet, so a
naïve "latest month" (`MAX(month)`) returns the *planning horizon* (Dec), not the latest actual (Mar). The
`scenario` column looks like just another dimension to filter on, but it is an **axis every query must pin** —
and it is independent of (orthogonal to) the reporting cycle, so the two are easy to conflate.

## The question, and the answer

> **The question** (what the data can't tell you): *Which scenario does "sales" mean — and may I aggregate
> across scenarios?*
>
> **The answer** (the fact we supply): *No — ACTUAL, PLAN, BUDGET are an **orthogonal tracking axis** over
> the same cell; pin exactly one (default ACTUAL) and never sum across them. "Latest month" resolves over
> the **pinned** scenario's rows, not the whole table.*

## The pattern (the structured entry)

```yaml
pattern: tracking_vintage
also_known_as: [scenario dimension, actual/plan/budget, tracking variant, version dimension, what-if axis]
tradition: dimensional   # with a cross-cutting "orthogonal axis" core
constellation: >
  A fact carries several co-existing versions of the same measurement (actual / plan / budget / forecast)
  as an axis ORTHOGONAL to time and to any reporting cycle. The cross-product is real: every scenario
  exists at every period, and the versions overlap on the same logical cell.
prior_art:
  relational: >
    A `scenario` column. Nothing stops `SUM` across it; nothing marks "pick exactly one"; nothing says which
    value is the default. The "actuals only, please" discipline is on every query author.
  dimensional: >
    Kimball models it as a scenario/version dimension — but the rules "never mix scenarios" and "actuals are
    the default" live in the cube config and the modeller's head, and a hand-written query bypasses both.
  rdf: >
    Separate named graphs (or scenario-qualified statements) per version — expressive, but nothing forces a
    query to scope to one, and the future-dated plan rows still contaminate a naïve "latest".
mac_expression: >
  Model the tracking variant as its OWN axis/concept (the orthogonal-axis principle, CONCEPT_SPEC §8),
  explicitly distinct from the reporting cycle. A `default` rule (`mac.rule_kind.default`) pins ACTUAL when
  the question is silent; an `exclusion`/`aggregation` rule forbids summing across scenarios; and relative-
  period resolution (the `MAX(month)` that means "now") is scoped to the PINNED scenario's rows, so the
  plan horizon never leaks in.
why_better: >
  The orthogonal axis is named and its cross-product is explicit, so an agent cannot (a) conflate scenario
  with the reporting cycle — a model-INVERTING error — nor (b) silently sum actual+plan+budget, nor (c)
  resolve "latest" against future plan rows. The actuals-default and the scoped-MAX are single-homed rules
  inherited by every query, not lore re-applied (or forgotten) per question.
projects_to:
  rdf: "named graphs / scenario-qualified statements per version"
  graph: "a scenario property + a 'pin exactly one' constraint"
  relational: "a scenario/version dimension + a default-scenario convention"
antipattern: >
  Treating `scenario` as an ordinary filter dimension and forgetting to pin it (COOKBOOK C9 — two orthogonal
  axes modelled as one); a global `MAX(date)` that lands on the plan horizon instead of the latest actual
  (the relative-period sibling of this footgun).
status: scattered   # CONCEPT_SPEC §8 (orthogonal axes) + the default/exclusion rule kinds exist; never named as a pattern
canon_ref: [CONCEPT_SPEC.md §8, mac_vocabulary.yaml (rule_kind.default / exclusion / aggregation), MODELLERS_COOKBOOK.md C9]
```

## The determinism border

Per [AUTHORING.md](../AUTHORING.md) A4 — and this is the first pattern whose `realized_by` is a **list** of
canons that **compose** (and **reuse** an existing one):

| Behaviour | Kind | How |
| --- | --- | --- |
| Never `SUM` across `scenario` (three measurements of one cell) | **canon-backed** | [`additivity_guard`](../canon/additivity_guard.md) **reused**, `{ scenario: non_aggregable }` |
| Default to `ACTUAL` when the question names no scenario | **canon-backed** | [`axis_default`](../canon/axis_default.md) injects `scenario = ?` |
| "Latest month" = `MAX` over the **pinned** scenario, not the whole table | **canon-backed** | [`scoped_latest`](../canon/scoped_latest.md) |
| *Which* relative period "last quarter" denotes | **prose-fallback** | interpretation of the question |

```yaml
scenario:
  prose: "ACTUAL/PLAN/BUDGET are an orthogonal tracking axis over one cell; pin exactly one (default ACTUAL); never sum across them."
  realized_by:
    - { udf: additivity_guard, params: { measure_column: amount, axis_effects: { scenario: non_aggregable, month: additive } } }
    - { udf: axis_default,     params: { axis_column: scenario, default_value: ACTUAL } }
    - { udf: scoped_latest,    params: { table: sales_fact, date_column: month, scope: { scenario: ACTUAL } } }
```

Three of the four behaviours are now canon-backed, one **reused unchanged** (`additivity_guard`) — the
library compounds. The lone remaining prose-fallback is *which* relative period a question means — the
irreducible interpretation, now anchored deterministically by `scoped_latest`.

## The footgun, concretely

```sql
-- Q: "What were sales in March?"
-- GUESS (plausible, and wrong): sums all three scenarios
SELECT SUM(amount) FROM sales_fact WHERE month = '2026-03';      -- 1200 + 1000 + 1100 = 3300  ❌
-- GROUNDED: pin the scenario (default ACTUAL)
SELECT SUM(amount) FROM sales_fact WHERE month = '2026-03' AND scenario = 'ACTUAL';   -- 1200  ✅
```

```sql
-- Q: "What's the latest month of sales?"
-- GUESS: MAX over the whole table → the plan horizon
SELECT MAX(month) FROM sales_fact;                               -- 2026-12 (a PLAN month, no actuals)  ❌
-- GROUNDED: MAX scoped to the pinned scenario
SELECT MAX(month) FROM sales_fact WHERE scenario = 'ACTUAL';     -- 2026-03  ✅
```

Both errors come from the *same* unstated fact: `scenario` is an axis you must pin, not a dimension you may
ignore. Naming it as an orthogonal axis — with a default and a no-sum rule — closes both at once.
