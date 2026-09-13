---
when: 2026-09-13T01:16:30
what: moved the SDK into the framework repository and deleted the vendored grammar fork, so there is no resolution step left to fall through
topics: [consolidation, grammar, registers, gates]
kind: build
track: core
repo: meaning-as-code
---

## WHAT FORCED IT

`sdk/` lived in a different repository from the grammar it validates against, so it had to FIND that
repository at runtime by guessing a sibling checkout. The guess broke twice. When it broke, the
resolver fell through IN SILENCE to a vendored copy of the schema.

Re-measured on this branch before deleting it, and it reproduces exactly:

```
fork       25 $defs  ->  22 of 22 concepts REJECTED
framework  37 $defs  ->   0 of 22 rejected
```

The authoring path could not validate the bundle it had itself produced, and nothing said which
schema had judged it. Declaration-driven resolution (`2026-09-12/007`) made the fork inert; it did
not make it absent.

## EVIDENCE

`git show -s 4cbf225` (meaning-as-code), 73 files, +16439.

```
MEASURED, this tree, no framework sibling and no fork:
    SDK gate self-tests           9 / 9
    run_framework_gates  tpch    30 / 34   (baseline 30/34 — unchanged)
    run_framework_gates  shop    30 / 34   (baseline 30/34 — unchanged)
    harvest --mode project       projects tpch offline, 37-$def grammar governing
```

## WHAT CHANGED

One repo means no resolution step, so nothing to fall through to and nothing to vendor from — the
grammar is simply on the path. **Drift becomes structurally impossible rather than detected
afterwards.**

* `sdk/grammar/mac.schema.json` DELETED
* `sdk/grammar/resolve.py` — no fallback; RAISES when no grammar resolves
* `sdk/project/mac_okf.py` — was building its own path to the fork, bypassing the resolver entirely:
  a second grammar in one process
* `sdk/cli/harvest.py` — the sibling guess is gone, and `_checkout_root()` with it
* `sdk/gate/check_grammar_home.py` — rewritten for the stronger invariant: EXACTLY ONE grammar in
  this tree, and it governs. Build output and egg-info copies are not forks; both seeded as
  false-positive cases. `8/8, 4 mutants`.

The handle register moved out on the same commit: the secrets gate carried four literal infra handles
— a production SSO profile, a workgroup family, a results bucket, another source's warehouse db, one
of them carrying a person's name. **A detector that names what it forbids IS a register of those
secrets, and this repository is published.**

## WHAT IT DOES NOT PROVE

Stated in the commit under NOT PUSHABLE YET: `sdk/` still carried instance tokens — 21 files naming
one source, 15 naming an internal system, and a real warehouse database name in one test fixture. The
cleanse was a PRECONDITION for pushing this branch, not a follow-up to it, and it took four more
commits and eight hours (`2026-09-13/055` through `/059`).
