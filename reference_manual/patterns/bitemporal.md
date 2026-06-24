---
title: "Pattern — Bitemporal (valid time vs system time)"
part_of: reference_manual/patterns
status: gap   # each axis is expressible (snapshot_collapse); coordinating BOTH as one as-of is the residual gap — FINDINGS F2
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (illustrative shop scenario).
---

# Pattern — Bitemporal  🟡 *each axis works; a dual-as-of construct is the residual gap*

> Like `polymorphic_association`, this one **stresses the framework**: each time axis is expressible with
> `snapshot_collapse`, but coordinating BOTH as a single "as of valid V, as known at system S" is not a
> first-class construct → [FINDINGS.md](../FINDINGS.md) **F2**.

## Initial state — what you're handed

A price history with **two independent time axes** — when a price was true in the world (*valid time*) and
when the database recorded it (*system time*):

```sql
CREATE TABLE price_history (
  product_id VARCHAR, price DECIMAL(10,2),
  valid_from DATE, valid_to DATE,          -- VALID time: when the price applied
  recorded_at DATE, superseded_at DATE     -- SYSTEM time: when we knew it
);
```

| product_id | price | valid_from | valid_to | recorded_at | superseded_at |
| --- | --- | --- | --- | --- | --- |
| P-100 | 12.00 | 2026-01-01 | 9999-12-31 | 2026-01-01 | 2026-02-01 |
| P-100 | 14.00 | 2026-01-01 | 9999-12-31 | 2026-02-01 | 9999-12-31 |

**Why this is dangerous.** Both rows have the *same* valid period (Jan onward) — the second is a **correction
recorded Feb 1**. "What was the January price?" has *two* right answers: **14.00** (what we believe now) and
**12.00** (what we believed *on Jan 10*). Collapse only the valid axis and you silently return the corrected
value, destroying auditability — "what did we report at the time?" becomes unanswerable.

## The question, and the answer

> **The question:** *Which "as of" does the question mean — as-of valid time, as-known-at system time, or
> both?*
>
> **The answer:** *They are two independent axes. Each collapses with `snapshot_collapse`; a bitemporal
> question pins BOTH (valid ≤ V AND system ≤ S). MAC expresses each axis but has no single dual-as-of
> construct — that's the flagged gap.*

## The pattern (the structured entry)

```yaml
pattern: bitemporal
also_known_as: [bitemporal, valid-time vs transaction-time, as-of-as-known-at, audit history]
tradition: dimensional   # + temporal-database theory (SQL:2011 system/application time)
constellation: >
  A fact carries TWO independent time axes — valid (application) time and system (transaction) time — so a
  correction creates a new system-time row over the same valid period. Audit questions need both.
prior_art:
  relational: >
    SQL:2011 system- and application-time period tables — powerful but rarely used; in practice four date
    columns whose dual semantics are undocumented, and most queries collapse one axis and lose the other.
  dimensional: >
    Type-2 on two axes; combinatorially awkward; the "as known at" axis is usually dropped.
  rdf: >
    Named graphs / reified statements with two validity intervals — expressible, heavy.
mac_expression: >
  Model TWO orthogonal as-of axes (valid + system), each with a `snapshot_rule`. A bitemporal read composes
  TWO `snapshot_collapse`s — collapse to `valid ≤ V`, then within that to `system ≤ S` (reuse the canon
  twice). HONEST GAP (🟡): "as of (V, S)" as a single first-class **bitemporal collapse** is not a construct;
  the workaround nests two collapses and the dual intent isn't single-homed. → [FINDINGS.md](../FINDINGS.md) F2.
why_better: >
  Even as a workaround, naming BOTH axes (and reusing one canon twice) makes auditable "what did we believe
  then?" answerable — versus the silent single-axis collapse that returns only the corrected value. Honest:
  the clean dual-as-of construct is a flagged candidate, not solved.
projects_to:
  rdf: "two validity intervals per statement / named graphs"
  graph: "valid + system interval properties on the edge"
  relational: "SQL:2011 system + application time period tables"
antipattern: >
  Collapsing only the valid axis (returns the corrected value, loses 'as known at'); treating the four date
  columns as one axis.
status: gap   # each axis expressible (snapshot_collapse ×2 workaround); single dual-as-of construct MISSING — FINDINGS F2
canon_ref: [patterns/scd_type_2.md, canon/snapshot_collapse.md, FINDINGS.md, CONCEPT_SPEC.md §8 (orthogonal axes)]
```

## The determinism border

| Behaviour | Kind | How |
| --- | --- | --- |
| Collapse each axis to a given as-of | **canon-backed** (reused) | [`snapshot_collapse`](../canon/snapshot_collapse.md), once per axis |
| A single first-class **bitemporal (V, S) collapse** | **🔴 framework gap** | not a construct — [FINDINGS.md](../FINDINGS.md) F2, not enacted |
| *Which* (V, S) the question means | **prose-fallback** | interpretation ("as we believed it on Jan 10") |

## The footgun, concretely

```sql
-- GUESS: collapse only valid time → "the" January price = the CORRECTED value
SELECT price FROM price_history
WHERE valid_from <= DATE '2026-01-10' AND valid_to > DATE '2026-01-10';   -- returns 12.00 AND 14.00, or "latest" → 14.00  ❌
-- GROUNDED: pin BOTH axes — as valid on Jan 10, as KNOWN on Jan 10
SELECT price FROM price_history
WHERE valid_from <= DATE '2026-01-10' AND valid_to > DATE '2026-01-10'
  AND recorded_at <= DATE '2026-01-10' AND superseded_at > DATE '2026-01-10';   -- 12.00 — what we believed then  ✅
```
