---
title: "Ch.03 — The Pattern Reference"
part_of: reference_manual
status: prototyped
scope: GENERIC — domain-neutral. Examples from example_shop_ontology/.
---

# Ch.03 — The Pattern Reference  🔧 *prototyped*

## 3.0 What this chapter is, and why it can be complete

Chapters 01–02 tell you the *language*. This chapter tells you the *idioms*: you have a recognizable shape
in front of you — a many-to-many with attributes, a dimension that keeps history, a code list that turns
out to be open-ended — and you need the canonical way to say it here.

Every entry below is a **Question → Answer** pair, where the question is a fact the data structurally cannot
contain (see the **anatomy of a pattern**, [Ch.00 §0.3](00_the_problem.md)). A *constellation* raises a
*latent fact*; a *response*, built from the Chapter-02 constructs, supplies it; the pattern is the bond
between them. This chapter is the periodic table of the **question** particles; Chapter 02 is the periodic
table of the **answer** particles.

**Why an "enumerate everything" catalogue is tractable** (and not hand-waving): the *target* vocabulary is
**closed** (Ch.02 — finite), and the *source* patterns are not invented here but inherited from three
**mature, finite, already-catalogued** traditions:

- **Relational / normalization** — keys, foreign keys, associative entities, supertype/subtype, EAV.
- **Dimensional / data-warehouse (Kimball)** — facts, dimensions, slowly-changing dimensions, bridges,
  degenerate/role-playing/junk dimensions, snapshot vs transaction vs accumulating facts.
- **RDF / OWL / graph** — classes, object/datatype properties, SKOS, `owl:oneOf`, cardinality
  restrictions, `owl:sameAs`, reification.

Coverage is therefore **checkable from both ends**: every established source pattern must route to a
construct in the closed vocabulary, and every construct must be reachable from some pattern. The same
bidirectional argument that justified "exactly six classes" justifies "these are the patterns."

**This first pass covers the novel/non-obvious subset** — the constellations where the expression here is
*not* a one-liner from the cookbook, or where enumerating exposes a genuine gap in the framework. The
"clean" patterns (a 1:N FK is a physical edge; a code list is an enumeration) are deferred; they are
already covered by `../MODELLERS_COOKBOOK.md` Parts A–B.

## 3.1 The entry template

Each pattern lives in its own file under [`patterns/`](patterns/) and has this shape:

```
pattern:        <stable-id>
also_known_as:  [the names the three traditions use]
tradition:      relational | dimensional | rdf | cross-cutting
constellation:  the shape you recognize in the source data (one or two sentences)
prior_art:      how each tradition handles it today — and what that costs you
                  relational:   ...
                  dimensional:  ...
                  rdf:          ...
mac_expression: the canonical way to say it here (the construct(s) + the rule it triggers)
why_better:     the specific advantage for THIS job (single-homing / agent-safety / projectability /
                explicit footgun) — honest, not marketing
projects_to:    { rdf: ..., graph: ..., relational: ... }   # proves it round-trips
antipattern:    the tempting wrong move + the cookbook antipattern id
status:         clean | scattered | gap
canon_ref:      FRAMEWORK / CONCEPT_SPEC / COOKBOOK pointers
```

`status` is the honest self-assessment: **scattered** = the framework handles it but the guidance was never
assembled; **gap** = enumerating it exposed a hole the framework should fill (these feed the framework
backlog, branch → PR).

Each pattern file is laid out in four parts, in this order (the anatomy from [Ch.00 §0.3](00_the_problem.md)):

1. **Initial state — what you're handed.** The raw artifact *before* any meaning is imposed: the table DDL,
   a handful of sample rows, and the one or two sentences on *why that raw state is dangerous*. These are
   the **observations** — start here.
2. **The question, and the answer.** The **latent fact** the data cannot contain, stated as a question, and
   the fact we supply in reply. Two labelled lines — this is the Q→A skeleton made explicit.
3. **The pattern (the structured entry).** The YAML block above — the **response** in full: prior art, the
   MAC expression (the constructs), why it is better, how it projects back.
4. **The footgun, concretely.** A *guess-vs-grounded* vignette: the plausible-wrong query an agent writes
   against the raw state, beside what the model yields.

## 3.2 The constellation enumeration (novel subset — the work-list)

The entries this chapter will contain, grouped by the recognizable shape. ⚠️ = scattered, 🔴 = gap.
Each becomes a file under `patterns/` as it is written; ✅-linked ones exist.

**Identity & structure**
- [`associative_entity`](patterns/associative_entity.md) — M:N relationship that carries its own attributes ⚠️ ✅
- [`polymorphic_association`](patterns/polymorphic_association.md) — a foreign key that may point at one of several types 🔴 → 🟡 ✅ (workaround + [finding F1](FINDINGS.md))
- `supertype_subtype` — table/class inheritance ⚠️
- [`recursive_hierarchy`](patterns/recursive_hierarchy.md) — self-referencing parent key (org chart, category tree) ⚠️ ✅

**History & time**
- [`scd_type_2`](patterns/scd_type_2.md) — a dimension that keeps history as versioned rows ⚠️ ✅
- `scd_type_3` — a dimension that keeps only the prior value in a column ⚠️
- `accumulating_snapshot` — one fact row with several milestone date stamps ⚠️
- `bitemporal` — valid-time vs system-time as two independent axes 🔴

**Aggregation hazards**
- [`semi_additive_balance`](patterns/semi_additive_balance.md) — a level that sums across entities but not across time ⚠️ ✅
- [`tracking_vintage`](patterns/tracking_vintage.md) — actual / plan / budget as an axis orthogonal to the reporting cycle ⚠️ ✅
- `pre_aggregated_summary` — a rollup table that must not be re-aggregated ⚠️

**Dimensional special cases**
- `degenerate_dimension` — a dimension attribute living in the fact (invoice no.) ⚠️
- `role_playing_dimension` — one dimension used in several roles (order date / ship date) ✅→short
- `multivalued_bridge` — a many-valued dimension (an array, or a bridge table) ✅→short
- `junk_dimension` — a grab-bag of low-cardinality flags 🔴

**Open- vs closed-world**
- [`explicit_closure`](patterns/explicit_closure.md) — when a value set is closed, open, or unknown — and why stating it matters ⚠️ ✅
- [`absence_semantics`](patterns/absence_semantics.md) — what a missing row means (true zero vs not-loaded vs untracked) ⚠️ ✅

**The hard semantic constellations (this framework's own additions — no equivalent in Kimball/RDF)**
- [`context_dependent_meaning`](patterns/context_dependent_meaning.md) — the same code means different things under different parents ⚠️ ✅
- `contaminated_code` — an opaque code/prefix that mixes unrelated things ⚠️
- [`competing_definitions`](patterns/competing_definitions.md) — one natural-language term, several defensible definitions ("Europe") ⚠️ ✅
- `required_unspecified` — a required dimension the question left out → ask, never guess ⚠️
- [`impurity_disposition`](patterns/impurity_disposition.md) — bake-into-view vs register-as-caveat vs block-as-needs-expert 🟡 ✅ **(partial:
  the query-time edges are canon-backed; the curation-layer + typed DQ-register *primitives* remain deferred — see `../MODELLERS_COOKBOOK.md` B8)**

> The 🔴 rows are the prize: enumerating systematically is what *surfaces* the framework's holes
> (associative-entity-with-payload, polymorphic/reification, junk dimension, the curation layer). Those
> become framework-backlog items — branch → PR per the binding principle.
