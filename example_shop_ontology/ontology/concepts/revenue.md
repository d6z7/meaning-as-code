---
type: Metric
title: Revenue
description: The monetary value of sales.
tags:
- SHOP
- measure
- confidence:C
resource: table://orders
rule_pages:
- rules/revenue.net_of_refunds.md
---

The monetary value of sales. GROSS revenue is the order total at checkout; NET revenue subtracts refunds (from returned orders). "Revenue" without qualification means NET — the figure the business reports. Net revenue is COMPUTED (see rules.yaml > net_revenue), not stored.

## Details

- **Identity** — code
- **Version** — 1.0
- **Schema version** — 0.1.16
- **Status** — production
- **Owner** — example-team
- **Last reviewed** — 2026-06-05

## How to answer

*What an agent needs ONLY, to answer with this concept — no data probing.*

```text
Everything needed to answer "revenue" is here. Use NET revenue (rule net_revenue = gross − refunds); never SUM(orders.gross_amount) on its own. No probe of the warehouse is needed to discover the refunds join — the rule encodes it. If you find yourself wanting to probe, this concept is incomplete: fix it.
```

## Grounded in

- `orders`

## Fields

| column | type | role | grounded in | description | joins → |
|---|---|---|---|---|---|
| `order_id` | string | — | `orders` | — | — |
| `customer_id` | string | — | `orders` | — | — |
| `status` | string | — | `orders` | — | — |
| `placed_at` | timestamp | — | `orders` | — | — |
| `paid_at` | timestamp | — | `orders` | — | — |
| `shipped_at` | timestamp | — | `orders` | — | — |
| `delivered_at` | timestamp | — | `orders` | — | — |
| `gross_amount` | decimal | — | `orders` | — | — |

_Declared per column, over 8 columns: description 0 of 8 · type 8 of 8 · joins → 0 of 8. An em dash is a column for which nothing is declared._

## Axes

Measure type: `flow` — `mac.concept.column.measure_type.flow`.

| axis | axis kind | fold |
|---|---|---|
| `customer` | categorical | additive |
| `product` | categorical | additive |
| `time` | time | additive |

_The fold is read from the framework registry (`measure_type.<type>.additivity.<axis kind>`), not declared on this concept. An em dash means the crossing is not declared there._

## Source of record
- Full MAC concept: `revenue.yaml` — open the **YAML** tab for the complete typed definition.