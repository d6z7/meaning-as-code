---
state: proposed
genre: proposal
---
# PROPOSED — 2026-10-02 · ONE Revenue concept, and the four things that break first

> **Paths in this document.** `planner/…`, `interpret/…` and `canons/…` are under
> `mac-platform/packages/mac-runtime/src/mac_runtime/`; `packages/…` is under `mac-platform/`;
> `data/…` and `ontology/…` are inside the bundle (`example/contoso5`). A `:line` suffix is the
> line the measurement was read at.


**Status: PROPOSED.** Per CORE §3 an agent may only write `PROPOSED`; adding or removing a concept is
the operator's act. Nothing in this record has been applied to `example/contoso5` — the real bundle
was read-only throughout and every experiment ran on a copy under the session scratchpad.

**The operator's ask, verbatim (2026-10-02):** *"since all concepts like Gross Revenue, Net Revenue,
etc all derive from one and the same view/table dont you think it would make more sense to create one
single KPI or Revenue and manage ALL KPIs from there. we are anyway managing them through RULES."*

**The reading is right about the duplication and the mechanism already exists.** It is wrong about
one thing only: the planner identifies a measure BY ITS CONCEPT NAME in four places, and when nine
KPIs share one concept name those four places stop telling them apart. Three of the four fail
LOUDLY. One fails SILENTLY, and that one is why this is a proposal and not a migration.

**Recommendation: DO IT, BUT NOT YET — four named runtime changes first, in this order.** §6.

---

## 1 · WHAT THE SIX CONCEPTS ACTUALLY DECLARE

All six ground the same relation `v_contoso5_sales_line` at the same grain (`one row per sale
(order_key, line_number)`), class `measure`, `measure_type: flow`. The table below is every declared
column of all six. `m:` is the column's `measure` block, `ax:` its `axis_kind`, `id:` its `identity`.

| column | GrossRevenue | NetRevenue | SalesCost | Margin | Discount | UnitsSold |
|---|---|---|---|---|---|---|
| order_key | key id:part | key id:part | key id:part | key id:part | key id:part | key id:part |
| line_number | key id:part | key id:part | key id:part | key id:part | key id:part | key id:part |
| order_date | period ax:time | period ax:time | period ax:time | period ax:time | period ax:time | period ax:time |
| delivery_date | dimension ax:time | dimension ax:time | dimension ax:time | dimension ax:time | dimension ax:time | dimension ax:time |
| customer_key | key id:reference ax:categorical | *same* | *same* | *same* | *same* | *same* |
| store_key | key id:reference ax:categorical | *same* | *same* | *same* | *same* | *same* |
| product_key | key id:reference ax:categorical | *same* | *same* | *same* | *same* | *same* |
| currency_code | dimension ax:categorical | *same* | *same* | *same* | *same* | *same* |
| gross_amount | **measure m:flow/USD/CANONICAL** | — | — | — | — | — |
| unit_price | measure m:intensive/USD | — | — | — | — | — |
| net_amount | — | **measure m:flow/USD/CANONICAL** | — | — | — | — |
| net_price | — | measure m:intensive/USD | — | — | — | — |
| cost_amount | — | — | **measure m:flow/USD/CANONICAL** | — | — | — |
| unit_cost | — | — | measure m:intensive/USD | — | — | — |
| margin_amount | — | — | — | measure m:flow/USD | — | — |
| discount_amount | — | — | — | — | measure m:flow/USD | — |
| quantity | — | — | — | — | — | measure m:flow/**units** |

**The eight shared columns are byte-identical in role, identity and axis_kind across all six.**
57 declared column blocks across the six files; 17 distinct ones. **40 of 57 (70 %) are copies.**
504 YAML lines across six files; the merged single concept is 198.

**Everything that differs between them, exhaustively:**

| what | the difference |
|---|---|
| measure column(s) | 1 or 2 each, all 9 distinct, **no name collides** |
| `canonical: true` | declared on 3 of 6 (gross/net/cost). Margin, Discount, UnitsSold declare one measure column, so `column_facts.canonical_measure` finds it by uniqueness |
| unit | `USD` on 5, **`units` on UnitsSold** — the only semantic difference in the set |
| contract rules | NetRevenue 2 (both `default`), Margin 1, Discount 1 (both `aggregation` binding `mac.canon.ratio_select`), GrossRevenue/SalesCost/UnitsSold **0** |
| `contract:` key | absent entirely on UnitsSold; present-but-null on GrossRevenue and SalesCost |
| `metadata.confidence` | `C` on Margin and Discount, `I` on the other four |
| `default_reading` | NetRevenue only |
| label and definition | all six differ (this is the part worth keeping) |

**Edges — the strongest number in this record.** `ontology/edges.yaml` holds 38 edges. **24 of 38
(63 %) are six copies of the same four.** Grouped by target and ignoring `edge_id`, the from-concept
name and the `verified_by` anchor, each of the four targets has **6 of 6 identical bodies** — same
`level: physical`, same `type: foreign_key`, same cardinalities, same `join_rule`:

```
-> Customer: 6 edges, join v_contoso5_sales_line.customer_key = dim_customer.customer_key
-> Store:    6 edges, join v_contoso5_sales_line.store_key    = dim_store.store_key
-> Currency: 6 edges, join v_contoso5_sales_line.currency_code = dim_currency.currency_code
-> Product:  6 edges, join v_contoso5_sales_line.product_key  = dim_product.product_key
```

**No gate in the estate sees this.** `check_common_rules` reports **0 restatements** on this bundle,
and `check_concepts_not_per_table` reports *"OK — the mapping is M:N"*. The operator found by eye a
70 % duplication that every automated check calls clean.

## 2 · THE BASELINE, SO THE CLAIM IS FALSIFIABLE

* **Plan digest** (plan_digest.py — scratch, never committed; every measure × every dimension × SUM/AVERAGE over all five
  example bundles plus `mac-ontology-contoso`): **157 plans → `be8a974dddc5b091`**, byte-identical to
  the hash recorded in `PROPOSED-2026-10-02_column-first-declarations.md` D1. contoso5's share is 98
  of 157: 86 plans, 7 refusals, 5 raises.
* **KPI probe** (rev_probe.py — scratch, never committed; the 6 concept names + 9 measure column names + `Revenue`, × SUM and
  AVERAGE, × no-slice and 6 dimensions, plus 8 named-ratio shapes): 232 rows, **194 PLAN / 38 REFUSE**.
* **`mac-platform/tools/gate.py`, all five planes, console up on :8890 — GATE: CLEAN.**
  * `[PASS] UNIT` — platform 1846 passed / 37 skipped / 6 xfailed; mac 384 passed / 1 skipped.
  * `[PASS] FRAGILITY` — 27 string-literal decisions (ceiling 27).
  * `[PASS] FROZEN PLANE` — 0 stale frozen readings.
  * `[PASS] BUNDLE RULES` — no concept carries an inline value list beyond the standing failures.
  * `[PASS] ANSWERS` — **46 approved questions, 36 pass / 10 fail / 0 ungradeable, 0 REGRESSED.**

**One thing the baseline run itself taught, and it belongs in the record.** `mac-platform/tools/gate.py` is not
read-only on the bundle: its ANSWERS plane POSTs to the console, which rewrote
`acceptance/questions_dashboard.json` (content changed — sha `296f042e…` → `97018ca7…`), appended to
`acceptance/history.jsonl` and re-stamped 46 files under `acceptance/answers/`; then gate.py:183
copied the dashboard to `acceptance/board_history/<stamp>.json`. **`git status --short` cannot see
any of it**: `board_history/` is an untracked DIRECTORY, so git collapses it to one `??` line and a
new file inside changes nothing in the output. A before/after `git status` diff over this bundle is a
PASS on a denominator of one line. The honest check is a content checksum, and it moved.

## 3 · EVERY REFERENCE TO THE SIX NAMES, COUNTED

Whole-estate, word-boundary matched, binaries excluded.

| concept | bundle files / hits | recorded intents naming it | mac-platform files / hits | meaning-as-code files / hits |
|---|---|---|---|---|
| GrossRevenue | 57 / 431 | 2 of 85 | 15 / 34 | 10 / 12 |
| NetRevenue | 120 / 815 | **31 of 85** | 23 / 57 | 12 / 22 |
| SalesCost | 42 / 203 | 0 of 85 | 10 / 15 | 4 / 4 |
| Margin | 24 / 100 | 0 of 85 | 22 / 58 | 2 / 2 |
| Discount | 46 / 156 | 2 of 85 | 10 / 13 | 3 / 3 |
| UnitsSold | 69 / 331 | 3 of 85 | 9 / 17 | 3 / 3 |

**The load-bearing subset — what a migration must change in the same act:**

1. **`ontology/concepts/*.yaml` — 6 files deleted, 1 written.**
2. **`ontology/edges.yaml` — 24 edges deleted, 4 written.**
3. **Recorded intents: 39 subject slots in 36 of 85 files** — `measure/subject` 33, `denominator` 3,
   `having[].subject` 2, `also[].subject` 1. These are FROZEN readings; every one of them resolves a
   concept name that would no longer exist.
4. **Approved answers: 18 of 46 reference questions** have a frozen intent naming one of the six —
   AGG-01…AGG-15, MQ-07, STORE-08, STORE-11. **16 of those 18 currently carry `outcome: pass`.**
5. **Cross-concept wiki-links: 40 `[[Name]]` links inside `ontology/`**, of which **10 come from
   concepts that SURVIVE** — `order.yaml` 7 (`[[Discount]] [[GrossRevenue]] [[Margin]] [[NetRevenue]]
   [[SalesCost]] [[UnitsSold]]×2`) and `product.yaml` 3.
6. **A SECOND HOME for the grounding: `objects.json`.** `check_edge_joins_its_grounding` reads
   concept→relation from `objects.json`, not from the concept YAML. On the merged copy it reported
   *"its from concept 'Revenue' grounds on no served relation"* for all 4 new edges while still
   counting **17 grounded concepts** — the derived plane had not been regenerated and the gate read
   the old one. Also derived and name-carrying: `compile.json`, `ontology/edges.json`,
   `ontology/concepts/*.md`, `ontology/concepts/rules/*.md`, `ontology/samples/*.csv`,
   `ontology/ontology_quality.json`, `references/usage_guardrails.md`, `ontology/concepts/index.md`.
7. **mac-platform tests: 13 test functions** hard-code the real contoso5 path AND name one of the six
   — `packages/mac-runtime/tests/test_framework_folds_with.py` 4 (one calls `index.get_concept("GrossRevenue")` directly),
   `packages/mac-runtime/tests/test_temporal_builtin.py` 8, `packages/mac-runtime/tests/test_planner_value_column.py` 1. On the merged copy
   `get_concept("GrossRevenue")` raises `UnknownConceptError`, so these ERROR rather than fail.
8. **meaning-as-code needs nothing.** All 34 hits across the six are in its own exemplar bundle,
   golden pages, `mac_vocabulary.yaml` prose and decision records — none reference contoso5.

**A measured side-finding, unrelated to this proposal but found on the way.** Three rule documents
under `ontology/concepts/rules/` describe rules that **no longer exist in any YAML**:
`gross_revenue.aggregation.never_from_unit_prices`, `net_revenue.aggregation.never_from_unit_prices`,
`sales_cost.aggregation.never_from_unit_costs`. `ontology/concepts/gross_revenue.yaml` and `ontology/concepts/sales_cost.yaml` carry
`contract: rules:` **null**. The `.md` plane, `compile.json` and `objects.json` still publish all
three. A reader following the documentation reads a rule the runtime has never heard of.

## 4 · THE PROPOSED SINGLE CONCEPT

Full YAML as tested (`revenue.yaml`, 198 lines, loads clean). Abridged below only in the repeated
column blocks, which are verbatim copies of the surviving declarations in §1.

```yaml
metadata:
  concept: Revenue
  source: CONTOSO5
  version: '1.0'
  schema_version: 0.1.16
  status: draft
  owner: operator
  confidence: C
  provenance: authored
concept:
  name: Revenue
  label: Revenue
  class: measure
  definition: >
    THE SALE LINE'S MONEY AND UNITS, one concept over one relation. Every KPI the operator manages
    is a COLUMN of it: `net_amount` (what the customer paid, the default reading of "revenue"),
    `gross_amount` (before discount), `cost_amount`, `margin_amount`, `discount_amount`,
    `quantity`, and the three intensive per-article figures `net_price`, `unit_price`, `unit_cost`.

    UNQUALIFIED, IT IS NET. Ask for a column by name to get that KPI; ask for the concept and you
    get `net_amount`, which is after discount.
  semantics:
    measure_type: mac.concept.column.measure_type.flow
    unit: USD
grounding:
  sources:
    - relation: v_contoso5_sales_line
      columns:
        order_key:       {role: key, identity: part}
        line_number:     {role: key, identity: part}
        net_amount:      {role: measure, measure: {type: ….flow,      unit: USD,   canonical: true}}
        net_price:       {role: measure, measure: {type: ….intensive, unit: USD}}
        gross_amount:    {role: measure, measure: {type: ….flow,      unit: USD}}
        unit_price:      {role: measure, measure: {type: ….intensive, unit: USD}}
        cost_amount:     {role: measure, measure: {type: ….flow,      unit: USD}}
        unit_cost:       {role: measure, measure: {type: ….intensive, unit: USD}}
        margin_amount:   {role: measure, measure: {type: ….flow,      unit: USD}}
        discount_amount: {role: measure, measure: {type: ….flow,      unit: USD}}
        quantity:        {role: measure, measure: {type: ….flow,      unit: units}}
        order_date:      {role: period,    axis_kind: ….time}
        delivery_date:   {role: dimension, axis_kind: ….time}
        customer_key:    {role: key, identity: reference, axis_kind: ….categorical}
        store_key:       {role: key, identity: reference, axis_kind: ….categorical}
        product_key:     {role: key, identity: reference, axis_kind: ….categorical}
        currency_code:   {role: dimension, axis_kind: ….categorical}
  grain: one row per sale (order_key, line_number)
contract:
  default_reading: >-
    An unqualified price means WHAT THE CUSTOMER PAID PER ARTICLE: `{net_amount}` summed and divided
    by `{quantity}`, 310.98 USD. Operator ruling, 2026-09-30.
  rules:
    - id: revenue.default.revenue_means_net                  # was net_revenue.default.revenue_means_net
    - id: revenue.default.a_price_is_revenue_per_article     # was net_revenue.default.…
    - id: revenue.aggregation.margin_two_named_ratios        # was margin.aggregation.two_named_ratios
    - id: revenue.aggregation.discount_percent_is_over_gross # was discount.aggregation.percent_is_over_gross
governance:
  owner: operator
  last_reviewed: '2026-10-02'
```

**`canonical: true` goes on `net_amount`**, because `net_revenue.default.revenue_means_net` already
rules that an unqualified "revenue" is net. `column_facts.canonical_measure` must find exactly ONE
marked column: with nine measure columns all of type `flow`, its type-proxy fallback returns `None`
and every unqualified question refuses. The flag is not optional here — it is the design.

**How each of the six KPIs is asked for:** `{subject: "<its measure column>", operation: sum}`. This
needs no new mechanism. `planner/plan._resolve_measure` falls through to `_column_owner_for` →
`_measure_column_owner`, which finds the one concept declaring that column a measure and returns a
`model_copy` narrowed to it. Each of the nine column names is declared on exactly one concept after
the merge, so the "UNIQUE OR NOTHING" rule is satisfied for all nine.

**The four rule sets become four rules on one `contract`**, with their `binds` unchanged (they
already name columns) and their ratio denominators restated as COLUMNS rather than concepts:
`margin_percent` → `net_amount`, `markup_percent` → `cost_amount`, `discount percent` →
`gross_amount`. Measured: `ratios.by_name` resolves all three correctly on the merged concept.

**The 24 edges become 4**, `from: Revenue`, with the join rules unchanged byte-for-byte:
`revenue__by__customer`, `revenue__by__store`, `revenue__in__currency`, `revenue__by__product`.

## 5 · WHAT BREAKS, WITH THE EVIDENCE

Method: `cp -R` the bundle to the session scratchpad (`revspike/c5base` pristine, `revspike/c5merged`
edited), load each with `OntologyIndex.from_directory`, plan the same Intents against both, execute
the resulting SQL against `example/contoso5/contoso5.duckdb` read-only with `SET search_path='contoso_served'`. The
real bundle was never edited.

The merged copy **loads clean**: 17 concepts → 12, 38 edges → 18, 7 measure concepts → 2
(`Revenue`, `ExchangeRate`).

### 5.0 · The good news first, and it is the operator's point proven

**126 of 126 column-name rows behave identically.** Same verdict, same FROM, same WHERE, same JOIN,
same GROUP BY, same refusal class. The only textual difference is the result ALIAS.

**And the numbers are identical to the cent.** Both plans executed against `example/contoso5/contoso5.duckdb`,
2024 period:

| KPI | BEFORE, `subject=<concept>` | AFTER, `subject=<column>` | equal |
|---|---|---|---|
| GrossRevenue | 33 514 481.458 00 | 33 514 481.458 00 | yes |
| NetRevenue | 31 529 483.247 34 | 31 529 483.247 34 | yes |
| SalesCost | 13 892 841.770 00 | 13 892 841.770 00 | yes |
| Margin | 17 636 641.477 34 | 17 636 641.477 34 | yes |
| Discount | 1 984 998.210 66 | 1 984 998.210 66 | yes |
| UnitsSold | 119 609.0 | 119 609.0 | yes |

**By brand: 6 of 6 breakdowns, 11 rows each, 66 rows row-for-row identical.** The additivity law
still fires correctly on the intensive columns (`unit_price`, `net_price`, `unit_cost` each refuse
`additivity_violation` on SUM and plan on AVERAGE, before and after). `column_facts.unit(Revenue,
'quantity')` returns `'units'` and `unit(Revenue, 'net_amount')` returns `'USD'` — the column-level
unit is read, so mixing units on one concept is safe. *(It is in fact an improvement: BEFORE,
`unit(NetRevenue, 'quantity')` returned `'USD'`, falling back to the concept because NetRevenue does
not declare that column.)*

**The hypothesis is mechanically sound. Four things stand between it and a working bundle.**

### 5.1 · BREAK 1 (loud) — a concept name as a subject resolves to nothing

**84 of 84 concept-name probe rows flip to `REFUSE unresolved_term`.** The question the task asked
to test, answered directly:

```
BEFORE  {subject: NetRevenue, operation: sum}
        SELECT SUM(v_contoso5_sales_line.net_amount) AS netrevenue FROM v_contoso5_sales_line WHERE …
AFTER   REFUSE unresolved_term: No measure or derivation rule named 'NetRevenue' is known to this pack.
```

It breaks in every slot a measure can occupy, not only `subject`:

```
ALSO     {subject: GrossRevenue, also: [NetRevenue]}
         -> REFUSE unresolved_term: This asks for 'GrossRevenue' beside 'NetRevenue', and the
            second could not be resolved…
HAVING   {subject: NetRevenue, having: [NetRevenue > 1e6]}
         -> REFUSE unresolved_term: This restricts the answer to groups where 'NetRevenue' gt
            1000000.0, and 'NetRevenue' could not be resolved…
DENOM    {subject: NetRevenue, denominator: UnitsSold, operation: ratio}
         -> REFUSE unresolved_term
```

**Blast radius: 39 frozen intent slots in 36 of 85 files; 18 of 46 approved reference questions, 16
of which pass today; 13 mac-platform test functions.** This is loud, mechanical and migratable — but
it must happen in the SAME act, or the bundle ships broken.

### 5.2 · BREAK 2 (SILENT — the one that matters) — nine KPIs, one result column name

`planner/sql.py:1127` derives the result alias as `measure_concept.name.lower()`, and `:1813` does
the same for every `also` measure. With one concept, **every KPI comes back as a column called
`revenue`**:

| column asked for | alias BEFORE | alias AFTER |
|---|---|---|
| gross_amount | `grossrevenue` | `revenue` |
| net_amount | `netrevenue` | `revenue` |
| cost_amount | `salescost` | `revenue` |
| margin_amount | `margin` | `revenue` |
| discount_amount | `discount` | `revenue` |
| quantity | `unitssold` | `revenue` |

For a single-measure question that is only a bad label. For a multi-measure answer it is a wrong
answer with no symptom. The operator's own ruling of 2026-09-30 ("compare gross vs net revenue by
brand") produces:

```sql
SELECT dim_product.brand,
       SUM(v_contoso5_sales_line.gross_amount) AS revenue,
       SUM(v_contoso5_sales_line.net_amount)   AS revenue,
       SUM(v_contoso5_sales_line.cost_amount)  AS revenue
FROM … GROUP BY dim_product.brand
```

**Executed against `example/contoso5/contoso5.duckdb`: no error. 11 rows. Result column names
`['brand', 'revenue', 'revenue', 'revenue']`.** Three different KPIs delivered under one name. The
`also` de-duplication at `sql.py:1823` compares `expr + " AS " + alias`, so identical aliases over
DIFFERENT expressions are not caught. Any consumer that reads a result by column name — the console
board, a chart spec, an oracle check — gets whichever column the driver hands back first.

### 5.3 · BREAK 3 (loud) — EVERY declared ratio dies, including a legitimate one

`planner/plan.py:300` decides whether a quotient is self-division by comparing CONCEPT NAMES:

```python
same = denominator[0].name == measure_concept.name
```

After the merge, numerator and denominator are both `Revenue` — even when they are `margin_amount`
over `net_amount`, two different columns. **All 3 of the bundle's 3 declared named ratios refuse, and
so does a plain unit-price quotient that worked before:**

```
BEFORE  {subject: Margin, denominator: "margin %"}   -> SELECT SUM(margin_amount)/NULLIF(SUM(net_amount),0) AS margin_per_netrevenue …
AFTER   {subject: margin_amount, denominator: "margin %"}
        -> REFUSE unsupported_intent: Revenue divided by itself over the same rows is 1.0 for
           every question, because the numerator and the denominator are then the same aggregate.

BEFORE  {subject: NetRevenue, denominator: UnitsSold} -> SELECT SUM(net_amount)/NULLIF(SUM(quantity),0) AS netrevenue_per_unitssold …
AFTER   {subject: net_amount, denominator: quantity}  -> REFUSE unsupported_intent: … divided by itself …
```

That last one is the operator's own ruled default reading — *what the customer paid per article,
310.98 USD* — refused as a tautology.

### 5.4 · BREAK 4 (SILENT, and latent behind Break 3) — rule order decides the answer

`planner/ratios.select` iterates a concept's ratio rules and **returns on the first one that yields a
selection**. Merging Margin's rule (two ratios, **no default, deliberately**) with Discount's rule
(one ratio, `default: percent`) onto one concept makes the second rule's default swallow the first
rule's question. Measured directly on both copies with `ratios.select(concept, asked=None)`:

```
BEFORE   Margin   : 1 rule, default=(none)
                    select(asked=None) -> ASK with candidates ('margin_percent','markup_percent')
         Discount : 1 rule, default=percent
                    select(asked=None) -> 'percent' / GrossRevenue (by_default=True)

AFTER    Revenue  : 2 rules
                    revenue.aggregation.margin_two_named_ratios        default=(none)
                    revenue.aggregation.discount_percent_is_over_gross default=percent
                    select(asked=None) -> 'percent' / gross_amount (by_default=True)
                                          from revenue.aggregation.discount_percent_is_over_gross
```

**"What is our margin?" stops asking and starts answering 5.93 %** — the discount rate — instead of
asking between 55.91 % over net and 126.79 % over cost. That is precisely the defect
`margin.aggregation.two_named_ratios` was written to prevent, and its own `why` names it: *"naming one
and computing the other is a wrong answer that looks right."* `ratios._read_all` also enforces its
one-word-one-ratio invariant **per rule**, so a surface colliding across two merged rules would go
undetected (no collision in this bundle today — latent, not live).

### 5.5 · What the bundle gates said

Run on `c5base` (pristine copy) and `c5merged`, same framework, same command:

| gate | c5base | c5merged |
|---|---|---|
| `check_concepts_not_per_table` | OK | OK — *blind to the 70 % duplication, before and after* |
| `check_common_rules` | 0 restatements | 0 restatements — *same blindness* |
| `check_concept_columns_exist` | OK, 17 concepts | OK, 12 concepts |
| `check_grain_declaration` | OK | OK |
| `check_no_inline_values` | OK | OK |
| `check_edge_joins_its_grounding` | **PASS**, 68 predicate sides / 34 joins | **FAIL** — 4 edges join a relation their concept does not bind *(reads `objects.json`, not the YAML — the derived plane was stale)* |
| `check_dangling_references` | FAIL, 62 new dangling | FAIL, **110** new dangling (**+48**, the deleted `.md` pages still linked from `references/usage_guardrails.md`, `concepts/index.md`, `ontology/MODELLING-LOG.md`, `SME-QUESTIONS.md`) |
| `check_question_shape_reachable` | OK, **85** joinable pairs | OK, **30** joinable pairs |
| `check_answerability` | FAIL, 19 uncovered steps | FAIL, 9 uncovered steps |

## 6 · RECOMMENDATION — DO IT, WITH THESE FOUR RUNTIME CHANGES FIRST

The operator is right: 70 % of the column declarations and 63 % of the edges are copies, no gate
sees it, and the mechanism that makes one concept workable (`_resolve_measure` → column) already
exists and already produces identical SQL and identical numbers. But **two of the four breaks are
silent**, and a silent break is the one thing this estate does not ship.

**R1 · THE RESULT ALIAS MUST COME FROM THE COLUMN, NOT THE CONCEPT.** `planner/sql.py:1127` and
`:1813` (and `:1780` for the `_per_<den>` suffix). Where a concept serves several measure columns,
the alias must name the column the question resolved to. Gate it: *no SELECT may carry two items with
the same alias* — that mutant exists today and nothing catches it. This is the blocking change.

**R2 · THE SELF-DIVISION GUARD MUST COMPARE COLUMNS, NOT NAMES.** `planner/plan.py:300`,
`same = denominator[0].name == measure_concept.name` → compare the resolved
`grounded_columns.measure_column` of each side. Today it is correct only because one concept means
one column. Independently of this proposal it is already wrong-by-luck.

**R3 · `ratios.select` MUST NOT LET ONE RULE'S DEFAULT PRE-EMPT ANOTHER RULE'S DELIBERATE SILENCE.**
`planner/ratios.py` — select the rule whose `binds` (its numerator) matches the column the question
resolved to, and ASK over the union of candidates when the question named nothing and more than one
rule applies. Extend the one-word-one-ratio invariant across a concept's rules, not within each.

**R4 · THE INTERPRETER PROMPT MUST OFFER THE MEASURE COLUMNS.** `Vocabulary.from_index`
(`interpret/vocabulary.py:263`) builds `measures` from `klass == MEASURE` and `MeasureTerm` carries
name/label/definition/ratios — **no column list**. After the merge the model would be offered exactly
one measure, `Revenue`, and could not name a KPI at all. The precedent is already in the file:
`DimensionTerm.groupable_columns` puts column names in the prompt and `interpret/prompt.py:244` renders them as
`[columns: …]`. 04 §4's invariant is *no TABLE names*, and `vocabulary.py:15` says `Grounding` is
never read here — so this is a real design decision for the operator, not a tidy-up, and it is the
one place where "manage all KPIs from one concept" costs the ontology something: the six definitions
that today teach the model what gross means and what net means collapse into one, and the KPI names
become bare column strings unless each column is given its own label and definition.

**Order:** R1 and R2 are mechanical and gateable — do them first, with the digest hash as the proof
(`157 plans → be8a974dddc5b091` must not move). R3 is a canon change and needs its own mutant tests.
R4 needs a ruling before code, because it decides whether a measure column can carry a label and a
definition of its own. **Only then** the migration, as one commit: 6 concept YAMLs out / 1 in,
24 edges → 4, 39 intent slots in 36 files retargeted, 10 surviving wiki-links retargeted, every
derived plane regenerated (`objects.json`, `compile.json`, `edges.json`, `concepts/*.md`,
`rules/*.md`, `samples/`, `references/`), 13 mac-platform tests updated — with `mac-platform/tools/gate.py`
showing **0 REGRESSED** over the 46 approved questions as the exit.

**The alternative not taken, and it is cheap.** Everything in §1 that is duplicated is duplicated in
the GROUNDING and in the EDGES, not in the meaning. A declared "this concept grounds the same
relation and columns as X" — one grounding, six concepts citing it — would remove 40 of 57 column
blocks and 20 of 24 edges with **zero** planner change, zero prompt change, zero frozen-intent
migration and zero loss of the six definitions. It does not satisfy the literal ask ("one single
KPI"), and it does satisfy the measurement behind it. Worth putting in front of the operator beside
this one.

## 7 · WHAT WAS LEFT BEHIND

The real bundle was read-only for this work. The two experiment copies live under the session
scratchpad at `revspike/c5base` (pristine) and `revspike/c5merged` (the merge as tested), with
rev.PROBE.BEFORE/AFTER.json, rev.PROBE2.BEFORE/AFTER.json, rev.GATE.BEFORE.txt and
`/tmp/rev.BEFORE.json` as the measurements. They are disposable; the numbers in this record are not.
