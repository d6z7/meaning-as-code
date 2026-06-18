# Shop — from question to SQL, generated *from the ontology*

Each question becomes SQL by **reading the model**: `FROM`/columns from a concept's `grounding` →
`data/datasets/<t>.yaml`; `JOIN … ON …` from an **edge**'s `join_rule`; the measure expression from a **rule**'s
`template`. Turning the question into an intent (which measure, which slice) is the one probabilistic
step; resolving that intent to tables, columns and joins is deterministic execution against the model.

Schema: `shop_warehouse`. The model declares exactly **two** joins (`ontology/edges.yaml`):

```
orders.customer_id   = customers.customer_id    (order__placed_by__customer)
products.category_id = categories.category_id   (product__belongs_to__category)
```

Net **Revenue** is rule `net_revenue` (`ontology/rules.yaml`): `gross − refunds`, **only paid orders**
(`paid_at IS NOT NULL`), refunds `LEFT JOIN`ed so unrefunded orders keep their full gross.

---

## Q1. "What was our net revenue in Q1 2026?"

**Intent → ontology.** Measure = Revenue (rule `net_revenue` → expression + the *only-paid* condition);
period filter on `orders.placed_at` (role `value`, `x-subrole: temporal`). Refunds are a **finer grain**
than orders (`data/datasets/refunds.yaml`: "zero or more rows per order"), so they are pre-aggregated to the
order grain before netting — honoring the Order grain (one row per order) instead of fanning it out.

```sql
SELECT SUM(o.gross_amount) - COALESCE(SUM(rf.refund_total), 0) AS net_revenue   -- rule net_revenue.template
FROM shop_warehouse.orders o
  LEFT JOIN (SELECT order_id, SUM(refund_amount) AS refund_total
             FROM shop_warehouse.refunds
             GROUP BY order_id) rf ON rf.order_id = o.order_id     -- refunds netted at order grain
WHERE o.paid_at IS NOT NULL                                        -- rule condition: only paid orders are revenue
  AND o.placed_at >= TIMESTAMP '2026-01-01 00:00:00'
  AND o.placed_at <  TIMESTAMP '2026-04-01 00:00:00';             -- half-open Q1 window
```

---

## Q2. "Net revenue by customer (email)."

**Intent → ontology.** Same Revenue rule; the per-customer slice uses the only join that reaches customer
attributes: edge `order__placed_by__customer`. `email` lives on `customers` (`data/datasets/customers.yaml`).

```sql
SELECT c.email,
       SUM(o.gross_amount) - COALESCE(SUM(rf.refund_total), 0) AS net_revenue
FROM shop_warehouse.orders o
  JOIN shop_warehouse.customers c ON o.customer_id = c.customer_id   -- edge order__placed_by__customer
  LEFT JOIN (SELECT order_id, SUM(refund_amount) AS refund_total
             FROM shop_warehouse.refunds GROUP BY order_id) rf ON rf.order_id = o.order_id
WHERE o.paid_at IS NOT NULL                                          -- rule condition
GROUP BY c.email
ORDER BY net_revenue DESC;
```

---

## Q3. "How many products are in each category?"

**Intent → ontology.** No measure — a count over the catalogue, sliced by the edge
`product__belongs_to__category`. `Category` is a `grouping` concept grounding to `categories`.

```sql
SELECT cat.name AS category,
       COUNT(*) AS product_count
FROM shop_warehouse.products p
  JOIN shop_warehouse.categories cat ON p.category_id = cat.category_id   -- edge product__belongs_to__category
GROUP BY cat.name
ORDER BY product_count DESC;
```

---

## Q4. "What was net revenue **by product category**?" — *the ontology answers: not derivable.*

This is the instructive one. The intent needs a path from **Revenue** (grounded on `orders`/`refunds`) to
**Category** (grounded on `categories`, reached only via `products`). Walking the declared edges:

```
Revenue → orders → customers          (order__placed_by__customer)   ─ dead end, no product link
Category ← products → categories      (product__belongs_to__category)
```

there is **no edge joining `orders` (or any line of an order) to `products`** — this shop model has no
order-line concept. The two subgraphs don't connect on the revenue side. A correct generator therefore
**refuses** rather than inventing an `orders.sku` column or a phantom join:

> *Not derivable from the model: Revenue grounds on `orders`/`refunds`; Category is reachable only through
> `products`; no edge connects them. Add an order-line concept (an event grounding `order_id` + `sku`) and
> the edges `orderline__part_of__order` and `orderline__of__product` to make this answerable.*

That is the point of encoding joins as data: the model knows the boundary of what it can answer, so the
gap is reported as a missing **edge/concept** to add — never papered over with a guessed identifier.
