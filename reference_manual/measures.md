---
title: How a measure folds — measure_type, axes, and what a question binds
status: measure_type and additivity are READ and enforced; binding_mode is not yet read
audience: ontology authors declaring a measure
companions: [column_roles.md, ../mac_vocabulary.yaml, patterns/semi_additive_balance.md]
---

# How a measure folds

**A measure is not a number you may add up.** Whether `SUM` is correct depends on the measure and on
the axis you are summing along — and the two combine into one answer per pair.

## The whole system in one table

Declare **one** thing per measure — `semantics.measure_type` — and the correct fold along every axis
follows:

| `measure_type` | along **time** | along **categorical** | example |
|---|---|---|---|
| `flow` | `additive` | `additive` | units sold in a period |
| `stock` | **`none`** | `additive` | inventory on hand |
| `intensive` | `average` | `average` | a duration, a rate, a ratio |
| `precomputed` | `none` | `none` | a stored rate at the grain it was computed for |
| `target` | `none` | `none` | a sales goal |

Read a row: **`stock` is additive across products and not across months.** That single cell is the
semi-additive balance problem, and it is why the type cannot be a boolean.

Read a column: **only `flow` is safe to sum along time.** Everything else either averages or must be
read rather than folded.

---

## `mac.concept.column.measure_type` — what kind of quantity it is

<!-- BEGIN GENERATED:vocabulary-terms:concept.column.measure_type (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> How a measure aggregates — defined once, over axis_kind.

*`mac.concept.column.measure_type` · 5 terms · closed — these are all of them*

#### `mac.concept.column.measure_type.flow`

A quantity that accrues per period and accumulates over time (e.g. units sold in a period).

| field | value |
|---|---|
| `additivity` | time: mac.concept.aggregation_effect.additive · categorical: mac.concept.aggregation_effect.additive |

#### `mac.concept.column.measure_type.stock`

A level read at a point in time; it does not accumulate over time (e.g. inventory on hand).

| field | value |
|---|---|
| `additivity` | time: mac.concept.aggregation_effect.none · categorical: mac.concept.aggregation_effect.additive |

#### `mac.concept.column.measure_type.intensive`

A per-entity magnitude that is meaningful only as an average, never a total (e.g. a duration, an
age, a rate, a ratio, or a signed deviation). Summing it across a population double-counts or is
meaningless; the correct fold on ANY axis is a mean / median / percentile, not a SUM.

| field | value |
|---|---|
| `additivity` | time: mac.concept.aggregation_effect.average · categorical: mac.concept.aggregation_effect.average |

#### `mac.concept.column.measure_type.precomputed`

A measure whose value EXISTS ONLY at the grains it was computed for — you locate the row
matching the requested axis/parameter combination and read it. Nothing is derivable from
narrower cells: the source documentation describes one such reach measure as non-additive (a sum
or average of the measure is not the measure of the summed or averaged inputs) and computed
iteratively. v0.1.15: `precomputed` is a property of the MEASURE, not of an axis — every axis of
such a measure is simply `none`, because no fold is valid anywhere. Where the value comes from
is a measure_type fact; whether you may fold is an axis fact.

| field | value |
|---|---|
| `additivity` | time: mac.concept.aggregation_effect.none · categorical: mac.concept.aggregation_effect.none |

#### `mac.concept.column.measure_type.target`

A planning target, not an observed quantity (e.g. a sales goal); not summable on any axis.

| field | value |
|---|---|
| `additivity` | time: mac.concept.aggregation_effect.none · categorical: mac.concept.aggregation_effect.none |
<!-- END GENERATED:vocabulary-terms:concept.column.measure_type -->

### Choosing

```
1. Is it a planning number rather than an observation?     → Target
2. Does it exist ONLY at the grains it was computed for?   → Precomputed
3. Is a TOTAL of it meaningless — a rate, ratio, duration? → Intensive
4. Does it accumulate over time?                   yes → Flow    no → Stock
```

Step 4 is the one that is got wrong. *"Does it accumulate?"* — units sold in January plus units sold
in February **is** units sold in the quarter, so `Flow`. Inventory in January plus inventory in
February is **not** inventory in the quarter, so `Stock`.

### Worked — contoso's four measures

| measure | type | why |
|---|---|---|
| `QuantitySold` | `Flow` | items sold accumulate; summable across markets and currencies |
| `GrossSalesAmount` | `Flow` | accrues per period — **but carries a currency**, see below |
| `NetSalesAmount` | `Flow` | likewise |
| `ExchangeRate` | `Precomputed` | a ratio that exists at the (pair, day) it was computed for; you **locate** the row, never fold it |

**`unit` does work the type does not.** `GrossSalesAmount` is `Flow`, so `SUM` is legal along every
axis — and its unit declares that it is *"denominated in the order's own CurrencyCode (5 measured
values) — NOT a single reporting currency"*, so two figures may be compared *"only when both are
restricted to one currency, or both converted"*.

**The type licenses the fold. The unit licenses the comparison.** `QuantitySold` shows the other
edge of it: summable everywhere, and its unit says a television and a cable each count 1, so a total
across categories answers *"how many"* and never *"how much"*.

---

## `mac.concept.axis_kind` — which kind of axis you are folding along

<!-- BEGIN GENERATED:vocabulary-terms:concept.axis_kind (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> The additivity-relevant classification of an aggregation axis.

*`mac.concept.axis_kind` · 2 terms · closed — these are all of them*

#### `mac.concept.axis_kind.time`

An ordered temporal axis (day, month, quarter). Stocks do not accumulate along it.

#### `mac.concept.axis_kind.categorical`

A non-temporal entity/dimension axis (product, location, customer). Flows and stocks are
additive along it.
<!-- END GENERATED:vocabulary-terms:concept.axis_kind -->

Two kinds, because only time has the property that matters: **a stock does not accumulate along it.**
Product, store and customer all behave the same way for folding, so they are one kind.

---

## `mac.aggregation_effect` — the correct fold for one (measure, axis) pair

<!-- BEGIN GENERATED:vocabulary-terms:concept.aggregation_effect (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> THE CORRECT FOLD of a measure along a single axis. Every term names the OPERATION, so the set
answers one question in one grammar: "how do I fold this measure along this axis?" v0.1.15
REPLACED THE PREVIOUS FOUR. They answered the same question in three different grammars —
`additive` named a property, `averageable` named a capability, `non_aggregable` named a negated
capability, and `point_in_time` named a POINT IN TIME rather than any operation at all, leaving
a reader to infer the fold. Worse, the old set sat beside a second, LOSSY scale
(mac.schema.json#additivityAxis: additive | non-additive) whose legacy spelling `non_additive`
was one character from `non_aggregable`, in a different scale, meaning something else. Eight
<dataset> rules fell into exactly that gap and guarded on a value no register could hold.
`last`/`point_in_time` MERGED INTO `precomputed`, on the bundles' own evidence: an inventory
measure says "READ the level at the END of the period" and a reach measure says "READ as stored
... resolve to the matching pre-computed abstraction level instead of folding". Both READ a
stored row and refuse to fold; they differ only in WHICH row, which is a RESOLUTION question and
already lives in each concept's `resolve.*` rules, never in the fold vocabulary.

*`mac.concept.aggregation_effect` · 3 terms · closed — these are all of them*

#### `mac.concept.aggregation_effect.additive`

SUM is correct across this axis.

#### `mac.concept.aggregation_effect.average`

SUM is MEANINGLESS across this axis (a total of durations, rates or ratios is not a number
anyone wants); the correct fold is a mean / median / percentile. Not a weaker `additive` — the
two disagree about whether the sum means anything.

#### `mac.concept.aggregation_effect.none`

NO fold is valid along this axis. If a value is needed at a coarser grain it must already EXIST
as a stored row: RESOLVE it, never compute it. Which row that is, is determined for the TIME
axis by mac_rules.yaml#mac.resolve.period_reading (a bare period reads its END cell) and needs
no per-concept rule. Only a NON-time axis whose answer genuinely varies — a reach measure
resolving to a matching abstraction level — needs the concept to say.
<!-- END GENERATED:vocabulary-terms:concept.aggregation_effect -->

**Every term names an OPERATION**, and that is deliberate. The vocabulary records why the previous
four were replaced: they answered one question in three grammars — `additive` named a property,
`averageable` a capability, `non_aggregable` a negated capability, and `point_in_time` named a point
in time rather than any operation at all, leaving a reader to infer the fold. It also sat beside a
second, lossy scale whose spelling `non_additive` was one character from `non_aggregable`, in a
different scale, meaning something else. **Eight rules fell into that gap and guarded on a value no
register could hold.**

`none` is the one to read carefully. It does not mean *"refuse"* — it means **no fold is valid, so if
a value is needed at a coarser grain it must already EXIST as a stored row: resolve it, never
compute it.**

---

## What a question does with a dimension — `mac.binding_mode`

A different axis from everything above. `measure_type` is intrinsic to the measure; **this is
per-question** — the interpreter assigns it to every dimension the question names.

<!-- BEGIN GENERATED:vocabulary-terms:binding_mode (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> The role a question binds a dimension with — restrict (a member-set scope) vs partition (a
per-member breakdown axis).

*`mac.binding_mode` · 2 terms · closed — these are all of them*

#### `mac.binding_mode.restrict`

A member or member-SET is named as a SCOPE (one value or many, however the set is derived or
expanded). It constrains WHERE and does NOT enter GROUP BY; its folded members are disclosed
under ASSUMPTIONS, never spread into result rows. Cardinality-agnostic: a set of many members is
still one filter.

#### `mac.binding_mode.partition`

The question asks to SEE the dimension varied PER-MEMBER (break it down / enumerate / rank it /
'per <axis>' / 'by <axis>' / 'each' / 'which <axis>'). It enters GROUP BY, one row per member —
the dimension is a breakdown axis, not a filter.
<!-- END GENERATED:vocabulary-terms:binding_mode -->

| the question | `Country` is bound as | SQL |
|---|---|---|
| *sales **in** Germany* | `restrict` | `WHERE Country = 'DE'` |
| *sales **in** Europe* | `restrict` — still one filter | `WHERE Country IN ('DE','FR','GB','IT','NL')` |
| *sales **by** country* | `partition` | `GROUP BY Country` |

**Cardinality is irrelevant.** A scope resolving to five members is still **one** `restrict`, not a
partition — which is why a continent roll-up filters rather than groups.

**Why it matters to folding:** a `partition` enters `GROUP BY`, so the grain law applies to it; a
`restrict` constrains `WHERE` and its folded members are disclosed under assumptions, never spread
into result rows.

> **Not yet read.** `binding_mode` is declared in the framework vocabulary and nothing in the runtime
> consults it — the planner infers restrict-vs-partition from the intent's shape instead. The two
> agree today; nothing checks that they will.

---

## What a violation looks like

```
> total inventory by quarter

REFUSED (ADDITIVITY_VIOLATION)
InventoryOnHand is mac.concept.column.measure_type.stock — along a time axis its fold is
`none`: a level does not accumulate. Sum it across products, or read the
level at a stated point in time.
```

The refusal quotes the contract text, so the reader learns the modelling fact and not merely that
something failed.

## Limits

- **`measure_type` and `additivity` are read and enforced** — `_check_additivity` in the planner,
  with a typed `ADDITIVITY_VIOLATION`.
- **`semantics.axis_kinds` is declared and read by nothing.** Zero contoso concepts populate it, so
  axis classification is inferred rather than declared.
- **`binding_mode` is not read.**
- **`unit` is prose.** It carries the comparison rules — same-currency, dimensionless, what a count
  does not license — and nothing enforces them. Two `GrossSalesAmount` figures in different
  currencies will add without complaint.
