<!-- STATUS: PROPOSED, and the code it documents is LANDED AND INERT. `decisions/0004-the-fold-plane.md`
     (mac-ontology-contoso) is not ratified; no bundle declares a fold plane, so on every bundle in the
     estate today this manual describes behaviour you must switch on yourself with an env var.
     Where the operator has not ruled, the section says UNRULED and names the options. Do not silently
     pick one. Every count below carries its denominator; figures marked [measured here] were re-run
     on 2026-09-20 against the installed runtime, the real bundle and the read-only warehouse. -->

# THE FOLD PLANE — DEVELOPER MANUAL
### You have a column, a table or a concept in front of you. This says exactly what to write.

---

## 1. WHAT THIS FILE IS

Use this file when you have a **specific situation in the data** and need the configuration block for it.

* It is **not** the design record. That is `decisions/0004-the-fold-plane.md` in `mac-ontology-contoso`: why four planes, what was deleted, what would reverse it.
* It is **not** the tutorial. That is `FOLD_GRAMMAR.md` in `meaning-as-code`: what the words mean, how to explain them to an SME, what an SME is asked.
* It **is** the lookup: 18 situations plus 5 combinations that actually occur, each with a copy-pasteable block, the SQL it produces, the command that proves it, and what it does not cover.

Read section 4 (the decision tree) once. After that, jump to the situation.

**About the numbers.** Every count carries its denominator. Figures tagged **[measured here]** were re-run on 2026-09-20 against the installed runtime (`packages/mac-runtime/src/mac_runtime/planner/plan.py`), the real contoso bundle, and — where a number rather than a plan is quoted — a read-only connection to `contoso.duckdb`. Untagged figures are carried from `decisions/0004`, `FOLD_GRAMMAR.md` and the option adjudication; they are attributed where it matters and none of them is load-bearing for a configuration block.

Two conventions used throughout:

```bash
# the platform checkout -- bare `python3` fails, always use the venv
PLAT=<your mac-platform checkout>
# the scratchpad this work was done in (the harness and the probes live here, uncommitted)
SP=<a scratch directory of your own>
```

---

## 2. THE MODEL IN ONE PARAGRAPH

A number column says **what kind of number it is** (`quantity_kind`: one of `extensive`, `intensive`, `indicator`, `ordinal`, `identifier`). Its relation says **how its rows came to exist** (`grain_semantics`: one of `event`, `observation`, `plan`, `precomputed`; absence is `UNKNOWN` and `UNKNOWN` means deny). A concept says **what one of these is for counting** (`counts_as`) and **whether it is asserted or observed** (`modality`, a disclosure and never an input to arithmetic). The framework — not you — owns the 25-cell table `LAW[grain_semantics][quantity_kind] -> one of 10 operators`, and it is consulted on the axes your question **folded**, i.e. `FOLDED = axes(fact) \ (partitioned ∪ pinned)`: everything you did not group by and did not pin to a single member. Before the table is read, five guards run in a fixed order and the first failure is the answer (G1 no declared kind, G2 identifier/ordinal reached by an aggregate, G3 a precomputed cell asked coarser than it is stored, G4 a folded unit column with more than one member, G5 two operand kinds and no rule). Provenance is by location plus one token: `ruled_by:` → `confirmed`, `derived_by:` → `derived`, silence → `inferred`, and an answer takes the weakest tier of everything it touched.

---

## 3. WHERE THE BLOCK GOES — **UNRULED (R1)**

**What the landed code reads, today, and the only form measured to work:** a directory named by `MAC_FOLD_PLANE_DIR` holding one or more `<name>.fold.yaml` files with two top-level keys, `relations:` and `concepts:`. Every block in this manual is in that form. `planes.py:load_plane` globs `*.fold.yaml`, **merges every file into one flat namespace keyed by relation name**, then keeps only the relations the loaded index actually grounds on.

The three candidate production homes, and why this manual does not pick:

| home | the key you would write | status |
|---|---|---|
| `fold/<bundle>.fold.yaml` (new top-level dir) | `relations: / concepts:` — **identical to the blocks below, byte for byte** | **recommended in the adjudication, NOT RULED.** Needs a `FoldFile` `$def` in `mac.schema.json` first, or the file is MAC001 |
| `data/datasets/<relation>.yaml` — the design's own stated home | `x-quantity-kind`, `x-per`, `x-denominated-by` on `columns[]`; `x-grain-semantics`, `x-observation` on `table:` | **rejected in the adjudication**: 13 of 18 cases (no concept plane there, so `counts_as`/`modality` have nowhere to sit), MAC012 exit 1 on `x-` keys, and `GroundingColumn` is `extra="forbid"` with 4 fields, so 0 of 9 `x-` keys reach the model |
| `ontology/...` anywhere | — | **do not.** The lock is armed; a write there is exit 2 |

Until R1 is ruled: keep the plane in a scratch directory and point `MAC_FOLD_PLANE_DIR` at it. Nothing else about the mechanism changes when the home is ruled — the reader in `planes.py` prefers real extension keys on `serving_columns` when they are present and falls back to the overlay, so the same code path serves both.

**One trap that is a property of the home, not of your file:** the merge is keyed by **relation name across the whole estate**, not by bundle. Two bundles that both serve a relation called `orders` share one plane entry. Keep relation names qualified the way contoso does (`v_contoso_order_line`, `dim_contoso_store`), and never name a plane entry after a fixture relation.

---

## 4. THE DECISION TREE — under a minute, with a pencil

Start: **I have a number column in front of me.**

```
Q0. Is it a key, a code, or an id?
    YES -> WRITE NOTHING. `quantity_kind: identifier` is derived from `field_role: key`.
           [measured here] 18 of 18 identifier entries on contoso were filled by the gate,
           0 authored. If you type it you have typed a derived value -- see mistake M4.
    NO  -> Q1.

Q1. If I add two of these together, do I get a real, bigger one of the same thing?
    YES -> quantity_kind: extensive                                  -> go to Q4
    NO  -> Q2.

Q2. Does it only ever hold two values, and is it really a yes/no?
    YES -> quantity_kind: indicator                                  -> go to Q4
           (and note: WHICH value means yes is NOT declarable; the runtime hardcodes `= 1`)
    NO  -> Q3.

Q3. Does it put things in an order (1st, 2nd, 3rd) rather than measure an amount?
    YES -> quantity_kind: ordinal                                    -> go to Q4
    NO  -> quantity_kind: intensive   (a price, rate, ratio, duration, percentage)
           Q3a. Is there a column ON THE SAME RELATION saying how many of the thing
                this is per?
                YES -> per: <that column>       (a real weighted mean; it composes)
                NO  -> WRITE NOTHING. Absence means a plain mean, and the plan will
                       disclose that a plain mean does not compose.
                       (`per: __rows__` is the same code path as silence -- do not type it)
           Q3b. Can this number be in different units on different rows?
                YES -> denominated_by: <the column naming the unit>
                NO  -> nothing.

Q4. How did the rows of this relation come to exist? ONE word, ONCE per relation.
    something happened, once, and is never re-stated          -> grain_semantics: event
    the same subject is read again at a later time            -> grain_semantics: observation
                                                                 + observation: {subject_key, observed_at}
    somebody asserted it for a future period                  -> grain_semantics: plan
    another tool already computed it for a fixed cell         -> grain_semantics: precomputed
    If the relation is realized by `mac.canon.snapshot_collapse` with `params.natural_key`,
    WRITE NOTHING: observation + subject_key + observed_at are all derived.
    [measured here] 1 of 1 on contoso, 0 authored.

Q5. Does ONE column disagree with the relation's answer to Q4?
    a level on an otherwise event relation   -> observed_as: {as_of: <date col>, subject: <subject col>}
    one precomputed column among events      -> stored_at: [<every key column of its cell>]

Q6. Will anybody ever ask HOW MANY of these things there are?
    YES -> on the CONCEPT: counts_as: <the column that is one of them>
           This is the one fact in the design no machine can reach. Nobody derives it.
    NO  -> nothing.

Q7. Is this number a promise rather than a measurement?
    YES -> on the CONCEPT: modality: planned      (changes no arithmetic; forces a sentence)

Q8. Is there a member of any axis of this relation that is not one of the things?
    YES -> a `sentinels:` entry on the relation: column, member, label, share.
           A sentinel NEVER changes a number. [measured here] delete it and the SQL is
           byte-identical with the caveat gone.

Then, always: add `ruled_by: "<what the person said>"` beside anything a person ruled.
Silence is not neutral -- it means `inferred`, the weakest tier.
```

**Do not type, in any situation:** `cell_key` (derived; [measured here] every `cell_key` removed from both planes still scores **16 of 18**), `quantity_kind: identifier` (derived 18 of 18), `denominator_distinct` (derive it from the profile — the one hand-typed value in the estate is wrong, see M6), `per: __rows__` (identical code path to silence), `evaluate_at` (parsed into `ConceptPlane` and read by **0 lines** of `law.py`), any `axes:` block ([measured here] appending one to the contoso plane leaves the score at **16 of 18** — it is silently dropped).

---

## 5. THE SITUATIONS

Each section is one situation. `# RELATION`, `# COLUMN`, `# CONCEPT`, `# AXIS`, `# PROVENANCE` and `# DERIVED` in the blocks name the level of each line.

The three bundles used in the commands: `contoso` (the real bundle, read-only), `legacy_stock` (a scratch copy of the platform's `additivity_fixture`), `typed_law` (synthetic, alpha/beta/gamma). All three are wired into `$SP/proto/harness_landed.py`.

---

### S1 · An amount accrued to a period
*(case 1 · contoso · correct today, and correct by luck)*

**WHEN YOU HAVE THIS.** A column whose sum has a name someone would say out loud ("total units sold"), on a relation where one row is one thing that happened. In the descriptors: `field_role: measure` or a `*.derivation.*` rule that multiplies it, `type: integer|decimal`, no snapshot canon on the relation, no reporting cycle.

**THE CONFIGURATION**

```yaml
relations:
  v_contoso_order_line:                 # RELATION -- one block per served relation
    grain_semantics: event              # RELATION -- one word: these rows happened
    derived_by: "no collapse canon and no reporting cycle is declared on this relation"
                                        # PROVENANCE -> tier `derived` (a gate said so)
    # cell_key: [OrderKey, RowNumber]   # DERIVED -- do NOT type it
    columns:
      Quantity:                         # COLUMN
        quantity_kind: extensive        # COLUMN -- the whole common case, one word
        ruled_by: "GSA-Q0 -- a count of units accrues per line and accumulates"
                                        # PROVENANCE -> tier `confirmed` (a person said so)
```

**WHAT YOU GET.** Byte-identical SQL to today, now for a stated reason:

```sql
SELECT SUM(f."Quantity" * f."UnitPrice") AS gross_sales_amount
FROM contoso_served.v_contoso_order_line f WHERE f.CurrencyCode = :currency
```

[measured here] the law saw **9 folded axes** (`CustomerKey, DeliveryDate, FromCurrency, OrderDate, OrderKey, ProductKey, RowNumber, StoreKey, ToCurrency`), `CurrencyCode` **pinned**, 0 partitioned, ops `['grain_expression', 'sum']`, tier `derived`. Today's legacy guard was consulted on 1 axis and read a field that is `{}` on 17 of 17 contoso concepts.

**HOW TO CHECK IT WORKED**

```bash
cd $PLAT && MAC_FOLD_PLANE_DIR=<your plane dir> .venv/bin/python $SP/proto/harness_landed.py \
  | sed -n '/--- CASE 1:/,/^$/p'
# look for: AFTER OK Plan ['SUM'] ... and no `fold:` refusal
```

**WHAT IT DOES NOT COVER.** Delete either line and the question refuses instead of guessing — which is the point, but it means an incomplete plane is *worse* than no plane for any single relation you started declaring. Nothing here says the amount is in one unit; that is S12, and without it this same question with no currency pinned is a five-currency sum.

---

### S2 · The same amount as one bare total
*(case 2 · contoso)*

**WHEN YOU HAVE THIS.** A question with no period and no breakdown: "total gross sales". This is the **maximal** fold — every axis at once — and it is the shape the legacy guard was never consulted on at all (0 axes, 11 of 11 typed measures).

**THE CONFIGURATION.** Nothing beyond S1. That is the finding: the 25-cell law has no axis dimension, so "over time" and "over stores" are one rule consulted about different columns.

**WHAT YOU GET.** The same `SUM`, plus every disclosure the relation carries (on contoso, the sentinel — see S17). [measured here] identical SQL to S1 with the `WHERE` dropped.

**HOW TO CHECK IT WORKED**

```bash
cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/manual/ask.py GrossSalesAmount pin=currency:USD
```

**WHAT IT DOES NOT COVER.** Drop the pin and this becomes S12 (a refusal). Nothing in the plane distinguishes "the user wants a grand total" from "the user forgot to say which currency"; the fold law only knows the axis is folded.

---

### S3 · A level on a relation that re-reads the same subject
*(case 3 · legacy_stock · the collapse)*

**WHEN YOU HAVE THIS.** The same subject appears many times with a later timestamp: stock on hand per site per day, a store's attributes republished, a balance. In the data: `COUNT(*) > COUNT(DISTINCT <subject>)`. In the descriptors: a snapshot/SCD canon (`mac.canon.snapshot_collapse`), a `valid_from`/`snapshot_date` column, or a contract rule saying "never SUM across days".

**THE CONFIGURATION**

```yaml
relations:
  stock_snapshots:                        # RELATION
    grain_semantics: observation          # RELATION -- the same subject, read again
    ruled_by: "the fixture's own contract: 'a point-in-time snapshot ... never SUM across days'"
    observation:                          # RELATION -- exactly these two key names
      subject_key: site_code              #   what the row is a version OF
      observed_at: snapshot_date          #   which column decides which version is latest
    # cell_key: [snapshot_id]             # DERIVED -- what makes a ROW unique. Not the same
                                          #   fact as subject_key, and collapsing the two IS the bug
    columns:
      quantity_on_hand:
        quantity_kind: extensive          # COLUMN -- a level is extensive ACROSS SITES
        ruled_by: "a level is extensive across sites; what makes it a level is the relation"
```

On contoso's `dim_contoso_store` you write **none of the relation half**: `grain_semantics: observation`, `subject_key: StoreCode` and `observed_at: OpenDate` are all filled by the `observation_from_snapshot_canon` derivation from `realized_by: mac.canon.snapshot_collapse` + `params.natural_key`. [measured here] 1 of 1 relations, 0 authored, tier `derived`.

**WHAT YOU GET.** Stage 0/1 collapse before the fold — never a bare SUM over every snapshot day:

```sql
SELECT SUM(fold_cycle.quantity_on_hand) AS stocklevel
FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY site_code ORDER BY snapshot_date DESC) AS mac_fold_rank
      FROM fixture_warehouse.stock_snapshots) fold_cycle
WHERE fold_cycle.mac_fold_rank = 1
```
plus `[fold law] collapsed to one row per site_code (ordered by snapshot_date, latest first) BEFORE folding; the relation's cell key is snapshot_id, which is the version grain and not the entity.`

The rule is **not** "never sum a level". It is *resolve the end reading per subject, then sum across subjects.*

**HOW TO CHECK IT WORKED**

```bash
cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/proto/harness_landed.py \
  | sed -n '/--- CASE 3:/,/^$/p'
# look for: PARTITION BY <your subject_key>, and mac_fold_rank = 1
```

**WHAT IT DOES NOT COVER — read this one.** The collapse partitions by the subject key **union the axes the question preserved**, so a breakdown can silently re-inflate it. [measured here] read-only on `dim_contoso_store`, 74 rows / 67 codes:

| the partition the planner emitted | rows surviving | `SUM(SquareMeters)` |
|---|---|---|
| `PARTITION BY StoreCode` (the correct one) | **67 of 74** | **99,300** |
| "by country" → `CountryCode, CountryName, StoreCode` | 67 of 74 | 99,300 |
| "by geography" → `CountryCode, GeoAreaKey, State, StoreCode, StoreKey` | **74 of 74** | **109,120** |
| "by store" → all 10 columns incl. `StoreKey` | **74 of 74** | **109,120** |

So **2 of 3** probed breakdowns put a version-varying column into the partition and the collapse became a no-op again, with no error and no caveat change. Nothing you can write in the plane prevents this; the collapse must partition by the subject key alone and group afterwards. Also unsettled: "latest" is itself a ruling (an as-of question wants the version whose validity window contains the date, and `observed_at` names only the ordering column), and a relation re-observed on two independent clocks is undefined.

---

### S4 · The same level, grouped by place — **NOT FIXED (case 4)**

**WHEN YOU HAVE THIS.** A level measure whose concept still carries the legacy `semantics.additivity` field with a per-axis entry, asked *by* that axis. Stock at site A plus stock at site B *is* total stock: grouping by site **preserves** the axis, so additivity across sites is not even the question.

**THE CONFIGURATION.** S3's block, and nothing more. Then, separately: stop authoring `semantics.additivity` on new concepts (it is **deprecated, never deleted** — `ConceptSemantics` is `extra="forbid"` and `mac.schema.json` is `additionalProperties: false`, so removing the field stops 13 of 13 files parsing and 3 are behind the armed lock).

**WHAT YOU GET.** Still the wrong refusal: `StockLevel is not additive over the 'storagesite' axis (declared 'non-additive')`. The legacy guard runs **first** by default and returns before the fold law is called.

**HOW TO CHECK IT WORKED — and the switch that fixes it**

```bash
cd $PLAT && MAC_FOLD_LEGACY_FIRST=0 MAC_FOLD_PLANE_DIR=<plane dir> \
  .venv/bin/python $SP/proto/harness_landed.py | tail -6
# [measured here] CORRECT AFTER: 17 of 18  (vs 16 of 18 with the default precedence)
```

**UNRULED (R3).** Flipping `MAC_FOLD_LEGACY_FIRST=0` costs 6 named tests of 1435 (4 of which assert the behaviour being replaced, 2 are fixture freshness) and moves the score 16 → 17 of 18. Only the operator can rule it. Until then this situation is **not configurable** — no line in any plane reaches it.

---

### S5 · An average with nothing to weight it by
*(case 5 · typed_law)*

**WHEN YOU HAVE THIS.** A per-something figure on a relation that carries no extent column: a duration, a list price on a catalogue row, a temperature. Give-away: the word "per" fits the sentence, and you look for the weight column and there is none. (Contoso's `dim_contoso_product` has 14 columns and none says how many were sold.)

**THE CONFIGURATION**

```yaml
relations:
  alpha_facts:
    grain_semantics: event                # RELATION
    columns:
      duration_minutes:
        quantity_kind: intensive          # COLUMN -- a per-something figure
        # per:                            # OMIT IT. Absence == a plain mean.
                                          #   `per: __rows__` is the identical code path: do not type it
        ruled_by: "synthetic intensive with no declared extent -- a plain mean"
```

**WHAT YOU GET.** `AVG`, never `SUM`, plus a disclosure that is true on this data:

```sql
SELECT AVG(alpha_facts.duration_minutes) AS betaduration
FROM fixture_warehouse.alpha_facts WHERE alpha_facts.fact_date >= :period_start AND ... < :period_end
```
```
[fold law] a plain mean DOES NOT COMPOSE across axes and this question folds 6: the one-shot
mean and the staged mean differ (measured 32.000000 vs 32.500000 on unequal groups).
Declaring `per:` on alpha_facts.duration_minutes makes the fold determinate.
```

**HOW TO CHECK IT WORKED**

```bash
cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/proto/harness_landed.py \
  | sed -n '/--- CASE 5:/,/^$/p'
# look for: AFTER OK Plan ['AVG'] ... and the words "does not compose"
```

**WHAT IT DOES NOT COVER.** Median, percentile and any other order statistic share one mean family with no operator parameter — there is no way to ask for them. A **time-weighted** mean cannot be stated at all: `per:` names a column, and an interval length is not one.

---

### S6 · An average that has a weight
*(case 6 · typed_law · and the same block answers S15)*

**WHEN YOU HAVE THIS.** A per-unit figure with the unit count sitting on the same row: a unit price beside a quantity, a rate beside its denominator. Give-away in the descriptors: the bundle's own prose already says it — "a price is per unit".

**THE CONFIGURATION**

```yaml
relations:
  alpha_facts:
    grain_semantics: event                  # RELATION
    columns:
      gamma_rate:
        quantity_kind: intensive            # COLUMN
        per: gamma_denominator              # COLUMN -- must name a column of the SAME relation
                                            #   so a gate can check it exists
        ruled_by: "synthetic ratio -- fold the parts, then divide: SUM(x*d)/SUM(d)"
      gamma_denominator:
        quantity_kind: extensive            # COLUMN -- the weight is itself a quantity
        ruled_by: "the weight of gamma_rate"
```

**WHAT YOU GET.** A weighted mean that composes — a breakdown and a grand total agree:

```sql
SELECT alpha_facts.brand_code,
       SUM(alpha_facts.gamma_rate * alpha_facts.gamma_denominator)
       / NULLIF(SUM(alpha_facts.gamma_denominator), 0) AS gammarate
FROM fixture_warehouse.alpha_facts GROUP BY alpha_facts.brand_code
```

**HOW TO CHECK IT WORKED**

```bash
cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/proto/harness_landed.py \
  | sed -n '/--- CASE 6:/,/^$/p'
# look for: NULLIF(SUM( ... in the AFTER line. If you see a bare SUM or AVG, `per:` did not land
```

**WHAT IT DOES NOT COVER.** The weight must be a column on the same relation. A weight that lives one join away, or a weight that is itself an expression, cannot be named. Nothing checks that the weight is `extensive` — declare an intensive weight and you get arithmetic nobody sanctioned (the `per`-target-must-be-extensive gate is proposed and **not landed**).

---

### S7 · A precomputed cell asked over a range
*(case 7 · contoso)*

**WHEN YOU HAVE THIS.** Another tool already computed the number for a fixed cell: an fx rate per (date, from, to); a pre-aggregated reach; any "grid" relation. Give-away: the value only makes sense at the intersection of two or more keys, and its range is narrow (contoso's `Exchange`: min 0.47908 / max 2.08733 over 100,450 of 100,450 rows) while a `SUM` of it grows with the row count.

**THE CONFIGURATION**

```yaml
relations:
  v_contoso_fx_rate_day:
    grain_semantics: precomputed            # RELATION -- a stored cell, not an event
    ruled_by: "exchange_rate.axis_handling -- read AT a date, never over a range"
    cell_key: [Date, FromCurrency, ToCurrency]
                                            # DERIVED from the grounding -- shown here because it
                                            #   IS the guard: G3 reads the cell key, so
                                            #   `never_half_a_pair` needs no new property
    columns:
      Exchange:
        quantity_kind: intensive            # COLUMN
        ruled_by: "a rate is per unit of the from-currency"
```

**WHAT YOU GET.** No SQL at all — a named refusal, before anything is built:

```
Refusal(fold:grain_not_stored)  reason_code=additivity_violation
ExchangeRate is stored only at the grain (Date, FromCurrency, ToCurrency) and this question
leaves Date, FromCurrency, ToCurrency unpinned, so there is no stored cell to read and no fold
that would be valid. Pin or group every key column, or ask at the grain it is stored at.
missing = ['fold:grain_not_stored', '<relation>.Date', '<relation>.FromCurrency', '<relation>.ToCurrency']
```

**HOW TO CHECK IT WORKED**

```bash
cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/manual/ask.py ExchangeRate
# look for: Refusal, and `fold:grain_not_stored` in the missing list
```

**WHAT IT DOES NOT COVER.** The advice in the refusal cannot be taken as written: a period is a range, so even a one-day period still refuses, and a monthly grouping is wrongly treated as discharging the day axis. There is no `resolve_match` path from a period to the cell it contains.

---

### S8 · The same precomputed cell asked by one of its keys
*(case 8 · contoso)*

**WHEN YOU HAVE THIS.** The grid relation again, now with a breakdown that covers *part* of the cell key ("the exchange rate by currency").

**THE CONFIGURATION.** Nothing new — S7's two lines govern both folds. That is the design working: one declaration, every fold of that relation.

**WHAT YOU GET.** The **same refusal, narrower**: it names `Date` only, because grouping by currency kept that part of the cell. [measured here] `missing = ['fold:grain_not_stored', 'v_contoso_fx_rate_day.Date']`. The refusal gets more specific as the question does, which is what makes it teachable.

**HOW TO CHECK IT WORKED**

```bash
cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/manual/ask.py ExchangeRate by=currency
```

**WHAT IT DOES NOT COVER.** "By currency" on an ordered pair is ambiguous (FROM or INTO?) and there is no field for the answer. And the thing this refusal prevented is worth knowing: before the plane, this question emitted `JOIN v_contoso_fx_rate_day ... ON` followed by **nothing** — an empty `ON` clause, in 3 of 5 plans this measure produced. That defect is in `planner/sql.py` (`join_rule = edge.join_rule or ""`, then the clause is appended with no guard) and **no plane, kind, home or derivation fixes it**. [measured here] I reproduced it this session on a different question: `... JOIN dim_contoso_customer ON WHERE fold_cycle.mac_fold_rank = 1`.

---

### S9 · A number somebody promised
*(case 9 · typed_law)*

**WHEN YOU HAVE THIS.** A target, budget, goal, forecast or quota. It accrues like any amount — January's goal plus February's goal is the two-month goal — and what distinguishes it is **who asserted it**, not how it folds. Give-away: a reader would be misled seeing it beside actuals with no label.

**THE CONFIGURATION**

```yaml
relations:
  alpha_facts:
    grain_semantics: event                  # RELATION -- or `plan` if EVERY row of the relation
                                            #   is an assertion; on a mixed relation leave the
                                            #   relation alone and use the concept's modality
    columns:
      goal_amount:
        quantity_kind: extensive            # COLUMN -- a planned quantity still folds by SUM
        ruled_by: "synthetic Target -- a planned quantity still folds by SUM"

concepts:
  GammaTarget:
    modality: planned                       # CONCEPT -- a DISCLOSURE, never a fold input
    ruled_by: "the matrix's `none` on Target is judged a mis-classification, not a law"
```

**WHAT YOU GET.** Byte-identical SQL plus a mandatory sentence:

```sql
SELECT SUM(alpha_facts.goal_amount) AS gammatarget FROM fixture_warehouse.alpha_facts WHERE ...
```
`[fold law] this is a PLAN figure, not an observation: it folds like any other extensive quantity, and it is not a measurement of what happened.`

Either home fires the disclosure: `grain_semantics: plan` on the relation, or `modality: planned` on the concept. Prefer the **concept** when the relation mixes actuals and plans; prefer the **relation** when every row is a promise.

**HOW TO CHECK IT WORKED**

```bash
cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/proto/harness_landed.py \
  | sed -n '/--- CASE 9:/,/^$/p'
# look for: the words "plan figure" in the AFTER line. No words -> the disclosure did not fire
```

**WHAT IT DOES NOT COVER.** Rolling a plan **up** works. Splitting a plan **down** (a regional goal asked per store) has **no term at all** — `grep -i "allocat\|disaggregat"` across the design and all three runtime modules returns 0 hits, and `stored_at` is the wrong tool (it refuses the up-fold too). `modality` has exactly two values in practice (`observed`, `planned`); a forecast that is neither is not expressible.

---

### S10 · The same promise, by a categorical axis
*(case 10 · typed_law)*

**WHEN YOU HAVE THIS.** The target from S9, asked by brand/region/store instead of by period.

**THE CONFIGURATION.** **Identical to S9. Nothing new.** This is the design's central claim made checkable: the 25-cell law has no axis dimension, so "over months" and "over stores" are one rule consulted about different columns. The old matrix carried two cells for `Target` with the same verdict — 2 of 10 cells carrying no information.

**WHAT YOU GET.** `SELECT alpha_facts.brand_code, SUM(alpha_facts.goal_amount) ... GROUP BY alpha_facts.brand_code` plus the same plan disclosure.

**HOW TO CHECK IT WORKED.** As S9, with `/--- CASE 10:/`. If S9 passes and S10 fails, something axis-dependent has crept into the law — that is a bug, not a missing declaration.

**WHAT IT DOES NOT COVER.** As S9.

---

### S11 · Two overlapping views of one row — **NOT CONFIGURABLE (case 11)**

**WHEN YOU HAVE THIS.** Two categorical axes that both slice the same activity and are not levels of each other: brand and product category; channel and region. The honest answer is the cross-product with a disclosure that the axes are independent.

**THE CONFIGURATION.** **There is none, and do not write one.** There is no axis level in the plane at all. An `axes:` block parses, is dropped, and changes nothing: [measured here] appending

```yaml
axes:                                    # DOES NOTHING. Parses, dropped, never read.
  v_contoso_order_line:
    CurrencyCode: {ordered: false, partition_role: partitions}
```
to the contoso plane leaves the 18 cases at **16 of 18**, unchanged. Do not believe a green run of one.

**WHAT YOU GET.** On contoso, a refusal for an unrelated reason: `Refusal(no_join_path) No legal join path between GrossSalesAmount and Brand.` — 0 of 17 declared edges name Brand (a roll-up belongs in `members.over`, and the route-finder reads only `edges.yaml`), so **4 of 17** concepts (Brand, ProductCategory, ProductSubcategory, Continent) can never appear in an answer however they are declared. That is a join defect, and the only case on this list no fold declaration can reach.

**HOW TO CHECK IT WORKED.** You cannot. `sed -n '/--- CASE 11:/,/^$/p'` shows the same refusal before and after, under every plane in this manual.

**WHAT IT DOES NOT COVER.** Everything: whether two axes are orthogonal, whether one is a level of the other, whether a member belongs to two parents at once, whether an axis is ordered. Contoso is safe by accident (0 of 2,517 products carry two brands) and nothing would stop the unsafe case.

---

### S12 · One amount, more than one unit
*(case 12 · contoso · the largest silent error in the bundle)*

**WHEN YOU HAVE THIS.** A money, weight or volume column with a sibling column naming the unit per row. Give-away: the unit column has >1 member in scope. [measured here] read-only: `v_contoso_order_line` carries **5** distinct `CurrencyCode` over **223,974 of 223,974** rows; `dim_contoso_product.WeightUnit` carries **3** distinct non-null values (pounds 1,867 / ounces 418 / grams 10, plus 222 of 2,517 null).

**THE CONFIGURATION**

```yaml
relations:
  v_contoso_order_line:
    grain_semantics: event                    # RELATION
    columns:
      UnitPrice:
        quantity_kind: intensive              # COLUMN
        per: Quantity                         # COLUMN -- see S6
        denominated_by: CurrencyCode          # COLUMN -- which column names THIS number's unit
        # denominator_distinct: 5             # DERIVE IT from the profile. See mistake M6:
                                              #   the one hand-typed value in the estate is wrong
        ruled_by: "order_line.currency.no_bare_cross_currency_sum"
```

**WHAT YOU GET.** A refusal naming three repairs that are all already in the bundle:

```
Refusal(fold:incommensurable)  reason_code=additivity_violation
v_contoso_order_line.UnitPrice is denominated by CurrencyCode, CurrencyCode is folded by this
question and carries 5 members in scope, so the result would add amounts in different units as if
they shared one. Three declared repairs, all of them in the bundle already: pin one CurrencyCode,
group by CurrencyCode, or convert through the declared conversion derivation.
```

The guard fires only when the unit column is **folded** and carries **more than one** member. [measured here] all three discharges:

| the question | outcome |
|---|---|
| bare total, no currency | **Refusal** `fold:incommensurable` |
| `pin=currency:USD` (S1) | `SUM(...)` with `WHERE f.CurrencyCode = :currency` |
| `by=currency` | `SELECT f.CurrencyCode, SUM(...) ... GROUP BY f.CurrencyCode` |

Delete that one line and the silent 232,601,542.66 — USD 118.9m + EUR 50.3m + CAD 24.7m + GBP 24.5m + AUD 14.2m, a number with no unit — comes straight back.

**HOW TO CHECK IT WORKED**

```bash
cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/manual/ask.py GrossSalesAmount
cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/manual/ask.py GrossSalesAmount by=currency
# expect: Refusal fold:incommensurable, then a Plan with GROUP BY CurrencyCode
```

**WHAT IT DOES NOT COVER.** Composite and scaled units ("thousands of USD") are not expressible. The third repair — "convert through the declared conversion derivation" — is a sentence, not a mechanism: nothing in the fold law invokes the conversion. And the guard is blind to a unit column that is `NULL` on some rows (222 of 2,517 products have no `WeightUnit`); `denominator_distinct` counts non-null members only.

---

### S13 · A yes/no written as 0 and 1
*(case 13 · typed_law)*

**WHEN YOU HAVE THIS.** An integer column with exactly 2 distinct values, min 0 max 1 — a flag. Give-away: its sum is a **count of rows** wearing a total's name. Contoso's `WorkingDay`: 4,018 rows, 2 distinct, 2,760 working / 1,258 not; `SUM` = 2,760 (right digit, wrong claim), `AVG` = 0.6869 ("0.69 working days").

**THE CONFIGURATION**

```yaml
relations:
  dim_contoso_calendar_day:
    grain_semantics: event                    # RELATION
    columns:
      WorkingDay:
        quantity_kind: indicator              # COLUMN -- one word, and SUM/AVG stop being options
        ruled_by: "calendar_day.working_day.flag_not_quantity"
```

**WHAT YOU GET.** `SELECT COUNT(*) FILTER (WHERE alpha_facts.working_flag = 1) AS alphaflagday ...` — the same number as the old `SUM` where the flag is 1-means-yes, computed as a count, and `SUM`/`AVG` are no longer choices the planner can make.

**HOW TO CHECK IT WORKED**

```bash
cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/proto/harness_landed.py \
  | sed -n '/--- CASE 13:/,/^$/p'
# look for: COUNT(*) FILTER (WHERE ... = 1). A SUM means `indicator` did not land
```

**WHAT IT DOES NOT COVER — a real hazard.** **Which value means yes is not declarable.** The runtime hardcodes `= 1` in `law.py`. A flag where `1 = holiday`, or one encoded `1/2`, is counted backwards, silently. An SME can answer this question and there is nowhere to put the answer. Also: folding a flag across a join still counts the wrong rows (`SUM(WorkingDay)` over order lines joined on `OrderDate` = 160,273 against a true 2,413 of 2,760 — a 66× error), and the `indicator` declaration does not prevent the join; it only fixes the operator. And the alias still reads `workingdaytotal` — the arithmetic is governed, the wording is not.

---

### S14 · Counting the things
*(case 14 · contoso · 109,120 → 67)*

**WHEN YOU HAVE THIS.** Anyone will ask "how many X". The relation is served at a grain that is *not* one-row-per-thing, or the thing's canonical key is a surrogate. [measured here] read-only: `dim_contoso_store` = **74 rows / 74 distinct StoreKey / 67 distinct StoreCode**, and `identity.canonical_key` is `StoreKey` — the number the ruling forbids.

**THE CONFIGURATION**

```yaml
concepts:
  Store:
    counts_as: StoreCode                      # CONCEPT -- the one fact in this design no machine
                                              #   can reach. The law REFUSES to pick between two
                                              #   declared candidates, by design
    ruled_by: "STR-Q1 (ruled verbally) -- a store is the code: 67, never 74 versions"
```

**WHAT YOU GET.** `count_distinct` over the collapsed rows, in place of whatever numeric column the concept happened to declare:

```sql
SELECT COUNT(DISTINCT fold_cycle.StoreCode) AS store
FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY StoreCode ORDER BY OpenDate DESC) AS mac_fold_rank
      FROM dim_contoso_store) fold_cycle
WHERE fold_cycle.mac_fold_rank = 1
```

**HOW TO CHECK IT WORKED**

```bash
cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/manual/ask.py Store
# look for: COUNT(DISTINCT ... StoreCode). SUM(SquareMeters) means counts_as did not land
```

**WHAT IT DOES NOT COVER — three things, all measured.**

1. **`counts_as` is consulted unconditionally.** [measured here] "stores by country" and "stores by geography" both come back as `COUNT(DISTINCT StoreCode)` grouped by the axis. There is no question-shape condition, so once you declare it you cannot ask for floor area by country through this concept.
2. **Remove it and the answer is not a refusal — it is a third number.** [measured here] with `counts_as` deleted and the rest of the plane present: `SUM(fold_cycle.SquareMeters)` over the collapsed rows — 99,300 m², confidently, with a collapse disclosure and no hint that a counting question was answered with an area.
3. **It cannot rescue a concept that carries no number.** 11 of 14 non-measure contoso concepts refuse one step earlier, in `_resolve_measure` (`plan.py`), which asks whether the row carries a number at all: *"Customer is declared class 'entity' … its grounding marks no column `field_role: measure`."* Adding a relation plane **and** `counts_as: CustomerKey` yields the identical refusal with the fold law never invoked. Customer is the most obviously countable entity in the bundle (104,990 rows / 104,990 keys) and is unanswerable because a customer row carries no number. That is a one-line ordering defect in `plan.py`, and it caps this design at 3 of 14 countable concepts.
4. Related trap: [measured here] deleting `quantity_kind` from `SquareMeters` while `counts_as` is present changes **nothing** — with a count target the operand list is empty, so G1 is never consulted. A `counts_as` concept is not evidence that the relation's columns are declared.

---

### S15 · A ratio — fold the parts, then divide once
*(case 15 · typed_law)*

**WHEN YOU HAVE THIS.** A share, margin, discount rate or utilisation: a number that is already a quotient on each row. Give-away: `SUM` of it grows without bound (`SUM(NetPrice/UnitPrice)` = 106,901.34 over 113,614 USD lines — a discount rate of 106,901), and the obvious repair is also wrong (`AVG(a/b)` = 0.940917 against the correct 0.940732 — on 118.9m USD of list value, 21,939.92 USD overstated).

**THE CONFIGURATION.** **Identical to S6** — one `per:` naming the denominator. The only difference between S6 and S15 is how many axes the question left folded, and the law has no axis dimension.

```yaml
      gamma_rate:
        quantity_kind: intensive            # COLUMN
        per: gamma_denominator              # COLUMN -- the denominator, on the same relation
        ruled_by: "fold the parts, then divide: SUM(x*d)/SUM(d)"
```

**WHAT YOU GET.** `SELECT SUM(gamma_rate * gamma_denominator) / NULLIF(SUM(gamma_denominator), 0) ...` — stage 2 (row-grain arithmetic) before stage 3 (the fold), which is exactly what the bundle's two `*.derivation.*` rules say in prose.

**HOW TO CHECK IT WORKED**

```bash
cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/proto/harness_landed.py \
  | sed -n '/--- CASE 15:/,/^$/p'
```

**WHAT IT DOES NOT COVER.** A ratio that is **not stored** as a column — contoso's real shape, where net share must be recomputed from two other columns — needs the fold to happen before the division across a *derived* expression. `evaluate_at: after_fold` exists for exactly this, parses into `ConceptPlane`, and is **read by 0 lines of `law.py`**: you can write it and it changes nothing. Until that is implemented, the only route is a `*.derivation.*` rule that owns its own SELECT (stage 2), which is what contoso does.

---

### S16 · Key columns never reach an aggregate
*(case 16 · contoso · the one case already right)*

**WHEN YOU HAVE THIS.** Always. Every relation has keys, and `SUM(OrderKey)` = 535,351,398,885 is available to any chooser that wanders into it.

**THE CONFIGURATION.** **Write nothing.** `quantity_kind: identifier` is derived from `field_role: key` (and from a dataset `primary_key` role) by the `identifier_from_key_role` conformance derivation. [measured here] on contoso with the full plane: **18 identifier entries filled, 0 authored, 0 conflicts**, tier `derived`, `source=derived:identifier_from_key_role`. Across both authored planes, of 20 typed `quantity_kind` tokens, `identifier` is typed **0** times.

**WHAT YOU GET.** G2: `Refusal(fold:type_error)` — *"declared an identifier, not a quantity: folding it produces a number with no referent. Nothing was executed."* Before the plane, the same guarantee existed only as a property of a candidate list: mis-declare `Quantity` as a key and today's chooser still picks it and today's runtime still sums it.

**HOW TO CHECK IT WORKED**

```bash
cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/manual/explain.py --measure GrossSalesAmount --pin currency=USD | head -40
# look for: DERIVED FILLS {'identifier': N, ...} and `kind=identifier ... source=derived:...`
```

**WHAT IT DOES NOT COVER.** A key that is not declared `field_role: key` anywhere is not derived and not protected. The `identifier_from_key_role` derivation also fabricates a column plane entry for a name the relation may not carry (2 of 18 phantom columns were measured in the adjudication) — the membership check that would stop it is proposed and **not landed**.

---

### S17 · A member that is not one of the things (a sentinel)
*(case 17 · contoso · 39.3% of one answer, unlabelled)*

**WHEN YOU HAVE THIS.** One member of a dimension is a placeholder, a channel, an "unknown" bucket or a catch-all. Give-away: a key like `999999`, `-1` or `0`; or a member whose share is far larger than its siblings'. On contoso: `StoreKey 999999` is the web channel and carries **93,550 of 223,974** lines and **86,790,054.13 of 218,814,471.66** net; in the USD gross question specifically, **46,924 of 113,614** lines and **39.3%** of the number.

**THE CONFIGURATION**

```yaml
relations:
  v_contoso_order_line:
    sentinels:                                  # AXIS (one member) -- a list, on the relation
                                                #   whose column carries the member
      - column: StoreKey                        # AXIS -- the column
        member: "999999"                        # AXIS -- the member, as a string
        label: "the non-physical channel, not a store"     # AXIS -- what a reader must be told
        share: "93,550 of 223,974 lines and 86,790,054.13 of 218,814,471.66 net"
                                                # AXIS -- derive this from the profile; it is prose
        ruled_by: "store.sentinel.online_is_served"
```

**WHAT YOU GET.** **Byte-identical SQL** plus one sentence, whichever side of the fold the member falls on:

* folded into the total → `[fold law] SENTINEL: StoreKey member '999999' (the non-physical channel, not a store) is folded into this total; it carries ...`
* shown as a row → the same sentence ending `is shown as a row; it carries ...`

A sentinel **never changes a number** and never blocks: disclosures accumulate. Delete the block and the SQL is identical with zero caveats. That is why it is safe to write one down.

**HOW TO CHECK IT WORKED**

```bash
cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/proto/harness_landed.py \
  | sed -n '/--- CASE 17:/,/^$/p'
# look for: the word "sentinel" and your share string in the AFTER line
```

**WHAT IT DOES NOT COVER.** The `share` string is fixed text, so it quotes whatever denominator you typed — on contoso it quotes the all-currency net share (41.8%) beside a USD gross answer (39.3%): right in magnitude, honest about its own denominators, not the share of the number in front of the reader. **At what share a sentinel should refuse rather than annotate is undecided.** And a sentinel is declared per relation: [measured here] the store *dimension* declares none, so "how many stores" returns 67 **including** the non-physical channel, with no sentinel caveat at all. If a sentinel matters on both the fact and the dimension, declare it twice.

---

### S18 · A dimension that republishes (SCD-2)
*(case 18 · contoso · 9,820 m² of 109,120 was one store counted twice)*

**WHEN YOU HAVE THIS.** One row per *version* of a thing, with a validity window: `OpenDate`/`CloseDate`, `valid_from`, `is_current`. Give-away: `COUNT(*) > COUNT(DISTINCT <business code>)` — 74 vs 67 here, with 6 codes at two versions and 1 at three.

**THE CONFIGURATION.** On contoso: **nothing.** `store.yaml` already carries `realized_by: mac.canon.snapshot_collapse` with `params.natural_key: StoreCode`, and the derivation fills `grain_semantics: observation`, `subject_key: StoreCode`, `observed_at: OpenDate`. [measured here] 1 of 1 relations, 0 authored, `tier=derived`. On a bundle with no canon, write S3's `observation:` block by hand.

```yaml
relations:
  dim_contoso_store:
    # grain_semantics: observation            # DERIVED from mac.canon.snapshot_collapse
    # observation: {subject_key: StoreCode, observed_at: OpenDate}   # DERIVED, 0 authored
    # cell_key: [StoreKey]                    # DERIVED -- what makes a ROW unique
    columns:
      SquareMeters:
        quantity_kind: extensive              # COLUMN -- floor area of ONE version; additive
                                              #   ACROSS stores, never across versions
        ruled_by: "STR-Q2 -- floor area of one store version; additive across stores"
```

**KEEP BOTH KEYS.** `cell_key` says what makes a **row** unique (the version). `subject_key` says what the row is a version **of** (the store). Collapsing those two into one field *is* the bug: the shipped collapse partitions by `StoreKey`, which is unique, so **74 of 74** rows survive, the window function runs, costs a sort and removes nothing.

**WHAT YOU GET.** `PARTITION BY StoreCode` → **67 of 74** rows survive → 99,300 m² (verified read-only), plus `[fold law] collapsed to one row per StoreCode (ordered by OpenDate, latest first) BEFORE folding; the relation's cell key is StoreKey, which is the version grain and not the entity.`

**HOW TO CHECK IT WORKED**

```bash
cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/proto/harness_landed.py \
  | sed -n '/--- CASE 18:/,/^$/p'
# look for: PARTITION BY StoreCode. PARTITION BY StoreKey means the canon was not read
```

**WHAT IT DOES NOT COVER.** Everything in S3's "does not cover", plus: the collapse is a window function and **not** `WHERE CloseDate IS NULL` for a measured reason — 9 of 67 store codes have no open version at all, so that filter silently drops 9 shops and every sale they made, while the collapse returns 67 of 67. Do not "simplify" it.

---

### C1 · A price that is also cross-currency
*(the combination that actually occurs: S1 + S6 + S12 + S16 on one column)*

**WHEN YOU HAVE THIS.** The normal shape of a money column on a fact: per-unit, weighted by quantity, denominated by a currency code, on an event relation, beside key columns.

**THE CONFIGURATION — the complete block, all four situations at once**

```yaml
relations:
  v_contoso_order_line:
    grain_semantics: event                    # RELATION (S1)
    derived_by: "no collapse canon and no reporting cycle is declared on this relation"
    # cell_key: [OrderKey, RowNumber]         # DERIVED (S16)
    columns:
      Quantity:
        quantity_kind: extensive              # COLUMN (S1) -- and it is UnitPrice's weight
        ruled_by: "GSA-Q0 -- a count of units accrues per line and accumulates"
      UnitPrice:
        quantity_kind: intensive              # COLUMN (S6)
        per: Quantity                         # COLUMN (S6) -- same relation
        denominated_by: CurrencyCode          # COLUMN (S12)
        ruled_by: "gross_sales_amount.derivation.quantity_times_unit_price"
      NetPrice:
        quantity_kind: intensive              # COLUMN -- repeat per money column; there is no
        per: Quantity                         #   inheritance and no defaulting
        denominated_by: CurrencyCode
        ruled_by: "net_sales_amount.derivation.quantity_times_net_price"
    sentinels:                                # AXIS (S17)
      - column: StoreKey
        member: "999999"
        label: "the non-physical channel, not a store"
        share: "93,550 of 223,974 lines and 86,790,054.13 of 218,814,471.66 net"
        ruled_by: "store.sentinel.online_is_served"
```

**WHAT YOU GET — the guard order decides, and it is fixed.** G4 (unit) runs **before** the operator is chosen, so the currency question is answered first and the `per:` never gets a chance to be wrong:

| question | outcome [measured here] |
|---|---|
| gross sales, `pin=currency:USD` | `SUM(f."Quantity" * f."UnitPrice")` + `WHERE CurrencyCode = :currency` + the sentinel caveat |
| gross sales, no currency | `Refusal(fold:incommensurable)`, 5 members named |
| gross sales, `by=currency` | `GROUP BY f.CurrencyCode`, `SUM(...)` per currency |
| gross sales for 2024, no currency | `Refusal(fold:incommensurable)` — the period does **not** discharge the unit axis |

Note what the `per:` did **not** do here: `GrossSalesAmount` is derived by a rule, so **stage 2 owns the SELECT** (`ops = ['grain_expression', 'sum']`, `select_sql = ''`) and the rule's own `Quantity * UnitPrice` is emitted. `per:` becomes load-bearing only for a question that reads the price column alone ("average unit price"). Both declarations are still correct and both should be written — but only one of them is read on this question.

**HOW TO CHECK IT WORKED**

```bash
cd $PLAT && for q in "GrossSalesAmount pin=currency:USD" "GrossSalesAmount" "GrossSalesAmount by=currency"; do
  MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/manual/ask.py $q | head -3; echo; done
```

**WHAT IT DOES NOT COVER.** Conversion. The refusal offers "convert through the declared conversion derivation" and nothing in the fold law invokes it; the fx relation is `precomputed` and S7 refuses a range, so the declared repair is currently unreachable in one question.

---

### C2 · A level that is also republished, on a relation whose other columns are events
*(the combination: S3 + S1 on one relation — the per-column override)*

**WHEN YOU HAVE THIS.** One relation carrying both flows and levels: `amount` accrues per row while `on_hand` is re-read per site per day. [measured on the synthetic fixture] 7 measures of 5 quantity kinds on one relation, and the relation grain alone mistypes **1 of 7**.

**THE CONFIGURATION**

```yaml
relations:
  alpha_facts:
    grain_semantics: event                    # RELATION -- the DEFAULT for every column here
    columns:
      amount:
        quantity_kind: extensive              # COLUMN -- folds like an event: SUM
        ruled_by: "synthetic Flow"
      on_hand:
        quantity_kind: extensive              # COLUMN -- extensive ACROSS SITES
        observed_as:                          # COLUMN -- the OVERRIDE. Note the key names:
          as_of: fact_date                    #   `as_of` here, `observed_at` on the relation
          subject: site_code                  #   `subject` here, `subject_key` on the relation
        ruled_by: "synthetic Stock -- a level re-observed per site per day"
```

**WHAT YOU GET.** The override wins for that column only, and the collapse is emitted exactly as in S3:

```sql
SELECT SUM(fold_cycle.on_hand) AS alphastock
FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY site_code ORDER BY fact_date DESC) AS mac_fold_rank
      FROM fixture_warehouse.alpha_facts) fold_cycle
WHERE fold_cycle.mac_fold_rank = 1
```
while `amount` on the same relation still folds by plain `SUM`. [measured here] both, in one plane, one process.

**HOW TO CHECK IT WORKED**

```bash
cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/manual/probe.py --bundle typed_law --measure AlphaStock
cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/manual/probe.py --bundle typed_law --measure AlphaFlow
# expect: a ROW_NUMBER subquery for the first, a bare SUM for the second
```

**WHAT IT DOES NOT COVER.** This is **two homes for one fact**, gated but real, and the design records it as the weakest joint in the whole position. The override does not fire the relation-level disclosure: [measured here] `AlphaStock` emits the collapse with **no** `[fold law] collapsed to one row per ...` caveat, because that sentence is written only on the relation-grain branch. A reader of the plan cannot tell the collapse happened. Also: when the override fires, the partition is `{subject} ∪ partitioned`, with the same re-inflation hazard as S3.

---

### C3 · Counting things over a versioned dimension
*(the combination: S14 + S18 — and all four settings were executed)*

**WHEN YOU HAVE THIS.** "How many stores?" on an SCD-2 dimension. Two independent declarations meet, and three of the four combinations give 67 — only one of them for the right reason.

**THE CONFIGURATION**

```yaml
relations:
  dim_contoso_store:
    # observation + subject_key + observed_at  # DERIVED from the canon (S18)
    columns:
      SquareMeters:
        quantity_kind: extensive              # COLUMN (S18)
        ruled_by: "STR-Q2 -- floor area of one store version; additive across stores"
concepts:
  Store:
    counts_as: StoreCode                      # CONCEPT (S14) -- SME only
    ruled_by: "STR-Q1 (ruled verbally) -- a store is the code: 67, never 74 versions"
```

**WHAT YOU GET.** `COUNT(DISTINCT fold_cycle.StoreCode)` over rows collapsed by `PARTITION BY StoreCode`. The four combinations, all executed in the earlier sessions:

| collapse partition | count column | answer | |
|---|---|---|---|
| `StoreCode` | `StoreCode` | **67** | right, for the stated reason |
| `StoreCode` | `StoreKey` | 67 | right by luck |
| `StoreKey` | `StoreCode` | 67 | right by luck |
| `StoreKey` | `StoreKey` | **74** | wrong — and this is the pair today's code holds |

**HOW TO CHECK IT WORKED**

```bash
cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/manual/ask.py Store
# look for BOTH: PARTITION BY StoreCode  AND  COUNT(DISTINCT ... StoreCode)
```

**WHAT IT DOES NOT COVER.** The count survives the S3 re-inflation defect (a `COUNT(DISTINCT StoreCode)` is 67 whether 67 or 74 rows survive) — but any **extensive** measure asked in the same breath does not: [measured here] the same question by geography partitions by 5 columns including `StoreKey`, 74 of 74 rows survive, and floor area goes back to 109,120. A count and an area asked together are not both safe.

---

### C4 · One precomputed column among ordinary ones
*(the combination: S7 at column grain)*

**WHEN YOU HAVE THIS.** A relation of events that carries one column another tool computed for a fixed cell — a modelled reach, an allocated cost, a pre-aggregated index.

**THE CONFIGURATION**

```yaml
relations:
  alpha_facts:
    grain_semantics: event                    # RELATION -- the rest of the relation is events
    columns:
      reach_value:
        quantity_kind: intensive              # COLUMN
        stored_at: [fact_date, site_code]     # COLUMN -- the per-column override of the stored
                                              #   grain: EVERY key column of the cell it exists in
        ruled_by: "synthetic Precomputed -- resolve the stored cell, never fold"
```

**WHAT YOU GET.** G3 at column grain: `Refusal(fold:grain_not_stored)` naming every unpinned key — [measured here] `missing = ['fold:grain_not_stored', 'alpha_facts.fact_date', 'alpha_facts.site_code']`.

**HOW TO CHECK IT WORKED**

```bash
cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/manual/probe.py --bundle typed_law --measure AlphaReach
```

**WHAT IT DOES NOT COVER.** `stored_at` is read from the **first operand that declares it** (`next(... for c in operands ...)`), so a measure reading two precomputed columns with different stored grains silently uses one of them. And as in S7, pinning every key is the only discharge: a period does not count.

---

### C5 · A relation your plane does not mention
*(the situation you are in most of the time)*

**WHEN YOU HAVE THIS.** You declared three relations and the bundle serves six. [measured here] the full contoso plane declares **5 of 6** grounded relations; `dim_contoso_customer` is ungoverned.

**THE CONFIGURATION.** None — and know exactly what that means: `decide()` returns `None` and the planner behaves **exactly as today** for every question anchored on that relation. No guard, no disclosure, no refusal. The fold law is not a floor; it is a law over what you declared.

```bash
# what it does NOT mean: closed world. That switch exists and is not shippable.
cd $PLAT && MAC_FOLD_CLOSED_WORLD=1 .venv/bin/python -m pytest packages/mac-runtime/tests -q | tail -2
# [measured here] 123 failed, 636 passed, 2 skipped, 2 errors -- of 763 collected
```

**WHAT YOU GET.** Today's behaviour, which on a bare total is a plain `SUM` of whatever column the chooser found. 11 of 11 typed measures across the three bundles emit a plain `SUM` with the law off; 4 of 11 refuse with the plane on.

**HOW TO CHECK WHICH RELATIONS ARE GOVERNED**

```bash
cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/manual/explain.py \
  --measure GrossSalesAmount --pin currency=USD | head -8
# RELATIONS  5 of 6 grounded relations declared
#   ungoverned  ['dim_contoso_customer']
```

**WHAT IT DOES NOT COVER.** Declaring a relation **partially** is the dangerous state, not the safe one: once a relation block exists, G1 refuses any operand column with no `quantity_kind`, and a missing `grain_semantics` refuses the whole relation (`fold:undeclared_grain`). Declare a relation completely or not at all.

---

## 6. THE COMMON MISTAKES

Each one: what it looks like, what happens, what to write instead. Mistakes marked **silent** produce no error — that is why they are on this list.

### M1 · `extensive` on a per-unit column — **silent**

```yaml
      duration_minutes:
        quantity_kind: extensive        # WRONG -- "the sum has a name" is false here
```
[measured here] `SELECT SUM(alpha_facts.duration_minutes) ...` — today's wrong number, restored by a declaration. Case 5 goes from correct to wrong, and nothing in the plan says so. The same mistake on a price is how `SUM(Price)` = 898,141.44 over 2,517 of 2,517 products happens.

**Write instead:** `quantity_kind: intensive`, and `per: <the extent column>` if one exists on that relation. Test yourself with one sentence: *"if I add two of these together, do I get a real, bigger one of the same thing?"* Two prices added together are not a price.

### M2 · `grain_semantics` on the column — **silent**

```yaml
    columns:
      amount:
        quantity_kind: extensive
        grain_semantics: event          # WRONG LEVEL -- silently ignored by the loader
```
The column loader reads exactly `quantity_kind`, `per`, `denominated_by`, `denominator_distinct`, `observed_as`, `stored_at`, `ruled_by`, `derived_by`. Anything else in a column block is dropped without a word. [measured here] the relation then has no grain at all: `Refusal(fold:undeclared_grain) — alpha_facts.amount (extensive) has no fold on a UNKNOWN relation.`

**Write instead:** `grain_semantics` at **relation** level, one word, once. If one column genuinely disagrees with the relation, that is `observed_as:` or `stored_at:` — see C2 and C4.

### M3 · Typing a value the gate derives

```yaml
    cell_key: [OrderKey, RowNumber]     # DERIVED from the grounding
    columns:
      StoreKey:
        quantity_kind: identifier       # DERIVED from field_role: key (18 of 18 on contoso)
      Weight:
        denominator_distinct: 2         # DERIVED from the profile -- and this one is WRONG (M6)
  dim_contoso_store:
    grain_semantics: observation        # DERIVED from mac.canon.snapshot_collapse
    observation: {subject_key: StoreCode, observed_at: OpenDate}   # DERIVED, 1 of 1
    sentinels:
      - share: "93,550 of 223,974 ..."  # the SHARE is a profile figure, not a ruling
```
Every one of those lines is filled by a conformance derivation when it is absent. [measured here] removing **every** `cell_key` from both authored planes leaves the score at **16 of 18**. Typing them costs you: a typed value is re-declared at `inferred` tier unless you add `ruled_by`, it drifts from the warehouse (M6), and it hides the fact that the derivation was never checked.

**Write instead:** nothing. Then run `explain.py` and read `DERIVED FILLS` and the per-column `source=derived:...` lines to confirm the gate filled what you expected.

### M4 · `cell_key` where `subject_key` is meant — **silent, and expensive**

```yaml
  dim_contoso_store:
    grain_semantics: observation
    observation:
      subject_key: StoreKey             # WRONG -- that is the VERSION key, and it is unique
      observed_at: OpenDate
```
The collapse then partitions by a unique column: [measured here, read-only] **74 of 74** rows survive, `SUM(SquareMeters)` = **109,120**, of which **9,820 m² is one store counted twice** (6 of 67 codes have two versions, 1 has three). The window function runs, costs a sort, and removes nothing. No error, no warning, no symptom on the page. This is the shipped behaviour today.

**Write instead:** `subject_key` is what the row is a version **of** (`StoreCode`, 67); `cell_key` is what makes the **row** unique (`StoreKey`, 74). Keep both, and let `cell_key` derive. Sanity check in SQL before you trust it: `COUNT(*)` vs `COUNT(DISTINCT <subject_key>)` must differ, and `COUNT(DISTINCT <cell_key...>)` must equal `COUNT(*)`.

### M5 · Using `observed_as` with the relation's key names — **silent**

```yaml
      on_hand:
        observed_as: { observed_at: fact_date, subject_key: site_code }   # WRONG KEY NAMES
```
The two blocks name the same two facts with **different keys**, and the column block reads only `as_of` and `subject`. [measured here] with the relation's names inside `observed_as`, the whole override vanishes: `SELECT SUM(alpha_facts.on_hand) AS alphastock FROM fixture_warehouse.alpha_facts` — no subquery, no collapse, no caveat.

**Write instead:**
```yaml
    observation: { subject_key: site_code, observed_at: snapshot_date }   # RELATION level
      # ...
        observed_as: { subject: site_code, as_of: fact_date }             # COLUMN level
```

### M6 · Hand-typing a denominator count — **measured wrong on this bundle**

```yaml
      Weight:
        denominated_by: WeightUnit
        denominator_distinct: 2         # WRONG. The warehouse says 3.
```
[measured here, read-only] `dim_contoso_product.WeightUnit`: **3** distinct non-null values — pounds 1,867 / ounces 418 / grams 10 — with 222 of 2,517 rows null. This is the only one of the estate's authored tokens that a derivation disagrees with, and the derivation is right. It is also written into `decisions/0004` itself, so the design record carries the wrong number too (**R6, unruled**: amend, or leave).

**Write instead:** omit it and let the profile fill it. G4 fires on `> 1`, so the exact value matters only for the sentence the reader sees — which is precisely why a wrong one is worth catching. If you must pin it, pin it with `derived_by:` naming the profile run, never bare.

### M7 · Expecting an `axes:` block to do anything — **silent**

```yaml
axes:                                   # PARSES. DROPPED. READ BY NOTHING.
  v_contoso_order_line:
    CurrencyCode: { ordered: false, partition_role: partitions }
```
[measured here] appended to the contoso plane, the 18 cases score **16 of 18** — identical to the plane without it. There is no axis level in the plane. `partition_role` is computed inside `law.py` from the relation's own facts and cannot be authored.

**Write instead:** nothing. If you need orthogonality, level-ness or orderedness of an axis, that is S11 and it is unbuilt — raise it rather than writing a block that reads as if it worked.

### M8 · Typing the dead tokens

```yaml
        per: __rows__                   # identical code path to silence: `per in (None, "__rows__")`
  GrossSalesAmount:
    evaluate_at: grain                  # parsed into ConceptPlane, read by 0 lines of law.py
      WorkingDayNumber:
        quantity_kind: ordinal          # load-bearing on 0 of 18 -- keep the framework term,
                                        #   stop asking anyone to type it
```
9 of 52 authored tokens across the two planes are measurably dead (6 × `per: __rows__`, 2 × `evaluate_at`, 1 × `ordinal`); ablating all nine holds **16 of 18** at 43 tokens.

**Write instead:** omit them. But know the difference between *dead* and *unreached*: 7 of the 14 tokens the 29-token floor drops are unreached rather than dead — they come back the day the multi-measure bail-out is fixed, and 2 of 30 diagnoses degrade from specific to generic without them. **UNRULED (R4)**: which plane ships — 29 tokens, 28, 43 or 52.

### M9 · Declaring a relation half-way

```yaml
  v_contoso_order_line:
    columns:                            # a block exists, so the relation is GOVERNED...
      Quantity:
        quantity_kind: extensive
                                        # ...and grain_semantics is missing: UNKNOWN MEANS DENY
```
Once a relation block exists, absence stops being neutral: a missing `grain_semantics` refuses every question on the relation (`fold:undeclared_grain`), and an operand column with no `quantity_kind` refuses at G1 (`fold:no_fold_law`). A half-declared relation is **worse than an undeclared one**.

**Write instead:** for each relation you touch, at minimum one `grain_semantics` and one `quantity_kind` per measure column you expect to be asked for. Then check with `explain.py` that `RELATIONS n of m` is the n you meant.

### M10 · Expecting `confirmed` without saying who ruled it

```yaml
      Price:
        quantity_kind: intensive        # no ruled_by -> tier `inferred`, the weakest
```
[measured here] `Cost`, `Price` and `Weight` come back `tier=inferred` in the full contoso plane for exactly this reason, and an answer takes the **meet** of everything it touched — so one silent entry downgrades the whole answer. Omission is not neutral; it is the weakest claim available.

**Write instead:** `ruled_by: "<the rule id or the sentence the person said>"` when a person ruled it; `derived_by: "<what computed it>"` when a gate did. Never dress a guess as either.

### M11 · Editing the plane in a live process

`load_plane` caches by `f"{directory}|{hash(relations)}"`. Edit the YAML in a long-running process (a notebook, a server, a test session) and you keep reading the old plane.

**Write instead:** a new process per check, or `from mac_runtime.foldplane import planes; planes.clear_cache()`. All three probes in the appendix call `clear_cache()` first.

### M12 · Naming a plane entry after a relation another bundle serves

Plane files in `MAC_FOLD_PLANE_DIR` are merged into **one flat namespace keyed by relation name**. A block called `orders` governs every bundle and fixture with a relation called `orders`; the adjudication measured a plane named that way failing **59 of 763** runtime tests.

**Write instead:** the served relation's real, qualified name — `v_contoso_order_line`, `dim_contoso_store`. Keep one file per bundle and never reuse a fixture relation name.

### M13 · Expecting a sentinel to refuse, or to change a number

A sentinel is a **disclosure**. It never blocks, never filters, never changes the SQL. [measured here] case 17's SQL is byte-identical with the block present and absent; only the caveat list differs. At what share a sentinel should invalidate rather than annotate is undecided.

**Write instead:** if the member must be excluded, that is a filter in the question or a rule in the bundle — not a sentinel.

---

## 7. HOW DO I KNOW IT IS ON

### The four switches, and their defaults

| env var | default | what it does | measured cost |
|---|---|---|---|
| `MAC_FOLD_ENABLED` | **`1` (on)** | `0`/`false`/`no` → `decide()` returns `None` immediately; `plan()` is today's runtime exactly | the harness's BEFORE column: **3 of 18** |
| `MAC_FOLD_PLANE_DIR` | **unset** | the directory of `*.fold.yaml` files. Unset = no plane = every relation ungoverned | unset: **3 of 18**; the floor plane: **16 of 18**; the full plane: **16 of 18** [measured here] |
| `MAC_FOLD_LEGACY_FIRST` | **`1` (legacy first)** | `0` → the legacy `semantics.additivity` guard stops being read and the fold law is the only law | `0`: **17 of 18**, and 6 named tests of 1435 to re-point. **UNRULED (R3)** |
| `MAC_FOLD_CLOSED_WORLD` | **`0` (off)** | `1` → a relation with no plane **refuses** instead of falling through | `1`: [measured here] **123 failed, 636 passed, 2 skipped, 2 errors of 763** in the runtime suite alone. Not shippable |

With `MAC_FOLD_ENABLED` on and a plane dir set, the estate's suites are unchanged: [measured here] `packages/mac-runtime/tests` **761 passed, 2 skipped** and `tests` **671 passed, 1 skipped** — identical with and without `MAC_FOLD_PLANE_DIR`. **0 of 1435 tests move.**

### Did my plane get read?

Three signals, in order of reliability:

1. **`explain.py`** prints the plane as loaded — the only complete answer:
   ```bash
   cd $PLAT && MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/manual/explain.py \
     --measure GrossSalesAmount --pin currency=USD
   # PLANE DIR        '<...>'
   # RELATIONS        5 of 6 grounded relations declared
   #   ungoverned     ['dim_contoso_customer']
   # DERIVED FILLS    {'identifier': 18, 'observation': 1, 'conflict': 0}
   #   <relation>: grain=event tier=derived subject=None observed_at=None cell_key=[...]
   #       UnitPrice   kind=intensive per=Quantity unit=CurrencyCode n_units=5 tier=confirmed source=overlay
   ```
   `conflict: n > 0` means a derivation disagreed with something you typed — investigate before shipping.
2. **A refusal whose `missing[0]` starts with `fold:`** is proof the law ran. The six `ReasonCode` members are pinned by a golden schema test, so the fold sub-code travels in `missing[0]`, not in `reason_code`.
3. **A `[fold law]` caveat** is sufficient but **not necessary**: cases 6, 13 and 15 are governed and emit no caveat at all. Never conclude "the plane was not read" from a plan with no caveats.

### Reading the provenance tier of an answer

**You cannot, from the answer.** `Plan` is `extra="forbid"` with six fields (`sql_preview`, `params`, `concepts_used`, `rules_used`, `edges_used`, `caveats_known`) and carries no tier; `planner/sql.py` consumes `fold.select_sql`, `fold.window` and `fold.disclosures` and **not** `fold.tier`. The tier is computed by `meet()` over the relation entry, every operand column and the concept entry — and then dropped.

In process, `explain.py` prints it:

```
DIRECTIVE ops    ['grain_expression', 'sum']
  FOLDED         ['CustomerKey','DeliveryDate','FromCurrency','OrderDate','OrderKey','ProductKey','RowNumber','StoreKey','ToCurrency']
  pinned         ['CurrencyCode']
  TIER           derived  (computed, and dropped: Plan carries no tier)
```

The rules, so you can predict it: `ruled_by:` → `confirmed`, `derived_by:` → `derived`, silence → `inferred`; the answer is the **weakest** of everything it touched. Derivation does not launder provenance — a mechanically derived value over inferred inputs is `inferred`.

**UNRULED (R8):** how a fold disclosure reaches a reader at all. `CaveatKind` is closed at `dq | open_question | staleness` and the console promotes a caveat to the answer card only under one prefix, so a `[fold law]` sentence reaches the trace and not the page. The recommendation on the table is to route fold disclosures through `open_question`; nothing is ruled.

---

## 8. HONEST LIMITS

### What cannot be expressed at all

| you want to say | status |
|---|---|
| "use the median / the 90th percentile" | one mean family, no operator parameter. Not expressible |
| "weight it by time, not by a column" | `per:` names a column; an interval length is not one |
| "this amount is in thousands of the currency" | composite and scaled units: not expressible |
| "this is additive here and not there" | **by design**: no property is a function of the question's filters. The axis-dependence lives in the guards, never in a token |
| "the regional goal splits to stores like this" | allocation / disaggregation: **0 hits** for the concept in the design and all three runtime modules |
| "brand and category are independent" / "one is a level of the other" / "a product can have two brands" | no axis level in the plane. An `axes:` block is dropped (M7) |
| "1 means holiday, not working day" | the runtime hardcodes `= 1` for `indicator` |
| "this categorical axis is ordered (small < medium < large)" | `mac.axis_kind` conflates orderedness with temporality and is **not read** |
| "by currency means the currency we convert INTO" | no term for the direction of an ordered pair |
| "at 40% share, stop answering and refuse" | the sentinel threshold is undecided |
| "this ratio is not stored; recompute it after the fold" | `evaluate_at: after_fold` parses and is read by 0 lines |
| "show the rows in this order" / "top 5" | **deliberately excluded** from the fold law (`decisions/0004` §4 role 4). `Intent` carries no sort and no top-N, and the planner emits no outer `ORDER BY` |
| "two independent re-observation clocks meet here" | undefined |

### The four things an SME can say and the system cannot hold

These have been answered out loud, by a person, on this estate, and there is nowhere to put the answer:

1. *"1 is the working day, not the holiday"* — measured in prose (2,760 of 4,018 days), no field.
2. *"A brand is not a kind of category; they are two ways of slicing the same product"* (and *"can one product carry two brands?"*) — no axis level; the block that looks like the answer is dropped.
3. *"By currency, about a quote, means the money we convert FROM"* — known in prose, no term.
4. *"The goal was set per region; nobody may ask it per store"* — rolling up works, splitting down has no term, and `stored_at` is the wrong tool (it refuses the up-fold too).

### And the limit under all four: nothing files the question

A fold refusal names the file, the relation, the column and the missing key — and then forgets. [measured here] `open_question_id=None` at **15 of 15** construction sites under `packages/*/src` (`planner/plan.py` ×9, `planner/resolve.py` ×4, `planner/joins.py` ×1, `foldplane/law.py` ×1) and **0 of 15** pass anything else. The downstream path already exists (`CaveatKind.OPEN_QUESTION` is a member of the closed set; caveat propagation is documented as mandatory; the console renders it). Nothing is missing but the assignment. Until it lands, "the SME will be asked when a question needs it" is not a workflow — and refusal-driven authoring has a measured ceiling anyway: a refusal can name only **2 of 11** plane terms, and the fixpoint is **8 of 18**.

### Two boundaries on every number in this file

* **No SQL was executed by the fold work.** Every outcome above is a plan or a refusal. Where a *number* is quoted (67, 99,300, 109,120, 3 weight units, 5 currencies), it was measured separately with a read-only connection to `contoso.duckdb` against `contoso_served.*`.
* **n = 1.** One real bundle has an authored plane. Every tier count, every precision figure and every "derived n of n" in this manual is measured on contoso plus two synthetic fixtures.

---

## 9. REFERENCE TABLES

### 9.1 `quantity_kind` — 5, closed, **COLUMN** grain

| word | the test | you get | who fills it |
|---|---|---|---|
| `extensive` | add two and you get a real, bigger one of the same thing | `SUM` | SME. 0 of 9 contoso measure columns are derivable from any declared type or profile statistic |
| `intensive` | the word "per" fits the sentence | weighted mean with `per:`, else plain `mean` + a non-composition disclosure | SME |
| `indicator` | two values, 0 and 1, really a yes/no | `COUNT(*) FILTER (WHERE col = 1)` | SME; derivable from a 0/1 profile (fires on 1 of 30 contoso numeric columns) |
| `ordinal` | it orders things and the gaps are not amounts | `Refusal(no_order_stat)` | SME only. The dense-sequence heuristic proposes it on 8 of 30 and is wrong on 2 of 8 — it may **fail** an authored value, never supply one |
| `identifier` | a label that happens to be numeric | `Refusal(type_error)` | **the gate**, from `field_role: key`. 18 of 18 on contoso, 0 authored |

### 9.2 `grain_semantics` — 4 + `UNKNOWN`, **RELATION** grain

| word | one row is | extra payload | who fills it |
|---|---|---|---|
| `event` | something that happened, once | — | SME confirms; the gate proposes 5 of 5 on contoso |
| `observation` | the same subject, read again | `observation: {subject_key, observed_at}` | the gate, from `mac.canon.snapshot_collapse` + `params.natural_key` (1 of 1, 0 authored) |
| `plan` | a number somebody asserted | — (the disclosure is automatic) | SME |
| `precomputed` | a cell another tool computed | the relation's `cell_key` **is** the stored grain | SME |
| `UNKNOWN` | **absence** | — | nobody. **UNKNOWN MEANS DENY**: `Refusal(fold:undeclared_grain)` |

### 9.3 The 10 operators, with stage and composition

| operator | stage | composes | operands |
|---|---|---|---|
| `collapse_to_identity` | 0 collapse | yes | `subject_key`, `observed_at` |
| `resolve_last` | 1 resolve | yes | `x`, `order_by`, `partition` |
| `resolve_match` | 1 resolve | yes | `x`, `on` |
| `grain_expression` | 2 row-grain arithmetic | yes | `template` |
| `sum` | 3 fold | yes | `x` |
| `weighted_mean` | 3 fold | yes | `x`, `w` |
| `mean` | 3 fold | **no — measured** | `x` |
| `count_filtered` | 3 fold | yes | `x`, `pred` |
| `count_distinct` | 3 fold | yes | `c` |
| `refuse` | 3 fold | yes | `code` |

Stages run in numbered order, and stages 0 and 1 **coincide** when the collapse identity is also the resolve partition — which is why S14 and S18 agree by construction rather than by coincidence. `composes: no` on `mean` is arithmetic, not taste: the one-shot and staged means differ (32.000000 vs 32.500000 on unequal groups), and the plan says so out loud.

### 9.4 The 25 cells — `LAW[grain_semantics][quantity_kind]`

| | `extensive` | `intensive` | `indicator` | `ordinal` | `identifier` |
|---|---|---|---|---|---|
| `event` | `sum` | `weighted_mean` | `count_filtered` | `refuse(no_order_stat)` | `refuse(type_error)` |
| `observation` | `sum` | `weighted_mean` | `count_filtered` | `refuse(no_order_stat)` | `refuse(type_error)` |
| `plan` | `sum` | `weighted_mean` | `count_filtered` | `refuse(no_order_stat)` | `refuse(type_error)` |
| `precomputed` | `resolve_match` | `resolve_match` | `resolve_match` | `resolve_match` | `resolve_match` |
| `UNKNOWN` | `refuse(undeclared_grain)` | `refuse(undeclared_grain)` | `refuse(undeclared_grain)` | `refuse(undeclared_grain)` | `refuse(undeclared_grain)` |

25 of 25 filled; `len(LAW) == 25` is asserted at import and re-asserted by `test_foldplane_law.py` (**3 tests, 3 passed** [measured here]). An `observation` relation folds exactly like an `event` on every axis it does not re-observe on; the re-observation axis is intercepted **before** this table is read, in the stage section, by `partition_role == "reobserves"`. `weighted_mean` degrades to `mean` when `per` is absent or `__rows__`. **Nobody authors this table**, and a sixth `quantity_kind` breaks `test_the_law_is_total`.

### 9.5 The refusal codes — what each means, what to do

The sub-code is `missing[0]`, formatted `fold:<code>`. `reason_code` is one of the closed 6 `ReasonCode` members (a golden schema test pins the enum), so read `missing[0]`, not `reason_code`. `open_question_id` is `None` at every site.

| `missing[0]` | `reason_code` | what happened | what to do about it |
|---|---|---|---|
| `fold:no_fold_law` | `ontology_gap` | G1: an operand column has no `quantity_kind` | declare the one word on that column (S1/S5/S13), or accept the refusal as correct |
| `fold:undeclared_grain` | `ontology_gap` | the relation has columns but no `grain_semantics` — **or** closed world is on and the relation has no plane at all | one word at **relation** level (9.2). Check you did not write it on the column (M2) |
| `fold:type_error` | `unsupported_intent` | G2: an `identifier` reached by an aggregate | the question, the chooser or `field_role` is wrong. Nothing to declare |
| `fold:no_order_stat` | `unsupported_intent` | G2: an `ordinal` reached by an aggregate | rank or sort by it; a total or mean of it is not a number |
| `fold:grain_not_stored` | `additivity_violation` | G3: a `precomputed` cell asked coarser than it is stored; the message names every unpinned key | pin **or** group every key column (S7/S8/C4). A period does not discharge a date key |
| `fold:incommensurable` | `additivity_violation` | G4: the `denominated_by` column is folded and carries >1 member | pin one unit, group by the unit, or convert (S12). Three repairs, all named in the message |
| `fold:mixed_quantity_kinds` | `ontology_gap` | G5: one measure reads columns of different kinds and names no derivation | give the measure a `*.derivation.*` rule that consumes them at row grain, or split it |

Refusals you will meet that are **not** the fold law (do not try to fix them with a plane): `no_join_path` (S11), *"nothing declares a number it carries"* (`_resolve_measure`, S14 note 3), *"N columns are declared the same way"* (the column chooser, upstream of the plane).

---

## 10. APPENDIX — the three probes

Uncommitted scratch tools, all three used for every `[measured here]` figure in this file. They read the bundle and the plane, execute no SQL and open no database.

| tool | path | what it prints |
|---|---|---|
| `ask.py` | `$SP/manual/ask.py` | one question → `Plan`/`Refusal`, the SQL, the caveats |
| `probe.py` | `$SP/manual/probe.py` | the same, with `--bundle contoso\|legacy_stock\|typed_law`, `--by`, `--pin`, `--period` |
| `explain.py` | `$SP/manual/explain.py` | the plane as loaded (coverage, derived fills, per-column tier and source) **plus** `FOLDED`/`partitioned`/`pinned`, the ops and the tier |
| `harness_landed.py` | `$SP/proto/harness_landed.py` | all 18 cases, BEFORE and AFTER, in one process, plus the bare-total sweep |

`ask.py` in full — 26 lines, and the shortest thing that answers *"did my declaration land?"*:

```python
import os, pathlib, sys
from mac_console.ask_engine import load_bundle
from mac_runtime.models import Intent, SliceRef, FilterRef, FilterOp
from mac_runtime.planner.plan import plan
from mac_runtime.resolver.enumeration import EnumerationResolver
from mac_runtime.resolver.lookup import LookupResolver
from mac_runtime.resolver.register_match import RegisterResolver

BUNDLE = pathlib.Path(os.environ.get("MAC_BUNDLE", "mac-ontology-contoso"))
b = load_bundle(BUNDLE.name, BUNDLE.name, BUNDLE)
r = RegisterResolver(b.registers, inner=EnumerationResolver(
    b.index, inner=LookupResolver(b.index, b.registers.entries)))
measure, *rest = sys.argv[1:]
by = [SliceRef(term=a[3:], utterance=a) for a in rest if a.startswith("by=")]
pin = [FilterRef(term=a[4:].split(":")[0], op=FilterOp.EQ, value=a[4:].split(":")[1], utterance=a)
       for a in rest if a.startswith("pin=")]
out = plan(Intent(measure=measure, slices=by, filters=pin, confidence=0.9), b.index, r)
print(type(out).__name__)
print(getattr(out, "sql_preview", "") or getattr(out, "human_reason", ""))
for c in getattr(out, "caveats_known", []) or getattr(out, "missing", []):
    print("   ", c)
```

```bash
# usage -- and remember a new process per edit (M11)
cd $PLAT
MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python ask.py GrossSalesAmount pin=currency:USD
MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python ask.py Store
MAC_BUNDLE=/path/to/other-bundle MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python ask.py <Measure> by=<term>
```

### The one-command regression you should run before committing a plane

```bash
cd $PLAT
MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python $SP/proto/harness_landed.py | tail -6
#   CORRECT AFTER : 16 of 18      <- the floor and the full plane both reach this
#   REGRESSED     : 0 of 18       <- this is the number that must never move
MAC_FOLD_PLANE_DIR=<plane dir> .venv/bin/python -m pytest packages/mac-runtime/tests tests -q | tail -2
#   expect 1432 passed, 3 skipped of 1435 collected -- unchanged with the plane on
```

---

## 11. WHAT IS STILL UNRULED — the short list, so nothing here reads as settled

| ref | question | this manual's stance |
|---|---|---|
| **R1** | Does the plane live in `fold/<bundle>.fold.yaml` (schema first), or stay behind `MAC_FOLD_PLANE_DIR`? | every block is written in the form the landed code reads; the keys are identical under the recommended home (§3) |
| **R2** | Adopt the 5 derivations that read the legacy fields `0004` deletes? | not used here. The blocks assume only the 10 admissible derivations plus the 2 landed ones |
| **R3** | `MAC_FOLD_LEGACY_FIRST=0`? | S4 is documented as **not fixed** under the default, and the switch is named with its cost |
| **R4** | Which plane ships: 29 tokens, 28, 43 or 52? | the blocks show the **complete honest declaration** per situation, and M8 marks what is dead versus merely unreached |
| **R5** | Does the SME edit the file directly, or only answer filed questions? | this manual assumes direct editing; §8 records that nothing files a question today |
| **R6** | `Weight.denominator_distinct` is 2 in the design record and 3 in the warehouse | M6 states the measurement and recommends deriving it |
| **R8** | Do fold disclosures reach a reader, and through which caveat kind? | §7 states that today they reach the trace and not the page |

**Nothing in this file is a ruling.** It is what to write so that the thing you meant is what the law reads.
