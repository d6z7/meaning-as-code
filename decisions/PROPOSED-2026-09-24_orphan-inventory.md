# PROPOSED — 2026-09-24 · the orphan inventory, and why a detector for it failed

**Status: PROPOSED. An agent may only write PROPOSED (CORE §3).** The operator's instruction that
prompted it:

> "we have multiple corpses and orphans in the code base that are unpatched. maybe some of them
> might be of great value ... but we have forgotten them. the functionality i have requested was
> existing at some point in time but was abandoned or drifted away. what i would recommend doing
> in any case is to destroy or archive everything which is redundant or unpatched."

---

## 0. The pattern, stated once

**Every defect found on 2026-09-24 was an orphan. Not one was a wrong algorithm.** That is the
finding that makes this document worth writing, and it is measured, not impressionistic:

| orphan | shape | what it cost | state |
|---|---|---|---|
| `Vocabulary._index` | asked for by TWO interpreters via `getattr`, set by nobody | ~15 kB of the bundle's MEANING — every edge, every default reading, every never-clause — never reached the model. The console sent a 4-section prompt where the code was written to send 5. | **fixed** |
| `Column.declared_fk` (bundlegen) | on the dataclass since the generator was written, assigned nowhere | every generated edge was a NAME GUESS, including on schemas that declare their keys outright | **fixed** |
| `rules_used` cannot hold a contract rule | two namespaces, one label | the trace read the shorter list and said "no declarations fired" on 33 of 77 answers whose reading demonstrably applied one | **fixed** |
| `testpaths` listed 4 of 8 test packages | a denominator nobody stated | the suite reported **834 passed** while `console_api.py` carried a SyntaxError that had taken the console down | **fixed** (→ 1274) |
| `acceptance/rulings/` | written by the console, read by NOTHING; exists in 0 of 6 bundles | the estate's ONLY authored-human authority, against 398 `authority: derived` anchors, lands in a file no projector opens | open |
| `TraceStore` + `run_pipeline` events | built, typed, persisted to NDJSON, served over HTTP — and linked to no capture | **0 of 77 captures carry a `run_id`.** The per-stage trace the operator asked for already exists; 52 traces, 952 kB, sit in `$TMPDIR` and are pruned at 200 | open |
| `packages/mac-eval` | `__all__: list[str] = []`; its one test asserts `__doc__ is not None` | a package inside `make check` whose only test cannot fail | open |
| `master.yaml` in 4 of 6 bundles | the projector reads `questions.yaml` only | **four acceptance planes invisible** to the board, the flags and the dashboard | open |
| `Resolution.candidates: int` | the COUNT survives; the alternatives are discarded | the "why" behind every resolver choice, thrown away one field short | open |
| `answer_parts.raw` | an unparseable Python repr beside the parsed fields | **185 553 of 455 691 bytes = 41 %** of the acceptance capture plane | open |

Eight of ten were invisible until someone read the code with a specific question in mind. None
would have been caught by a test, because **each one is a thing that is never called** — and a
test suite only exercises what is called.

---

## 1. The detector, and why it is NOT recommended

The obvious response is a gate. One was written and run against both repos. It is reported here
because its FAILURE is the useful part.

**Detection A — `getattr(x, "literal")` where the literal is assigned nowhere.** This is the
`_index` shape exactly. It returned **16 hits, and essentially all were false positives**:
`__file__`, `CSafeLoader`, `__isabstractmethod__`, and a dozen LangChain message attributes
(`tool_calls`, `usage_metadata`, `additional_kwargs`) which are set inside a dependency this repo
does not contain.

**Detection B — `check_*.py` gate scripts no runner invokes.** It returned **40 of 66**, which
looked like a major finding. It is wrong. `tools/run_framework_gates.sh:146` reads
`for checker in "$HERE"/check_*.py` — the runner DISCOVERS them. A detector that cannot see a glob
reports 40 live gates as dead.

**The lesson, and it is this estate's own doctrine turned on itself:** a noisy gate is worse than
no gate, because a reader learns to ignore it, and an ignored gate is indistinguishable from a
passing one. Both detections failed the standard `TESTING.md` already sets — *a check that cannot
discriminate is not evidence*. **Do not ship either.**

What WOULD be soundly detectable, and is proposed instead of a general detector:

* **declared-but-unread in the DATA plane, not the code plane.** A bundle key the loader never
  reads is decidable: the loader's read set is enumerable, the bundle's key set is enumerable, and
  the difference is exact. The estate already has this gate — `the-runtime-ignores-its-own-
  declarations` — and it is the one that works.
* **one specific code shape, narrowly:** a pydantic/dataclass field declared on a model in
  `mac_runtime.models` or a generator's `Table`/`Column` that NO module in the repo ever assigns.
  Narrow enough to have no dependency false positives, and it catches `declared_fk` and
  `candidates: int` — two of the ten above.

---

## 2. What to archive, and what to keep

The operator's instruction is to destroy or archive the redundant. Applying it to the ten above
gives three different answers, and the distinction matters more than the list:

**ARCHIVE — redundant, superseded, no live caller.**
* `packages/mac-eval` as an empty skeleton — delete, or rehome as the Leg C benchmark runner. What
  must not survive is a package inside `make check` whose test cannot fail.
* `docs/06-SPEC-eval-harness.md` → SUPERSEDED, with its four live clauses harvested first (stage
  attribution; mandatory clarify+refuse fixtures; `--interpret cached|live`; baseline gating).
  Marked and pointed, never deleted: a spec that was never implemented still records what someone
  thought was needed, and three of those four are still needed.
* `answer_parts.raw` — 41 % of the capture plane duplicating what sits beside it, parsed.

**WIRE — built, valuable, forgotten. This is the category the operator suspected exists, and it
does.**
* `TraceStore` + the pipeline's typed events. **The functionality requested already exists.** It
  needs two scalars on the capture (`run_id`, `trace_sha`), not a build.
* `acceptance/rulings/` — needs a reader. A stage ruling of `wrong` over all-green flags should
  surface as `disputed`, a state `flags.py` already carries.
* `Resolution.candidates` — keep the set, not the count.

**ADAPT — not redundant, just unreachable.**
* `master.yaml` × 4 bundles. One reader change in one module lights up four dark acceptance
  planes. Renaming the bundles instead would discard authored `groups[]` content (`why_hard`,
  `sources`, `description`) for no gain.

---

## 3. The recommendation

1. **Do not ship a general orphan detector.** Two were built and both failed to discriminate.
2. **Ship the narrow one**: a model field declared and never assigned, scoped to the runtime's
   models and the generator's schema types. It catches two of the ten and has no false positives.
3. **Before proposing any new mechanism, grep for the existing one.** This is already a standing
   note in the operator's memory (`the-runtime-ignores-its-own-declarations`) and it was NOT
   applied when the `stages:` block was first proposed — the architect withdrew that proposal for
   exactly this reason once `run_pipeline` was found to emit the events already.
4. **An orphan is a finding, not a chore.** `_index` cost 15 kB of meaning on every question for
   an unknown number of weeks and no test failed. The inventory above should be re-measured after
   each of the open five is closed, not archived as a one-off.

---

**The open five, in the order they are worth closing:**

| | why first |
|---|---|
| link `TraceStore` to the capture | the requested functionality already exists; half a day |
| give `rulings/` a reader | the only authored authority in the estate is currently write-only |
| teach the corpus reader `master.yaml` | four bundles appear; every count changes, so announce it |
| stop duplicating `answer_parts.raw` | 41 % of the capture plane |
| `Resolution.candidates` → the set | the "why" behind every resolver decision |
