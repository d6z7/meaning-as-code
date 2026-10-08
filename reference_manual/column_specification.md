---
title: The column specification — everything about a column, on the column
status: >-
  CURRENT (2026-10-08, revision 6). The long form of column_declaration.md: every key, its
  cardinality, its terms, and who reads it. A column has FOUR top-level keys — `offers` (required),
  `references`, `value_register`, `rulings` — and `mac.schema.json` admits only those four
  (`additionalProperties: false`), as does mac-runtime's `ColumnSpec` (`extra="forbid"`), so a fifth
  is a load error rather than a line nothing reads. `offers` is a map from each USE a question may
  make of the column to that use's own terms; the five scalar role names are DERIVED by
  `ColumnSpec.role` and never authored. Every planner step asks `Grounding.offers(column, use)`,
  which reads this map. RELATION-OWNED SINCE REVISION 6 (operator ruling 2026-10-08, option A): the body below is
  unchanged to the last term, and it now lives in `ontology/relations/<relation>.yaml` keyed by
  column, with a concept naming the relation and the columns of it it serves under
  `grounding.bindings[]`. `$defs.columnDeclaration` is the one home both planes $ref. The inline
  `source:` form still loads. TWO FACTS ARE THE SOURCE'S AND NOT ANY COLUMN'S: what makes one row unique
  (`source.key`, an ordered list) and what a count of the concept counts (`source.counts`, a column
  name). TERMS ARE BARE — `axis: categorical`, `aggregate.type: flow` — closed enums the schema
  validates by name. contoso5 is authored entirely in this shape and every example on this page is a
  column of that bundle. column_declaration.md carries the same model on one screen.
audience: ontology authors, importer developers, framework developers
companions:
  - column_declaration.md     # the same model on one screen — the overview this page is the long form of
  - column_roles.md           # the five uses in detail, generated from the vocabulary
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
column. Two facts are *about the source and not about any one column* — what makes one row unique,
and what a count of the concept counts — and those are
[`key`](#key--what-makes-one-row-unique) and [`counts`](#counts--when-a-count-of-the-concept-is-not-a-count-of-its-rows).
[column_declaration.md](column_declaration.md) states the same model on one screen.

## The principle

> **A fact about one column is declared on that column.**
> A fact about the concept, or spanning several columns, stays at concept level.

Nothing else. Every rule below follows from it.

---

## The shape

The one block on this page that is a SHAPE and not an example: `a | b` means *one of these*, `<…>`
means *your value*. Every other fenced block below is a column of contoso5 and is authorable exactly
as it stands — terms are bare, and the schema validates each one by name.

```yaml
grounding:
  source:                                       # SINGULAR — one concept, one relation
    relation: <relation>
    key: <column> | [<column>, <column>, …]     # REQUIRED — ordered; the source's, not a column's
    counts: <column>                            # optional — what a count of the concept DISTINCTs
    columns:

      <column-name>:
        offers:                                 # REQUIRED — `{}` is legal
          axis: time | categorical
          suppressed: <DQ register id>          # REQUIRES axis
          aggregate:
            type: flow | stock | intensive | precomputed | target
            unit: <string>
            default: true
            additivity: {<axis>: <effect>}
          period_binding: true
          extremum: [min, max]
        references: <ConceptName>
        value_register: <bundle-relative path>
        rulings:
          label_of: <column>
          naming: common | legal | long | short | code
          finer_than: <column>
          scoped_by: <column>
          sort: asc | desc | none
```

No column carries all of that. Most carry one or two uses and nothing else, and contoso5's
`Customer` is typical: 10 columns — a one-column key, seven axes, four of them ruled on or
suppressed, and three offered to no question.

```yaml
source:
  relation: dim_customer
  key: customer_key
  columns:
    customer_key: {offers: {}}
    gender:       {offers: {axis: categorical, extremum: [min, max]}}
```

`source` is **singular**. A concept binds one relation; many concepts bind one relation — contoso5
grounds `Product`, `Brand`, `Color` and `ProductCategory` on `dim_product`, each with its own key.
`sources:` as a list is a **load error** (`mac.schema.json` gives it `not: {}`): it was never
honoured, because `Grounding` carries no `sources` field, `_primary_source` took the first entry and
a second was silently dropped. A notion genuinely over two relations is a transform view, or two
concepts and an edge.

### Why a column nests under its source

A column name only means anything within a relation, and `country_code` is the proof: contoso5 carries
it on `dim_country`, `dim_customer`, `dim_location` and `dim_store`, and it plays a different part on
each. A block keyed on a bare column name could not say which one it meant.

| level | what it holds | why it cannot move |
|---|---|---|
| `grounding.source` | one relation, its `key`, what a count of it counts, and that relation's columns | the grain and the count are facts about the RELATION this concept reads, and they have an order and a column name as their values |
| `source.columns` | a map from column name to that column's four keys | the facts are per column AND per relation; a name alone is ambiguous |
| `source.columns.<col>.offers` | the uses a question may make of this column | per column AND per CONCEPT — `country_code` is the key of `Country` and a categorical axis of `Customer` |

A bundle may still write `columns:` as a flat list of names. That form says which columns a concept
serves and nothing about what each one IS, `check_column_spec` reports it, and `Grounding.offers`
falls back to the derived role for it.

---

## `key` — what makes one row unique

The first of the two facts about a source that are not facts about any one of its columns.

```yaml
source:
  relation: v_contoso5_sales_line
  key: [order_key, line_number]              # ordered; the composite
  columns:
    order_key:    {offers: {}}               # a key column claims nothing of its own
    line_number:  {offers: {}}
    customer_key: {offers: {axis: categorical}, references: Customer}
```

```yaml
source:
  relation: dim_store
  key: store_key                             # one column: a bare string is legal
  counts: location_code
  columns:
    store_key:     {offers: {}}
    location_code: {offers: {}, references: Location}
```

| | |
|---|---|
| where | on the **source**, beside `relation` |
| card | a string, or an ordered list of column names |
| required | **yes** — `mac.schema.json` gives `source` `required: ["relation", "key"]` |
| order | **load-bearing** — it becomes `Grounding.cell_key` and reaches the SQL |
| read by | `cell_key` and its readers — the count route, `composite_key_guard`, the snapshot cycle, the fold plane's grain; `concept.identity.canonical_key` (a one-column key); `ColumnSpec.role` takes it as an argument; `key_column`, the legacy spelling of a one-column key |

| the key's shape | what it means | consequence |
|---|---|---|
| **one column** | that column **alone** identifies an instance | it is the canonical identity — what `COUNT(DISTINCT …)` counts and what an answer discloses that it counted; `concept.identity.canonical_key` is filled from it |
| **two or more** | the columns **together** identify an instance | `cell_key` carries them in the order written; none identifies anything alone, and using one as if it did returns a set where a row was expected — which looks like an answer |
| any shape, on a `class: measure` concept | the **grain**, and nothing else | a measure is summed, not counted (`mac_vocabulary.yaml#concept.class.measure`: *"Decides COUNT(DISTINCT key) vs SUM(column)"*), so it has no canonical key whatever its key's length. A tall fact's DISCRIMINATOR — the column saying which measure a row states — is `grounding.code_column`, never the key |

**One home, so the two cannot disagree.** The columns do not repeat the key, and both reasons it sits
here rather than on them are measured. It needs an ORDER and a per-column flag has nowhere to put
one: swapping two YAML column blocks in `units_sold` turned `(order_key, line_number)` into
`(line_number, order_key)` — an edit no gate can see and any formatter may make — and that order
reaches the SQL. And it needs to be READABLE: 7 of contoso5's 17 concepts are keyed on a composite,
and reading the key meant scanning every column of the source for a flag. After the move all 112 of
contoso5's derived column roles are byte-identical to what the per-column flags produced, so no
reader downstream reads a different answer.

A key is per source **and per concept**: `country_code` is the `key` of `Country` and
`axis: categorical` in `Customer`, the same column playing a different part in two concepts. A fact
attached to the column's *name* could not say that.

---

## The column, top level

Four keys, four different questions. Only `offers` is required, and `mac.schema.json` admits no
fifth: `offer: {}` is a LOAD ERROR naming the four, where a misspelled sentence is just another
sentence. The source's [`key`](#key--what-makes-one-row-unique) and
[`counts`](#counts--when-a-count-of-the-concept-is-not-a-count-of-its-rows) are not among them, and
that is the point: each is one statement about the relation, and each sits beside `relation:`.

| key | card | value | required | says | read by |
|---|---|---|---|---|---|
| `offers` | **map** | use → that use's qualifier | **yes** — `{}` is legal | what a question may do with this column | the planner, at every step it takes, through `Grounding.offers(column, use)` |
| `references` | string | a **concept name** | iff it points | my values identify one row of **that concept** — a join target, never part of this concept's grain | join and edge derivation; `planner/sql._filterable` |
| `value_register` | string | a bundle-relative path | no | the file whose rows **are** my values — one register per value set | `ColumnSpec.value_register`, `column_facts.value_register` |
| `rulings` | map | see [`rulings`](#rulings--what-a-person-decided-about-a-column) | no | how this column relates to **another column** | `planner/sql.assemble_plan`, `planner/contract_guards`, `interpret/vocabulary` |

`offers` is the only key read through a projection; `rulings` is read ON the column, through
`Grounding.spec(name).rulings`, because a ruling is a fact about the column.

### Two absences, two different findings

| what is written | what it means | what follows |
|---|---|---|
| `offers: {}` | **a positive statement** — the column exists, is typed, is served, and is offered to no question | nothing: no route reaches the column, and its absence from every answer is correct. contoso5 writes it on `valid_from` / `valid_to`, and on every key column — a column named in `key` is reached through the key, not through a use |
| no `offers` key | **unclassified** — nobody has said what the column is for | a finding raised against the concept: an unjudged column is work owed, not a state |

Absence is never load-bearing except where it is declared to be. These two are the declared case and
must not be collapsed into one.

---

## `offers` — the five uses, each with its own terms

The value of a use **is** its qualifier, so a use cannot be claimed without stating its terms.
The requirement is structural: there is nothing to write that would claim a use and say nothing.

| use | qualifier card | terms | says | read by |
|---|---|---|---|---|
| `axis` | scalar | `time` · `categorical` | a question may **group or filter** by me | `planner/grounded_columns.axis_columns`, `column_facts.axis` — the fold law's lookup key |
| `suppressed` | scalar | a DQ register id | I **am** that axis and a person has ruled that no question may group by me. **Requires `axis`** | `planner/plan._axis_denied` → a Refusal quoting the finding |
| `aggregate` | map | `{type, unit, default, additivity}` | a question may **fold** me | `column_facts.measure_type` / `unit`; `planner/plan._check_additivity` |
| `period_binding` | `true` | — | I am **the** reporting date when the relation carries several | `planner/plan._period_columns`; `Grounding.offering('period_binding')` |
| `extremum` | list | `[min]` · `[max]` · `[min, max]` | my earliest or latest value may be **asked for** — not folded | `planner/plan._OPERATION_NEEDS` → MIN/MAX; `Grounding.offering('extremum')` |

**A map, because one column routinely has several uses.** Measured on contoso5, 2026-10-07: 21 of
112 columns are a join key you also group by. `customer_key` on a sale line is
`references: Customer` *and* a categorical axis; `date_day` on the FX relation is in the `key` *and*
a time axis; `order_date` on a sale line is a time axis *and* the period binding *and* an extremum.
A single-valued key would have to pick one and lose the rest.

The five use names are the `mac.concept.column.offers` vocabulary, closed, generated into
[column_roles.md](column_roles.md). **A term is authored BARE** — `axis: categorical`,
`type: flow`, `naming: legal`. Each is a closed `enum` in `mac.schema.json` and is validated by
name; `ColumnRoles` reads `rsplit(".", 1)[-1]`, so the fully qualified spelling
(`mac.concept.axis.categorical`) still loads, but it is the term's IDENTITY in
`mac_vocabulary.yaml` rather than what an author writes. A fenced example on this page is
authorable exactly as it stands.

### `references` — a pointer at ANOTHER concept

Not a use, and that is the revision-5 change: it answers *"does this column point at another
concept"*, which is a statement about the other concept rather than something a question does with
this column. So it is a top-level key and its value is **the concept's name**.

```yaml
customer_key:  {offers: {axis: categorical}, references: Customer}   # v_contoso5_sales_line
location_code: {offers: {}, references: Location}                    # dim_store
product_key:   {offers: {}, references: Product}                     # dim_product, on Brand
```

| | |
|---|---|
| card | a concept name, one string |
| required | iff the column points somewhere |
| consequence | the column is a join target and never part of **this** concept's grain; whether every value is present over there is a measurement, and a reference with no parent relation in the delivery is recorded AS dangling |

**What identifies a row of *this* concept is [`key`](#key--what-makes-one-row-unique) on the
source** — one fact, with an order, in one place. A column named in the `key` therefore carries no
identity statement of its own and writes `offers: {}`; a column carrying `references` is a pointer
whether or not the key also names it.

**The target is authored because it is not always measurable.** Of contoso5's 25 references, 22
resolve from the descriptor's own `references.to` in `data/datasets/<relation>.yaml`. Three do not:
`Brand`, `Color` and `ProductCategory` are member-sets **over** `dim_product` and declare
`product_key`, which the data plane calls that relation's own primary key — a pointer inside one
relation is conceptual, and no descriptor can see it. So the descriptor is the check, not the
source. (The retired spelling was `roles: {identity: reference}`, which said only THAT the column
pointed somewhere; the target was then recovered by matching column names against concepts whose key
is that column, an inference that has been observed to fail — and that those three break by
construction.)

**What it does today, and what it does not.** `parser._check_references_known` refuses a concept the
bundle does not declare; `ColumnSpec.offers("identity")` answers from the key's presence, which is
what `planner/sql._filterable` asks to place a predicate; and `ColumnSpec.role` derives `key` from
*in the source's key OR carrying a reference*. It is **not** a join driver: every one of contoso5's
25 references already has a matching edge in `edges.yaml` and the planner joins from there.

### `offers.axis` — what a question may group or filter by

| term | what it is | what the fold law does with it |
|---|---|---|
| `time` | an ordered temporal axis — day, month, quarter | stocks do not accumulate along it |
| `categorical` | a non-temporal entity or dimension axis — product, location, customer | flows and stocks are additive along it |

**The kind IS the permission.** A column that declares one may be grouped and filtered by; a column
that declares none is not an axis and the fold law is never consulted on it. Two kinds and no more,
because the law is a grid of `aggregate.type × axis` and a third kind would leave cells nobody has
ruled on — `.none` was added and withdrawn inside an hour on 2026-10-07 for exactly that reason, and
it is also why a prohibition is a separate key rather than a third term.

A declared kind must agree with the column's measured TYPE family (temporal → `time`, everything
else → `categorical`), which is measured rather than assumed: 70 of 70 agree on contoso5.

**`axis` is declared, not derived**, and these two concepts are why. Both are keyed on a composite;
only one of them is keyed on columns a question slices by.

| | `UnitsSold` | `ExchangeRate` |
|---|---|---|
| relation | `v_contoso5_sales_line` | `v_contoso5_fx_rate` |
| the key | `key: [order_key, line_number]` | `key: [date_day, from_currency, to_currency]` |
| each key column carries | `offers: {}` | `axis: time` / `axis: categorical` / `axis: categorical` |
| so a question may | join and count on them | join, count, **and group** by them |
| because | a line number is a position in a basket; *"quantity by line number"* asks nothing | *"the USD→EUR rate on 2025-01-03"* names the row **by** its axes |

Nothing in cardinality, type or reference structure separates those two cases. The `axis` term is the
only thing that says which one you have.

### `offers.suppressed` — the axis no question may group by

```yaml
city:          {offers: {axis: categorical, extremum: [min, max],
                         suppressed: DQ-IDENTIFYING-DIM_CUSTOMER-CITY}}
customer_name: {offers: {axis: categorical, extremum: [min, max],
                         suppressed: DQ-IDENTIFYING-DIM_CUSTOMER-CUSTOMER_NAME}}
```

| | |
|---|---|
| card | one string: the id of a finding in `data/quality/data_quality_register.yaml` |
| requires | **`axis`**, by schema `dependentRequired` — the ontology states what the warehouse IS, and a suppression is a judgement on top of that |
| consequence | the column is never OFFERED as an axis, and a question that names it anyway gets `POLICY_DENIED` quoting the finding; the FILTER stays legal |

**The value is the evidence**, so a prohibition cannot be authored without naming its measurement
and the refusal quotes the register rather than a word. `DQ-IDENTIFYING-DIM_CUSTOMER-CITY` reads
*"21,317 of 34,581 distinct values (62%) over 104,990 rows are held by exactly one row … a column
most of whose values name one row is an identifier wearing a dimension's role: GROUP BY it returns
one row per person, and the query succeeds."* That sentence is what the reader meets.

It sits in `offers` and not in `rulings` because every member of `rulings` names ANOTHER column and
this one never did — it is a judgement about the column's own use. (It was two keys,
`rulings: {never_axis, evidence}`, and the prose field carried a reason CODE — `privacy` — in both
of contoso5's uses while the measurement it claimed to hold already lived in the register.)

### `offers.aggregate` — the qualifier of a foldable column

```yaml
net_amount:
  offers:
    aggregate: {type: flow, unit: USD, default: true}
    extremum: [min, max]
net_price:
  offers:
    aggregate: {type: intensive, unit: USD}
    extremum: [min, max]
```

| sub-key | card | terms | required | says |
|---|---|---|---|---|
| `type` | scalar | `flow` · `stock` · `intensive` · `precomputed` · `target` | **yes**, within `aggregate` | what kind of quantity this is — the row of the fold law |
| `unit` | string | free — `USD`, `units`, `m2`, `to-currency per from-currency` | **yes**, within `aggregate` | what the number is in; two different units may not be combined |
| `default` | bool | `true` | no | **which** aggregate column is *the* one, when a concept carries several |
| `additivity` | map | `{<axis>: <effect>}` over `mac.concept.aggregation_effect` | no | a per-axis EXCEPTION the type cannot state; it projects to `semantics.additivity`, and an entry that agrees with the type is a second home for the type |

`type` is a `mac.concept.column.measure_type` term, defined once in [measures.md](measures.md) and
never restated per concept — and it is a closed `enum` in the schema as of 2026-10-07; it was
`{"type": "string"}` with no enum, so any spelling validated while the law it keys could match none
of them. `unit` is what unit algebra reads: a sum over two units refuses, and a ratio names the unit
of its result.

**PER COLUMN, not per concept, and `default` is why that works.** `NetRevenue` grounds `net_amount`
(`flow`, USD) and `net_price` (`intensive`, USD) on one relation. A single statement for the whole
concept could only misreport one of them, and did: `SUM(unit_price) AS grossrevenue` planned and was
permitted. `default: true` on `net_amount` says which number a question about the concept itself
folds, and with it the unit of that answer. Where several carriers agree on a unit the concept need
state nothing; where they disagree and none carries `default`, the load refuses rather than let YAML
key order decide an answer's unit.

### `offers.period_binding` — which date a period binds to

```yaml
order_date:    {offers: {axis: time, period_binding: true, extremum: [min, max]}}
delivery_date: {offers: {axis: time, extremum: [min, max]}}
```

A sale line carries both dates and both are real time axes. `period_binding` says which one *"sales
in March"* means; a bare flag, because this use has no parameter. On a relation with exactly one date
it is still worth writing: the relation that grows a second date later does not then change the
meaning of every period question already asked of it.

### `offers.extremum` — a value that may be asked for, not folded

```yaml
close_date:    {offers: {axis: time, extremum: [min, max]}}
square_metres: {offers: {aggregate: {type: stock, unit: m2}, extremum: [min, max]}}
```

An extremum **picks one value that exists in the data** instead of combining several, which is why it
is its own use and not a corner of `aggregate`: it answers to no additivity cell and is meaningful on
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
column with no `axis` is never consulted: there is no axis to cross. A column whose every cell
is `none` — `precomputed`, `target` — is foldable by nothing, and that is the measure type's ruling
rather than a fact about the column. contoso5's `Location.units_ever_here` is the `precomputed` case.

Ten cells, derived from two declared terms, so a column that restated one of them would be a second
home for the law and the home that disagreed would win silently. `aggregate.additivity` is the one
exception and exists only for it: a NAMED axis where the type is wrong in general, such as a balance
that sums across stores and not across days. contoso5 authors none.

---

## `counts` — when a count of the concept is not a count of its rows

The second fact about a source that is not a fact about any one of its columns. A concept's key
identifies a **row**. What a **count** counts is sometimes a different column — and it may be a
column the `key` does not name at all.

```yaml
source:
  relation: dim_store
  key: store_key
  counts: location_code
```

| | `Store.store_key` | `Store.location_code` |
|---|---|---|
| in `key` | **yes** — `key: store_key` | no |
| `offers` | `{}` | `{}` |
| other keys | — | `references: Location` |
| named in `counts` | — | **yes** |
| rows | 74 — one per trading period | — |
| a count of *stores* | would say 74, wrongly | says **67** |

`counts` is how a concept says *"a count of me is not a count of my rows"*. The `key` stays what the
fact JOINS on; `counts` names what a count DISTINCTs, it fills `concept.identity.counts_as`, and the
answer discloses which column it counted.

**It names a column, so it belongs to the source.** It was a boolean on the column until 2026-10-07
and moved for the same reason `key` did: it is one fact about the concept whose value is a column
name, and the column it names adds nothing by carrying a flag. It also could not be a term of the
retired `identity:` slot, because the column that counts is routinely also the one that references —
contoso5's `location_code` carries `references: Location` at once, and a single slot could hold only
one of them.

---

## `value_register` — where this column's values come from

```yaml
source:                                        # Country
  relation: dim_country
  key: country_code
  columns:
    country_code:
      offers: {}
      value_register: data/lookups/contoso5_country_code.lookup.yaml
```

```yaml
source:                                        # Brand
  relation: dim_product
  key: brand
  columns:
    brand:
      offers: {axis: categorical, extremum: [min, max]}
      value_register: data/lookups/contoso5_brand.lookup.yaml
    product_key:
      offers: {}
      references: Product
```

One register per value set, and the column points at it. The register's rows **are** the values; the
column never restates them. Two columns carrying the same value set point at the same register — the
register's identity is the value set, not the column that uses it.

A register exists so a typed word can reach a stored code without probing the warehouse. The
resolution ladder that walks it — exact, then near miss, then ask with candidates — is the resolver's,
not the column's.

### Three facts, three names

The word `register` named three different things one nesting level apart, and contoso5's `Country`
concept declared two of them seven lines from each other. Each now has its own name.

| key | value | says |
|---|---|---|
| `value_register` on the column | a bundle-relative path | where this column's VALUES come from — the register a name resolves through |
| `rulings.naming` | a `mac.name_register` term | **which of the thing's names** this column carries; legal only beside `label_of` |
| `domain.register` | a bundle-relative path | the designed `domain` block's name for the first of these; not a key a column may carry today |

The runtime had already been forced to split the first two — `ColumnSpec.value_register` and
`ColumnRulings.naming_register` — while the author was still asked to write one word for both.

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

`offers` says what a question may do with a column; the type family says what a comparison against it
may mean. A threshold of `630.5` against an integer key and a boolean against a numeric both refuse at
the same gate, and they refuse by FAMILY rather than by warehouse spelling — the spellings are a
bundle's descriptor data and differ per warehouse, so the families are closed here and the spellings
are normalised before matching (the text before `(` or `<`).

The family is **measured**, from the relation's descriptor. It is never declared on the column — and
it is what `offers.axis` is measured against: temporal → `time`, everything else → `categorical`, with
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

A ruling is a judgement measurement cannot establish. All five are optional; a column with no rulings
behaves as its `offers` alone dictate. **Each names ANOTHER column**, or says which of that other
column's names this one is — which is why a ruling is not a use, and why the block is nested:
`offers` describes the data, `rulings` relates it, and a slot that accepted both would silt up until
nobody could tell which kind a value is.

| ruling | value | required | says | the measurement that gets you to the door | read by |
|---|---|---|---|---|---|
| `label_of` | a column of the same source map | — | I am **another name for that column's thing**, not another thing — group on it, display me | `a = b = pairs` (1:1) | `planner/sql.assemble_plan`: the label is SELECTed and the named column grouped on |
| `naming` | `common` · `legal` · `long` · `short` · `code` | **with `label_of`** | **which** of that thing's names I carry | — only a person can say | `planner/sql.assemble_plan`, named in the disclosure *("legal register")* |
| `finer_than` | a column of the same source map | — | I distinguish **more members** than that column and roll up into it; both stay legitimate axes and an answer must **disclose which level it used** | `pairs = finer_distinct` — a clean N:1 | `planner/sql.assemble_plan`, the level disclosure |
| `scoped_by` | a column of the same source map | — | my values are unique **only within** that column, so I may not be grouped or filtered alone — the scope must travel with me | 0 collisions within the parent, many across it | it synthesises a `composite_key_guard` binding, read by `planner/contract_guards.sql_guard_bindings` |
| `sort` | `asc` · `desc` · `none` | — | the order my values are presented in when the question states none | **none — and that is the point:** SQL guarantees no row order without `ORDER BY` | `planner/sql.column_sort` → the ORDER BY this column contributes |

```yaml
country_name:      {offers: {axis: categorical, extremum: [min, max]},
                    rulings: {label_of: country_code, naming: long}}      # Location
manufacturer:      {offers: {axis: categorical, extremum: [min, max]},
                    rulings: {label_of: brand, naming: legal}}            # Product
state:             {offers: {axis: categorical, extremum: [min, max]},
                    rulings: {scoped_by: country_code}}                   # Customer
sub_category_name: {offers: {axis: categorical, extremum: [min, max]},
                    rulings: {finer_than: category_name}}                 # ProductCategory
```

**A prohibition is not here.** That no question may group by a column is a judgement about the
column's OWN use, names no other column, and is
[`offers.suppressed`](#offerssuppressed--the-axis-no-question-may-group-by).

### What the load refuses

| the shape | what happens | why |
|---|---|---|
| `naming` without `label_of`, or `label_of` without `naming` | LOAD ERROR — schema `dependentRequired` in both directions, and the `ColumnRulings` validator | `naming` says WHICH of the thing's names this column is, so it needs the thing; and a redirected label whose name nobody stated cannot be disclosed |
| `suppressed` without `axis` | LOAD ERROR — schema `dependentRequired` on `offers` | declaring a real axis "not an axis" would make the ontology lie about the warehouse |
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
| contoso5 | `Customer.country_code finer_than continent`; `ProductCategory.sub_category_name finer_than category_name` — 32 sub-categories over 8 categories; `Location.state finer_than country_code` | `Customer.state scoped_by country_code` |
| what a question gets | both levels stay legal; the answer discloses which it used, and an ambiguous question is offered both | the scope column is added, or the engine ASKS which parent was meant |
| what the mistake costs | a disclosure nobody made | one row labelled `CO` merging three unrelated regions — Corse, Como and Colorado, measured in [column_rulings.md](column_rulings.md) §3 — with a plausible row count and a meaningless number |

**The same column, both ways, in one bundle.** `state` is `scoped_by: country_code` on `Customer`
and `finer_than: country_code` on `Location`, and both are right: 40 of `dim_customer`'s 565 state
codes are carried by more than one country, while `dim_location` holds one state per location and
every one of them sits in exactly one country. The ruling is per source and per concept because the
measurement is.

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
| what the column IS | `offers: {axis: categorical, extremum: [min, max]}` | the truth about the data, so joins, resolution, the extremum route and the fold law all read it correctly |
| that no question may group by it | `suppressed: DQ-IDENTIFYING-DIM_CUSTOMER-CITY`, **in the same map** | a refusal: the column is never OFFERED as an axis, and a question that names it anyway gets `POLICY_DENIED` |
| the measurement | **the value itself** — the id of the finding, raised from `data/profiles/<relation>.yaml` `singletons`, which the refusal quotes back | 21,317 of 34,581 distinct values over 104,990 rows are held by exactly one row |

One key, and its value is the evidence: a prohibition cannot be authored without naming its
measurement. The reader meets a refusal that teaches instead of a column that lies. Where the
prohibition is cross-column — *"never report nine countries"* — it is a concept rule with `never`,
`why` and `binds`; the shape, its six kinds and the `never` → refusal path are in
[identity_and_rules.md](rules_and_canons/identity_and_rules.md).

---

## Worked: `Customer`, all 10 columns

One source, a one-column key, seven axes — two of them suppressed and two ruled on — and three
columns offered to no question.

```yaml
grounding:
  source:
    relation: dim_customer
    key: customer_key
    columns:
      customer_key:  {offers: {}}
      customer_name: {offers: {axis: categorical, extremum: [min, max],
                               suppressed: DQ-IDENTIFYING-DIM_CUSTOMER-CUSTOMER_NAME}}
      continent:     {offers: {axis: categorical, extremum: [min, max]}}
      country_code:  {offers: {axis: categorical, extremum: [min, max]},
                      rulings: {finer_than: continent}}
      state:         {offers: {axis: categorical, extremum: [min, max]},
                      rulings: {scoped_by: country_code}}
      city:          {offers: {axis: categorical, extremum: [min, max],
                               suppressed: DQ-IDENTIFYING-DIM_CUSTOMER-CITY}}
      gender:        {offers: {axis: categorical, extremum: [min, max]}}
      birth_date:    {offers: {axis: time, extremum: [min, max]}}
      valid_from:    {offers: {}}
      valid_to:      {offers: {}}
```

| the choice | what is written | why |
|---|---|---|
| `customer_key` | named in `key`, and `offers: {}` | the key is the source's one statement about what a row IS; the column adds nothing to it, and the derived role `key` comes from the key naming it |
| `country_code` here is **not** the key | `axis` alone, plus `finer_than` | it is the `key` of the `Country` concept, not of `Customer` — the same column, a different part in two concepts |
| `valid_from`, `valid_to` | `offers: {}` | SCD-2 row-validity stamps: when the ROW was written, not when anything happened. No question is offered them, and saying so is a declaration |
| `state` | `scoped_by: country_code` | its codes are reused across countries, so a group by `state` alone merges two places |
| `city`, `customer_name` | `axis`, **and** `suppressed` with the finding's id | they *are* axes; that no question may group by one is a judgement, and its value is the measurement |
| every axis also carries `extremum` | `extremum: [min, max]` | *"the earliest birth date"* is a pick, not a fold, and a categorical axis admits it too |

## Worked: one column, three parts in three concepts

`country_code` is declared in `Country`, `Customer` and `Location`, and it means something different
in each. Nothing attached to the column's name could say that.

| concept | relation | the source's `key` | `offers` | other keys |
|---|---|---|---|---|
| `Country` | `dim_country` | `country_code` | `{}` | `value_register: data/lookups/contoso5_country_code.lookup.yaml` |
| `Customer` | `dim_customer` | `customer_key` | `axis: categorical`, `extremum: [min, max]` | `rulings: {finer_than: continent}` |
| `Location` | `dim_location` | `location_code` | `axis: categorical`, `extremum: [min, max]` | — (and `country_name` beside it is its `label_of`) |

**Being the key and being an axis are two statements, and that is what the map is for.**
`Brand.brand` is the whole of `key: brand` *and* carries `axis: categorical`,
`extremum: [min, max]` and a `value_register`: a brand *is* the thing the concept is about, it is
also what a question slices by, and its earliest and latest value may be asked for — which is why
its derived role is `dimension` and not `key`, the one case where a key column's own role name
changes (`brand.brand`, `color.color`, `category_name`). `UnitsSold.order_key` is the opposite
corner — named in a two-column `key` and `offers: {}`, grain without groupability. A single
per-column flag could express neither.

---

## Why there is no free-text key

**A free-text key on a column is where rulings go to hide.** Measured on contoso 2026-09-25:
`grounding.note` carried ruling language — *never*, *must not*, *display-only*, *because* — in **12 of
21 concepts**. The clearest was a 1 044-character note reading:

> *"`ZipCode` and `City` are display-only, never filter or group — because DQ-CUSTOMER-02 measured
> that ZipCode alone singles out 29 193 of 104 990 served rows."*

A measured privacy ruling, stated in prose, in a field nothing reads — while the runtime happily
planned `GROUP BY ZipCode`. It is now `offers: {axis: categorical, suppressed: DQ-…}`, and the
refusal reaches the person who asked.

**So the column block has no free-text key at all.** Every value on a column is a closed term, a
column name, a concept name, a path, a unit, a boolean or a register id — and the last of those is
the one that reaches a reader, because the refusal quotes the finding it names. If you want to write
something about a column:

| what you want to say | where it goes |
|---|---|
| it changes what the engine does | a **declaration** — find the key, or the key is missing and *that* is the finding |
| the reader of a REFUSAL must know it | `offers.suppressed` with the finding's id, or a concept rule's `never` and `why` |
| why a ruling was made | the measurement's id — `DQ-…`, raised from a profile, not a paragraph |
| it is unresolved | the SME ledger outside `ontology/` — with an id, an owner and a status |
| it is about the concept, not this column | `concept.definition`, or the account in `knowledge/<concept>.md` |

The one sentence the design still reserves is `disclose`, and it is reserved rather than shipped:
it would reach the reader of a successful ANSWER, which no other key does. It is a load error today.

---

## What stays at concept level

| key | why it cannot descend |
|---|---|
| `concept.definition`, `concept.class` | about the concept |
| `grounding.source.relation`, `.key`, `.counts` | the binding itself, what one row of that relation is, and what a count of the concept counts — each one statement, with an order or a column name as its value |
| `grounding.snapshot_rule`, `grounding.realized_by` | how the whole relation collapses before anything is summed |
| `edges` | between **concepts** |
| `contract.default_reading` | what an unqualified **word** means |
| `contract.rules[].when` / `then` / `never` / `why` | a rule's **prose** is usually cross-column; `binds` names the columns it governs |
| `semantics.unit` | the COMPOSED unit, where several carriers disagree and none carries `default` |

**But a rule's params are not prose.** A column name, a register path, a sort direction are mechanics
about one column and they descend onto it. **Prose stays, params descend** — that split is what stops
`columns:` becoming a second dumping ground.

**And the grain does not live at concept level either.** `concept.identity` holds two COLUMN NAMES,
neither of them authored there: `canonical_key` is a ONE-column `source.key` — and is empty on a
`class: measure` concept whatever the key's length, because a measure is summed rather than counted —
and `counts_as` comes from `source.counts`. A prose line restating what one row is would be a second
home for a fact the source already states, and the one that disagrees is the one nothing checks.

---

## What is never declared here

These are **measured**. Declaring them would create a second home for a fact the warehouse states.

| fact | where it comes from |
|---|---|
| type family, storage role, key position | `data/datasets/<relation>.yaml` |
| distinct, nulls, min, max, singletons, functional determination | `data/profiles/<relation>.yaml` |
| observed landing values | `data/sources/<relation>.yaml` |
| the members themselves | `data/lookups/<name>.lookup.yaml` |
| whether a `references`' values are all present in the parent | the dangling-key measurement over the delivery |
| what a `references` points AT, in 22 of contoso5's 25 cases | `data/datasets/<relation>.yaml` `references.to` — which is the CHECK on the authored concept name, not its source; three of the 25 are pointers inside one relation that no descriptor can see |
| the five scalar role names — key, dimension, measure, period, housekeeping | `ColumnSpec.role`, derived from `offers` in the vocabulary's own precedence, **with the source's `key` as an argument** — a column alone cannot know whether it is in the key. It reproduces all 112 of contoso5's columns exactly: a column the key names is `key`, unless the key is one column that also declares an `axis`, which is `dimension` |

A declaration says what a thing IS and what may be done with it. It never restates what counting would
tell you.

---

## Every key — the complete surface

Thirty-two keys an author writes, plus one nobody authors, each with its effect — which plane it
lands on, which `mac.outcome_class` terms it can produce, and what reads it — declared in
[column_effects.yaml](column_effects.yaml) and rendered interactively by `column_bench.html`. The
container key `rulings` and the sub-keys of `aggregate` have their sections above. `storage_role` is
the one key nothing authors: the data plane measures it, so it is declared there and not here. And
`key` and `counts` are the two that are not column keys at all — each is one statement about the
**source** — and they are listed here because this table is the complete surface an author writes,
and the key is the first thing they write.

| key | required | default | legal values | decides |
|---|---|---|---|---|
| `key` | **yes** | — | a column name, or an ordered list of them — *on the source, not the column* | what makes ONE ROW unique; the order becomes `cell_key` and reaches the SQL |
| `counts` | no | the `key` | a column name — *on the source, not the column* | which column one INSTANCE is counted by, when the relation is served finer than the thing |
| `offers` | **yes** | — | a map over `mac.concept.column.offers` — axis · suppressed · aggregate · period_binding · extremum | what a question may do with this column at all; `{}` means *offered to no question* |
| `offers.axis` | iff claimed | — | `time` · `categorical` (`mac.concept.axis`) | which KIND of axis this column is, which is both the permission to group and the fold law's lookup key |
| `offers.suppressed` | iff claimed | — | a DQ register id | that no question may group by this column — the finding the refusal quotes; **requires `axis`** |
| `offers.aggregate` | iff claimed | — | a map over `type` · `unit` · `default` · `additivity` | that a question may fold this column, and on what terms |
| `offers.aggregate.additivity` | no | the fold law | `{<axis>: <effect>}` over `mac.concept.aggregation_effect` | the effect of folding along ONE named axis, overriding the law — authoring it means authoring both premise and conclusion, so leave it unwritten |
| `offers.period_binding` | iff claimed | — | `true` | which date a question's period binds to, when the relation carries several |
| `offers.extremum` | iff claimed | — | a list over `min` · `max` — at least one, no repeats | that the earliest or latest value may be asked for — a pick, never a fold |
| `references` | iff it points | — | a concept name | which concept this column's values identify a row of, so it is a join target and never part of this concept's grain |
| `value_register` | no | — | a bundle-relative lookup path | where this column's values come from, so a word resolves to the exact value it holds instead of probing for a match |
| `rulings.label_of` | no | — | a column of the same source map | that this column NAMES that one; group there, display here |
| `rulings.naming` | **with `label_of`** — schema `dependentRequired` | — | `mac.name_register` — common · legal · long · short · code | which of the thing's names this column carries, so an answer can say which it showed |
| `rulings.finer_than` | no | — | a column of the same source map | that this column rolls up into that one, and that an answer discloses which level it used |
| `rulings.scoped_by` | no | — | a column of the same source map | that the scope column must travel with this one, which is unique only within it — synthesising a `composite_key_guard` binding |
| `rulings.sort` | no | — | `asc` · `desc` · `none` | the order this column's values are presented in when the question states none |
| `domain.closure` | never — not a column flag; a load error | open | `closed` · `open` | whether the register states every member, so a word outside it is answerable without a probe |
| `domain.complete_for` | never — not a column flag; a load error | — | `data` · `world` | whether a word that misses answers zero-disclosed or refuses as not a member of the kind |
| `domain.warranty` | never — not a column flag; a load error | — | `derived` · `monitored` | how a closed set is kept true: a rule makes the members, or a scheduled check reconciles them |
| `domain.register` | never — not a column flag; a load error | — | a bundle-relative path | which register's rows ARE the members; the live spelling of this fact is `value_register` |
| `domain.members` | never — not a column flag; a load error | — | an inline list of members | the inline form, for a domain too small for a file — fifteen age bands, not five hundred countries |
| `resolution.search` | never — not a column flag; a load error | — | register columns, in order | which columns of the register a typed word is compared to, and in what order |
| `resolution.display` | never — not a column flag; a load error | — | a register column | which column an answer PRINTS when the group is on the code |
| `resolution.strategy` | never — not a column flag; a load error | the whole ladder | an ordered list over `exact` · `normalized` · `prefix` · `fuzzy` · `ask` | which rungs of the resolution ladder this column admits |
| `resolution.fuzzy_floor` | never — not a column flag; a load error | — | a similarity between 0 and 1 | below which a candidate is not worth offering |
| `resolution.on_miss` | never — DERIVED, not authored | — | `ask` · `zero, disclosed` · `refuse` | what a word matching nothing produces; read off `closure` and `complete_for`, never set |
| `resolution.candidates` | never — not a column flag; a load error | show | `show` · `suppress` | whether an ASK may list the members, or listing them would itself leak something |
| `placement.fact_join` | never — not a column flag; a load error | — | a column of the fact | that a predicate lands on the fact and the dimension is never joined |
| `absence.nulls` | never — not a column flag; a load error | — | a reading of NULL, per column | what a NULL in THIS column means — *"no status event recorded, so NOT operating"* against *"not applicable"* |
| `absence.sentinels` | never — not a column flag; a load error | — | stored values that are not members | the `--` that is not a country, per column and per source |
| `disclose` | never — not a column flag; a load error | — | one line of prose | one sentence every answer touching this column must carry |
| `discriminates` | never — not a column flag; a load error | — | a concept or value name | that this column says WHICH KIND of row a tall relation holds |

---

## Rules this model holds

1. **One fact, one key.** No column states the same thing twice, and no key restates what another
   declares — not the grain, not the additivity law, not the member list.
2. **Claim a use, state its terms.** The qualifier *is* the value, so a use cannot be claimed
   without it. The requirement is structural, not a gate.
3. **A declaration describes the data; a prohibition is ruled.** A column that *is* an axis says so
   even when policy forbids grouping by it; `suppressed` sits BESIDE `axis`, never instead of it,
   and its value is the finding the refusal cites. Declaring a real axis "not an axis" would make
   the ontology lie about the warehouse.
4. **Absence is never load-bearing except where it is declared to be.** `offers: {}` means *offered
   to nothing*; a missing `offers` means *unclassified*. The two are different findings.
5. **A key arrives with its reader.** A declaration nothing consumes is the defect this model exists
   to end, so the surface grows one key at a time, each with the code that acts on it and the test
   that measures it. The first draft of this block carried 19 flags and
   `test_every_declared_field_is_consumed_or_waived` failed on all 19.
6. **A word carries one fact.** Five keys have been retired for failing this — `role`,
   `identity: canonical`, `identity`, `register`, `never_axis` — each found only after it had
   shipped. A key whose value space has two shapes, or whose name describes two questions, is the
   next one.

---

## What a column does not yet say

The limits are declared, because an undeclared limit is found by a reader who needed it. Each row is a
fact a column cannot state today, the key the effects registry reserves for it, and where the model
answers that question instead.

| the fact | reserved key | where it is answered today |
|---|---|---|
| that a `references` target is where the JOIN comes from | `references` — authored and read, but not yet a join driver | `edges.yaml`: all 25 of contoso5's references already have a matching edge and the planner joins from there. The key's target is checked against the concept set (`parser._check_references_known`) and otherwise unexercised on the join path |
| whether a register states every member, and complete for which world | `domain.closure`, `domain.complete_for` | the [explicit_closure](patterns/open_vs_closed_world/explicit_closure.md) pattern, realized by the `enum_from_register` canon, plus `values.closure` on the concept |
| how a closed set is kept true | `domain.warranty` | nothing — a closed set nobody watches is a refusal backed by a stale sample |
| which register columns a word is matched and printed from | `resolution.search`, `resolution.display`, `resolution.strategy`, `resolution.fuzzy_floor`, `resolution.candidates` | the resolver's own ladder, the same for every column with a register |
| what a NULL means **in this column** | `absence.nulls` | the [absence_semantics](patterns/open_vs_closed_world/absence_semantics.md) pattern, realized by `densify` |
| a non-null value that is not a member | `absence.sentinels` | an exclusion rule on the concept — contoso5's `country_code != '--'` |
| that a predicate may land on the fact and skip the dimension join | `placement.fact_join` | nothing; the plan walks the join |
| one line every answer touching the column must carry | `disclose` | nothing: a refusal reaches a reader and a successful answer does not |
| which column selects what KIND of row this is | `discriminates` | `grounding.code_column` names the column — a tall fact's discriminator is NOT its key, and on a `class: measure` concept it cannot be one; `values.aliases.map`, read as `variant_codes`, says which code is this concept's |
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
transform cannot grow a fourth store status — or they were observed and a scheduled check reconciles
them. There is no third option.
