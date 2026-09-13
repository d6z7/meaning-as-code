---
when: 2026-09-13T12:40:00
what: added the claims layer and the compiled index, after the first real compile produced 15 pages that were verbatim, checkable and unreadable
topics: [the-record, gates, denominators]
track: core
kind: build
---

* **WHAT FORCED IT** — the first compile over the backfilled protocol, read as a stranger would read
  it.

  ```
  compiled 48 entry(ies) -> 15 page(s) (core 13, ontology-builder 1, platform-builder 1);
  15 written, 0 moved, 0 entry(ies) carried NO topic and are on no page, 0 declared no track
  PASS: mac-wiki — 0 violation(s) over 15 page(s) examined, 656 span(s) verified verbatim
  PASS: check_wiki_citations — 0 violation(s) over 15 page(s) examined, 820 citation(s) checked
  ```

  Every number was green and the product was still wrong. `wiki/core/connectors.md` — 434 lines, 6
  entries, 24 spans — opened with a defect about an account id in a bundle's prose and reached the
  span that says what a connector IS in position 3 of 6, under the heading *"proposed the connector
  plugin architecture, after three measured facts overturned the brief it was written against"*. A
  reader who was not in the conversation met five things that went wrong before one statement of
  what the thing is. **It was not a list of commit messages — the entries are far richer than
  that — but it was a CHRONOLOGY, and the operator asked for pages that "actually disect and
  compile these aspects based on semantic of the subject". Time is not a semantic.**

  The second measurement, on the audience split the operator asked for in two groups:

  ```
  wiki/core/             13 page(s)
  wiki/ontology-builder/  1 page(s)   projections
  wiki/platform-builder/  1 page(s)   console
  ```

  yet 12 topics carry at least one `platform` entry and 8 carry at least one `ontology` entry. The
  routing rule ("two or more different tracks -> core, because a topic both audiences touch is
  shared law") is defensible per page and useless in aggregate: `capabilities` is 6 platform
  entries out of 7 and is filed as shared law. A platform builder opening their own directory found
  one page out of forty-eight entries.

* **EVIDENCE** — the fix is the one `sdk/project/knowledge.py` had already named, and it was in the
  docstring the whole design was borrowed from:

  > Judgement about WHICH statements are normative belongs in a separate claims layer, so that
  > extraction and interpretation never blur.

  There was no claims layer. `protocol/claims.yaml` is it: a claim is an ADDRESS and a ROLE
  (`rule` | `boundary`) and carries no prose of its own, so it cannot reword what it marks. The
  compiler lifts THOSE SAME BYTES to the top of the page with the same `q` anchor and the same
  verifiable line range, and both gates check them exactly as they check the body.

  It is a separate FILE and not new front matter because `protocol/README.md` says entries *"are
  never edited, only superseded by later ones that say so"* — marking a span normative a week later
  is an edit to the raw record.

  Re-measured after, on the same 48 entries:

  ```
  compiled 48 entry(ies) -> 15 page(s) (core 13, ontology-builder 1, platform-builder 1);
  16 written ... 55 normative span(s) marked over 37 of 48 entry(ies), 0 claim(s) rejected
  PASS: mac-wiki — 0 violation(s) over 16 page(s) examined, 731 span(s) verified verbatim
        — 55 normative span(s) marked over 37 of 48 entry(ies)
  PASS: check_wiki_citations — 0 violation(s) over 16 page(s) examined, 943 citation(s) checked
        — 943 of 943 resolved; 731 carried a quoted span checked VERBATIM
  PASS: mac-wiki self-test — 131/131 asserted ... 15 mutant(s) ... extras: 24 of 24
  PASS: check_mac_public — 0 leak(s) over 583 tracked file(s) examined
  ```

  `wiki/` was deleted entirely and recompiled: all 16 files byte-identical. A page is still a pure
  function of its inputs, and the claims are now one of those inputs.

* **WHAT CHANGED** — `tools/mac_wiki.py`, additive, self-test 85/85 -> 131/131 and 10 reject classes
  -> 15.

  * **`## What holds` / `## What is not settled`** render above the chronology, in the order the
    CLAIMS FILE declares rather than entry date — reading order is part of the judgement, and
    sorting by date is what put the definition under two corrections of it.
  * **A page with no marked span says so**, as `## What holds — NOT YET COMPILED`, and the verdict
    line carries `N normative span(s) marked over K of M entry(ies)`. An uninterpreted page is an
    honest anthology; one that reads as compiled knowledge without being it is the confident wrong
    answer this estate exists to remove.
  * **Claims are inside `source_hash`**, so editing the claims layer reads as `stale-stamp`
    (recompile) and never as `hand-edited-page`. A ratchet with the wrong name on it is most of the
    damage.
  * **Four new reject classes** — `malformed-claims`, `unknown-claim-role`, `dangling-claim`,
    `claim-topic-mismatch` — and a broken claim QUARANTINES the topics it touches rather than being
    dropped, exactly as an unplaceable entry does. Every claim mutant ADDS a bad claim instead of
    corrupting a good one: rewriting one removes a span from a page and a second class fires, so
    the mutant would be rejected for two reasons and attributed to neither.
  * **`wiki/index.md`, compiled**, with `stale-index` as its class, listing every page with its
    topic, audience, entry count, marked-span count and compile stamp — plus the AUDIENCE CROSS-CUT:
    per audience, every page carrying at least one entry of that track, with that audience's count
    beside the page's own. `platform-builder/` now leads to the 11 core pages carrying platform
    entries instead of to one page.
  * **`must_pass`: a protocol with NO claims layer compiles and passes.** Interpretation is
    optional. `sdk/gate/contract.py` states the cost of getting that wrong — *"A gate that rejects
    the absence of an optional thing is the most expensive kind of wrong"* — and here it would buy
    invented normativity on every page.
  * **55 claims authored**, all `ratified: false`. `2026-09-12/008` records that ratification is the
    operator's act, so every one renders as UNRATIFIED and the count is printed.

* **WHAT IT DOES NOT PROVE** — that the RIGHT spans were marked. The claims layer moves judgement
  out of the compiler and into a reviewable file; it does not make the judgement correct, and all 55
  of these were proposed by an agent in one pass over entries it did not write. 11 of 48 entries
  carry no mark at all, and no gate can say whether that is correct.

  It also does not prove the wiki is USED. Two gates now pass over 16 pages, and the number of
  people who have read one is zero. And the ENFORCEMENT half of the record is still red:
  `check_protocol — 52 code-bearing commit(s) examined, 0 covered, 52 orphaned, over 48 entr(y/ies)`,
  exit 1, because 47 of 48 backfilled entries carry no `commits:`. The wiki compiles beautifully
  from a record that is not yet accounting for the work it describes.
