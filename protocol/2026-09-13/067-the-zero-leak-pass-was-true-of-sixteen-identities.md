---
when: 2026-09-13T14:05:00
what: a public-repo gate printed zero leaks over a complete file list while a tracked file carried an author's home directory, because the PATTERN denominator was the empty set
topics: [denominators, gates, the-public-boundary, registers]
kind: fix
track: core
repo: meaning-as-code
commits: [1abb9df]
---

## WHAT FORCED IT

An agent recompiling the wiki reported, unasked, that `compile.json` line 3 held
`"bundle": "/Users/<user>/dev/meaning-as-code"` — in the PUBLIC repo, in a TRACKED file, while the
gate guarding that boundary printed green. The repo is days from going public.

## EVIDENCE

    PASS: check_mac_public — 0 leak(s) over 613 tracked file(s) examined

`613` is exactly `git ls-files | wc -l`, so the FILE denominator was complete. The PATTERN
denominator was not: 16 register entries, every one an identity token, **none matching an absolute
home path**. Verified directly — `/Users/<user>/dev/meaning-as-code`, `/home/alice/repo` and `~/dev/x`
all returned no match.

**So the green meant "none of 16 identities, over 613 files" and was read as "nothing leaks". A
ZERO-DENOMINATOR PASS ONE LEVEL UP: the property was the empty set, not the file list.** This
estate's dominant defect class, in the one gate whose failure is published.

`protocol/2026-09-13/050-…` had already predicted it and fixed the WRITER
(`tools/mac_compile.py:572` now emits `Path(root).name`); the already-committed artifact was never
regenerated, and that entry's own "WHAT IT DOES NOT PROVE" said why — nothing enumerates writers of
absolute paths into committed artifacts, so the class is found one instance at a time.

## WHAT CHANGED

**Two seams, one instance each.**

1. IDENTITY vs SHAPE. Every pattern lived in the gitignored register — correct for brands and names,
   since listing those in a public repo IS the leak. But a home path is a SHAPE, not an identity, so
   writing it down leaks nothing, and expressing it only as a register entry put it absent exactly
   where it matters: the register is gitignored, so a fresh clone and CI carry no values at all.
   `BUILTIN_PATTERNS` now ships two shapes in code, applied unconditionally. The
   missing-register refusal STAYS — a shape floor does not substitute for the identity table.
   `(?!<)` is load-bearing: ten tracked lines quote `/Users/<someone>/dev/...` while DOCUMENTING
   this defect, and flagging those would make describing the bug the same offence as committing it.

2. `.gitignore` vs THE INDEX. `.gitignore:13-14` already listed `compile.json` and `**/compile.json`,
   added to stop this very leak. **It did nothing: git ignores only UNTRACKED files**, and the file
   was committed before the rule existed. Two declarations of one fact, nothing reading both.
   `git rm --cached` honours the rule that was already there.

    self-test: PASS 7/7 over 2 built-in shape(s) + 16 register token(s)
    before:    FAIL — 1 leak(s) over 613 tracked file(s), 1 ABOVE the declared floor of 0
    after:     PASS — 0 leak(s) over 612 tracked file(s) examined

The denominator drops 613 -> 612 and that is normally how a suite is gamed. The one file removed is
the leaking one, removed by UNTRACKING what `.gitignore` already forbade — not by exempting it from
the scan.

## WHAT IT DOES NOT PROVE

HEAD is clean; **HISTORY IS NOT.** Measured: 2 commits of 186 ever carried the literal, and
`compile.json` is the only path that ever did — small and surgical, but the going-public cleanse must
still cover it. And no gate enumerates "tracked yet gitignored"
(`git ls-files -i -c --exclude-standard`, currently 0 of 612) — one command that would have caught
this at the commit that created it. Proposed, not built.
