---
title: "Findings — framework-enhancement candidates (for the maintainer's decision)"
part_of: reference_manual
status: living
scope: META — decisions the reference manual surfaces but does NOT enact.
---

# Findings — framework-enhancement candidates

*While writing the reference manual, some patterns reveal that the framework **core** (the schema, the
construct set) may need a new or extended construct. Per the binding principle and [AUTHORING.md](AUTHORING.md),
these are **documented here for the maintainer's decision — not enacted.** Nothing in this file changes
`mac.schema.json` or the class/edge vocabulary; each is a candidate awaiting a yes/no.*

A finding earns a place here only when a pattern is **not** cleanly absorbed by the existing six structures
+ three-level edge model — i.e. it is expressible only as a workaround, or not at all. (Patterns the
structures *do* absorb — e.g. `associative_entity` — are **not** findings; they are confirmations.)

| # | Candidate | Surfaced by | Today's workaround | Status |
| --- | --- | --- | --- | --- |
| **F1** | A first-class **polymorphic edge** (one edge → a discriminated union of targets) | [`polymorphic_association`](patterns/polymorphic_association.md) | N discriminated `physical` edges + `parent_type` enum + reused `composite_key_guard` | **open — for decision** |
| **F2** | A first-class **bitemporal (dual-as-of) collapse** (as-of valid V, as-known-at system S) | [`bitemporal`](patterns/bitemporal.md) | nest `snapshot_collapse` twice (valid then system) | **open — for decision** |

---

## F1 — A first-class polymorphic edge / abstract role target

**Surfaced by:** [`polymorphic_association`](patterns/polymorphic_association.md).

**The gap.** A `(type, id)` pair references one of several concepts, chosen by the discriminator. MAC's edge
model assumes a **single** typed target (`realized_by` one FK), so a polymorphic reference has no first-class
home. The *intent* — "this edge points at one of {Product, Order, Customer}" — cannot be stated as one
construct.

**Today's workaround (works, but verbose).** Decompose into **N discriminated `physical` edges**, one per
discriminator value, each `realized_by` a join that includes `parent_type = '<value>'`; model `parent_type`
as an `enumeration`. Query-time safety **reuses** `composite_key_guard` (`{code_column: parent_id,
scope_columns: [parent_type]}`) so the FK can't be used without its discriminator.

**Why it's a real candidate.** The workaround scatters one relationship across N edges and loses the
"one-of-many target" intent; RDF expresses it cleanly as an object property with an `owl:unionOf` range (or a
shared superclass). This is one of the few places RDF is ahead of MAC today.

**Candidate shape (for discussion, not decided).** Either (a) a **polymorphic edge** whose target is a
declared discriminated union of concepts + the discriminator column, single-homed; or (b) an abstract
cross-class **role** concept the heterogeneous targets share, with one ordinary edge to the role.

**Decision needed.** Is this worth a framework construct, or is the N-edge workaround acceptable? If adopted,
it is a `mac.schema.json` change → branch → PR, exercised on **both** worked examples (shop + TPC-H) per the
framework quality checklist. **Not enacted here.**

---

## F2 — A first-class bitemporal (dual-as-of) collapse

**Surfaced by:** [`bitemporal`](patterns/bitemporal.md).

**The gap.** A bitemporal fact has two independent time axes — *valid* (when true in the world) and *system*
(when recorded). `snapshot_collapse` collapses **one** axis to an as-of; a bitemporal read needs **both**
pinned at once ("as valid on V, as we knew it on S"). MAC expresses each axis (a `snapshot_rule` per axis)
but has no single construct for the coordinated dual-as-of.

**Today's workaround.** Nest `snapshot_collapse` twice — collapse to `valid ≤ V`, then within that to
`system ≤ S` (the canon reused, once per axis). Works; but the "(V, S)" intent is not single-homed, and the
ordering/independence of the two axes is left to the author.

**Why it's a real candidate.** Bitemporal correctness (auditable "what did we believe then?") is exactly
where a silent single-axis collapse goes wrong; a first-class construct would make the dual-as-of explicit
and prevent dropping the system axis. Temporal-DB theory (SQL:2011 system/application time) is the prior art.

**Candidate shape (for discussion, not decided).** A **bitemporal collapse** that takes both as-of points
and both validity-window pairs, declared once on the concept; or a generalization of `snapshot_rule` to an
ordered list of as-of axes.

**Decision needed.** Worth a framework construct, or is nesting the canon acceptable? If adopted →
`mac.schema.json` change → branch → PR, exercised on shop + TPC-H. **Not enacted here.**
