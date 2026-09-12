---
type: Rule
title: order.revenue.paid_only
description: exclusion rule · binds paid_at
tags:
- mac.rule_kind.exclusion
applies_to: ../order.md
---

## Rule

- **Kind** — `exclusion`
- **Binds** — `paid_at`
- **Rule id** — `order.revenue.paid_only`

### When

counting an order toward revenue

### Then — do (then)

include it only if it is paid (paid_at IS NOT NULL)

### Never — don't (never)

counting a PLACED-but-unpaid order as revenue

Applies to [Order](../order.md).