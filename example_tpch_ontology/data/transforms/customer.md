---
type: Transform
title: 'Cleansing: customer'
description: Cleansing → tpch.customer
relation: tpch.customer
tags:
- TPCH
- transform
- lifecycle:draft
sql_file: data/transforms/customer.sql
---

Produces `tpch.customer` · grain: one row per c_custkey

## Rules
## Lineage
- Source: [customer_raw](../sources/customer_raw.md)
- Clean dataset: [customer](../datasets/customer.md)

## SQL realization
Realized by `customer.sql` (a deployed `CREATE VIEW`) — open it with the **SQL** button in the header, or in the Source browser.

## Lineage (column-level)

`tpch.customer` · kinds: passthrough

| output column | ← from | rule | kind |
|---|---|---|---|
| `c_custkey` | `customer_raw.c_custkey` | None | passthrough |
| `c_name` | `customer_raw.c_name` | None | passthrough |
| `c_nationkey` | `customer_raw.c_nationkey` | None | passthrough |
| `c_phone` | `customer_raw.c_phone` | None | passthrough |
| `c_acctbal` | `customer_raw.c_acctbal` | None | passthrough |
| `c_mktsegment` | `customer_raw.c_mktsegment` | None | passthrough |
| `c_comment` | `customer_raw.c_comment` | None | passthrough |