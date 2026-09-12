---
type: Transform
title: 'Cleansing: part'
description: Cleansing → tpch.part
relation: tpch.part
tags:
- TPCH
- transform
- lifecycle:draft
sql_file: data/transforms/part.sql
---

Produces `tpch.part` · grain: one row per p_partkey

## Rules
## Lineage
- Source: [part_raw](../sources/part_raw.md)
- Clean dataset: [part](../datasets/part.md)

## SQL realization
Realized by `part.sql` (a deployed `CREATE VIEW`) — open it with the **SQL** button in the header, or in the Source browser.

## Lineage (column-level)

`tpch.part` · kinds: passthrough

| output column | ← from | rule | kind |
|---|---|---|---|
| `p_partkey` | `part_raw.p_partkey` | None | passthrough |
| `p_name` | `part_raw.p_name` | None | passthrough |
| `p_mfgr` | `part_raw.p_mfgr` | None | passthrough |
| `p_brand` | `part_raw.p_brand` | None | passthrough |
| `p_type` | `part_raw.p_type` | None | passthrough |
| `p_size` | `part_raw.p_size` | None | passthrough |
| `p_retailprice` | `part_raw.p_retailprice` | None | passthrough |
| `p_comment` | `part_raw.p_comment` | None | passthrough |