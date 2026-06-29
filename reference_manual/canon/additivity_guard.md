---
title: "Canon — additivity_guard"
part_of: reference_manual/canon
status: reference   # illustrative reference implementation, not a finished production function
scope: GENERIC — domain-neutral. Examples from example_shop_ontology/.
---

# Canon — `additivity_guard`

> A **canon** is a generic, parameterized UDF — the deterministic realization of a behaviour-bearing slot,
> single-homed here and bound to a concept via `realized_by: { udf, params }`. See the
> [content model](../the_content_model.md) §4–§5 and the entry template in
> [composite_key_guard](composite_key_guard.md).

## Serves

The [`semi_additive_balance`](../patterns/semi_additive_balance.md) pattern — and **any** measure whose
additivity differs by axis (a Stock, a Target, a balance). Its parameters are the **projection of
`mac.MeasureType × axis_kind`** over the concrete axes, so for a typed measure they are *derived, not
hand-authored*.

## Contract (the pluggable interface)

- **Signature:** `additivity_guard(sql, *, measure_column, axis_effects, dialect="trino") -> list[str]`
- **Params:**
  - `measure_column` — the measure being aggregated (e.g. `units_on_hand`).
  - `axis_effects` — `{ axis_column: mac.aggregation_effect }`, each effect `additive` / `point_in_time` /
    `non_aggregable`. *(This map is the measure's type law applied to its axes.)*
- **Guarantee — per `mac.aggregation_effect` of each axis** (the full option set, not just the rejecting one):
  - **`additive`** → a `SUM` across that axis is correct; **never flagged**. (The guard does not over-restrict.)
  - **`point_in_time`** → a `SUM` is **rejected** unless the axis is pinned to one value or grouped (take the
    level at the grain, never accumulate it over the axis).
  - **`non_aggregable`** → treated like `point_in_time` here (must be pinned/grouped); conceptually the `SUM`
    fold does not apply at all (a Target) — see limits for the stricter variant.
- **Returns:** violation messages; **empty list == passes**.

## Reference implementation

```python
import sqlglot
from sqlglot import exp

CANON = "additivity_guard"
NON_ADDITIVE = {"point_in_time", "non_aggregable"}

def additivity_guard(sql: str, *, measure_column: str, axis_effects: dict[str, str],
                     dialect: str = "trino") -> list[str]:
    """Generic canon for the semi_additive_balance pattern.
    axis_effects: axis column -> mac.aggregation_effect ('additive'|'point_in_time'|'non_aggregable').
    Rejects SUM(measure_column) that crosses a non-additive axis without pinning it to one value
    or grouping by it. Logic lives here once; a measure supplies (measure_column, axis_effects)."""
    out: list[str] = []
    for select in sqlglot.parse_one(sql, read=dialect).find_all(exp.Select):
        if not _sums(select, measure_column):
            continue
        for axis, effect in axis_effects.items():
            if effect in NON_ADDITIVE and not (_pinned(select, axis) or _grouped(select, axis)):
                out.append(f"SUM(`{measure_column}`) crosses {effect} axis `{axis}`; "
                           f"pin it to one value or GROUP BY it.")
    return out

def _sums(select, col):
    return any(any(c.name == col for c in s.find_all(exp.Column))
               for s in select.find_all(exp.Sum))

def _grouped(select, col):
    g = select.args.get("group")
    return bool(g) and any(c.name == col for c in g.find_all(exp.Column))

def _pinned(select, col):
    """col = <literal / scalar subquery> in WHERE → pinned to a single value."""
    w = select.args.get("where")
    return bool(w) and any(col in {c.name for c in eq.find_all(exp.Column)}
                           for eq in w.find_all(exp.EQ))
```

## How a concept plugs in

```yaml
# InventoryLevel — a Stock: additive across warehouses, point-in-time over time
realized_by:
  udf: additivity_guard
  params:
    measure_column: units_on_hand
    axis_effects: { snapshot_date: point_in_time, warehouse_id: additive }   # = MeasureType.Stock × axis_kind
```

The `axis_effects` are **not invented** — they are `MeasureType.Stock` projected over the axes' kinds
(`time → point_in_time`, `categorical → additive`). The skeleton *feeds* the canon: write the type, the
params follow.

## Demonstration

All three options of `mac.aggregation_effect`, end to end — the guard rejects exactly where additivity
forbids and **passes everywhere it allows** (it does not over-restrict):

```python
# A — FULLY ADDITIVE measure (a Flow, e.g. units_sold): every axis additive → SUM is always correct
additivity_guard("SELECT SUM(units_sold) FROM sales WHERE month BETWEEN '2026-01' AND '2026-03'",
                 measure_column="units_sold",
                 axis_effects={"month": "additive", "product_id": "additive"})
# → []  PASSES — nothing to flag; an additive measure may be summed across any axis

# B — SEMI-ADDITIVE measure (a Stock, units_on_hand): point_in_time over time, additive across warehouses
additivity_guard("SELECT SUM(units_on_hand) FROM inventory_snapshot "
                 "WHERE snapshot_date BETWEEN '2026-01-01' AND '2026-03-31'",
                 measure_column="units_on_hand",
                 axis_effects={"snapshot_date": "point_in_time", "warehouse_id": "additive"})
# → ["SUM(`units_on_hand`) crosses point_in_time axis `snapshot_date`; pin it to one value or GROUP BY it."]  REJECTED

additivity_guard("SELECT SUM(units_on_hand) FROM inventory_snapshot WHERE snapshot_date = DATE '2026-03-31'",
                 measure_column="units_on_hand",
                 axis_effects={"snapshot_date": "point_in_time", "warehouse_id": "additive"})
# → []  PASSES — time pinned to one point; sums only across the additive warehouse axis

# C — NON-AGGREGABLE measure (a Target, sales_target): not summable on any axis
additivity_guard("SELECT SUM(sales_target) FROM plan WHERE month BETWEEN '2026-01' AND '2026-03'",
                 measure_column="sales_target",
                 axis_effects={"month": "non_aggregable", "product_id": "non_aggregable"})
# → ["SUM(`sales_target`) crosses non_aggregable axis `month`; ...",
#    "SUM(`sales_target`) crosses non_aggregable axis `product_id`; ..."]  REJECTED on every axis
```

The contrast is the whole point: **A** shows the guard staying silent when summing is legitimate (it is not
a blanket "no SUM" rule); **B** the classic semi-additive case (reject across time, allow when pinned); **C**
a measure that may not be summed at all.

## Determinism & honest limits (AUTHORING A5)

- **Deterministic** where it reaches; params derivable from the type law (often zero hand-authoring).
- **A guard, not a resolver** — it catches the bad SUM; it does not rewrite to a point-in-time read.
- **`_pinned` is an approximation** — `col = <value>` counts as pinned; it does not yet distinguish a
  literal from `col = other_col`, nor verify a scalar subquery returns one row.
- **A production version must handle** windowed aggregates, `HAVING`, nested aggregations, CTEs/aliases, and
  the `non_aggregable` case (a Target should arguably reject the `SUM` fold outright, not merely require
  pinning). Reference, not finished — coverage goes up by building.
