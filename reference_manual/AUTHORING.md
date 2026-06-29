---
title: "Authoring constitution — the framework for this reference manual"
part_of: reference_manual
status: written
scope: META — the agreed rules for how this manual is written. Domain-neutral; binds every chapter and pattern.
---

# Authoring constitution — the framework for this reference manual

*A reference manual for frameworks needs its own framework. This is it: the rules we **agree** and then
**enforce on ourselves** while writing every chapter and every pattern. They exist so the manual stays
honest, single-homed, and machine-trustworthy — the same properties it asks of the ontologies it describes.
If a section breaks one of these rules, the section is wrong, not the rule.*

The constitution is grounded in three companion ideas, stated once and referenced everywhere:
the **content model** ([the_content_model.md](the_content_model.md)) — skeleton / prose / UDF;
the **anatomy of a pattern** ([00_the_problem.md](00_the_problem.md) §0.3) — every entry is a Question → Answer;
the **formal stance** — we describe what we have built and validated, and nothing more.

## The rules

### A1 — Classify every slot
Every piece of content is one of: **skeleton** (typed/pointer, deterministic), **behaviour-bearing**
(drives a query/decision), or **pure prose** (informs a human only). No unclassified content. *Check:* apply
the discriminator — "could two competent models produce different behaviour from this slot?"
([content model §2](the_content_model.md)). The complete slot inventory per object type — which keys exist
and where they nest — is the [Shape Reference](shape_reference.md).

### A2 — Behaviour-bearing prose carries a UDF seam
A slot that drives behaviour ships **prose always**, and a `realized_by:` **canon wherever determinism is
required**. Determinism is achieved *exactly* where the canon is filled — never assumed from prose. *Check:*
no behaviour-bearing slot relied on for a deterministic answer is prose-only.

### A3 — Single-home
Every fact lives in **one** place. Prose never restates skeleton; prose never restates its own UDF; a
chapter never restates the canon. *(This is the rule my early "YAML-costume" pattern blocks broke — prose
and a structured block saying the same thing three times.)* *Check:* delete any sentence whose content is
already carried by a typed field or a canon, and link instead.

### A4 — Mark the border
Every concept and every pattern states **which of its behaviour is canon-backed (deterministic) and which is
prose-fallback (interpretative)**, so a reader — or an agent — knows where determinism holds and where it is
trusting a mind. *Check:* a reader can tell, per claim, whether it is guaranteed or interpreted.

### A5 — No completeness claims; publish coverage; hope; challenge
We never claim the theory is complete — *we cannot know that.* We publish the **coverage we have built and
validated** (the determinism-coverage metric), we **express the hope** that it covers most real needs, and
we close with the challenge: **"give us something better if you can."** Every basis (the structures, the
facts, the rule kinds) is **explicitly open**, with an extension procedure (below). *Check:* no sentence
asserts totality; every basis names how to extend it.

### A6 — Necessity needs a witness
Any claim that a structure, fact, or rule is **necessary** must cite a **witness** — a concrete pattern that
produces a wrong answer if that thing is omitted. Necessity is shown by counterexample, not asserted.
*Check:* "X is necessary" → which pattern breaks without X?

### A7 — Rigor and prose never share a claim
Prose **motivates and explains**; **skeleton or a canon decides.** A single claim is never half-formal,
half-narrative. Prose may surround a deterministic claim; it may not *be* it where determinism is required.
*Check:* for any load-bearing claim, point at the typed field or canon that enforces it.

### A8 — The manual is itself meaning-as-code
Structural content of the manual — the building-block catalog, the pattern index, the discrimination table —
is kept as **checkable, projectable data**, not only prose. We dogfood the framework on its own
documentation. *Check:* the manual's own indices could be validated/projected, not just read.

### A9 — Human-readability is first-class; cover both
Prose is **required** for the human path, even where a canon exists. The canon is the deterministic **twin**,
not a replacement. Every behaviour-bearing slot, fully realized, carries **both**: prose a person reads and a
canon a machine runs. *Check:* no slot is canon-only (unreadable to a human) and none is prose-only where
determinism is required.

### A10 — Examples are domain-neutral; changes follow the binding principle
All examples come from the synthetic shop (`example_shop_ontology/`); no real domain, warehouse, or vendor
appears. The manual lives in the framework repo and evolves by **branch → PR**, never edited as a byproduct
of an applied project. *Check:* grep for any real-domain term; confirm the change is on a framework branch.

## How we extend (the procedure A5 promises)

When a real case does not fit, we **extend**, in the open — we do not pretend it fit. The procedure is the
same for each basis:

1. **Show the misfit.** A concrete case the current basis cannot express (the witness, A6 — but in reverse:
   here it witnesses *insufficiency*).
2. **Propose the addition** — a 7th structure, an extra necessary fact, a new rule kind — as the *smallest*
   change that absorbs the case.
3. **Re-check the basis is still closed and minimal** — does the addition overlap an existing member? Can an
   existing member be generalized instead?
4. **Version it** — bump the relevant `schema_version` / basis version; record it; branch → PR.

Coverage goes up by **building**, never by **claiming**.

---

*This constitution binds the manual to the standards the manual preaches. Authored on `docs/reference-manual`;
amended only by branch → PR, like any other framework contract.*
