---
title: The canon library — what makes a declaration executable
status: 21 defined, 21 described, 18 implemented (measured 2026-10-05) — check_canon_documented.py holds the three lists together
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

## How a canon runs — YAML to Python to SQL

The question people ask first, and the one the rest of this page assumes: **what actually executes?**

Three actors, one job each.

| | does | sees |
|---|---|---|
| the **model** | proposes *meaning* — tokens only (`Margin`, `markup`, `Germany`, `2024`) | the question |
| **Python** | disposes *structure* — picks columns, denominator, filters, joins, and emits **one SQL statement** | the declarations and those tokens |
| **SQL** | produces the *number* | the rows |

**Python's output is SQL text, not numbers.** A canon is a pure decision: `ratio_select` returns
`Selection(name='markup_percent', denominator='SalesCost')` — a name and a name. Every canon page
states the constraint the same way: *reads no rows*, because no SQL may run to decide which SQL to
write. The planner renders the decision as an aggregate and the warehouse computes it.

Here is one question asked three ways against the same bundle, with the SQL each declaration produced:

```sql
-- "margin %"          → the ratio_select binding on Margin picked NetRevenue
SELECT (SUM(sales_line.margin_amount)) / NULLIF(SUM(sales_line.net_amount), 0)  AS margin_per_netrevenue
FROM sales_line

-- "markup"            → the same rule, the other declared reading
SELECT (SUM(sales_line.margin_amount)) / NULLIF(SUM(sales_line.cost_amount), 0) AS margin_per_salescost
FROM sales_line

-- "price per article" → NetRevenue's binding, denominator UnitsSold
SELECT (SUM(sales_line.net_amount))    / NULLIF(SUM(sales_line.quantity), 0)    AS netrevenue_per_unitssold
FROM sales_line
```

The declaration changed one identifier — `net_amount` / `cost_amount` / `quantity` — and nothing else.
`NULLIF` is not a nicety: a group with no denominator rows is a group the question has no answer for,
and division by zero is an engine error on some engines and infinity on others.

### Why the Python layer costs the same at ten rows or ten billion

It never scales with the data, because it only ever reads two small things: the declarations, and the
intent. **So the aggregate is always pushed into the warehouse** — a mean over ten million rows is
`SUM(...) / NULLIF(SUM(...), 0)` in one statement, never ten million values crossing a process
boundary. Measured on a worked bundle: a share-of-total denominator summed **223 974 lines to
218 814 471.66**, matching a human-approved reference figure to the cent, in a single query.

The only rows Python ever sees are the **result** rows — one per group, after aggregation — which the
presenter formats and attaches disclosures to. Its rule is: no new number.

Two honest qualifications. The canons whose `sqlglot` column below says *yes* take **SQL text** as
input and parse it to catch or rewrite the statement — still no rows, just the query. And `densify` is
the one canon whose job is to add rows; it does that by emitting a grid join in SQL, not in Python.

### Where the single statement is deliberately broken

One shape does not fit one `SELECT`: a share-of-total, whose denominator must ignore the filters its
numerator applies. That becomes a scalar subquery over a second scope — and not a `CASE` inside the
aggregate, because the denominator's expression comes from *its own* concept's definition, so reusing
the text verbatim over a second `FROM` keeps one definition of the number instead of editing it. Still
SQL; still no rows in Python.

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
| **defined** | `mac_vocabulary.yaml#canon.terms` | 21 |
| **described** | `reference_manual/canon/*.md` | 21 |
| **implemented** | `mac_runtime.canon.IMPLEMENTED` | **18** |

`tools/check_canon_documented.py` compares them. On 2026-09-25 no two agreed:
`resolve_by_register` — which every name resolution in every bundle goes through, declared by eight
concepts — was **implemented and undocumented**, while ten canons nothing implements had pages. Two
pages described canons the vocabulary did not define.

> **Seventeen of twenty do something today**, and on 2026-09-25 it was three. A declaration naming
> one of the remaining three parses, passes every gate, and has no effect.
> `check_canon_implemented.py` is what makes that visible; before it existed, four concepts bound
> `grouping_from_register` and silently got nothing. **Check before you bind** — DNA P1: a canon
> declared and not implemented is a rule that reads as enforced and is not.

## The canons, by the pattern they serve

<!-- BEGIN generated: canon tree (tools/gen_canon_index.py) -->

**21 canons across 12 patterns.** The middle layer is not a filing choice: it is each canon's own `serves`, the data pattern it exists for, which also names its page under [`patterns/`](patterns/). A canon changes group by changing that declaration.

| | defined | described | implemented |
|---|---|---|---|
| **count** | 21 | 21 | 18 |
| **read from** | `mac_vocabulary.yaml#canon.terms` | `reference_manual/canon/*.md` | `mac_runtime.canon.IMPLEMENTED` |

`tools/check_canon_documented.py` holds the three together; this table is read from the same places it reads.

### [`competing_definitions`](patterns/competing_definitions.md) &nbsp;·&nbsp; 5

| canon | long form | definition | runtime | sqlglot |
|---|---|---|---|---|
| `alias_resolve` | [page](canon/alias_resolve.md) | [below](#maccanonaliasresolve) | **acts** | no |
| `ambiguity_gate` | [page](canon/ambiguity_gate.md) | [below](#maccanonambiguitygate) | **acts** | no |
| `population_select` | [page](canon/population_select.md) | [below](#maccanonpopulationselect) | **acts** | no |
| `ratio_select` | [page](canon/ratio_select.md) | [below](#maccanonratioselect) | **acts** | no |
| `relation_alias_resolve` | [page](canon/relation_alias_resolve.md) | [below](#maccanonrelationaliasresolve) | declared only | no |

### [`explicit_closure`](patterns/explicit_closure.md) &nbsp;·&nbsp; 3

| canon | long form | definition | runtime | sqlglot |
|---|---|---|---|---|
| `closure_anomaly_check` | [page](canon/closure_anomaly_check.md) | [below](#maccanonclosureanomalycheck) | **acts** | no |
| `enum_from_register` | [page](canon/enum_from_register.md) | [below](#maccanonenumfromregister) | **acts** | no |
| `grouping_from_register` | [page](canon/grouping_from_register.md) | [below](#maccanongroupingfromregister) | declared only | no |

### [`contaminated_code`](patterns/contaminated_code.md) &nbsp;·&nbsp; 2

| canon | long form | definition | runtime | sqlglot |
|---|---|---|---|---|
| `opaque_code_guard` | [page](canon/opaque_code_guard.md) | [below](#maccanonopaquecodeguard) | **acts** | yes |
| `resolve_by_register` | [page](canon/resolve_by_register.md) | [below](#maccanonresolvebyregister) | **acts** | no |

### `exclusion_no_evidence` &nbsp;·&nbsp; 2

| canon | long form | definition | runtime | sqlglot |
|---|---|---|---|---|
| `refuse_measure_no_row` | [page](canon/refuse_measure_no_row.md) | [below](#maccanonrefusemeasurenorow) | declared only | no |
| `refuse_unresolvable_name` | [page](canon/refuse_unresolvable_name.md) | [below](#maccanonrefuseunresolvablename) | **acts** | no |

### [`tracking_vintage`](patterns/tracking_vintage.md) &nbsp;·&nbsp; 2

| canon | long form | definition | runtime | sqlglot |
|---|---|---|---|---|
| `axis_default` | [page](canon/axis_default.md) | [below](#maccanonaxisdefault) | **acts** | yes |
| `scoped_latest` | [page](canon/scoped_latest.md) | [below](#maccanonscopedlatest) | **acts** | no |

### [`absence_semantics`](patterns/absence_semantics.md) &nbsp;·&nbsp; 1

| canon | long form | definition | runtime | sqlglot |
|---|---|---|---|---|
| `densify` | [page](canon/densify.md) | [below](#maccanondensify) | **acts** | no |

### [`context_dependent_meaning`](patterns/context_dependent_meaning.md) &nbsp;·&nbsp; 1

| canon | long form | definition | runtime | sqlglot |
|---|---|---|---|---|
| `composite_key_guard` | [page](canon/composite_key_guard.md) | [below](#maccanoncompositekeyguard) | **acts** | yes |

### [`impurity_disposition`](patterns/impurity_disposition.md) &nbsp;·&nbsp; 1

| canon | long form | definition | runtime | sqlglot |
|---|---|---|---|---|
| `exclusion_filter` | [page](canon/exclusion_filter.md) | [below](#maccanonexclusionfilter) | **acts** | yes |

### [`multivalued_bridge`](patterns/multivalued_bridge.md) &nbsp;·&nbsp; 1

| canon | long form | definition | runtime | sqlglot |
|---|---|---|---|---|
| `array_membership_guard` | [page](canon/array_membership_guard.md) | [below](#maccanonarraymembershipguard) | **acts** | yes |

### [`recursive_hierarchy`](patterns/recursive_hierarchy.md) &nbsp;·&nbsp; 1

| canon | long form | definition | runtime | sqlglot |
|---|---|---|---|---|
| `hierarchy_rollup` | [page](canon/hierarchy_rollup.md) | [below](#maccanonhierarchyrollup) | **acts** | no |

### [`scd_type_2`](patterns/scd_type_2.md) &nbsp;·&nbsp; 1

| canon | long form | definition | runtime | sqlglot |
|---|---|---|---|---|
| `snapshot_collapse` | [page](canon/snapshot_collapse.md) | [below](#maccanonsnapshotcollapse) | **acts** | no |

### [`semi_additive_balance`](patterns/semi_additive_balance.md) &nbsp;·&nbsp; 1

| canon | long form | definition | runtime | sqlglot |
|---|---|---|---|---|
| `additivity_guard` | [page](canon/additivity_guard.md) | [below](#maccanonadditivityguard) | **acts** | yes |

<!-- END generated: canon tree -->

## Every canon, defined

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

| field | value |
|---|---|
| `serves` | competing_definitions |
| `needs_sqlglot` | False |

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

## The three the runtime does not act on

The tree's **runtime** column says `declared only` for three: `grouping_from_register`,
`refuse_measure_no_row` and `relation_alias_resolve`, each listed in
`mac_runtime.canon.KNOWN_UNIMPLEMENTED` with its reason. They are honest sketches, not a backlog —
each shows the shape its pattern needs, and some record why a canon may be the **wrong shape** for
the job rather than merely unbuilt: `grouping_from_register` is unnecessary because
[`resolve_by_register`](canon/resolve_by_register.md) already binds every code a name covers, and
[`relation_alias_resolve`](canon/relation_alias_resolve.md) is not implementable from its own page
because no slot holds the surfaces it would match against.

**A declaration naming one of the three parses, passes every gate, and has no effect** —
`check_canon_implemented.py` is what makes that visible. Check the runtime column before you bind.

## Why these pages are a flat directory and a nested tree

The tree above is a reading structure; on disk `reference_manual/canon/` is flat, one page per canon.
That is deliberate, and measured rather than preferred:

- `check_canon_documented.py` reads `{p.stem for p in pages_dir.glob("*.md")}` — a FLAT glob.
  Subdirectories make it report 0 described against 21 undescribed, and a `canon/README.md` would be
  counted as a canon named "README".
- **28** files outside the generated index link `canon/<name>.md` directly.
- Six of those are in `decisions/PROTOCOL-2026-10-01_rule-engine.md`, a DATED record. Rewriting a
  link inside it would make the record claim a path that did not exist on its date.

So the basenames stay where every existing reference points, and the grouping lives in the
declaration that already carried it. Moving the files is a separate change that must bring the gate's
glob and the 28 links with it.
