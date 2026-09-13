---
when: 2026-09-12T12:48:43
what: traced all seven golden-replay failures to a cause instead of leaving the xfail markers that hid them
topics: [harness, gates, denominators]
kind: measurement
track: platform
repo: mac-platform
commits: [mac-platform:e56d607]
---

## WHAT FORCED IT

The previous commit had added seven `xfail(strict=True)` markers to the acceptance golden test. The
spec that governs that file forbids exactly that:

> "the discrepancy is either a bug in the implementation or a genuine new finding. INVESTIGATE IT; DO
> NOT TUNE THE GRADER UNTIL THE NUMBERS MATCH."

The markers were a holding action against the file's own convention, which is to leave a known
failure standing with the measurement in its docstring.

## EVIDENCE

`git show -s e56d607` (mac-platform). Three causes, none of them an inverted grader:

1. **Arity, not behaviour.** Schema `/4` added `rules` as a FOURTH flag. Three tests did
   `outcome, pins, value = row["flags"]` and died on the unpack while their actual assertions still
   held. They now read flags BY ID, so a fifth flag cannot break them.
2. **One question, fully attributed.** A single row moving `unrun -> routed` accounts for EVERY
   delta: `routed 11->12, unrun 72->71, outcome/pins pass 21->22, value na 14->15, evidence_stale
   24->25, warnings_total 72->73`. `proven 8, unproven 1, failed 4` are UNCHANGED.
3. **Two literal-in-the-wrong-place traps.** The schema test asserted `"/3"` as a literal and caught
   nothing, because a literal cannot tell a deliberate bump from a regression. Another test had its
   count welded into its NAME.

Result: `24 pass, 0 xfail`.

## WHAT CHANGED

`SCHEMA_ID` asserted at both ends (projector and the UI's `DASHBOARD_SCHEMA` constant) instead of a
literal in one place. Censuses updated WITH their provenance in the docstring.

A NEW FINDING was made assertable rather than invisible: the `rules` flag is INERT on this corpus —
`25 na, zero pass, zero fail`. Every row that reached it got "the ontology states no concept rule
with a never-clause", so it can currently neither prove nor refute anything.

## WHAT IT DOES NOT PROVE

That the grader is correct. It proves the seven deltas are attributable. The four standing reds are
still red and one flag is measurably inert — a flag that cannot fire is not evidence of a clean
corpus, and this entry is the record that says so.
