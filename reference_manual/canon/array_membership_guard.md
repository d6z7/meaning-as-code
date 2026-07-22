---
title: "Canon — array_membership_guard"
part_of: reference_manual/canon
status: reference   # illustrative reference implementation, not a finished production function
scope: GENERIC — domain-neutral. Examples from example_shop_ontology/.
---

# Canon — `array_membership_guard`

> A **guard** canon: a multivalued attribute (an array column, or a value reached through a bridge) must be
> tested with **membership** (`contains` / `EXISTS`), never scalar **equality**. Single-homed here; bound via
> `realized_by: { udf, params }`. See [content model](../the_content_model.md).

## Serves

The [`multivalued_bridge`](../patterns/multivalued_bridge.md) pattern — any attribute a row has *many* of
(tags, categories, segments, labels).

## Contract (the pluggable interface)

- **Signature:** `array_membership_guard(sql, *, column, dialect="trino") -> list[str]`
- **Param:** `column` — the multivalued attribute.
- **Guarantee:** rejects `column = <literal>` (treating a set as a scalar); directs to a membership test.
- **Returns:** violation messages; **empty list == passes**.

## Reference implementation

```python
import sqlglot
from sqlglot import exp

CANON = "array_membership_guard"

def array_membership_guard(sql: str, *, column: str, dialect: str = "trino") -> list[str]:
    """A multivalued attribute must be tested by membership (contains/EXISTS), not scalar `=`.
    Rejects `column = <literal>`. Logic lives here once; a concept supplies `column`."""
    out: list[str] = []
    for eq in sqlglot.parse_one(sql, read=dialect).find_all(exp.EQ):
        if column in {c.name for c in eq.find_all(exp.Column)}:
            out.append(f"`{column}` is multivalued; use a membership test "
                       f"(contains({column}, …) / EXISTS), not `=`.")
    return out
```

## How a concept plugs in

```yaml
realized_by: { udf: array_membership_guard, params: { column: tags } }
```

## Demonstration

```python
array_membership_guard("SELECT * FROM product WHERE tags = 'sale'", column="tags")
# → ["`tags` is multivalued; use a membership test (contains(tags, …) / EXISTS), not `=`."]  REJECTED

array_membership_guard("SELECT * FROM product WHERE contains(tags, 'sale')", column="tags")
# → []   PASSES — contains() is not an equality
```

## Determinism & honest limits (AUTHORING A5)

- **Deterministic** for the array-column case (`contains()` is not an `EQ`, so no false positive).
- **Bridge subtlety** — the *correct* bridge form `EXISTS (SELECT 1 FROM product_tag t WHERE t.tag = 'sale')`
  uses `=` on the **bridge's own** column; a naïve check would flag it. A production version scopes the check
  to the fact, not the membership subquery (same scoping concern as `composite_key_guard`).
- **Catches `=` only** — `IN (…)` and `!=` on a multivalue need their own handling. Reference, not finished.
