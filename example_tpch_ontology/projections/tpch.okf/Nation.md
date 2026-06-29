---
type: Entity
title: Nation
description: A country (TPC-H has 25).
resource: table://tpch/nation
tags:
- TPCH
- entity
- confidence:C
timestamp: '2026-06-17'
---

# Nation

A country (TPC-H has 25). The middle level of the geography hierarchy: a Nation belongs to one Region (see edges) and is the nation of customers and suppliers. The grain at which most geography filtering happens before rolling up to Region.

## Purpose

Attributes customer demand and supplier capacity to a country, and bridges them to a Region.

# Schema

Grounded in `tpch.nation`.

| column | type | role | description |
|---|---|---|---|
| `n_nationkey` | integer | primary_key |  |
| `n_name` | string | value |  |
| `n_regionkey` | integer | foreign_key |  |
| `n_comment` | string | value |  |

## Relationships

- **inRegion** → [Region](/Region.md) (cardinality 1; grounded join `nation.n_regionkey = region.r_regionkey`)
- inverse of **fromNation** ← [Customer](/Customer.md) (grounded join `customer.c_nationkey = nation.n_nationkey`)
- inverse of **fromNation** ← [Supplier](/Supplier.md) (grounded join `supplier.s_nationkey = nation.n_nationkey`)

# Citations

1. MAC concept source of record: `concepts/geography/nation.yaml` (schema_version 0.1.9, confidence C).
