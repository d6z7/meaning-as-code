---
title: "Pattern — Accumulating snapshot (one row, several milestone dates)"
part_of: reference_manual/patterns
status: prototype
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (illustrative shop scenario).
---

# Pattern — Accumulating snapshot

## Initial state — what you're handed

One row per order that *fills in* as the order moves through its pipeline:

```sql
CREATE TABLE order_pipeline (
  order_id VARCHAR,
  placed_at    DATE,
  paid_at      DATE,
  shipped_at   DATE,    -- NULL until shipped
  delivered_at DATE     -- NULL until delivered
);
```

| order_id | placed_at | paid_at | shipped_at | delivered_at |
| --- | --- | --- | --- | --- |
| O-1 | 2026-03-01 | 2026-03-01 | 2026-03-03 | 2026-03-06 |
| O-2 | 2026-03-05 | 2026-03-05 | *(null)* | *(null)* |

**Why this is dangerous.** O-2's `delivered_at` is NULL because it *hasn't happened yet*, not because it's
missing. `AVG(delivered_at − placed_at)` over all rows either errors or silently drops in-flight orders —
and "average delivery time" computed over only-delivered rows is a *survivorship* number unless you say so.

## The question, and the answer

> **The question:** *What does a NULL milestone date mean, and which durations are even defined yet?*
>
> **The answer:** *A NULL milestone = not-yet-reached (a lifecycle state, not missing data). Durations are
> derived measures defined only between reached milestones; in-flight rows are excluded from a
> completed-duration average — explicitly, not silently.*

## The pattern (the structured entry)

```yaml
pattern: accumulating_snapshot
also_known_as: [accumulating snapshot fact, pipeline fact, milestone fact, lag measures]
tradition: dimensional
constellation: >
  One fact row carries several milestone date stamps and is UPDATED in place as milestones complete; the
  durations between milestones are the measures, and unreached milestones are NULL-because-not-yet.
prior_art:
  relational: >
    Nullable milestone columns; the not-yet-vs-missing distinction and the survivorship of duration
    averages are undocumented.
  dimensional: >
    The canonical accumulating-snapshot fact with lag measures — well understood; the in-flight exclusion is
    tribal.
  rdf: >
    Milestones as states + transition timestamps; durations would be derived.
mac_expression: >
  An `event` concept with a `lifecycle:` (the milestones as ordered phases/states), the date columns as
  `properties:`, and the lags (e.g. delivered_at − placed_at) as derived `measure`s. A NULL milestone is
  `null_semantics: not_loaded`-like → "not yet reached" (a lifecycle fact); completed-duration measures
  exclude rows that haven't reached the end milestone, and SAY they do. No new structure (`event` + `measure`).
why_better: >
  The pipeline's states, the meaning of an unreached milestone, and the survivorship of a lag average all
  become explicit — so "average delivery time" is computed over completed orders by construction, with the
  exclusion disclosed, not a silent guess. Six structures suffice.
projects_to:
  rdf: "states + transition timestamps; lag = derived"
  graph: "milestone properties + state nodes"
  relational: "the accumulating-snapshot fact with lag measures"
antipattern: >
  Averaging a lag over all rows (errors / drops in-flight silently); reporting completed-only durations as
  "all orders" without disclosing survivorship; treating an unreached milestone as missing data.
status: scattered   # event lifecycle + measures + null_semantics express it; never named as a pattern
canon_ref: [FRAMEWORK.md §5 (event lifecycle), CONCEPT_SPEC.md §6 (lifecycle, null_semantics), patterns/absence_semantics.md]
```

## The determinism border

| Behaviour | Kind | How |
| --- | --- | --- |
| The milestone pipeline / states | **skeleton** | `event` `lifecycle:` |
| A NULL milestone = not-yet-reached | **skeleton** | `null_semantics` (→ [absence_semantics](absence_semantics.md)) |
| A completed-duration average excludes in-flight rows | **canon-backed** | a `WHERE end_milestone IS NOT NULL` guard (reuses the exclusion idea) |
| interpretative remainder | **minimal** | once the end-milestone requirement is stated |

## The footgun, concretely

```sql
-- GUESS: average delivery lag over everything
SELECT AVG(delivered_at - placed_at) FROM order_pipeline;     -- in-flight rows (NULL) distort / drop silently  ❌
-- GROUNDED: lag defined only for delivered orders; the exclusion is explicit
SELECT AVG(delivered_at - placed_at) FROM order_pipeline WHERE delivered_at IS NOT NULL;   ✅ (and disclose "delivered orders only")
```
