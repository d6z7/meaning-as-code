---
type: Source
title: supplier_raw
description: One row per supplier as delivered by the TPC-H generator (dbgen). Schema-of-record
  for the raw input; the supplier dataset is a passthrough load of it.
resource: table://tpch_raw.supplier_raw
tags:
- TPCH
- source
- lifecycle:draft
- confidence:C
---

## Columns

| column | type | role | confidence |
|---|---|---|---|
| `s_suppkey` | string | value |  |
| `s_name` | string | value |  |
| `s_nationkey` | string | value |  |
| `s_phone` | string | value |  |
| `s_acctbal` | string | value |  |
| `s_comment` | string | value |  |