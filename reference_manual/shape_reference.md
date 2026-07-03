---
title: The Shape Reference — how a MAC file is shaped, key by key
version: '0.1.0'
date: 2026-06-26
status: CANONICAL — the per-object-type reference. The structural-shapes section is GENERATED from the
  schema (can't drift); the two contracts below are hand-written reference prose.
audience: ontology architects, platform/vendor integrators, AI-agent builders, new contributors
scope: GENERIC — domain-neutral. No business domain, warehouse, or vendor appears here.
companions:
  - ../mac.schema.json          # the authoritative closed schema this is generated from (governs syntax)
  - ../CONFORMANCE.md           # the schema changelog + conformance levels
  - 02_building_blocks.md       # what the six classes ARE (the structures); this shows their YAML shape
  - ../FRAMEWORK.md             # the canonical why + construct definitions
---

# The Shape Reference

> **The readable face of [`mac.schema.json`](../mac.schema.json).** For *what* a concept, class, or layer
> **is**, read [Ch.02 — building blocks](02_building_blocks.md) and [`FRAMEWORK.md`](../FRAMEWORK.md). This
> document is the **reference** for *how a file is shaped* — which keys exist, where they nest, what is
> required, the per-class conditionals, and the `x-` extension rule.
>
> It has two parts. The **two contracts** (naming · reference syntax) are stable hand-written rules that
> apply to every file and that the schema can't express on its own. The **structural shapes** section is
> **generated** from the schema by `tools/gen_schema_shapes.py` — re-run it after any schema change; it is
> always current. Where prose and schema disagree, the schema governs syntax.

## The naming contract (applies to every file)

The fix for namespace collisions (an early version let physical column names double as YAML keys). Two rules:

1. **Ontology identifiers live ONLY in `name:` / `id:` fields** — never as a bareword YAML key.
2. **Physical names** (columns, tables, stored codes) live ONLY as VALUES of designated fields:
   `column:`, `code:`, `grounds_column:`, `eav_attribute:`, `table:`, `key_column:`,
   `column_string_prefix:`.

Corollary a reader/agent can rely on: *a string is an ontology concept iff it's a `name:`/`id:`
value; a string is a physical artifact iff it's a `column:`/`code:`/`table:` value.* A bareword key
is always schema vocabulary — never an entity name, never a data value. (So an enumeration named
after a column becomes `{ name: PaymentMethod, grounds_column: payment_method }`, not a
`payment_method:` key.)

**`rule` is reserved for derivations** (the rules layer — see the `RulesFile` shape below). A data-quality
constraint's description field is `assert:`, never `rule:` — so the word `rule` means one thing only.

## Reference syntax (how one file points at another)

The naming contract says *where* an identifier lives; this says *how a reference addresses it*, so that
references are mechanically resolvable (a checker can verify no reference is orphaned — see
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

<!-- BEGIN GENERATED:schema-shapes (tools/gen_schema_shapes.py — do not edit inside this block) -->

## Structural shapes — generated (schema 0.1.11)

_Generated from [`mac.schema.json`](../mac.schema.json) by `tools/gen_schema_shapes.py`._
_Do not hand-edit between the markers; re-run the generator. The closed vocabulary is
authoritative in the schema — this is its readable, per-object-type face._

### ConceptFile

*discriminator key:* `concept:` · *required:* `metadata`, `concept`

```yaml
metadata:  # REQUIRED
  concept: <…>  # REQUIRED · string
  source: <…>  # REQUIRED · string
  version: <…>  # string
  schema_version: <…>  # REQUIRED · string
  benchmark_baseline: <…>  # string
  status: <…>  # enum: production | draft | prototype
  owner: <…>  # string
  confidence: <…>  # enum: C | I | Q · Trust tier (pluggable scale; default C/I/Q)

concept:  # REQUIRED
  name: <…>  # REQUIRED · string · PascalCase ontology id — the single canonical identifier.
  label: <…>  # string
  german: <…>  # string
  class: <…>  # REQUIRED · enum: entity | event | measure | enumeration | reference | grouping · The closed six-class vocabulary
  definition: <…>  # string
  semantics:  # The SINGLE home for interpretive reasoning facts (FRAMEWORK §5).  # closed: only keys above + x-*
    purpose: <…>  # string
    scope: <…>  # string
    additivity:  # Per-dimension aggregation rule — the footgun-preventer  # open: extra keys allowed
    axis_kinds:  # v0.6: map each aggregation axis (the same axis names used in…  # open: extra keys allowed
    measure_type: <…>  # string · v0.6: the measure's additivity class — a reference to a mac.MeasureType…
    unit: <…>  # string
    null_semantics: <…>  # string
    realized_by:  # one of: object | array · v0.1.9: a single canon binding  # closed: only keys above + x-*
      udf: <…>  # REQUIRED · string · the canon name — canonical form `mac.canon.<name>`, resolved by…
      params:  # the per-concept parameters the canon's signature names  # open: extra keys allowed
      applied_as: <…>  # string · how the canon output is used (subquery_wrapper | predicate_injection |…
      note: <…>  # string
  notes: <…>  # string
  grounded_by: <…>  # string · (enumerations) the discriminator column the values come from.
  related_axis: <…>  # string
  identity:  # The concept's CANONICAL IDENTITY — how it is identified…  # closed: only keys above + x-*
    kind: <…>  # REQUIRED · enum: iso | code | namespace_code | fk_name | composite | resolved_axis | sme_pending · mac.identity_kind.<term> — how the canonical identity is established.
    canonical_key: <…>  # string · the column/expression that IS the identity (omit for resolved_axis /…
    note: <…>  # string

contract:  # string|object · v0.5 NEW core construct (DECISION 0)
  no_probe_guarantee: <…>  # string · What an agent needs ONLY, to use this concept without probing the data;…
  resolution: <…>  # string|object · How identity / name→code resolves (a join, not a probe)
  default_reading: <…>  # string|object · The default aggregation / role / perspective to assume when the…
  answer_rules: <…>  # string|object · Binding constraints on answering — which definition to use, what to…
  axis_handling: <…>  # string|object · How to treat time / orthogonal axes for this concept
  rules:  # v0.1.6: typed behavioural rules (promoted from an applied pilot,…
    - <item>
      id: <…>  # REQUIRED · string · stable dotted id, e.g
      kind: <…>  # REQUIRED · string · a mac.rule_kind.* reference…
      scope: <…>  # string · general | <SOURCE> (general = framework default; else a source fact)
      when: <…>  # string · trigger — the situation the rule applies to
      then: <…>  # string · directive — what to do
      never: <…>  # string · anti-pattern to avoid (optional)
      why: <…>  # string · one-line rationale
      binds: [ ... ]  # the grounded field(s) this rule governs — must be columns of the table…
      enforced_by: <…>  # string · deterministic backstop (e.g
      realized_by:  # one of: object | array · v0.1.9: a single canon binding  # closed: only keys above + x-*
        udf: <…>  # REQUIRED · string · the canon name — canonical form `mac.canon.<name>`, resolved by…
        params:  # the per-concept parameters the canon's signature names  # open: extra keys allowed
        applied_as: <…>  # string · how the canon output is used (subquery_wrapper | predicate_injection |…
        note: <…>  # string
      examples: [ ... ]
      status: <…>  # enum: active | proposed

values:  # v0.5: 'values:' is the SINGLE carrier for an enumeration's value set +…
  closure: <…>  # enum: closed | open | unknown
  closure_why: <…>  # string
  items:  # the value rows — every value has a stable `code`;…
    - <item>
      code: <…>  # REQUIRED · string|number · the canonical value identifier
      label: <…>  # string
      meaning: <…>  # string
      confidence: <…>  # enum: C | I | Q · Trust tier (pluggable scale; default C/I/Q)
      note: <…>  # string
      open_question: <…>  # string
      from: <…>  # string|array · raw source attribute(s) this value was conformed from (a list when…
  unmapped:  # the orphan-quarantine bucket — how raw values outside the closed set…  # open: extra keys allowed
  canonicalization: <…>  # string|object · how raw spellings/duplicates were conformed to the canonical codes.
  realized_by:  # one of: object | array · v0.1.9: a single canon binding  # closed: only keys above + x-*
    udf: <…>  # REQUIRED · string · the canon name — canonical form `mac.canon.<name>`, resolved by…
    params:  # the per-concept parameters the canon's signature names  # open: extra keys allowed
    applied_as: <…>  # string · how the canon output is used (subquery_wrapper | predicate_injection |…
    note: <…>  # string
  aliases:  # v0.1.9 (additive): a CLOSED two-tier alias map: surface tokens → a…  # closed: only keys above + x-*
    scope_key: <…>  # string · the dimension/column whose value selects a Tier-1 scope_relative row…
    realized_by:  # one of: object | array · v0.1.9: a single canon binding  # closed: only keys above + x-*
      udf: <…>  # REQUIRED · string · the canon name — canonical form `mac.canon.<name>`, resolved by…
      params:  # the per-concept parameters the canon's signature names  # open: extra keys allowed
      applied_as: <…>  # string · how the canon output is used (subquery_wrapper | predicate_injection |…
      note: <…>  # string
    map:  # REQUIRED · canonical code → its alias tiers.  # open: extra keys allowed

properties:  # Intrinsic PRIMITIVE attributes — each a cross-class PropertyItem…
  - <item>  # $defs.PropertyItem
    name: <…>  # REQUIRED · string
    type: <…>  # string · the primitive datatype (string/int/date/...)
    required: <…>  # boolean
    doc: <…>  # string
    german: <…>  # string
    value_domain: <…>  # string · (optional) an enumeration this property's values must belong to

attributes:  # EAV / enum-constrained attributes — each an AttributeItem
  - <item>  # $defs.AttributeItem
    name: <…>  # REQUIRED · string
    value_domain: <…>  # string · the enumeration the attribute's values belong to
    eav_attribute: <…>  # string
    column: <…>  # string
    confidence: <…>  # enum: C | I | Q · Trust tier (pluggable scale; default C/I/Q)
    note: <…>  # string

subclasses: [ ... ]  # is-a hierarchy (e.g

instances: [ ... ]

members:  # one of: array | object · v0.5 grouping template — how a grouping rolls up its leaf
  over: <…>  # REQUIRED · string · the leaf concept this groups (region over country, category over…
  member_source:  # open: extra keys allowed
    kind: <…>  # enum: rule | enumerated
    rule: <…>  # string|object · (rule) how membership is computed — a FK / transitive walk
  definitions:  # (enumerated) the named member sets — each an explicit list or a derived…
    - <item>
      namespace: <…>  # string · disambiguator (brand / 'standard' / 'political') — kills same-code…
      code: <…>  # REQUIRED · string|number
      label: <…>  # string
      brand: <…>  # string
      members: [ ... ]  # (explicit) the leaf codes in this set
      derived_rule: <…>  # string|object · (derived) how this set's members are computed
      confidence: <…>  # enum: C | I | Q · Trust tier (pluggable scale; default C/I/Q)
  realized_by:  # one of: object | array · v0.1.9: a single canon binding  # closed: only keys above + x-*
    udf: <…>  # REQUIRED · string · the canon name — canonical form `mac.canon.<name>`, resolved by…
    params:  # the per-concept parameters the canon's signature names  # open: extra keys allowed
    applied_as: <…>  # string · how the canon output is used (subquery_wrapper | predicate_injection |…
    note: <…>  # string

members_resolution: <…>  # string|object

enumerations: [ ... ]  # list of enum sub-blocks when a concept carries several coded columns.

related_concepts: [ ... ]

lifecycle:  # (event class) the state machine: phases group states, in sequence
  phase_sequence: [ ... ]
  phases: [ ... ]
  phase_closure: <…>
  states: <…>
  boundary: <…>
  note: <…>  # string

individual_kpis: [ ... ]  # (measure catalogue) concrete measures, each referencing a measure_type…

derived_by_rule: <…>  # string · marks a concept whose value is produced by a rule; the formula lives in…

grounding:  # Thin pointer to where the data lives (FRAMEWORK §5)
  kind: <…>  # string · Grounding adapter (pluggable): sql_table | api | file | graph.
  sources:  # v0.5 agnostic source binding — the relation(s) this concept queries,…
    - <item>
      relation: <…>  # REQUIRED · string · the table OR view name to query (agnostic — the AI does not care which)
      key: <…>  # string|array · primary / join key column(s)
      columns: [ ... ]  # the columns this concept uses
  table: <…>  # string
  tables: [ ... ]
  primary_tables: [ ... ]
  schema: <…>  # string
  key_column: <…>  # string
  code_column: <…>  # string
  value_filter: <…>  # string
  join_rule: <…>  # string
  discriminator: <…>  # string
  snapshot_rule: <…>  # string
  family_resolution: <…>  # string
  row_count: <…>  # integer|string
  used_in: <…>  # array|string
  serves_from: <…>  # string|array · v0.5 PROMOTED to core: the serving-view .sql file(s) this concept is…
  grain: <…>  # string · v0.5 PROMOTED to core: the committed leaf grain — one row = one ..
  grounds_column: <…>  # string · (naming contract) a physical column name as a VALUE, never a key.
  field_roles:  # v0.1.7: the WHITELIST of grounded columns that carry ontology meaning,…  # open: extra keys allowed
  note: <…>  # string
  notes: <…>  # string
  realized_by:  # one of: object | array · v0.1.9: a single canon binding  # closed: only keys above + x-*
    udf: <…>  # REQUIRED · string · the canon name — canonical form `mac.canon.<name>`, resolved by…
    params:  # the per-concept parameters the canon's signature names  # open: extra keys allowed
    applied_as: <…>  # string · how the canon output is used (subquery_wrapper | predicate_injection |…
    note: <…>  # string

constraints:
  - <item>  # $defs.constraintEntry
    assert: <…>  # REQUIRED · string
    severity: <…>  # enum: ERROR | WARNING | INFORMATIONAL
    machine_executable: <…>  # boolean
    sql_assertion: <…>  # string
    open_question: <…>  # string
    notes: <…>  # string

governance:  # Housekeeping
  owner: <…>  # string
  last_reviewed: <…>  # ISO date — string or a YAML-parsed date
  approval_status: <…>  # string
  change_log:
    - <item>  # $defs.changeLogEntry
      date: <…>  # REQUIRED · ISO date — string or a YAML-parsed date
      change: <…>  # REQUIRED · string
      change_type: <…>  # REQUIRED · enum: CREATION | ADDITION | CORRECTION | REMOVAL | REFACTOR
      by: <…>  # string
      rationale: <…>  # string

open_questions:
  - <item>  # $defs.openQuestion
    id: <…>  # REQUIRED · string
    topic: <…>  # string
    question: <…>  # REQUIRED · string
    status: <…>  # enum: OPEN | PARTIAL | RESOLVED | NEEDS_SME_CONFIRMATION
    owner_for_resolution: <…>  # string
    priority: <…>  # string
    category: <…>  # string
    note: <…>  # string
    cross_references: <…>  # array|string
# x-<name>:  project-specific extension keys allowed anywhere (only sanctioned extension)
```

**Per `concept.class` (conditional shape):**

- **event** — requires `lifecycle`
- **measure** — requires `concept.semantics.additivity`; requires `concept.semantics`
- **enumeration** — requires `values`; forbids `enumerations`
- **grouping** — requires `members`

### RulesFile

*discriminator key:* `rules:` · *required:* `rules`

```yaml
metadata:

governance:  # Housekeeping
  owner: <…>  # string
  last_reviewed: <…>  # ISO date — string or a YAML-parsed date
  approval_status: <…>  # string
  change_log:
    - <item>  # $defs.changeLogEntry
      date: <…>  # REQUIRED · ISO date — string or a YAML-parsed date
      change: <…>  # REQUIRED · string
      change_type: <…>  # REQUIRED · enum: CREATION | ADDITION | CORRECTION | REMOVAL | REFACTOR
      by: <…>  # string
      rationale: <…>  # string

rules:  # REQUIRED
  - <item>
    rule: <…>  # REQUIRED · string
    derives: <…>  # REQUIRED · string
    over: <…>  # REQUIRED · array|string
    logic: <…>  # REQUIRED · string
    render_kind: <…>  # REQUIRED · enum: sql_expression | sql_view | derived_set | spark_udf | spec_only
    template: <…>  # string
    view_ref: <…>  # string
    usage_template: <…>  # string
    requires_join: <…>  # string
    relative_template: <…>  # string
    applied_as: <…>  # string
    closure: <…>
    disambiguation: <…>
    validated_against: <…>  # array|string
    conditions: <…>
    edge_cases: <…>
    inspectable: <…>  # boolean
    confidence: <…>  # enum: C | I | Q · Trust tier (pluggable scale; default C/I/Q)
    cross_references: <…>  # array|string
# x-<name>:  project-specific extension keys allowed anywhere (only sanctioned extension)
```

### EdgesFile

*discriminator key:* `edges:` · *required:* `edges`

```yaml
metadata:

governance:  # Housekeeping
  owner: <…>  # string
  last_reviewed: <…>  # ISO date — string or a YAML-parsed date
  approval_status: <…>  # string
  change_log:
    - <item>  # $defs.changeLogEntry
      date: <…>  # REQUIRED · ISO date — string or a YAML-parsed date
      change: <…>  # REQUIRED · string
      change_type: <…>  # REQUIRED · enum: CREATION | ADDITION | CORRECTION | REMOVAL | REFACTOR
      by: <…>  # string
      rationale: <…>  # string

planned_edges: [ ... ]

edges:  # REQUIRED
  - <item>
    edge_id: <…>  # string
    level: <…>  # REQUIRED · enum: physical | business | federation
    type: <…>  # REQUIRED · string
    endpoints:  # REQUIRED  # closed: only keys above + x-*
      from:  # REQUIRED · v0.1.6: an edge endpoint is a CONCEPT, never a raw view/table  # closed: only keys above + x-*
        source: <…>  # string · the source/ontology this concept belongs to (enables cross-source…
        concept: <…>  # REQUIRED · string · REQUIRED — the concept at this end of the edge.
        ref: <…>  # string · pointer to the concept definition (path#anchor), resolved cross-file by…
        role: <…>  # string · the relationship role/name read from this end (typically on `from`): e.g
        cardinality: <…>  # string
      to:  # REQUIRED · v0.1.6: an edge endpoint is a CONCEPT, never a raw view/table  # closed: only keys above + x-*
        source: <…>  # string · the source/ontology this concept belongs to (enables cross-source…
        concept: <…>  # REQUIRED · string · REQUIRED — the concept at this end of the edge.
        ref: <…>  # string · pointer to the concept definition (path#anchor), resolved cross-file by…
        role: <…>  # string · the relationship role/name read from this end (typically on `from`): e.g
        cardinality: <…>  # string
    join_rule: <…>  # string
    realized_by: <…>
    conditions: <…>
    confidence: <…>  # enum: C | I | Q · Trust tier (pluggable scale; default C/I/Q)
    federation_concept_id: <…>  # string
    notes: <…>  # string
    cross_references: <…>  # array|string
# x-<name>:  project-specific extension keys allowed anywhere (only sanctioned extension)
```

### TableFile

*discriminator key:* `table:` · *required:* `table`, `columns`

```yaml
metadata:

table:  # REQUIRED
  name: <…>  # REQUIRED · string
  schema: <…>  # string
  type: <…>  # enum: table | view | materialized_view
  description: <…>  # string
  confidence: <…>  # enum: C | I | Q · Trust tier (pluggable scale; default C/I/Q)

derived_from:  # (views only) LINEAGE — how this serving relation is built
  sources: [ ... ]  # the raw/upstream relation(s) this view is built from
  serves_from: <…>  # string · the executable DDL file (the SELECT)
  bakes_out: <…>  # string|array · the impurities/workarounds this view dissolves (the homologation payoff)
  notes: <…>  # string

columns:  # REQUIRED
  - <item>
    name: <…>  # REQUIRED · string
    type: <…>  # string
    role: <…>  # REQUIRED · enum: primary_key | foreign_key | value | discriminator | audit | composite_key_part | unknown · v0.5 (DECISION 4): the canonical PHYSICAL role set is kept
    description: <…>  # string
    confidence: <…>  # enum: C | I | Q · Trust tier (pluggable scale; default C/I/Q)
    nullable: <…>  # boolean
    notes: <…>  # string
    enum_ref: <…>  # string

foreign_keys:
  - <item>
    name: <…>  # REQUIRED · string
    from_column: <…>  # REQUIRED · string
    to_table: <…>  # REQUIRED · string
    to_column: <…>  # REQUIRED · string
    enforced: <…>  # boolean
    required: <…>  # boolean
    cardinality_at_to: <…>  # string
    confidence: <…>  # enum: C | I | Q · Trust tier (pluggable scale; default C/I/Q)
    notes: <…>  # string

grounded_by_concepts:
  - <item>
    concept: <…>  # string
    ref: <…>  # string
    role: <…>  # string · descriptive reverse-pointer role (e.g

governance:  # Housekeeping
  owner: <…>  # string
  last_reviewed: <…>  # ISO date — string or a YAML-parsed date
  approval_status: <…>  # string
  change_log:
    - <item>  # $defs.changeLogEntry
      date: <…>  # REQUIRED · ISO date — string or a YAML-parsed date
      change: <…>  # REQUIRED · string
      change_type: <…>  # REQUIRED · enum: CREATION | ADDITION | CORRECTION | REMOVAL | REFACTOR
      by: <…>  # string
      rationale: <…>  # string
# x-<name>:  project-specific extension keys allowed anywhere (only sanctioned extension)
```

### TransformFile

*discriminator key:* `transforms:` · *required:* `produces`, `inputs`

```yaml
metadata:

produces:  # REQUIRED · the single dataset this pipeline emits — the seam the ontology binds to.
  relation: <…>  # REQUIRED · string · the produced dataset relation (schema.name)
  sql_file: <…>  # string · the executable transform (the SELECT / CREATE VIEW) realizing this…
  grain: <…>  # string
  serves_ontology: <…>  # string · pointer to the consuming concept/ontology file (documentation only)

inputs:  # REQUIRED · EVERY relation this transform reads, each typed by `kind`
  - <item>
    relation: <…>  # REQUIRED · string
    kind: <…>  # enum: raw_source | dataset | authored_seed | external · raw_source = an observed upstream table (described under data/sources/)…
    role: <…>  # string · free-text role of this input in the transform (not a controlled…
    descriptor: <…>  # string · pointer to the input's schema-of-record (data/sources/<name>.yaml for…
    consumes:  # optional map: input column -> the transform id (or rule) that reads it  # open: extra keys allowed
    note: <…>  # string

transforms:  # the ordered cleansing steps, each dissolving ONE impurity so it never…
  - <item>
    id: <…>  # REQUIRED · string
    impurity_class: <…>  # string
    raw_defect: <…>  # string
    rule: <…>  # string
    sql: <…>  # string
    establishes_guarantee: <…>  # string · the clean fact the consuming ontology then inherits (and must not…
    status: <…>  # string
    note: <…>  # string

open_transforms: [ ... ]  # impurities KNOWN but NOT yet dissolved — carried, not hidden (the…

governance:  # Housekeeping
  owner: <…>  # string
  last_reviewed: <…>  # ISO date — string or a YAML-parsed date
  approval_status: <…>  # string
  change_log:
    - <item>  # $defs.changeLogEntry
      date: <…>  # REQUIRED · ISO date — string or a YAML-parsed date
      change: <…>  # REQUIRED · string
      change_type: <…>  # REQUIRED · enum: CREATION | ADDITION | CORRECTION | REMOVAL | REFACTOR
      by: <…>  # string
      rationale: <…>  # string
# x-<name>:  project-specific extension keys allowed anywhere (only sanctioned extension)
```

<!-- END GENERATED:schema-shapes -->
