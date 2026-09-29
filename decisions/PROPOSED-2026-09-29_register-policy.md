# PROPOSED 2026-09-29 — a register is a VALUE SET, and not everything is a register

Operator, 2026-09-29: *"they all show the same thing! lookup policy must be changed in way that
there only one lookup for one thing that can be attached to multiple targets. and another thing is
that not everyting is suitable for lookup. one huge table where the search criteria is text cannot
be converted into lookup. it should just be declared later to be searchebal with like."*

Measured on contoso5 before anything was proposed: **48 register files holding 25 distinct value
sets** — 23 redundant copies, 47 %. The five currency codes are stored eight times.

---

## 1. What is actually wrong

Not the cutter's care. Three separate mechanisms, each individually reasonable:

**(a) The identity is the source column.** `mac_lookups` keys `seen_columns` on `(relation,
column)`, so one value set carried by eight columns becomes eight files.

**(b) The gate cannot see it.** `check_one_register_per_dimension.py` reports over those 48:

```
registers: 48   distinct domains: 48   DUPLICATED: 0
OK — every (source_view, column) has at most one register.
```

It calls a `(source_view, column)` pair a *domain*. DNA P4's **title** rules "one register per
DIMENSION"; P4's **body** rules "refuse to write where a register already covers that source
column". The cutter and the checker both implement the body. Every layer is self-consistent and
none does what the title says, which is how 47 % duplication passed a wired gate.

**(c) A misread gate cut more.** `check_registers_reachable.py` records it: *"Reading that false
sentence is what caused the duplicate-register episode: '9 of 17 orphaned' was believed to mean
unusable, and fifteen new registers were cut to replace files that already worked."*

## 2. Both alternative names have already failed here

`mac_lookups._stem` is the record. The name was `{marker}_{column}` — two relations carrying a
same-named column collided on one filename and the second cut **silently overwrote** the first:
contoso4's `customer.State`, 565 members, pointing at a 67-member register cut from `store`. That
was fixed by qualifying every name with its relation, which is exactly what produces today's
duplication.

> Notion-naming collides. Column-naming duplicates. **Neither is the identity.**

contoso5 reproduces the same pair independently: `state` is **67 names** (`Alaska`, `Arkansas`) on
`dim_location` and **565 codes** (`AK`, `AL`) on `customer`. Genuinely two registers under one
notion — not a filename to disambiguate.

---

## THE PROPOSAL

### P1 — A register IS a value set

One file per distinct set of members. Two columns holding the same members share one register
however they are spelled; two columns holding different members never share one however alike they
are named. This is the whole change; everything below follows from it.

contoso5: **48 files → 28 registers over 56 attach points**, computed by
`tools/mac_register_plan.py` (read-only).

### P2 — Attachment is already many-to-one; only the cutter prevents it

Descriptor columns already carry `register: data/lookups/<name>.lookup.csv`. Eight columns can point
at one file today with no change to the descriptor schema, the projector, or the page. **No new
mechanism is needed for the operator's "attached to multiple targets" — only the removal of the
per-column key.**

### P3 — Suitability: three clauses, and not the obvious one

```
REGISTER   it is the target of a declared reference      (a shared dimension key)
        or <= 100 members                                (a person can name them all)
        or <= 5 % of its rows AND <= 1000 members        (a vocabulary, repeated)

searchable: like   anything else                         (open text)
```

The obvious rule — `distinct/rows` — is **killed** by the most canonical register in the bundle:
`dim_currency.currency_code` is 5 values over 5 rows, ratio 1.0, because a dimension table IS its
own register. The reference clause is load-bearing only above the small-set line.

contoso5: 72 candidates → 56 registers, **16 open-text columns** — `customer_name` 99 200 of
104 990 rows, `StreetAddress` 95 854, `ProductName` 2 517 of 2 517. **None of those 16 is a register
today**, so naming them is not a regression; it covers what is currently unhandled.

### P4 — `searchable: like` is a DECLARATION, and it needs a consumer

It exists nowhere in the vocabulary or the guardrails today. Declaring it and stopping is this
estate's recurring failure — see `the-runtime-ignores-its-own-declarations`. It is only worth adding
together with the thing that reads it.

### P5 — The name is authored once, and collisions are refused

Every derivable name depends on what else the bundle holds — add a relation and an alphabetical
winner changes, which is the instability `_stem` warns about. So: the plan **proposes**, a person
**confirms**, the confirmed name never moves. `lifecycle: authored-once`.

Two different value sets proposing one name is **REFUSED** with both member samples, never silently
qualified — qualifying is what produced the duplication. contoso5 has one such collision (`state`)
and five unsettled names (`store_name`, `month`, `status`, `dayof_week`, …).

### P6 — Fix the gate's denominator FIRST

`check_one_register_per_dimension.py` counts distinct **value sets**, not `(source_view, column)`
pairs. This costs one function, changes no artifact, and turns today's silent `OK` into a refusal of
23 files. **It is the only step that is safe in isolation, so it goes first.**

---

## The one real risk, and why it sets the order

A register's header today names its source column (`CurrencyCode`, `currency_code`, …). A shared
register cannot, so the header wants to become stable — `code,label,search_key`. That is **what the
runtime already expects**: `resolver/registers.py::Declaration` binds `code` / `search` /
`display_label` by column NAME against the register's header, validated on load.

But there is also a **live undeclared path**, and `check_registers_reachable.py` names it:

> *"the register's first header field matches a column of some concept, and the loader attributes it
> there … Renaming its first column, or the file, breaks a live behaviour with no error."*

So the header must not be renamed on its own. Sequence:

| # | step | risk |
|---|---|---|
| a | `check_one_register_per_dimension` counts by value set | none — no artifact changes |
| b | operator rules the 1 collision and 5 unsettled names | none |
| c | declare the bindings that currently resolve through the undeclared path | none — additive |
| d | cut by value set into the confirmed names, **old files kept** | none — additive |
| e | repoint descriptors; `check_registers_reachable` must show nothing lost | reversible |
| f | delete the 23 redundant files | after (e) is green |
| g | `searchable: like` for the 16, **with its consumer** | new declaration |

Steps (a)–(b) are cheap and I would do them next. (c) is the one that must not be skipped: it is the
same defect as `renames-break-readers-silently`, and skipping it breaks resolution with no error.

## What I am NOT proposing

- Not renaming any header before (c).
- Not re-cutting anything until the names are ruled — the plan writes nothing on purpose.
- Not touching `store_name`, `middle_initial` or the date-part registers on suitability grounds.
  They pass the rule as written. `middle_initial` (37 one-character members) is useless but not
  wrong, and a rule that removed it would need a criterion I cannot measure offline. Flagged, not
  invented around.
