---
title: "Pattern — Recursive hierarchy (a self-referencing parent key)"
part_of: reference_manual/patterns
status: prototype
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (illustrative shop scenario).
---

# Pattern — Recursive hierarchy

## Initial state — what you're handed

The shop's catalogue is a category tree, stored as an adjacency list — each row points at its own parent:

```sql
CREATE TABLE category (
  category_id VARCHAR, name VARCHAR, parent_id VARCHAR   -- parent_id self-references category_id
);
```

| category_id | name | parent_id |
| --- | --- | --- |
| C1 | Outdoor | NULL |
| C2 | Camping | C1 |
| C3 | Tents | C2 |
| C4 | Footwear | C1 |

Products attach to **leaf** categories (Tents, Footwear), not to "Outdoor".

**Why this is dangerous.** "Revenue for Outdoor" should include Camping, Tents, and Footwear — the whole
subtree. But `WHERE category_id = 'C1'` returns only products tagged *exactly* Outdoor, which is usually
**none** (products sit at the leaves). The hierarchy is right there in `parent_id`, but a flat filter ignores
it, and the depth is arbitrary — you cannot hardcode "join three levels".

## The question, and the answer

> **The question** (what the data can't tell you): *Does filtering `category_id = 'C1'` include the
> category's descendants?*
>
> **The answer** (the fact we supply): *No — "Outdoor" means C1 **and its entire subtree**, to arbitrary
> depth. The parent/child closure must be traversed. Supplied as a recursive-CTE expansion over the
> self-key (containment is concept structure; the traversal is a canon).*

## The pattern (the structured entry)

```yaml
pattern: recursive_hierarchy
also_known_as: [self-referencing FK, parent-child hierarchy, adjacency list, ragged hierarchy, transitive closure]
tradition: relational   # with the dimensional "ragged/variable-depth hierarchy"
constellation: >
  A table whose rows point at their own parent via a self-referencing key. A question about a node almost
  always means the node PLUS its transitive descendants, to arbitrary (ragged) depth.
prior_art:
  relational: >
    An adjacency list. A flat `= node` filter silently drops descendants; correct traversal needs a recursive
    CTE the analyst must remember to write, every time.
  dimensional: >
    A "ragged / variable-depth hierarchy". Often flattened into fixed levels (loses depth) or materialised as
    a bridge/closure table the ETL must keep in sync.
  rdf: >
    Transitive properties / `rdfs:subClassOf` chains — but querying the closure needs property paths the
    consumer must author; the default reading is one hop.
mac_expression: >
  Containment is CONCEPT STRUCTURE (a node's `members:` / parent), NOT an edge (FRAMEWORK §7). The traversal
  — node + all descendants — is a canon: a recursive-CTE expansion over the self-key. A question about a node
  deterministically resolves to its subtree.
why_better: >
  "A node means its subtree" becomes a single-homed, reusable traversal instead of a recursive CTE
  re-written (or forgotten) per query. The flat-filter footgun — silently returning nothing or only the
  directly-tagged rows — is closed. It still projects to a recursive CTE, a closure table, or a graph
  traversal.
projects_to:
  rdf: "a transitive property / property path over the parent relation"
  graph: "a native :CONTAINS / variable-length traversal"
  relational: "a recursive CTE, or a maintained closure/bridge table"
antipattern: >
  A flat `= node` filter (drops descendants); flattening to fixed levels (loses ragged depth); modelling
  containment as an edge in edges.yaml (it is concept structure — COOKBOOK C3).
status: scattered   # containment-as-concept-structure exists; the recursive traversal was never named as a canon/pattern
canon_ref: [FRAMEWORK.md §7 (containment is concept structure), MODELLERS_COOKBOOK.md C3, CONCEPT_SPEC.md §6 (members)]
```

## The determinism border

Per [AUTHORING.md](../AUTHORING.md) A4 — this pattern is **fully deterministic**: structure + a mechanical traversal.

| Behaviour | Kind | How |
| --- | --- | --- |
| "A node" means node + all descendants | **canon-backed** | [`hierarchy_rollup`](../canon/hierarchy_rollup.md) |
| Traversal to arbitrary (ragged) depth | **canon-backed** | the same recursive CTE |
| Containment is structure, not an edge | **skeleton** | `members:` on the concept |
| interpretative remainder | **none** | the subtree is mechanical once the root is named |

```yaml
members:
  prose: "A category contains its subtree; a question about a node spans the node and all descendants."
  realized_by:
    udf: hierarchy_rollup
    params: { table: category, id_col: category_id, parent_col: parent_id }   # root bound from the question
```

## The footgun, concretely

```sql
-- Q: "What was revenue for the Outdoor category?"
-- GUESS (plausible, and wrong): flat filter on the node
SELECT SUM(amount) FROM sales s JOIN product p ON p.id = s.product_id
WHERE p.category_id = 'C1';      -- returns ~nothing: products sit at leaves, not at 'Outdoor'  ❌
```

```sql
-- GROUNDED: expand the node to its subtree via the canon, then filter to the subtree
SELECT SUM(amount) FROM sales s JOIN product p ON p.id = s.product_id
WHERE p.category_id IN (
  WITH RECURSIVE subtree(category_id) AS (
    SELECT category_id FROM category WHERE category_id = ?              -- root, BOUND
    UNION ALL
    SELECT c.category_id FROM category c JOIN subtree t ON c.parent_id = t.category_id
  ) SELECT category_id FROM subtree
);                                -- C1 ∪ {C2, C3, C4} — the whole Outdoor subtree  ✅
```

The difference is the unstated fact "a node means its subtree", made a reusable traversal — so the agent
cannot ship the flat filter that silently returns nothing.
