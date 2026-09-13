---
when: 2026-09-13T14:50:00
what: read what the entry-point invoker and seam enumerator had already found — three real crashes, a seam teaching generated SQL a nonexistent column, and a floor that pre-forgave every witness it named
topics: [gates, floors, seams, denominators]
kind: fix
track: core
repo: meaning-as-code
commits: [30aa112]
---

## WHAT FORCED IT

Two gates landed earlier the same day and **nobody read their output.** An instrument nobody reads
is indistinguishable from one that was never built, and this estate had just spent a day measuring
exactly that class.

## EVIDENCE

Three findings, all REAL code defects — **zero false positives against this estate's measured >20%
false-positive rate on escalations.** Each was attacked before being accepted.

`sdk/authoring/validate_one.py:23` — `read_text()` sat inside a `try` catching only `yaml.YAMLError`,
so every `OSError` escaped. **Refutation attempted and failed:** the crash does not depend on the
gate's `--help` convention; an ordinary bad path raises the identical traceback.

`sdk/gate/test_operations_refuses_invalid.py:37` — a STALE FIXTURE, not a code defect.
`operations.py`'s own docstring records that the containment guard was deliberately changed from "any
path containing `sources`" — exactly the shape the fixture builds — to requiring a `mac.project.yaml`
ancestor. The fixture was not moved with it. **Placement was proven, not guessed:** at `base` all six
steps pass; one level up, step 5 reports `CONTAINMENT BREACH: write outside bundle was ALLOWED`.

`tools/mac_to_meta.py:193` — **THE SEAM.** Two declarations of one column name:

    producer  project_model.py:776 -> mac_to_meta.py:97   region_definition_used
    consumer  mac_to_meta.py:193                          region_definition

Decided by three independent witnesses all naming the producer's spelling: the prose in the SAME
dict entry, the relations for the same relation, and **the other example query for the same
relation, already correct.** Line 193 was the sole outlier. The consequence was live: `_GROUNDING`
examples are emitted into the grounding YAML an interpreter inlines, so it was **teaching generated
SQL a column that does not exist.**

## WHAT CHANGED

Beyond the three fixes: `entry_point_floor.txt` declared all 4 crashes as witnesses, so a
**REGRESSION at any of them would have been silently forgiven** (`1 <= 4`, witness already declared →
PASS over a live crash). Demonstrated against the real `_floor()`. Per that file's own instruction —
"lower the number and delete the line together" — it is now 0 with the 4 witness lines deleted.

    before: PASS: check_entry_points — 4 crash(es) over 29 of 33 exercised ... 2 crashed
    after:  PASS: check_entry_points — 0 violation(s) over 29 entry point(s), 70 invocation(s)
    before: FAIL: check-seam-agreement — 1 violation(s) over 658 seam(s), 87 checked
    after:  PASS: check-seam-agreement — 0 violation(s) over 664 seam(s), 87 checked

## WHAT IT DOES NOT PROVE

**4 modules are UNMEASURED, not passing** — harvest, connector.conformance, connector.probe and
container.save BILL, so they are skipped by name with AWS env scrubbed. `0 crashed` is a statement
about 29, never 33. **The gate asserts EXIT, not ANSWER:** `container.spec --help` exits 0 having
"validated" a path literally named `--help`. Crashes became verdicts; the verdicts are not proven
right. **571 of 664 seams are ENUMERATED BUT NOT SCORED** across four excluded classes, unaudited.

And the larger one: **`pytest tests -q` cannot run AT ALL** — five files carry module-level
`sys.exit()`, so collection dies with `INTERNALERROR`. Proved in a pristine `HEAD` worktree, so it is
pre-existing. The fixture above is the same defect at small scale: still named `test_*.py` with its
body in `main()`, so **pytest collects ZERO tests from it.** The whole `tests/` directory looks
covered and is not.
