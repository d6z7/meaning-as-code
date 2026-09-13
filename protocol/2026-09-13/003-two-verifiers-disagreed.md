---
when: 2026-09-13T12:41:00
what: measured a disagreement between the wiki compiler and the citation gate over the same 556 spans, and found the compiler was right and its own line addresses were unverified
topics: [the-record, gates, denominators]
kind: measurement
track: core
repo: meaning-as-code
commits: [b4092e5]
---

## WHAT FORCED IT

Two tools were built in parallel for the two ends of one seam: `tools/mac_wiki.py` renders verbatim
spans onto compiled pages, and `tools/check_wiki_citations.py` asserts that what a page quotes still
appears at the address it cites. They disagreed on their first meeting, which is the only reason a
second verifier is worth having.

The compiler initially emitted no `[[cite: ...]]` marker at all, so the citation gate resolved
nothing and refused:

```
FAIL: check_wiki_citations — 15 page(s) ... [page-uncited] ... carries NO citation
```

That refusal was correct. The compiler then emitted the ADDRESS form — `protocol/<id>.md:START-END`
rather than the bare entry id — because an id asserts only that the entry exists, while an address
makes the other gate re-verify the span against the entry's literal bytes.

## EVIDENCE

With addresses emitted, the two tools disagreed about 180 of 556 spans:

```
$ python3 tools/mac_wiki.py --check
PASS: mac-wiki — 0 violation(s) over 15 page(s) examined, 556 span(s) verified verbatim

$ python3 tools/check_wiki_citations.py
FAIL: check_wiki_citations — 180 violation(s) over 15 page(s) examined, 556 citation(s) checked
[class(es): span-changed] — 376 of 556 citation(s) across 15 page(s) resolved
```

Driving the citation gate's own matcher on one disputed span located the divergence exactly. The
span is byte-identical to entry lines 12-21; the two sides normalise it differently:

```
longest matching prefix: 350 of 657
PAGE says next:  'd — and the SDK reads them per bundle. **A module-level default cannot be bundle'
```

`norm_line` strips ONE furniture token per line, and `FURNITURE` contains both `>` and `*`. On the
page side that single strip is consumed by the blockquote prefix, leaving `**A module-level`. On the
source side there is no blockquote, so the strip eats the bold marker, leaving `*A module-level`.
Every entry line whose own first character is furniture — a bullet, a bold opener, a heading — is
compared against a form of itself that was stripped one token further. That is the 180.

The compiler's spans are verbatim. The matcher is asymmetric.

## WHAT CHANGED

Nothing in `tools/check_wiki_citations.py`. It belongs to the agent building it, the measurement is
recorded here rather than patched around, and the minimal fix is in ONE function: strip furniture
symmetrically, or strip the quote prefix before normalising rather than as part of it.

What changed is in `tools/mac_wiki.py`, and it is a defect this disagreement exposed on our own
side: the compiler had begun printing line addresses that NOTHING on its side verified. It was
relying on the other gate to check them, and the other gate was red for an unrelated reason.

* A tenth reject class, `bad-address`: the cited line range must literally contain the span.
* Its mutant leaves the quote perfectly verbatim and shifts the address by one line. No other check
  in the tool can see that — the section-based comparison re-parses the entry and never looks at a
  line number.
* Exactly one tolerance: the FIRST line may begin mid-line, because the bulleted section form puts
  the marker and the first words of the span on the same line. Every other line is compared whole.

```
$ python3 tools/mac_wiki.py --check
PASS: mac-wiki — 0 violation(s) over 15 page(s) examined, 644 span(s) verified verbatim — 46
entry(ies) -> 15 page(s) (core 14, ontology-builder 0, platform-builder 1); 0 entry(ies) carried NO
topic and are on no page; 0 entry(ies) declared no track
```

## WHAT IT DOES NOT PROVE

* That the citation gate has no other defect. One span was traced to a cause; the other 179 share
  its shape but were not individually traced.
* That the wiki is green. It is not: `check_wiki_citations` fails against these pages as this is
  written, and the estate should read that as RED until its owner fixes the normalisation.
* That two verifiers will keep disagreeing usefully. They agree now only because one of them was
  taught to check the thing the other could not — which is a weaker property than independence.
* `wiki/ontology-builder/` holds 0 pages over 46 entries. No entry has declared `track: ontology`.
  The compiler reports that number rather than filling the directory, and one of the operator's
  three groups is therefore empty.
