---
when: 2026-09-13T11:01:56
what: put the plan in a file and wrote the four rules that keep capacity working on the goal instead of on the operator, each from something measured today
topics: [method, harness, denominators]
kind: build
track: core
repo: meaning-as-code
commits: [70df2c1]
---

## WHAT FORCED IT

The operator's complaint, verbatim: **"rather then me asking and now and now and now."** The failure
is capacity sitting idle while the human is the only thing moving work forward.

## EVIDENCE

`git show -s 70df2c1` (meaning-as-code). FOUR RULES, EACH FROM SOMETHING MEASURED THAT DAY:

> 1. NEVER IDLE WHILE RUNNABLE WORK EXISTS. I waited on a verifier that blocked nothing, and the
>    operator had to notice for me.
> 2. UNBLOCK BEFORE YOU BUILD. A human ruling blocks hardest because its latency is unbounded — so
>    surface rulings EARLY and in BATCHES. Fourteen presented one at a time is fourteen round-trips.
> 3. BLOCKED ON A RULING IS NOT UNBUILDABLE. Most such work can be BUILT now and only TESTED later.
>    This is where most of the recovered time comes from.
> 4. RESPECT CONTENTION, MEASURED: three workflows plus background bash turned a 13s gate run into
>    663s. **Fifty times.** Two heavy workflows is the practical ceiling. When a run looks stalled,
>    check contention before diagnosing a bug — I reported a 74x "regression" that was my own
>    background jobs, and a "stalled" verifier that had written three seconds earlier.

**ITS FIRST ANSWER IS THE USEFUL KIND: runnable now = 0.** Everything is in flight or waiting on one
of three rulings. That is not a capacity problem and more agents would not touch it — the critical
path is a decision, and saying so is worth more than launching something to look busy.

## WHAT CHANGED

`decisions/PLAN.yaml` holds the goal, the items, their dependencies and their blockers; a reader
answers "what is runnable NOW, what is blocked, on what". **A plan that lives only in a context
window is gone at the next compaction, and the operator is back to asking.**

The plan also carries a backlog of things measured and deliberately not done — among them that a
runtime module exists twice, that the framework's `tests/` cannot be collected by pytest, and that 14
of 34 framework checkers still have no self-test.

## WHAT IT DOES NOT PROVE

Stated in the skill rather than implied away: **it cannot make a session act unprompted.** A watchdog
makes silence visible; a standing self-driven loop is a separate mechanism and only the operator
starts it. The plan is also hand-maintained — `Update when anything lands` is an instruction, not a
gate, which is the exact defect the resource description and the requirements register were both
built to avoid.
