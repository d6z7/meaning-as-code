# RULED — 2026-09-13 · the testing strategy's two gating decisions

**Status: RULED BY THE OPERATOR.** This records a ratification, not a proposal. The analysis it
rules on is `PROPOSED-2026-09-13_testing-strategy.md` (1517 lines, six measurement passes plus two
adversarial ones). Per CORE §3 an agent may only write `PROPOSED`; these two lines are the operator's.

---

## R-A · THE RATCHET, AND THE TWO RULINGS THAT TRAVEL WITH IT — **TAKE ALL THREE, TOGETHER**

Ruled: **R15 FALSIFIABLE · R2 UNKNOWN · R0 EXIT 2 BLOCKS.**

| | ruled | the cost, accepted with open eyes |
|---|---|---|
| **R15** the ratchet counts | **DEMONSTRATED-FALSIFIABLE** — an item enters a numerator only when a seeded mutant made its check FAIL, and the record names the mutant | one measured headline goes **1 565 → ~162** |
| **R2** a frozen-engine capture | **UNKNOWN**, not WORKING | a board's headline greens go to **near zero**; the estate's demonstrated fraction drops ~8 points |
| **R0** a gate's exit 2 | **BLOCKING, but distinguishable** — its own ladder segment, never folded into red, never into green | today's **five** could-not-run SDK gates become five reds |

**Why all three and not one.** Each is the same question in a different place: does a number get to
look good by examining nothing? On *observed*, an adversary moved the headline to ~90 % improvement
**in one day with three commits that add no test**, exit 0 throughout. A frozen capture proves a
regression, and 0008 §2(a)'s own table already says it is "no — regression only" as proof of
meaning. And if exit 2 lands non-blocking, **the cheapest way to green any gate in this estate
becomes making it could-not-run** — a route already open: one panel reads 54/67 passed while 9 are
skipped, and the 9 include every end-to-end check.

**THE CONSEQUENCE TO STATE OUT LOUD ON THE DAY IT LANDS: the numbers get worse. That is the
instrument being installed, not the estate degrading.** A drop that arrives with no explanation will
be read as a regression by everyone who sees it, including us in three weeks.

---

## R-B · THE ACCEPTANCE DIALECT — **DIALECT B, AND ADOPT A's `runs/` INTO IT**

Ruled on the census of 8 bundles / 3 dialects.

- **B is the standard.** It is the only dialect with a reader (**13 of 13** console path literals),
  the only one with anchors (21) and properties (291 across 6 suites), and the only one with a trend
  series. Standardising on A would **delete the entire property plane**.
- **A's `runs/` directory is adopted into B.** Purely additive, and the only way the operator's
  42,7 % becomes both *readable* and *auditable* — B commits a projection and overwrites
  `<suite>_runs.json` on every run, so it has no home for a dated record.
- **Grouped corpora land as an optional `group` key.** A's 11 group ids map 1:1 onto the `category`
  values the console already groups by, so a grouped corpus needs **zero console change**.
- **Accepted migration cost, named rather than discovered later:** 55 group-metadata fields
  (`tier`/`description`/`why_hard`/`sources` × 11) need a sidecar; `b_answers/` → `answers/` is a
  91-file rename; A's `dimensions`/`assessment` fields have no counterpart yet; and 4 bundles
  currently publish `questions: []` with the SHA-256 of empty as their fingerprint — those must
  **declare their zero denominator** rather than render as healthy and empty.

### The number this exists to make visible

    35 of 82 graded at `with-b` = 42,7 % NOT PASSED     run dated 2026-07-15
    no console view reads the file it lives in

**Quote it with its denominator or not at all.** Three rates are computable from that one file —
35/82 (`with-b` rows), 42/89 (all rows), ≥42/96 (7 authored ids never ran in any mode). The bundle's
own `master.yaml:meta.denominator_note` rules **82** to be the denominator, so 42,7 % stands, and
must always be written as *"35 of 82 graded at `with-b`"*.

---

## What is NOT ruled here

R1, R3's residue, R4–R14, R16, R17 remain open. **R16 (the admission test — "name the gate that
exits 2 when this artifact is absent or stale, in the same paragraph that proposes it, or do not
create it") is the one to rule next**, because everything the ratchet needs is a new artifact and
this estate's own record shows what happens without it: `authority: sme` adopted 0 of 101,
`question_id` 0 of 21, `QUALITY.md` 183 commits and zero appends — against `accepted:`/`frozen:` at
26 blocks, adopted because a red cannot move without one.
