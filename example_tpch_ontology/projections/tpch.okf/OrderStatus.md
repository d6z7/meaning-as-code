---
type: Enumeration
title: Order Status
description: 'The status of an order, derived in TPC-H from the line-status of its
  lines: open if all lines are still open, fulfilled if all are fulfilled, partial
  when mixed.'
resource: table://tpch/orders
tags:
- TPCH
- enumeration
- confidence:C
timestamp: '2026-06-18'
---

# Order Status

The status of an order, derived in TPC-H from the line-status of its lines: open if all lines are still open, fulfilled if all are fulfilled, partial when mixed. The code list the o_orderstatus discriminator column carries.

## Purpose

Gives the order roll-up status stable codes + meanings so a filter ("open orders") uses one agreed vocabulary rather than ad-hoc string matching on a single-letter column.

# Schema

Grounded in `tpch.orders`.

| column | type | role | description |
|---|---|---|---|
| `o_orderkey` | integer | primary_key |  |
| `o_custkey` | integer | foreign_key |  |
| `o_orderstatus` | string | discriminator |  |
| `o_totalprice` | decimal | value |  |
| `o_orderdate` | date | value |  |
| `o_orderpriority` | string | discriminator |  |
| `o_comment` | string | value |  |

# Values

Closed code list — these 3 are the complete set.

| code | label | meaning |
|---|---|---|
| `O` | Open | all of the order's lines are still open (in-flight) |
| `F` | Fulfilled | all of the order's lines are fulfilled |
| `P` | Partial | the order's lines are a mix of open and fulfilled |

# Citations

1. MAC concept source of record: `concepts/order/order_status.yaml` (schema_version 0.1.9, confidence C).
