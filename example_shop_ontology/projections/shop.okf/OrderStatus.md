---
type: Enumeration
title: Order Status
description: The set of states an Order can be in.
resource: table://shop_warehouse/orders
tags:
- SHOP
- enumeration
- confidence:C
timestamp: '2026-06-05'
---

# Order Status

The set of states an Order can be in. This is the value vocabulary that the Order lifecycle moves through (see order.yaml > lifecycle); here it is enumerated as a closed code list with meanings.

## Purpose

Gives the lifecycle states stable codes + meanings so reports and filters use one agreed vocabulary ("count delivered orders") rather than ad-hoc string matching.

# Schema

Grounded in `shop_warehouse.orders`.

| column | type | role | description |
|---|---|---|---|
| `order_id` | string | primary_key |  |
| `customer_id` | string | foreign_key | → customers.customer_id (placed_by edge) |
| `status` | string | discriminator | OrderStatus code (PLACED…CANCELLED) |
| `placed_at` | timestamp | value |  |
| `paid_at` | timestamp | value | NULL until paid |
| `shipped_at` | timestamp | value | NULL until shipped |
| `delivered_at` | timestamp | value | NULL until delivered |
| `gross_amount` | decimal | value | order total before refunds |

# Values

Closed code list — these 6 are the complete set.

| code | label | meaning |
|---|---|---|
| `PLACED` | Placed | Created, not yet paid |
| `PAID` | Paid | Payment captured |
| `SHIPPED` | Shipped | Handed to carrier |
| `DELIVERED` | Delivered | Received by customer (happy-path terminal) |
| `RETURNED` | Returned | Returned after delivery |
| `CANCELLED` | Cancelled | Cancelled before shipping |

# Citations

1. MAC concept source of record: `concepts/order/order_status.yaml` (schema_version 0.1.6, confidence C).
