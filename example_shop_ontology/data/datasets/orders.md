---
type: Dataset
title: 'Clean: orders'
description: AI-friendly clean shape the ontology binds to
relation: shop_warehouse.orders
tags:
- SHOP
- dataset
- lifecycle:draft
---

## Columns

| column | type | role | reference |
|---|---|---|---|
| `order_id` | string | PK |  |
| `customer_id` | string | FK |  |
| `status` | string | discriminator |  |
| `placed_at` | timestamp | value |  |
| `paid_at` | timestamp | value |  |
| `shipped_at` | timestamp | value |  |
| `delivered_at` | timestamp | value |  |
| `gross_amount` | decimal | value |  |