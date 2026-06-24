---
title: "Ch.05 — Tutorial: from blank canvas to a running model"
part_of: reference_manual
status: written
scope: GENERIC — domain-neutral. Builds a tiny synthetic shop model from scratch.
---

# Ch.05 — Tutorial: from blank canvas to a running model

*Chapters 02–04 told you what the building blocks are and how to reason about them. This chapter is the
on-ramp: you start with nothing, write one concept, **run it**, and grow a model one validated file at a
time. It teaches the *mechanics*; when a shape turns tricky, it hands you to the matching pattern in Ch.03.*

> **Relationship to the canon (A3 — reference, don't restate).** The step-by-step *recipes* live in
> [`../MODELLERS_COOKBOOK.md`](../MODELLERS_COOKBOOK.md) (B1 author a concept · B3 enumeration · B4 rule ·
> B5 edge · B6 grounding); the full worked model is [`../example_shop_ontology/`](../example_shop_ontology/).
> This tutorial is the *narrative that runs them* — it points at each recipe rather than copying it.

## 5.1 Hello, ontology

The smallest complete thing you can write is **one concept**. An `enumeration` is the simplest — values +
closure + grounding, no joins (cookbook **B3**). Create `shop/concepts/order/order_status.yaml`:

```yaml
metadata: { concept: OrderStatus, source: shop, version: '1.0', schema_version: '0.1.9', status: draft, confidence: I }
concept:
  name: OrderStatus
  label: Order status
  class: enumeration
  definition: > The lifecycle state of an order.
  semantics: { purpose: classify an order's current stage }
values:
  closure: closed
  closure_why: "the order lifecycle is a fixed state machine; any other value is a defect"
  items: [ {code: PLACED}, {code: PAID}, {code: SHIPPED}, {code: DELIVERED}, {code: RETURNED}, {code: CANCELLED} ]
grounding: { kind: sql_table, table: orders, code_column: status }
```

That is a valid ontology. Note what you already declared without thinking of it as theory: a **closed**
value set (Ch.03 `explicit_closure`) and where it's **grounded**.

## 5.2 Test it — the two gates, on your very first concept

Structure first (data-free), then reality:

```bash
python3 tools/validate_schema.py  shop     # 1. structural  — green = WELL-FORMED (not yet correct)
python3 tools/check_references.py shop     # 2. referential — every cross-file reference resolves
python3 tools/check_shapes.py     shop     # 3. constraint  — invariants declared as data
```

Green means *well-formed*, **not correct** (Ch.04). The correctness check is one query:

```sql
SELECT DISTINCT status FROM orders;   -- do the real values match your 6 items? does `closed` actually hold?
```

If the warehouse returns a `REFUNDED` you didn't model, the data just **refuted** your concept (Ch.02 §2.1:
a concept is a falsifiable equation) — you fix the model and your `confidence:` earns its way up. **That loop
— author → gate → run → promote — is the whole method.** You just did it on a 12-line file.

## 5.3 The build loop — grow one validated file at a time

A model is never "set up" in one shot; it **accretes**, each file run through the same loop. Add them in
this order — each is one cookbook recipe + one gate run + one query:

| Step | Add | Class | Recipe | The test |
| --- | --- | --- | --- | --- |
| 1 | `OrderStatus` *(done)* | enumeration | B3 | `SELECT DISTINCT status …` |
| 2 | `Product` | reference | B1 + B6 | `SELECT count(*) FROM product` — key unique? |
| 3 | `Order` (lifecycle *uses* OrderStatus) | event | B2 | the states match OrderStatus |
| 4 | `Order —placed_by→ Customer` | *edge* | B5 | the join returns 1 customer per order |
| 5 | `net_revenue` = gross − refunds | *rule* | B4 | run the implied SQL; sanity-check the number |

Each step is small enough to own, diff, and validate in isolation — the payoff of one-file-per-concept. By
step 5 you have a tiny but **real, running** model: concepts grounded, an edge that joins, a rule that
computes, all gated and all execution-checked.

## 5.4 When a shape gets hard — jump to Ch.03

The loop above handles the *easy* shapes. The moment the data fights back — a measure you're tempted to
`SUM` across time, a code that means different things per parent, a dimension that keeps history — stop and
find the **pattern** in [Ch.03](03_pattern_reference.md). Each pattern is the same loop with the *one
declared fact* (and its canon) that makes the hard case come out right. A few you'll meet early:

- a stock you might sum over time → [`semi_additive_balance`](patterns/semi_additive_balance.md)
- "revenue?" with no period → [`required_unspecified`](patterns/required_unspecified.md)
- a dimension with versioned history → [`scd_type_2`](patterns/scd_type_2.md)
- a missing row that might mean zero → [`absence_semantics`](patterns/absence_semantics.md)

## 5.5 Where to go next

- **A recipe for the exact thing you're authoring** → [`../MODELLERS_COOKBOOK.md`](../MODELLERS_COOKBOOK.md)
  (decisions A1–A4, recipes B1–B8, antipatterns C).
- **A complete model to read and copy** → [`../example_shop_ontology/`](../example_shop_ontology/) — every
  construct, in full, with its own `validate.sh` and `QUERIES.md`.
- **The hard shapes** → [Ch.03 — the Pattern Reference](03_pattern_reference.md).

You now have the on-ramp: write one concept, run it, grow the model a validated file at a time, and reach for
a pattern when a shape resists. That is the whole job.
