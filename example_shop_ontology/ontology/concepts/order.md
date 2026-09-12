---
type: Event
title: Order
description: 'A purchase a customer places: one or more products bought in a single checkout.'
tags:
- SHOP
- event
- confidence:C
rule_pages:
- rules/order.state.from_timestamps.md
- rules/order.revenue.paid_only.md
---

A purchase a customer places: one or more products bought in a single checkout. An order is a thing that HAPPENS and then moves through states — placed → paid → shipped → delivered, with returned/cancelled as terminal branches. Its current state is its furthest-reached lifecycle state.

## Details

- **Identity** — fk_name
- **Version** — 1.0
- **Schema version** — 0.1.9
- **Status** — production
- **Owner** — example-team
- **Last reviewed** — 2026-06-05

## How to answer

*What an agent needs ONLY, to answer with this concept — no data probing.*

```text
Everything needed to read an order's state and its revenue-eligibility is on the orders row — the lifecycle is which `*_at` timestamps are present, not a separate column. No warehouse probe needed.
```

## Fields

| column | role | grounded in | description | joins → |
|---|---|---|---|---|
| `order_id` | key | — |  |  |
| `customer_id` | key | — |  | [Customer](customer.md) |
| `status` | dimension | — |  |  |
| `gross_amount` | measure | — |  |  |

## Relationships

*1 join(s) out · 0 in — click a concept to open it.*

**Joins to** — this concept references:

- [Customer](customer.md) — joined on `customer_id`

## Source of record
- Full MAC concept: `order.yaml` — open the **YAML** tab for the complete typed definition.