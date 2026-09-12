---
type: Dataset
title: 'Clean: lineitem'
description: AI-friendly clean shape the ontology binds to
relation: tpch.lineitem
tags:
- TPCH
- dataset
- lifecycle:draft
---

## Columns

| column | type | role |
|---|---|---|
| `l_orderkey` | integer | foreign_key |
| `l_linenumber` | integer | composite_key_part |
| `l_partkey` | integer | foreign_key |
| `l_suppkey` | integer | foreign_key |
| `l_quantity` | decimal | value |
| `l_extendedprice` | decimal | value |
| `l_discount` | decimal | value |
| `l_tax` | decimal | value |
| `l_returnflag` | string | discriminator |
| `l_linestatus` | string | discriminator |
| `l_shipdate` | date | value |
| `l_commitdate` | date | value |
| `l_receiptdate` | date | value |
| `l_shipmode` | string | discriminator |
| `l_comment` | string | value |

## Foreign keys
- `l_orderkey` → `orders.o_orderkey`