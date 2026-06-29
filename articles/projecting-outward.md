---
title: "Projecting outward: one governed model, every platform"
date: 2026-06-17
status: article — exporters companion to positioning.md
scope: GENERIC — domain-neutral. Names technology standards/products as targets, no business domain.
---

# Projecting outward: one governed model, every platform

The positioning argument ([positioning.md](positioning.md)) ends on a claim: MAC is *vendor-neutral
meaning you own, that **projects onto** whatever you run.* This piece makes that claim concrete. "Projects
onto" is not a slogan — it is running code. One MAC ontology, authored and governed once, is emitted
**mechanically** onto six target formats across five platform families, and each projection **validates in
its target's own terms** — not on the author's say-so.

## The discipline: projections are derived, never authored

A projection is a build artifact, not a source. The MAC files (`concepts/`, `edges.yaml`, `tables/`,
`rules.yaml`) are the single source of record; everything a projector emits is regenerable from them and
lives apart, under `projections/`, so it can never be mistaken for — or drift from — the model. You author
in one place, govern in one place, and re-run the projectors whenever the model changes. The gates ignore
`projections/` for exactly this reason: an export is output, never input.

That direction is the whole point. Meaning flows *out* of MAC to the tools; it is never smeared *across*
them.

## Six projections, five families

| Projector | Target | Standard / vendor home | Self-validation |
|---|---|---|---|
| [`mac_to_osi.py`](../tools/mac_to_osi.py) | **OSI** semantic model | Open Semantic Interchange (Snowflake et al.) | validates against **OSI's own JSON Schema** (v0.2.0.dev0) |
| [`mac_to_graph.py`](../tools/mac_to_graph.py) | **openCypher** graph | Neo4j, Amazon Neptune, Memgraph | node/edge **self-consistency** check (every endpoint is a declared label) |
| [`mac_to_rdf.py`](../tools/mac_to_rdf.py) | **RDF / OWL** (Turtle) | W3C; Stardog, Neptune-RDF, GraphDB | **re-parses** as valid RDF (round-trip) |
| [`mac_to_shacl.py`](../tools/mac_to_shacl.py) | **SHACL** shapes | W3C | a real engine (**pySHACL**) accepts good data, rejects broken data |
| [`mac_to_okf.py`](../tools/mac_to_okf.py) | **OKF** knowledge bundle | Google Cloud Open Knowledge Format v0.1 | every doc carries the required `type`; every internal link resolves |
| [`mac_to_mermaid.py`](../tools/mac_to_mermaid.py) | **Mermaid** diagram | renders inline on GitHub / any Mermaid viewer | renders as a valid flowchart; a hand-laid drawio companion exists for the curated hero image |

Five families because these are genuinely different jobs: a **semantic-interchange** format (OSI), a
**graph** query model (openCypher), the **RDF/OWL + SHACL** triple-and-shapes world, an **agent-knowledge**
bundle (OKF), and a **human-facing diagram** (Mermaid). One model serves all five.

### OSI — the semantic-interchange target

[OSI](https://github.com/open-semantic-interchange/osi) is an industry-backed YAML interchange for
datasets, fields, relationships, and metrics, built to move a semantic layer *between tools*. The
projector maps MAC's Physical layer to `datasets`/`fields`, its Edges to `relationships` (the composite
associative-entity join survives as a multi-column relationship), and its measure Rules to `metrics`. The
output is validated against **OSI's published JSON Schema** — so conformance is OSI's verdict, not ours.

### openCypher — the property-graph target

The graph projector turns node-class concepts into node labels and edges into typed relationships, emitting
node-key constraints and a schema comment block. Property graphs (Neo4j, Neptune, Memgraph) speak
**openCypher**; the projector checks its own output for self-consistency — every relationship endpoint is a
label it actually declared — so the script cannot emit a graph that references a node type that doesn't
exist.

### RDF / OWL — the triple-store target

The RDF projector emits an OWL ontology in Turtle: concepts become `owl:Class`, grounded columns become
`owl:DatatypeProperty` (with `xsd:` ranges), and edges become `owl:ObjectProperty` (carrying the grounded
join as a comment). Property URIs are class-qualified, so a column name reused across tables stays a
distinct property with a single domain. Because it is built with `rdflib`, the Turtle is valid by
construction — and the projector **re-parses** what it wrote to prove the round-trip. (TPC-H: 8 classes,
8 object + 55 datatype properties, 313 triples.)

### SHACL — validating the RDF

OWL says what *exists*; SHACL says what instance data must *satisfy*. The SHACL projector is the validation
companion to the RDF one: node-class concepts become `sh:NodeShape`s; columns become property shapes with
datatypes and key cardinality; **closed enumerations become `sh:in` value lists**. The proof is the
strongest of the set — `--selftest` synthesises instance data and runs a real SHACL engine (**pySHACL**),
asserting the shapes **accept** a conforming graph and **reject** a deliberately broken one (missing keys,
out-of-enum codes). The engine, not the author, is the judge.

### OKF — the agent-knowledge target

[OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) is Google Cloud's
portable "LLM-wiki": a directory of markdown concept docs with YAML frontmatter whose one required field is
`type`. The projector emits one doc per concept — `type` from the concept class, a `# Schema` section from
the grounded columns, linked `## Relationships` from the edges, a `# Values` table for enumerations, and
`# Citations` back to the source `.yaml` — plus the reserved `index.md` and `log.md`. The check asserts
every doc has `type` and every internal link resolves.

OKF makes the deepest point of all. Its own reference implementation *enriches* each concept with "schemas,
citations, and join paths" by running **a second LLM pass that crawls documentation**. MAC already holds
all of that as data, so the projector emits the enriched bundle **deterministically** — no crawl, no guess.
This is the thesis in one line: *the knowledge another tool reconstructs with a model, MAC simply has.*

## What every projection drops — and why that is the point

Each target carries the slice it was built for and **drops** the constructs only MAC holds:

- typed `contract.rules` **bound to physical fields**, enforced cross-file by a gate;
- the **additivity law** (which measures are safe to sum across which axes);
- the **six closed concept classes** and the closed-core vocabulary an LLM can author without inventing keys;
- the **L0–L3 trust tiers**, confidence, and provenance.

That these are dropped on the way out is not a gap — it is the reason MAC exists *above* the targets. You
author the governed, LLM-safe, field-anchored model **once**, in a format you own; then you project the
right slice onto OSI for interchange, onto a graph for traversal, onto RDF+SHACL for reasoning and
validation, onto OKF for agents. The full model stays home; the platforms get exactly what they can use.

## The meta-point: trust comes from the target

The reason this matters for "can I trust the export?" is that **no projection asks you to trust the
projector**. OSI conformance is OSI's JSON Schema. RDF validity is a re-parse. Shape enforcement is
pySHACL's report. Graph integrity is a self-consistency pass. OKF completeness is a `type`-and-link check.
The author's claim is never the evidence; the target's own validator is. Five formats, five independent
verdicts, one model behind them.

---

*Companions: [meaning-as-code.md](meaning-as-code.md) (the idea) · [positioning.md](positioning.md) (where
MAC sits among the standards) · [mac-in-the-loop.md](mac-in-the-loop.md) (the question→answer→provenance
loop) · [FRAMEWORK.md](../FRAMEWORK.md) (the spec). Worked outputs live under each example's
`projections/`.*
