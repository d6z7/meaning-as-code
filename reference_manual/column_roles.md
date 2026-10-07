---
title: What a column offers — the five things a question may do with it
status: >-
  CURRENT (2026-10-07, revision 5). `offers` is what mac.schema.json admits and what the runtime
  loads: a MAP from each use a question may make of the column to that use's own terms, with `{}`
  legal and an ABSENT `offers` a different finding. TERMS ARE BARE — `axis: categorical`,
  `aggregate: {type: flow}` — closed enums the schema validates by name. Every planner step asks
  `Grounding.offers(column, use)`, which reads this map; the five scalar role NAMES are derived by
  `ColumnSpec.role` and no column carries a `role:` key. The fold law reads `axis` and refuses a
  fold it does not permit (`ADDITIVITY_VIOLATION`, mac-runtime `planner/plan.py` +
  `foldplane/law.py`). A declared `axis` kind must agree with the column's measured type family,
  which the runtime suite measures: 70 of 70 on contoso5. THE FILENAME IS KEPT as a stable address —
  `guardrails/reference_manual.yaml` and two generators name this path — and the page is about
  `offers`, which is the key. column_declaration.md is the overview; this page is the detail.
audience: ontology authors, importer developers, framework developers
companions:
  - column_declaration.md     # the whole column on one page — every key, and who reads each answer
  - column_specification.md   # the long form: every key, with its enforcement state
  - column_rulings.md         # what a PERSON decided about a column, on top of what it offers
  - measures.md               # the fold law, stated once: aggregate.type × axis
  - shape_reference.md        # where `columns:` nests in a concept file
  - ../mac_vocabulary.yaml    # the authoritative terms; the chapters below are generated from it
---

# What a column offers

A column declares **one** key for what a question may do with it:

> **`offers` — a map from a use to that use's own qualifier.**

Five uses. A column claims every one that is true of it, and the qualifier *is* the value, so a use
cannot be claimed without stating its terms.

```yaml
grounding:
  source:
    relation: v_contoso5_sales_line
    key: [order_key, line_number]
    columns:
      order_key:    {offers: {}}
      customer_key: {offers: {axis: categorical}, references: Customer}
      order_date:   {offers: {axis: time, period_binding: true}}
      quantity:     {offers: {aggregate: {type: flow, unit: units}}}
      city:         {offers: {axis: categorical, suppressed: DQ-IDENTIFYING-DIM_CUSTOMER-CITY}}
```

> **A use is READ, not decided** — every one of the five follows from cardinality, type and
> reference structure, which is why a generator assigns them over a thousand columns with no human
> present. The exception is `suppressed`, and it is the exception *because* it is a judgement: the
> ratio that gets you to the door is a measurement, that grouping on the column names individuals
> is not. If you find yourself *deciding* rather than *reading* anywhere else, you are holding a
> **ruling**. See [column_rulings.md](column_rulings.md).

## The key

| key | card | value | required | says | read by |
|---|---|---|---|---|---|
| `offers` | **map** | use → that use's qualifier | **yes** — `{}` is legal | what a question may do with this column | the planner, at every step it takes |

| what you write | what it means | what it is |
|---|---|---|
| `offers: {axis: categorical}` | a question may group or filter by this column and do nothing else with it | a classification |
| `offers: {}` | the column exists, is typed, is loaded, and **no question is offered it** | a positive statement |
| *no `offers` key* | nobody has said what this column is | a finding, not a state |

Three keys sit beside `offers` on a column, and two more on the source, because none of them says
what a question may DO with the column:

| also declared | where | says | page |
|---|---|---|---|
| `references` | on the column | my values identify one row of **that concept** | [column_specification.md](column_specification.md#references--a-pointer-at-another-concept) |
| `value_register` | on the column | the file whose rows **are** my values | [column_specification.md](column_specification.md#value_register--where-this-columns-values-come-from) |
| `rulings` | on the column | how this column relates to **another column** | [column_rulings.md](column_rulings.md) |
| `key` | on the **source** | what makes ONE ROW unique, in order | [column_specification.md](column_specification.md#key--what-makes-one-row-unique) |
| `counts` | on the **source** | which column a count of this concept DISTINCTs | [column_specification.md](column_specification.md#counts--when-a-count-of-the-concept-is-not-a-count-of-its-rows) |

---

## 1 · Two real relations, every column assigned

A fact and a dimension from contoso5. Every column, its measured cardinality, and what it offers.

### `v_contoso5_sales_line` — the FACT, 223 974 rows

Read as `NetRevenue` keys it. **Seven** concepts ground this relation — `UnitsSold`, `GrossRevenue`,
`NetRevenue`, `SalesCost`, `Discount`, `Margin` and `Order` — and each reads a different measure
column. The axes are the same in all seven; the key is not, because `Order` is keyed on `order_key`
alone while the other six are keyed on `[order_key, line_number]`.

| column | distinct | `offers` | other keys | why |
|---|---:|---|---|---|
| `order_key` | 93 470 | `{}` | — | half the grain — `key: [order_key, line_number]` says so on the SOURCE, and the column adds nothing to it |
| `line_number` | 7 | `{}` | — | the other half. A position in a basket: *"revenue by line number"* asks nothing, so no `axis` |
| `order_date` | 3 450 | `{axis: time, period_binding: true, extremum: [min, max]}` | — | THE reporting date — §5 |
| `delivery_date` | 3 498 | `{axis: time, extremum: [min, max]}` | — | a real date, askable by name, never the one a bare period binds to |
| `customer_key` | 52 189 | `{axis: categorical}` | `references: Customer` | points at a row over there **and** a question groups by it — 21 of contoso5's 112 columns are this shape |
| `store_key` | 64 | `{axis: categorical}` | `references: Store` | 64 distinct over 223 974 rows is a pointer, not a category — and it is still an axis |
| `product_key` | 2 517 | `{axis: categorical}` | `references: Product` | likewise |
| `currency_code` | 5 | `{axis: categorical, extremum: [min, max]}` | — | 5 members, a legitimate axis |
| `quantity` | 10 | `{aggregate: {type: flow, unit: units}, extremum: [min, max]}` | — | items sold accumulate per period (`UnitsSold`) |
| `net_amount` | 54 291 | `{aggregate: {type: flow, unit: USD, default: true}, extremum: [min, max]}` | — | accrues per period, and it is the one a bare question about `NetRevenue` folds |
| `net_price` | 18 407 | `{aggregate: {type: intensive, unit: USD}, extremum: [min, max]}` | — | a rate: a TOTAL of prices is not a price. 18 407 distinct values are not an invitation to group by it |
| `unit_cost` | 1 955 | `{aggregate: {type: intensive, unit: USD}, extremum: [min, max]}` | — | likewise a per-unit rate (`SalesCost`) |

**Read the pointer shape:** many rows, far fewer distinct values, every value present in a parent
relation. `store_key` has 64 distinct over 223 974 rows — a pointer, even though its cardinality
looks dimension-sized. What it points AT is `references: Store`, authored, because a column name is
not a concept name and matching one against the other has been observed to fail.

### `dim_customer` — the DIMENSION, 104 990 rows

| column | distinct | `offers` | `rulings` | why |
|---|---:|---|---|---|
| `customer_key` | **104 990** | `{}` | — | distinct **equals** row count, and `key: customer_key` on the source is where that is said |
| `valid_from` | 11 305 | `{}` | — | when the ROW was written |
| `valid_to` | 14 711 | `{}` | — | the other end of the SCD-2 validity window |
| `continent` | 3 | `{axis: categorical, extremum: [min, max]}` | — | |
| `country_code` | 8 | `{axis: categorical, extremum: [min, max]}` | `finer_than: continent` | 8 codes rolling cleanly into 3 continents |
| `state` | 565 | `{axis: categorical, extremum: [min, max]}` | `scoped_by: country_code` | 40 codes are reused across countries |
| `city` | 34 581 | `{axis: categorical, extremum: [min, max], suppressed: DQ-IDENTIFYING-DIM_CUSTOMER-CITY}` | — | 21 317 values are held by exactly one row. It **is** an axis and says so; the suppression carries the finding |
| `customer_name` | 99 200 | `{axis: categorical, extremum: [min, max], suppressed: DQ-IDENTIFYING-DIM_CUSTOMER-CUSTOMER_NAME}` | — | 94 488 singletons; same shape, same route |
| `gender` | 2 | `{axis: categorical, extremum: [min, max]}` | — | |
| `birth_date` | 24 147 | `{axis: time, extremum: [min, max]}` | — | a real time axis of the business, 1935-02-04 to 2002-02-20 |

**Notice what cardinality alone cannot tell you.** `continent` (3) and `gender` (2) are both tiny and
one of them is a hierarchy level. `city` (34 581) and `customer_key` (104 990) are both high.
`valid_from` (11 305) has the exact shape of a date axis and `birth_date` (24 147) is one. In each
case what the column offers — or the judgement on top of it — comes from something the numbers do not
contain.

### Reading the uses off the data

| what you measure | what it reads to |
|---|---|
| distinct **equals** row count, no nulls | the source's `key`, one column — not a use |
| unique only in combination with its siblings | the source's `key`, an ordered list — not a use |
| many rows, few distinct, every value present in a parent relation | `references: <Concept>` beside whatever the column offers |
| distinct far below row count, categorical, repeated | `axis: categorical` |
| a date, a month, a period label | `axis: time` |
| **the** date a bare period must bind to, where a relation carries several | `axis: time` **and** `period_binding: true` |
| a numeric payload where adding two values means something | `aggregate` — then [measures.md](measures.md) decides the `type` |
| the earliest or latest value is something a question asks for | `extremum` |
| most of its values name exactly one row, and a person has ruled on it | `axis` **and** `suppressed: <DQ id>` |
| exists for the pipeline; nobody would ask about it | `offers: {}` |

---

## 2 · The five uses

| use | qualifier card | terms | says | claiming it commits the bundle to | read by |
|---|---|---|---|---|---|
| `axis` | scalar | `time` · `categorical` | a question may **group or filter** by me | every fold across me being judged by the law, and the column being OFFERED as groupable to a reader | `planner/grounded_columns.axis_columns` · `column_facts.axis` · the fold law · [`additivity_guard`](rules_and_canons/semi_additive_balance/additivity_guard.md) |
| `suppressed` | scalar | a DQ register id | I **am** that axis and no question may group by me. **Requires `axis`** | a refusal that quotes the finding this value names | `planner/plan._axis_denied` → `POLICY_DENIED` |
| `aggregate` | map | `{type, unit, default, additivity}` | a question may **fold** me | one fold per axis, fixed by `type`; a comparison legitimate only inside `unit` | `column_facts.measure_type` / `.unit` · `planner/plan._check_additivity` |
| `period_binding` | `true` | — | I am **the** reporting date of this relation | *"sales in March"* binding here and nowhere else | `planner/plan._period_columns` · `interpret/vocabulary` |
| `extremum` | list | `[min]` · `[max]` · `[min, max]` | my earliest or latest value may be **asked for** — not folded | answering *"when did we first sell in Spain"* from this column, and ASKING when a concept admits more than one | `planner/plan._OPERATION_NEEDS` — the MIN/MAX route |

A column carries as many of the five as are true of it. `customer_key` on a sale line is
`{axis: categorical}` with `references: Customer` — it points at a row over there **and** a question
groups by it. Neither claim weakens the other, and the retired scalar `role` could hold only one of
them: it held `key`, and `key` denied the axis to all 21 columns of that shape.

### `axis` — two kinds, because only one of them has the property that matters

| term | the axis is | the law's row for it |
|---|---|---|
| `time` | ordered and temporal — day, month, quarter | a `stock` does **not** accumulate along it |
| `categorical` | non-temporal — product, location, customer, currency | flows and stocks are both additive along it |

Product, store and customer all fold the same way, so they are one term. This is why `axis` carries a
term and not a boolean. A column with **no** `axis` is never consulted by the law: there is no
axis to cross. Two terms and no more — `test_foldplane_law` asserts that five types × two kinds is
exactly the ten cells the law states, so a third kind would leave cells nobody has ruled on.

### `suppressed` — the axis no question may group by

A column declares truthfully what it IS, including when a person forbids using it that way. `city`
is `{axis: categorical}` — 34 581 distinct values over 104 990 customers, 21 317 of them held by one
row — because it genuinely *is* a categorical axis of the warehouse. The prohibition sits **beside**
that, in the same map, and its value is the id of the finding that justifies it:

```yaml
city:
  offers:
    axis: categorical
    extremum: [min, max]
    suppressed: DQ-IDENTIFYING-DIM_CUSTOMER-CITY
```

Declaring a real axis "not an axis" to express a judgement would make the ontology lie about the
warehouse, and the next reader of the measurement finds 34 581 distinct values under a column the
ontology says is not an axis. The filter stays legal — a suppression forbids the AXIS, not the
predicate — which is only expressible because `axis` is still declared. The full route, and why this
is not a member of `rulings`, is in
[column_rulings.md](column_rulings.md#when-the-judgement-is-a-prohibition).

### `aggregate` — the qualifier of a foldable column

| sub-key | card | required | terms | says |
|---|---|---|---|---|
| `type` | scalar | **yes**, within `aggregate` | `flow` · `stock` · `intensive` · `precomputed` · `target` — the members of `mac.concept.column.measure_type` | what kind of quantity this is: the law's row |
| `unit` | string | **yes**, within `aggregate` | free prose — `USD`, `units`, `m2`, `to-currency per from-currency` | what the number is in. Two different units may not be combined |
| `default` | bool | no | `true` | **which** aggregate column is *the* one, when a concept carries several |
| `additivity` | map | no | `{<axis>: <effect>}` | a per-axis exception the type cannot state — leave it unwritten |

**The type licenses the fold; the unit licenses the comparison.** Both are declared once per measure and
read everywhere — [measures.md](measures.md) carries the type chapter, the worked contoso5 measures, and
what a unit does that a type cannot. `default` was spelled `canonical` until 2026-10-07, a word
retired from `identity` the same day; `NetRevenue.net_amount` carries it and `net_price` does not.

### `period_binding` — which date a bare period lands on

| value | card | says | read by |
|---|---|---|---|
| `true` | the only value | this is THE reporting date of the relation | `planner/plan._period_columns`, `interpret/vocabulary` |

One per relation. The claim only matters where a relation carries several dates — and there it decides
the number: *"lines in 2025"* answers a different figure depending which of `order_date` and
`delivery_date` is bound, and nothing in the result says which. See §5.

### `extremum` — a value asked for, never folded

| value | says |
|---|---|
| `[min]` | the earliest or smallest value this column holds may be asked for |
| `[max]` | the latest or largest |
| `[min, max]` | both |

**Not a fold.** An extremum PICKS one value that already exists in the data instead of combining
several, so it answers to no additivity cell and is meaningful on a column no law would let anyone SUM
— a date axis admits it while remaining non-aggregatable. When a concept admits more than one such
column, `planner/plan.py` ASKS, naming every column the declaration admits; a concept admitting exactly
one needs no question and gets none. It is its own use rather than a corner of the others precisely so
that a column can DECLINE it: `models._ROLE_OFFERS` granted every `dimension` and every `measure` one
implicitly, so no column could.

---

## 3 · The fold law — stated once, in measures.md

The law is `aggregate.type` × `axis` → the correct fold, over **kinds** and never over column names,
which is what makes it universal.

| this page declares | the law uses it as |
|---|---|
| `aggregate.type` | the row |
| `axis` | the column |

**The grid, its three effects (`additive` · `average` · `none`) and the refusal text live in
[measures.md](measures.md#the-whole-system-in-one-table)** and are not repeated here. Two consequences
belong to this page: a fold the law does not permit is refused naming the axis it crossed, and a column
with no `axis` is never consulted at all.

## 4 · What reads each use

Every use is reached through one function, so a bundle whose columns declare them is read by the
same code everywhere.

| asked | where | answers for | state |
|---|---|---|---|
| `Grounding.offers(column, use)` — may a question do this with this column | mac-runtime `ontology/models.py`, and every planner step that asks it | all five | ENFORCED |
| `Grounding.offering(use)` — the whole population that offers it | `ontology/models.py` | all five | ENFORCED |
| the groupable set a prompt OFFERS and a refusal LISTS | `planner/grounded_columns.axis_columns` | `axis` minus `suppressed` | ENFORCED |
| whether a predicate may land on this column | `planner/sql._filterable` — `offers(col, "axis") or offers(col, "identity")` | `axis`, and the pointer | ENFORCED |
| which column a fold lands on, and the fold's legality | `planner/plan._check_additivity`, `foldplane/law.py` (`ADDITIVITY_VIOLATION`) | `axis` + `aggregate` | ENFORCED |
| which date a bare period binds to | `planner/plan._period_columns`, `interpret/vocabulary` | `period_binding` | ENFORCED |
| which column a MIN/MAX names, and whether to ask | `planner/plan._OPERATION_NEEDS` | `extremum` | ENFORCED |
| the refusal when a question names a column it may not group by | `planner/plan._axis_denied` | `suppressed`, and an empty `offers` | ENFORCED — see [column_effects.yaml](column_effects.yaml) for what it reads at a named commit |

## 5 · The constellations behind two of the uses

Two claims exist because of a named constellation. **The constellations are documented as patterns —
read them there, not here.**

| claim | the constellation | pattern |
|---|---|---|
| `period_binding: true` | one relation, several dates, each a different ROLE of the same calendar — `order_date` 2016-05-18..2025-12-31 and `delivery_date` ..2026-01-06, so *"lines in 2025"* answers a different number depending which is bound, and nothing in the result says which | [role_playing_dimension](patterns/dimensional_special_cases/role_playing_dimension.md) |
| `offers: {}` | a column with the shape of a perfectly good date axis — `valid_from`, 11 305 distinct over 104 990 rows — that records when the ROW was written, not when anything happened | *no pattern yet* |

**What this page adds that the pattern does not:** the pattern tells you what to do when you meet the
constellation. This page tells you which USES it resolves to, and §1 shows every column of two real
relations with its uses already assigned, so the shapes can be read off real data.

## 6 · Where `columns:` sits — a complete concept file

`offers` is not a standalone block. This is contoso5's `Customer`, structurally complete, abridged
only in the prose fields (`…`):

```yaml
# ontology/concepts/customer.yaml
metadata:
  concept: Customer
  source: CONTOSO5
  schema_version: 0.1.19
  status: draft
  owner: operator
  confidence: I
  provenance: derived

concept:
  name: Customer
  label: Customer
  class: entity
  definition: >-
    A person who can place an order, served as the geography they belong to plus two
    generalised demographics. …

contract:
  default_reading: >-
    …
  rules:
    - id: customer.geography.rollup_only
      kind: mac.concept.rule.resolution
      when:  "a question groups customers by geography"
      then:  …
      never: …
      why:   …
      binds: [country_code, continent]
      confidence: P

grounding:
  kind: sql_table
  source:
    relation: dim_customer
    key: customer_key
    columns:
      customer_key:  {offers: {}}
      customer_name:
        offers:
          axis: categorical
          extremum: [min, max]
          suppressed: DQ-IDENTIFYING-DIM_CUSTOMER-CUSTOMER_NAME
      continent:     {offers: {axis: categorical, extremum: [min, max]}}
      country_code:
        offers:  {axis: categorical, extremum: [min, max]}
        rulings: {finer_than: continent}
      state:
        offers:  {axis: categorical, extremum: [min, max]}
        rulings: {scoped_by: country_code}
      city:
        offers:
          axis: categorical
          extremum: [min, max]
          suppressed: DQ-IDENTIFYING-DIM_CUSTOMER-CITY
      gender:        {offers: {axis: categorical, extremum: [min, max]}}
      birth_date:    {offers: {axis: time, extremum: [min, max]}}
      valid_from:    {offers: {}}
      valid_to:      {offers: {}}
  serves_from: data/transforms/dim_customer.sql
```

`city` and `customer_name` are axes of this warehouse and declare it. That no question may group by
them travels in the same map, as `suppressed`, whose value is the id of the finding the refusal
quotes — [column_rulings.md](column_rulings.md#when-the-judgement-is-a-prohibition).

**What is NOT in `columns:`, and why.** `type` and measured cardinality come from
`data/datasets/dim_customer.yaml` and are merged at load. They are *measured*, not authored —
putting them here would create a second home for a fact the warehouse already states. `columns:`
carries only what a person declares: what the column offers, what it points at, where its values
come from, and any rulings. What makes a row unique is not there either: `key` is on the source,
because it has an ORDER.

## 7 · Claiming a use

Ask all five. Each answer is independent of the other four, so a column may leave with one use,
three, or none.

```
1. Would a question group or filter by it?                         → axis: time | categorical
2. … and has a person ruled that nobody may group by it?           → suppressed: <DQ id>, BESIDE the axis
3. Does adding two of its values mean something?                   → aggregate: {type, unit}
4. Is it THE date a bare period must bind to?                      → period_binding: true
5. Is its earliest or latest value something a question asks for?  → extremum: [min | max]
   None of the five                                                → offers: {}

   Does it identify a row of THIS concept?    → the source's `key`, which has an order
   Does it identify a row of ANOTHER concept? → references: <ConceptName>
```

**Anti-patterns**

- **`period_binding` on every date.** A relation with three dates has one reporting date; the others are
  ordinary `axis: time` columns. Marking them all makes the binding arbitrary.
- **An aggregate mistaken for an axis.** `net_price` has 18 407 distinct values. That is not an
  invitation to group by it; `aggregate` and `axis` are different claims and a numeric payload is
  rarely both.
- **`offers: {}` used to hide an inconvenient column.** It means *not part of the business*, not
  *awkward*. A column someone might legitimately ask about declares its axis and, if a person has
  ruled on it, a `suppressed` carrying the finding.
- **`suppressed` instead of `axis`.** The schema refuses it (`dependentRequired`), and the reason is
  the point: a suppression is a judgement on top of what the warehouse is, never a denial of it.
- **A use claimed without its qualifier.** The qualifier *is* the value: `axis:` with nothing after
  it says which of two kinds?
- **`offers` omitted.** That is not `offers: {}`. One says *offered to nothing*; the other says
  *nobody has classified this column*, and they are different findings.

---

## 8 · The measured companion — `storage_role`

A column answers a second question that has nothing to do with what it offers: what SHAPE is it in
the relation.

| column | storage_role | `offers` + other keys |
|---|---|---|
| `dim_store.store_key` | `primary_key` | `{}` — and `key: store_key` on the source |
| `dim_store.country_code` | `value` | `{axis: categorical, extremum: [min, max]}` |
| `v_contoso5_sales_line.customer_key` | `foreign_key` | `{axis: categorical}` + `references: Customer` |
| `v_contoso5_sales_line.line_number` | `primary_key` + `key_position: 2` | `{}` — the second name in `key: [order_key, line_number]` |
| `dim_store.status_annotation` | `discriminator` | `{axis: categorical, extremum: [min, max]}` |

**You never author this one.** It is measured — the profile plane counts distinct values and nulls, the
reference plane measures inclusion against candidate parents, and `data/datasets/<relation>.yaml`
records what they found. If you are hand-writing a `storage_role`, something upstream failed. Every key
column is `primary_key`, and its place in a composite key is the integer `key_position`.

<!-- BEGIN GENERATED:vocabulary-terms:dataset.column.role (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> The physical shape of a column in its relation, independent of its analytical role.

*`mac.dataset.column.role` · 6 terms · closed — these are all of them*

#### `mac.dataset.column.role.primary_key`

The relation's own identity: one row per distinct value, measured rather than assumed.

#### `mac.dataset.column.role.foreign_key`

A reference to another relation's identity. Whether every value is PRESENT in the parent is a
separate measurement — a declared key says the relationship is intended, not that it holds.

#### `mac.dataset.column.role.value`

A payload column: it carries data, not identity and not a choice of row kind.

#### `mac.dataset.column.role.discriminator`

A column whose value selects WHICH KIND of row this is — the column a perspective, status or
type is read from.

#### `mac.dataset.column.role.audit`

A column recording WHEN THE ROW WAS WRITTEN or by what, rather than anything that happened in
the business. A load timestamp, a batch id, a validity window on a versioned row. It is
physically a payload column, and naming it apart is what keeps it out of a question's reach:
grouping a measure by the row's own write time is meaningless, and nothing in the data says so.

#### `mac.dataset.column.role.delivery_axis`

A column the DELIVERY partitions or orders by, carried for the pipeline's sake rather than for a
question. `mac_admit_identity.py` assigns it to a column an SME has ruled is not the relation's
identity but which the load still keys on — so the key survives as a physical fact without
claiming to be the concept's identity.
<!-- END GENERATED:vocabulary-terms:dataset.column.role -->

---

## 9 · The vocabulary registers

The terms above are declared in `mac_vocabulary.yaml`, and the chapters below are generated from it.

### The five uses — `mac.concept.column.offers`

<!-- BEGIN GENERATED:vocabulary-terms:concept.column.offers (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> WHAT A QUESTION MAY DO WITH A COLUMN. A column declares these under `roles:` as a MAP from the
term to that role's own qualifier — `identity: composite`, `axis: time`, `aggregate: {type,
unit}` — so the role and its parameter are one statement and a role cannot be claimed without
its terms. THIS WAS `query_use`, 'the machine-readable half of concept.column.role', and `role`
was the other half: one fact in two vocabularies, of which only one had a key in mac.schema.json
and neither could say that a join key is also an axis. 21 of contoso5's 112 columns are exactly
that. `role` is gone and this is the whole declaration. AN EMPTY MAP IS A STATEMENT: the column
is offered to no question, which is what `role: housekeeping` said. A MISSING `roles:` is a
column nobody classified, and the two are different findings.

*`mac.concept.column.roles` · 5 terms · closed — these are all of them*

#### `mac.concept.column.roles.axis`

LEGITIMATE IN A FILTER AND IN A GROUP BY. The column names a thing a question can slice by. A
per-column `rulings.never_axis` still overrides this with its own measurement: the role says the
KIND of column may be an axis, the ruling says this ONE may not.

#### `mac.concept.column.roles.aggregate`

A NUMBER A QUESTION MAY FOLD. HOW it folds is not stated here and must not be: it is
`concept.column.measure_type` x `concept.axis` -> `aggregation_effect`, read through
`framework.vocabulary().additivity`. A column carrying this use whose every additivity cell is
`none` — `precomputed`, `target` — is foldable by nothing, and that is the measure type's
ruling, not this one's.

#### `mac.concept.column.roles.period_binding`

THE COLUMN A QUESTION'S PERIOD BINDS TO. Says which date is THE reporting date when a relation
carries several, so "sales in March" cannot silently pick the wrong one.

#### `mac.concept.column.roles.extremum`

THE EARLIEST OR LATEST VALUE THE COLUMN HOLDS may be asked for -- `min`/`max`, which is what a
"when did X first ..." question wants. NOT A FOLD, and that is why it is a separate use rather
than a corner of `aggregate`: an extremum PICKS one value that exists in the data instead of
combining several, so it answers to no additivity cell and is meaningful on a column no law
would let anyone SUM. A date axis therefore admits it while remaining non-aggregatable.

#### `mac.concept.column.roles.identity`

WHAT THE ROW IS, FOR JOINING AND COUNTING. Filtered on an exact value a register resolved to,
joined on, and what COUNT(DISTINCT) counts — never matched against a label and never aggregated,
an identifier that is summed being a number nobody asked for.
<!-- END GENERATED:vocabulary-terms:concept.column.offers -->

### The five role names are DERIVED, and have no chapter

`mac.concept.column.role` was retired from the vocabulary on 2026-10-07 and no column carries a
`role:` key. The five names — `key`, `dimension`, `measure`, `period`, `housekeeping` — are
computed from a column's `offers` map by `ColumnSpec.role`, **with the source's `key` as an
argument**, for one legacy reader, `grounding.field_roles`; the derivation reproduces all 112 of
contoso5's previously-authored values. `models._ROLE_OFFERS` is its inverse and is the only
surviving copy of the retired `mac.concept.column.role#query_use` table. Nothing declares them, so
there is nothing here to generate.

### `mac.concept.column.identity` is retired, and has no chapter either

Its last term was `reference`, and a foreign key's declaration is the CONCEPT IT POINTS AT rather
than a term from a closed set — so the fact is the top-level `references:` key, whose value is a
concept name. `canonical` and `composite` went earlier the same day, to the source's `key`, which
can state the key's ORDER. All three are refused BY NAME by `ColumnRoles`, each refusal naming where
the fact went, so an unmigrated bundle is told it moved rather than that it has a typo.
