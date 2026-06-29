---
title: "Pattern — Degenerate dimension (a dimension key living in the fact)"
part_of: reference_manual/patterns
status: prototype
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (illustrative shop scenario).
---

# Pattern — Degenerate dimension

## Initial state — what you're handed

An `order_line` fact carries an `order_number` — an identifier you group and filter by, but which has **no
attributes of its own** and no dimension table:

```sql
CREATE TABLE order_line (
  order_number VARCHAR,   -- groups the lines of one order; no separate table, no own attributes
  product_id   VARCHAR, quantity INTEGER, unit_price DECIMAL(10,2)
);
```

**Why this is dangerous.** `order_number` *looks* like a foreign key to an Order dimension — so the instinct
is to invent an `Order` concept/table for it. But it has no attributes; it is just the **grouping grain** of
the lines. Over-modelling it as its own entity adds a phantom join and a table that isn't there.

## The question, and the answer

> **The question:** *Is `order_number` a foreign key to a dimension, or just a grouping key on the fact?*
>
> **The answer:** *A grouping key with no attributes — a degenerate dimension. Model it as a `property:` on
> the fact concept (it defines a grain), NOT as a separate `reference` concept and edge.*

## The pattern (the structured entry)

```yaml
pattern: degenerate_dimension
also_known_as: [degenerate dimension, dimension key in the fact, grouping key without a table]
tradition: dimensional
constellation: >
  An identifier sits in the fact, is used to group/filter (it defines a grain), but has no attributes of its
  own and no dimension table to join to.
prior_art:
  relational: >
    A column that looks like an FK but references nothing; modellers either orphan it or invent a table for it.
  dimensional: >
    Kimball's "degenerate dimension" — a dimension key with no dimension table; well understood, but the
    "don't build a table for it" guidance is tribal.
  rdf: >
    Would tend to mint a resource/IRI for it; here that's usually over-modelling.
mac_expression: >
  A `property:` on the fact/event concept that defines a grain — NOT a `reference` concept, NOT an edge.
  (If it later acquires attributes, it graduates to a `reference` — but absent attributes, a property is the
  honest model.) No new structure.
why_better: >
  The grain-defining key is modelled at its true weight — a property — instead of a phantom dimension with a
  join that doesn't exist. The contrast with `associative_entity` is exact: there, attributes PROMOTE a
  junction to a concept; here, the ABSENCE of attributes keeps an id as a property.
projects_to:
  rdf: "a literal datatype property (not a minted resource)"
  graph: "a node property"
  relational: "the degenerate dimension (a fact column, no dimension table)"
antipattern: >
  Inventing a dimension concept/table for an attribute-less grouping key; or dropping it and losing the grain
  it defines.
status: scattered   # a property expresses it; the "don't over-model" judgment is the point
canon_ref: [CONCEPT_SPEC.md §6 (properties), patterns/associative_entity.md]
```

## The determinism border

A **structural** pattern — skeleton decides, no canon. The mirror image of `associative_entity`: the
*presence* of non-key attributes promotes a junction to a concept; their *absence* keeps an id a property.

| Behaviour | Kind | How |
| --- | --- | --- |
| Model as a property, not a dimension | **skeleton** | the rule: *no own attributes ⇒ property, not a `reference`* |
| It defines a grain | **skeleton** | the property is part of the fact's grain |
| interpretative remainder | **none** | structural |

## The footgun, concretely

```text
OVER-MODEL: create an `Order` reference concept + an edge for `order_number`
  → a join to a table that doesn't exist, and a phantom entity with no attributes.  ❌
GROUNDED: `order_number` is a property of OrderLine that defines the order grain — no table, no edge.  ✅
```
