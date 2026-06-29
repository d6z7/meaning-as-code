---
title: "Canon — hierarchy_rollup"
part_of: reference_manual/canon
status: reference   # illustrative reference implementation, not a finished production function
scope: GENERIC — domain-neutral. Examples from example_shop_ontology/.
---

# Canon — `hierarchy_rollup`

> A **query-generator** canon: it produces a recursive CTE that returns a node **and all its descendants**
> over a self-referencing `(id, parent)` key — the deterministic realization of "a node means its subtree".
> Single-homed here; the root is a bound parameter.

## Serves

The [`recursive_hierarchy`](../patterns/recursive_hierarchy.md) pattern — any self-referencing parent/child
structure (category tree, org chart, bill-of-materials) whose nodes are queried with their descendants.

## Contract (the pluggable interface)

- **Signature:** `hierarchy_rollup(table, *, id_col, parent_col, root, dialect="trino") -> (sql, params)`
- **Params:** `id_col` (the node id), `parent_col` (the self-referencing parent), `root` (the node to expand).
- **Guarantee:** returns a relation of `id_col` for `root` **and all transitive descendants**, to arbitrary
  depth. The `root` is **bound (`?`), never interpolated** (FRAMEWORK §6).
- **Returns:** the recursive-CTE SQL (usable as a subquery / `IN (...)`) and the bound params.

## Reference implementation

```python
CANON = "hierarchy_rollup"

def hierarchy_rollup(table, *, id_col, parent_col, root, dialect="trino"):
    """Return a relation of `id_col` for `root` and ALL its descendants, via a recursive CTE over the
    self-referencing (id_col, parent_col) key. Root BOUND (?), never interpolated (FRAMEWORK §6).
    Realizes containment traversal: 'a node means its subtree'."""
    sql = (f"WITH RECURSIVE subtree({id_col}) AS ("
           f"SELECT {id_col} FROM {table} WHERE {id_col} = ? "
           f"UNION ALL "
           f"SELECT c.{id_col} FROM {table} c JOIN subtree s ON c.{parent_col} = s.{id_col}"
           f") SELECT {id_col} FROM subtree")
    return sql, [root]
```

## How a concept plugs in

```yaml
members:
  prose: "A category contains its subtree; a question about a node spans node + all descendants."
  realized_by:
    udf: hierarchy_rollup
    params: { table: category, id_col: category_id, parent_col: parent_id }   # root bound from the question
```

## Demonstration

```python
hierarchy_rollup("category", id_col="category_id", parent_col="parent_id", root="C1")
# → ("WITH RECURSIVE subtree(category_id) AS (SELECT category_id FROM category WHERE category_id = ? "
#    "UNION ALL SELECT c.category_id FROM category c JOIN subtree s ON c.parent_id = s.category_id) "
#    "SELECT category_id FROM subtree", ["C1"])
# Used as:  ... WHERE p.category_id IN ( <that SQL> )   → C1 ∪ {C2, C3, C4}
```

## Determinism & honest limits (AUTHORING A5)

- **Deterministic**; binds the root, never interpolates.
- **No cycle protection** — a malformed parent loop would recurse without bound; a production version adds a
  visited-set or a depth cap.
- **Single-column id/parent**; a composite key needs a multi-column join. **Assumes `WITH RECURSIVE`** in the
  dialect. Reference, not finished.
