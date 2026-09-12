---
type: Entity
title: Part
description: A catalogue item that can be ordered.
tags:
- TPCH
- entity
- confidence:C
---

A catalogue item that can be ordered. Identified by p_partkey, classified by brand and type. Sold through one or more suppliers (see PartSupp) and bought on order lines.

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

- [Part-Supplier](partsupp.md) — on `p_partkey`

## Source of record
- Full MAC concept: `part.yaml` — open the **YAML** tab for the complete typed definition.