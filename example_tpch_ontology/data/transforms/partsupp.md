---
type: Transform
title: 'Cleansing: partsupp'
description: Cleansing → tpch.partsupp
relation: tpch.partsupp
tags:
- TPCH
- transform
- lifecycle:draft
sql_file: data/transforms/partsupp.sql
---

Produces `tpch.partsupp` · grain: one row per partsupp

## Rules
## Lineage
- Source: [partsupp_raw](../sources/partsupp_raw.md)
- Clean dataset: [partsupp](../datasets/partsupp.md)

## SQL realization
Realized by `partsupp.sql` (a deployed `CREATE VIEW`) — open it with the **SQL** button in the header, or in the Source browser.

## Lineage (column-level)

`tpch.partsupp` · kinds: passthrough

| output column | ← from | rule | kind |
|---|---|---|---|
| `ps_partkey` | `partsupp_raw.ps_partkey` | None | passthrough |
| `ps_suppkey` | `partsupp_raw.ps_suppkey` | None | passthrough |
| `ps_availqty` | `partsupp_raw.ps_availqty` | None | passthrough |
| `ps_supplycost` | `partsupp_raw.ps_supplycost` | None | passthrough |
| `ps_comment` | `partsupp_raw.ps_comment` | None | passthrough |