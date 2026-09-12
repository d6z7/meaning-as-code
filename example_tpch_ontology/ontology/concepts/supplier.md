---
type: Entity
title: Supplier
description: A party that supplies parts.
tags:
- TPCH
- entity
- confidence:C
---

A party that supplies parts. Identified by s_suppkey and located in one Nation (see edges). The supply side — which supplier provides a part, at what cost, is captured by PartSupp.

## Details

- **Identity** — fk_name
- **Version** — 1.0
- **Schema version** — 0.1.9
- **Status** — production
- **Owner** — example-team
- **Last reviewed** — 2026-06-17

## Relationships

*1 join(s) out · 1 in — click a concept to open it.*

**Joins to** — this concept references:

- [Nation](nation.md) — joined on `s_nationkey`

**Referenced by** — these point at this concept:

- [Part-Supplier](partsupp.md) — on `s_suppkey`

## Source of record
- Full MAC concept: `supplier.yaml` — open the **YAML** tab for the complete typed definition.