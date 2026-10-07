<!-- STATUS: PROPOSED. Not ratified. An agent may write PROPOSED (Part A §A.8); the rulings this
     document defers are marked and are the operator's.
     TWO PARTS SINCE 2026-09-29. Part A is the former TESTING.md — the one law, the three-question test,
     the ten categories and the six laws of reporting — merged here so the doctrine and the instruments
     are one document. Part B is the original PIPELINE TESTING proposal: WHICH INSTRUMENT TESTS WHICH
     STAGE of question -> answer, and where each one's oracle comes from. Part B's section numbers are
     unchanged, so existing citations of `PIPELINE_TESTING.md §n` still resolve.
     Paths: bundle-relative for bundle files (`acceptance/…`, `data/…`, `master.yaml`, `compile.json` …);
     runtime files carry the `mac-platform/` prefix. Every number was measured on 2026-09-24 (Part B) and
     2026-09-13/14 (Part A) against the landed code and the worked bundle. -->

# TESTING IN MAC — THE DOCTRINE AND THE INSTRUMENTS

> **§ anchor map — citations of the former `TESTING.md` resolve here.** `TESTING.md §1` → [A.1 The One Law](#testing-1) · `TESTING.md §2` → [A.2 The Categories](#testing-2) · `TESTING.md §3` → [A.3 Provenance, And The Combinations That Are Forbidden](#testing-3) · `TESTING.md §4` → [A.4 Quality And Testing Are One Overview](#testing-4) · `TESTING.md §5` → [A.5 The Six Laws Of Reporting](#testing-5) · `TESTING.md §6` → [A.6 Naming Hazards](#testing-6) · `TESTING.md §7` → [A.7 The Horizon](#testing-7) · `TESTING.md §8` → [A.8 What This Document Refuses To Decide](#testing-8) · `TESTING.md §9` → [A.9 How To Write Test Cases For Data Quality](#testing-9). Citations of `PIPELINE_TESTING.md §n` (from `invariants/`, `recognition/`, `benchmark/`, `bundlegen/`) resolve to
> Part B, whose numbering is unchanged. Merged 2026-09-29; `TESTING.md` is now a redirect naming these anchors.

---

<a id="testing"></a>
# PART A · WHAT TESTING MEANS IN MAC, AND WHAT A GREEN IS ALLOWED TO MEAN
### (the former `TESTING.md`, merged here 2026-09-29 — section numbers A.1–A.9)

**Status: the lighthouse.** Not a plan and not a checklist. This is the fixed point to steer by; it is
deliberately further away than any quarter's work, and its job is to make the direction unambiguous
when a hundred small decisions each look locally reasonable. Reaching it will not be easy. Steering
by it should be.

**Scope.** Testing of **data** and of the **ontology** — because the operator's ruling is that ontology
tests become part of the MAC standard, and a standard lives in the language repo. The testing of the
**console and platform surface** is the same concept applied to a different subject and is specified
in `mac-platform/docs/08-SPEC-testing-surface.md`. The **practice** — how an agent goes about authoring
a suite — stays in `mac-integration-kit/ontology/planes/testing.md`, which this document does not
replace and must not duplicate.

**What this document is NOT about.** `CONFORMANCE.md` §5.4 already owns *what a clean compile does and
does not prove*; compiling is not testing and this document defers to it. `QUALITY.md` in this repo is
the **pre-offer change checklist for the framework itself** — a different sense of the word, and the
first naming hazard recorded below.

---

<a id="testing-1"></a>
## A.1 · THE ONE LAW

> **A test is classified by WHERE ITS EXPECTATION COMES FROM, not by how much code it runs.**

Unit / integration / end-to-end classifies by blast radius. That axis is useless here, and the
estate has the measurement to prove it:

```
tests DERIVED from the artifact they test     2,5 % not green   (241 of 293)
tests AUTHORED independently                 46,2 % not green   ( 52 of 293)
                                             ------------------
                                             an 18x gap
```

Not because derived tests are better. Because **a test rendered from the artifact it tests cannot
disagree with it.** This framework's own vocabulary states the mechanism:

> *"a test rendered entirely from the ontology AGREES WITH THE ONTOLOGY, so a wrong declaration
> produces a green suite."* — `mac_vocabulary.yaml`, `test_kind` preamble

And the worked proof runs the other way too: a grain property, an **authored** one, caught a
descriptor claiming `VERIFIED … 0 multi-row` against a warehouse that had reached millions of multi-row cells. The
plane records that *"a conformance test rendered from that same declaration would have confirmed the
stale claim."*

### THE THREE-QUESTION TEST — apply this BEFORE proposing any test, suite or category

Operator, and it is the governing rule of this document:

> *"the major problem with the question for a unit test: (1) you have to understand functionality
> that is implemented (2) you have to know how to write proper question — or what do you want to
> assert (3) you need to know what is the correct outcome/answer. So all what you are proposing must
> be subject to these categories."*

Those three are **SUBJECT · CLAIM · ORACLE**, and they decide generatability mechanically:

> **A TEST IS GENERATABLE EXACTLY WHEN ALL THREE ARE ALREADY DECLARED MACHINE-READABLY.**
> Where one is only in prose or only in a person's head, THAT part must be authored — and **which of
> the three is missing tells you exactly what the bundle must declare** to make it generatable.

Worked, against this estate's own measurements:

| suite | (1) subject | (2) claim | (3) oracle | consequence |
|---|---|---|---|---|
| data-sanity GENERATED | the profile | same-as-measured | **the prior measurement** | fully generated. The oracle is the SAME SUBJECT SEPARATED IN TIME — the only oracle in the estate permitted to disagree with the model |
| ontology GENERATED | the concept | warehouse matches declaration | the declaration | generated, and legitimate ONLY because the two sides have different authors and different reasons. Otherwise it is a mirror |
| rules GENERATED | the rule | SQL respects it | the directive | **BLOCKED AT (1)** — 23 of 31 rules state their directive in prose `then:` clauses, so nothing can read what the rule means. This is why coverage ceilings at 8 of 31: a tooling fix cannot reach it |
| grounding · registers · joins | a declaration | structural | the other declaration | fully generated |
| freshness | `produces`/`reads` | derived newer than subject | timestamps | fully generated — arithmetic over facts |
| vocabulary | the closed set | no term outside it | the set | fully generated |
| boundaries | declared scope | must refuse | **a human rules it out of scope** | enumeration generates, **(3) authored** |
| corpus (TRUTH) | **human** | **human** | **human, from outside the system** | nothing generates but the FRAME |

**AND THE VACUITY RULE FALLS OUT OF IT.** A test with (1) and (2) but a hollow (3) passes and proves
nothing — that is the estate's 59 vacuous assertions over 29 properties. So a `conformance` test,
whose oracle IS the declaration, is honest only where the two declarations are genuinely maintained
by different people for different reasons. Where they are not, it is a mirror wearing a verdict.

### The rule an agent can apply

> **DERIVE THE ENUMERATION. AUTHOR THE ORACLE.**
> Generating *which* concepts, rules and questions need a test is legitimate and should be
> exhaustive. Generating *what the answer should be on the axis under test* is forbidden, because
> there the test inherits the claim it exists to challenge.

---

<a id="testing-2"></a>
## A.2 · THE CATEGORIES

Derived from the goal sentence rather than from observed failures, which **is** the exhaustiveness
argument: a missing category would have to be a clause of the goal that maps to nothing.

> *An ontology **declares meaning once**, and a **business question** gets a **trustworthy answer**
> from **real data** — **repeatably**, **across bundles**, by **people who didn't write the ontology**.*

| category | the claim it establishes | provenance | where its red goes |
|---|---|---|---|
| **FITNESS** | the source is complete, consistent, correctly shaped, free of material never meant to be read | **generated** from data profiles | the **source owner** — never the ontology |
| **FORM** | every declaration is legal against its grammar | **generated** (the grammar is the authority) | whoever authored the declaration |
| **AGREEMENT** | two declarations of one fact match | **generated** (the other side is the oracle) | whichever side is wrong — name **both** |
| **COMPOSITION** | the machinery computes what the meaning says: grain, additivity | enumeration generated · **invariant authored** | the rule's author, or the generator |
| **COMPLETENESS** | the declaration is sufficient for the questions asked of it | **generated** | whoever owns the gap |
| **RECOGNITION** | a question reaches the right concepts | enumeration generated · **gold slots authored** | the concept's aliases |
| **TRUTH** | the number is right about the world | **authored only — generation forbidden** | a **named human** |
| **HUMILITY** | it declines when it must | enumeration generated · **expected class authored** | the scope declaration |
| **CURRENCY** | this result is about the artifact as it is now | **generated** from fingerprints | whoever let the result outlive its subject |
| **INSTRUMENT** | each check can still reject a deliberately broken input | **generated** mutants | the gate's author, **before** its subject |

**QUALITY IS NOT A SEPARATE SURFACE.** Operator ruling: *"quality belongs to the same overview — do
not separate it."* Data quality **is** FITNESS. Ontology quality **is** COMPLETENESS. They are rows in
this table, reported on the same board, not a parallel plane with its own findings and its own score.
§A.4 states what that fixes.

**`data_sanity.yaml` already carries the doctrine that makes this table actionable**, and it is a
*routing* rule no taxonomy had before it:

> *"A red here is **NOT a modelling defect and must never be "fixed" by changing the ontology** — the
> response is to tell the source owner, or to disclose the limitation in the answer."*

### KNOWN GAP — EXECUTION has no category

When a query fails **in the engine** — not in the meaning, not in the SQL — this table has nowhere to
send it. Three of one measured run's 35 failures were exactly that. Ten destinations are named above
and **none of them is the warehouse**. Either an eleventh category exists or engine failure is
declared out of scope; **an agent may not settle this.**

---

<a id="testing-3"></a>
## A.3 · PROVENANCE, AND THE COMBINATIONS THAT ARE FORBIDDEN

Provenance is the load-bearing property of every test, so it must be **declared and validated**, not
inferred. A category whose tests are wholly generated is reporting **agreement**, not truth.

```
legal for FITNESS · FORM · AGREEMENT · COMPLETENESS · CURRENCY · INSTRUMENT     derived
legal, as the ENUMERATION only, for COMPOSITION · RECOGNITION · HUMILITY        derived
FORBIDDEN as the expectation for COMPOSITION · RECOGNITION · HUMILITY · TRUTH   derived
```

**That single constraint is what stops this estate generating its way to a green suite** — and it must
live in the schema, because prose does not hold here. Measured adoption of prose instruments:
`authority: sme` used **0 of 398**; `question_id` **0 of 21**; `QUALITY.md` **183 commits and zero
appends**. The one channel that *was* adopted — `accepted:`/`frozen:`, 26 blocks — was adopted because
**a red could not move without it.**

### EXTEND THE EXISTING VOCABULARY. DO NOT COIN A PARALLEL ONE.

These already exist and are in use. Coining a synonym creates a seam, and that mistake has been made
four times in a single day in this estate:

| in use today | where |
|---|---|
| `mac.test_kind` — `ground_truth` · `conformance` | property and suite entries |
| `family`, `severity`, `source` (prose provenance) | suite entries |
| tier — `tier1-properties`, `tier2-retrieval` | suite names |
| `accepted:` / `frozen:` — the human-ruling channel | run records |
| `oracle_class` — `COMMIT` · `ASK` · `REFUSE` · `BLOCK` | oracles, dashboards |
| the authored/generated split, **as a file convention** | `x.yaml` beside `x_generated.yaml` |
| `mac.questions_dashboard/4` — the projector contract | console ↔ bundle |

What the standard still **lacks**, and these are additions rather than renames:

- **the outcome classes are ungoverned.** `mac.schema.json` contains no `COMMIT/ASK/REFUSE/BLOCK`
  enum. **CORRECTED 2026-09-13, and the correction is the lesson.** This first read "DECLINE (14)
  and REFUSE (4) coexist in one bundle for one concept". Those were counts from ONE FILE, quoted as
  if estate-wide. Structurally parsed across four roots, the real figures are **1 049 `DECLINE`
  against 1 347 `REFUSE` over 16 292 declarations** — off by ~75x — and the axis carries **ten
  spellings, not four**: the four canonical, plus `DECLINE` (deprecated), `COMMIT_PENDING`
  (provisional), and `ENUMERATE`/`MODEL_PROPERTY`/`DEFER`/`ENGINE_ERR` (non-grading). There are also
  **214 live lowercase case-variants**, invisible to any exact search. A closed enum drawn from the
  wrong count would have turned working bundles red, which is why membership must be decided from a
  measurement and not from a memory. A population that cannot be enumerated cannot have a
  denominator — and a population counted in one file is not the population.
- **`test_kind` is optional** where its whole point is that the two kinds have *opposite* rules about
  where their numbers come from. An undeclared property can be trusted for neither.
- **oracle authority is undeclared** on 297 of 398 oracles — not "derived", *undeclared*, which is
  worse, because nothing distinguishes an oracle resting on an independently known value from one
  reading its answer off the ontology.
- **tier is prose.** Nothing machine-readable carries it, so "run the cheap tier on every change" is
  a policy nothing can enforce or report against.

---

<a id="testing-4"></a>
## A.4 · QUALITY AND TESTING ARE ONE OVERVIEW

**A test** is one falsifiable claim about one subject with one verdict, belonging to exactly one
category above. **Quality** is the standing of a subject derived from the tests that bear on it. Same
facts; one surface.

Today they are stored twice, which is why the Quality section and the testing pages can disagree
without either being wrong:

| the fact | home 1 | home 2 |
|---|---|---|
| a property failed | `property_runs.json` | `ontology_quality.findings` (`category: property-failure`) |
| a data defect | `data_sanity.yaml` (machine) | `data/quality/DQ-*.md` (prose, ungated) |
| an SME question | 59 in `ontology_quality.json` | **0 of 398 oracles** |
| the compile verdict | `compile.json` | the console's `compile` kind |

**One verdict store. One overview. No second findings store.** `ontology_quality.json` stops *holding*
property failures and starts *reading* them. The `DQ-*.md` prose becomes the narrative attached to a
failing FITNESS entry, not a parallel tracker.

**And the `score` goes.** It averages concepts, rules, findings and SME questions — four units in one
number. That is precisely what makes a true failure rate unactionable.

---

<a id="testing-5"></a>
## A.5 · THE SIX LAWS OF REPORTING

Each from something measured, not from taste.

1. **NO SCORE, NO AVERAGE, NO HEADLINE PERCENTAGE.** A file, a rule, a question and a route are not
   addable. Every row declares its unit. Seven meanings of green averaged into one number is how a
   true 42,7 % became unreadable.
2. **NEVER-RUN IS ITS OWN STATE AND ITS OWN COLOUR.** Never folded into red, never into green. And
   *"no instrument declared at all"* is a **third** kind of empty, distinct from never-run.
3. **EVERY NUMBER SHOWS ITS DENOMINATOR.** A `PASS` over an unexamined population is this estate's
   dominant defect, found twice in one day in gates written that same day by their own author. And the
   denominator has two axes: a complete file list proves nothing if the *pattern* list is empty.
4. **A GREEN MUST HAVE BEEN ABLE TO FAIL.** An item counts as passing only where a seeded mutant made
   its check fail. Without this, the cheapest way to improve any number is to add checks that cannot
   fail — demonstrated: a headline moved from 1 565 to ~162 in one day, exit 0 throughout. So
   **CANNOT-FAIL is a real fourth state.**
5. **THE BOARD COMPUTES NOTHING.** Every flag, state and verdict arrives from the projector and is
   rendered verbatim. Already law here, and the reason is recorded: a board that re-derived its own
   grades disagreed with the export, on live data, and nothing errored.
6. **EVERY ROW SHOWS THE AGE OF WHAT IT READ.** A sixty-day-old green must look sixty days old. When
   history is shown: the ruled axis is the **never-run count, not a rate**, because a pass-rate line in
   this estate's record drew a *redefinition* as improvement — and never-run is the one series that
   cannot be shrunk without actually running something.

---

<a id="testing-6"></a>
## A.6 · NAMING HAZARDS — recorded so the next reader is not caught

- **"quality" means two things here.** `QUALITY.md` is the framework's pre-offer *change checklist*.
  The console's Quality section is *ontology and data* quality. Same word, unrelated subjects.
- **"eval" and "acceptance" are two corpus formats for one idea.** `acceptance/` (questions, oracles,
  anchors) is the ontology track's; `eval/suite.yaml` is specified for the platform's `mac-eval`. They
  both mean "a question with a verified answer". See the platform spec for the state of the second.
- **"conformance" is a `test_kind` AND a compile level.** `mac.test_kind.conformance` means "renders
  its assertion from the declaration"; `CONFORMANCE.md` means "passes the three compile gates".

---

<a id="testing-7"></a>
## A.7 · THE HORIZON — what arrival looks like, in numbers

Not targets for a quarter. The fixed point.

| | today | arrived |
|---|---|---|
| oracles with an independent, human-ruled authority | **0 of 398** | every TRUTH oracle, or the question is declared out of scope |
| rules carrying a machine-checkable invariant | **10 of 433** | every rule, or the rule is reshaped to be generatable |
| declared files neither validated nor waived | **1 144 of 1 195** | zero — validated or waived with a reason |
| seams enumerated but not scored | **577 of 664** | zero undispositioned |
| gates that prove they can reject | **11 of 51** | every gate, with a mutant per reject class |
| results whose staleness is detectable | **2 of 32** | every result carries its subject's fingerprint |
| bundles checking any seam at all | **1 of 11** | every bundle |
| the outcome-class vocabulary | **ungoverned** | closed in the schema, so the population is countable |
| a category's reds | reported | **routed** — every red names the desk it goes to |

**The one number that must become visible before any of the others move:** a live bundle's own last
committed run says **35 of 82 graded at `with-b` did not pass**, it is dated 2026-07-15, and **no
console view reads the file it lives in.** A true number that nothing displays cannot be seen to fall.

---

<a id="testing-8"></a>
## A.8 · WHAT THIS DOCUMENT REFUSES TO DECIDE

An agent may write `PROPOSED`; these are the operator's.

- whether **EXECUTION** becomes an eleventh category or engine failure is declared out of scope (§A.2)
- whether **RECOGNITION and HUMILITY** are one category or two — held apart on judgement, not
  measurement: a system that always answers is worse than one that declines, and that guarantee may
  deserve its own row
- whether a **frozen engine capture** is a legal TRUTH authority at all — currently legal but never
  green, which is stricter than it looks and retires existing captures if tightened
- whether `severity: blocker` already answers *"does this red block the build"*, in which case that
  question is settled in the ontology grammar and not open
- who the **named SME** is. An agent can propose the shape of the authority channel; it cannot create
  the authority.

---

<a id="testing-9"></a>
## A.9 · HOW TO WRITE TEST CASES FOR DATA QUALITY

§A.1 says when a test is generatable. This says where the tests actually come from, and the answer is
not "think of good checks". It is: **a MAC bundle already states dozens of claims about its own
data and verifies almost none of them.** Every unverified claim is a test waiting to be written.

So the work is not invention. It is **inventory, then falsification**.

### A.9.1 · WHAT A BUNDLE ALREADY HOLDS, AND WHAT EACH PIECE CAN GROUND

This is the whole method in one table. Left column: information every MAC bundle carries. Right
column: the test it grounds, with no domain knowledge added.

| where the claim lives | what it asserts | the test it grounds | oracle |
|---|---|---|---|
| `transforms/*.yaml` → `produces.grain` | "one row per X" (prose) | **IDENTITY** — uniqueness on X; a fan-out is a defect | internal coherence |
| `transforms/*.yaml` → rule `resolves: [DQ-id]` | "this transform dissolves that defect" | **DERIVATION** — differential, see 9.2 | internal coherence |
| `transforms/*.yaml` → `inputs[]` + `produces.relation` | the two ends of the transform | *which two relations to measure* | — |
| `quality/data_quality_register.yaml` + `DQ-*.md` | what the defect IS, concretely | *the predicate that detects it* | — |
| `datasets/*.yaml` → `columns[].role` | primary_key · composite_key_part · foreign_key | **IDENTITY** (the key list) and **REFERENCE** (orphans) | declaration |
| `profiles/*.yaml` → `columns[].distinct/nulls/min/max` | "when measured, it looked like this" | **STRUCTURE · VOCABULARY · COMPLETENESS** — drift only | prior measurement |
| `profiles/*.yaml` → `identity_evidence` | a measured key with a verdict | **IDENTITY**, and a cross-check on the grain prose | prior measurement |
| `concepts/*.yaml` → `values.closure` + `items[]` | "these are all the codes" | **VOCABULARY** — an undeclared code is a defect | declaration |
| `concepts/*.yaml` → a column's `roles.aggregate.type` | flow · stock · intensive · precomputed · target | **ARITHMETIC** — sum the parts, compare to the whole | declaration |
| `concepts/*.yaml` → `values.items[].served` | "these rows must never be read" | **SCOPE** — served material only | declaration |
| `transforms` + `datasets` + the fact | a produced relation and its inputs | **CONSISTENCY** — the same fact stated twice must agree | internal coherence |

**Read the table as a coverage grid.** A row with no test in the bundle is a claim nobody is
checking. An empty ORACLE of "internal coherence" across the whole grid means every green is drift
detection — the source could be wrong from the first day and nothing would ever say so.

### A.9.2 · THE DIFFERENTIAL TEST — the one that earns its keep

The strongest test available without a human, and it applies to every `resolves:` claim:

    UPSTREAM     the defect IS present in the transform's declared INPUT
    DOWNSTREAM   the defect is ABSENT from its declared OUTPUT
    same statement, same read, so neither half can see a different vintage

**Both halves or it proves nothing.** A check asserting only a clean output passes identically when
the transform does nothing and the defect never existed. The upstream half is the falsifier — and it
fires: the first such suite written here found a transform whose claimed defect was **not present in
its input at all**, meaning either the register is stale or the transform has been taking credit for
work it never did. No amount of downstream checking could have surfaced that.

The defect predicate comes from the register entry, never invented. Shapes vary — an EAV pivot, a
name inconsistency, a corrupt identity, an unresolved bucket — so **do not force one template over
all of them.** One query per claim, written from that claim's own prose.

### A.9.3 · TRANSLATING A PROSE CLAIM INTO COLUMNS

Most of the valuable claims are prose. A grain written as a sentence says *"one row per
(object × scope)"* and names no columns. Do not skip these — they are the highest-value claims in the bundle — and do not
guess the columns either. **Derive the key, then corroborate it twice:**

    the prose                      says WHAT identifies a row
    datasets[].columns[].role      primary_key / composite_key_part — the declared key
    profiles[].identity_evidence   a MEASURED key, where one exists

Where the three disagree, **that disagreement is itself the finding** — report it, do not silently
pick one. A grain the data plane and the profile describe differently is a defect nobody had seen.

### A.9.4 · FOUR TRAPS, EACH PAID FOR

**THE NEWEST CYCLE IS NOT THE NEWEST COMPLETE CYCLE.** Pinning `MAX(period)` lands on whatever
arrived last, including partial loads — and partial loads happen *mid-period*, not only at the
boundary. Measured here: of twelve periods, three were partial, two of them mid-month, each carrying
a single perspective and no roll-up. Eight blocker properties returned no rows for four days and
were read as eight data defects. **Pin to the newest period that satisfies a declared completeness
predicate**, and make that predicate a check of its own so a partial load is reported rather than
silently skipped past.

**`SUM` OVER AN EMPTY SET IS NULL; `COUNT` IS 0.** A query over zero rows still returns a row, with
nulls in every aggregate. The assertion then reads "column missing/null" and looks like a defect. It
is not — nothing was computed. Treat *no rows* and *all asserted columns null* as the same state:
**no verdict**, distinct from both pass and fail.

**A GREEN FROM A PRIOR MEASUREMENT IS NEARLY FREE.** Checks projected from a profile cannot
disagree with the profile. They are worth having — they catch drift — but they must be counted
separately, or a suite of two hundred of them will report a broken source as healthy.

**THE MIRROR PAIR.** Two relations with identical profiles produce two identical checks. Detect them
by profile fingerprint at generation time and emit one, or the suite inflates with duplicates that
all pass together and all miss together.

### A.9.5 · WHEN THE BUNDLE DOES NOT SAY ENOUGH

Some claims cannot be tested from what is declared: an ordering nobody wrote down, a meaning only a
domain expert holds, a proposal not yet applied. **Emit the question, not a test.**

A recorded *"not expressible, because X"* beside the claim it belongs to is worth more than a test
that passes for the wrong reason. It is also the exact input the ratification channel needs — the
question a named human can answer, after which the test generates itself.


---

<a id="pipeline"></a>
# PART B · PIPELINE TESTING
### An instrument for each stage, and the one stage that has no subject

> Part A answers *what a green is allowed to mean*. Part B answers *what we point at each stage of
> the pipeline, and what the oracle is when we do*.

The operator's complaint, verbatim, and it is accurate:

> *"our current testing is indicative … but in big picture its a joke. from my perspective we MIGHT
> need/want to break it down into steps and test steps individually. i don't know how to do it, but
> i do know that we need BETTER solution for testing and identification of white spots in the FW."*

---

## 1. THE FINDING THAT SHAPES THIS PROPOSAL

**The taxonomy is already right and already complete. What is missing is instruments, and one
subject.** TESTING.md's ten categories were derived from the goal sentence, not from observed
failures, and the four stages the operator asked for map onto them with nothing left over:

| the stage asked for | category (existing) | subject | where the oracle comes from |
|---|---|---|---|
| LLM → Intent | **RECOGNITION** | the question | enumeration generated · gold slots **authored** |
| the Intent itself | **FORM** + **COMPLETENESS** | *nothing today — §2* | the grammar · the corpus |
| Intent → SQL | **COMPOSITION** | the plan | enumeration generated · invariant **authored** |
| E2E with the DB | **TRUTH** + **HUMILITY** | the answer | **authored only** · the scope declaration |

So this proposal coins **no new category**. TESTING.md §3 is explicit — *"EXTEND THE EXISTING
VOCABULARY. DO NOT COIN A PARALLEL ONE"* — and records that the mistake was made four times in one
day. The two category questions that are genuinely open (EXECUTION as an eleventh; RECOGNITION and
HUMILITY as one or two) are held by TESTING.md §8 and are not reopened here.

### And the E2E leg was specified twice already

Before proposing anything, the estate's own test applies: *is this declared and unread?* It is.

* **`mac-platform/docs/06-SPEC-eval-harness.md`** — version 1.0, dated **2026-07-07**, status
  WORKING. It specifies the suite format, `clarify`/`refuse` fixtures as mandatory, ground truth
  *"established independently of the ontology"*, `--interpret cached` versus `live`, baseline
  gating, and — the operator's exact request — **per-failure stage attribution**: *"for each failure,
  whether interpret, resolve, plan, or execute diverged from the recorded passing run (this is what
  makes regressions bisectable)."*
* **`mac-platform/packages/mac-eval`** — the component 06 names. Its README today: *"Empty-but-typed skeleton
  (WP-0.1). The runner, report format, and baseline gating land in WP-1.7."*
* **No bundle has an `eval/` directory.** 06's suite format was never adopted anywhere.
* What grew instead is `acceptance/` — `questions.yaml`, `oracle/`, `anchors/`, `answers/`,
  `sdk/acceptance/flags.py`, `questions_dashboard.json`. Built, evolving, working, and **specified
  nowhere**.

**Two homes for one fact, and each is missing what the other has.** 06 has stage attribution and no
implementation; `acceptance/` has an implementation, a projector and a console, and no stage
attribution at all. Reconciling them is §9's first open item and it is not an agent's call.

**Measured consequence, today:** the worked bundle records **20 refusals of 70 run**. A refused
capture carries `answer`, `route`, `sql`, `sql_valid`, `sql_errors`, `error`, two fingerprints — and
**no stage**. So of those 20, nothing says how many are the interpreter failing to build an intent
and how many are the planner refusing a good one. That distinction is the whole of the operator's
"break it down into steps", and 06 specified it fourteen weeks ago.

---

## 2. THE HOLE: nothing in the estate takes the INTENT as a subject

Every category has a subject today, and the Intent is not one of them. FITNESS points at source
data. FORM, AGREEMENT and COMPLETENESS point at declarations. TRUTH and HUMILITY point at answers.
COMPOSITION points at the machinery. **The pipeline's only intermediate representation — the sole
output of the only non-deterministic step — is graded by nothing.**

That is the structural reason the operator could feel the problem without being able to name it.
It has three consequences, all measured:

1. **Interpretation failures and planner failures are indistinguishable** (§1's 20 refusals).
2. **The kill-test runs in one direction only.** `mac-ontology-contoso/acceptance/tools/intent_killtest.py` and `trace_question.py` (beside it) replay
   a **hand-written** intent through the real planner, which isolates the planner beautifully — the
   STORE family's findings this week are entirely its work. Nothing runs the other direction:
   *LLM-produced intent versus the hand-written one*. `acceptance/intents.yaml` holds recorded
   intents and the platform holds 9 recorded question fixtures; neither is scored.
3. **`Intent.confidence` is consumed but never validated.** `mac-platform/packages/mac-runtime/src/mac_runtime/ask.py` and `pipeline.py` (beside it) compare it to
   `DEFAULT_LOW_CONFIDENCE_THRESHOLD` to decide whether to turn an answer into a clarification. No
   test anywhere relates that self-score to whether the intent was actually right. A threshold on an
   uncalibrated number is a coin-flip with a parameter.

**Everything in §3 rests on closing this, and the first instrument is the cheapest thing in the
document.**

---

## 3. THE FIVE INSTRUMENTS

Each is given as TESTING.md §1 requires — **SUBJECT · CLAIM · ORACLE** — with which of the three is
generated and which must be authored, because that is what decides whether it can be built at all.

### 3.0 The Intent algebra — canonical form and equivalence

> **SUBJECT** an Intent · **CLAIM** two intents mean the same query · **ORACLE** the grammar
> *(generated — this is FORM)*

Nothing else in this document works without it. Two intents are equivalent but not equal when they
differ by filter order, slice order, `operation` present versus inferred, `subject` versus the
`measure` alias, or `period` as `[2024-01-01, 2025-01-01)` versus raw `"2024"`.

Deliverables: `canon(Intent) -> Intent`, `equivalent(a, b) -> bool`, and `diff(a, b) -> per-field`.
Properties worth asserting (property-based; `hypothesis` is **not** currently installed):
`canon` is idempotent, `equivalent` is an equivalence relation, and `canon(a) == canon(b)`
whenever `equivalent(a, b)`.

**The per-field diff is the white-spot detector the operator asked for.** Spider's exact-set-match
scores SELECT / WHERE / GROUP BY / ORDER BY separately rather than as one string; the same
decomposition over `subject · operation · slices · filters · period · ordering · limit ·
denominator` turns "the LLM got it wrong" into a confusion matrix that names the field.

Beyond benchmarking it pays for itself: dedupe, caching, run-to-run diffing, prompt-regression
detection.

### 3.1 RECOGNITION — does the LLM produce the right intent

> **SUBJECT** the question · **CLAIM** the emitted intent means what was asked · **ORACLE** a gold
> intent, **authored**

Three metrics, and the second needs no gold at all:

* **Accuracy** — exact match after `canon`, plus the per-field breakdown of 3.0.
* **Stability under paraphrase** — k paraphrases of one question must yield equivalent intents.
  **Self-consistency: no gold, no database, no anchor.** Runs entirely inside our ecosystem today.
  Method from Spider-Syn / Spider-Realistic (synonym substitution, removing explicit column
  mentions) and Dr.Spider's perturbation taxonomy.
* **Calibration** — reliability of `Intent.confidence` against actual correctness (ECE / reliability
  diagram). Closes §2's third consequence and either justifies the threshold or retires it.

Because the interpreter is stochastic, every run is n-sampled: report pass@1 **and** self-consistency
rate, never a single draw.

### 3.2 COMPLETENESS — can the Intent express the question at all

> **SUBJECT** the corpus · **CLAIM** a gold intent exists · **ORACLE** the grammar *(generated)*

The **encodability rate**: the fraction of questions for which a correct intent can be hand-written
at all. A failure is a **grammar gap** and nothing else — it is independent of the LLM, the planner,
the data and the bundle.

We have already run this once, at n=70: `QUERY_GRAMMAR.md` §4 records *"every one of the seventy
ENCODED"* with one exception (`HAVING`). That is the right metric and the wrong denominator — it is
a statement about Contoso. The same count over an external corpus is the first real evidence the
grammar generalises. Precedent: NatSQL and SemQL both report IR **coverage** over Spider's gold SQL
for exactly this reason.

Today `grammar/query_grammar.yaml#not_expressible` holds four entries — `having`,
`correlated_subquery_filter`, and the two found this week, `null_test` and `negation_over_nullable`.

### 3.3 COMPOSITION — does the planner compute what the meaning says

> **SUBJECT** the plan · **CLAIM** a metamorphic invariant holds · **ORACLE** the invariant,
> **authored once for the framework**

**This is the largest and most under-exploited win in the document.** TESTING.md's horizon records
**10 of 433 rules carrying a machine-checkable invariant**, and treats that as a per-rule authoring
problem. Metamorphic invariants are different: they are authored **once, for the planner**, and then
apply to every question in every bundle forever. They need **no gold answer and no anchor.**

Relations that must hold, each checkable by running two plans and comparing:

| invariant | what a violation means |
|---|---|
| adding a filter never increases a count | predicate placement is wrong |
| a total equals the sum over a **total** partition | the grouping drops or duplicates rows |
| `limit=k` is a prefix of `limit=k+1` under one ordering | ordering is unstable |
| reordering filters changes nothing | binding leaks position |
| a collapse never increases row count, and is idempotent | **the collapse is a no-op or fans out** |
| **TLP**: `p` ∪ `NOT p` ∪ `p IS NULL` equals the unpartitioned query | **three-valued logic drops rows** |

The last two are not hypothetical.

> **CORRECTED 2026-09-24, on building it.** This section first claimed TLP — Ternary Logic
> Partitioning, from the DBMS-testing line (Rigger & Su, with PQS and NoREC) — was "precisely,
> mechanically, the detector" for the `Status <> 'Closed'` defect. **Applied as published, it is
> not.** TLP partitions a query by `p / NOT p / p IS NULL` and checks the union equals the
> unpartitioned query. Run against the planner's emitted SQL, that check **passes** on our defect:
> 7 + 8 + 59 = 74. SQL is being perfectly consistent with itself. The bug is not an inconsistent
> DBMS — TLP's actual subject — it is a **translation**: the Intent's `ne` does not mean SQL's
> `<>`.
>
> The ternary *idea* survives, re-aimed one level up at the Intent's operator semantics:
> **`|Q(T eq v)| + |Q(T ne v)| == |Q()|`** — `eq` and `ne` must partition the population, because
> that is what a person means by "not". That form does go red: 8 + 6 = 14 against 67. Built as
> `invariants/planner_invariants.py#inv_complement`.
>
> The correction is recorded rather than edited away because it is the general hazard in §7: an
> academic technique adopted by name, aimed at a subject one level away from ours, looks right
> until it is run.

The collapse invariant is the detector for the second defect of the same day: `PARTITION BY
StoreKey` leaving **74 of 74 rows**, a collapse that collapses nothing — which `store.yaml` had
predicted in prose and nothing could read.

Supporting technique for the fragment our planner actually emits (SELECT · aggregate · inner JOIN on
keys · conjunctive WHERE · GROUP BY · ORDER BY · LIMIT · one ROW_NUMBER window · `NULLIF`):
**differential execution on synthesised instances** — generate small adversarial tables (NULLs,
duplicate keys, empty groups, single-row groups, multi-version rows), run both sides, compare.

### 3.4 TRUTH and HUMILITY — the number, and the decline

> **TRUTH: SUBJECT** the answer · **CLAIM** the number is right about the world · **ORACLE**
> **authored only — generation forbidden**
> **HUMILITY: SUBJECT** the refusal · **CLAIM** it declined when it must · **ORACLE** the scope
> declaration

Largely built. The 17 anchors derive a value from the data by two independent routes, neither of them
the engine, and grade the `value` flag. What is missing is not an instrument but the two things 06
specified and nobody built:

* **stage attribution** on every non-pass outcome — interpret · resolve · plan · execute;
* **abstention scoring**, so a correct refusal counts as a pass rather than a loss. Today 20
  refusals are 20 non-answers with no verdict on whether declining was right. TrustSQL's framing —
  abstention required on unanswerable questions, wrong answers penalised harder than declines — is
  the published version of what HUMILITY already claims.

---

## 4. THE THREE LEGS — one vocabulary, three subjects

The operator's split is a **subject** split, not a vocabulary split. The ten categories, the metric
definitions and the runners are shared; what changes is what the instrument is pointed at.

| leg | subject | answers | corpus |
|---|---|---|---|
| **A — conformance** | the grammar and the planner | does the FRAMEWORK handle each pattern? | synthetic reference bundles |
| **B — acceptance** | one ontology | is THIS bundle right, and does the engine answer ITS questions? | the bundle's own corpus |
| **C — benchmark** | the whole pipeline, comparably | how do we compare to published work, and does the grammar generalise? | third-party (BIRD, Spider) |

**Leg A** needs bundle-independent subjects: small ontologies isolating exactly one pattern each — a
nullable dimension · an SCD-2 relation · a degenerate dimension · a many-to-many · a non-additive
measure · a multi-hop join · a question with an empty result. Each is a dozen lines and a handful of
rows. **This is also the way past n = 1**: the `entity_key` / `versioned_by` redesign is deferred
pending more than one sample, and building a minimal synthetic SCD-2 bundle is an afternoon where
finding a second real one is a quarter.

**Leg B** is what `acceptance/` already is.

**Leg C** is §5, and it is the operator's explicit requirement: *"at least one (best fit) framework
for testing of text-2-sql … a large corpus of third party questions … benchmark what we do with
that what other do … and use this as a standard for our acceptance where it makes sense."*

**Shared across all three:** the Intent algebra (3.0), the metric definitions (§5.5), the runners
(paraphrase · metamorphic · differential), the synthesised-instance generator, the denotation
comparator, and the report schema. One board reads all three.

---

## 5. LEG C — the external benchmark, and how to be honest about it

### 5.1 The corpus: BIRD primary, Spider for breadth

| | scale | why it is here |
|---|---|---|
| **BIRD** | ~12.7k question–SQL pairs · 95 databases · 37 domains · ships SQLite | **primary.** Dirty values, a public leaderboard with **EX** and **VES**, and — decisive for us — a hand-written **external-knowledge `evidence` string per question**, which is a per-question semantic layer and therefore the thing our ontology claims to replace |
| **Spider 1.0** | ~10.2k questions · 200 databases · ships SQLite | **breadth.** Largely saturated, so it is a *floor and a regression corpus*, not a headline. Its value is **200 databases = 200 independent chances to catch a bundle-specific assumption** |
| **Spider 2.0(-lite)** | ~600 enterprise tasks | stretch. Closest to real warehouses; hardest to run |
| **TrustSQL** | abstention-scored | the only corpus that rewards declining — the published form of **HUMILITY** |

*(Figures are from published descriptions and must be re-verified against the release actually
downloaded; a benchmark quoted from memory is the zero-denominator mistake this estate keeps
finding.)*

### 5.2 THE COMPARABILITY PROBLEM — and it is the whole design

**MAC is not entered in the same event.** A text-to-SQL baseline gets *(question, schema)* and must
emit SQL. MAC gets *(question, a curated ontology)*. That is strictly more input, so a bare *"we
beat X on BIRD"* would be dishonest and any reviewer would say so first.

Four controls make the comparison mean something. **None is optional.**

**(1) Bundle-depth tiers — the fair comparison is L0.**

| tier | how the bundle is produced | human effort | runs on |
|---|---|---|---|
| **L0 — schema** | **generated**: tables → concepts, FKs → edges, column types → field_roles, PKs → `identity: canonical` on the column | none | all 95 DBs |
| **L1 — profiled** | L0 + **generated** from a data profile: cardinality, null rates, candidate keys, value registers auto-cut from low-cardinality columns | none | all 95 DBs |
| **L2 — authored** | L1 + a human adds rules, default readings, refusal scope, disclosures | hours per DB | a handful |

**L0 receives no more human input than the baselines do**, so L0-versus-published is an apples-to-apples
number. L1 and L2 then measure what declaration *buys* — and the curve of **accuracy against
declaration depth is this estate's entire thesis rendered as a graph**. It is also the only version
of the claim that survives an adversarial reading.

The tiering follows TESTING.md's own rule, applied to bundles rather than tests: **derive the
enumeration, author the meaning.** L0 and L1 are enumeration.

**(2) A same-model control, and without it every number is uninterpretable.** Run the *same* LLM
through a standard text-to-SQL baseline prompt on the same databases, and through MAC. Same model,
same questions, different scaffolding. Otherwise an improvement is confounded with model choice and
the result says nothing about the architecture.

**(3) The evidence ablation — the sharpest experiment available to us.**

```
baseline  +  BIRD evidence          (published)
baseline  −  BIRD evidence          (published ablations, or re-run)
MAC (L2)  −  BIRD evidence          ← ours
```

If MAC-without-evidence reaches baseline-with-evidence, the ontology has **subsumed** the
per-question hints: declared once instead of hand-written ~1.5k times, and reusable by every future
question on that database. That is a fair claim with a number behind it, and it is the closest
published analogue to what a semantic layer is for.

**(4) Held-out discipline, and per-database reporting.** Bundles are authored against a train split
and reported on a held-out split. Results are reported **per database**, never only as an average —
an aggregate hides exactly the variance that would show a bundle-specific assumption.

### 5.3 THE GOLD-SQL → GOLD-INTENT TRANSPILER — how the corpus gets large

Hand-writing gold intents for thousands of questions is impossible, and it is also unnecessary.
`sqlglot` (30.18.0, already a dependency) decomposes gold SQL into precisely the components an
Intent carries — verified 2026-09-24 on a Spider-shaped query:

```
aggregates  COUNT(*)            ->  operation + subject
GROUP BY    T1.name             ->  slices
WHERE       T1.age > 30         ->  filters
JOIN ... ON T1.id = T2.sid      ->  the join path the edges must support
ORDER BY    COUNT(*) DESC       ->  ordering
LIMIT       3                   ->  limit
```

So the transpiler runs over the whole corpus and every question lands in one of two buckets:

* **transpiles** → a candidate gold intent, free, at scale → feeds RECOGNITION scoring (3.1);
* **does not transpile** → **an encodability gap, detected automatically** → feeds COMPLETENESS
  (3.2) and names the missing grammar feature.

**This converts encodability from a hand-authored metric into a generated one**, which is the only
reason a large corpus is affordable at all. It is the single highest-leverage component in Leg C.

**Two honest limits, stated because they bound every claim built on it.** A gold-SQL-derived intent
**inherits gold SQL's interpretation**, so it measures *expressiveness*, never *whether the reading
was right* — it cannot adjudicate an `SST-Q3`-class ambiguity, where two faithful readings give 58
and 59. And the transpiler itself needs an INSTRUMENT test: seeded mutants, or it becomes a
generated oracle agreeing with its own source, which is TESTING.md's mirror.

### 5.4 The denotation comparator

**EX compares result sets, not SQL text** — which is what makes Leg C possible at all, because our
SQL runs over a *served* plane and gold runs over the raw schema. Two queries over different
relations can still denote the same answer.

The comparator must align columns **by meaning, not by name** — our aliases are generated
(`net_sales_amount`), gold's are the source's. It needs explicit, declared rulings on row order,
column order, duplicate rows, and NULL-versus-empty, because every text-to-SQL evaluator makes those
choices differently and a silent choice here quietly moves the headline number. The estate already
holds this concept: the `oracle-check` agent judges *"by MEANING, not by matching column-name
strings."*

### 5.5 WHAT WE ADOPT AS STANDARD — the operator's acceptance requirement

Adopted as **shared metric definitions**, used by all three legs so one number is comparable across
them and to published work:

| adopted | from | used in |
|---|---|---|
| **EX — execution accuracy**, denotation match | Spider / BIRD | A · B · C |
| **VES — valid efficiency score** | BIRD | C, advisory in B |
| **abstention scoring** — a correct refusal is a pass | TrustSQL | HUMILITY, all legs |
| held-out split · per-database reporting · same-model control | standard practice | C, and B when a bundle changes |

**Our flags are not replaced.** `outcome · pins · value · rules` are strictly richer than a single
pass/fail — EX cannot distinguish a right number from a right number reached by a forbidden route,
and `pins` can. So **EX becomes one derived number emitted alongside them**, which is what puts our
acceptance on a public axis without discarding what it knows that the public axis does not.

Where it does **not** make sense, and this is a deliberate limit: EX cannot grade a refusal, a
clarification, or a disclosure. Those stay on HUMILITY and on the flags. A bundle reporting only EX
would score its 20 correct refusals as 20 losses.

### 5.6 What we will be able to claim, and what we will not

**Can:** *"At L0 — a generated bundle, no human input — MAC scores X on BIRD dev against the same
model's Y through a standard prompt."* · *"L2 authoring of N hours moves that database from X to
Z."* · *"MAC without per-question evidence reaches W, where the baseline with evidence reaches V."* ·
*"Of K questions, J were not expressible as an Intent, and here are the features they needed."*

**Cannot:** any leaderboard claim, since we are not submitting to a held-out test server and our
input differs · any claim from an aggregate that hides per-database variance · any claim about
*meaning* from a gold-SQL-derived intent (§5.3).

---

## 6. WOULD IT HAVE GONE RED? — validated against defects already found

A gate that cannot go red is the zero-denominator pass wearing a green tick. The proposal is checked
the way `check_query_grammar.py --self-test` checks itself: against real, dated defects.

| defect (all 2026-09-24 unless noted) | caught by | without |
|---|---|---|
| `Status <> 'Closed'` → 6, answer 59 | **3.3 TLP** | any oracle, anchor or bundle knowledge |
| collapse `PARTITION BY StoreKey`, 74 of 74 rows | **3.3 collapse invariant**; **Leg A** SCD-2 bundle | Contoso existing at all |
| RC05 74 → 67, masked by `counts_as` | 3.4 anchors *(already caught, 2026-09-23)* | — |
| STORE-01 refuses: `CloseDate IS NULL` unreachable | **3.2 encodability** | the LLM or the DB |
| ADV-09 pinned `StoreKey=500` from "exceeds 500" | INSTRUMENT mutant on the oracle producer | — |
| ANCHOR_14 `agree:false` on date-vs-datetime | FORM on the anchor artifact | — |
| 70 captures stale after a corpus edit | CURRENCY *(already caught — the category works)* | — |
| interpreter prompt carried 23 bundle-specific examples | **Leg A** — a synthetic bundle fails outright | — |

**What it would NOT have caught, stated plainly.** The `main.orders` error (*"there is no order
table"* — false) and the order/line grain confusion were caught by the **operator**, from domain
knowledge, and no instrument here substitutes for that. The atomicity table that measured its own
JOIN is TESTING.md's vacuity rule — already named, already counted at 59 vacuous assertions over 29
properties, and not improved by anything proposed here.

---

## 7. THE ACADEMIC IMPORTS — what each is for, and the one we refuse

| import | used for | note |
|---|---|---|
| Spider — component-wise exact-set-match | per-field intent scoring (3.0) | the decomposition **and**, in Leg C, the breadth corpus |
| Spider-Syn · Spider-Realistic · Dr.Spider | paraphrase stability (3.1) | method applies to **our** corpus; their data optional |
| NatSQL · SemQL coverage | encodability (3.2) | IR coverage is the published form of this metric |
| TLP · NoREC · PQS (DBMS testing) | metamorphic invariants (3.3) | TLP is the NULL detector, exactly |
| TrustSQL | abstention scoring (3.4) | the only benchmark that rewards declining |
| BIRD | **Leg C primary corpus — §5** | ships databases, carries per-question `evidence`, has a public EX/VES leaderboard |
| Cosette · SPES · VeriEQL | **NOT adopted** | see below |

**Why no SQL-equivalence prover.** Not primarily decidability — though general SQL equivalence is
undecidable, conjunctive-query equivalence is NP-complete (Chandra–Merlin 1977), and under bag
semantics, which is SQL's, it collapses to isomorphism. The real reason is that **benchmark gold SQL
is the wrong target**: gold queries are written against the raw schema and ours against a *served*
plane with declared transforms, conformed nulls and collapses. Those genuinely are different queries
over different relations that should nevertheless produce the same answer. Equivalence at the query
level is not just hard here, it is the wrong question. Equivalence at the **answer** level, on
synthesised instances, is the right one — and it is the only method that would have caught the NULL
bug.

**The BIRD evidence ablation is not restated here** — it is §5.2 control (3), where it belongs
alongside the other three controls that make it mean something. A sharp experiment quoted twice is
two homes for one fact.

---

## 8. THE ITINERARY

### 8.1 THE INTENTION — four claims, and what would kill each

Not "build a test framework". The intention is to be able to **say, with a number and a denominator,
which part of the pipeline owns any given failure — on an axis other people publish on.**

That decomposes into four claims. Each is written so it can be **refuted**, per the estate's own
research loop: *state it, design the test that kills it, run that first.*

| | claim | instrument | **what kills it** |
|---|---|---|---|
| **C1 EXPRESSIVENESS** | the Intent can express the questions people actually ask | encodability (3.2) over BIRD + Spider, via the transpiler (5.3) | a large fraction of an external corpus that no Intent can encode |
| **C2 STABILITY** | the same question, asked differently, reaches the same Intent | paraphrase invariance (3.1) | paraphrases of one question producing materially different intents |
| **C3 SOUNDNESS** | a correct Intent yields a correct answer | metamorphic invariants (3.3) + anchors (3.4) | an invariant violated, or an anchor disagreeing with the engine |
| **C4 THE PRODUCT CLAIM** | declaring meaning **once** beats supplying it **per question** | the evidence ablation (5.2 control 3) | MAC at L2 without evidence failing to reach the baseline with it |

**C1–C3 are about the framework and we control them. C4 is the business.** C4 is also the only one
that can be lost outright, and losing it is the most valuable single result available to this
project — it would say the semantic layer is not paying for itself *on this workload*, which no
amount of internal green can tell us.

**Today all four are unfalsifiable**, because every instrument that could kill one is missing or
pointed at a corpus of 77 questions from one bundle.

### 8.2 THE ROUTE

Ordered by **information per unit of effort**, not by dependency alone. Each stage ends in a number
that changes what the next stage should be.

| # | stage | build | the number out | size | needs |
|---|---|---|---|---|---|
| **0** | Provisioning | download BIRD dev + Spider; pin versions; record checksums | corpus sizes, with denominators | S | network |
| **1** | *The Intent becomes a subject* | `canon` · `equivalent` · `diff` (3.0) | — (foundation) | S | nothing |
| **2** | *Stability, free* | paraphrase harness (3.1) over our 77 | **C2's first number** | S | 1, a model |
| **3** | *The outside world* | gold-SQL → gold-intent transpiler (5.3) + its mutants | transpile rate | M | 0, 1 |
| **4** | **The headline** | encodability (3.2) over BIRD dev + Spider | **C1's number, and the ranked gap list** | S | 3 |
| **5** | *The planner under law* | metamorphic invariants (3.3): TLP + collapse pair first | **C3's number**; 2 known-reds must go red | M | a local DB |
| **6** | *Splitting the refusals* | stage attribution (3.4) per 06 §3 | 20 refusals → interpret/resolve/plan/execute | M | §9 ruling 1 |
| **7** | *The floor* | L0/L1 bundle generator + denotation comparator (5.2, 5.4) | **EX at zero human input, all 95 DBs** | L | 1, 5 |
| **8** | *Past n = 1* | Leg A synthetic reference bundles | conformance per pattern | M | 5 |
| **9** | *The thesis* | L2 bundle + same-model control + evidence ablation | **C4's number** | L | 7, 8, live model |

**Stages 0–4 need no warehouse credentials, no Bedrock session and no ontology authoring.** Stage 2
needs a model but no gold and no database. **Stage 4 is where the operator's requirement is actually
satisfied** and it arrives early on purpose.

### 8.3 PRE-REGISTERED DECISION RULES

**Agreed before the numbers are seen**, because a threshold chosen afterwards is a rationalisation.
These are proposals; the operator sets the cut points.

**After stage 4 — encodability on BIRD dev:**

| result | reading | what we do next |
|---|---|---|
| **≥ 90 %** | the grammar is not the bottleneck | skip to stages 6–7; effort moves to interpretation and the L0 floor |
| **70–90 %** | the gap list *is* the roadmap | close the top three missing features, re-run stage 4, then continue |
| **< 70 %** | the Intent model is under-specified for real workloads | **stop Leg C.** No benchmark claim is meaningful until the grammar is redesigned |

**After stage 2 — paraphrase agreement on our 77:**

| result | reading | what we do next |
|---|---|---|
| **≥ 95 %** | stability is not the dominant error source | proceed; revisit only on regression |
| **80–95 %** | the per-field diff names the weak field | fix that field's prompting or its declarations first |
| **< 80 %** | interpretation dominates | deprioritise planner work until it is fixed — a sound planner behind an unstable interpreter is invisible |

**After stage 5 — the two known-reds:** if TLP does **not** go red on `Status <> 'Closed'`, or the
collapse invariant does **not** go red on `PARTITION BY StoreKey`, **the instrument is broken, not
the planner.** Fix the instrument before trusting a single green from it. This is the INSTRUMENT
category applied to ourselves.

**After stage 9 — C4:** state the result in both directions before running it. If MAC-without-evidence
reaches baseline-with-evidence, the ontology subsumes per-question hints. If it does not, we report
that, and the next question is whether the gap is the ontology's depth (fix: L2 authoring) or the
architecture's (fix: unknown, and worth knowing).

### 8.4 RULINGS, AND THE STAGE EACH ONE BLOCKS

Nothing before stage 6 is blocked. Stated so no stage stalls waiting on a decision nobody knew was
needed.

| ruling (§9) | blocks | when it is needed |
|---|---|---|
| `acceptance/` or `eval/` is the home | **stage 6** | before stage attribution is written anywhere |
| may a generated **L0** bundle carry oracles | **stage 7** | before the floor number is quoted as anything |
| is a `derived` anchor a legal TRUTH authority | interpretation of **5, 7, 9** | does not block building; blocks *claiming* |
| what may be said publicly from Leg C | **publication only** | before any number leaves the estate |
| `SST-Q3`, EXECUTION category, RECOGNITION vs HUMILITY | nothing here | as convenient |

### 8.5 WHAT ARRIVED LOOKS LIKE

The fixed point, in the shape TESTING.md §7 uses.

| | today | arrived |
|---|---|---|
| refusals carrying the stage that produced them | **0 of 20** | every one |
| corpora the grammar has been measured against | **4** — 77 local + BIRD dev + Spider dev + Spider train (9 568 questions, 171 DBs, 2026-09-24) | per-database, and held out |
| questions with a gold Intent | **0 scored** | every transpilable question, generated |
| planner invariants that hold framework-wide | **3** (complement · collapse_reduces · filter_monotone, 2026-09-24) | + the rest of 3.3 |
| bundles the framework is proven on | **1** | 1 real + the Leg A patterns + L0 on 95 |
| `Intent.confidence` | consumed, never validated | calibrated, or removed |
| the four claims of 8.1 | **C1 = 74.0 %, C3 has an instrument with 2 known-reds; C2 and C4 still unfalsifiable** | each carrying a number and the test that could kill it |

---

## 9. WHAT THIS REFUSES TO DECIDE — the operator's

* **`acceptance/` or `eval/`.** 06-SPEC designed a suite format nobody adopted; `acceptance/` is a
  working implementation nobody specified. One must become the other's home. Picking is a ruling
  about two existing artifacts, not a design choice an agent may make.
* **Whether a `derived` anchor is a legal TRUTH authority.** TESTING.md's horizon reads *"oracles
  with an independent, human-ruled authority: 0 of 398"*. Our 17 anchors are `authority: derived` —
  two data routes, no human. Stricter than it looks: tightening retires them.
* **EXECUTION as an eleventh category**, and **RECOGNITION versus HUMILITY as one or two.** Both are
  already held by TESTING.md §8 and are only re-pointed at here, because RECOGNITION is now a leg
  with an instrument behind it.
* **`SST-Q3`** — what a question phrased as a negation should return when 58 and 59 are both
  faithful. Any stability metric scores it, and none of them can rule it.
* **What we are allowed to claim publicly from Leg C**, and how the ontology's extra input is
  disclosed whenever a number leaves this estate. §5.6 proposes the honest boundary and §5.2 the
  four controls that support it; **whether we publish, and in what venue, is not an agent's call**.
  A benchmark number is the easiest thing in this document to quote without its denominator, and
  this estate's own history says that is exactly what happens.
* **Whether a generated L0 bundle may carry `authority: derived` oracles at all.** It is a bundle
  nobody authored, grading questions nobody vetted. Useful as a *floor measurement*; a category
  error if it were ever read as acceptance.

---

## 10. HOW THIS PROPOSAL IS ITSELF CHECKED

Per TESTING.md, a claim is worth what its check is worth:

* §5 is the self-test: six dated defects, each with the instrument that goes red on it, and three
  named that nothing here would catch.
* Each instrument in §3 carries its SUBJECT · CLAIM · ORACLE, so a reader can apply the
  three-question test without trusting this document's own classification.
* Every number carries its denominator: 20 of 70 refused · 17 anchors · 4 `not_expressible` · 10 of
  433 rules with an invariant · 11 of 51 gates that prove they can reject · 0 of 398 oracles with a
  human-ruled authority · **0 of 20 refusals carrying a stage**.

**The last one is the smallest number in the document and the one to move first.**
