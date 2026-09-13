---
when: 2026-09-13T12:06:00
what: added a ninth reject class after the gate printed a finding whose text was false about a real page
topics: [the-record, gates]
kind: defect
track: core
repo: meaning-as-code
commits: [b4092e5]
---

## WHAT FORCED IT

`2026-09-13/001-the-wiki-compiler` records eight reject classes. Running that gate against the live
protocol — which had grown to 26 entries while the tool was being written — printed this about a
page that exists and is derived from six entries:

```
[orphan-page] `wiki/platform-builder/projections.md` is stamped as topic `projections`, and no
entry carries topic `projections` — this page is derived from nothing.
```

Entries do carry topic `projections`. A new entry declared a different `track:` for it, so the topic
now compiles to `wiki/core/projections.md`, and the old page was left where it was. The gate had one
label for two situations — a topic that DISAPPEARED and a topic that MOVED — and printed the wrong
one. The compile arm already distinguished them (it moves a stamped page whose track changed, and
refuses to delete one whose topic is gone, because a move is derivable and a disappearance is not);
the check arm did not.

A finding that states something untrue is worse than no finding. It sends a reader to restore an
entry that was never lost.

## EVIDENCE

Before, on the live tree — the false finding, and a second finding for the same one situation:

```
$ python3 tools/mac_wiki.py --check
  [missing-page] topic `projections` has 3 entry(ies) but no page on disk at
  `wiki/core/projections.md` — the protocol moved ahead of the wiki; recompile
  [orphan-page] `wiki/platform-builder/projections.md` ... this page is derived from nothing.
FAIL: mac-wiki — 13 violation(s) over 15 page(s) examined, 32 span(s) verified verbatim
[class(es): missing-page, orphan-page, stale-stamp]
```

After, with the ninth class and its mutant:

```
$ python3 tools/mac_wiki.py --self-test
PASS: mac-wiki self-test — 79/79 asserted: 1 clean fixture, for a non-zero denominator and no
findings; 2 must-pass fixture(s), for clean over a non-zero denominator; 9 mutant(s), for mutation,
rejection AND attribution to their own class with no other class firing; 12 main() invocation(s),
for the verdict line and the exit code; extras: established 12 of 12 claimed
```

## WHAT CHANGED

* `misfiled-page` — a stamped page whose topic IS still derived but whose path is not the derived
  one. Its message names where the topic compiles to now and says a recompile will move it.
* `orphan-page` keeps only the case it can honestly claim: no entry carries the topic at all.
* `missing-page` is suppressed for a topic that has a misfiled copy, because one recompile answers
  both and reporting one situation twice is how a reader learns to skim findings.
* A mutant per class, so the count in `2026-09-13/001-the-wiki-compiler` is now nine, not eight.

## WHAT IT DOES NOT PROVE

* That the other eight class boundaries are right. This one was found by running the gate on a tree
  that moved underneath it, not by reasoning about the class model. Seven classes have never been
  fired by anything except their own mutant.
* That a misfiled page is rare. It was produced here by ordinary use — one entry declaring a track
  that the rest of a topic did not — within an hour of the tool existing.
