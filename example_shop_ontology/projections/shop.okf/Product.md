---
type: Reference
title: Product
description: A sellable item in the catalogue, identified by sku.
resource: table://shop_warehouse/products
tags:
- SHOP
- reference
- confidence:C
timestamp: '2026-06-05'
---

# Product

A sellable item in the catalogue, identified by sku. Orders reference products; products roll up into a Category (see grouping). The leaf of the catalogue hierarchy.

## Purpose

The dimension that says WHAT was bought. Joins order lines to a name, price, and category so revenue can be sliced by product or rolled up by category.

# Schema

Grounded in `shop_warehouse.products`.

| column | type | role | description |
|---|---|---|---|
| `sku` | string | primary_key |  |
| `name` | string | value |  |
| `category_id` | string | foreign_key |  |
| `list_price` | decimal | value |  |

## Relationships

- **belongsToCategory** → [Category](/Category.md) (cardinality 0..1; grounded join `products.category_id = categories.category_id`)

# Citations

1. MAC concept source of record: `concepts/catalog/product.yaml` (schema_version 0.1.9, confidence C).
