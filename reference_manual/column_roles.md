---
title: Column Roles — what a column IS, and where a query may use it
status: DRAFT — the shape is specified; `housekeeping` and the `columns:` block are not yet implemented
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

#### `mac.concept.column.role.dimension`

A CATEGORICAL AXIS — legitimate in WHERE and in GROUP BY. Its value domain is either CLOSED (a
register states every member, so a non-member is answerable without probing) or OPEN (names
resolve through the ladder: exact, normalized, prefix, fuzzy, then ask). Example: `Gender` —
`WHERE Gender = 'female'` and `GROUP BY Gender` are both legitimate.

#### `mac.concept.column.role.measure`

A NUMERIC PAYLOAD. Folded only as its mac.measure_type and the axis allow — the law is stated
once there and never restated per concept. Never filtered on directly: a threshold on a measure
is a HAVING over the aggregate, not a WHERE over the column. Example: `SalesAmount`.

#### `mac.concept.column.role.period`

THE COLUMN A QUESTION'S PERIOD BINDS TO. It says which date is THE reporting date when a
relation carries several, so "sales in March" cannot silently pick the wrong one. Example:
`OrderDate` on a line that also carries `DeliveryDate`.

#### `mac.concept.column.role.housekeeping`

PIPELINE BOOKKEEPING, NOT BUSINESS VOCABULARY — validity windows, load stamps, surrogate
housekeeping. It is not offered to a question, not grouped on, not filtered on, and its absence
from an answer is correct rather than a gap. Example: `StartDT`/`EndDT`, an SCD-2 validity
window — when the ROW was written, not when anything happened. Grouping sales by it is
meaningless, and until this term existed it was spelled `attribute`, which reads as "a dimension
you may not use" rather than "not part of the business at all". NAMED FOR THE MODELLING
TRADITION that already has a word for these columns, rather than for the system that writes
them: a load stamp is housekeeping whoever keeps the house.
<!-- END GENERATED:vocabulary-terms:concept.column.role -->

---

## 2B. The other role every column carries — `storage_role`

A column carries **two** roles, and they answer different questions. `column_role` says what a
QUERY may do with it; `storage_role` says what SHAPE it is in the relation.

| column | storage_role | column_role |
|---|---|---|
| `dim_contoso_store.StoreKey` | `primary_key` | `key` |
| `dim_contoso_store.CountryCode` | `value` | `dimension` |
| `v_contoso_order_line.CustomerKey` | `foreign_key` | `key` |
| `v_contoso_order_line.RowNumber` | `composite_key_part` | `key` |
| `dim_contoso_store.Status` | `discriminator` | `dimension` |

**You never author this one.** It is measured — the profile plane counts distinct values and nulls,
the reference plane measures inclusion against candidate parents, and
`data/datasets/<relation>.yaml` records what they found. If you are hand-writing a `storage_role`,
something upstream failed.

<!-- BEGIN GENERATED:vocabulary-terms:relation.column.role (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> The physical shape of a column in its relation, independent of its analytical role.

*`mac.relation.column.role` · 4 terms · closed — these are all of them*

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
<!-- END GENERATED:vocabulary-terms:relation.column.role -->

### Anti-patterns

**`composite_key_part` used as though it were a key.** It identifies nothing alone. A query
filtering on one part of a composite identity returns a **set** where a row was expected, and looks
like it returned an answer. That is what [`composite_key_guard`](canon/composite_key_guard.md)
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
    null_semantics: >-
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
    CustomerKey:  { role: mac.column_role.key }
    GeoAreaKey:   { role: mac.column_role.key }
    StartDT:      { role: mac.column_role.housekeeping }
    EndDT:        { role: mac.column_role.housekeeping }
    Continent:    { role: mac.column_role.dimension }
    Country:      { role: mac.column_role.dimension }
    CountryFull:
      role: mac.column_role.dimension
      rulings: { label_of: Country, register: long }
    State:
      role: mac.column_role.dimension
      rulings: { scoped_by: Country }
    StateFull:
      role: mac.column_role.dimension
      rulings: { label_of: State, register: long }
    City:
      role: mac.column_role.dimension
      rulings: { never_axis: privacy, evidence: DQ-CUSTOMER-02 }
    ZipCode:
      role: mac.column_role.dimension
      rulings: { never_axis: privacy, evidence: DQ-CUSTOMER-02 }
    Gender:       { role: mac.column_role.dimension }
    age_band_5y:  { role: mac.column_role.dimension }

open_questions:
  - id: CUS-Q1
    topic: versioning
    question: >-
      …
    status: OPEN
    owner_for_resolution: operator
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
