---
title: "Pattern — Competing definitions (one term, several defensible meanings)"
part_of: reference_manual/patterns
status: prototype
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (illustrative shop scenario).
---

# Pattern — Competing definitions

## Initial state — what you're handed

The shop sells across countries. Someone asks for "Europe" — but the `country` table supports several
different, materially-different groupings, and "Europe" is a row in none of them:

```sql
CREATE TABLE country (
  iso2 VARCHAR, name VARCHAR, continent VARCHAR, in_eu BOOLEAN, sales_region VARCHAR
);
```

| iso2 | name | continent | in_eu | sales_region |
| --- | --- | --- | --- | --- |
| DE | Germany | Europe | true | EU |
| NO | Norway | Europe | false | EU |
| GB | United Kingdom | Europe | false | EMEA |

**Why this is dangerous.** "Revenue in Europe" has at least three defensible answers: the **continent**
(DE, NO, GB), the **EU members** (DE only), or the **EU sales region** (DE, NO). Each is a different country
set and a different number. The data supports all three; "Europe" maps to none of them uniquely. Pick one
silently and you have answered a *different question* than may have been asked — with no signal.

## The question, and the answer

> **The question** (what the data can't tell you): *When the question says "Europe", which of the several
> defensible definitions is meant?*
>
> **The answer** (the fact we supply): *It is genuinely ambiguous. The ontology records the **competing
> definitions** as named candidates; the system **detects** the ambiguity (>1 candidate, none pinned) and
> **asks**, offering them — it never silently picks one.*

## The pattern (the structured entry)

```yaml
pattern: competing_definitions
also_known_as: [ambiguous term, disambiguation, polysemy, contested definition]
tradition: cross-cutting   # this framework's addition; ties to RDF's lack of forced disambiguation
constellation: >
  One natural-language term maps to several defensible, materially-different definitions in the data, and no
  single grounding is canonical. The term ("Europe", "active customer", "this quarter") names a CHOICE, not
  a row.
prior_art:
  relational: >
    The analyst picks one join silently. The choice is invisible, undocumented, and inconsistent across
    reports — three dashboards quietly mean three different "Europes".
  dimensional: >
    A "Europe" rollup is hardcoded one way in the cube; another tool hardcodes another. The definition is
    real but buried in tool config, not stated where a reader or agent can see the alternatives.
  rdf: >
    SKOS can hold several concepts, but nothing FORCES a query to disambiguate; the default reading silently
    resolves to one.
mac_expression: >
  A `disambiguation` block listing the competing definitions as NAMED candidates (each a resolution
  predicate), plus an `mac.rule_kind.ambiguity` rule: when the term matches more than one candidate and the
  question pins none, ABSTAIN and ask, offering the candidates. Never silently pick.
why_better: >
  The competing definitions become first-class, named options, and the ambiguity is SURFACED (ask), not
  hidden. Relational/cube resolve silently and inconsistently; here the system refuses to guess and shows
  the alternatives — and once the user pins one, the answer is deterministic.
projects_to:
  rdf: "several skos:Concepts + a note that the term is ambiguous"
  graph: "candidate definition nodes the caller chooses between"
  relational: "several candidate views + a 'which definition?' prompt"
antipattern: >
  Hardcoding one definition; silently defaulting to a 'house' meaning; treating an ambiguous term as
  resolved; offering only one option when several exist.
status: scattered   # mac.rule_kind.ambiguity + the rule `disambiguation` block exist; never named as a pattern
canon_ref: [CONCEPT_SPEC.md §7 (rule disambiguation), mac_vocabulary.yaml (rule_kind.ambiguity), query_rules (ambiguity.ask_dont_guess)]
```

## The determinism border

Per [AUTHORING.md](../AUTHORING.md) A4 — the *detection* of ambiguity is deterministic; only the *choice* is not:

| Behaviour | Kind | How |
| --- | --- | --- |
| Detecting the term matches >1 candidate (or 0) | **canon-backed** | [`ambiguity_gate`](../canon/ambiguity_gate.md) |
| Producing the answer once a definition is pinned | **canon-backed** | the chosen candidate's predicate |
| *Which* definition the user means | **prose-fallback** | the ask — the irreducible interpretation |

```yaml
disambiguation:
  prose: "'Europe' has several defensible definitions; if the question pins none, ask — never guess."
  candidates:
    - { name: continent_europe, predicate: "continent = 'Europe'" }
    - { name: eu_members,       predicate: "in_eu = true" }
    - { name: eu_sales_region,  predicate: "sales_region = 'EU'" }
  realized_by:
    udf: ambiguity_gate
    params: { term: Europe, candidates: [continent_europe, eu_members, eu_sales_region] }
```

The gate makes "ask, don't guess" mechanical: >1 candidate unpinned → `ASK`; exactly one → `RESOLVE`. The
only soft step is the human's choice — which a human would also have had to make.

## The footgun, concretely

```sql
-- Q: "What was revenue in Europe last year?"
-- GUESS (plausible, and wrong): silently pick ONE meaning
SELECT SUM(amount) FROM sales s JOIN country c ON c.iso2 = s.country
WHERE c.continent = 'Europe';     -- one of THREE different answers, chosen with no signal  ❌
```

```text
-- GROUNDED: ambiguity_gate fires (3 candidates, none pinned) → ASK:
--   "Europe could mean: the continent (incl. UK, Norway), EU members (excl. them),
--    or the EU sales region — which?"  → then answer with the chosen candidate's predicate.  ✅
```

The grounded behaviour is the model *refusing to choose for you*. The competing definitions had nowhere to
live in a schema or a cube; here they are named options, and the ambiguity is surfaced, not buried.
