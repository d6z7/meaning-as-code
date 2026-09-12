---
type: Transform
title: 'Cleansing: orders'
description: Cleansing → tpch.orders
relation: tpch.orders
tags:
- TPCH
- transform
- lifecycle:draft
sql_file: data/transforms/orders.sql
---

Produces `tpch.orders` · grain: one row per o_orderkey

## Rules
## Lineage
- Source: [orders_raw](../sources/orders_raw.md)
- Clean dataset: [orders](../datasets/orders.md)

## SQL realization
Realized by `orders.sql` (a deployed `CREATE VIEW`) — open it with the **SQL** button in the header, or in the Source browser.

## Lineage (column-level)

`tpch.orders` · kinds: passthrough

| output column | ← from | rule | kind |
|---|---|---|---|
| `o_orderkey` | `orders_raw.o_orderkey` | None | passthrough |
| `o_custkey` | `orders_raw.o_custkey` | None | passthrough |
| `o_orderstatus` | `orders_raw.o_orderstatus` | None | passthrough |
| `o_totalprice` | `orders_raw.o_totalprice` | None | passthrough |
| `o_orderdate` | `orders_raw.o_orderdate` | None | passthrough |
| `o_orderpriority` | `orders_raw.o_orderpriority` | None | passthrough |
| `o_comment` | `orders_raw.o_comment` | None | passthrough |