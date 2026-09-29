# guardrails/

One file per TOPIC. Small, readable, independently rulable — the way `ontology/concepts/` works,
and for the same reason: a five-hundred-line file is a file nobody reads, and a topic buried in one
cannot be approved, revised or retired on its own.

## What a guardrail file is

A guardrail declares, for ONE topic:

| block | what it settles |
|---|---|
| `delivers` | the items the topic owes — each with its path, naming rule, producer, consumers, checker |
| `conventions` | the spellings that are CLOSED, and what owns each one |
| `refuses` | the actions that are blocked outright, with the reason and what to do instead |
| `watch` | where the measurement is written, and what a person looks at |

## The one rule about rules

**UNSPECIFIED IS NOT RULED.** A guardrail constrains exactly what it declares and nothing else.
There is no rule by omission, no implicit convention, no "it should have been obvious". If a thing
is not in a guardrail, doing it is allowed — and if that turns out to be wrong, the fix is to write
the rule down, not to expect it to have been inferred.

This is deliberate and it is what makes starting small safe. `data-ingestion` rules the landing
plane. It says nothing about datasets, the ontology, or the acceptance plane, and it must not be
read as if it did.

## Why this exists

Measured 2026-09-28: one bundle was ingested five times in a day and each run lost a different
deliverable — the lineage artifact, then the whole data-quality assessment, then the SME questions —
while every run reported itself complete. Operator: *"every new time you have managed to forget
someting ... this is maximal unreliability and it is unacceptable."*

It was not forgetting. Anything not written down as a durable artifact gets RE-DERIVED on the next
run, and re-derivation is stochastic. The answer is not a better instruction; it is a declaration
that a deterministic check can hold the work to.

## REPORTING IS NOT REFUSING

Every gate in this estate reports. On 2026-09-28 `conformance` printed FAIL and the delivery carried
on to completion; `mac_artifacts.yaml` was committed unparseable because nothing stood between
writing it and committing it. A finding delivered after the fact is a record of a mistake. A
guardrail that cannot say NO at the moment of the action is a note, not a guard.

So each topic declares `refuses`, and those are enforced by a hook that blocks the tool call — not
by a checker that complains about it later.

## How it is laid out

Grouped by PLANE, then one file per SUBJECT within it — the way `ontology/concepts/` groups by
domain. The topic id is the path, dotted: `data/sources.yaml` declares `topic: data.sources`.

```
guardrails/
  common.yaml                  rules that hold everywhere; delivers NOTHING
  unfiled.yaml                 delivered, and filed under no subject yet — the debt list
  data/
    sources.yaml               what is THERE      — the physical layer, described
    quality.yaml               what is WRONG      — findings and their projections
    sme_questions.yaml         what must be DECIDED
    transformation.yaml        what we decided to SERVE — and it CONSUMES the two above
  ontology/                    empty; see its README. Unruled is not unnoticed.
```

**TOPIC IS SUBJECT. PHASE IS DELIVERY.** They are not the same axis, and conflating them is what
made an earlier file called `data-ingestion` declare `phase: sources` over a set of items that were
mostly written by both deliveries. A topic groups by what an artifact is ABOUT; the phase lives on
the ITEM and says which delivery owes it.

**A LOADER HERE MUST RECURSE.** A flat `guardrails/*.yaml` sees `common` and `unfiled` and misses
every topic under `data/` — measured the hour this tree was grouped: 2 topics found instead of 6,
which would have reported a complete delivery as entirely undeclared. This estate's most-repeated
defect is a flat glob over a grouped directory; the worst instance ships an empty
`usage_guardrails.md`, 30 lines against 645, because `references.py` globs `concepts/*.yaml`.

**A KIND BELONGS TO EXACTLY ONE FILE.** Moving one between topics is a MOVE, never a copy — which
is why no precedence rule exists anywhere in this tree, and why `bom.conflicts` must stay empty.
I have made that mistake twice; the gate caught it both times.
