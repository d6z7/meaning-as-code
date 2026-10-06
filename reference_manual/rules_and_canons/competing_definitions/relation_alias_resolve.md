---
title: "Canon — relation_alias_resolve"
part_of: reference_manual/canon
status: retired
scope: GENERIC — domain-neutral
---

> **RETIRED 2026-10-07.** `mac.canon.relation_alias_resolve` is no longer a term of the canon: it is gone from
> `mac_vocabulary.yaml#canon.terms` and from the runtime registry, so a `realized_by` naming it is
> now an ERROR at `check_references` rather than a binding that parses and decides nothing. This
> page is kept in place — 28 pages link to the five retired canons, and a moved page is a broken
> link — as the record of what was considered and why it went.
>
> **Why:** superseded by `path_select`, which shipped on 2026-10-06 and is bound in this bundle. Its page's stated reason to exist — "'sales by country' reaching country through the customer or through the store, which are different numbers" — is the question `path_select` now answers, with the same surface-to-relation mapping and the same ASK semantics. It was also NOT IMPLEMENTABLE as written: `relationAliasBlock` has no slot holding the surfaces it matches, and `parse_edges` drops an edge alias block silently.

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
