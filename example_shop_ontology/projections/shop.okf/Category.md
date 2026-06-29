---
type: Grouping
title: Category
description: A grouping of products into a browsable hierarchy — e.g.
resource: table://shop_warehouse/categories
tags:
- SHOP
- grouping
- confidence:C
timestamp: '2026-06-05'
---

# Category

A grouping of products into a browsable hierarchy — e.g. Electronics > Phones, Home > Kitchen. A Category is not a sellable thing (that is Product, a reference); it is the roll-up level used to aggregate revenue and browse the catalogue. Categories nest (a category may have a parent category).

## Purpose

The roll-up axis for the catalogue: lets "revenue by category" aggregate over the products it contains, and supports drill-down (Electronics → Phones → a specific Product).

# Schema

Grounded in `shop_warehouse.categories`.

| column | type | role | description |
|---|---|---|---|
| `category_id` | string | primary_key |  |
| `name` | string | value |  |
| `parent_id` | string | foreign_key |  |

## Relationships

- inverse of **belongsToCategory** ← [Product](/Product.md) (grounded join `products.category_id = categories.category_id`)

# Citations

1. MAC concept source of record: `concepts/catalog/category.yaml` (schema_version 0.1.9, confidence C).
