---
title: "Canon — axis_default"
part_of: reference_manual/canon
status: reference   # illustrative reference implementation, not a finished production function
scope: GENERIC — domain-neutral. Examples from example_shop_ontology/.
---

# Canon — `axis_default`

> A **transform** canon (it *rewrites* the query, unlike a guard which only catches). Realizes
> `mac.rule_kind.default`: when an orthogonal axis is left unspecified but a safe default exists, inject it.
> Single-homed here; bound via `realized_by: { udf, params }`. See the [content model](../the_content_model.md).

## Serves

The [`tracking_vintage`](../patterns/tracking_vintage.md) pattern (default `scenario = ACTUAL`) — and any
concept with a `default` rule over an unspecified-but-safe axis.

## Contract (the pluggable interface)

- **Signature:** `axis_default(sql, *, axis_column, default_value, dialect="trino") -> (sql, params)`
- **Params:** `axis_column` (the orthogonal axis), `default_value` (what to assume when it is unconstrained).
- **Guarantee:** if the query does **not** constrain `axis_column`, inject `axis_column = ?` bound to
  `default_value`. Values are **bound (`?`), never interpolated** (FRAMEWORK §6 — the security rule).
- **Returns:** the (possibly rewritten) SQL and the bound params (`[]` if nothing was injected).

## Reference implementation

```python
import sqlglot
from sqlglot import exp

CANON = "axis_default"

def axis_default(sql: str, *, axis_column: str, default_value, dialect: str = "trino"):
    """If the query does not constrain `axis_column`, inject `axis_column = ?` bound to default_value.
    The value is BOUND, never interpolated (FRAMEWORK §6). Transform canon — it rewrites the query."""
    tree = sqlglot.parse_one(sql, read=dialect)
    top = tree.find(exp.Select)
    where = top.args.get("where")
    present = bool(where) and any(c.name == axis_column for c in where.find_all(exp.Column))
    if present:
        return sql, []
    top.where(f"{axis_column} = ?", append=True, dialect=dialect)
    return top.sql(dialect=dialect), [default_value]
```

## How a concept plugs in

```yaml
realized_by: { udf: axis_default, params: { axis_column: scenario, default_value: ACTUAL } }
```

It **composes** with [`additivity_guard`](additivity_guard.md): `axis_default` injects the default
scenario, `additivity_guard` (with `{ scenario: non_aggregable }`) catches a `SUM` across scenarios. A
pattern's `realized_by` may therefore be a **list** of canons.

## Demonstration

```python
axis_default("SELECT SUM(amount) FROM sales_fact WHERE month = '2026-03'",
             axis_column="scenario", default_value="ACTUAL")
# → ("SELECT SUM(amount) FROM sales_fact WHERE month = '2026-03' AND scenario = ?", ["ACTUAL"])

axis_default("SELECT SUM(amount) FROM sales_fact WHERE scenario = 'PLAN'",
             axis_column="scenario", default_value="ACTUAL")
# → ("SELECT SUM(amount) FROM sales_fact WHERE scenario = 'PLAN'", [])   # already pinned — untouched
```

## Determinism & honest limits (AUTHORING A5)

- **Deterministic**; respects the bind-not-interpolate security rule.
- **Top-level scope only** — does not detect the axis being pinned inside a subquery/CTE, and rewrites only
  the outermost `SELECT`. A production version walks every scope and accounts params per scope.
- **A transform, not a judge** — it assumes the default is genuinely safe; deciding *whether* a safe default
  exists is the modeller's call (`mac.rule_kind.default` vs `ambiguity` → ask). Reference, not finished.
