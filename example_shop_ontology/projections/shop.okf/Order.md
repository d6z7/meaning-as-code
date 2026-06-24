---
type: Event
title: Order
description: 'A purchase a customer places: one or more products bought in a single
  checkout.'
resource: table://shop_warehouse/orders
tags:
- SHOP
- event
- confidence:C
timestamp: '2026-06-05'
---

# Order

A purchase a customer places: one or more products bought in a single checkout. An order is a thing that HAPPENS and then moves through states — placed → paid → shipped → delivered, with returned/cancelled as terminal branches. Its current state is its furthest-reached lifecycle state.

## Purpose

The central event of the shop — what revenue is computed from and what the fulfilment process tracks. Each order is placed_by one Customer (see edges) and contains one or more Products.

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

## Relationships

- **placedBy** → [Customer](/Customer.md) (cardinality 1; grounded join `orders.customer_id = customers.customer_id`)

# Citations

1. MAC concept source of record: `concepts/order/order.yaml` (schema_version 0.1.9, confidence C).
