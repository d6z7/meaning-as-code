---
type: Doc
title: Plane health — chain, lineage & protocol
description: Chain integrity, lineage coverage and change-protocol metrics
tags:
- TPCH
- plane-health
---

The structural health of this source's data plane — the same numbers the gates check, surfaced here so they are visible without running a terminal command. **The gates remain authoritative**; this page is a read-view.

## Chain — `raw source → transformation → dataset → ontology concept`

| link | count |
|---|---|
| raw sources | 8 |
| transformations | 8 |
| served datasets | 8 |
| ontology concepts | 0 |

✅ every dataset is produced by a transformation.

## Lineage coverage

How many of each served view's columns descend from an upstream column. Computed columns (pivots, aggregates, literals) legitimately have no single parent, so <100% is normal — **0% is the alarm**: it means the transform's inputs are mis-declared and the lineage silently collapsed.

| dataset | covered | of | coverage | |
|---|---|---|---|---|
| `customer` | 7 | 7 | 100% | 🟢 |
| `lineitem` | 9 | 15 | 60% | 🟢 |
| `nation` | 4 | 4 | 100% | 🟢 |
| `orders` | 7 | 7 | 100% | 🟢 |
| `part` | 8 | 8 | 100% | 🟢 |
| `partsupp` | 5 | 5 | 100% | 🟢 |
| `region` | 3 | 3 | 100% | 🟢 |
| `supplier` | 6 | 6 | 100% | 🟢 |

**Overall — 49/55 columns (89%) trace to an upstream column.**

## Change protocol — autodiscovery vs manual

| | count |
|---|---|
| objects harvested (self-documenting) | 0 |
| objects authored / tuned (need a protocol entry) | 0 |
| objects with no provenance stamp | 24 |
| protocolled interventions | 0 |

⚠️ no `interventions/ledger.yaml` yet — manual changes are unrecorded.
