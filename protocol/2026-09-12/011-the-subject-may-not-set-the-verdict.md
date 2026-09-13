---
when: 2026-09-12T17:06:03
what: stopped a bundle under test from setting its checker's verdict, and stopped the fabricated-identifier gate passing over nothing
topics: [gates, harness, denominators, the-public-boundary]
kind: defect
track: core
repo: meaning-as-code
---

## WHAT FORCED IT

Five tools need a resolver or a warehouse connection that only the bundle under test can supply, so
they import the bundle's own `tools/run_properties.py`. Three guarded that import with
`except Exception: pass` and degraded to identity. Both halves are wrong, in opposite directions, and
together they let the SUBJECT choose the CHECKER's answer:

* `SystemExit` is not a subclass of `Exception`. The plugin calls `sys.exit()` for a missing
  dependency, so its exit code became the checker's — a could-not-run published as a FAIL.
* When the guard did fire, identity resolution left every `@cols:` slot in the SQL, every parse
  failed, and each failure was reported as a fabricated identifier — a confident FALSE report of an
  invariant breach.

`check_no_fabricated_identifiers` predicted the second in its own docstring ("a checker that punishes
the correct pattern is worse than no checker") and then did it. Broadening to `BaseException` does
not fix this; it converts the first failure mode into the second, which is the more damaging one.

Separately, the same gate was committing the defect it exists to catch. Verified before changing
anything:

```
nonexistent directory       "OK - 0 propert(ies)", exit 0
example_shop_ontology       "OK - 0 propert(ies)", exit 0   (no acceptance plane)
example_tpch_ontology       "OK - 0 propert(ies)", exit 0   (no acceptance plane)
--self-test                 absent
```

## EVIDENCE

`git show -s fddd679 b49f499` (meaning-as-code). Measured against a worktree of develop:

```
dependency present  three verify checkers, output BYTE-IDENTICAL, exit 0/1/1
dependency absent   check_no_fabricated_identifiers  1 -> 2
                    check_additivity_in_sql          1 -> 2
                    check_vacuous_assertions         1 -> 2
                    mac_profile                      1 -> 2
_plugin --self-test 21/21
```

A SECOND defect of the same shape was found by the helper's own self-test: the seam loaded by NAME
off `sys.path`, so which plugin won was decided by path order rather than by the root asked for —
check bundle A then bundle B in one process and B silently got A's plugin.

## WHAT CHANGED

The rule now lives once, in `tools/_plugin.py`: a bundle that DECLARES a plugin and cannot supply it
makes the check unrunnable (exit 2); only a bundle that declares NO plugin gets the documented
fallback. Loading is by explicit file path under a per-root module name, and the bundle's `tools/` is
appended rather than prepended so a bundle-local `version.py` cannot shadow the stdlib.

Four conditions on the gate are now COULD NOT RUN, never a pass: root not a directory; the bundle
declares no looked-up identifier at all; no acceptance plane; an acceptance plane with no property
carrying SQL. `--self-test: 8/8`, with an assertion that each mutant actually mutated — the lesson
from a self-test in this estate that once passed because its mutant was a no-op.

The gate was given a real subject in its own repo: `example_shop_ontology/acceptance` with five
properties. Liveness proven end to end by injecting a fabricated join key, watching exit 1 name the
built column and the descriptor that declares it, and reverting to exit 0 over 5.

## WHAT IT DOES NOT PROVE

Two honest residues are in the record. The first draft of that acceptance plane added 2 compile
errors of its own by using values outside the closed vocabularies — the gate's new subject was
authored by the same agent that wrote the gate. And compiling a bundle writes the schema's
description text into `compile.json`, which carried customer identifiers, so a compile in a fresh
clone of this PUBLIC repo produced a committable leak; `compile.json` was gitignored, and that did
NOT turn the hygiene gate green — it reported 613, overwhelmingly from gitignored build output
(fixed in `2026-09-12/018`).
