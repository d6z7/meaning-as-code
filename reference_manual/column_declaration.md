---
title: The column declaration — everything a column says, and who reads each answer
status: >-
  CURRENT (2026-10-07). Every key on this page is what mac.schema.json admits and what the runtime
  reads: `roles` as a required map, `key` on the source, `identity: reference`, `axis` closed to two
  kinds, and `grounding.grain` retired. `never_axis` STAYS — it is a live refusal path citing its
  evidence. The platform suite is green on it (1461 tests) and contoso5 compiles with 0 errors.
  THE KEY IS ON THE SOURCE as of this date: it was collected from `identity: canonical`/`composite`
  on the columns, which could not state its ORDER — and that order reaches the SQL, so swapping two
  column blocks silently changed the key.
audience: ontology authors, importer developers, framework developers
companions:
  - column_specification.md   # the long form: every key, with its enforcement state
  - column_roles.md           # the role terms, generated from the vocabulary
  - column_rulings.md         # the rulings block, in detail
  - measures.md               # the measures this feeds
  - specification/FOLD_GRAMMAR.md
  - ../mac_vocabulary.yaml
---

# The column declaration

A concept means what its columns say. Each column answers one question —

> **What may a question do with me, and on what terms?**

— and every key below is either one of those uses, a parameter of one, or a relation to another column.

```yaml
grounding:
  sources:
    - relation: v_contoso5_sales_line
      key: [order_key, line_number]          # what makes ONE ROW unique, in order
      columns:
        order_key:     {roles: {}}           # a key column claims no role of its own
        line_number:   {roles: {}}
        customer_key:  {roles: {identity: reference, axis: mac.concept.axis.categorical}}
        order_date:    {roles: {axis: mac.concept.axis.time, period_binding: true}}
        quantity:      {roles: {aggregate: {type: …measure_type.flow, unit: units}}}
        valid_from:    {roles: {}}
```

## `key` — what makes one row unique

| | |
|---|---|
| where | on the **source**, under `relation` |
| card | a string, or a list of column names |
| required | **yes**, on a primary source — the parser refuses one without it |
| order | **load-bearing**: it becomes `cell_key` and reaches the SQL |
| read by | `cell_key` (52 sites), `canonical_key` (a one-column key), `key_parts` (two or more) |

A **one-column** key is the canonical identity — what `COUNT(DISTINCT …)` counts. **Two or more** is
the composite: no column identifies anything alone, and using one as if it did returns a set where a
row was expected. A **measure** has no canonical identity whatever its key's shape — it is summed,
not counted — so its key is the grain and nothing else.

The columns do not repeat it. One home, so the two cannot disagree — which is why it is stated here
rather than collected from a per-column flag: a flag has nowhere to put the order, and the order is
what reaches the SQL.

## The column, top level

| key | card | value | required | says | read by |
|---|---|---|---|---|---|
| `roles` | **map** | role → its qualifier (next table) | **yes** — `{}` is legal and means *offered to no question* | what a question may do with this column | the planner, for every step it takes |
| `counts` | bool | `true` | no | **a count of this concept counts THIS column**, not the canonical one | the count route; disclosed in the answer (*"counted by location_code"*) |
| `register` | string | a lookup path | no | where this column's values come from | `resolver/registers`, `resolver/register_match` — name → code resolution |
| `rulings` | map | see below | no | how this column relates to **another column** | the planner and the refusal path |

`roles: {}` is a **positive statement** — the column exists, is typed, is loaded, and no question is offered it. A column with **no** `roles` key is unclassified, which is a finding rather than a state.

## `roles` — the five uses, each with its own terms

| role | qualifier card | terms | says | read by |
|---|---|---|---|---|
| `identity` | scalar | `reference` | I identify a row in **another** concept — a join target, never part of this grain | join resolution; `composite_key_guard`. *This* concept's key is `key` on the source |
| `axis` | scalar | `time` · `categorical` | a question may **group or filter** by me | the fold law; `additivity_guard` |
| `aggregate` | map | `{type, unit, canonical}` | a question may **fold** me | the fold law; unit algebra; the measure route |
| `period_binding` | `true` | — | I am **the** reporting date when the relation carries several | period binding — *"sales in March"* cannot pick the wrong date |
| `extremum` | list | `[min]` · `[max]` · `[min, max]` | my earliest or latest value may be **asked for** — not folded | the extremum route — *"when did we first sell in Spain"* |

> **How a term is written.** A vocabulary term is authored **fully qualified** — `axis:
> mac.concept.axis.time`, `type: mac.concept.column.measure_type.flow`. The bare term is the
> term's NAME and is what the tables on this page abbreviate to; written into a bundle it fails
> validation, because the schema's pattern is `^mac\.concept\.axis\.(categorical|time)$` and
> what makes a token checkable is that it names its namespace. `identity`'s one term and
> the two of `extremum` are the exception: they are closed `enum`s, authored bare.

### `identity` — one term, about **another** concept

| term | holds when | consequence |
|---|---|---|
| `reference` | this column identifies an instance **in another concept** | the row names a row over there; it is a join target and never part of this concept's grain. Whether every value is present there is a measurement, not a declaration |

That is the only identity statement a column makes. What identifies a row of **this** concept is
[`key`](#key--what-makes-one-row-unique) on the source — one fact, with an order, in one place.

### `aggregate` — the qualifier of a foldable column

| sub-key | card | terms | says |
|---|---|---|---|
| `type` | scalar | `flow` · `stock` · `intensive` · `precomputed` · `target` | what kind of quantity this is — the row of the fold law |
| `unit` | string | free (`USD`, `units`, `m2`, `to-currency per from-currency`) | what the number is in; two different units may not be combined |
| `canonical` | bool | `true` | **which** aggregate column is *the* one, when a concept carries several |

## The fold law — `type` × `axis` → what folding does

This is why `axis` carries a term and not a boolean. The law is stated over **kinds**, never over column names, which is what makes it universal.

| `aggregate.type` | across a `time` axis | across a `categorical` axis |
|---|---|---|
| `flow` | **additive** | **additive** |
| `stock` | `none` — does not accumulate | **additive** |
| `intensive` | `average` | `average` |
| `precomputed` | `none` | `none` |
| `target` | `none` | `none` |

A fold the law does not permit is refused, naming the axis it crossed. A column with no `axis` role is never consulted: there is no axis to cross.

## `rulings` — what a person decided about a column

A ruling is a judgement measurement cannot establish. All optional; a column with none behaves as its `roles` alone dictate.

| ruling | value | says | read by |
|---|---|---|---|
| `label_of` | a column | I am **another name for that column's thing**, not another thing — group on it, display me | `planner/sql` |
| `register` | `common` · `legal` · `long` · `short` · `code` | **which** of that thing's names I am | the resolver, choosing a display name |
| `finer_than` | a column | I distinguish **more members** than that column and roll up into it; both are legitimate axes and an answer must **disclose which level it used** | `planner/sql` |
| `scoped_by` | a column | my values are unique **only within** that column, so I may not be grouped or filtered alone — the scope must travel with me | synthesises a `composite_key_guard` binding |
| `sort` | `asc` · `desc` · `none` | the order my values are presented in when the question states none | the assembler |
| `never_axis` | the measurement | **I am a real axis and a person has ruled that no question may group by me** — the sentence is the measurement that justifies it (*"29 193 of 40 639 postcodes are held by exactly one customer"*) | `grounded_columns._ruled_never_axis` → `_axis_denied`, which REFUSES and quotes this sentence |
| `evidence` | a DQ issue id | which finding this ruling rests on — an argument to a ruling, not a ruling of its own | the refusal, so a reader can go and read the finding |

## Worked: the same shape meaning two different things

The two cases that decide why `axis` is declared per column rather than derived from identity.

| | `units_sold` | `exchange_rate` |
|---|---|---|
| `key` | `[order_key, line_number]` | `[date_day, from_currency, to_currency]` |
| each key column carries | `roles: {}` | `axis: time` / `axis: categorical` |
| so a question may | join and count on them | join, count, **and group** by them |
| because | a line number is a position in a basket; *"revenue by line number"* asks nothing | *"the USD→EUR rate on 2025-01-03"* names the row **by** its axes |

Both are the grain. Only one is also an axis, and the only thing that says so is the `axis` role — which is why it is a declaration and not a derivation.

## Where identity and the key part company

`key` identifies a **row**. What a **count** counts is sometimes a different column — and it may be
a column that is not in the key at all.

| | `store.store_key` | `store.location_code` |
|---|---|---|
| in `key` | **yes** — `key: store_key` | no |
| roles | `{}` | `identity: reference` |
| `counts` | — | `true` |
| rows | 74 — one per trading period | — |
| a count of *stores* | would say 74, wrongly | says **67** |

`counts` is how a concept says *"a count of me is not a count of my rows"*, and the answer discloses which column it counted.

## The complete surface, at a glance

| | card | required | terms |
|---|---|---|---|
| `roles` | map | **yes** | `identity` · `axis` · `aggregate` · `period_binding` · `extremum` |
| `key` *(on the source)* | string or list | **yes** | column names, in order |
| `roles.identity` | scalar | iff claimed | `reference` |
| `roles.axis` | scalar | iff claimed | `time` · `categorical` |
| `roles.aggregate` | map | iff claimed | `{type, unit, canonical}` |
| `roles.aggregate.type` | scalar | **yes**, within `aggregate` | `flow` · `stock` · `intensive` · `precomputed` · `target` |
| `roles.aggregate.unit` | string | **yes**, within `aggregate` | free |
| `roles.aggregate.canonical` | bool | no | `true` |
| `roles.period_binding` | bool | iff claimed | `true` |
| `roles.extremum` | list | iff claimed | `min` · `max` |
| `counts` | bool | no | `true` |
| `register` | string | no | a lookup path |
| `rulings.label_of` | string | no | a column name |
| `rulings.register` | scalar | no | `common` · `legal` · `long` · `short` · `code` |
| `rulings.finer_than` | string | no | a column name |
| `rulings.scoped_by` | string | no | a column name |
| `rulings.sort` | scalar | no | `asc` · `desc` · `none` |
| `rulings.never_axis` | string | no | the measurement, in words |
| `rulings.evidence` | string | no | a DQ issue id |

## Rules this model holds

1. **One fact, one key.** No column states the same thing twice, and no key restates what another declares.
2. **Claim a role, state its terms.** The qualifier *is* the value, so a role cannot be claimed without it — the requirement is structural, not a gate.
3. **A declaration describes the data; a prohibition is a rule.** A column that *is* an axis says so even when policy forbids grouping by it; the prohibition, its reason and its evidence live in a rule that refuses and cites the measurement. Declaring a real axis "not an axis" to express a policy would make the ontology lie about the warehouse.
4. **Absence is never load-bearing except where it is declared to be.** `roles: {}` means *offered to nothing*; a missing `roles` means *unclassified*. The two are different findings.
