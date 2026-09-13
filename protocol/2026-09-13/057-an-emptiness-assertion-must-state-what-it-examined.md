---
when: 2026-09-13T02:09:16
what: gave the test suite two assertions that refuse to pass over nothing, and found two assertions that were already vacuous
topics: [denominators, harness, gates]
kind: build
track: core
repo: meaning-as-code
commits: [b7a5cfb]
---

## WHAT FORCED IT

`assert gate.check(tree) == []` reads as "the gate found no leaks". It also passes when the gate
examined ZERO files, matched ZERO declared patterns, or was pointed at an empty directory — and the
assertion cannot tell those apart from clean.

**That is the estate's dominant defect, the zero-denominator pass, reproduced inside the suite meant
to catch it.**

## EVIDENCE

`git show -s b7a5cfb` (meaning-as-code). Six assertions converted; two of them were ALREADY VACUOUS:

> one asserted a source scan stayed clean "even though the sidecar names a denylisted handle". Once
> the handle register moved out of the repository the handle was no longer declared anywhere a test
> could see, so the assertion held whether or not the skip logic worked — it would have passed with
> the feature deleted.

> another built a fixture whose every file lived in a SKIPPED directory. `examined()` was 0, so
> "clean" proved nothing about skipping; the helper caught this one on its first run, which is the
> whole argument for the helper.

```
pytest sdk                   88 passed  (was 83; +5 for the helpers)
denominator-free emptiness assertions in sdk/   0
SDK gate self-tests           9 / 9
run_framework_gates  tpch    30 / 34   (baseline — unchanged)
run_framework_gates  shop    30 / 34   (baseline — unchanged)
```

## WHAT CHANGED

`sdk/testing.py` adds two assertions that refuse to pass over nothing:

```
assert_clean_over(findings, examined=N, what=...)   empty AND N > 0
assert_absent_from(needle, haystack)                absent AND haystack non-empty
```

The helpers are themselves tested in `sdk/test_testing.py`: a tool for catching vacuous passes is
worthless if it can pass vacuously, so each refusal is exercised rather than assumed.

## WHAT IT DOES NOT PROVE

Six assertions were converted, in one package. `denominator-free emptiness assertions in sdk/ 0` is a
measurement over `sdk/` alone — `tools/` and `tests/` were not swept, and nothing enforces the helper
on a newly written test. A convention with no gate is a convention that decays, and this one has no
gate.
