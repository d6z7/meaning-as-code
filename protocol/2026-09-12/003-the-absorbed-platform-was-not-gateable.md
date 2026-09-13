---
when: 2026-09-12T11:46:08
what: made the absorbed platform actually runnable under its own gate — nothing in it could run, so nothing in it was true
topics: [gates, harness, consolidation, denominators]
kind: defect
track: platform
repo: mac-platform
commits: [mac-platform:e4e9091]
---

## WHAT FORCED IT

The absorption (2026-09-11) landed the code but not the build system. Measured:

* `make install` installed 4 of 9 packages
* `make typecheck` checked those 4
* `make test` collected the whole `packages/` tree and died on 45 import errors
* repo-root `tests/` was never collected at all

A gate that cannot run is not a green gate and not a red one. Nothing in the gate could run, so
nothing in it was true.

## EVIDENCE

`git show -s e4e9091` (mac-platform). Three defects were behaviour, not style:

> `sdk/cli/harvest.py` `_MAC_TOOLS` pointed at `packages/mac-sdk/meaning-as-code/tools`. `_REPO` is
> the IMPORT root; before the absorption that was also the checkout root, so `_REPO.parent` reached
> `~/dev`. Afterwards it reached `packages/mac-sdk/`. The framework was silently unreachable and the
> compile gate refused EVERY bundle for "compiler could not be run" instead of compiling it.

> `console_api.py` called `_is_safe_qid` which was never defined here — every acceptance-sheet import
> with a non-empty id raised NameError instead of the intended 400.

> B023 in test_policy_check: a lambda closed over the loop variable, so every iteration asserted
> against the last value.

Measured after: `TESTS: nothing ran -> 987 passed, 7 skipped, 7 xfailed`; `LINT 1370 -> 0`;
`PACKAGES: 4 -> 8`. mypy's own verdict recorded as a burn-down meter with the number named:
`mac-pack/runtime/mcp/eval 0 -- mac-sdk 731, okf-core 266, okf-aws 243, mac-console 232`.

## WHAT CHANGED

The Makefile gained `TYPECHECKED` (everything installed and tested, only strict-clean packages
typechecked), `mac-chat` is EXCLUDED with its reason in the Makefile (it imports a package that
exists in no repository in this estate), and `meaning-as-code` must be installed for the compile gate
to run at all.

## WHAT IT DOES NOT PROVE

The sixth gate stayed red and was left red on purpose: `neutrality-gate, 213 violations`, the bulk of
it real customer geography inside `sdk/authoring/exemplars/`. The commit refused to sweep it —
"needs an operator decision, not a sweep" — and 213 was later measured to be the WRONG NUMBER
(see `2026-09-12/018`). So "5 of 6 green" is a statement about the build system, not about the tree.
