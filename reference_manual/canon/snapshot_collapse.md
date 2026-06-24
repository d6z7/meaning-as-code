---
title: "Canon — snapshot_collapse"
part_of: reference_manual/canon
status: reference   # illustrative reference implementation, not a finished production function
scope: GENERIC — domain-neutral. Examples from example_shop_ontology/.
---

# Canon — `snapshot_collapse`

> A **query-shape** canon (`applied_as: subquery_wrapper`): it produces a relation already collapsed to one
> row per entity, so downstream aggregation cannot multiply facts across versions. Single-homed here; bound
> via `realized_by: { udf, params }`. See the [content model](../the_content_model.md).

## Serves

The [`scd_type_2`](../patterns/scd_type_2.md) pattern — and any versioned/snapshotted relation that must be
reduced to a current (or as-of) view before use.

## Contract (the pluggable interface)

- **Signature:** `snapshot_collapse(table, *, natural_key, order_by, valid_from=None, valid_to=None, as_of=None) -> (sql, params)`
- **Params:** `natural_key` (the stable business key), `order_by` (the version-ordering column, e.g.
  `valid_from`); for an explicit as-of: `valid_from`/`valid_to` (the validity window) and `as_of` (the date).
- **Guarantee:** returns a relation with **exactly one row per `natural_key`** — the version valid **as of**
  a bound date if given, else the **latest**. The as-of value is **bound (`?`), never interpolated** (FW §6).
- **Returns:** the SQL relation (a parenthesised subquery) and its bound params.

## Reference implementation

```python
CANON = "snapshot_collapse"

def snapshot_collapse(table, *, natural_key, order_by, valid_from=None, valid_to=None, as_of=None):
    """Collapse a versioned relation to one row per natural_key: the version valid AS OF a bound date,
    else the latest. Values BOUND (?), never interpolated (FRAMEWORK §6). Query-shape canon."""
    if as_of is not None:
        pred = f"{valid_from} <= ? AND ({valid_to} IS NULL OR {valid_to} > ?)"
        return f"(SELECT * FROM {table} WHERE {pred})", [as_of, as_of]
    sql = (f"(SELECT * FROM (SELECT *, ROW_NUMBER() OVER "
           f"(PARTITION BY {natural_key} ORDER BY {order_by} DESC) AS _rn "
           f"FROM {table}) WHERE _rn = 1)")
    return sql, []
```

## How a concept plugs in

```yaml
grounding:
  prose: "dim_product keeps SCD-2 history; collapse to the current version unless an as-of is given."
  realized_by:
    udf: snapshot_collapse
    applied_as: subquery_wrapper
    params: { table: dim_product, natural_key: product_id, order_by: valid_from, valid_to: valid_to }
```

## Demonstration

```python
snapshot_collapse("dim_product", natural_key="product_id", order_by="valid_from")
# → ("(SELECT * FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY valid_from DESC)
#      AS _rn FROM dim_product) WHERE _rn = 1)", [])           # one row per product — the current version

snapshot_collapse("dim_product", natural_key="product_id", order_by="valid_from",
                  valid_from="valid_from", valid_to="valid_to", as_of="2026-01-15")
# → ("(SELECT * FROM dim_product WHERE valid_from <= ? AND (valid_to IS NULL OR valid_to > ?))",
#     ["2026-01-15", "2026-01-15"])                            # the version valid on that date
```

## Determinism & honest limits (AUTHORING A5)

- **Deterministic**; honours bind-not-interpolate.
- **Single-column `natural_key`/`order_by`** in this reference — a composite key needs a column list and a
  composite `PARTITION BY`.
- **Tie-breaks** (two rows with the same `valid_from`) are not resolved; a production version adds a
  deterministic secondary sort (e.g. surrogate key).
- **Assumes ROW_NUMBER support** in the target dialect. Reference, not finished.
