<!-- The running record of BUNDLE GENERATION (PIPELINE_TESTING.md §8.2 stage 7). Append, never
     rewrite. -->

# BUNDLE GENERATION — RESULTS

## 2026-09-24 · First generated bundle, and the first point on the L0 → L2 curve

`bundlegen/generate.py --tier L1` over **`contoso.duckdb#main`** — the RAW landing, eight tables,
**no declared constraints at all** (measured: `duckdb_constraints()` returns 0 rows for that
schema). Nothing was asked of a person.

Contoso's own landing was chosen over a BIRD database deliberately: it is an unmodelled warehouse
sitting beside a **hand-authored bundle over the same rows**, so L1 and L2 can be compared on the
same questions with the same 21 anchors. No download, and ground truth on both sides.

```
8 concepts · 5 with an inferred key · 8 candidate edges
  Currencyexchange reference  key=None          measures=[Exchange]
  Customer         reference  key=CustomerKey   measures=[Age, Latitude, Longitude]
  Date             reference  key=DateKey       measures=[YearQuarterNumber, MonthNumber, …]
  Orderrows        event      key=None          measures=[RowNumber, Quantity, UnitPrice]
  Orders           reference  key=OrderKey      measures=[]
  Product          reference  key=ProductKey    measures=[Weight, Cost, Price]
  Sales            event      key=None          measures=[LineNumber, Quantity, UnitPrice]
  Store            reference  key=StoreKey      measures=[SquareMeters]
```

**It loads, and it answers.** That is the milestone: a bundle nobody wrote, over a schema nobody
modelled, reaching the planner.

### THE RESULT THAT MATTERS — it answers CONFIDENTLY AND WRONGLY

| question | L1 generated | L2 authored | error |
|---|---|---|---|
| how many stores | **74** | 67 | **10.4 %** |
| average store size | **1 494.79** | 1 504.55 | **0.6 %** |
| total floor space | **109 120** | 99 300 | **9.9 %** |
| how many products | 2 517 | 2 517 | — |
| how many customers | 104 990 | 104 990 | — |

**Every store figure is wrong, and wrong the same way: no SCD-2 collapse.** `main.store` holds 74
versions of 67 stores and *nothing in the schema says so*. Getting it right needs
`natural_key: StoreCode` and a declared snapshot collapse — which is **authoring**, not inference.

**None of the wrong numbers looks wrong.** 0.6 %, 9.9 %, 10.4 % — plausible figures, valid SQL, no
symptom on the page. The generated bundle does not refuse and does not hedge; it answers, and a
reader has no way to tell. That is the clearest statement of what declaring meaning buys that this
estate has produced, and it is one data point on the curve rather than an argument.

### What the generator gets right, and what it cannot

**Right:** `Store.SquareMeters` as a measure — the thing that took a full day to find by hand;
`Orderrows`/`Sales` as events; five keys measured rather than named.

**Wrong, and each names something authoring supplies:**

| | what it did | what that costs |
|---|---|---|
| `Orders` → `reference` | 2 foreign keys but no numeric column, so the "event" rule missed a genuine fact | the fold gate and the count route both treat it as a dimension |
| `Orderrows`, `Sales`, `Currencyexchange` → no key | their keys are **composite**; only single-column uniqueness is searched | no countable identity, so "how many order lines" is unreachable |
| `Date` measures = `Year`, `MonthNumber` | numeric and not key-shaped, so called measures | averaging a year is meaningless and nothing forbids it |
| `Customer` measures = `Age`, `Latitude` | same rule | `Age` is the stale column the authored bundle explicitly refuses |
| **`Sales` emitted as a second fact** | it is the DOUBLE DELIVERY that `NS-ORDERS-01` refuses — the same 223 974 lines under a second name | a question is answerable two ways with different provenance, and nothing says which |

The last one is the sharpest: **no amount of profiling can know that one of two identical tables
must not be served.** That is a ruling, and rulings are what L2 is.

### Two platform gates were out of date with their own planner

Both surfaced by trying to load a generated bundle, both the same defect as the rest of the day:

* `edges.yaml` written flat (`from`/`to`) is refused — the loader requires `endpoints`. Fixed in
  the generator: the shape the loader declares is the shape it gets.
* **`ask_engine` refused the bundle outright: "declares no measure".** It required a measure-CLASS
  concept, while the planner had that morning been taught that a `field_role: measure` COLUMN is a
  measure. A bundle declaring 11 measure columns and no measure concept could not be loaded at
  all. Now both homes are read.

Suite 834 passed; planner invariants 176 checks, 0 red.

### Next

* composite keys (three of eight tables have one, and it is the known `case X` shape);
* containment checks, so an edge is a measured join rather than a name match;
* `--tier L0` measured separately, since on a landing with no constraints L0 is nearly empty —
  which is itself the argument for L1;
* then the same generator over a BIRD database, where SQLite *does* declare keys, and the corpus
  becomes askable.
