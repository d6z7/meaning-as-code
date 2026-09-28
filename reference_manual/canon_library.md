---
title: The canon library — what makes a declaration executable
status: 19 defined, 19 described, 3 implemented — check_canon_documented.py holds the three lists together
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

## Three lists, which must agree

| list | where | count |
|---|---|---|
| **defined** | `mac_vocabulary.yaml#canon.members` | 19 |
| **described** | `reference_manual/canon/*.md` | 19 |
| **implemented** | `mac_runtime.canon.IMPLEMENTED` | **3** |

`tools/check_canon_documented.py` compares them. On 2026-09-25 no two agreed:
`resolve_by_register` — which every name resolution in every bundle goes through, declared by eight
concepts — was **implemented and undocumented**, while ten canons nothing implements had pages. Two
pages described canons the vocabulary did not define.

> **Only three canons do anything today.** A declaration naming any of the other sixteen parses,
> passes every gate, and has no effect. `check_canon_implemented.py` is what makes that visible;
> before it existed, four concepts bound `grouping_from_register` and silently got nothing.

## The nineteen

<!-- BEGIN GENERATED:vocabulary-terms:canon (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> The deterministic UDFs a concept's realized_by binds to; logic in tools/canon/.

*`mac.canon` · 19 terms · open — a bundle may add its own*

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
| `params_from` | label: concept.label · null_is_real: concept.semantics.null_semantics |

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
