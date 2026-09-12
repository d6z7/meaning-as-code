---
type: Dataset
title: 'Clean: orders'
description: AI-friendly clean shape the ontology binds to
relation: tpch.orders
tags:
- TPCH
- dataset
- lifecycle:draft
---

## Columns

| column | type | role |
|---|---|---|
| `o_orderkey` | integer | primary_key |
| `o_custkey` | integer | foreign_key |
| `o_orderstatus` | string | discriminator |
| `o_totalprice` | decimal | value |
| `o_orderdate` | date | value |
| `o_orderpriority` | string | discriminator |
| `o_comment` | string | value |

## Foreign keys
- `o_custkey` → `customer.c_custkey`