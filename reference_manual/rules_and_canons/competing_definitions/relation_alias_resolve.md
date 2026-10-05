---
title: "Canon — relation_alias_resolve"
part_of: reference_manual/canon
status: NOT IMPLEMENTED — no bundle in the estate declares it
scope: GENERIC — domain-neutral
---

# Canon — `mac.canon.relation_alias_resolve`

## Serves

The [`competing_definitions`](../../patterns/competing_definitions.md) pattern, one level up: the
ambiguous word names a **relationship**, not a value.

## Contract

Resolve a surface token against a business edge's multilingual surfaces, returning **the edge** as
the routing target. More than one hit → **ASK**.

Where [`alias_resolve`](alias_resolve.md) answers *"which member did they mean"*, this answers
*"which relationship did they mean"* — *"sales by country"* reaching country through the customer
or through the store, which are different numbers.

## Why it matters even unimplemented

The contoso bundle meets exactly this and answers it with a **rule** instead:

> `continent.side.customer_only` — *"the store dimension has no continent column at all, so this
> roll-up exists only on the customer side. A store-side continent figure is not available — a
> refusal with a reason, not an empty result."*

One ambiguity, resolved by declaring one side impossible. That works where a side genuinely does not
exist; it does not where both are real and the asker must choose.

## Limits

- **Not implemented**, and nothing declares it.
- Needs edges to carry alias surfaces, which no bundle populates today.
