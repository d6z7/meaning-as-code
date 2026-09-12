---
type: Dataset
title: 'Clean: supplier'
description: AI-friendly clean shape the ontology binds to
relation: tpch.supplier
tags:
- TPCH
- dataset
- lifecycle:draft
---

## Columns

| column | type | role |
|---|---|---|
| `s_suppkey` | integer | primary_key |
| `s_name` | string | value |
| `s_nationkey` | integer | foreign_key |
| `s_phone` | string | value |
| `s_acctbal` | decimal | value |
| `s_comment` | string | value |

## Foreign keys
- `s_nationkey` → `nation.n_nationkey`