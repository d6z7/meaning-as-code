---
title: Column rulings — reference
status: >-
  The schema admits all five under `grounding.sources[].columns.<col>.rulings`, and `register` requires
  `label_of` (`dependentRequired`). READ by mac-runtime `planner/sql.py`: `label_of` + `register` (the
  label is selected, the named column grouped on, with a disclosure naming the register), `finer_than`
  (a disclosure that the finer level was used) and `sort` (`column_sort` → the ORDER BY this column
  contributes). `scoped_by` is LOADED, NOT PLANNED-ON (`ontology/models.py` `ColumnRulings`) — the
  protection it describes comes today from the `composite_key_guard` canon. The prohibition route of
  §"When the judgement is a prohibition" is PROPOSED (2026-10-07): no canon realizes an axis prohibition
  yet, and a contract rule has no dedicated key for the DQ id it cites. Per-ruling status is on each
  section below.
audience: ontology authors, importer developers
companions: [column_declaration.md, column_roles.md, column_specification.md, ../mac_vocabulary.yaml]
---

# Column rulings

A **ruling** is a judgement about a column that measurement cannot establish. Rulings are declared
under `rulings:` on a column and are always optional; a column with no rulings behaves as its
[roles](column_roles.md) alone dictate.

```
SYNOPSIS
    columns:
      <column>:
        roles: { … }                                     # what a question may DO with it — column_roles.md
        rulings:
          label_of:   <column>
          register:   common | legal | long | short | code      # REQUIRES label_of (schema dependentRequired)
          finer_than: <column>
          scoped_by:  <column>
          sort:       asc | desc | none
```

## The five rulings

| ruling | value | required | says | the measurement that gets you to the door | read by |
|---|---|---|---|---|---|
| `label_of` | a column of the same relation | — | I am **another name for that column's thing**, not another thing — group on it, display me | `a = b = pairs` | `planner/sql.py` |
| `register` | `common` · `legal` · `long` · `short` · `code` | **with `label_of`** | **which** of that thing's names I carry | — only a person can say | `planner/sql.py`, in the disclosure |
| `finer_than` | a column of the same relation | — | I distinguish **more members** than that column and roll up into it; both are legitimate axes and an answer must disclose which level it used | `pairs = finer_distinct` | `planner/sql.py` |
| `scoped_by` | a column of the same relation | — | my values are unique **only within** that column, so I may not be grouped or filtered alone — the scope must travel with me | 0 collisions within, many across | loaded (`ontology/models.py`); enforced today by `composite_key_guard` |
| `sort` | `asc` · `desc` · `none` | — | the order my values are presented in when the question states none | **none — and that is the point:** SQL guarantees no row order without `ORDER BY` | `planner/sql.py` `column_sort` |

### Two keys spelled `register`

| key | value | says |
|---|---|---|
| `register:` on the column | a lookup path | where this column's VALUES come from — the register a name resolves through |
| `rulings.register` | a `mac.name_register` term | **which of the thing's names** this column carries |

<!-- BEGIN GENERATED:vocabulary-terms:concept.column.ruling (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> An authored judgement about a column, beyond what measurement can establish.

*`mac.concept.column.ruling` · 5 terms · closed — these are all of them*

#### `mac.concept.column.ruling.label_of`

THIS COLUMN IS ANOTHER NAME FOR THE NAMED COLUMN'S THING, NOT ANOTHER THING. The argument is the
column it labels; `register` says WHICH of that thing's names this one is. Group on the named
column and DISPLAY this one: a question asking in these words gets answered in them, never
refused. Example: `Manufacturer` is the trade-register name of `Brand` — "Contoso" is what the
world calls it, "Contoso, Ltd" is what the register calls it, and they are one company under two
naming registers. NOT a parent: had the column meant the OWNING company it would be one-to-many
and this ruling would be wrong. Cardinality cannot tell you which you have.

| field | value |
|---|---|
| `constellation` | TWO COLUMNS ARE 1:1 AND ONE IS THE OTHER'S NAME. Cardinality is symmetric so the data cannot say which direction it runs; a person must. Getting it backwards produces an answer with the wrong column as its axis rather than an error.
 |

#### `mac.concept.column.ruling.finer_than`

THIS COLUMN DISTINGUISHES MORE MEMBERS than the named column, which it rolls up into. Both are
legitimate axes and an answer must DISCLOSE which level it used. Example: `SubCategoryName`
carries 32 values that roll up cleanly into `CategoryName`'s 8 — measured 32 distinct pairs over
32 subcategories, so every subcategory has exactly ONE parent and the roll-up cannot
double-count. THAT CLEAN N:1 IS THE TEST. A pair that merely differs in cardinality may be a
colliding code space instead — see `scoped_by`, and measure before you rule.

| field | value |
|---|---|
| `constellation` | TWO DIMENSIONS ARE A HIERARCHY AND THE ROWS SHOW ONLY A CORRELATION. Every sub-category sits in exactly one category, so the coarser question is answerable from the finer rows and not the reverse — a containment that is a business fact, not a measurable one.
 |

#### `mac.concept.column.ruling.scoped_by`

THIS COLUMN'S VALUES ARE ONLY UNIQUE WITHIN THE NAMED COLUMN, so it may not be grouped or
filtered on alone — the scope column must travel with it. Example: `State` carries 'CO' for
Corse in France, Como in Italy and Colorado in the United States. measured on a worked bundle:
40 of 563 state codes are carried by more than one country and 0 collide WITHIN a country, so
`GROUP BY State` silently merges three unrelated regions into one row that looks like data. NOT
`finer_than`: nothing here is a level of anything. It is one code space reused per parent, which
is the composite identity `mac.canon.composite_key_guard` exists to protect.

| field | value |
|---|---|
| `constellation` | A CODE IS UNIQUE ONLY INSIDE ITS PARENT, AND THE COLLISION IS SILENT. Measured: 40 of 565 state codes repeat across countries, so grouping on state merges regions and still returns a plausible table.
 |

#### `mac.concept.column.ruling.sort`

THE ORDER THIS COLUMN'S VALUES ARE PRESENTED IN when the question states none. `asc` is
alphanumeric / smallest-first and is the reading for a NAME; `desc` is largest-first and is the
reading for a MAGNITUDE; `none` means this column is never an ordering key. PER COLUMN AND NEVER
PER CONCEPT -- operator ruling, 2026-10-02: "it must be sort per column and not concept" --
because one breakdown legitimately wants `brand asc`, `country_code asc` and `net_amount desc`
at the same time. NOT A FORMATTING PREFERENCE, WHICH IS WHY IT IS A RULING. SQL guarantees NO
row order without ORDER BY, so an unordered answer is not a reading of the question: it is
whatever the engine happened to emit, and it changes between runs. MEASURED 2026-10-02 on AGG-15
("net revenue by brand and customer country for 2024"), an 88-row breakdown -- the grader
compares the approved rows against the capture's first 50, WHICH 50 depended on unordered
output, and the question passed and failed on alternate runs with the data unchanged. An
ordering is also what makes a truncated view honest: the first N rows of a descending measure
are the N that matter. A COLUMN THAT DECLARES NOTHING falls to
query_grammar.yaml#projection.default_ordering (an aggregate desc, a bare list asc on its slice
columns), and `Intent.ordering` -- the reader's own words, "top 5 by price" -- outranks both.

| field | value |
|---|---|
| `constellation` | THE READER WILL SCAN THE ROWS IN ORDER AND NOBODY SAID WHAT THE ORDER IS. SQL promises none without ORDER BY, so the answer changes between runs on unchanged data — measured, on an 88-row breakdown that passed and failed alternately.
 |

#### `mac.concept.column.ruling.never_axis`

THIS COLUMN MUST NOT BE GROUPED ON, for the stated reason, and `evidence` must name the
measurement that establishes it. A ruling made from a measurement must produce a REFUSAL THAT
CITES IT, never a silent success. Example: `ZipCode`, which alone singles out 29 193 of 104 990
served customers and is the dominant identifier in the row.

| field | value |
|---|---|
| `constellation` | GROUPING BY THE COLUMN WOULD RETURN ONE ROW PER INSTANCE. Measured: 29,193 of 104,990 postcodes identify a single customer. The query is legal and the result is a customer list pretending to be a breakdown.
 |
<!-- END GENERATED:vocabulary-terms:concept.column.ruling -->

**A prohibition is not a ruling.** A ruling relates a column to another column. A judgement that a
column may not be used a particular way leaves the column unchanged and lives in a contract rule —
[When the judgement is a prohibition](#when-the-judgement-is-a-prohibition).

---

# 1 · `label_of`

**Status: READ** — `planner/sql.py` selects the label, groups on the named column, and discloses the
register it showed.

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
Contoso, Ltd are one company in two registers; Fabrikam Group and Contoso are two companies, and
that pair would be one-to-many — an `identity: reference` pointing at a parent, not a label.

## What happens without it

| | |
|---|---|
| **Two answers to one question** | *by brand* → 11 rows. *by manufacturer* → 11 rows. Identical numbers, different labels, nothing says they are the same cut. |
| **Meaningless cross-product** | `GROUP BY Brand, Manufacturer` yields 11 rows where a reader expects 121, and reads as a data bug. |
| **A refusal instead of a redirect** | Prohibiting the second column as an axis refuses *"by manufacturer"* — a good question asked in the reader's own words. The right behaviour is to group on `Brand` and DISPLAY `Manufacturer`, which is what this ruling buys. |

## Examples

**Declaring it**

```yaml
# ontology/concepts/catalog/brand.yaml
grounding:
  columns:
    Brand:
      roles: { axis: mac.concept.axis.categorical }
    Manufacturer:
      roles: { axis: mac.concept.axis.categorical }
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
State:     { roles: { axis: mac.concept.axis.categorical }, rulings: { scoped_by: Country } }
StateFull: { roles: { axis: mac.concept.axis.categorical }, rulings: { label_of: State, register: long } }
```

## Errors

| condition | outcome |
|---|---|
| `label_of` names a column not in this relation | load refuses — a column is never assumed to exist |
| the pair is not 1:1 in the data | `check_column_rulings` reds: the ruling claims one thing, the data shows many |
| `register` without `label_of` | the schema refuses — `dependentRequired` |
| `register` is not a `mac.name_register` term | load refuses |

## See also

[`finer_than`](#2--finer_than) when the two columns are levels, not names ·
[column_roles.md](column_roles.md) ·
[patterns/semantic_constellations/competing_definitions.md](patterns/semantic_constellations/competing_definitions.md) for one term with several
*meanings*, which is the opposite problem

---

## The `register` argument

<!-- BEGIN GENERATED:vocabulary-terms:name_register (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> Which register a name belongs to, when one thing carries several names.

*`mac.name_register` · 5 terms · closed — these are all of them*

#### `mac.name_register.common`

The name people use. 'Contoso', 'Germany', 'Monday'.

#### `mac.name_register.legal`

The name in a trade or statutory register. 'Contoso, Ltd'.

#### `mac.name_register.long`

The unabbreviated form of a coded name. 'United Kingdom' for GB.

#### `mac.name_register.short`

The abbreviated form. 'Mon' for Monday, 'Jan' for January.

#### `mac.name_register.code`

A machine identifier standing for the name. 'GB', 'DE', a numeric key.
<!-- END GENERATED:vocabulary-terms:name_register -->

---

# 2 · `finer_than`

**Status: READ** — `planner/sql.py` discloses that the finer of two levels was used.

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
| Contosoo | Bluetooth Headphones |
| Contosoo | MP4&MP3 |
| Contosoo | Recording Pen |
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
    CategoryName:    { roles: { axis: mac.concept.axis.categorical } }
    SubCategoryName:
      roles:   { axis: mac.concept.axis.categorical }
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

[patterns/identity_and_structure/recursive_hierarchy.md](patterns/identity_and_structure/recursive_hierarchy.md) when the hierarchy is a
self-reference rather than two columns

---

# 3 · `scoped_by`

**Status: LOADED, NOT PLANNED-ON.** Schema-admitted and parsed into `ColumnRulings` (mac-runtime
`ontology/models.py`), and no planner step reads it — waived in `test_declared_but_unread` as a ticket.
The protection this describes comes today from the `composite_key_guard` canon, not from this key.

## Synopsis

```yaml
rulings:
  scoped_by: <column>
```

## Description

Declares that this column's values are **unique only within the named column**. It may not be
grouped or filtered on alone; the scope column travels with it.

**The full treatment is [patterns/semantic_constellations/context_dependent_meaning.md](patterns/semantic_constellations/context_dependent_meaning.md)**
— *"a code meaningless without its parent"* — which is canonical for this constellation and is
enforced by the [`composite_key_guard`](rules_and_canons/context_dependent_meaning/composite_key_guard.md) canon. `scoped_by` is the
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
    Country: { roles: { axis: mac.concept.axis.categorical } }
    State:
      roles:   { axis: mac.concept.axis.categorical }
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

# 4 · `sort`

**Status: READ** — `planner/sql.py` `column_sort` turns it into the `ORDER BY` this column contributes.

## Synopsis

```yaml
rulings:
  sort: asc | desc | none
```

## Description

Declares the order this column's values are presented in **when the question states none**.

| term | the order | the reading it is for |
|---|---|---|
| `asc` | alphanumeric, smallest first | a NAME |
| `desc` | largest first | a MAGNITUDE |
| `none` | — | a column that is never an ordering key |

**Per column, never per concept** — operator ruling, 2026-10-02: *"it must be sort per column and not
concept"* — because one breakdown legitimately wants `brand asc`, `country_code asc` and
`net_amount desc` at the same time, which no concept-level flag can express.

## Parameters

| parameter | required | default | legal values | meaning |
|---|---|---|---|---|
| `sort` | yes | — | `asc` · `desc` · `none` | the order this column's values are presented in |

## When to use it — the constellation

**The one ruling with no measurement constellation, and that is the point rather than a gap.** SQL
guarantees no row order without `ORDER BY`, so nothing in the data can establish the order a reader
expects — only a person can say it. An unordered answer is not a reading of the question: it is
whatever the engine happened to emit, and it changes between runs.

Measured 2026-10-02 on AGG-15 (*"net revenue by brand and customer country for 2024"*), an 88-row
breakdown: the grader compares the approved rows against the capture's **first 50**, which 50 depended
on unordered output, and the question passed and failed on alternate runs with the data unchanged.

An ordering is also what makes a truncated view honest: the first N rows of a descending measure are
the N that matter.

## Precedence

| rank | source | example |
|---|---|---|
| 1 | `Intent.ordering` — the reader's own words | *"top 5 by price"* |
| 2 | `rulings.sort` on the column | `net_amount: desc` |
| 3 | `query_grammar.yaml#projection.default_ordering` | an aggregate `desc`; a bare list `asc` on its slice columns |

## Examples

```yaml
grounding:
  columns:
    Brand:
      roles:   { axis: mac.concept.axis.categorical }
      rulings: { sort: asc }
    NetPrice:
      roles:   { aggregate: { type: flow, unit: the order's own CurrencyCode } }
      rulings: { sort: desc }
    ZipCode:
      roles:   { axis: mac.concept.axis.categorical }
      rulings: { sort: none }
```

| you ask | ordering applied | why |
|---|---|---|
| *net revenue by brand* | `ORDER BY SUM(NetPrice) DESC` | the measure's `desc` — the rows that matter come first |
| *list the brands* | `ORDER BY Brand ASC` | a name reads alphabetically |
| *top 5 brands by price* | `ORDER BY ... DESC LIMIT 5` | `Intent.ordering` outranks the column's ruling |

---

# When the judgement is a prohibition

A judgement that a column **may not be used** a particular way is not a ruling about the column,
because the column has not changed: it still is what the warehouse made it. `ZipCode` is
`{axis: categorical}` and declares it. The prohibition is a **rule**.

| measured over `dim_contoso_customer` | |
|---|---:|
| customers | 104 990 |
| distinct `ZipCode` | 40 639 |
| postcodes held by **exactly one** customer | **29 193** |

`City` is the same shape at 34 581 distinct. `GROUP BY ZipCode` plans, executes and returns 29 193 rows
that each describe one person: the query is valid, and only a rule stands between it and an answer.

**Where each part of the judgement lives** — a `contract.rules[]` entry, anchored to the column:

| the rule carries | in | note |
|---|---|---|
| what it governs | `kind` | a `mac.concept.rule.*` term — mac.schema.json closes the slot to the six |
| the prohibition | `when` / `then` / `never` | the situation, the directive, the anti-pattern |
| the reason | `why` | one line, and it is what the refusal quotes back |
| the column | `binds: [ZipCode]` | the field-anchoring: `binds` must name columns the concept grounds to, enforced cross-file by the rule-binds-grounded shape in `mac_shapes.yaml` |
| the deterministic realization | `realized_by` | the canon that executes the `when`/`then`; a refusal from a canon is filed `POLICY_DENIED` (`planner/contract_guards.py`) |
| where the decision came from | `decided_in` | a ref to the record, `<repo>#<path>` or bundle-relative |
| its standing | `status` · `confidence` | `proposed` · `ruled` · `retired` · and `C` · `P` · `R` |

**The refusal cites the measurement.** A judgement made from a measurement must produce a refusal that
names it, never a silent success:

```
> customers by postcode
```
```
REFUSED (POLICY_DENIED)
Customer.ZipCode is a categorical axis, and the rule bound to it refuses grouping: DQ-CUSTOMER-02
measured that 29 193 of 40 639 postcodes are held by exactly one customer, so grouping on it names
individuals. Customer can be grouped by: Continent, Country, Gender, State, age_band_5y.
```

**Why it is not on the column.** A declaration describes the data; a prohibition is a rule. A column
that *is* an axis says so even where policy forbids grouping by it — declaring a real axis "not an axis"
would make the ontology lie about the warehouse, and the measurement that justifies the prohibition
would then contradict the declaration that hides it.

## See also

[patterns/dimensional_special_cases/junk_dimension.md](patterns/dimensional_special_cases/junk_dimension.md) ·
[patterns/dimensional_special_cases/degenerate_dimension.md](patterns/dimensional_special_cases/degenerate_dimension.md)

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
| none — the data cannot say | [`sort`](#4--sort) | the order a reader expects; SQL promises none |
| cardinality ≈ row count | **not a ruling** — the column is an axis and says so; the prohibition is a [contract rule](#when-the-judgement-is-a-prohibition) | whether the identification matters |

**`scoped_by` mistaken for `finer_than` is the expensive error**: it merges unrelated members and
nothing in the result betrays it.
