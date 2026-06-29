---
title: "Pattern — Semi-additive balance (a level read at a point in time)"
part_of: reference_manual/patterns
status: prototype
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (illustrative shop scenario).
---

# Pattern — Semi-additive balance

## Initial state — what you're handed

The warehouse system writes one inventory row per product, per warehouse, **per day**:

```sql
CREATE TABLE inventory_snapshot (
  snapshot_date DATE,
  product_id    VARCHAR,
  warehouse_id  VARCHAR,
  units_on_hand INTEGER
);
```

| snapshot_date | product_id | warehouse_id | units_on_hand |
| --- | --- | --- | --- |
| 2026-03-29 | P-100 | WH-DE | 120 |
| 2026-03-30 | P-100 | WH-DE | 118 |
| 2026-03-31 | P-100 | WH-DE | 125 |
| 2026-03-31 | P-100 | WH-US |  60 |

**Why this is dangerous.** `120, 118, 125` are the **same goods** counted on three days — not 363 mugs. But
`125 + 60` across WH-DE and WH-US on one day **is** a real total of 185. The `units_on_hand` column gives no
hint which axis is which: `SUM` is correct across warehouses and catastrophically wrong across time, and
nothing in the schema tells you so.

## The question, and the answer

> **The question** (what the data can't tell you): *Is `units_on_hand` additive over time?*
>
> **The answer** (the fact we supply): *No — it is a **Stock**: point-in-time over time, additive across
> entities (warehouses). Declared once on `MeasureType`, inherited by every query.*

## The pattern (the structured entry)

```yaml
pattern: semi_additive_balance
also_known_as: [semi-additive fact, period-end balance, stock measure, level measure, snapshot measure]
tradition: dimensional
constellation: >
  A measure that is a LEVEL read at a point in time — units of a product on hand, an account balance, a
  headcount. It is additive across entities (total stock = sum of stock across warehouses) but NOT additive
  across time (summing Monday's stock + Tuesday's stock is meaningless — you double-count the same goods).
prior_art:
  relational: >
    Just a numeric column. Nothing in the schema says "do not sum me across time." SUM(units_on_hand) over
    a date range runs happily and returns a number ~N× too large, where N is the number of snapshots.
  dimensional: >
    Kimball names it precisely — a "semi-additive" fact — and the rule (sum across other dimensions, but
    take last/average/period-end across time) is documented. But the rule lives in the modeller's head and
    the cube's config; whether it is enforced depends on the BI tool, and a hand-written query bypasses it.
  rdf: >
    A datatype property holding a number. RDF carries no additivity semantics at all; the "never sum across
    time" fact has nowhere to live.
mac_expression: >
  class: measure, with `semantics.additivity` referencing `mac.MeasureType.Stock`. The additivity LAW is
  stated ONCE on the type, over axis KINDS (Stock × time = point_in_time; Stock × categorical = additive),
  and the measure references it rather than re-encoding it. An agent reads the law and SUMs across
  warehouses but takes the value AT the grain (or last/avg) across months — because the artifact says time
  is point_in_time for a Stock.
why_better: >
  Additivity is intrinsic to the measure TYPE and declared in the model, so the most common analytics
  footgun is closed BY CONSTRUCTION rather than by discipline. The agent literally cannot choose to SUM
  across time without contradicting a stated fact — and a reviewer can check it. The same declaration
  projects to a semi-additive measure in a cube and degrades to an annotation in a graph; the meaning is
  stated once and kept everywhere.
projects_to:
  rdf: "numeric datatype property + an additivity annotation"
  graph: "numeric property + an additivity note on the node"
  relational: "a semi-additive measure in the cube / a documented level column"
antipattern: >
  Re-encoding additivity on every measure (duplication — the law belongs on the type), or omitting it
  entirely (the agent assumes additive and sums the stock across time). The rule-count smell C6 if every
  measure grows its own "don't sum over time" note instead of pointing at the type.
status: scattered   # the additivity law (mac.MeasureType × axis_kind) exists; "semi-additive balance" was never named as a pattern
canon_ref: [mac_vocabulary.yaml (MeasureType × axis_kind), CONCEPT_SPEC.md §6 semantics.additivity, MODELLERS_COOKBOOK.md C6]
```

## The determinism border

Per [AUTHORING.md](../AUTHORING.md) A4, this pattern is — unusually — **fully deterministic once typed**; it
has no interpretative remainder at all:

| Behaviour | Kind | How |
| --- | --- | --- |
| Which axis is additive vs point-in-time | **skeleton** | `MeasureType.Stock × axis_kind` — typed, no prose |
| `SUM(units_on_hand)` may not cross the time axis unpinned | **canon-backed** | the [`additivity_guard`](../canon/additivity_guard.md) canon |
| anything interpretative | **none** | the cleanest case: skeleton + canon → 100% determinism coverage |

**The canon** — and note its params are *not hand-authored*: they are the **projection of the measure's type
law** over the axes (so the skeleton *feeds* the canon):

```yaml
additivity:
  prose: "InventoryLevel is a Stock: additive across warehouses, point-in-time over time."
  realized_by:
    udf: additivity_guard
    params:
      measure_column: units_on_hand
      axis_effects: { snapshot_date: point_in_time, warehouse_id: additive }   # = MeasureType.Stock × axis_kind
```

Because `axis_effects` is derived from `MeasureType.Stock × axis_kind` (already in the ontology), the guard
is **auto-pluggable** — write the type, the params follow. Contrast `context_dependent_meaning`, which keeps
a genuine prose-fallback ("which brand?"); here there is none.

## The footgun, concretely

The shop keeps a daily `inventory_snapshot` of `units_on_hand` per product per warehouse. Ask an agent
*"how much stock did we hold last quarter?"*

```sql
-- GUESS (plausible, and wrong): sums ~90 daily snapshots → ~90× overstated
SELECT SUM(units_on_hand) FROM inventory_snapshot
WHERE snapshot_date BETWEEN '2026-01-01' AND '2026-03-31';
```

```sql
-- GROUNDED: Stock is point_in_time over time, additive across warehouses.
-- Take the level at a point (here period-end), summed across warehouses.
SELECT SUM(units_on_hand) FROM inventory_snapshot
WHERE snapshot_date = '2026-03-31';     -- one point in time; sum only across the categorical (warehouse) axis
```

The two queries differ by ~90×. The difference is not cleverness — it is one declared fact
(`Stock × time = point_in_time`) that the first query had no way to know and the second inherited from the
model. That is the entire argument of Chapter 01, reduced to a single `SUM`.
