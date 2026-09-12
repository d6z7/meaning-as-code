---
type: Reference
title: Product
description: A sellable item in the catalogue, identified by sku.
tags:
- SHOP
- reference
- confidence:C
---

A sellable item in the catalogue, identified by sku. Orders reference products; products roll up into a Category (see grouping). The leaf of the catalogue hierarchy.

## Details

- **Identity** — fk_name
- **Version** — 1.0
- **Schema version** — 0.1.9
- **Status** — production
- **Owner** — example-team
- **Last reviewed** — 2026-06-05

## Relationships

*2 join(s) out · 1 in — click a concept to open it.*

**Joins to** — this concept references:

- [Category](category.md) — joined on `category_id`
- [Product](product.md) — joined on `?`

**Referenced by** — these point at this concept:

- [Product](product.md) — on `?`

## Source of record
- Full MAC concept: `product.yaml` — open the **YAML** tab for the complete typed definition.