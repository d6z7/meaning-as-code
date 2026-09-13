---
when: 2026-09-12T09:21:09
what: brought the framework to one voice on x- extension keys, one current version, and no pointer to a retired private repo
topics: [grammar, the-public-boundary, consolidation]
kind: build
track: core
repo: meaning-as-code
---

## WHAT FORCED IT

The framework contradicted itself in three ways at once, and a reader reaches for what the README
teaches. `CONFORMANCE.md` §2 had been corrected earlier to say `x-` keys are PROHIBITED while
`README.md` still advertised them as a feature — "only schema-defined keys (plus namespaced x-
extensions)". Two documents in one repo stating opposite rules is why the construct kept coming back.

Two further contradictions rode along: `VERSION` read `0.1.14-develop` while three documents asserted
`0.1.9` was what the framework IS today, and five shipped checkers told the reader to wire their gate
into a now-private, reference-only repository's `check_all.sh`.

## EVIDENCE

`git show -s 439f41e` (meaning-as-code), and the merge `14fe379`, which state the measurement:

> Verified after: both example bundles validate 0 errors (20/20 and 26/26 clean),
> 12 checker self-tests pass, 0 fail, the package imports and framework_root() resolves.

The merge carried nine commits, four of them from 2026-09-11 removing the banned `x-` keys from the
framework's own examples (`aee2fee`), from the OSI projector (`30a91d2`) and from the meta generator
(`ec7c1cd`).

## WHAT CHANGED

`CONFORMANCE.md`, `FRAMEWORK.md`, `README.md`, and five `tools/check_*.py` — 8 files, +18/-17. The
checkers now name the ROLE ("your bundle's offline gate chain") rather than one estate's filename.
Changelog entries describing what 0.1.9 INTRODUCED were deliberately left alone: bumping those would
falsify the record rather than fix it.

## WHAT IT DOES NOT PROVE

That the `x-` ban is enforced. This entry is a consistency fix across prose; the enforcement is
`tools/check_extension_keys.py`, whose own coverage was not re-measured here. It also does not prove
no other pointer to a retired repo survives — five were found by grep, and grep over prose is not a
gate.
