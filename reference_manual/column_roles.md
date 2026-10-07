---
title: Column roles — the five things a question may do with a column
status: >-
  CURRENT (2026-10-07). The `roles` map is what mac.schema.json admits and what the runtime loads:
  `identity: composite`, `aggregate` as a qualifier and `roles: {}` all load, and the five role NAMES
  are derived rather than authored. Every planner step asks `Grounding.offers(column, use)`, which
  reads this map. The fold law reads `axis` and refuses a fold it does not permit
  (`ADDITIVITY_VIOLATION`, mac-runtime `planner/plan.py` + `foldplane/law.py`). A declared `axis` kind
  must agree with the column's declared type family, which the runtime suite measures: 70 of 70 on
  contoso5. column_declaration.md is the overview; this page is the detail.
audience: ontology authors, importer developers, framework developers
companions:
  - column_declaration.md     # the whole column on one page — every key, and who reads each answer
  - column_rulings.md         # what a PERSON decided about a column, on top of its roles
  - measures.md               # the fold law, stated once: aggregate.type × axis
  - shape_reference.md        # where `columns:` nests in a concept file
  - ../mac_vocabulary.yaml    # the authoritative terms; the chapters below are generated from it
---

# Column roles

A column declares **one** key for what a question may do with it:

> **`roles` — a map from a role to that role's own qualifier.**

Five roles. A column claims every one that is true of it, and the qualifier *is* the value, so a role
cannot be claimed without stating its terms.

```yaml
grounding:
  sources:
    - relation: v_contoso5_sales_line
      columns:
        order_key:     {roles: {identity: composite}}
        customer_key:  {roles: {identity: reference, axis: mac.concept.axis.categorical}}
        order_date:    {roles: {axis: mac.concept.axis.time, period_binding: true}}
        quantity:      {roles: {aggregate: {type: flow, unit: units}}}
        valid_from:    {roles: {}}
```

> **A role is READ, not decided.** All five follow from cardinality, type and reference structure —
> which is why a generator assigns them over a thousand columns with no human present. If you find
> yourself *deciding* rather than *reading*, you are holding a **ruling**, not a role. See
> [column_rulings.md](column_rulings.md).

## The key

| key | card | value | required | says | read by |
|---|---|---|---|---|---|
| `roles` | **map** | role → that role's qualifier | **yes** — `{}` is legal | what a question may do with this column | the planner, at every step it takes |

| what you write | what it means | what it is |
|---|---|---|
| `roles: {axis: categorical}` | a question may group or filter by this column and do nothing else with it | a classification |
| `roles: {}` | the column exists, is typed, is loaded, and **no question is offered it** | a positive statement |
| *no `roles` key* | nobody has said what this column is | a finding, not a state |

Three keys sit beside `roles` on a column and are documented elsewhere, because none of them says what
a question may DO with the column:

| also on a column | says | page |
|---|---|---|
| `counts` | a count of this concept counts **this** column, not the canonical one | [column_declaration.md](column_declaration.md) |
| `register` | where this column's values come from — a lookup path | [column_declaration.md](column_declaration.md) |
| `rulings` | how this column relates to **another column** | [column_rulings.md](column_rulings.md) |

---

## 1 · Two real relations, every column assigned

A fact and a dimension from the same warehouse. Every column, its type, its measured cardinality, and
the roles that follow.

### `v_contoso_order_line` — the FACT, 223 974 rows

| column | type | distinct | `roles` | why these roles |
|---|---:|---:|---|---|
| `OrderKey` | BIGINT | 93 470 | `{identity: composite}` | half the grain — `(OrderKey, RowNumber)` is unique, neither is alone; the order header is reached through it |
| `RowNumber` | INTEGER | 7 | `{identity: composite}` | the other half. A position in a basket: *"revenue by line number"* asks nothing, so no `axis` |
| `OrderDate` | DATE | 3 450 | `{axis: time, period_binding: true}` | THE reporting date — §5 |
| `DeliveryDate` | DATE | 3 498 | `{axis: time}` | a real date, askable by name, never the one a bare period binds to |
| `CustomerKey` | INTEGER | 52 189 | `{identity: reference}` | identifies a row in `dim_contoso_customer`; a breakdown uses Customer's own axes |
| `StoreKey` | INTEGER | 64 | `{identity: reference}` | identifies a row in `dim_contoso_store` |
| `ProductKey` | INTEGER | 2 517 | `{identity: reference}` | identifies a row in `dim_contoso_product` |
| `CurrencyCode` | VARCHAR | 5 | `{axis: categorical}` | 5 members, a legitimate axis |
| `Quantity` | INTEGER | 10 | `{aggregate: {type: flow, unit: units}}` | items sold accumulate per period |
| `UnitPrice` | DECIMAL | 1 760 | `{aggregate: {type: intensive, unit: order currency per unit}}` | a rate: a TOTAL of unit prices is not a price. 1 760 distinct values are not an invitation to group by it |
| `NetPrice` | DECIMAL | 18 407 | `{aggregate: {type: flow, unit: the order's own CurrencyCode}}` | accrues per period — and the **unit**, not the type, is what restricts the comparison |
| `UnitCost` | DECIMAL | 1 955 | `{aggregate: {type: intensive, unit: order currency per unit}}` | likewise a per-unit rate |

**Read the FK shape:** many rows, far fewer distinct values, and every value present in a parent
relation. `StoreKey` has 64 distinct over 223 974 rows — that is a pointer, not a category, even
though its cardinality looks dimension-sized.

### `dim_contoso_customer` — the DIMENSION, 104 990 rows

| column | type | distinct | `roles` | `rulings` | why |
|---|---:|---:|---|---|---|
| `CustomerKey` | INTEGER | **104 990** | `{identity: canonical}` | — | distinct **equals** row count: this column alone identifies a customer |
| `GeoAreaKey` | INTEGER | 608 | `{identity: reference}` | — | identifies a row elsewhere — and no parent relation in this delivery, recorded as dangling |
| `StartDT` | DATE | 11 305 | `{}` | — | when the ROW was written |
| `EndDT` | DATE | 14 711 | `{}` | — | the other end of the SCD-2 validity window |
| `Continent` | VARCHAR | 3 | `{axis: categorical}` | — | |
| `Country` | VARCHAR | 8 | `{axis: categorical}` | — | the canonical geography code |
| `CountryFull` | VARCHAR | 8 | `{axis: categorical}` | `label_of: Country`, `register: long` | 1:1 — the same 8 countries, spelled out |
| `State` | VARCHAR | 563 | `{axis: categorical}` | `scoped_by: Country` | 40 codes are reused across countries |
| `StateFull` | VARCHAR | 608 | `{axis: categorical}` | `label_of: State`, `register: long` | |
| `City` | VARCHAR | 34 581 | `{axis: categorical}` | — | 1 in 3 rows would be its own group. It **is** an axis and says so; a contract rule carries the prohibition |
| `ZipCode` | VARCHAR | 40 639 | `{axis: categorical}` | — | 29 193 postcodes are held by exactly one customer; same shape, same route |
| `Gender` | VARCHAR | 2 | `{axis: categorical}` | — | |
| `age_band_5y` | INTEGER | 15 | `{axis: categorical}` | — | derived by the transform, served as an ordinary column |

**Notice what cardinality alone cannot tell you.** `CountryFull` (8) and `Country` (8) are
indistinguishable by count. `City` (34 581) and `CustomerKey` (104 990) are both high. `StartDT`
(11 305) has the exact shape of a date axis. In each case the role — or the ruling on top of it — comes
from something the numbers do not contain.

### Reading the roles off the data

| what you measure | the role it reads to |
|---|---|
| distinct **equals** row count, no nulls | `identity: canonical` |
| unique only in combination with its siblings | `identity: composite` on each of them |
| many rows, few distinct, every value present in a parent relation | `identity: reference` |
| distinct far below row count, categorical, repeated | `axis: categorical` |
| a date, a month, a period label | `axis: time` |
| **the** date a bare period must bind to, where a relation carries several | `axis: time` **and** `period_binding: true` |
| a numeric payload where adding two values means something | `aggregate` — then [measures.md](measures.md) decides the `type` |
| the earliest or latest value is something a question asks for | `extremum` |
| exists for the pipeline; nobody would ask about it | `roles: {}` |

---

## 2 · The five roles

| role | qualifier card | terms | says | claiming it commits the bundle to | read by |
|---|---|---|---|---|---|
| `identity` | scalar | `canonical` · `composite` · `reference` | the row is identified by me — alone, jointly, or elsewhere | a `COUNT(DISTINCT …)` that counts instances rather than rows, and a join that lands here | `concept.identity.canonical_key` — 22 runtime read sites · [`composite_key_guard`](rules_and_canons/context_dependent_meaning/composite_key_guard.md) |
| `axis` | scalar | `time` · `categorical` | a question may **group or filter** by me | every fold across me being judged by the law, and the column being OFFERED as groupable to a reader | `planner/grounded_columns.py` · the fold law · [`additivity_guard`](rules_and_canons/semi_additive_balance/additivity_guard.md) |
| `aggregate` | map | `{type, unit, canonical}` | a question may **fold** me | one fold per axis, fixed by `type`; a comparison legitimate only inside `unit` | `planner/plan.py` · `concept.semantics.measure_type` / `.unit` / `.additivity` |
| `period_binding` | `true` | — | I am **the** reporting date of this relation | *"sales in March"* binding here and nowhere else | `planner/plan.py` · `interpret/vocabulary.py` |
| `extremum` | list | `[min]` · `[max]` · `[min, max]` | my earliest or latest value may be **asked for** — not folded | answering *"when did we first sell in Spain"* from this column, and ASKING when a concept admits more than one | `planner/plan.py` — the MIN/MAX route |

A column carries as many of the five as are true of it. `customer_key` is `{identity: reference, axis:
categorical}` — it points at a row over there **and** a question groups by it. Neither claim weakens
the other.

### `identity` — three ways to identify

| term | holds when | the answer it licenses | what getting it wrong does |
|---|---|---|---|
| `canonical` | this column **alone** identifies an instance — at most one per concept | `COUNT(DISTINCT …)` counts instances, and the answer discloses which column it counted | a count of ROWS is handed over as a count of things |
| `composite` | this column **with its siblings** identifies an instance | the join and the count, over the whole set of columns carrying it | a filter on one part returns a SET where a row was expected, and looks like an answer — this is what [`composite_key_guard`](rules_and_canons/context_dependent_meaning/composite_key_guard.md) catches |
| `reference` | this column identifies an instance **in another concept** | the join: the row names a row over there | declaring the reference says the relationship is INTENDED. Whether every value is present there is a measurement, and the reference plane records a dangling reference AS dangling — `Customer.GeoAreaKey` is exactly that, 608 distinct values with no parent relation in this delivery |

### `axis` — two kinds, because only one of them has the property that matters

| term | the axis is | the law's row for it |
|---|---|---|
| `time` | ordered and temporal — day, month, quarter | a `stock` does **not** accumulate along it |
| `categorical` | non-temporal — product, location, customer, currency | flows and stocks are both additive along it |

Product, store and customer all fold the same way, so they are one term. This is why `axis` carries a
term and not a boolean. A column with **no** `axis` role is never consulted by the law: there is no
axis to cross.

**A prohibition is a rule, not a role.** A column declares truthfully what it IS, including when policy
forbids using it that way. `ZipCode` is `{axis: categorical}` — 40 639 distinct values over 104 990
customers — because it genuinely *is* a categorical axis of the warehouse; the prohibition, its reason
and its evidence live in a contract rule that refuses and cites the measurement. Declaring a real axis
"not an axis" to express a policy would make the ontology lie about the warehouse, and the next reader
of the measurement finds 40 639 distinct values under a column the ontology says is not an axis. The
route is in [column_rulings.md](column_rulings.md).

### `aggregate` — the qualifier of a foldable column

| sub-key | card | required | terms | says |
|---|---|---|---|---|
| `type` | scalar | **yes**, within `aggregate` | `flow` · `stock` · `intensive` · `precomputed` · `target` — the members of `mac.concept.column.measure_type` | what kind of quantity this is: the law's row |
| `unit` | string | **yes**, within `aggregate` | free prose — `USD`, `units`, `m2`, `to-currency per from-currency` | what the number is in. Two different units may not be combined |
| `canonical` | bool | no | `true` | **which** aggregate column is *the* one, when a concept carries several |

**The type licenses the fold; the unit licenses the comparison.** Both are declared once per measure and
read everywhere — [measures.md](measures.md) carries the type chapter, the worked contoso measures, and
what a unit does that a type cannot.

### `period_binding` — which date a bare period lands on

| value | card | says | read by |
|---|---|---|---|
| `true` | the only value | this is THE reporting date of the relation | `planner/plan.py`, `interpret/vocabulary.py` |

One per relation. The claim only matters where a relation carries several dates — and there it decides
the number: *"lines in 2025"* answers **37 708** or **37 616** depending which date is bound, and
nothing in the result says which. See §5.

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
one needs no question and gets none.

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
with no `axis` role is never consulted at all.

## 4 · What reads each role

Every role is reached through one function, so a bundle whose roles are declared is read by the
same code everywhere.

| asked | where | answers for | state |
|---|---|---|---|
| `framework.serves(role, use)` — does a column of this role serve this use | mac-runtime `mac_runtime/framework.py`, 8 call sites in 3 files | all five | ENFORCED |
| the groupable set a prompt OFFERS and a refusal LISTS | `planner/grounded_columns.py` | `axis` | ENFORCED |
| which column a fold lands on, and the fold's legality | `planner/plan.py`, `foldplane/law.py` (`ADDITIVITY_VIOLATION`) | `axis` + `aggregate` | ENFORCED |
| which date a bare period binds to | `planner/plan.py`, `interpret/vocabulary.py` | `period_binding` | ENFORCED |
| which column a MIN/MAX names, and whether to ask | `planner/plan.py` | `extremum` | ENFORCED |
| what `COUNT(DISTINCT …)` counts and what a join lands on | `concept.identity.canonical_key` — 22 read sites | `identity` | ENFORCED |
| the `roles` map as written above | — | — | PROPOSED 2026-10-07; see `status` and [column_specification.md](column_specification.md) |

## 5 · The constellations behind two of the roles

Two claims exist because of a named constellation. **The constellations are documented as patterns —
read them there, not here.**

| claim | the constellation | pattern |
|---|---|---|
| `period_binding: true` | one relation, several dates, each a different ROLE of the same calendar — `OrderDate` 2016-05-18..2025-12-31 and `DeliveryDate` ..2026-01-06, so *"lines in 2025"* answers **37 708** or **37 616** depending which is bound, and nothing in the result says which | [role_playing_dimension](patterns/dimensional_special_cases/role_playing_dimension.md) |
| `roles: {}` | a column with the shape of a perfectly good date axis — `StartDT`, 11 305 distinct over 104 990 rows — that records when the ROW was written, not when anything happened | *no pattern yet* |

**What this page adds that the pattern does not:** the pattern tells you what to do when you meet the
constellation. This page tells you which ROLES it resolves to, and §1 shows every column of two real
relations with its roles already assigned, so the shapes can be read off real data.

## 6 · Where `columns:` sits — a complete concept file

Roles are not a standalone block. This is `Customer`, structurally complete, abridged only in the prose
fields (`…`):

```yaml
# ontology/concepts/customer/customer.yaml
metadata:
  concept: Customer
  source: CONTOSO
  version: '1.0'
  schema_version: 0.1.14
  status: draft
  owner: operator
  confidence: I
  provenance: derived

concept:
  name: Customer
  label: Customer
  class: entity
  identity:
    kind: fk_name
    canonical_key: CustomerKey
  definition: >-
    A person who can place an order, served as the geography they belong to plus two
    generalised demographics. …
  semantics:
    purpose: >-
      …
contract:
  default_reading: >-
    …
  no_probe_guarantee: >-
    …
  rules:
    - id: customer.geography.rollup_only
      kind: mac.concept.rule.resolution
      subject: …
      when:  "a question groups customers by geography"
      then:  …
      never: …
      why:   …
      binds: [Country, Continent]
      confidence: P

grounding:
  kind: sql_table
  sources:
    - relation: dim_contoso_customer
      key: CustomerKey
  serves_from: data/transforms/dim_contoso_customer.sql

  columns:
    CustomerKey:  { roles: { identity: canonical } }
    GeoAreaKey:   { roles: { identity: reference } }
    StartDT:      { roles: {} }
    EndDT:        { roles: {} }
    Continent:    { roles: { axis: mac.concept.axis.categorical } }
    Country:      { roles: { axis: mac.concept.axis.categorical } }
    CountryFull:
      roles:   { axis: mac.concept.axis.categorical }
      rulings: { label_of: Country, register: long }
    State:
      roles:   { axis: mac.concept.axis.categorical }
      rulings: { scoped_by: Country }
    StateFull:
      roles:   { axis: mac.concept.axis.categorical }
      rulings: { label_of: State, register: long }
    City:         { roles: { axis: mac.concept.axis.categorical } }
    ZipCode:      { roles: { axis: mac.concept.axis.categorical } }
    Gender:       { roles: { axis: mac.concept.axis.categorical } }
    age_band_5y:  { roles: { axis: mac.concept.axis.categorical } }
```

`City` and `ZipCode` are axes of this warehouse and declare it. What may not be asked of them travels as
a rule under `contract.rules`, anchored by `binds` to the column it governs —
[column_rulings.md](column_rulings.md).

**What is NOT in `columns:`, and why.** `type` and measured cardinality come from
`data/datasets/dim_contoso_customer.yaml` and are merged at load. They are *measured*, not authored —
putting them here would create a second home for a fact the warehouse already states. `columns:` carries
only what a person declares: the roles, and any rulings.

## 7 · Claiming a role

Ask all five. Each answer is independent of the other four, so a column may leave with one role, three,
or none.

```
1. Does it identify a row — alone, with siblings, or over there?   → identity: canonical|composite|reference
2. Would a question group or filter by it?                         → axis: mac.concept.axis.time|categorical
3. Does adding two of its values mean something?                   → aggregate: {type, unit}
4. Is it THE date a bare period must bind to?                      → period_binding: true
5. Is its earliest or latest value something a question asks for?  → extremum: [min|max]
   None of the five                                                → roles: {}
```

**Anti-patterns**

- **`period_binding` on every date.** A relation with three dates has one reporting date; the others are
  ordinary `axis: time` columns. Marking them all makes the binding arbitrary.
- **An aggregate mistaken for an axis.** `UnitPrice` has 1 760 distinct values. That is not an invitation
  to group by it; `aggregate` and `axis` are different claims and a numeric payload is rarely both.
- **`roles: {}` used to hide an inconvenient column.** It means *not part of the business*, not
  *awkward*. A column someone might legitimately ask about is a declared role plus a rule that states
  its own reason.
- **A role claimed without its qualifier.** The qualifier *is* the value: `identity:` with nothing after
  it says which of three things?
- **`roles` omitted.** That is not `roles: {}`. One says *offered to nothing*; the other says *nobody has
  classified this column*, and they are different findings.

---

## 8 · The measured companion — `storage_role`

A column answers a second question that has nothing to do with a role: what SHAPE is it in the relation.

| column | storage_role | roles |
|---|---|---|
| `dim_contoso_store.StoreKey` | `primary_key` | `{identity: canonical}` |
| `dim_contoso_store.CountryCode` | `value` | `{axis: categorical}` |
| `v_contoso_order_line.CustomerKey` | `foreign_key` | `{identity: reference}` |
| `v_contoso_order_line.RowNumber` | `primary_key` + `key_position: 2` | `{identity: composite}` |
| `dim_contoso_store.Status` | `discriminator` | `{axis: categorical}` |

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

### The five role names — `mac.concept.column.query_use`

<!-- BEGIN GENERATED:vocabulary-terms:concept.column.roles (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

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
<!-- END GENERATED:vocabulary-terms:concept.column.roles -->

### The five role names are DERIVED, and have no chapter

`mac.concept.column.role` was retired from the vocabulary on 2026-10-07 and no column carries a
`role:` key. The five names — `key`, `dimension`, `measure`, `period`, `housekeeping` — are
computed from a column's `roles` map by `ColumnSpec.role` for one legacy reader,
`grounding.field_roles`, and the derivation reproduces all 112 of contoso5's previously-authored
values. Nothing declares them, so there is nothing here to generate.
