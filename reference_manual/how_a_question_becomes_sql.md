---
title: How a question becomes SQL — read this first
status: the trace is real; every number was measured 2026-09-25 on the contoso bundle, which lives in a
  separate repository (mac-ontology-contoso) and runs on mac-platform's runtime — not reproducible from this repo alone
audience: anyone who wants to change what the ontology does
paths: bundle-relative (the contoso bundle) unless prefixed
---

# How a question becomes SQL

One question, traced end to end. At each step: **which declaration decided it**, and **what
actually happened when that declaration was missing** — every failure below was observed on this
bundle this week, not invented.

Read this before the reference tables. The tables list the switches; this shows the machine they
are switches *on*.

---

## The question

```
How many female customers are in Europe?
```

## The answer

```sql
SELECT COUNT(DISTINCT dim_contoso_customer.CustomerKey) AS customer
FROM   contoso_served.dim_contoso_customer
WHERE  dim_contoso_customer.Gender  = 'female'
  AND  dim_contoso_customer.Country IN ('DE','FR','GB','IT','NL')
```

```
19 564
```

Between those two things are **six decisions**, each made by a declaration a person wrote.

---

## Step 1 — which concept does "female" belong to?

The model is shown a vocabulary. For it to place the word, the vocabulary must contain the word.

**And the ontology never says which file supplies it. The runtime works it out.**

The register carries two clues about where it belongs:

```
data/lookups/contoso_gender.lookup.csv

Gender,label,search_key,source_view,confidence,note
female,female,female,dim_contoso_customer,I,"served customers with this value: 51927"
^^^^^^                ^^^^^^^^^^^^^^^^^^^^
first column          the relation the values were cut from
```

The loader reads both and asks **one question with two conditions**:

> Which concept is grounded on `dim_contoso_customer` **and** declares a column called `Gender`?

`Customer`. The two rows attach there, carrying `column='Gender'`.

Both conditions are required, and deliberately: several concepts share a relation, and a column
name can repeat across relations — so either clue alone would be a guess. If more than one concept
still matches, the tie-break is the **filename**: the concept whose name the file names wins.

| measured | |
|---|---|
| registers **declared** by the `Customer` concept | **NONE** |
| how the link is made | inferred from the CSV's first column + `source_view` |
| where the file is mentioned in the ontology | only inside a `no_probe_guarantee` **prose** paragraph |

### What this costs

| change | consequence |
|---|---|
| rename the CSV's first column | no concept matches → the file becomes a reported `SkippedRegister`. **Caught, with a reason.** |
| a second concept declares `Gender` on the same relation | ambiguous; resolved by the filename tie-break, which may pick the wrong one |
| rename the file | does **not** break the link — but can silently **re-point** it, if the new name matches a competing candidate |

So the mechanism is careful, and the residual risk is not "it breaks silently" — it is that
**nothing in the ontology tells you the link exists.** Reading `customer.yaml`, nothing says that
`contoso_gender.lookup.csv` is what makes *"female customers"* answerable. You have to know the
loader infers it.

> **And before any of that, the values were not in the prompt at all.** The model saw concept names
> and no values, had to guess which concept owned a word it had never been shown, and routed
> `Female` to **AgeBand** — whose members are 20, 25 … 90. The question refused.
>
> The fix was not a better prompt. It was **rendering the register's values into it**: 190 rows
> across fifteen registers, about 2 kB against a 49 kB prompt.

### What the specification changes

A register **on the column** turns an inference into a statement — `value_register` is the live
key for it, and the designed `domain` block adds only whether the list is complete:

```yaml
gender:
  offers: {axis: categorical}
  value_register: data/lookups/contoso5_gender.lookup.yaml   # the live key
  domain:                                                    # DESIGNED — a load error today
    closure: closed
```

Now the link is readable where the column is, and renaming either side is a **load error** instead
of a re-point or a skip a reader has to go looking for.

## Step 2 — which *value* does "female" resolve to?

The word a person types is not the value the warehouse stores. A register maps one to the other,
through a ladder.

| decided by | the register's `search` column, and the resolution ladder |
|---|---|
| **the ladder** | exact → normalized → prefix → fuzzy → **ask with candidates** |
| **what it produces** | `female` (exact) · `Female` (normalized) · `FeMaLe` (normalized) → all one value |

> **When the last rung was unreachable.** The ladder only *asked* when two candidates tied, so a
> lone fuzzy match bound silently: `Asia` matched `Australia` at ratio 0.62 and **bound it**. A
> question about Asia was one step from being answered with Australian numbers.
>
> Now a lone guess asks. `Germny` → *"did you mean Germany?"*. Case folding still binds silently,
> because `FeMaLe` **is** `female` and asking would be pedantry.

**Switch:** the ladder is currently hardcoded, not declarable per column. That is a gap.

---

## Step 3 — which *column* does that value live in?

This is the step everyone forgets, and the one that fails silently.

| decided by | the source column the register was cut from — the CSV's **first header field** |
|---|---|
| **what it produces** | `female` → column `Gender` |

> **When it was missing.** The entry knew which **concept** owned the word and not which **column**
> held it, so the planner fell back to the concept's identity column and emitted:
>
> ```sql
> WHERE dim_customer.customer_key = 'female'
> ```
>
> DuckDB refused to cast `'female'` to INT32, which is the *lucky* outcome. **On a varchar key the
> same plan returns zero rows and reads as an answer.**

**Switch:** `grounding.source.columns.<C>` — and note this one is *implemented but declared nowhere*: the
runtime assumes the CSV's first field is the source column, and no schema says so.

---

## Step 4 — "Europe" is not a column value. What is it?

`Europe` is a continent. The customer row carries a `Continent` column **and** a `Country` column,
and the register holds the map between them.

**This step, unlike Step 1, is declared** — and here is the whole declaration, verbatim from
`ontology/concepts/geography/continent.yaml`:

```yaml
contract:
  rules:
    - id: continent.resolution.by_register        # contract.rules[1]
      kind: mac.concept.rule.resolution
      when:  "a question names a continent"
      then:  resolve through the register's `continent` column to the member country codes …
      never: resolving a continent on the STORE side — that relation has no continent column …
      binds: [Continent, Country]
      realized_by:
        udf: mac.canon.resolve_by_register
        params:
          thing:         continent
          code:          Country
          register:      data/lookups/contoso_country.lookup.csv
          search:        continent
          display_label: label
```

What the loader made of it, measured:

```
status = loaded   rule = continent.resolution.by_register
register = data/lookups/contoso_country.lookup.csv
search = ('continent',)   display = ('label',)   fact_join = None
```

| | |
|---|---|
| **what it produces** | `Europe` → `('DE','FR','GB','IT','NL')` — **every** code the name covers, never one of them |

Two routes were legal and both give 19 564:

| route | SQL | why this one |
|---|---|---|
| **roll-up** *(chosen, because `code: Country`)* | `Country IN ('DE','FR','GB','IT','NL')` | the answer can **name what it counted** |
| direct | `Continent = 'Europe'` | shorter, and opaque |

### Declared here, inferred in Step 1 — and that is the lesson

| | Step 1 · `female` | Step 4 · `Europe` |
|---|---|---|
| how the register is found | **inferred** from the CSV's first column + `source_view` | **declared** at `contract.rules[1].realized_by.params.register` |
| where you read it | nowhere — you must know the loader's rule | in the concept, next to the rule that uses it |
| what a rename does | re-points, or skips | **load error** |
| what the gate says | `UNDECLARED but resolving` | `declared` |

Both work. Only one can be read.

> **And this step refused for weeks.** The concept declared its register under
> `mac.canon.grouping_from_register` — a canon **the runtime has never implemented**. One of six
> such bindings in this bundle: valid YAML, passing every gate, doing nothing. `Continent='Europe'`
> refused a value `SELECT DISTINCT` returns.
>
> Worse: reading that refusal, an agent concluded the **registers** were missing and cut fifteen
> new ones. Thirteen duplicated files that already existed, each worse than the original. The rule
> above — `resolve_by_register`, which the runtime *does* implement — replaced it and the question
> answered.

**Switches:** which canon, and whether the runtime implements it → `mac.canon.*`,
`check_canon_implemented.py`. On the column standard the register itself is already there, as
`value_register`; what is still designed is `resolution.search` + `resolution.display`, which say
which of its columns a word is matched and printed from.

## Step 5 — what is being counted?

"How many customers" needs to know what **one customer** is.

| decided by | `key: customer_key` on the **source** — one column, so it is the canonical identity |
|---|---|
| **what it produces** | `COUNT(DISTINCT customer_key)`, and a disclosure naming the key it counted |

Where the relation is served FINER than the thing, `counts:` on the source names the column a count
DISTINCTs instead: `dim_store` is keyed on `store_key` over 74 trading periods and declares
`counts: location_code`, so a count of stores answers 67 and says which column it counted.

Without it the question is not wrong — it is **unanswerable**, because nothing declares which
column identifies one instance. The dimension over-covers the fact here (52 189 of 104 990
customers ever appear on an order), so "customers" and "buyers" are different questions and the
ontology says so rather than picking one.

---

## Step 6 — what must the answer say?

The SQL is not the answer. What travels with it:

| decided by | carried |
|---|---|
| `constraints[].assert` | *"Country determines Continent — the roll-up is a function, measured 0 of 8 countries on two continents"* |
| `contract.rules[].why` | why a store-side continent figure is refused |
| the source's `key` | *"counted by customer_key"* — or the column `counts:` names, where the two differ |
| `metadata.confidence` | reduced to the minimum over everything touched |

---

## The chain, and where each group of switches plugs in

```
   "How many female customers are in Europe?"
                │
   ┌────────────▼──────────────┐
   │ 1  Is the word in the     │   A · VISIBILITY   — is the column declared at all?
   │    vocabulary?            │   C · RESOLUTION   — is a register bound?
   ├───────────────────────────┤
   │ 2  Which value?           │   C · RESOLUTION   — search column, the ladder
   ├───────────────────────────┤
   │ 3  Which column?          │   D · PLACEMENT    — the source column ← silent failures live here
   ├───────────────────────────┤
   │ 4  Which codes?           │   C · RESOLUTION   — canon, roll-up, scope
   ├───────────────────────────┤
   │ 5  What is counted?       │   B · CAPABILITY   — the source's key, offers, additivity
   ├───────────────────────────┤
   │ 6  What is disclosed?     │   F · DISCLOSURE   — caveats, defaults, confidence
   └───────────────────────────┘
                │
            the SQL, and 19 564
```

`E · ABSENCE` does not appear in this trace because nothing was missing. It is the group that
decides what happens when a word is real and the rows are not — *"sales in Asia"*, where the
honest answer is **zero, and no customer in this delivery is in Asia**, and the ontology currently
cannot say it.

---

## What to read next

| you want to | read |
|---|---|
| declare everything about a column, in one place | [column_specification.md](column_specification.md) |
| decide what a column offers | [column_roles.md](column_roles.md) |
| declare something measurement cannot establish | [column_rulings.md](column_rulings.md) |
| recognise a shape you have been handed | [patterns/](patterns/) — 22 constellations |
