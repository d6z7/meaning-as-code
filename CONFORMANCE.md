---
title: MAC Conformance — the strict-syntax contract (v0.5)
version: '0.5'
date: 2026-06-14
status: DRAFT — the normative conformance rules; companion to mac.schema.json
companions:
  - mac.schema.json     # the machine-checkable schema this document governs
  - FRAMEWORK.md        # the why (READ FIRST)
  - CONCEPT_SPEC.md     # the prose key reference
  - MODELLERS_COOKBOOK.md
---

# MAC Conformance

This document is the **strict-syntax contract** for Meaning-as-Code. `FRAMEWORK.md` says *why* MAC
exists and `CONCEPT_SPEC.md` describes every key in prose; **this** document plus **`mac.schema.json`**
say, normatively and machine-checkably, *exactly what a conformant file may contain*. The schema is the
enforcer; this document is the rulebook around it.

> **The core vocabulary is CLOSED.** A MAC file may use only the keys defined in `mac.schema.json`, plus
> declared `x-` extensions (below). Any other key is a conformance error. This is the discipline that
> makes the model legible to a developer, projectable to a platform, and safely authorable by an LLM —
> an LLM cannot hallucinate a plausible-but-wrong key, because the schema rejects it.

## 1. Conformance levels

| Level | Name | Gate | Means |
|---|---|---|---|
| **L0** | well-formed | parses as YAML | structurally loadable |
| **L1** | **core-conformant** | validates against `mac.schema.json` | only core keys + declared `x-` extensions; closed class/level/type/role vocabularies; required keys present |
| **L2** | execution-validated | the query the model implies runs and the number is sane | the trust gradient's right end (FRAMEWORK §8) — schema **cannot** check this |
| **L3** | expert-confirmed | an SME has ratified the meaning | `confidence: C` |

A file claims a level in `metadata` (`schema_version` pins the schema generation; `status` and
`confidence` carry L2/L3 state). **L1 is the new bar this release adds:** before v0.5 the validator
checked placement and legality but not a closed key-set, so files drifted (e.g. eight ad-hoc
`*_contract` keys). v0.5 closes that hole.

## 2. The closed-core + `x-` extension rule (how we stay strict without ossifying)

Strictness is **layered**, not uniform:

- **Core** — the universal constructs in `mac.schema.json`. Strict: unknown keys are **rejected**
  (`additionalProperties: false` at every object level).
- **Extension** — the **only** legal way to add a key the core doesn't define is the **`x-` namespace**
  (e.g. `x-attribute-owner:`). The schema permits `^x-` keys everywhere via `patternProperties`. This is
  the OpenAPI-style extension convention, chosen for the same reason: visible, namespaced, never
  mistaken for core.
- **Profile** — a project (e.g. GAPS) declares a **profile**: the list of `x-` keys it uses and what
  each means. An `x-` key with no profile entry is undeclared debt, not license. (GAPS's
  `x-attribute-owner`, the grounding annotations, the HIFA/SPG bespoke blocks live here.)

**Promotion path.** An `x-` key that recurs across multiple sources/profiles, an agent reads directly,
*and* projects cleanly onto all three target families (FRAMEWORK §10) earns **promotion to core** via a
`schema_version` bump. That is exactly how the v0.5 `contract:` construct was born — the application
invented it eight ways under no namespace; v0.5 promotes it. The rule going forward: invent under `x-`,
prove it, promote it. **Never sprinkle a bare key into the core again.**

## 3. What changed in v0.5 (the formalization delta from 0.4)

Driven by the GAPS drift audit (promote / profile / drop verdicts, ratified 2026-06-14):

| Change | Kind | Detail |
|---|---|---|
| `contract:` block | **PROMOTE** | new core construct — resolves the deferred `reasoning_guidance:` question. Absorbs `no_probe_guarantee` + the `answer/name/resolution/aggregation/time` contracts. The interpretive ones fold home: `additivity_contract`→`semantics.additivity`, `identity_contract`→the key, `two_axes_contract`→`semantics`. |
| `grounding.serves_from`, `grounding.grain` | **PROMOTE** | first-class core grounding keys (serving-view path; the grain-commitment lesson). |
| `value_set:` | **DROP** | consolidated into `values:` (single carrier; `closure` inline). |
| concept/`grounding.columns` | **DROP** | column metadata is single-homed in the Physical layer; concepts/grounding no longer restate columns. |
| edge type `denormalized`, `literal_equal` | **DROP** | not legal for `physical`. `denormalized`→ re-model (not an edge); `literal_equal`→ `value_mapped_key`. |
| `additivity` axes | **GENERALIZE** | axis names are domain-specific (not hardcoded to GAPS's time/geography/model). |
| rule `render_kind` | **ENFORCE** | now required on every rule. The `formula*` family drops → `template`/`logic`. |

Conformance fixes these create for the GAPS application (Phase C, not schema changes): 4 FPL_CLEAN rules
need `render_kind`; FPL_CLEAN analytical column roles map down to canonical; the `non_additive`→
`non-additive` spelling; the `value_set`→`values` migration.

## 4. Open canon questions (surfaced by validating the framework's OWN example — need a ruling)

Validating `mac.schema.json` against `example_shop_ontology/` (the framework's reference example)
exposed two places where the **canon contradicts itself** — the example uses constructs the schema docs
don't sanction. These are **decisions, not bugs**, and they are PENDING:

- **Q1 — column-role vocabulary.** `TABLES_SCHEMA`/the ratified DECISION 4 keep a *physical* role set
  (`primary_key/foreign_key/value/discriminator/audit/composite_key_part`). But the shop example itself
  uses `measure`, `attribute`, `temporal`. So the "canonical" set is narrower than the framework already
  writes. **Options:** (a) widen the core role enum to include the analytical roles the example needs
  (`dimension/measure/attribute/temporal`) — this *reverses* DECISION 4 for the framework core while GAPS
  may still choose to map down; or (b) migrate the example to the narrow set. *(Schema currently enforces
  the narrow set; the example fails until ruled.)*
- **Q2 — foreign-key shape.** `TABLES_SCHEMA` documents `{name, from_column, to_table, to_column}`; the
  shop example uses `{column, references}`. **Options:** (a) the rich shape is canonical (migrate the
  example); (b) the terse shape is the generic core and the rich one is a GAPS profile. *(Schema
  currently enforces the rich shape.)*

## 5. Validating a file (Phase C wires this into the gate)

```
# parsed-YAML → schema check (dates loaded as strings; file type by location)
python tools/validate_schema.py <path>      # to consume mac.schema.json + keep the semantic checks
```

The structural gate (schema) proves **L1**. It does **not** prove correctness — `mac.schema.json` is
silent on whether a column exists in the warehouse or a label means what you think. **L2** (execution
validation) and **L3** (SME) remain mandatory and unchanged (FRAMEWORK §8). A green schema is the
*start* of trust, not the end.

## 6. schema_version discipline

- Every file pins `metadata.schema_version` (now `'0.5'`).
- A **breaking** change to the core vocabulary bumps the minor (`0.5`→`0.6` while pre-1.0).
- A **promotion** (an `x-` key entering core) is a minor bump with a changelog entry here.
- The validator refuses a file whose `schema_version` it does not recognise — so a stale file fails
  loudly rather than validating against the wrong contract.
