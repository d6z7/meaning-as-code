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
attribution at all. Reconciling them is §8's first open item and it is not an agent's call.

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

## 4. THE TWO LEGS — one set of categories, two subjects

The operator's split is correct and it is a **subject** split, not a vocabulary split:

**Leg A — framework conformance.** Subject: the grammar and the planner. Answers *is the FRAMEWORK
complete and stable?* Needs bundle-independent subjects, of which there are two kinds:

* **Synthetic reference bundles** — small ontologies that isolate exactly one pattern each: a
  nullable dimension · an SCD-2 relation · a degenerate dimension · a many-to-many · a non-additive
  measure · a multi-hop join · an empty-result question. Each is a dozen lines and a handful of
  rows.
* **An external corpus** — a BIRD database, for encodability (§3.2) and for the experiment in §6.

**This is also the way past n=1.** The `entity_key` / `versioned_by` redesign is deferred pending
more than one sample, and finding a second *real* versioned bundle is slow. Building a minimal
synthetic one that exhibits the pattern is an afternoon, and it is a legitimate second sample for a
structural claim.

**Leg B — bundle acceptance.** Subject: one ontology. Answers *is THIS bundle correctly declared, and
does the engine answer ITS questions?* This is what `acceptance/` already is.

**Shared — and this is the whole point of the split:** the Intent algebra (3.0), the metric
definitions, the runners (paraphrase · metamorphic · differential), the synthesised-instance
generator, and the report schema. Both legs emit the same shape, so one board reads both.

---

## 5. WOULD IT HAVE GONE RED? — validated against defects already found

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

## 6. THE ACADEMIC IMPORTS, and the one experiment worth running

| import | used for | note |
|---|---|---|
| Spider — component-wise exact-set-match | per-field intent scoring (3.0) | the decomposition, not the benchmark |
| Spider-Syn · Spider-Realistic · Dr.Spider | paraphrase stability (3.1) | method applies to **our** corpus; their data optional |
| NatSQL · SemQL coverage | encodability (3.2) | IR coverage is the published form of this metric |
| TLP · NoREC · PQS (DBMS testing) | metamorphic invariants (3.3) | TLP is the NULL detector, exactly |
| TrustSQL | abstention scoring (3.4) | the only benchmark that rewards declining |
| BIRD | Leg A corpus, and below | ships databases, so differential execution is possible |
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

### The experiment

BIRD supplies hand-written **external knowledge evidence** per question — domain hints the model
needs to read the question correctly. That is a per-question semantic layer, and it sets up a clean
test of this entire estate's thesis:

> Build a MAC bundle over one BIRD database. Run its questions **without** the evidence strings.
> **Does declaring the knowledge once, in an ontology, match or beat supplying it per question?**

A number either way is worth more than another architectural argument. If the ontology loses, that
is the most valuable thing we could learn this quarter.

---

## 7. SEQUENCING

Phases 1–3 need **no database, no warehouse credentials and no Bedrock session**.

1. **Intent algebra** (3.0) — canonical form, equivalence, per-field diff. Everything depends on it.
2. **Paraphrase stability** (3.1) over the existing 77 questions. Self-consistency, no gold. Will
   produce findings immediately: STORE-01 vs STORE-02 is already a known instance of the class.
3. **Encodability** (3.2) over one BIRD database — hand-written gold intents, counted. The first
   external evidence that the grammar is not just Contoso-shaped.
4. **Metamorphic invariants** (3.3) — TLP and the collapse invariants first, since both have a
   known-red on record to prove they can fail.
5. **Stage attribution** (3.4) — build what 06 §3 specified. Requires §8's first ruling.
6. **Leg A synthetic bundles**, then the BIRD bundle and the §6 experiment.

---

## 8. WHAT THIS REFUSES TO DECIDE — the operator's

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

---

## 9. HOW THIS PROPOSAL IS ITSELF CHECKED

Per TESTING.md, a claim is worth what its check is worth:

* §5 is the self-test: six dated defects, each with the instrument that goes red on it, and three
  named that nothing here would catch.
* Each instrument in §3 carries its SUBJECT · CLAIM · ORACLE, so a reader can apply the
  three-question test without trusting this document's own classification.
* Every number carries its denominator: 20 of 70 refused · 17 anchors · 4 `not_expressible` · 10 of
  433 rules with an invariant · 11 of 51 gates that prove they can reject · 0 of 398 oracles with a
  human-ruled authority · **0 of 20 refusals carrying a stage**.

**The last one is the smallest number in the document and the one to move first.**
