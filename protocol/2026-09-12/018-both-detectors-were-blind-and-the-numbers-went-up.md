---
when: 2026-09-12T19:43:21
what: fixed the denominators of both public-hygiene detectors — one counted its own build output, the other could not see the identifiers it exists to find — and ratcheted each at its measured floor
topics: [the-public-boundary, gates, denominators, ratchets]
kind: defect
track: core
repo: meaning-as-code
---

## WHAT FORCED IT

The phase's recorded criterion was "neutrality 213 -> 0, hygiene 611 -> 0". It had no correct number
in it, on either half.

**The hygiene gate counted its own build output.** 611 findings, of which 311 were in `build/` — a
directory holding ZERO tracked files. Half the reported debt was the gate reading its own build
output and calling it a disclosure. `SKIP_DIRS` omitted `build`, and the scan walked the filesystem
with `rglob` rather than asking git what is tracked.

**The neutrality detector could not see the source's own identifiers.** Its pattern was
`\b(<source>|<brand>|...)\b`, and `\b` after a source token requires a NON-word character. Measured
before changing anything, with the instance tokens redacted here as `<source>`:

```
SCHEMA = "<source>2"        INVISIBLE
table  = "<source>2.v_kpi"  INVISIBLE
q      = "v_<source>_kpi"   INVISIBLE     <- the actual view names
x      = "<source>"         caught
```

It caught the bare English word and missed every real identifier. A planted leak using the schema
name did not turn the gate red — so the gate's green was a property of its blindness, not of the
tree.

## EVIDENCE

`git show -s 0a23934` (meaning-as-code) and `393ad70` (mac-platform).

```
hygiene     before  611 findings  (311 in build/, 0 tracked files there)
            after   300 findings  (0 in build/)  over 290 tracked file(s) examined

neutrality  before  213
            after   257  (181 in shipped code, 76 in tests and fixtures; all audited, no false
                          positives)
```

The hygiene gate also had no argparse and read `sys.argv[1]` as a path, so `--root src` globbed a
directory literally named `--root`, found nothing, and printed "clean" with exit 0. Reproduced before
fixing; now exit 2.

`--self-test 5/5`, including the true negative that matters: the same token in a gitignored build
file must NOT be reported. Its fixture token is derived from the gate's own pattern table rather than
typed, because this gate COUNTS such tokens and a spelled-out one would plant what it scans for.

## WHAT CHANGED

Both populations now come from `git ls-files`, both verdicts carry a denominator, and 0 files scanned
is exit 2 rather than a neutral report.

The neutrality detector gained two match modes: SOURCE identifiers match as SUBSTRINGS, because
appearing inside a longer identifier is exactly where such a leak hides; ordinary words and
abbreviations stay word-bounded, because an unbounded two-letter abbreviation matches `software`,
`viewport`, `switch` and half the alphabet soup in any codebase. Asserted both ways — 3
previously-invisible forms caught, 5 ordinary words still clean.

Both gained a RATCHET at the measured floor. "Burn down to 0" is not reachable while a gate's own
denylist and its tests must name the terms they forbid; the criterion is ZERO NEW findings above a
declared, measured floor, with the instruction to lower it and never raise it.

## WHAT IT DOES NOT PROVE

Strengthening a detector makes the number go UP, and the number has to be true before it is worth
reducing. Neither 300 nor 257 is a debt measurement anyone had before this date, and neither is a
clean tree. The hygiene floor was later found to be a ratchet in name only — 146 was declared while
the count fell to 4, leaving 141 findings of silent headroom (`2026-09-13/059`).
