---
type: Entity
title: Customer
description: A party that places orders.
resource: table://tpch/customer
tags:
- TPCH
- entity
- confidence:C
timestamp: '2026-06-17'
---

# Customer

A party that places orders. Identified by c_custkey, located in one Nation (see edges), and classified by a market segment. The demand side — orders and revenue attribute to a customer.

## Purpose

Attributes orders and revenue to a party, and (through its nation) to geography and market segment.

# Schema

Grounded in `tpch.customer`.

| column | type | role | description |
|---|---|---|---|
| `c_custkey` | integer | primary_key |  |
| `c_name` | string | value |  |
| `c_nationkey` | integer | foreign_key |  |
| `c_phone` | string | value |  |
| `c_acctbal` | decimal | value |  |
| `c_mktsegment` | string | discriminator |  |
| `c_comment` | string | value |  |

## Relationships

- **fromNation** → [Nation](/Nation.md) (cardinality 1; grounded join `customer.c_nationkey = nation.n_nationkey`)
- inverse of **placedBy** ← [Orders](/Orders.md) (grounded join `orders.o_custkey = customer.c_custkey`)

# Citations

1. MAC concept source of record: `concepts/party/customer.yaml` (schema_version 0.1.9, confidence C).
