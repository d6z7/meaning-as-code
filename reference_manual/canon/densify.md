---
title: "Canon — densify"
part_of: reference_manual/canon
status: reference   # illustrative reference implementation, not a finished production function
scope: GENERIC — domain-neutral. Examples from example_shop_ontology/.
---

# Canon — `densify`

> A **transform** canon for `null_semantics = genuine_zero`: it `LEFT JOIN`s a sparse fact onto the complete
> **grid** of cells that *should* exist and `COALESCE`s the measure to 0, so absent cells count as zero
> rather than vanish. The skeleton `null_semantics` flag selects it; this canon executes it. Single-homed here.

## Serves

The [`absence_semantics`](../patterns/absence_semantics.md) pattern (the genuine-zero case) — any sparse
measure whose missing rows mean a real zero and must be counted as such in averages, coverage, and totals.

## Contract (the pluggable interface)

- **Signature:** `densify(fact, measure, *, keys, grid, dialect="trino") -> (sql, params)`
- **Params:** `keys` (the cell-identifying columns), `grid` (a SQL relation enumerating **every cell that
  should exist** — the complete date × entity space, restricted to *tracked* cells).
- **Guarantee:** returns the fact `LEFT JOIN`ed onto `grid` with `COALESCE(measure, 0)` — every grid cell
  present, absent ones zeroed. (Only valid when absence means genuine zero; `not_loaded` must **not** use it.)
- **Returns:** the densified SQL relation and its params (`[]` — the grid carries any literals).

## Reference implementation

```python
CANON = "densify"

def densify(fact, measure, *, keys, grid, dialect="trino"):
    """For null_semantics == genuine_zero: LEFT JOIN `fact` onto the complete `grid` of cells and COALESCE
    the measure to 0, so absent cells count as zero (not excluded). `keys` are the join columns; `grid` is a
    relation enumerating every cell that SHOULD exist. Realizes null_semantics=genuine_zero."""
    on = " AND ".join(f"g.{k} = f.{k}" for k in keys)
    sel_keys = ", ".join(f"g.{k}" for k in keys)
    return (f"SELECT {sel_keys}, COALESCE(f.{measure}, 0) AS {measure} "
            f"FROM ({grid}) g LEFT JOIN {fact} f ON {on}"), []
```

## How a concept plugs in

```yaml
semantics:
  null_semantics: genuine_zero
  realized_by:
    udf: densify
    params: { fact: daily_sales, measure: units, keys: [sale_date, store_id, product_id],
              grid: "SELECT d.sale_date, sp.store_id, sp.product_id FROM calendar d CROSS JOIN store_product sp" }
```

## Demonstration

```python
densify("daily_sales", "units",
        keys=["sale_date", "store_id", "product_id"],
        grid="SELECT d.sale_date, sp.store_id, sp.product_id FROM calendar d CROSS JOIN store_product sp")
# → ("SELECT g.sale_date, g.store_id, g.product_id, COALESCE(f.units, 0) AS units "
#    "FROM (SELECT d.sale_date, sp.store_id, sp.product_id FROM calendar d CROSS JOIN store_product sp) g "
#    "LEFT JOIN daily_sales f ON g.sale_date = f.sale_date AND g.store_id = f.store_id "
#    "AND g.product_id = f.product_id", [])
```

## Determinism & honest limits (AUTHORING A5)

- **Deterministic** given a correct grid.
- **The grid is the hard part** — defining the complete, *tracked* cell space is domain work (a calendar ×
  the store/product pairs each store actually carries). `structurally_untracked` cells must be excluded *from
  the grid*, or densify will fabricate zeros for products a store never sold.
- **genuine_zero only** — `not_loaded` must NOT be densified (that would impute a zero over missing data);
  it routes to exclude-and-flag instead. Reference, not finished.
