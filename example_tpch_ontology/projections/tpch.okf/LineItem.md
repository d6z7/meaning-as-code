---
type: Event
title: Order Line
description: A single line of an order — one part, supplied by one supplier, in some
  quantity at some price.
resource: table://tpch/lineitem
tags:
- TPCH
- event
- confidence:C
timestamp: '2026-06-17'
---

# Order Line

A single line of an order — one part, supplied by one supplier, in some quantity at some price. The central fact of TPC-H (composite key order + line number). It is an EVENT: it is shipped, received, and possibly returned, moving through a fulfilment lifecycle read from its ship/receipt dates and status flags. Revenue is computed from its extended price and discount.

## Purpose

The grain of sales analysis — quantity, price and discount per part/supplier/order, the source of Revenue and of fulfilment timing.

# Schema

Grounded in `tpch.lineitem`.

| column | type | role | description |
|---|---|---|---|
| `l_orderkey` | integer | foreign_key |  |
| `l_linenumber` | integer | composite_key_part |  |
| `l_partkey` | integer | foreign_key |  |
| `l_suppkey` | integer | foreign_key |  |
| `l_quantity` | decimal | value |  |
| `l_extendedprice` | decimal | value | use l_extendedprice * (1 - l_discount); a NULL discount counts as 0 (full extended price) |
| `l_discount` | decimal | value | use l_extendedprice * (1 - l_discount); a NULL discount counts as 0 (full extended price) |
| `l_tax` | decimal | value |  |
| `l_returnflag` | string | discriminator |  |
| `l_linestatus` | string | discriminator | a line is received iff l_receiptdate IS NOT NULL; l_linestatus = F confirms fulfilment |
| `l_shipdate` | date | value |  |
| `l_commitdate` | date | value |  |
| `l_receiptdate` | date | value | a line is received iff l_receiptdate IS NOT NULL; l_linestatus = F confirms fulfilment |
| `l_shipmode` | string | discriminator |  |
| `l_comment` | string | value |  |

## Relationships

- **partOfOrder** → [Orders](/Orders.md) (cardinality 1; grounded join `lineitem.l_orderkey = orders.o_orderkey`)
- **suppliedVia** → [PartSupp](/PartSupp.md) (cardinality 1; grounded join `lineitem.l_partkey = partsupp.ps_partkey AND lineitem.l_suppkey = partsupp.ps_suppkey`)

# Citations

1. MAC concept source of record: `concepts/order/lineitem.yaml` (schema_version 0.1.9, confidence C).
