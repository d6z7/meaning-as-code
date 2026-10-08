---
state: proposed
genre: proposal
---
# PROPOSED — 2026-10-08 · the closed-store reading, and the ASK the board cannot express

> **Paths in this document.** `ontology/…`, `data/…` and `acceptance/…` are inside the bundle
> (`cap-ontology-sources/example/contoso5`); `mac_vocabulary.yaml` and `tools/…` are in
> `meaning-as-code`; `packages/…` is under `mac-platform`. A `:line` suffix is the line a measurement
> was read at. Every number below was read from the bundle's own DuckDB, read-only on 2026-10-08.

## Why this exists

The operator, 2026-10-08: *"continue analyzing test questions … i need to have most of them
promoted to passed"*. The board stood at 36 pass of 83, with 8 failing flags, 4 errors, 17 refusals
and 37 questions carrying no approved answer. This record is the diagnosis: **eight failing flags are
not eight defects.** Five of them are one, and the one is a word.

## ONE ROOT CAUSE, FIVE QUESTIONS: the bare word "closed"

`ontology/concepts/store.yaml:101-144` declares four populations through
`mac.canon.population_select`. Measured against the data:

| population | definition | rows | locations |
| --- | --- | --- | --- |
| `closed` | `close_date is_not_null` | 16 | **14** |
| `active` | `not: closed` | 58 | — |
| `shut` | `of: closed` + `status_annotation = 'Closed'` | **9** | 9 |
| `restructured` | `of: closed` + `status_annotation = 'Restructured'` | **7** | 6 |

The surfaces are the tell. The `closed` population lists `ceased`, `no longer trading`, `not active`,
`inactive` — **the bare word "closed" is not among them**, yet the population is NAMED `closed`.
`shut` lists `shut down`, `shut for good`, `closed permanently`, `closed and not replaced`. So an
unqualified "closed" lands on the 16-row population by NAME while every approved reference means the
9-row one, and nothing declares which reading wins.

### The money proves it rather than suggesting it

`STORE-11 — "What is the revenue of all closed stores?"`, approved 2,870,369 (operator, 2026-09-30):

| population | revenue |
| --- | --- |
| `closed` (16 rows) | **3,205,452.33** ← exactly what the engine answered |
| `shut` (9 rows) | **2,870,369.00** ← exactly the approved reference |
| `shut` without the Utah row (8) | 1,809,514.15 |
| `restructured` | 335,083.32 |

and `3,205,452.33 − 2,870,369.00 = 335,083.33`, the restructured stores to the cent. The engine is
internally consistent; it is answering a different question from the one the reference answers.

### The five

| question | engine | should be | why |
| --- | --- | --- | --- |
| `RC08` how many stores are closed? | 14 | 9 | population `closed`, not `shut` |
| `STORE-07` how many of our stores have closed? | 14 | 9 | same |
| `STORE-11` revenue of all closed stores | 3,205,452.33 | 2,870,369.00 | same |
| `STORE-13` list all restructured stores | 6 rows | 7 rows | counted at the INSTANCE unit (`counts: location_code`), so 6 locations instead of 7 versions |
| `STORE-06` how many store versions are recorded? | 57 | 74 | the `active` default applied where the question asks for the version grain |

`STORE-06` is the question `ANCHOR_16` exists to catch: *"if an engine answers 67 here it has applied
the collapse where the question asked for the version grain"*. It answered **57**, which is neither
74 nor 67 — it applied the `active` population on top of the collapse, a filter the question never
asked for.

## THE REFERENCES DISAGREE WITH EACH OTHER, on one row

Contoso Store Utah, `StoreCode 63`, shut 2019-11-03 carrying a **blank** `Status` in the landing.

- `data/transforms/dim_store.sql:38-45` FILLS it. The rule is measured and documented: a restructured
  location always has a later row at the same code (6 of 6), a closed one never does (0 of 8), Utah
  has no successor, so it is Closed by the data's own rule — *"reproduces all 15 stated values exactly
  and fills only the 16th"*.
- `store.resolution.active_is_the_absent_close_date` records the operator's ruling of **2026-10-01**:
  *"The fill made them equivalent: `close_date IS NOT NULL` now selects exactly the rows
  `status_annotation IN ('Closed','Restructured')` selects, 16 of them."*
- So `main.store` has **8** `Status='Closed'`; `contoso_served.dim_store` has **9**.

And the approved references split exactly on it:

| reference | approved | implies |
| --- | --- | --- |
| `STORE-11` revenue 2,870,369 | 2026-09-30 | 9 stores — **Utah counted** |
| `RC08` count 8 | 2026-09-25 | 8 — Utah not counted |
| `ANCHOR_17` value 8 | cloned 2026-09-29 | 8 — Utah not counted |

Both of the "8"s PREDATE the 2026-10-01 fill. `ANCHOR_17` even predicts this: *"Counting closures by
date instead gives 9, because store 63 closed on 2019-11-03 carrying a NULL Status. Both numbers are
in the data and only one is what the bundle says the words mean."* **OWED: the operator ratifies 8 → 9,
or rules that the fill must not write `Closed`.** An agent cannot settle it — this is a meaning, and
`ANCHOR_17`'s own `authority_note` says an anchor *"CANNOT say the ontology's MEANING is right"*.

Two further anchor defects found while reading them, neither blocking:
ANCHOR_17's derivation SQL and ANCHOR_21's both name `contoso_served.dim_contoso_store`, **which does
not exist in this bundle** — only the `cross_check_sql` against `main.*` still runs. `ANCHOR_17`
discloses this (*"the served-plane derivation is owed"*); it is now also the reason the served plane's
9 went unmeasured.

## THE SECOND FINDING, AND IT IS BIGGER: the board cannot say ASK

The operator, on being offered a default reading: *"how difficult would it be … to add deliberate ask
question here: closed + restructured or closed only. so the right answer would be ASK (ambigouos)"*.

That is the resolution ladder applied, and it is the right answer rather than picking a default. What
exists and what does not:

- **Declared:** `mac_vocabulary.yaml:1209` — `ambiguity: "An underspecified REQUIRED dimension — ASK,
  never guess."` The rule kind is in the vocabulary.
- **Half-built:** `mac_vocabulary.yaml:700` — *"ambiguity_gate — the four `*_select` canons each
  construct their own ASK and none calls it; bound, it can only refuse."* Four canons each build their
  own ASK; the gate that should own it is called by nobody.
- **MISSING ENTIRELY:** the acceptance vocabulary has no ASK. `expected_outcome` carries exactly two
  values across all 83 questions — **COMMIT 81, REFUSE 2**. "The right answer is ASK" is UNSAYABLE on
  this board.

### And that is why the refusal count was read wrongly

`disposition` records what HAPPENED; `expected_outcome` records what was REQUIRED. Of the 17 refusals,
**15 have `expected_outcome: COMMIT`** — only `MQ-15` and `ADV-23` were meant to refuse. So 15
questions refuse where they should answer, and they are real failures. A reading of `disposition`
alone says the opposite, and did: this record exists partly to correct that, having stated it to the
operator in this session before measuring `expected_outcome`.

Those 15 are the measured population for the ASK work, and the prize: a disclosed ambiguity scored as
a PASS rather than a mismatch.

## Proposed, in the order the effort actually falls

1. **Three explicit questions, today, no mechanism work.** "How many were closed" → 9, "how many were
   restructured" → 7, "how many were closed and restructured" → 16 rows / 14 locations. All three
   populations are already declared with surfaces; this needs the questions and their anchors derived
   from the data.
2. **`STORE-06` and `STORE-13`**, independent of every ruling above: the version grain must not take
   the `active` population, and a LIST at version grain must not collapse to the instance unit.
3. **The Utah ratification** — 8 → 9, or revert the fill. Operator only.
4. **ASK as its own piece of work**, not bolted on: a third `expected_outcome` term, the scorer taught
   that a disclosed ambiguity passes, and `ambiguity_gate` actually called by the `*_select` canons
   instead of four private ASKs. Vocabulary + runtime + acceptance scorer, with those 15 refusals as
   its denominator.

Nothing in 1–4 has been written. This record is the measurement, and 3 is owed before 1 can state a
number.
