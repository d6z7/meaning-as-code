---
type: Transform
title: 'Cleansing: region'
description: Cleansing → tpch.region
relation: tpch.region
tags:
- TPCH
- transform
- lifecycle:draft
sql_file: data/transforms/region.sql
---

Produces `tpch.region` · grain: one row per r_regionkey

## Rules
## Lineage
- Source: [region_raw](../sources/region_raw.md)
- Clean dataset: [region](../datasets/region.md)

## SQL realization
Realized by `region.sql` (a deployed `CREATE VIEW`) — open it with the **SQL** button in the header, or in the Source browser.

## Lineage (column-level)

`tpch.region` · kinds: passthrough

| output column | ← from | rule | kind |
|---|---|---|---|
| `r_regionkey` | `region_raw.r_regionkey` | None | passthrough |
| `r_name` | `region_raw.r_name` | None | passthrough |
| `r_comment` | `region_raw.r_comment` | None | passthrough |