---
when: 2026-09-12T17:57:36
what: wrote the gate contract once and brought all eight SDK gates to it, closing three live false greens
topics: [gates, harness, denominators]
kind: build
track: core
repo: mac-platform
commits: [mac-platform:981a9a6, mac-platform:b69f4f7]
---

## WHAT FORCED IT

Measured before starting, over the eight gates in the package: **0 with a `--self-test`, 0 with any
exit-2 path, three printing no denominator, two with no argparse at all.** A gate with no mutant is a
gate nobody has tested, and a gate with no could-not-run path must express "I could not judge" as
either PASS or FAIL — both of which are lies.

## EVIDENCE

`git show -s 981a9a6 b69f4f7` (mac-platform). Three false greens were LIVE:

> `check_boundaries` printed "PASS — no cross-boundary import coupling" in BOTH modes over a repo
> where NONE of the configured directories exist. `check()` skips a missing dir, so it examined ZERO
> files and gave the strongest verdict available. This is the gate behind this estate's canonical
> false green — "0 import violations" meant "0 files examined".

> `check_write_paths` passed on 0 files at the repository root while its DEFAULT root examines 28 and
> finds a real violation. A record of this review had those two labelled the wrong way round.

> `check_source_coupling` printed a tick over 0 files from the wrong root.

Two gates returned `1` — a FINDING — for conditions that are not findings: `check_rule_lock` for a
missing `ontology/`, `check_artifact` for nothing published. A caller reading 1 as drift would refuse
to serve an artifact that merely does not exist yet.

Result: `PASS: run_gates — 8/8 gate self-tests green`, `25 mutants across 8 gates, each rejected AS
ITS OWN CLASS`, `78 passed`.

## WHAT CHANGED

`sdk/gate/contract.py` holds the contract once: an `Outcome` carrying its denominator, a `verdict()`
that refuses to call an examined count of zero a pass, a `could_not_run()` for `main()`, and a
self-test harness that seeds a clean fixture plus one mutant per reject class and PROVES EACH MUTANT
ACTUALLY MUTATED.

**The shape is forced by the publisher.** `publish.py` calls four of these gates as IN-PROCESS
functions, so a `check()` returning 2 for "could not run" would be read there as a FINDING — "no lock
armed yet" would arrive as "the lock has drifted". Exit 2 belongs to `main()` alone and every
`check()` keeps its return shape.

Four self-tests that would have passed FOR THE WRONG REASON were caught while writing them: a mutant
that did not mutate (`_PATHISH` needs path punctuation, so a bare `from annotations import` never
matched); a fixture that locked "1 files, 0 RULES" so the rule dimension was never exercised; a
WARNING-class mutant missed by a findings-only count; and a class with no subject on disk.

Fixtures derive their tokens from each gate's own deny list rather than typing one: these gates COUNT
such literals, so a self-test that spelled one out would plant the thing it scans for.

## WHAT IT DOES NOT PROVE

Contract shape is not correctness. Measured the same day across the estate's 41 gates, the same
census read `147 findings, no-verdict 38/41, no-self-test 29/41, no-denominator 28/41`
(`2026-09-12/009`), so 8/8 here is one package of that population. `check_source_coupling` passed its
own contract while remaining blind to the f-string its own docstring cites — fixed in the same
commit, but the sequence is the lesson: a gate can meet every clause of this contract and still be
measuring nothing.
