<!-- STATUS: PROPOSED. Not ratified. An agent may write PROPOSED (TESTING.md §8); the rulings this
     document defers are marked and are the operator's.
     CONCEPT OWNER: TESTING.md. The one law, the three-question test, the ten categories and the six
     laws of reporting are defined there and are NOT restated here. This document owns one thing:
     WHICH INSTRUMENT TESTS WHICH STAGE of question -> answer, and where each one's oracle comes from.
     Every number below was measured on 2026-09-24 against the landed code and the worked bundle. -->

# PIPELINE TESTING
### An instrument for each stage, and the one stage that has no subject

> Read [TESTING.md](TESTING.md) first. It answers *what a green is allowed to mean*. This answers
> *what we point at each stage of the pipeline, and what the oracle is when we do*.

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
* **`packages/mac-eval`** — the component 06 names. Its README today: *"Empty-but-typed skeleton
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
2. **The kill-test runs in one direction only.** `intent_killtest.py` and `trace_question.py` replay
   a **hand-written** intent through the real planner, which isolates the planner beautifully — the
   STORE family's findings this week are entirely its work. Nothing runs the other direction:
   *LLM-produced intent versus the hand-written one*. `acceptance/intents.yaml` holds recorded
   intents and the platform holds 9 recorded question fixtures; neither is scored.
3. **`Intent.confidence` is consumed but never validated.** `ask.py` and `pipeline.py` compare it to
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

The last two are not hypothetical. **TLP — Ternary Logic Partitioning, from the DBMS-testing line of
work (Rigger & Su, alongside PQS and NoREC) — is precisely, mechanically, the detector for the defect
found on 2026-09-24**: `Status <> 'Closed'` returning 6 where the answer is 59, because 59 of 67
current stores carry a NULL status and `<>` discards every one. TLP finds that with no oracle, no
anchor and no knowledge of what a store is.

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
| **L0 — schema** | **generated**: tables → concepts, FKs → edges, column types → field_roles, PKs → `identity.canonical_key` | none | all 95 DBs |
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

## 8. SEQUENCING

Phases 1–4 need **no warehouse credentials and no Bedrock session**. Phase 2 needs neither a gold
answer nor a database.

| # | build | unblocks | needs |
|---|---|---|---|
| 1 | **Intent algebra** (3.0) — canon · equivalence · per-field diff | everything below | nothing |
| 2 | **Paraphrase stability** (3.1) over the existing 77 | first real RECOGNITION number | nothing |
| 3 | **Gold-SQL → gold-intent transpiler** (5.3) + its mutant test | encodability at corpus scale | a benchmark download |
| 4 | **Encodability** (3.2) over BIRD dev + Spider | the first evidence the grammar is not Contoso-shaped | phase 3 |
| 5 | **Metamorphic invariants** (3.3) — TLP and the collapse pair first | COMPOSITION, and two known-reds to prove they fail | a local DB |
| 6 | **Stage attribution** (3.4), per 06 §3 | splits the 20 refusals by stage | §9's first ruling |
| 7 | **L0/L1 bundle generator** (5.2) + denotation comparator (5.4) | the L0 apples-to-apples number on all 95 DBs | phases 1, 5 |
| 8 | **Leg A synthetic bundles** | past n = 1; unblocks the deferred `entity_key` work | phase 5 |
| 9 | **L2 bundle + same-model control + evidence ablation** (5.2) | the headline claims of 5.6 | 7, 8, live model |

**Phases 3 and 4 are the ones to reach for early.** They are where the operator's requirement is
actually satisfied — a large third-party corpus, scored on an axis other people publish on — and
they need no engine run, no anchor and no ontology authoring. The number they produce (*"of K BIRD
questions, J are not expressible as an Intent, and here are the features they need"*) is the most
decision-useful single figure available to this project right now.

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
