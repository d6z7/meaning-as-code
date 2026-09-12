---
type: Rule
title: revenue.net_of_refunds
description: aggregation rule · binds gross_amount
tags:
- mac.rule_kind.aggregation
applies_to: ../revenue.md
---

## Rule

- **Kind** — `aggregation`
- **Binds** — `gross_amount`
- **Rule id** — `revenue.net_of_refunds`

### When

computing revenue from orders

### Then — do (then)

net = SUM(gross_amount) minus the order's summed refunds (rule net_revenue); an absent refund counts as 0

### Never — don't (never)

summing gross_amount alone — that is gross, not net revenue

Applies to [Revenue](../revenue.md).