---
title: "Pattern — Associative entity (a junction that carries its own attributes)"
part_of: reference_manual/patterns
status: prototype
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (illustrative shop scenario).
---

# Pattern — Associative entity

## Initial state — what you're handed

A table linking orders and products — but it is more than a link: it carries its own facts.

```sql
CREATE TABLE order_line (
  order_id   VARCHAR,
  product_id VARCHAR,
  quantity   INTEGER,
  unit_price DECIMAL(10,2)
);  -- PK (order_id, product_id)
```

| order_id | product_id | quantity | unit_price |
| --- | --- | --- | --- |
| O-1 | P-100 | 2 | 12.00 |
| O-1 | P-200 | 1 | 90.00 |
| O-2 | P-100 | 5 | 12.00 |

**Why this is dangerous.** It *looks* like a pure many-to-many junction (two foreign keys), so the instinct
is to model it as an **edge**. But it carries `quantity` and `unit_price` — and the line revenue
`quantity × unit_price` — which are facts of **neither** the order nor the product. Model it as a bare link
and those attributes are **orphaned** (or misattributed to an endpoint); model revenue anywhere else and you
lose that the *line* is its grain.

## The question, and the answer

> **The question** (what the data can't tell you): *Is `order_line` a link between Order and Product, or a
> thing in its own right?*
>
> **The answer** (the fact we supply): *Because it carries its own attributes, it is a **thing** — promote it
> to a concept (an `event`/`entity` at line grain), grounded on the junction table, with two edges to its
> endpoints. A junction with **no** payload would be just an edge; the payload is what promotes it.*

## The pattern (the structured entry)

```yaml
pattern: associative_entity
also_known_as: [junction with payload, associative entity, link table with attributes, reified relationship, line item]
tradition: relational   # + RDF reification; + the dimensional line-grain fact
constellation: >
  An M:N junction table that carries its OWN attributes/measures, not only the two foreign keys — the
  relationship is itself something the business measures (a line item, an enrolment, an assignment).
prior_art:
  relational: >
    A junction/associative table. Whether it is "just a join" or "an entity" is a modelling judgment usually
    left implicit; its non-key attributes get orphaned or misattributed to an endpoint.
  dimensional: >
    The classic line-grain fact table — well understood as a fact; but its duality (it is ALSO the M:N
    bridge between two dimensions) is implicit.
  rdf: >
    Reification — a statement about a statement, or an n-ary relation pattern — expressible but heavy
    (rdf:Statement / a blank intermediate node / named graphs).
mac_expression: >
  PROMOTE the junction-with-payload to a CONCEPT — class `event` (a line item belongs to the order
  lifecycle) or `entity` — grounded on the junction table; its two foreign keys become two `physical` edges
  to the endpoint concepts (Order, Product); its measures (line revenue = quantity × unit_price) are
  `measure`s grounded here, at line grain. A pure, attribute-less junction stays a single `edge`. The
  presence of non-key attributes is the discriminator.
why_better: >
  The relationship-as-a-thing gets a first-class home for its measures and an explicit grain — instead of
  orphaned columns on a junction nobody owns. Crucially it needs NO new structure: `event`/`entity` + two
  edges + `measure` already express it. (This is a stress test of Ch.02's open "is six structures enough?"
  — and it PASSES: the associative entity is not a seventh structure, it is an entity that an edge would
  have under-modelled.)
projects_to:
  rdf: "an n-ary relation / reified statement class with its own properties"
  graph: "a node for the relationship + two edges (or a rich edge carrying properties)"
  relational: "the line-grain fact table (which is also the M:N bridge)"
antipattern: >
  Modelling a junction-with-payload as a bare edge (orphans its attributes); or as a property of one endpoint
  (a quantity is neither the order's nor the product's); or losing the line grain by defining its measures
  elsewhere.
status: scattered   # expressible today (promote to concept + edges); never named — a candidate 🔴 that RESOLVES to ⚠️
canon_ref: [FRAMEWORK.md §5 (the six classes), FRAMEWORK.md §7 (edges), CONCEPT_SPEC.md §4]
```

## The determinism border

Per [AUTHORING.md](../AUTHORING.md) A4 — this is a **structural** pattern: its answer is a modelling choice,
not a query-time guard, so it is **100% skeleton, zero canon** (and fully deterministic once the choice is made).

| Behaviour | Kind | How |
| --- | --- | --- |
| Promote to a concept (vs leave as a bare edge) | **skeleton** | the rule: *promote iff it carries non-key attributes* |
| The line grain + its measures | **skeleton** | an `event`/`entity` + `measure`, grounded on the junction |
| The two endpoint links | **skeleton** | two `physical` edges to Order and Product |
| interpretative remainder | **none** | structural — once promoted, everything follows |

Not every pattern needs a canon. Some are resolved entirely by **choosing the right structure** — and this
is one. The "footgun" it closes is a *modelling* error, caught at authoring time by the schema, not a
query-time guess.

## The footgun, concretely

```text
-- Model order_line as a bare EDGE (Order —— Product):
--   where does `quantity` live? `unit_price`? the line revenue `quantity × unit_price`?
--   → nowhere. They get bolted onto Order or Product (wrong: a quantity is neither's attribute),
--     or revenue is defined at the wrong grain and silently mis-aggregates.
```

```yaml
# GROUNDED — promote to a concept at line grain; the attributes finally have a home:
concept: { name: OrderLine, class: event }           # the line item — a thing, not just a link
grounding: { table: order_line, key: [order_id, product_id] }
measure:   { name: LineRevenue, derivation: "quantity * unit_price" }   # defined HERE, at line grain
edges:
  - { level: physical, from: OrderLine, to: Order,   realized_by: order_line.order_id }
  - { level: physical, from: OrderLine, to: Product, realized_by: order_line.product_id }
```

The difference is not a clever query — it is giving the relationship's own facts a **home at the right
grain**. And the useful result for the formal core: a case that *looked* like it might need a new structure
turned out to be an `entity` an edge had under-modelled. One stress test of "is six enough?" — passed.
