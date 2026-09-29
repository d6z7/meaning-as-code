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

### P7 — A REGISTER IS A VIRTUAL TABLE (operator, 2026-09-29)

> *"it reads like one register is like virtual table. then many rules from the table domain will fit
> for the register lookup. you have authored/invariant column names — i agree on this"*

This is the frame the rest of the policy was groping for, and it settles the open question in §P1–P6
rather than adding to it: **a register's schema is ITS OWN, not borrowed from whatever column it was
cut from.** That single consequence is what makes one register serve many attach points, because a
file headed `CurrencyCode` can only ever belong to the column called `CurrencyCode`.

The estate was already treating registers as tables without saying so — which is exactly why the
schema stayed borrowed. `check_register_membership` compares a register's members against the
warehouse and reports `MISSING / NEW / NULLS / ORPHANED`: that is referential integrity between a
dimension and its source, written as if it were something else.

**Column names become invariant — RULED.**

```
code,label,search_key          every register, every bundle
```

`«code»` in the current declaration is a guillemetted VARIABLE — the source column's name. It
becomes the literal `code`. This is also what the runtime already expects:
`resolver/registers.py::Declaration` binds `code` / `search` / `display_label` by column NAME against
the header, validated on load.

**What else the table domain gives for free**

| table rule | applied to a register |
|---|---|
| a relation has a DESCRIPTOR | `data/lookups/<name>.yaml` — `table:` + `columns:` + grain |
| a relation declares its GRAIN | one row per `code`; `code` is `primary_key`, `key_position: 1` |
| a column declares a REFERENCE | an attach point IS a reference — `sales.CurrencyCode → currency_code.code` |
| references are checked for INTEGRITY | `check_register_membership` over EVERY attach point, not just the one relation it was cut from — a strengthening, see below |
| a relation's name follows a CONVENTION | already declared; the convention's BODY changes (§P5) |
| a page is held to a declared SHAPE | `register_page` exists and is currently governed by nothing |
| a descriptor is held to a SCHEMA | `validate_schema` applies once the descriptor exists |

**Provenance leaves the rows.** `source_view` and `source_schema` are repeated on every row today —
a table storing its own lineage in each row. Under the table model they move to the descriptor as
the ATTACH LIST, which is the thing that became plural. This also fixes a real narrowing:
`check_register_membership` reads `source_view` from the file and checks the register against that
ONE relation. With an attach list it checks every attached column, which is what referential
integrity over a shared dimension actually means.

**What does NOT transfer.** A register has no SQL transform, so no lineage edge from one; it is not
in the warehouse catalog, so it has no schema there and `check_pages_current`-style physical
verification does not apply to its existence; and its `rows_measured` is trivially its member count.
A reference to a register is a reference to a VIRTUAL relation, so it keeps its own field
(`register:`) rather than being folded into `references:` — same rules, different target plane.
Folding them would have the page claim a physical foreign key that the warehouse does not hold.

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

| # | step | risk | status |
|---|---|---|---|
| a | `check_one_register_per_dimension` counts by value set | none — no artifact changes | **done** — 48/25/23 on contoso5, 213/114/99 estate-wide |
| b | operator rules the 1 collision and 5 unsettled names | none | **superseded** — the cutter resolves them mechanically, see below |
| c | declare the bindings that currently resolve through the undeclared path | none — additive | **done for the attach list** — `<stem>.lookup.yaml`, read by `mac_descriptors` and `check_register_membership`; the CSV header itself is untouched, so nothing that resolved through it has moved |
| d | cut by value set into the confirmed names | none — additive | **done** — 48 → 25 |
| e | repoint descriptors; nothing lost | reversible | **done** — 48 attach points over 25 files; value sets 25 → 25, 0 lost, 0 with fewer labels |
| f | delete the 23 redundant files | after (e) is green | **done** — the re-cut produces 25 |
| g | `searchable: like` for the 16, **with its consumer** | new declaration | **done** — `mac_descriptors` → `mac.schema.json` → the relation page prints `search: like` |

**(b) did not need a ruling after all.** The naming question dissolved once the identity moved to the
value set: a notion claimed by exactly one set is usable as a name, and a notion claimed by TWO is
not — every claimant then falls back to its own cut site, which is unique by construction. So
`state` resolves to `contoso5_state` and `contoso5_customer_state` mechanically, with no authored
map and no name that moves when an unrelated relation is added. The one judgement left is cosmetic.

**What (c) still owes.** Renaming the CSV's first header field to the literal `code` — the last of
the seven column names that is not invariant. It is not done and the guardrail says so where the
kind is declared. Four readers take it today (`mac_descriptors`, `check_register_membership`,
`check_registers_reachable`, `check_one_register_per_dimension`) plus the runtime's undeclared path,
and `check_registers_reachable` states that renaming it "breaks a live behaviour with no error".

**Two things the work itself taught, both worth keeping:**

- **A gate found none of the three real defects.** The name collision that silently dropped four
  state codes was found by seeding it deliberately; the lost `AU,Australia` label was found by
  diffing the re-cut bundle against a backup. Gates hold what is already understood — a diff against
  the previous state is what finds what is not.
- **The closed schema earned its keep twice in one hour**, on a kind that had no definition at the
  start of it: it refused `searchable` until the key was declared, then caught the producer writing
  the member LIST where an integer was declared.

**Other bundles are not migrated.** contoso2/3/4 and estate/estate2 still hold 99 redundant copies between
them, and the gate now refuses them. They are cut, not re-cut: the migration needs each bundle's
warehouse, because labels are re-derived at cut time and a connectionless cut would silently flatten
`AU,Australia` to `AU,AU` — the very regression above, estate-wide.

## What I am NOT proposing

- Not renaming any header before (c).
- Not re-cutting anything until the names are ruled — the plan writes nothing on purpose.
- Not touching `store_name`, `middle_initial` or the date-part registers on suitability grounds.
  They pass the rule as written. `middle_initial` (37 one-character members) is useless but not
  wrong, and a rule that removed it would need a criterion I cannot measure offline. Flagged, not
  invented around.
