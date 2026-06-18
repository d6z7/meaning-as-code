---
title: "Where does your meaning live — and who hosts it?"
date: 2026-06-17
status: article — positioning companion to meaning-as-code.md
scope: GENERIC — domain-neutral. Names technology categories/products as landscape, no business domain.
---

# Where does your meaning live — and who hosts it?

Every team answering questions over a warehouse has, somewhere, a model of what the data *means*. The
only questions are **how much of that model is written down** and **who owns the place it lives.** That is
the lens for "why Meaning-as-Code instead of X" — and the honest answer is: *MAC composes a slice the
existing options leave empty, and interoperates with the rest rather than replacing them.*

## Four levels of meaning

Meaning isn't one thing; it stacks. A useful cut — and the one the tooling landscape implicitly sorts
itself by:

| Level | The question it answers | The MAC layer that holds it |
|---|---|---|
| **Meaning** | what does this *denote*? | `concept:` definition (+ class, semantics) |
| **Ontology** | what *relates* to what? | **Edges** (joins as data) |
| **Semantic** | how do I *compute* it? | **Rules** (derivations, bound to fields) |
| **Physical** | where does the data *live*? | **Physical / Tables** (grounding, single-homed) |

MAC's four layers *are* these four levels — which is the whole point of the comparison below.

## The landscape sorts into two failure modes

**Single-slice tools own one level — and you stitch the rest yourself.**

| Approach (examples) | Meaning | Ontology | Semantic | Physical |
|---|:---:|:---:|:---:|:---:|
| Data catalog (Collibra, Glue) | ◐ glossary | — | — | ● tables |
| Semantic layer (dbt, Cube) | — | — | ● metrics | — |
| Graph / RDF (Stardog, Neptune) | ◐ comment | ● RDF/OWL | ◐ SPARQL | ● assertions |

Each is excellent at its slice. But meaning that spans all four levels ends up **smeared across three
products** with three formats, three governance stories, and no single artifact you can diff, review, or
hand to an agent. The glossary doesn't know the join; the semantic layer doesn't know the definition; the
graph doesn't know the warehouse columns.

**All-in-one platforms own all four — inside one vendor's world.**

| Approach | Meaning | Ontology | Semantic | Physical | Neutral? |
|---|:---:|:---:|:---:|:---:|:---:|
| All-in-one platform A (proprietary) | ● object defs | ● objects·links | ● functions | ● pipelines | **no — lock-in** |
| All-in-one platform B (preview) | ● | ● | ● BI | ● lakehouse | **no — lock-in** |
| **Meaning as Code** | ● definition | ● edges | ● rules | ● grounding | **yes** |

This is the most important row in the argument, and it cuts *for* the idea, not against it: **the leading
platforms cover all four levels — which proves meaning needs its own dedicated layer.** They just make you
**buy the platform** to get it, and your meaning then lives in their format, on their compute, under their
roadmap. The two full columns are the proof of concept; the lock-in is the bill.

## The gap MAC fills

Full coverage **and** vendor-neutral had not come together. MAC is exactly that cell: the four levels of
meaning as **version-controlled YAML you own**, that *projects onto* whatever you run — a graph DB, a
semantic layer, SQL views — instead of being trapped in one of them. Same four-level coverage as the
all-in-one platforms; no lock-in; runs on the stack you already have.

That is the *hosting* answer. There is a second axis — *notation* — and there MAC's stance is interop, not
conquest.

## Within that model: how MAC relates to the standards

A vendor-neutral model still has to choose a notation, and several standards already own pieces of it. MAC
**borrows their best ideas and exports to them** rather than reinventing — *formalize the closed, govern
the open*:

- **OSI (Open Semantic Interchange)** — an industry-backed YAML interchange for datasets, measures,
  dimensions, relationships; built to move a semantic layer *between tools*. It overlaps MAC's
  Semantic/Physical levels and is the natural **export target** — and MAC *does* export it: [`tools/mac_to_osi.py`](../tools/mac_to_osi.py)
  projects a MAC ontology onto an OSI semantic model (Physical→`datasets`/`fields`, Edges→`relationships`,
  Rules→`metrics`), and the output ([`example_tpch_ontology/projections/tpch.osi.yaml`](../example_tpch_ontology/projections/tpch.osi.yaml))
  **validates against OSI's own JSON Schema** (v0.2.0.dev0). What OSI is *not*: an authoring discipline with a *closed core an LLM can't hallucinate*, typed
  **rules bound to physical fields with cross-file enforcement**, an edges-as-data join model, a
  constraint/shapes gate, or L0–L3 trust tiers. *Adopt for interchange; keep MAC for authoring + governance.*
- **SHACL (W3C)** — constraints as data over RDF graphs. MAC's constraint gate is deliberately
  SHACL-*shaped* (target · path · constraint · severity) but runs over plain YAML — the "constraints are
  data" win without the triple-store. *Borrowed the shape; dropped the RDF.*
- **SBVR (OMG)** — business vocabulary and rules with modality and verbalization. MAC's typed
  `contract.rules` are the lighter, executable-adjacent cousin: bound to real columns, run by a gate.
- **OKF (Google Cloud Open Knowledge Format)** — a portable "LLM-wiki": markdown concept docs with YAML
  frontmatter, built to hand *agents* their context. It overlaps MAC's *Meaning* level and is a natural
  **export target** — and MAC exports it: [`tools/mac_to_okf.py`](../tools/mac_to_okf.py) projects a bundle
  of `type`-tagged concept docs with `# Schema`, linked `## Relationships`, and `# Citations`. The telling
  contrast: OKF's reference implementation *enriches* each concept with schemas and join paths via a second
  LLM pass that crawls documentation; MAC already holds those as data and emits them deterministically.
  *Author governed meaning in MAC; project to OKF to feed agents.*
- **OWL / RDFS (W3C)** — maximally expressive, with reasoning. MAC is *deliberately* less expressive: no
  triple store, closed-world (a column is or isn't valid), and a small closed vocabulary an LLM can author
  without inventing keys. Reach for OWL when you need inference; reach for MAC when you need a model an
  agent reads to generate correct SQL.
- **Semantic-layer-as-code (LookML, Cube, dbt, Malloy)** — closest in spirit, but tool-coupled and
  metric-shaped. MAC is the vendor-neutral layer *above* them that can project down.

## When it is *not* MAC

Honesty, because the framework insists on it:

- If you need **only metric portability across BI tools**, OSI or a tool's native semantic layer is the
  pragmatic pick — MAC is more than you need.
- If you need **logical inference / a reasoner**, use OWL + a triple store; MAC doesn't reason.
- If you are **happy inside one all-in-one platform** and lock-in is acceptable, that platform already
  gives you the four levels — buy it.

MAC earns its place in the **opposite** situation: you want to author meaning **once**, **own it**, keep it
**vendor-neutral**, have an **LLM author and read it safely**, enforce **rules bound to fields**, and carry
**provenance/confidence** for trust — i.e. the multi-vendor, governed-agent setting where no single
platform should own your meaning. That cell was empty. That is the one MAC fills.

---

*Companions: [meaning-as-code.md](meaning-as-code.md) (the idea) · [projecting-outward.md](projecting-outward.md)
(the exporters that prove "projects onto whatever you run") · [mac-in-the-loop.md](mac-in-the-loop.md)
(where MAC sits in the question→answer→provenance loop) · [FRAMEWORK.md](../FRAMEWORK.md) (the spec).*
