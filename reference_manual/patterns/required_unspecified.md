---
title: "Pattern — Required-but-unspecified dimension (ask, don't default)"
part_of: reference_manual/patterns
status: prototype
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (illustrative shop scenario).
---

# Pattern — Required-but-unspecified dimension

## Initial state — what you're handed

The schema has the axes; the **question** omits a required one. There is no table to show — the constellation
is a *question shape*:

```text
Question:  "What was revenue?"
Schema has: sales(amount, sale_date, region, scenario, ...)
Missing from the question: a PERIOD bound (and arguably a region).
```

**Why this is dangerous.** `revenue` is a measure; a measure with no period bound silently `SUM`s **all
loaded time** — including forward-dated plan rows — overstating by ~20–30×. The axis is *required* for a
meaningful answer, the question left it out, and there is **no safe default** (unlike `scenario`, which
defaults to ACTUAL). Filling one silently is a wrong answer with a confident face.

## The question, and the answer

> **The question:** *A required dimension is unspecified and no safe default exists — fill it, or ask?*
>
> **The answer:** *Ask. Declare which axes are required and whether each has a safe default; if required +
> unspecified + no default → abstain (⊥) and ask. (Contrast `axis_default`: when a safe default DOES exist,
> fill it.)*

## The pattern (the structured entry)

```yaml
pattern: required_unspecified
also_known_as: [mandatory dimension, missing period, underspecified query, ask-don't-guess]
tradition: cross-cutting   # this framework's addition
constellation: >
  A dimension that is REQUIRED for a meaningful answer (period for a measure; region for a non-additive
  geographic measure) is absent from the question, and no safe default exists for it.
prior_art:
  relational: >
    The query just runs against whatever filter is (or isn't) there; an unbounded measure SUMs everything
    silently. No notion of "this axis was required."
  dimensional: >
    Tools may have a default time filter — but a silent default is itself a guess; whether an axis is
    *required* is undocumented.
  rdf: >
    Not applicable — querying is the consumer's job.
mac_expression: >
  Declare per measure/concept which axes are REQUIRED and whether each has a safe default. At query time:
  required + unspecified + no-default → `ambiguity` → abstain (⊥) and ASK, offering the choice. REUSES the
  `ambiguity_gate` canon. The distinction from `axis_default` is the whole point: default when safe, ask when
  not.
why_better: >
  "This axis is required and has no default" becomes an explicit fact, so the system asks instead of silently
  summing all-time (the classic ~20–30× inflation) — and the ask is mechanical, not model-mood.
projects_to:
  rdf: "a cardinality/required annotation on the relation"
  graph: "a required-property constraint"
  relational: "a NOT-NULL-ish query contract / a mandatory filter"
antipattern: >
  Silently summing a measure with no period; defaulting a required axis the user never set; treating
  'required + no default' the same as 'has a safe default'.
status: scattered   # ambiguity rule + ask-don't-guess exist (query_rules); naming the required-axis case is new
canon_ref: [query_rules (measure.period_mandatory, ambiguity.ask_dont_guess), canon/ambiguity_gate.md, patterns/competing_definitions.md]
```

## The determinism border

| Behaviour | Kind | How |
| --- | --- | --- |
| Which axes are required / have a safe default | **skeleton** | per-measure `required` + `default` declarations |
| Required + unspecified + no default → ASK | **canon-backed** (reused) | [`ambiguity_gate`](../canon/ambiguity_gate.md) |
| *Which* period/region the user then means | **prose-fallback** | the clarifying answer (interpretation) |

```yaml
revenue:
  required_axes: [period]            # period is mandatory; no safe default
  realized_by: { udf: ambiguity_gate, params: { term: period, candidates: [], pinned: null } }   # empty+unpinned → ASK
```

## The footgun, concretely

```sql
-- GUESS: revenue with no period → sums all loaded time, incl. forward plan rows
SELECT SUM(amount) FROM sales;     -- ~20–30× overstated; looks like a clean number  ❌
-- GROUNDED: period is required, no default → ambiguity_gate fires → ASK
--   "Revenue over which period? (e.g. last quarter, FY2025, a custom range)"   ✅
```
