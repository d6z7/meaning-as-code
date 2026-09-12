---
type: Dataset
title: 'Clean: part'
description: AI-friendly clean shape the ontology binds to
relation: tpch.part
tags:
- TPCH
- dataset
- lifecycle:draft
---

## Columns

| column | type | role |
|---|---|---|
| `p_partkey` | integer | primary_key |
| `p_name` | string | value |
| `p_mfgr` | string | value |
| `p_brand` | string | discriminator |
| `p_type` | string | discriminator |
| `p_size` | integer | value |
| `p_retailprice` | decimal | value |
| `p_comment` | string | value |