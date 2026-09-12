---
type: Dataset
title: 'Clean: categories'
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
| `category_id` | string | primary_key |
| `name` | string | value |
| `parent_id` | string | foreign_key |

## Foreign keys
- `parent_id` → `categories.category_id`