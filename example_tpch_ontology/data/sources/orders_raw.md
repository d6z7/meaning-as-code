---
type: Source
title: orders_raw
description: One row per orders as delivered by the TPC-H generator (dbgen). Schema-of-record
  for the raw input; the orders dataset is a passthrough load of it.
resource: table://tpch_raw.orders_raw
tags:
- TPCH
- source
- lifecycle:draft
- confidence:C
---

## Columns

| column | type | role | confidence |
|---|---|---|---|
| `o_orderkey` | string | value |  |
| `o_custkey` | string | value |  |
| `o_orderstatus` | string | value |  |
| `o_totalprice` | string | value |  |
| `o_orderdate` | string | value |  |
| `o_orderpriority` | string | value |  |
| `o_comment` | string | value |  |