---
title: "Pattern — Multivalued bridge (a many-valued dimension)"
part_of: reference_manual/patterns
status: prototype
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (illustrative shop scenario).
---

# Pattern — Multivalued bridge

## Initial state — what you're handed

A product can carry **several** tags — a many-to-many via a bridge table:

```sql
CREATE TABLE product_tag (product_id VARCHAR, tag VARCHAR);   -- one product → many tags
```

| product_id | tag |
| --- | --- |
| P-100 | drinkware |
| P-100 | sale |
| P-100 | gift-idea |

**Why this is dangerous.** Two traps at once: (1) `WHERE tag = 'sale'` treats a *set-valued* attribute as
single-valued; (2) joining sales to tags and `SUM`ming revenue **by tag** counts P-100's revenue **three
times** (once per tag) — a sale isn't three sales because its product has three tags.

## The question, and the answer

> **The question:** *How do I filter and aggregate across an attribute a row has many of?*
>
> **The answer:** *Membership, not equality (`contains` / `EXISTS`), for filtering; and an additive measure
> summed across the multivalue **double-counts** — it needs an allocation factor or a distinct base, never a
> naïve `SUM ... GROUP BY tag`.*

## The pattern (the structured entry)

```yaml
pattern: multivalued_bridge
also_known_as: [multivalued dimension, bridge table, many-to-many dimension, array attribute, tag set]
tradition: dimensional   # + relational M:N + array columns
constellation: >
  A dimension a fact relates to MANY of at once (tags, categories, segments) — via a bridge table or an
  array column. Membership is set-valued, and additive measures don't sum cleanly across it.
prior_art:
  relational: >
    A bridge/junction; `= value` is wrong (it's set-valued), and joining-then-summing double-counts. Both
    traps are undocumented.
  dimensional: >
    Kimball's bridge table with an "allocation factor" to avoid double-counting — well known, but the
    factor (and the don't-use-equality rule) are tribal.
  rdf: >
    A multi-valued object property — natural; but the aggregation double-count is the consumer's problem.
mac_expression: >
  Model the multivalue as an `array` attribute (membership via `contains()`) or a bridge (an
  `associative_entity`). Filtering uses membership, enforced by the `array_membership_guard` canon (reject
  `= value` on a multivalued attribute; require `contains`/`EXISTS`). For an additive measure summed across
  the multivalue, declare it needs an **allocation factor** (or report distinct base counts) — otherwise it
  double-counts (a known limit, see border).
why_better: >
  The set-valued nature is explicit and the equality trap is CAUGHT; and the double-count hazard is a stated
  fact, so "revenue by tag" is allocated (or count-distinct) by design instead of silently tripled.
projects_to:
  rdf: "a multi-valued object property"
  graph: "multiple :TAGGED edges / a list property"
  relational: "the bridge table (+ allocation factor) or an array column"
antipattern: >
  `= value` on a multivalued attribute (use membership); `SUM(measure) GROUP BY tag` without allocation
  (double-counts multi-tagged rows).
status: scattered   # array-membership rule exists (query_rules attr.array_membership); the allocation hazard is a stated limit
canon_ref: [query_rules (attr.array_membership), CONCEPT_SPEC.md §6, patterns/associative_entity.md]
```

## The determinism border

| Behaviour | Kind | How |
| --- | --- | --- |
| Filter by membership, never equality | **canon-backed** | [`array_membership_guard`](../canon/array_membership_guard.md) |
| An additive measure double-counts across the multivalue | **data / caveat** | declared limit: needs an allocation factor or distinct base (not auto-solved) |
| interpretative remainder | **minimal** | the allocation policy is a modelling choice |

```yaml
tags:
  prose: "A product has a SET of tags; filter by membership; additive measures need allocation across them."
  realized_by:
    udf: array_membership_guard
    params: { column: tag, multivalued: true }
```

## The footgun, concretely

```sql
-- GUESS: equality on a set-valued attribute + sum that triple-counts
SELECT SUM(s.amount) FROM sales s JOIN product_tag t ON t.product_id = s.product_id
WHERE t.tag = 'sale' GROUP BY t.tag;     -- a 3-tag product's revenue counted 3×; '=' misses the set  ❌
-- GROUNDED: membership for the filter; distinct base (or an allocation factor) for the total
SELECT SUM(s.amount) FROM sales s
WHERE EXISTS (SELECT 1 FROM product_tag t WHERE t.product_id = s.product_id AND t.tag = 'sale');  ✅
```
