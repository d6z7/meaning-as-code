---
title: "Pattern — Contaminated code (an opaque code/prefix that mixes unrelated things)"
part_of: reference_manual/patterns
status: prototype
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (illustrative shop scenario).
---

# Pattern — Contaminated code

## Initial state — what you're handed

A `product_code` whose **prefix** used to identify a family — but the prefix was reused over time and now
mixes unrelated things:

```sql
CREATE TABLE product (product_id VARCHAR, product_code VARCHAR, name VARCHAR, category VARCHAR);
```

| product_id | product_code | name | category |
| --- | --- | --- | --- |
| P-100 | BK-001 | The Trail (novel) | Books |
| P-900 | BK-742 | LedgerPro (accounting app) | Software |

**Why this is dangerous.** `BK-` once meant "Books", so the instinct is `WHERE product_code LIKE 'BK%'` to
"get all books". But the prefix was overloaded — `BK-742` is bookkeeping *software*. The opaque code carries
no reliable semantics anymore; prefix-matching silently mixes novels and accounting apps.

## The question, and the answer

> **The question:** *Can I resolve a family by the code's prefix?*
>
> **The answer:** *No — the opaque code is contaminated; its prefix no longer identifies the family. Resolve
> by a **curated** attribute (`category` / `name`), never by code prefix. A guard forbids the `LIKE 'BK%'`.*

## The pattern (the structured entry)

```yaml
pattern: contaminated_code
also_known_as: [overloaded code, reused prefix, opaque key, semantic-free identifier]
tradition: cross-cutting   # this framework's addition (a real overloaded-code lesson, domain-neutral)
constellation: >
  An opaque code (or code prefix) is treated as if it carried semantics, but has been reused/overloaded so
  the same prefix now spans unrelated things. Resolving by the code silently conflates them.
prior_art:
  relational: >
    The code is just a string; nothing records that its prefix is unreliable. `LIKE 'X%'` compiles and
    quietly mixes families.
  dimensional: >
    A "smart key" whose embedded meaning has rotted; the rot is undocumented.
  rdf: >
    An opaque IRI/literal; no notion that string structure is unsafe to match on.
mac_expression: >
  A `resolution` rule: resolve the entity by a CURATED attribute (its `name`/`category`, the
  [semantic identity](context_dependent_meaning.md)), with a `never` clause forbidding match on the opaque
  code or its prefix. Enforced by the `opaque_code_guard` canon (reject `LIKE`/prefix on a code flagged
  opaque). The code remains a join key only.
why_better: >
  "This code carries no reliable semantics" becomes a first-class, enforced fact instead of tribal scar
  tissue. An agent that writes `product_code LIKE 'BK%'` is doing exactly what the rule forbids — caught, not
  silently mixed. (Same shape as the resolve-by-name principle in `query_rules`.)
projects_to:
  rdf: "resolve via a curated category property; flag the code as opaque (skos:notation, not a class)"
  graph: "a curated category edge; the code is a non-semantic property"
  relational: "join on the code, classify via a curated attribute"
antipattern: >
  `LIKE 'prefix%'` / substring-matching an opaque code; treating a reused prefix as a family identifier.
status: scattered   # the resolve-by-name principle exists (query_rules); naming the contaminated-code case + the guard is new
canon_ref: [query_rules (resolve.by_semantic_identity), patterns/context_dependent_meaning.md]
```

## The determinism border

| Behaviour | Kind | How |
| --- | --- | --- |
| Resolve by curated `name`/`category`, not the code | **skeleton** | a `resolution` rule (resolve-by-semantic-identity) |
| Reject prefix/`LIKE` matching on the opaque code | **canon-backed** | [`opaque_code_guard`](../canon/opaque_code_guard.md) |
| interpretative remainder | **none** | once the curated attribute is named |

```yaml
product_code:
  prose: "An opaque, overloaded code; resolve families by `category`/`name`, never by code prefix."
  realized_by:
    udf: opaque_code_guard
    params: { code_column: product_code, resolve_via: category }
```

## The footgun, concretely

```sql
-- GUESS: prefix-match the opaque code
SELECT count(*) FROM product WHERE product_code LIKE 'BK%';   -- novels + bookkeeping software, mixed  ❌
-- GROUNDED: resolve via the curated attribute (guard rejects the LIKE above)
SELECT count(*) FROM product WHERE category = 'Books';        ✅
```
