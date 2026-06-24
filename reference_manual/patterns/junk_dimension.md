---
title: "Pattern — Junk dimension (a grab-bag of low-cardinality flags)"
part_of: reference_manual/patterns
status: prototype
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (illustrative shop scenario).
---

# Pattern — Junk dimension

## Initial state — what you're handed

Several unrelated low-cardinality flags bundled into one physical "junk" table to avoid a swarm of tiny
dimensions:

```sql
CREATE TABLE order_flags (
  flags_key VARCHAR,    -- surrogate; the fact joins on this
  is_gift   BOOLEAN, is_promo BOOLEAN, channel VARCHAR   -- 'web' | 'store' | 'phone'
);
```

**Why this is dangerous.** The *physical* bundling tempts you to model the bundle as **one** thing — a
single "OrderFlags dimension" — which buries three independent meanings (gift? promo? which channel?) behind
one surrogate, and makes `channel` un-findable as a concept.

## The question, and the answer

> **The question:** *Is this junk table one dimension, or several flags that happen to share a table?*
>
> **The answer:** *Several. Each flag is its own meaning — model each as its own `enumeration`. The bundling
> is a **physical/storage** choice MAC is neutral to: the enumerations simply ground to columns of the
> shared table.*

## The pattern (the structured entry)

```yaml
pattern: junk_dimension
also_known_as: [junk dimension, grab-bag dimension, flag bundle]
tradition: dimensional
constellation: >
  Several unrelated, low-cardinality flags are physically bundled into one table (with a surrogate key) to
  avoid many tiny dimension tables.
prior_art:
  relational: >
    The flags might be columns on the fact, or a shared lookup; whether they're "one dimension" is a storage
    artefact, not a meaning.
  dimensional: >
    Kimball's junk dimension — a storage optimization (one table for a Cartesian-ish set of flags); the
    individual flags are still distinct meanings.
  rdf: >
    Each flag is just its own property/value-set; no notion of bundling.
mac_expression: >
  Model each flag as its OWN `enumeration` (small closed set: is_gift {true,false}, channel {web,store,
  phone}). Each grounds to its column (`grounds_column`) in the shared junk table; the junk surrogate key is
  a PHYSICAL join key, not meaning. The framework is neutral to the bundling — meaning is per-flag. No new
  structure.
why_better: >
  Each flag stays a first-class, findable concept with its own closure, instead of being buried behind one
  surrogate. The physical optimization (bundling) and the meaning (N enumerations) are cleanly separated —
  another "six suffice" confirmation: the junk dimension is N enumerations, not a new kind of thing.
projects_to:
  rdf: "N value-sets / enumerated properties"
  graph: "N node properties"
  relational: "the junk dimension table (a grounding detail) backing N enumerations"
antipattern: >
  Modelling the bundle as ONE enumeration/dimension (buries the individual flags); treating the junk
  surrogate key as semantically meaningful.
status: scattered   # N enumerations + shared grounding express it — a "six suffice" confirmation, NOT a finding
canon_ref: [CONCEPT_SPEC.md §6 (enumerations, grounds_column), FRAMEWORK.md §5]
```

## The determinism border

A **structural** pattern — skeleton (N enumerations), no canon.

| Behaviour | Kind | How |
| --- | --- | --- |
| Each flag is its own meaning | **skeleton** | N `enumeration` concepts |
| The bundling is physical, not semantic | **skeleton** | each enumeration's `grounds_column` on the shared table |
| interpretative remainder | **none** | structural |

## The footgun, concretely

```text
OVER-BUNDLE: one "OrderFlags" enumeration keyed by flags_key
  → "how many web orders?" can't bind to a `channel` concept; the flags are invisible.  ❌
GROUNDED: is_gift, is_promo, channel are three enumerations grounding to order_flags columns;
          "web orders" binds to channel = 'web'.  ✅
```
