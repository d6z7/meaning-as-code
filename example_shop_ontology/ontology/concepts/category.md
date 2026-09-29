---
type: Grouping
title: Category
description: A grouping of products into a browsable hierarchy — e.g.
tags:
- SHOP
- grouping
- confidence:C
resource: table://categories
---

A grouping of products into a browsable hierarchy — e.g. Electronics > Phones, Home > Kitchen. A Category is not a sellable thing (that is Product, a reference); it is the roll-up level used to aggregate revenue and browse the catalogue. Categories nest (a category may have a parent category).

## Details

- **Identity** — fk_name
- **Version** — 1.0
- **Schema version** — 0.1.16
- **Status** — production
- **Owner** — example-team
- **Last reviewed** — 2026-06-05

## Grounded in

- `categories` — key `['category_id']`

## Fields

| column | type | role | grounded in | description | joins → |
|---|---|---|---|---|---|
| `category_id` | string | — | `categories` | — | — |
| `name` | string | — | `categories` | display name (e.g. 'Phones') | — |
| `parent_id` | string | — | `categories` | — | — |

_Declared per column, over 3 columns: description 1 of 3 · type 3 of 3 · joins → 0 of 3. An em dash is a column for which nothing is declared._

## Relationships

*0 join(s) out · 1 in — click a concept to open it.*

**Groups** → **Product** — the leaf concept this rolls up.

**Referenced by** — these point at this concept:

- [Product](product.md) — on `category_id`

## Source of record
- Full MAC concept: `category.yaml` — open the **YAML** tab for the complete typed definition.