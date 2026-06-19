# Design: the two-plane project layout (data plane · ontology plane)

status: design — ratified; implemented on the v0.1.6 contract (opt-in per project via mac.project.yaml)
scope: GENERIC — domain-neutral. Uses the shop example; no business domain.

## Why

A MAC project does two jobs that today live tangled in one directory:

1. **Make the data** — start from raw source tables, transform them (SQL/views/Spark) into clean,
   consistent, query-ready relations. *How the data is made.*
2. **Mean the data** — define concepts, edges, rules over those clean relations. *What the data means.*

This is exactly Palantir Foundry's split (datasets + transforms vs. the Ontology), and the order is the
natural one: **you clean and conform the data first; only once it is consistent do you put semantics on
top.** Today `concepts/` sits beside `views/*.sql` with `tables/` in between, so the two stages — and two
*kinds of join* (see below) — share a namespace with no boundary. This design separates them into two
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
dir, descriptors = `tables/`, exactly as today. So every existing single-root example keeps working
untouched; the two-plane layout is opt-in per project.

## How the tools resolve it

The model never tied a descriptor to a directory — a concept's `grounding` references a relation by
**name** (`…v_fpl_kpi_current`), not a path; the *tools* resolve that name to a descriptor file. So the
only thing the tools learn is **two roots**, via one shared resolver (`tools/mac_project.py`):

- `ontology_root` — where `concepts/`, `edges.yaml`, `rules.yaml` live (flat: project root; two-plane:
  `<root>/ontology`).
- `descriptor_dir` — where TableFiles live (flat: `<root>/tables`; two-plane: `<root>/data/datasets`).

Every gate and projector asks the resolver instead of hardcoding `concepts/` / `tables/`. The referential
checker additionally treats the plane dirs as transparent for its single-source derivation (a two-plane
project is one source, so `ontology/concepts/…` and `data/datasets/…` share source `''`).

## The descriptor: structure vs. meaning (Option A → Option B)

Today a TableFile single-homes **both** a column's *structure* (name, type, key, role) **and** its
*meaning* (prose: "iso2 is the identity"; "this label is a perspective, not the identity"). The two planes
want these on opposite sides. We get there in two steps:

- **Option A (relocate) — transitional.** Move the descriptor as-is into `data/datasets/`. Pure path
  change; zero semantic risk; gates stay green. Proves the planes, the seam, and the manifest. It is *not*
  the end-state: the data plane still physically contains ontology knowledge (column prose), so the planes
  are split by directory but still entangled by content.
- **Option B (clean split) — RATIFIED end-state.** Column **structure** (name, type, key, role) stays in
  `data/datasets/`; column **meaning** moves **up** into the ontology, carried by the field-anchored typed
  `contract.rules[].binds` the framework already has. The data plane becomes pure "what the pipeline
  emits"; the ontology owns *all* meaning. Only B makes "clean data first, semantics on top" literally true
  — there is no semantics left in the data plane.

Option B intentionally **re-splits** what v0.5 fused (it had single-homed structure+meaning in the Physical
layer) — but in the right direction, and as a continuation of the field-anchoring work, not against it.
Because that field-meaning is load-bearing (it is what lets an agent generate correct SQL without
probing), B is a deliberate, gate-green migration — never a duplication.

**B has one consequence beyond moving text: meaning gets a single home that *everything* reads.** Today the
projectors source field meaning from the descriptor (OKF's `# Schema` notes, RDF's `rdfs:comment`). Under B
the descriptor is structure-only, so the projectors must read field meaning from the ontology's
`contract.rules[].binds` instead. This is the point, not a cost: after B, gates *and* projectors both read
meaning from the one place it lives. The projector update is part of B.

## Conformance impact

- New optional artifact: `mac.project.yaml` (absent ⇒ flat, today's behaviour).
- New recognized descriptor location `data/datasets/` (in addition to `tables/`).
- **v0.1.7 — the data plane is now fully typed.** `data/transforms/` (declared via the manifest
  `transforms:` key) validate against the new `TransformFile` def, and `data/sources/` (`sources:` key)
  validate as raw-input `TableFile`s (`metadata.kind: raw_source`). They are no longer un-scanned
  pipeline artifacts — they are first-class, structurally gated data-plane files. The realizing SQL
  (`*.sql`) stays an artifact, not a MAC file. A data-bound project may additionally claim the
  **lineage-complete** profile (CONFORMANCE.md §1).
- No change to any *ontology-plane* file's content schema; concepts still bind to `data/datasets/` only.

## Sequence

1. Framework: add the manifest + resolver; teach the gates and projectors to use it; **prove on the shop
   example** (shop two-plane, tpch stays flat ⇒ back-compat proof).
2. Apply Option A to an applied project (relocate into `data/` + `ontology/`).
3. Option B: migrate column meaning into ontology field-anchoring.
