---
when: 2026-09-12T16:00:16
what: recorded the P5 repository design and the live gate defect it found on the way, plus the first estate-wide measurement of gate-contract compliance
topics: [gates, harness, denominators, the-public-boundary]
kind: measurement
track: core
repo: mac-integration-kit
---

## WHAT FORCED IT

An architect was asked to design the merged repository. It built the thing, installed it into five
clean venvs, and falsified two premises of its own brief — and found a live defect in the gate that
guards the invariant the whole programme is about. The defect outranks the design it came from, so it
is recorded first.

## EVIDENCE

`git show -s 177d94f ef50545` (mac-integration-kit). The defect, re-verified independently:

> a bundle can set the verdict of the gate written to police it. The checker imports a plugin the
> SUBJECT supplies and guards it with `except Exception`, which SystemExit is not a subclass of. Both
> branches of that one function are wrong in opposite directions — the subject's exit code becomes
> the gate's verdict, or a silent identity fallback reports every unresolved slot as a fabricated
> identifier.

> This machine has the missing dependency, so the gate reads OK here. It is invisible on the author's
> machine and present everywhere else.

Three further measurements:

* `jsonschema` is missing from the framework's declared dependencies, so a verify-only install cannot
  reach a compile verdict at all — the two compile diagnostics come back UNKNOWN rather than clean.
  `+6 packages, +3 MB.`
* an extras boundary is not import-visible: all 26 modules import in the verify install because the
  heavy imports are function-local. A purity gate must be STATIC; the naive design would have shipped
  one that passes on everything.
* `check_gate_contract`, run against the estate's 41 gates: **147 findings, no-verdict 38/41,
  no-self-test 29/41, no-denominator 28/41.** The grain gate's breaches are the estate MEDIAN, not an
  outlier — corroborated from an independent direction.

A disclosure claim was corrected in the same record: the architect measured `develop`, but the public
default branch is `main`, where the scrub had already landed. Public face on this date was two files
carrying real customer literals, not sixty-two — with `develop` 109 commits ahead and carrying all
52, the normative schema included.

## WHAT CHANGED

The record; nothing was built from this design on this date. The defect it found was picked up as
packet P0.3 the same afternoon (`2026-09-12/011`), and the 41-gate measurement became the argument
for the shared gate contract (`2026-09-12/014`).

## WHAT IT DOES NOT PROVE

`147 findings over 41 gates` is a contract-shape census, not a correctness census: a gate can carry a
verdict line, a denominator and a self-test and still be measuring the wrong thing. It also does not
prove the exposure is bounded — "two files today" is a statement about one branch at one moment, and
the forward-looking half (a release merge publishes 52) is what actually forced the cleanse.
