---
title: YAML Ontology Framework — Structure Map (visual companion)
version: '0.1.6'
date: 2026-06-05
status: VISUAL COMPANION to the canonical framework description (framework/FRAMEWORK.md). Read FRAMEWORK.md first for the narrative + complete definition; this provides the diagrams.
audience: ontology architects, platform/vendor integrators, AI-agent builders, new contributors
scope: GENERIC — domain-neutral. The visual/structural index over the framework. Contains NO reference
       to any specific business domain, warehouse, or vendor.
---

# YAML Ontology Framework — Structure Map

The *generic* framework, in diagrams: the object types the model defines, where they live, and what
each layer holds — independent of any data source or target platform. Read this alongside
`FRAMEWORK.md` (the narrative) and `CONCEPT_SPEC.md` (the key-by-key reference). For a concrete
instantiation, see the worked example `example_shop_ontology/`.

---

## A.1 The object types (what you create, and where)

The framework defines a small, fixed set of **authored object types**. Everything you author is one of
these. Each has exactly one home (a file location pattern) and belongs to exactly one layer.

| # | Object type | What it is | File (generic path) | Layer | Cardinality |
| - | --- | --- | --- | --- | --- |
| 1 | **Concept** | one named thing the business reasons about | `<source>/concepts/<group>/<concept>.yaml` | Concept | 1 file = 1 concept |
| 2 | **Rule** | a derivation / membership computation | entry in `<source>/rules.yaml` | Rules | many per file |
| 3 | **Edge** | a navigable relation between two concepts | entry in `<source>/edges.yaml` | Edges (intra-source) | many per file |
| 4 | **Federation edge** | a cross-source bridge / identity alias | entry in `federation/edges.yaml`, `federation/aliases.yaml` | Edges (cross-source) | many per file |
| 5 | **Table descriptor** | physical grounding target (columns/types/FKs) | `<source>/tables/<table>.yaml` | Physical | 1 file = 1 table |
| 6 | **Finding** | a data-vs-model discrepancy caught by execution | entry in `<source>/recon_findings.md` | (cross-cutting record) | append-only log |
| 7 | **Open question** | an SME-actionable unknown | `open_questions:` inside a concept (or a rule) | (lives on the object) | inline list |

Authored-but-not-instance artifacts (the framework *definition* itself, not a data source):
the **schema spec** (`CONCEPT_SPEC`), the **stencil/exemplar**, the **validator**. These define the
rules every object above must obey.

## A.2 The four layers (what each holds, and the no-overlap law)

> **Law:** every fact lives in exactly ONE layer. No layer restates another. This is what keeps each
> file small and each fact single-homed — and what makes the model projectable to a target platform.

```
                 a business question
                          │
                          ▼   (an AI agent OR a target platform reads the model)
   ┌───────────────────────────────────────────────────────────────────────┐
   │                         THE SEMANTIC MODEL                              │
   │                                                                         │
   │   CONCEPT layer            RULES layer             EDGES layer          │
   │   "what it MEANS"          "what is COMPUTED"      "how concepts        │
   │                                                     CONNECT"            │
   │   ┌─────────────┐          ┌──────────────┐        ┌────────────────┐   │
   │   │  Concept    │◀── over ─│   Rule       │        │ intra-source   │   │
   │   │  (1 of 6    │          │ (derivation /│        │   edges        │   │
   │   │   classes)  │          │  membership) │        │ ───────────    │   │
   │   │             │──refers─▶│              │        │ federation     │   │
   │   └──────┬──────┘ derives  └──────┬───────┘        │   edges/alias  │   │
   │          │ grounding:             │ validated_     └───────┬────────┘   │
   │          │                        │  against:              │ realized_  │
   │          ▼                        ▼                        ▼  by:       │
   │   ┌───────────────────────────────────────────────────────────────┐    │
   │   │                     PHYSICAL layer                             │    │
   │   │        Table descriptors: columns · types · foreign keys       │    │
   │   │        (the grounding TARGETS — the only layer that names       │    │
   │   │         physical columns/tables as data)                       │    │
   │   └───────────────────────────────┬───────────────────────────────┘    │
   └───────────────────────────────────┼─────────────────────────────────────┘
                                        ▼
                          the live warehouse / API / graph
                          (NOT authored — the ground truth the
                           Physical layer must be reconciled against)
```

| Layer | Holds | Does NOT hold | Points at |
| --- | --- | --- | --- |
| **Concept** | meaning, structure, interpretive facts (`semantics:`), enumerations, properties, lifecycle | computations, cross-concept relations, physical column data | the Physical layer (via `grounding:`) |
| **Rules** | derivations + scope/membership rules (the *computed* things) | stored measures (those need no rule), meaning, relations | Concepts (`over:`/`derives:`) + tables (`validated_against:`) |
| **Edges** | relations between concepts (3 levels: physical / business / federation) | the meaning of either endpoint, any computation | Concepts (endpoints) + the physical FK (`realized_by:`) |
| **Physical** | tables, columns, types, FKs — grounding targets | any meaning, rule, or relation | the warehouse (reconciled by execution) |

## A.3 What a CONCEPT is made of (the unit of meaning)

A concept is the framework's central object. Its `class:` (one of six) decides which *shape block*
appears. Everything interpretive collects in one `semantics:` block.

```
CONCEPT  (1 file = 1 concept)
│
├─ metadata:      name · source · version · schema_version · status · confidence
│
├─ concept:       ── IDENTITY + MEANING ──
│   ├─ name · label · german
│   ├─ class:  ───────▶  the SIX structural classes:
│   │                    ┌──────────────────────────────────────────────┐
│   │                    │ entity      a structured thing / abstract class│
│   │                    │ event       a stateful occurrence + lifecycle  │
│   │                    │ measure     a counted/aggregated quantity      │
│   │                    │ enumeration a controlled vocabulary of values  │
│   │                    │ reference   a dimension entity facts point at  │
│   │                    │ grouping    an aggregation above the leaf level │
│   │                    └──────────────────────────────────────────────┘
│   ├─ definition:
│   └─ semantics:   ── the SINGLE home for interpretive facts ──
│         purpose · scope · additivity{} · unit · null_semantics
│
├─ ⟨ ONE shape block, chosen by class: ⟩
│     enumeration → values: + value_set:{ closure · closure_why }
│     reference/entity → properties:
│     measure → subclasses: / individual measures (+ measure semantics)
│     event → lifecycle: { phase_sequence → phases → states }
│     (companions) → related_concepts:   (several coded cols) → enumerations:
│
├─ grounding:     kind · table(s) · schema · key_column · value_filter   ──▶ PHYSICAL layer
├─ constraints:   assert:  (data-quality validation; the word 'rule' is RESERVED for derivations)
├─ governance:    last_reviewed · change_log[]  (append-only)
└─ open_questions: id · question · status · owner_for_resolution  ──▶ SME backlog
```

## A.4 The two consumers (why the model is shaped this way)

The same authored model is read two ways — this is the design driver:

```
                       ┌──────────────────────────────┐
            ┌─────────▶│  AI agent                    │  reads concept + grounding,
            │          │  (reads YAML into context)   │  composes correct SQL/query
   THE      │          └──────────────────────────────┘
   MODEL ───┤
            │          ┌──────────────────────────────┐
            └─────────▶│  Target platform             │  ingests YAML, casts into its
                       │  (RDF store / property graph │  own primitives (classes,
                       │   / semantic layer / Palantir-│  relations, attributes, rules)
                       │   style ontology)            │
                       └──────────────────────────────┘
```

Consequence: the model is **declarative and vendor-neutral**. Meaning lives in `semantics:`,
computation in `rules:` (with a renderable form), relations in `edges:` — so a platform can map each
layer to its own constructs, and an agent can read each layer as context.

## A.5 The validation / trust gradient (how an object earns confidence)

```
 authored          structural            execution
 (draft)    ──▶    validation     ──▶    validation        ──▶   SME-confirmed
 confidence:Q      (validator:            (run against            (confidence:C,
                    0 errors)              live warehouse)         OQ resolved)
                          │                      │
                          │                      └─ produces FINDINGS (object type #6)
                          │                         when model ≠ data
                          └─ enforces: class present, semantics placement,
                             closure home, assert-not-rule, rule render_kind,
                             edge level/type, naming contract
```

The **naming contract** (cross-cutting law): ontology identifiers live ONLY in `name:`/`id:`;
physical names (columns/tables/codes) live ONLY as VALUES of `column:`/`table:`/`grounds_column:`/etc.
So a reader can always tell an ontology concept from a physical artifact by *where the string sits*.

---

*Companion documents: `FRAMEWORK.md` (the narrative description — read first), `CONCEPT_SPEC.md` (the
full key-by-key reference), and `example_shop_ontology/` (the canonical stencil — a worked, validated
instantiation on a neutral domain). This file is the visual/structural index over the framework. For how
a specific project instantiates the framework on disk, see that project's own documentation.*
