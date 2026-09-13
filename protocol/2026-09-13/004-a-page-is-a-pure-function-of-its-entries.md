---
when: 2026-09-13T13:04:00
what: removed the compiled page's citation index, because it was the one element that was not a pure function of the entries the page names
topics: [the-record, gates]
kind: decision
track: core
repo: meaning-as-code
commits: [b4092e5]
---

## WHAT FORCED IT

Every compiled page ended with a table, "Sources these entries cite", listing each `file:line` an
entry mentioned. The citation gate reported three findings against it, on three pages that had
quoted their entries faithfully:

```
[file-missing] wiki/core/gates.md:2465 — 'materialize.py' is cited but the cited file is gone
[file-missing] wiki/core/harness.md:1299 — 'materialize.py' is cited but the cited file is gone
[file-missing] wiki/core/registers.md:709 — 'materialize.py' is cited but the cited file is gone
```

The entry wrote a bare basename. Inside a quoted span that is a true record of what somebody wrote.
Lifted into an address table it becomes a citation that does not resolve — the page had turned
quoted testimony into a live claim, which is the exact move the whole instrument exists to prevent,
committed by the one part of the page that was not a quotation.

## EVIDENCE

The obvious repair — measure whether each reference resolves and say so — was rejected, and the
reason is the more useful half of this entry. Resolution is a fact about the TREE, not about the
entries. Folding it into the page makes the page's text change when a file moves, so `--check`
would report `hand-edited-page` for a refactor that nobody made by hand: a true finding of a false
class, on a page that is exactly correct.

A page is a pure function of the entries it names. `source_hash` covers precisely those inputs, and
that is what lets a difference be attributed to the protocol moving rather than to the world moving.

After removing the table, two independent verifiers agree over the same spans:

```
$ python3 tools/mac_wiki.py --check
PASS: mac-wiki — 0 violation(s) over 15 page(s) examined, 648 span(s) verified verbatim — 47
entry(ies) -> 15 page(s) (core 13, ontology-builder 1, platform-builder 1); 0 entry(ies) carried NO
topic and are on no page; 0 entry(ies) declared no track

$ python3 tools/check_wiki_citations.py
PASS: check_wiki_citations — 0 violation(s) over 15 page(s) examined, 810 citation(s) checked — 810
of 810 citation(s) across 15 page(s) resolved; 648 carried a quoted span checked VERBATIM
```

The citation gate's normalisation defect recorded in `2026-09-13/003-two-verifiers-disagreed` was
fixed by its own author while this was being written; the 180 false `span-changed` findings are gone.

## WHAT CHANGED

* The citation index is gone from `render()`, and the reasoning above is written where the table was,
  so the next person to want one finds the cost first.
* Every reference an entry makes is still on the page, inside the span that quotes it.

## WHAT IT DOES NOT PROVE

* That an index is not wanted. It is — but it belongs in a tool that MEASURES resolution, which a
  page body cannot do without ceasing to be derived from its entries alone.
* That the two verifiers are independent. They agree partly because one was taught to check line
  addresses after the other could not, which is a weaker property than independence.
