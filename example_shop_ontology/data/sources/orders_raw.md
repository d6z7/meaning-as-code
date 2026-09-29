---
type: Source
title: orders_raw
description: Raw upstream orders as they arrive (mixed status casing, amount in integer
  cents).
resource: table://shop_raw.orders_raw
tags:
- SHOP
- source
- lifecycle:draft
- confidence:Q
---

## Columns

| column | type | role | reference |
|---|---|---|---|
| `order_id` | string | PK |  |
| `customer_id` | string | FK |  |
| `status` | string | discriminator |  |
| `gross_cents` | bigint | value |  |
| `placed_at` | timestamp | value |  |