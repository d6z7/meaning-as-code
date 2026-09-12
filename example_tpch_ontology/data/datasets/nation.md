---
type: Dataset
title: 'Clean: nation'
description: AI-friendly clean shape the ontology binds to
relation: tpch.nation
tags:
- TPCH
- dataset
- lifecycle:draft
---

## Columns

| column | type | role |
|---|---|---|
| `n_nationkey` | integer | primary_key |
| `n_name` | string | value |
| `n_regionkey` | integer | foreign_key |
| `n_comment` | string | value |

## Foreign keys
- `n_regionkey` → `region.r_regionkey`