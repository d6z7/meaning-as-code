---
type: Dataset
title: 'Clean: customer'
description: AI-friendly clean shape the ontology binds to
relation: tpch.customer
tags:
- TPCH
- dataset
- lifecycle:draft
---

## Columns

| column | type | role |
|---|---|---|
| `c_custkey` | integer | primary_key |
| `c_name` | string | value |
| `c_nationkey` | integer | foreign_key |
| `c_phone` | string | value |
| `c_acctbal` | decimal | value |
| `c_mktsegment` | string | discriminator |
| `c_comment` | string | value |

## Foreign keys
- `c_nationkey` → `nation.n_nationkey`