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
- confidence:C
---

## Columns

| column | type | role | confidence |
|---|---|---|---|
| `order_id` | string | primary_key |  |
| `customer_id` | string | foreign_key |  |
| `status` | string | discriminator |  |
| `gross_cents` | bigint | value |  |
| `placed_at` | timestamp | value |  |