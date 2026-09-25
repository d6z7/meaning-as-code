---
title: The column specification — everything about a column, on the column
status: PROPOSAL — greenfield. No ontology is in production; nothing here preserves an older shape.
audience: ontology authors, importer developers, console developers
companions: [how_a_question_becomes_sql.md, column_rulings.md, patterns/]
---

# The column specification

## The principle

> **A fact about one column is declared on that column.**
> A fact about the concept, or spanning several columns, stays at concept level.

Nothing else. Every rule below follows from it.

---

## The shape, at a glance

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
          references: <Concept>
          domain:
            closure: closed | open
            complete_for: data | world
            warranty: derived | monitored
            register: <path>
            members: [<code>, ...]
          resolution:
            search: [<register column>, ...]
            display: <register column>
            strategy: [exact, normalized, prefix, fuzzy]
            fuzzy_floor: 0.80
            on_miss: refuse | zero_disclosed | ask
            candidates: <n> | suppress
          placement:
            fact_join: <column>
            scoped_by: <column>
          absence:
            nulls: none | unknown | not_applicable | <meaning>
            sentinels: [<value>, ...]
          rulings:
            label_of: <column>
        register: common | legal | long | short | code
            finer_than: <column>
            never_axis: privacy | grain | derived
            evidence: <dq-id>
          measure:
            type: mac.MeasureType.<term>
            unit: <string>
            additivity: { time: ..., categorical: ... }
          disclose: <one line>
          discriminates: true
```

**Columns nest under the source they belong to**, because a column name only means anything within
a relation. `Country` proves why: the concept binds two relations, and the same identity is spelled
`Country` on the customer dimension and `CountryCode` on the store dimension. A flat block could
not say that.

**Only `role` is required.** The common case is one line:

```yaml
sources:
  - relation: dim_contoso_customer
    columns:
      Gender: { role: dimension }
```

---

## The eight sections

### `role` — where a query may use the column at all

```yaml
Gender: { role: dimension }
```

The only required key. Five values, all **derivable** from the data, which is the test a role has
to pass — a generator assigns them over a thousand columns with no human present. Detail:
[column_roles.md](column_roles.md).

### `identity` — which column IS the thing

```yaml
CustomerKey: { role: key, identity: canonical }
GeoAreaKey:  { role: key, identity: reference, references: Region }
OrderKey:    { role: key, identity: part }
RowNumber:   { role: key, identity: part }
```

Three values, defined in `mac.identity_role`: **`canonical`** is the one column that identifies an
instance — what `COUNT(DISTINCT)` counts; **`part`** is one column of a composite identity and
**identifies nothing alone**; **`reference`** points at another concept's identity.

**This is narrower than `mac.identity_kind`, and deliberately.** That vocabulary is per **concept**
and says how identity is *established* — `iso`, `code`, `namespace_code`, `fk_name`, `composite`,
`resolved_axis`, `sme_pending`. It stays on `concept.identity.kind`. The concept says *"identity is
a composite"*; these say *which columns compose it*.

> An earlier draft of this page had a fourth value, `natural`. It was a category error: a natural
> key is a claim about the **kind** of identity, which is `mac.identity_kind.code` or `fk_name` on
> the concept, not a statement about one column's part in it.

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
forces the scope column to travel with a code that is only unique within it.

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

### `rulings` — judgements measurement cannot make

```yaml
ZipCode:
  role: dimension
  rulings: { never_axis: privacy, evidence: DQ-CUSTOMER-02 }
```

Four of them, each with its own constellation and worked example in
[column_rulings.md](column_rulings.md). `evidence` is **required** with `never_axis`: a prohibition
without a measurement is a preference.

### `measure` — which folds are legal

```yaml
NetPrice:
  role: measure
  measure: { type: mac.MeasureType.additive, unit: USD }
```

Only on `role: measure`. `additivity` overrides the type for one named axis — a balance that sums
across products and not across time.

### `disclose` and `discriminates`

```yaml
age_band_5y: { role: dimension, disclose: "banded to 5 years, as of 2025-12-31" }
Status:      { role: dimension, discriminates: true }
```

`disclose` is one line quoted verbatim into any answer that touches the column — **the only
free-text key here, and it exists because it reaches the reader of an answer**, which prose in a
YAML file never does. `discriminates` marks the column that selects which kind of row this is.

---

## Every key

| key | required | default | legal values | decides |
|---|---|---|---|---|
| `role` | **yes** | — | `mac.column_role.*` | where a query may use the column at all |
| `identity` | role: key | `reference` | `mac.identity_role.*` | what part this column plays in the concept's identity — see `mac.identity_role` for the three meanings, and `concept.identity.kind` (`mac.identity_kind.*`) for how identity is **established** |
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
| `placement.scoped_by` | no | — | a column | the scope column must travel with this code |
| `absence.nulls` | no | `unknown` | `none` · `unknown` · `not_applicable` · free text | what NULL **in this column** means |
| `absence.sentinels` | no | — | values | non-null values that are not members |
| `rulings.label_of` | no | — | a column | this column NAMES that one; group there, display here |
| `rulings.register` | with label_of | `common` | `mac.name_register.*` | which of the thing's names this is |
| `rulings.finer_than` | no | — | a column | this column rolls up into that one |
| `rulings.never_axis` | no | — | `privacy` · `grain` · `derived` | may not be grouped on |
| `rulings.evidence` | **with never_axis** | — | a DQ id | the measurement. Without it, a prohibition is a preference. |
| `measure.type` | role: measure | — | `mac.MeasureType.*` | which folds are legal |
| `measure.unit` | no | — | free text | what the number is in |
| `measure.additivity` | no | from `measure.type` | per-axis | overrides the type for a named axis |
| `disclose` | no | — | one line | text quoted into any answer that touches this column |
| `discriminates` | no | `false` | boolean | this column selects which kind of row |

---

## Worked: `Customer`, all 13 columns

`identity.kind: fk_name` · `canonical_key: CustomerKey` · one source.

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
          references: Region

        Continent:
          role: dimension

        Country:
          role: dimension

        CountryFull:
          role: dimension
          rulings: { label_of: Country, register: long }

        State:
          role: dimension
          placement: { scoped_by: Country }

        StateFull:
          role: dimension
          rulings: { label_of: State, register: long }

        Gender:
          role: dimension
          domain:
            closure: closed
            complete_for: world
            warranty: monitored
            register: data/lookups/contoso_gender.lookup.csv
          absence: { nulls: none }

        age_band_5y:
          role: dimension
          domain:
            closure: closed
            complete_for: world
            warranty: derived
            members: [20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90]
          disclose: "banded to 5 years, as of 2025-12-31"

        City:
          role: dimension
          rulings: { never_axis: privacy, evidence: DQ-CUSTOMER-02 }

        ZipCode:
          role: dimension
          rulings: { never_axis: privacy, evidence: DQ-CUSTOMER-02 }

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

`identity.kind: iso` · `canonical_key: Country` · **two sources**, and the same identity spelled
differently on each.

```yaml
grounding:
  sources:
    - relation: dim_contoso_customer
      key: CustomerKey
      columns:
        Country:
          role: key
          identity: canonical
          domain:
            closure: closed
            complete_for: data
            warranty: monitored
            register: data/lookups/contoso_country.lookup.csv
          resolution:
            search:  [search_key, Country]
            display: label
          placement:
            fact_join: Country
          absence: { nulls: none }
          disclose: >-
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
          absence:
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

## Why there is no `note` field

**A free-text key on a column is where rulings go to hide.** Measured on contoso 2026-09-25:
`grounding.note` carries ruling language — *never*, *must not*, *display-only*, *because* — in
**12 of 21 concepts**. The clearest is `customer.yaml`, whose 1 044-character note read:

> *"`ZipCode` and `City` are display-only, never filter or group — because DQ-CUSTOMER-02 measured
> that ZipCode alone singles out 29 193 of 104 990 served rows."*

A measured privacy ruling, stated in prose, in a field nothing reads — while the runtime happily
planned `GROUP BY ZipCode`. It became `never_axis: privacy` + `evidence: DQ-CUSTOMER-02`, and the
refusal now cites the measurement.

That is the whole failure mode of this estate in one field, and it is not unique: `contract.resolution`
is 13 careful paragraphs nothing reads, `null_semantics` is declared on 20 concepts and read by
none. **A block designed to end that must not ship with a slot that restarts it.**

So: **the column block has no free-text key.** If you want to write something about a column:

| what you want to say | where it goes |
|---|---|
| it changes what the engine does | a **declaration** — find the key, or the key is missing and that is the finding |
| the reader of an ANSWER must know it | `disclose:` — it reaches them, which prose never does |
| why a ruling was made | `evidence:` — a measurement id, not a paragraph |
| it is unresolved | `open_questions` — with an id, an owner and a status |
| it is about the concept, not this column | `concept.definition` |

**The worked case.** An earlier draft of this document wrote:

```yaml
CountryCode:
  role: dimension
  note: the store side's spelling of the same geography
```

**That third line is wrong.** It is a claim that two columns in two relations hold the same
geography — an **edge between concepts**, undeclared, hiding in prose.

That sentence is a claim that two columns in two relations hold the same geography. It is not a
reader's aside — it is an **edge between concepts**, undeclared, hiding in prose. The note did not
describe the model; it substituted for a missing part of it.

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

`domain.closure` says *whether the list is complete*. It never restates the list.

---

## The five defaults that decide behaviour

A column with only `role:` behaves as if:

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
