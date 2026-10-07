---
title: The column declaration — every key an author writes, and who reads each answer
status: >-
  CURRENT (2026-10-07, revision 5). This page IS the surface: mac.schema.json admits exactly these
  keys, mac_vocabulary.yaml declares exactly these terms, and the runtime reads them. Revisions 1-4
  each retired a key that carried two facts — `role` (join key vs axis), `identity: canonical`
  (relation key vs tall-fact discriminator), `identity` (key vs foreign key), `register` (a file path
  vs a naming term). This revision is the result of a four-agent design review that looked for the
  remaining ones.
audience: ontology authors, importer developers, framework developers
companions:
  - column_specification.md   # the long form: every key, with its enforcement state
  - column_rulings.md         # the rulings block, in detail
  - measures.md               # the fold law this feeds
  - specification/FOLD_GRAMMAR.md
  - ../mac_vocabulary.yaml
---

# The column declaration

A concept means what its columns say. The source says what makes one row unique; each column answers
one question —

> **What may a question do with me, and on what terms?**

```yaml
grounding:
  source:
    relation: v_contoso5_sales_line
    key: [order_key, line_number]        # what makes ONE ROW unique, in order
    columns:
      order_key:     {offers: {}}        # loaded, offered to no question
      line_number:   {offers: {}}
      quantity:      {offers: {aggregate: {type: flow, unit: units}, extremum: [min, max]}}
      order_date:    {offers: {axis: time, period_binding: true, extremum: [min, max]}}
      customer_key:  {offers: {axis: categorical}, references: Customer}
      city:          {offers: {axis: categorical, suppressed: DQ-IDENTIFYING-DIM_CUSTOMER-CITY}}
```

## The source

| key | card | required | value | says | read by |
|---|---|---|---|---|---|
| `relation` | string | **yes** | a table or view | which relation this concept is grounded on | `Grounding.table` |
| `key` | string · **ordered list** | **yes** | column names of this map | what makes ONE ROW unique. **The order is load-bearing** — it becomes `cell_key` and reaches the SQL | `Grounding.cell_key`; `canonical_key` (one name, and not a measure); `key_parts` (two or more) |
| `counts` | column name | no | a column of this map | a count of this concept counts THAT column, not its rows | the count route; disclosed in the answer |
| `columns` | map | **yes** | column name → body | the columns this concept serves | `served_columns` |

`source` is **singular**. A concept binds one relation; many concepts bind one relation. `sources:` as
a list is a load error — it was never honoured (`Grounding` carries no `sources` field, a second entry
was silently dropped), and a notion genuinely over two relations is a transform view, or two concepts
and an edge.

## The column — four keys

| key | card | required | says | read by |
|---|---|---|---|---|
| `offers` | map | **yes** — `{}` is legal | what a question may **do** with me | `Grounding.offers(column, use)` — every planner step |
| `references` | **concept name** | iff it points | my values identify one row of **that concept** | `Grounding.offers(col, "identity")` → `sql._filterable`; `parser._check_references_known` refuses an unknown concept. **NOT yet a join driver** — contoso5's joins come from `edges.yaml`, and all 25 references already have a matching edge |
| `value_register` | path | no | the file whose rows **are** my values | `resolver/registers._scan_concepts`, which synthesises an `enum_from_register` declaration. `register_match` reads that declaration, not this key |
| `rulings` | map | no | what a **person** decided about my relation to **another column** | `planner/sql`, the refusal path |

A missing `offers` is a column nobody classified — a finding. `offers: {}` is a positive statement:
the column is loaded, typed, and no question is offered it.

## `offers` — the five uses

| use | card | terms | says | read by |
|---|---|---|---|---|
| `axis` | scalar | `time` · `categorical` | a question may **group or filter** by me — and which row of the fold law a fold across me resolves against | `grounded_columns.axis_columns`; `column_facts.axis` |
| `suppressed` | string | a DQ issue id | I **am** that axis and a person has ruled that no question may group by me. **Requires `axis`** | `_axis_denied` — a Refusal citing the finding |
| `aggregate` | map | `{type, unit, default, additivity}` | a question may **fold** me | `column_facts.measure_type/unit`; `plan._check_additivity` |
| `period_binding` | bool | `true` | I am **the** reporting date when the relation carries several | period binding; `offering('period_binding')` |
| `extremum` | list | `min` · `max` | my earliest or latest value may be **asked for** — a pick, never a fold | `plan._OPERATION_NEEDS` → MIN/MAX |

### `aggregate` — the qualifier of a foldable column

| sub-key | card | required | terms | says |
|---|---|---|---|---|
| `type` | scalar | **yes**, within | `flow` · `stock` · `intensive` · `precomputed` · `target` | what kind of quantity — the fold law's row |
| `unit` | string | **yes**, within | free (`USD`, `units`, `m2`) | what the number is in; two units may not be combined |
| `default` | bool | no | `true` | **which** aggregate a bare question means, when a concept carries several |
| `additivity` | map | no | `{<axis>: <effect>}` | a per-axis override of the law — **leave unwritten**; authoring premise and conclusion is how a `target` got summed |

### The fold law — `type` × `axis`

Stated over **kinds**, never over column names, which is what makes it universal. Five types × two
axis kinds = ten cells, and `test_foldplane_law` asserts exactly that — which is why `axis` has two
terms and a suppression is a separate key rather than a third term.

| `aggregate.type` | across `time` | across `categorical` |
|---|---|---|
| `flow` | **additive** | **additive** |
| `stock` | `none` — does not accumulate | **additive** |
| `intensive` | `average` | `average` |
| `precomputed` | `none` | `none` |
| `target` | `none` | `none` |

## `rulings` — what a person decided about **another column**

Every member names one. All optional; a column with none behaves as its `offers` alone dictate.

| ruling | value | says | read by |
|---|---|---|---|
| `label_of` | a column | I am **another name for that column's thing**, not another thing — group on it, display me | `planner/sql` |
| `naming` | `common` · `legal` · `long` · `short` · `code` | **which** of that thing's names I am. Required with `label_of` | `planner/sql.assemble_plan` — named in the disclosure. *(NOT the resolver: `resolver/` has zero readers of it.)* |
| `finer_than` | a column | I distinguish **more members** and roll up into it; an answer must **disclose which level it used** | `planner/sql` |
| `scoped_by` | a column | my values are unique **only within** that column — the scope must travel with me | synthesises a `composite_key_guard` binding |
| `sort` | `asc` · `desc` · `none` | the order my values take when the question states none | the assembler |

## Derived — never authored

| | from | read by |
|---|---|---|
| `role` — key · dimension · measure · period · housekeeping | `offers`, **the source's `key`**, and **`references`** — a key column claims nothing of its own, and a foreign key IS a join column, which is what `role: key` always meant. Dropping `references` from this derivation moves 25 of contoso5's 112 columns out of `key` | `grounding.field_roles` |
| `cell_key` | `key`, verbatim | `planner`, the count route, the snapshot cycle, the fold plane's grain |
| `canonical_key` | `key` when it names one column **and the class is not `measure`** — a measure is summed, not counted | `grounded_columns`, `joins`, the count route |
| `counts_as` | `source.counts` | the count route |
| `semantics.{measure_type, unit, additivity}` | the columns' `aggregate` | `column_facts`, the fold law |

> **No read-site counts on this page, deliberately.** Five appeared here and none reproduced: each
> was a `grep` summed across repos, or across src and tests, or over comments — and a reader cannot
> tell a measurement from a recollection. The ADDRESS is the fact a reader needs; a count that drifts
> with the next commit is decoration. `reference_manual/column_effects.yaml` carries the per-key
> reader as a `module::symbol`, which does not move when a line does.

## What `references` does not yet do

It is **not** read by join derivation. Every one of contoso5's 25 `references` columns already has a
matching edge in `edges.yaml`, and the planner joins from there. Deriving the join from the column
would make the two agree by construction instead of by coincidence — it is a feature, not a rename,
and it is unbuilt. Stated here because this page claimed that reader before it existed.

## Measured — the data plane writes it, nobody authors it

`storage_role` · `type` · `distinct` · `references.to` + cardinality + participation · `register`
→ `data/datasets/<relation>.yaml`.

**The target of a reference is measurable in most cases and not all.** Of contoso5's 25 references,
22 resolve from the descriptor's own `references.to`. Three do not: `Brand`, `Color` and
`ProductCategory` are member-sets **over** `dim_product` and declare `product_key`, which the data
plane calls that relation's own primary key. A pointer inside one relation is conceptual, and no
descriptor can see it — so `references` is authored, and the descriptor is the check, not the source.

## Rules this model holds

1. **One fact, one key.** No column states the same thing twice, and no key restates what another declares.
2. **Claim a use, state its terms.** The qualifier *is* the value, so a use cannot be claimed without it.
3. **A declaration describes the data; a prohibition is a rule.** A column that *is* an axis says so even when a person forbids grouping by it — `suppressed` sits beside `axis`, never instead of it, and its value is the finding. Declaring a real axis "not an axis" would make the ontology lie about the warehouse.
4. **Absence is load-bearing only where it is declared to be.** `offers: {}` means *offered to nothing*; a missing `offers` means *unclassified*. Two different findings.
5. **A word carries one fact.** Four keys have been retired for failing this — `role`, `identity: canonical`, `identity`, `register` — each found only after it had shipped. A key whose value space has two shapes, or whose name describes two questions, is the next one.
