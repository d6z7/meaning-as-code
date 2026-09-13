---
when: 2026-09-13T00:10:12
what: made the compile record name the bundle rather than an absolute path, after a bundle that commits that record published an author's home directory
topics: [the-public-boundary, projections]
kind: defect
track: ontology
repo: meaning-as-code
---

## WHAT FORCED IT

`compile.json` recorded `"bundle": <root>` — an ABSOLUTE path on whoever ran the compile. The
framework gitignores that file, so the leak stayed local there; a bundle that COMMITS its compile
record published an author's home directory with it, and one in this estate does.

## EVIDENCE

`git show -s 11b26b2 c05c8fa` (meaning-as-code). Same defect and same fix as the diagnostics
projector eight hours earlier (`2026-09-12/026`): record the bundle NAME, which is the identity a
reader needs.

> The path is the operator's, not the bundle's.

`Gates unchanged: tpch 30/34, matching the post-merge baseline.`

## WHAT CHANGED

One file, `tools/mac_compile.py`, +6/-1.

## WHAT IT DOES NOT PROVE

This is the SECOND producer of the same class found by reading, not by a gate — the first was found
the previous evening and the fix did not generalise to its sibling. Nothing in the estate enumerates
"writers of absolute paths into committed artifacts", so the honest state is that this class is found
one instance at a time. The `gitignore`-in-one-repo mitigation is also not a fix: it makes the leak
invisible where it is harmless and leaves it live where it is not.
