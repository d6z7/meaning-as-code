# The YAML Ontology Framework

Write the *meaning* of your data down once — as plain-text, version-controlled YAML, organised into
four layers — so that the same artifact can be read by an AI agent (to answer questions correctly) and
ingested by any target platform (to become that platform's ontology), without locking your meaning into
a vendor.

This repository is the complete, domain-neutral description of the framework, plus a worked example.

## Start here

| Document | What it is |
| --- | --- |
| **[FRAMEWORK.md](FRAMEWORK.md)** | The canonical description — the problem, the thesis, the four layers, the six classes, the rules layer, the trade-offs, and the projection table (RDF / property-graph / relational). **Read this first.** |
| [CONCEPT_SPEC.md](CONCEPT_SPEC.md) | The exhaustive key-by-key reference — every predefined key and its meaning. |
| [MODELLERS_COOKBOOK.md](MODELLERS_COOKBOOK.md) | The task-oriented guide — *when you're authoring*: decision procedures (which layer? which class? which edge level?), recipes per task, and antipatterns. Routes to the canon; doesn't restate it. |
| [FRAMEWORK_STRUCTURE_MAP.md](FRAMEWORK_STRUCTURE_MAP.md) | The visual companion — diagrams of the object types, layers, and concept anatomy. |
| [example_shop_ontology/](example_shop_ontology/) | A tiny, complete, **synthetic** ontology (an online shop) — the framework applied end-to-end. Read it to *see* every construct, rather than read about it. |
| [tools/validate_schema.py](tools/validate_schema.py) | A **structural** validator — enforces the framework's contracts within each file (class present, semantics placement, naming contract, edge legality). |
| [tools/check_references.py](tools/check_references.py) | A **referential** validator — its companion; checks that every cross-file reference resolves (no orphans). Together: well-formed *and* internally whole. |

## In one paragraph

Most semantic stacks make you author meaning *inside* a platform (an RDF store, a property graph, a
semantic layer); the model then lives in that platform's format, and moving or comparing across
platforms means re-authoring. This framework inverts that: **meaning is authored once, as YAML, and
each platform is a renderer of it.** The same artifact serves two consumers — an AI agent reads it as
context to compose correct queries, and a target platform ingests it and casts it into its own
primitives. The discipline that makes this work is a small fixed schema (four layers, six concept
classes), single-homing (every fact lives in exactly one place), and execution validation (structure is
not correctness — you run the queries the model implies and let the data correct you).

## What this is not

Not a runtime, not a reasoner, not a W3C standard. It *describes* a domain richly enough that an agent
can reason and a platform can ingest — it does not run logic itself. See [FRAMEWORK.md §9](FRAMEWORK.md)
for the honest trade-offs and when *not* to use it.

## Status

The framework is at v0.4 of its schema. It has been exercised across multiple independent domains of
genuinely different shape. It is offered as a pragmatic convention, not a finished product — feedback
and adversarial testing on new domains are the most useful contributions.
