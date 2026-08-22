---
title: "Prose wins wherever the schema permits it"
date: 2026-08-22
status: hypothesis — evidence from one bundle, stated so it can be refuted
scope: GENERIC — domain-neutral.
---

# Prose wins wherever the schema permits it

A knowledge artefact accumulates prose in exactly the places its schema accepts prose, and no amount
of discipline reverses that. The hypothesis:

> **Where a field will accept a sentence, it will eventually contain one — and the sentence will be
> read as though it were enforced.**

This is not a claim about carelessness. It is a claim about gradients: a sentence is always cheaper
to write than a specification, so wherever both are legal the sentence wins.

## The same defect in four planes

Measured on one bundle, all four at once:

| plane | the permissive field | what it cost |
|---|---|---|
| rules | the directive is free text | 23 of 31 rules untestable |
| transformations | a step's implementation is free text | **0 of 15 steps carry executable code**; 14 declared guarantees unverifiable |
| test corpus | *what this question exercises* is free text | 96 of 101 questions cannot be linked to any rule |
| extensions | `^x-` keys permitted in **58 places** of the schema | an extension held a false grain for four days |

Four planes, one shape. In each case the container accepted prose and nothing objected.

## The cost is not confusion — it is invisible staleness

Prose can be true, false, or **stale**, and nothing distinguishes them.

In the measured case, an extension field declared a relation's identity key and carried the word
*VERIFIED* with a date. Four days later the same claim was checked against the warehouse: two of the
four such declarations were false, one of them describing 11.689.530 duplicate figures as zero. The
field had been read by a downstream component the entire time.

Nothing was wrong with the people or the process. The field was **unreachable by every gate in the
system**, so being wrong cost nothing, and correctness decayed the way anything uninspected decays.

A machine-readable form can be *wrong*. It cannot be *quietly stale* — it either renders or refuses.

## Closing the hatch works, and works quickly

Of the four planes, one was fixed. The `^x-` escape was written into the schema as:

```
"additionalProperties": false,
"patternProperties": { "^x-": true }
```

Every closure in the document was undone by the line beside it, and `true` means *any shape, no
validation*. The extensions were therefore never violations — **the schema sanctioned them.**

Removing the fifty-eight exemptions took an afternoon, and afterwards an extension key produced a
schema error rather than a checker's opinion. The problem did not recur, because it could not be
expressed.

The generalisation:

> **The cheapest formalisation lever is not discipline, tooling, or review. It is making the informal
> path impossible.**

## Why a consumer is the second-cheapest lever

Before the hatch was closed, nothing had made the scale of the rules problem visible. What made it
visible was building a **generator** — a tool that had to read the rules to emit tests. It reported
that none could be read, and that number had not existed before.

This suggests a principle:

> **A tool formalises exactly the plane it must consume, and no other.**

A generator forces rules to become executable. A compiler forces transformation steps to become code.
A grader forces test questions to name what they test. An explorer forces relationships to be real.
Each converts one plane from prose to program, and none of them helps the others.

Which also bounds the ambition of any single tool. A step-by-step transformation editor cannot render
a panel for a step whose implementation is a sentence — so it forces *that* plane, immediately and
visibly. It does nothing for the rules, because rules are not in its path.

## What would falsify this

- A field that has accepted prose for a long period and contains none would be a direct counterexample.
- If closing an escape hatch produced pressure that reappeared elsewhere rather than dissolving, the
  "make it impossible" claim would need weakening.
- If a plane became formal through review discipline alone, without a consumer demanding it, the
  second half is wrong.

The prediction is cheap to test on any existing artefact: **list the fields whose schema type is
effectively `string`, and check what proportion carry a specification versus a sentence.** The
hypothesis says the proportion will be poor wherever nothing consumes the field.
