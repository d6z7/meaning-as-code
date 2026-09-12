---
type: Transform
title: 'Cleansing: supplier'
description: Cleansing → tpch.supplier
relation: tpch.supplier
tags:
- TPCH
- transform
- lifecycle:draft
sql_file: data/transforms/supplier.sql
---

Produces `tpch.supplier` · grain: one row per s_suppkey

## Rules
## Lineage
- Source: [supplier_raw](../sources/supplier_raw.md)
- Clean dataset: [supplier](../datasets/supplier.md)

## SQL realization
Realized by `supplier.sql` (a deployed `CREATE VIEW`) — open it with the **SQL** button in the header, or in the Source browser.

## Lineage (column-level)

`tpch.supplier` · kinds: passthrough

| output column | ← from | rule | kind |
|---|---|---|---|
| `s_suppkey` | `supplier_raw.s_suppkey` | None | passthrough |
| `s_name` | `supplier_raw.s_name` | None | passthrough |
| `s_nationkey` | `supplier_raw.s_nationkey` | None | passthrough |
| `s_phone` | `supplier_raw.s_phone` | None | passthrough |
| `s_acctbal` | `supplier_raw.s_acctbal` | None | passthrough |
| `s_comment` | `supplier_raw.s_comment` | None | passthrough |