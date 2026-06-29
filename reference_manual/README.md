---
title: Modeling Meaning as Code — The Reference Manual
version: '0.1.0'
date: 2026-06-23
status: DRAFT SCAFFOLD — structure laid as a directory of chapters; ch.01 written, ch.03 + one pattern prototyped.
audience: data modellers, ontology architects, data/AI engineers, and evaluators comparing this to RDF/OWL,
  dimensional/BI semantic layers, and platform ontologies (Palantir-style).
scope: GENERIC — domain-neutral. All examples are from example_shop_ontology/ (a synthetic online shop).
  No real business domain, warehouse, or vendor appears here.
companions:
  - ../FRAMEWORK.md            # the canon — the why + the complete construct definitions
  - shape_reference.md         # the per-object-type Shape Reference (generated shapes + naming/ref contracts)
  - ../MODELLERS_COOKBOOK.md   # decision procedures + recipes for the closed primitives
  - ../example_shop_ontology/  # the worked example every entry points at
---

# Modeling Meaning as Code — The Reference Manual

> **The book this wants to be.** Kernighan & Ritchie did not just list C's keywords; they taught the
> *idioms* — "here is the shape of problem you will meet, here is how you say it in this language." No
> such book exists for **modeling meaning**. The relational world has Codd and the normal forms; the
> warehouse world has Kimball's dimensional catalogue; the semantic-web world has RDF/OWL. Each is a
> mature pattern language for *one* target. None is a pattern language for capturing meaning **once**,
> tool-neutrally, readable by a person, a machine, and an AI agent alike. This manual is the attempt.

This manual is a **directory of chapters** (one file each), plus a `patterns/` subdirectory holding **one
file per worked pattern** — the most MAC-native shape: each pattern is a lookup unit, like a concept.

## Chapters

| File | Chapter | Status |
| --- | --- | --- |
| [00_the_problem.md](00_the_problem.md) | **The problem, and the shape of the answer** — a concrete demonstration of what goes wrong today, and the **anatomy of a pattern**: the units this manual is built from (observation · constellation · latent fact · construct · response) and how every entry is a Question → Answer. Start here. | ✅ written |
| [01_why_meaning_as_code.md](01_why_meaning_as_code.md) | **Why model meaning as code** — the honest case against the four alternatives you use today, and the bet this framework makes instead. | ✅ written |
| [02_building_blocks.md](02_building_blocks.md) | **The building blocks (the formal core)** — the six classes as six mathematical structures, the concept-as-equation, edges-as-relations, rules-as-derivations, and the completeness argument over Q. References FRAMEWORK for prose; owns the math. | ✅ written |
| [data_plane.md](data_plane.md) | **The data plane** *(foundations — read after Ch.02)* — two-plane layout (data plane vs ontology plane), the seam, the two kinds of join, the manifest, Option A→B. Migrated in from `design/`; seeds a bigger **data handling & transformation** chapter. | ✅ written |
| [the_content_model.md](the_content_model.md) | **The content model** *(foundations — read after Ch.02)* — skeleton vs prose vs UDF; the one discriminator; the `realized_by:` seam; canonization (a strong model writes the prose's UDF canon); the determinism-coverage metric. | ✅ written |
| [03_pattern_reference.md](03_pattern_reference.md) | **The Pattern Reference** — the idioms. Why it can be complete, the entry template, and the enumeration work-list. Links to `patterns/`. | 🔧 prototyped |
| [04_discipline.md](04_discipline.md) | **The discipline** — two orthogonal axes: the correctness gradient (ref. FRAMEWORK §8) and the determinism gradient (canon vs prose); why correctness must come *before* canonization; the manual's self-review discipline. | ✅ written |
| [05_tutorial.md](05_tutorial.md) | **Tutorial: from blank canvas to a running model** — "hello, ontology" (one concept, run it), the author→gate→run→promote loop, growing to concept + edge + rule, and when to jump to a Ch.03 pattern. References the cookbook + example; doesn't restate them. | ✅ written |

## Shape reference

The **per-object-type structural reference** — what keys exist, where they nest, what's required, the
per-class conditionals, and the `x-` extension rule. The structural shapes are **generated from
[`mac.schema.json`](../mac.schema.json)** (always current — re-run `tools/gen_schema_shapes.py`), wrapped
by two hand-written contracts (naming · reference syntax). It is the readable face of the closed schema and
the concrete companion to [Ch.02](02_building_blocks.md) (which owns the six classes *as structures*; this
shows their YAML shape). Supersedes the retired `../CONCEPT_SPEC.md`.

| File | Reference | Status |
| --- | --- | --- |
| [shape_reference.md](shape_reference.md) | Shape Reference — `ConceptFile` · `RulesFile` · `EdgesFile` · `TableFile` · `TransformFile`, plus the naming contract + reference syntax | generated + prose |

## Patterns (worked entries)

| File | Pattern | Status |
| --- | --- | --- |
| [patterns/scd_type_2.md](patterns/scd_type_2.md) | Slowly-Changing Dimension, Type 2 | ✅ written |
| [patterns/semi_additive_balance.md](patterns/semi_additive_balance.md) | Semi-additive balance (a level read at a point in time) | ✅ written |
| [patterns/context_dependent_meaning.md](patterns/context_dependent_meaning.md) | Context-dependent meaning (a code meaningless without its parent) | ✅ written |
| [patterns/explicit_closure.md](patterns/explicit_closure.md) | Explicit closure (closed / open / unknown value set) | ✅ written |
| [patterns/tracking_vintage.md](patterns/tracking_vintage.md) | Tracking vintage (actual / plan / budget orthogonal axis) | ✅ written |
| [patterns/impurity_disposition.md](patterns/impurity_disposition.md) | Impurity disposition (bake / register / block) | 🟡 partial — edges canon-able, curation-layer deferred |
| [patterns/competing_definitions.md](patterns/competing_definitions.md) | Competing definitions (one term, several meanings → ask) | ✅ written |
| [patterns/recursive_hierarchy.md](patterns/recursive_hierarchy.md) | Recursive hierarchy (self-referencing parent key → subtree) | ✅ written |
| [patterns/absence_semantics.md](patterns/absence_semantics.md) | Absence semantics (missing row = zero / not-loaded / untracked) | ✅ written |
| [patterns/associative_entity.md](patterns/associative_entity.md) | Associative entity (junction with payload → promote to concept) | ✅ written |
| [patterns/polymorphic_association.md](patterns/polymorphic_association.md) | Polymorphic association (FK → one of several types) | 🟡 workaround + finding F1 |
| [patterns/supertype_subtype.md](patterns/supertype_subtype.md) | Supertype / subtype (is-a hierarchy) | ✅ written |
| [patterns/scd_type_3.md](patterns/scd_type_3.md) | SCD type 3 (prior value in a column) | ✅ written |
| [patterns/accumulating_snapshot.md](patterns/accumulating_snapshot.md) | Accumulating snapshot (one row, milestone dates) | ✅ written |
| [patterns/pre_aggregated_summary.md](patterns/pre_aggregated_summary.md) | Pre-aggregated summary (a rollup you must not re-aggregate) | ✅ written |
| [patterns/degenerate_dimension.md](patterns/degenerate_dimension.md) | Degenerate dimension (a grouping key in the fact) | ✅ written |
| [patterns/role_playing_dimension.md](patterns/role_playing_dimension.md) | Role-playing dimension (one dimension, several roles) | ✅ written |
| [patterns/multivalued_bridge.md](patterns/multivalued_bridge.md) | Multivalued bridge (a many-valued dimension) | ✅ written |
| [patterns/junk_dimension.md](patterns/junk_dimension.md) | Junk dimension (a grab-bag of flags = N enumerations) | ✅ written |
| [patterns/bitemporal.md](patterns/bitemporal.md) | Bitemporal (valid vs system time) | 🟡 workaround + finding F2 |
| [patterns/contaminated_code.md](patterns/contaminated_code.md) | Contaminated code (an overloaded opaque prefix) | ✅ written |
| [patterns/required_unspecified.md](patterns/required_unspecified.md) | Required-but-unspecified dimension (ask, don't default) | ✅ written |

*(The full novel-subset work-list — ~22 constellations — is enumerated in
[03_pattern_reference.md](03_pattern_reference.md); each becomes a file under `patterns/` as it is written.)*

## Canon library

The deterministic UDFs that a concept's `realized_by:` names (the content model's "canon"). Each is generic
and parameterized — logic single-homed, bound to a concept's columns via `{ udf, params }`. Patterns
discover which canons are needed; the library is where the determinism lives.

> **Enacted (schema v0.1.9).** The seam is no longer scaffold: `realized_by` is a typed slot in
> [`../mac.schema.json`](../mac.schema.json) (`$defs/canonBinding`) on every behaviour-bearing container; the
> canon names are a closed registry (`mac.canon.*`) in [`../mac_vocabulary.yaml`](../mac_vocabulary.yaml),
> resolved by `check_references` (an unknown name is an ERROR); the **logic is single-homed in the executable
> library [`../tools/canon/`](../tools/canon/)** and demonstrated runnable in
> [`../tests/test_canon.py`](../tests/test_canon.py) (6 pure canons run; the 4 sqlglot-backed ones skip when
> sqlglot is absent). The markdown entries below are now the **prose companions** to that module
> (contract · honest limits · demo) and should be kept in step with it. `example_shop_ontology`
> (`OrderStatus`) and `example_tpch_ontology` (`ReturnFlag`) each bind `closure_anomaly_check` — the same
> canon, different params — and pass all three gates.

| File | Canon | Serves | Status |
| --- | --- | --- | --- |
| [canon/composite_key_guard.md](canon/composite_key_guard.md) | `composite_key_guard` | context-dependent / parent-scoped codes | reference impl |
| [canon/additivity_guard.md](canon/additivity_guard.md) | `additivity_guard` | semi-additive balances / non-additive measures | reference impl |
| [canon/axis_default.md](canon/axis_default.md) | `axis_default` | default an unspecified orthogonal axis (e.g. scenario→ACTUAL) | reference impl |
| [canon/snapshot_collapse.md](canon/snapshot_collapse.md) | `snapshot_collapse` | SCD-2 / versioned relations (collapse to current / as-of) | reference impl |
| [canon/closure_anomaly_check.md](canon/closure_anomaly_check.md) | `closure_anomaly_check` | closed vs open value sets (anomaly check, or decline) | reference impl |
| [canon/exclusion_filter.md](canon/exclusion_filter.md) | `exclusion_filter` | exclude reliably-identifiable junk (the bake disposition) | reference impl |
| [canon/scoped_latest.md](canon/scoped_latest.md) | `scoped_latest` | "latest" anchored to a scoped subset (not the whole table) | reference impl |
| [canon/ambiguity_gate.md](canon/ambiguity_gate.md) | `ambiguity_gate` | detect competing definitions → resolve or ask | reference impl |
| [canon/hierarchy_rollup.md](canon/hierarchy_rollup.md) | `hierarchy_rollup` | recursive subtree expansion (node + all descendants) | reference impl |
| [canon/densify.md](canon/densify.md) | `densify` | sparse fact → full grid, absent cells COALESCE 0 (genuine-zero) | reference impl |
| [canon/array_membership_guard.md](canon/array_membership_guard.md) | `array_membership_guard` | multivalued attribute → membership, not `=` | reference impl |
| [canon/opaque_code_guard.md](canon/opaque_code_guard.md) | `opaque_code_guard` | reject prefix-match on a contaminated code; resolve via curated attr | reference impl |

## Findings — framework decisions, flagged not enacted

[FINDINGS.md](FINDINGS.md) — when a pattern isn't cleanly absorbed by the existing six structures + edge
model, the candidate framework change is recorded there **for the maintainer's decision**, never enacted on
my own. Currently: **F1** — a polymorphic edge (from `polymorphic_association`); **F2** — a bitemporal
dual-as-of collapse (from `bitemporal`).

## How this manual is written (its own framework)

[AUTHORING.md](AUTHORING.md) — the **authoring constitution**: the rules we agree and enforce on ourselves
(classify every slot · behaviour-bearing prose carries a UDF seam · single-home · mark the determinism
border · no completeness claims, publish coverage, challenge the reader · necessity needs a witness · the
manual is itself meaning-as-code). A reference manual for frameworks needs its own framework.

## Resolved: how this manual relates to the canon

*(Was an open decision; settled by how Ch.02/04 were written.)* Chapters 02 and 04 chose **(a) reference**:
they point at the canon (`FRAMEWORK.md`, `shape_reference.md`, `mac_vocabulary.yaml`) for the prose definitions
and own only the **new layer** — Ch.02 the formal core (structures + the equation + completeness), Ch.04 the
determinism axis. Nothing canonical is copied in; single-homing (A3) holds. If a future need for a fully
standalone "book" arises, option (b) — absorb the canon and make these the canonical home — remains open,
but it is not needed for v0.1.

---

*Scaffold authored 2026-06-23 on `docs/reference-manual`. Framework changes follow branch → PR per the
binding principle — not pushed without explicit go-ahead.*
