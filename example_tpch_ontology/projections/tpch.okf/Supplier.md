---
type: Entity
title: Supplier
description: A party that supplies parts.
resource: table://tpch/supplier
tags:
- TPCH
- entity
- confidence:C
timestamp: '2026-06-17'
---

# Supplier

A party that supplies parts. Identified by s_suppkey and located in one Nation (see edges). The supply side — which supplier provides a part, at what cost, is captured by PartSupp.

## Purpose

Attributes supply (availability, cost) and the supplied side of order lines to a party and its geography.

# Schema

Grounded in `tpch.supplier`.

| column | type | role | description |
|---|---|---|---|
| `s_suppkey` | integer | primary_key |  |
| `s_name` | string | value |  |
| `s_nationkey` | integer | foreign_key |  |
| `s_phone` | string | value |  |
| `s_acctbal` | decimal | value |  |
| `s_comment` | string | value |  |

## Relationships

- **fromNation** → [Nation](/Nation.md) (cardinality 1; grounded join `supplier.s_nationkey = nation.n_nationkey`)
- inverse of **fromSupplier** ← [PartSupp](/PartSupp.md) (grounded join `partsupp.ps_suppkey = supplier.s_suppkey`)

# Citations

1. MAC concept source of record: `concepts/party/supplier.yaml` (schema_version 0.1.9, confidence C).
