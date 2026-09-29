---
type: Enum
title: Order Status
description: The set of states an Order can be in.
tags:
- SHOP
- enumeration
- confidence:C
resource: table://orders
---

The set of states an Order can be in. This is the value vocabulary that the Order lifecycle moves through (see order.yaml > lifecycle); here it is enumerated as a closed code list with meanings.

## Details

- **Identity** — code
- **Version** — 1.0
- **Schema version** — 0.1.16
- **Status** — production
- **Owner** — example-team
- **Last reviewed** — 2026-06-05

## Grounded in

- `orders`

## Fields

| column | type | role | grounded in | description | joins → |
|---|---|---|---|---|---|
| `order_id` | string | — | `orders` | — | — |
| `status` | string | — | `orders` | — | — |

_Declared per column, over 2 columns: description 0 of 2 · type 2 of 2 · joins → 0 of 2. An em dash is a column for which nothing is declared._

## Source of record
- Full MAC concept: `order_status.yaml` — open the **YAML** tab for the complete typed definition.