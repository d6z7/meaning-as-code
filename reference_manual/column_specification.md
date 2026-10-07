---
title: The column specification — everything about a column, on the column
status: >-
  CURRENT (2026-10-07). The long form of column_declaration.md: every key, its cardinality, its
  terms, and who reads it. A column has FOUR top-level keys — `roles` (required), `counts`,
  `register`, `rulings` — and `mac.schema.json` admits only those four
  (`additionalProperties: false`), as does mac-runtime's `ColumnSpec` (`extra="forbid"`), so a fifth
  is a load error rather than a line nothing reads. `roles` is a map from each USE a question may
  make of the column to that use's own terms; the five scalar role names are DERIVED by
  `ColumnSpec.role` and never authored. Every planner step asks `Grounding.offers(column, use)`,
  which reads this map. contoso5 is authored entirely in this shape, and every example on this page
  is a column of that bundle. column_declaration.md carries the same model on one screen.
audience: ontology authors, importer developers, framework developers
companions:
  - column_declaration.md     # the same model on one screen — the overview this page is the long form of
  - column_roles.md           # the five roles in detail, generated from the vocabulary
  - column_rulings.md         # the rulings block, one section per ruling
  - column_effects.yaml       # per key: which plane, which outcome classes, and what reads it
  - measures.md               # the fold law and the measure types it is stated over
  - how_a_question_becomes_sql.md
  - column_map.generated.md   # the generated, cannot-drift view of the schema's column map
  - shape_reference.md        # where `columns:` nests in a concept file
---

# The column specification

A concept means what its columns say. Each column answers one question —

> **What may a question do with me, and on what terms?**

— and every key on a column is one of those uses, a parameter of one, or a relation to another
column. [column_declaration.md](column_declaration.md) states the same model on one screen.

## The principle

> **A fact about one column is declared on that column.**
> A fact about the concept, or spanning several columns, stays at concept level.

Nothing else. Every rule below follows from it.

---

## The shape

```yaml
grounding:
  sources:
    - relation: <relation>
      columns:

        <column-name>:
          roles:                                  # REQUIRED — `{}` is legal
            identity: canonical | composite | reference
            axis: mac.concept.axis.time | mac.concept.axis.categorical
            aggregate:
              type: mac.concept.column.measure_type.flow | .stock | .intensive | .precomputed | .target
              unit: <string>
              canonical: true
            period_binding: true
            extremum: [min, max]
          counts: true
          register: <bundle-relative path>
          rulings:
            label_of: <column>
            register: common | legal | long | short | code
            finer_than: <column>
            scoped_by: <column>
            sort: asc | desc | none
            never_axis: <the measurement, in words>
            evidence: <DQ register id>
```

No column carries all of that. Most carry one or two roles and nothing else, and contoso5's
`Customer` is typical: one canonical identity, seven axes, four of them ruled on, and two columns
offered to no question.

```yaml
sources:
  - relation: dim_store
    columns:
      store_key: {roles: {identity: canonical}}
  - relation: dim_customer
    columns:
      gender: {roles: {axis: mac.concept.axis.categorical, extremum: [min, max]}}
```

### Why a column nests under its source

A column name only means anything within a relation, and `country_code` is the proof: contoso5 carries
it on `dim_country`, `dim_customer`, `dim_location` and `dim_store`, and it plays a different part on
each. A block keyed on a bare column name could not say which one it meant; neither could it hold a
concept that binds two relations, where one identity legitimately has two spellings.

| level | what it holds | why it cannot move |
|---|---|---|
| `grounding.sources[]` | one relation, and the columns of THAT relation | a concept may bind several relations, and each has its own spelling of the identity they share |
| `sources[].columns` | a map from column name to that column's four keys | the facts are per column AND per relation; a name alone is ambiguous |
| `sources[].columns.<col>.roles` | the uses a question may make of this column | per column AND per CONCEPT — `country_code` is the identity of `Country` and a categorical axis of `Customer` |

A bundle may still write `columns:` as a flat list of names. That form says which columns a concept
serves and nothing about what each one IS, `check_column_spec` reports it, and `Grounding.offers`
falls back to the derived role for it.

---

## The column, top level

Four keys, four different questions. Only `roles` is required, and `mac.schema.json` admits no
fifth: `rol: dimension` is a LOAD ERROR naming the four, where a misspelled sentence is just
another sentence.

| key | card | value | required | says | read by |
|---|---|---|---|---|---|
| `roles` | **map** | role → that role's qualifier | **yes** — `{}` is legal | what a question may do with this column | the planner, at every step it takes, through `Grounding.offers(column, use)` |
| `counts` | bool | `true` | no | **a count of this concept counts THIS column**, not the canonical one | the count route, via `concept.identity.counts_as`; disclosed in the answer |
| `register` | string | a bundle-relative path | no | where this column's values come from — one virtual table per value set | `resolver/registers`, `resolver/register_match` — name → code resolution |
| `rulings` | map | see [`rulings`](#rulings--what-a-person-decided-about-a-column) | no | how this column relates to **another column** | `planner/plan.py`, `planner/sql.py`, `interpret/vocabulary.py` |

`roles` is the only key read through a projection; `rulings` is read ON the column, through
`Grounding.spec(name).rulings`, because a ruling is a fact about the column.

### Two absences, two different findings

| what is written | what it means | what follows |
|---|---|---|
| `roles: {}` | **a positive statement** — the column exists, is typed, is served, and is offered to no question | nothing: no route reaches the column, and its absence from every answer is correct. contoso5 writes it on `valid_from` / `valid_to` |
| no `roles` key | **unclassified** — nobody has said what the column is for | a finding raised against the concept: an unjudged column is work owed, not a state |

Absence is never load-bearing except where it is declared to be. These two are the declared case and
must not be collapsed into one.

---

## `roles` — the five uses, each with its own terms

The value of a role **is** its qualifier, so a role cannot be claimed without stating its terms.
The requirement is structural: there is nothing to write that would claim a role and say nothing.

| role | qualifier card | terms | says | read by |
|---|---|---|---|---|
| `identity` | scalar | `canonical` · `composite` · `reference` | the row is identified by me — alone, jointly, or elsewhere | `Grounding.cell_key`, `concept.identity.canonical_key`; join resolution; `composite_key_guard` |
| `axis` | scalar | `time` · `categorical` | a question may **group or filter** by me | `planner/grounded_columns.axis_columns`, `column_facts.axis` — the fold law's lookup key |
| `aggregate` | map | `{type, unit, canonical}` | a question may **fold** me | `column_facts.measure_type` / `unit`; `planner/plan._check_additivity` |
| `period_binding` | `true` | — | I am **the** reporting date when the relation carries several | `planner/plan` period binding; `Grounding.offering('period_binding')` |
| `extremum` | list | `[min]` · `[max]` · `[min, max]` | my earliest or latest value may be **asked for** — not folded | `planner/plan._OPERATION_NEEDS` → MIN/MAX; `Grounding.offering('extremum')` |

**A map, because one column routinely has several uses.** Measured on contoso5, 2026-10-07: 21 of
112 columns are a join key you also group by. `date_day` on the FX relation is identity *and* a time
axis; `country_code` in `Country` is identity *and* a categorical axis; `order_date` on a sale line
is a time axis *and* the period binding *and* an extremum. A single-valued key would have to pick
one and lose the rest.

The five role names are the `mac.concept.column.roles` vocabulary, closed, generated into
[column_roles.md](column_roles.md). A term may be written bare or fully qualified — `categorical`
and `mac.concept.axis.categorical` are the same term — and contoso5 writes the qualified form.

### `roles.identity` — which column IS the thing

```yaml
customer_key:  {roles: {identity: canonical}}          # dim_customer
store_key:     {roles: {identity: canonical}}          # dim_store
location_code: {roles: {identity: reference}, counts: true}   # dim_store
order_key:     {roles: {identity: composite}}          # v_contoso5_sales_line
line_number:   {roles: {identity: composite}}
```

| term | holds when | consequence |
|---|---|---|
| `canonical` | this column **alone** identifies an instance | it is what `COUNT(DISTINCT …)` counts and what an answer discloses that it counted; `concept.identity.canonical_key` is filled from it, and at most one per concept, per source spelling |
| `composite` | this column **with its siblings** identifies an instance | the set of columns carrying it **is** the key, in declaration order, and that order reaches the SQL; none of them identifies anything alone, and using one as if it did returns a set where a row was expected — which looks like an answer |
| `reference` | this column identifies an instance **in another concept** | it is a join target and never part of this concept's grain; whether every value is present over there is a measurement, and a reference with no parent relation in the delivery is recorded AS dangling |

**The key is read off the columns.** `Grounding.cell_key` is the `canonical` column, or every
`composite` column in declaration order. A source where no column carries either — and that declares
no legacy `key:` list — is a LOAD ERROR naming both ways to fix it. Measured across the estate before
the derivation shipped: 38 sources declare `key:`, and in 38 of 38 it equals exactly what the columns
declare, order included for all 10 composite keys.

**This is the only home for identity**, and it is per column **and per concept**: `country_code` is
`identity: canonical` in `Country` and `axis: categorical` in `Customer`. A fact attached to the
column's *name* could not say that. (An author converting a bundle will meet `part` named in a load
error — it is refused by name so the message can say the term is now `composite`.)

The three terms in full, injected from `mac_vocabulary.yaml` by `tools/gen_vocabulary_terms.py`:

<!-- BEGIN GENERATED:vocabulary-terms:concept.column.identity (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> What part a column plays in its concept's identity. THE ONLY HOME — there is no concept-level
identity block.

*`mac.concept.column.identity` · 3 terms · closed — these are all of them*

#### `mac.concept.column.identity.canonical`

THE column that identifies one instance. What `COUNT(DISTINCT …)` counts, and what an answer
discloses that it counted. Exactly one per concept, and a concept that legitimately has none
declares `composite` on every column of its key tuple instead — several composite columns and no
canonical IS the composite — rather than nominating a column that does not identify.

| field | value |
|---|---|
| `constellation` | EXACTLY ONE COLUMN IS THE THING ITSELF AND NAMES RESOLVE TO IT. The case that compels it: a surrogate key every fact points at, with a human-readable code and a name beside it that are both 1:1 with it. All three look alike in a profile; only this says which one the joins and the counts are about.
 |

#### `mac.concept.column.identity.composite`

ONE COLUMN OF A COMPOSITE IDENTITY, which IDENTIFIES NOTHING ALONE. Using it as though it did
returns a set where a row was expected, and looks like an answer. Declared on every column of
the tuple, and that is the whole declaration: no canonical column over a key of two or more IS
the composite, and the concept adds nothing.

| field | value |
|---|---|
| `constellation` | NO SINGLE COLUMN IDENTIFIES A ROW AND TWO OR MORE TOGETHER DO. A sale line is identified by its order and its line number — neither is unique alone, and declaring either as the identity would make the grain a lie. Mark each participating column, and the composite is what the concept is keyed on.
 |

#### `mac.concept.column.identity.reference`

A POINTER AT ANOTHER CONCEPT'S IDENTITY — this concept's row names a row over there. What it
points at is named separately; whether every value is PRESENT in the parent is a measurement,
not a declaration, and a reference with no parent relation in the delivery is recorded AS
dangling rather than dropped or invented.

| field | value |
|---|---|
| `constellation` | THE COLUMN HOLDS ANOTHER CONCEPT'S IDENTITY, NOT THIS ONE'S. A customer key on a sale identifies a customer; the sale is identified by something else entirely. Without this the key reads as part of the sale's own identity, and a count of sales becomes a count of customers.
 |
<!-- END GENERATED:vocabulary-terms:concept.column.identity -->

### `roles.axis` — what a question may group or filter by

| term | what it is | what the fold law does with it | schema |
|---|---|---|---|
| `time` | an ordered temporal axis — day, month, quarter | stocks do not accumulate along it | `mac.concept.axis.time` |
| `categorical` | a non-temporal entity or dimension axis — product, location, customer | flows and stocks are additive along it | `mac.concept.axis.categorical` |

**The kind IS the permission.** A column that declares one may be grouped and filtered by; a column
that declares none is not an axis and the fold law is never consulted on it. Two kinds and no more,
because the law is a grid of `measure_type × axis` and a third kind would leave cells nobody has
ruled on — `.none` was added and withdrawn inside an hour on 2026-10-07 for exactly that reason.

A declared kind must agree with the column's declared TYPE family (temporal → `time`, everything
else → `categorical`), which is measured rather than assumed: 70 of 70 agree on contoso5.

**`axis` is declared, not derived**, and these two concepts are why. Both are keyed on a composite;
only one of them is keyed on columns a question slices by.

| | `UnitsSold` | `ExchangeRate` |
|---|---|---|
| relation | `v_contoso5_sales_line` | `v_contoso5_fx_rate` |
| the key | `order_key` + `line_number` | `date_day` + `from_currency` + `to_currency` |
| each key column carries | `identity: composite` | `identity: composite` |
| **and also** | *nothing* | `axis: time` / `axis: categorical` / `axis: categorical` |
| so a question may | join and count on them | join, count, **and group** by them |
| because | a line number is a position in a basket; *"quantity by line number"* asks nothing | *"the USD→EUR rate on 2025-01-03"* names the row **by** its axes |

Nothing in cardinality, type or reference structure separates those two cases. The `axis` role is the
only thing that says which one you have.

### `roles.aggregate` — the qualifier of a foldable column

```yaml
gross_amount:
  roles:
    aggregate: {type: mac.concept.column.measure_type.flow, unit: USD, canonical: true}
    extremum: [min, max]
unit_price:
  roles:
    aggregate: {type: mac.concept.column.measure_type.intensive, unit: USD}
    extremum: [min, max]
```

| sub-key | card | terms | required | says |
|---|---|---|---|---|
| `type` | scalar | `flow` · `stock` · `intensive` · `precomputed` · `target` | **yes**, within `aggregate` | what kind of quantity this is — the row of the fold law |
| `unit` | string | free — `USD`, `units`, `m2`, `to-currency per from-currency` | **yes**, within `aggregate` | what the number is in; two different units may not be combined |
| `canonical` | bool | `true` | no | **which** aggregate column is *the* one, when a concept carries several |
| `additivity` | map | axis name → a `mac.concept.aggregation_effect` term | no | a per-axis EXCEPTION the type cannot state; it projects to `semantics.additivity`, and an entry that agrees with the type is a second home for the type |

`type` is a `mac.concept.column.measure_type` term, defined once in [measures.md](measures.md) and
never restated per concept. `unit` is what unit algebra reads: a sum over two units refuses, and a
ratio names the unit of its result.

**PER COLUMN, not per concept, and `canonical` is why that works.** `GrossRevenue` grounds
`gross_amount` (`flow`, USD) and `unit_price` (`intensive`, USD) on one relation. A single statement
for the whole concept could only misreport one of them, and did: `SUM(unit_price) AS grossrevenue`
planned and was permitted. `canonical: true` on `gross_amount` says which number a question about the
concept itself folds, and with it the unit of that answer. Where several carriers agree on a unit the
concept need state nothing; where they disagree and none is `canonical`, the load refuses rather than
let YAML key order decide an answer's unit.

### `roles.period_binding` — which date a period binds to

```yaml
order_date:    {roles: {axis: mac.concept.axis.time, period_binding: true, extremum: [min, max]}}
delivery_date: {roles: {axis: mac.concept.axis.time, extremum: [min, max]}}
```

A sale line carries both dates and both are real time axes. `period_binding` says which one *"sales
in March"* means; a bare flag, because this use has no parameter. On a relation with exactly one date
it is still worth writing: the relation that grows a second date later does not then change the
meaning of every period question already asked of it.

### `roles.extremum` — a value that may be asked for, not folded

```yaml
close_date:    {roles: {axis: mac.concept.axis.time, extremum: [min, max]}}
square_metres: {roles: {aggregate: {type: mac.concept.column.measure_type.stock, unit: m2}, extremum: [min, max]}}
```

An extremum **picks one value that exists in the data** instead of combining several, which is why it
is its own role and not a corner of `aggregate`: it answers to no additivity cell and is meaningful on
a column no law would let anyone SUM. A list over `min` and `max`, at least one entry, no repeats.
*"When was the first store closed?"* is `SELECT MIN(dim_store.close_date)`. Where several columns of a
concept admit an extremum and the question names none, the planner ASKS which — and
`Grounding.offering('extremum')` is the population it names back.

---

## The fold law — `aggregate.type` × `axis`

This is why `axis` carries a term and not a boolean. The law is stated over **kinds**, never over
column names, which is what makes it universal: `mac.concept.column.measure_type` ×
`mac.concept.axis` → `mac.concept.aggregation_effect`, read through
`framework.vocabulary().additivity`.

| `aggregate.type` | across a `time` axis | across a `categorical` axis |
|---|---|---|
| `flow` | **additive** | **additive** |
| `stock` | `none` — does not accumulate | **additive** |
| `intensive` | `average` | `average` |
| `precomputed` | `none` | `none` |
| `target` | `none` | `none` |

A fold the law does not permit is refused as `ADDITIVITY_VIOLATION`, naming the axis it crossed. A
column with no `axis` role is never consulted: there is no axis to cross. A column whose every cell
is `none` — `precomputed`, `target` — is foldable by nothing, and that is the measure type's ruling
rather than a fact about the column.

Ten cells, derived from two declared terms, so a column that restated one of them would be a second
home for the law and the home that disagreed would win silently. `aggregate.additivity` is the one
exception and exists only for it: a NAMED axis where the type is wrong in general, such as a balance
that sums across stores and not across days.

---

## `counts` — when a count of the concept is not a count of its rows

A concept's key identifies a **row**. What a **count** counts is sometimes a different column.

| | `Store.store_key` | `Store.location_code` |
|---|---|---|
| roles | `identity: canonical` | `identity: reference` |
| `counts` | — | `true` |
| rows | 74 — one per trading period | — |
| a count of *stores* | would say 74, wrongly | says **67** |

`counts` is how a concept says *"a count of me is not a count of my rows"*. `identity: canonical`
stays what the fact JOINS on; `counts` is what a count DISTINCTs, it fills
`concept.identity.counts_as`, and the answer discloses which column it counted. It is a key of its own
rather than a fourth `identity` term because the column that counts is routinely also the one that
references: contoso5's `location_code` carries both at once, and a single slot could hold only one.

---

## `register` — where this column's values come from

```yaml
country_code:                                  # dim_country
  roles: {identity: canonical}
  register: data/lookups/contoso5_country_code.lookup.yaml
brand:                                         # dim_product
  roles: {identity: canonical, axis: mac.concept.axis.categorical, extremum: [min, max]}
  register: data/lookups/contoso5_brand.lookup.yaml
```

One register per value set, and the column points at it. The register's rows **are** the values; the
column never restates them. Two columns carrying the same value set point at the same register — the
register's identity is the value set, not the column that uses it.

A register exists so a typed word can reach a stored code without probing the warehouse. The
resolution ladder that walks it — exact, then near miss, then ask with candidates — is the resolver's,
not the column's.

### Three keys spelled `register`

| key | value | says |
|---|---|---|
| `register` on the column | a bundle-relative path | where this column's VALUES come from — the register a name resolves through |
| `rulings.register` | a `mac.name_register` term | **which of the thing's names** this column carries; legal only beside `label_of` |
| `domain.register` | a bundle-relative path | the designed `domain` block's name for the first of these; not a key a column may carry today |

### When a value set is a calendar, not a register

`March`, `Mon`, `2024-Q3` and `2024-03-01` are recognised by a built-in reader, so no lookup is cut
for them, none is carried into a bundle, and none is monitored. A column whose values are one of these
forms is a calendar, and declaring a register for it would create a second home for the Gregorian
calendar.

<!-- BEGIN GENERATED:vocabulary-terms:calendar_vocabulary (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> The words and literal forms of the Gregorian calendar. A column whose value set is one of these
is a calendar, not a register: the built-in reader recognises it and no lookup is cut, carried
or monitored for it.

*`mac.calendar_vocabulary` · 9 terms · closed — these are all of them*

#### `mac.calendar_vocabulary.month_name`

The twelve month names in full.

| field | value |
|---|---|
| `members` | January, February, March, April, May, June, July, August, September, October, November, December |

#### `mac.calendar_vocabulary.month_short`

The three-letter month abbreviations. `Sept` is admitted beside `Sep` because deliveries write
both.

| field | value |
|---|---|
| `members` | Jan, Feb, Mar, Apr, May, Jun, Jul, Aug, Sep, Sept, Oct, Nov, Dec |

#### `mac.calendar_vocabulary.weekday_name`

The seven weekday names in full.

| field | value |
|---|---|
| `members` | Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday |

#### `mac.calendar_vocabulary.weekday_short`

The three-letter weekday abbreviations.

| field | value |
|---|---|
| `members` | Mon, Tue, Tues, Wed, Thu, Thur, Thurs, Fri, Sat, Sun |

#### `mac.calendar_vocabulary.quarter_label`

A quarter of a year, unqualified by which year.

| field | value |
|---|---|
| `members` | Q1, Q2, Q3, Q4 |

#### `mac.calendar_vocabulary.iso_date`

A day. `2020-12-31`, with an optional time this estate's served dates do not carry (every date
column measured on the worked bundle is midnight).

| field | value |
|---|---|
| `shape` | YYYY-MM-DD |

#### `mac.calendar_vocabulary.year`

A year as four digits. Half-open over twelve months when compared.

| field | value |
|---|---|
| `shape` | YYYY |

#### `mac.calendar_vocabulary.year_month`

A month of a named year. `2024-03`, `March 2024`, `Mar 2024`.

| field | value |
|---|---|
| `shape` | YYYY-MM |

#### `mac.calendar_vocabulary.year_quarter`

A quarter of a named year. `Q1 2024`, `2024-Q1`.

| field | value |
|---|---|
| `shape` | Qn YYYY |
<!-- END GENERATED:vocabulary-terms:calendar_vocabulary -->

---

## What the column HOLDS — its type family

`roles` says what a question may do with a column; the type family says what a comparison against it
may mean. A threshold of `630.5` against an integer key and a boolean against a numeric both refuse at
the same gate, and they refuse by FAMILY rather than by warehouse spelling — the spellings are a
bundle's descriptor data and differ per warehouse, so the families are closed here and the spellings
are normalised before matching (the text before `(` or `<`).

The family is **measured**, from the relation's descriptor. It is never declared on the column — and
it is what `roles.axis` is measured against: temporal → `time`, everything else → `categorical`, with
70 of 70 agreeing on contoso5. A measurement, and the obvious next gate; not one today.

<!-- BEGIN GENERATED:vocabulary-terms:column_type (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> The family of value a column holds, with the warehouse spellings that mean it. Closed over
FAMILIES; open over spellings, which a bundle's descriptors supply and which are normalised
before matching (the text before `(` or `<`).

*`mac.column_type` · 5 terms · closed — these are all of them*

#### `mac.column_type.text`

Characters. A NAME, a code, a label -- something read rather than measured.

| field | value |
|---|---|
| `spellings` | string, varchar, char, text, nvarchar, uuid |

#### `mac.column_type.number`

A magnitude. Something that can be larger or smaller than another of its kind.

| field | value |
|---|---|
| `spellings` | integer, int, bigint, smallint, tinyint, decimal, numeric, double, float, real |

#### `mac.column_type.temporal`

A point in time. The only family a date literal may be compared against.

| field | value |
|---|---|
| `spellings` | date, timestamp, datetime, timestamptz, time |

#### `mac.column_type.boolean`

True or false. Two members, so it is never a magnitude and never a name.

| field | value |
|---|---|
| `spellings` | boolean, bool |

#### `mac.column_type.collection`

Several values in one cell. Never an axis and never an ordering key: GROUP BY over a collection
groups by the container, which is not a member of anything a question asked about.

| field | value |
|---|---|
| `spellings` | array, map, struct, row, json |
<!-- END GENERATED:vocabulary-terms:column_type -->

---

## `rulings` — what a person decided about a column

A ruling is a judgement measurement cannot establish. All seven are optional; a column with no rulings
behaves as its `roles` alone dictate. Each says how this column relates to **another column**, or what
a person decided about it — which is why a ruling is not a role, and why the block is nested: `roles`
describes the data, `rulings` rules on it, and a slot that accepted both would silt up until nobody
could tell which kind a value is.

| ruling | value | required | says | the measurement that gets you to the door | read by |
|---|---|---|---|---|---|
| `label_of` | a column of the same source map | — | I am **another name for that column's thing**, not another thing — group on it, display me | `a = b = pairs` (1:1) | `planner/sql.py`: the label is SELECTed and the named column grouped on |
| `register` | `common` · `legal` · `long` · `short` · `code` | **with `label_of`** | **which** of that thing's names I carry | — only a person can say | `planner/sql.py`, named in the disclosure *("legal register")* |
| `finer_than` | a column of the same source map | — | I distinguish **more members** than that column and roll up into it; both stay legitimate axes and an answer must **disclose which level it used** | `pairs = finer_distinct` — a clean N:1 | `planner/sql.py`, the level disclosure |
| `scoped_by` | a column of the same source map | — | my values are unique **only within** that column, so I may not be grouped or filtered alone — the scope must travel with me | 0 collisions within the parent, many across it | it synthesises a `composite_key_guard` binding, read by `planner/contract_guards.py` |
| `sort` | `asc` · `desc` · `none` | — | the order my values are presented in when the question states none | **none — and that is the point:** SQL guarantees no row order without `ORDER BY` | `planner/sql.py` `column_sort` → the ORDER BY this column contributes |
| `never_axis` | the measurement, in prose | — | **I am a real axis and a person has ruled that no question may group by me** | the sentence IS the measurement | `planner/plan.py` `_axis_denied` → `POLICY_DENIED` quoting it; `planner/grounded_columns.py` and `interpret/vocabulary.py` never OFFER the column as an axis |
| `evidence` | a DQ register id | **with `never_axis`** | which finding this ruling rests on — an argument to a ruling, not a ruling of its own | — | the refusal, which cites it so a reader can go and read the finding |

```yaml
country_name:  {roles: {axis: mac.concept.axis.categorical}, rulings: {label_of: country_code, register: long}}
state:         {roles: {axis: mac.concept.axis.categorical}, rulings: {scoped_by: country_code}}
country_code:  {roles: {axis: mac.concept.axis.categorical}, rulings: {finer_than: continent}}
city:          {roles: {axis: mac.concept.axis.categorical},
                rulings: {never_axis: privacy, evidence: DQ-IDENTIFYING-DIM_CUSTOMER-CITY}}
```

### What the load refuses

| the shape | what happens | why |
|---|---|---|
| `never_axis` without `evidence` | LOAD ERROR — schema `dependentRequired` and the `ColumnRulings` validator both refuse it | a prohibition without a measurement is a preference, and the refusal would have nothing to cite |
| `register` without `label_of` | LOAD ERROR, same two readers | it says WHICH of the thing's names this column is, so it needs the thing |
| `label_of`, `finer_than` or `scoped_by` naming a column that is not in this source's map | LOAD ERROR naming the target | a ruling relates two DECLARED columns; it never assumes one exists |
| a ruling spelled wrong | LOAD ERROR — `extra="forbid"` | a flag the runtime does not read must fail the bundle, which is the only way a reader can tell it is unread |

### `finer_than` and `scoped_by` look alike and are opposite

Both pair a column with a coarser one, and cardinality alone cannot tell them apart. Measure the pairs
before ruling; mistaking the second for the first is the expensive error, because it merges unrelated
members and nothing in the result betrays it.

| | `finer_than` | `scoped_by` |
|---|---|---|
| the relationship | a clean N:1 — every child has exactly one parent | one code space reused per parent |
| the test | `pairs = finer_distinct`; higher, and a child has two parents and the roll-up double-counts | 0 collisions within the parent, many across it |
| contoso5 | `Customer.country_code finer_than continent`; `ProductCategory.sub_category_name finer_than category_name` — 32 sub-categories over 8 categories | `Customer.state scoped_by country_code` |
| what a question gets | both levels stay legal; the answer discloses which it used, and an ambiguous question is offered both | the scope column is added, or the engine ASKS which parent was meant |
| what the mistake costs | a disclosure nobody made | one row labelled `CO` merging three unrelated regions — Corse, Como and Colorado, measured in [column_rulings.md](column_rulings.md) §3 — with a plausible row count and a meaningless number |

### `sort` is per column, never per concept

One breakdown legitimately wants `brand asc`, `country_code asc` and `net_amount desc` at once, which
no concept-level flag can express. `asc` is alphanumeric and is the reading for a NAME; `desc` is
largest-first, the reading for a MAGNITUDE; `none` means never an ordering key. A column declaring
nothing falls to `query_grammar.yaml#projection.default_ordering`, which reads the column's declared
type family, and `Intent.ordering` — the reader's own words — outranks both.

It is the one ruling with no measurement that could establish it, and that is the point rather than a
gap: SQL guarantees no row order without `ORDER BY`, so nothing in the data can say what order a
reader expects. Measured 2026-10-02 on an 88-row breakdown: the grader compared the approved rows
against the capture's first 50, which 50 depended on unordered output, and the question passed and
failed on alternate runs with the data unchanged.

---

## A prohibition does not change what the column IS

A column declares what it **is**. What may not be done with it is ruled separately — and the two must
stay apart, because a column that lied about the warehouse to express a policy would make every other
reader of the declaration wrong.

`city` and `customer_name` on contoso5's customer dimension are the case. They are categorical axes by
every test, and they are also identifiers wearing a dimension's clothes.

| | where it is stated | what it carries |
|---|---|---|
| what the column IS | `roles: {axis: mac.concept.axis.categorical, extremum: [min, max]}` | the truth about the data, so joins, resolution, the extremum route and the fold law all read it correctly |
| that no question may group by it | `rulings: {never_axis: privacy}` on the same column | a refusal: the column is never OFFERED as an axis, and a question that names it anyway gets `POLICY_DENIED` |
| the measurement | `rulings: {evidence: DQ-IDENTIFYING-DIM_CUSTOMER-CITY}` | the id of the finding, raised from `data/profiles/<relation>.yaml` `singletons`, which the refusal quotes back |

The reader meets a refusal that teaches instead of a column that lies. Where the prohibition is
cross-column — *"never report nine countries"* — it is a concept rule with `never`, `why` and
`binds`; the shape, its six kinds and the `never` → refusal path are in
[identity_and_rules.md](rules_and_canons/identity_and_rules.md).

---

## Worked: `Customer`, all 10 columns

One source, one canonical identity, seven axes, four of them ruled on, two columns offered to no
question.

```yaml
grounding:
  sources:
    - relation: dim_customer
      columns:
        customer_key:  {roles: {identity: canonical}}
        customer_name: {roles: {axis: mac.concept.axis.categorical, extremum: [min, max]},
                        rulings: {never_axis: privacy, evidence: DQ-IDENTIFYING-DIM_CUSTOMER-CUSTOMER_NAME}}
        continent:     {roles: {axis: mac.concept.axis.categorical, extremum: [min, max]}}
        country_code:  {roles: {axis: mac.concept.axis.categorical, extremum: [min, max]},
                        rulings: {finer_than: continent}}
        state:         {roles: {axis: mac.concept.axis.categorical, extremum: [min, max]},
                        rulings: {scoped_by: country_code}}
        city:          {roles: {axis: mac.concept.axis.categorical, extremum: [min, max]},
                        rulings: {never_axis: privacy, evidence: DQ-IDENTIFYING-DIM_CUSTOMER-CITY}}
        gender:        {roles: {axis: mac.concept.axis.categorical, extremum: [min, max]}}
        birth_date:    {roles: {axis: mac.concept.axis.time, extremum: [min, max]}}
        valid_from:    {roles: {}}
        valid_to:      {roles: {}}
```

| the choice | what is written | why |
|---|---|---|
| `country_code` here is **not** identity | `axis` alone, plus `finer_than` | it is the identity of the `Country` concept, not of `Customer` — the same column, a different part in two concepts |
| `valid_from`, `valid_to` | `roles: {}` | SCD-2 row-validity stamps: when the ROW was written, not when anything happened. No question is offered them, and saying so is a declaration |
| `state` | `scoped_by: country_code` | its codes are reused across countries, so a group by `state` alone merges two places |
| `city`, `customer_name` | `axis`, **and** `never_axis` with its evidence | they *are* axes; that no question may group by one is a ruling, and it carries the measurement |
| every axis also carries `extremum` | `extremum: [min, max]` | *"the earliest birth date"* is a pick, not a fold, and a categorical axis admits it too |

## Worked: one column, three parts in three concepts

`country_code` is declared in `Country`, `Customer` and `Location`, and it means something different
in each. Nothing attached to the column's name could say that.

| concept | relation | `roles` | `rulings` |
|---|---|---|---|
| `Country` | `dim_country` | `identity: canonical`, plus `register: data/lookups/contoso5_country_code.lookup.yaml` | — |
| `Customer` | `dim_customer` | `axis: categorical`, `extremum: [min, max]` | `finer_than: continent` |
| `Location` | `dim_location` | `axis: categorical`, `extremum: [min, max]` | — (and `country_name` beside it is its `label_of`) |

**`identity` and `axis` on one column is what the map is for.** `Brand.brand` carries
`identity: canonical`, `axis: categorical` and `extremum: [min, max]` at once: a brand *is* the thing
the concept is about, it is also what a question slices by, and its earliest and latest value may be
asked for. `UnitsSold.order_key` is the opposite corner — `identity: composite` and no `axis`,
identity without groupability. One key with one value could express neither.

---

## Why there is no free-text key

**A free-text key on a column is where rulings go to hide.** Measured on contoso 2026-09-25:
`grounding.note` carried ruling language — *never*, *must not*, *display-only*, *because* — in **12 of
21 concepts**. The clearest was a 1 044-character note reading:

> *"`ZipCode` and `City` are display-only, never filter or group — because DQ-CUSTOMER-02 measured
> that ZipCode alone singles out 29 193 of 104 990 served rows."*

A measured privacy ruling, stated in prose, in a field nothing reads — while the runtime happily
planned `GROUP BY ZipCode`. It is now `rulings: {never_axis: privacy, evidence: …}`, and the refusal
reaches the person who asked.

**So the column block has no free-text key.** Every value on a column is a closed term, a column name,
a path, a unit, a boolean or — for `never_axis` alone — the measurement itself, which is quoted into a
refusal and therefore reaches a reader. If you want to write something about a column:

| what you want to say | where it goes |
|---|---|
| it changes what the engine does | a **declaration** — find the key, or the key is missing and *that* is the finding |
| the reader of a REFUSAL must know it | `rulings.never_axis` with its `evidence`, or a concept rule's `never` and `why` |
| why a ruling was made | the measurement's id — `DQ-…`, raised from a profile, not a paragraph |
| it is unresolved | the SME ledger outside `ontology/` — with an id, an owner and a status |
| it is about the concept, not this column | `concept.definition`, or the account in `knowledge/<concept>.md` |

---

## What stays at concept level

| key | why it cannot descend |
|---|---|
| `concept.definition`, `concept.class` | about the concept |
| `grounding.sources[].relation` | the binding itself |
| `grounding.snapshot_rule`, `grounding.realized_by` | how the whole relation collapses before anything is summed |
| `edges` | between **concepts** |
| `contract.default_reading` | what an unqualified **word** means |
| `contract.rules[].when` / `then` / `never` / `why` | a rule's **prose** is usually cross-column; `binds` names the columns it governs |
| `semantics.unit` | the COMPOSED unit, where several carriers disagree and none is `canonical` |

**But a rule's params are not prose.** A column name, a register path, a sort direction are mechanics
about one column and they descend onto it. **Prose stays, params descend** — that split is what stops
`columns:` becoming a second dumping ground.

**And the grain does not live at concept level either.** `concept.identity` holds two COLUMN NAMES,
both filled from the column map: `canonical_key` from `identity: canonical` and `counts_as` from
`counts: true`. A prose line restating what one row is would be a second home for a fact the
declaration already states, and the one that disagrees is the one nothing checks.

---

## What is never declared here

These are **measured**. Declaring them would create a second home for a fact the warehouse states.

| fact | where it comes from |
|---|---|
| type family, storage role, key position | `data/datasets/<relation>.yaml` |
| distinct, nulls, min, max, singletons, functional determination | `data/profiles/<relation>.yaml` |
| observed landing values | `data/sources/<relation>.yaml` |
| the members themselves | `data/lookups/<name>.lookup.yaml` |
| whether a `reference`'s values are all present in the parent | the dangling-key measurement over the delivery |
| the five scalar role names — key, dimension, measure, period, housekeeping | `ColumnSpec.role`, derived from `roles` in the vocabulary's own precedence; it reproduces all 112 of contoso5's columns exactly |

A declaration says what a thing IS and what may be done with it. It never restates what counting would
tell you.

---

## Every key — the complete surface

Thirty-three keys, each with its effect — which plane it lands on, which `mac.outcome_class` terms
it can produce, and what reads it — declared in
[column_effects.yaml](column_effects.yaml) and rendered interactively by `column_bench.html`. The
container key `rulings` and the sub-keys of `aggregate` have their sections above. `storage_role` is
the one key nothing authors: the data plane measures it, so it is declared there and not here.

| key | required | default | legal values | decides |
|---|---|---|---|---|
| `roles` | **yes** | — | a map over `mac.concept.column.roles` — identity · axis · aggregate · period_binding · extremum | what a question may do with this column at all; `{}` means *offered to no question* |
| `roles.identity` | iff claimed | — | `mac.concept.column.identity` — canonical · composite · reference | what part this column plays in the concept's identity — and, over a set of columns, the key |
| `roles.axis` | iff claimed | — | `mac.concept.axis.time` · `mac.concept.axis.categorical` | which KIND of axis this column is, which is both the permission to group and the fold law's lookup key |
| `roles.aggregate` | iff claimed | — | a map over `type` · `unit` · `canonical` · `additivity` | that a question may fold this column, and on what terms |
| `roles.period_binding` | iff claimed | — | `true` | which date a question's period binds to, when the relation carries several |
| `roles.extremum` | iff claimed | — | a list over `min` · `max` — at least one, no repeats | that the earliest or latest value may be asked for — a pick, never a fold |
| `counts` | no | `false` | `true` | which column one INSTANCE is counted by, when the relation is served finer than the thing |
| `references` | never — not a column flag; a load error | — | a concept name | which concept a `reference` points at; the edge that realizes the join names it today |
| `domain.closure` | never — not a column flag; a load error | open | `closed` · `open` | whether the register states every member, so a word outside it is answerable without a probe |
| `domain.complete_for` | never — not a column flag; a load error | — | `data` · `world` | whether a word that misses answers zero-disclosed or refuses as not a member of the kind |
| `domain.warranty` | never — not a column flag; a load error | — | `derived` · `monitored` | how a closed set is kept true: a rule makes the members, or a scheduled check reconciles them |
| `domain.register` | never — not a column flag; a load error | — | a bundle-relative path | which register's rows ARE the members; the live spelling of this fact is the top-level `register` |
| `domain.members` | never — not a column flag; a load error | — | an inline list of members | the inline form, for a domain too small for a file — fifteen age bands, not five hundred countries |
| `resolution.search` | never — not a column flag; a load error | — | register columns, in order | which columns of the register a typed word is compared to, and in what order |
| `resolution.display` | never — not a column flag; a load error | — | a register column | which column an answer PRINTS when the group is on the code |
| `resolution.strategy` | never — not a column flag; a load error | the whole ladder | an ordered list over `exact` · `normalized` · `prefix` · `fuzzy` · `ask` | which rungs of the resolution ladder this column admits |
| `resolution.fuzzy_floor` | never — not a column flag; a load error | — | a similarity between 0 and 1 | below which a candidate is not worth offering |
| `resolution.on_miss` | never — DERIVED, not authored | — | `ask` · `zero, disclosed` · `refuse` | what a word matching nothing produces; read off `closure` and `complete_for`, never set |
| `resolution.candidates` | never — not a column flag; a load error | show | `show` · `suppress` | whether an ASK may list the members, or listing them would itself leak something |
| `placement.fact_join` | never — not a column flag; a load error | — | a column of the fact | that a predicate lands on the fact and the dimension is never joined |
| `register` | no | — | a bundle-relative lookup path | where this column's values come from, so a word resolves to the exact value it holds instead of probing for a match |
| `roles.aggregate.additivity` | no | the fold law | `{<axis>: mac.concept.aggregation_effect.<term>}` | the effect of folding along ONE named axis, overriding the law — authoring it means authoring both premise and conclusion, so leave it unwritten |
| `rulings.scoped_by` | no | — | a column of the same source map | that the scope column must travel with this one, which is unique only within it — synthesising a `composite_key_guard` binding |
| `absence.nulls` | never — not a column flag; a load error | — | a reading of NULL, per column | what a NULL in THIS column means — *"no status event recorded, so NOT operating"* against *"not applicable"* |
| `absence.sentinels` | never — not a column flag; a load error | — | stored values that are not members | the `--` that is not a country, per column and per source |
| `rulings.label_of` | no | — | a column of the same source map | that this column NAMES that one; group there, display here |
| `rulings.register` | **with `label_of`** — schema `dependentRequired` | — | `mac.name_register` — common · legal · long · short · code | which of the thing's names this column carries, so an answer can say which it showed |
| `rulings.finer_than` | no | — | a column of the same source map | that this column rolls up into that one, and that an answer discloses which level it used |
| `rulings.sort` | no | — | `asc` · `desc` · `none` | the order this column's values are presented in when the question states none |
| `rulings.never_axis` | no | — | the measurement, in prose | that no question may group by this column — the sentence the refusal quotes |
| `rulings.evidence` | **with `never_axis`** — schema `dependentRequired` | — | a DQ register id | which measurement the ruling rests on, so the refusal cites rather than asserts |
| `disclose` | never — not a column flag; a load error | — | one line of prose | one sentence every answer touching this column must carry |
| `discriminates` | never — not a column flag; a load error | — | a concept or value name | that this column says WHICH KIND of row a tall relation holds |

---

## Rules this model holds

1. **One fact, one key.** No column states the same thing twice, and no key restates what another
   declares — not the grain, not the additivity law, not the member list.
2. **Claim a role, state its terms.** The qualifier *is* the value, so a role cannot be claimed
   without it. The requirement is structural, not a gate.
3. **A declaration describes the data; a prohibition is ruled.** A column that *is* an axis says so
   even when policy forbids grouping by it; the prohibition, its reason and its evidence live in
   `rulings` — or, when they span columns, in a rule — and the refusal cites the measurement.
   Declaring a real axis "not an axis" would make the ontology lie about the warehouse.
4. **Absence is never load-bearing except where it is declared to be.** `roles: {}` means *offered to
   nothing*; a missing `roles` means *unclassified*. The two are different findings.
5. **A key arrives with its reader.** A declaration nothing consumes is the defect this model exists
   to end, so the surface grows one key at a time, each with the code that acts on it and the test
   that measures it. The first draft of this block carried 19 flags and
   `test_every_declared_field_is_consumed_or_waived` failed on all 19.

---

## What a column does not yet say

The limits are declared, because an undeclared limit is found by a reader who needed it. Each row is a
fact a column cannot state today, the key the effects registry reserves for it, and where the model
answers that question instead.

| the fact | reserved key | where it is answered today |
|---|---|---|
| which concept a `reference` points at | `references` | the edge that realizes the join — nothing on the column names the target |
| whether a register states every member, and complete for which world | `domain.closure`, `domain.complete_for` | the [explicit_closure](patterns/open_vs_closed_world/explicit_closure.md) pattern, realized by the `enum_from_register` canon, plus `values.closure` on the concept |
| how a closed set is kept true | `domain.warranty` | nothing — a closed set nobody watches is a refusal backed by a stale sample |
| which register columns a word is matched and printed from | `resolution.search`, `resolution.display`, `resolution.strategy`, `resolution.fuzzy_floor`, `resolution.candidates` | the resolver's own ladder, the same for every column with a register |
| what a NULL means **in this column** | `absence.nulls` | the [absence_semantics](patterns/open_vs_closed_world/absence_semantics.md) pattern, realized by `densify` |
| a non-null value that is not a member | `absence.sentinels` | an exclusion rule on the concept — contoso5's `country_code != '--'` |
| that a predicate may land on the fact and skip the dimension join | `placement.fact_join` | nothing; the plan walks the join |
| one line every answer touching the column must carry | `disclose` | nothing: a refusal reaches a reader and a successful answer does not |
| which column selects what KIND of row this is | `discriminates` | `values.aliases.map` on the concept, read as `variant_codes` |
| the role a reference plays when two point at the same concept | — | nothing — [role_playing_dimension](patterns/dimensional_special_cases/role_playing_dimension.md) at the column level |
| a measure type that varies per ROW | — | nothing: `aggregate.type` is one type per column. Split the concept per measure type, or read the type from a column and accept that the fold rule is not knowable until a row is read |

### The closure question needs two bits, not one

Whether a list is complete and whether it is complete *for the world* are two different facts, and
together they decide what a word that matches nothing produces:

| the list is | complete for | a word that matches nothing |
|---|---|---|
| open | — | **ask**, with candidates |
| closed | the delivery | **zero, disclosed** — a real word, no rows |
| closed | the kind | **refuse** — not a member of the kind |

`Country` and `Gender` are the same closure with opposite answers. The eight countries are the ones
*delivered*, so *"sales in Japan"* answers zero; the two genders *are* the kind, so a third word is
not a gender here and refuses. Without the second bit, *"sales in Asia"* and *"gender Q"* get the same
answer, and only one of them deserves it. Unstated must mean **open**: a list nobody promised was
complete would otherwise refuse real values.

And a closed list carries an obligation. Either a rule produces the members — a `CASE` expression in a
transform cannot grow a sixteenth age band — or they were observed and a scheduled check reconciles
them. There is no third option.
