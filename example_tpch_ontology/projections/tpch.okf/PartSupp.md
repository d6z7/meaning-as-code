---
type: Entity
title: Part-Supplier
description: The supply of a Part by a Supplier — a reified many-to-many relationship
  with its own attributes (available quantity, supply cost).
resource: table://tpch/partsupp
tags:
- TPCH
- entity
- confidence:C
timestamp: '2026-06-17'
---

# Part-Supplier

The supply of a Part by a Supplier — a reified many-to-many relationship with its own attributes (available quantity, supply cost). Identified by the composite key (ps_partkey, ps_suppkey). It is an entity, not an edge, precisely because it CARRIES data: an edge cannot hold availqty/supplycost.

## Purpose

Captures which supplier stocks which part, at what cost — the bridge an order line is supplied through.

# Schema

Grounded in `tpch.partsupp`.

| column | type | role | description |
|---|---|---|---|
| `ps_partkey` | integer | composite_key_part |  |
| `ps_suppkey` | integer | composite_key_part |  |
| `ps_availqty` | integer | value |  |
| `ps_supplycost` | decimal | value |  |
| `ps_comment` | string | value |  |

## Relationships

- **ofPart** → [Part](/Part.md) (cardinality 1; grounded join `partsupp.ps_partkey = part.p_partkey`)
- **fromSupplier** → [Supplier](/Supplier.md) (cardinality 1; grounded join `partsupp.ps_suppkey = supplier.s_suppkey`)
- inverse of **suppliedVia** ← [LineItem](/LineItem.md) (grounded join `lineitem.l_partkey = partsupp.ps_partkey AND lineitem.l_suppkey = partsupp.ps_suppkey`)

# Citations

1. MAC concept source of record: `concepts/part/partsupp.yaml` (schema_version 0.1.9, confidence C).
