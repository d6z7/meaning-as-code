---
type: Transform
title: 'Cleansing: orders'
description: Cleansing → shop_warehouse.orders
relation: shop_warehouse.orders
tags:
- SHOP
- transform
- lifecycle:draft
sql_file: data/transforms/orders.sql
---

Produces `shop_warehouse.orders` · grain: one row per order_id

## Rules
### vocabulary_drift — `status-canonicalize` · applied
- **defect** raw status arrives in mixed casing / synonyms (PAID, paid, Paid)
- **rule** lower-case, trim, and map synonyms to the canonical status token set
- **guarantee** status is exactly one canonical token (OrderStatus enumeration values)

### type_truncation — `amount-to-decimal` · applied
- **defect** gross is stored as integer cents (gross_cents) — currency math would truncate
- **rule** convert integer cents to a decimal currency amount
- **guarantee** gross_amount is a decimal currency value — ratios/sums never truncate

## Lineage
- Source: [orders_raw](../sources/orders_raw.md)
- Clean dataset: [orders](../datasets/orders.md)

## SQL realization
Realized by `orders.sql` (a deployed `CREATE VIEW`) — open it with the **SQL** button in the header, or in the Source browser.

## Lineage (column-level)

`shop_warehouse.orders` · kinds: const · passthrough · transform

| output column | ← from | rule | kind |
|---|---|---|---|
| `status` | `orders_raw.status` | status-canonicalize | passthrough |
| `gross_cents` | `orders_raw.gross_cents` | amount-to-decimal | transform |
| `order_id` | `orders_raw.order_id` | None | passthrough |
| `customer_id` | `orders_raw.customer_id` | None | passthrough |
| `placed_at` | `orders_raw.placed_at` | None | passthrough |
| `paid_at` | _literal per branch_ |  | const |
| `shipped_at` | _literal per branch_ |  | const |
| `delivered_at` | _literal per branch_ |  | const |
| `gross_amount` | _literal per branch_ |  | const |