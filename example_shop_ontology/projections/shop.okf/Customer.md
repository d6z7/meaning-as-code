---
type: Entity
title: Customer
description: A person (or business) who can place orders in the shop.
resource: table://shop_warehouse/customers
tags:
- SHOP
- entity
- confidence:C
timestamp: '2026-06-05'
---

# Customer

A person (or business) who can place orders in the shop. Identified by customer_id. The root party of the ordering process; an Order is placed_by exactly one Customer.

## Purpose

Identifies who placed an order, so revenue and behaviour can be attributed to a party and orders can be grouped per customer.

# Schema

Grounded in `shop_warehouse.customers`.

| column | type | role | description |
|---|---|---|---|
| `customer_id` | string | primary_key |  |
| `email` | string | value |  |
| `created_at` | timestamp | value |  |

## Relationships

- inverse of **placedBy** ← [Order](/Order.md) (grounded join `orders.customer_id = customers.customer_id`)

# Citations

1. MAC concept source of record: `concepts/customer/customer.yaml` (schema_version 0.1.9, confidence C).
