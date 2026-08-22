---
title: "Transformation is where business logic belongs"
date: 2026-08-22
status: hypothesis — evidence from one bundle, stated so it can be refuted
scope: GENERIC — domain-neutral.
---

# Transformation is where business logic belongs

A semantic layer can express a business decision two ways. It can write a **rule** — *never sum this
measure across that axis* — and then detect violations. Or it can **bake the decision into a
transformation**, so the relation downstream has one value on that axis and the violation cannot be
expressed at all.

> **The hypothesis: a rule baked into a transformation stops being a rule and becomes a mapping
> claim — and mapping claims are mechanically testable, while rules are not.**

## The conversion, concretely

| as a rule | as a baked transformation |
|---|---|
| *"never sum across the consolidated and constituent rows"* | this relation has one value on that axis |
| needs scope-aware analysis of arbitrary SQL | `count(DISTINCT axis)` must be 1 |
| a violation must be **detected** after it happens | a violation cannot be **expressed** |

The first is the harder elevation — a claim about correct *use*, judgeable only by inspecting a query.
The second is the easier one — a claim about correspondence, checkable against data alone. Baking
moves a claim across the boundary.

## What a chain looks like when the rules are run as steps

Measured on one fact relation, five decisions that existed only as sentences, applied in sequence:

| step | rows after | keeps |
|---|---:|---:|
| raw fact | 800.821.485 | — |
| restrict to the readable delivery labels | 442.426.434 | 55,2 % |
| restrict to the official plan level | 442.426.434 | **100,0 %** |
| restrict to the marques in scope | 428.669.926 | 96,9 % |
| pin the consolidated perspective | 207.226.410 | 48,3 % |
| read as of one reporting cycle | 5.906.042 | 2,9 % |

Two things are visible here that were not visible while the same decisions were sentences.

**One step removes nothing.** The third keeps 100,0 %. Either every surviving row already satisfies it,
or the rule is redundant on this relation. As prose it had been unfalsifiable indefinitely; as a step
it is a one-line no-op. **The chain does not only implement the rules — it exposes which of them do
nothing.**

**One step halves the data.** The consolidated perspective restates the constituent rows rather than
partitioning them; summing across the axis double-counts. After that step, the rule forbidding the
sum is unnecessary, because there is one value to sum.

## The cost is optionality, and it is a ruling

Baking is not free and should never be automatic.

Pin the consolidated perspective and questions about a constituent's own view become unanswerable.
In the measured case, an upstream system bakes a stricter filter still — and the local deployment
*rejected* it, because it returns no rows for the current period. That is not a defect in either
system; it is two different answers to *what is this relation for*, and the answer belongs to a
domain expert, per bake.

Which is why the discipline matters more than the technique: **a transformation that bakes without
declaring what it baked is a black box.** The declaration is what keeps a baked decision
challengeable.

## Design time is human. Run time is mechanical.

The claim most likely to be resisted, and the one this rests on:

> **A transformation step cannot be verified mechanically at design time.**

Nothing in the data says whether collapsing two product variants into one name is correct. A machine
can prove the step ran, that the output has 1.108 rows and 223 distinct names, that nothing became
null. It cannot prove that is what the business meant.

| | design time | run time |
|---|---|---|
| who | domain expert + engineer + machine | machine |
| what | instruction → fragment → **look at the output** → approve | detect deviation from the approved shape |
| verdict | ratification | pass / fail |

This reverses a natural assumption about a declared guarantee. It is **not** something to prove when
the step is written. It is the **record of what the expert approved**, and its whole job is to be
checked forever afterwards.

### Two kinds of prose, and only one is a defect

The distinction that makes the model coherent:

- prose **substituting** for logic — a step whose implementation field contains a sentence. A defect:
  it cannot be executed, profiled, or compiled.
- prose as the **instruction that produces** logic — the expert states intent, the engineer writes the
  fragment, the expert validates the output. **Necessary**, and the only way semantics can be
  specified at all.

A chain needs both, joined by an approval of the observed output. In the measured bundle, of fifteen
declared steps: **fifteen carry an instruction, three carry anything resembling executable code, and
none records an approval.** The status vocabulary has two values, *authored* and *applied* — both
describing what the authors did. Neither says a domain expert looked at the output and agreed.

A decision recorded without its decider is the same defect as a test marked *accepted* with no
acceptor, and it is equally invisible.

## Why steps cost nothing to keep

An objection to decomposition is materialisation: fifteen relations become fifty, and someone pays
for storage and refresh.

They need not exist. A step's output can be profiled as a subquery — grain, domains, nullability, the
diff against the previous step — at the cost of one scan and no table. And the chain compiles: N step
fragments become one relation for production, mechanically, the same operation as inlining a fragment
into a query.

So the real cost is not storage. **It is that the steps must become code**, which returns to the
harder problem: a field that accepts a sentence will contain one.

## What would falsify this

- A business decision that genuinely cannot be baked, yet is reliably enforced as a rule, would
  bound the claim. *Refusal* rules are already known to be outside it: no relation can make an engine
  say "not reported."
- If baking a decision produced more downstream error than the rule it replaced — because the bake
  was wrong and invisible — the claim needs the declaration discipline to be *mandatory*, not
  advisory.
- If a domain expert cannot validate a step's output in reasonable time, the design-time half fails
  and the chain is no better than the monolith it replaced.

The cheapest test: **take the relation carrying the most rules, run each rule as a step, and show a
domain expert the before and after.** If the reductions are legible to them, the model holds. If they
cannot tell, it does not — and that is worth knowing in an afternoon rather than after a rebuild.
