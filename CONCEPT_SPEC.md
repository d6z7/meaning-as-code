---
title: Concept & Rules Schema — key-by-key reference (RETIRED)
version: '0.1.6'
date: 2026-06-26
status: RETIRED — content single-homed elsewhere (see the redirect map below). This file is kept only
  so existing links resolve; it carries no content of its own.
---

# Concept & Rules Schema — RETIRED

This hand-maintained key-by-key reference has been **retired and split along its natural seam**: its
*reference* content moved into the generated [Shape Reference](reference_manual/shape_reference.md), and
its *conceptual / process* content was already owned by the framework canon, so it was dropped (not
duplicated). The authoritative, machine-checkable contract remains [`mac.schema.json`](mac.schema.json).

## Where each section went

| Was (`CONCEPT_SPEC §`) | Now |
| --- | --- |
| §1 What is a concept? · §2 1-file-1-concept · §3 the layers · §4 the `class:` vocabulary | [`FRAMEWORK.md`](FRAMEWORK.md) + [reference_manual/02_building_blocks.md](reference_manual/02_building_blocks.md) (the canonical definitions; the **per-class shape** is now generated in the Shape Reference) |
| **§5 the naming contract** · **§5a reference syntax** | [reference_manual/shape_reference.md](reference_manual/shape_reference.md) — the two hand-written contracts |
| **§6 predefined keys** · **§7 the rules layer** | [reference_manual/shape_reference.md](reference_manual/shape_reference.md) — the **generated** per-object-type shapes (`ConceptFile` … `TransformFile`), produced from the schema by `tools/gen_schema_shapes.py` |
| §8 orthogonal axes (footgun) | [reference_manual/patterns/tracking_vintage.md](reference_manual/patterns/tracking_vintage.md) |
| §9 validation | [`CONFORMANCE.md`](CONFORMANCE.md) |
| §10 what is deferred | [reference_manual/FINDINGS.md](reference_manual/FINDINGS.md) |

> **Looking for "what keys can I use, and where do they go?"** → [the Shape Reference](reference_manual/shape_reference.md).
