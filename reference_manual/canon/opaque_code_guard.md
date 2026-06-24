---
title: "Canon — opaque_code_guard"
part_of: reference_manual/canon
status: reference   # illustrative reference implementation, not a finished production function
scope: GENERIC — domain-neutral. Examples from example_shop_ontology/.
---

# Canon — `opaque_code_guard`

> A **guard** canon: an opaque / contaminated code carries no reliable semantics, so its prefix may **not**
> be `LIKE`/substring-matched to identify a family — resolution must go through a **curated** attribute.
> Single-homed here; bound via `realized_by: { udf, params }`.

## Serves

The [`contaminated_code`](../patterns/contaminated_code.md) pattern — any opaque key whose embedded
structure has been reused/overloaded (the domain-neutral form of the "resolve by name, never by code prefix"
principle).

## Contract (the pluggable interface)

- **Signature:** `opaque_code_guard(sql, *, code_column, resolve_via, dialect="trino") -> list[str]`
- **Params:** `code_column` (the opaque code), `resolve_via` (the curated attribute resolution should use).
- **Guarantee:** rejects `code_column LIKE '<prefix>%'` (and similar prefix matching); points to `resolve_via`.
- **Returns:** violation messages; **empty list == passes**.

## Reference implementation

```python
import sqlglot
from sqlglot import exp

CANON = "opaque_code_guard"

def opaque_code_guard(sql: str, *, code_column: str, resolve_via: str, dialect: str = "trino") -> list[str]:
    """Reject prefix/LIKE matching on an opaque (contaminated) code; resolve families via `resolve_via`
    (a curated attribute). The code carries no reliable semantics. Logic lives here once."""
    out: list[str] = []
    for like in sqlglot.parse_one(sql, read=dialect).find_all(exp.Like):
        target = like.this
        if target is not None and code_column in {c.name for c in target.find_all(exp.Column)}:
            out.append(f"`{code_column}` is an opaque/contaminated code; do not LIKE/prefix-match it — "
                       f"resolve via `{resolve_via}` instead.")
    return out
```

## How a concept plugs in

```yaml
realized_by: { udf: opaque_code_guard, params: { code_column: product_code, resolve_via: category } }
```

## Demonstration

```python
opaque_code_guard("SELECT count(*) FROM product WHERE product_code LIKE 'BK%'",
                  code_column="product_code", resolve_via="category")
# → ["`product_code` is an opaque/contaminated code; do not LIKE/prefix-match it — resolve via `category`."]  REJECTED

opaque_code_guard("SELECT count(*) FROM product WHERE category = 'Books'",
                  code_column="product_code", resolve_via="category")
# → []   PASSES — resolved via the curated attribute
```

## Determinism & honest limits (AUTHORING A5)

- **Deterministic**; catches the `LIKE`-prefix misuse.
- **`LIKE` only** — a production version also catches `substr(code,1,2) = 'BK'`, `starts_with(code, 'BK')`,
  and regex prefix matching. It does not (and shouldn't) block `code = '<exact>'` used purely as a join key.
- Reference, not finished — coverage goes up by building.
