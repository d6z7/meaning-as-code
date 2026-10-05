---
title: Column Roles — what a column IS, and where a query may use it
status: ENFORCED (2026-09-29) — the `columns:` map is admitted by mac.schema.json (v0.1.16) with `role` closed to
  the vocabulary's five terms (re-closed 2026-09-29; `attribute` retired), and mac-runtime's parser reads it
  (ontology/parser.py projects it to field_roles; an explicit field_roles block still wins). §2B's storage
  role is measured, not authored.
audience: ontology authors, importer developers
companions:
  - column_rulings.md        # what a PERSON decided about a column, on top of its role
  - shape_reference.md       # where `columns:` nests in a concept file
  - ../mac_vocabulary.yaml   # the authoritative terms; definitions below are generated from it
---

# Column roles

Every column a concept binds carries **exactly one role**, and the role decides where a query may
use it. It is the first thing declared about a column and the only required one.

> **A role is READ, not decided.** All five are derivable from cardinality, type and reference
> structure — which is why a generator assigns them over a thousand columns with no human present.
> If you find yourself *deciding* rather than *reading*, you are holding a **ruling**, not a role.
> See [column_rulings.md](column_rulings.md).

---

## 1. Two real tables, every column assigned

This is a fact and a dimension from the same warehouse. Every column, its type, its measured
cardinality, and the role that follows.

### `v_contoso_order_line` — the FACT, 223 974 rows

| column | type | distinct | role | why this role |
|---|---:|---:|---|---|
| `OrderKey` | BIGINT | 93 470 | `key` | foreign key to the order header |
| `RowNumber` | INTEGER | 7 | `key` | the other half of the grain: `(OrderKey, RowNumber)` is unique, neither is alone |
| `OrderDate` | DATE | 3 450 | **`period`** | THE reporting date — see §3 |
| `DeliveryDate` | DATE | 3 498 | `dimension` | a real date, askable by name, never the default |
| `CustomerKey` | INTEGER | 52 189 | `key` | FK → `dim_contoso_customer` |
| `StoreKey` | INTEGER | 64 | `key` | FK → `dim_contoso_store` |
| `ProductKey` | INTEGER | 2 517 | `key` | FK → `dim_contoso_product` |
| `CurrencyCode` | VARCHAR | 5 | `dimension` | 5 members, a legitimate axis |
| `Quantity` | INTEGER | 10 | `measure` | numeric payload, additive |
| `UnitPrice` | DECIMAL | 1 760 | `measure` | numeric payload — **not** an axis, despite 1 760 values |
| `NetPrice` | DECIMAL | 18 407 | `measure` | numeric payload |
| `UnitCost` | DECIMAL | 1 955 | `measure` | numeric payload |

**Read the FK shape:** many rows, far fewer distinct values, and every value present in a parent
relation. `StoreKey` has 64 distinct over 223 974 rows — that is a pointer, not a category, even
though its cardinality looks dimension-sized.

### `dim_contoso_customer` — the DIMENSION, 104 990 rows

| column | type | distinct | role | ruling | why |
|---|---:|---:|---|---|---|
| `CustomerKey` | INTEGER | **104 990** | `key` | — | distinct **equals** row count: the identity |
| `GeoAreaKey` | INTEGER | 608 | `key` | — | a reference — and one with no parent relation in this delivery, recorded as dangling |
| `StartDT` | DATE | 11 305 | **`housekeeping`** | — | when the ROW was written |
| `EndDT` | DATE | 14 711 | **`housekeeping`** | — | SCD-2 validity window |
| `Continent` | VARCHAR | 3 | `dimension` | — | |
| `Country` | VARCHAR | 8 | `dimension` | — | the canonical geography code |
| `CountryFull` | VARCHAR | 8 | `dimension` | `label_of: Country` | 1:1 — the same 8 countries, spelled out |
| `State` | VARCHAR | 563 | `dimension` | `scoped_by: Country` | 40 codes are reused across countries |
| `StateFull` | VARCHAR | 608 | `dimension` | `label_of: State` | |
| `City` | VARCHAR | 34 581 | `dimension` | `never_axis` | 1 in 3 rows would be its own group |
| `ZipCode` | VARCHAR | 40 639 | `dimension` | `never_axis` | 29 193 postcodes held by exactly one customer |
| `Gender` | VARCHAR | 2 | `dimension` | — | |
| `age_band_5y` | INTEGER | 15 | `dimension` | — | derived by the transform, served as an ordinary column |

**Notice what cardinality alone cannot tell you.** `CountryFull` (8) and `Country` (8) look
identical. `City` (34 581) and `CustomerKey` (104 990) are both high. `StartDT` (11 305) looks
exactly like a date dimension. In each case the role — or the ruling on top of it — comes from
something the numbers do not contain.

### Reading a role off the data

| what you measure | role |
|---|---|
| distinct **equals** row count, no nulls | `key` — the primary identity |
| many rows, few distinct, every value present in a parent | `key` — a reference |
| distinct far below row count, categorical, repeated | `dimension` |
| numeric payload, no identity, summable | `measure` |
| a date, and **the** one a period filter should bind to | `period` |
| exists for the pipeline; nobody would ask about it | `housekeeping` |

---

## 2. The terms

<!-- BEGIN GENERATED:vocabulary-terms:concept.column.role (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> The analytical role of a column — where a query may use it, and the default guardrail.

*`mac.concept.column.role` · 5 terms · closed — these are all of them*

#### `mac.concept.column.role.key`

IDENTITY OR JOIN COLUMN. A name resolves TO it through a register; a query then filters or joins
on the exact value. Never matched against a label, and never aggregated — an identifier that is
summed is a number nobody asked for. Example: `CustomerKey`, what COUNT(DISTINCT) counts and
what the fact joins on.

| field | value |
|---|---|
| `query_use` | identity |
| `constellation` | A NAME MUST RESOLVE TO AN EXACT VALUE BEFORE ANYTHING CAN BE FILTERED OR JOINED ON IT. Reach for it when the column is what a join lands on or what a distinct count counts — and never let it be summed: an identifier that is totalled is a number nobody asked for.
 |

#### `mac.concept.column.role.dimension`

A CATEGORICAL AXIS — legitimate in WHERE and in GROUP BY. Its value domain is either CLOSED (a
register states every member, so a non-member is answerable without probing) or OPEN (names
resolve through the ladder: exact, normalized, prefix, fuzzy, then ask). Example: `Gender` —
`WHERE Gender = 'female'` and `GROUP BY Gender` are both legitimate.

| field | value |
|---|---|
| `query_use` | axis, extremum |
| `constellation` | A QUESTION WILL LEGITIMATELY BOTH FILTER ON THE COLUMN AND GROUP BY IT. `WHERE gender = 'female'` and `GROUP BY gender` are both reasonable, which is the test. If only one of the two is reasonable, the column is probably a key or a measure wearing a dimension's name.
 |

#### `mac.concept.column.role.measure`

A NUMERIC PAYLOAD. Folded only as its mac.measure_type and the axis allow — the law is stated
once there and never restated per concept. Never filtered on directly: a threshold on a measure
is a HAVING over the aggregate, not a WHERE over the column. Example: `SalesAmount`.

| field | value |
|---|---|
| `query_use` | aggregate, extremum |
| `constellation` | ADDING TWO OF ITS VALUES MEANS SOMETHING. That is the whole test and it is not about the datatype. The corollary matters as much: a threshold on a measure is a HAVING over the aggregate, never a WHERE over the column, so declaring this also declares where a filter may not go.
 |

#### `mac.concept.column.role.period`

THE COLUMN A QUESTION'S PERIOD BINDS TO. It says which date is THE reporting date when a
relation carries several, so "sales in March" cannot silently pick the wrong one. Example:
`OrderDate` on a line that also carries `DeliveryDate`.

| field | value |
|---|---|
| `query_use` | axis, extremum, period_binding |
| `constellation` | THE RELATION CARRIES MORE THAN ONE DATE AND "SALES IN MARCH" HAS TO PICK ONE. An order line with an order date and a delivery date is the compelling case: both are dates, both are plausible, and the question does not say. This names which one is THE reporting date so the choice is not made silently.
 |

#### `mac.concept.column.role.housekeeping`

PIPELINE BOOKKEEPING, NOT BUSINESS VOCABULARY — validity windows, load stamps, surrogate
housekeeping. It is not offered to a question, not grouped on, not filtered on, and its absence
from an answer is correct rather than a gap. Example: `StartDT`/`EndDT`, an SCD-2 validity
window — when the ROW was written, not when anything happened. Grouping sales by it is
meaningless, and until this term existed it was spelled `attribute`, which reads as "a dimension
you may not use" rather than "not part of the business at all". NAMED FOR THE MODELLING
TRADITION that already has a word for these columns, rather than for the system that writes
them: a load stamp is housekeeping whoever keeps the house.

| field | value |
|---|---|
| `query_use` | none |
| `constellation` | THE COLUMN RECORDS WHEN THE ROW WAS WRITTEN RATHER THAN WHEN ANYTHING HAPPENED. A validity window on a versioned dimension is the case: grouping sales by the row's own start date is meaningless, but nothing in the data says so, and the column is a perfectly good date. Declaring it keeps the column out of a question's reach entirely — its absence from an answer is correct rather than a gap.
 |
<!-- END GENERATED:vocabulary-terms:concept.column.role -->

---

## 2A. The machine-readable half of a role — `query_use`

Each role above carries a `query_use` list, and the table under each term prints it. Those values are
not free text: they are the terms of `mac.concept.column.query_use`, which is what a planner reads
when it decides whether a column may become a `GROUP BY`, a `SUM`, a period binding or an `ORDER BY`.
The role is the word a person writes; `query_use` is the part a program acts on. One is derivable from
the other, which is why the role is the only thing authored.

`housekeeping` has an EMPTY `query_use`, and that is a value, not an omission: a question may use it
nowhere.

<!-- BEGIN GENERATED:vocabulary-terms:concept.column.query_use (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> Where a question may use a column — the machine-readable half of concept.column.role.

*`mac.concept.column.query_use` · 5 terms · closed — these are all of them*

#### `mac.concept.column.query_use.axis`

LEGITIMATE IN A FILTER AND IN A GROUP BY. The column names a thing a question can slice by. A
per-column `rulings.never_axis` still overrides this with its own measurement: the role says the
KIND of column may be an axis, the ruling says this ONE may not.

#### `mac.concept.column.query_use.aggregate`

A NUMBER A QUESTION MAY FOLD. HOW it folds is not stated here and must not be: it is
`concept.column.measure_type` x `concept.axis_kind` -> `aggregation_effect`, read through
`framework.vocabulary().additivity`. A column carrying this use whose every additivity cell is
`none` — `precomputed`, `target` — is foldable by nothing, and that is the measure type's
ruling, not this one's.

#### `mac.concept.column.query_use.period_binding`

THE COLUMN A QUESTION'S PERIOD BINDS TO. Says which date is THE reporting date when a relation
carries several, so "sales in March" cannot silently pick the wrong one.

#### `mac.concept.column.query_use.extremum`

THE EARLIEST OR LATEST VALUE THE COLUMN HOLDS may be asked for -- `min`/`max`, which is what a
"when did X first ..." question wants. NOT A FOLD, and that is why it is a separate use rather
than a corner of `aggregate`: an extremum PICKS one value that exists in the data instead of
combining several, so it answers to no additivity cell and is meaningful on a column no law
would let anyone SUM. A date axis therefore admits it while remaining non-aggregatable.

#### `mac.concept.column.query_use.identity`

WHAT THE ROW IS, FOR JOINING AND COUNTING. Filtered on an exact value a register resolved to,
joined on, and what COUNT(DISTINCT) counts — never matched against a label and never aggregated,
an identifier that is summed being a number nobody asked for.
<!-- END GENERATED:vocabulary-terms:concept.column.query_use -->

---

## 2B. The other role every column carries — `storage_role`

A column carries **two** roles, and they answer different questions. `column_role` says what a
QUERY may do with it; `storage_role` says what SHAPE it is in the relation.

| column | storage_role | column_role |
|---|---|---|
| `dim_contoso_store.StoreKey` | `primary_key` | `key` |
| `dim_contoso_store.CountryCode` | `value` | `dimension` |
| `v_contoso_order_line.CustomerKey` | `foreign_key` | `key` |
| `v_contoso_order_line.RowNumber` | `primary_key` + `key_position: 2` | `key` |
| `dim_contoso_store.Status` | `discriminator` | `dimension` |

(`composite_key_part` was retired 2026-09-27: every key column is `primary_key` and its place in a
composite key is the integer `key_position` — see `mac.relation.column.role`.)

**You never author this one.** It is measured — the profile plane counts distinct values and nulls,
the reference plane measures inclusion against candidate parents, and
`data/datasets/<relation>.yaml` records what they found. If you are hand-writing a `storage_role`,
something upstream failed.

<!-- BEGIN GENERATED:vocabulary-terms:relation.column.role (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> The physical shape of a column in its relation, independent of its analytical role.

*`mac.relation.column.role` · 6 terms · closed — these are all of them*

#### `mac.relation.column.role.primary_key`

The relation's own identity: one row per distinct value, measured rather than assumed.

#### `mac.relation.column.role.foreign_key`

A reference to another relation's identity. Whether every value is PRESENT in the parent is a
separate measurement — a declared key says the relationship is intended, not that it holds.

#### `mac.relation.column.role.value`

A payload column: it carries data, not identity and not a choice of row kind.

#### `mac.relation.column.role.discriminator`

A column whose value selects WHICH KIND of row this is — the column a perspective, status or
type is read from.

#### `mac.relation.column.role.audit`

A column recording WHEN THE ROW WAS WRITTEN or by what, rather than anything that happened in
the business. A load timestamp, a batch id, a validity window on a versioned row. It is
physically a payload column, and naming it apart is what keeps it out of a question's reach:
grouping a measure by the row's own write time is meaningless, and nothing in the data says so.

#### `mac.relation.column.role.delivery_axis`

A column the DELIVERY partitions or orders by, carried for the pipeline's sake rather than for a
question. `mac_admit_identity.py` assigns it to a column an SME has ruled is not the relation's
identity but which the load still keys on — so the key survives as a physical fact without
claiming to be the concept's identity.
<!-- END GENERATED:vocabulary-terms:relation.column.role -->

### Anti-patterns

**`composite_key_part` used as though it were a key.** It identifies nothing alone. A query
filtering on one part of a composite identity returns a **set** where a row was expected, and looks
like it returned an answer. That is what [`composite_key_guard`](canon/context_dependent_meaning/composite_key_guard.md)
catches.

**A `foreign_key` assumed to be present.** Declaring the reference says it is *intended*.
Containment — whether every child value exists in the parent — is a separate measurement, and the
reference plane records dangling references AS dangling rather than dropping them.
`Customer.GeoAreaKey` is exactly that: 608 distinct values and no parent relation in this delivery.

---

## 3. The two roles with a pattern behind them

Two of the five roles exist because of a named constellation. **Those constellations are documented
as patterns — read them there, not here.**

| role | the constellation | pattern |
|---|---|---|
| `period` | one relation, several dates, each a different ROLE of the same calendar — `OrderDate` 2016-05-18..2025-12-31 and `DeliveryDate` ..2026-01-06, so *"lines in 2025"* answers **37 708** or **37 616** depending which is bound, and nothing in the result says which | [role_playing_dimension](patterns/role_playing_dimension.md) |
| `housekeeping` | a column with the shape of a perfectly good date dimension — `StartDT`, 11 305 distinct over 104 990 rows — that records when the ROW was written, not when anything happened | *no pattern yet* |

**What this page adds that the pattern does not:** the pattern tells you what to do when you meet
that constellation. This page tells you which ROLE it resolves to, and §1 shows you every column of
two real relations with its role already assigned, so you can read the shapes off real data.

## 5. Where `columns:` sits — a complete concept file

Roles are not a standalone block. This is `Customer`, structurally complete, abridged only in the
prose fields (`…`):

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
    CustomerKey:  { role: key }
    GeoAreaKey:   { role: key }
    StartDT:      { role: housekeeping }
    EndDT:        { role: housekeeping }
    Continent:    { role: dimension }
    Country:      { role: dimension }
    CountryFull:
      role: dimension
      rulings: { label_of: Country, register: long }
    State:
      role: dimension
      rulings: { scoped_by: Country }
    StateFull:
      role: dimension
      rulings: { label_of: State, register: long }
    City:
      role: dimension
      rulings: { never_axis: "identifies a person (with ZipCode)", evidence: DQ-CUSTOMER-02 }
    ZipCode:
      role: dimension
      rulings: { never_axis: "identifies a person — 29 193 of 104 990 values held by one customer", evidence: DQ-CUSTOMER-02 }
    Gender:       { role: dimension }
    age_band_5y:  { role: dimension }

```

**What is NOT in `columns:`, and why.** `type` and measured cardinality come from
`data/datasets/dim_contoso_customer.yaml` and are merged at load. They are *measured*, not
authored — putting them here would create a second home for a fact the warehouse already states.
`columns:` carries only what a person declares: the role, and any rulings.

---

## 6. Choosing, in order

```
1. Would anyone ever ask a question about this column?      no  → housekeeping
2. Does it identify a row, or point at one?                 yes → key
3. Is it a number you would add up?                         yes → measure
4. Is it THE date a period filter should bind to?           yes → period
5. Otherwise                                                    → dimension
```

**Anti-patterns**

- **`period` on every date.** A relation with three dates has one reporting date; the others are
  dimensions. Marking them all makes the binding arbitrary.
- **`measure` mistaken for an axis.** `UnitPrice` has 1 760 distinct values. That is not an
  invitation to group by it.
- **`housekeeping` used to hide an inconvenient column.** It means *not part of the business*, not
  *awkward*. A column someone might legitimately ask about is a `dimension` carrying a ruling — and
  the ruling states its reason.
- **`attribute`.** It is gone. It was four different judgements wearing one word, and no generator
  ever assigned it because all four are authored. They live in
  [column_rulings.md](column_rulings.md).
