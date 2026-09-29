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

| column | type | role | reference |
|---|---|---|---|
| `refund_id` | string | PK |  |
| `order_id` | string | FK |  |
| `refund_amount` | decimal | value |  |
| `refunded_at` | timestamp | value |  |