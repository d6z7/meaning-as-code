---
when: 2026-09-13T11:52:00
what: built the wiki compiler, so a topic page is derived from the protocol and stamped with what it was compiled from
topics: [the-record, gates, denominators]
kind: build
track: core
repo: meaning-as-code
---

## WHAT FORCED IT

`protocol/README.md` and `wiki/README.md` had already decided the shape — raw and append-only on one
side, compiled and by-audience on the other — and nothing existed to get from one to the other. The
gap is not a missing convenience. It is the one step where a person summarises, and
`sdk/project/knowledge.py` states why that step is the dangerous one:

> VERBATIM OR NOTHING. Every span rendered here is quoted from the extraction, never paraphrased.
> That is not stylistic: it makes the register mechanically verifiable — a gate can assert that each
> span still appears in the source, which is impossible once someone has summarised it.

The concrete failure this has to stop is a measurement turning into a mood: an entry saying
`0 leak(s) over 488 tracked file(s)` becoming a page that says "the repository is clean". The second
sentence has no denominator, and this estate has already shipped a gate that reported PASS over zero
files.

## EVIDENCE

The self-test, after the repair described below:

```
$ python3 tools/mac_wiki.py --self-test
PASS: mac-wiki self-test — 73/73 asserted: 1 clean fixture, for a non-zero denominator and no
findings; 2 must-pass fixture(s), for clean over a non-zero denominator; 8 mutant(s), for mutation,
rejection AND attribution to their own class with no other class firing; 11 main() invocation(s),
for the verdict line and the exit code; extras: established 12 of 12 claimed
```

The first run of that self-test failed, and the failure is worth more than the pass:

```
  mutant not caught: paraphrased-quote
  mutant 'paraphrased-quote': gate reported 0 finding(s) but attributed NO class
FAIL: mac-wiki self-test — 4 of 73 assertions failed
```

The seeder for `paraphrased-quote` substituted a string that was not present — the quoted line is
indented inside its entry — so it rewrote the page without changing it. The harness caught it only
because the mutant then went unrejected. That is the same defect as a self-test passing because the
token it planted was already absent, so `_rewrite` now refuses to be a no-op and raises instead.

Against the live tree, after the protocol reached 20 entries:

```
$ python3 tools/mac_wiki.py --check
PASS: mac-wiki — 0 violation(s) over 11 page(s) examined, 276 span(s) verified verbatim — 20
entry(ies) -> 11 page(s) (core 9, ontology-builder 0, platform-builder 2); 0 entry(ies) carried NO
topic and are on no page; 0 entry(ies) declared no track
```

Before the first compile, over the same protocol, the gate refused rather than reporting either
verdict:

```
could not run: mac-wiki — 10 page(s) examined but 0 span(s) verified verbatim: the gate declared
span(s) verified verbatim as what it judges BY, so zero of them is a missing yardstick, not a clean
tree (10 finding(s) held, unjudged)
```

## WHAT CHANGED

`tools/mac_wiki.py` — named `mac_*` because in `tools/` that prefix means generator and `check_*`
means a read-only gate swept by `run_framework_gates.sh`; this one WRITES, and the same shape is
already set by `tools/mac_resources.py`.

* A page is rendered as verbatim spans plus citations. The only transform applied to a span is the
  blockquote prefix, it is reversible, and comparison is line-by-line with trailing whitespace
  stripped. That is the entire tolerance.
* Each page carries a `source_hash` — sha256 over each compiled entry's id and bytes — the same
  instrument `mac_resources.py` uses as `tree_hash`, for the same stated reason: "A description
  maintained by hand drifts from the tree it describes, and there is nothing to catch it."
* Routing is derived, not defaulted: one declared `track:` sends the topic to that audience, two
  different tracks send it to `wiki/core/` because a topic both audiences touch is shared law, and
  nobody declaring one files it under core with the stamp saying exactly that.
* Eight reject classes, evaluated first-match per page so that eight labels are eight predicates:
  `missing-page`, `stale-stamp`, `unstamped-page`, `orphan-page`, `paraphrased-quote`,
  `hand-edited-page`, `unknown-track`, `malformed-topic`.
* An entry the compiler cannot place quarantines its topics: those pages are not judged this run.
  Reporting a stale page downstream of an unreadable entry is reporting a symptom.
* The verdict line carries three numbers a reader would otherwise never see: pages examined, spans
  verified verbatim, and entries that carried NO topic and are therefore on no page.

## WHAT IT DOES NOT PROVE

* That any `file:line` an entry cites still exists. The pages render those citations under a heading
  that says, in the page, that this compiler has not checked them. A citation gate is a separate
  instrument and does not exist yet.
* That the grouping is right. Which topic an entry belongs to is judgement, made by whoever wrote
  the entry; the compiler only proves the page did not invent anything.
* That an entry is honest. A paraphrase committed INSIDE a protocol entry is quoted faithfully onto
  the page. Verbatim protects the compiled layer, not the raw one.
* Anything about `wiki/ontology-builder/`. It holds 0 pages over 20 entries, because no entry so far
  declared `track: ontology` — the compiler reports that number rather than filling the directory.
