---
when: 2026-09-12T20:14:59
what: built aggregate gate runners in the product and framework repos, now that a green line means something, and took an honest inventory of all 34 framework checkers
topics: [gates, harness, denominators]
kind: build
track: core
repo: meaning-as-code
commits: [1a69768, mac-platform:a82dbc5]
---

## WHAT FORCED IT

The framework's checkers were run one at a time, by hand, with no aggregate verdict and no honest
denominator for "how many of our own gates actually ran". An aggregate runner BEFORE the contract
work would have been worse than nothing: a gate that prints PASS having examined zero files
contributes a green line and no evidence, and three of them did exactly that.

## EVIDENCE

`git show -s a82dbc5` (mac-platform, 19:44) and `1a69768` (meaning-as-code, 20:14).

```
PASS: run_all_gates — 12/12 green
```

Measured by the framework runner over 34 checkers, against real bundles, none of them modified:

```
example_shop_ontology  FAIL: 30/34 green, 3 failing, 1 could-not-run (13s)
example_tpch_ontology  FAIL: 29/34 green, 2 failing, 3 could-not-run (13s)
<domain>/<bundle>      FAIL: 27/34 green, 7 failing, 0 could-not-run (40s)
```

Every failing / could-not-run there is pre-existing bundle content — confirmed unchanged against the
compiler's own error counts before and after — or a legitimate could-not-run. None of the 34
checkers were modified to make a bundle look cleaner than it is.

The INVENTORY was taken by actually invoking each checker, not guessed: `--self-test` where the
literal flag string is wired, exit code against a nonexistent root, and whether a `PASS:`/`FAIL:`
line with an explicit denominator appears. Before the packet, 4 of 34 were already at contract.

## WHAT CHANGED

A checker's own exit 2 is counted SEPARATELY from pass and fail and can never read as a pass —
folding it into "green" is the exact false confidence the programme exists to remove.

Five checkers were brought to contract, chosen by the worst offence: no exit-2 path AND no
denominator AND reachable on a real bundle. Each treated a NONEXISTENT bundle root identically to a
legitimate empty state, printing the same tick and exit 0 either way. One produced a full zero-valued
1104-line report ending "EXIT 0"; three answered `✓ OK ... nothing to check` for a root that does not
exist.

## WHAT IT DOES NOT PROVE

The budget was fixed at five and the commit names what it did NOT touch, which is the part worth
keeping: five more gates carry the SAME nonexistent-root-reads-as-clean defect. Two of them have real
self-tests elsewhere so their residual gap is narrower; four have no self-test and no exit-2 path at
all — "the next packet's honest starting point". As of `2026-09-13`, 14 of 34 framework checkers
still have no self-test.
