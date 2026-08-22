---
title: "Two elevations: why mapping can be derived and ruling cannot"
date: 2026-08-22
status: hypothesis — evidence from one bundle, stated so it can be refuted
scope: GENERIC — domain-neutral. The measurements come from one deployment and are marked as such.
---

# Two elevations

An ontology makes two kinds of claim about a database, and almost every difficulty in building one
comes from treating them as the same kind.

> **MAPPING is a claim of CORRESPONDENCE.** *This concept is these columns of this relation.*
> Checkable against data alone.
>
> **RULING is a claim about CORRECT USE.** *You may not sum this measure across that axis.*
> Not checkable against data alone — it needs a query, or an answer, to judge.

The hypothesis is that this distinction is load-bearing: **mapping is mechanically derivable and
ruling is not**, and a system that mixes them will keep trying to automate the half that cannot be.

## What derivation actually reaches

Given a relation and nothing else, a profiler can establish, exactly and dated:

- the **grain** — by growing a minimal key, then testing whether omitting each column makes the
  *measure disagree*, not merely split
- **functional dependencies** — which column determines which
- **value domains**, **nullability**, **uniqueness**, and the **earliest** value of a date domain

That is enough to generate a test suite. In one deployment, **238 of 288 acceptance properties are
generated from those measurements**; nobody authored them.

### Splitting, and disagreeing, are different questions

The subtlety that makes grain derivable at all: a discrimination test alone gets it wrong.

Removing a column from a candidate key may **split** groups without making the measure **disagree** —
which means the column identifies a *delivery* of a figure rather than a *figure*. In the measured
case, one axis scored 0,0000 % disagreement over 11.195.386 split groups and another 0,0161 % over
11.689.530, while the genuine identity columns scored 93 % to 99 %. Four significant figures separate
the two populations, and nothing separates the two members of the residue.

So the machine can say: *these eighteen columns are settled, and these two are not.*

## The reduction is the product

That is the claim worth testing:

> **Autodiscovery does not answer the questions. It reduces them to a small, EXHAUSTIVE list — and
> the list is known to be complete, because everything not on it was settled by measurement.**

Twenty columns became two questions. The two were genuinely undecidable from data, because the
difference between them is what the business *means*. A domain expert answered both in a sentence
each, and the answers are now enforced by generation forever.

Not "the machine understood the data." Something narrower and far more useful: **the unknown was
reduced to a finite ratification list, and you can prove the list is complete.**

## Where derivation stops

An attempt was made to derive the other elevation. Twenty-three rules stated their directive in
prose; a large agent pass drafted machine-readable directives for eighteen of them, each draft was
then attacked by an independent reviewer instructed to default to *refuted*.

**Eighteen drafted. Eighteen refuted. None ratifiable.**

The cause was not that the rules were badly written. Consider a rule that says *"never sum across the
consolidated and the constituent rows."* Perfectly clear to a person, and silent on everything a
machine needs:

- at what **scope** — one SELECT, or the whole statement?
- does a pin in a subquery govern an aggregate in the outer query?
- is it violated by summing, or by *failing to pin*? Those differ when the axis is absent.
- what is the **violation instance** — a query, a row, or a number?

A gate built to answer these was wrong twice in one sitting — not because the rule was unclear, but
because **the rule had never been asked.** Prose is cheap precisely because it defers the questions
that formalising forces, and a human reader supplies the missing answers from context without
noticing they were missing.

An agent asked to formalise such a rule is therefore not transcribing. It is *deciding* — and
eighteen refutations is a better outcome than eighteen plausible rules, because plausibility survives
review in a way error does not.

## The instruments follow from the elevation

Once the distinction is made, which instrument a claim needs stops being a matter of taste:

| the claim constrains | example | instrument |
|---|---|---|
| the DATA | *every code resolves in the register* | a **property** — SQL against the warehouse |
| the ANSWER | *where no row exists, refuse; never return a zero* | a **question** put to the engine |

No SQL can test the second. A query that returns nothing and an engine that correctly says *"not
reported"* are indistinguishable in the data. This was discovered by building the generators, not by
designing them: one canon pattern produced properties and another produced nothing, and the reason
was that its claim was about speech rather than about rows.

## What would falsify this

- A rule whose directive is genuinely derivable from data alone, with no human ruling, would weaken
  the second half. *Candidate values* can be derived — the residue above proves that — but a candidate
  is not a directive.
- A mapping fact that measurement cannot settle even in principle would weaken the first.
- If a system reliably converts prose rules to executable form without a human deciding what a
  violation is, the hypothesis is simply wrong.

The prediction it makes is testable and cheap: **for any unknown relation, the ratio of columns
settled by measurement to columns requiring a ruling should be large, and the residue should be the
axes a domain expert would also name as ambiguous.** In the measured case it was eighteen to two, and
the two were the right two.
