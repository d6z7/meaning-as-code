---
title: The column declaration — what a column says about itself, and where each fact lives
status: >-
  PROPOSED (2026-10-07) — NOTHING ON THIS PAGE IS ENFORCED. It is the classification put to the operator
  for review: one key where there are two vocabularies today (`role` and `query_use`), and three
  retirements (`grounding.grain`, `concept.semantics`, `rulings.never_axis`). The `axis_kind` → `axis`
  rename IS done (463 occurrences, 104 files); everything else below is a proposal. The pages this one
  summarises — column_roles.md, column_rulings.md, column_specification.md — still describe what the
  schema admits TODAY, and they are the authority until this is ruled on.
audience: ontology authors, importer developers, framework developers
companions:
  - column_roles.md           # what `role` admits today — the scalar this proposal replaces
  - column_rulings.md         # the rulings block, which survives this proposal almost intact
  - column_specification.md   # the long-form spec: every flag, and the seven sections still refused
  - measures.md               # the fold law this classification feeds
  - specification/FOLD_GRAMMAR.md
  - ../mac_vocabulary.yaml    # the authoritative terms
---

# The column declaration

A concept says what it means by declaring its columns. This page is the map of **which fact goes in
which key**, and it exists because the same fact is currently declarable in two places and three facts
are declared twice.

> **Read this first if you are deciding where to put something.** The detail of each key is in
> [column_specification.md](column_specification.md); the terms are generated into
> [column_roles.md](column_roles.md) and [column_rulings.md](column_rulings.md) from
> `mac_vocabulary.yaml`. This page is the shape, not the detail.

## 1. One question, one key

A column answers exactly one question about itself:

> **What may a question do with me, and on what terms?**

Everything else a column carries is either a *parameter of one of those uses* or a *relationship to
another column*. The proposal is that the answer lives in one key, `roles`, as a **map from each role
to its own qualifier**:

```yaml
grounding:
  sources:
    - relation: v_contoso5_sales_line
      columns:

        order_key:
          roles:
            identity: composite

        customer_key:
          roles:
            identity: reference
            axis: categorical

        order_date:
          roles:
            axis: time
            period_binding: true

        quantity:
          roles:
            aggregate: {type: mac.concept.column.measure_type.flow, unit: units}

        valid_from:
          roles: {}
```

### Why a map and not a list

A list needs a second key to carry each role's parameter, and then the column says the same word
twice — `roles: [identity]` beside `identity: composite`. A map carries the parameter *as the value*,
which has three consequences worth stating:

* **Nothing is written twice.** The role and its terms are one statement.
* **"If you claim a role, state its parameter" is structural, not a rule.** You cannot write `axis`
  without a kind, because the kind *is* the value. The requirement needs no gate.
* **`roles: {}` is a positive statement**, and it is exactly the definition `role: housekeeping`
  carries today — *"it is not offered to a question"*. An absent `roles:` is a different thing: a
  column nobody has classified, which is a finding.

## 2. The five roles

| role | its qualifier | means |
|---|---|---|
| `identity` | `canonical` · `composite` · `reference` | the row is identified by me — alone, jointly, or elsewhere |
| `axis` | `time` · `categorical` | a question may group or filter by me; the term is the fold law's lookup key |
| `aggregate` | `{type, unit, canonical}` | a question may fold me; `type` × `axis` decides how |
| `period_binding` | `true` | I am **the** reporting date when the relation carries several |
| `extremum` | `[min]` · `[max]` · `[min, max]` | my earliest or latest value may be asked for — **not** a fold |

### `identity` — three ways to identify

| | |
|---|---|
| `canonical` | this column **alone** identifies an instance. What `COUNT(DISTINCT …)` counts. At most one per concept. |
| `composite` | this column **with its siblings** identifies an instance. Declared on every column of the tuple; the set of columns carrying it *is* the key. |
| `reference` | this column identifies an instance **elsewhere** — the row names a row in another concept. |

`composite` replaces the term `part`. `part` named a fragment and left the reader to find out what it
was part of, where `canonical` and `reference` both say what the column *does*; and `composite` is the
word the canon that polices it already uses — `mac.canon.composite_key_guard`, whose subject is a
parent-scoped code used without its scope columns.

### `extremum` is new capability, not a rename

Nothing in the schema today lets a column say *"my earliest value may be asked for"*. That is what
*"when did we first sell in Spain"* needs, and it is not a fold: `MIN(order_date)` over a flow measure
is legitimate where `SUM(order_date)` is nonsense. It arrives with this classification rather than
being added by it.

## 3. What is NOT a role

Three keys stay beside `roles`, because they answer different questions:

| key | question |
|---|---|
| `counts` | what does a **count of this concept** count, when it is not the canonical column? |
| `register` | where do this column's values come from? |
| `rulings` | how does this column relate to **another column**? |

`counts` is the key-is-not-identity case, and contoso5 has exactly one: `store.store_key` is
`identity: canonical` — one row per trading period — while `store.location_code` carries
`counts: true`, because a count of *stores* is 67 and a count of *rows* is 74.

`rulings` keeps `label_of`, `register` (which *name* of the thing — `common`/`legal`/`long`/`short`/
`code`, not to be confused with the column-level `register:`, which is a *path*), `finer_than`,
`scoped_by` and `sort`.

## 4. What this replaces, and the measurement for each

| retiring | why | replaced by |
|---|---|---|
| `role` (scalar) | one slot for five orthogonal facts. **21 of 112** contoso5 columns are declared `role: key` while carrying an axis kind — a join key you group by — which the scalar cannot say. And the vocabulary contradicts itself about them: `key` is *"never aggregated"*, `dimension` is *"legitimate in GROUP BY"*. | `roles`, a map |
| `query_use` | its own description is *"the machine-readable half of `concept.column.role`"* — one fact, two vocabularies. Declared, closed, 5 terms, and **0 occurrences in `mac.schema.json`**: no column may declare it. | its terms **become** `roles`'s terms |
| `grounding.grain` | prose restating the identity columns, **17 of 17**. And it is *false* on one: it says *"one row per customer version"* where `dim_customer` holds 104,990 rows and 104,990 distinct `customer_key`. Nothing could tell, because prose has no reader. | `identity: canonical` / `composite` |
| `concept.semantics` | one blanket `measure_type` per concept, where **3 of 7** measure concepts carry two measure columns of **different** types — `net_revenue` has `net_amount` (flow) and `net_price` (intensive). The concept-level form cannot express it. The schema's own comment has said since v0.1.15 that it *"is no longer required here"*. | per-column `aggregate: {type, unit}` |
| `rulings.never_axis` | it encodes a **policy** by making a claim about the **data**. `customer_name` has 99,200 distinct values over 104,990 rows: it *is* a categorical axis, and it is forbidden for privacy. Declaring it "not an axis" would be false — the same shape as calling the `--` sentinel an exclusion rather than a population. | `roles` omits `axis`; the reason and its `evidence` move to a rule with `decided_in` |
| `measure.additivity` | derived from `type` × `axis` by the law in `mac_vocabulary.yaml#concept.column.measure_type`. **0 uses** in contoso5. A concept writing it states the same fact twice and the two can drift. | the fold law |

## 5. The case that forced the design

Two concepts, declared identically today, meaning opposite things:

| | `units_sold` | `exchange_rate` |
|---|---|---|
| grain | one row per `(order_key, line_number)` | one row per `(date_day, from_currency, to_currency)` |
| those columns | `role: key`, `identity: part` | `role: key`, `identity: part` |
| are they axes? | **no** — nobody asks "revenue by line number" | **yes** — *"the USD→EUR rate on 2025-01-03"* names the row **by** its axes |
| how you can tell today | it carries no axis kind | it carries one |

The declarations are byte-identical apart from that. So the presence of an axis term is doing the
whole work, and it is the only place the distinction is stated — which is why `axis` is not redundant
with `identity`, and why the map form makes the rule enforceable instead of inferred.

## 6. What is enforced today

| | |
|---|---|
| **done** | `axis_kind` → `axis` (463 occurrences over 104 files, three repositories); `values` and `semantics` no longer `required` by `mac.schema.json` |
| **proposed, not enforced** | everything else on this page |
| **the bill** | `roles` as a map is a scalar→map change on a key read at **96 comparison sites over 78 files**. The plural rename is deliberate: a reader still looking for `role` fails to find it rather than silently reading a map as a string. |

## 7. Open questions this page does not settle

1. **`label` as a sixth role.** `customer_name` is forbidden as an axis but still *displayable* when
   one customer is looked up by key. `roles: {}` forbids that too. Either `label` becomes a role, or
   display is not a query use and belongs elsewhere.
2. **`identity` is both a role name and a key name** in the current schema. Under this proposal the
   key disappears into the role, so the collision goes with it — but any transitional state carries
   both.
3. **The guard `never_axis` becomes.** Moving the privacy ruling to a rule needs a guard that refuses
   a grouping and cites the measurement. It does not exist yet; it is one of the four guards already
   owed by the `never`-clause classification in [rules_and_canons/rule_engine.md](rules_and_canons/rule_engine.md).
