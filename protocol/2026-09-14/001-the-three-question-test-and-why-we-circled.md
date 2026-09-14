---
when: 2026-09-14T10:30:00
what: recorded the operator's three-question test as the governing rule for what a test is, and the four process defects that made two days circle
topics: [method, denominators, gates, harness]
kind: build
track: core
repo: meaning-as-code
commits: []
---

## WHAT FORCED IT

The operator, after two days: *"i am under impression to be standing exactly where we were standing
when we started this discussion"* and *"i also think that some of what we just discuss must be
protocolled and general findings and rules, or otherwise we will be again turning in circles."*

Both correct. This entry exists so the next agent — or this one after compaction — does not re-derive
what took two days, and does not repeat the four process defects that caused the circling.

## THE RULE, AND IT IS THE OPERATOR'S

> *"the major problem with the question for a unit test: (1) you have to understand functionality that
> is implemented (2) you have to know how to write proper question — or what do you want to assert
> (3) you need to know what is the correct outcome/answer. So all what you are proposing must be
> subject to these categories."*

Those three are **SUBJECT · CLAIM · ORACLE**. Written into `TESTING.md` §1 as the governing test,
because it decides generatability MECHANICALLY rather than by argument:

> **A TEST IS GENERATABLE EXACTLY WHEN ALL THREE ARE ALREADY DECLARED MACHINE-READABLY. Where one is
> only in prose or only in a person's head, THAT part must be authored — and WHICH of the three is
> missing tells you exactly what the bundle must declare.**

It immediately explains two numbers nobody could previously account for:

- **Rule coverage ceilings at 8 of 31 because (1) FAILS** — 23 of 31 rules state their directive in
  prose `then:` clauses, so nothing can read what the rule means. No tooling fix reaches that; it is a
  declaration-shape problem.
- **TRUTH is empty because all three are human** — 0 of 101 oracles carry a value, and the one
  independent channel that exists (6 named reviewers, 68 human answers) is parsed by no code.

And the vacuity rule falls out of it: **a test with (1) and (2) but a hollow (3) passes and proves
nothing** — the estate's 59 vacuous assertions over 29 properties. A `conformance` test, whose oracle
IS the declaration, is honest only where the two declarations are genuinely maintained by different
people for different reasons. Where they are not, it is a mirror wearing a verdict.

## THE FRAME, ALSO THE OPERATOR'S, AND BETTER THAN THE ONE IT REPLACED

Not ten abstract categories. **Three kinds of thing**, on the axis the estate already uses:

    SUITES   subject x {GENERATED, AUTHORED} — the existing list, EXTENDED. The naming pattern is
             already in the console: "<subject>, GENERATED — projected from <plane>, never authored"
             beside "<subject> — <the question it answers>".
    GATES    what protects the REPOSITORY, not the ontology. Straightened: one declared subject
             population, a printed denominator, named reject classes, a seeded mutant per class.
    CORPUS   authored questions. The FRAME generates; the question and the expected value never do.

A consequence worth keeping: **several current gates are suites in the wrong clothes.**
`check_concept_columns_exist` asks a per-concept question about a declaration plane and reports one
pass/fail over a population nobody sees. Moved into a suite, coverage becomes visible per instance
and the gate count drops. That is what "straighten the gates" means concretely.

## THE FOUR PROCESS DEFECTS THAT CAUSED THE CIRCLING

Recorded as rules, because each cost hours and each recurred.

1. **WRONG ALTITUDE.** Asked for a high-level picture, I produced instruments and commits. The
   operator's own diagnosis was sharper than mine: *"you were flying on another altitude which turn
   out to be too low."* The work was correct at the altitude flown, and useless at the one required.
   RULE: when asked to generalise, converge and stop; do not enumerate and do not build.

2. **REPORTING BEFORE VERIFYING — about ten times in one day.** Every headline number moved on the
   next check: 24 divergences were 17; DECLINE 14 was 1 049; "zero run records in history" was true
   only of the repos searched; 8 bundles were 11; "the score averages four units" was six dimensions
   each with a denominator; "this estate draws no history" while one tab had drawn 61 runs for weeks.
   RULE: a figure is UNVERIFIED until two differently-shaped commands agree. Say `UNVERIFIED`.

3. **COINING BESIDE AN EXISTING NAME — eleven times in two days, twice against my own document.**
   `SourceErrorReason` beside `AdapterErrorReason`; `mac.test_type` beside `mac.test_kind`; eight
   "new" presentation invariants already shipped in two console views; a `DESIGN.md` written beside
   the 396-line `ontology/planes/testing.md` it duplicated; and "GROUP A — DATA FIT" beside
   `TESTING.md`'s own FITNESS, same claim, same provenance, same routing rule.
   RULE: PROVE ABSENCE BEFORE YOU NAME. It is already Part IV of the design document and it was
   violated by the document that carries it.

4. **TRUNCATING A CRITIC'S INPUT — twice, in consecutive workflows.** Both reconciliation passes were
   handed a sliced JSON blob and both received only the FIRST of the groups they were asked to
   cross-check. Each found real defects anyway, and neither did the job it was for.
   RULE: a critic that cannot see all its inputs is not a critic. Pass a digest, or pass a file path.

## A GATE DEFECT FOUND WHILE WRITING THIS

`check_mac_public`'s population is `git ls-files` — **TRACKED files only** — so a NEW, UNTRACKED file
is invisible to it. Running it BEFORE `git add` proves nothing about what is about to be committed.
That is how two instance tokens reached HEAD of a PUBLIC repo this morning behind a green line:

    PASS: check_mac_public — 0 leak(s) over 621 tracked file(s) examined     (the new file was untracked)
    FAIL: check_mac_public — 2 leak(s) over 625 tracked file(s) examined     (after it was committed)

Scrubbed. The general form: **a gate whose population is the index cannot see the working tree, and
the moment you care about is the one between them.** Either it examines staged files too, or the
order is add-then-check and never the reverse.

## WHAT THIS DOES NOT SETTLE

The candidate suite list (grounding · registers · joins · freshness · vocabulary · boundaries) is
proposed and unratified. Which current gates are suites in the wrong clothes is proposed and
unratified. And the three-question test says WHICH part must be authored — it does not author it: the
estate still has 0 oracles carrying a human-ruled value, and no rule declares its directive in a form
a generator can read.
