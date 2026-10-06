---
title: "Canon — grouping_from_register"
part_of: reference_manual/canon
status: retired
scope: GENERIC — domain-neutral contract; the failure below was measured
---

> **RETIRED 2026-10-07.** `mac.canon.grouping_from_register` is no longer a term of the canon: it is gone from
> `mac_vocabulary.yaml#canon.terms` and from the runtime registry, so a `realized_by` naming it is
> now an ERROR at `check_references` rather than a binding that parses and decides nothing. This
> page is kept in place — 28 pages link to the five retired canons, and a moved page is a broken
> link — as the record of what was considered and why it went.
>
> **Why:** never implemented, never hooked, and its own page carries a section headed "You almost certainly do not need it": `resolve_by_register` guarantees a name binds EVERY code it covers, so an exploded register searched on the group column and resolving to the member column IS the re-aggregation. The four concepts that once bound it are gone or rule-free, and every grouping column in this bundle sits on the same row as its members.

# Canon — `mac.canon.grouping_from_register`

> **Read this before declaring it.** The runtime does not implement this canon. A concept binding
> it parses, passes every gate, and gets **no behaviour** — see *"What it cost"* below, which is
> not hypothetical.

## Serves

The [`explicit_closure`](../../patterns/explicit_closure.md) pattern, for a **grouping**: a concept
whose members are sets of other members — continents over countries, categories over products.

## Contract

```yaml
values:
  realized_by:
    udf: mac.canon.grouping_from_register
    params:
      register:   <path>        # an EXPLODED register: one row per (group, member)
      group_key:  <column>      # the column holding the GROUP's value
      member_col: <column>      # the column holding the MEMBER's code
      carry:      [<column>, …] # columns carried onto each member
```

**Intended guarantee:** read the exploded register, re-aggregate by `group_key`, and bind each
distinct group to the set of `member_col` values beneath it.

## What it cost

Four concepts in contoso declared it — `Continent`, `Brand`, `ProductCategory`,
`ProductSubcategory` — and all four got nothing. The loader recognises two canon names and dropped
the rest with a bare `continue`, so:

```
Continent='Europe'   REFUSED a value SELECT DISTINCT returns
ProductSubcategory   0 of 32 members resolved, while its sibling ProductCategory resolved all 8
                     — the only difference being a second, implemented, declaration
```

**And the refusal sent the diagnosis the wrong way.** Reading *"Continent has no resolvable
values"*, an agent concluded the **registers** were missing and cut fifteen new ones. Thirteen
duplicated files that already existed, each worse than the original — no labels, no roll-up column,
no sentinel. A day spent treating the symptom, because an unimplemented declaration is
indistinguishable from an absent one.

`check_canon_implemented.py` exists to make that distinction visible.

## You almost certainly do not need it

**[`resolve_by_register`](../contaminated_code/resolve_by_register.md) already expresses a grouping**, because its
guarantee is that a name binds **every** code it covers:

```yaml
realized_by:
  udf: mac.canon.resolve_by_register
  params:
    thing:         continent
    code:          Country       # the MEMBER column
    register:      data/lookups/contoso_country.lookup.csv
    search:        continent     # the GROUP column
    display_label: label
```

A register exploded one row per (continent, country), searched on the group column, resolving to
the member column, *is* a re-aggregation. Measured:

```
'Europe' → ('DE','FR','GB','IT','NL')       "in how many countries do we sell" → 8
```

**And the roll-up route is the better of the two**, because the answer can name what it counted.
That is how `Continent` works today.

## Limits

- **Not implemented.** Nothing below this line is behaviour you can rely on.
- If it is ever built, it must not duplicate `resolve_by_register`'s member binding; the case it
  would genuinely add is a group whose members are *not* reachable as codes on the same row.
