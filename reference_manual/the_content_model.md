---
title: "The content model — skeleton, prose, and the UDF seam"
part_of: reference_manual
status: written
position: Foundations — read after Ch.02 (the building blocks), before Ch.03 (the patterns).
scope: GENERIC — domain-neutral. Examples from example_shop_ontology/.
---

# The content model — skeleton, prose, and the UDF seam

*Chapter 02 says what the building blocks **are**. This chapter says what each block is **filled with** —
and which of that fill is deterministic, which is interpretative, and how to convert one into the other
without giving up the other. It is the line between the part a machine can be trusted to read identically,
and the part that depends on the mind reading it.*

## 1. Interpretation happens in two places, not one

It is tempting to say: the only "soft" step is reading the user's question; everything the ontology states
is hard. **That is false, and the error matters.** Interpretation — *mapping a natural-language string to
meaning, associatively and probabilistically* — happens in **two** places:

- **(a)** reading the user's **question**; and
- **(b)** reading the **prose inside the ontology itself** — a rule whose `logic:` is a sentence, a
  `scope:` paragraph, a `when/then/never` written in words.

A prose rule is exactly as model-variant as a question. Two consequences, both real:

1. a *weaker* model may not interpret the prose correctly **at all**;
2. two *different* models may interpret the same prose **differently** — so non-determinism is baked into
   the **definition**, before any question is asked.

So determinism is not a property of "the pipeline." It is a property of **the content, slot by slot.** A
great mind can read prose correctly — but so can a great mind read it *its own way*. The same prose, two
readers, two canons. We do not get to assume the great reader.

## 2. Three kinds of content, and one discriminator

Every slot in a definition is exactly one of three things:

1. **Skeleton** — typed, drawn from a closed vocabulary, or a resolvable pointer. Deterministic by
   construction; machine-checkable. *(`class`, `closure`, `additivity`, `cardinality`, a `grounding` table
   pointer.)*
2. **Deterministic flesh — a UDF** — an executable realization: a SQL expression, a predicate, a view, an
   invariant. Deterministic because it is *run*, not *read*. *(a rule `template`, a `sql_assertion`.)*
3. **Prose flesh** — natural language. Human-readable, **interpretative**, model-variant.

The border between them is one question, asked of each slot:

> **"If two competent models read this slot, could they produce *different query behaviour*?"**

| Answer | The slot is… |
| --- | --- |
| No — it's typed / a pointer | **skeleton** |
| No — it's executable | **UDF** |
| **Yes — it's prose that drives behaviour** | **behaviour-bearing prose** — the danger zone; it *needs a UDF seam* |
| It drives no behaviour, only informs a human | **pure prose** — leave it; this is the *good* prose |

That question **is** the line you asked to be drawn. Everything else here follows from it.

## 3. The discrimination, applied

| Slot | Kind | The seam (if behaviour-bearing) |
| --- | --- | --- |
| `class` (∈ 6) | **skeleton** | — |
| `grounding.table / key / column` | **skeleton** (pointer) | a checker resolves it |
| `semantics.additivity` (MeasureType × axis_kind) | **skeleton** | the algebra decides the fold |
| `closure`, `cardinality`, edge `level` / `type` | **skeleton** | — |
| `value_set` items (the codes) | **skeleton** (data) | — |
| `grounding.value_filter / snapshot_rule / discriminator` | **behaviour-bearing** | UDF = a SQL predicate / a ROW_NUMBER wrapper |
| `semantics.scope` (where it applies / excludes) | **behaviour-bearing** | UDF = a scope predicate |
| rule `logic:` | **behaviour-bearing** | UDF = `template` (`sql_expression`/`sql_view`/`derived_set`); **`spec_only` = the prose fallback** |
| typed rule `when / then / never` | **behaviour-bearing** | UDF = `binds` + predicate + `enforced_by` |
| `null_semantics` (drives anomaly-of-absence) | **behaviour-bearing** | UDF = typed enum + an absence predicate |
| resolution (e.g. `name_norm LIKE 'X%'`) | **behaviour-bearing** | UDF = a resolver expression |
| ambiguity trigger (when to abstain → ⊥) | **behaviour-bearing** | UDF = a multi/no-match predicate |
| `definition`, `purpose`, `closure_why`, every `*_why`, `open_questions` | **pure prose** | — leave it; the human path |

## 4. The seam — generalized from one mechanism MAC already has

The framework already carries the seam, in pieces: a rule's `render_kind` is exactly a **UDF-or-prose
switch** — `sql_expression` / `sql_view` / `derived_set` are deterministic; `spec_only` means "a model
generates it from the prose." `sql_assertion`, `enforced_by`, and `binds` are UDF seams too.

The content model **generalizes that one idea to every behaviour-bearing slot**: each gets an optional
`realized_by:` (its UDF) alongside its prose. Filled → deterministic; empty → prose → model-interpreted.

```yaml
# behaviour-bearing slot, BOTH forms present — prose for the human, UDF as its canon
scope:
  prose: "Applies to sold products only; excludes QA fixtures and rollup buckets."
  realized_by:                    # the canon — deterministic, run not read
    kind: sql_predicate
    expr: "product_id NOT LIKE 'P-TEST-%' AND product_id <> 'P-MISC'"
```

## 5. Canonization — why we keep both, and how the UDF is born

Prose is not the enemy of determinism; it is its **source**. The move is not "replace prose with code." It
is: **a capable model reads the prose once and writes its canon as a UDF** — the same way a skilled engineer
turns a paragraph of intent into a precise function. The prose stays (a human must be able to read the
meaning); the UDF is its frozen, reviewed twin.

```
   prose  ──[ a capable model canonizes, ONCE ]──▶  UDF (realized_by)  ──[ run by anyone ]──▶  deterministic
 (human source)        (elevation, reviewed)            (the canon)            (weak model or pure execution)
```

This is the payoff: **determinism is reached by *elevation*, not by forcing humans to hand-author
functions.** A strong model produces the canon; a weak model — or no model at all, just the executor —
inherits it. And we **cover both**: the prose for every human and the auditing eye, the UDF for every
machine that must not guess. Neither replaces the other; the UDF is the prose's canon, the prose is the
UDF's explanation.

> **Authoring rule (see [AUTHORING.md](AUTHORING.md) A2/A9):** a behaviour-bearing slot ships prose
> *always*, and its `realized_by:` canon *wherever determinism is required*. A canon is **reviewed and
> frozen**, never silently regenerated — otherwise it is just prose again.

## 6. The honest metric — and a challenge

Determinism is now **measurable**, per ontology:

> **Determinism coverage = (behaviour-bearing slots with a frozen `realized_by:` canon) ÷ (all
> behaviour-bearing slots).**

We make **no completeness claim** about it. We do not say "this covers 60% of what you'll need" — *we don't
know that, and nobody does.* What we say is honest and smaller: here is the coverage we have *built and
validated*; we **hope** it covers most of what you meet, and if it does, we have done our job well. And to
the reader weighing this against the alternatives, we put it plainly:

> *Here is the meaning, written down — skeleton, prose, and canon — checkable, vendor-neutral, and read
> identically by every machine that touches it. **Give us something better if you can.***

## 7. What stays prose forever (and should)

Pure prose is not a weakness to be eliminated — it is the human path, and it is **required** (AUTHORING A9).
A `purpose`, a `definition` read as documentation, a `closure_why`, the rationale on any `*_why` field: none
of these drive query behaviour, so the discriminator in §2 leaves them prose. Make them excellent prose. The
goal of this chapter is not to delete prose — it is to know, for every slot, **whether a machine may be
trusted to read it, or whether it needs a canon first.**
