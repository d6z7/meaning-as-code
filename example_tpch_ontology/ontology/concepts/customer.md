---
type: Entity
title: Customer
description: A party that places orders.
tags:
- TPCH
- entity
- confidence:C
---

A party that places orders. Identified by c_custkey, located in one Nation (see edges), and classified by a market segment. The demand side — orders and revenue attribute to a customer.

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

- [Nation](nation.md) — joined on `c_nationkey`

**Referenced by** — these point at this concept:

- [Order](orders.md) — on `c_custkey`

## Source of record
- Full MAC concept: `customer.yaml` — open the **YAML** tab for the complete typed definition.