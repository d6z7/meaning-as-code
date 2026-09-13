---
when: 2026-09-12T19:47:06
what: neutralised the detector probe strings that had been quoted verbatim into a public method document, after pushing past the gate that caught them
topics: [the-public-boundary, gates, method]
kind: defect
track: core
repo: mac-integration-kit
commits: [mac-integration-kit:f2adef0]
---

## WHAT FORCED IT

A decision-record section quoted the neutrality detector's denylist and its probe strings VERBATIM to
explain the regex defect. That put instance tokens into the kit's own method documentation — the
documentation that is PROJECTED onto every machine that installs the method — and the doc gate caught
three of them.

## EVIDENCE

`git show -s f2adef0` (mac-integration-kit), which records the process failure alongside the content
failure:

> The gate went red and I pushed anyway before reading it, which is the second time today.

The first time was the same day at 18:08, when three red tests were pushed unread
(`2026-09-12/016`).

> The finding was never about WHICH words are on the list; it is about the regex shape — a
> \b-bounded alternation cannot match a token inside a longer identifier. The probes now read
> `<source>2` / `<source>2.v_kpi` / `v_<source>_kpi` and say exactly the same thing without carrying
> the instance.

`PASS: run_gates — 12/12 gates green`.

## WHAT CHANGED

Three probe strings replaced by placeholders that preserve the SHAPE the finding is about. The rule
this establishes is the same division-of-labour constraint the detectors themselves have: a document
that forbids naming a source may not name one to make its point.

## WHAT IT DOES NOT PROVE

That the class is closed. This was caught because a gate ran on a text file; the same tokens in a
commit message, a branch name or an issue body are outside every gate in this estate. The protocol
you are reading inherits the constraint and the exposure — these entries quote the same measurements
and redact by hand.
