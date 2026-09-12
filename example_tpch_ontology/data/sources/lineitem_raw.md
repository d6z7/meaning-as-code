---
type: Source
title: lineitem_raw
description: Raw upstream order lines as they arrive (single-char return-flag codes,
  discount as basis points).
resource: table://tpch_raw.lineitem_raw
tags:
- TPCH
- source
- lifecycle:draft
- confidence:C
---

## Columns

| column | type | role | confidence |
|---|---|---|---|
| `l_orderkey` | integer | foreign_key |  |
| `l_linenumber` | integer | composite_key_part |  |
| `l_partkey` | integer | foreign_key |  |
| `l_suppkey` | integer | foreign_key |  |
| `l_quantity` | decimal | value |  |
| `l_extendedprice` | decimal | value |  |
| `l_discount_bps` | integer | value |  |
| `l_returnflag` | string | discriminator |  |
| `l_linestatus` | string | discriminator |  |
| `l_shipdate` | date | value |  |