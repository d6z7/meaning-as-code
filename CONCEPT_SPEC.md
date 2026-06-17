---
title: Concept & Rules Schema — key-by-key reference (v0.1.6)
version: '0.1.6'
date: 2026-06-05
status: CANONICAL — the exhaustive key reference for the framework. Domain-neutral.
audience: ontology architects, platform/vendor integrators, AI-agent builders, new contributors
scope: GENERIC — domain-independent. Contains NO reference to any specific business domain, warehouse,
  or vendor. Examples are drawn from the synthetic worked example (`example_shop_ontology/`).
role: detailed key-by-key REFERENCE APPENDIX to the canonical framework description (framework/FRAMEWORK.md). Read FRAMEWORK.md first for the why + the complete picture; read this for the exhaustive key meanings.
companion: framework/FRAMEWORK.md (canonical description — READ FIRST), FRAMEWORK_STRUCTURE_MAP.md (visuals), example_shop_ontology/ (worked reference on a neutral domain)
---

# Concept & Rules Schema — key-by-key reference (v0.1.6)

> **v0.1.6 — read alongside the formal schema.** The authoritative, machine-checkable contract is now
> [`mac.schema.json`](mac.schema.json) + [`CONFORMANCE.md`](CONFORMANCE.md). This prose reference is
> brought into line with v0.1.6: the `contract:` construct is added (the deferred
> `reasoning_guidance:` question, resolved), now carrying typed `rules` bound to fields (`binds`);
> `value_set:` is consolidated into `values:`; `grounding.serves_from`/`grain` are promoted. **Where prose
> and schema disagree, the schema governs syntax.** The change list is in `CONFORMANCE.md §3`.

This is the complete, reader-facing reference for an ontology authored in YAML under this framework.
Read it to understand **what a concept is, how the files are organised, the `class:` vocabulary, and the
meaning of every predefined key.** The running reference is the worked example `example_shop_ontology/`
(an online shop) — open it alongside this document; it shows the canonical shape in full, and the
concrete examples below are drawn from it.

The keys and shapes below reflect a model that has been **execution-validated** — authored, structurally
checked, then proven by running the queries it implies against live data and correcting the model where
data disagreed (the trust gradient, FRAMEWORK §8). "Validates cleanly" is the start of trust, not the end.

---

## 1. What is a concept?

A **concept** is one named *thing the business reasons about* in a data domain — a measure
(Revenue), a classification (OrderStatus), an entity (Customer), a reference dimension
(Product), a process/event (Order), or a grouping (Category). It is the unit of *meaning*: it answers
"what is this, what does it mean, where does its data live, and what must a reasoner know to use it
correctly?"

A concept is NOT a table, a column, or a query. It is the **semantic layer** that sits above the
physical data and is consumed two ways:

1. an **AI agent** reads it (plus its grounding) to compose correct queries; and
2. a **target platform** (RDF store, property graph, semantic layer, Palantir-style ontology) can
   ingest it and cast it into its own primitives.

Each concept lives in one YAML file under `<source>/concepts/<group>/<concept>.yaml`.

---

## 2. Why "1 file = 1 concept"

Every concept is its own file. This is deliberate:

- **Readability / ownership.** A human opens one file and sees one complete thing — definition,
  meaning, values, grounding, open questions — without scrolling past unrelated concepts. One file
  is small enough for one person to own and review.
- **Change isolation.** A concept changes when *its* business meaning changes. One-file-per-concept
  means a change touches exactly one file; diffs and change-logs are scoped and legible.
- **Referenceability.** Other files (rules, edges, federation) point at a concept by a stable path
  (`<source>/concepts/<group>/<concept>.yaml`). One file = one stable address.
- **No-redundancy enforcement.** "Every fact lives in exactly one place" is only checkable when the
  boundaries are explicit. One concept per file makes the boundary obvious: a fact is either *this*
  concept's, or it belongs in another file (or a different layer — see §3).
- **Portability / parallel work.** Files are independent, so they project to a target platform, get
  validated, or get authored in parallel without collision.

Companion concepts that are inseparable from a primary (e.g. an `as-of` revision axis alongside the
calendar `period` it qualifies) may share the file via a `related_concepts:` list — but they are the
exception, not the rule, and each still carries its own `name:`.

---

## 3. The layers (where a fact lives)

Each fact lives in exactly one layer; no layer restates another.

| Layer | File | Holds |
| --- | --- | --- |
| **Physical** | `<source>/tables/<table>.yaml` | columns, types, foreign keys (the grounding targets) |
| **Concept** | `<source>/concepts/<group>/<concept>.yaml` | meaning, structure, reasoning facts (THIS document) |
| **Rules** | `<source>/rules.yaml` | derivations + scope/membership rules (computed things) — §7 |
| **Edges** | `<source>/edges.yaml`, `federation/edges.yaml` | navigable relations between concepts |

What is intrinsic to a concept lives ON the concept (its attributes, its closure, its purpose).
What is a *relation between two concepts* is an edge. What is *computed* (a formula, a ratio, a
scope set) is a rule. Keeping these apart is what keeps each file small and each fact single-homed.

---

## 4. The `class:` vocabulary

Every concept declares exactly one `class:` — the structural shape of the thing. This is the single
classifying word a reader (or projector) keys off. There are **six** classes:

| `class:` | Meaning | Typical shape block | Example (shop) |
| --- | --- | --- | --- |
| **enumeration** | A controlled vocabulary — a set of allowed coded values (closed or open). | `values:` (with `closure`) | OrderStatus |
| **measure** | A quantity that is counted/aggregated; has additivity, unit, possibly a derivation. | `subclasses:` + a catalogue (or just measure semantics) | Revenue |
| **reference** | A dimension entity identified by a key, that facts point at. | `properties:` + `grounding` | Product |
| **entity** | An abstract class / a thing with structure or named instances that isn't one of the above. | `properties:` + `instances:` | Customer |
| **grouping** | A categorical aggregation of other things (above the leaf level). | mixed | Category (over Product) |
| **event** | A thing that happens / a stateful occurrence, OR the lifecycle state machine it moves through. | `lifecycle:` (phases→states→sequence) on the machine; `properties:` on the occurrence | Order (placed→paid→shipped→delivered) |

Coverage claim: the six classes are intended to absorb any data-grounded domain without new
vocabulary. The vocabulary has been exercised across multiple independent domains of genuinely different
shape — snapshot-measure grains, per-record event grains with real lifecycles, and completeness-tier
axes — each modelled with these six classes alone. (A given project may leave one class unexercised —
e.g. a domain whose hierarchies are all expressible as `reference` + containment never needs
`grouping`; the class remains specified, ready when a domain requires it.)

Notes:
- `class:` **retires an earlier `type:` zoo** (`enumerated_classification`, `composite_reference`,
  `abstract_class_with_named_instances`, `hierarchical`, `hierarchical_grouping`…). The mapping:
  enumerated_* → enumeration; composite_reference/date_dimension/singleton → reference;
  abstract_class* → entity; a hierarchical measure → measure; a hierarchical grouping → grouping.
- **`entity` is narrower than TypeDB's `entity`.** Here it is the "structured thing" bucket *after*
  measure/enumeration/reference/grouping are split out. Don't read TypeDB semantics into it.
- The class determines which shape block(s) appear — but a concept includes only the blocks it needs.

---

## 5. The naming contract (applies to every file)

The fix for namespace collisions (v0.3 had physical column names doubling as YAML keys). Two rules:

1. **Ontology identifiers live ONLY in `name:` / `id:` fields** — never as a bareword YAML key.
2. **Physical names** (columns, tables, stored codes) live ONLY as VALUES of designated fields:
   `column:`, `code:`, `grounds_column:`, `eav_attribute:`, `table:`, `key_column:`,
   `column_string_prefix:`.

Corollary a reader/agent can rely on: *a string is an ontology concept iff it's a `name:`/`id:`
value; a string is a physical artifact iff it's a `column:`/`code:`/`table:` value.* A bareword key
is always schema vocabulary — never an entity name, never a data value. (So an enumeration named
after a column becomes `{ name: PaymentMethod, grounds_column: payment_method }`, not a
`payment_method:` key.)

**`rule` is reserved for derivations** (the rules layer, §7). A data-quality constraint's description
field is `assert:`, never `rule:` (§6 constraints) — so the word `rule` means one thing only.

---

## 5a. Reference syntax (how one file points at another)

The naming contract (§5) says *where* an identifier lives; this says *how a reference addresses it*, so
that references are mechanically resolvable (a checker can verify no reference is orphaned — see
`tools/check_references.py`).

A reference is a **path to a file, optionally followed by a `#anchor`**:

```
<relative-path>.yaml[#<anchor>]
```

- **Path** — relative to the ontology root (e.g. `concepts/order/order.yaml`, or in a wrapped/federated
  project `<source>/concepts/...`). It must resolve to a real file.
- **Anchor** — addresses an object *within* the file. The addressable anchors are:
  - `#concept` — the file's top-level `concept:` block.
  - `#<top-level-key>` — any top-level mapping key (e.g. `#foreign_keys`, `#gold_layer_architecture`).
  - `#<list>.<id-or-name>` — an entry of any list whose items carry an `id:` or `name:`, nested by its
    container. So `instances:` → `#instances.<id>`; a `foreign_keys:` list → `#foreign_keys.<name>`; a
    nested `country_instances.instances:` → `#country_instances.instances.<id>`.
  - **Names with spaces are backtick-quoted** in the anchor (e.g. ``#individual_kpis.`Total Market` ``);
    backticks are ignored on resolution, so the quoted and unquoted forms are equivalent.

Where references appear (each must resolve): edge `endpoints.{from,to}.ref`, edge `realized_by` (→ a
table's `#foreign_keys...`), grounding (concept → its `table:`/`tables:`), rule `validated_against` (→ a
table) and `over:`/`derives:` (→ concept/subclass names), `value_domain:` (→ an enumeration/reference
concept), and any `{{ rules.<id>.template }}` injection (→ a rule in the same rules file).

**Grounding may name its table two ways** (both valid): scalar `grounding.table: orders` for a
single-table concept, or a `grounding.tables:`/`primary_tables:` **list** of `{ name: ..., role: ... }`
for multi-table grounding. Either way the named table must have a `tables/<name>.yaml` descriptor.

A reference that is not yet authored is marked with an explicit placeholder (`TODO`, `<...>`,
`NEEDS_MAP`) so it reads as intentionally-incomplete, not broken — a checker reports these as INFO, not
errors.

---

## 6. Predefined keys — complete reference

Concept files use these top-level keys, in this conventional **order** (the order tells a story:
identity → meaning → structure → grounding → rules → housekeeping):

```
metadata → concept → (values | properties | subclasses | instances | members | attributes |
  enumerations | related_concepts | lifecycle) → grounding → constraints → governance → open_questions
```

### `metadata:` — what this file is
| key | meaning |
| --- | --- |
| `concept:` | the concept's name (matches `concept.name`) |
| `source:` | the data source this concept belongs to (one application's source identifier) |
| `version:` | this file's content version (semver-ish; bump on change) |
| `schema_version:` | which generation of THIS schema the file conforms to (current '0.1.6') |
| `status:` | production / draft / prototype |
| `owner:` | CODEOWNERS-style owning group |
| `confidence:` | whole-file default confidence — C (confirmed) / I (inferred) / Q (needs-SME). Individual values may override. |

### `concept:` — what it IS and what it MEANS
| key | meaning |
| --- | --- |
| `name:` | the ontology identifier (PascalCase). The single canonical id. |
| `label:` | human display name |
| `german:` | the German source term, when relevant (the domain is bilingual) |
| `class:` | the structural shape — one of the six (§4) |
| `definition:` | plain-language description of what the thing is (folded `>` — reads as a sentence) |
| `semantics:` | the interpretive/reasoning block (below). Single home for "how to reason with this." |
| `notes:` | caveats / context that aren't the definition |
| `grounded_by:` | (enumerations) the discriminator column the values come from |
| `related_axis:` | (rare) points at an orthogonal axis on another concept (e.g. PlanStage → the kpi-suffix tracking variant) |

### `concept.semantics:` — the interpretive block (single home for reasoning facts)
| key | meaning | applies to |
| --- | --- | --- |
| `purpose:` | why the concept exists / what business question or decision it serves | all |
| `scope:` | where it applies AND where it does NOT (coverage asymmetry) | measures, scoped concepts |
| `additivity:` | per-dimension aggregation rule `{time:, geography:, model:}` — each `additive` / `non-additive`. THE footgun-preventer (a stock measure is non-additive over time). | measures |
| `unit:` | the measure's unit (orders, vehicles, months…) | measures |
| `null_semantics:` | what an ABSENT row means — genuinely zero vs not-loaded vs structurally-untracked. (Drives anomaly-of-absence correctness.) | where absence is meaningful |

### Shape blocks (pick what matches `class:`)
| block | meaning |
| --- | --- |
| `values:` | the enumeration's value list. Carries `closure:` (open/closed/unknown) + `closure_why:` describing the value set, then `items:` (inline `{code, …}` maps). `closure` lives WITH the value set, not in `semantics`. |
| `value_set:` | alternative carrier for `closure:`/`closure_why:` when the values are a separate `values:` list (keeps the list a clean list). |
| `properties:` | intrinsic PRIMITIVE attributes (string/int/date) — `{name, type, required, doc}`. Concept-typed relations are NOT properties (they're edges). |
| `attributes:` | (model/entity) attributes whose value is read from an EAV row / column and constrained by an enumeration concept: `{name, eav_attribute, value_domain, confidence}`. value_domain references the enumeration. |
| `subclasses:` | is-a hierarchy (e.g. measure classes Flow/Stock/Target; derived subclasses). |
| `instances:` | concrete named instances of an abstract entity. |
| `members:` / containment | whole→part membership as a list on the container (e.g. a Category's member Products), with a `members_resolution:` for whole→part navigation. Containment is concept structure, NOT an edge. |
| `related_concepts:` | companion concepts homed in the same file, each with its own `name:` (§2). |
| `enumerations:` | a list of enumeration sub-blocks each `{name, grounds_column, closure, values}` — used when a concept carries several coded columns. On a companion enumeration, `closure`/`closure_why` sit at the **entry level** (siblings of `grounds_column`); a concept's own single value-set uses the top-level `value_set:`/`values:` instead. |
| `lifecycle:` | (event class) the state machine an entity moves through. Shape: `phase_sequence:` (ordered macro-phases) → `phases:` (each a `{name, meaning, states:[...]}` grouping leaf states) → `phase_closure:`, plus a `states:` block (`closure` + `items:` of `{nr, code, phase, meaning, confidence}`). The transition order IS the state sequence; no separate transition graph is required when the lifecycle is a sequence. Descriptive only — the framework RECORDS the machine, does not execute it. |
| catalogue list (e.g. `individual_kpis:`) | (measure concept) the catalogue of concrete measures, each referencing its `measure_type` + carrying its own `semantics`. |

**Why phases, not flat states.** An earlier draft defined `lifecycle:` as a flat `states:` +
`transitions:` list. Applied to real lifecycles long enough (dozens of states across distinct stages),
flat states became illegible — the domain needs **macro-phases that group states, plus an ordered
`phase_sequence:`** (e.g. the shop Order's CHECKOUT → FULFILMENT → CLOSED). So the canonical shape is
phases-grouping-states-with-a-sequence, not flat states.

### `grounding:` — where the data lives (thin pointer; column metadata stays in the tables layer)
| key | meaning |
| --- | --- |
| `kind:` | the grounding adapter — `sql_table` (pluggable: api / file / graph) |
| `table:` / `tables:` | the physical table(s) |
| `schema:` | the warehouse schema/catalog |
| `key_column:` / `code_column:` | the identity / code columns |
| `value_filter:` | filter that selects this concept's rows within a shared table (e.g. an EAV `attribute='...'`) |
| `join_rule:` / `discriminator:` / `snapshot_rule:` | join / row-selection / snapshot guidance (query-dialect expressions; the dialect is pluggable) |
| `family_resolution:` | how to resolve a parent/family to its leaf fact codes (e.g. a code prefix, rather than a dimension-attribute join) |
| `row_count:` / `used_in:` | volumetrics / where the dimension feeds facts |

### `constraints:` — data-quality invariants (validation, NOT derivation)
Each entry: **`assert:`** (the rule text — note: `assert`, never `rule`), `severity:`
(ERROR / WARNING / INFORMATIONAL), `machine_executable:` (bool), `sql_assertion:` (a check query,
expected 0), `open_question:` (link). Answers "is the DATA valid?" — distinct from a derivation rule.

### `governance:` — housekeeping (append-only)
`last_reviewed:` + `change_log:` — a list of `{date, change, change_type, by}`. Change_type:
CREATION / ADDITION / CORRECTION / REMOVAL / REFACTOR. **Append-only; never edit history.**

### `open_questions:` — SME-actionable unknowns
Each: `id`, `topic`, `question` (interrogative, with options), `status` (OPEN/PARTIAL/RESOLVED),
`owner_for_resolution`, optional `priority` / `category` / `cross_references`. The canonical home for
"what we don't know"; projected into the SME backlog.

---

## 7. The Rules layer (`<source>/rules.yaml`)

Derivations and scope/membership rules — the *computed* things (stored measures need NO rule).
Each rule entry:

| key | meaning |
| --- | --- |
| `rule:` | the derivation's id (the reserved word `rule` — §5) |
| `derives:` | the concept / named result it produces |
| `over:` | the concepts it operates on |
| `logic:` | plain-language statement of the computation |
| `render_kind:` | how it becomes executable SQL: `sql_expression` (canonical snippet INJECTED at query time) · `sql_view` (PRE-DEPOSITED view, referenced by `view_ref:`) · `derived_set` (a membership predicate, injected) · `spark_udf` (rare) · `spec_only` (agent generates from `logic:`) |
| `template:` | the canonical SQL (Jinja-templated). **Jinja shapes STRUCTURE; user-derived values are BOUND as SQL params `?`, never interpolated.** |
| `view_ref:` / `usage_template:` | (sql_view) the deposited view + how to query it |
| `requires_join:` / `relative_template:` | the surrounding join skeleton / a variant formula |
| `applied_as:` | e.g. `subquery_wrapper` — for rules that change query SHAPE (a snapshot-latest rule is a ROW_NUMBER wrapper, not a WHERE predicate) |
| `closure:` (on a derived_set) | whether the membership set is closed |
| `disambiguation:` | competing rules for an ambiguous natural-language term (e.g. several candidate definitions of "Europe"), with a "resolve or flag" note for the agent |
| `validated_against:` | tables whose columns the injected SQL uses (for the validator to check) |
| `conditions:` / `edge_cases:` | filters/caveats that must be applied / known edge cases |
| `inspectable:` | may the agent substitute inputs (for counterfactuals) |
| `confidence:` / `cross_references:` | confidence marker + links to findings |

Rules **compose**: one rule's `template:` can inject another (`{{ rules.<other_rule>.template }}`). A
common foundational rule is a *snapshot-latest* collapse — when a table stores multiple snapshots per
logical cell, nearly every aggregation must first reduce to the latest snapshot (via ROW_NUMBER) to
avoid double-counting.

---

## 8. Orthogonal axes (a recurring footgun)

A recurring modelling hazard: two axes that *look* like one. When a domain has two independent
dimensions that an agent could conflate (e.g. a *tracking variant* — actual vs plan vs budget — that is
orthogonal to a *reporting cycle* — first estimate vs revised vs year-end close), each must be modelled
as its own concept/axis, and the cross-product is real: every value of one carries the full range of the
other. Conflating them inverts the model — a class of error execution validation reliably catches.
Where a project has such axes, they are documented in that project's concept files, not here.

---

## 9. Validation

`tools/validate_schema.py` enforces this schema: `class:` present, interpretive keys in
`semantics:` (not loose), `closure` not a top-level key, `constraints[]` use `assert:` not `rule:`,
rules have a legal `render_kind` + payload, edge level/type legality, naming-contract spot-checks. A
clean run (0 errors) means **well-formed**, not **correct** — correctness is earned by execution
validation (FRAMEWORK §8), not by the validator.

## 10. What is deferred / unexercised (framework-level)

- `reasoning_guidance:` (agent-facing dos/don'ts) is DEFERRED — undecided whether it belongs in the
  ontology or in agent configuration; the structured facts in `semantics:` carry the same information
  declaratively, from which guidance can be derived.
- The `grouping` class is specified but may be unexercised in a given project — a domain whose
  hierarchies are all `reference` + containment never needs it. Retained, ready when a domain requires
  it.

(Per-application status — which sources are converted, which facts await expert confirmation, which
findings are open — lives in that application's own decision records and findings, not in this
framework reference.)
