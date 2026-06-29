---
title: "Ch.04 — The discipline"
part_of: reference_manual
status: written
scope: GENERIC — domain-neutral.
---

# Ch.04 — The discipline

*Structure is not correctness; and — the manual's addition — correctness is not determinism. A fact you can
build on must earn trust on **two** axes, and the order in which it earns them matters. This chapter states
both, and the self-discipline that keeps the manual honest.*

> **Relationship to the canon (single-homing, A3).** The **correctness gradient** is defined in
> [`../FRAMEWORK.md`](../FRAMEWORK.md) §8 and [`../MODELLERS_COOKBOOK.md`](../MODELLERS_COOKBOOK.md) Part D;
> this chapter summarizes and **references** it (§4.1), then adds what is new here: the **determinism
> gradient** (§4.2), how the two compose (§4.3), and the manual's own review discipline (§4.4).

## 4.1 The correctness gradient (referenced, not restated)

A fact moves left-to-right, earning trust at each step (FRAMEWORK §8):

```
authored ─▶ structurally validated ─▶ execution-validated ─▶ expert-confirmed
(draft)     (the three data-free gates) (run the implied query,  (SME resolves the
                                         let data correct you)     open question)
```

The non-negotiable middle step is **execution validation**: a green validator means *well-formed*, not
*correct* — you run the query the model implies and let the data refute it. (Ch.02 §2.1 said the same
formally: a concept is a *falsifiable equation*; this is how you falsify it.)

## 4.2 The determinism gradient (the manual's addition)

Correctness asks *does the model match reality?* Determinism asks a different question entirely: *will two
LLMs reading this produce the same behaviour?* From [the content model](the_content_model.md): a
behaviour-bearing slot is **skeleton** or **canon** (deterministic) or **prose** (interpretative,
model-variant). The measurable form is **determinism coverage** (content model §6): the fraction of
behaviour-bearing slots that are canon-backed.

Chapter 03's patterns sit at visibly different points on this axis — and that is honest, not a defect:

| determinism | patterns |
| --- | --- |
| ≈ full (skeleton + canon, no remainder) | `semi_additive_balance` · `explicit_closure` · `recursive_hierarchy` · `associative_entity` |
| partial (a named, irreducible prose-fallback) | `context_dependent_meaning` · `tracking_vintage` · `competing_definitions` · `polymorphic_association` |
| mostly prose, by nature | `impurity_disposition` |

## 4.3 The two axes compose — and order matters

The axes are **orthogonal**, so a fact lives in one of four quadrants:

```
                    deterministic (canon)              prose (LLM-variant)
   correct      ┃  TRUSTWORTHY — build on it       ┃  correct but SOFT — canonize it
   not (yet)    ┃  ENFORCED-WRONG — repeatably,    ┃  a guess about a guess — fix the
   correct      ┃  confidently wrong; most danger  ┃  model first, then canonize
```

The dangerous quadrant is **bottom-left**: a canon that is *deterministic but wrong* industrializes a
mistake — it returns the same wrong answer, confidently, every time, and its very determinism hides that it
was never checked. Hence the **ordering rule of the discipline**:

> **Execution-validate first; canonize second.** Canonizing a rule you have not run against data just freezes
> a bug into a UDF. Correctness earns the right to determinism — never the reverse.

So the path for any load-bearing fact is: author → gate → **run it** (correctness) → *then* lift the prose to
a canon (determinism) → trustworthy.

## 4.4 The manual's self-discipline

Because you review the *first full version*, not each item, the manual checks itself:

- **Canons must run.** Every canon ships a runnable reference implementation and a demo with a
  **rejected/passes** (or input → output) example — the canon's own execution validation. A canon that
  doesn't run is prose in a code costume.
- **Necessity carries a witness.** Every "this fact/structure is necessary" claim (Ch.02 §2.5) names a
  pattern that breaks without it; the witness set is kept complete as the fact-set grows (A6).
- **Flag, don't enact.** When a pattern isn't absorbed by the existing constructs, the candidate framework
  change goes to [FINDINGS.md](FINDINGS.md) for the maintainer's decision — never into the schema unilaterally.
- **The constitution is the checklist.** A self-review pass against [AUTHORING.md](AUTHORING.md) A1–A10
  precedes calling anything "done": every slot classified, behaviour-bearing prose carries a seam,
  single-homed, border marked, no completeness claim, examples domain-neutral.

## 4.5 The honest end-state

A clean run of all gates means **well-formed, internally whole, and canon-backed to the coverage we have
built** — *not* "correct for your data" (that needs execution validation against it) and *not* "complete"
(we claim **coverage, not completeness**, and extend as we learn). The discipline is what keeps that claim
truthful rather than aspirational — *the discipline is the product* (FRAMEWORK §9). And the standing
invitation from Ch.00 still holds: bring the case it gets wrong, and the gradient — both axes — is how we'll
know.
