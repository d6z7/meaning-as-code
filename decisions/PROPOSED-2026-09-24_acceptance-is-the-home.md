# PROPOSED — 2026-09-24 · `acceptance/` is the home, and the trace already exists

**Status: PROPOSED. An agent may only write PROPOSED (CORE §3).**
Packet for `PIPELINE_TESTING.md` §9 ruling 1. The ruling is the operator's.

Produced by a system-architect analysis, then verified independently. Every number below was
measured; the command or file is given.

---

## 1. The ruling as posed is already decided — the real fork is elsewhere

| measured | |
|---|---|
| bundles with an `eval/` directory | **0 of 6** |
| `packages/mac-eval` public surface | `__all__: list[str] = []`; one test asserting `__doc__ is not None` |
| references to `06-SPEC-eval-harness` outside itself | **0** |
| bundles with `acceptance/` | **6 of 6** |
| …whose corpus file is `questions.yaml` | **1** (contoso) |
| …whose corpus file is `master.yaml` | **4** (estate, SystemC, spg, federation) |
| corpus files the projector can read | **`questions.yaml` only** (`sdk/project/questions.py:267`, `sdk/acceptance/run.py:165`) |

`eval/` was designed and never built. **The fork that actually happened is inside `acceptance/`:
four of six acceptance planes are invisible to the projector, the flag model and the board**
because they spell the corpus differently. That is a bigger number than anything 06 was about.

**Recommendation: `acceptance/` is the home. `eval/` is retired as a per-bundle directory.**

What is genuinely lost, and must be harvested rather than dropped — four clauses 06 had and
`acceptance/` lacks:

1. **stage attribution** on every non-pass (§2 below — and it turns out to exist already);
2. **mandatory `clarify` + `refuse` fixtures per suite** — contoso has 21 refusals but no rule that
   a suite must contain one, so a suite could quietly stop testing the decline;
3. **`--interpret cached | live`** — replay determinism; `intents.yaml` + `replay_diff.py` are most
   of it already;
4. **baseline gating, non-zero exit below baseline** — `suite_history.jsonl` records and gates
   nothing.

What is lost by keeping both homes: **two denominators.** This estate's signature failure is a
number without one; a second suite guarantees "how many are green" has two answers.

**Keep 06's separation as the LEG axis, not as a directory.** `PIPELINE_TESTING` §4's
A-conformance / B-acceptance / C-benchmark split is by SUBJECT. A and C are not per-bundle and
must not live in a bundle directory: A is synthetic reference bundles, C is
`meaning-as-code/benchmark/`. **`acceptance/` is exactly and only Leg B.**

---

## 2. Stage attribution is not missing — it is recorded and then destroyed

The finding that reframes the operator's whole request.

| measured | where |
|---|---|
| `run_pipeline` is already "the ask pipeline as a stream of typed stage events" | `mac-runtime/pipeline.py:1` |
| typed per-stage detail records already exist | `LoadDetail`…`EvaluateDetail`, `pipeline.py:212–270` |
| a per-run NDJSON trace store already exists | `TraceStore`, `mac-console/ask_stream.py:285` |
| an endpoint already serves it | `GET /ask-runs/{domain}/{dataset}/{run_id}/trace` |
| traces on disk right now | **52 files, 952 kB**, `$TMPDIR/mac-console-ask/` |
| traces carrying a stage-named refusal | **26 of 52** |
| **captures carrying a `run_id`** | **0 of 77** |

A real event, read off disk:

```json
{ "kind": "stage.finished", "stage": "interpret", "attempt": 2, "status": "clarify",
  "duration_ms": 5019,
  "summary": "Not confident enough to go on (confidence 0.40 < 0.50)",
  "detail": { "intent": {"subject": "NetSalesAmount", "operation": "rank", ...},
              "confidence": 0.4, "threshold": 0.5, "question_sent": "...", "carried": ... } }
```

The stage is named. The confidence is there. **The intent is there** — and the capture for that
same question records `route: refusal` with no intent at all. Measured: **21 of 77 captures are
refusals, and 21 of 21 carry no intent, no prompt, no `answer_parts`.**

> The trace view renders stages 2–7 as em-dashes on exactly the questions that need debugging,
> because the capture is built from the returned answer object, not from the run.

The traces are written to `$TMPDIR`, pruned at 200 files, deleted wholesale by `/close`, and never
linked to the question they answered.

**Withdrawn:** an earlier version of this proposal added a `stages:` block to
`answers/<id>.yaml`. That would have been a second home for a fact `run_pipeline` already emits —
precisely the objection made above to keeping `eval/`. It is withdrawn.

**The corrected shape:**

```
  trace (NDJSON, hot)  ──▶ SOURCE OF TRUTH for what happened, per run
        ├─ pinned for the run-of-record ──▶ acceptance/traces/<sha>.ndjson.gz
        └─ projected at read time       ──▶ the console's 8-stage trace view (unchanged)

  answers/<id>.yaml ──▶ EVIDENCE   + run_id + trace_sha.  No stages: block.
  rulings/<id>.yaml ──▶ JUDGEMENT  per stage.  Unchanged — still needs a reader.
```

`_trace_for` keeps working as written (which is what makes it work on all 77 pre-existing
captures) and gains one branch: *if `trace_sha` is present read the pinned trace, else derive from
the capture as today.* No schema bump.

---

## 3. File layout

```
acceptance/
  questions.yaml            CORPUS       one record per QUESTION. authored. the denominator.
  oracle/<id>.yaml          EXPECTATION  one per question. `authority` REQUIRED.
  anchors/<ID>.yaml         PINNED FACT  two non-engine routes. `authority` REQUIRED.
  intents.yaml              GOLD INTENT  hand-written, no LLM         [exists, unspecified]
  paraphrases.yaml          STABILITY    one question -> k variants   [exists, unspecified]
  answers/<id>.yaml         EVIDENCE     + run_id + trace_sha
  prompts/<sha>.txt         INPUT        content-addressed            [exists — 5 files / 77 Q]
  responses/<sha>.txt       INPUT        the raw LLM response         [new]
  assembly/<sha>.json       INPUT        which concept contributed which block, and what was EXCLUDED
  traces/<sha>.ndjson.gz    EXECUTION    the run-of-record's trace    [new]
  rulings/<id>.yaml         JUDGEMENT    per stage                    [written, UNREAD]
  questions_dashboard.json  PROJECTION   derived, never edited
  runs/                     suite run records
```

Four opinions inside it:

**(a) One corpus reader — adapt, do not rename.** `master.yaml`'s `groups[].questions[]` flattens
to the same row shape with `tier`/`complexity`/`category` the dashboard rows already have. One
reader change, zero bundle edits, four dark planes light up. Renaming would discard authored
`groups[]` content for no gain.

**(b) `b_answers/` (estate) → `answers/`.** Two answer directories in one bundle is two homes.

**(c) `acceptance/tools/` leaves the bundle.** `tools/intent_killtest.py` has
`ROOT = Path("/Users/<operator>/dev/mac-ontology-contoso")` hardcoded at module level — framework
machinery in a bundle's clothing, unable to run on estate. Generic goes generic.

**(d) `rulings/` is promoted from write-only to an input.** Verified: the directory exists in
**0 of 6** bundles and the only code naming the path is `console_api.py` — the writer. **The
estate's only authored authority is a file nobody consults.** A stage ruling of `wrong` over
all-green flags must surface as **`disputed`**, a state `flags.py` already carries.

---

## 4. Migration

**Monday — half a day, no schema change, no new module.** Make the capture writer read the run it
already made: `run_id` + `trace_sha` onto the capture; keep the rejected intent and confidence
`InterpretDetail` already carries; carry `stage.finished.stage` onto the refusal.

> This alone moves `PIPELINE_TESTING` §10's smallest number — **0 of 21 refusals carrying a
> stage** — to 21 of 21, and it is self-checking: the machine's spread must match the hand
> classification of the same 21 (**12 interpret · 6 resolve · 3 plan · 0 execute**). If it does
> not, the instrument is wrong, not the classification.

**Then, in order:** stop discarding the low-confidence intent in `interpret/gate.py` (12 of 21
refusals become debuggable, and `Intent.confidence` — consumed, calibrated nowhere — gets its
first 21 points against outcome) · make `rulings/` readable as `disputed` · teach the reader
`master.yaml` (announce the denominator change before it lands or it reads as a regression) ·
retire or rehome `mac-eval`.

**What breaks:** the committed ask fixtures change the moment `StageFinished.detail` gains a
field; `tools/gen_ask_fixtures.py` regenerates in the same commit. That is the contract working,
but it will look like a regression on the diff.

---

## 5. Open, and it is a leak ruling

`TraceStore`'s own docstring: the base "lives outside the repository and outside every bundle:
**traces hold result rows**." Contoso is public at leak floor 0. Pinning into `acceptance/traces/`
needs either **(a)** redaction on pin — drop everything beyond the `result.sample_rows` the capture
already carries — or **(b)** a sibling store outside the bundle with only `trace_sha` in the repo.
The architect leans (a); **run the leak gate against one redacted pinned trace before building the
pin.** That is the assumption not yet verified, and it decides the layout.
