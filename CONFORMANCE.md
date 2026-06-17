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

### The three gates — structural · referential · constraint (the constraint gate is new in v0.1.6)

L1 is reached by three complementary, data-free validators, not one:

| Gate | Tool | Checks |
|---|---|---|
| **structural** | `tools/validate_schema.py` | each file against `mac.schema.json` — closed keys, required keys, class/level/type/role enums, naming, edge legality |
| **referential** | `tools/check_references.py` | every cross-file reference resolves (no orphans), `mac.*` terms resolve to the vocabulary |
| **constraint** | `tools/check_shapes.py` | **shapes** — constraints declared as DATA ([mac_shapes.yaml](mac_shapes.yaml)) that the schema cannot express, above all **relational** invariants ("the values at path A ⊆ the set at path B") |

The schema is necessarily *loose* where a rule is relational or cross-document — it validates one file's
tree, not a fact in file A against a set in file B. The **constraint gate** fills exactly that gap:
constraints become inspectable, versioned model content (and generator-readable), run by one engine over
declared shapes. The framework ships **built-in** universal invariants (`mac_shapes.yaml`, governed by
[mac.shapes.schema.json](mac.shapes.schema.json)); an application adds its own via `--shapes`.

**Field-anchoring (v0.1.6).** A concept's `contract.rules[]` are typed behavioural rules (`kind` →
`mac.rule_kind`, `when`/`then`/`why`) **anchored to the field(s) they govern** via `binds:` — promoted
from the GAPS pilot into core (the `contract.rules` RuleObject in `mac.schema.json`). The built-in
`rule-binds-grounded` shape enforces it **cross-file**: every `binds` value must be a column of the table
the concept grounds to (`grounding.table`/`sources` → `tables/<name>.yaml#columns`). Columns are
single-homed in the Physical layer, so a rule cannot claim to govern a field the concept does not ground —
the relational check the schema structurally cannot make. See `example_tpch_ontology` LineItem for a
worked instance.

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

## 4. Resolved canon questions (decided 2026-06-14)

Validating `mac.schema.json` against `example_shop_ontology/` exposed two places where the canon
contradicted itself. Both are now ruled — and in both, **the schema as written is already correct; the
example is what migrates** (a Phase-C task):

- **Q1 — column-role vocabulary → KEEP NARROW.** The core role set stays *physical*
  (`primary_key/foreign_key/value/discriminator/audit/composite_key_part/unknown`); DECISION 4 holds.
  Rationale: a column's *analytical* meaning (measure/dimension/attribute) already lives in the Concept
  layer — tagging the column too would restate it (single-homing). Phase C migrates the example's
  `measure/attribute/temporal` down to canonical (`→ value`).
- **Q2 — foreign-key shape → RICH SHAPE CANONICAL.** `{name, from_column, to_table, to_column}` is the
  one canonical FK shape (explicit; feeds edge cardinality). Phase C migrates the example's terse
  `{column, references}` to it.

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
