# PROTOCOL — 2026-10-01 · the rule engine: a declared rule that fires and selects rows

**Written because the operator asked for it: "i want one agent to protocol and document ALL what is
relevant as documentation user manual".** Everything below is measured, quoted, or carries a
`file:line`. Where a number appears, the command that produced it is nameable. Where I could not
verify something, it says so.

**The user manual is [`reference_manual/rule_engine.md`](../reference_manual/rule_engine.md)**; the
canon's contract page is [`reference_manual/canon/population_select.md`](../reference_manual/canon/population_select.md).
This record is the decision trail behind them.

**Paths.** `ontology/…`, `data/…` and `acceptance/…` name files of the applied bundle
(`<sources>/example/contoso5`, where `<sources>` is the private bundle-sources repository).
`packages/…` names mac-platform. Bare `reference_manual/…`, `sdk/…`, `tools/…` name this repository.

---

## PART 1 — THE DAY'S VERDICT, IN THE OPERATOR'S WORDS

> i will want to have rule act like DB trigger. if the condition is met ... then something should
> happen ... and then system must be able to act accordingly if trigger has established that a
> condition on specific column must be not null in order to fetch the data. **this must be doable
> with symbolic language and having null or not null test is good first step**

And on the shape of the declaration:

> i believe there is no reason anymore for when then never

And on the first cut's extra key:

> this is redundant and unnecessary

And on the concept that held the duplicated fact:

> if channel has no reason for being ... then lets remove it

A rule's prose was never executed. The estate's 28 contract rules were 7 % bodied and nothing read
the bodies it had. A business state that is a **column combination** — `closed` IS
`close_date IS NOT NULL` — had no home anywhere: not on a concept (it does not say what a store *is*),
not on an edge (it joins nothing). So it was written as prose in a `then:`, and prose is re-inferred
by whoever reads it next.

---

## PART 2 — WHAT WAS DECIDED

### The mechanism

```
ontology (a contract rule)              runtime
────────────────────────────            ──────────────────────────────────────────────────────────
binds: [close_date, …]        ←── THE CONDITION ──→  planner/populations.py:164-171
realized_by[].udf:                                   planner/populations.py:134
  mac.canon.population_select
  params:
    populations: {name: {all: […]}}  ← THE ACTION →  planner/predicates.py        (parse + lower)
    default: active                                  canons/population_select.py  (the PURE decision)
why: "a person ruled this, on …"                     nothing executes it; the model reads it
```

| file | what it owns | lines |
|---|---|---|
| `packages/mac-runtime/src/mac_runtime/planner/predicates.py` | the symbolic predicate language: 6 operators, `all:` conjunction, **no slot for SQL text**, values BOUND | 253 |
| `packages/mac-runtime/src/mac_runtime/canons/population_select.py` | the PURE decision — `Selection`, `population_select`, `stray_columns`, `fold`. No ontology types, no I/O, no SQL | 122 |
| `packages/mac-runtime/src/mac_runtime/planner/populations.py` | reads the declaration off a Concept, multi-axis, and lowers the chosen predicate | 327 |
| `packages/mac-runtime/src/mac_runtime/planner/plan.py` | **step 4d**, the firing point (`647-690`), and the naming route (`1550-1602`) | — |
| `packages/mac-runtime/src/mac_runtime/planner/sql.py` | renders the applied population and every disclosure (`1442-1455`) | — |
| `mac_vocabulary.yaml` | the registry entry `canon.terms.population_select` (`994-1001`) | — |
| `reference_manual/canon/population_select.md` | the canon's contract page | 162 |
| `packages/mac-runtime/src/mac_runtime/canon.py` | the `IMPLEMENTED` claim (`45-53`) | — |

**Nothing was invented.** `realized_by` is the only declared door onto a contract rule
(`ContractRule` is `extra="forbid"` with eight fields), `canonRef.params` is deliberately untyped, and
the canon registry is `closed: false` — *"extends as patterns surface new deterministic needs"*
(`mac_vocabulary.yaml:915`). `check_canon_documented.py` reports **defined 20 · described 20 ·
implemented 17 · OK** with the new member in place.

### The eight rulings

| # | ruling | the reason, measured |
|---|---|---|
| 1 | **`binds` IS the trigger condition** | the operator struck the redundant `about:`. Reusing `binds` inherits the `rule-binds-grounded` shape (`mac_shapes.yaml:94-99`), which already resolves every bound column against the PHYSICAL layer cross-file |
| 2 | **one rule is one AXIS**, several per concept, independent | Store has two. Suppression is keyed `(concept, rule_id)` (`plan.py:675-679`); keyed on the concept it silenced both, so "revenue from the online store" would have dropped the active-store default too |
| 3 | **`default:` is optional and its absence is a declaration** | no default means the axis has no "unless told otherwise" reading; `select()` skips it (`populations.py:222-226`) and a silent question means the whole range |
| 4 | **a named population matches EXACTLY** | `activ`→`active` 0.9091 sits BETWEEN `neaktivan`→`aktivan` 0.8750 and `inactive`→`active` 0.8571; containment holds for all three. The guard must be structural |
| 5 | **no `when:`/`then:`/`never:` on a rule that HAS a body** | that rule's own `never:` went FALSE after the impurity fix and no gate caught it. **`why:` stays** — no predicate encodes "a person ruled this, on this date" |
| 6 | **structure, never SQL text** | `assert_bound_params_only` (`adapters/safety.py:46-53`) refuses any raw string literal, so a string-valued predicate written as text is UNEXECUTABLE: plans clean, dies at the adapter |
| 7 | **`ne` is `IS DISTINCT FROM`; `not_in` keeps NULLs** | 66 against 67, and 57 against 58, on `dim_store.status_annotation`. A text form ships whichever the author typed |
| 8 | **a population may only test columns its rule binds** | an unbound column could never displace the default, so the trigger would be blind on the axis it claims to own (`populations.py:186-194`) |

### Where the firing point sits, and why

Step 4d is in `plan.py` **before** `assemble_plan`, not inside it. `assemble_plan` is typed `-> Plan`
and so cannot return a `Clarification` or a `Refusal` — and a population decision may need to ask.
Deciding it there is what made the old inline per-conjunct override unable to do anything but guess
(`plan.py:660-662`).

---

## PART 3 — WHAT WAS MEASURED

### The defect removed

```sql
-- contoso5.duckdb · schema contoso_served · 2026-10-01
SELECT count(*) FROM dim_store WHERE status_annotation='Closed'                         -->  9
SELECT count(*) FROM dim_store WHERE status_annotation='Closed' AND close_date IS NULL  -->  0
```

*"How many stores are closed?"* planned **perfectly** and then had the declared `close_date IS NULL`
ANDed onto it. **0 rows, every stage green, against a truth of 9.**

### The bundle, enumerated and lowered

Every declared population was parsed by the real `predicates.parse`, lowered by the real
`predicates.lower` through the real `_ParamAllocator`, and passed through the real
`assert_bound_params_only`. **10 populations · 4 axes · 3 concepts · 10 of 10 PASS the adapter gate.**

| concept · axis | population | lowered | rows |
|---|---|---|---|
| Store · trading | **`active`** (default) | `t.close_date IS NULL` | **58** — 57 with `physical` |
| | `ended` | `t.close_date IS NOT NULL` | 16 rows / 14 locations |
| | `closed` | `t.status_annotation = :p` | 9 |
| | `restructured` | `t.status_annotation = :p` | 7 rows / 6 locations |
| Store · channel | **`physical`** (default) | `t.location_code IS DISTINCT FROM :p` | 73 |
| | `online` | `t.location_code = :p` | 1 |
| Location · channel | **`physical`** (default) | `t.location_code IS DISTINCT FROM :p` | 66 |
| | `online` | `t.location_code = :p` | 1 |
| Country · sentinel | **`real`** (default) | `t.country_code IS DISTINCT FROM :p` | **8**, not 9 |
| | `sentinel` | `t.country_code = :p` | 1 |

Revenue, `SUM(v_contoso5_sales_line.net_amount)` joined on `store_key`: `online` **86 790 054,13**
(39,7 % of 218 814 471,66); `closed` stores **2 870 369,00**; `active ∧ physical` 128 818 965,21.

### A number this work CORRECTS

**`active` alone is 58 rows, not 57.** The online sentinel carries no close date, so it is an `active`
store too.

```sql
close_date IS NULL                                        -->  58
close_date IS NULL AND location_code IS DISTINCT FROM -1  -->  57
```

The familiar 57 is `active ∧ physical` — **two independent axes each applying its own default**. The
inline comment at `store.yaml:249` ("57 rows, 57 locations") describes the composition, not the
predicate beside it. This is the cleanest available demonstration of ruling 2, and it is also an
instance of ruling 5 one level down: a measured count written beside a body, where the body moved.

### The adapter gate, run over both forms

| predicate as written | gate |
|---|---|
| `(dim_store.close_date IS NULL AND dim_store.location_code <> -1)` | PASS — *only* because `-1` is numeric |
| `(dim_country.country_code <> '--')` | **REFUSE** `unbound_literal` |
| `(dim_store.status_annotation IN ('Closed','Restructured'))` | **REFUSE** `unbound_literal` |
| `(dim_store.status_annotation IN (:a, :b))` + params | PASS |

### The NULL rulings

On `dim_store.status_annotation`, exactly one NULL row — **and that row is the online sentinel**
(`store_key 999999`, `location_code -1`, `country_code '--'`, no close date):

| form | rows |
|---|---|
| `<> 'Restructured'` | 66 |
| `IS DISTINCT FROM 'Restructured'` | **67** |
| `NOT IN ('Closed','Restructured')` | 57 |
| `IS NULL OR … NOT IN (…)` | **58** |

One-row differences, valid SQL, plausible integers, nothing in the answer to mark them. The ruling now
lives **once**, in `predicates.py:234-247`, with its measurement beside it.

### The exact-matching measurement

```
activ      -> active    0.9091   typo               difflib.SequenceMatcher, substring: yes
neaktivan  -> aktivan   0.8750   antonym, Croatian                      substring: yes
inactive   -> active    0.8571   antonym, English                       substring: yes
```

Reproduced 2026-10-01. The typo sits **between** the two antonyms and containment separates nothing.
No threshold and no affix rule can split them, and an affix rule would be English-only. So the guard
is structural: an exact (case-, space-, underscore-folded) name or nothing.

### Suites

| suite | result |
|---|---|
| `packages/mac-runtime/tests` (full) | **1246 passed · 11 failed · 2 skipped**, 17 s |
| `test_planner_predicates.py` + `test_param_types.py` + `test_planner_value_column.py` + `test_planner_declared_default.py` | **75 passed** |
| `tools/check_canon_documented.py` | defined 20 · described 20 · implemented 17 · **OK**, exit 0 |

The 11 failures are **not this mechanism**: 9 in `test_temporal_builtin.py` (a separate seam built the
same day — the fixture concept `Sale` does not resolve: *"No measure or derivation rule named 'Sale' is
known to this pack"*) and 2 schema-golden drifts in `test_models_golden.py` (`AnswerObject`, `Intent`).
Named here rather than counted as green, per *a red gate must stop something*: these are **news**, they
have no declared owner yet, and they are owed.

### Staleness

Measured read-only on contoso5 (a corpus run was writing captures at the time, so this is a
point-in-time reading): **83 questions · 83 captures · 165 `evidence_stale` warnings** — 83 on the
acceptance plane and **82 of 83** on the ontology plane. Captures carry ontology `306429bf9cdd8a02`;
the bundle reads `3bc7b5d247d0eab2`.

---

## PART 4 — WHAT WAS REJECTED, AND WHY

| rejected | why, measured |
|---|---|
| **infer the condition from column names** — drop a declared conjunct when the question names a column it mentions | it did NOT fire for the worked case (question names `status_annotation`, declaration named `close_date`, intersection empty) and when it DID fire it could not tell a domain clause from a default one, so a question naming `location_code` would have re-admitted the online channel into a question about shops. **Column identity is not meaning** (`sql.py:1412-1418`) |
| **a second key `about:` beside `binds:`** | operator: *"this is redundant and unnecessary"*. It would also have had no cross-file validation, where `binds` already has `rule-binds-grounded` |
| **fuzzy / threshold matching of a population name** | the 0.9091 / 0.8750 / 0.8571 measurement. A typo costs one clarification turn; the alternative is answering `inactive` with the `active` rows |
| **SQL text in a predicate** | 4 of this bundle's 10 populations are string-valued and every one of them is refused as a raw literal by the adapter gate. The text form is latently dead for them: plans clean, dies at execute |
| **`<>` and plain `NOT IN`** | 66 against 67; 57 against 58. A person saying "not X" means "not X, including the rows with no value" |
| **`gt/gte/lt/lte` in a predicate** | every threshold in the worked corpus is in the QUESTION, where `FilterOp` already has them. A population is a membership statement, not a magnitude one |
| **a bare clause without `all:`** | `oneOf[clause, {all: [clause]}]` is two spellings for one fact, and adding a second clause would force the author to restructure the first |
| **an `any:` block** | a **declared gap**: admitting one costs the narrow answer to "which clause did the question contradict" |
| **an `inactive` population beside `ended`** | measured: `status_annotation IN (Closed, Restructured)` and `close_date IS NOT NULL` select the **same 16 rows, zero disagreements**. Two names and two predicates for one set is the drift this mechanism removes. `inactive` is a SURFACE for `ended` — a synonym question, and a different concern |
| **`grounding.value_filter` as the home for either clause** | both were default readings. A predicate a question can legitimately ask the other side of is a DEFAULT, not a domain: `ended` is 16 askable rows, and `online` is one row carrying 86 790 054,13 |
| **keying default-suppression on the CONCEPT** | it silenced both of Store's axes at once |
| **deciding the population inside `assemble_plan`** | that function is typed `-> Plan` and cannot ask |
| **keeping the `Channel` concept** | its three statements were PROSE duplicates of a predicate that belongs where the column is; its edge `order__through__channel` declared no join key and was never emittable — the only path was `NetRevenue -> Customer -> Order -> Channel` and the assembler refused it because `dim_store.location_code` landed in the WHERE with nothing binding `dim_store` (`ontology/edges.yaml:20-32`). Operator: *"if channel has no reason for being ... then lets remove it"* |

### What was NOT a duplicate

One fact now has **three bodies** — Store (`dim_store.location_code`), Location
(`dim_location.location_code`), Country (`dim_country.country_code`). Those are **not** duplicates: the
source wrote the sentinel into three relations, and a population selects the rows of the relation it is
declared on and nothing else (`country.yaml:155-161`). The duplicates were the three *prose*
statements on `Channel`.

### The distinction that keeps being got wrong

Operator, on a different point the same day: *"what do you mean with answer manual = cloned ?!?! if
the answer is approved ?!?!"* — that is about the approved-answer plane, not about populations. The
population-relevant half is the one-line test: **a predicate a question can ask the other side of is a
default, not a domain.** contoso5 now declares **zero** `value_filter` anywhere
(`grep -rn '^\s*value_filter:' ontology/` → no matches) and 10 populations.

---

## PART 5 — WHAT ELSE WAS BUILT, BECAUSE IT IS PART OF THE SAME ANSWER

### `planner/column_types.py` — the type gate

`assert_bound_params_only` proves a value is BOUND. It says nothing about whether the value belongs on
the column. Two live defects passed it:

| | what shipped | consequence |
|---|---|---|
| RC08 | `dim_store.store_key = :store`, `{'store': True}` | `store_key` declared `integer`; DuckDB coerces `TRUE` to `1`; no key is 1 -> **0 rows, every stage green**, against 9 |
| MQ-07 | `v_contoso5_sales_line.store_key = :channel`, `{'channel': 'online'}` | **86 790 054,13** — 40 % of the bundle — reported as `no_value` with `disclosures: []` |

Three decisions inside it, each with a measurement: **bool before numeric** (`isinstance(True, int)` is
`True` in python — that ordering *is* the RC08 fix, `column_types.py:112-116`); **a float with no
fraction is an integer** (`FilterRef.value` is typed with no `int` member, so pydantic turns `630` into
`630.0`; `630.5` onto an integer column still refuses, `124-132`); and **only a DIRECTLY compared
column is checked** — the first cut read `HAVING COUNT(DISTINCT orders.order_id) >= :threshold` as a
comparison against `order_id` and refused a valid threshold (`180-212`). It refuses in the **planner**,
not the adapter: the planner has the declared types and `ExecutablePlan` carries none, and a question
that cannot be answered correctly deserves a `Refusal`, not an `AdapterError` (`24-32`).

**`fits()` has ONE home.** `packages/mac-console/src/mac_console/trace_losses.py:38-47` imports it
rather than keeping a second table, *"because two copies of 'a bool onto an integer column is wrong' is
the drift the check exists to catch"*.

### `planner/resolve.py` — `ResolvedTerm`

The resolver had already computed the answer and dropped it on the `return`. Asked *"How many stores
are closed?"* it matched `closed` exactly —
`Candidate(identity='Closed', concept='Store', column='status_annotation', score=1.0)` — wrote both into
the capture's `resolutions` block for a human to read, and returned the bare `Concept`. With no column,
the planner fell back to the identity column: `dim_store.store_key = :store`, `{'store': True}`.

`ResolvedTerm(concept, candidate)` now carries `.column` and `.identity` through (`resolve.py:137-168`,
returned at `202` and `211`); `.concept` is what every caller wanted and keeps getting. Read at
`plan.py:1628-1645` (the `{term: closed, value: true}` case — **narrow on purpose**: only a bool, and
only when the term matched ON a declared column) and `plan.py:1686-1687` (value's column first, term's
second). **The fix is not new machinery; it is not throwing the answer away.**

### The two staleness fixes

| fix | where | the event behind it |
|---|---|---|
| `reference/` joined `_FINGERPRINT_TREES` | `sdk/acceptance/bundleio.py:128-136` | fourteen approved answers were written and the acceptance hash did not move (`b9167f36ed15449f` before and after). The board read 25 pass / 16 fail with **no `evidence_stale` anywhere** — the one warning that exists to prevent exactly that |
| `evidence_stale` compares the ONTOLOGY fingerprint too | `sdk/acceptance/flags.py:140-149`, `1304-1326` | it compared only the acceptance plane, so a capture produced by an ontology that no longer exists graded as **current**. A capture is evidence about the DECLARATIONS that produced it; when those move it is evidence about nothing |

Optional by design: `ontology_fingerprint=None` means *do not check*, so a caller that cannot supply it
behaves exactly as before rather than raising a warning it has no basis for. Both fingerprints now reach
the evaluator from `sdk/project/questions.py:468`, `503`.

---

## PART 6 — WHAT IS OWED

Ordered by what I would do next.

1. **NOTHING IS COMMITTED.** Every file of this mechanism is **untracked or modified in a working
   tree**: `planner/predicates.py`, `planner/populations.py`, `planner/column_types.py`,
   `canons/population_select.py`, `mac-console/trace_losses.py`, `tests/test_planner_predicates.py`,
   `tests/test_param_types.py` are all `??` on `mac-platform@develop`;
   `reference_manual/canon/population_select.md` is `??` on `meaning-as-code@develop`; the three
   concept files and `edges.yaml` are modified on `<sources>@master`. The last commit in any
   of the three repos is 2026-09-29. **This is the item that matters most**: a mechanism that exists
   only in a working tree is one `git checkout` from never having happened.
2. **THREE EXPORTED PIECES OF THE CANON ARE UNREACHED.** `stray_columns()` and `fold()` have **zero
   callers** (`grep -rn stray_columns --include '*.py'` finds only the definition and `__all__`), and
   `population_select`'s `asked=` parameter is **never passed** — `populations.py:230-235` calls it with
   `populations`, `default`, `binds`, `constrained_columns` only. `planner/populations.py`
   re-implements the folding inline at `271-274` and the stray-column check inline at `186-194`, and
   naming goes through `by_name()`. **Two homes for two invariants, inside the mechanism built to
   remove exactly that** — and by the estate's own standing rule, a declaration nobody reads is prose
   with a colon after it. Either the canon's three pieces become the only homes, or they go.
3. **NO TEST COVERS THE PURE DECISION.** `grep -rn population_select packages/*/tests/*.py` returns
   **nothing**. `test_planner_predicates.py` (11 tests) covers the predicate language;
   `test_planner_value_column.py` covers the naming route. The four-row decision table in
   `canon/population_select.md` is asserted by no test, and neither is the per-axis suppression that a
   wrong key silently broke once already.
4. **NO GATE HOLDS A POPULATION RULE'S PROSE TO ITS BODY.** `tools/check_canon_binding.py:141-146`
   compares authored prose against what a canon RENDERS, but the render registry is
   `tools/canon/rules.py:175-179` — three canons, and `population_select` is a decision, not a
   renderer. So the exact defect ruling 5 is about (a `never:` that went false under a body that moved)
   is **still uncaught today**. The cheapest form is a shape: *a bodied rule carries no
   `when`/`then`/`never`*, with the mutant that proves it rejects.
5. **`declared_for()` has zero callers.** Written "for gates and diagnostics"
   (`populations.py:288-298`); no gate and no diagnostic reads it. A gate over it is the natural home
   for item 4 and for the stray-column invariant.
6. **THE VOCABULARY ENTRY IS STALE ON THE DAY IT WAS WRITTEN.** `mac_vocabulary.yaml:991-1001` still
   documents a param called **`about`** — *"`about` (the columns this set of populations is a statement
   about…)"* — in both the comment and the `doc:` string. The ruling struck `about` in favour of
   `binds`, and the registry is what a bundle author and the model are shown. `planner/sql.py:1418`
   carries the same stale word.
7. **`canon_library.md` does not list `population_select`.** Its generated block
   (`reference_manual/canon_library.md:40-241`) predates the entry; `gen_vocabulary_terms.py` has not
   been re-run. `reference_manual/README.md:59` also still reads *"only 3 of 19 do anything today"*
   where the gate now reports 17 of 20, and `README.md` has no row for `rule_engine.md`.
8. **"FIVE OF THE TEN PREDICATES" IS NOW FOUR OF TEN.** `planner/predicates.py:12`,
   `canon/population_select.md:150` and `tests/test_planner_predicates.py:7` all say five; the figure
   counted `inactive`, removed the same day (`store.yaml:257-263`). Measured today: **10 populations,
   4 string-valued, 4 numeric, 2 valueless.** The argument is unchanged and the number is wrong.
9. **ELEVEN RUNTIME TESTS ARE RED WITH NO DECLARED OWNER.** 9 in `test_temporal_builtin.py`
   (*"No measure or derivation rule named 'Sale' is known to this pack"* — a fixture gap, not this
   mechanism) and 2 schema goldens in `test_models_golden.py` (`AnswerObject`, `Intent`). Per *a red
   gate must stop something*, each needs an owner and a line in the standing-failures register, or a
   fix.
10. **`binds` RESOLVES AGAINST TWO HOMES, LOWERING AGAINST THREE.** `populations.py:176-178` uses
    `field_roles | served_columns`; `sql.py:1921-1928` adds `serving_columns`. A column declared only in
    the third would be refused as a `binds` entry while being perfectly lowerable. An asymmetry, not a
    design.
11. **`select()`'s docstring contradicts its signature.** It says *"Returns `None` when the concept
    declares no population rule"*; it returns `list[Population]` and yields `[]`
    (`populations.py:217-219`). Also `populations.py:273` is indented six spaces inside a four-space
    `for`. Cosmetic, but this is the file that argues prose beside code rots.
12. **165 `evidence_stale` warnings stand on contoso5** and the board is honest about it for the first
    time. Those captures must be re-run before any verdict on them is quoted — and per
    *gates report PASS on zero files*, no pass rate from that corpus should be reported without the
    82-of-83 denominator beside it.
13. **An `any:` disjunction is a declared gap**, and the day a bundle needs one the cost named in the
    canon page (the narrow "which clause did the question contradict") has to be paid or re-argued.
14. **Synonym surfaces have no home.** `inactive` was correctly refused as a population and correctly
    identified as a *surface* for `ended`. Nothing yet maps a surface word onto a declared population
    name; until it does, a question saying `inactive` asks instead of answering.

---

## PART 7 — THE RULINGS THAT STAND

| | |
|---|---|
| **the condition** | a rule's own `binds`. No second list, ever |
| **the axis** | one rule is one axis; a concept declares as many as its rows carry states; suppression is per axis |
| **the default** | optional; its absence declares that the axis has no unqualified reading |
| **matching** | exact, case-/space-/underscore-folded, checked BEFORE any value ladder. Never fuzzy, in any language |
| **prose** | none beside a body. `why:` always — it is the only carrier of "a person ruled this, on this date, against this measurement" |
| **form** | structure, never SQL text. There is deliberately no slot that accepts it |
| **nulls** | `ne` is `IS DISTINCT FROM`; `not_in` keeps them. Ruled once, with the measurement beside it |
| **the domain** | `grounding.value_filter` is for rows no question may reach. If a question can ask the other side, it is a default |
| **evidence** | the condition is tested against the INTENT and the DECLARATIONS. No SQL may run to decide which SQL to write |
| **disclosure** | every selected population is disclosed — applied *or* displaced — and names the alternatives. Expose the granularity, never narrow silently |
| **inertness** | a bundle that binds no population canon is unchanged in every respect |

---

## PART 8 — THE RECORD

**No commits.** See owed item 1. The working-tree state, 2026-10-01:

```
mac-platform@develop        ?? planner/{predicates,populations,column_types}.py
                            ?? canons/population_select.py
                            ?? mac-console/trace_losses.py
                            ?? tests/{test_planner_predicates,test_param_types}.py
                             M planner/{plan,sql,resolve,types}.py · canon.py · canons/__init__.py
meaning-as-code@develop     ?? reference_manual/canon/population_select.md
                             M mac_vocabulary.yaml · sdk/acceptance/{bundleio,flags}.py
<sources>@master             M example/contoso5/ontology/concepts/{store,location,country}.yaml
                             M example/contoso5/ontology/edges.yaml
```

**Defects found by building this, not by looking for them** — the ones worth carrying:

* **A predicate that plans cleanly and dies at the adapter is worse than one that refuses.** Four of
  this bundle's ten populations could not have been written in the form the estate had. The text form
  worked only because its single authored instance happened to use a numeric `-1`.
* **Internal consistency is not correctness, again.** `close_date IS NULL AND location_code <> -1` was
  perfectly self-consistent, measured, and justified in prose — and ANDing it onto a question about
  closed stores can never be true. The bug was not in either clause; it was in treating two kinds of
  statement as one.
* **A measurement written beside a body rots exactly like prose.** `active` is 58 and the comment
  beside it says 57, which was true of a composition, not of the predicate. The mechanism built to
  stop prose drifting from bodies drifted in its own worked example within hours.
* **A canon can be pure, documented, registered, implemented — and still have three exported pieces
  nothing calls.** That is the estate's own standing finding (*the runtime ignores its own
  declarations*) reproduced by the change that cites it.
