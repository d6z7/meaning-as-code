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
| `customer_id` | string | foreign_key |  |
| `status` | string | discriminator |  |
| `placed_at` | timestamp | value |  |
| `paid_at` | timestamp | value | read it from which timestamps are present — paid iff paid_at IS NOT NULL, shipped iff shipped_at IS NOT NULL, delivered iff delivered_at IS NOT NULL (furthest-reached state wins) include it only if it is paid (paid_at IS NOT NULL) |
| `shipped_at` | timestamp | value | read it from which timestamps are present — paid iff paid_at IS NOT NULL, shipped iff shipped_at IS NOT NULL, delivered iff delivered_at IS NOT NULL (furthest-reached state wins) |
| `delivered_at` | timestamp | value | read it from which timestamps are present — paid iff paid_at IS NOT NULL, shipped iff shipped_at IS NOT NULL, delivered iff delivered_at IS NOT NULL (furthest-reached state wins) |
| `gross_amount` | decimal | value | net = SUM(gross_amount) minus the order's summed refunds (rule net_revenue); an absent refund counts as 0 |

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

1. MAC concept source of record: `concepts/order/order_status.yaml` (schema_version 0.1.9, confidence C).
