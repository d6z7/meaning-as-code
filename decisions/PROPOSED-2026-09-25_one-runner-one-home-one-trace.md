# PROPOSED — 2026-09-25 · one runner, one home, one trace

**Status: PROPOSED. An agent may only write PROPOSED (CORE §3).**

This is the plan. It supersedes the three analysis packets of 2026-09-24
(`orphan-inventory`, `acceptance-is-the-home`, `execution-tracing-and-testing-ux`), which stay on
disk as the evidence behind it. **Every choice in those packets is taken here.** One question is
left open at the end, and it is the only one that is genuinely the operator's.

---

## The diagnosis, in one paragraph

Nothing needs to be invented. The estate already contains a typed per-stage execution trace
(`run_pipeline`), a store that persists it (`TraceStore`, 52 files on this machine), an endpoint
that serves it, a file for authored human judgement (`acceptance/rulings/`), and a spec for stage
attribution (06). **None of them is connected to the testing plane**, and the reason is a single
fork: **there are two runners.** The Chat calls `run_pipeline`, which emits events. The Board calls
`ask()`, which does not. The question corpus — the 77 questions most in need of debugging — is
wired to the blind door. Everything else in this document follows from closing that fork.

---

## 1. ONE RUNNER — `run_pipeline`, always

`/questions/run` stops calling `mac_runtime.ask.ask()` and drains `run_pipeline` instead. A caller
that wants only the answer keeps the terminal outcome and discards the events; a caller that wants
the protocol keeps them. **That is already the shape `run_pipeline` has** — it takes injected
`new_uuid`, `now`, `monotonic`, `is_cancelled`, a deadline and an `on_stage_start` hook,
explicitly so a batch caller can drive it deterministically.

`ask()` keeps one caller (`local_ask.py`) and becomes a thin wrapper over `run_pipeline`, not a
second implementation. Two functions that answer a question is how you get a board whose captures
cannot be traced and nobody notices for weeks.

**What this buys immediately, at no further cost:** every board capture gains a `run_id`, and
therefore a trace. The refusals stop being blank — the stage, the confidence and the rejected
intent are all already on the wire and simply never reached the corpus.

**Measured, so the change is checkable:** 0 of 77 captures carry a `run_id` today. After, 77 of 77.
And `PIPELINE_TESTING` §10's smallest number — *0 of 21 refusals carrying a stage* — becomes 21 of
21, verifiable against a hand classification of the same 21 (**12 interpret · 6 resolve · 3 plan ·
0 execute**). If the machine disagrees with that, the instrument is wrong, not the classification.

## 2. ONE HOME — `acceptance/`

`eval/` is retired as a per-bundle directory. It was designed in spec 06 and built in 0 of 6
bundles; `acceptance/` exists in 6 of 6 and drives everything. `docs/06-SPEC-eval-harness.md` goes
SUPERSEDED **with its four live clauses harvested first**, because three of them are still needed:
stage attribution (§1 delivers it), mandatory clarify+refuse fixtures per suite, `--interpret
cached|live`, and baseline gating that actually exits non-zero.

`packages/mac-eval` — an empty skeleton whose only test asserts `__doc__ is not None` — is rehomed
as the Leg C benchmark runner, which is genuinely platform code and genuinely not per-bundle. What
must not survive is a package inside `make check` whose test cannot fail.

**And the fork that actually matters is inside `acceptance/`, not between it and `eval/`:** four of
six bundles spell their corpus `master.yaml` and the projector reads only `questions.yaml`, so four
acceptance planes are invisible to the board. One reader change in one module, no bundle edits.
Announce the denominator change before it lands or it will read as a regression.

`acceptance/` is Leg B and only Leg B. Leg A (synthetic reference bundles) and Leg C
(`meaning-as-code/benchmark/`) are not per-bundle and do not live in a bundle directory.

## 3. ONE TRACE — wire what exists, then deepen it

The trace becomes the source of truth for what happened. The capture gains two scalars —
`run_id`, `trace_sha` — and nothing else. **No `stages:` block**: that would be a second home for a
fact `run_pipeline` already emits, which is the same objection that retires `eval/`.

`_trace_for` keeps working exactly as written, which is what makes it work on all 77 captures taken
before any of this existed, and gains one branch: read the pinned trace when `trace_sha` is
present, else derive from the capture as today. No schema bump.

**Then the depth**, which is the part that answers *why* rather than *what*: a context-local
decision journal, `mac_runtime/journal.py`. When no journal is bound the calls are a `None` check
and a return — every unit test and every embedded use pays nothing. `run_pipeline` binds one per
stage and drains it into the `StageDetail` that already reaches the wire.

The record that matters is the DECISION:

```yaml
choosing: measure_column
among:
  - {id: SquareMeters, verdict: chosen,   because: "field_role: measure"}
  - {id: Latitude,     verdict: rejected, because: "field_role: dimension"}
chose: SquareMeters
decided_by: concept://example/contoso/Store#grounding.field_roles
at: "planner/grounded_columns.py:323"
```

`decided_by` is the load-bearing field and it doubles as the instrument: when it reads
`code:<module>.<fn>` instead of a declaration ref, **that is a finding** — the engine deciding
something the ontology did not. Count it with its denominator; the target is zero. It is the only
part of this design that can go red on its own.

**Three seams first, because three known live defects sit in them:** `_format_ontology_context`
(the truncation that shipped rules at 37 % and 66 % of their authored text, cut mid-word),
`_format_measures`/`_dimensions`/`_countables` (the `SquareMeters` omission), and the resolver's
candidate set (`Resolution.candidates: int` keeps the count and discards the alternatives — the
"why", one field short). The other nine seams follow.

Two mutants ship in the same PR: force `_place_filter` down its other branch and assert the
decision's `chose` changes; truncate a default reading and assert the assembly record goes red.
**A trace that does not move when the engine moves is a narrative, not evidence.**

Large payloads are content-addressed the way `prompts/` already is (5 files for 77 captures — 15×
dedup): `responses/<sha>` for the raw model output, `assembly/<sha>` for which concept contributed
which block and **what was excluded and on what test**. The `answer` event stops carrying a second
copy of the answer — measured at **63 % of the largest existing trace**, the same pathology as
`answer_parts.raw` being 41 % of the capture plane. Both retire together.

**On "stack and calls of python functions":** every record carries `at: file.py:line fn`, and span
ancestry gives the call path in the domain's own words (`run → plan → resolve.filter →
register.match`). That form is readable and, unlike a frame list, **diffable between two runs** —
which is the point. `MAC_TRACE=stack` attaches the literal `traceback` to decisions only, for the
pathological hour.

## 4. ONE SURFACE

**The board** tells the truth about its own denominator. `Unproven` gets a stat card the same size
as Proven/Routed/Failed, reading *"not yet checked — not wrong"*: 59 of 77 are unproven and most of
that is a missing anchor, not a wrong answer. Columns reorder to `ID | Question | Verdict | Checks
| Run` so the rollup comes before the four quiet squares. The legend stands visible instead of
hiding in a tooltip. `CorpusHealth` stops rendering `Alert variant="destructive"` — it is **red**
today under text that says *"findings about the corpus, not the engine; they never change a
verdict"*, and red spent on a declared non-failure is what teaches a reader to see the whole page
as failure.

**The detail page** is the answer in the form the chat window gives it, then everything else in the
order it happened. The trace is the spine, not a section: the SQL becomes the expanded body of
stage 6 because that is where it happened, and the standalone `ResultSection` and `Executed SQL`
sections go. Three table implementations, five `<pre>` stylings and three near-identical mono pills
consolidate to one each.

**Depth is opt-in and scoped.** Stages and decisions are on the page; calls, prompt accounting and
raw model I/O open in a `Sheet` scoped to one stage — never "the whole run", which is how a
debugging surface becomes the log viewer this exercise exists to avoid.

**Two guards, both non-negotiable.** There are currently two independent state vocabularies both
claiming to be canonical for "did this pass" (`kit.jsx`, 7 states; `FlagStrip.jsx`, 5 with its own
dev-time invariant), and both exist because a UI-side re-derivation once disagreed with the
server's. They merge, and the merge ships with the invariant extended over the merged table —
emerald reachable only from `pass` — so a mis-mapped state fails the build rather than turning an
honest wall of amber into a dishonest wall of green. And a decision's basis gets **its own**
vocabulary: the existing C/I/Q badge already means *"how confirmed are the concepts this answer
touched"*, and reusing it for *"what decided this choice"* gives one badge two meanings, which is
the same defect at a different layer.

## 5. WHAT WE STOP DOING

**No general orphan detector.** Two were written against this estate. One flagged 40 of 66
framework gates as dead; `run_framework_gates.sh:146` globs them. The other returned sixteen hits
of which essentially all were LangChain attributes and `__file__`. **A noisy gate is worse than
none, because a reader learns to ignore it** — this estate's own standard, applied to itself.

What ships instead is narrow and has no false positives: **a model field declared and never
assigned**, scoped to the runtime's models and the generator's schema types. It catches
`declared_fk` and `candidates: int`, two of the ten orphans measured yesterday.

The habit matters more than the gate: **before proposing a mechanism, grep for the existing one.**
Every defect found on 2026-09-24 was an orphan — `_index` asked for by two interpreters and set by
nobody, `declared_fk` on the dataclass since day one, `testpaths` naming four of eight test
packages while the suite reported 834 green over a console that would not start. Not one was a
wrong algorithm.

---

## The order

| | why here |
|---|---|
| 1. `/questions/run` drains `run_pipeline` | one runner; every capture gains a trace; the 21 blank refusals stop being blank. Smallest change, largest unlock |
| 2. `rulings/` gets a reader, surfacing as `disputed` | the estate's only authored authority is currently write-only, and it is the answer to 398 anchors that are all `authority: derived` |
| 3. board + detail page, and the merged vocabulary | the plane is now worth reading; make it readable |
| 4. `journal.py` + the three seams + the two mutants | the *why*. Three known defects sit in those three seams |
| 5. corpus reader learns `master.yaml` | four bundles appear. Do it after the board is honest, so the denominator change lands on a page that explains itself |
| 6. retire `raw:`, the duplicated answer event, and `mac-eval`'s skeleton | cleanup, once nothing depends on them |

Steps 1 and 2 are days, not weeks. Nothing before step 4 needs a schema bump.

---

## The one thing that is yours

**Traces hold result rows, and contoso is a public bundle at leak floor 0.** `TraceStore`'s own
docstring says the base "lives outside the repository and outside every bundle" for exactly that
reason. So pinning a trace into `acceptance/traces/` is a leak decision:

- **redact on pin** — drop everything beyond the `result.sample_rows` the capture already carries,
  and gate it with the existing leak check; or
- **pin outside the bundle**, with only `trace_sha` in the repo.

I recommend redaction, because a trace nobody can fetch from the repo is a trace nobody reads — but
this is a leak ruling and not an agent's call. **It blocks step 4's pinning and nothing else**;
steps 1–3 proceed either way.
