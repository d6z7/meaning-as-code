---
state: proposed
genre: proposal
---
# PROPOSED — 2026-10-05 · the tests that hold what `brand.exclusion.is_not_manufacturer` claimed

> **Paths in this document.** `acceptance/…`, `ontology/…` and `data/…` are inside the bundle
> (`cap-ontology-sources/example/contoso5`); `tools/…` and `decisions/…` are in `meaning-as-code`;
> `planner/…` and `resolver/…` are under
> `mac-platform/packages/mac-runtime/src/mac_runtime/`. A `:line` suffix is where a measurement was read.

## Why a test and not a rule

`brand.exclusion.is_not_manufacturer` says: *"when a question asks who is behind a product, decide
whether it means the brand the customer buys or the manufacturer, and say which; never treat the two
columns as interchangeable because their member sets overlap."*

Measured 2026-10-05, nothing reads it. `when:` and `then:` appear **zero** times in the runtime —
`interpret/prompt.py` carries only `never:` to the model, and no planner module reads either. So the rule
is a sentence a model may see, and the behaviour it describes is asserted by nothing.

Meanwhile the ontology declares the **opposite**, and that declaration DOES run.
`ontology/concepts/product.yaml:30` gives the manufacturer column
`rulings: {label_of: brand, register: legal}`, and `planner/sql.py:1288-1300` acts on it: it groups on
`brand`, SELECTs `manufacturer`, and appends a disclosure naming the `legal` register. The framework's
own source comment at that line uses this very pair as its worked example — *"`SELECT Manufacturer …
GROUP BY Brand` is not SQL. The row count equals GROUP BY Brand exactly when the ruling's 1:1 holds;
when it does not, the extra rows are VISIBLE, which is the honest failure mode."*

And the data says the 1:1 holds. The two registers, paired:

| brand | manufacturer | differs by |
|---|---|---|
| A. Datum | A. Datum Corporation | `+ Corporation` |
| Contoso | Contoso, Ltd | `+, Ltd` |
| Fabrikam | Fabrikam, Inc. | `+, Inc.` |
| Litware | Litware, Inc. | `+, Inc.` |
| Proseware | Proseware, Inc. | `+, Inc.` |
| Adventure Works · Northwind Traders · Southridge Video · Tailspin Toys · The Phone Company · Wide World Importers | identical | — |

**11 brands, 11 manufacturers, 6 byte-identical, 5 differing only by a corporate suffix, 0 with a
different stem.** Manufacturer is the registered name of the same eleven companies.

So the question is not "which rule wins". It is: **what must be true for `label_of` to be right, and
what does a reader see when it is?** Those are testable. A rule restating either answer is not.

### The coverage, in three numbers

* **10 brand questions in `acceptance/questions.yaml`, 0 manufacturer questions.** The corpus has never
  asked what this rule governs.
* **83 oracles: 81 `COMMIT`, 2 `REFUSE`, 0 `ASK`.** `mac.concept.rule.ambiguity` is defined as *"an
  underspecified REQUIRED dimension — ASK, never guess"*, and no oracle in the bundle asserts an ASK.
* **5 rules of kind `ambiguity`, 0 carrying a canon body.** Every one is prose.

### The constraint every test below obeys

`acceptance/oracle/RC01.yaml` states its own authority limit: *"NO EXPECTED VALUE IS ASSERTED and none
may be added here: this bundle has no second source of truth for what a measure means, so a value
written from the ontology would test the planner against the ontology and not against the world."*

That rules out "manufacturer X sold N". So every behavioural test below is an **EQUIVALENCE between two
questions**, which needs no external truth: if manufacturer is a label of brand, the two questions are
the same question, and the engine must say so. That is the strongest assertion available here, and it is
available precisely because the claim under test is an identity.

## The six tests

### T1 — the bijection `label_of` silently depends on · DATA · **the one that must never be skipped**

**Asserts** over `dim_product`: every `brand` has exactly one distinct `manufacturer`, and every
`manufacturer` exactly one distinct `brand`.

**Why it is first.** `planner/sql.py:1292-1296` groups on `brand` and shows `manufacturer`. If one brand
ever carries two manufacturers, the GROUP BY produces more rows than there are brands, and the engine's
own comment calls that "the honest failure mode" because the extra rows are *visible* — but visible to
a reader is not asserted by a test, and nobody reads 11 rows to check there are 11.

**Where it lands.** `acceptance/data_sanity_generated.yaml`, the plane that already holds warehouse
invariants, so it runs on every rebuild rather than only when somebody asks a question.

**Expected today: GREEN** (11/11, measured above, at the register level — T1 asserts it at the
warehouse level, which is the population the planner actually groups).

**If it ever goes red**, the retirement of this rule was wrong and a choice between the two columns is
real. T1 is therefore the falsifier for the whole position, and it is cheap.

### T2 — "by manufacturer" and "by brand" are the same question · BEHAVIOUR · the falsifier

**Asserts** that `Break down net revenue by manufacturer` returns the same number of rows and the same
figures as the corpus's existing `Break down net revenue by brand` (`cap-ontology-sources/example/contoso5/acceptance/questions.yaml:132`), differing
only in the label column's text.

**Why.** This is the entire formal content of `label_of: brand`. If the two disagree, `label_of` is a
false declaration and rule 2 was right to forbid interchange — in which case the fix is to remove
`label_of` from `product.yaml`, not to re-add a prose rule.

**Expected today: UNKNOWN, and that is the point of running it.** I have not executed the pair. The
declaration says they must agree; whether the engine makes them agree is exactly what is unmeasured.

### T3 — a question by legal name must resolve · BEHAVIOUR · **expected RED**

**Asserts** that `What is the net revenue for Contoso, Ltd?` equals the corpus's existing
`What is the net revenue for the Contoso brand?` (`cap-ontology-sources/example/contoso5/acceptance/questions.yaml:149`).

**Why it will fail, measured.** Of 17 registers on disk under `data/lookups/`, **5 are bound by a
declaration that loads**; `cap-ontology-sources/example/contoso5/data/lookups/contoso5_manufacturer.lookup.yaml` is one of the 12 that are not. The
`register: legal` on the manufacturer column is `ColumnRulings.naming_register` — *"register says WHICH
of a thing's names this label is"* (`ontology/models.py:277`) — a naming TIER, not a pointer to an
artifact. So the eleven legal names exist as a file and resolve through nothing.

**This is the real gap the rule was gesturing at.** A reader who says "Contoso, Ltd" is naming something
the warehouse holds, and the bundle cannot currently reach it. The prose rule did not help: it told the
model not to confuse the columns, which is not the same as letting a question use either name.

**The fix the test forces is a design choice, so the test comes first.** Binding the manufacturer
register as `enum_from_register` would declare a SECOND closed value set over the same eleven members —
the two-homes defect again. The shapes that fit are `resolve_by_register` (a spoken name resolving to the
code that stands for it) or `alias_resolve` (a surface token through naming tiers, `>1 hit or unknown ->
ASK`). Which one, and whether it belongs on Product or Brand, is owed — and is a far smaller question
once the test says what is broken.

### T4 — the disclosure must reach the reader · BEHAVIOUR

**Asserts** that an answer grouped by manufacturer carries the disclosure `planner/sql.py:1297-1301`
builds — *"grouped by Product.brand, shown as manufacturer (legal register): the bundle rules
`label_of`"* — in what the reader sees, not only in a plan structure.

**Why.** This is the platform's standing granularity rule: answer the whole range and DISCLOSE the
narrower reading, never narrow silently. The engine composes the sentence; nothing asserts it arrives.

**Expected today: UNKNOWN.** `ruling_disclosures` is built in the SQL layer; whether it reaches the
rendered answer is unmeasured.

### T5 — the genuinely ambiguous question · **needs your ruling, and I will not derive it**

**The question**: `Who is behind the Adventure Works products?`

Two defensible oracles, and the difference is a decision about the product, not a fact about the data:

| | oracle | the argument |
|---|---|---|
| **A** | `expected_outcome: COMMIT` | with a 1:1 and the same stems, both readings name the same company; asking the reader to choose between "Contoso" and "Contoso, Ltd" is a clarification with no consequence, and the resolution ladder exists to avoid exactly that |
| **B** | `expected_outcome: ASK`, offering both readings | "behind" is not a declared surface of either column; `column_select`'s rule is that no default IS a declaration — a question naming neither reading asks with both offered |

**Whichever you rule, this is the bundle's first `ASK`-or-deliberate-`COMMIT` oracle on an ambiguity**,
and it sets the pattern for the other four unbound ambiguity rules. **If B**, the rule should come back —
on Product, as `kind: ambiguity`, with a `column_select` body and no `default:`, which is the notation I
drafted before the data disproved its premise; the surfaces would be the narrow ones only, and "behind"
deliberately absent from both so it falls through to the ASK. **If A**, nothing comes back and T2/T3 are
the whole coverage.

### T6 — two instrument defects the above uncovered · GATE

**(a) `REGISTER-ORPHAN` fails 17 of 17 and means nothing.** `check_delivery_consistency.py` records
`enumerated 17, examined 17, held 0, failed 17, verdict FAIL`, with one violation per register reading
*"pointed at by no descriptor column, so nothing can resolve a code through it"* — including
`cap-ontology-sources/example/contoso5/data/lookups/contoso5_brand.lookup.csv`, which demonstrably loads 11 members through
`ontology/concepts/brand.yaml`'s `columns.brand.register`. A 100 % failure rate is an instrument looking
in the wrong place: the invariant wants a DESCRIPTOR column pointer, and the column standard (>= 0.1.14)
puts the pointer on the CONCEPT's column. **I nearly cited this as evidence that the manufacturer
register is orphaned; it is not evidence of anything until it is fixed.** Point it at the concept column
and it reports 12, which is a real number and the same one T3 rests on.

**(b) Nothing gates "a register on disk that no declaration loads" — 12 of 17.**
`check_register_membership.py:94` defines `orphaned` in the opposite direction, *"register(s) point at
something the warehouse does not have"*, and the manufacturer register passes it: its `source_view`
exists. Both directions are real and only one is checked. A register nobody loads is 11 authored names a
reader cannot use, which is precisely T3.

## Sequencing

| | | lands in | blocked on |
|---|---|---|---|
| 1 | **T1** | `acceptance/data_sanity_generated.yaml` | nothing — write it first, it is the safety net under the retirement |
| 2 | **T6a** | `tools/check_delivery_consistency.py` | nothing — a broken instrument first, so T3 is measured and not argued |
| 3 | **T6b** | a new invariant beside T6a | T6a |
| 4 | **T2**, **T3**, **T4** | `acceptance/questions.yaml` + `acceptance/oracle/` | nothing; T3 is expected red and should be DECLARED in `acceptance/standing_failures.yaml` with an owner, not left as news |
| 5 | **T5** | same | **your ruling, A or B** |
| 6 | the `resolve_by_register` / `alias_resolve` binding | `cap-ontology-sources/example/contoso5/ontology/concepts/product.yaml` or `.../brand.yaml` | T3 red, then your ruling on which canon and which concept |

T1 and T6 need no decision from you and are where I would start. T5 is the only item that cannot be
derived from the data, and it is the one that decides whether a rule comes back at all.

## What this proposal does not claim

* **It does not re-add a rule.** `brand.exclusion.is_not_manufacturer` is still prose nothing reads, and
  still contradicts a running declaration. These tests pin the behaviour; whether a rule returns depends
  entirely on T5.
* **It asserts no value.** Every behavioural test is an equivalence between two questions, for the
  authority reason the oracles state themselves.
* **It does not touch the retirement already made.** `brand.resolution.by_grouping_products` was retired
  in `cap-ontology-sources` `1f42457` with `check_plan_replay` 0 gained over 58 — no plan changed. T1 is
  the test that keeps that safe.
