---
title: MAC Conformance — the strict-syntax contract (v0.1.9)
version: '0.1.9'
date: 2026-06-14
status: DRAFT — the normative conformance rules; companion to mac.schema.json
companions:
  - mac.schema.json     # the machine-checkable schema this document governs
  - tools/mac_diag.py   # the FROZEN diagnostic contract §5.1 reproduces (the code IS the contract)
  - tools/mac_compile.py # the compiler §5 defines — one invocation, one finding list, one verdict
  - FRAMEWORK.md        # the why (READ FIRST)
  - CONCEPT_SPEC.md     # the prose key reference
  - MODELLERS_COOKBOOK.md
---

# MAC Conformance

This document is the **strict-syntax contract** for Meaning-as-Code. `FRAMEWORK.md` says *why* MAC
exists and `CONCEPT_SPEC.md` describes every key in prose; **this** document plus **`mac.schema.json`**
say, normatively and machine-checkably, *exactly what a conformant file may contain*. The schema is the
enforcer; this document is the rulebook around it.

> **The core vocabulary is CLOSED, and nothing escapes it.** A MAC file may use only the keys defined
> in `mac.schema.json`. Any other key is a conformance error — including a key in the `x-` namespace,
> which is **prohibited** (§2, MAC012). This is the discipline that makes the model legible to a
> developer, projectable to a platform, and safely authorable by an LLM — an LLM cannot hallucinate a
> plausible-but-wrong key, because the schema rejects it, and there is no namespace it can reach for
> when it does.

## 1. Conformance levels

| Level | Name | Gate | Means |
|---|---|---|---|
| **L0** | well-formed | parses as YAML | structurally loadable |
| **L1** | **core-conformant** | validates against `mac.schema.json` | core keys ONLY (no `x-`, §2); closed class/level/type/role vocabularies; required keys present |
| **L2** | execution-validated | the query the model implies runs and the number is sane | the trust gradient's right end (FRAMEWORK §8) — schema **cannot** check this |
| **L3** | expert-confirmed | an SME has ratified the meaning | `confidence: C` |

A file claims a level in `metadata` (`schema_version` pins the schema generation; `status` and
`confidence` carry L2/L3 state). **L1 is the new bar this release adds:** before v0.5 the validator
checked placement and legality but not a closed key-set, so files drifted (e.g. eight ad-hoc
`*_contract` keys). v0.5 closes that hole.

A **level is claimed per file**; conformance is judged **per bundle**. The three gates below establish
L1 for the files they reach — **§5 is what establishes it for the bundle as a whole**, names every way a
bundle can fail (the closed diagnostic taxonomy, §5.1), and makes a clean result the *precondition* for
running anything on it (§5.2). §5.4 is explicit about which of L0–L3 that does and does not cover.

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
from an applied pilot into core (the `contract.rules` RuleObject in `mac.schema.json`). The built-in
`rule-binds-grounded` shape enforces it **cross-file**: every `binds` value must be a column of the table
the concept grounds to (`grounding.table`/`sources` → `tables/<name>.yaml#columns`). Columns are
single-homed in the Physical layer, so a rule cannot claim to govern a field the concept does not ground —
the relational check the schema structurally cannot make. See `example_tpch_ontology` LineItem for a
worked instance.

**The data-plane transform construct (v0.1.8).** The two-plane layout's data plane is now fully typed,
not just its seam. Alongside `data/datasets/` (produced relations → `TableFile`) and `data/sources/`
(observed raw inputs → `TableFile`, marked `metadata.kind: raw_source`), `data/transforms/` descriptors
validate against a new **`TransformFile`** def: a pipeline declares what it `produces` (one dataset) and
its `inputs[]`, **each typed by a closed `kind`** — `raw_source` · `dataset` (view-on-view) ·
`authored_seed` (rows authored from the ontology, no upstream table) · `external` (federation,
upstream-owned). The validator routes these dirs by location (declared in `mac.project.yaml`:
`transforms:` / `sources:`). See `example_shop_ontology/data/` for the worked `orders` triple
(`orders_raw` source → `orders` transform → `orders` dataset).

**The lineage-complete profile (opt-in, gated by the data plane).** A project that declares
`planes.data` in `mac.project.yaml` may claim the **lineage-complete** profile: the data-plane graph is
**total and connected** — every dataset is `produced` by a transform; every transform's `inputs[]`
resolve and **mirror the realizing SQL** (no input present in the SQL but absent from `inputs[]`); every
concept binding lands on a dataset (the referential gate already enforces the binding half). Under this
profile the **lineage projection is a guaranteed derivation** — it cannot silently drop a node. This is
a *structural completeness* requirement layered on L1 for data-bound projects, **not** a new L-level
(L0–L3 stay orthogonal); a pure vocabulary ontology with no data plane is unaffected. The `inputs[]`-vs-SQL
completeness check is the recorded follow-on (a referential-gate rule); the schema legalizes the
construct it will enforce.

## 2. The closed core — and the only way to add a key

Strictness is **uniform**, not layered. There is one rule, and no namespace exempt from it:

- **Core** — the universal constructs in `mac.schema.json`. Unknown keys are **rejected**
  (`additionalProperties: false` at every object level) and — since **v0.1.14** — there is no
  `patternProperties` hatch standing beside them. The core is closed, and closed with nothing behind it.
- **`x-` keys are PROHIBITED.** An `x-` key is a conformance **error** wherever it appears, diagnosed
  **MAC012** by `tools/check_extension_keys.py`. Not "discouraged", not "debt": prohibited. There is no
  profile, register or declaration that makes one legal, because declaring a key changes nothing about
  what can *check* it — and being checkable is the entire content of the word "conformant".

> **This section used to say the opposite.** Until now it taught the `x-` namespace as "the **only**
> legal way to add a key", described a `patternProperties` hatch the schema had already closed, and
> offered a profile in which an extension could be *declared* rather than removed. That construct is
> withdrawn, and MAC009 (`undeclared-extension`) is withdrawn with it (§5.1) — a code whose remedy was
> "declare it" ratified the very thing MAC012 forbids, and a framework that encodes two opposite
> policies on one construct has a defect, not a nuance.

**Why the namespace was removed rather than governed.** MAC closes every structural plane and validates
it. An `x-` key sits **by construction** outside that, so nothing checks what it holds — and what one
was found holding was the *grain*: the single most consequential fact about a relation. Measured on the
day the offending key was retired, with the core schema untouched around it, **two of four** declared
cell keys were false while still reading as VERIFIED; the two that held were the two whose view
*enforces* the key, so it was true by construction rather than by declaration. Nobody was careless. The
field was unreachable by every gate in the system, so being wrong cost nothing and stayed invisible.
**An extension is not a small schema. It is an unchecked one.**

**The only way to add a key: PROPOSE A CORE KEY.** Where a construct seems to need a key the core does
not define, that is a **MAC gap** — a wall worth naming — and the response is to change MAC, which is
now the only mechanism that exists:

1. **Name the wall.** What can the model not say? Record it as a decision, with the sites that hit it.
2. **Show it recurs** across more than one source or bundle, and that an agent or projector reads it
   directly — a key nothing consumes is a note, and a note belongs in prose.
3. **Show it projects** cleanly onto all three target families (FRAMEWORK §10). A key that projects onto
   one is that target's concern, not the core's.
4. **Land it in `mac.schema.json`** as a core key, typed and constrained, with a `schema_version` bump
   and a changelog entry in §6 — at which point every gate in this framework can reach it.

Until step 4 lands, the model says it in prose or does not say it. That is a real cost and it is the
intended one: it puts the pressure on the schema, where it can be resolved once, instead of on 478
unreachable sites where it cannot be resolved at all. The v0.5 `contract:` construct is the worked
example, and it is worth being precise about what it proves — the application had invented it **eight
ways under no namespace**, and v0.5 resolved that by *promoting it into core*. The promotion was the
fix; the eight private spellings were the defect. **Never sprinkle a bare key into the core, and never
reach for a namespace instead.**

## 3. What changed in v0.5 (the formalization delta from 0.4)

Driven by an applied-instance drift audit (promote / profile / drop verdicts, ratified 2026-06-14):

| Change | Kind | Detail |
|---|---|---|
| `contract:` block | **PROMOTE** | new core construct — resolves the deferred `reasoning_guidance:` question. Absorbs `no_probe_guarantee` + the `answer/name/resolution/aggregation/time` contracts. The interpretive ones fold home: `additivity_contract`→`semantics.additivity`, `identity_contract`→the key, `two_axes_contract`→`semantics`. |
| `grounding.serves_from`, `grounding.grain` | **PROMOTE** | first-class core grounding keys (serving-view path; the grain-commitment lesson). |
| `value_set:` | **DROP** | consolidated into `values:` (single carrier; `closure` inline). |
| concept/`grounding.columns` | **DROP** | column metadata is single-homed in the Physical layer; concepts/grounding no longer restate columns. |
| edge type `denormalized`, `literal_equal` | **DROP** | not legal for `physical`. `denormalized`→ re-model (not an edge); `literal_equal`→ `value_mapped_key`. |
| `additivity` axes | **GENERALIZE** | axis names are domain-specific (not hardcoded to a fixed time/geography/model triple). |
| rule `render_kind` | **ENFORCE** | now required on every rule. The `formula*` family drops → `template`/`logic`. |

Conformance fixes these create for a consuming application (Phase C, not schema changes): rules that
lack `render_kind` need it added; bespoke analytical column roles map down to canonical; the
`non_additive`→`non-additive` spelling; the `value_set`→`values` migration.

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

## 5. Compiling a bundle — the compiler, the taxonomy, and the refusal

A single file can be checked on its own:

```bash
# parsed-YAML → schema check (dates loaded as strings; file type by location)
python tools/validate_schema.py <path>      # consumes mac.schema.json + keeps the semantic checks
```

That answers *is this file legal*. It does not answer the question that decides whether a bundle may be
used — **what is the state of the whole model**: what is defined, what is defined redundantly, what is
not defined, on every criterion this standard has. A per-file check cannot answer it, and neither can a
row of independent gates: each reports on the part it happened to look at, so a bundle can hold a green
tick from every one of them and still be full of artifacts nothing ever validated. That is not a
theoretical failure mode; it is the observed one, and it is why the **compiler** exists.

```bash
python tools/mac_compile.py <bundle-root> [--show error|warning|info] [--json <path>]
# exit 0 = compiles · 1 = does not conform · 2 = the compiler could not run
```

**ONE invocation · ONE finding list · ONE verdict · ONE exit code.** Every finding is a `Diagnostic`
(`tools/mac_diag.py`, the frozen contract) carrying a **code** from the closed taxonomy below, a
one-sentence summary that is the finding itself, and **witnesses** — the places it is evidenced, each
addressable as `file#path:line`.

**Fanout is collapsed, always.** A finding evidenced in *N* files is **one** diagnostic carrying *N*
witnesses — never *N* diagnostics. A report that prints one line per file gets muted within a week and
its root cause dies with it. Anything that emits per-object findings is not conforming to this section.

**The finding set MUST persist.** `--json <path>` writes the complete set — every diagnostic, every
witness, every code in the taxonomy with whether it was **computed** — so that after any compile the
whole state is readable at any later point, by anyone, without re-running it. A code that fired zero
times and a code no check computed are **different facts** and the record keeps them apart; a report
that renders them the same is lying by omission.

### 5.1 The diagnostic taxonomy (closed)

The **code is the contract**: its text may be reworded, its meaning may not change without a version
bump, because suppressions and counts are keyed on it. Meanings are normative and reproduced verbatim
from `tools/mac_diag.py`.

| Code | Kind | Means | Default severity |
|---|---|---|---|
| | **what is not defined** | | |
| **MAC001** | undefined-artifact | present in the bundle, carries no MAC definition, not declared out of scope | **error** — `info` for a file that *is* declared out of scope (the waiver, reported as a fact) |
| **MAC002** | invalid-artifact | has a MAC definition and does not satisfy it | **error** — `warning` where a routed file's `schema_version` is outside the recognized set, so it claims a definition nothing checked |
| **MAC012** | extension-duplicates-core | an `x-` extension key. **Prohibited outright** (§2) — it sits by construction outside every gate MAC has, so nothing can check what it holds. Where it duplicates a core field the finding names that field; where it does not, it is a MAC gap to be proposed into core, not declared beside it | **error** |
| **MAC009** | ~~undeclared-extension~~ | **WITHDRAWN.** It diagnosed an `x-` key *with no profile entry*, whose remedy was to declare it — a remedy that ratified the construct §2 now prohibits. Its subject is a strict subset of MAC012's (MAC012 reads every YAML in the bundle; MAC009 read only schema-routed files), so nothing is lost by withdrawing it and one contradiction is. **The code is burned, never reassigned** — counts and suppressions keyed on it must not silently start meaning something else | **retired** |
| | **what is defined redundantly** | | |
| **MAC003** | fact-restated | one fact stated in more than one home; nothing keeps the copies in step | **warning** |
| **MAC004** | fact-contradicted | statements of one fact disagree — something downstream is reading the wrong one | **error** |
| | **what is offered and not taken** | | |
| **MAC005** | capability-unadopted | MAC offers a mechanism for this and the bundle does not use it | **warning**, and **never error** — enforced structurally, the severity function cannot return `error`. `info` where the bundle has no applicable site, or where MAC itself cannot honour its own offer (framework debt — the bundle is not the subject) |
| | **what is claimed without warrant** | | |
| **MAC006** | claim-unearned | a conformance level or confidence asserted with no evidence behind it | **warning** |
| **MAC010** | change-unprotocolled | an authored or tuned object with no entry in the change record | **error** — `warning` where the change record does not exist at all (there is nothing to be missing *from*) |
| | **what points at nothing** | | |
| **MAC007** | guard-dead | a rule or guard testing a value that cannot occur — it can never fire | **error** |
| **MAC008** | reference-unresolved | a reference that resolves to nothing | **error** |
| | **what is not covered** | | |
| **MAC011** | coverage-missing | a required completeness the bundle does not reach | **error** — `warning` for the bands ruled legitimate (thin lineage, seed-only assembly) and where the completeness could not be measured |

Severities mean exactly this, and nothing else:

- **error** — the bundle **does not conform**. Nothing may run on it.
- **warning** — conformant, but carrying a defect that becomes an error under a stated condition. The
  condition belongs in the diagnostic's `note`, not in the reader's head.
- **info** — a fact about the bundle worth reporting. Never blocks.

**retired** is not a severity — it is the absence of one. A retired code is never emitted, never
counted, and never reported as *clean*: "clean" means computed and found nothing, and a withdrawn code
computes nothing at all. The compiler prints retired codes on their own line so a reader who remembers
the code learns what replaced it instead of reading a green tick that means neither. **A retired code is
never reassigned.** Closing the taxonomy means the code is the contract; re-pointing `MAC009` at some
future defect would silently change the meaning of every count and suppression already keyed on it.

A check the compiler has not yet absorbed natively runs **wrapped**, as a subprocess, and its failure
becomes **one** diagnostic under the code its subject belongs to, carrying the gate's own output as
witnesses. A wrapped gate is **debt**, and the compiler prints the wrapped list on every run so it
stays visible. A wrapped gate that exits with a *setup* failure (exit 2) did not judge the bundle: its
code is then **UNKNOWN, not clean**, and it is reported as a warning — failing a bundle nobody checked
is a lie in the other direction.

### 5.2 A bundle MUST compile before anything runs on it

> **Normative.** A bundle with one or more **error**-severity diagnostics **does not conform**. No tool
> in this framework, and no consumer of it, may project, publish, serve, seal or answer from such a
> bundle. This is not advisory: **a check that does not block is not enforcement.**

The refusal is wired at the point where a bundle stops being source and starts becoming artifacts — the
**projector**. It compiles first, refuses on any error, and reports the **compiler's own rendered
findings** as the reason (never a paraphrase — a gate that restates a finding in its own words is a
second home for it, MAC003, and the two wordings drift). It persists the complete finding set beside the
bundle on **every** attempt, refused runs included, so a refusal is as readable afterwards as a pass.

**The override.** A human who knows what they are doing may proceed over a non-conformant bundle, and
the escape is shaped so that using it is a decision somebody made and can be held to:

- it is a **command-line flag**, never an environment variable or a config key — an env var is invisible
  in the command somebody typed, and a config key drifts on and stays on;
- its **value is the reason**, so the flag cannot be used without stating why;
- it prints a **banner** that cannot be mistaken for normal output, listing the codes being ignored;
- it is **recorded** — reason, username, timestamp, and the codes overridden — in the same persisted
  compile record the findings live in, so an artifact built over a refusal carries the admission next to
  the evidence, permanently.

An override is a **statement**, not a setting. A bundle that needs one on every run is a bundle whose
findings should have been cleared or declared.

### 5.3 The declared escape — `conformance.out_of_scope`

A bundle may legitimately own files this framework has no definition for (a testing plane, an
application's own registers). MAC001 does not forbid that. It forbids it being **silent**. The bundle
declares them, with a reason, in the manifest:

```yaml
# mac.project.yaml
conformance:
  out_of_scope:
    - path: acceptance/**
      reason: "testing plane; MAC has no schema for it — see decisions/00NN"
```

A declared path is reported as **info**, not error. The `reason` is not decoration: it is what makes the
debt arguable in review, and what a later reader needs to decide whether it is still true. A broken
manifest yields **no** waivers rather than silently waiving everything — an escape hatch that widens
under a parse error is not an escape hatch.

**Declared debt is visible and arguable; silent debt is how a standard stops being one.** Note the
limit of that principle, because §2 used to overreach it: declaring works for an artifact MAC has *no
definition for* — the declaration is the only handle anything has on it, and it costs nothing to be
honest about. It does **not** work for a key inside a file MAC *does* define, because there the
declaration competes with a definition and loses: nothing validates what the key holds, so the
declaration buys silence rather than coverage. That is why `conformance.out_of_scope` is a legitimate
escape and the `x-` profile was not.

### 5.4 What a clean compile does and does not prove

A clean compile proves **L1** and the data-free relational rules layered on it (§1's three gates). It
does **not** prove correctness: nothing here knows whether a column exists in the warehouse, whether a
number is sane, or whether a label means what you think.

- **L2 (execution-validated) is NOT implemented in MAC.** No gate, shape, or diagnostic code in this
  framework runs the query a model implies and checks the answer. The taxonomy has no code for it and
  the compiler will never emit one, so **a clean compile must not be read as any L2 evidence at all.**
  Applications do implement L2 — a suite of executable properties, each with the SQL that tests it and
  the expected result — but they do so **outside MAC's sight**, in artifacts MAC has no definition for,
  which means such a suite is itself an MAC001 until the bundle declares it out of scope. That is an
  honest report of a hole in this framework, not a covered case. Bringing execution validation under a
  definition — so that L2 evidence is *addressable* the way L1 findings are — is open framework work.
- **L3 (expert-confirmed) is asserted, not proven.** `confidence: C` is a claim about a human act. The
  compiler checks the claim for **warrant** (MAC006 — machine-written provenance asserting C with no
  ratification on record) but it cannot manufacture the ratification. An SME still has to say yes.

A green compile is the **start** of trust, not the end — and it is now also the *precondition*: the
bundle must reach the start before anything is allowed to run.

## 6. schema_version discipline

- `metadata.schema_version` pins **the `mac.schema.json` generation a file is written against** — there is
  one version axis, and it *is* the MAC schema version. The current generation is **`'0.1.9'`**.
- A **new core key** (§2's proposal path, step 4) or any **breaking** change to the core vocabulary bumps
  the patch while pre-`0.x` stabilises, with a changelog entry here. The field-anchoring promotion — the
  `contract.rules` RuleObject with `binds` (§1, FRAMEWORK §6d) — defined `0.1.6`.
- **`0.1.7`** adds, on the same contract: the **two-plane project layout** (`data/` + `ontology/`, opt-in via
  `mac.project.yaml`; absent ⇒ flat); the **edge-endpoints-are-concepts** rule (`EdgeEndpoint` — view/table
  endpoints rejected); **`grounding.field_roles`** (a whitelist of meaningful columns → an analytical role)
  with the **application-vocabulary** mechanism (`<ns>.<vocab>.<term>` references resolved from a project
  `vocabulary.yaml`, e.g. `shop.field_role.measure`) and the `field-roles-grounded` coverage shape; and
  the six self-validating projectors (OSI · RDF/OWL · SHACL · openCypher · OKF · Mermaid). Per RELEASING.md,
  the tag, schema title, validator `CURRENT`, and every example `schema_version` move to `0.1.7` together.
- **`0.1.8`** adds, on the same contract: the **data-plane transform construct** — the `TransformFile` def
  (`produces` + typed `inputs[]`, the closed `kind` enum `raw_source`/`dataset`/`authored_seed`/`external`),
  validated under `data/transforms/` and `data/sources/` (manifest `transforms:`/`sources:` keys); the
  **lineage-complete** profile (§1); and a **data-plane lineage view** in `mac_to_mermaid` (the
  `--lineage` mode: physical sources→transforms→datasets in production flow, alongside `--ontology` /
  `--er` / `--physical`). Per RELEASING.md, the
  tag, schema title, validator `CURRENT`, and every example `schema_version` move to `0.1.8` together.
- **`0.1.9`** adds, on the same contract: the **content-model UDF seam** — an optional `realized_by` **canon
  binding** on the behaviour-bearing slots (`semantics`, `grounding`, enumeration `values`, grouping
  `members`, and each `contract.rules[]`), `{ udf: mac.canon.<name>, params }` or a list (`$defs/canonBinding`).
  It names a canon in the new **`mac.canon`** vocabulary registry (`mac_vocabulary.yaml`), resolved by
  `check_references` (an unknown canon name is an ERROR); the canon **logic is single-homed** in the
  executable library **`tools/canon/`** and demonstrated runnable in **`tests/test_canon.py`**. The seam is
  the determinism-coverage mechanism (reference_manual/the_content_model.md §4): a behaviour-bearing slot
  WITH a `realized_by` is canon-backed (deterministic); WITHOUT, its prose is model-interpreted. Optional and
  backward-compatible. Per RELEASING.md, the tag, schema title, validator `CURRENT`, and every example
  `schema_version` move to `0.1.9` together.
- **`0.1.12`** adds, on the same contract, a first-class home for a **business relation's NL-trigger
  vocabulary** (additive over `0.1.11`, so `0.1.11` files remain valid): the business-edge `type` enum
  widens from `identity` to **`identity | shared_attribute`** (`shared_attribute` = a symmetric business
  relation where two instances of the SAME concept relate iff they share a non-null value of a named
  attribute — not a stored FK); two OPTIONAL edge fields — **`resolved_by`** (a `path.yaml#anchor` ref to
  the rule that computes the relation set; the `shared_attribute` counterpart of the `identity`-edge
  `realized_by` requirement) and **`aliases`** (`$defs/relationAliasBlock`); and the **`relationAliasBlock`**
  `$def` — a CLOSED `{ realized_by, multilingual{de,en,syn} }` object holding the auditable surface→relation
  trigger vocabulary, where a surface resolves to THIS EDGE (by `edge_id`) via the new
  **`mac.canon.relation_alias_resolve`** deterministic token→relation resolver (registered in
  `mac_vocabulary.yaml`, resolved by `check_references`). Contrast `aliasBlock`, whose keys are value codes:
  the routing target here is the relation itself. Optional and backward-compatible.
- **Canon-registry extension (vocabulary-only, no schema bump): `mac.canon.enum_from_register`.** A new
  member of the **`closed: false`** `mac.canon` registry (`mac_vocabulary.yaml`): the deterministic canon
  that realizes a **closed enumeration's value set by reading a PINNED register** (a lookup artifact) —
  the value domain IS the register's `code` column — instead of restating the codes in inline
  `values.items`. An enumeration binds it on `values.realized_by`:
  `{ udf: mac.canon.enum_from_register, params: { register: <artifact stem/path>, key_column: code } }`
  and **OMITS `items`** (the register is single-homed; restating the codes would double-home them). This
  needs **NO `mac.schema.json` change** — the `enumerationValues` `$def` already permits `values` with
  `realized_by` and no `items` (`items` is not required). Per **RELEASING.md “When to bump”**, a change
  that does not touch `mac.schema.json` (a vocabulary-only addition to a registry that is explicitly
  `closed: false` and “extends by branch → PR with a witnessing pattern”) **does not bump the
  `schema_version`**; it rides on the current `0.1.12` generation. (It mirrors `alias_resolve` /
  `relation_alias_resolve` as a **declarative** registry entry — a consumer sources the value set from the
  register; it is not an executable `tools/canon/` UDF.) Witness: `example_shop_ontology` `ShippingCarrier`
  (enumeration, no inline items) + the `shipping_carriers` register. *(Were this to arrive bundled with a
  schema change, it would go out under the next additive number, `0.1.13`.)*
- **Canon-registry extension (vocabulary-only, no schema bump): `mac.canon.grouping_from_register`.** The
  **nested-membership twin** of `enum_from_register` — another member of the **`closed: false`** `mac.canon`
  registry (`mac_vocabulary.yaml`): the deterministic canon that realizes a **grouping's enumerated member
  sets by reading an EXPLODED register** (a lookup artifact with one row per `(group_key, member)`) and
  **RE-AGGREGATING** it by the group key into nested member arrays — instead of restating the sets in inline
  `members.definitions`. A grouping binds it on `members.realized_by`:
  `{ udf: mac.canon.grouping_from_register, applied_as: member_set, params: { register: <artifact stem/path>,
  group_key: <col | [cols]>, member_col: <col>, carry: [<scalar cols>] } }` and **OMITS `definitions`** (the
  register is single-homed; restating the sets would double-home them). `group_key` is the identity
  column(s) each set is keyed by (a string, or a list for a composite key); `member_col` is the column
  collected into each set's array; `carry` lists the per-group scalar columns repeated on every member row
  and carried through onto each set (label / count / flags). This needs **NO `mac.schema.json` change** — the
  `groupingMembers` `$def` already permits `members` with `over` + `realized_by` and no `definitions`
  (`over` is the only required key; `definitions` is optional). Per **RELEASING.md “When to bump”**, a
  vocabulary-only addition to a registry that is explicitly `closed: false` and “extends by branch → PR with
  a witnessing pattern” **does not bump the `schema_version`**; it rides on the current `0.1.12` generation.
  (Like `alias_resolve` / `enum_from_register`, it is a **declarative** registry entry — a consumer
  re-aggregates the member sets from the register; it is not an executable `tools/canon/` UDF.) Witness:
  `example_shop_ontology` `ProductBundle` (grouping, no inline `definitions`) + the exploded
  `product_bundles` register. *(Were this to arrive bundled with a schema change, it would go out under the
  next additive number, `0.1.13`.)*
- **The `x-` prohibition (§2) — normative prose + tooling, no schema bump.** §2 withdraws the `x-`
  extension namespace, the extension **profile**, and the "invent under `x-`, prove it, promote it"
  promotion path, replacing them with the core-key proposal path. The enforcing gate is
  `tools/check_extension_keys.py` (**MAC012**), now run by the compiler; **MAC009** is withdrawn (§5.1).
  It adds **no key** to `mac.schema.json` and removes none — the schema had already closed `^x-` in
  **v0.1.14**, in 58 places, and this is the prose and the taxonomy catching up with it — so per
  **RELEASING.md "When to bump"** it does not move the `schema_version`. What it changes is the
  **remedy** a bundle is handed: previously "declare the key in a profile", now "remove the key, or
  propose it into core". Measured across the estate at the time of the ruling: **478 `x-` sites in 198
  files across six bundles, and not one bundle declaring a profile** — so this escalates nothing that
  was passing, it replaces an error that pointed the wrong way with one that points at the fix.
- **The compiler (§5) — normative prose + tooling, no schema bump.** §5 defines the closed diagnostic
  taxonomy (`tools/mac_diag.py`, frozen), the rule that a bundle MUST compile clean before anything runs,
  and the `conformance.out_of_scope` escape. It adds **no key** to `mac.schema.json` — it states how the
  existing contract is *enforced*, not what a file may contain — so per **RELEASING.md “When to bump”**
  it does not move the `schema_version` and rides on the current generation. One thing it makes visible
  rather than fixes, recorded here so it is not mistaken for covered: **L2 is unimplemented** (§5.4).
  *(This bullet previously recorded a second item — that `mac.schema.json` had no home for the §2
  extension profile. That is obsolete twice over: v0.1.14 both closed the `^x-` hatch and added a
  `ProjectFile#profile.extensions` slot, and §2 has since withdrawn the profile construct outright. The
  slot is now a place to declare a prohibited key, which MAC012 reads as a finding like any other.)*
- The validator (`tools/validate_schema.py`) enforces files at the **current** `schema_version` (`0.1.9`)
  and skips the rest, so a stale file fails loudly rather than validating against the wrong contract.
- **Note on the label.** `0.1.6` *re-bases* the earlier `0.5`/`0.6` working labels onto the framework's
  own `0.1.x` line (it sorts below them — a relabel, not a forward bump). The historical deltas below
  (§3) describe that same generation under its former `v0.5` name.
