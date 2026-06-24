---
type: Entity
title: Part
description: A catalogue item that can be ordered.
resource: table://tpch/part
tags:
- TPCH
- entity
- confidence:C
timestamp: '2026-06-17'
---

# Part

A catalogue item that can be ordered. Identified by p_partkey, classified by brand and type. Sold through one or more suppliers (see PartSupp) and bought on order lines.

## Purpose

The product axis — slices revenue and quantity by brand, type, and individual part.

# Schema

Grounded in `tpch.part`.

| column | type | role | description |
|---|---|---|---|
| `p_partkey` | integer | primary_key |  |
| `p_name` | string | value |  |
| `p_mfgr` | string | value |  |
| `p_brand` | string | discriminator |  |
| `p_type` | string | discriminator |  |
| `p_size` | integer | value |  |
| `p_retailprice` | decimal | value |  |
| `p_comment` | string | value |  |

## Relationships

- inverse of **ofPart** ← [PartSupp](/PartSupp.md) (grounded join `partsupp.ps_partkey = part.p_partkey`)

# Citations

1. MAC concept source of record: `concepts/part/part.yaml` (schema_version 0.1.9, confidence C).
