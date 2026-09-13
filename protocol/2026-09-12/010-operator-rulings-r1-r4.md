---
when: 2026-09-12T16:21:00
what: recorded operator rulings R1-R4 and re-scoped P0.3 after its "currently green" premise was falsified
topics: [method, gates, grammar]
kind: ruling
track: core
repo: mac-integration-kit
commits: [mac-integration-kit:33189f9]
---

## WHAT FORCED IT

Five phases were planned against premises an agent had asserted. One of those premises — that the
fabricated-identifier gate is "currently green" — had just been falsified: it is green on ONE machine.
Wiring it as it stood would have locked a lie into CI.

## EVIDENCE

`git show -s 33189f9` (mac-integration-kit):

> R1 pin to a develop SHA (P2 unblocks, nothing published). R2 the generated acceptance suites are a
> projection, so the harness regenerating them in place is lawful and the author-tool count drops
> 9 -> 6. R3 the model-authored-SQL ban is runtime-only; ADR D2 is a runtime invariant and authoring
> may draft what a gate and a human seal. R4 commit authority on the feature branch only: no
> deletions, no pushes, no merge to develop without the operator.

The §1 merger proposal was declined for now, with a sharper trigger to revisit — the first lockstep
change across both homes, rather than the arrival of a second consumer estate.

## WHAT CHANGED

R4 has two mechanical consequences, both recorded at the time: P2.1 must meet its exit criterion
WITHOUT deleting the vendored fork, and P4, which IS subtraction, cannot complete — it is prepared as
one reviewable commit instead.

P0.3 was re-scoped to absorb the seam fix, and its exit criterion became "a verdict that does not
move with the subject's dependencies" rather than "wired into CI".

## WHAT IT DOES NOT PROVE

R3 is the ruling with the longest reach and the least evidence behind it: it scopes an invariant to
answer time on the grounds that authoring may draft SQL a gate and a human seal. That is a
judgement, not a measurement, and it was tested within four hours — the advisor path was found to
execute live queries in response to a user's question, which R3 does NOT cover
(`2026-09-12/021`).
