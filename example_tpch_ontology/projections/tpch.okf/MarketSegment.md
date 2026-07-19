---
type: Enumeration
title: Market Segment
description: The market segment a customer belongs to — the code list the c_mktsegment
  discriminator column carries.
resource: table://tpch/customer
tags:
- TPCH
- enumeration
- confidence:C
timestamp: '2026-06-18'
---

# Market Segment

The market segment a customer belongs to — the code list the c_mktsegment discriminator column carries. TPC-H defines exactly five segments.

## Purpose

Stable codes + meanings so "customers in the BUILDING segment" filters on one agreed vocabulary rather than free-text matching.

# Schema

Grounded in `tpch.customer`.

| column | type | role | description |
|---|---|---|---|
| `c_custkey` | integer | primary_key |  |
| `c_name` | string | value |  |
| `c_nationkey` | integer | foreign_key |  |
| `c_phone` | string | value |  |
| `c_acctbal` | decimal | value |  |
| `c_mktsegment` | string | discriminator |  |
| `c_comment` | string | value |  |

# Values

Closed code list — these 5 are the complete set.

| code | label | meaning |
|---|---|---|
| `AUTOMOBILE` | Automobile | automotive sector customers |
| `BUILDING` | Building | building/construction sector customers |
| `FURNITURE` | Furniture | furniture sector customers |
| `HOUSEHOLD` | Household | household sector customers |
| `MACHINERY` | Machinery | machinery sector customers |

# Citations

1. MAC concept source of record: `concepts/party/market_segment.yaml` (schema_version 0.1.10, confidence C).
