---
type: Source
title: partsupp_raw
description: One row per partsupp as delivered by the TPC-H generator (dbgen). Schema-of-record
  for the raw input; the partsupp dataset is a passthrough load of it.
resource: table://tpch_raw.partsupp_raw
tags:
- TPCH
- source
- lifecycle:draft
- confidence:C
---

## Columns

| column | type | role | confidence |
|---|---|---|---|
| `ps_partkey` | string | value |  |
| `ps_suppkey` | string | value |  |
| `ps_availqty` | string | value |  |
| `ps_supplycost` | string | value |  |
| `ps_comment` | string | value |  |