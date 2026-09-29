---
title: Column rulings — reference
status: PARTIALLY ENFORCED (2026-09-29) — the schema admits all four under grounding.sources[].columns.<col>.rulings
  (added 2026-09-28); mac-runtime READS label_of and finer_than (planner/sql.py) and never_axis (planner/plan.py
  POLICY_DENIED, interpret/vocabulary.py never offers it); scoped_by is LOADED, NOT PLANNED-ON (waived in
  test_declared_but_unread as a ticket). Per-ruling status is stated on each section below.
companions: [column_roles.md, column_specification.md, ../mac_vocabulary.yaml]
---

# Column rulings

A **ruling** is a judgement about a column that measurement cannot establish. Rulings are declared
under `rulings:` on a column and are always optional; a column with no rulings behaves as its
[role](column_roles.md) alone dictates.

```
SYNOPSIS
    columns:
      <column>:
        role: key | dimension | measure | period | housekeeping   # a bare mac.concept.column.role term
        rulings:
          label_of:   <column>
          register:   common | legal | long | short | code      # REQUIRES label_of (schema dependentRequired)
          finer_than: <column>
          scoped_by:  <column>
          never_axis: <the reason, one line of prose>          # free text; no privacy|grain|derived vocabulary exists
          evidence:   <dq-id>                                  # REQUIRED with never_axis (schema dependentRequired)
```

<!-- BEGIN GENERATED:vocabulary-terms:concept.column.ruling (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> An authored judgement about a column, beyond what measurement can establish.

*`mac.concept.column.ruling` · 4 terms · closed — these are all of them*

#### `mac.concept.column.ruling.label_of`

THIS COLUMN IS ANOTHER NAME FOR THE NAMED COLUMN'S THING, NOT ANOTHER THING. The argument is the
column it labels; `register` says WHICH of that thing's names this one is. Group on the named
column and DISPLAY this one: a question asking in these words gets answered in them, never
refused. Example: `Manufacturer` is the trade-register name of `Brand` — "Contoso" is what the
world calls it, "Contoso AG" is what the register calls it, and they are one company under two
naming registers. NOT a parent: had the column meant the OWNING company it would be one-to-many
and this ruling would be wrong. Cardinality cannot tell you which you have.

#### `mac.concept.column.ruling.finer_than`

THIS COLUMN DISTINGUISHES MORE MEMBERS than the named column, which it rolls up into. Both are
legitimate axes and an answer must DISCLOSE which level it used. Example: `SubCategoryName`
carries 32 values that roll up cleanly into `CategoryName`'s 8 — measured 32 distinct pairs over
32 subcategories, so every subcategory has exactly ONE parent and the roll-up cannot
double-count. THAT CLEAN N:1 IS THE TEST. A pair that merely differs in cardinality may be a
colliding code space instead — see `scoped_by`, and measure before you rule.

#### `mac.concept.column.ruling.scoped_by`

THIS COLUMN'S VALUES ARE ONLY UNIQUE WITHIN THE NAMED COLUMN, so it may not be grouped or
filtered on alone — the scope column must travel with it. Example: `State` carries 'CO' for
Corse in France, Como in Italy and Colorado in the United States. Measured on contoso: 40 of 563
state codes are carried by more than one country and 0 collide WITHIN a country, so `GROUP BY
State` silently merges three unrelated regions into one row that looks like data. NOT
`finer_than`: nothing here is a level of anything. It is one code space reused per parent, which
is the composite identity `mac.canon.composite_key_guard` exists to protect.

#### `mac.concept.column.ruling.never_axis`

THIS COLUMN MUST NOT BE GROUPED ON, for the stated reason, and `evidence` must name the
measurement that establishes it. A ruling made from a measurement must produce a REFUSAL THAT
CITES IT, never a silent success. Example: `ZipCode`, which alone singles out 29 193 of 104 990
served customers and is the dominant identifier in the row.
<!-- END GENERATED:vocabulary-terms:concept.column.ruling -->

---

# 1 · `label_of`

**Status: IMPLEMENTED.** Schema-admitted; read by mac-runtime `planner/sql.py` (the label is selected, the
named column grouped on, with a disclosure naming the register).

## Synopsis

```yaml
rulings:
  label_of: <column>
  register: common | legal | long | short | code      # optional, default: common
```

## Description

Declares that this column is **another name for the thing the named column identifies**, not a
different thing. The named column stays canonical: queries group and filter on it, and this column
supplies the words shown to the reader.

Without the ruling both columns are independent axes, and *"by X"* and *"by Y"* return the same
cut under different labels with nothing relating them.

## Parameters

| parameter | required | default | legal values | meaning |
|---|---|---|---|---|
| `label_of` | yes | — | a column of the same relation | the canonical column this one names |
| `register` | no | `common` | `common` · `legal` · `long` · `short` · `code` | which of the thing's names this column carries |

## When to use it — the constellation

Two columns, **equal distinct counts and an equal pair count**:

| measured over `dim_contoso_product` | |
|---|---:|
| distinct `Brand` | 11 |
| distinct `Manufacturer` | 11 |
| distinct pairs | **11** |

| `Brand` | `Manufacturer` | products |
|---|---|---:|
| A. Datum | A. Datum Corporation | 132 |
| Contoso | Contoso, Ltd | 710 |
| Fabrikam | Fabrikam, Inc. | 267 |
| Adventure Works | Adventure Works | 192 |

1:1 gets you to the door. **Only a person can say the two names denote one thing.** Contoso and
Contoso AG are one company in two registers; Northwind AG and Contoso are two companies, and that pair
would be one-to-many — a `key` pointing at a parent, not a label.

## What happens without it

| | |
|---|---|
| **Two answers to one question** | *by brand* → 11 rows. *by manufacturer* → 11 rows. Identical numbers, different labels, nothing says they are the same cut. |
| **Meaningless cross-product** | `GROUP BY Brand, Manufacturer` yields 11 rows where a reader expects 121, and reads as a data bug. |
| **Refusal instead of an answer** | Marking the second column never-an-axis refuses *"by manufacturer"* — a good question asked in the user's own words. |

## Examples

**Declaring it**

```yaml
# ontology/concepts/catalog/brand.yaml
grounding:
  columns:
    Brand:
      role: dimension
    Manufacturer:
      role: dimension
      rulings:
        label_of: Brand
        register: legal
```

**Asking for the label**

```
> revenue by manufacturer
```
```sql
SELECT p.Brand AS "Manufacturer", SUM(l.NetPrice) AS revenue
FROM   contoso_served.v_contoso_order_line l
JOIN   contoso_served.dim_contoso_product  p USING (ProductKey)
GROUP  BY p.Brand
```
| Manufacturer | revenue |
|---|---:|
| Contoso, Ltd | … |
| Fabrikam, Inc. | … |

> *grouped by Brand, shown as Manufacturer (legal register)*

**Filtering by the label**

```
> revenue for Contoso Ltd
```
```sql
WHERE p.Brand = 'Contoso'
```

**Chaining** — a label of a scoped column is scoped too:

```yaml
State:     { role: …dimension, rulings: { scoped_by: Country } }
StateFull: { role: …dimension, rulings: { label_of: State, register: long } }
```

## Errors

| condition | outcome |
|---|---|
| `label_of` names a column not in this relation | load refuses — a column is never assumed to exist |
| the pair is not 1:1 in the data | `check_column_rulings` reds: the ruling claims one thing, the data shows many |
| `register` is not a `mac.name_register` term | load refuses |

## See also

[`finer_than`](#2--finer_than) when the two columns are levels, not names ·
[column_roles.md](column_roles.md) ·
[patterns/competing_definitions.md](patterns/competing_definitions.md) for one term with several
*meanings*, which is the opposite problem

---

## The `register` argument

<!-- BEGIN GENERATED:vocabulary-terms:name_register (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> Which register a name belongs to, when one thing carries several names.

*`mac.name_register` · 5 terms · closed — these are all of them*

#### `mac.name_register.common`

The name people use. 'Contoso', 'Germany', 'Monday'.

#### `mac.name_register.legal`

The name in a trade or statutory register. 'Contoso AG', 'Contoso, Ltd'.

#### `mac.name_register.long`

The unabbreviated form of a coded name. 'United Kingdom' for GB.

#### `mac.name_register.short`

The abbreviated form. 'Mon' for Monday, 'Jan' for January.

#### `mac.name_register.code`

A machine identifier standing for the name. 'GB', 'DE', a numeric key.
<!-- END GENERATED:vocabulary-terms:name_register -->

---

# 2 · `finer_than`

**Status: IMPLEMENTED.** Schema-admitted; read by mac-runtime `planner/sql.py` (a disclosure that the finer of
two levels was used).

## Synopsis

```yaml
rulings:
  finer_than: <column>
```

## Description

Declares that this column distinguishes **more members** than the named column, and rolls up into
it. Both remain legal axes. The ruling makes the relationship explicit so an answer can disclose
which level it used, and so an ambiguous question can offer both.

## Parameters

| parameter | required | default | legal values | meaning |
|---|---|---|---|---|
| `finer_than` | yes | — | a column of the same relation | the coarser column this one rolls up into |

## When to use it — the constellation

N:1, and **the pair count equals the finer column's distinct count** — which is what proves every
child has exactly one parent:

| measured over `dim_contoso_product` | |
|---|---:|
| distinct `SubCategoryName` (finer) | 32 |
| distinct `CategoryName` (coarser) | 8 |
| distinct pairs | **32** |

| `CategoryName` | `SubCategoryName` |
|---|---|
| Audio | Bluetooth Headphones |
| Audio | MP4&MP3 |
| Audio | Recording Pen |
| Cameras and camcorders | Camcorders |

**`pairs == finer_distinct` is the whole test.** Higher, and a child has two parents — the roll-up
double-counts. If the columns merely differ in size, check [§3 `scoped_by`](#3--scoped_by) before
ruling.

## What happens without it

Both are axes with no stated relationship. *"By category"* returns 8 rows and *"by subcategory"* 32,
and a reader cannot tell whether the 32 sum to the 8. If a subcategory later acquires a second
parent the totals stop adding up, with no symptom.

## Examples

```yaml
grounding:
  columns:
    CategoryName:    { role: dimension }
    SubCategoryName:
      role: dimension
      rulings: { finer_than: CategoryName }
```

| you ask | plan | result |
|---|---|---|
| *sales by category* | `GROUP BY p.CategoryName` | 8 rows |
| *sales by subcategory* | `GROUP BY p.SubCategoryName` | 32 rows · *"the finer of two levels; rolls up into 8 categories"* |
| *sales by product line* | **CLARIFY** | *"which level — category (8) or subcategory (32)?"* |

## Errors

| condition | outcome |
|---|---|
| `pairs > finer_distinct` | `check_column_rulings` reds — a child with two parents; the roll-up would double-count |
| the two columns are mutually N:M | reds — this is not a hierarchy |

## See also

[patterns/recursive_hierarchy.md](patterns/recursive_hierarchy.md) when the hierarchy is a
self-reference rather than two columns

---

# 3 · `scoped_by`

**Status: LOADED, NOT PLANNED-ON.** Schema-admitted and parsed into `ColumnRulings` (mac-runtime
`ontology/models.py`), but no planner step reads it yet — waived in `test_declared_but_unread` as a ticket.
The protection this describes comes today from the `composite_key_guard` canon, not from this key.

## Synopsis

```yaml
rulings:
  scoped_by: <column>
```

## Description

Declares that this column's values are **unique only within the named column**. It may not be
grouped or filtered on alone; the scope column travels with it.

**The full treatment is [patterns/context_dependent_meaning.md](patterns/context_dependent_meaning.md)**
— *"a code meaningless without its parent"* — which is canonical for this constellation and is
enforced by the [`composite_key_guard`](canon/composite_key_guard.md) canon. `scoped_by` is the
column-level shorthand. If the two ever disagree, the pattern wins.

## When to use it — the constellation

| `State` | `Country` | `StateFull` | customers |
|---|---|---|---:|
| `CO` | FR | Corse | 37 |
| `CO` | IT | Como | 64 |
| `CO` | US | Colorado | 709 |
| `PA` | FR | Provence-Alpes-Côte d'Azur | 495 |
| `PA` | US | Pennsylvania | 2 017 |

| measured over `dim_contoso_customer` | |
|---|---:|
| distinct `State` codes | 563 |
| carried by **more than one** country | **40** |
| colliding **within** a country | **0** |

**Zero within, many across** is the signature. It separates a scoped code from a hierarchy, which
cardinality alone cannot.

## What happens without it

`GROUP BY State` puts Corse, Como and Colorado in one row labelled `CO`, totalling 810 customers.
The query succeeds, the row count is plausible, the number is meaningless. *"Customers in CO"*
returns French, Italian and American customers.

## Examples

```yaml
grounding:
  columns:
    Country: { role: dimension }
    State:
      role: dimension
      rulings: { scoped_by: Country }
```

| you ask | plan | result |
|---|---|---|
| *customers by state* | `GROUP BY c.Country, c.State` | 603 rows · *"Country added — State is scoped by it"* |
| *customers in CO* | **CLARIFY** | *"'CO' is carried by 3 countries — Corse (FR), Como (IT), Colorado (US)"* |
| *customers in Colorado* | `WHERE c.Country='US' AND c.State='CO'` | 709 — scope inferred from the label |

## Errors

| condition | outcome |
|---|---|
| the code is grouped or filtered without its scope | **REFUSE** — `composite_key_guard` |
| `scoped_by` declared where 0 codes actually collide | `check_column_rulings` warns — the guard costs a join for nothing |

---

# 4 · `never_axis`

**Status: IMPLEMENTED.** Refuses today with `POLICY_DENIED` (mac-runtime `planner/plan.py` `_axis_denied`,
citing `evidence`; `interpret/vocabulary.py` never offers the column as groupable). **The value is a
REASON in prose, not a code**: an earlier draft of this page proposed the closed set `privacy | grain |
derived`, no vocabulary has ever declared those three, and the schema admits a free string. Closing the
reason is an open question for the operator.

## Synopsis

```yaml
rulings:
  never_axis: <the reason, one line of prose>
  evidence:   <dq-id>                          # REQUIRED — schema dependentRequired
```

## Description

Declares that this column, though a legitimate dimension, **must not be used as an axis**. The
reason is outside the data, so the ruling carries both the reason (a sentence) and the measurement
that establishes it.

## Parameters

| parameter | required | default | legal values | meaning |
|---|---|---|---|---|
| `never_axis` | yes | — | free text — one line stating the reason | why it may not be an axis (quoted into the refusal) |
| `evidence` | **yes** | — | a DQ register id | the measurement. A prohibition without one is a preference. |

## When to use it — the constellation

Cardinality approaching the row count:

| measured over `dim_contoso_customer` | |
|---|---:|
| customers | 104 990 |
| distinct `ZipCode` | 40 639 |
| postcodes held by **exactly one** customer | **29 193** |

`City` is the same shape at 34 581 distinct.

## What happens without it

`GROUP BY ZipCode` plans, executes, and returns 29 193 rows that each describe one person. The
query is valid; the ontology's own measurement forbids it; nothing connects the two.

## Examples

```yaml
grounding:
  columns:
    ZipCode:
      role: dimension
      rulings:
        never_axis: "identifies a person — 29 193 of 104 990 values are held by exactly one customer"
        evidence: DQ-CUSTOMER-02
```

```
> customers by postcode
```
```
REFUSED (POLICY_DENIED)
Customer.ZipCode is declared `never_axis` ("identifies a person") — DQ-CUSTOMER-02 measured that
29 193 of 40 639 postcodes are held by exactly one customer, so grouping on it names
individuals. Customer can be grouped by: Continent, Country, Gender, State, age_band_5y.
```

## Errors

| condition | outcome |
|---|---|
| `never_axis` without `evidence` | load refuses |
| `evidence` names no entry in the DQ register | `check_dq_resolution_sync` reds |

## See also

[patterns/junk_dimension.md](patterns/junk_dimension.md) ·
[patterns/degenerate_dimension.md](patterns/degenerate_dimension.md)

---

# Choosing between them

Run this before ruling:

```sql
SELECT count(DISTINCT a)      AS a_distinct,
       count(DISTINCT b)      AS b_distinct,
       count(DISTINCT (a, b)) AS pairs
FROM   <relation>
```

| measurement | ruling | the thing measurement cannot tell you |
|---|---|---|
| `a = b = pairs` | [`label_of`](#1--label_of) | whether the two names denote one thing or two |
| `pairs = a`, `a > b` | [`finer_than`](#2--finer_than) | — this one is safe to read off the data |
| `pairs > a` **and** `pairs > b` | [`scoped_by`](#3--scoped_by) | — also safe: check collisions within vs across |
| cardinality ≈ row count | [`never_axis`](#4--never_axis) | whether the identification matters |

**`scoped_by` mistaken for `finer_than` is the expensive error**: it merges unrelated members and
nothing in the result betrays it.
