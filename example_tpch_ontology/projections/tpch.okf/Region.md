---
type: Entity
title: Region
description: 'A top-level geographic grouping of nations (TPC-H regions: AFRICA, AMERICA,
  ASIA, EUROPE, MIDDLE EAST).'
resource: table://tpch/region
tags:
- TPCH
- entity
- confidence:C
timestamp: '2026-06-17'
---

# Region

A top-level geographic grouping of nations (TPC-H regions: AFRICA, AMERICA, ASIA, EUROPE, MIDDLE EAST). The root of the geography hierarchy — a Nation belongs to exactly one Region, and customers/suppliers roll up to a region through their nation.

## Purpose

The coarsest geography level — the axis for continental roll-ups of revenue, supply, and demand.

# Schema

Grounded in `tpch.region`.

| column | type | role | description |
|---|---|---|---|
| `r_regionkey` | integer | primary_key |  |
| `r_name` | string | value |  |
| `r_comment` | string | value |  |

## Relationships

- inverse of **inRegion** ← [Nation](/Nation.md) (grounded join `nation.n_regionkey = region.r_regionkey`)

# Citations

1. MAC concept source of record: `concepts/geography/region.yaml` (schema_version 0.1.9, confidence C).
