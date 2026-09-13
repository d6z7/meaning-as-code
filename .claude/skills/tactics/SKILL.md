---
name: tactics
description: Keep capacity working toward the strategic goal. Read the plan, launch what is runnable, batch the human decisions, never idle. Use at the start of any turn where work could be in flight, and after any workflow completes.
---

# Tactics — spend capacity, not the operator's patience

The operator's complaint, in their words: *"rather then me asking and now and now and now."* The
failure this skill exists to prevent is **capacity sitting idle while the operator is the only thing
moving the work forward.**

## The plan is a file, not a memory

`decisions/PLAN.yaml` holds the goal, the work items, their dependencies and their blockers. Read it
first, every time. Update it when anything lands. A plan that lives only in a context window is gone
at the next compaction, and the operator is back to asking.

    python3 .claude/skills/tactics/plan.py           # what is runnable NOW, what is blocked, on what
    python3 .claude/skills/tactics/plan.py --brief   # one line per item, for a status answer

## The four rules, in priority order

**1 · NEVER IDLE WHILE RUNNABLE WORK EXISTS.**
Before ending any turn, ask: is capacity free, and is anything runnable? If yes, launch it. The
verifier running does not block work it does not touch — today I waited on one that blocked nothing,
and the operator had to notice for me.

**2 · UNBLOCK BEFORE YOU BUILD.**
Prefer the item that frees the most other items. A human ruling blocks hardest of all, because it
has unbounded latency — so **surface rulings EARLY and in BATCHES.** Fourteen rulings presented one
at a time is fourteen round-trips; the three that actually gate work, presented together with a
recommendation each, is one. Never stop at a ruling you could have asked about an hour earlier.

**3 · BLOCKED ON A RULING ≠ UNBUILDABLE.**
Most ruling-blocked work can be BUILT now and only TESTED later. Build it, isolated, wired into
nothing. Say plainly what it cannot prove yet and which ruling would let it. This is where most
recovered time comes from.

**4 · RESPECT CONTENTION — MEASURED, NOT ASSUMED.**
Concurrency caps around 10-14 agents, but the machine caps lower. **Measured 2026-09-13: three
workflows plus background bash turned a 13s gate run into 663s — 50x.** Two heavy workflows is the
practical ceiling; a third buys nothing and costs everything. When a run looks stalled, check
contention before diagnosing a bug — I reported a 74x "regression" that was my own background jobs.

## Choosing what to run

- **Disjoint files → parallel.** Agents editing disjoint sets never conflict; no worktree needed.
- **Same repo as a running measurement → worktree.** A new file shifts a gate's denominator under a
  verifier mid-run. `isolation: 'worktree'`.
- **Different repo → free.** Zero interference, always safe to run alongside.
- **One agent per coherent unit of judgement.** Splitting one decision across two agents produces two
  half-decisions that disagree.

## Verify separately from building

A builder reporting its own success is an unverified claim. Today a verifier caught: a gate blind to
its own new files, a claim that a test was general when it needed proving, and a "byte-identical"
assertion that had to diff raw payloads before normalising. **The verify agent is not overhead; it is
the only reason the numbers mean anything.**

## What this skill cannot do

It cannot make the session act unprompted. Claude works when invoked. The watchdog
(`dev/wf-watchdog.sh`, a persistent Monitor) emits one line when everything goes quiet, so silence
becomes visible — but a standing self-driven loop is `/loop`, and only the operator can start it.

Be honest about this rather than implying autonomy that does not exist.
