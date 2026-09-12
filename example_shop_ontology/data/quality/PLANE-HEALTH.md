---
type: Doc
title: Plane health — chain, lineage & protocol
description: Chain integrity, lineage coverage and change-protocol metrics
tags:
- SHOP
- plane-health
---

The structural health of this source's data plane — the same numbers the gates check, surfaced here so they are visible without running a terminal command. **The gates remain authoritative**; this page is a read-view.

## Chain — `raw source → transformation → dataset → ontology concept`

| link | count |
|---|---|
| raw sources | 1 |
| transformations | 1 |
| served datasets | 7 |
| ontology concepts | 0 |

⚠️ **6** dataset(s) with no transformation: `categories`, `customers`, `product_bundles`, `products`, `refunds`, `shipping_carriers`

## Lineage coverage

How many of each served view's columns descend from an upstream column. Computed columns (pivots, aggregates, literals) legitimately have no single parent, so <100% is normal — **0% is the alarm**: it means the transform's inputs are mis-declared and the lineage silently collapsed.

| dataset | covered | of | coverage | |
|---|---|---|---|---|
| `orders` | 4 | 8 | 50% | 🟢 |

**Overall — 4/8 columns (50%) trace to an upstream column.**

## Change protocol — autodiscovery vs manual

| | count |
|---|---|
| objects harvested (self-documenting) | 0 |
| objects authored / tuned (need a protocol entry) | 0 |
| objects with no provenance stamp | 9 |
| protocolled interventions | 0 |

⚠️ no `interventions/ledger.yaml` yet — manual changes are unrecorded.
