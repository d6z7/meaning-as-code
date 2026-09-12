---
type: Rule
title: lineitem.state.received_iff_receiptdate
description: resolution rule · binds l_receiptdate, l_linestatus
tags:
- mac.rule_kind.resolution
applies_to: ../lineitem.md
---

## Rule

- **Kind** — `resolution`
- **Binds** — `l_receiptdate`, `l_linestatus`
- **Rule id** — `lineitem.state.received_iff_receiptdate`

### When

deciding whether a line has been received (the IN_FLIGHT → CLOSED boundary)

### Then — do (then)

a line is received iff l_receiptdate IS NOT NULL; l_linestatus = F confirms fulfilment

Applies to [Order Line](../lineitem.md).