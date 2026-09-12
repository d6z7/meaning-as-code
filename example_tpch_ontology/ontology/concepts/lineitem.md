---
type: Event
title: Order Line
description: A single line of an order — one part, supplied by one supplier, in some quantity at some price.
tags:
- TPCH
- event
- confidence:C
rule_pages:
- rules/lineitem.revenue.net_of_discount.md
- rules/lineitem.state.received_iff_receiptdate.md
---

A single line of an order — one part, supplied by one supplier, in some quantity at some price. The central fact of TPC-H (composite key order + line number). It is an EVENT: it is shipped, received, and possibly returned, moving through a fulfilment lifecycle read from its ship/receipt dates and status flags. Revenue is computed from its extended price and discount.

## Details

- **Identity** — composite
- **Version** — 1.0
- **Schema version** — 0.1.9
- **Status** — production
- **Owner** — example-team
- **Last reviewed** — 2026-06-17

## How to answer

*What an agent needs ONLY, to answer with this concept — no data probing.*

```text
To read a line you need only its columns here; revenue is net of discount (see net_revenue), and the fulfilment state is read from the dates/flags — no warehouse probe is needed.
```

## Relationships

*2 join(s) out · 0 in — click a concept to open it.*

**Joins to** — this concept references:

- [Order](orders.md) — joined on `l_orderkey`
- [Part-Supplier](partsupp.md) — joined on `l_partkey`

## Source of record
- Full MAC concept: `lineitem.yaml` — open the **YAML** tab for the complete typed definition.