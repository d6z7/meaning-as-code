---
type: Transform
title: 'Cleansing: lineitem'
description: Cleansing → tpch.lineitem
relation: tpch.lineitem
tags:
- TPCH
- transform
- lifecycle:draft
sql_file: data/transforms/lineitem.sql
---

Produces `tpch.lineitem` · grain: one row per (l_orderkey, l_linenumber)

## Rules
### unit_mismatch — `discount-basis-points-to-fraction` · applied
- **defect** discount arrives as integer basis points (l_discount_bps, e.g. 700 = 7%)
- **rule** convert basis points to the [0,1] fraction the ontology's Revenue rule expects
- **guarantee** l_discount is a [0,1] fraction — Revenue = extendedprice * (1 - l_discount) is correct

## Lineage
- Source: [lineitem_raw](../sources/lineitem_raw.md)
- Clean dataset: [lineitem](../datasets/lineitem.md)

## SQL realization
Realized by `lineitem.sql` (a deployed `CREATE VIEW`) — open it with the **SQL** button in the header, or in the Source browser.

## Lineage (column-level)

`tpch.lineitem` · kinds: const · passthrough · transform

| output column | ← from | rule | kind |
|---|---|---|---|
| `l_discount_bps` | `lineitem_raw.l_discount_bps` | discount-basis-points-to-fraction | transform |
| `l_orderkey` | `lineitem_raw.l_orderkey` | None | passthrough |
| `l_linenumber` | `lineitem_raw.l_linenumber` | None | passthrough |
| `l_partkey` | `lineitem_raw.l_partkey` | None | passthrough |
| `l_suppkey` | `lineitem_raw.l_suppkey` | None | passthrough |
| `l_quantity` | `lineitem_raw.l_quantity` | None | passthrough |
| `l_extendedprice` | `lineitem_raw.l_extendedprice` | None | passthrough |
| `l_returnflag` | `lineitem_raw.l_returnflag` | None | passthrough |
| `l_linestatus` | `lineitem_raw.l_linestatus` | None | passthrough |
| `l_shipdate` | `lineitem_raw.l_shipdate` | None | passthrough |
| `l_discount` | _literal per branch_ |  | const |
| `l_tax` | _literal per branch_ |  | const |
| `l_commitdate` | _literal per branch_ |  | const |
| `l_receiptdate` | _literal per branch_ |  | const |
| `l_shipmode` | _literal per branch_ |  | const |
| `l_comment` | _literal per branch_ |  | const |