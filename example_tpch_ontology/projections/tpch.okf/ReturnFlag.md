---
type: Enumeration
title: Return Flag
description: Whether an order line was returned.
resource: table://tpch/lineitem
tags:
- TPCH
- enumeration
- confidence:C
timestamp: '2026-06-18'
---

# Return Flag

Whether an order line was returned. The code list the l_returnflag discriminator column carries — R for returned; A and N are the two not-returned codes (TPC-H splits not-returned by receipt date).

## Purpose

Stable codes + meanings so "returned lines" is one agreed filter (l_returnflag = 'R') rather than guessing which letters mean returned.

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

# Values

Closed code list — these 3 are the complete set.

| code | label | meaning |
|---|---|---|
| `R` | Returned | the line was returned |
| `A` | Not returned | not returned (TPC-H's first not-returned class) |
| `N` | Not returned | not returned (TPC-H's second not-returned class) |

# Citations

1. MAC concept source of record: `concepts/order/return_flag.yaml` (schema_version 0.1.9, confidence C).
