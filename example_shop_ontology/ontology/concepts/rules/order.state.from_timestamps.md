---
type: Rule
title: order.state.from_timestamps
description: resolution rule · binds paid_at, shipped_at, delivered_at
tags:
- mac.rule_kind.resolution
applies_to: ../order.md
---

## Rule

- **Kind** — `resolution`
- **Binds** — `paid_at`, `shipped_at`, `delivered_at`
- **Rule id** — `order.state.from_timestamps`

### When

deciding an order's lifecycle state (placed / paid / shipped / delivered)

### Then — do (then)

read it from which timestamps are present — paid iff paid_at IS NOT NULL, shipped iff shipped_at IS NOT NULL, delivered iff delivered_at IS NOT NULL (furthest-reached state wins)

### Never — don't (never)

treating a NULL shipped_at as 'shipped at an unknown time' — NULL means not yet shipped

Applies to [Order](../order.md).