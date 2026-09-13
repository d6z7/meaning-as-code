---
when: 2026-09-12T15:32:47
what: committed the five-agent topology review and its five re-planned phases into the repo that owns the method they govern
topics: [method, consolidation, gates]
kind: decision
track: core
repo: mac-integration-kit
commits: [mac-integration-kit:31f5c98]
---

## WHAT FORCED IT

The review's ruling existed only as an untracked file: seventeen hours of five-agent analysis, two
evaluations and five execution plans, one `rm` from gone.

## EVIDENCE

`git show -s 31f5c98` (mac-integration-kit). Every estate-describing number in the new §8 was
re-measured independently of the planner that reported it, and the two that could not be reproduced
are attributed rather than restated. Six findings landed from that re-measurement:

> - the base branch must be `feat/absorb-gui`; `develop` carries neither package nor
>   `boundaries.yaml` and is 1 commit ahead of master against the branch's 224
> - exit 2 belongs to `main()`, never `check()` — four gates are called in-process by the publisher,
>   which would read "could not run" as a finding
> - `make check` never invokes these gates, so the phase's make-facing work was scoped against an
>   integration that does not exist
> - `check_source_coupling` is blind to the f-string its own docstring cites: Python 3.12 emits
>   FSTRING_*, not STRING. Green because blind, not because clean
> - the grain gate returns 62 or 66 for the same commit depending on the interpreter hash seed
> - running the harness regenerates the acceptance suites in place, so a before/after must pin to a
>   SHA, not to a tree it is also rewriting

It also corrected an inversion in the review's own §6: `check_write_paths`' default root is the
correct subject (28 files, a real finding); the repo root is where it passes on zero.

## WHAT CHANGED

The review and all five phases are tracked. Status PROPOSED, not accepted — ratification is the
operator's act, and §4/§6/§7/§8 carry the items only they can settle. The board's "~8 working days"
was stale the moment §6 landed; all five phases re-planned come to ≈10.25.

## WHAT IT DOES NOT PROVE

A plan is not a measurement. Three of the six findings above were later measured to be understated
(`2026-09-12/017` on the grain gate, `2026-09-12/018` on both detectors), which is the expected
direction: re-measuring a blind instrument makes numbers go UP. The review's authority here is that
it survives an `rm`, not that its numbers are final.
