---
type: Entity
title: Region
description: 'A top-level geographic grouping of nations (TPC-H regions: AFRICA, AMERICA, ASIA, EUROPE, MIDDLE EAST).'
tags:
- TPCH
- entity
- confidence:C
---

A top-level geographic grouping of nations (TPC-H regions: AFRICA, AMERICA, ASIA, EUROPE, MIDDLE EAST). The root of the geography hierarchy — a Nation belongs to exactly one Region, and customers/suppliers roll up to a region through their nation.

## Details

- **Identity** — fk_name
- **Version** — 1.0
- **Schema version** — 0.1.9
- **Status** — production
- **Owner** — example-team
- **Last reviewed** — 2026-06-17

## Relationships

*0 join(s) out · 1 in — click a concept to open it.*

**Referenced by** — these point at this concept:

- [Nation](nation.md) — on `r_regionkey`

## Source of record
- Full MAC concept: `region.yaml` — open the **YAML** tab for the complete typed definition.