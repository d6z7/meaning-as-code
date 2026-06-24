---
type: Metric
title: Revenue
description: 'The monetary value of sales, net of discount: per order line, l_extendedprice
  × (1 − l_discount).'
resource: table://tpch/lineitem
tags:
- TPCH
- measure
- confidence:C
timestamp: '2026-06-17'
---

# Revenue

The monetary value of sales, net of discount: per order line, l_extendedprice × (1 − l_discount). "Revenue" without qualification means this net figure. It is COMPUTED (see rules.yaml > net_revenue), not a stored column.

## Purpose

The headline financial measure — sliced by part, customer, supplier, geography and time; the numerator of TPC-H's revenue and market-share queries.

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

## Derivation

Computed by rule `net_revenue` (see the MAC rules layer); do not re-derive the formula.

# Citations

1. MAC concept source of record: `concepts/finance/revenue.yaml` (schema_version 0.1.9, confidence C).
