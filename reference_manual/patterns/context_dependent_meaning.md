---
title: "Pattern — Context-dependent meaning (a code meaningless without its parent)"
part_of: reference_manual/patterns
status: prototype
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (illustrative shop scenario).
---
# Pattern — Context-dependent meaning

## Initial state — what you're handed

Products carry a `size_code`; each brand publishes its own size chart in a separate table:

```sql
CREATE TABLE product (
  product_id VARCHAR, name VARCHAR, brand_id VARCHAR, size_code VARCHAR
);
CREATE TABLE brand_size_chart (
  brand_id VARCHAR, size_code VARCHAR, chest_cm INTEGER
);
```

`product`

| product_id | name          | brand_id | size_code |
| ---------- | ------------- | -------- | --------- |
| P-200      | Alpine Jacket | BR-NORD  | M         |
| P-201      | Summit Tee    | BR-PEAK  | M         |

`brand_size_chart`

| brand_id | size_code | chest_cm |
| -------- | --------- | -------- |
| BR-NORD  | M         | 100      |
| BR-PEAK  | M         | 94       |

**Why this is dangerous.** Both products are `M` — but BR-NORD's `M` (100 cm chest) is essentially BR-PEAK's
`L`. The string `'M'` is not a size; `(brand_id, 'M')` is. The meaning of the code lives in *another table*,
reachable only through a join nobody is forced to make — so `WHERE size_code = 'M'` compiles, runs, and
quietly adds incomparable garments together.

## The question, and the answer

> **The question** (what the data can't tell you): *Does `size_code = 'M'` mean the same thing in every row?*
>
> **The answer** (the fact we supply): *No — its meaning is **scoped by `brand_id`**; identity is
> `(brand_id, size_code)`, never the bare code. Supplied as a scoped resolution rule that forbids equality
> on the code alone.*

## The pattern (the structured entry)

```json
pattern: context_dependent_meaning
also_known_as: [context-dependent code, parent-scoped value, homonymous code, qualified identity]
tradition: cross-cutting   # this framework's own addition — no equivalent named pattern in Kimball/RDF
constellation: >
  The same coded value means different things under different parents. An apparel size "M" maps to
  different body measurements depending on the garment's BRAND; the code "M" is not interpretable — and two
  "M" rows are not comparable — without knowing the parent it sits under. Filtering or grouping on the code
  alone silently conflates incomparable things.
prior_art:
  relational: >
    The value is stored as-is. The (brand, size_code) → measurements mapping, if it exists, lives in a
    lookup nobody joins consistently. `WHERE size_code = 'M'` compiles, runs, and quietly mixes a size-M
    dress from one brand with a size-M shoe from another. Nothing flags that the code is parent-scoped.
  dimensional: >
    Modelled as a dimension attribute or a junk dimension. There is no mechanism that records "this code's
    meaning depends on its parent" — the warehouse treats 'M' as a global value.
  rdf: >
    You COULD model per-brand SKOS concept schemes so each brand's 'M' is a distinct concept — but nothing
    forces a query/resolver to scope by parent, and the default reading conflates them.
mac_expression: >
  A scoped resolution rule (`mac.rule_kind.resolution`) on the concept: identity/scoping MUST include the
  parent — resolve a size by (brand, size_code), NEVER by size_code alone. The rule is typed (when → then →
  never), `binds` the columns it governs, and is enforced; the concept's `semantics.scope` states that the
  code is parent-relative.
why_better: >
  "This code is meaningless without its parent" becomes a FIRST-CLASS, typed, checkable fact instead of
  tribal knowledge. An agent that writes `size_code = 'M'` across brands is doing exactly the thing the
  rule's `never` clause forbids — so the error is caught, not silently returned. No other framework makes
  context-dependent identity an enforceable rule; this is one of the constellations that motivated the
  framework.
projects_to:
  rdf: "per-context concept schemes / qualified (parent, code) relations"
  graph: "a parent-qualified composite node key"
  relational: "a composite key (brand, size_code) + a CHECK/join that enforces it"
antipattern: >
  Equality on the bare code; treating a context-dependent code as a single global enumeration; pushing the
  parent-scoping into a comment instead of a typed resolution rule.
status: clean   # mac.rule_kind.resolution + scoped resolution + binds support this directly
canon_ref: [mac_vocabulary.yaml (rule_kind.resolution), CONCEPT_SPEC.md §6 semantics.scope, query_rules (resolve.by_semantic_identity)]
```

## The determinism border

Per [AUTHORING.md](../AUTHORING.md) A4 and [the content model](../the_content_model.md), here is exactly what
this pattern guarantees by **canon** (deterministic) and what it leaves to **prose** (interpretative):

| Behaviour | Kind | How |
| --- | --- | --- |
| Identity is keyed on `(brand_id, size_code)` — never the bare code | **canon-backed** | the [`composite_key_guard`](../canon/composite_key_guard.md) canon |
| Catching that a bare-code filter was written | **canon-backed** | the same guard, at the SQL gate |
| *Which* brand "size M" means when the question is silent | **prose-fallback** (interpretative) | the agent asks — the irreducible question-reading step |

**The canon** — the prose *"resolve by `(brand, size_code)`, never the bare code"* is realized not by a
per-concept snippet but by **naming a generic library UDF and binding its parameters** (content model §5;
single-homing per AUTHORING A3 — the logic lives once, in
[canon/composite_key_guard.md](../canon/composite_key_guard.md)):

```yaml
scope:
  prose: "A size code is parent-relative: it identifies a size only together with its brand."
  realized_by:
    udf: composite_key_guard          # generic canon — logic lives in the library, once
    params: { code_column: size_code, scope_columns: [brand_id] }
```

The point of the border: a **weak** model that forgets the rule still cannot ship the bad query — the guard
**rejects** a bare `size_code = 'M'`. The only soft step left is *which* brand — the one a human would have
had to ask too. Determinism is bought everywhere the canon reaches; prose carries only the genuinely
interpretative remainder.

## The footgun, concretely

The shop sells apparel from several brands; each brand publishes its own size chart, so size "M" is a
different set of body measurements per brand. Ask *"how many size-M items did we sell?"*

```sql
-- GUESS (plausible, and wrong): 'M' is treated as a global size
SELECT COUNT(*) FROM order_line ol JOIN product p ON p.id = ol.product_id
WHERE p.size_code = 'M';     -- conflates brand-X 'M' with brand-Y 'M' — incomparable sizes counted as one
```

```sql
-- GROUNDED: a size is resolved by (brand, size_code); the question, as asked, is under-specified
-- → the resolution rule fires and the agent ASKS which brand's size chart "M" refers to, or returns
--   the count broken out per brand rather than a single conflated number.
```

The grounded behaviour is not "a better query" — it is the model *refusing the conflation* the bare code
invites. The fact that made the difference ("size is parent-scoped") is exactly the kind of meaning that
has no home in a schema, a cube, or an RDF graph, and a typed home here.
