---
type: Grouping
title: Product Bundle
description: A curated set of products sold and reported together (e.g.
tags:
- SHOP
- grouping
- confidence:C
---

A curated set of products sold and reported together (e.g. a "starter kit"). A ProductBundle is not a sellable leaf (that is Product, a reference); it is the roll-up level used to aggregate revenue over the products it contains. Its member sets are a CLOSED enumeration, but they are NOT listed here — they live in the pinned, exploded `product_bundles` register (one row per bundle×product), the single home of the membership. The grouping realizes its member sets by re-aggregating that register.

## Details

- **Identity** — code
- **Version** — 1.0
- **Schema version** — 0.1.12
- **Status** — production
- **Owner** — example-team
- **Last reviewed** — 2026-07-15

## Relationships

*0 join(s) out · 0 in — click a concept to open it.*

**Groups** → **Product** — the leaf concept this rolls up.

## Source of record
- Full MAC concept: `product_bundle.yaml` — open the **YAML** tab for the complete typed definition.