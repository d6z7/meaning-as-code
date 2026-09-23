<!-- STATUS: PROPOSED. This describes decisions/0004 in mac-ontology-contoso, which the operator
     has NOT ratified. The code it documents is landed and INERT: the law is consulted only where a
     bundle declares a fold plane, and no bundle declares one. Two points ARE ruled and marked so.
     Do not treat this as framework guidance until 0004 is ratified.

     AND 0004 IS SUPERSEDED IN APPROACH BY 0005, which this header used to omit. 0005's words:
     "Its measurements stand; its proposal largely should not be built. The premise all three
     records share — that the model needs new declarations — was measured wrong: the facts are
     mostly declared already and the runtime does not read them." So: the MEASUREMENTS below are
     sound and were taken against the real warehouse. The PROPOSAL — a new fold plane a bundle
     authors — is the shape 0005 warns against, and should be weighed against wiring what is
     already declared before any of it is built. Read 0005 first.

     See QUERY_GRAMMAR.md for the orthogonal axis (what a question contributes to a SELECT). -->

# THE FOLD GRAMMAR
### How to say what a number means, in words a domain expert can check

You have the design. This is how to use it. Nothing here is new work: every number below was measured, most of them tonight, read-only, against the real warehouse and the landed code. Where something is unhandled, it says so in the same voice.

---

## 1. THE GRAMMAR IN ONE PAGE

### The four sentences

There are four places a fact can live, and each one answers exactly one question.

1. **The COLUMN says what kind of number this is.** Does it accumulate, or is it a per-something figure, or a yes/no, or a rank, or a name written in digits? One word.
2. **The RELATION (the table) says how its rows came to exist.** Did something happen, or was the same thing read again, or did somebody promise it, or did another tool already work it out? One word, once per table.
3. **The CONCEPT says what one of these *is*, and whether it is observed or planned.** "A store is the business code, not the version row." "This figure is a promise, not a measurement."
4. **The FRAMEWORK says what may be done to each kind of number on each kind of table.** Nobody writes this. It ships with the runtime as a 25-cell lookup, and a drift test recomputes it and reds on disagreement.

That is the whole shape. Everything else in the design is either derived from data you already have, or a name for one of those four things.

### The one word that is not a level: **fold**

**"Fold" means the axes your question did not name.**

Ask *"sales by country"* and you preserved country. You folded store, product, day, customer and currency — they vanished into each row of the answer. `GROUP BY` **preserves** an axis; folding happens to everything else:

```
FOLDED = every axis of the fact  minus  (the ones you grouped by  +  the ones you pinned with a filter)
```

This is the whole defect the design fixes. The old guard was consulted on the axes a question **named**. Measured: a bare total ("total gross sales") was checked on **0 axes** — and it is the question that folds the most. Nine axes at once, examined on none. The new law is consulted on the nine.

Once you have that sentence, the rest reads.

### The decision procedure — five steps, with a pencil

For one number on one table:

**Step 1 — Name the number.** Which column actually carries the figure someone asks for? (If two columns are declared the same way, the system refuses before any of this: *"3 columns are declared the same way (Cost, Price, Weight), so nothing says which one."* That refusal is upstream of the fold plane and has to be fixed first.)

**Step 2 — Say what kind of number it is.** One word from five. The test is one sentence: *"If I add two of these together, do I get a real, bigger one of the same thing?"* Section 2 has all five words and their give-aways.

**Step 3 — Say how the table's rows came to exist.** One word from four: `event`, `observation`, `plan`, `precomputed`. On contoso the gate already proposes this for **5 of 5** declared relations; you confirm it.

**Step 4 — If step 2 said `intensive`, name what it is *per*.** A price is per unit → `per: Quantity`. And if the number can be in different units on different rows, name the column that says which → `denominated_by: CurrencyCode`. The count of units in play is measured for you, never typed.

**Step 5 — If anyone will ever *count* these things, say which column one of them is.** `counts_as: StoreCode`. This is the only fact in the whole design that no machine can reach, and it is the difference between 67 and 109,120.

Then the framework does four things, in a fixed order, and you can follow it with the same pencil:

- **the guards**, in order, first failure wins: **G1** no declared kind → refuse (never a silent SUM); **G2** an identifier or an ordinal reached by an aggregate → refuse; **G3** a precomputed value asked coarser than the cell it was stored at → refuse; **G4** the unit column is folded and carries more than one member → refuse; **G5** one figure reads two different kinds of column and names no rule for combining them → refuse.
- **the lookup**: `LAW[how the rows came to exist][what kind of number]` → one operator.
- **the stages**, in numbered order: `0` collapse re-published rows to one per subject · `1` resolve a stored cell · `2` do the row-level arithmetic · `3` fold. Ten operators, each carrying its stage and whether it **composes** — i.e. whether a breakdown and a grand total agree. `weighted_mean` composes; a plain `mean` does not, and the plan says so out loud.
- **the provenance**: `ruled_by:` means a person said so → **confirmed**. `derived_by:` means a gate computed it → **derived**. Silence → **inferred**, the weakest. The answer takes the *weakest* tier of everything it touched. Derivation does not launder provenance, and nothing can be dressed as fact by leaving the token out.

---

## 2. THE FIVE WORDS

One word per number column. These are the five, and the give-away that tells you it is this one and not its neighbour.

### `extensive` — it accumulates
**The question:** *"If I add two of these together, do I get a real, bigger one of the same thing?"*
**Yes → extensive.** Two units sold plus three units sold is five units sold. January's goal plus February's goal is the two-month goal. Store A's floor area plus store B's is their combined floor area.
**Real examples:** `v_contoso_order_line.Quantity`, `dim_contoso_store.SquareMeters`.
**Give-away against `intensive`:** the sum has a name. "Total units sold" is a thing. "Total price" is not.
**What you get:** `SUM`.

### `intensive` — it is per something
**The question:** *"Is this a price, a rate, a speed, a duration, a percentage — a per-something figure?"*
**Real examples:** `UnitPrice`, `dim_contoso_product.Price`, `v_contoso_fx_rate_day.Exchange`.
**Give-away:** the word "per" fits in the sentence. A price is per unit. A rate is per one unit of the other currency.
**The proof it matters:** `SUM(Price)` over the catalogue measures **898,141.44** across **2,517 of 2,517** products. The catalogue does not cost 898 thousand of anything — prices are per unit, and there is no unit called "the whole catalogue". `SUM(UnitPrice)` on USD lines measures **37,694,027.89** over **113,614 of 223,974** lines: 113,614 price tags added up.
**What you get:** an average — **weighted by whatever you named in `per:`**. And the weighting is not fussiness. Measured, USD only: the plain average of `UnitPrice` is **331.772738**; weighted by units it is **333.691614**. Worse, the plain average will not stack — staged over the 32 subcategories it gives **395.233809** against the one-shot **331.772738**, on the same rows. The weighted one gives **333.691614** both ways, identical to six decimals.

### `indicator` — a yes/no written as 0 and 1
**The question:** *"Does this column only ever hold two values, and is it really a yes-or-no?"*
**Real example:** `dim_contoso_calendar_day.WorkingDay` — **4,018** rows, exactly **2** distinct values, min 0, max 1, **2,760** working days and **1,258** not.
**Give-away against `extensive`:** the sum of it is a *count of rows*, not an amount. "Working Day Total: 2,760" is a count wearing a total's name. And `AVG(WorkingDay)` = **0.6869** — "0.69 working days" is a proportion wearing a quantity's name.
**Why it is not harmless:** fold the same flag across a join and the number is simply wrong. `SUM(WorkingDay)` over the order lines joined on `OrderDate` = **160,273** — a count of order *lines* that fell on a working day. The true answer to "how many working days did we sell on" is **2,413 of 2,760**. A 66× error with no symptom.
**What you get:** `COUNT(*) FILTER (WHERE flag = 1)`, and `SUM` / `AVG` of it stop being choices the planner can make at all.

### `ordinal` — order, and no arithmetic
**The question:** *"Does this column put things in an order — 1st, 2nd, 3rd — rather than measure an amount?"*
**Real example:** `WorkingDayNumber`.
**Give-away against `extensive`:** the gap between 1 and 2 is not a quantity of anything. You may sort and rank by it; a total or an average of it is not a number.
**What you get:** a refusal, by name: *"declared an ordinal, not a quantity: it has an order and no arithmetic."*
**Honest note:** on this bundle `ordinal` is load-bearing on **0 of 18** cases. Keep the word in the framework; nobody needs to type it today. And no machine may guess it: the obvious heuristic (a dense integer sequence must be a rank) proposes `ordinal` on **8 of 30** contoso numeric columns and is **wrong on 2 of 8** — one of them `Quantity`, the most load-bearing measure in the bundle. So that test is allowed to *fail* an authored value and never to *supply* one.

### `identifier` — a name written in digits
**The question:** *"Is this a key — a label that happens to be numeric?"*
**Real examples:** `OrderKey`, `RowNumber`, `StoreKey`, `CustomerKey`, `ProductKey`.
**Give-away:** you would never ask "how much" of it. `SUM(OrderKey)` = **535,351,398,885** and `SUM(RowNumber)` = **260,100** over 223,974 rows. Neither is a quantity of anything.
**What you get:** a refusal — *"folding it produces a number with no referent."*
**And you never type it.** **18 of 29** columns in the contoso plane carry `identifier`, and **18 of 18** were filled by the gate from `field_role: key`, precision **8 of 8**. No SME is ever asked about a key column.

**The whole column vocabulary is those five words, plus `per:` when the word was `intensive`.**

---

## 3. WHAT DO I ACTUALLY TYPE?

### The loud answer first

**In the common case: one word per measure column, and nothing else.**

That is measured, not hoped:

- **60 of 71** contoso columns need **zero** words.
- Of the **10** columns that carry any declaration, **6 carry exactly one word** (`Quantity`, `SquareMeters`, `Exchange`, `WorkingDay`, `Cost`, `Price`), `Weight` carries two, and **3 carry three** — `UnitPrice`, `NetPrice`, `UnitCost`, whose two extra words are `per: Quantity` and `denominated_by: CurrencyCode`, i.e. exactly the two sentences the bundle already writes out as prose ("a price is per unit", "no bare cross-currency sum").
- **One word per table** for `grain_semantics` — and on contoso the gate proposes all **5 of 5**.
- **Nothing** for identifier columns (18 of 18 derived), **nothing** for `cell_key` (5 of 5 derived), **nothing** for the store table's collapse (1 of 1 derived from a canon already in the bundle), **nothing** for any counted share.

The vocabulary a modeller must actually learn to reach 16 of 18 is **two words: `extensive` and `intensive`.** Measured across both authored planes, of 20 typed `quantity_kind` tokens: `intensive` 10, `extensive` 7, `indicator` 2 (and derivable from a 0/1 profile), `ordinal` 1 (load-bearing on 0 of 18), `identifier` **0 — never typed**.

### The minimal recipe for a new measure column

```yaml
# file: <MAC_FOLD_PLANE_DIR>/<bundle>.fold.yaml
# In production these are `x-` keys on data/datasets/<relation>.yaml, which the
# runtime ALREADY parses (71 of 71 contoso columns) and which sits OUTSIDE
# ontology/ -- so the armed lock does not govern it.

relations:
  v_contoso_order_line:                # RELATION level -- one block per served table.
    grain_semantics: event             # RELATION: how these rows came to exist. One word.
                                       #   Gate proposes it; you confirm.
    ruled_by: "an order line happens once and is never re-stated"
                                       # PROVENANCE (any level) -> tier `confirmed`.
    # cell_key: [OrderKey, RowNumber]  # RELATION, DERIVED -- do NOT type it. 5 of 5.
    columns:
      Quantity:                        # COLUMN level.
        quantity_kind: extensive       # COLUMN: the one word. THIS IS THE WHOLE COMMON CASE.
        ruled_by: "a count of units accrues per line and accumulates"
      UnitPrice:                       # COLUMN level -- the uncommon case, three lines.
        quantity_kind: intensive       # COLUMN: a per-unit figure.
        per: Quantity                  # COLUMN: what it is per. Must name a column of the
                                       #   SAME table, so a gate can check it exists.
        denominated_by: CurrencyCode   # COLUMN: which column names this number's unit.
        # denominator_distinct: 5      # COLUMN, DERIVED from the profile -- do NOT type it.
        ruled_by: "a price is per unit, and CurrencyCode says which money"
      # OrderKey / RowNumber / StoreKey / CustomerKey / ProductKey:
      #   quantity_kind: identifier    # COLUMN, DERIVED from `field_role: key`. 18 of 18.

concepts:
  Store:
    counts_as: StoreCode               # CONCEPT: what ONE of these is, for counting.
    ruled_by: "a store is the business code: 67, never the 74 versions we keep"
  GammaTarget:
    modality: planned                  # CONCEPT: observed or planned. Changes NO arithmetic;
                                       #   forces a sentence beside the number.
    ruled_by: "a target is asserted by a planner; it is not measured from events"
```

### The word count for contoso, added up

| what you type | tokens |
|---|---|
| one kind word on each of the 10 declared columns | **10** |
| `per:` ×3 and `denominated_by:` ×4 | **7** |
| one grain word on each of the 5 declared relations | **5** |
| `counts_as: StoreCode` | **1** |
| the one sentinel (the member that is not a store) | **1** |
| **total, honest minimum** | **24** |

The plane as actually authored carries **31**. The extra 7 are measured dead: `per: __rows__` ×4 (the code treats it identically to silence), `evaluate_at` ×2 (parsed into the concept plane and **read by zero lines of `law.py`**), `ordinal` ×1. Ablated all together, across both bundles, the score is unchanged: **16 of 18 at 43 tokens instead of 52.**

### Only now, the summary table

This is bookkeeping for whoever maintains the framework. It is not the introduction, and a modeller does not read it.

| what | level | who fills it | contoso |
|---|---|---|---|
| `quantity_kind` | **column** | SME rules; gate fills `identifier` | 29 entries: 18 derived, 8 confirmed, 3 inferred |
| `per` | column | SME, when the kind is `intensive` | 3 real weights; 4 `__rows__` = silence |
| `denominated_by` | column | SME names the unit column | 4 of 29 |
| `denominator_distinct` | column | **profile — never typed** | derived |
| `grain_semantics` | **relation** | gate proposes, SME confirms | 5 of 6 relations |
| `observation{subject_key, observed_at}` | relation | **gate, from the collapse canon** | 1 of 1, **0 authored** |
| `cell_key` | relation | **gate, from the declared key** | 5 of 5 derived |
| `counts_as` | **concept** | **SME only — the law refuses to pick** | 1 of 17 |
| `modality` | concept | SME | 0 on contoso (no plan figure exists) |
| `sentinel{column, member, label}` | **axis (one member)** | SME; the share is derived | 1 |
| the 25-cell law, 10 operators | **framework** | nobody | 25 of 25 cells filled |
| `provenance_tier` | every entry | **nobody** — falls out of the token | 0 mandatory |

**What earns its keep, measured by building each rung and running the 18 cases:**

| adds | tokens | score |
|---|---|---|
| `quantity_kind` alone | 20 | 2 of 18 |
| `+ grain_semantics` | 26 | **8 of 18** — 6 words, 6 cases: the best-value property in the design |
| `+ per` | 36 | 10 of 18 |
| `+ denominated_by` | 40 | 11 of 18 |
| `+ observation` / `stored_at` | 46 | 12 of 18 |
| `+ counts_as` | 47 | 13 of 18 — one word, one case |
| `+ modality` | 48 | **15 of 18** — one word, two cases |
| `+ sentinels` | 50 | 16 of 18 |
| `+ evaluate_at` | 52 | 16 of 18 — **no gain; it is never read** |

---

## 4. THE EIGHTEEN CASES — reference

Each one: the question, what goes wrong today, what you declare, what you get. **16 of 18 fixed, 0 of 18 regressed**; the 2 that are not fixed say so.

**1 · A quantity totalled to a year.** *"Gross sales in USD in 2024?"*
Today: `SUM(Quantity*UnitPrice)` — right, and right by luck. The old guard was consulted on **1 axis**, read a field that is `{}` on **17 of 17** concepts, and returned `None`. Nothing checked anything.
Declare: `grain_semantics: event` (relation) + `quantity_kind: extensive` (column).
After: the same SQL, and the law saw **9 folded axes** with `CurrencyCode` pinned, read `LAW[event][extensive] = sum`, and stamped the answer `derived`. Delete either line and it refuses instead of guessing.

**2 · The same quantity as one bare total.** *"Total gross sales in USD?"*
Today: correct, and examined by **nothing at all** — the old guard is called once per period and once per breakdown, and a bare total has neither. **0 axes.**
Declare: nothing new.
After: the law sees all 9 folded axes, plus the sentinel disclosure. Drop the `in USD` and it becomes case 12.

**3 · A level read across a history that republishes.** *"How much floor space in total?"*
Today: **109,120**. There *is* a collapse and it does nothing — it partitions by `StoreKey`, which is unique, so **74 of 74** rows survive and every superseded store version is added again.
Declare: `grain_semantics: observation` + `observation: {subject_key: StoreCode, observed_at: OpenDate}` (relation) — on contoso **all of it derived, 0 authored**.
After: one word changes in the `PARTITION BY` and the answer is **99,300** over 67 stores. Plus: *"collapsed to one row per StoreCode (ordered by OpenDate, latest first) BEFORE folding."* The rule is not "never sum a level" — it is **resolve the end reading per subject first, then sum across subjects.**

**4 · The same level, shown BY warehouse. ✗ NOT FIXED.** *"Stock on hand by storage site?"*
Today: a refusal, wrong twice. Grouping by site **preserves** the site axis, so additivity across sites is not the question being asked — and the declaration is false anyway: stock at site A plus stock at site B *is* total stock. A level is non-additive over **time** and perfectly additive over **place**.
Declare: case 3's two lines. Delete the false per-axis `additivity` field (deprecated, not removed — `extra="forbid"` means deleting it stops 13 of 13 files parsing, and 3 are behind the armed lock).
After: still wrong, because the false legacy field is read **first**. **Precedence is unruled and only the operator can rule it.** Cost of ruling "the fold law wins": **6 of 1,429** named tests, and the score goes **16 → 17 of 18**.
Also found tonight and not in the design: the collapse partitions by the subject key **union the preserved axes**. Harmless on this data, but `PARTITION BY Status, StoreCode` keeps **73 of 74** rows, sums to **108,015**, and manufactures a "Restructured" band of 6 stores / 8,715 m² that does not exist in the correct collapse. The collapse must partition by the subject key alone and group afterwards.

**5 · An average with nothing to weight it by.** *"Average product price?"*
Today: refused one gate earlier ("3 columns declared the same way") — and the moment anyone names one column, a `SUM`: **898,141.44** over 2,517 products.
Declare: `quantity_kind: intensive` + `per: __rows__` (there is genuinely no weight column on this table: 14 columns, none says how many were sold).
After: `AVG(Price)` = **356.830130**, plus the disclosure that a plain mean **does not compose**. And that disclosure is true on this data: one-shot **356.830130** against the average of the 32 subcategory averages **370.966608** (+3.96%), because subcategories hold 20–201 products each. "The average price" and "the average of the category averages" are different numbers, and with no weight the system can only tell you the question is ambiguous. That is the right answer, not a consolation prize.

**6 · An average that has a weight.** *"Average unit price by subcategory, in USD?"*
Today: `SUM(UnitPrice)` = **37,694,027.89** — 113,614 price tags added up.
Declare: `per: Quantity` — one line, and it is the bundle's own prose rule.
After: `SUM(UnitPrice*Quantity)/NULLIF(SUM(Quantity),0)` = **333.691614** over 356,346 units. And it **stacks**: staged over the 32 subcategories, identical to six decimals. The plain mean gives 331.772738 one-shot and 395.233809 staged.

**7 · A rate has no total.** *"What was the exchange rate in 2024?"*
Today: a valid plan returning **9,702.54554** — the sum of 9,150 quotes across 366 days and 25 currency pairs, in a table where **no rate exceeds 2.08733** (min 0.47908 / max 2.08733 over 100,450 of 100,450 rows).
Declare: `grain_semantics: precomputed` (relation) + `quantity_kind: intensive` (column).
After: no SQL is built. *"ExchangeRate is stored only at the grain (Date, FromCurrency, ToCurrency) and this question leaves Date, FromCurrency, ToCurrency unpinned… Pin or group every key column."* A precomputed number exists only in the cell it was computed for.
Not yet bought: "ask at the grain it is stored at" is advice you cannot take — a period is a range, so even a one-day period still refuses. And a monthly grouping is wrongly treated as discharging the day axis.

**8 · A rate "by currency".** *"Show me the exchange rate by currency."*
Today: `JOIN v_contoso_fx_rate_day ... ON` followed by **nothing** — `Parser Error`. The same empty `ON` appears in 3 of 5 plans this measure produced. Had it been filled: SUM by to-currency gives AUD 555.58, CAD 496.05, EUR 337.82; `AVG` is worse because it looks right (AUD 1.518, EUR 0.923).
Declare: nothing new — the same two lines from case 7 govern both folds.
After: the same refusal, narrower — it names `Date` only, because grouping by currency kept that part of the cell. The refusal gets narrower as the question gets more specific, which is what makes it teachable.
Still open: "by currency" on an ordered pair is ambiguous (FROM or INTO?) and there is no field for the answer.

**9 · A monthly goal rolled to a year.** *"What is our target for January?"*
Today: the right number, silently. A reader sees "January 4.1m" beside "December 3.8m" with nothing saying one is a promise. The old rule book said Target is "not summable on any axis" — bad arithmetic, and **ruled a mis-classification by the operator on 2026-09-20**.
Declare: `quantity_kind: extensive` (column) + `modality: planned` (concept).
After: the same SQL, byte for byte, plus *"this is a PLAN figure, not an observation: it folds like any other extensive quantity, and it is not a measurement of what happened."* The case where the arithmetic did not need fixing and the honesty did.
Invented: contoso has **0 of 17** concepts mentioning a target, budget, forecast or plan, so this runs on the synthetic fixture.

**10 · A per-store goal rolled to a region.**
Today: right number, no disclosure.
Declare: **the same lines as case 9 — nothing new.** That is the finding: the 25-cell law has **no axis dimension**. "Over months" and "over stores" are not two rules; they are one rule consulted about different columns. The old matrix gave `Target` the same verdict in both its cells — **2 of 10 cells carrying no information** — precisely because the axis was never a factor.
Open and unhandled: rolling a plan **up** works. Splitting a plan **down** does not, and there is no term for it. `grep -i "allocat|disaggregat"` across the design and all three runtime modules: **0 hits.**

**11 · Two ways of slicing the same sale. ✗ NOT FIXED.** *"Gross sales by brand and by product category."*
Today and after: `Refusal(no_join_path)` — **a join defect, not a fold defect**. `0 of 17` declared edges name Brand, deliberately: a roll-up belongs in the concept's `members.over` block, and the route-finder reads only `edges.yaml`. So **4 of 17** concepts (Brand, ProductCategory, ProductSubcategory, Continent) can never appear in an answer, however they are declared.
Also missing: there is **no axis level in the plane at all**. An `axes:` block parses, is read, and is **silently dropped**. Do not believe a green run of one.
Contoso is safe for now: **0 of 2,517** products carry two brands; 29 of 88 (brand × category) cells non-empty, 8 of 11 brands span >1 category. Neither is a level of the other, so the cross-product is the honest answer — and nothing stops the unsafe case either.

**12 · Five currencies added together.** *"What were our total gross sales?"*
Today: **232,601,542.66** over 223,974 of 223,974 lines. It is USD 118,909,671.98 + EUR 50,272,341.05 + CAD 24,708,880.13 + GBP 24,512,650.21 + AUD 14,197,999.29 — **a number with no unit**, which cannot even be converted, because the mixture is already lost.
Declare: `denominated_by: CurrencyCode` on the amount columns. The count of 5 is derived.
After: a refusal naming three repairs already in the bundle — pin one currency, group by currency, or convert through the declared derivation. **Delete that one line and the silent 232m comes straight back.**
One honest finding: `dim_contoso_product.Weight` declares `denominator_distinct: 2` and the warehouse has **3** non-null units (pounds 1,867 / ounces 418 / grams 10, plus 222 of 2,517 null). Hand-typed and wrong. Derive it.

**13 · A yes/no flag summed like a total.** *"How many working days do we have?"*
Today: nothing stops `SUM(WorkingDay)` = **2,760**. The digit is right; the *claim* is wrong — a count wearing a total's name. What looks like protection is a role dodge (`field_role: dimension`) plus prose. Change that one role the way any author would, and today's planner emits the SUM.
Declare: `quantity_kind: indicator`.
After: `COUNT(*) FILTER (WHERE WorkingDay = 1)` = **2,760** — the same number, computed as a count, and `SUM`/`AVG` are no longer choices the planner can make.
Two gaps: **which value means yes is not declarable** (the runtime hardcodes `= 1`; a flag where 1 = holiday would be counted backwards, silently), and the alias still reads `workingdaytotal`. The arithmetic is governed; the wording is not.

**14 · "How many stores?"** *— the system answers 109,120.*
Today: **109,120** square metres, offered as the answer to a counting question, with no warning. Because `Store` declares one measure column (`SquareMeters`, 1 of 1) and nothing anywhere says that counting stores means counting a column rather than summing one. The bundle *knows*: `store.yaml` says in as many words *"a question about 'how many stores' means 67, not 74"* — in a `definition:` block that no machine reads.
Declare: `counts_as: StoreCode` (concept). **One line.**
After: `COUNT(DISTINCT StoreCode)` over the collapsed rows = **67**.
Worth checking: cases 14 and 18 are two declarations, and all four combinations were run and executed — partition by StoreCode + count StoreCode = 67 *right for the stated reason*; StoreCode + StoreKey = 67 *by luck*; StoreKey + StoreCode = 67 *by luck*; StoreKey + StoreKey = **74**, which is the pair today's code holds. One of four is wrong and two are right by accident.

**15 · A ratio: fold the parts, then divide once.** *"What share of list price do we collect, in USD?"*
Today: `SUM(NetPrice/UnitPrice)` = **106,901.34** over 113,614 USD lines. A discount rate of 106,901, growing with the row count.
And the obvious repair is also wrong: `avg(NetPrice/UnitPrice)` = **0.940917** against `SUM(Net·Qty)/SUM(Unit·Qty)` = **0.940732** — on 118.9m USD of list value, **21,939.92 USD** of net overstated.
Declare: `per:` naming the denominator (same line as case 6).
After: `SUM(x·w)/NULLIF(SUM(w),0)` = **0.940732**. One declaration answers cases 6 and 15, because the only difference between them is how many axes the question left folded.
Unfixed half: for a ratio that is **not stored** (contoso's real shape), `evaluate_at: after_fold` is parsed and **read by zero lines of the law**. The declaration can be written and it changes nothing.

**16 · Key columns never reach an aggregate.** *— the one case already right.*
Today and after: correct. **1 of 18** was already outcome-correct *and* governed by a declaration the runtime read — and that one is governed by `field_role: key`, outside the additivity system entirely.
But right for a reason about a *chooser's candidate list*, not about the number. Mis-declare `Quantity` as an identifier and today the chooser still picks it and today's runtime still sums it. With the law on: *"declared an identifier, not a quantity: folding it produces a number with no referent."*
This case fixes no bug. It converts a guarantee that depended on a candidate list into a stated law with a named refusal.

**17 · The store that is not a store.** *"Gross sales by store, in USD."*
Today: the SQL is right, the arithmetic is right, and **one of the 24 rows is not a shop.** `StoreKey 999999` is the web channel, and in exactly this question's scope it carries **46,924 of 113,614** lines and **46,768,925.43 of 118,909,671.98** — **39.3% of the number**, in one unlabelled row. Across all currencies on net: **93,550 of 223,974** lines (41.8%). The largest silent error available in this bundle. The operator has already ruled it — *include it as its own row, labelled* — and it was machine-readable on 0 of 17 concepts.
Declare: a `sentinels:` entry — column, member, label. The share is derived.
After: **byte-identical SQL**, plus one sentence naming the member, its label and both shares with their denominators. **A sentinel never changes a number** — delete the block and the SQL is identical with zero caveats. That is why it is safe to write one down: disclosures accumulate and never block.
Gap: the share string is fixed, so it quotes the all-currency net share (41.8%) beside a USD gross answer (39.3%). Right in magnitude, honest about its own denominators, not the share of the number in front of the reader. And at what share a sentinel should *refuse* rather than annotate is undecided.

**18 · The store that changed address.** *"How many stores, and how much floor space?"*
Today: the collapse partitions by `StoreKey`, which is unique — **74 of 74** rows survive. The window function runs, costs a sort, and removes nothing. No error, no warning, no symptom. **9,820 m² of the 109,120 is the same store counted twice** (6 of 67 codes have two versions, 1 has three) — **9.0%**, silently.
Declare: nothing on contoso. `store.yaml` already carries `params.natural_key: StoreCode`, written deliberately with a paragraph explaining why, and read by **0 of 62** runtime source files. The gate reads it and fills all three values: **1 of 1, 0 authored.**
After: `PARTITION BY StoreCode` → **67 of 74** rows survive, **99,300** m², and a disclosure saying what it did.
**Keep both lines.** `cell_key` says what makes a **row** unique (the version). `subject_key` says what the row is a version **of** (the store). Collapsing those two into one field *is* the bug.
Two things not settled: *"latest"* is itself a ruling — an as-of question wants the version whose validity window contains the date, and `observed_at` names only the ordering column; and a relation re-observed on two independent clocks is undefined.
One thing settled and worth knowing: the collapse is a window function and not `WHERE CloseDate IS NULL` for a measured reason — **9 of 67** store codes have no open version at all, so the filter silently drops 9 shops and every sale they ever made. The collapse returns 67 of 67.

---

## 5. THE TWO-FLAG PROPOSAL

The proposal was **built** as a real plane directory and run through the same harness, in its most generous faithful encoding (where a case is lost under both settings, the better-scoring setting was chosen). Not argued — measured.

### Where the instinct is right — and it should change the design

1. **"The common case should be trivial."** Correct, and the design *already is* — **60 of 71** columns need nothing, and 6 of the 10 that do need exactly one word. The design's presentation is the defect, not its authoring cost. A 13-row property table at four grains badly misrepresents *one word per measure column*. That is section 3 of this document, and it is a documentation fix.
2. **"One word per column."** Right. Only the word must be a **kind**, not a boolean.
3. **`is_sortable` should be dropped.** Yes — but not because `ordinal` subsumes it (a revenue amount is sortable and is not ordinal; they say different things). Drop it because it carries no information: it would be `yes` on **71 of 71** contoso columns, the runtime emits **no `ORDER BY`** in any outer query, and it changes **0 of 18** outcomes. What sort actually needs is not a boolean but a **column name** — which column decides which row is true inside the collapse. That is `observed_at`, it drives cases 3, 14 and 18, and it is already there, **0 authored / 1 of 1 derived**.
4. **Ship smaller than the table suggests.** **43 tokens, not 52.** Drop `evaluate_at` (2, parsed and never read), `per: __rows__` (6, identical code path to silence — make absence mean it), `ordinal` (1, load-bearing on 0 of 18 — keep the framework term, stop asking anyone to type it). All three ablated together: score unchanged at 16 of 18.

### What was measured

| design | contoso tokens | score |
|---|---|---|
| shipped runtime today | — | **3 of 18** |
| two booleans, measure columns only | 9 + 9 = **18** | **4 of 18** |
| two booleans, every column | 71 + 71 = 142 | 4 of 18 |
| the fold plane, as authored | 31 | **16 of 18** |
| the fold plane, minus the 9 dead tokens | **24** | **16 of 18** |

Scored three ways, honestly: **4 of 18** by the harness's own predicates; **5 of 18** outcome-fair (+2 — cases 7 and 8 refuse correctly and a boolean simply cannot emit the sub-code the harness wanted; −1 — case 3's predicate credits *any* refusal, and that question has a real number as its answer); **7 of 18** if the plan disclosures in cases 9 and 10 are not required. The fold plane is **16 of 18 under all three scorings**.

**By the machine's own predicates, the only case two booleans add over the runtime shipping today is case 3 — and that one is the lenient-refusal loophole.** Outcome-fair, they add cases 7 and 8.

Two findings that cut against the design and are reported anyway: case 3's harness predicate is too loose and flatters the two-flag design by one case; and **`quantity_kind` alone scores 2 of 18 — *below* the two booleans' 4**, because without the relation word the design fails closed and refuses nearly everything. The relation term is doing more of the work than the property table's ordering implies.

### The single clearest case a boolean cannot carry

**"Is a duration foldable?" Yes — by MEAN.** One column, `duration_minutes`, measured three ways:

- `is_foldable: yes` → `SUM(duration_minutes)` — today's wrong number.
- `is_foldable: no` → a refusal — a question that has an answer, refused.
- the right answer → `AVG(duration_minutes)`, plus a disclosure that a plain mean does not compose (measured 32.000000 one-shot against 32.500000 staged, same data).

There is no third value of a boolean. **The word "average" has nowhere to live.** In one line: *a boolean can only ever say STOP; it can never say WHAT TO DO INSTEAD.* On the bare-total sweep, today **11 of 11** typed measures emit a plain SUM; two booleans turn **6 of 11** into refusals; the fold plane turns **4 of 11** into refusals and **5 of the remaining 7** into a *different and correct operator*.

Two more, briefly. **A boolean is a constant and the requirement is a function of the question**: `UnitPrice` is foldable across stores, products and dates and not across currencies — same column, and the difference is whether the question pinned a currency. Flipping the flag to protect case 12 was run: **the score goes from 4 of 18 to 1 of 18**, breaking cases 1, 2 and 16 and still not naming the repair. And **a boolean has no slot for a column name**: case 14's right answer is `COUNT(DISTINCT StoreCode)` = 67, a fold over a column the question never mentions. `yes` gives 109,120; `no` gives a refusal; neither can reach 67.

### Straight verdict

The proposal does not cover **15 of 18**. Two booleans plus a per-column SQL escape hatch reaches **about 10 of 18** — and that figure is *reasoned, not measured*, because there is no such key to run. It would recover the operator-naming cases (5, 6, 13, 14, 15) and cannot recover 3, 12, 17, 18: a static expression cannot introduce the `ROW_NUMBER` subquery, cannot be conditional on whether *this* question folded the currency axis, and is not a disclosure. The cost is 5 hand-written, ungateable SQL strings — the prose route that gets 2 of 6 aggregation rules into SQL today, re-opened.

**The smallest honest thing is not two booleans and it is not the 52-token table. It is: one kind-word per measure column, one grain-word per relation, and four names — `per`, `denominated_by`, `counts_as`, `observed_at`.** 24 tokens on contoso, 43 across both bundles, 16 of 18.

---

## 6. HOW MANY SHOPS — the worked answer, and where self-awareness stops

### There is more than one true answer

All executed read-only tonight:

| number | what it is |
|---|---|
| **74** | rows in `dim_contoso_store` |
| **74** | distinct `StoreKey`, the surrogate — and `identity.canonical_key` **is** `StoreKey` |
| **67** | distinct `StoreCode`, the business code |
| **67** | distinct `StoreCode` after collapsing to the current version |
| **64** | `StoreKey` values ever seen on the fact |
| **58** | codes with an open version (`CloseDate IS NULL`) |
| **109,120** | what the console answers for "Store" **today** — a floor area in square metres |

There are several because **the table was deliberately served at the wrong grain for this question, and that was the right decision**: one row is one *version* of a shop, because the order line carries the version it was placed against, so the join cannot fan out (measured 0 fan-out). 74 − 67 = 7 extra versions. Two traps sit underneath, both declared: **58 is not 67 minus closed** — 9 of 67 codes have *no* open version, so that filter silently drops 9 shops (58 + 9 = 67); and **74 includes a thing that is not a shop** (case 17).

Note the asymmetry: five of the six are answers to a slightly different question. **109,120 is an answer to no question at all.**

### What the system works out alone, and where the boundary is

**Derived, no human, recomputable:** that the relation is an `observation`; that `StoreCode` is the subject of the collapse; that `OpenDate` orders the versions; that `StoreKey` is the row key; that all three key columns are identifiers and folding one is a type error. All of it from `realized_by: mac.canon.snapshot_collapse` + `params.natural_key: StoreCode`, already in the repository. **1 of 1 relations, 0 authored.** Against an empty directory it derives **0 of 6** relations — the derivations fill gaps in a plane, they do not invent one.

**Requires a human:** that a *count of shops* means `StoreCode` rather than `StoreKey`. And the model is not one measurement away from working this out — it has **no measurement at all**. The profile index holds 16 entries; on **16 of 16** the row count is `None` and every distinct count is `None`. Those entries are keyed to the raw landing relations, not the served ones, and `store`'s measured key is `('StoreKey',)` — the very number the ruling forbids. `Store.grounding.measured_identity` is `None`. The one mechanical rule anybody would write — *count the concept's canonical key* — reads `StoreKey` and answers **74**.

**Also not known, and not the fold plane's gap:** the word "shop" appears **0 times** in 17 of 17 concept files, labels and definitions. The mapping *shops → Store* is done entirely by the language model, ungoverned and unrecorded.

### What it must be told

```yaml
concepts:
  Store:
    counts_as: StoreCode      # CONCEPT level -- the only fact here no machine can reach
    ruled_by: "a store is the code: 67, never the 74 versions we keep"
```

The question, for a person: ***"When someone asks how many shops we have, do you mean the business code (67), the delivered version row (74), or the ones that actually sold something (64)?"*** One word back.

Measured authoring cost: the plane was reduced to the minimum text that still answers — **8 lines, 3 of them the ruling** — and it returns **67**, byte-identical to the full plane.

### What it does when nobody has told it — six worlds, each executed

| world | outcome | number |
|---|---|---|
| today, law off | `SUM(SquareMeters)` | **109,120** |
| law on, `counts_as` declared | `COUNT(DISTINCT StoreCode)` | **67** ✅ |
| law on, `counts_as` removed, kind still declared | `SUM(SquareMeters)` after collapse | **99,300** ⚠ |
| law on, both removed | **REFUSAL** | — |
| law on, no plane, open world | ungoverned | 109,120 |
| law on, no plane, closed world | **REFUSAL** | — |

The refusals are good ones. Verbatim: *"`dim_contoso_store.SquareMeters` declares no `quantity_kind`, so nothing says what folding it means. A fold with no declared law is refused rather than emitted as a SUM."* They name the file, the relation, the column and the missing key — enough to act on without a conversation.

### Where self-awareness stops — three layers, plainly

1. **The fold law reflects on arithmetic.** Given the declarations it knows whether a fold is licensed, and when it is not it refuses and names what is missing. 16 of 18, 0 regressions, and 67 instead of 109,120.
2. **It does not reflect on intent.** With the count ruling absent but everything else complete, it does *not* refuse — it answers **99,300**, confidently, with a disclosure about the collapse and no disclosure that it answered a different question. And the symmetric failure: once `counts_as` is declared it is consulted **unconditionally**, so "floor area by country" comes back as `COUNT(DISTINCT StoreCode)` grouped by country. **`counts_as` needs a question-shape condition it does not have.** Self-awareness about arithmetic is not self-awareness about intent.
3. **It does not reflect on itself at all.** *"Which of my measures can I sum?"* is now derivable — I computed it in fifteen lines from the plane plus the law: **2 of 29** governed columns fold by `sum` (`SquareMeters` and `Quantity`); everything else resolves to `weighted_mean`, `resolve_match` or `refuse`. And it is **unreachable as a question**: `Intent` has one required subject slot, `measure: str`, and **3 of 17** concepts can be a question's subject at all. The fold plane moves that question from *not declared and not representable* to *declared, derivable, and still not representable*. Real progress, not an answer.
    It also refuses and **does not file**: `open_question_id` is `None` at **15 of 15** refusal sites, and 0 sites set it to anything else — some refusals say the words *"Filing an open question"* while the id travels as `None`. It knows what it does not know, says so precisely, and forgets immediately. Given the SME-console thread, that is the cheapest high-value gap on this list.

### The wider class — 1 of 14 countable today

I asked "how many X" for all 14 non-measure concepts.

- **Answerable today: 1 of 14** — Store → 67.
- **Answerable with one declaration: 2 of 14**, both executed — OrderLine → `counts_as: OrderKey` → **93,470** (and `order_line.grain.no_header_relation` **already says** "answer by count(DISTINCT OrderKey)… never counting rows, which overstates 93,470 orders as 223,974", with `binds: [OrderKey]` — authored, machine-readable, and unexecutable); Product → **2,517** (the one concept where every candidate agrees; tier came back **`inferred`**, because the product relation carries no `ruled_by` and the meet law refuses to launder a strong ruling through a weak input).
- **Not answerable, and not reachable by any fold-plane declaration: 11 of 14.** They refuse at step 1, in `_resolve_measure`, before the fold law is ever called: *"Customer is declared class 'entity'… its grounding marks no column `field_role: measure` — so nothing declares a number it carries."* I proved `counts_as` cannot rescue them: added a relation plane **and** `counts_as: CustomerKey`, and got the identical refusal with the fold law never invoked.

So which concepts can be counted is decided by **whether they happen to declare a numeric payload column** — Store has `SquareMeters`, Product has `Weight/Cost/Price`. That has nothing to do with countability. **Customer is the most obviously countable entity in the bundle — 104,990 rows / 104,990 `CustomerKey` / 52,189 on the fact — and it is unanswerable because a customer row carries no number.** That is a one-line ordering defect in `plan.py`, not a flaw in the fold plane, and **it caps this design at 3 of 14 countable concepts**. It is the item I would raise first, ahead of anything in the design itself.

One closing measurement. `Store.definition` contains, verbatim, *"a question about 'how many stores' means 67, not 74."* That string is written into the interpreter's system prompt on **every single call**. The model is told the answer every time it is asked, and until `counts_as` existed it could not emit it — because the only output it had was a request for a number, and 67 was not a number it was allowed to want.

---

## 7. WHAT AN SME IS ACTUALLY ASKED

Every human ruling the design needs, as plain questions. No YAML, no SQL, no jargon. Most take one word back.

**About a number (once per measure column)**
1. *"Is this number something you can add up — an amount, a count, a floor area? Or something you can only average — a price, a rate, a duration? Or a yes/no written as 0 and 1? Or a rank?"* → the one kind word.
2. *(if it was a price or a rate)* *"When you average this, should a line of 10 units count ten times as much as a line of 1?"* → `per: Quantity`. If there is no such column on that table, say so — that is a real answer.
3. *"Can this number be in different units on different rows? Which column tells you which?"* → the unit column.

**About a table (once per table)**
4. *"Does one row of this table record something that happened, a reading taken at a moment, a number somebody promised, or a figure a tool already worked out?"*
5. *(if readings)* *"This table has the same store in it three times. Which column tells you it's the same store, and which column tells you which row is the newest?"* → two column names.

**About a thing people name**
6. *"When someone asks how many of these we have, what is one of them?"* → the column to count.
7. *"When this number appears on a page next to last year's actuals, does the reader need to be told it is a promise rather than a measurement?"*

**About the data as it actually is**
8. *"Look at the list of stores. Is any one of these not actually a store — and if somebody saw it sitting in a store-by-store breakdown, would they be fooled?"*

### Counted for contoso

| question | asked | note |
|---|---|---|
| the kind word | **10** | 9 measure columns + `WorkingDay`. **0 of 9** get a sound answer from any declared type or profile statistic, so all must be asked |
| `per:` | **3** | `UnitPrice`, `NetPrice`, `UnitCost`. The other 4 intensive columns have no weight column — silence |
| the unit column | **4** | the three prices + `Weight` |
| the table's grain word | **5** | the gate proposes all 5; these are **confirmations**, not investigations |
| what one of these is (`counts_as`) | **1**, worth **3** | Store today; OrderLine and Product are both one line away |
| the sentinel | **1** | and the ruling already exists, verbally |
| observed or planned | **0** | contoso declares no plan figure (0 of 17 concepts) |
| the collapse's subject and order | **0** | derived, 1 of 1 |
| anything about a key column | **0** | 18 of 18 derived, precision 8 of 8 |
| any share, count or row total | **0** | derived from the profile — and the one hand-typed count (`Weight`'s `2` against a measured `3`) is why |

**Total, recordable today: 24 one-word or one-name answers for the whole bundle** — and 5 of the 24 are confirmations of something a gate already proposed.

**Four answers a person can give and the system cannot yet hold. Say these out loud so nobody thinks they were forgotten:**
- *"Which value means yes — is 1 the working day or the holiday?"* The runtime hardcodes `= 1`. Contoso's SME has answered in prose (1 = working, 2,760 of 4,018) and there is nowhere to put it.
- *"Can one product belong to two brands at once?"* and *"Is a brand a kind of category, or two ways of slicing the same product?"* There is **no axis level in the plane** — the block parses and is silently dropped (case 11).
- *"When you say 'by currency' about an exchange quote, do you mean the money you convert FROM or INTO?"* Known in prose, no term.
- *"The goal was set per region; can someone ask per store?"* Rolling up works; splitting down has no term at all, and `stored_at` is the wrong tool (measured: it refuses the up-fold too).

**And one ruling that is the operator's, not an SME's, and only they can make it:** *"When the old per-axis additivity field and the new fold law disagree, which wins?"* Answering "the fold law" costs **6 of 1,429** named tests and moves the score **16 → 17 of 18**.

**What an SME must never be asked:** for an additivity table, one row per axis. That is the level error case 4 exposes — open-ended, untestable (`{}` on 17 of 17 concepts), and measured **wrong on the single axis** the one fixture that filled it in bothered to fill in. Two declarations one level down — "rows here are re-readings of the site, ordered by date" and "the number adds up" — imply every row of that table, and imply them correctly. Nor for `cell_key`: what makes a row unique is measured, derived 5 of 5, and the whole bug is that it was being used to answer the SME's question instead.

---

### Three small corrections found while grounding this document

- `vocabulary.py`'s comment says the re-observation axis is "intercepted by **G4**". In `law.py`, G4 is the **unit** guard; the collapse is decided in the stage section from `partition_role == "reobserves"`. Cosmetic, and it misleads a reader of the design.
- `evaluate_at` should be deleted from `ConceptPlane`, not just left unread. It is authored on **2 of 2** concept entries in the real bundle and changes nothing about the emitted SQL.
- The landed test file holds **3 tests**, all about the 25-cell table being total, naming known operators, and not having drifted. **0 of 3** assert the emitted mean or weighted-mean SQL. That coverage lives only in the 18-case harness, which is a scratchpad script and not a suite test.

**Where things live.** The decision: `decisions/0004-the-fold-plane.md` in the worked-example bundle. The code: `packages/mac-runtime/src/mac_runtime/foldplane/{vocabulary,planes,law}.py` in the platform repository. The tests: `packages/mac-runtime/tests/test_foldplane_law.py`. The worked planes, the 18-case harness and every probe behind the figures above were run from a scratch directory and are not committed; the figures are reproducible from the bundle and the landed code.

No repo file was edited, no `ontology/` path was written, no lock marker was created or moved, the warehouse was opened read-only, and no server was touched.

STOPPING