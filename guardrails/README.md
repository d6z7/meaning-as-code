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

## Files

| file | topic |
|---|---|
| `data-ingestion.yaml` | phase 1 — the landing plane: what an ingestion of data SOURCES owes |
