---
type: Entity
title: Order
description: 'The header of a customer order: who placed it (one Customer), when, its total price and status.'
tags:
- TPCH
- entity
- confidence:C
---

The header of a customer order: who placed it (one Customer), when, its total price and status. The parent of one or more LineItems. Modelled as an entity (a header record); the fulfilment lifecycle lives on its LineItems, which is where shipping actually happens.

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

- [Customer](customer.md) — joined on `o_custkey`

**Referenced by** — these point at this concept:

- [Order Line](lineitem.md) — on `o_orderkey`

## Source of record
- Full MAC concept: `orders.yaml` — open the **YAML** tab for the complete typed definition.