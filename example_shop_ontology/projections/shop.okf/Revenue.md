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
| `customer_id` | string | foreign_key | → customers.customer_id (placed_by edge) |
| `status` | string | discriminator | OrderStatus code (PLACED…CANCELLED) |
| `placed_at` | timestamp | value |  |
| `paid_at` | timestamp | value | NULL until paid |
| `shipped_at` | timestamp | value | NULL until shipped |
| `delivered_at` | timestamp | value | NULL until delivered |
| `gross_amount` | decimal | value | order total before refunds |

## Derivation

Computed by rule `net_revenue` (see the MAC rules layer); do not re-derive the formula.

# Citations

1. MAC concept source of record: `concepts/finance/revenue.yaml` (schema_version 0.1.6, confidence C).
