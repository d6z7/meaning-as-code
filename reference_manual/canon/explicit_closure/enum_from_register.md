---
title: "Canon — enum_from_register"
part_of: reference_manual/canon
status: SHIPPED — implemented in mac-runtime and honoured today
scope: GENERIC — domain-neutral contract; examples measured on a live bundle
---

# Canon — `mac.canon.enum_from_register`

**The register IS the concept's closed value domain.** Not a way to resolve names to codes — a
statement that these rows are *all the members there are*, so a value outside them is answerable
without touching the warehouse.

One of the two canons the runtime actually implements; see
[`resolve_by_register`](../contaminated_code/resolve_by_register.md) for the other, and for the distinction below.

## Serves

The [`explicit_closure`](../../patterns/explicit_closure.md) pattern — a value set that is **closed**,
where the members live in one place and are not restated in the concept.

Four concepts declare it in the worked bundle: `Color`, `Currency`, `Channel`, `StoreStatus`.

## Contract

Declared under `values.realized_by` — **not** on a contract rule, which is the shape difference from
`resolve_by_register`:

| param | required | default | meaning |
|---|---|---|---|
| `register` | **yes** | — | the `.lookup.csv` whose rows ARE the members |
| `key_column` | no | `code` | which column of that CSV holds the member code |

**Guarantees**

- **The members match on the key column only.** A human-readable column that merely *looks* like an
  identity is not matched — that is precisely the trap `resolve_by_register` exists for. An
  enumeration whose values should also resolve by name declares **both** canons.
- **`items:` may be omitted.** The register is the single home for the member list; restating it in
  the concept would create a second one that drifts when the register is re-cut.
- **A non-member is answerable from the declaration.** No probe, no empty result read as "no data".

## Implementation

`mac_runtime/resolver/registers.py` — the `value_domain` declaration form. Shipped.

## How a concept plugs in

```yaml
values:
  closure: closed
  closure_why: >-
    Enumerated from the served column and DELEGATED rather than copied: exactly 2 distinct non-null
    values measured over 74 store versions.
  realized_by:
    udf: mac.canon.enum_from_register
    params:
      register: contoso_store_status.lookup.csv
      key_column: Status
```

## The distinction that matters

| | `enum_from_register` | `resolve_by_register` |
|---|---|---|
| declared under | `values.realized_by` | `contract.rules[].realized_by` |
| says | *these are all the members* | *this word maps to that code* |
| matches on | the key column only | whatever `search` names |
| a word outside it | answerable from the list | a refusal naming what was searched |
| both at once | the members are closed **and** resolvable by name — declare both |

**Getting this wrong is silent.** A concept declaring only `enum_from_register` has a closed domain
whose members do **not** resolve by name: `'Closed'` matches, *"shut stores"* does not.

## Determinism & honest limits

- **Deterministic**; the register is a file in the bundle and is never probed.
- **Closure is a claim this canon does not verify.** It binds the members; whether the list is still
  complete is the [`warranty`](../../column_specification.md) question, and a `closed` set nobody
  reconciles is a refusal backed by a stale sample.
- **`closed` covers the CODED members only.** An absence is not a third member and must not be
  minted as one — `StoreStatus` has no code for an operating store, and inventing `Operating` would
  put a value in the ontology that no row carries.
