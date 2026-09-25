# PROTOCOL — 2026-09-25 · what was decided, found and still owed

**Written because the operator asked for it: "we discussed so many things which you will ALL
forget until next time. protocl !!!"** Everything below is measured or quoted, not remembered.

---

## PART 1 — THE OPERATOR'S VERDICT ON THE DAY, AND HE IS RIGHT

> "do you have any impression that we are converging step by step anywhere? i do not at the
> moment ... we started this discussion today about testing and fixing the framework. but after
> whole day of work ... we are still where we were in the morning."

**Correct.** The day produced instruments, not outcomes: C1 74.0 % → 85.4 %, C3 179 → 453 checks,
834 → 1274 tests. **None of those makes a single question answer better.** The requirement was
*"insight in every single step ... to see what is not behaving in order to make it behave as
desired"* — the seeing got built, the making-it-behave did not.

Three named failures, to not repeat:

1. **The frontier widened instead of closing.** BIRD — a new corpus, adapter, comparator — was
   opened while contoso has 9 unreachable registers and 11 questions emitting invalid SQL.
2. **One architectural defect was fixed five times as five bugs.** `declared-but-unread` appeared
   as `_index`, `declared_fk`, `stages`, `SkippedRegister`, `binds`. Instances do not converge.
3. **No priorities were proposed.** "What's next" was answered fifteen times with "another thing
   I found". Deciding what NOT to do was the job.

**And three times the fix was proposed at the wrong level** — bundle edit, then register binding,
then the resolver — each time by fixing whatever was in front of me instead of asking why the
requirement existed. The operator's "it is COMMON SENSE" was the correct read every time.

---

## PART 2 — THE TESTING FRAMEWORK: WHERE IT CAME FROM

**Asked: "I dont know where did you take this testing framework ?!?!?! is is from some reerence
... it is important to know."**

**It is from no reference.** No external citation in `TESTING.md`; written in this repo
2026-09-13. The four flags come from a commit of **2026-08-17** titled:

> *"acceptance: replace **one opaque verdict** with three per-assertion flags"*

**There was a pass/fail. An agent replaced it** with four graded flags (disposition, pinned axes,
value, ontology rules) rolling up into eight verdict words. `proven` requires an anchor; 21 of 77
questions have one; the headline was 0 and could never be anything else. A board whose best state
is unreachable is not a test.

### What replaced it, today

`tools/check_answers.py` + `acceptance/reference/<id>.yaml`. The operator's own words as the spec:

> "you have ACCESS to the DATA make manual query and let me know hat do you think the right answer
> is and let me approve it. then this becomes reference ... if the answer in the next run is the
> same then pass."

First run: **PASS 8 of 8 approved (100 %)**. 12 answers approved; 65 of 77 still have none and are
counted as neither pass nor fail — the denominator is never borrowed.

**Comparison is forgiving where forgiveness costs nothing**, per the operator: *"female === Female
is absolute common sense ... you cannot be so snesitive"*. Numbers compare numerically, text
case- and whitespace-insensitively.

**Two reference answers I got wrong on the first pass, both recorded in the files** — they are the
argument for a human approving these:
* RC07 → I computed **0**. `Country` holds `DE`, not `Germany`; the column is `CountryFull`. Correct: **9 981**.
* RC12 → I computed **0**. The stored gender value is lowercase. Correct: **19 564**.

**Three still need a ruling, not arithmetic:** RC08 counts `Status='Closed'` only and excludes 7
`Restructured` (8 vs 15); RC02 returns a count where the question says "list"; RC05 is 67 by SCD-2
collapse, not 74 rows.

**Owed:** the remaining 65 reference answers, in blocks of ~12, and RC01/02/03 re-written as list
answers rather than counts (my error).

---

## PART 3 — RESOLUTION: THE OPERATOR'S DESIGN, AND WHAT ALREADY EXISTS

### The design, in his words

> "if it is not in the lookup ... then it shold try with LIKE in lookup ... and offer any version
> from the lookup that was find. if not fournd ask for permission to search in the table first
> .... with like again. after that again offer to chose similar word from multiple choice."

### What is already built

| step | state |
|---|---|
| 1. exact match in the register | **works** |
| 2. LIKE / fuzzy in the register, offer matches | **BUILT AND UNREACHABLE** — `exact > normalized > prefix > fuzzy`, difflib, disjoint score bands, in `resolver/lookup.py` |
| 3. search the column itself | **does not exist** |
| 4. offer a multiple choice | **built** — the planner returns a `Clarification` carrying candidates |

### Why step 2 never runs

`RegisterResolver.resolve()`: if a concept HAS a register, only that register is searched, exact
only, and it **never falls through** to the tiered ladder. Falling through happens only when the
concept declares NO register. It is deliberate — a comment forbids a fuzzy tier reaching a
declared register — but the effect is that **declaring one register disables fuzzy matching for
every value of that concept**, the opposite of what declaring should buy.

### The deeper finding: the register requirement is itself wrong for most registers

The operator: *"what i dont understand is what do you need gender register ?!?!?!?! it is COMMON
SENSE !!!"*

```
contoso_gender.lookup.csv:  female,female,female        <- code = label = search_key
                            male,male,male
contoso_country.lookup.csv: AU,Australia,australia      <- a REAL map
```

**The gender register is a no-op.** The column holds `female`/`male`; the register maps
`female → female`. It exists because the architecture demands one, not because anything needed
mapping. `Germany → DE` needs a map; `female → female` does not.

And there is no `Gender` CONCEPT at all — only `Customer.field_roles["Gender"] = dimension`. So
all three routes are shut: no register binding, no inline `values.items`, and **no path that
simply filters a declared dimension column on its own values.** That third absence is the defect.

### Orphaned registers — measured

**9 of 17 in contoso are unreachable**: calendar_quarter (4 rows), calendar_weekday (7),
working_day (2), gender (2), geo_area (608), product_subcategory (32), weight_unit (3), measure
(3), dim_contoso_product (**2 517** — every product by name).

**How they came to be:** one commit, *"feat(contoso): re-ingest the bundle from the database"*,
added **all 17 lookup files and 0 register bindings**. The cutter produces registers; nothing
produces declarations; the 8 that work were hand-written later. `dim_contoso_store` got a rule and
`dim_contoso_product` did not — the split is arbitrary, not a decision.

**The runtime already knows.** `registers.py` scans the directory and builds
`SkippedRegister(name, "no concept declares this register, so nothing may resolve through it")`.
The list is constructed and dropped. `tools/check_registers_reachable.py` was written today to
re-derive it — that is a second source of truth and should be retired in favour of surfacing what
the loader already computes.

### The change this all points at — ONE change, not nine bindings

1. **A register miss falls through to the tiered ladder.** The score bands already guarantee an
   exact match outranks a fuzzy one, so the safety argument behind the block is already handled.
2. **Near-misses return as a `Clarification`**, not a refusal.
3. **A dimension column with no register resolves against its own values.** This retires the whole
   orphaned-register class at once and makes gender, quarter, weekday and status work with no
   declaration, ever.

---

## PART 4 — THE PROMPT: GENERIC ONLY, AND HOW THE ONTOLOGY SHOULD LOAD

### The requirement

> "i do not want in prompt anything wich is not GENERIC !!! all speficig things should come
> throuch ontology"

### Measured violation

The `_INSTRUCTIONS` block is 3 723 chars of supposedly generic text and contains: `store` ×1,
`revenue` ×2, `customer` ×1, and the hardcoded system-concept names `Concept` ×3, `Edge` ×1,
`ContractRule` ×1. `"how many stores"` appears **3× in every prompt** as a baked-in example.

### What the prompt is today

**6 distinct prompts across 77 questions — and those 6 differ only because the ontology changed
during the day, never because the question did.** ~53 000 characters of the entire ontology, sent
whole, every time. It does not adapt to the question at all.

### The operator's original design, to be restored

> "1 LLM gets ontology.yaml --> containing a list of all concepts that we have. 2. LLM request the
> concept needed for elaboration 3. LLM repeats the cyclus until it has full infomration about
> everything it needs 4. then it spucks result."

**Progressive retrieval instead of a 53 kB dump.** The proposal to write against it:

* the prompt carries **only generic instructions** plus a **concept INDEX** — name, class, one
  line each. For contoso that is 20 lines, not 53 kB.
* the model **asks for** the concepts it needs; each returns its definition, default reading,
  never-clauses, edges and — for a small closed domain — its VALUES.
* it loops until it can answer, then emits the Intent.
* **every request and every response is a trace event**, which is exactly the debugging record the
  operator has been asking for: not "here is the prompt" but "here is what it asked for and why".

**The value question this settles too:** 3 315 register rows exist, but 2 517 (product) + 608
(geo_area) are identity registers that must never be inlined. **The other fifteen hold 190 rows
total** — every enumeration in the bundle, ~2 kB, and the model is currently told none of them.
Under progressive loading, a concept's values arrive when the concept is requested, so the
question of "what fits in the prompt" disappears.

---

## PART 5 — WHAT THE DAY ACTUALLY LANDED, AND WHAT IS OWED

### Landed (committed)

* **ONE RUNNER.** The board called `mac_runtime.ask.ask()` (emits nothing) while the Chat called
  `run_pipeline` (emits typed stage events). The corpus was wired to the blind door: **0 of 77
  captures carried a run_id.** Now every capture records its stages, statuses, durations and the
  owning stage.
* **11 of 77 questions were failing with SQL Binder or Parser errors and the board called them
  `answered`.** `run_status` and `_is_error_capture` keyed only on top-level `error`/`result.status`.
  Now: verdict `error` 1 → 12, `unproven` 56 → 48.
* The board had **no `Error` segment at all** — 12 questions could not be reached from the page.
* The ontology reaches the LLM whole: rules were arriving at **37 % and 66 %** of their authored
  text, cut mid-word; rule SQL templates were leaking into the prompt.
* `Intent.having` / `any_of` / `all_of`; C1 74.0 → 85.4 % on pinned sources.
* BIRD ingested and pinned (sha256 recorded); 11 L1 bundles generated and committed; a real
  `SQLiteAdapter`; a denotation comparator validated at 60/60 gold-vs-itself and 32/32 effective
  mutants.

### Owed, in priority order

1. **The resolution ladder** (Part 3) — one change, retires the orphaned-register class.
2. **Progressive ontology loading + a generic-only prompt** (Part 4).
3. **The remaining 65 reference answers** (Part 2), in blocks for approval.
4. **The 11 SQL errors** — our invalid SQL, now visible, still unfixed.
5. Surface `SkippedRegister` where the runtime already computes it; retire the duplicate gate.

### Rulings still open

* `acceptance/` vs `eval/` — packet written (`PROPOSED-2026-09-24_acceptance-is-the-home.md`).
* Pinning traces into a public bundle: redact, or store outside. Traces hold result rows.
* RC08 / RC02 / RC05 readings (Part 2).

### The convergence test

**Of the 77 questions, how many return the approved answer?** Today: **8 of 8 judged, 8 of 77
approved.** If that number does not rise next session, the plan is wrong and gets changed rather
than added to.
