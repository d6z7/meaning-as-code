---
when: 2026-09-13T17:30:00
what: turned the testing lighthouse into a route — five phases ordered by what makes the next thing visible, with additive-first encoded as a blocker rather than remembered
topics: [method, denominators, gates, harness]
kind: build
track: core
repo: meaning-as-code
commits: [36550e8]
---

## WHAT FORCED IT

The operator asked for the concept to be persisted as a fixed point — *"it could be light-tower for
quality testing overall. will not be easy to reach but could serve as a great strategic orientation
on the horizont"* — and then for the route: *"lets protocol the way to the goal and lets go."*

The lighthouse is `TESTING.md`. This entry is about the route, and about the two rules that keep the
route from repeating this session's mistakes.

## EVIDENCE

**The route follows from one measured fact: almost all the machinery exists and is not wired.** The
generators are written (`mac_generate_sanity.py`, `mac_generate_ontology_tests.py`,
`mac_generate_rule_tests.py`). Six suites exist. The per-test views are good and the operator has
accepted them. Four independent authority channels exist. And:

    acceptance/*_runs.json          ZERO instances across ALL of git history
    suite_history.py                asserts "The run records are committed"

**The suites run and nothing keeps the answer.** So this is a wiring programme, not a building
programme — which is why `P1-runs` ("commit run records at all") is nearly free and is what populates
the board on day one.

**The ordering rule is NOT severity.** It is *what makes the next thing visible*, because invisible
work dies here: 47 initiative folders, 3 done, 8 untouched for 70 days. Phase 0 is the one exception —
money and publication are irreversible and do not wait for a concept.

## WHAT CHANGED

`decisions/PLAN.yaml` gained the programme as twelve items in its existing schema, so
`.claude/skills/tactics/plan.py` reads it unchanged — **verified by running it**, and it now reports
8 runnable, 5 blocked, 1 ruling that unblocks work. No second plan file was created; PLAN.yaml is the
one home and adding another would have been this session's fifth re-invention.

**TWO OPERATOR RULES, ENCODED AS STRUCTURE RATHER THAN REMEMBERED:**

> **ADDITIVE FIRST** — *"i would recommend doing NEW pages first ... before retiring old testing and
> quality."* `P5-retire` is therefore `state: blocked, blocked_on: [P1-board]`. It cannot happen early
> because the plan reader will not offer it. A note would have been forgotten; a blocker cannot be.

> **ONE OVERVIEW** — *"quality belongs to the same overview, do not separate it."* Data quality is the
> FITNESS row, ontology quality is the COMPLETENESS row. No second Quality surface exists in the plan.

`PLAN.yaml` was also **stale and the reader caught it**: it offered `retire-the-fork` as runnable
after that work landed this morning. Marked done with its evidence — the directory was already gone
and **four readers still named it**, one of which made `make install`, `make test` and `make check`
all hard-fail.

`R16` was added as the one ruling that gates the programme: *name the gate that exits 2 when this
artifact is absent or stale, in the same paragraph that proposes it, or do not create it.* Recommended
binding, and the measured basis is on both sides — without it, `authority: sme` adopted 0 of 398 and
`question_id` 0 of 21; with the same shape, `accepted:`/`frozen:` reached 26 blocks because a red could
not move without one.

## WHAT IT DOES NOT PROVE

**A plan is not a gate.** `Update when anything lands` is an instruction, and this same file was stale
within a day of being written — which is the argument for R16 applied to the plan itself. Nothing
currently exits 2 when `PLAN.yaml` disagrees with the repository, and until something does, the plan's
own currency rests on someone remembering.

The phase ordering is also a judgement, not a measurement. It is defensible — Phase 1 makes a true
number visible so every later phase can be seen to move — but a different operator could reasonably
put authority (`P2`) first, since the 24 value divergences are the felt failure and are **unjudged
rather than broken**.
