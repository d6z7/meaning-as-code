---
title: "Pattern — Role-playing dimension (one dimension, several roles)"
part_of: reference_manual/patterns
status: prototype
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (illustrative shop scenario).
---

# Pattern — Role-playing dimension

## Initial state — what you're handed

One `calendar` dimension, referenced by an order in **three roles** at once:

```sql
CREATE TABLE order_pipeline (
  order_id VARCHAR,
  placed_date   DATE,   -- → calendar
  shipped_date  DATE,   -- → calendar
  delivered_date DATE   -- → calendar
);
CREATE TABLE calendar (cal_date DATE, day_of_week VARCHAR, is_holiday BOOLEAN, fiscal_quarter VARCHAR);
```

**Why this is dangerous.** All three columns point at the *same* `calendar` table, but in different roles. A
single naïve join (`JOIN calendar ON cal_date = placed_date`) silently answers everything in terms of the
*placed* date; "deliveries in fiscal Q1" then quietly filters on the wrong role.

## The question, and the answer

> **The question:** *Are these three date columns three dimensions, or one dimension in three roles?*
>
> **The answer:** *One dimension, three roles. Model ONE `reference` (Calendar) and THREE `edges`, each
> tagged with a distinct `role`; a query names the role it means.*

## The pattern (the structured entry)

```yaml
pattern: role_playing_dimension
also_known_as: [role-playing dimension, dimension role, aliased dimension]
tradition: dimensional
constellation: >
  A single dimension is referenced by one fact in several distinct ROLES (order date vs ship date; origin
  vs destination), each a separate foreign key into the same table.
prior_art:
  relational: >
    Several FKs to one table; the role distinction lives only in the column names, and a join must alias the
    table per role — easy to conflate.
  dimensional: >
    Kimball's role-playing dimension (often via DB views aliasing the same table); the roles are real but
    tool-specific.
  rdf: >
    The same class as range of several distinct object properties (orderedOn, shippedOn…).
mac_expression: >
  ONE `reference` concept (Calendar) and N `edges`, each carrying a distinct endpoint `role`
  (placed / shipped / delivered), each `realized_by` its own FK column. The edge `role` field IS the
  mechanism. No new structure — one reference + role-tagged edges.
why_better: >
  The dimension is modelled once and reused in named roles, so a query must say WHICH role it filters on —
  "deliveries in Q1" binds to the delivered-date edge, not silently to placed-date. Avoids both conflation
  and three duplicate Calendar copies.
projects_to:
  rdf: "one class as range of several object properties"
  graph: "one node label reached by several distinct relationship types"
  relational: "role-aliased views over one dimension table"
antipattern: >
  A single un-roled join (conflates the roles); or cloning the dimension once per role (loses that it's one
  thing).
status: scattered   # edge `role` expresses it; never named as a pattern — a "six suffice" confirmation
canon_ref: [FRAMEWORK.md §7 (edges, per-endpoint role), CONCEPT_SPEC.md §6]
```

## The determinism border

A **structural** pattern — skeleton (edges with roles), no behavioural canon.

| Behaviour | Kind | How |
| --- | --- | --- |
| One dimension, many roles | **skeleton** | one `reference` + N role-tagged `edges` |
| A query binds to the right role | **skeleton** | the edge `role` the question names |
| interpretative remainder | **none** | structural |

## The footgun, concretely

```sql
-- GUESS: one un-roled join → everything is in terms of placed_date
SELECT count(*) FROM order_pipeline o JOIN calendar c ON c.cal_date = o.placed_date
WHERE c.fiscal_quarter = 'Q1';     -- silently counts orders PLACED in Q1, even if asked about DELIVERIES  ❌
-- GROUNDED: bind to the delivered-date role
SELECT count(*) FROM order_pipeline o JOIN calendar c ON c.cal_date = o.delivered_date
WHERE c.fiscal_quarter = 'Q1';     -- deliveries in Q1  ✅
```
