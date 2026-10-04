---
title: The canon library — what makes a declaration executable
status: 21 defined, 20 described, 18 implemented (measured 2026-10-04) — check_canon_documented.py holds the three lists together
audience: ontology authors binding realized_by; anyone implementing a canon
---

# The canon library

**A canon is the executable half of a declaration.** A concept states a fact in its own terms and
names a canon to realize it; the canon holds the logic **once**, for every concept that binds it.

```yaml
realized_by:
  udf: mac.canon.resolve_by_register
  params: { code: Country, register: …, search: search_key }
```

The concept supplies **parameters only**. It never restates the logic — that is the whole point, and
the reason a rule written once can serve a dozen bundles.

## What a canon is FOR — the determinism seam

The sentence above says what a canon *is*. This says why the mechanism exists, which is the question an
author actually arrives with.

`the_content_model.md` §4 states the problem a canon answers: **determinism is not a property of the
pipeline, it is a property of the content, slot by slot.** A slot whose meaning is prose is read by a
model, and two models may read the same prose differently — so the non-determinism is in the content,
not in the engine. A slot with a canon is **run**, not read.

That is the whole of it, and `mac.schema.json#$defs/canonBinding` says it in one line: *present → the
slot is canon-backed (deterministic, run not read); absent → the slot's prose is model-interpreted.*

So a canon is not an optimisation and not a helper library. It is **the one move that takes a slot out
of interpretation**, and the ratio of behaviour-bearing slots that have one to behaviour-bearing slots
that could is the measure of how much of an ontology is deterministic at all. `canonBinding` calls that
ratio the determinism-coverage seam.

**The prose does not leave.** A bound slot keeps its sentence beside the binding — the human twin
(`AUTHORING` A9). The canon makes the behaviour reproducible; the prose is still how a person checks
that the behaviour is the one they meant. A canon with no prose beside it is executable and
unreviewable.

## When you would reach for one

Three things have to be true together. If one is missing, a canon is the wrong shape:

1. **The decision recurs.** The same question is asked of more than one concept — "which rows does this
   have", "what does this name resolve to", "may this be summed along that axis". A behaviour needed by
   exactly one concept does not want a canon; it wants a rule on that concept.
2. **Two readers could disagree.** The prose admits more than one defensible reading, and the difference
   shows up in an answer rather than in an error. This is the test that matters: if every reader would
   do the same thing, prose is already deterministic and a canon buys nothing.
3. **The difference between concepts is PARAMETERS, not logic.** A concept binding a canon supplies only
   what is particular to it — which column, which register, which code. The moment two concepts would
   need the canon to behave differently, it is two canons or none.

## How to bind one

A behaviour-bearing slot names the canon and passes its parameters. Seven slots admit a binding, which
is the whole surface: `grounding`, `contract.rules`, `enumerationValues`, `groupingMembers`,
`aliasBlock`, `relationAliasBlock`, and an edge in `EdgesFile.edges`.

A LIST composes, in order — the schema admits `canonRef` or an array of them, and composition is the
normal case rather than an advanced one: a slot often needs a population chosen and then a ratio taken.
Each entry carries its own `params`.

```yaml
realized_by:
  - udf: mac.canon.population_select
    params: { population: active }
  - udf: mac.canon.ratio_select
    params: { numerator: …, denominator: … }
```

What the concept must NOT do is restate the logic. The canon holds it once; a concept that explains
*how* beside a binding has created a second home for the behaviour, and the two will disagree.

## Where the logic lives, today

An implementer needs this and the vocabulary's one-line definition does not say it. MEASURED 2026-10-04:
the canon logic has **two homes**, and nine canons exist in both.

| home | canons | who calls it |
|---|---|---|
| `mac-platform/.../mac_runtime/canons/` + `planner/` + `resolver/` | 15 modules, plus canons implemented inside the planner and resolver | the runtime, and `mac_runtime.canon.IMPLEMENTED` reports it |
| `meaning-as-code/tools/canon/` | 12, whose own docstring calls it "the EXECUTABLE single-home of the canon logic" | this repository's tools |

Both cannot be the single home. In both: `additivity_guard`, `ambiguity_gate`, `axis_default`,
`closure_anomaly_check`, `composite_key_guard`, `densify`, `exclusion_filter`, `hierarchy_rollup`,
`scoped_latest`. Which one is authoritative is an operator ruling and is not settled here — so until it
is, read `mac_runtime.canon.IMPLEMENTED` for what actually runs when a question is answered, and treat
this repository's copy as the one the framework's own tools use.

Note also that a canon's implementation need not be a file named after it: `IMPLEMENTED` maps each name
to WHERE its logic is, and three of them live in the planner and the resolver rather than in `canons/`.
Read the map, not the directory.

## Three lists, which must agree

| list | where | count |
|---|---|---|
| **defined** | `mac_vocabulary.yaml#canon.members` | 20 |
| **described** | `reference_manual/canon/*.md` | 20 |
| **implemented** | `mac_runtime.canon.IMPLEMENTED` | **17** |

`tools/check_canon_documented.py` compares them. On 2026-09-25 no two agreed:
`resolve_by_register` — which every name resolution in every bundle goes through, declared by eight
concepts — was **implemented and undocumented**, while ten canons nothing implements had pages. Two
pages described canons the vocabulary did not define.

> **Seventeen of twenty do something today**, and on 2026-09-25 it was three. A declaration naming
> one of the remaining three parses, passes every gate, and has no effect.
> `check_canon_implemented.py` is what makes that visible; before it existed, four concepts bound
> `grouping_from_register` and silently got nothing. **Check before you bind** — DNA P1: a canon
> declared and not implemented is a rule that reads as enforced and is not.

## The twenty

<!-- BEGIN GENERATED:vocabulary-terms:canon (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> The deterministic UDFs a concept's realized_by binds to; logic in tools/canon/.

*`mac.canon` · 21 terms · open — a bundle may add its own*

#### `mac.canon.composite_key_guard`

reject a parent-scoped code used without its scope columns

| field | value |
|---|---|
| `serves` | context_dependent_meaning |
| `needs_sqlglot` | True |

#### `mac.canon.array_membership_guard`

reject equality on a MANY-valued column; membership is the only correct test

| field | value |
|---|---|
| `serves` | multivalued_bridge |
| `needs_sqlglot` | True |

#### `mac.canon.opaque_code_guard`

reject reading meaning out of an opaque code's embedded structure; resolve by name instead

| field | value |
|---|---|
| `serves` | contaminated_code |
| `needs_sqlglot` | True |

#### `mac.canon.refuse_measure_no_row`

RENDER canon — a measure has no row for the resolved scope; emit the refusal clauses

| field | value |
|---|---|
| `serves` | exclusion_no_evidence |
| `needs_sqlglot` | False |
| `params_from` | label: concept.label |

#### `mac.canon.resolve_by_register`

RENDER canon — resolve a NAME to a CODE through a declared register, never through the display
label. MEASURED on <domain>/<dataset>: four rules said this with different nouns, and each
existed because the register carries a human-readable column that LOOKS like an identity
(market_label_raw = HOME for the home country; a product's display name where the search key is
name_key). params: thing, code, register, search, display_label, scope, fact_join, served_view.

| field | value |
|---|---|
| `serves` | contaminated_code |
| `needs_sqlglot` | False |

#### `mac.canon.refuse_unresolvable_name`

RENDER canon — a name does not resolve to a code; emit the refusal clauses

| field | value |
|---|---|
| `serves` | exclusion_no_evidence |
| `needs_sqlglot` | False |
| `params_from` | thing: concept.label · code: concept.identity.canonical_key |

#### `mac.canon.additivity_guard`

reject SUM of a measure across a non-additive axis

| field | value |
|---|---|
| `serves` | semi_additive_balance |
| `needs_sqlglot` | True |

#### `mac.canon.axis_default`

inject a safe default for an unconstrained orthogonal axis

| field | value |
|---|---|
| `serves` | tracking_vintage |
| `needs_sqlglot` | True |

#### `mac.canon.exclusion_filter`

inject an exclusion predicate for reliably-identifiable junk (bake)

| field | value |
|---|---|
| `serves` | impurity_disposition |
| `needs_sqlglot` | True |

#### `mac.canon.snapshot_collapse`

collapse a versioned relation to current / as-of one row per key; the partition is a COMPOSITE
column list and the order accepts a tie-break (vintage, then written-at)

| field | value |
|---|---|
| `serves` | scd_type_2 |
| `needs_sqlglot` | False |
| `params_from` | natural_key: profile#identity_evidence.key |

#### `mac.canon.closure_anomaly_check`

for a closed value set, the query that finds out-of-set values (else None)

| field | value |
|---|---|
| `serves` | explicit_closure |
| `needs_sqlglot` | False |

#### `mac.canon.scoped_latest`

MAX(date) over a scoped subset, not the whole table

| field | value |
|---|---|
| `serves` | tracking_vintage |
| `needs_sqlglot` | False |

#### `mac.canon.hierarchy_rollup`

recursive-CTE subtree: a node and all its descendants

| field | value |
|---|---|
| `serves` | recursive_hierarchy |
| `needs_sqlglot` | False |

#### `mac.canon.densify`

LEFT JOIN a sparse fact onto the full grid, COALESCE 0 (genuine-zero)

| field | value |
|---|---|
| `serves` | absence_semantics |
| `needs_sqlglot` | False |

#### `mac.canon.ambiguity_gate`

resolve a single/pinned candidate, else ASK (⊥) — never guess

| field | value |
|---|---|
| `serves` | competing_definitions |
| `needs_sqlglot` | False |

#### `mac.canon.population_select`

select WHICH ROWS a concept has: named populations as structured predicates (all: of {column,
op, value|values} over is_null/is_not_null/eq/ne/in/not_in, every value BOUND — never SQL text,
which assert_bound_params_only refuses) and one optional `default`. THE CONDITION IS THE RULE'S
OWN `binds`, not a param: a question constraining a bound column is making its own statement
about that state, so the default steps aside and the answer discloses it. One rule is one AXIS.
A name is matched EXACTLY, never fuzzily. The unaskable DOMAIN stays on grounding.value_filter;
a predicate a question can ask the other side of does NOT. The trigger for a business state that
is a column combination rather than a stored value — `closed` IS `close_date IS NOT NULL`.

| field | value |
|---|---|
| `serves` | competing_definitions |
| `needs_sqlglot` | False |

#### `mac.canon.ratio_select`

WHICH DENOMINATOR A NAMED RATIO DIVIDES BY -- the twin of population_select, which says which
ROWS a concept has. Both map a word a reader says to a declared body, and both were prose.
`params.ratios` is a name -> {denominator, surfaces} map with an OPTIONAL `default`; the
numerator is the rule's own `binds`, as it is for a population. A name is matched EXACTLY over
its declared `surfaces`, case/space/underscore folded and nothing more -- no string distance,
for the reason population_select records. TWO RATIOS AND NO DEFAULT IS A DECLARATION: a question
naming neither must ASK, with both names offered, which is the resolution ladder's third rung.
MEASURED on the worked bundle 2026-10-02: Discount's percentage is over GrossRevenue (5.93%) and
not NetRevenue (6.30%) on the same money; Margin names TWO -- margin % over NetRevenue (55.91%)
and markup % over SalesCost (126.79%), a factor of 2.27 on the same profit. `Intent.denominator`
has always carried the choice and the planner has always read it, so a model's guess went
straight through and nothing declared which was meant.

#### `mac.canon.alias_resolve`

resolve a surface token (scope_relative tier first, then multilingual) to a canonical value
code; >1 hit or unknown-in-closed-set -> ASK; never a silent bind/drop

| field | value |
|---|---|
| `serves` | competing_definitions |
| `needs_sqlglot` | False |

#### `mac.canon.relation_alias_resolve`

resolve a surface token against a business edge's relationAliasBlock.multilingual surfaces to
that relation (the edge_id) as the routing target; >1 hit or unknown -> ASK; never a silent
bind/drop. The token->relation twin of alias_resolve (token->value code)

| field | value |
|---|---|
| `serves` | competing_definitions |
| `needs_sqlglot` | False |

#### `mac.canon.enum_from_register`

realize a closed enumeration's value set by reading a PINNED register (a lookup artifact)
instead of inline values.items — the value domain IS the register's `code` column
(params.register names the artifact, params.key_column names the code column, default 'code').
Declarative registry entry (like alias_resolve): a consumer sources the value set from the
register; the concept omits items and supplies only the register pointer. The register-sourced
twin of an inline closed enumeration.

| field | value |
|---|---|
| `serves` | explicit_closure |
| `needs_sqlglot` | False |

#### `mac.canon.grouping_from_register`

realize a grouping's enumerated member sets by reading an EXPLODED register (one row per
(group_key, member)) and RE-AGGREGATING it by the group key into nested member arrays, instead
of inline members.definitions. The nested-membership twin of enum_from_register (which sources a
FLAT value set): params.register names the artifact, params.group_key names the identity
column(s) each set is keyed by (a string or a list for a composite key), params.member_col names
the column collected into each set's member array, and params.carry lists the per-group scalar
columns carried through onto each set (label / count / flags). Declarative registry entry (like
alias_resolve / enum_from_register): a consumer re-aggregates the member sets from the register;
the concept omits members.definitions and supplies only the register pointer. The
register-sourced twin of an inline enumerated grouping.

| field | value |
|---|---|
| `serves` | explicit_closure |
| `needs_sqlglot` | False |
<!-- END GENERATED:vocabulary-terms:canon -->

## Reading the table

Each member carries two fields, and both are useful before you read a page:

- **`serves`** names the [pattern](patterns/) the canon realizes. That is the cross-reference
  between the two halves of this manual — a pattern describes the constellation you were handed, a
  canon is what makes the response deterministic. It is data, not prose, so it cannot drift.
- **`needs_sqlglot`** says whether enforcing it requires parsing SQL. A canon that must inspect a
  query — `composite_key_guard`, `additivity_guard` — is a **guard**: it catches, it does not
  rewrite. One that does not, usually builds something instead.

## Implemented, and what they carry

| canon | what depends on it |
|---|---|
| [`resolve_by_register`](canon/resolve_by_register.md) | every name→code resolution in every bundle; 8 concepts in contoso |
| [`enum_from_register`](canon/enum_from_register.md) | every closed value domain; 4 concepts |
| [`snapshot_collapse`](canon/snapshot_collapse.md) | SCD-2 collapse to one row per key at a date |

## Declared in a bundle and NOT implemented

| canon | declared by | consequence |
|---|---|---|
| [`grouping_from_register`](canon/grouping_from_register.md) | 4 contoso concepts | nothing; and [`resolve_by_register`](canon/resolve_by_register.md) already expresses it |
| [`refuse_measure_no_row`](canon/refuse_measure_no_row.md) | 2 contoso measures | nothing; an empty scope still returns `0` |

## The rest

Thirteen more are defined with reference implementations and no runtime behaviour. They are
honest sketches, not pending work: each shows the shape its pattern needs, and several — 
[`refuse_unresolvable_name`](canon/refuse_unresolvable_name.md) especially — record why the canon
may be the **wrong shape** for the job rather than merely unbuilt.
