---
type: Source
title: customer_raw
description: One row per customer as delivered by the TPC-H generator (dbgen). Schema-of-record
  for the raw input; the customer dataset is a passthrough load of it.
resource: table://tpch_raw.customer_raw
tags:
- TPCH
- source
- lifecycle:draft
- confidence:C
---

## Columns

| column | type | role | confidence |
|---|---|---|---|
| `c_custkey` | string | value |  |
| `c_name` | string | value |  |
| `c_nationkey` | string | value |  |
| `c_phone` | string | value |  |
| `c_acctbal` | string | value |  |
| `c_mktsegment` | string | value |  |
| `c_comment` | string | value |  |