---
type: Entity
title: Order
description: 'The header of a customer order: who placed it (one Customer), when,
  its total price and status.'
resource: table://tpch/orders
tags:
- TPCH
- entity
- confidence:C
timestamp: '2026-06-17'
---

# Order

The header of a customer order: who placed it (one Customer), when, its total price and status. The parent of one or more LineItems. Modelled as an entity (a header record); the fulfilment lifecycle lives on its LineItems, which is where shipping actually happens.

## Purpose

Groups order lines under one customer + date, and carries the order-level total and status.

# Schema

Grounded in `tpch.orders`.

| column | type | role | description |
|---|---|---|---|
| `o_orderkey` | integer | primary_key |  |
| `o_custkey` | integer | foreign_key |  |
| `o_orderstatus` | string | discriminator |  |
| `o_totalprice` | decimal | value |  |
| `o_orderdate` | date | value |  |
| `o_orderpriority` | string | discriminator |  |
| `o_comment` | string | value |  |

## Relationships

- **placedBy** → [Customer](/Customer.md) (cardinality 1; grounded join `orders.o_custkey = customer.c_custkey`)
- inverse of **partOfOrder** ← [LineItem](/LineItem.md) (grounded join `lineitem.l_orderkey = orders.o_orderkey`)

# Citations

1. MAC concept source of record: `concepts/order/orders.yaml` (schema_version 0.1.9, confidence C).
