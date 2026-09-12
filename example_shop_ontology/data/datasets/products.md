---
type: Dataset
title: 'Clean: products'
description: AI-friendly clean shape the ontology binds to
relation: null
tags:
- SHOP
- dataset
- lifecycle:draft
---

## Columns

| column | type | role |
|---|---|---|
| `sku` | string | primary_key |
| `name` | string | value |
| `category_id` | string | foreign_key |
| `list_price` | decimal | value |

## Foreign keys
- `category_id` → `categories.category_id`