---
title: "Canon — resolve_by_register"
part_of: reference_manual/canon
status: SHIPPED — implemented in mac-runtime and honoured today, unlike the reference-only entries
scope: GENERIC — domain-neutral contract; examples measured on a live bundle
---

# Canon — `mac.canon.resolve_by_register`

> A **canon** is a generic, parameterized UDF — the deterministic realization of a behaviour-bearing
> slot. Its logic is single-homed; concepts name it and bind parameters, never restating its logic.

**This entry is not a reference sketch.** Most of the canon library is illustrative Python showing
what a canon *would* look like. This one, and [`enum_from_register`](enum_from_register.md), are the
two the runtime actually implements — so the contract below is the real one, and the examples are
measured rather than imagined.

## Serves

**Turning a word a person typed into the value the warehouse stores.** Every name-to-code resolution
in every bundle goes through this canon. It is the mechanism behind
[lookup pre-resolution](../patterns/../patterns/explicit_closure.md) and the reason a question can
name `Germany` when the column holds `DE`.

Eight concepts declare it in the worked bundle: `Brand`, `Color`, `Country`, `Continent`,
`ProductCategory`, `ProductSubcategory`, `CalendarDay`, `Store`.

## Contract

Declared on a **contract rule**, under `realized_by`:

| param | required | meaning |
|---|---|---|
| `register` | **yes** | the `.lookup.csv` holding the members |
| `code` | **yes** | the column a word resolves **to** — what the SQL will bind |
| `search` | **yes** | the register column(s) a typed word is matched against |
| `display_label` | no | the register column shown back to the reader |
| `fact_join` | no | when set, the **fact** filters on this column directly and no dimension join is walked |
| `scope` | no | a row filter on the register (`col = value`, `col IN (…)`, joined by `AND`) |
| `thing` | no | the noun used in refusals — *"no **continent** named 'Africa'"* |
| `served_view` | no | the relation the register was cut from |

**Guarantees**

- **Every code a name covers is bound, never one of them.** A name matching five register rows binds
  all five: `Europe` → `IN ('DE','FR','GB','IT','NL')`. Silent narrowing is the defect this
  removes — a filter that quietly drops codes returns a number nobody can see is wrong.
- **`search` and `display_label` may not be the same column.** A column cannot be both a name to
  match and a label that must never be matched; the load refuses.
- **Codes are kept byte for byte.** Not trimmed, not case-folded. The *word* is normalised; the
  *code* is what the warehouse stores.
- **A malformed declaration is SKIPPED with a reason, not raised.** One bad parameter costs the
  questions that touch its concept, not the whole bundle.

## Implementation

Shipped, in two files — not reproduced here, because a copy would be a second home:

| file | what it does |
|---|---|
| `mac_runtime/resolver/register_declarations.py` | parses and validates the declaration; every column checked against the CSV header |
| `mac_runtime/resolver/registers.py` | reads the register, applies `scope`, builds the match rows |
| `mac_runtime/resolver/register_match.py` | the tiered ladder: exact → normalized → prefix → fuzzy → near-miss |

## How a concept plugs in

Resolving a country by its name, filtering the fact directly:

```yaml
contract:
  rules:
    - id: country.resolution.by_register
      kind: mac.concept.rule.resolution
      when:  "a question names a country"
      then:  resolve through the register to the two-letter code, then filter on it
      never: matching on the long name in the fact
      binds: [Country, CountryFull]
      realized_by:
        udf: mac.canon.resolve_by_register
        params:
          thing:         country
          code:          Country
          register:      data/lookups/contoso_country.lookup.csv
          search:        search_key
          display_label: label
          fact_join:     Country
```

The **same** canon expressing a roll-up — one name covering several codes — by pointing `search` at
a grouping column instead of a name column:

```yaml
      realized_by:
        udf: mac.canon.resolve_by_register
        params:
          thing:         continent
          code:          Country
          register:      data/lookups/contoso_country.lookup.csv
          search:        continent
          display_label: label
```

**Nothing about the canon changed.** `search: continent` over a register exploded one row per
(continent, country) *is* a roll-up, because the guarantee is that every matching code is bound.
That is why a separate grouping canon was never needed.

## Demonstration — measured

```
'Germany'  → 'DE'                                          exact, one code
'germany'  → 'DE'                                          normalized: case and whitespace fold
'Germny'   → CLARIFY "did you mean Germany?"               near-miss, 0.92 — asks, never binds
'Europe'   → ('DE','FR','GB','IT','NL')                    five codes, all bound
'Africa'   → REFUSE  "No continent named 'Africa' in
              contoso_country.lookup.csv: compared case-
              and whitespace-insensitively with continent
              over 9 rows."
```

The refusal names **what was searched and how many rows** — because *"filtering on an unresolved
name would return no rows, which reads as 'no data'."*

## Determinism & honest limits

- **Deterministic.** Same register, same word, same codes. No model in the loop.
- **`search` must be a column, not a pattern.** There is no regex form; a word not present under
  some search column does not resolve.
- **The ladder is not declarable per column.** `fuzzy_floor`, the candidate count and which rungs
  run are runtime constants today. The [column specification](../column_specification.md) moves them
  onto the column; until then every register shares one ladder.
- **`scope` accepts three forms only** — `col = value`, `col IN (v, …)`, joined by `AND`. Anything
  else is skipped with the grammar quoted back.
- **It does not know which COLUMN of the concept the value lives in.** That travels separately, and
  omitting it is how `CustomerKey = 'female'` reached the warehouse. See
  [how a question becomes SQL](../how_a_question_becomes_sql.md) §3.
