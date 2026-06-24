---
title: "Canon — composite_key_guard"
part_of: reference_manual/canon
status: reference   # illustrative reference implementation, not a finished production function
scope: GENERIC — domain-neutral. Examples from example_shop_ontology/.
---

# Canon — `composite_key_guard`

> A **canon** is a generic, parameterized UDF — the deterministic realization of a behaviour-bearing slot.
> Its logic is **single-homed here** (AUTHORING A3) and bound to a concept's columns via
> `realized_by: { udf, params }`. Concepts name it; they never restate its logic. See the
> [content model](../the_content_model.md) §4–§5. *(This entry also doubles as the template for future
> canon entries: Serves · Contract · Reference implementation · Plug-in · Demonstration · Limits.)*

## Serves

The [`context_dependent_meaning`](../patterns/context_dependent_meaning.md) pattern — and **any** concept
whose code is **parent-scoped** (meaningless, and not comparable across rows, without a parent/scope column).

## Contract (the pluggable interface)

- **Signature:** `composite_key_guard(sql, *, code_column, scope_columns, dialect="trino") -> list[str]`
- **Params:**
  - `code_column` — the parent-scoped code (e.g. `size_code`).
  - `scope_columns` — the parent key(s) that complete its identity (e.g. `[brand_id]`).
- **Guarantee:** rejects any query scope that **constrains or `GROUP BY`s** `code_column` without **all**
  `scope_columns` constrained in the **same** scope.
- **Returns:** a list of violation messages; **empty list == passes**. It is a *guard* — it **catches**, it
  does not rewrite.
- **Determinism:** same `(sql, params)` → same verdict, with **no model in the loop**.

## Reference implementation

```python
import sqlglot
from sqlglot import exp

CANON = "composite_key_guard"   # its registered name in the canon library

def composite_key_guard(sql: str, *, code_column: str, scope_columns: list[str],
                        dialect: str = "trino") -> list[str]:
    """Generic canon for the context_dependent_meaning pattern.
    A parent-scoped code may be CONSTRAINED or GROUPED only together with its scope columns.
    Rejects any SELECT scope that touches `code_column` without all `scope_columns` present.
    The logic lives here ONCE; a concept supplies only (code_column, scope_columns)."""
    out: list[str] = []
    for select in sqlglot.parse_one(sql, read=dialect).find_all(exp.Select):
        if _constrained(select, code_column):
            missing = [s for s in scope_columns if not _constrained(select, s)]
            if missing:
                out.append(f"`{code_column}` used without its scope {missing}; "
                           f"identity is ({code_column}, {scope_columns}).")
    return out

def _constrained(select: exp.Select, col: str) -> bool:
    """True if `col` appears in WHERE / HAVING / GROUP BY / a JOIN condition of this SELECT."""
    zones = [select.args.get("where"), select.args.get("having"), select.args.get("group"),
             *[j.args.get("on") for j in select.find_all(exp.Join)]]
    return any(any(c.name == col for c in z.find_all(exp.Column)) for z in zones if z)
```

## How a concept plugs in

The concept names the canon and binds its parameters — nothing more (logic stays in this file):

```yaml
# size scoped by brand (the worked pattern)
realized_by: { udf: composite_key_guard, params: { code_column: size_code, scope_columns: [brand_id] } }

# SAME canon, a different concept — an order status whose meaning differs per sales channel
realized_by: { udf: composite_key_guard, params: { code_column: status, scope_columns: [channel] } }
```

That reuse — one function, many concepts, parameters only — is what "generally pluggable" means.

## Demonstration

```python
composite_key_guard("SELECT count(*) FROM product WHERE size_code='M'",
                    code_column="size_code", scope_columns=["brand_id"])
# → ["`size_code` used without its scope ['brand_id']; identity is (size_code, ['brand_id'])."]   REJECTED

composite_key_guard("SELECT count(*) FROM product WHERE brand_id='BR-NORD' AND size_code='M'",
                    code_column="size_code", scope_columns=["brand_id"])
# → []   PASSES
```

A weak model that forgets the rule still cannot ship the bad query: the guard rejects bare `size_code='M'`.

## Determinism & honest limits (AUTHORING A5)

- **Deterministic** where it reaches: parsed and run, not read.
- **A guard, not a resolver** — it catches the conflation; it does not auto-rewrite the query.
- **Needs a SQL parser/dialect** (`sqlglot` here).
- **A production version must handle** CTEs, table aliases, correlated subqueries, and column-name ambiguity
  across joins (a bare column name may not bind to the intended table). This is a **reference**, not a
  finished library function — coverage goes up by building, never by claiming.
