---
title: "Ch.02 — The building blocks (the formal core)"
part_of: reference_manual
status: written   # a STARTING BASIS, stated formally — explicitly open, not claimed complete (AUTHORING A5)
scope: GENERIC — domain-neutral. Examples from example_shop_ontology/.
---

# Ch.02 — The building blocks (the formal core)

*Chapter 00 gave the units of a pattern (observation · constellation · construct · response). This chapter
defines the **constructs** — the answer-particles — as what they actually are: a small set of
**mathematical structures**, each an equation between a meaning and a grounding. This is the formal core the
patterns and canons rest on.*

> **Relationship to the canon (single-homing, AUTHORING A3).** The *prose* definitions of the four layers and
> six classes live in [`../FRAMEWORK.md`](../FRAMEWORK.md) §4–§5; their concrete YAML **shape** (which keys,
> where, per class) is the generated [Shape Reference](shape_reference.md); the additivity law lives in
> [`../mac_vocabulary.yaml`](../mac_vocabulary.yaml). This chapter does **not** restate them — it adds the
> layer FRAMEWORK leaves implicit: the **formal structure** under each construct, and the **completeness
> argument** over them. Where prose and this chapter overlap, FRAMEWORK owns the prose; this owns the math.
>
> **Honesty up front (AUTHORING A5).** What follows is a **starting basis**, stated precisely so it can be
> *tested and extended* — not a claim of completeness. We do not know that six structures and six facts are
> enough. We know they cover the cases we have tried, and we have an extension procedure for the ones they
> won't (§2.7).

## 2.1 The one equation

Every concept is an **equation** between a meaning and a grounding:

```
⟦ C ⟧   =   { construction over the Physical layer }
 meaning            grounding
```

- the left side `⟦C⟧` is the concept's **extension** (or function) — *what it denotes*;
- the right side is a **construction over physical rows** — *how that denotation is built from data*;
- the `=` is a **falsifiable assertion**: run the construction, compare to reality. When the computed `⟦C⟧`
  disagrees with the data, the equation is **wrong** and the model is corrected. (This is the trust gradient
  of FRAMEWORK §8, stated formally: a concept is a *refutable* claim, and the Physical layer is the **nature**
  it answers to.)

A construct's **class** says *what kind of right-hand side is allowed*. There are six.

## 2.2 The six classes are six structures

| `class:` | The structure it **is** | The equation it defines | Grounded in |
| --- | --- | --- | --- |
| **reference / entity** | a **set with identity** — a key is an injection `id: ⟦C⟧ ↪ K` | `⟦C⟧ = { r ∈ table : filter(r) }`; each row has a unique identity | extensional set theory |
| **enumeration** | a **set + a closure predicate** | `V(C) = { allowed values }`; `closed ⇒ V complete`, `open ⇒ V a lower bound` | open-/closed-world logic |
| **measure** | a **function + an aggregation algebra** `m: cells → ℝ`, `α: axis → effect` | the value *and* which fold is valid per axis (`α` from `mac.MeasureType × axis_kind`) | dimensional analysis (stock vs flow) |
| **grouping** | a **surjection** `π: leaves ↠ groups` | the roll-up map (a partition of the leaf set) | order theory / lattices |
| **event** | a **transition system** `(S, →, ≤)` | the reachable states and their order | automata / partial orders |
| **edge** *(relation between the above)* | a **relation** `R ⊆ A × B` | how two extensions connect | relational algebra |

Concretely, in the shop:

- `⟦Country⟧ = { r ∈ country }`, `id = iso2` (injective) — a **set with identity**.
- `⟦OrderStatus⟧ = {PLACED, …, CANCELLED}`, `closure = closed` ⇒ the set is *complete* — a **set + closure**.
- `⟦InventoryLevel⟧ : (date, warehouse, product) → ℤ`, with `α(time) = point_in_time`, `α(categorical) =
  additive` — a **function + algebra**.
- `⟦Category⟧ : products ↠ categories` — a **surjection**.
- `⟦Order⟧ : (CHECKOUT → FULFILMENT → CLOSED)` — a **transition system**.

The claim behind "exactly six": *set, set-with-closure, function-with-algebra, surjection, transition-system,
relation* are the structures a data domain's meaning takes. Strong, and explicitly open (§2.7).

## 2.3 Relations (edges) and derived concepts (rules)

**Edges** are relations between extensions, at three levels:

- `physical` — a relation `R ⊆ A × B` realized by a foreign key (a function `key: A → B`);
- `business` — an **identity / equivalence** `a ≈ b` (the two denote the same real-world thing);
- `federation` — a **partial bijection** between two sources' extensions (an alias map).

**Rules** are equations for *derived* concepts: `derived = f(base₁, …, baseₙ)` — a new meaning on the left, an
expression over existing extensions on the right (`render_kind` only says *how the right side is evaluated*).
The six `mac.rule_kind`s are the operators of this algebra:

| rule_kind | as an operation |
| --- | --- |
| **resolution** | a matching map: question-term → an element/subset of an extension |
| **exclusion** | a filter predicate on an extension |
| **aggregation** | the fold chosen by the measure's algebra `α` |
| **default** | a *section* — choosing a canonical value when an axis is left free |
| **guarantee** | an invariant the serving view maintains (relied on, not re-derived) |
| **ambiguity** | the **partial** case: when the resolution map is one-to-many or undefined → return **⊥** (abstain) |

`ambiguity → ⊥` is the formal version of *ask, don't guess*: abstention is a **defined output**, not a failure.

## 2.4 Where each structure is grounded (logic · physics · nature)

The "left and right of the `=`, grounded in something real" you asked for — each structure rests on an
established foundation, not on our taste:

- **sets / identity** (reference, entity, edges) → **extensional set theory** and equality: a thing *is* its
  members; identity is an injection; an edge is a relation.
- **measure additivity** → **dimensional analysis / physics**: a *stock* is a level read at an instant
  (point-in-time over time), a *flow* accrues per period (additive — integrable over time). The
  `MeasureType × axis_kind` law is this physics, written down once.
- **closure** → **open- vs closed-world logic** (CWA/OWA): `closed` is `owl:oneOf` / a complete set; `open` is
  the open-world default; `unknown` is honest about not having decided.
- **resolution / identity** → **equality theory**: when are two coded values the *same* thing (and under what
  scope — see `context_dependent_meaning`).
- **absence** (`null_semantics`) → **three-valued logic**: the meaning of a missing row — true zero vs
  not-loaded vs structurally-untracked — is the meaning of `⊥`, made explicit.

## 2.5 Completeness — stated as a theorem, honestly

**The area covered (be precise):** deriving a correct lookup/aggregate query for a question in the class
**Q = { resolve an entity · filter · aggregate over axes }**, against a grounded relational/dimensional
source. Completeness has two halves.

**(I) Structural completeness** — *the structures cover the domain.* Every construct in the three mature,
finite source pattern-languages (relational normal forms; Kimball's dimensional catalogue; RDF/OWL) maps to
exactly one structure in §2.2–2.3. This is **coverage by exhaustion**, and **Chapter 03 is the proof
obligation, discharged one pattern at a time** — each pattern = one element of those catalogs landing on a
structure.

**(II) Semantic completeness** — *the captured facts suffice to derive the query.* Beyond the raw schema, the
facts a question in Q needs are a **finite set**:

```
{ grounding, identity, additivity, closure, absence, scope }
```

and the framework provides **exactly one slot for each**. The claim has two parts:

- **Necessary** — drop any one and a question in Q exists whose answer is *derivably wrong*. The **witnesses
  are the patterns**: `additivity` ← [`semi_additive_balance`](patterns/semi_additive_balance.md); `closure`
  ← [`explicit_closure`](patterns/explicit_closure.md); scoped `identity` ←
  [`context_dependent_meaning`](patterns/context_dependent_meaning.md); `scope` ←
  [`competing_definitions`](patterns/competing_definitions.md); `absence` ←
  [`absence_semantics`](patterns/absence_semantics.md). (`grounding` is necessary trivially — no grounding ⇒
  no extension.)
- **Sufficient** — with all six, `intent → query` is a **total** function (or correctly returns `⊥`).

⟹ **Complete for Q; sound by abstention outside Q.**

**What this is and isn't (AUTHORING A5).** This is rigour at the level of *argument-by-exhaustion-with-witnesses* —
real, and finishable, but **not a machine-checked proof**. To harden it: (a) make the structural map a
checkable table, (b) pin Q's grammar exactly, (c) keep the witness set complete as the fact-set grows (the
`absence` witness, `absence_semantics`, is now written). We state the shape of the theorem and exactly how
far it currently reaches.

## 2.6 The determinism corollary

Completeness (§2.5) says the needed facts are **captured**. It does *not* say they are **deterministic** —
that is a separate property, and it is the subject of [the content model](the_content_model.md): a captured
fact is deterministic where its slot is **skeleton** or a **canon**, and interpretative where it is **prose**.
So two distinct guarantees compose:

- **complete for Q** — every fact a Q-question needs has a home (this chapter);
- **deterministic for Q** — every such fact is canon/skeleton, not prose (the content model).

A pattern can be complete (fact captured) yet partly non-deterministic (fact still prose) — which is exactly
the gradient Chapter 03's patterns display.

## 2.7 A starting basis, not a settled truth (open)

Stated plainly, as the constitution requires (AUTHORING A5):

- **Is six structures enough?** We don't know. Polymorphic associations and associative-entities-with-payload
  (🔴 on the Ch.03 list) are the first stress tests; if one needs a seventh structure, it gets one — via the
  extension procedure (AUTHORING) with a witness that the six couldn't express it.
- **Is the six-fact set `{grounding, identity, additivity, closure, absence, scope}` closed?** Unknown — it is
  the smallest set that covers Q *so far*. A question in Q that needs a seventh fact would refute closure;
  that, too, is welcomed and versioned.
- **Where the math stops and prose begins** is drawn in [the content model](the_content_model.md), not here:
  the structures and the equation are exact; the interpretation of a natural-language *question* into an
  intent over them is not.

We hope this basis covers most of what a real domain throws at it. We do not claim it does — and the most
useful thing you can do is bring the case it can't model.
