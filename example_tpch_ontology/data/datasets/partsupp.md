---
type: Dataset
title: 'Clean: partsupp'
description: AI-friendly clean shape the ontology binds to
relation: tpch.partsupp
tags:
- TPCH
- dataset
- lifecycle:draft
---

## Columns

| column | type | role |
|---|---|---|
| `ps_partkey` | integer | composite_key_part |
| `ps_suppkey` | integer | composite_key_part |
| `ps_availqty` | integer | value |
| `ps_supplycost` | decimal | value |
| `ps_comment` | string | value |

## Foreign keys
- `ps_partkey` → `part.p_partkey`
- `ps_suppkey` → `supplier.s_suppkey`