---
type: Source
title: region_raw
description: One row per region as delivered by the TPC-H generator (dbgen). Schema-of-record
  for the raw input; the region dataset is a passthrough load of it.
resource: table://tpch_raw.region_raw
tags:
- TPCH
- source
- lifecycle:draft
- confidence:C
---

## Columns

| column | type | role | confidence |
|---|---|---|---|
| `r_regionkey` | string | value |  |
| `r_name` | string | value |  |
| `r_comment` | string | value |  |