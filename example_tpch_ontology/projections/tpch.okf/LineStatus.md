---
type: Enumeration
title: Line Status
description: The fulfilment status of a single order line — whether the line has shipped/been
  fulfilled or is still in flight.
resource: table://tpch/lineitem
tags:
- TPCH
- enumeration
- confidence:C
timestamp: '2026-06-18'
---

# Line Status

The fulfilment status of a single order line — whether the line has shipped/been fulfilled or is still in flight. The code list the l_linestatus discriminator column carries.

## Purpose

Stable codes + meanings for line fulfilment so a filter uses one agreed vocabulary rather than matching a single-letter column directly.

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

Closed code list — these 2 are the complete set.

| code | label | meaning |
|---|---|---|
| `O` | Open | in-flight — not yet fulfilled |
| `F` | Fulfilled | fulfilled |

# Citations

1. MAC concept source of record: `concepts/order/line_status.yaml` (schema_version 0.1.9, confidence C).
