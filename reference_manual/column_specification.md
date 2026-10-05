---
title: The column specification — everything about a column, on the column
status: >-
  PARTIALLY ENFORCED (2026-10-05) — five flags LOAD (`role`, `identity`, `counts`, `measure`, `rulings`: what
  mac.schema.json admits under grounding.sources[].columns.<col> with additionalProperties:false, and what
  mac-runtime reads); seven sections are PROPOSED and REFUSED by the schema today (`references`, `domain`,
  `resolution`, `placement`, `absence`, `disclose`, `discriminates`). They are banded at the end of this page.
audience: ontology authors, importer developers, console developers
companions: [how_a_question_becomes_sql.md, column_rulings.md, column_roles.md, column_map.generated.md, patterns/]
---

# The column specification

> **Designed, then partly enforced — read this before copying a block.** `mac.schema.json` admits, under
> `grounding.sources[].columns.<column>`, exactly five keys — **`role`, `identity`, `counts`, `measure`,
> `rulings`** —
> and refuses every other key (`additionalProperties: false`); mac-runtime reads those five. Everything
> else this page designed — `references`, `domain`, `resolution`, `placement`, `absence`, `disclose`,
> `discriminates` — is **refused by the schema today: a concept that writes one of them does not load.**
> Those sections are kept, unchanged in substance, in the banded
> [PROPOSED — refused by the schema today](#proposed--refused-by-the-schema-today) section at the end, and
> each worked example says which of its keys would not load. The generated, cannot-drift view of what the
> schema admits is [column_map.generated.md](column_map.generated.md).
>
> Two corrections to the earlier draft of this page, both from the schema: `rulings.never_axis` is a
> **free-text reason** (no `privacy | grain | derived` vocabulary exists anywhere), and `rulings.register`
> **requires `rulings.label_of`** (`dependentRequired`, added 2026-09-29). The concept-level identity
> kinds are gone entirely — the whole block was retired 2026-10-05; identity is declared on the column.

## The principle

> **A fact about one column is declared on that column.**
> A fact about the concept, or spanning several columns, stays at concept level.

Nothing else. Every rule below follows from it.

---

## The shape, at a glance — what loads today

No comments — every key is explained in its own section below.

```yaml
grounding:
  sources:
    - relation: <relation>
      key: <column>
      columns:

        <column-name>:
          role: key | dimension | measure | period | housekeeping
          identity: canonical | part | reference
          rulings:
            label_of: <column>
            register: common | legal | long | short | code
            finer_than: <column>
            scoped_by: <column>
            never_axis: <the reason, one line of prose>
            evidence: <dq-id>
          measure:
            type: flow | stock | intensive | precomputed | target
            unit: <string>
            additivity: { <axis>: ..., ... }
```

The fuller shape this page designed — the same four plus seven more sections — is shown, and marked as
not loading, in the [PROPOSED](#proposed--refused-by-the-schema-today) section.

**Columns nest under the source they belong to**, because a column name only means anything within
a relation. `Country` proves why: the concept binds two relations, and the same identity is spelled
`Country` on the customer dimension and `CountryCode` on the store dimension. A flat block could
not say that.

**`role` is the one key every column should carry** (the schema also admits `null` — "serve the column
and say nothing more"). The common case is one line:

```yaml
sources:
  - relation: dim_contoso_customer
    columns:
      Gender: { role: dimension }
```

---

## The four flags that load

### `role` — where a query may use the column at all

```yaml
Gender: { role: dimension }
```

Five values, all **derivable** from the data, which is the test a role has to pass — a generator
assigns them over a thousand columns with no human present. Written as the bare term: the namespace
`mac.concept.column.role` is added by the projection, never by the author. Detail:
[column_roles.md](column_roles.md).

### `identity` — which column IS the thing

```yaml
CustomerKey: { role: key, identity: canonical }
GeoAreaKey:  { role: key, identity: reference }
OrderKey:    { role: key, identity: part }
RowNumber:   { role: key, identity: part }
```

Three values, defined in `mac.concept.column.identity`: **`canonical`** is the one column that
identifies an instance — what `COUNT(DISTINCT)` counts; **`part`** is one column of a composite
identity and **identifies nothing alone**; **`reference`** points at another concept's identity.
(*Which* concept it points at was designed as `references: <Concept>` beside it — that key does not
load today; see PROPOSED.)

**This is the ONLY home for identity.** A concept-level `identity:` block once sat beside it,
declaring how identity was *established* — `iso`, `code`, `namespace_code`, `fk_name`, `composite`,
`sme_pending`. It was retired on 2026-10-05. Operator ruling: *"declare on concept level only what
belongs to the concept level … identity of the concept is given by column combination and it belongs
there."* Measured before removing it: `composite` was derived from the `part` columns anyway, `iso`,
`namespace_code`, `fk_name` and `sme_pending` had **zero** readers in the runtime, and the single
reader of `code` was misfiring — it refused a reference dimension that merely carried a rollup.

A fourth column value, `natural`, was dropped earlier as a category error. The reasoning then was
that a natural key is a claim about the *kind* of identity and so belonged on the concept; the kind
turned out not to be worth declaring at all.

Beside `identity` sits **`counts: true`** — the column one *instance* is counted by, when the
relation is served finer than the thing. A store dimension keyed on a version surrogate counts
versions unless this says otherwise, and the two numbers differ with nothing in the result saying
which you got. It is a separate flag because the column that counts is routinely also the one that
`references`.

<!-- BEGIN GENERATED:vocabulary-terms:concept.column.identity (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> What part a column plays in its concept's identity. THE ONLY HOME — there is no concept-level
identity block.

*`mac.concept.column.identity` · 3 terms · closed — these are all of them*

#### `mac.concept.column.identity.canonical`

THE column that identifies one instance. What `COUNT(DISTINCT …)` counts, and what an answer
discloses that it counted. Exactly one per concept, and a concept that legitimately has none
declares `part` on every column of its key tuple instead — several parts and no canonical IS the
composite — rather than nominating a column that does not identify.

| field | value |
|---|---|
| `constellation` | EXACTLY ONE COLUMN IS THE THING ITSELF AND NAMES RESOLVE TO IT. The case that compels it: a surrogate key every fact points at, with a human-readable code and a name beside it that are both 1:1 with it. All three look alike in a profile; only this says which one the joins and the counts are about.
 |

#### `mac.concept.column.identity.part`

ONE COLUMN OF A COMPOSITE IDENTITY, which IDENTIFIES NOTHING ALONE. Using it as though it did
returns a set where a row was expected, and looks like an answer. Declared on every column of
the tuple, and that is the whole declaration: no canonical column over a key of two or more IS
the composite, and the concept adds nothing.

| field | value |
|---|---|
| `constellation` | NO SINGLE COLUMN IDENTIFIES A ROW AND TWO OR MORE TOGETHER DO. A sale line is identified by its order and its line number — neither is unique alone, and declaring either as the identity would make the grain a lie. Mark each participating column, and the composite is what the concept is keyed on.
 |

#### `mac.concept.column.identity.reference`

A POINTER AT ANOTHER CONCEPT'S IDENTITY — this concept's row names a row over there. What it
points at is named separately; whether every value is PRESENT in the parent is a measurement,
not a declaration, and a reference with no parent relation in the delivery is recorded AS
dangling rather than dropped or invented.

| field | value |
|---|---|
| `constellation` | THE COLUMN HOLDS ANOTHER CONCEPT'S IDENTITY, NOT THIS ONE'S. A customer key on a sale identifies a customer; the sale is identified by something else entirely. Without this the key reads as part of the sale's own identity, and a count of sales becomes a count of customers.
 |
<!-- END GENERATED:vocabulary-terms:concept.column.identity -->

### `rulings` — judgements measurement cannot make

```yaml
ZipCode:
  role: dimension
  rulings:
    never_axis: "identifies a person — 29 193 of 104 990 values are held by exactly one customer"
    evidence: DQ-CUSTOMER-02
```

Four of them — `label_of` (with its `register`), `finer_than`, `scoped_by` (loaded, not yet planned-on; not in the
table below because `column_effects.yaml` has no entry for it yet), `never_axis` — each with
its own constellation, worked example and implementation status in
[column_rulings.md](column_rulings.md). Two things the schema enforces: `evidence` is **required**
with `never_axis` (a prohibition without a measurement is a preference), and `register` is **only
legal beside `label_of`** (it says *which* of the thing's names this column is, so it needs the
thing). `never_axis` is the reason as a sentence, quoted into the refusal — not a token.

### `measure` — which folds are legal

```yaml
NetPrice:
  role: measure
  measure: { type: flow, unit: USD }
```

Only on `role: measure`. `type` is a `mac.concept.column.measure_type` term (`flow`, `stock`,
`intensive`, `precomputed`, `target` — see [measures.md](measures.md)); `additivity` overrides the
type for one named axis — a balance that sums across products and not across time.

---

## Every key

Two tables, one heading: the first is what loads today, the second is what this page designed and
the schema refuses. A key is in exactly one of them.

**Loads today — admitted by `mac.schema.json`, read by mac-runtime:**

| key | required | default | legal values | decides |
|---|---|---|---|---|
| `role` | **yes** | — | `mac.concept.column.role.*` (written bare) | where a query may use the column at all |
| `identity` | role: key | `reference` | `mac.concept.column.identity.*` | what part this column plays in the concept's identity — see `mac.concept.column.identity` for the three meanings, and `concept.identity.kind` (`mac.concept.identity.*`) for how identity is **established** |
| `rulings.label_of` | no | — | a column | this column NAMES that one; group there, display here |
| `rulings.register` | with label_of | `common` | `mac.name_register.*` | which of the thing's names this is (schema: `dependentRequired` on `label_of`) |
| `rulings.finer_than` | no | — | a column | this column rolls up into that one |
| `rulings.sort` | no | — | `asc` \| `desc` \| `none` | the order this column's values are presented in when the question states none — `asc` alphanumeric for a NAME, `desc` largest-first for a MAGNITUDE, `none` never an ordering key. Per column, never per concept. |
| `rulings.never_axis` | no | — | free text — the reason, one line | may not be grouped on; the reason is quoted into the refusal |
| `rulings.evidence` | **with never_axis** | — | a DQ id | the measurement. Without it, a prohibition is a preference. |
| `axis_kind` | no | — | `mac.concept.axis_kind.*` | which KIND of aggregation axis this column is — the fold law is stated over kinds, so it is universal |
| `register` | no | — | a bundle-relative path | the value set this column carries, one virtual table per set |
| `measure.type` | role: measure | — | `mac.concept.column.measure_type.*` | which folds are legal |
| `measure.unit` | no | — | free text | what the number is in |
| `measure.canonical` | no | — | `true` | this column IS the concept's number — what a question about the concept itself folds. Settles the unit where a concept grounds several measure columns. |
| `measure.additivity` | no | from `measure.type` | per-axis | overrides the type for a named axis |

**PROPOSED — refused by the schema today (`additionalProperties: false`); none of these loads:**

| key | required | default | legal values | decides |
|---|---|---|---|---|
| `references` | identity: reference | — | a concept name | what the pointer points at |
| `domain.closure` | no | `open` | `closed` · `open` | whether a non-member is answerable from the list, with no probe |
| `domain.complete_for` | closure: closed | `data` | `data` · `world` | a recognised word outside the list → **zero, disclosed** (`data`) or **refuse** (`world`) |
| `domain.warranty` | closure: closed | — | `derived` · `monitored` | a rule produces the members, or a scheduled check reconciles them. **No third option.** |
| `domain.register` | no | — | a path | where the members live |
| `domain.members` | no | — | a list | inline members, for a handful |
| `resolution.search` | no | the register's key column | register column names | what a typed word is matched against |
| `resolution.display` | no | the code | a register column | what is shown back to the reader |
| `resolution.strategy` | no | `[exact, normalized, prefix, fuzzy]` | an ordered subset | which rungs of the ladder run |
| `resolution.fuzzy_floor` | no | `0.80` | 0.0–1.0 | below this, no candidate is offered at all |
| `resolution.on_miss` | no | derived from closure+complete_for | `refuse` · `zero_disclosed` · `ask` | what a word that resolves to nothing produces |
| `resolution.candidates` | no | `5` | integer · `suppress` | how many "did you mean" options |
| `placement.fact_join` | no | — | a column | the fact filters here; no dimension join is walked |
| `placement.scoped_by` | no | — | a column | the scope column must travel with this code (the loading form is `rulings.scoped_by`) |
| `absence.nulls` | no | `unknown` | `none` · `unknown` · `not_applicable` · free text | what NULL **in this column** means |
| `absence.sentinels` | no | — | values | non-null values that are not members |
| `disclose` | no | — | one line | text quoted into any answer that touches this column |
| `discriminates` | no | `false` | boolean | this column selects which kind of row |

---

## What the column HOLDS — its type family

`role` says where a query may use a column; the type family says what a comparison against it may
mean. A threshold of `630.5` against an integer key and a boolean against a numeric both refuse at the
same gate, and they refuse by FAMILY rather than by warehouse spelling — the spellings are a bundle's
descriptor data and differ per warehouse, so the families are closed here and the spellings are
normalised before matching (the text before `(` or `<`).

<!-- BEGIN GENERATED:vocabulary-terms:column_type (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> The family of value a column holds, with the warehouse spellings that mean it. Closed over
FAMILIES; open over spellings, which a bundle's descriptors supply and which are normalised
before matching (the text before `(` or `<`).

*`mac.column_type` · 5 terms · closed — these are all of them*

#### `mac.column_type.text`

Characters. A NAME, a code, a label -- something read rather than measured.

| field | value |
|---|---|
| `spellings` | string, varchar, char, text, nvarchar, uuid |

#### `mac.column_type.number`

A magnitude. Something that can be larger or smaller than another of its kind.

| field | value |
|---|---|
| `spellings` | integer, int, bigint, smallint, tinyint, decimal, numeric, double, float, real |

#### `mac.column_type.temporal`

A point in time. The only family a date literal may be compared against.

| field | value |
|---|---|
| `spellings` | date, timestamp, datetime, timestamptz, time |

#### `mac.column_type.boolean`

True or false. Two members, so it is never a magnitude and never a name.

| field | value |
|---|---|
| `spellings` | boolean, bool |

#### `mac.column_type.collection`

Several values in one cell. Never an axis and never an ordering key: GROUP BY over a collection
groups by the container, which is not a member of anything a question asked about.

| field | value |
|---|---|
| `spellings` | array, map, struct, row, json |
<!-- END GENERATED:vocabulary-terms:column_type -->

---

## When a value set is a calendar, not a register

`register` above points at the value set a column carries, and the usual reason to declare one is that
a typed word has to resolve to a stored code. A calendar needs none of that: `March`, `Mon`, `2024-Q3`
and `2024-03-01` are recognised by a built-in reader, so no lookup is cut for them, none is carried
into a bundle, and none is monitored. A column whose values are one of these forms is a calendar, and
declaring a register for it would create a second home for the Gregorian calendar.

<!-- BEGIN GENERATED:vocabulary-terms:calendar_vocabulary (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> The words and literal forms of the Gregorian calendar. A column whose value set is one of these
is a calendar, not a register: the built-in reader recognises it and no lookup is cut, carried
or monitored for it.

*`mac.calendar_vocabulary` · 9 terms · closed — these are all of them*

#### `mac.calendar_vocabulary.month_name`

The twelve month names in full.

| field | value |
|---|---|
| `members` | January, February, March, April, May, June, July, August, September, October, November, December |

#### `mac.calendar_vocabulary.month_short`

The three-letter month abbreviations. `Sept` is admitted beside `Sep` because deliveries write
both.

| field | value |
|---|---|
| `members` | Jan, Feb, Mar, Apr, May, Jun, Jul, Aug, Sep, Sept, Oct, Nov, Dec |

#### `mac.calendar_vocabulary.weekday_name`

The seven weekday names in full.

| field | value |
|---|---|
| `members` | Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday |

#### `mac.calendar_vocabulary.weekday_short`

The three-letter weekday abbreviations.

| field | value |
|---|---|
| `members` | Mon, Tue, Tues, Wed, Thu, Thur, Thurs, Fri, Sat, Sun |

#### `mac.calendar_vocabulary.quarter_label`

A quarter of a year, unqualified by which year.

| field | value |
|---|---|
| `members` | Q1, Q2, Q3, Q4 |

#### `mac.calendar_vocabulary.iso_date`

A day. `2020-12-31`, with an optional time this estate's served dates do not carry (every date
column measured on the worked bundle is midnight).

| field | value |
|---|---|
| `shape` | YYYY-MM-DD |

#### `mac.calendar_vocabulary.year`

A year as four digits. Half-open over twelve months when compared.

| field | value |
|---|---|
| `shape` | YYYY |

#### `mac.calendar_vocabulary.year_month`

A month of a named year. `2024-03`, `March 2024`, `Mar 2024`.

| field | value |
|---|---|
| `shape` | YYYY-MM |

#### `mac.calendar_vocabulary.year_quarter`

A quarter of a named year. `Q1 2024`, `2024-Q1`.

| field | value |
|---|---|
| `shape` | Qn YYYY |
<!-- END GENERATED:vocabulary-terms:calendar_vocabulary -->

---

## Worked: `Customer`, all 13 columns

`identity: canonical` on `CustomerKey` · one source.

> **Which keys would not load:** `references` (on GeoAreaKey), `placement` (State), `domain` and
> `absence` (Gender, age_band_5y), `disclose` (age_band_5y). Strip those and the block validates;
> keep them and `validate_schema` refuses the file. The `role`, `identity` and `rulings` lines load.

```yaml
grounding:
  grain: one row = one customer
  sources:
    - relation: dim_contoso_customer
      key: CustomerKey
      columns:

        CustomerKey:
          role: key
          identity: canonical

        GeoAreaKey:
          role: key
          identity: reference
          references: Region                       # PROPOSED — does not load

        Continent:
          role: dimension

        Country:
          role: dimension

        CountryFull:
          role: dimension
          rulings: { label_of: Country, register: long }

        State:
          role: dimension
          placement: { scoped_by: Country }        # PROPOSED — does not load; write rulings.scoped_by

        StateFull:
          role: dimension
          rulings: { label_of: State, register: long }

        Gender:
          role: dimension
          domain:                                  # PROPOSED — does not load
            closure: closed
            complete_for: world
            warranty: monitored
            register: data/lookups/contoso_gender.lookup.csv
          absence: { nulls: none }                 # PROPOSED — does not load

        age_band_5y:
          role: dimension
          domain:                                  # PROPOSED — does not load
            closure: closed
            complete_for: world
            warranty: derived
            members: [20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90]
          disclose: "banded to 5 years, as of 2025-12-31"   # PROPOSED — does not load

        City:
          role: dimension
          rulings: { never_axis: "identifies a person (with ZipCode)", evidence: DQ-CUSTOMER-02 }

        ZipCode:
          role: dimension
          rulings: { never_axis: "identifies a person — 29 193 of 104 990 values held by one customer", evidence: DQ-CUSTOMER-02 }

        StartDT:
          role: housekeeping

        EndDT:
          role: housekeeping
```

**`Country` here is only a dimension.** It is the *identity* of the `Country` concept, not of
`Customer` — the same column, a different part in two concepts, which is exactly why `identity` is
per column and not a property of the column's name.

---

## Worked: `Country`, two relations

`identity: canonical` on `Country` · **two sources**, and the same identity spelled
differently on each.

> **Which keys would not load:** `domain`, `resolution`, `placement`, `absence` and `disclose` on
> `Country`; `absence` on `CountryCode`. The `role`, `identity` and `rulings` lines load.

```yaml
grounding:
  sources:
    - relation: dim_contoso_customer
      key: CustomerKey
      columns:
        Country:
          role: key
          identity: canonical
          domain:                                  # PROPOSED — does not load
            closure: closed
            complete_for: data
            warranty: monitored
            register: data/lookups/contoso_country.lookup.csv
          resolution:                              # PROPOSED — does not load
            search:  [search_key, Country]
            display: label
          placement:                               # PROPOSED — does not load
            fact_join: Country
          absence: { nulls: none }                 # PROPOSED — does not load
          disclose: >-                             # PROPOSED — does not load
            Country determines Continent — measured a function, 0 of 8 countries on two continents.

        CountryFull:
          role: dimension
          rulings: { label_of: Country, register: long }

    - relation: dim_contoso_store
      key: StoreKey
      columns:
        CountryCode:
          role: key
          identity: canonical
          absence:                                 # PROPOSED — does not load
            sentinels: ['--']

        CountryName:
          role: dimension
          rulings: { label_of: CountryCode, register: long }
```

**Two `identity: canonical` declarations, one per source, and that is correct.** The concept has one
identity; each relation has its own spelling of it. The bundle's own identity note says so:
*"`canonical_key` names the CUSTOMER dimension's spelling because that relation is sources[0] …
the store dimension carries the same values under `CountryCode`."*

**And the sentinel sits where it belongs.** `'--'` appears only on the store side — 9 distinct codes
there against 8 on the customer side — so `sentinels` is declared on `CountryCode` and not on
`Country`. A flat column block would have had to state it for both or neither.

### The five choices in that example that are not obvious

| column | key | value | why |
|---|---|---|---|
| `Country` | `complete_for` | `data` | the eight countries are the ones **delivered**, not the ones that exist. *"Sales in Japan"* answers **zero**, not *"not a country"*. |
| `Gender` | `complete_for` | `world` | the two members **are** the kind. A third word is not a gender here, so it refuses. **Same closure as Country, opposite answer.** |
| `Country` | `warranty` | `monitored` | the members were observed from the served plane, so a scheduled check must reconcile them or the closure decays |
| `age_band_5y` | `warranty` | `derived` | a CASE expression in the transform makes the members — a new load **cannot** add a sixteenth, so no watchdog is needed |
| `Country` | `resolution.display` | `label` | a person asked for *"Germany"* and must be shown *"Germany"*, not `DE` |

(All five are choices among PROPOSED keys.)

## Why there is no `note` field

**A free-text key on a column is where rulings go to hide.** Measured on contoso 2026-09-25:
`grounding.note` carries ruling language — *never*, *must not*, *display-only*, *because* — in
**12 of 21 concepts**. The clearest is `customer.yaml`, whose 1 044-character note read:

> *"`ZipCode` and `City` are display-only, never filter or group — because DQ-CUSTOMER-02 measured
> that ZipCode alone singles out 29 193 of 104 990 served rows."*

A measured privacy ruling, stated in prose, in a field nothing reads — while the runtime happily
planned `GROUP BY ZipCode`. It became `never_axis` + `evidence: DQ-CUSTOMER-02`, and the
refusal now cites the measurement.

That is the whole failure mode of this estate in one field, and it is not unique: `contract.resolution`
is 13 careful paragraphs nothing reads, the absence reading was declared on 20 concepts and read by
none. **A block designed to end that must not ship with a slot that restarts it.**

So: **the column block has no free-text key** — with one deliberate exception, `never_axis`, whose
value is a sentence *because it reaches the reader of the refusal*. If you want to write something
about a column:

| what you want to say | where it goes |
|---|---|
| it changes what the engine does | a **declaration** — find the key, or the key is missing and that is the finding |
| the reader of an ANSWER must know it | `disclose:` (PROPOSED) — it reaches them, which prose never does |
| why a ruling was made | `evidence:` — a measurement id, not a paragraph |
| it is unresolved | the SME ledger outside `ontology/` — with an id, an owner and a status |
| it is about the concept, not this column | `concept.definition` |

**The worked case.** An earlier draft of this document wrote:

```yaml
CountryCode:
  role: dimension
  note: the store side's spelling of the same geography
```

**That third line is wrong.** It is a claim that two columns in two relations hold the same
geography — an **edge between concepts**, undeclared, hiding in prose. The note did not describe the
model; it substituted for a missing part of it.

## What stays at concept level

| key | why it cannot descend |
|---|---|
| `concept.definition`, `concept.class` | about the concept |
| `grounding.grain` | about a **set** of columns — what one row is |
| `grounding.sources[].relation` | the binding itself |
| `edges` | between **concepts** |
| `contract.default_reading` | what an unqualified **word** means |
| `contract.rules[].when` / `then` / `never` / `why` | a rule's **prose** is usually cross-column |

**But a rule's params are not prose.** `code`, `search`, `display_label`, `fact_join` are mechanics
about one column and they descend onto it. **Prose stays, params descend** — that split is what
stops `columns:` becoming a second dumping ground.

---

## What is never declared here

These are **measured**. Declaring them would create a second home for a fact the warehouse states.

| fact | where it comes from |
|---|---|
| type, storage role | `data/datasets/<relation>.yaml` |
| distinct, nulls, min, max | `data/profiles/<relation>.yaml` |
| observed landing values | `data/sources/<relation>.yaml` |
| the members themselves | `data/lookups/<name>.lookup.csv` |

`domain.closure` (PROPOSED) says *whether the list is complete*. It never restates the list.

---

## PROPOSED — refused by the schema today

> **Nothing in this section loads.** The column map in `mac.schema.json` is `additionalProperties:
> false` over `role`, `identity`, `measure`, `rulings`; every key below is a LOAD ERROR until the
> schema admits it and code reads it — a flag ships with its consumer. The design is kept because
> the arguments are still the arguments; when one of these is admitted, move its section up into
> *The four flags that load* and its rows into the first table.

### The proposed shape, in full

```yaml
<column-name>:
  role: key | dimension | measure | period | housekeeping
  identity: canonical | part | reference
  references: <Concept>                          # PROPOSED
  domain:                                        # PROPOSED
    closure: closed | open
    complete_for: data | world
    warranty: derived | monitored
    register: <path>
    members: [<code>, ...]
  resolution:                                    # PROPOSED
    search: [<register column>, ...]
    display: <register column>
    strategy: [exact, normalized, prefix, fuzzy]
    fuzzy_floor: 0.80
    on_miss: refuse | zero_disclosed | ask
    candidates: <n> | suppress
  placement:                                     # PROPOSED (scoped_by loads as rulings.scoped_by)
    fact_join: <column>
    scoped_by: <column>
  absence:                                       # PROPOSED
    nulls: none | unknown | not_applicable | <meaning>
    sentinels: [<value>, ...]
  rulings:                                       # loads — see above
    label_of: <column>
    register: common | legal | long | short | code
    finer_than: <column>
    scoped_by: <column>
    never_axis: <the reason, one line of prose>
    evidence: <dq-id>
  measure:                                       # loads — see above
    type: flow | stock | intensive | precomputed | target
    unit: <string>
    additivity: { <axis>: ..., ... }
  disclose: <one line>                           # PROPOSED
  discriminates: true                            # PROPOSED
```

### `references` — what an `identity: reference` points at

```yaml
GeoAreaKey: { role: key, identity: reference, references: Region }
```

`identity: reference` loads; the concept it points at does not have a slot yet. Today the target is
recoverable only from the edge that realizes the join.

### `domain` — what values exist, and whether the list is complete

```yaml
Gender:
  role: dimension
  domain:
    closure: closed
    complete_for: world
    warranty: monitored
    register: data/lookups/contoso_gender.lookup.csv
```

`closure` says whether the list is complete — it **never restates the list**, which lives in the
register. `complete_for` distinguishes *"complete for this delivery"* from *"complete for the
world"*, and that single bit decides whether a word outside the list refuses or answers zero.
`warranty` says how the closure is kept true: `derived` (a rule makes the members, so nothing can
add one) or `monitored` (observed, so a scheduled check reconciles it). **There is no third value** —
a closed set nobody watches is a refusal backed by a stale sample.

### `resolution` — how a typed word becomes this column's value

```yaml
Country:
  role: key
  resolution:
    search:  [search_key, Country]
    display: label
```

`search` is what a typed word is matched against; `display` is what is shown back — *"Germany"*,
not *"DE"*. The ladder (`strategy`, `fuzzy_floor`, `candidates`) has working defaults and is
narrowed only when a column needs it. `on_miss` is **derived**, not set — see
[the defaults](#the-five-defaults-that-decide-behaviour).

### `placement` — which column the predicate actually lands on

```yaml
State:   { role: dimension, placement: { scoped_by: Country } }
Country: { role: key,       placement: { fact_join: Country } }
```

**The group that fails silently.** A predicate on the wrong column returns rows — just not the
right ones. `fact_join` lets the fact filter directly with no dimension join walked; `scoped_by`
forces the scope column to travel with a code that is only unique within it. (`scoped_by` exists
today as `rulings.scoped_by` — loaded, not yet planned-on.)

### `absence` — what a missing value means, in this column

```yaml
Status:
  role: dimension
  absence:
    nulls: "no status event recorded — NOT 'operating'; read that from CloseDate IS NULL"
```

Per column, because that is where nulls happen. `sentinels` lists non-null values that are not
members — though a sentinel carrying *meaning* is usually a column that should be
[split](column_rulings.md), not flagged.

### `disclose` and `discriminates`

```yaml
age_band_5y: { role: dimension, disclose: "banded to 5 years, as of 2025-12-31" }
Status:      { role: dimension, discriminates: true }
```

`disclose` is one line quoted verbatim into any answer that touches the column — **the only
free-text key here besides `never_axis`, and it exists because it reaches the reader of an answer**,
which prose in a YAML file never does. `discriminates` marks the column that selects which kind of
row this is.

### The five defaults that decide behaviour

A column with only `role:` would behave, under this design, as if:

```yaml
domain:     { closure: open }
resolution: { strategy: [exact, normalized, prefix, fuzzy], fuzzy_floor: 0.80,
              on_miss: ask, candidates: 5 }
absence:    { nulls: unknown }
```

**Open, not closed.** An unstated domain must not be treated as complete — that would refuse real
values. And `on_miss` is derived rather than set:

| closure | complete_for | a word that matches nothing |
|---|---|---|
| `open` | — | **ask** with candidates |
| `closed` | `data` | **zero, disclosed** — real word, no rows |
| `closed` | `world` | **refuse** — not a member of the kind |

That table is the whole reason `complete_for` exists. Without it, *"sales in Asia"* and *"gender
Q"* get the same answer, and only one of them deserves it.

### Validation spike — shapes this specification does NOT yet handle

The block above was designed against **one bundle**. A spike against two further real bundles on
2026-09-25 — called **bundle A** and **bundle B** here, because whose estates they are is not this
manual's to publish; checking whether the shape *crashes*, not whether those bundles could migrate,
since both will be re-authored — found three constellations contoso has no equivalent of. **One of
them the specification cannot express at all.**

#### 1. The measure TYPE is data, not a declaration — bundle A's `kpi`

One concept holds **70 KPIs across six measure types**, served through four conformed views:

```
kpi_code        which KPI this row is
measure_type    Runtime | Reliability | Stock | StockAge | Event | Scheduling
value_seconds   the measure value
```

A `RuntimeMeasure` is a duration between two checkpoints — **averageable, never summed**. A
`StockMeasure` is a count of orders in a state — **additive across dimensions**. Both arrive in the
same column, and which one a row is comes from `measure_type` **on that row**.

**`measure.type` on a column cannot say this.** It declares one type per column; here the type
varies per row.

How bundle A copes today is itself the finding:

```yaml
semantics:
  additivity: { dimensions: non-additive, time: non-additive }
```

**One blanket non-additive over all six**, which is safe and lossy: the `StockMeasure` that *is*
additive across products is refused along with the duration that is not.

Two ways out, and the spike does not choose between them:

* **Split the concept** — one per measure type, which the four conformed views already half-do. Then
  `measure.type` is a declaration again and each gets its true fold rule. This is what "a completely
  new ontology" makes possible.
* **Let the type be read from a column** — `measure: { type_from: measure_type }`. More faithful to
  the data, and it means the fold rule is not knowable until a row is read, which the planner
  currently assumes it is.

#### 2. Several columns of the same kind, and two references to the same concept

Bundle A's `checkpoint_events` carries **five date columns**: `actual_ts` plus four planning
anchors (`eta_1`, `eta_2`, `eta_3`, `eta_4` here — each a different milestone's estimate).

| | |
|---|---|
| expressible | `period: actual_ts`, the four ETAs as dimensions |
| **not expressible** | *"vehicles late against the `eta_3` anchor"* — comparing two dates where neither is *the* period |

And `from_cp` / `to_cp` both reference the same `Checkpoint` concept in **different roles**.
`identity: reference` + `references: Checkpoint` cannot tell them apart. This is
[role_playing_dimension](patterns/role_playing_dimension.md) at the column level, and the block has
no `role_name`.

#### 3. A concept class contoso does not use

Bundle B declares `meta` eight times, alongside `reference`, `enumeration`, `measure`, `entity` and
`grouping`. Nothing in this specification is written with `meta` concepts in mind, and the spike did
not establish what column facts they carry.

#### What the spike does NOT say

- It does **not** say the specification is wrong. Two of the three are expressible with a small
  addition (`role_name`, and splitting or `type_from`).
- It does **not** say bundle A's current shape must be preserved — it will be re-authored.
- It is a **first pass** over two bundles by reading declarations, not a proof. Bundle B was surveyed
  only at the level of concept classes.

#### One thing it does say, about `axis_kinds`

Bundle A populates `semantics.axis_kinds`; contoso populates it **zero** times; the runtime reads it
**zero** times. A field one bundle fills carefully, another ignores entirely, and nothing consumes —
which is the defect this specification exists to stop, found in the field it would have inherited.
