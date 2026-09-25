# DNA — WHAT EVERY ONTOLOGY DESIGN MUST DECLARE

*Instructions to myself, written 2026-09-25 on the operator's instruction: "YOU must write
instructions to yourself what everything must be part of the ontology design."*

This is a CHECKLIST, not an essay. If a dimension cannot answer every question in Part 1, the
ontology is not finished — whatever else is green.

---

## THE LAW THIS ALL RESTS ON

**A DECLARATION WITHOUT A CONSUMER IS A LIE.** Measured this week: `null_semantics` declared on 15
of 16 contoso dimensions and read by NOTHING; `contract.resolution` declared on 13 of 16, in prose,
read by nothing — and Continent's prose literally contains the fix for a live bug ("then filter on
`Continent`"). Before adding any field to a concept model, name the code that will read it. If
there is none, do not add the field.

**PROSE IS NOT A DECLARATION.** It repeats, it drifts, and no runtime can act on it. Everything
that determines BEHAVIOUR is a flag. Prose keeps exactly one job: saying what a thing IS, in one
or two sentences. Every `IT IS NOT…` paragraph that restates what a flag enforces gets deleted
when the flag lands.

---

## PART 1 — EVERY DIMENSION MUST ANSWER THESE

### 1.1 Closure — what does a miss MEAN?

```yaml
domain:
  closure: closed | open
```

* **closed** — the member list IS the domain. A non-member is answerable from the list alone,
  with no probe.
* **open** — the domain grows with the data. A name is resolved, never enumerated.

MANDATORY. No default. A missing closure is exactly the ambiguity that produced this week's bugs:
the resolver could not tell whether to refuse or to widen, so it guessed the same way for both.

**Closure is NOT cardinality.** Product could be closed at 2 517 (a controlled catalogue);
Continent is open at 3 (the world has seven). Cardinality decides how to PRESENT a domain —
inline the members, or resolve them. Closure decides what a MISS means. One number must never do
both jobs; `VALUE_LIMIT = 40` and `MAX_MEMBERS = 40` were doing exactly that.

### 1.2 Complete for what — the data, or the world?

```yaml
domain:
  complete_for: data | world     # may be defaulted at configuration level
```

* **data** — these are the members PRESENT. A word the model recognises as belonging to this kind
  but absent from the list answers **ZERO, WITH DISCLOSURE** — not a refusal.
  *"Sales in Asia"* → `0, and no customer in the delivery is in Asia.*
* **world** — the list is the kind. Absent means NOT A MEMBER, and refuses.
  *"Sales in Atlantis"* → refuse, that is not a continent.

One bit, and it settles every hard case in contoso: Continent, Country, StoreStatus, Color, Brand,
ProductCategory, ProductSubcategory. Set it once at configuration level for the bundle; override
per dimension only where a dimension genuinely differs.

The model already knows Asia is a continent. The bundle only has to say whether its list is the
world's or its own.

### 1.3 Warranty — WHY is the closure trustworthy?

```yaml
domain:
  warranty: derived | monitored
```

* **derived** — the members come out of a transform rule. A new load CANNOT add one.
  (AgeBand: 20..90 by `derive-age-band-as-of`.)
* **monitored** — the members were observed, and a scheduled check reconciles them against the
  source. (StoreStatus: 2 codes, measured — and tomorrow's load may carry `Relocated`.)

**`unwatched` IS NOT A PERMITTED VALUE.** A closed set that nothing watches is a refusal backed by
what we happened to see last Tuesday. That is the whole of the operator's ad-3 ruling:

> *"even if it would have lookup table in the database … the content of the table might increase
> overnight and we must get information about it. therefore a data quality monitoring must be
> applied … this is not what any ontology alone can answer."*

Correct, and it changes the shape of the problem: **closure is a CONTRACT, and a contract needs a
WATCHDOG.** Observed-closed is not a weaker warranty than derived-closed — it is an equal one, on
condition that something checks it daily and raises to a data engineer when it drifts. From the
refresh onward, everything is as designed. An ontology that declares `closed` without naming the
monitor is making a promise it has no way to keep.

A closure question that cannot be settled by a transform rule is therefore not an ontology
question at all — it is a monitoring requirement. Do not agonise over it; wire the check.

### 1.4 Where a resolved value LANDS

```yaml
domain:
  filter_column: Gender
  resolve_to:    column | key | register
```

Without it the planner falls back to the concept's identity column, which is how
`CustomerKey = 'female'` reached DuckDB. The register was CUT FROM a column; that column must
travel with the entry. Never derived, never guessed — declared.

### 1.5 A value that is in the DATA but not in the DOMAIN — SPLIT FIRST

**THE RULE, and it is the operator's, 2026-09-25:**

> *A sentinel that carries MEANING is a dimension in disguise. Split the source; do not flag the
> value.*

Ask one question of every sentinel: **is it a different KIND of thing, or is it an absence?**

* **A different kind → SPLIT IT OUT as its own dimension.** No flag, no special case, and the
  domain it was polluting becomes cleanly closed.
* **An absence ("we do not know") → then, and only then, declare it:**

```yaml
domain:
  null_means: unknown | <code>
```

**THE WORKED CASE, measured.** `dim_contoso_store` carries `CountryCode '--'` with CountryName and
State both `Online` — [store.md](ontology/concepts/store.md) already calls it *"a SALES CHANNEL
sitting in a store dimension"*, in prose, and then keeps it as a country anyway. Measured on the
served plane:

```
store dimension   online       1 row  (StoreKey 999999, StoreCode -1)
                  physical    73 rows over 8 countries
order lines       online   93 550   41.8 %
                  physical 130 424   58.2 %
```

**41.8 % of the fact is not a sentinel — it is half the business filed under a punctuation mark.**
The split is perfectly clean: one row, one key, a deterministic test (`CountryCode = '--'`), no
judgement call.

What the split yields, every item of which was otherwise a special case:

1. **`Channel` becomes a real dimension** — `physical | online`, 2 members, produced by a rule, so
   `warranty: derived`. No watchdog, because the rule DEFINES the domain rather than observing it.
2. **`Country` becomes cleanly closed at 8** on the store side. The `sentinels:` flag I originally
   proposed here is then unnecessary — which is the tell that the flag was the wrong instrument.
3. ***"In how many countries do we sell?"* answers 8 by construction**, not by a carve-out.
4. ***"Sales by country"*** discloses a channel with no country STRUCTURALLY, instead of carrying a
   caveat that a reader has to notice.
5. **Explicit search becomes possible.** This is live today and wrong: `contoso_country.lookup.csv`
   maps search key `online` to a COUNTRY. So *"online sales"* currently resolves to a country
   called Online. After the split it resolves to `Channel = online`, which is what was asked.

**THE GENERAL FORM.** A column holding two kinds of thing is two columns. Reach for a flag only
when the odd value is genuinely an absence — a NULL gender, an unrecorded date. StoreStatus's NULL
IS such a case and stays a flag: 59 of 74 versions carry no status and "operating" is the absence
itself, with the test `CloseDate IS NULL`. `--` is not an absence. It is a shop with no street.

### 1.6 The resolution ladder, per dimension

```yaml
resolution:
  strategy:    [exact, normalized, prefix, fuzzy]
  fuzzy_floor: 0.80
  on_miss:     refuse | zero_disclosed | ask
  candidates:  5 | suppress
```

The DEFAULT is the full ladder, per [[resolution-ladder-is-default]]: exact → normalized →
prefix → fuzzy → ask with candidates. A dimension narrows it, never invents its own.

`normalized` is not optional and is not a flag anyone declares: **case and whitespace folding is
common sense.** `female`, `Female`, `FeMaLe` are one word. A runtime that refuses on case has a
bug, not a strictness setting.

`on_miss` follows from 1.1 + 1.2 and should be derivable, not restated:

| closure | complete_for | a miss means |
|---|---|---|
| closed | world | **refuse** — not a member of the kind |
| closed | data  | **zero, disclosed** — real word, no rows |
| open   | *any* | **ladder, then ask with candidates** |

### 1.7 What may be an AXIS

```yaml
axis:
  groupable:     true | false
  groupable_why: privacy | grain | derived
  orderable:     true | false
```

`field_roles` already carries `dimension` vs `attribute`, and the prompt IGNORES it: 20 of 73
offered columns are declared `attribute`, including `ZipCode`, which [customer.yaml] forbids as an
axis on a measured privacy finding (DQ-CUSTOMER-02: ZipCode alone singles out 29 193 of 104 990
rows). A ruling made from a measurement must produce a REFUSAL WITH ITS REASON, not a silent
offer.

### 1.8 Closed sets get a register; registers get a monitor

Every `closure: closed` dimension has a register in `data/lookups/`, and every register has:
* a `source_view` and a source COLUMN naming where it was cut from;
* labels a person would say (`Germany`), not just codes (`DE`);
* a scheduled reconciliation — see Part 2.

**ONE REGISTER PER DIMENSION.** Two registers for one dimension WILL disagree. Found 2026-09-25:
`contoso_country` (9 rows, labels `Germany`, carries the continent roll-up) and
`country_country` (8 rows, labels `DE`, no roll-up, no sentinel) — the second cut by
`cut_missing_registers.py` on top of an existing register it never checked for. A cutter must
refuse to write where a register already covers that column.

---

## PART 2 — THE MONITOR (what the ontology cannot answer alone)

The gate chain is real and it is **entirely offline**: `check_lookups.py` says so in its own
docstring — *"it checks files on disk, never the warehouse."* `check_enumeration_closure.py`
catches a closed set holding a guessed member; `check_vocabulary_drift.py` catches code that
re-lists a closed vocabulary. None of them asks the database whether the members are still the
members.

**MISSING, and required by 1.3:** a scheduled `check_register_membership` that, for every register
declaring a `source_view` + source column:

```
SELECT DISTINCT <column> FROM <source_view>     vs     the register's rows
```

* in the warehouse, not in the register → **STALE. Alert the data engineer; the register needs a
  refresh.** Not a silent refusal to the user.
* in the register, not in the warehouse → **PHANTOM member.** A closed set that can refuse a true
  word, or offer a value that returns nothing.
* identical → the `monitored` warranty holds for another day.

This runs on a schedule against the live plane, not in the offline gate chain. It is the
difference between an ontology that CLAIMS a domain is closed and one that KNOWS it.

---

## PART 3 — STANDING LAWS (do not relearn these)

1. **Derive the enumeration, author the meaning.** Members are CUT FROM DATA. Nobody types a
   member list. What a member MEANS is authored.
2. **Never hardcode — every behaviour comes from a declaration.** No code branch per question
   type, per bundle, per concept name. [[never-hardcode-use-declarations]]
3. **Nothing bundle-specific in the prompt.** All specificity arrives through the ontology.
4. **Pass/fail is the only verdict**, against a human-approved reference answer.
   [[pass-fail-is-the-only-verdict]]
5. **Fix the requirement, not the instance.** Ask why a mechanism exists before satisfying it.
   [[fix-the-requirement-not-the-instance]]
6. **Check for an unread declaration before proposing a new one.**
   [[the-runtime-ignores-its-own-declarations]]
7. **Common sense is not a declaration.** Case folding, "Europe is a continent", "female is a
   gender" — the model brings these. The ontology declares what the model CANNOT know: which
   column, which grain, which ruling, which refusal.

---

## PART 3B — PREMISES I MUST NOT NEED TO BE TOLD AGAIN

*Written on the operator's instruction: "you must be able to repeat these premisses next time you
build ontology without my help." Each one is a trap I walked into on 2026-09-25, with the
measurement that proves it.*

### P1 — BEFORE DECLARING A CANON, CHECK THE RUNTIME IMPLEMENTS IT

Audited across contoso: **7 of 16 canon bindings name a UDF the loader has never supported.**

```
  6  mac.canon.resolve_by_register      KNOWN
  3  mac.canon.enum_from_register       KNOWN
  4  mac.canon.grouping_from_register   ** UNKNOWN TO THE LOADER **
  2  mac.canon.refuse_measure_no_row    ** UNKNOWN **
  1  mac.canon.snapshot_collapse        ** UNKNOWN **
```

The loader knows exactly two names (`register_declarations.py`: `RESOLVE_BY_REGISTER`,
`ENUM_FROM_REGISTER`). Everything else parses as valid YAML, passes every gate, and does nothing.

**This is why Continent, Brand, ProductCategory and ProductSubcategory had no resolvable values.**
Their registers were never orphaned for want of a declaration — the declaration was there, written
carefully, naming the right file and the right columns. The runtime simply did not implement the
verb.

**Rule: `grep` the runtime for the UDF name before writing it into a bundle.** A canon that
nothing implements is a comment.

### P2 — AN UNIMPLEMENTED CANON MUST FAIL LOUDLY, NEVER SKIP

A declaration the runtime cannot honour must refuse at load with the concept and the UDF named. A
silent skip is how four registers stayed dark long enough for me to rebuild them by hand. The same
law as [[the-runtime-ignores-its-own-declarations]], stated for canons: **the loader may not decide
on its own that part of the ontology does not exist.**

### P3 — NEVER BUILD A WORKAROUND FOR AN UNIMPLEMENTED MECHANISM

On 2026-09-25 I cut 15 registers from the warehouse to make `Continent='Europe'` resolve. It
worked. **13 of the 15 duplicated registers the bundle already had**, and every duplicate was
strictly worse:

```
contoso_country.lookup.csv   DE,Germany,germany,Europe,…   9 rows  labels, continent roll-up, sentinel
country_country.lookup.csv   DE,DE,de,…                    8 rows  no labels, no roll-up, no sentinel
```

The second one cannot resolve the word "Germany". I had produced a worse copy of a better file,
because I fixed the data instead of the reader.

**Rule: when a fix produces data the bundle already contains, STOP. You are treating a symptom.**
Ask what should have read the existing data and did not.

### P4 — ONE REGISTER PER DIMENSION, ENFORCED BY THE CUTTER

Two registers over one column WILL disagree, and nothing in the runtime arbitrates. A cutter must
refuse to write where a register already covers that source column, and say which file already
covers it.

### P6 — A LONE GUESS IS STILL A GUESS

The ladder's last rung is ASK WITH CANDIDATES, and it must be reachable with ONE candidate. The
clarify test asked only when two candidates TIED, so a single fuzzy match was treated as
certainty:

```
'Asia'   -> Australia   (lookup:fuzzy, ratio 0.62)      BOUND, never asked
'Germny' -> DE          (register:near-miss 0.92)       BOUND, never asked
```

A question about Asia was about to be answered with Australian numbers. **Offering one candidate
is a question with one option, which is exactly what should be put to a person.**

The exception, and it is not a judgement call: the NORMALIZED tier binds silently. `norm()` folds
case and whitespace, so `FeMaLe` IS `female`. Asking there is pedantry, not caution.

### P7 — DO NOT INVENT A CANON THAT AN IMPLEMENTED ONE ALREADY EXPRESSES

Four concepts declared `mac.canon.grouping_from_register` and none of them needed it.
`resolve_by_register` binds EVERY code a name covers — which is precisely a group over its
members. Continent through the country register:

```
Europe -> Country IN ('DE','FR','GB','IT','NL')     19 564
direct    Continent = 'Europe'                      19 564     AGREE
```

The roll-up route is the better of the two: the answer can name which countries it counted.

**Before writing a new canon, check whether an implemented one already says it.** Reach for a new
verb only when the meaning is genuinely absent, not when the existing verb is unfamiliar.

### P5 — THE ORDER OF DIAGNOSIS, when a value will not resolve

Work it in this order. Every step but the last was skipped at least once this week:

1. **Is there a register?** — `data/lookups/`
2. **Is it DECLARED on the concept?** — `realized_by.udf` + `params.register`
3. **Is the declared UDF IMPLEMENTED?** — grep the runtime *(this is the one that was missed)*
4. **Did the register LOAD?** — a skipped load must be visible, never inferred
5. **Does the entry carry its SOURCE COLUMN?** — else the planner filters on the identity key
6. **Is the value in the PROMPT?** — a model cannot pick a value it was never shown

Only after all six comes "the data is missing." It almost never is.

## PART 4 — THE ORDER TO BUILD IT IN

1. `domain.closure` + `complete_for` on the model; parser; **mandatory** (a bundle without it
   fails to load — a default would reintroduce the guess).
2. `filter_column` — kills the identity-key fallback. Smallest fix, biggest live bug.
3. `sentinels` + `null_means` read by the resolver and the count route.
4. `axis.groupable` read by the prompt builder — drop `attribute` from the offered set.
5. `resolution.*` replacing `contract.resolution`'s prose; migrate contoso's 13 paragraphs.
6. `check_register_membership` on a schedule; `warranty: monitored` becomes provable.
7. Delete the prose the flags now enforce.

---

## PART 4B — WHICH PREMISES ARE ENFORCED

A premise nobody checks is a premise nobody keeps — this document's own first law turned on
itself. What holds each one today:

| | premise | enforced by |
|---|---|---|
| P1 | canon must be implemented | **`check_canon_implemented.py`** — walks every `realized_by` in the document tree |
| P2 | unimplemented canon fails loudly | **the loader** — reports each as a `SkippedRegister`; **console readiness** publishes them |
| P3 | no workaround for an unimplemented mechanism | P1 + P5 make the real cause findable; not mechanically checkable |
| P4 | one register per dimension | **`check_one_register_per_dimension.py`**, and **the cutter refuses by column** |
| P5 | the diagnosis order | this document; step 3 is now a gate |
| P6 | a lone guess still asks | **`test_planner_value_column.py`** — 3 near-miss cases + the normalized counter-case |
| P7 | no canon an implemented one expresses | `mac_runtime/canon.py` `KNOWN_UNIMPLEMENTED` says so at the point of temptation |

**`mac_runtime/canon.py` is the registry** — the canons this runtime honours and where, plus the
ones it knowingly does not. `test_canon_registry.py` holds both lists to the source, stripping
docstrings with `ast` first: `registers.py` names both unimplemented canons in PROSE, narrating
this very defect, and a text search read that as evidence of support.

---

## PART 5 — STATUS, 2026-09-25

| # | item | state |
|---|---|---|
| 1 | `domain.closure` + `complete_for`, mandatory | **open** — see below, it got MORE motivated today |
| 2 | `filter_column` on the entry | **DONE** — `LookupEntry.column -> Candidate.column -> ResolvedFilter.concept_column`, 7 tests |
| 3 | sentinels / `null_means` | **superseded by 1.5** — split the source instead; the Channel split is the open piece |
| 4 | `axis.groupable` read by the prompt | **open** — 20 of 73 offered columns are declared `attribute` |
| 5 | `resolution.*` replacing prose | **open** — 13 paragraphs to migrate |
| 6 | `check_register_membership` on a schedule | **open** — still the only gate that would touch the warehouse |
| 7 | delete the prose the flags enforce | **open** — follows 5 |

**What landed today, measured.** "How many female customers are in Europe?" — a question that
refused three different ways this week — now plans, executes and answers **19 564**, cross-checked
against every cell of the dimension (5033+5075+19564+20024+27330+27964 = 104 990). All 11
dimension probes resolve. 1 294 tests pass.

**Why item 1 got more motivated, not less.** With the guessing fixed, `Asia` now REFUSES — no
member matched. That is better than binding Australia, and it is still not the right answer. Asia
is a real continent with no customers in this delivery, and the honest answer is **zero, with
disclosure**, not "I do not know that word". Exactly the `complete_for: data | world` bit from
§1.2. The defect was hiding behind a worse defect; fixing the worse one uncovered it.

**Consolidation, same day.** Four locks, so the day's gains cannot quietly reverse: the canon gate
(6 of 18 bindings caught on contoso), the duplicate-register gate, a cutter that refuses by COLUMN
and now asks the right question about what already resolves, and skipped registers published in
readiness (1 → 7 visible). Run against the same bundle it damaged yesterday, the cutter now says
*"nothing to cut — every low-cardinality dimension already resolves"* and writes **0**.
