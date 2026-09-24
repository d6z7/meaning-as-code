<!-- The running record of RECOGNITION measurements (PIPELINE_TESTING.md §3.1, stage 2).
     Append, never rewrite. COMPOSITION results live in invariants/RESULTS.md and Leg C's in
     benchmark/RESULTS.md — different subjects, different claims, not the same fact. -->

# RECOGNITION — RESULTS

## 2026-09-24 · Stage 2c · **CALIBRATION, re-run** — the gate cannot catch the failure that matters

Re-run after anchoring 4 of the 12 gated questions. 77 interpreted, planned **ungated**, graded
against 21 anchors.

```
confidence       n  planned  graded  correct   gate
0.00–0.30       5        3       1      0/1   BLOCKED
0.30–0.50       6        2       0        —   BLOCKED
0.50–0.80      13        6       1      0/1   allowed
0.80–1.01      53       40      14    13/14   allowed
```

### The finding, and it is not the one the experiment was designed for

**Three answers were wrong against an anchor. Two of them passed the gate.**

| | confidence | engine | anchor | |
|---|---|---|---|---|
| MQ-06 average store size | **0.70** | 67 | 1 504.55 | **allowed** |
| STORE-06 store versions | **0.90** | 67 | 74 | **allowed** |
| ADV-13 stores above average | 0.25 | −1 | 8 | blocked |

**A confidence gate cannot catch a confidently wrong answer — that is what the words mean.** The
band with the best record, ≥ 0.80 at 13 of 14, contains the single most dangerous failure on the
board. Raising the threshold would not have caught either: 0.90 is above any threshold anyone
would set, and a threshold that rejects 0.90 rejects everything.

So the honest conclusion is neither "raise it" nor "lower it". **The gate is the wrong instrument
for this failure class**, and the right one is an invariant that reads the SQL — see
`invariants/RESULTS.md`, where MQ-06 became a framework-wide check the same afternoon.

### MQ-06 is two defects in one question

The intent was `subject='Store', operation='average'` — **the model named the CONCEPT, not the
measure** (`SquareMeters`). That is a RECOGNITION failure. Then the planner, asked to average
something carrying no number, emitted `COUNT(DISTINCT StoreCode)` and returned **67** — a real
figure, and the answer to a different question. That is a COMPOSITION failure, and it is generic.

### Confidence is not stable on one question either

MQ-06 self-scored **0.70** in the calibration run and **0.15** on a re-interpretation minutes
later, same model, same prompt. A threshold applied to a number that moves 0.55 between runs of
the same question is not gating on a property of the question.

### What still cannot be measured

Of the 11 blocked readings only **1** has an anchor, because most of the blocked set cannot have
one — the value is absent from the data, or the question is genuinely ambiguous. That part of the
2026-09-24 record stands: the gate is mostly catching bad QUESTIONS, and on those a confident
answer would be the worse outcome.

---

## 2026-09-24 · Stage 2b · **CALIBRATION** — inconclusive, and the reason is the finding

`recognition/calibration.py`, all 77 questions interpreted and planned **ungated**, graded against
the anchors. 11 minutes, `claude_code` + sonnet, no AWS.

```
confidence       n  planned  graded  correct   gate
0.00–0.30       2        1       0        —   BLOCKED
0.30–0.50      10        5       0        —   BLOCKED
0.50–0.80      11        8       1      0/1   allowed
0.80–1.01      54       37      14    13/14   allowed
```

### It cannot answer its own question, and that is worth more than a number

**Zero of the 12 questions the gate blocks has an anchor.** Every one of the 16 anchored questions
sits at confidence **0.60–0.97**. So nothing here can say whether a blocked reading would have been
right — the comparison has no data on the side that matters.

**Our TRUTH plane covers exactly the questions least in need of it.** The anchors cluster on the
confident half; the hard half has no independent ground truth at all. That is a statement about the
CORPUS, not about the model, and no amount of re-running fixes it.

### What it does establish

* **High confidence is reliable: 13 of 14 correct at ≥ 0.80.** Worth having.
* **The gate is partly redundant.** Of the 12 it blocks, **5 the planner would have refused
  anyway** (`refusal`) and 1 raised — so for half of them the gate is a second "no" over the top of
  a first one. Only **6** are readings the gate actually discards that would have produced a number.
* **The blocked questions look genuinely underspecified** — *"Average price"*, *"Total sales in
  dollars"*, *"Sales in Turkey"*, *"What is the average customer age?"*. A low self-score on those
  may be the model being right about the question rather than wrong about the answer. These are the
  `SST-Q3` class, and a confident answer to them would be the worse outcome.

### What would make it conclusive

**Anchor the gated questions.** Anchors are derived by two SQL routes and cost nothing but care;
12 of them would put ground truth where the hard cases are and make this measurement answerable.

Two of the twelve will not take a numeric anchor and should not be forced to: *"Sales in Turkey"*
is a HUMILITY case (the right answer is a refusal if Turkey is not in the data), and *"Show me the
full lineage from OrderLine to Continent"* is not a number at all. Those need a declared expected
OUTCOME, not a value.

**Until that is done, the 0.50 threshold is neither vindicated nor convicted, and this record says
so rather than picking the flattering reading.**

---

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
