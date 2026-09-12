---
type: Metric
title: Revenue
description: The monetary value of sales.
tags:
- SHOP
- measure
- confidence:C
rule_pages:
- rules/revenue.net_of_refunds.md
---

The monetary value of sales. GROSS revenue is the order total at checkout; NET revenue subtracts refunds (from returned orders). "Revenue" without qualification means NET — the figure the business reports. Net revenue is COMPUTED (see rules.yaml > net_revenue), not stored.

## Details

- **Identity** — code
- **Version** — 1.0
- **Schema version** — 0.1.9
- **Status** — production
- **Owner** — example-team
- **Last reviewed** — 2026-06-05

## How to answer

*What an agent needs ONLY, to answer with this concept — no data probing.*

```text
Everything needed to answer "revenue" is here. Use NET revenue (rule net_revenue = gross − refunds); never SUM(orders.gross_amount) on its own. No probe of the warehouse is needed to discover the refunds join — the rule encodes it. If you find yourself wanting to probe, this concept is incomplete: fix it.
```

## Source of record
- Full MAC concept: `revenue.yaml` — open the **YAML** tab for the complete typed definition.