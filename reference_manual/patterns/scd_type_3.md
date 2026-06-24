---
title: "Pattern — Slowly-Changing Dimension, Type 3 (prior value in a column)"
part_of: reference_manual/patterns
status: prototype
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (illustrative shop scenario).
---

# Pattern — Slowly-Changing Dimension, Type 3

## Initial state — what you're handed

A dimension that keeps only the **previous** value of an attribute alongside the current one:

```sql
CREATE TABLE dim_product (
  product_id VARCHAR, name VARCHAR,
  category          VARCHAR,   -- current
  previous_category VARCHAR,   -- the one prior value; older history is gone
  category_changed_on DATE
);
```

| product_id | category | previous_category | category_changed_on |
| --- | --- | --- | --- |
| P-100 | Drinkware | Kitchen | 2026-02-10 |

**Why this is dangerous.** It *looks* like history, but it is **one step only** — the category before
Kitchen is gone. Treat `previous_category` as "the history" and any question deeper than one change is
silently answered with fabricated confidence.

## The question, and the answer

> **The question:** *How much history does this dimension retain?*
>
> **The answer:** *Exactly one prior step — current + previous, no more. Model both as `properties:`; declare
> the one-step limit as `scope`, so a deeper question is refused, not guessed.*

## The pattern (the structured entry)

```yaml
pattern: scd_type_3
also_known_as: [SCD type 3, prior-value column, limited-history dimension]
tradition: dimensional
constellation: >
  A dimension retains only the prior value of an attribute in a sibling column (current + previous), not a
  full version history. Bounded, one-step memory.
prior_art:
  relational: >
    A `previous_*` column. Cheap; but "only one step is kept" is undocumented, so consumers over-read it as
    full history.
  dimensional: >
    The canonical Kimball SCD-3 — well defined, but the one-step bound lives in the modeller's head.
  rdf: >
    A separate "previous value" property; the bound is not expressed.
mac_expression: >
  Two `properties:` — `category` (current) and `previous_category` (prior) — plus a `semantics.scope` fact
  stating history depth = 1 (older changes not retained). Contrast `scd_type_2`, which keeps FULL history as
  an as-of axis; SCD-3 is deliberately lossy. No new structure.
why_better: >
  The retention LIMIT becomes an explicit, agent-readable fact, so a question that needs deeper history is
  ABSTAINED on (→ ambiguity/⊥) rather than answered from the single prior value as if it were complete.
projects_to:
  rdf: "current + previous datatype properties + an annotation of depth"
  graph: "two properties on the node"
  relational: "the SCD-3 columns"
antipattern: >
  Reading `previous_category` as "the history"; computing a change-count or a multi-step trajectory from a
  one-step column.
status: scattered   # properties + scope express it; the depth-bound is the fact that needs stating
canon_ref: [CONCEPT_SPEC.md §6 (properties, semantics.scope)]
```

## The determinism border

| Behaviour | Kind | How |
| --- | --- | --- |
| Current and prior values | **skeleton** | two `properties:` |
| History depth = 1 (older gone) | **skeleton** | `semantics.scope` |
| A deeper-history question | **prose-fallback → ⊥** | abstain (the scope fact triggers it) |

No behavioural canon — the discipline is *declaring the limit* so the agent does not fabricate beyond it.

## The footgun, concretely

```text
Q: "What category was P-100 two changes ago?"
GUESS:    read previous_category → "Kitchen" — but that's ONE change ago; two-ago is unknowable.  ❌
GROUNDED: scope says depth = 1 → ABSTAIN: "only the immediately-prior value is retained."           ✅
```
