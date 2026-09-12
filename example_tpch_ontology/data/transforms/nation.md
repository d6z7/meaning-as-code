---
type: Transform
title: 'Cleansing: nation'
description: Cleansing → tpch.nation
relation: tpch.nation
tags:
- TPCH
- transform
- lifecycle:draft
sql_file: data/transforms/nation.sql
---

Produces `tpch.nation` · grain: one row per n_nationkey

## Rules
## Lineage
- Source: [nation_raw](../sources/nation_raw.md)
- Clean dataset: [nation](../datasets/nation.md)

## SQL realization
Realized by `nation.sql` (a deployed `CREATE VIEW`) — open it with the **SQL** button in the header, or in the Source browser.

## Lineage (column-level)

`tpch.nation` · kinds: passthrough

| output column | ← from | rule | kind |
|---|---|---|---|
| `n_nationkey` | `nation_raw.n_nationkey` | None | passthrough |
| `n_name` | `nation_raw.n_name` | None | passthrough |
| `n_regionkey` | `nation_raw.n_regionkey` | None | passthrough |
| `n_comment` | `nation_raw.n_comment` | None | passthrough |