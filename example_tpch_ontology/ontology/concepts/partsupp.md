---
type: Entity
title: Part-Supplier
description: The supply of a Part by a Supplier — a reified many-to-many relationship with its own attributes (available quantity, supply cost).
tags:
- TPCH
- entity
- confidence:C
---

The supply of a Part by a Supplier — a reified many-to-many relationship with its own attributes (available quantity, supply cost). Identified by the composite key (ps_partkey, ps_suppkey). It is an entity, not an edge, precisely because it CARRIES data: an edge cannot hold availqty/supplycost.

## Details

- **Identity** — composite
- **Version** — 1.0
- **Schema version** — 0.1.9
- **Status** — production
- **Owner** — example-team
- **Last reviewed** — 2026-06-17

## Relationships

*2 join(s) out · 1 in — click a concept to open it.*

**Joins to** — this concept references:

- [Part](part.md) — joined on `ps_partkey`
- [Supplier](supplier.md) — joined on `ps_suppkey`

**Referenced by** — these point at this concept:

- [Order Line](lineitem.md) — on `ps_suppkey`

## Source of record
- Full MAC concept: `partsupp.yaml` — open the **YAML** tab for the complete typed definition.