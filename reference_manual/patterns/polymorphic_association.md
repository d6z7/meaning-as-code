---
title: "Pattern — Polymorphic association (a foreign key that points at one of several types)"
part_of: reference_manual/patterns
status: gap   # expressible via N discriminated edges (workaround); a first-class polymorphic-edge construct is MISSING — flagged in FINDINGS.md
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (illustrative shop scenario).
---

# Pattern — Polymorphic association  🟡 *workaround exists; a framework construct is the residual gap*

> This pattern is the first that **stresses the framework**: it is expressible today, but only as a
> workaround, and it surfaces a genuine **framework-enhancement candidate** recorded (not enacted) in
> [FINDINGS.md](../FINDINGS.md) **F1**. Honesty here is the point — and it is one of the few places RDF is
> genuinely cleaner than MAC today.

## Initial state — what you're handed

An `attachment` whose target is *one of several different tables*, chosen by a type column:

```sql
CREATE TABLE attachment (
  attachment_id VARCHAR,
  parent_type   VARCHAR,   -- 'product' | 'order' | 'customer'
  parent_id     VARCHAR,   -- references product.id OR orders.id OR customer.id, per parent_type
  url           VARCHAR
);
```

| attachment_id | parent_type | parent_id | url |
| --- | --- | --- | --- |
| A-1 | product | P-100 | … |
| A-2 | order | O-1 | … |
| A-3 | customer | C-9 | … |

**Why this is dangerous.** `parent_id` has **no single foreign-key target** — so no normal FK can be
declared, and referential integrity isn't enforceable the usual way. The real target lives in `parent_type`,
which every join *must* branch on. `JOIN product ON product.id = attachment.parent_id` silently pulls in
order- and customer-attachments (if id spaces collide) or drops them — a mis-join with no error.

## The question, and the answer

> **The question** (what the data can't tell you): *What does `parent_id` reference?*
>
> **The answer** (the fact we supply): *One of several concepts, selected by `parent_type` — there is no
> single FK. Expressed as **N discriminated edges** (one per type, joined only when `parent_type` matches);
> query-time safety **reuses** the `composite_key_guard` canon (never use `parent_id` without
> `parent_type`). And it flags a real framework gap: MAC has no first-class **polymorphic edge**.*

## The pattern (the structured entry)

```yaml
pattern: polymorphic_association
also_known_as: [polymorphic FK, generic foreign key, type+id reference, heterogeneous association]
tradition: relational   # the ORM "polymorphic association"; ER generalization
constellation: >
  A single (type, id) pair references one of several different tables, chosen by the type column. The
  foreign key has no single referent; integrity and joins both depend on the discriminator.
prior_art:
  relational: >
    A "polymorphic FK": no declarable foreign key, no enforceable referential integrity; every join must
    branch on the type column, and a forgotten branch silently mis-joins.
  dimensional: >
    Usually avoided or denormalized; sometimes a junk "type" dimension. No clean handling.
  rdf: >
    Natural here — an object property whose range is a UNION / shared superclass (`owl:unionOf`, or an
    abstract superclass the targets share). RDF expresses "one of several types" cleanly; this is a place
    RDF is genuinely ahead of MAC today.
mac_expression: >
  TODAY (workaround): decompose into N `physical` edges — one per `parent_type` value — each `realized_by` a
  DISCRIMINATED join (`parent_type = 'product' AND parent_id = product.id`), with `parent_type` modelled as
  an `enumeration`. Query-time safety REUSES `composite_key_guard` with
  `{ code_column: parent_id, scope_columns: [parent_type] }` — the FK may never be used without its
  discriminator. THE GAP (🟡): MAC has no first-class **polymorphic edge** (one edge → a discriminated union
  of targets) nor an abstract cross-class **role** the heterogeneous targets share, so the intent ("an
  attachment points at one Commentable") is expressible but not single-homed. → [FINDINGS.md](../FINDINGS.md) F1.
why_better: >
  Even as a workaround, the N-edge decomposition makes the type-branching EXPLICIT and the reused guard makes
  "forgot the discriminator" CATCHABLE — versus a silent mis-join. But honestly: here the framework is
  stressed, RDF's union-range is cleaner, and the clean construct is a flagged candidate, not a solved
  pattern.
projects_to:
  rdf: "an object property with owl:unionOf range / a shared superclass (clean)"
  graph: "a relationship type to a labelled-union target"
  relational: "the polymorphic FK + per-type discriminated joins"
antipattern: >
  Joining on `parent_id` without the `parent_type` discriminator (silent cross-type mis-join); declaring a
  single-target FK (impossible / wrong); collapsing the types and losing which target a row points at.
status: gap   # workaround expressible; first-class polymorphic-edge construct MISSING — FINDINGS.md F1 (for decision)
canon_ref: [FRAMEWORK.md §7 (edges), CONCEPT_SPEC.md §6 (grounding discriminator / value_filter), FINDINGS.md]
```

## The determinism border

Per [AUTHORING.md](../AUTHORING.md) A4 — the query-time safety is canon-backed (by **reuse**); the clean
*construct* is the residual gap:

| Behaviour | Kind | How |
| --- | --- | --- |
| Never use `parent_id` without its `parent_type` discriminator | **canon-backed** (reused) | [`composite_key_guard`](../canon/composite_key_guard.md) `{parent_id; [parent_type]}` |
| Per-type target resolution | **skeleton** (workaround) | N discriminated `physical` edges + a `parent_type` enumeration |
| A single first-class **polymorphic edge** | **🔴 framework gap** | not a construct yet — flagged in [FINDINGS.md](../FINDINGS.md) F1, *not* enacted |
| interpretative remainder | **none** | once the discriminator is required, joins are mechanical |

## The footgun, concretely

```sql
-- GUESS (plausible, and wrong): join the polymorphic FK to one type, no discriminator
SELECT a.url FROM attachment a JOIN product p ON p.id = a.parent_id;
-- pulls order/customer attachments too (if ids collide) or drops them — a silent cross-type mis-join  ❌
```

```sql
-- GROUNDED: the discriminated join (and composite_key_guard REJECTS the bare one above)
SELECT a.url FROM attachment a JOIN product p
  ON p.id = a.parent_id AND a.parent_type = 'product';   ✅
```

The honest result for the formal core: unlike `associative_entity` (which the six structures absorbed),
this one the **edge model** does *not* absorb cleanly. The workaround works and is safe; the clean
abstraction is a real candidate addition — which is exactly why it goes to FINDINGS for your decision, not
into the schema on my say-so.
