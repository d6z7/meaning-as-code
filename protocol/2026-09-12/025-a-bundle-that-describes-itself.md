---
when: 2026-09-12T23:55:02
what: gave a bundle one generated file at its root that describes what it contains, so a host can open an ontology without knowing its layout beforehand
topics: [containers, projections, grammar]
kind: build
track: ontology
repo: meaning-as-code
---

## WHAT FORCED IT

An ontology is hundreds of files across two planes. A host that wants to OPEN one had nothing to
read: it had to know the layout beforehand, which is the assumption that breaks quietly every time
the layout moves — and it had just broken twice in one day, on nested concepts and on the grounding
key (`2026-09-12/024`).

## EVIDENCE

`git show -s 63c4be4` (meaning-as-code) and `38c8e4d` (the customer-bundle repo). The shape, per the
operator: **the BASENAME IS ARBITRARY, the EXTENSION IS FIXED, and the file sits at the bundle ROOT**
— the project-file convention. A host globs `*.mac` in a directory: exactly one match means this IS
an ontology and that file describes it; zero means it is not one; two is ambiguous and must be
REFUSED rather than guessed at.

`Self-test 8/8.` Generated for three bundles on the day: `tpch.mac` (295 lines), `shop.mac` (199
lines), and the customer bundle's own at **113 components** across concepts, datasets, lookups,
sources, transforms, profiles and suites.

## WHAT CHANGED

GENERATED AND STAMPED, never hand-maintained — the rule stated in the generator and quoted by the
wiki:

> A description maintained by hand drifts from the tree it describes, and there is nothing to catch
> it.

It carries identity (container, label, grammar_id, tree_hash), counts, the measured per-kind layout,
the derived artifacts WITH their producers, and an explicit `absent` list — so a reader can tell
"this bundle has no acceptance plane" from "I did not look".

Both example manifests also gained the container identity the console addresses them by; without it
`POST /open` refuses the bundle outright.

## WHAT IT DOES NOT PROVE

`tree_hash` moves with the tree, by design, so a description is only true of the commit that
generated it — nothing regenerates it on write, and a stale one is not detectable from inside the
file. The `absent` list is honest about what the GENERATOR looked for; it cannot report a plane
nobody taught it to expect.
