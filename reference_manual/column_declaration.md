---
title: The column declaration — everything a column says, and who reads each answer
status: >-
  PROPOSED (2026-10-07) — this page describes the column model as DESIGNED. The `axis` key is enforced;
  `roles` as a map, `identity: composite` and the removal of `grain`/`semantics`/`never_axis` are put to
  the operator and are not yet admitted by mac.schema.json. For what the schema admits TODAY see
  column_specification.md, which stays the authority until this is ruled on.
audience: ontology authors, importer developers, framework developers
companions:
  - column_specification.md   # the long form: every flag, with its enforcement state
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
      columns:
        order_key:     {roles: {identity: composite}}
        customer_key:  {roles: {identity: reference, axis: categorical}}
        order_date:    {roles: {axis: time, period_binding: true}}
        quantity:      {roles: {aggregate: {type: …measure_type.flow, unit: units}}}
        valid_from:    {roles: {}}
```

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
| `identity` | scalar | `canonical` · `composite` · `reference` | the row is identified by me — alone, jointly, or elsewhere | `COUNT(DISTINCT …)`; join resolution; `composite_key_guard` |
| `axis` | scalar | `time` · `categorical` | a question may **group or filter** by me | the fold law; `additivity_guard` |
| `aggregate` | map | `{type, unit, canonical}` | a question may **fold** me | the fold law; unit algebra; the measure route |
| `period_binding` | `true` | — | I am **the** reporting date when the relation carries several | period binding — *"sales in March"* cannot pick the wrong date |
| `extremum` | list | `[min]` · `[max]` · `[min, max]` | my earliest or latest value may be **asked for** — not folded | the extremum route — *"when did we first sell in Spain"* |

### `identity` — three ways to identify

| term | holds when | consequence |
|---|---|---|
| `canonical` | this column **alone** identifies an instance | it is what `COUNT(DISTINCT …)` counts; at most one per concept |
| `composite` | this column **with its siblings** identifies an instance | the set of columns carrying it **is** the key; none of them identifies anything alone, and using one as if it did returns a set where a row was expected |
| `reference` | this column identifies an instance **in another concept** | the row names a row over there; whether every value is present there is a measurement, not a declaration |

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

## Worked: the same shape meaning two different things

The two cases that decide why `axis` is declared per column rather than derived from identity.

| | `units_sold` | `exchange_rate` |
|---|---|---|
| the key | `order_key` + `line_number` | `date_day` + `from_currency` + `to_currency` |
| each carries | `identity: composite` | `identity: composite` |
| **and also** | *nothing* | `axis: time` / `axis: categorical` |
| so a question may | join and count on them | join, count, **and group** by them |
| because | a line number is a position in a basket; *"revenue by line number"* asks nothing | *"the USD→EUR rate on 2025-01-03"* names the row **by** its axes |

Both are the grain. Only one is also an axis, and the only thing that says so is the `axis` role — which is why it is a declaration and not a derivation.

## Where identity and the key part company

A concept's key identifies a **row**. What a **count** counts is sometimes a different column.

| | `store.store_key` | `store.location_code` |
|---|---|---|
| roles | `identity: canonical` | `identity: reference` |
| `counts` | — | `true` |
| rows | 74 — one per trading period | — |
| a count of *stores* | would say 74, wrongly | says **67** |

`counts` is how a concept says *"a count of me is not a count of my rows"*, and the answer discloses which column it counted.

## The complete surface, at a glance

| | card | required | terms |
|---|---|---|---|
| `roles` | map | **yes** | `identity` · `axis` · `aggregate` · `period_binding` · `extremum` |
| `roles.identity` | scalar | iff claimed | `canonical` · `composite` · `reference` |
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

## Rules this model holds

1. **One fact, one key.** No column states the same thing twice, and no key restates what another declares.
2. **Claim a role, state its terms.** The qualifier *is* the value, so a role cannot be claimed without it — the requirement is structural, not a gate.
3. **A declaration describes the data; a prohibition is a rule.** A column that *is* an axis says so even when policy forbids grouping by it; the prohibition, its reason and its evidence live in a rule that refuses and cites the measurement. Declaring a real axis "not an axis" to express a policy would make the ontology lie about the warehouse.
4. **Absence is never load-bearing except where it is declared to be.** `roles: {}` means *offered to nothing*; a missing `roles` means *unclassified*. The two are different findings.
