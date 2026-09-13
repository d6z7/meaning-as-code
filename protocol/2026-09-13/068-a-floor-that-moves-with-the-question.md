---
when: 2026-09-13T14:45:00
what: a gate's floor was measured over a population the caller chose, so the same tree gave four verdicts and the runner's own calling convention silently substituted the denominator
topics: [denominators, gates, floors, harness]
kind: fix
track: core
repo: meaning-as-code
commits: [27710c2]
---

## WHAT FORCED IT

I built `check_protocol` earlier the same day and measured its floor at 6, 9 and 24 orphans at
different commit ranges without stopping to ask what that meant. A floor that changes with the
question is not a floor, and I shipped it.

## EVIDENCE

Same gate, same tree, four ranges, four verdicts:

    HEAD~12..HEAD    7 orphans   PASS (7 <= 9)
    HEAD~20..HEAD    7 orphans   PASS
    HEAD~25..HEAD   10 orphans   FAIL
    HEAD~40..HEAD   24 orphans   FAIL

The numerator came from a caller-supplied range; the floor was a bare integer that never said what
population it was measured over. **Three defects compounded:**

`HEAD~N` IS NOT FIXED EVEN AS A STRING. The floor was declared "9 over HEAD~25..HEAD / 37 examined";
one commit later that identical string measured 38 and 10. The window slid under the declaration.

A BARE TOKEN IS NOT A RANGE. `run_framework_gates.sh` hands every gate `<bundle-root>` as `argv[1]`.
`git log` read that path as a **PATHSPEC**, so the gate judged 7 commits against a floor measured
over 38 — **and printed PASS.** The runner's own convention substituted the denominator, invisibly.

AN INTEGER FLOOR IS IDENTITY-BLIND. Proved by the SWAP mutant: floor declares `{B}`, the tree's
orphans are `{C}` — same count, different identity. The old rule passes that tree; the new one fails
it. **And it was not hypothetical: at `HEAD~12` and `HEAD~20`, `c0782f9` was INVISIBLE (7 <= 9).**
Identity-blindness buys headroom for exactly the commit nobody wrote up.

## WHAT CHANGED

The floor is an **ID SET of orphan shas keyed to an immutable `BASE`** — the parent of the oldest
declared debt, so narrowing the subject can never quietly drop something the floor calls debt. Any
range resolving to another population is **REFUSED with exit 2, never answered**; `--survey` keeps
the old numbers measurable and always exits 2, because a count is not a verdict. `STANDING` must
agree with the number of shas listed or exit 2 — a self-contradictory declaration is not
half-believed. Four spellings of the declared range now produce one byte-identical verdict line.

Coverage also matches citations against the **full 40-char sha**: `git log`'s abbreviation length is
chosen from object-DB size, so the day it goes 7→8, every entry in `protocol/` would have silently
stopped covering anything.

Same commit repairs the other side of the clash, because it is one fact with two sides:
`REPO_SUBJECT_GATES` declares which gates judge the repository rather than a bundle, and **both
counts print on the verdict line.** A gate not listed that refuses a bundle root still exits 2 and
still fails the suite, so omission forgives nothing.

## WHAT IT DOES NOT PROVE

**15 undeclared orphans from 2026-08-20..09-10 now sit OUTSIDE the declared `BASE`** and are
reachable only via `--survey`. That debt is real and is not claimed gone. 10 of 53 commits are
merges, which emit no path list under `--name-only` and cannot be judged here — now disclosed on
every verdict rather than silent. And `--survey` itself has no self-test mutant; its exit-2 behaviour
was verified by hand only.
