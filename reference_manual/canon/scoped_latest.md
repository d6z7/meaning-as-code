---
title: "Canon — scoped_latest"
part_of: reference_manual/canon
status: reference   # illustrative reference implementation, not a finished production function
scope: GENERIC — domain-neutral. Examples from example_shop_ontology/.
---

# Canon — `scoped_latest`

> A **transform/anchor** canon: it produces "now" as `MAX(date_column)` computed **over a scoped subset**
> (e.g. `scenario = 'ACTUAL'`), never the whole table — so forward-dated plan/budget rows cannot masquerade
> as the latest actual. It supplies the *deterministic anchor*; deciding *which* relative window a question
> means ("last quarter") stays interpretative. Single-homed here.

## Serves

The [`tracking_vintage`](../patterns/tracking_vintage.md) pattern (scoped "latest") — and any relative-period
resolution that must anchor to the latest *actual*, not the planning horizon.

## Contract (the pluggable interface)

- **Signature:** `scoped_latest(table, date_column, *, scope=None, dialect="trino") -> (sql, params)`
- **Params:** `scope` — a `{ column: value }` map pinning the subset (e.g. `{ scenario: ACTUAL }`).
- **Guarantee:** returns a **scalar subquery** `(SELECT MAX(date_column) FROM table WHERE <scope>)` —
  the anchor for "now". Scope values are **bound (`?`), never interpolated** (FRAMEWORK §6).
- **Returns:** the scalar-subquery SQL and its bound params.

## Reference implementation

```python
CANON = "scoped_latest"

def scoped_latest(table, date_column, *, scope=None, dialect="trino"):
    """Return a scalar subquery for 'now' = MAX(date_column) over the SCOPED subset (e.g. scenario='ACTUAL'),
    never the whole table — so forward-dated plan/budget rows can't pose as the latest actual.
    Scope values BOUND (?), never interpolated (FRAMEWORK §6)."""
    scope = scope or {}
    where, params = "", []
    if scope:
        where = " WHERE " + " AND ".join(f"{c} = ?" for c in scope)
        params = list(scope.values())
    return f"(SELECT MAX({date_column}) FROM {table}{where})", params
```

## How a concept plugs in

```yaml
# "latest month" must anchor to actuals, not the plan horizon
realized_by:
  udf: scoped_latest
  params: { table: sales_fact, date_column: month, scope: { scenario: ACTUAL } }
```

## Demonstration

```python
scoped_latest("sales_fact", "month", scope={"scenario": "ACTUAL"})
# → ("(SELECT MAX(month) FROM sales_fact WHERE scenario = ?)", ["ACTUAL"])

scoped_latest("sales_fact", "month")
# → ("(SELECT MAX(month) FROM sales_fact)", [])    # no scope → whole table (use only when there is no axis to pin)
```

The first form is the fix for `tracking_vintage`'s second footgun: a global `MAX(month)` returns the plan
horizon (Dec); scoped to `scenario = 'ACTUAL'` it returns the latest actual (Mar).

## Determinism & honest limits (AUTHORING A5)

- **Deterministic anchor**; binds, never interpolates.
- **Anchor only, not window-resolution** — it gives "now"; turning *"last quarter"* into a date range
  (anchored to this `MAX`) is a separate step, and *which* relative period a question means is
  interpretative (prose-fallback). A later revision may add a `relative=` window-math parameter.
- **Single equality scope** per column. Reference, not finished.
