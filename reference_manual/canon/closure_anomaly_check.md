---
title: "Canon — closure_anomaly_check"
part_of: reference_manual/canon
status: reference   # illustrative reference implementation, not a finished production function
scope: GENERIC — domain-neutral. Examples from example_shop_ontology/.
---

# Canon — `closure_anomaly_check`

> A **conditional generator** canon: it *generates* a data-quality check, but only when the value set is
> closed — and **declines** (returns nothing) when it is open. The skeleton `closure` flag decides whether
> the check exists at all. Single-homed here; bound via `realized_by: { udf, params }`.

## Serves

The [`explicit_closure`](../patterns/explicit_closure.md) pattern — any enumeration whose `closure` governs
whether an "unknown value" is an **anomaly** (closed) or **expected** (open).

## Contract (the pluggable interface)

- **Signature:** `closure_anomaly_check(table, column, *, closure, known_values) -> (sql, params) | None`
- **Params:** `closure` (`closed` / `open` / `unknown`), `known_values` (the enumeration's members).
- **Guarantee:** for `closed`, returns a query selecting rows whose `column` value is **not** among
  `known_values` (the anomalies). For `open`/`unknown`, returns **`None`** — an unseen value is expected, so
  no false-alarming check is emitted. Values are **bound (`?`), never interpolated** (FW §6).
- **Returns:** `(sql, params)` for a closed set; `None` otherwise.

## Reference implementation

```python
CANON = "closure_anomaly_check"

def closure_anomaly_check(table, column, *, closure, known_values):
    """For a CLOSED enumeration, return the anomaly query (rows with an unknown value).
    For open/unknown closure, return None — an unseen value is expected, not an anomaly.
    Values BOUND (?), never interpolated (FRAMEWORK §6). The skeleton `closure` flag decides."""
    if closure != "closed":
        return None
    placeholders = ", ".join("?" for _ in known_values)
    sql = f"SELECT DISTINCT {column} FROM {table} WHERE {column} NOT IN ({placeholders})"
    return sql, list(known_values)
```

## How a concept plugs in

```yaml
# OrderStatus — closed: the check exists and fires on any unknown status
realized_by:
  udf: closure_anomaly_check
  params: { table: orders, column: status, closure: closed,
            known_values: [PLACED, PAID, SHIPPED, DELIVERED, RETURNED, CANCELLED] }

# PaymentMethod — open: the SAME canon returns None → no check, no false alarms
realized_by:
  udf: closure_anomaly_check
  params: { table: orders, column: payment_method, closure: open,
            known_values: [CARD, PAYPAL, INVOICE] }
```

## Demonstration

```python
closure_anomaly_check("orders", "status", closure="closed",
                      known_values=["PLACED","PAID","SHIPPED","DELIVERED","RETURNED","CANCELLED"])
# → ("SELECT DISTINCT status FROM orders WHERE status NOT IN (?, ?, ?, ?, ?, ?)",
#     ["PLACED","PAID","SHIPPED","DELIVERED","RETURNED","CANCELLED"])      # a valid anomaly check

closure_anomaly_check("orders", "payment_method", closure="open",
                      known_values=["CARD","PAYPAL","INVOICE"])
# → None                                                                   # open set — no check (correct)
```

## Determinism & honest limits (AUTHORING A5)

- **Deterministic**; the skeleton `closure` flag drives the branch (skeleton feeds canon).
- **`NULL` handling** — `NOT IN` with a `NULL` in the column or list behaves per SQL three-valued logic; a
  production version handles `NULL` explicitly.
- **Case / whitespace** normalization of values is not applied. Reference, not finished.
