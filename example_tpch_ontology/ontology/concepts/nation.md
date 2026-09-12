---
type: Entity
title: Nation
description: A country (TPC-H has 25).
tags:
- TPCH
- entity
- confidence:C
---

A country (TPC-H has 25). The middle level of the geography hierarchy: a Nation belongs to one Region (see edges) and is the nation of customers and suppliers. The grain at which most geography filtering happens before rolling up to Region.

## Details

- **Identity** — fk_name
- **Version** — 1.0
- **Schema version** — 0.1.9
- **Status** — production
- **Owner** — example-team
- **Last reviewed** — 2026-06-17

## Relationships

*1 join(s) out · 2 in — click a concept to open it.*

**Joins to** — this concept references:

- [Region](region.md) — joined on `n_regionkey`

**Referenced by** — these point at this concept:

- [Customer](customer.md) — on `n_nationkey`
- [Supplier](supplier.md) — on `n_nationkey`

## Source of record
- Full MAC concept: `nation.yaml` — open the **YAML** tab for the complete typed definition.