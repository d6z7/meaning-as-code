---
type: Event
title: Order
description: 'A purchase a customer places: one or more products bought in a single checkout.'
tags:
- SHOP
- event
- confidence:C
resource: table://orders
rule_pages:
- rules/order.state.from_timestamps.md
- rules/order.revenue.paid_only.md
---

A purchase a customer places: one or more products bought in a single checkout. An order is a thing that HAPPENS and then moves through states — placed → paid → shipped → delivered, with returned/cancelled as terminal branches. Its current state is its furthest-reached lifecycle state.

## Details

- **Identity** — fk_name
- **Version** — 1.0
- **Schema version** — 0.1.16
- **Status** — production
- **Owner** — example-team
- **Last reviewed** — 2026-06-05

## How to answer

*What an agent needs ONLY, to answer with this concept — no data probing.*

```text
Everything needed to read an order's state and its revenue-eligibility is on the orders row — the lifecycle is which `*_at` timestamps are present, not a separate column. No warehouse probe needed.
```

## Grounded in

- `orders` — key `['order_id']`

## Fields

| column | type | role | grounded in | description | joins → |
|---|---|---|---|---|---|
| `order_id` | string | — | `orders` | — | — |
| `customer_id` | string | — | `orders` | — | [Customer](customer.md) |
| `status` | string | — | `orders` | — | — |
| `gross_amount` | decimal | — | `orders` | — | — |
| `placed_at` | timestamp | — | `orders` | — | — |
| `paid_at` | timestamp | — | `orders` | — | — |
| `shipped_at` | timestamp | — | `orders` | — | — |
| `delivered_at` | timestamp | — | `orders` | — | — |

_Declared per column, over 8 columns: description 0 of 8 · type 8 of 8 · joins → 1 of 8. An em dash is a column for which nothing is declared._

## Relationships

*1 join(s) out · 0 in — click a concept to open it.*

**Joins to** — this concept references:

- [Customer](customer.md) — joined on `customer_id`

## Source of record
- Full MAC concept: `order.yaml` — open the **YAML** tab for the complete typed definition.