---
title: The rule engine — a declared rule fires, and selects which rows a concept HAS
status: implemented in mac-runtime (planner/populations.py · canons/population_select.py · planner/predicates.py); the bodies are READ, lowered to bound SQL and disclosed
audience: ontology authors
scope: GENERIC — domain-neutral. Every measurement from example/contoso5, 2026-10-01.
companions: [canon/population_select.md, identity_and_rules.md, column_specification.md, canon_library.md]
---

# The rule engine

> **Paths in this document.** `planner/…`, `interpret/…` and `canons/…` are under
> `mac-platform/packages/mac-runtime/src/mac_runtime/`; `packages/…` is under `mac-platform/`;
> `data/…` and `ontology/…` are inside the bundle (`example/contoso5`). A `:line` suffix is the
> line the measurement was read at.


> A contract rule with an **executable body** acts like a database trigger. Its `binds` is the
> CONDITION; its body is the ACTION; the action selects **which rows the concept has for this
> question**. Until 2026-10-01 such a statement could only be prose in a rule's `then:`, and nothing
> executed it.

Operator framing, 2026-10-01, which `planner/populations.py:3-6` quotes and implements literally:

> i will want to have rule act like DB trigger. if the condition is met ... then something should
> happen ... and then system must be able to act accordingly if trigger has established that a
> condition on specific column must be not null in order to fetch the data.

This page is the **authoring** surface. The pure decision it calls is specified in
[`canon/population_select.md`](canon/population_select.md); the rule vocabulary it lives inside is
[`identity_and_rules.md`](identity_and_rules.md).

---

## 1. The problem: a state that is a column COMBINATION

A business state is often not a stored value.

| the state | what actually says it | does any column hold the word? |
|---|---|---|
| a store is **closed** | `close_date IS NOT NULL` | no |
| a sale is **online** | its store's `location_code = -1` | no |
| a country is **real** | `country_code <> '--'` | no |

That fact has **no home on a concept** (it does not say what a store *is*) and **none on an edge**
(it joins nothing). It is a statement about which rows the concept HAS under a given reading — so it
is a rule, and a rule's body is a canon (`canons/population_select.py:1-7`).

### The defect this removed, measured

Store declared one predicate, `grounding.value_filter: close_date IS NULL AND location_code <> -1`,
and the runtime applied it inviolably. So *"How many stores are closed?"* planned **perfectly** —
`status_annotation = 'Closed'`, the right column, the right bound value — and then had
`close_date IS NULL` ANDed onto it.

```sql
-- measured against contoso_served, 2026-10-01
SELECT count(*) FROM dim_store WHERE status_annotation='Closed'                        -->  9
SELECT count(*) FROM dim_store WHERE status_annotation='Closed' AND close_date IS NULL -->  0
```

A closed store always carries a close date, so the conjunction can never be true: **0 rows, every
stage green, against a truth of 9** (`planner/populations.py:13-26`).

---

## 2. Two statements, applied differently

A concept can say two different things about its own rows, and conflating them is the defect above.

| | `grounding.value_filter` | a population rule |
|---|---|---|
| it is | the **unaskable DOMAIN** — rows that are not this concept's at all | a **DEFAULT READING** — what the concept means unqualified |
| applied | always, unconditionally (`planner/sql.py:1419-1436`) | unless the question speaks about the same columns (`planner/sql.py:1442-1455`) |
| a question may ask the other side of it | **no** | **yes** |
| disclosed | yes, as "rows outside it are not this concept's" | yes, as which population applied and which were available |

> **The test.** *Can a question legitimately ask for the rows this predicate removes?* If yes it is a
> **default**, not a domain. Store declared `close_date IS NULL AND location_code <> -1` and now
> declares **no `value_filter` at all** — both clauses were default readings. `close_date IS NOT NULL`
> is 16 rows a question may ask for, and the single `location_code = -1` row carries
> **86 790 054,13** of revenue, 39,7 % of the bundle's 218 814 471,66.

Measured on contoso5 today: `grep -rn '^\s*value_filter:' ontology/` returns **nothing**. The slot is
still read; this bundle simply has no unaskable rows.

---

## 3. The authoring surface

Two rules on `Store` (`example/contoso5/ontology/concepts/store.yaml:170-263`, bundle-relative),
because Store carries **two orthogonal states**:

```yaml
contract:
  rules:
    # ---- axis 1: the trading state -----------------------------------------
    - id: store.resolution.active_is_the_absent_close_date
      kind: mac.concept.rule.resolution
      confidence: C
      binds: [close_date, status_annotation]        # <- THE CONDITION
      why: >
        two columns state one thing; a person ruled the close date is the truth on 2026-09-30
      realized_by:
        - udf: mac.canon.population_select
          params:                                   # <- THE ACTION
            default: active
            populations:
              active:       {all: [{column: close_date,        op: is_null}]}
              ended:        {all: [{column: close_date,        op: is_not_null}]}
              closed:       {all: [{column: status_annotation, op: eq, value: Closed}]}
              restructured: {all: [{column: status_annotation, op: eq, value: Restructured}]}

    # ---- axis 2: the channel, same relation, independent of axis 1 ----------
    - id: store.resolution.the_channel_is_the_location_sentinel
      kind: mac.concept.rule.resolution
      confidence: P
      binds: [location_code]
      why: >
        the sentinel row has no country and no floor, and as the single largest "store" it sits at
        the top of every list it is allowed into
      realized_by:
        - udf: mac.canon.population_select
          params:
            default: physical
            populations:
              physical: {all: [{column: location_code, op: ne, value: -1}]}
              online:   {all: [{column: location_code, op: eq, value: -1}]}
```

| slot | what it is | read by |
|---|---|---|
| `binds` | **the trigger condition** — the columns this state is stated by | `planner/populations.py:164-171` |
| `realized_by[].udf` | `mac.canon.population_select` | `planner/populations.py:134` |
| `params.populations` | name -> predicate (`all:` of clauses) | `planner/populations.py:144-147` |
| `params.default` | the name that applies when the question says nothing; **optional** | `planner/populations.py:148-154` |
| `why` | the only prose a bodied rule keeps | nothing executes it; the model reads it |

Nothing here is invented vocabulary: `realized_by` is the only declared door onto a contract rule
(`ContractRule` is `extra="forbid"` with eight fields), `canonRef.params` is deliberately untyped,
and the canon registry is `closed: false` — *"extends as patterns surface new deterministic needs"*
(`mac_vocabulary.yaml:915`). The registry entry is `mac_vocabulary.yaml:994-1001`; the runtime's
claim to honour it is `mac_runtime/canon.py:45-53`.

---

## 4. The eight rules an author must get right

### R1 — `binds` IS the trigger condition, not a second list beside it

A question constraining a bound column is **making its own statement** about that state, so the
default steps aside and the answer discloses it (`canons/population_select.py:93-97`).

The first cut declared `about: [close_date, status_annotation]` next to an identical
`binds:`. Operator ruling: *"this is redundant and unnecessary"*
(`planner/populations.py:155-163`). Reusing `binds` also inherits validation **for free**: the
framework shape `rule-binds-grounded` (`mac_shapes.yaml:94-99`) already resolves every bound column
against the PHYSICAL layer cross-file. A new key would have had none.

**Why it must be DECLARED and cannot be inferred.** The first attempt compared *column names* — drop
a conjunct when the question names a column that conjunct mentions. Measured, it cannot work: the
question constrains `status_annotation`, the declaration constrained `close_date`, the intersection is
**empty**, so nothing fired and the contradiction shipped. Those two columns are two statements of
ONE fact, and no reader derives that from their names (`planner/sql.py:1412-1418`,
`planner/populations.py:40-45`).

### R2 — one rule is one AXIS; axes are independent

Store has two. `select()` is asked **once per rule** and returns a list
(`planner/populations.py:207-250`). Default-suppression is keyed on `(concept, rule_id)` —
**per axis, not per concept** (`planner/plan.py:671-679`); keying it on the concept silenced both, so
*"revenue from the online store"* would have dropped the active-store default too.

**The measurement that makes this concrete, and it corrects a number.**

```sql
close_date IS NULL                                      -->  58   -- `active` ALONE
close_date IS NULL AND location_code IS DISTINCT FROM -1 -->  57   -- both defaults, one per axis
```

The sentinel row has **no close date**, so it is an `active` store too. The familiar **57** is not
what `active` selects — it is `active ∧ physical`, two independent axes each applying its own
default. The comment at `data/references/store.yaml:249` ("57 rows, 57 locations") describes the composition, not
the predicate beside it.

### R3 — `default:` is optional, and its absence is a declaration

No default means **this axis has no "unless told otherwise" reading**, so a question silent about it
means the whole range. `select()` skips such a rule outright
(`planner/populations.py:222-226`); `by_name()` still reaches its populations, so they stay askable.

### R4 — a named population is matched EXACTLY, never fuzzily

Folding is case, spaces and underscores and nothing else (`canons/population_select.py:48-50`;
`planner/populations.py:271-274`). The reason is a measurement, not a preference:

```
activ      -> active    0.9091   typo               (difflib.SequenceMatcher)
neaktivan  -> aktivan   0.8750   antonym, Croatian
inactive   -> active    0.8571   antonym, English
```

The **typo sits between the two antonyms**, and substring containment holds for all three. No
threshold and no affix rule separates them, and an affix rule would be English-only anyway. So the
guard is **structural**. A typo costs one clarification turn; the alternative is answering `inactive`
with the `active` rows, which is the opposite of the question.

A population name is also checked **before** any value ladder
(`canons/population_select.py:85-91`; `planner/plan.py:1575-1577`), so it cannot lose a tie to a
coincidental value match. Measured: `online` resolved as a *value* to four candidates at score 1.0
and **not one was the channel** — the sentinel country code `'--'` on three concepts, and `'Online'`
on a state column (`planner/plan.py:1554-1558`).

### R5 — no `when:`/`then:`/`never:` on a rule that HAS a body

Operator ruling, 2026-10-01: *"i believe there is no reason anymore for when then never"*. The body
states the condition and the action **executably**; prose beside a body is a second home, and the
prose home is the one that rots without anything noticing.

**MEASURED on that very rule.** Its `never:` read *"read `{status_annotation}` as the state. It is
empty on all 58 rows that never closed"* — true when written, **FALSE** after the impurity fix of
2026-10-01 filled the Utah row, and no gate caught it (`data/references/store.yaml:209-221`). It was corrected by
hand hours later, only because a human re-read it.

> **There is still no gate for this.** `tools/check_canon_binding.py:141-146` compares a rule's prose
> against what its canon RENDERS — but the render registry is `tools/canon/rules.py:175-179`, three
> canons, and `population_select` is not one of them (it is a *decision*, not a renderer). A
> population rule's prose is outside every drift check today. See *what is owed* in the protocol.

**`why:` STAYS, and is not redundant.** No predicate encodes *"a person ruled this, on this date,
against this measurement"*. Prose survives exactly where there is no body: `Country`'s
`never: report nine countries` was kept for that reason (`ontology/concepts/country.yaml:143-149`), and so was
`Location`'s remaining prose.

### R6 — structure, not SQL text, and this is not a style choice

`adapters/safety.py:46-53` refuses **any** raw single-quoted literal in a plan's SQL. Run it over the
two forms:

| predicate, as written | gate |
|---|---|
| `(dim_store.close_date IS NULL AND dim_store.location_code <> -1)` | PASS — *only* because `-1` is numeric |
| `(dim_country.country_code <> '--')` | **REFUSE** `unbound_literal` |
| `(dim_store.status_annotation IN ('Closed','Restructured'))` | **REFUSE** `unbound_literal` |
| `(dim_store.status_annotation IN (:a, :b))` + params | PASS |

(Reproduced against the real `assert_bound_params_only`, 2026-10-01; the same four cases are pinned
by `packages/mac-runtime/tests/test_planner_predicates.py:103-112`.)

So a string-valued predicate written as **text** is *unexecutable*: it plans cleanly and dies at the
adapter. Measured on this bundle today: **10 populations are declared, 4 of them string-valued**
(`closed`, `restructured`, `real`, `sentinel`), 4 numeric and 2 needing no value at all. Structure is
the only form that can carry a string.

> The figure "five of ten" in `planner/predicates.py:12` and `canon/population_select.md:150` counted
> `inactive`, which was removed the same day (`data/references/store.yaml:257-263`). Today's measured count is **4 of
> 10**. Recorded rather than edited — the file is another agent's.

There is also **deliberately no slot** that accepts SQL text. A clause carries `column`, `op`, and
either `value` or `values`, and an unknown key refuses with those words
(`planner/predicates.py:139-148`). That forgery bound is what makes a predicate safe to **show a
model**: it can read what a named population means without being able to write one
(`planner/predicates.py:29-33`).

### R7 — `ne` lowers to `IS DISTINCT FROM`, and `not_in` keeps the NULLs

A person saying "not X" means "not X, **including the rows with no value**". Measured on
`dim_store.status_annotation`, which has exactly one NULL row (it is the online sentinel):

| form | rows |
|---|---|
| `status_annotation <> 'Restructured'` | 66 |
| `status_annotation IS DISTINCT FROM 'Restructured'` | **67** |
| `status_annotation NOT IN ('Closed','Restructured')` | 57 |
| `status_annotation IS NULL OR … NOT IN (…)` | **58** |

One-row differences, valid SQL, plausible integers, and **nothing in the answer to mark them** — the
grammar's `negation_over_nullable`, *"the worst class in this file: the other gaps refuse, this one
answers"*. A text predicate ships whichever the author happened to type. A structured `op: ne` is
lowered through one table where the ruling is made **once** with its measurement beside it
(`planner/predicates.py:17-27`, `234-247`).

### R8 — every population must only test columns its rule `binds`

An invariant, not a convenience: a population testing an unbound column **could never be displaced**
by a question about that column, so the trigger would be silently blind on exactly the axis it claims
to own. Enforced at read time with the refusal spelled out (`planner/populations.py:186-194`); stated
purely as `stray_columns()` (`canons/population_select.py:105-119`).

---

## 5. The predicate language

Six operators and no more (`planner/predicates.py:44-47`, `64-67`).

| `op` | value slot | lowers to | source |
|---|---|---|---|
| `is_null` | none | `col IS NULL` | `planner/predicates.py:227-228` |
| `is_not_null` | none | `col IS NOT NULL` | `planner/predicates.py:229-230` |
| `eq` | `value:` (one) | `col = :p` | `planner/predicates.py:231-232` |
| `ne` | `value:` (one) | `col IS DISTINCT FROM :p` | `planner/predicates.py:234-237` |
| `in` | `values:` (list) | `col IN (:p0, :p1, …)` | `planner/predicates.py:238-240` |
| `not_in` | `values:` (list) | `(col IS NULL OR col NOT IN (:p0, …))` | `planner/predicates.py:241-247` |

**No `gt/gte/lt/lte`**, no column-to-column comparison, no `expr`, no `sql`, no `function`. Every
threshold in the worked corpus is in the QUESTION, where `FilterOp` already has them, and a
population is a **membership** statement rather than a magnitude one.

### The shape

```yaml
all:                                   # mandatory, even for ONE clause
  - {column: close_date,        op: is_null}
  - {column: location_code,     op: ne,     value: -1}
  - {column: status_annotation, op: in,     values: [Closed, Restructured]}
```

`all:` is required at one clause too. `oneOf[clause, {all: [clause]}]` would be two spellings for one
fact, and adding a second clause would force the author to restructure the first
(`planner/predicates.py:41-42`).

- **Conjunctions only.** `in` is the same-column disjunction. An `any:` block is a **declared gap**:
  admitting one costs the narrow answer to *"which clause did the question contradict"*.
- **Members are de-duplicated, order preserved** (`planner/predicates.py:187-190`) — a duplicate
  would bind the same value twice and make the SQL byte-unstable across authorings.
- **A null test binds nothing**, enforced from both sides: `assert_bound_params_only` refuses a
  dangling placeholder *and* an orphaned param (`adapters/safety.py:55-71`), so a dummy
  `:p = None` for an `IS NULL` would be caught as an orphan.

---

## 6. How a question reaches a population

Three stages, in this order. Nothing reads a row to decide any of it: the condition is tested against
the **INTENT** and the **DECLARATIONS**, because no SQL may run to decide which SQL to write.

| # | stage | where | what happens |
|---|---|---|---|
| 1 | the question **NAMED** a population | `planner/plan.py:1575-1602` | `by_name(concept, filter.value)` then `by_name(concept, filter.term)`. The population's predicate **IS** the filter; no value resolution happens at all |
| 2 | the trigger fires, per axis | `planner/plan.py:647-690` (**step 4d**) | `populations.select(concept, constrained_columns=…)` -> the default, or the disclosure that the question displaced it. Axes named at stage 1 are skipped |
| 3 | render | `planner/sql.py:1442-1455` | `by_default=True` -> the predicate joins the WHERE, bound. **Every** selected population contributes its `disclosure`, applied or displaced |

**Step 4d sits BEFORE `assemble_plan` for a structural reason**: that function is typed `-> Plan` and
cannot return a `Clarification` or a `Refusal`, and a population decision may need to ask. Deciding it
there is what made the old inline override unable to do anything but guess
(`planner/plan.py:660-662`).

**The question may name a population in either intent slot.** `{term: Store, value: Closed}` puts it
in the value; `{term: closed, value: true}` puts it in the term and leaves a meaningless boolean
behind. Both are real intents the model produced for *"How many stores are closed?"* on the same
bundle, hours apart — and both must take the same route, or the answer's SQL depends on which
phrasing the model chose (`planner/plan.py:1565-1573`).

**Naming scopes the match.** A value is matched only against populations declared by the concept the
TERM resolved to, so a population name cannot capture a question about a different concept
(`planner/plan.py:1560-1565`).

### The decision table (the canon's guarantee)

| the question | the selection |
|---|---|
| named a population | that one, matched **exactly** |
| constrained a column in `binds` | **none** — the question's own statement governs; `displaced_by` names the columns |
| neither | the `default`, if one is declared |
| neither, and no `default` | none — this axis has no "unless told otherwise" reading |

### What the reader is told

Three disclosure forms, one per outcome (`planner/populations.py:81-101`). Each names the **other**
populations, under the standing rule *expose the granularity, never narrow silently*:

- applied by default — *"Store was read as its DEFAULT population 'active' (close_date IS NULL),
  declared by store.resolution.active_is_the_absent_close_date. The question named no state, and the
  other populations declared are: closed, ended, restructured."*
- named by the question — *"… which the question named and `<rule_id>` declares. The others are: …"*
- displaced — *"Store's default population was NOT applied: the question constrains
  `status_annotation`, which `<rule_id>` declares this concept's state is stated by, so the question's
  own statement governs."*

---

## 7. The worked bundle, measured

`example/contoso5/contoso5.duckdb`, schema `contoso_served`, 2026-10-01, via
`mac-platform/.venv/bin/python`. **Ten populations across four axes on three
concepts** — every one of them lowered through `predicates.parse` + `predicates.lower` and passed
through the real adapter gate.

| concept | axis (`rule_id` tail) | `binds` | population | predicate | rows |
|---|---|---|---|---|---|
| Store | `active_is_the_absent_close_date` | `close_date`, `status_annotation` | **`active`** (default) | `close_date IS NULL` | 58 (**57** with `physical`) |
| Store | ″ | ″ | `ended` | `close_date IS NOT NULL` | 16 rows / 14 locations |
| Store | ″ | ″ | `closed` | `status_annotation = 'Closed'` | 9 |
| Store | ″ | ″ | `restructured` | `status_annotation = 'Restructured'` | 7 rows / 6 locations |
| Store | `the_channel_is_the_location_sentinel` | `location_code` | **`physical`** (default) | `location_code IS DISTINCT FROM -1` | 73 |
| Store | ″ | ″ | `online` | `location_code = -1` | 1 |
| Location | `the_online_row_is_not_a_place` | `location_code` | **`physical`** (default) | `location_code IS DISTINCT FROM -1` | 66 |
| Location | ″ | ″ | `online` | `location_code = -1` | 1 |
| Country | `sentinel_is_not_a_country` | `country_code` | **`real`** (default) | `country_code IS DISTINCT FROM '--'` | **8**, not 9 |
| Country | ″ | ″ | `sentinel` | `country_code = '--'` | 1 |

Revenue (`SUM(v_contoso5_sales_line.net_amount)`, joined on `store_key`):

| population | revenue |
|---|---|
| `online` (1 row) | **86 790 054,13** — 39,7 % of the bundle |
| `closed` stores | **2 870 369,00** |
| `active ∧ physical` | 128 818 965,21 |
| all rows | 218 814 471,66 |

### One fact, three bodies — and they are NOT duplicates

The sentinel is written into **three relations**, each with its own column and its own row:
`dim_store.location_code = -1`, `dim_location.location_code = -1`, `dim_country.country_code = '--'`.
A population selects the rows of the relation it is declared on and nothing else, so three relations
need three bodies (`ontology/concepts/country.yaml:155-161`).

What **was** duplicated were the **three prose statements** on a `Channel` concept. That concept and
its edge `order__through__channel` were deleted on 2026-10-01 — operator ruling: *"if channel has no
reason for being ... then lets remove it"*. The edge declared no join key and pointed at a prose rule,
so it was never emittable: the only path was `NetRevenue -> Customer -> Order -> Channel`, and the
assembler refused the plan because `dim_store.location_code` landed in the WHERE with nothing binding
`dim_store` (`ontology/edges.yaml:20-32`). Nothing was lost: `dim_store` is reached in **one**
emittable hop by `net_revenue__by__store`.

---

## 8. What refuses, and what it says

Nothing is inferred. A malformed predicate refuses **naming the declaration it came from**, because a
predicate that half-applies is a wrong population reported as a right one
(`planner/predicates.py:106-108`).

| what you wrote | the refusal says | source |
|---|---|---|
| a predicate with no `all:` | *"A predicate is a conjunction: `all: [{column: …, op: …}]`"* | `planner/predicates.py:110-117` |
| a key beside `all:` | *"a predicate carries `all:` and nothing else"* | `planner/predicates.py:118-124` |
| `all:` empty or not a list | *"must be a non-empty list of clauses"* | `planner/predicates.py:126-130` |
| a clause key outside `column`/`op`/`value`/`values` | *"There is deliberately no slot for SQL text"* | `planner/predicates.py:139-148` |
| no `column` | *"names no column"* | `planner/predicates.py:151` |
| an operator outside the six | *"A threshold belongs in the question, where the grammar already has one"* | `planner/predicates.py:152-160` |
| `value:` on a null test | *"is a `<op>` test and takes no value"* | `planner/predicates.py:162-168` |
| `values:` on `eq`/`ne` | *"takes exactly one `value`, not `values`"* | `planner/predicates.py:169-175` |
| `value:` on `in`/`not_in` | *"takes `values:` (a list), not a single `value`"* | `planner/predicates.py:176-181` |
| `values: []` | *"must be a non-empty list"* | `planner/predicates.py:182-186` |
| a column the relation does not declare (at lowering) | lists the declared set | `planner/predicates.py:219-225` |
| the canon bound with no `populations:` | *"declares no `populations:` mapping"* | `planner/populations.py:139-143` |
| `default:` naming an undeclared population | *"which it does not declare. Declared: …"* | `planner/populations.py:148-154` |
| the canon bound with no `binds:` | *"`binds` is its trigger condition"* | `planner/populations.py:165-171` |
| a `binds` column the relation does not declare | lists the declared set | `planner/populations.py:179-185` |
| a population testing a column outside `binds` | *"or a question about those columns could never displace it"* | `planner/populations.py:186-194` |
| a population name compared with `>`/`<`/`between` | *"A population is a set of rows: a question is either in it or not."* | `planner/plan.py:1579-1588` |

---

## 9. Two supporting mechanisms built the same day

### `planner/column_types.py` — the type gate

`assert_bound_params_only` proves every value travels as a `:name` placeholder. It says **nothing**
about whether the value makes sense for the column. Two live defects passed it:

| | what shipped | why it was silently wrong |
|---|---|---|
| RC08 | `WHERE dim_store.store_key = :store`, `{'store': True}` | `store_key` is declared `integer`; DuckDB coerces `TRUE` to `1`; no key is 1 -> **0 rows, every stage green**, against a truth of 9 |
| MQ-07 | `WHERE v_contoso5_sales_line.store_key = :channel`, `{'channel': 'online'}` | same declared-integer key; **86 790 054,13** reported as `no_value` with `disclosures: []` |

`fits(value, declared)` answers `True` / `False` / `None` — `None` meaning *the declared type is one
this module has no opinion about*, which is not a violation, because an opinion without evidence is a
guess (`planner/column_types.py:99-143`). Two orderings are load-bearing:

- **bool before numeric.** `isinstance(True, int)` is `True` in python, so a naive numeric test passes
  a bool onto an integer key — exactly RC08 (`planner/column_types.py:112-116`).
- **a float with no fraction is an integer.** `FilterRef.value` is typed `str | float | bool |
  list[str]` with **no `int` member**, so pydantic turns the model's `630` into `630.0` before the
  planner sees it. `630.5` onto an integer column still refuses (`planner/column_types.py:124-132`).

Only the **DIRECTLY** compared column is checked — the operand must *be* a column, never contain one.
The first cut read `HAVING COUNT(DISTINCT orders.order_id) >= :threshold` as a comparison against
`order_id` and refused a threshold of `10.0` (`planner/column_types.py:180-212`).

It refuses in the **planner**, not the adapter: the planner has the declared types through
`Grounding.serving_columns[].type`, `ExecutablePlan` carries none; and a question that cannot be
answered correctly deserves a `Refusal` naming the concept and the column, not an `AdapterError`
(`planner/column_types.py:24-32`). It fires after the SQL transforms, beside `check_sql_guards`
(`planner/plan.py:745-757`).

**`fits()` has one home.** `mac-console/src/mac_console/trace_losses.py:38-47` **imports** it rather
than keeping a second table, so a trace diagnosis and a planner refusal cannot disagree.

### `planner/resolve.py` — `ResolvedTerm`, so the resolution survives the return

The resolver had already worked out the answer and **dropped it on the return statement**. Asked
*"How many stores are closed?"* it matched `closed` EXACTLY —
`Candidate(identity='Closed', concept='Store', column='status_annotation', score=1.0)` — wrote both
into the capture's `resolutions` block for a human to read, and returned the bare `Concept`. With no
column to place the predicate on, the planner fell back to the identity column and emitted
`dim_store.store_key = :store` with `{'store': True}` (`resolve.py:137-168`).

`ResolvedTerm(concept, candidate)` now carries `.column` and `.identity` through
(`resolve.py:159-168`, returned at `resolve.py:202` and `211`). `.concept` is what every existing
caller wanted and keeps getting. The planner reads them at `planner/plan.py:1628-1645` (the
`{term: closed, value: true}` case, narrow on purpose — **only a bool**, and only when the term
matched ON a column the concept declares) and at `planner/plan.py:1686-1687` (value's column first, term's
second). **The fix is not new machinery; it is not throwing the answer away.**

---

## 10. Staleness: a capture is evidence about the DECLARATIONS that produced it

Two fixes, because a rule engine that moves the declarations makes every stored answer a claim about
a model that no longer exists.

| fix | where | why |
|---|---|---|
| `reference/` joined the acceptance fingerprint | `sdk/acceptance/bundleio.py:128-136` | fourteen approved answers were written and the hash did not move (`b9167f36ed15449f` before and after) — the board read 25 pass / 16 fail with **no `evidence_stale` anywhere** |
| `evidence_stale` now compares the **ontology** fingerprint too | `sdk/acceptance/flags.py:140-149`, `1304-1326` | it compared only the acceptance plane, so a capture produced by an ontology that no longer exists graded as current |

Measured read-only on contoso5, 2026-10-01 (a corpus run was writing captures at the time, so this is
a point-in-time reading): **83 questions, 83 captures, 165 `evidence_stale` warnings** — 83 on the
acceptance plane and **82 of 83** on the ontology plane, which is the comparison that did not exist
this morning. The captures carry ontology `306429bf9cdd8a02`; the bundle now reads
`3bc7b5d247d0eab2` — the populations, the `value_filter` split and a deleted concept between them.

`ontology_fingerprint` is optional and `None` means *do not check*, so a caller that cannot supply it
behaves exactly as before rather than raising a warning it has no basis for
(`flags.py:147-149`).

---

## 11. Authoring checklist

```
1. Is this predicate one a question may legitimately ask the OTHER SIDE of?
     yes -> a population rule.  no -> grounding.value_filter (the unaskable domain).
2. How many INDEPENDENT states does this relation's rows carry?  One rule per state.
3. For each rule:
     binds:        every column this state is stated by — this is the trigger
     populations:  one name per reading, each `all:` of {column, op, value|values}
     default:      the unqualified reading — or omit it, and mean the whole range
     why:          the person, the date, the measurement.  No when/then/never.
4. Every population tests ONLY columns the rule binds.           (R8)
5. No synonyms: two names for the same rows is the drift this removes.
6. Nothing is written as SQL text.                                (R6)
7. Measure every population's row count and put it beside its line.
```

**No synonyms.** `inactive` was declared as `status_annotation IN (Closed, Restructured)` beside
`ended` as `close_date IS NOT NULL` — and measured, those select the **same 16 rows with zero
disagreements**. Two names and two predicates for one set is exactly the drift this mechanism exists
to remove: the day they stop agreeing, two questions that mean the same thing answer differently and
nothing says why. `inactive` is a **surface** for `ended`, which is a synonym question and belongs to
the reader that shows the model the names (`data/references/store.yaml:257-263`).

---

## 12. Determinism & honest limits (AUTHORING A5)

- **Deterministic.** Same declaration + same constrained columns + same asked word -> same selection.
  The decision is pure: no ontology types, no I/O, no SQL (`canons/population_select.py:67-102`).
- **Reads no rows, ever.** The condition is tested against the INTENT and the DECLARATIONS.
- **Inert on a bundle that declares nothing.** A concept that binds no population canon is unchanged
  in every respect — that is what made this shippable (`planner/populations.py:125-127`).
- **It selects; it does not render.** Lowering to bound SQL is `planner/predicates.py`.
- **One rule is one axis.** It cannot express a dependency *between* axes ("online stores are never
  restructured"); that would be a constraint, not a population.
- **Conjunctions only.** `any:` is a declared gap, not an oversight.
- **A column declared only in `serving_columns` cannot be bound today.** `_read_all` resolves `binds`
  against `field_roles | served_columns` (`planner/populations.py:176-178`) while lowering accepts three homes
  (`sql.py:1921-1928`). An asymmetry, not a design.
- **Three exported pieces of the canon are unreached by the runtime.** `fold()` and `stray_columns()`
  have **zero callers**, and `population_select`'s `asked=` parameter is never passed:
  `planner/populations.py` re-implements the folding inline at `271-274` and the stray-column check
  inline at `186-194`, and naming goes through `by_name()` instead of `asked=`. Two homes for two
  invariants, in the mechanism built to remove exactly that. Recorded in
  [`decisions/PROTOCOL-2026-10-01_rule-engine.md`](../decisions/PROTOCOL-2026-10-01_rule-engine.md).
- **No test covers the canon directly.** `grep -rn population_select packages/*/tests/*.py` returns
  nothing; `packages/mac-runtime/tests/test_planner_predicates.py` (11 tests) covers the predicate language and
  `packages/mac-runtime/tests/test_planner_value_column.py` the naming route. The pure decision is exercised only through them.
