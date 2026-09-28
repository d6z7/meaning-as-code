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

### 1.7B `attribute` IS NOT A KIND — IT IS FOUR STATEMENTS IN ONE WORD

The operator's question, 2026-09-25: *"could we not say that the attribute is subset of dimension
that can be tuned with flags on the dimension level ... like never axis"* — right in direction,
and one flag is too few. Measured over contoso's 20 `attribute` columns, four different things are
wearing the word:

```
CountryFull     vs Country        8 /   8 distinct,   8 pairs   1:1
CountryName     vs CountryCode    9 /   9 distinct,   9 pairs   1:1
MonthShort      vs Month         12 /  12 distinct,  12 pairs   1:1
DayofWeekShort  vs DayofWeek       7 /   7 distinct,   7 pairs   1:1
YearMonthNumber vs YearMonth     132 / 132 distinct, 132 pairs   1:1
Manufacturer    vs Brand          11 /  11 distinct,  11 pairs   1:1
StateFull       vs State         608 / 563 distinct, 608 pairs   N:1
ZipCode          40 639 distinct over 104 990 rows
City             34 581 distinct over 104 990 rows
StartDT          11 305 distinct over 104 990 rows
```

**(a) ANOTHER NAMING REGISTER OF THE SAME THING — 6 of 20, every one 1:1.**

The operator's ruling that settles what this IS (BRD-Q1):

> *"Brand is Contoso, known as Contoso. But Manufacturer registered name is Contoso AG. One is what is
> known to people of the world and the other is what is entered in the trade registers."*

**TWO NAMING REGISTERS FOR ONE ENTITY**, not two entities. That is why the 1:1 holds by MEANING
rather than by luck — every brand has exactly one trade-register entry. Had `Manufacturer` meant
the OWNING company it would be 1:N (Northwind AG owns Contoso, CTSO and Contoso) and the modelling
would be the opposite. The distinction between *a thing's other name* and *a thing's parent* is
the whole question, and cardinality alone cannot tell you which you have.

`GROUP BY CountryFull` yields exactly the 8 groups `GROUP BY Country` yields. So this is not
"not an axis" — it is a **REDUNDANT** axis, and the flag is a RELATIONSHIP, not a prohibition:

```yaml
Manufacturer: { role: dimension, name_form_of: Brand,   register: legal }
CountryFull:  { role: dimension, name_form_of: Country, register: long }
MonthShort:   { role: dimension, name_form_of: Month,   register: short }
```

**AND THE RIGHT BEHAVIOUR IS REDIRECT, NOT REFUSE.** *"Sales by manufacturer"* is a good question:
answer it by grouping on `Brand` and DISPLAYING `Manufacturer`. Refusing it — which is what
`never_axis` does, and what this estate shipped on 2026-09-25 — trades a silent wrong answer for a
wrong refusal. The improvement is real; the destination is redirect.

**(b) A DIFFERENT LEVEL OF THE SAME THING — `StateFull` vs `State`, N:1.**

608 long names over 563 codes: the long name is **finer**, so grouping on the code MERGES regions
the name separates. The bundle files this beside case (a) with the note that grouping on the long
name "would split the same geography two ways" — true of `Country`, and the wrong diagnosis here,
where the two columns genuinely disagree about how many regions exist. This is a real axis at
another grain, and the answer must disclose which level it used.

**(c) TOO IDENTIFYING TO BE AN AXIS — `ZipCode` 40 639, `City` 34 581 over 104 990 rows.**

**Only this group is a genuine prohibition**, and it carries a measured basis (DQ-CUSTOMER-02).
This is where `never_axis` belongs, with its evidence so the refusal can cite it.

**(d) NOT BUSINESS CONTENT AT ALL — `StartDT`, `EndDT`.**

SCD-2 validity windows: when the ROW was written, not when anything happened. These are not a
dimension you may not group by; they should not be in the business vocabulary at all. A different
PLANE, not a weaker permission.

**THE RESULTING SHAPE:**

```yaml
Gender:      { role: dimension }
CountryFull: { role: dimension, name_form_of: Country, register: long }
StateFull:   { role: dimension, finer_than: State }
ZipCode:     { role: dimension, never_axis: privacy, evidence: DQ-CUSTOMER-02 }
StartDT:     { role: system }
```

So `attribute` does collapse into `dimension`, as the operator proposed — but what replaces it is
mostly a RELATIONSHIP between columns, and only one of the four is a prohibition. A single
`never_axis` flag would have preserved the conflation in a new spelling.

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
8. **Every concept carries a SAMPLE of its real rows — always, and generated.** A concept states
   what a thing IS; the sample is the only artifact that shows what it actually CONTAINS, in the
   columns the concept itself declares. Authoring one is forbidden for the same reason authoring a
   member list is: it is a fact about data. Generate it, date it, regenerate it. Whether the rows
   may be RENDERED to a reader is a separate, declared decision (`disclosure.samples`) that
   defaults to withheld — withholding is not silence, so the page still says a sample exists and
   over what denominator. See P9.
9. **Every ontology projects an ER MODEL — always, and generated, and only what is REALIZED.**
   A sample shows what one concept CONTAINS; the ER projection shows what the ontology CONNECTS,
   and it is the only artifact in which an edge that joins NOTHING is visible. Draw an edge only
   when it carries a realization, and there are exactly THREE: a `join_rule` (a predicate between
   two relations), a `realized_by` column (one relation — the relationship IS a column of the row),
   or a `resolved_by` RULE (the predicate is conditioned, so a rule carries it). Draw the
   unrealized ones in a separate REPORT, never silently. See P10.
10. **One IMPORT RUN must hand the operator the FULL STATE.** Not the files a run happens to make —
    the state a person can continue tuning an ontology FROM: sources, assets, the measurement plane,
    the referential structure, lineage, the ER model, concepts, registers, SME questions, and both
    quality suites GENERATED AND EXECUTED WITH THEIR RESULTS. The list, with each item's producer and
    its measured status, is [DELIVERABLES-2026-09-26_first-run-state.md](DELIVERABLES-2026-09-26_first-run-state.md)
    — referenced and not copied, by law 1's own logic. The acceptance test is the operator's:
    *"dont give me this shit over and over where i have to ask for functionality here and there."*
    A deliverable that has to be asked for was not delivered. See P11.
11. **Two bundles share NOTHING.** No file, path, connection or declaration of one may name another.
    The single permitted cross-border act is comparing a reference ANSWER, which is a review
    performed from OUTSIDE both and leaves no path inside either — and the ontology plane is excluded
    from even that. See P12.
12. **A GATE MUST NOT FAIL A WORKING BUNDLE, and must never SKIP where it should FAIL.** Both
    failures teach an operator to ignore it, which is worse than having none. See P13.
13. **STRUCTURED IN THE DECLARATION, COMPOSED IN THE PRESENTATION.** A declaration keeps each fact in
    its own typed field — `role: primary_key` + `key_position: 2`, because a position is a NUMBER that
    compares, sorts and can be checked 1..n. A page composes them and renders `PK2`, because a table is
    read by a person and parsed by nothing. **The test is: does anything PARSE this?** Backwards either
    way costs something measured — `primary_key_2` puts string surgery in every consumer that wants the
    order, and a separate `key` column leaves the reader joining two cells in their head. Abbreviate only
    where the abbreviation is CONVENTIONAL — `PK`/`FK` need no gloss; a framework `mac.*` token is the
    opposite case and law 2 governs it. And ONE RENDERER PER ARTIFACT KIND: the columns table
    lived in four places, so every change to it was made four times or three times and a bug.
    CONFORMANCE.md §2.4.
14. **A DERIVED PAGE IS BUNDLE CONTENT, and must match what its source renders.** A bundle is the unit
    of delivery; a page that is merely regenerable is reconstructable, not delivered (P11). In an
    ONTOLOGY repo the pages and the console-read projections are TRACKED — the one place an ontology
    repo takes the opposite rule from a code repo, on the operator's correction: *"ontology should by
    all means contain everything."* A report is still not bundle content. And a delivered page that
    disagrees with its source is a FAILURE, not a staleness to tidy later: measured 2026-09-28, a table
    change crossed the schema, a producer, four renderers and 28 references in three bundles while every
    delivered page still showed the old shape and thirteen invariants passed. `check_pages_current`
    re-renders into a copy and fails on any difference. CONFORMANCE.md §2.5.

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

### P9 — A CONCEPT WITHOUT A SAMPLE IS UNREVIEWABLE, AND I AUTHORED THREE WRONG DECLARATIONS
### THAT A SAMPLE WOULD HAVE SHOWN AT A GLANCE

**The rule.** Generate a sample for EVERY concept, from the columns that concept declares, before
believing any of its declarations. Not for the relation — for the CONCEPT: the same relation read
through two concepts is two different subsets, and the subset is the thing under review.

**Measured 2026-09-26, authoring example/contoso2's 19 concepts.** Three declarations were wrong in
a way no amount of re-reading the YAML revealed, and each one is visible in four rows of the
concept's own columns:

| what I declared | what the engine did | what the sample shows |
|---|---|---|
| `StoreStatus`: `StoreKey: { identity: canonical }` | `WHERE StoreKey = 'Closed'` — DuckDB refused to cast | `StoreKey` holds integers; `Status` holds `Closed`/`Restructured`. The identity is obviously the word column |
| `StoreStatus`: `identity.kind: code` | refused: *"nothing declares which code is StoreStatus's"*, missing `variant_code` | two coded values on a store row, not a measure discriminator on a tall fact |
| `Country`: `enum_from_register` on the code column | refused: *"No country named 'Germany' … compared with Country"* | `Country=DE` beside `CountryFull=Germany` — the word is in the OTHER column |

On the varchar case the first one is worse than an error: `WHERE <key> = 'Closed'` returns zero
rows and reads as an answer.

**PER CONCEPT AND NOT PER RELATION, and this is not a preference — it is the difference between
catching and missing.** example/contoso ALREADY HAS samples: 15 files under `data/samples/`, one per
relation, cut by the framework's own `mac_sample.py`. They would not have caught any of the three
defects above. `dim_contoso_store.sample.csv` shows all twelve columns of the store row, so a
reviewer of `StoreStatus` — a concept that declares TWO of them — cannot tell from it which two the
concept means, which is the entire question. Measured: the relation sample has 12 columns, the
concept sample has 2, and the defect lives in the choice between them.

**Why a sample and not a profile.** A profile counts (distinct, nulls, min, max) and a sample
SHOWS. The three defects above are all shape mismatches between a declared role and the values in
the column, and a count cannot make a shape visible. They are also exactly what a domain expert who
does not read YAML can review — which is the operator's standing complaint about every artifact
that names a thing without showing one: *"just the name is NOT example."*

**And it is the cheapest evidence in the estate.** Twenty rows per concept, one seeded query each,
free against a local warehouse. There is no argument for a concept that has never been looked at.

### P10 — AN EDGE THAT JOINS NOTHING LOOKS EXACTLY LIKE AN EDGE. PROJECT THE ER MODEL AND IT
### DOES NOT

**The rule.** Project the ER model from the DECLARED edges and draw only the ones that carry a
realization. An edge with neither a `join_rule` nor a `realized_by` is a line in a YAML file and
nothing in a query.

**Measured 2026-09-26, authoring example/contoso2.** I wrote 13 edges: 3 fact-to-dimension with a
`join_rule`, and 10 same-table ones — Country, Gender, AgeBand on the customer row; Brand, Color and
two categories on the product row; Status on the store row; Currency on the fact. All 13 parsed. All
13 read as edges. **Ten of them were inert**, because a same-table edge needs `realized_by:
"<relation>.<column>"` to name the column that realizes it, and I had written none.

Nothing said so until a question failed:

```
PlannerTemplateError: the qualifier(s) dim_contoso_customer are bound by nothing in its
FROM/JOIN clauses, which bind f
```

"Net revenue in Germany" needs the two-hop path fact -> Customer -> Country. The second hop could
not be traversed, so the dimension was never joined and the filter named a relation the query did
not bind. **An ER projection would have drawn 3 edges where the ontology claims 13**, and the gap
is the whole defect — visible in a glance at a picture, invisible in thirteen correct-looking YAML
blocks.

**AND THE PROJECTION IS WHERE A WRONG EDGE NAME BECOMES OBVIOUS TOO.** contoso carries
`order_line__denominated_in__currency`, whose name asserts the premise that each line's money is in
its own CurrencyCode — measured false on 2026-09-26 (the undiscounted cross-currency price ratio is
exactly 1.0, sd 0.0, on all ten pairs, against rate quotes spanning 0.6725..1.7253). A reader
skimming twenty-four edge blocks does not notice; a reader looking at a diagram labelled
*denominated in* does. Logged as OL-Q3.

**THREE REALIZATIONS, AND THE THIRD IS NOT A LOOPHOLE.** A first version of the gate accepted only
`join_rule` and `realized_by`, and flagged example/contoso's
`order_line__converts_at__exchange_rate` as inert. That edge carries no predicate DELIBERATELY, and
the bundle says why: the relationship is a three-clause conditioned join, and the single equality a
gate could measure (`OrderDate = Date`) returns 25 quotes for every one of the 223 974 lines — a 25x
fan-out that writes the exact defect the ExchangeRate concept's own rule forbids. So the realization
is the RULE that resolves it, and a gate demanding a predicate there would be demanding the defect.
`join_rule` · `realized_by` · `resolved_by` — and nothing else counts.

**AND THE GATE MUST NOT FAIL A WORKING BUNDLE.** Its first run reported 10 of contoso2's 13 edges
inert while every one of that bundle's 21 questions passed: `Edge.realized_by` is typed by the
grammar as a CANON BINDING, so a plain `"dim_contoso_customer.Country"` parses to an empty tuple and
the string lands in `realized_by_ref`. A gate that reds a bundle which demonstrably works is worse
than no gate, because the next person silences it. Read every shape the parser accepts.

**Why generated and never drawn.** The same reason as the member list and the sample: it is a fact
about declarations. A hand-drawn diagram is a claim that ages the moment an edge is added, and the
one thing it must be able to say — *this edge realizes nothing* — is exactly what an author
flattered by their own diagram will not draw.

### P11 — A PRODUCED FILE IS NOT A DELIVERED DELIVERABLE. DELIVER WHERE THE OPERATOR LOOKS

**The rule.** A deliverable is delivered when the operator can SEE it in the surface they use. A file
on disk that no reader consumes is work, not delivery — and reporting it as present is a false claim
about the state of the bundle.

**Measured 2026-09-26, twice in one hour, and both times the operator had to tell me.**

| I produced | I reported | what the operator saw |
|---|---|---|
| `data/lineage/lineage.json`, 13 nodes / 7 edges, measured from the engine | "lineage delivered" | *"i did not get lineage"* — the console renders `objects.json#lineage_graph`, which had **14 nodes and 0 edges** |
| a generated DQ suite, 86 cases, 86 PASS | "DQ tests executed" | *"DQ is completely empty"* — the board reads `data/quality/dq_dashboard.json`, built from a findings register that did not exist |

Both artifacts were real. Neither was where anything reads. The lineage graph needed
`data/transforms/*.yaml` (a `.sql` is the RECIPE; the descriptor is the declared claim, and only the
second is read), and the board needed a register of ISSUES — which a passing suite is not: **a suite
proves invariants HOLD; a register says what is WRONG and who must rule on it.**

**So a report must probe the CONSUMER, not the producer.** "`data/lineage/lineage.json` exists" is
not the question; "what will the page draw" is. The state report now reads `objects.json` and the
dashboard themselves and says *"0 EDGES — the view draws nothing"* when that is what is true.

---

### P12 — A WAREHOUSE THAT CARRIES ANOTHER ONTOLOGY'S MEANING PLANE WILL BE IMPORTED AS DATA

**The rule.** A bundle holds its own landings, its own transforms and its own warehouse. One relative
path is enough to lose that.

**Measured 2026-09-26.** A bundle's `connection.yaml` named
`../../../mac-ontology-contoso/contoso.duckdb`, and that warehouse carried the eight `meta_*`
relations the runtime emits so a planner can answer questions ABOUT an ontology. The import measured
them like any other relation: **32 artifacts**, including a sample file holding rows reading
`('AgeBand','enumeration')` — another bundle's CONCEPT NAMES presented as this one's data.

**And the worst outcome was still ahead.** The concept stage authors over the WHOLE relation
inventory. Asked what business notion `meta_concept` represents, the honest answer is *a concept* —
so the bundle would have grown an ontology ABOUT an ontology, from 21 rows of someone else's
declarations, with every gate passing.

Two things follow, and the second is the general one:
  * exclude the meaning plane at the entry point, deriving its names from the module that EMITS them
    so a ninth relation is covered the day it is added — and SAY SO when excluding, because a reader
    comparing 22 relations against 14 descriptors needs to know why eight are missing;
  * **a shared warehouse makes a bundle's state unprovable.** Re-run it a week later and a difference
    is unattributable. That is the reason for law 11, not tidiness.

---

### P13 — A GATE THAT FAILS A WORKING BUNDLE GETS SILENCED, AND ONE THAT SKIPS GETS BELIEVED

**The rule.** Before trusting a gate's verdict, run it against a bundle KNOWN to be correct. A gate
is a claim about other people's work and has to earn it.

**Measured 2026-09-26, building three gates in one afternoon — every one was wrong first:**

  * `check_er_projection` reported **10 of 13 edges INERT on a bundle whose every question passed**.
    `Edge.realized_by` is typed as a canon binding, so a plain `"relation.column"` parses to an empty
    tuple and the string lands in `realized_by_ref`. It also printed **"SKIP: no edges"** for a bundle
    with thirteen, because `index.edges` is a `Graph` with `edge_ids()`/`get_edge()` and no
    `.values()` — reporting SKIP where FAIL belongs is the one failure mode a gate must not have.
  * `check_bundle_isolation` produced **62 BREACHES** on rule pages linking their own concept as
    `../brand.md`, which resolves INSIDE the bundle; and reported **180 lines of prose** as naming
    another bundle because `example` is both a container name and an ordinary English word.
  * `check_measure_denomination`, broadened to catch any phrasing, **flagged the CORRECTION as the
    defect** — a fix contains the false claim's own words in order to deny it.

**And the deeper lesson from that last one:** prose cannot be gated. A regex tuned to one phrasing
misses its rephrasing; broadened, it cannot tell assertion from denial. That is not a tooling gap, it
is a property of prose — and it is the argument for flags over paragraphs (law 8's cousin).

**Give every gate a `--self-test` with seeded cases.** Mine caught two defects no bundle would have:
a pattern that captured only the FIRST `../` so every relative path resolved one level up whatever
its depth, and a comparison of a resolved path against an unresolved root, which on macOS makes
`/tmp` and `/private/tmp` disagree.

---

### P14 — FUNCTIONAL DEPENDENCE IS NOT A HIERARCHY, AND IT IS NOT A LABEL EITHER

**The rule.** "Each A maps to exactly one B" is satisfied by a PARENT, an ALIAS and a LABEL alike.
Whatever you concluded from it, measure the OTHER direction before acting.

**Measured twice, on different artifacts, from the same mistake:**

  * `finer_than` was pointed at `State`/`StateFull` on the strength of 608 and 563 distinct values.
    It is not a hierarchy: `CO` is Corse (FR), Como (IT) and Colorado (US) — 40 of 563 codes collide
    ACROSS countries and 0 within. What the data showed was a code needing a SCOPE, not a level.
  * a register cutter accepted `Year` as the LABEL of `YearQuarter`, because every quarter maps to
    exactly one year. `Year` is a coarser AXIS; a register built on it resolves "2024" to one quarter
    of four. Requiring the pairing to hold BOTH ways dropped four such registers and kept
    `Country` <-> `CountryFull`.

**And when a bijection IS found, which half is the CODE still has to be decided:** `DE` is the code
and `Germany` the label, and iterating in column order got it backwards. The code is the terser half.

---

### P15 — CONCEPTS ARE NEVER 1:1 WITH DATASETS, AND THE FIX IS THE DRIVER, NOT WITHHOLDING THE STAGE

**The operator, 2026-09-26, deleting an instruction I had accepted and repeated:** *"datasets DO NEVER
MATCH CONCEPTS 1:1 — concepts must SEARCH for business LOGIC in data and create it independent of
physical layer objects."*

**What the deleted instruction said, and why it was wrong.** The import pipeline printed *"concepts:
NOT RUN — onboarding stops at the data plane"*, justified by an outcome: a bundle came out at exactly
20 concepts over 20 datasets. That number is real and it is a defect OF THE DRIVER — the loop called
the model ONCE PER DATASET and named each file after the dataset stem, so 1:1 was true by
construction. A caller that asks *"what is the concept for THIS table"* can only be answered with one
concept per table.

Withholding the stage left that driver unfixed and moved the cost onto the operator, who then has to
ask for concepts — the very thing law 10 exists to end. **An unmarked guess and a withheld stage are
both worse than a labelled draft:** the first hides that a decision was made, the second hides that
one is needed. So the stage runs and writes `status: draft`.

**And a shape a loop can produce must be REFUSED BY A CHECK, not requested by a paragraph** — the
authoring prompt already said "A CONCEPT IS A BUSINESS NOTION, NOT A TABLE. The mapping is M:N" and
the loop produced 1:1 anyway. `check_concepts_not_per_table.py` fails a bundle only when all four hold
at once: as many concepts as datasets, every concept on one relation, no relation shared, no relation
declined. It never demands a NUMBER — a source whose notions genuinely align with its relations is
legitimate; arriving there without looking is not.

---

### P4 — ONE REGISTER PER DIMENSION, ENFORCED BY THE CUTTER

Two registers over one column WILL disagree, and nothing in the runtime arbitrates. A cutter must
refuse to write where a register already covers that source column, and say which file already
covers it.

### P8 — EVERY PRODUCED ARTIFACT NEEDS SOMETHING THAT PRODUCES IT

`setup.sh` built contoso's eight landing tables and stopped. The six
`CREATE OR REPLACE VIEW contoso_served.<name>` statements in `data/transforms/*.sql` — the
relations every dataset descriptor names in `produces.relation`, and every question reads — were
applied BY HAND, once, by someone. The database file is gitignored, so **a fresh clone ran the
setup script, got no served schema at all, and every question failed.**

The same law as P1 and P2 one plane down: a transform nobody runs is a declaration nobody reads.

**Rule: if a file describes something that must EXIST, find the thing that creates it from that
file. If there isn't one, that is the defect** — not the missing artifact.

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

0. **Cut a sample per concept BEFORE reviewing a single declaration** (P9). It costs one seeded
   query each, it is the only artifact that shows what a concept CONTAINS, and on 2026-09-26 it
   would have caught three wrong declarations that re-reading the YAML did not. Step zero because
   every step below is a claim about values, and this is the step that shows the values.
0b. **Project the ER model as soon as the edges exist** (P10), and read the count: an ontology
   claiming 13 edges and drawing 3 has ten that join nothing, which no amount of reading the YAML
   reveals.
0c. **Run the import and read its STATE REPORT before authoring anything** (law 10, P11). One command
   produces the data plane, the measurement plane, the referential structure, lineage, the registers,
   both quality suites and the DQ findings — measured on one bundle: 12 of 19 deliverables from
   nothing but a manifest and a connection. What it CANNOT produce it names, with the reason. Every
   declaration below is a claim about values, and this is the step that puts the values in front of
   you.
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
| P9 | every concept has a generated sample | **`check_concept_samples.py`** — every concept, its declared columns, and the sample's freshness against the ontology |
| P10 | the ER model is projected, and unrealized edges are reported | **`check_er_projection.py`** — every declared edge must carry a `join_rule`, a `realized_by` or a `resolved_by` rule |
| P11 | a deliverable is delivered where the operator LOOKS | **`mac_import.py --report`** — probes the CONSUMER (`objects.json`, the DQ dashboard), never the producer, and prints the reason for every absence |
| P12 | no bundle imports another's meaning plane | **`check_meaning_plane_not_imported.py`** across all 8 planes; **`mac_descriptors`** excludes them at the entry point and names them |
| P11/12 | two bundles share nothing | **`check_bundle_isolation.py`** — a path into another bundle is a BREACH under `ontology/`, and a path outside the bundle that is neither a bundle nor the framework is a portability finding |
| P13 | a gate is right before it is trusted | every gate ships `--self-test` with seeded cases, and is run against a bundle KNOWN to be correct before it is believed |
| P14 | a dependence is measured BOTH ways | `mac_lookups` requires a bijection before accepting a label; `finer_than` is repointed at a pair that holds |
| P15 | concepts are never per-table | **`check_concepts_not_per_table.py`** — fails only when all four clauses of the per-table shape hold at once |

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
| 4 | `axis.groupable` read by the prompt | **DONE** — 73 → 46 offered; `GROUP BY ZipCode` now POLICY_DENIED |
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

**Later the same day — C and A.**

*C, the axis ruling.* `field_role: attribute` means display-only, never filter or group, and two
places ignored it: the prompt OFFERED those columns (27 of 73) and the planner never read the role
at all, so `GROUP BY ZipCode` planned and would have executed — against DQ-CUSTOMER-02, which
measured that ZipCode alone singles out 29 193 of 104 990 rows. Now 46 columns offered, and a
forbidden axis is `POLICY_DENIED` naming what CAN be grouped on instead.

*A, the channel split.* The operator's ruling applied: `Channel` is derived in the store
transform, declared `closure: closed` with warranty **derived** — produced by a CASE expression,
so no watchdog is needed — and the country register's `--` row stops answering to the word
`online`. Measured after: `'online'` as a Country resolves to **nothing**, as a Channel to
**online**, and *"in how many countries do we sell"* answers **8** where it answered 9.

*And the gap underneath both.* Fixing A meant editing a transform — which exposed that nothing
ever ran the transforms. P8.
