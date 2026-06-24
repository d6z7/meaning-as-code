---
title: "Canon — exclusion_filter"
part_of: reference_manual/canon
status: reference   # illustrative reference implementation, not a finished production function
scope: GENERIC — domain-neutral. Examples from example_shop_ontology/.
---

# Canon — `exclusion_filter`

> A **transform** canon realizing `mac.rule_kind.exclusion`: it injects a predicate that removes
> **reliably-identifiable** junk (test rows, known buckets, unmapped sentinels). It is the **bake**
> disposition of [`impurity_disposition`](../patterns/impurity_disposition.md) — and *only* that: it does
> not touch the partially- or not-separable residual (those are register / block). Single-homed here.

## Serves

The [`impurity_disposition`](../patterns/impurity_disposition.md) pattern (bake disposition) — and any
concept with an `exclusion` rule over reliably-identifiable rows.

## Contract (the pluggable interface)

- **Signature:** `exclusion_filter(sql, *, column, not_in=None, not_like=None, dialect="trino") -> (sql, params)`
- **Params:** `not_in` (exact values to drop), `not_like` (patterns to drop). At least one.
- **Guarantee:** appends `column NOT IN (?…)` and/or `column NOT LIKE ?` to the query. Values are
  **bound (`?`), never interpolated** (FRAMEWORK §6).
- **Returns:** the rewritten SQL and the bound params (`[]` if no exclusions given).
- **Scope limit (deliberate):** excludes only what the caller asserts is *reliably* junk — never guesses.

## Reference implementation

```python
import sqlglot
from sqlglot import exp

CANON = "exclusion_filter"

def exclusion_filter(sql: str, *, column: str, not_in=None, not_like=None, dialect: str = "trino"):
    """Inject an exclusion predicate removing reliably-identifiable junk on `column` (the BAKE disposition).
    Values BOUND (?), never interpolated (FRAMEWORK §6). Transform canon — it rewrites the query."""
    not_in, not_like = not_in or [], not_like or []
    conds, params = [], []
    if not_in:
        conds.append(f"{column} NOT IN ({', '.join('?' for _ in not_in)})")
        params += list(not_in)
    conds += [f"{column} NOT LIKE ?" for _ in not_like]
    params += list(not_like)
    if not conds:
        return sql, []
    top = sqlglot.parse_one(sql, read=dialect).find(exp.Select)
    top.where(" AND ".join(conds), append=True, dialect=dialect)
    return top.sql(dialect=dialect), params
```

## How a concept plugs in

```yaml
# the BAKE disposition: P-TEST-* are reliably QA fixtures → excluded in the served view
realized_by:
  udf: exclusion_filter
  params: { column: product_id, not_like: ['P-TEST-%'] }
# NOTE: P-MISC is NOT excluded here — its status is undecidable without an SME (block/register, not bake).
```

## Demonstration

```python
exclusion_filter("SELECT count(*) FROM product", column="product_id", not_like=["P-TEST-%"])
# → ("SELECT count(*) FROM product WHERE product_id NOT LIKE ?", ["P-TEST-%"])

exclusion_filter("SELECT count(*) FROM product",
                 column="product_id", not_in=["P-MISC"], not_like=["P-TEST-%"])
# → ("SELECT count(*) FROM product WHERE product_id NOT IN (?) AND product_id NOT LIKE ?",
#     ["P-MISC", "P-TEST-%"])
```

## Determinism & honest limits (AUTHORING A5)

- **Deterministic**; binds, never interpolates.
- **Bake only** — it removes what is *reliably* identifiable; it cannot decide the *partially-* or
  *not-separable* cases (those are the register and block dispositions — not this canon's job).
- **Top-level scope only**; a production version walks subqueries/CTEs. Reference, not finished.
