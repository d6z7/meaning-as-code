---
type: Reference
title: Product
description: A sellable item in the catalogue, identified by sku.
tags:
- SHOP
- reference
- confidence:C
resource: table://products
---

A sellable item in the catalogue, identified by sku. Orders reference products; products roll up into a Category (see grouping). The leaf of the catalogue hierarchy.

## Details

- **Identity** — fk_name
- **Version** — 1.0
- **Schema version** — 0.1.16
- **Status** — production
- **Owner** — example-team
- **Last reviewed** — 2026-06-05

## Grounded in

- `products` — key `['sku']`

## Fields

| column | type | role | grounded in | description | joins → |
|---|---|---|---|---|---|
| `sku` | string | — | `products` | sku — identity key | — |
| `name` | string | — | `products` | display name | — |
| `category_id` | string | — | `products` | — | [Category](category.md) |
| `list_price` | decimal | — | `products` | — | — |

_Declared per column, over 4 columns: description 2 of 4 · type 4 of 4 · joins → 1 of 4. An em dash is a column for which nothing is declared._

## Relationships

*2 join(s) out · 1 in — click a concept to open it.*

**Joins to** — this concept references:

- [Category](category.md) — joined on `category_id`
- [Product](product.md) — joined on `?`

**Referenced by** — these point at this concept:

- [Product](product.md) — on `?`

## Source of record
- Full MAC concept: `product.yaml` — open the **YAML** tab for the complete typed definition.