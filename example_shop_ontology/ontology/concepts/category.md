---
type: Grouping
title: Category
description: A grouping of products into a browsable hierarchy — e.g.
tags:
- SHOP
- grouping
- confidence:C
---

A grouping of products into a browsable hierarchy — e.g. Electronics > Phones, Home > Kitchen. A Category is not a sellable thing (that is Product, a reference); it is the roll-up level used to aggregate revenue and browse the catalogue. Categories nest (a category may have a parent category).

## Details

- **Identity** — fk_name
- **Version** — 1.0
- **Schema version** — 0.1.9
- **Status** — production
- **Owner** — example-team
- **Last reviewed** — 2026-06-05

## Relationships

*0 join(s) out · 1 in — click a concept to open it.*

**Groups** → **Product** — the leaf concept this rolls up.

**Referenced by** — these point at this concept:

- [Product](product.md) — on `category_id`

## Source of record
- Full MAC concept: `category.yaml` — open the **YAML** tab for the complete typed definition.