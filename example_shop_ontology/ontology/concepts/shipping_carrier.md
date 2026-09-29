---
type: Enum
title: Shipping Carrier
description: The set of shipping carriers an Order can be handed to.
tags:
- SHOP
- enumeration
- confidence:C
resource: table://shipping_carriers
---

The set of shipping carriers an Order can be handed to. This is a closed value vocabulary, but its members are NOT enumerated here — they live in the pinned `shipping_carriers` register (code + label), the single home of the code set. The enumeration realizes its value domain by reading that register.

## Details

- **Identity** — code
- **Version** — 1.0
- **Schema version** — 0.1.16
- **Status** — production
- **Owner** — example-team
- **Last reviewed** — 2026-07-14

## Grounded in

- `shipping_carriers`

## Fields

| column | type | role | grounded in | description | joins → |
|---|---|---|---|---|---|
| `code` | string | — | `shipping_carriers` | — | — |
| `label` | string | — | `shipping_carriers` | — | — |

_Declared per column, over 2 columns: description 0 of 2 · type 2 of 2 · joins → 0 of 2. An em dash is a column for which nothing is declared._

## Source of record
- Full MAC concept: `shipping_carrier.yaml` — open the **YAML** tab for the complete typed definition.