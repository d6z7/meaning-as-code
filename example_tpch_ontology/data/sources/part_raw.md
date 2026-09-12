---
type: Source
title: part_raw
description: One row per part as delivered by the TPC-H generator (dbgen). Schema-of-record
  for the raw input; the part dataset is a passthrough load of it.
resource: table://tpch_raw.part_raw
tags:
- TPCH
- source
- lifecycle:draft
- confidence:C
---

## Columns

| column | type | role | confidence |
|---|---|---|---|
| `p_partkey` | string | value |  |
| `p_name` | string | value |  |
| `p_mfgr` | string | value |  |
| `p_brand` | string | value |  |
| `p_type` | string | value |  |
| `p_size` | string | value |  |
| `p_retailprice` | string | value |  |
| `p_comment` | string | value |  |