---
when: 2026-09-12T18:08:04
what: replaced a containment guard that matched a substring of a directory name with one that reads the bundle's own declaration, and routed the last illegal write through it
topics: [gates, registers, harness]
kind: defect
track: platform
repo: mac-platform
---

## WHAT FORCED IT

The declared sole writer's containment guard tested whether any path component CONTAINS the substring
`sources`. That passed for one bundle because its repository happens to be NAMED for the word, and
REFUSED two others that are equally legitimate, the public example among them. A guard whose verdict
depends on what a checkout was called is not a containment guard, it is a coincidence.

Fixing the second defect first would have been unsafe: routing a write through that guard naively
would have turned a green gate into a runtime refusal for two of three live bundles.

## EVIDENCE

`git show -s e742c37 ca7e4b6` (mac-platform). Measured after the guard was made declaration-driven —
it walks up from the target and accepts when an ancestor carries `mac.project.yaml`:

```
reference bundle   ACCEPTED (was accepted, for the wrong reason)
public example     ACCEPTED (was REFUSED)
demo bundle        ACCEPTED (was REFUSED)
```

The exit criterion, met:

```
correct root   PASS: check_write_paths — 0 violation(s) over 28 file(s)
wrong root     exit 2  (it used to PASS there, on 0 files)
```

`78 passed · run_gates 9/9`.

## WHAT CHANGED

`materialize.py:232` wrote a generated lookup CSV with a bare `.write_text()` into the content root,
bypassing the declared writer and therefore the guard entirely — the same shape as every defect in
that phase: a second path to a thing that is supposed to have exactly one. It now goes through a
named `operations.write_lookup_csv`.

Three fixtures went red on the tightened guard, and the honest half of this act is what happened
next, recorded in `ca7e4b6`'s own subject line — "the fixtures judged by directory name too — and I
pushed them broken":

> I committed and pushed before reading the test output. That was wrong; this fixes it forward.

The failures were correct behaviour, not collateral: the fixtures built `tmp_path/sources/...` and
passed the old guard for exactly the reason the real bundles did. A fixture standing in for a bundle
now declares itself like one. One test must NOT pre-declare, because the scaffold under test is the
thing that writes the declaration — stated in the test rather than left as a puzzle.

## WHAT IT DOES NOT PROVE

`0 violations over 28 files` is the count from the DEFAULT root. The same gate passes on 0 files from
the repository root, which is why the exit-2 path was added — and a record of this review had those
two roots labelled the wrong way round, so the number alone has been misread before.
