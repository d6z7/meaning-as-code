---
title: "The data plane — two-plane layout, data handling & transformation"
part_of: reference_manual
status: written   # the two-plane layout (migrated from design/); data-handling & transformation depth to expand here
position: Foundations — read after Ch.02 (the building blocks); the data side of the four layers.
scope: GENERIC — domain-neutral. Uses the shop example; no business domain.
---

# The data plane — two-plane layout, data handling & transformation

*Ch.02 defined the building blocks of **meaning**. But a model does two jobs, and the other one comes first:
**making** the data (clean, conform, transform it) before **meaning** it. This chapter is the data side —
how a project separates the two, and the seam between them. It is the foundation of the broader
data-handling and transformation material that will grow here.*

> **This chapter is now the home of the two-plane layout** (migrated from the former `design/two-plane-layout.md`).
> Everything that pointed at that file now points here. *Planned expansion (a bigger chapter):* sources →
> transforms → datasets in depth — descriptor shapes, the transform construct, lineage-completeness, and
> data-quality registers. The ratified architecture below is the spine; the handling/transformation detail
> is the growth.

## Why two planes

A MAC project does two jobs that otherwise live tangled in one directory:

1. **Make the data** — start from raw source tables, transform them (SQL / views / Spark) into clean,
   consistent, query-ready relations. *How the data is made.*
2. **Mean the data** — define concepts, edges, rules over those clean relations. *What the data means.*

This is exactly Palantir Foundry's split (datasets + transforms vs. the Ontology), and the order is the
natural one: **you clean and conform the data first; only once it is consistent do you put semantics on
top.** When `concepts/` sits beside `views/*.sql` with `tables/` in between, the two stages — and two
*kinds of join* (below) — share a namespace with no boundary. The two-plane layout separates them into two
**planes** with a single, one-directional **seam**.

## The two planes and the seam

```
<project>/
  data/                 # STAGE 1 — the data plane: HOW the data is made
    sources/            #   descriptors of the raw input tables
    transforms/         #   the SQL/views: source → target (all INTERNAL joins live here)
    datasets/           #   descriptors (MAC TableFiles) of the OUTPUT relations  ← THE SEAM
    quality/            #   cleansing/grounding exceptions, DQ register, recon findings
  ontology/             # STAGE 2 — the semantic plane: WHAT it means
    concepts/  edges.yaml  rules.yaml  shapes.yaml
  mac.project.yaml      # declares the planes (see below)
```

**Seam rule (one-directional):** the ontology plane may reference **`data/datasets/`** (the published
output schemas) and *nothing else* of the data plane — never `transforms/`, never `sources/`. Dependencies
flow ontology → datasets, never back. This is the Foundry contract: an ontology object is *backed by* a
dataset; it never reaches into the pipeline that built it.

### The two kinds of join — why the seam is the right cut

A join is either:

- a **pipeline join** (raw EAV → flat dim): performed *inside* a transform, **encapsulated**, invisible to
  the ontology — the consumer never re-does it. Lives in `data/transforms/`.
- an **ontology edge** (fact → dim): a join the **consumer must still perform at query time**. Lives in
  `ontology/edges.yaml`.

> **Rule:** every join the consumer must perform is an ontology edge; every join the pipeline already
> performed is encapsulated, not an edge.

The plane boundary *is* this rule made structural. And the safety property follows: a needed query-time
join with **no edge** makes the ontology correctly *refuse* (it never fabricates a join) — it is never
blind, only either (a) reusing an upstream-completed join or (b) honestly refusing.

## The manifest

A single `mac.project.yaml` at the project root declares the planes and where descriptors live:

```yaml
# mac.project.yaml
planes:
  data: data
  ontology: ontology
descriptors: data/datasets     # where MAC TableFiles (the seam) live
```

**Back-compatible default:** with *no* manifest, the project is **flat** — ontology root = the project
dir, descriptors = `tables/`. Every existing single-root example keeps working untouched; the two-plane
layout is opt-in per project.

## How the tools resolve it

The model never tied a descriptor to a directory — a concept's `grounding` references a relation by
**name**, not a path; the *tools* resolve that name to a descriptor file. So the only thing the tools learn
is **two roots**, via one shared resolver (`tools/mac_project.py`):

- `ontology_root` — where `concepts/`, `edges.yaml`, `rules.yaml` live (flat: project root; two-plane:
  `<root>/ontology`).
- `descriptor_dir` — where TableFiles live (flat: `<root>/tables`; two-plane: `<root>/data/datasets`).

Every gate and projector asks the resolver instead of hardcoding `concepts/` / `tables/`.

## The descriptor: structure vs. meaning (Option A → Option B)

A TableFile can single-home **both** a column's *structure* (name, type, key, role) **and** its *meaning*
(prose: "iso2 is the identity"). The two planes want these on opposite sides. We get there in two steps:

- **Option A (relocate) — transitional.** Move the descriptor as-is into `data/datasets/`. Pure path change;
  zero semantic risk; gates stay green. Proves the planes, the seam, and the manifest. *Not* the end-state:
  the data plane still physically contains ontology knowledge (column prose).
- **Option B (clean split) — RATIFIED end-state.** Column **structure** stays in `data/datasets/`; column
  **meaning** moves **up** into the ontology, carried by the field-anchored typed `contract.rules[].binds`.
  The data plane becomes pure "what the pipeline emits"; the ontology owns *all* meaning. Only B makes
  "clean data first, semantics on top" literally true — no semantics left in the data plane.

**B has one consequence beyond moving text: meaning gets a single home that *everything* reads.** The
projectors must then source field meaning from the ontology's `contract.rules[].binds`, not the descriptor.
After B, gates *and* projectors both read meaning from the one place it lives. The projector update is part
of B.

## Conformance impact

- New optional artifact: `mac.project.yaml` (absent ⇒ flat, today's behaviour).
- New recognized descriptor location `data/datasets/` (in addition to `tables/`).
- **The data plane is fully typed.** `data/transforms/` validate against the `TransformFile` def, and
  `data/sources/` validate as raw-input `TableFile`s (`metadata.kind: raw_source`) — first-class,
  structurally gated data-plane files. The realizing SQL (`*.sql`) stays an artifact. A data-bound project
  may claim the **lineage-complete** profile.
- No change to any *ontology-plane* file's content schema; concepts still bind to `data/datasets/` only.

## Sequence

1. Framework: add the manifest + resolver; teach the gates and projectors to use it; prove on the shop
   example (shop two-plane, tpch back-compat proof).
2. Apply Option A to an applied project (relocate into `data/` + `ontology/`).
3. Option B: migrate column meaning into ontology field-anchoring.
