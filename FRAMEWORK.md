---
title: The YAML Ontology Framework — meaning and semantics as version-controlled YAML
version: '1.2'
date: 2026-06-05
status: CANONICAL — the complete, self-contained, domain-neutral description of the framework. Read this first.
audience: ontology architects, data/AI engineers, platform/vendor integrators, new contributors
scope: GENERIC methodology — domain-independent and vendor-neutral. Contains NO reference to any
  specific business domain, warehouse, or vendor. Any specific project is ONE application of
  this framework, not the framework itself.
supersedes: FRAMEWORK_v0.4_partial.md, ONTOLOGY_FRAMEWORK.md (both retired to archive/)
companions:
  - CONCEPT_SPEC.md     # the detailed, key-by-key reference (appendix to this document)
  - mac.schema.json     # v0.1.9: the machine-checkable schema — the strict, enforceable contract
  - CONFORMANCE.md      # v0.1.9: conformance levels + the closed-core / `x-` extension rule
  - FRAMEWORK_STRUCTURE_MAP.md  # the visual companion (diagrams)
  - example_shop_ontology/   # a worked, validated example on a neutral domain — "this framework, applied"
---

# The YAML Ontology Framework

> **In one sentence.** Write the *meaning* of your data down once — as plain-text, version-controlled
> YAML, organised into four layers — so that the same artifact can be read by an AI agent (to answer
> questions correctly) and ingested by any target platform (to become that platform's ontology),
> without locking your meaning into a vendor.

This document is the complete description of the framework: what problem it solves, the principles it is
built on, every construct it defines, and — honestly — what it is *not* and when not to use it. A
stakeholder can read §1–§4 and understand the idea; an engineer can read §5–§8 and author a concept
without opening another file; §9 answers the obvious objections. The worked example
(`example_shop_ontology/`) shows the whole framework applied to a small, neutral domain.

---

## 1. The problem

In any organisation of scale, the *meaning* of data is scattered. It lives in:

- people's heads ("everyone knows the order book excludes cancelled orders"),
- BI-tool configurations and report definitions that only that tool can read,
- transformation code (the real business rules are buried in SQL `CASE` statements),
- tribal knowledge that walks out the door when someone leaves.

Two modern pressures make this expensive:

1. **AI agents now query data directly.** Ask an LLM "what was revenue in Q3?" and it will write a
   query — but it does not know that revenue is net of refunds, that one table double-counts across a
   reporting dimension, or that a "stock" measure must never be summed across time. It guesses, and it
   guesses *plausibly and wrongly*, with no signal that it was wrong.
2. **Platform adoption locks meaning in.** Encode your semantics inside vendor X's ontology product and
   you have (a) paid for it, (b) coupled your meaning to its primitives, and (c) made the next
   migration a rewrite. The meaning should outlive the tool.

The missing thing is a **single, authoritative, tool-neutral place where meaning lives** — readable by
humans, by machines, and portable across whatever platform you eventually choose.

## 2. The thesis

Capture meaning as **plain-text YAML, version-controlled in Git**, structured by a small fixed schema.

This one artifact has **two consumers**:

```
                         ┌────────────────────────────┐
              ┌─────────▶│  AI agent                  │  reads the YAML into context,
              │          │  (LLM in a reasoning loop) │  composes a correct query
   THE YAML ──┤          └────────────────────────────┘
   ONTOLOGY   │
              │          ┌────────────────────────────┐
              └─────────▶│  Target platform           │  ingests the YAML, casts it into
                         │  (RDF store / property      │  its own primitives (classes,
                         │   graph / semantic layer /  │  relations, attributes, rules)
                         │   Palantir-style ontology)  │
                         └────────────────────────────┘
```

Because the artifact is **declarative** (it states what things mean, not how a particular engine
executes them), each consumer can map it to its own world. The agent reads `semantics:` as context; a
graph database maps a concept to a node type and an edge to an edge type; a semantic layer maps a
measure to a metric. **Write once; project anywhere.** That is the vendor-neutrality the framework
exists to deliver.

YAML specifically — not a database, not OWL, not a proprietary format — because it is simultaneously:
human-readable and diff-able (a person reviews a change in a pull request), machine-parseable (every
tool reads YAML), and **LLM-native** (models read and write it fluently, which matters when an agent is
one of the two consumers). §9 addresses why not RDF/OWL or a platform.

## 3. Design principles

The framework is the disciplined application of seven principles. Everything in §4–§8 follows from these.

1. **Separation of concerns — four layers.** Meaning, computation, relations, and physical grounding are
   different kinds of fact and live in different layers (§4). You can change a formula without touching a
   definition; you can re-point grounding at a new table without re-stating meaning.
2. **Single-homing.** Every fact lives in exactly one place. No layer restates another; no concept
   restates another. This is what makes the model legible, diff-able, and projectable — and it is only
   *checkable* because the boundaries are explicit.
3. **A closed structural vocabulary.** Every concept is exactly one of **six classes** (§5). A small,
   fixed vocabulary (rather than an open zoo of ad-hoc "types") is what lets a reader — or a projector —
   key off one word and know the shape of the thing.
4. **The naming contract.** Ontology identifiers live *only* in `name:`/`id:` fields; physical names
   (columns, tables, codes) live *only* as values of designated fields (`column:`, `table:`,
   `grounds_column:`…). So a reader can always tell "is this string a concept or a physical artifact?"
   by *where it sits*. (This fixes a real defect: physical column names doubling as YAML keys.)
5. **Declarative, not procedural.** The model states facts and rules; it does not embed an execution
   engine. Computation is described (with a renderable form) but run by the consumer.
6. **Human *and* machine readable, equally.** Readability for a person is a first-class requirement, not
   a nicety — because humans author and review the meaning, and because an LLM reads the same text.
7. **Execution-validated.** A structurally valid model can still be *wrong about the data*. The
   framework treats running model-generated queries against the real warehouse as part of authoring:
   discrepancies become recorded findings that correct the model. Structure ≠ correctness.

## 4. The four layers

> **The no-overlap law:** every fact lives in exactly one layer; no layer restates another.

```
   CONCEPT layer            RULES layer            EDGES layer
   "what it MEANS"          "what is COMPUTED"     "how concepts CONNECT"
   ┌─────────────┐          ┌──────────────┐       ┌────────────────┐
   │  Concept    │◀── over ─│   Rule       │       │ physical /     │
   │ (1 of 6     │          │ (derivation /│       │ business /     │
   │  classes)   │──refers─▶│  membership) │       │ federation     │
   └──────┬──────┘ derives  └──────┬───────┘       │   edges        │
          │ grounding:             │ validated_     └───────┬────────┘
          ▼                        ▼  against:              ▼ realized_by:
   ┌──────────────────────────────────────────────────────────────────┐
   │                      PHYSICAL layer                                │
   │     table descriptors: columns · types · foreign keys              │
   │     (the only layer that names physical columns/tables as data)    │
   └────────────────────────────────┬───────────────────────────────────┘
                                     ▼
                       the live warehouse / API / graph
                       (ground truth — the Physical layer is reconciled against it)
```

| Layer | Holds | Does NOT hold | Points at |
| --- | --- | --- | --- |
| **Concept** | meaning, structure, interpretive facts (`semantics:`), values, properties, lifecycle | computations, cross-concept relations, physical column data | the Physical layer, via `grounding:` |
| **Rules** | derivations + scope/membership rules (the *computed* things) | stored values (no rule needed), meaning, relations | Concepts (`over:`/`derives:`) + tables (`validated_against:`) |
| **Edges** | relations between concepts, at three levels | the meaning of either endpoint, any computation | Concepts (endpoints) + the physical FK (`realized_by:`) |
| **Physical** | tables, columns, types, foreign keys — the grounding targets | any meaning, rule, or relation | the data backing (reconciled by execution) |

A concept file lives at `<source>/concepts/<group>/<concept>.yaml`; rules at `<source>/rules.yaml`;
edges at `<source>/edges.yaml` (plus a cross-source `federation/edges.yaml`); tables at
`<source>/tables/<table>.yaml`. (`<source>` is one application's data source; a single-source project
has one, a federated project has several.)

## 5. The concept — the unit of meaning

A **concept** is one named thing the business reasons about: a measure, a classification, an entity, a
reference dimension, an event, a grouping. It answers *what is this, what does it mean, where does its
data live, and what must a reasoner know to use it correctly?* One concept per file — small enough for
one person to own, isolate a change to, and reference by a stable path.

### The six classes

Every concept declares exactly one `class:` — the structural shape of the thing. The vocabulary is
**closed**: six values, no more.

| `class:` | Meaning | When to use it |
| --- | --- | --- |
| **entity** | a structured thing with identity / an abstract class with instances | a thing that *is*, that other things reference, and that isn't better described as one of the below |
| **event** | a stateful occurrence, or the lifecycle it moves through | something that *happens* and has states/phases over time |
| **measure** | a counted/aggregated quantity (has additivity, a unit, maybe a derivation) | a number you sum/average; the thing analytics reports |
| **enumeration** | a controlled vocabulary of allowed coded values | a fixed (or open) set of categories/codes |
| **reference** | a dimension entity identified by a key, that facts point at | a lookup/dimension — country, product, calendar period |
| **grouping** | a categorical/geographic aggregation above the leaf level | a roll-up (region over country, category over product) |

This six-way split is deliberately narrower than, say, RDF's open class system: it is the set that
remained after measure, enumeration, reference, and grouping were *factored out* of the generic
"entity" bucket. The payoff is that one word tells you the shape — and tells a target platform how to
project it.

### Anatomy of a concept

```
metadata:        name · source · version · schema_version · status · confidence

concept:         ── identity + meaning ──
  name · label · class · definition
  semantics:     ── the SINGLE home for interpretive facts ──
      purpose · scope · additivity{} · unit · null_semantics

⟨ one shape block, chosen by class: ⟩
  values: + value_set:{closure}     (enumeration)
  properties:                        (reference / entity)
  subclasses:                        (measure hierarchy)
  lifecycle: phases → states → seq   (event)
  related_concepts:                  (companions in the same file)

grounding:       where the data lives (table, schema, key, value_filter) → Physical layer
constraints:     assert:  (data-quality checks; the word 'rule' is RESERVED for derivations)
governance:      last_reviewed · change_log[]   (append-only)
open_questions:  the SME-actionable unknowns
```

Two homes for "how to reason with this," each local to what it describes:

- **`concept.semantics:`** — concept-level interpretive facts. `purpose` (why it exists), `scope`
  (where it applies / does *not*), `additivity` (per-dimension — the footgun-preventer: a stock measure
  is *non-additive over time*), `unit`, `null_semantics` (what an absent value means).
- **`value_set:` / `values:`** — for enumerations, `closure` (open/closed/unknown) lives *with* the
  value set it constrains, not in `semantics`.

### The event class and the lifecycle block

An `event` concept can carry a **lifecycle**: the state machine the thing moves through. The canonical
shape is **macro-phases that group states, in an ordered sequence** — `phase_sequence:` → `phases:`
(each grouping its `states:`). The worked example's `Order` shows it: `CHECKOUT` (PLACED, PAID) →
`FULFILMENT` (SHIPPED, DELIVERED) → `CLOSED` (RETURNED, CANCELLED). The phases-grouping-states shape
(rather than flat states-and-transitions) was earned by applying it to real lifecycles long enough that
the states needed grouping into ordered macro-phases to stay legible. The framework *records* the
machine; it does not execute it.

## 6. The rules layer — computation

Some facts *describe* a concept (interpretive — they live on the concept). Others *operate over*
concepts to *produce* something (a derived measure, a membership set). Those are **rules**, and they
live in their own layer.

**The cut-line test:** *does it produce/derive something (→ rule), or describe how to use what's already
there (→ interpretive)?* A closure describes a value set → interpretive. A net-revenue formula
(gross − refunds) computes → rule. A "which regions count as the EU domestic market" membership set →
rule (membership).

Each rule carries plain-language `logic:` (always) and a `render_kind:` that decides how it becomes
executable: `sql_expression` / `derived_set` (canonical SQL injected at query time), `sql_view`
(pre-deposited view, referenced), or `spec_only` (the agent generates from the logic). Stored values
that are simply filtered/aggregated need **no** rule — only *computed* things appear here.

**The security rule (hard):** a rule's SQL template uses Jinja to shape *structure* (which clauses, which
fragments compose); values that originate from a user's question are **bound as SQL parameters**, never
string-interpolated. Templating structure is fine; interpolating user-derived literals is SQL injection.

## 7. The edges layer — relations

A relation *between two concepts* is an edge, not a property of either. Edges come at three levels:

- **physical** — a real foreign-key join between tables (carries the join rule / `realized_by:` FK).
- **business** — an identity relation at the concept level (references the physical edge via
  `realized_by:`; never restates the join).
- **federation** — a *cross-source* bridge or identity alias (e.g. "this source's customer code denotes
  the same real-world customer as that source's account id"), living in `federation/edges.yaml` /
  `aliases.yaml`. Federation edges *refer*; they never carry a raw join.

Containment (whole→part membership) and is-a hierarchy are *concept structure*, not edges — they live on
the concept. Keeping relations out of concepts is what keeps each concept file about one thing.

## 8. The trust gradient — how a fact earns confidence

```
 authored          structural             execution               domain-expert
 (draft,    ──▶    validation     ──▶     validation       ──▶    confirmed
  conf: low)       (validator:             (run against            (conf: high,
                    0 errors)               the live data)          open question resolved)
                         │                       │
                         │                       └─ produces FINDINGS when model ≠ data
                         └─ enforces: class present, semantics placement, closure home,
                            assert-not-rule, rule render_kind, edge level/type, naming contract
```

A validator (`tools/validate_schema.py`) enforces the structural rules. But structure is not
correctness: the framework's distinctive discipline is **execution validation** — you run the query the
model implies and let the data correct you. When the model says "X" and the data says "Y," that becomes a
recorded **finding**, and the model is fixed. In practice this loop catches modelling errors that careful
paper review passes — including ones that invert the logic — which is why a fact is only trustworthy at
the right-hand end of this gradient.

## 9. Trade-offs — what it is NOT, and when not to use it

Honesty here is what makes the rest credible.

**What the framework is NOT:**

- **Not a runtime or query engine.** It describes; it does not execute. You still need a warehouse,
  graph, or semantic layer to run anything. The YAML is the *map*, not the territory.
- **Not a reasoner.** There is no built-in inference (no OWL-style entailment). Reasoning is supplied by
  a consumer — an LLM agent, or the target platform. The model gives the agent enough *declarative*
  context to reason well; it does not reason for it.
- **Discipline-dependent.** The legibility and projectability depend on the contracts (single-homing,
  naming, the closed vocabulary) actually being followed. Without the validator enforcing them, a
  YAML ontology drifts into the same mess it replaced. The discipline is the product.
- **Validated only as far as it has been executed.** A green validator means *well-formed*, not
  *correct*. Untested grounding can be wrong (a column that doesn't exist, a label that means something
  else). The trust gradient (§8) is not optional.
- **Not a W3C standard.** It is a pragmatic convention, not RDF/OWL/SHACL. See below for why.

**Why not RDF/OWL (the standard)?** RDF/OWL is more expressive and standardised — but it is heavy to
author and read, its tooling assumes a triple store, and its inference power is mostly unused by the
query-shaping job an LLM agent actually does. We chose plain YAML for authorability, diff-ability, and
LLM-nativeness, and kept a *projection* path to RDF for when a triple store is the target. Portability,
not lock-in to a standard's tooling.

**Why not just buy an ontology platform?** A platform gives you a runtime and a UI, but it couples your
meaning to its primitives and its licence. The framework lets you capture meaning *now*, vendor-neutral,
and project it into whatever platform is chosen later — so the platform decision doesn't gate, or get
locked in by, the semantics work.

**When NOT to use it:** if a single team owns a single tool and will never migrate, the tool's native
semantic layer may be enough. The framework earns its keep when meaning must outlive a tool, be shared
across sources/teams, and serve both humans and AI agents.

## 10. Core vs pluggable — what is universal, what each project chooses

The framework is a small **core** (universal) plus **pluggable concerns** (per project / ecosystem). A
construct belongs in the core only if it (a) an agent reads directly **and** (b) projects cleanly onto
RDF/OWL *and* property-graph *and* relational + semantic-layer (§11). Everything ecosystem-specific is a
plug — declared once in a small project `profile`, leaving the core untouched.

**Core (universal):** the six classes; the four layers; `semantics:` (purpose / scope / additivity /
unit / null_semantics); enumeration + `closure:`; the rules layer with `render_kind:`; edges at three
levels with per-endpoint cardinality; abstract `grounding:` (that grounding exists, and which attributes
map); the naming contract; a `confidence:`/provenance slot.

**Pluggable (NOT in the core):**

| Concern | Core slot it plugs into | Examples a project might choose |
| --- | --- | --- |
| Confidence scale | `confidence:` | Confirmed/Inferred/Needs-expert · a 1–5 score · RAG green/amber/red · none |
| Grounding adapter | `grounding.kind:` | SQL table + column · REST endpoint · GraphQL · parquet path · graph node-label |
| Query dialect | constraints / join expressions | ANSI SQL · a vendor SQL dialect · SPARQL · Cypher · KQL |
| Onboarding workflow | `open_questions:`, findings refs | reverse-engineer + expert validation · forward-design · import from a catalog |
| Federation arity | federation layer | none (single-source) · 1 · N named sources |

That core/pluggable split is what lets the *same* framework serve a single-source SQL warehouse and a
multi-source graph estate without changing the definition — only the profile differs.

## 11. Projections — one artifact, every target

A construct is in the core **only if it projects onto all three target families.** This table is both
the contract a platform integrator implements and the proof that the framework is interchange-grade, not
agent-only. An **agent** ignores these columns (it reads the constructs directly); a **platform
integrator** reads one column and knows how to cast the whole ontology.

> **This is now running code, not just a contract.** The conceptual mapping below is realized by **six
> self-validating projectors** (`tools/mac_to_*.py`) — **OSI** (semantic interchange) · **RDF/OWL** ·
> **SHACL** (validating the RDF) · **openCypher** (property graph) · **OKF** (agent-knowledge bundle) ·
> **Mermaid** (diagram). Each output is checked **in its target's own terms** (OSI's JSON Schema, a real
> SHACL engine, an RDF re-parse, …) — no projection asks you to trust the projector. See
> [articles/projecting-outward.md](articles/projecting-outward.md). The projectors resolve a project's
> layout (flat, or the **two-plane** data/ontology split — [reference_manual/data_plane.md](reference_manual/data_plane.md))
> automatically.

| Framework construct | RDF / OWL | Property graph | Relational + semantic layer |
| --- | --- | --- | --- |
| `class: entity` / `reference` | `owl:Class` | node label | dimension / entity table |
| `class: measure` | class + datatype property | node + numeric property | measure in a cube |
| `subclasses:` (is-a) | `rdfs:subClassOf` | label hierarchy / `:IS_A` edge | rollup hierarchy |
| `properties:` (primitive) | `owl:DatatypeProperty` | node property | column |
| `attributes:` (value_domain) | property, range = enum class | property + value-set constraint | FK to dimension |
| `enumeration` + `closure: closed` | `owl:oneOf` | enumerated value set | complete reference table |
| `enumeration` + `closure: open` | class, no `oneOf` | open value set | extensible reference table |
| edge `level: physical` | (the join itself) | relationship type | JOIN / FK |
| edge `level: business` (identity) | shared IRI / `owl:sameAs`-ish | `:SAME_AS` edge | conformed key |
| edge `level: federation` | mapping axiom / `skos:exactMatch` | cross-graph link | cross-source bridge view |
| containment (`members:`) | part-of property (`dcterms:hasPart`) | `:CONTAINS` edges | parent-child dimension |
| `lifecycle:` (phases/states) | states as `skos:Concept`s + transition props | state node + `:TRANSITIONS_TO` edges | status dimension + state-transition fact |
| `derivation:` (rule) | annotation, or rule if an engine is present | computed property | calculated measure / SQL expression |
| cardinality min..max | `owl:minQualifiedCardinality` etc. | schema constraint | FK multiplicity |
| `grounding:` | R2RML / ontop mapping | data-import mapping | the physical binding itself |
| `purpose` / `scope` / `closure` / `additivity` | annotation properties | node/edge properties | metadata / measure config |
| `confidence:` (provenance) | annotation property | property | metadata column |

Where a target lacks a construct (e.g. a plain property graph has no formal `closure`), the projection
degrades to an annotation or convention — the *information is never lost*, only its enforcement.

## 12. How it is consumed (concretely)

- **AI-agent path.** The agent retrieves the relevant concept(s) + grounding + applicable rules into
  context, resolves the user's intent to parameters and which rules apply, and composes a query —
  Jinja assembles the structure, bound parameters carry the values. The LLM is not in the per-query hot
  path for canonical rules; it authored the template once.
- **Platform-projection path.** A loader reads the YAML and casts each layer into the target's
  primitives, per the table in §11. The same source, a different target, no re-authoring.

## 13. Where to go next

- **The complete key reference** — every predefined key, exhaustively — is `CONCEPT_SPEC.md`
  (the appendix to this document).
- **The visual companion** — directory layout, layer diagrams, the concept anatomy — is
  `FRAMEWORK_STRUCTURE_MAP.md`.
- **The worked example** — this entire framework applied to a small, neutral, synthetic domain
  (an online shop) — is `example_shop_ontology/`. Read it to see, rather than read about, every
  construct above.

---

*This is the canonical, domain-neutral framework description. Two prior drafts are superseded and
retired to `archive/`, their content absorbed here: `FRAMEWORK_v0.4_partial.md` (the prior provisional
definition) and `ONTOLOGY_FRAMEWORK.md` (the earlier domain-neutral draft — its core/pluggable split
and projection table are now §10–§11 above, upgraded to the current model).*
