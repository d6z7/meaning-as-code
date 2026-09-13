# TESTING.md — what testing MEANS in MAC, and what a green is allowed to mean

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

## 1 · THE ONE LAW

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

And the worked proof runs the other way too: `S-GRAIN-KPI`, an **authored** property, caught a
descriptor claiming `VERIFIED … 0 multi-row` against a warehouse that had reached 11.689.530. The
plane records that *"a conformance test rendered from that same declaration would have confirmed the
stale claim."*

### The rule an agent can apply

> **DERIVE THE ENUMERATION. AUTHOR THE ORACLE.**
> Generating *which* concepts, rules and questions need a test is legitimate and should be
> exhaustive. Generating *what the answer should be on the axis under test* is forbidden, because
> there the test inherits the claim it exists to challenge.

---

## 2 · THE CATEGORIES

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
§4 states what that fixes.

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

## 3 · PROVENANCE, AND THE COMBINATIONS THAT ARE FORBIDDEN

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

## 4 · QUALITY AND TESTING ARE ONE OVERVIEW

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

## 5 · THE SIX LAWS OF REPORTING

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

## 6 · NAMING HAZARDS — recorded so the next reader is not caught

- **"quality" means two things here.** `QUALITY.md` is the framework's pre-offer *change checklist*.
  The console's Quality section is *ontology and data* quality. Same word, unrelated subjects.
- **"eval" and "acceptance" are two corpus formats for one idea.** `acceptance/` (questions, oracles,
  anchors) is the ontology track's; `eval/suite.yaml` is specified for the platform's `mac-eval`. They
  both mean "a question with a verified answer". See the platform spec for the state of the second.
- **"conformance" is a `test_kind` AND a compile level.** `mac.test_kind.conformance` means "renders
  its assertion from the declaration"; `CONFORMANCE.md` means "passes the three compile gates".

---

## 7 · THE HORIZON — what arrival looks like, in numbers

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

## 8 · WHAT THIS DOCUMENT REFUSES TO DECIDE

An agent may write `PROPOSED`; these are the operator's.

- whether **EXECUTION** becomes an eleventh category or engine failure is declared out of scope (§2)
- whether **RECOGNITION and HUMILITY** are one category or two — held apart on judgement, not
  measurement: a system that always answers is worse than one that declines, and that guarantee may
  deserve its own row
- whether a **frozen engine capture** is a legal TRUTH authority at all — currently legal but never
  green, which is stricter than it looks and retires existing captures if tightened
- whether `severity: blocker` already answers *"does this red block the build"*, in which case that
  question is settled in the ontology grammar and not open
- who the **named SME** is. An agent can propose the shape of the authority channel; it cannot create
  the authority.
