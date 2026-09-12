---
type: Rule
title: lineitem.revenue.net_of_discount
description: aggregation rule · binds l_extendedprice, l_discount
tags:
- mac.rule_kind.aggregation
applies_to: ../lineitem.md
---

## Rule

- **Kind** — `aggregation`
- **Binds** — `l_extendedprice`, `l_discount`
- **Rule id** — `lineitem.revenue.net_of_discount`

### When

computing revenue from order lines

### Then — do (then)

use l_extendedprice * (1 - l_discount); a NULL discount counts as 0 (full extended price)

### Never — don't (never)

summing l_extendedprice alone — that is gross, not revenue

Applies to [Order Line](../lineitem.md).