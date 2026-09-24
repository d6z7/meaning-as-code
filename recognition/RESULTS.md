<!-- The running record of RECOGNITION measurements (PIPELINE_TESTING.md §3.1, stage 2).
     Append, never rewrite. COMPOSITION results live in invariants/RESULTS.md and Leg C's in
     benchmark/RESULTS.md — different subjects, different claims, not the same fact. -->

# RECOGNITION — RESULTS

## 2026-09-24 · Stage 2 · **C2 STABILITY** — pilot, 12 of 77 questions

First measurement of the interpreter this project has ever had, and it runs with **no AWS
session**: the `claude_code` provider added the same day. Model `haiku`, 2 generated paraphrases
per question, variants committed to `acceptance/paraphrases.yaml` so the run is reproducible.

```
12 questions attempted · 11 graded · 36 interpretations

  INTENT-equivalent    9 of 11   81.8 %   read the same way
  + absorbed                +2            named differently, same plan
  ANSWER-equivalent   11 of 11  100.0 %   same number
  CONSEQUENTIAL            0             a different answer
```

### The two rates are both honest, and the gap between them is the finding

Both unstable questions disagree **only on how a term or value is spelled**, and both plan to the
same SQL and the same number:

| question | phrasings produced | plans to |
|---|---|---|
| RC07 "How many customers are in Germany?" | `Country eq 'DE'` ×2, `Country eq 'Germany'` ×1 | **9 981** either way |
| RC08 "How many stores are closed?" | term `Status`, term `StoreStatus` | **8** either way |

**That is the register doing exactly what a register is for.** Reporting these as interpreter
instability would indict it for something the architecture handles by design. So the harness now
classifies every unstable question as *absorbed* or *consequential* by planning both readings and
comparing — the first version reported one rate, and one rate would have made a working resolver
look like a defect.

`CONSEQUENTIAL` is the number that matters, and in this pilot it is **0**.

### Against the pre-registered rule

PIPELINE_TESTING §8.3 sets ≥95 % as "stability is not the dominant error source", 80–95 % as "the
per-field diff names the weak field". At 81.8 % intent-equivalence this lands in the middle band —
**but the field it names is `filters`, and every instance is absorbed.** The rule was written
before the absorbed/consequential distinction existed and should be re-cut against the
ANSWER-equivalent rate, which is the one a reader experiences. **That is an operator ruling, not a
mid-measurement adjustment**, and it is flagged rather than taken.

### Caveats, and they are large

* **n = 12 of 77.** A pilot. The rate is not the corpus's.
* **6 interpretation failures** (`claude exited 1`) at `--workers 6`, and **0** at `--workers 3`.
  Concurrency, not the interpreter. One question went ungraded as a result; 11 is the denominator,
  not 12.
* **One model, one temperature, one run.** Stability across RUNS of the same phrasing is a
  different measurement (self-consistency) and is not made here.
* A disagreement says the interpreter READ two phrasings differently, never that either reading is
  wrong. Which is right needs an anchor — and for a genuinely ambiguous question (SST-Q3) a
  disagreement is the instrument working.

### Cost, recorded because it bounds how often this can run

Each interpretation is a full CLI session: ~28 k cache-creation tokens of the CLI's own harness
before our prompt is seen, and 20–30 s wall clock. 36 interpretations took 151 s at 6 workers. The
full corpus at k=2 is 231 interpretations — roughly 20 minutes at a concurrency that does not
fail. Acceptable for a measurement taken deliberately; not something to put in a pre-commit hook.
