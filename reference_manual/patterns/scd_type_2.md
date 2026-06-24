---
title: "Pattern — Slowly-Changing Dimension, Type 2"
part_of: reference_manual/patterns
status: prototype
scope: GENERIC — domain-neutral. Example from example_shop_ontology/.
---

# Pattern — Slowly-Changing Dimension, Type 2

## Initial state — what you're handed

The shop's product dimension keeps history. When the Trail Mug's price changed, the row was **not**
overwritten — a new row was inserted and the old one closed off:

```sql
CREATE TABLE dim_product (
  product_sk  BIGINT,         -- surrogate key: one per VERSION
  product_id  VARCHAR,        -- natural/business key: stable across versions
  name        VARCHAR,
  list_price  DECIMAL(10,2),
  valid_from  DATE,
  valid_to    DATE,           -- '9999-12-31' while current
  is_current  BOOLEAN
);
```

| product_sk | product_id | name | list_price | valid_from | valid_to | is_current |
| --- | --- | --- | --- | --- | --- | --- |
| 5001 | P-100 | Trail Mug | 12.00 | 2025-01-01 | 2026-02-28 | false |
| 5002 | P-100 | Trail Mug | 14.00 | 2026-03-01 | 9999-12-31 | true |

**Why this is dangerous.** One real-world product is now *two rows*. Join `order_line` to `dim_product` on
`product_id` and every line for the Trail Mug matches **both** versions — facts double. "What is the Trail
Mug's price?" has no answer without a date. The history is real and must be kept; the danger is that naïve
use silently corrupts every aggregate that touches the dimension.

## The question, and the answer

> **The question** (what the data can't tell you): *Are these N rows one entity observed over time, or N
> different entities — and for a question that gives no date, which version is meant?*
>
> **The answer** (the fact we supply): *One entity; the rows differ only on an **as-of (validity) axis**.
> For an undated question, collapse to the current version; never multiply facts across versions. Supplied
> as one concept + an as-of axis + a single snapshot-collapse rule.*

## The pattern (the structured entry)

```yaml
pattern: scd_type_2
also_known_as: [slowly changing dimension type 2, SCD2, dimension versioning, temporal dimension]
tradition: dimensional
constellation: >
  A dimension keeps its own history. Instead of overwriting an attribute when it changes, the table
  carries multiple rows per logical entity, each stamped with a validity window (valid_from / valid_to)
  or a snapshot date, and usually an is_current flag. One real-world Product becomes N rows.
prior_art:
  relational: >
    A "Type-2 dimension": rows keyed by (natural_key, valid_from). Correct, but the discipline that you
    must filter to the right version — and must NOT join-then-aggregate naively, or you multiply facts by
    version count — lives in every analyst's head and every hand-written query.
  dimensional: >
    The canonical Kimball SCD-2: a surrogate key per version, valid_from/valid_to, is_current. Well-defined
    — but defined inside the ETL/BI tool, and the "never sum across versions" rule is tribal, not stated on
    the artifact. A different tool re-implements the slice.
  rdf: >
    Temporal modelling via versioned IRIs, named graphs, or reification of each statement with a validity
    interval. Expressive but heavy; the validity logic is not something an LLM reads and applies cheaply.
mac_expression: >
  History is a SECOND AXIS, not a second concept. Model the validity/as-of as its own axis (the
  orthogonal-axis principle, CONCEPT_SPEC §8) — NOT by minting a concept per version. The dimension concept
  stays one concept; its grounding carries a `snapshot_rule:` describing the versioning, and a single
  snapshot-latest collapse rule (a ROW_NUMBER wrapper, `applied_as: subquery_wrapper`) reduces to the
  current version unless the question supplies an explicit as-of. The collapse rule is authored ONCE and
  injected; the agent does not re-derive it per query.
why_better: >
  The footgun (multiplying facts by version count, or reporting a stale version) is made structural, not
  left to discipline: additivity over the as-of axis is declared in `semantics.additivity`, and the
  collapse is a single-homed rule every consumer inherits. The same artifact still projects to a Kimball
  Type-2 for a warehouse target and to valid-time edges for a graph — so you state the temporal meaning
  once and keep every target.
projects_to:
  rdf: "versioned IRIs or validity-interval annotations per statement"
  graph: "valid-from/valid-to properties on the relationship, or time-sliced edges"
  relational: "the Kimball Type-2 dimension (surrogate key per version + is_current)"
antipattern: >
  Minting one concept per version, or letting each query re-invent the version filter. This is COOKBOOK
  C9 (two orthogonal axes — here entity-identity and validity-time — modelled as one), and the rule-count
  smell C6 if every measure grows its own "latest version" special-case instead of inheriting the one
  collapse rule.
status: scattered   # the pieces exist (SPEC §8 + snapshot collapse rule) but were never named "SCD-2"
canon_ref: [CONCEPT_SPEC.md §8, CONCEPT_SPEC.md §7 (snapshot-latest collapse), MODELLERS_COOKBOOK.md C6/C9]
```

## The determinism border

Per [AUTHORING.md](../AUTHORING.md) A4 — the canon here is a **query-shape** transform, not a guard:

| Behaviour | Kind | How |
| --- | --- | --- |
| Collapse to one row per natural key before aggregating (no fact-multiplication) | **canon-backed** | [`snapshot_collapse`](../canon/snapshot_collapse.md) (`subquery_wrapper`) |
| An explicit AS-OF date resolves to the version valid then | **canon-backed** | the same canon, `as_of=?` (bound) |
| An undated question means the current version | **skeleton/default** | the collapse defaults to latest (`ROW_NUMBER`) |
| interpretative remainder | **none/minimal** | "undated → current" is a safe default, not a guess |

```yaml
grounding:
  prose: "dim_product keeps SCD-2 history; collapse to the current version unless an as-of is given."
  realized_by:
    udf: snapshot_collapse
    applied_as: subquery_wrapper
    params: { table: dim_product, natural_key: product_id, order_by: valid_from, valid_to: valid_to }
```

The footgun from the *Initial state* — one product becoming two rows and doubling every join — is closed
*before* any aggregation runs: downstream SQL sees one row per `product_id`.

## Reading the entry

The value of writing SCD-2 out this way is the manual's thesis in miniature: the warehouse world *has* this
pattern but states the safety rule tribally; the relational world states the structure but not the meaning;
RDF can express it but expensively. Here the temporal meaning is declared once (an axis with stated
additivity + a single collapse rule), it is **agent-safe by construction**, and it still **projects back**
to each of the three worlds. That is the "why is this better" Ch.01 argues — shown, per pattern, rather
than asserted.
