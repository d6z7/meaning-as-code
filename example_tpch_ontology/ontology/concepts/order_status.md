---
type: Enum
title: Order Status
description: 'The status of an order, derived in TPC-H from the line-status of its lines: open if all lines are still open, fulfilled if all are fulfilled, partial when mixed.'
tags:
- TPCH
- enumeration
- confidence:C
---

The status of an order, derived in TPC-H from the line-status of its lines: open if all lines are still open, fulfilled if all are fulfilled, partial when mixed. The code list the o_orderstatus discriminator column carries.

## Details

- **Identity** — code
- **Version** — 1.0
- **Schema version** — 0.1.9
- **Status** — production
- **Owner** — example-team
- **Last reviewed** — 2026-06-18

## Source of record
- Full MAC concept: `order_status.yaml` — open the **YAML** tab for the complete typed definition.