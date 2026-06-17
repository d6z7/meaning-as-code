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
| `l_orderkey` | integer | foreign_key | → orders.o_orderkey (part_of edge); + composite-key part |
| `l_linenumber` | integer | composite_key_part | line sequence within the order |
| `l_partkey` | integer | foreign_key | → part.p_partkey (with l_suppkey = partsupp) |
| `l_suppkey` | integer | foreign_key | → supplier.s_suppkey (with l_partkey = partsupp) |
| `l_quantity` | decimal | value |  |
| `l_extendedprice` | decimal | value | list price × quantity (gross, pre-discount) |
| `l_discount` | decimal | value | fractional discount 0..1 |
| `l_tax` | decimal | value |  |
| `l_returnflag` | string | discriminator | R returned · A/N not |
| `l_linestatus` | string | discriminator | O in-flight · F fulfilled |
| `l_shipdate` | date | value |  |
| `l_commitdate` | date | value |  |
| `l_receiptdate` | date | value |  |
| `l_shipmode` | string | discriminator |  |
| `l_comment` | string | value |  |

## Relationships

- **partOfOrder** → [Orders](/Orders.md) (cardinality 1; grounded join `lineitem.l_orderkey = orders.o_orderkey`)
- **suppliedVia** → [PartSupp](/PartSupp.md) (cardinality 1; grounded join `lineitem.l_partkey = partsupp.ps_partkey AND lineitem.l_suppkey = partsupp.ps_suppkey`)

# Citations

1. MAC concept source of record: `concepts/order/lineitem.yaml` (schema_version 0.1.6, confidence C).
