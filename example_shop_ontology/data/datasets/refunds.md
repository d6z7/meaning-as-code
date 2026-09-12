---
type: Dataset
title: 'Clean: refunds'
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
| `refund_id` | string | primary_key |
| `order_id` | string | foreign_key |
| `refund_amount` | decimal | value |
| `refunded_at` | timestamp | value |

## Foreign keys
- `order_id` → `orders.order_id`