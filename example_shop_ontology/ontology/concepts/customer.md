---
type: Entity
title: Customer
description: A person (or business) who can place orders in the shop.
tags:
- SHOP
- entity
- confidence:C
resource: table://customers
---

A person (or business) who can place orders in the shop. Identified by customer_id. The root party of the ordering process; an Order is placed_by exactly one Customer.

## Details

- **Identity** — fk_name
- **Version** — 1.0
- **Schema version** — 0.1.16
- **Status** — production
- **Owner** — example-team
- **Last reviewed** — 2026-06-05

## Grounded in

- `customers` — key `['customer_id']`

## Fields

| column | type | role | grounded in | description | joins → |
|---|---|---|---|---|---|
| `customer_id` | string | — | `customers` | — | — |
| `email` | string | — | `customers` | — | — |
| `created_at` | timestamp | — | `customers` | — | — |

_Declared per column, over 3 columns: description 0 of 3 · type 3 of 3 · joins → 0 of 3. An em dash is a column for which nothing is declared._

## Relationships

*0 join(s) out · 1 in — click a concept to open it.*

**Referenced by** — these point at this concept:

- [Order](order.md) — on `customer_id`

## Source of record
- Full MAC concept: `customer.yaml` — open the **YAML** tab for the complete typed definition.