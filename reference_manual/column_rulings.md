---
title: Column rulings — reference
status: >-
  CURRENT (2026-10-07, revision 5). FIVE rulings, under `grounding.source.columns.<col>.rulings`:
  `label_of`, `naming`, `finer_than`, `scoped_by`, `sort`. Each names ANOTHER column or says which
  of that other column's names this one is — which is the test for membership, and is why
  `never_axis` left this block on 2026-10-07: it named no other column, and a prohibition on a
  column's OWN use is `offers.suppressed`, whose value is the finding that justifies it. `label_of`
  and `naming` require each other (schema `dependentRequired`, both directions). READ by mac-runtime
  `planner/sql.assemble_plan`: `label_of` + `naming` (the label is selected, the named column grouped
  on, with a disclosure naming which name it showed) and `finer_than` (a disclosure that the finer
  level was used); `planner/sql.column_sort` for `sort`; and
  `planner/contract_guards.sql_guard_bindings` synthesises a `composite_key_guard` binding from
  `scoped_by`. Per-ruling status is on each section below. Every example is a column of contoso5.
audience: ontology authors, importer developers
companions: [column_declaration.md, column_specification.md, column_roles.md, ../mac_vocabulary.yaml]
---

# Column rulings

A **ruling** is a judgement about a column that measurement cannot establish. Rulings are declared
under `rulings:` on a column and are always optional; a column with no rulings behaves as its
[offers](column_roles.md) alone dictate.

```
SYNOPSIS
    columns:
      <column>:
        offers: { … }                                        # what a question may DO with it — column_roles.md
        rulings:
          label_of:   <column>
          naming:     common | legal | long | short | code   # REQUIRES label_of, and is required BY it
          finer_than: <column>
          scoped_by:  <column>
          sort:       asc | desc | none
```

## The five rulings

| ruling | value | required | says | the measurement that gets you to the door | read by |
|---|---|---|---|---|---|
| `label_of` | a column of the same source map | — | I am **another name for that column's thing**, not another thing — group on it, display me | `a = b = pairs` | `planner/sql.assemble_plan` |
| `naming` | `common` · `legal` · `long` · `short` · `code` | **with `label_of`**, and it with this | **which** of that thing's names I carry | — only a person can say | `planner/sql.assemble_plan`, in the disclosure |
| `finer_than` | a column of the same source map | — | I distinguish **more members** than that column and roll up into it; both are legitimate axes and an answer must disclose which level it used | `pairs = finer_distinct` | `planner/sql.assemble_plan` |
| `scoped_by` | a column of the same source map | — | my values are unique **only within** that column, so I may not be grouped or filtered alone — the scope must travel with me | 0 collisions within, many across | `planner/contract_guards.sql_guard_bindings` → a `composite_key_guard` binding |
| `sort` | `asc` · `desc` · `none` | — | the order my values are presented in when the question states none | **none — and that is the point:** SQL guarantees no row order without `ORDER BY` | `planner/sql.column_sort` |

### Every ruling names another column

That is the membership test, and it is what tells a ruling from a judgement about the column itself.

| the judgement | names another column? | where it lives |
|---|---|---|
| this column is another name for that one | yes | `rulings.label_of` |
| which of that thing's names this is | yes — the companion of `label_of` | `rulings.naming` |
| this column rolls up into that one | yes | `rulings.finer_than` |
| this column's values are unique only within that one | yes | `rulings.scoped_by` |
| the order this column's values are presented in | its own, and nothing else is affected | `rulings.sort` |
| **no question may group by this column** | **no** | **[`offers.suppressed`](column_specification.md#offerssuppressed--the-axis-no-question-may-group-by)** — beside the `axis` it suppresses, and its value is the DQ finding the refusal quotes |

`naming` was spelled `register` until 2026-10-07, one word that also named the column's own
`value_register` a single nesting level away — contoso5's `Country` concept declared both seven
lines apart. The runtime had already been forced to split them (`ColumnSpec.value_register` /
`ColumnRulings.naming_register`) while the author was still asked to write one word for both.

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

**A prohibition is not a ruling, and it is not a rule either.** A ruling relates a column to another
column. That no question may group by a column is a judgement about the column's own use, so it
sits in `offers` beside the axis it suppresses —
[`offers.suppressed`](#when-the-judgement-is-a-prohibition), whose value IS the measurement's id.

---

# 1 · `label_of`

**Status: READ** — `planner/sql.assemble_plan` selects the label, groups on the named column, and
discloses which of the thing's names it showed.

## Synopsis

```yaml
rulings:
  label_of: <column>
  naming: common | legal | long | short | code      # REQUIRED with label_of
```

## Description

Declares that this column is **another name for the thing the named column identifies**, not a
different thing. The named column stays the axis: queries group and filter on it, and this column
supplies the words shown to the reader.

Without the ruling both columns are independent axes, and *"by X"* and *"by Y"* return the same
cut under different labels with nothing relating them.

## Parameters

| parameter | required | default | legal values | meaning |
|---|---|---|---|---|
| `label_of` | yes | — | a column of the same source map | the column this one names |
| `naming` | **yes, with `label_of`** | — | `common` · `legal` · `long` · `short` · `code` | which of the thing's names this column carries |

Both directions are `dependentRequired` in `mac.schema.json`: `naming` without `label_of` has no
thing to name, and `label_of` without `naming` leaves the disclosure unable to say which name it
showed. There is no default — `common` was one until 2026-10-07, and a default here is a claim about
the data that nobody made.

## When to use it — the constellation

Two columns, **equal distinct counts and an equal pair count**:

| measured over `dim_product` | |
|---|---:|
| distinct `brand` | 11 |
| distinct `manufacturer` | 11 |
| distinct pairs | **11** |

| `brand` | `manufacturer` |
|---|---|
| A. Datum | A. Datum Corporation |
| Adventure Works | Adventure Works |
| Contoso | Contoso, Ltd |
| Fabrikam | Fabrikam, Inc. |

The two registers `mac_lookups.py` cut from the same relation each measure **11 members**
(`data/lookups/contoso5_brand.lookup.yaml`, `data/lookups/contoso5_manufacturer.lookup.yaml`), and
the fourth row
is the one that matters: `Adventure Works` is the SAME string in both, so the pair's 1:1 is not even
a difference in spelling. Nothing in the data says which of the two is the name.

1:1 gets you to the door. **Only a person can say the two names denote one thing.** Contoso and
Contoso, Ltd are one company in two registers; Fabrikam Group and Contoso are two companies, and
that pair would be one-to-many — a `references` pointing at a parent, not a label.

## What happens without it

| | |
|---|---|
| **Two answers to one question** | *by brand* → 11 rows. *by manufacturer* → 11 rows. Identical numbers, different labels, nothing says they are the same cut. |
| **Meaningless cross-product** | `GROUP BY brand, manufacturer` yields 11 rows where a reader expects 121, and reads as a data bug. |
| **A refusal instead of a redirect** | Suppressing the second column as an axis refuses *"by manufacturer"* — a good question asked in the reader's own words. The right behaviour is to group on `brand` and DISPLAY `manufacturer`, which is what this ruling buys. |

## Examples

**Declaring it** — contoso5's `Product`, verbatim:

```yaml
# ontology/concepts/product.yaml
grounding:
  source:
    relation: dim_product
    key: product_key
    columns:
      brand:
        offers: {axis: categorical, extremum: [min, max]}
      manufacturer:
        offers: {axis: categorical, extremum: [min, max]}
        rulings:
          label_of: brand
          naming: legal
```

**Asking for the label**

```
> revenue by manufacturer
```
```sql
SELECT p.brand AS "manufacturer", SUM(l.net_amount) AS revenue
FROM   v_contoso5_sales_line l
JOIN   dim_product           p USING (product_key)
GROUP  BY p.brand
```
| manufacturer | revenue |
|---|---:|
| Contoso, Ltd | … |
| Fabrikam, Inc. | … |

> *grouped by brand, shown as manufacturer (legal register)*

**Filtering by the label**

```
> revenue for Contoso Ltd
```
```sql
WHERE p.brand = 'Contoso'
```

**The other two in contoso5** — one thing, three names, each saying which it is:

```yaml
product_code: {offers: {axis: categorical, extremum: [min, max]},
               rulings: {label_of: product_key, naming: code}}
product_name: {offers: {axis: categorical, extremum: [min, max]},
               rulings: {label_of: product_key, naming: common}}
```

**Chaining** — a label of a scoped column is scoped too. contoso5 carries no such pair; this is the
shape, and the column names are illustrative:

```yaml
state:      {offers: {axis: categorical}, rulings: {scoped_by: country_code}}
state_full: {offers: {axis: categorical}, rulings: {label_of: state, naming: long}}
```

## Errors

| condition | outcome |
|---|---|
| `label_of` names a column not in this source's map | load refuses — a column is never assumed to exist |
| the pair is not 1:1 in the data | `check_column_rulings` reds: the ruling claims one thing, the data shows many |
| `naming` without `label_of`, or `label_of` without `naming` | the schema refuses — `dependentRequired`, both directions |
| `naming` is not a `mac.name_register` term | load refuses |

## See also

[`finer_than`](#2--finer_than) when the two columns are levels, not names ·
[column_roles.md](column_roles.md) ·
[patterns/semantic_constellations/competing_definitions.md](patterns/semantic_constellations/competing_definitions.md) for one term with several
*meanings*, which is the opposite problem

---

## The `naming` argument

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

**Status: READ** — `planner/sql.assemble_plan` discloses that the finer of two levels was used.

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
| `finer_than` | yes | — | a column of the same source map | the coarser column this one rolls up into |

## When to use it — the constellation

N:1, and **the pair count equals the finer column's distinct count** — which is what proves every
child has exactly one parent:

| measured over `dim_product` | |
|---|---:|
| distinct `sub_category_name` (finer) | 32 |
| distinct `category_name` (coarser) | 8 |
| distinct pairs | **32** |

| `category_name` | `sub_category_name` |
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

contoso5 declares it on `ProductCategory`, which grounds `dim_product` on `key: category_name` —
one relation, four concepts, and this ruling belongs to the one the hierarchy is about:

```yaml
# ontology/concepts/product_category.yaml
grounding:
  source:
    relation: dim_product
    key: category_name
    columns:
      category_name:
        offers: {axis: categorical, extremum: [min, max]}
        value_register: data/lookups/contoso5_category_name.lookup.yaml
      sub_category_name:
        offers: {axis: categorical, extremum: [min, max]}
        rulings: {finer_than: category_name}
      product_key:
        offers: {}
        references: Product
```

| you ask | plan | result |
|---|---|---|
| *sales by category* | `GROUP BY p.category_name` | 8 rows |
| *sales by subcategory* | `GROUP BY p.sub_category_name` | 32 rows · *"the finer of two levels; rolls up into 8 categories"* |
| *sales by product line* | **ASK** | *"which level — category (8) or subcategory (32)?"* |

The second case in the bundle is `Customer.country_code finer_than continent` — 8 codes rolling into
3 continents — and the third is `Location.state finer_than country_code`, which is the same column
`Customer` rules `scoped_by`. §3 is why both are right.

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

**Status: READ** — `planner/contract_guards.sql_guard_bindings` synthesises a `composite_key_guard`
binding from it (`code_column` + `scope_columns`), which is what refuses the shape. The guard
REFUSES rather than adding the scope column or asking which parent was meant; the designed
behaviour below is what the §Examples table describes.

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

| `state` | `country_code` | the place | customers |
|---|---|---|---:|
| `CO` | FR | Corse | 37 |
| `CO` | IT | Como | 64 |
| `CO` | US | Colorado | 709 |
| `PA` | FR | Provence-Alpes-Côte d'Azur | 495 |
| `PA` | US | Pennsylvania | 2 017 |

| measured over `dim_customer` | | source |
|---|---:|---|
| distinct `state` codes | 565 | `data/profiles/dim_customer.yaml`, measured 2026-09-30 |
| carried by **more than one** country | **40** | the collision scan, taken when the column held 563 codes |
| colliding **within** a country | **0** | the same scan |

**Zero within, many across** is the signature. It separates a scoped code from a hierarchy, which
cardinality alone cannot. The two rows above come from two measurements of the same column two days
apart, and they are kept apart rather than reconciled: re-badging a 563-code scan as a 565-code one
would be a number nobody took.

## What happens without it

`GROUP BY state` puts Corse, Como and Colorado in one row labelled `CO`, totalling 810 customers.
The query succeeds, the row count is plausible, the number is meaningless. *"Customers in CO"*
returns French, Italian and American customers.

## Examples

```yaml
# ontology/concepts/customer.yaml
columns:
  country_code:
    offers: {axis: categorical, extremum: [min, max]}
    rulings: {finer_than: continent}
  state:
    offers: {axis: categorical, extremum: [min, max]}
    rulings: {scoped_by: country_code}
```

| you ask | plan | result |
|---|---|---|
| *customers by state* | `GROUP BY c.country_code, c.state` | 603 rows · *"country_code added — state is scoped by it"* |
| *customers in CO* | **ASK** | *"'CO' is carried by 3 countries — Corse (FR), Como (IT), Colorado (US)"* |
| *customers in Colorado* | `WHERE c.country_code='US' AND c.state='CO'` | 709 — scope inferred from the label |

**The same column, the opposite ruling, in the same bundle.** `Location.state` is
`finer_than: country_code`: `dim_location` holds one state per location, 67 over 67 rows, and every
one of them sits in exactly one country. `Customer.state` is `scoped_by: country_code`, because
there the same code space is reused per parent. The ruling is per source and per concept because
the measurement is — which is the whole reason a column's facts cannot hang off its name.

## Errors

| condition | outcome |
|---|---|
| the code is grouped or filtered without its scope | **REFUSE** — `composite_key_guard` |
| `scoped_by` declared where 0 codes actually collide | `check_column_rulings` warns — the guard costs a join for nothing |

---

# 4 · `sort`

**Status: READ** — `planner/sql.column_sort` turns it into the `ORDER BY` this column contributes.

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
columns:
  brand:
    offers:  {axis: categorical, extremum: [min, max]}
    rulings: {sort: asc}
  net_amount:
    offers:  {aggregate: {type: flow, unit: USD, default: true}, extremum: [min, max]}
    rulings: {sort: desc}
  city:
    offers:  {axis: categorical, suppressed: DQ-IDENTIFYING-DIM_CUSTOMER-CITY}
    rulings: {sort: none}
```

| you ask | ordering applied | why |
|---|---|---|
| *net revenue by brand* | `ORDER BY SUM(net_amount) DESC` | the measure's `desc` — the rows that matter come first |
| *list the brands* | `ORDER BY brand ASC` | a name reads alphabetically |
| *top 5 brands by price* | `ORDER BY … DESC LIMIT 5` | `Intent.ordering` outranks the column's ruling |

`sort` and `suppressed` on the same column are not in tension: the suppression says the column is
never an AXIS, and `sort: none` says it is never an ORDERING KEY. Two different operations, and a
column a question may still filter on and display earns both statements.

---

# When the judgement is a prohibition

A judgement that a column **may not be grouped on** leaves the column unchanged: it still is what
the warehouse made it. So it is declared **beside** what the column is, in the same map, and never
instead of it.

```yaml
city:
  offers:
    axis: categorical                              # what the column IS
    extremum: [min, max]
    suppressed: DQ-IDENTIFYING-DIM_CUSTOMER-CITY   # what no question may do with it
```

| measured over `dim_customer` | |
|---|---:|
| customers | 104 990 |
| distinct `city` | 34 581 |
| values held by **exactly one** row | **21 317** |

`customer_name` is the same shape at 99 200 distinct and 94 488 singletons. `GROUP BY city` plans,
executes and returns 34 581 rows, 21 317 of which each describe one person: the query is valid, and
only a declaration stands between it and an answer.

**The value IS the evidence.** `offers.suppressed` takes the id of a finding in
`data/quality/data_quality_register.yaml`, so a prohibition cannot be authored without naming the
measurement that justifies it, and the refusal quotes the register rather than a word:

```
> customers by city
```
```
REFUSED (POLICY_DENIED)
Customer.city is a categorical axis and is suppressed by DQ-IDENTIFYING-DIM_CUSTOMER-CITY, which
measured that 21,317 of 34,581 distinct values (62%) over 104,990 rows are held by exactly one row,
so grouping on it names individuals. Customer can be grouped by: continent, country_code, state,
gender, birth_date.
```

| where each part lives | |
|---|---|
| what the column IS | `offers: {axis: categorical, extremum: [min, max]}` — so joins, resolution, the extremum route and the fold law all read it correctly |
| that no question may group by it | `offers.suppressed`, in the same map; `axis` is required alongside (schema `dependentRequired`) |
| the measurement | the key's own value — a DQ register id, raised from `data/profiles/<relation>.yaml` `singletons` |
| the refusal | `planner/plan._axis_denied` → `POLICY_DENIED`, quoting the finding; `planner/grounded_columns.axis_columns` drops the column, so the set the prompt OFFERS and the set a refusal LISTS stay one set |

**Why it is not a ruling.** Every member of `rulings` names another column; this names none. It was
two keys in that block — `never_axis`, carrying a prose reason, and `evidence`, carrying the id —
and the prose field held a reason CODE (`privacy`) in both of contoso5's uses while the sentence it
claimed to carry already lived in the register. One key whose value is the finding says the same
thing once, and cannot be authored half-done.

**Why it is not a rule either.** A cross-column prohibition — *"never report nine countries"* — IS a
`contract.rules[]` entry with `kind`, `never`, `why`, `binds` and `realized_by`; contoso5 declares
one on `Country.country_code` for the `--` sentinel. The shape and the `never` → refusal path are in
[identity_and_rules.md](rules_and_canons/identity_and_rules.md). A prohibition on ONE column's own
use needs none of that machinery, and routing it through a rule is what left the measurement in
prose for twelve concepts.

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
| `a = b = pairs` | [`label_of`](#1--label_of) + [`naming`](#the-naming-argument) | whether the two names denote one thing or two, and which name this one is |
| `pairs = a`, `a > b` | [`finer_than`](#2--finer_than) | — this one is safe to read off the data |
| `pairs > a` **and** `pairs > b` | [`scoped_by`](#3--scoped_by) | — also safe: check collisions within vs across |
| none — the data cannot say | [`sort`](#4--sort) | the order a reader expects; SQL promises none |
| cardinality ≈ row count | **not a ruling** — [`offers.suppressed`](#when-the-judgement-is-a-prohibition) beside the axis it suppresses | whether the identification MATTERS; the ratio is a measurement, the judgement is not, and the key's value is the id of the one that was taken |

**`scoped_by` mistaken for `finer_than` is the expensive error**: it merges unrelated members and
nothing in the result betrays it.
