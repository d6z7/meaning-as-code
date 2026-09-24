# PROPOSED — 2026-09-24 · execution tracing, and the UX that reads it

**Status: PROPOSED. An agent may only write PROPOSED (CORE §3).**

The requirement, in the operator's words:

> "i would still like every step ideally to be traceable — or at least debug loggable: what goes
> to llm, how is it composed and why ... what steps are deciding what goes ... stack and calls of
> functions and python functions ... everything what LLM responds ... and everything what happens
> after that."

Read `PROPOSED-2026-09-24_acceptance-is-the-home.md` first — §2 there establishes that the trace
already exists and is discarded at the capture boundary. **This document is about the DEPTH it
lacks and the surface that reads it.**

---

# PART I — RECORDING

## 1. Mechanism: a context-local decision journal

One new module, `mac_runtime/journal.py`, holding a `ContextVar[Journal | None]`. Call sites call
`journal.decide(...)` / `note(...)` / `span(...)`. **When no journal is bound — every unit test,
every embedded use, production if switched off — the calls are a `None` check and a return.**

`run_pipeline` binds a journal per stage and drains it at `StageFinished`, attaching it to the
existing `StageDetail`. **No new transport, no new file format, no new endpoint, no new consumer.**

Alternatives and why not:

| option | why not |
|---|---|
| return-value threading | touches every signature in `planner/`, `resolver/`, `foldplane/` and buys nothing a ContextVar does not |
| decorators at seams | a decorator sees arguments and a return value. **It cannot see the candidates that lost** — which is exactly the "why" |
| OpenTelemetry | a dependency, a collector, a wire format we do not control — and a span has no slot for "here are the 6 candidates and why 5 lost". Steal the vocabulary; refuse the dependency |
| stdlib `logging` | the runtime has **zero** logging today. String logs in a pure engine give an unparseable log nobody reads — the failure mode to design against |

**Two constraints, both already stated in the code:**

1. **Determinism survives.** `pipeline.py:1` — the caller injects `new_uuid`, `now`, `monotonic`
   "so a fixture generator can produce byte-stable output", and `tools/gen_ask_fixtures.py` relies
   on it. **The journal takes no clock and no uuid of its own.** Ordering is the envelope's
   existing `seq`. A journal calling `time.time()` would break the committed fixtures and the
   breakage would look like a contract regression.
2. **The prompt rule holds inside the trace.** The trace may and must record physical names — that
   is its job. The prompt-assembly span **must not become a back door** by which a column name is
   rendered into something later fed to a model. `diagnose/base.py` already defines the blind
   projection for anything that goes back to a model; that discipline does not bend.

## 2. Span · Event · Decision

**SPAN** — a named region with a parent. Structural, cheap.
**EVENT** — a point observation inside a span (a register read, an emit).
**DECISION** — the novel record, and the one that answers "why":

```yaml
kind: decision
choosing: register_candidate
among:
  - {id: DE, verdict: chosen,   tier: exact, because: "name_key == 'germany'"}
  - {id: DD, verdict: rejected, tier: fuzzy, because: "below the declared match floor"}
  - {id: AT, verdict: rejected, tier: none,  because: "no declared search key matched"}
chose: DE
decided_by: register://contoso/country#match.by_name_key
fallback: false
at: "resolver/register_match.py:131"
```

Four fields carry the design:

* **`among`** — the alternatives AND why each lost. Nothing records this today. It is a near-miss,
  not a greenfield: `resolver/pinned.py:165` already has `Resolution` with `chosen` and
  **`candidates: int`** — the count survives, the set is discarded.
* **`decided_by`** — a declaration ref, **or** the literal `code:<module>.<fn>` when no declaration
  decided it.
* **`fallback: true`** — the branch was a default taken in the declaration's silence.
* **`at`** — a literal at the call site, not a `traceback` call.

**Why `decided_by` is the most important field.** The estate's standing rule is that every
behaviour comes from a declaration, never a code branch. So a decision recording
`decided_by: code:planner._place_filter` is **a finding, not a log line** — the engine deciding
something the ontology did not. That turns the trace from a diagnostic into an instrument with a
number and a denominator:

> `code:` decisions / total decisions, per question and per bundle — **target zero.**

It is the only part of this design that can go red on its own.

## 3. "Stack and calls of python functions" — the form

A `traceback` frame list from `plan()` is 20–40 frames of pydantic machinery, answers *how the
interpreter got here* rather than *what the code chose*, and **changes when someone extracts a
helper — so it cannot be diffed run-to-run**, which is the whole point.

The same information, addressed twice, serves the need better:

* **the site** — `at: "planner/grounded_columns.py:323 measure_column"` on every record. Zero cost,
  clickable.
* **the path** — span ancestry IS a call stack, written in the domain's words:
  `run → plan → resolve.filter → register.match → decision`. Readable, and **diffable between two
  runs**.

And the literal thing too, gated: `MAC_TRACE=stack` attaches `traceback.extract_stack()` **to
decisions only**. The escape hatch for the pathological hour, free when off.

## 4. Volume — measured, not guessed

The largest trace on disk is 39 kB, decomposed:

| share | event |
|---|---|
| **63.3 %** | `answer` — one duplicated answer payload |
| 12.1 % | `stage.finished/plan` |
| 5.9 % | `stage.finished/evaluate` |
| remainder | the other stages and envelopes |

**Today's trace is already 63 % a duplicated answer** — the same pathology as `answer_parts.raw`
(41 % of the capture plane). Fix both in the same commit: the `answer` event carries the answer's
id and sha, not a second copy.

Five levels via `MAC_TRACE=`: `off` · `stages` (today, minus the duplicate, ~13 kB) · `decisions`
(default for acceptance runs, est. 20–30 kB) · `full` (~35–45 kB + refs) · `stack` (opt-in, one
question). **The estimates are derived from a seam count, not measured — measure on 10 questions
before fixing the level defaults.**

Large payloads are content-addressed, and the estate already proved the ratio: `acceptance/prompts/`
holds **5 files for 77 captures** — 15× dedup on a 52 kB artefact. Same trick for `responses/<sha>`
and `assembly/<sha>`.

`assembly/<sha>.json` is requirement 1 done properly — per concept:
`{concept, blocks, included, because, chars_authored, chars_emitted}`. **That last pair is the
direct instrument for a live defect**: default readings reached the model at 2 000 of 5 418 chars
(37 %) and never-clauses at 66 %, cut mid-word, and nothing surfaced it. With both numbers on a
record, a gate asserts equality and truncation can never be silent again.

## 5. Seams — 12, and the selection rule

**Instrument a function only where it chooses among alternatives, or where it includes/excludes
something from what the model sees.** Everything else is a span boundary at most.

*Interpret:* `build_system_prompt` (span + `prompts/` + `assembly/`) · `_format_ontology_context`
(decision per concept, the 37 %/66 % detector) · `_format_measures`/`_dimensions`/`_countables`
(decision: which concepts entered each list — the `SquareMeters` defect's home) · the provider call
(event: resolved model, retries, tokens, `responses/<sha>` verbatim) · `gate.py:63` (decision:
confidence vs threshold, **keeping the rejected intent**).

*Plan:* `_resolve_measure` · `_place_filter` · `resolve.py:131` (**`among` = the candidates, not
`candidates: int`**) · `reporting_cycle` / `measure_column` / `period_column` / `variant_selector` ·
`resolve_join` · `foldplane/law.py decide`.

*Execute/Evaluate:* bound params, engine query id, bytes scanned; the verdict and its checks.

**Deliberately not instrumented:** the ontology parser, the index, adapter SQL string building,
pydantic validators. They transform; they do not choose. Add one when a defect justifies it — that
is how the list stays short enough to read.

## 6. How it stays honest

1. **The trace is a by-product of execution, not a description of it.** A decision record is
   written by the branch that was taken, inside the function that took it. There is no second code
   path that could describe something the engine did not do.
2. **`decided_by: code:` is a red** — count it with its denominator, trend to zero. **This is the
   check that can fail.**
3. **`chars_authored` ≠ `chars_emitted` is a red.** The 37 % defect becomes impossible to
   reintroduce silently.
4. **Instrument the instrument.** Two mutants: force `_place_filter` down its other branch and
   assert the decision's `chose` changes; truncate a default reading to `[:100]` and assert the
   assembly record goes red. **A trace that does not move when the engine moves is a narrative,
   not evidence.**

And one negative discipline: **the trace never carries a verdict.** It records what happened;
`rulings/` records what a person says about it.

---

# PART II — READING

## 7. Three levels, plus an overlay

| level | unit | where | default |
|---|---|---|---|
| **L1 Stage** | the 8 steps | detail page, in Trace | always visible, body collapsed |
| **L2 Decision** | one choice, with alternatives | inside an opened stage | visible on open; the implicated one auto-expands |
| **L3 Call / Composition / Raw** | calls, prompt accounting, raw LLM I/O, diff | a `Sheet` overlay | closed, and **scoped** to one stage — never "the whole run" |

L1 is 8 rows; L2 is 1–4 decisions per stage, ~15–25 for a whole question — dense but readable in
one scroll, and it answers "why" for most sessions. **L3 is uncounted**, and inlining any of it
recreates the exact complaint that started this.

**Click budget.** Operator: row → auto-flashed stage, auto-expanded decision, one-sentence why —
**0 further clicks.** Developer: same, then "Show calls" — **2 clicks to the call ladder**, scoped
to ~10–20 calls rather than the run's few hundred.

## 8. A decision, rendered

```
┌──────────────────────────────────────────────────────────────────┐
│ ▣  Picked SquareMeters as Store's measure column                  │
│    because field_role: measure on the grounding declaration.      │
│    considered  [SquareMeters ✓] [Latitude ✗] [Longitude ✗]       │
│                                                        [expand ▾] │
├──────────────────────────────────────────────────────────────────┤
│    excluded — Latitude   field_role: dimension  (grounding:41)    │
│    declaration  concept://example/contoso/Store#SquareMeters      │
│    ── dev ───────────────────────────────────────────────────────│
│    call site  measure_column()  grounded_columns.py:323 · 0.4ms   │
└──────────────────────────────────────────────────────────────────┘
```

**And it must render the murky case as easily as the clean one:**

```
┌──────────────────────────────────────────────────────────────────┐
│ ▨  Picked NetSalesAmount over GrossSalesAmount for "revenue"       │
│    — no declaration named a default; the LLM inferred it from     │
│    phrasing. Not independently confirmed.                         │
└──────────────────────────────────────────────────────────────────┘
```

**CORRECTION TO THE ORIGINAL PROPOSAL, and it matters.** The designer proposed reusing the
existing `ConfidenceBadge` C/I/Q tiers for a decision's basis. **Those tiers already mean something
else** — `AnswerSections.jsx:118`: *C = every concept and rule this answer touched is confirmed;
I = at least one is inferred; Q = at least one is still an open question.* That is about the
ontology's confidence in its concepts, not about what decided a choice. Reusing them gives one
badge two meanings — **precisely the defect the same review identified in the two colour tables.**
A decision's basis needs its own vocabulary.

## 9. Prompt composition — a ledger, not a 52 kB `<pre>`

```
┌ Prompt breakdown — RC05 · 49,292 chars · 5 sections ──────────────────────┐
│ ## Business Model                                          14,220 / 14,220 │
│   Store        [████████████████████]  3,120 / 3,120   full            ▸  │
│   OrderLine    [█████████████░░░░░░░]  2,400 / 3,636   66%  ⚠ truncated ▸ │
│ ## Dimensions — 3 concepts EXCLUDED (no rows matched this route)       ▸  │
│ [Show raw prompt text ↓]                                                   │
└────────────────────────────────────────────────────────────────────────────┘
```

**Every contributor shows included / authored always.** Because the bar is drawn from that ratio
for every contributor on every trace, **a silent truncation becomes structurally visible** rather
than something a view happens to catch. Excluded contributors get a row with the reason, never
just absence — an omission not shown as an omission is the failure this fixes.

## 10. Board and detail page

Unchanged from the first UX review and still recommended:

* **`Unproven` gets a stat card**, same size as Proven/Routed/Failed, with the sub-line *"not yet
  checked — not wrong."* Today it has none, while Failed sits in red as the loudest number. 59 of
  77 are unproven and most of that is **absence of an anchor**, not a wrong answer.
* **Reorder columns** to `ID | Question | Verdict | Checks | Run` — the rollup a reader scans for
  comes first.
* **A standing legend**, not a tooltip.
* **`CorpusHealth` stops using `Alert variant="destructive"`.** Verified at
  `QuestionResultView.jsx:591`: it renders **red** under text that says *"findings about the
  corpus, not the engine; they never change a verdict."* Red spent on a declared non-failure is
  what trains a reader to see the whole page as failure.
* **Delete** the standalone `ResultSection` and `Executed SQL` sections — the SQL becomes the
  expanded body of Trace stage 6, where it happened. Consolidate three table implementations, five
  `<pre>` stylings, and the three near-identical mono pills.

## 11. The two risks

**One vocabulary, or the merge reintroduces what it was built to remove.** Two independent state
tables both claim to be canonical for "did this pass" — `kit.jsx` (7 states) and `FlagStrip.jsx`
(5 states, with its own dev-time invariant). Both exist *because* a UI-side re-derivation once
disagreed with the server's. Merging them is right, but **it must ship with the dev-time invariant
extended over the merged table** — emerald reachable only from `pass` — so a mis-mapped state fails
the build rather than turning an honest wall of amber into a dishonest wall of green.

**The decision card is seductive because it reads as a confident sentence.** "Picked X because Y"
can outrun what the system knows. The moment every decision is forced into that shape — including
when the real answer is "a heuristic guessed and nothing confirms it" — the page fabricates
certainty. The mitigation is structural, not stylistic: **the low-confidence rendering must be as
fully supported and as commonly exercised as the confident one**, or someone will eventually smooth
it into a fake "because" to make the page look tidy.
