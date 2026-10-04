---
title: "Canon — refuse_unresolvable_name"
part_of: reference_manual/canon
status: SHIPPED — implemented in mac-runtime as a canon (`canons/refuse_unresolvable_name.py`) and honoured today; it was built directly by the resolver when this page was written
scope: GENERIC — domain-neutral
---

# Canon — `mac.canon.refuse_unresolvable_name`

## Serves

`exclusion_no_evidence` — a name that resolves to no code must **refuse**, never silently filter on
nothing.

## Contract

A **RENDER canon**: refusal text, not SQL.

| param | read from |
|---|---|
| `thing` | `concept.label` |
| `code` | `concept.identity.canonical_key` |

## The behaviour exists — without the canon

This is the one entry where "not implemented" does not mean "does not happen". The resolver builds
the refusal itself, and it is better than a generic one because it names what was searched:

```
No continent named 'Africa' in data/lookups/contoso_country.lookup.csv: compared case-
and whitespace-insensitively with continent over 9 rows. Filtering on an unresolved name
would return no rows, which reads as 'no data'.
```

**Register, search column, row count, and the consequence.** A canon reading only `thing` and `code`
could not produce that, because neither param names the register.

## Limits

- **Not implemented, and possibly should not be.** The information the good refusal needs lives in
  the *resolution attempt*, not in the concept — so a render canon parameterised from the concept
  is the wrong shape for it.
- Listed here because the vocabulary defines it and an author will meet the name.
