---
when: 2026-09-12T23:58:47
what: derived a register of the current requirements on each aspect from the estate itself, instead of leaving them in conversations and scattered decision records
topics: [registers, method, gates, denominators]
kind: build
track: core
repo: mac-integration-kit
commits: [mac-integration-kit:4633f75]
---

## WHAT FORCED IT

Requirements lived in conversations and in whichever decision record happened to catch them. Asked
what the latest set of requirements on any aspect of the platform was, nobody could answer without
reading the whole history.

## EVIDENCE

`git show -s 4633f75` (mac-integration-kit). The tracker itself showed why:

> 47 initiatives, 16 with a spec, 237 criteria of which 41 are met and 100 citable, and 47 carrying
> no declared aspect at all.

Gate contract met: one `PASS:`/`FAIL:` line, a printed denominator, and `--self-test` with a mutant
per reject class — `13/13` (aspect and status derived, uncitable criteria counted, drift refused,
no-specs refused). Wired into the runner, which now reads `run_gates 13/13`:

> A self-test the runner does not call is a self-test nobody runs, and this repo already ships the
> gate that makes that point.

## WHAT CHANGED

`mac_requirements.py` reads the estate and reports it as one measured register: per aspect, the
current requirement set, its status, and which criteria can actually be CITED. Derived from what is
on disk rather than maintained alongside it, because a register kept by hand is a second home for the
same fact and drifts from the first.

## WHAT IT DOES NOT PROVE

`100 citable of 237` is the honest headline and it is not a good one: well over half the recorded
acceptance criteria cannot be traced to anything. The register makes that measurable; it does not
make it smaller. `47 initiatives carrying no declared aspect` means the per-aspect view is
incomplete by construction until those are classified.
