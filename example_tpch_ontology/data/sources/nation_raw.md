---
type: Source
title: nation_raw
description: One row per nation as delivered by the TPC-H generator (dbgen). Schema-of-record
  for the raw input; the nation dataset is a passthrough load of it.
resource: table://tpch_raw.nation_raw
tags:
- TPCH
- source
- lifecycle:draft
- confidence:C
---

## Columns

| column | type | role | confidence |
|---|---|---|---|
| `n_nationkey` | string | value |  |
| `n_name` | string | value |  |
| `n_regionkey` | string | value |  |
| `n_comment` | string | value |  |