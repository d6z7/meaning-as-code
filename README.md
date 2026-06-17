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
| [mac.schema.json](mac.schema.json) | The **formal, machine-checkable schema** (v0.5) — the single source of structural truth: closed vocabulary, class/level/type/role enums, required keys, and the `x-` extension rule. |
| [CONFORMANCE.md](CONFORMANCE.md) | Conformance levels (L0–L3), the closed-core + `x-` extension contract, and the v0.5 change list. |
| [tools/validate_schema.py](tools/validate_schema.py) | The **structural** validator — schema-driven (MAC v0.5): checks every model file against `mac.schema.json` (closed vocabulary, required keys, naming contract, edge legality). |
| [tools/check_references.py](tools/check_references.py) | A **referential** validator — its companion; checks that every cross-file reference resolves (no orphans). Together: well-formed *and* internally whole. |
| [tools/check_shapes.py](tools/check_shapes.py) | A **constraint** validator (new in v0.1.6) — runs *shapes* (constraints declared as DATA in [mac_shapes.yaml](mac_shapes.yaml)) that the schema can't express, e.g. the relational invariant "the values here ⊆ a set declared there". The third gate: structural + referential + **constraint**. |
| [mac_shapes.yaml](mac_shapes.yaml) · [mac.shapes.schema.json](mac.shapes.schema.json) | The **built-in constraint shapes** + the meta-schema governing their form — universal MAC invariants run by `check_shapes.py`; applications add domain/dialect shapes via `--shapes`. |

## In one paragraph

Most semantic stacks make you author meaning *inside* a platform (an RDF store, a property graph, a
semantic layer); the model then lives in that platform's format, and moving or comparing across
platforms means re-authoring. This framework inverts that: **meaning is authored once, as YAML, and
each platform is a renderer of it.** The same artifact serves two consumers — an AI agent reads it as
context to compose correct queries, and a target platform ingests it and casts it into its own
primitives. The discipline that makes this work is a small fixed schema (four layers, six concept
classes), single-homing (every fact lives in exactly one place), and execution validation (structure is
not correctness — you run the queries the model implies and let the data correct you).

## Validating the model

The model is checked by two deterministic, data-free gates (no warehouse needed) — **structural**, then
**referential**. A clean run means *well-formed* (L1), not *correct*: execution validation (L2) and SME
confirmation (L3) still apply — see [CONFORMANCE.md](CONFORMANCE.md).

```bash
pip install jsonschema pyyaml      # one-time

# 1. STRUCTURAL — validate every file against the formal schema (mac.schema.json)
python3 tools/validate_schema.py example_shop_ontology
#   enforces files at schema_version 0.5 and skips legacy; add --all to check everything, --strict to fail on warnings

# 2. REFERENTIAL — every cross-file reference (realized_by / grounding / over: / value_domain) resolves
python3 tools/check_references.py example_shop_ontology

# 3. NEGATIVE TESTS — prove the schema REJECTS bad input (not just that it accepts good)
python3 tests/test_negative.py
```

Point (1) and (2) at *your own* model's root instead of `example_shop_ontology` to validate it. Exit code
`0` = clean, `1` = violations, `2` = setup error (missing deps). The negative suite lives in
[tests/](tests/) — intentionally-malformed fixtures the schema must reject; wire it into CI alongside (1)+(2).

## What this is not

Not a runtime, not a reasoner, not a W3C standard. It *describes* a domain richly enough that an agent
can reason and a platform can ingest — it does not run logic itself. See [FRAMEWORK.md §9](FRAMEWORK.md)
for the honest trade-offs and when *not* to use it.

## Status

The framework is **v0.1.6**; its schema contract is **v0.5** — formalized as a machine-checkable contract
([mac.schema.json](mac.schema.json) + [CONFORMANCE.md](CONFORMANCE.md)), with a schema-driven validator,
a referential checker, and (new in v0.1.6) a **constraint/shapes** validator + a negative-test suite. It has been exercised across multiple independent domains of genuinely
different shape. It is offered as a pragmatic convention, not a finished product — feedback and
adversarial testing on new domains are the most useful contributions.
