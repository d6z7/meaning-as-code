---
title: "Pattern — Supertype / subtype (table or class inheritance)"
part_of: reference_manual/patterns
status: prototype
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (illustrative shop scenario).
---

# Pattern — Supertype / subtype

## Initial state — what you're handed

A `product` table with a `kind` discriminator and attributes that apply only to *some* kinds:

```sql
CREATE TABLE product (
  product_id VARCHAR, name VARCHAR, kind VARCHAR,   -- 'physical' | 'digital'
  weight_kg  DECIMAL(8,3),    -- physical only; NULL for digital
  download_url VARCHAR        -- digital only; NULL for physical
);
```

| product_id | name | kind | weight_kg | download_url |
| --- | --- | --- | --- | --- |
| P-100 | Trail Mug | physical | 0.350 | *(null)* |
| P-300 | Trail Map PDF | digital | *(null)* | https://… |

**Why this is dangerous.** `weight_kg` is `NULL` for every digital product — not because the weight is
*missing*, but because it does not *apply*. Aggregate or filter `weight_kg` across all products and you
silently mix "no value because N/A" with "no value because unknown" — the [absence-semantics](absence_semantics.md)
trap, here caused by inheritance.

## The question, and the answer

> **The question:** *Is `product` one homogeneous thing, or a supertype with kind-specific subtypes?*
>
> **The answer:** *A supertype with subtypes. Model the is-a hierarchy with `subclasses:`; subtype-only
> attributes belong to their subtype, and a subtype attribute is `structurally_untracked` for the others.*

## The pattern (the structured entry)

```yaml
pattern: supertype_subtype
also_known_as: [is-a hierarchy, table inheritance, single/class-table inheritance, generalization]
tradition: relational   # + RDF rdfs:subClassOf
constellation: >
  A concept has subtypes that share common attributes but each add their own; a discriminator column says
  which subtype a row is, and subtype-specific columns are NULL-because-N/A for the others.
prior_art:
  relational: >
    Single-table (one table + a kind column + nullable subtype columns), class-table (a table per subtype),
    or concrete-table inheritance. The "NULL means not-applicable" fact is undocumented.
  dimensional: >
    Usually flattened; the subtype distinction and its N/A columns are left implicit.
  rdf: >
    rdfs:subClassOf — native and clean; subtype properties have domains on the subclass.
mac_expression: >
  Model the supertype as the concept and the subtypes via `subclasses:` (is-a). Common attributes sit on the
  supertype; subtype-only attributes are documented on their subclass, with `null_semantics:
  structurally_untracked` for rows of other subtypes. The `kind` column is the discriminator (an
  `enumeration`). No new structure — `entity` + `subclasses` already express it.
why_better: >
  The is-a hierarchy and the not-applicable-ness of subtype columns become explicit and agent-readable, so a
  query about `weight_kg` is correctly scoped to physical products instead of averaging NULLs across digital
  ones. Another confirmation that the six structures suffice.
projects_to:
  rdf: "rdfs:subClassOf + per-subclass property domains"
  graph: "label hierarchy / an :IS_A edge"
  relational: "the inheritance mapping (single-/class-table) + a CHECK on the discriminator"
antipattern: >
  Treating the supertype as homogeneous (averaging subtype-only columns across all rows); or splitting into
  unrelated concepts and losing the shared identity.
status: scattered   # subclasses + null_semantics express it; never named as a pattern — a "six suffice" confirmation
canon_ref: [FRAMEWORK.md §5 (subclasses / is-a), CONCEPT_SPEC.md §6 (subclasses, null_semantics)]
```

## The determinism border

A **structural** pattern: skeleton decides, no behavioural canon.

| Behaviour | Kind | How |
| --- | --- | --- |
| The is-a hierarchy | **skeleton** | `subclasses:` on the concept |
| A subtype column is N/A (not unknown) for other subtypes | **skeleton** | `null_semantics: structurally_untracked` (→ [absence_semantics](absence_semantics.md)) |
| Scoping a subtype-only query to its subtype | **skeleton** | the `kind` discriminator |
| interpretative remainder | **none** | structural |

## The footgun, concretely

```sql
-- GUESS: average weight "of products" — silently includes digital products' N/A NULLs in the population
SELECT AVG(weight_kg) FROM product;                          -- denominator ambiguity, mixes N/A with unknown  ❌
-- GROUNDED: weight is a PHYSICAL-subtype attribute; scope to it
SELECT AVG(weight_kg) FROM product WHERE kind = 'physical';  ✅
```
