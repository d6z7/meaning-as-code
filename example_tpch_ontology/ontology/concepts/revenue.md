---
type: Metric
title: Revenue
description: 'The monetary value of sales, net of discount: per order line, l_extendedprice × (1 − l_discount).'
tags:
- TPCH
- measure
- confidence:C
---

The monetary value of sales, net of discount: per order line, l_extendedprice × (1 − l_discount). "Revenue" without qualification means this net figure. It is COMPUTED (see rules.yaml > net_revenue), not a stored column.

## Details

- **Identity** — code
- **Version** — 1.0
- **Schema version** — 0.1.9
- **Status** — production
- **Owner** — example-team
- **Last reviewed** — 2026-06-17

## Source of record
- Full MAC concept: `revenue.yaml` — open the **YAML** tab for the complete typed definition.