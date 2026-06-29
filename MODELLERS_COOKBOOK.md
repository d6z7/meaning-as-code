---
title: The Modeller's Cookbook — decision procedures & recipes for authoring the framework
version: '1.0'
date: 2026-06-07
status: GUIDE — the task-oriented companion to the canon. Routes to FRAMEWORK.md / CONCEPT_SPEC.md; does not restate them.
audience: anyone authoring or reviewing concept/rules/edges/tables YAML under this framework
scope: GENERIC — domain-neutral. All examples are from example_shop_ontology/ (a synthetic online shop). No real domain.
companions:
  - FRAMEWORK.md            # the canon — the why and the complete definition (READ FIRST)
  - CONCEPT_SPEC.md         # the exhaustive key-by-key reference
  - FRAMEWORK_STRUCTURE_MAP.md  # the visual companion
  - example_shop_ontology/  # the worked example every recipe below points at
---

# The Modeller's Cookbook

> **What this is.** A decision-and-recipe manual for the moment you are *authoring* — when you have a
> thing in front of you and need to know *where it goes and how to shape it*. It does not re-define the
> framework; it routes you to the canon. Every rule of truth lives in [FRAMEWORK.md](FRAMEWORK.md) and
> [CONCEPT_SPEC.md](CONCEPT_SPEC.md); this file is the procedure for *applying* them.
>
> **What this is NOT.** Not a tutorial (read the canon + `example_shop_ontology/` first), not a spec
> (every key is in CONCEPT_SPEC.md), and deliberately **not an exhaustive scenario catalogue** — the
> framework is closed (4 layers, 6 classes), so this manual is organised around its *closed primitives*
> and the *recurring decisions* you make against them, not around the open-ended list of domains you
> might model. New domains will surprise you; the decisions you make about them won't.

## How to use it

1. **At a decision point** ("is this a concept or an edge?" "which class?") → jump to the matching
   **Decision** in Part A. Each is a short procedure ending in a verdict.
2. **About to author a thing** ("model an event", "add a derived measure") → jump to the matching
   **Recipe** in Part B. Each is: *when → steps → validate → canon ref → worked diff*.
3. **Reviewing, and something smells off** → scan the **Antipatterns** in Part C. Each is: *smell →
   why it's wrong → fix*.
4. **Always finish at the validator and then at execution** — Part D. A green validator means
   *well-formed*, not *correct* (FRAMEWORK §8).

Section references like *(FW §6)* point at [FRAMEWORK.md](FRAMEWORK.md); *(SPEC §7)* at
[CONCEPT_SPEC.md](CONCEPT_SPEC.md).

---

# Part A — Decision procedures

The five decisions you make over and over. Run them in this order; each assumes the ones above it.

## A1. Is this a *concept*, an *edge*, a *rule*, or *physical*? (which layer)

The single most common confusion. Decide by *what kind of fact it is* (FW §4, SPEC §3):

```
Is the thing you're capturing…

 a relation BETWEEN two named concepts?           → EDGE      (edges.yaml)        → A4 for the level
   ("an Order is placed by a Customer")

 something COMPUTED / derived / a membership set?  → RULE      (rules.yaml)        → Recipe B4
   ("net revenue = gross − refunds"; "which
    regions count as the EU market")

 a physical column / type / foreign key?           → PHYSICAL  (tables/<t>.yaml)
   ("orders.gross_amount is a NUMBER")

 the MEANING / structure / values of one thing?    → CONCEPT   (concepts/…/x.yaml) → A2 for the class
   ("an Order is a stateful purchase event")
```

Two tie-breakers that catch most mistakes:

- **Stored vs computed.** If the value is *already in a column* and you only filter/aggregate it, it
  needs **no rule** — the concept's `grounding:` + the agent's query handle it. A rule exists **only**
  when something is *derived* (FW §6, the cut-line test). Adding rules for stored values is the most
  common rules-layer mistake.
- **Relation vs property.** A link to *another concept* is an **edge**, never a property. A *primitive*
  attribute (string/int/date) intrinsic to the thing is a `properties:` entry on the concept (SPEC §6
  `properties:`). `Order.grossAmount` is a property; "Order → Customer" is an edge.

> **Single-homing law (FW §3.2):** every fact lives in exactly one layer; no layer restates another. If
> you're tempted to write the same fact in two places, one of them is wrong — decide which layer owns it.

## A2. Which of the six *classes*? (FW §5, SPEC §4)

Only for concepts. The vocabulary is **closed** — six values, never invent a seventh. Run top-to-bottom;
take the first that fits:

```
Does it HAPPEN and move through states/phases over time?        → event
A number you sum/average/count (has additivity + unit)?         → measure
A controlled set of allowed coded values (open or closed)?      → enumeration
A roll-up ABOVE the leaf level (region over country)?           → grouping
A keyed dimension that facts point at (lookup)?                 → reference
A structured thing with identity, none of the above?            → entity   (the residual bucket)
```

Disambiguators that actually come up:

- **measure vs reference.** Revenue (a quantity you aggregate) is a `measure`. Product (a thing facts
  *point at*) is a `reference`. If you'd `SUM()` it, measure; if you'd `JOIN` to it, reference.
- **reference vs grouping.** Both are dimensional. `reference` is the **leaf** (Product, Country);
  `grouping` is the **roll-up over leaves** (Category over Product, Region over Country). If it has
  members below it, it's a grouping.
- **enumeration vs reference.** A small fixed code set with no attributes of its own → `enumeration`
  (OrderStatus). A keyed dimension *with attributes/columns* → `reference` (Product). Rule of thumb: if
  it has its own table with multiple columns, reference; if it's a code list, enumeration.
- **entity is the residual**, deliberately narrow (SPEC §4 note: narrower than TypeDB's entity). Reach
  for it only when none of the other five fit. Customer is an entity; most "objects" you'll meet are
  actually reference/measure/event in disguise — check those first.

## A3. Where does an interpretive fact go — `semantics:`, a shape block, or `grounding:`?

Inside a concept, facts still have one home each (SPEC §6):

```
"how to REASON with this" (purpose, scope, unit, additivity, null meaning)  → concept.semantics:
the VALUE SET of an enumeration (+ its closure)                             → values: / value_set:
a primitive attribute of the thing                                          → properties:
the state machine of an event                                              → lifecycle:
WHERE the data physically lives                                            → grounding:
a data-quality CHECK ("this must never be null")                           → constraints: (assert:)
```

Two placement traps (the validator enforces both):

- **`closure:` lives WITH the value set** (`values:`/`value_set:`), **not** in `semantics:` (SPEC §6).
- **`additivity:`, `unit:`, `scope:`, `null_semantics:` live in `semantics:`**, not loose at concept
  top-level.

## A4. Which *edge level* — physical, business, or federation? (FW §7)

```
Same source, a real FK join between tables?              → level: physical    (carries join_rule + realized_by)
Same source, an identity relation at concept level?      → level: business    (references the physical edge via realized_by; never restates the join)
ACROSS sources — "this code = that id, same real thing"? → level: federation  (federation/edges.yaml or aliases.yaml; refers, never carries a raw join)
```

And the thing that is **not** an edge: **containment** (whole→part) and **is-a** hierarchy are *concept
structure*, not edges (FW §7, SPEC §6 `members:`/`subclasses:`). A Category's member Products live on
the Category concept; a measure's subclasses live on the measure. Putting these in `edges.yaml` is a
common error — see C3.

---

# Part B — Recipes

Each recipe: **When** · **Steps** · **Validate** · **Canon** · **Worked diff** (from
`example_shop_ontology/`). Copy the worked file as your starting skeleton.

## B1. Author a new concept (the base recipe every other recipe extends)

**When:** you've run A1 (→ concept) and A2 (→ a class) and need a well-formed file.

**Steps:**
1. Create `concepts/<group>/<name>.yaml`. One concept per file (SPEC §2). `<group>` is a folder for a
   cohesive set (e.g. `order/`, `catalog/`, `finance/`).
2. Fill keys **in canonical order** (SPEC §6): `metadata → concept → ⟨shape block⟩ → grounding →
   constraints → governance → open_questions`.
3. `metadata:` — `concept`, `source`, `version: '1.0'`, `schema_version: '0.1.6'`, `status: draft`,
   `owner`, `confidence:` (start low; it earns its way up via the trust gradient, FW §8).
4. `concept:` — `name:` (PascalCase, the one canonical id), `label:`, `class:`, `definition:` (folded
   `>`, reads as a sentence), and a `semantics:` block with at least `purpose:`.
5. Add the **one shape block** your class needs (A2 → §B2/B3/… below).
6. `grounding:` — a thin pointer (`kind`, `table`/`tables`, `schema`, `key_column`). Column *metadata*
   stays in the tables layer, not here (SPEC §6 grounding).
7. `governance.change_log:` — one `CREATION` entry. Append-only forever after.

**Validate:** run the validator (Part D). **Canon:** SPEC §6; FW §5. **Worked diff:** any file under
`example_shop_ontology/concepts/` — `customer/customer.yaml` is the simplest entity.

## B2. Model an *event* with a lifecycle

**When:** A2 → `event` and the thing moves through states.

**Steps:**
1. B1 with `class: event`.
2. Add a `lifecycle:` block in the **canonical shape — phases group states, in sequence** (FW §5.3,
   SPEC §6 lifecycle; *not* flat states+transitions, which was retired for illegibility):
   - `phase_sequence:` — the ordered macro-phases.
   - `phases:` — each `{ name, meaning, states: [...] }`.
   - `phase_closure:` and a `note:` for the happy path + branch transitions.
3. If the leaf states are themselves a controlled vocabulary, model that vocabulary as a **separate
   `enumeration` concept** (B3) and point at it — don't duplicate the value list (the shop's
   `OrderStatus` is the value vocabulary for `Order`'s lifecycle).
4. Lifecycle is **descriptive** — the framework records the machine, never executes it.

**Validate:** phases present; states grouped under phases; sequence ordered. **Canon:** FW §5.3, SPEC §6.
**Worked diff:** [`concepts/order/order.yaml`](example_shop_ontology/concepts/order/order.yaml) — the
`CHECKOUT → FULFILMENT → CLOSED` machine, with the OrderStatus enumeration carrying the value set.

## B3. Add an *enumeration* (controlled value set)

**When:** A2 → `enumeration` — a fixed/open code list.

**Steps:**
1. B1 with `class: enumeration`.
2. Put the values in `values:` (or `value_set:` if you keep `values:` a clean list). The set carries
   **`closure:`** (`closed` / `open` / `unknown`) **+ `closure_why:`** — and `closure` lives **here, with
   the values**, never in `semantics:` (A3, SPEC §6).
3. Name follows the naming contract: the concept is `{ name: OrderStatus }`; the physical column it comes
   from is a **value** of `grounded_by:` / `grounds_column:`, never a YAML key (SPEC §5). So
   `{ name: PaymentMethod, grounds_column: payment_method }` — *not* a `payment_method:` key.

**Validate:** `closure` not at top level; naming contract (no physical name as a key). **Canon:** SPEC §4,
§5, §6. **Worked diff:** `concepts/order/order_status.yaml`.

## B4. Add a *derived measure* / a rule

**When:** A1 → rule — the thing is *computed* (not a stored column you just aggregate).

**Steps:**
1. In `rules.yaml`, add an entry with `rule:` (the id — the reserved word, SPEC §5), `derives:` (the
   concept it produces), `over:` (concepts it reads), and plain-language `logic:` (**always**).
2. Choose `render_kind:` (SPEC §7): `sql_expression` (snippet injected at query time) ·
   `derived_set` (a membership predicate) · `sql_view` (a pre-deposited view, via `view_ref:`) ·
   `spec_only` (agent generates from `logic:`).
3. Write the `template:` as **Jinja that shapes STRUCTURE only**. Values that come from the user's
   question are **bound as SQL params (`?`)**, never string-interpolated — this is the hard security rule
   (FW §6). `{% if period_start %}AND o.placed_at BETWEEN ? AND ?{% endif %}` is correct; interpolating
   a literal is SQL injection.
4. List `validated_against:` (the tables the SQL touches) so the validator can check the columns, and
   `conditions:`/`edge_cases:` for caveats.
5. On the concept it derives, mark it (e.g. `derived_by_rule: net_revenue`) — don't restate the formula
   on the concept (single-homing).

**Validate:** legal `render_kind` + payload; params bound not interpolated; `validated_against` columns
exist. **Canon:** FW §6, SPEC §7. **Worked diff:**
[`rules.yaml` → `net_revenue`](example_shop_ontology/rules.yaml) — gross − refunds, paid-only, period
bound as params.

## B5. Connect two concepts with an *edge*

**When:** A1 → edge. Run A4 for the level first.

**Steps:**
1. In `edges.yaml` (or `federation/edges.yaml` for cross-source), add an entry with the canonical edge
   shape: `edge_id` · `level` · `type` · `endpoints{from,to}` · `join_rule` · `realized_by`.
2. Each endpoint: `{ source, concept, ref: "concepts/…/x.yaml#concept", role, cardinality }`. Set
   cardinality on **both** ends (e.g. customer `0..N` ↔ order `1`).
3. For `level: physical`, `join_rule:` is the actual ON clause and `realized_by:` points at the FK in the
   tables layer — **don't restate the join** anywhere else.
4. For `level: business`/`federation`, **refer** to the physical edge / alias; never carry a raw join.

**Validate:** level/type legal; endpoints resolve; cardinality on both ends. **Canon:** FW §7. **Worked
diff:** [`edges.yaml`](example_shop_ontology/edges.yaml) — `order__placed_by__customer` and
`product__belongs_to__category`.

## B6. Ground a concept to physical data

**When:** any concept (do it as part of B1, but here's the focused recipe).

**Steps:**
1. On the concept, `grounding:` is a **thin pointer** (SPEC §6 grounding): `kind:` (`sql_table` — the
   adapter is pluggable, FW §10), `table:`/`tables:`, `schema:`, `key_column:`/`code_column:`,
   `value_filter:` (to select this concept's rows from a shared/EAV table), `join_rule:` /
   `discriminator:` / `snapshot_rule:` as needed.
2. The **column types, FKs, volumetrics** live in `tables/<table>.yaml` (the Physical layer), *not* in
   grounding. Grounding says *which* table/columns; the tables layer describes them.
3. Naming contract: physical names are **values** (`table:`, `column:`, `key_column:`), never keys.

**Validate:** referenced table/columns exist in the tables layer; naming contract. **Canon:** SPEC §6
grounding + §5. **Worked diff:** the `grounding:` block in `concepts/order/order.yaml` + the matching
[`tables/orders.yaml`](example_shop_ontology/tables/orders.yaml).

## B7. Bridge two sources (federation)

**When:** "this source's X denotes the same real-world thing as that source's Y."

**Steps:**
1. This is an **edge at `level: federation`** (A4), homed in `federation/edges.yaml` or an
   `aliases.yaml` — **not** in either source's `edges.yaml`.
2. It **refers** to the two concepts and asserts the identity/mapping; it does **not** carry a raw join
   (the sources may not even be co-located). Use `realized_by:`-style references, not an ON clause.
3. Federation arity is a project plug (FW §10): a single-source project has none; a federated one names
   N sources.

**Validate:** level `federation`; lives in the federation file; no raw join. **Canon:** FW §7, §10.
**Worked diff:** the shop example is single-source, so this is specified-but-unexercised here — the
*shape* mirrors B5 with `level: federation`. (Your application's `federation/` directory is the live
example.)

## B8. Handle a dirty enumeration / data impurity (rebadges, "Rest" buckets, missing attributes)

**When:** the real values don't match the published taxonomy — catch-all buckets, variants that fold
oddly, an attribute that's simply absent in one slice.

**Steps (within the current framework):**
1. **Record it first.** Add an `open_questions:` entry on the affected concept (SPEC §6) — `id`, `topic`,
   the interrogative `question` with options, `status: OPEN`, `owner_for_resolution`. Don't silently
   "fix" data in the model.
2. **If it's a value-set fact** (a known catch-all value, an open set), capture it honestly:
   `closure: open` + `closure_why:` explaining the impurity, rather than pretending the set is closed.
3. **If it's a derivation** (normalising/remapping values), it's a **rule** (B4), not a concept edit —
   `render_kind: derived_set` or `sql_expression`, with the mapping in `logic:` and `validated_against:`.
4. **If an attribute is missing in one source**, that's a `scope:` fact in `semantics:` (coverage
   asymmetry — "applies to A, not to B"), plus an `open_question` if resolution is pending.

> **Scope note / honest limit.** A *dedicated curation layer* (Palantir-style raw→curated→object
> normalisation) is **not** a framework primitive today — it's deliberately deferred until an impurity
> *catalogue* is large enough to design the abstraction from pattern, rather than from two or three
> cases. Until then, impurities are handled with the tools above (open_questions + rules + scope/closure
> honesty). This is a known gap, not an oversight. *(Applied note: a consuming application may track this
> as an internal "data-curation layer" backlog item — but that belongs to the application, not this framework.)*

**Validate:** open_question well-formed; any remap is a rule, not a concept edit; closure honest.
**Canon:** SPEC §6 (open_questions, scope, closure), §7 (rules).

---

# Part C — Antipatterns (smells & fixes)

What to look for in review. Each: **smell → why wrong → fix.**

## C1. The same fact in two layers
**Smell:** a net-revenue formula written both on the `Revenue` concept and in `rules.yaml`; a join
written both in an edge `join_rule:` and restated on a concept. **Why wrong:** violates single-homing
(FW §3.2) — diffs lie, drift becomes invisible. **Fix:** decide the owning layer (A1) and reference it
from the other; delete the copy.

## C2. A rule for a stored value
**Smell:** a `rules.yaml` entry whose `logic:` is "select column X where Y" with no derivation. **Why
wrong:** stored values that are merely filtered/aggregated need **no** rule (FW §6) — the rules layer is
for *computed* things only. **Fix:** delete the rule; let the concept's `grounding:` + the agent's query
handle it.

## C3. A relation (or containment) modelled as a property — or containment modelled as an edge
**Smell (a):** a concept has a property whose value is *another concept*. **Fix:** it's an edge (A1, B5).
**Smell (b):** a whole→part membership or is-a hierarchy sitting in `edges.yaml`. **Why wrong:**
containment and is-a are *concept structure*, not edges (A4, FW §7). **Fix:** move to `members:` /
`subclasses:` on the concept.

## C4. A physical name used as a YAML key
**Smell:** `payment_method:` as a key; a column name doubling as an identifier. **Why wrong:** breaks the
naming contract (SPEC §5) — a reader can no longer tell "concept or column?" by position. **Fix:**
make the identifier a `name:` value and the physical name a `grounds_column:`/`column:` value.

## C5. `closure` / `additivity` / `unit` in the wrong home
**Smell:** `closure:` in `semantics:`; `additivity:` loose at concept top-level. **Why wrong:** placement
is contractual and validator-enforced (A3, SPEC §6). **Fix:** `closure` → with the value set;
`additivity`/`unit`/`scope`/`null_semantics` → into `semantics:`.

## C6. Exploding rule-count (the litmus-test smell)
**Smell:** the rules layer fills with special-cases — "except when role = Group", "but only the latest
snapshot", per-slice overrides. **Why wrong:** this is **the ontology refusing to sit cleanly on the
data** — usually *scar tissue around a physical-model defect*, not genuine business logic (FW §8 trust
gradient; the determinism/quality argument). A snapshot-collapse wrapper that exists only because a view
stores multiple snapshots per cell is the canonical example. **Fix:** don't keep patching the ontology —
**re-model the physical layer** until the special-case rules can be dropped. A rising exception-count is
a *failing test for the data model*. (One genuine foundational rule — e.g. a real snapshot-latest
collapse the warehouse forces on you — is fine; a *pile* of them is the signal.)

## C7. "Validates cleanly" treated as "correct"
**Smell:** a concept marked `confidence: C` with a green validator but never run against data. **Why
wrong:** structure ≠ correctness (FW §3.7, §8) — untested grounding can name a column that doesn't exist
or a label that means something else. **Fix:** keep confidence low until **execution validation** (Part
D); a discrepancy becomes a recorded finding that corrects the model.

## C8. Inventing a seventh class (or reviving the old `type:` zoo)
**Smell:** `class: hierarchical_grouping` / `enumerated_classification` / any value not in the six. **Why
wrong:** the vocabulary is closed (FW §5, SPEC §4); the old `type:` zoo was deliberately retired. **Fix:**
map to one of the six (SPEC §4 note gives the mapping). If you genuinely can't, that's a framework-level
question for an issue/PR — not a local invention.

## C9. Two orthogonal axes modelled as one
**Smell:** one concept conflating two independent dimensions (e.g. a tracking variant *and* a reporting
cycle). **Why wrong:** the cross-product is real; conflating inverts the model (SPEC §8 — a recurring
footgun). **Fix:** model each axis as its own concept; document the cross-product. Execution validation
reliably catches the inversion if it slips through.

---

# Part D — Always finish here: validate, then execute

Two gates, in order — neither is optional (FW §8, SPEC §9):

1. **Structural validation.** Run the validator:
   ```
   python tools/validate_schema.py <path-to-your-source-or-file>
   ```
   It enforces: `class:` present · interpretive keys in `semantics:` · `closure` not top-level ·
   `constraints[]` use `assert:` not `rule:` · rules have a legal `render_kind` + payload · edge
   level/type legality · naming-contract spot-checks. **0 errors = well-formed.** Not "correct."

2. **Execution validation.** Run the query the model implies against the live warehouse/graph and
   sanity-check the number. When the model says X and the data says Y, that is **the loop working**:
   record a **finding** (see `example_shop_ontology/recon_findings.md` for the shape), fix the model,
   move on. A fact is only trustworthy at the right-hand end of the trust gradient — *authored →
   structurally valid → execution-validated → expert-confirmed* (FW §8). Promote `confidence:`
   accordingly.

> The discipline **is** the product (FW §9). A YAML ontology with the contracts unenforced rots into the
> mess it replaced. These two gates are how the contracts stay real.

---

## Quick index — symptom → where to go

| You are… | Go to |
| --- | --- |
| unsure which layer a fact belongs to | A1 |
| unsure which of the 6 classes | A2 |
| unsure where an interpretive fact goes inside a concept | A3 |
| unsure which edge level | A4 |
| creating any concept | B1 |
| modelling something with states | B2 (event + lifecycle) |
| capturing a code list | B3 (enumeration) |
| capturing a computed/derived value | B4 (rule) |
| linking two concepts | B5 (edge) |
| pointing a concept at its table | B6 (grounding) |
| linking across sources | B7 (federation) |
| facing messy/impure data | B8 (+ the curation-layer scope note) |
| reviewing and something smells off | Part C |
| done authoring | Part D (validate → execute) |

*All recipes are grounded in `example_shop_ontology/` (synthetic shop). The canon — every definition and
every key — is [FRAMEWORK.md](FRAMEWORK.md) and [CONCEPT_SPEC.md](CONCEPT_SPEC.md); this cookbook only
tells you how to apply them.*
