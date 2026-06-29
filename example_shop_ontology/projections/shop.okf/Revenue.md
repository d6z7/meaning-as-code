---
type: Metric
title: Revenue
description: The monetary value of sales.
resource: table://shop_warehouse/orders
tags:
- SHOP
- measure
- confidence:C
timestamp: '2026-06-05'
---

# Revenue

The monetary value of sales. GROSS revenue is the order total at checkout; NET revenue subtracts refunds (from returned orders). "Revenue" without qualification means NET — the figure the business reports. Net revenue is COMPUTED (see rules.yaml > net_revenue), not stored.

## Purpose

The headline financial measure: what the shop earned, net of returns. The numerator of margin, the thing sliced by product/category/period.

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

## Derivation

Computed by rule `net_revenue` (see the MAC rules layer); do not re-derive the formula.

# Citations

1. MAC concept source of record: `concepts/finance/revenue.yaml` (schema_version 0.1.9, confidence C).
