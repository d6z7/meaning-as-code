---
title: "Canon — ratio_select"
part_of: reference_manual/canon
status: reference   # implemented in mac-runtime/canons/ratio_select.py; the decision only, not the rendering
scope: GENERIC — domain-neutral. Measurements from example/contoso5.
---

# Canon — `ratio_select`

> A **pure** canon and the twin of [`population_select`](population_select.md): that one maps a word
> a reader says to the **rows** a concept has, this one to the **figure** a ratio divides by. Given a
> concept's declared ratios and what the question said, it selects which named reading applies — or
> states that the question named none and the caller must ask. It decides; it does not render.
> Building the division is the planner's job.

## Serves

[`competing_definitions`](../../patterns/competing_definitions.md) — and specifically the case where one
word a person says has **several arithmetic readings of the same measure**, each a defensible answer
and only one of them the answer.

No column holds the denominator. "Margin" is a number you compute, not a value you look up, and the
choice of what it divides by is not presentational — it moves the figure by more than a factor of two
on the same profit. That fact has no home on a concept (it does not say what Margin *is*) and none on
an edge (it joins nothing). It is a statement about which figure a named reading divides, so it is a
rule, and a rule's body is a canon.

**Measured on contoso5**, and this is the whole argument for the canon existing:

| the word | over | figure | over | figure | gap |
|---|---|---|---|---|---|
| discount % | GrossRevenue | **5,93 %** | NetRevenue | 6,30 % | the discount itself |
| margin % / markup | NetRevenue | **55,91 %** | SalesCost | 126,79 % | factor **2,27** |
| price per article | UnitsSold | **310,98** | sale lines | 976,96 | factor **3,14** |

Before this canon, `Intent.denominator` already carried the choice and the planner already read it —
so a model's guess went straight through and nothing declared which reading was meant.

## Contract (the pluggable interface)

- **Signature:** `ratio_select(*, ratios, default=None, asked=None, surfaces=None) -> Selection`
- **Params:**
  - `ratios` — name → `{denominator}`, the declared readings. The denominator **names a concept**,
    not a column.
  - `default` — the name that applies when the question names no reading, or `None`.
  - `asked` — a word or value the question used, which may name a ratio.
  - `surfaces` — name → the words a person may use for it. Declared, because matching is exact.
  - **The numerator is not a param.** It is the rule's own `binds` — declared once, not twice. Same
    ruling `population_select` carries: *"this is redundant and unnecessary"* (operator, 2026-10-01,
    on a second column list beside `binds`).
- **Guarantee**, in this order:

  | the question | the selection |
  |---|---|
  | named a declared surface | that ratio, matched **exactly** (case-, space- and underscore-folded) |
  | named nothing recognisable, and a `default` is declared | the default, flagged `by_default=True` |
  | named nothing recognisable, and no `default` | **none** — `candidates` carries every declared name so the caller can ASK with them |
  | the concept declares no ratios at all | `None` from the reader — this canon does not apply |

- **Returns:** `Selection(name, denominator, by_default, named_by_question, candidates)`.
  `name is None` means ask, and `candidates` is what to offer.
- **Reads no rows.** The decision is made against the INTENT and the DECLARATIONS, because no SQL may
  run to decide which SQL to write.

## How a concept plugs in

Three shapes, all live in contoso5. They differ only in whether a ruling exists.

**One reading, settled — commit.** A person said which denominator; a bare mention takes it.

```yaml
- id: discount.aggregation.percent_is_over_gross
  kind: mac.concept.rule.aggregation
  binds: [discount_amount]                     # ← the NUMERATOR
  why: >
    the operator's KPI specification of 2026-09-30 fixes the denominator as gross sales. The two
    differ by the discount itself, so the choice is not presentational: 5,93 % over gross against
    6,30 % over net, on the same money.
  realized_by:
    - udf: mac.canon.ratio_select
      params:
        default: percent                       # ← the ruling
        ratios:
          percent:
            denominator: GrossRevenue
            surfaces: [discount percentage, discount rate, discount %, discount as a percentage]
```

**Two readings, neither ruled — ask.** The absent `default` is the declaration.

```yaml
- id: margin.aggregation.two_named_ratios
  kind: mac.concept.rule.aggregation
  binds: [margin_amount]
  why: >
    both ratios and their denominators are named in the operator's KPI specification. They differ by
    more than a factor of two on the same profit -- 55,91 % over net against 126,79 % over cost -- so
    naming one and computing the other is a wrong answer that looks right. NO `default` IS DECLARED,
    DELIBERATELY: the prose this replaces said "never use one name for the other", and a question
    saying only "margin" names neither.
  realized_by:
    - udf: mac.canon.ratio_select
      params:
        ratios:
          margin_percent:
            denominator: NetRevenue
            surfaces: [margin %, margin percentage, margin rate, net margin, margin on net]
          markup_percent:
            denominator: SalesCost
            surfaces: [markup, markup %, markup percentage, margin on cost]
```

**One reading among three candidates — the shape a prose rule converts into.** NetRevenue's price
rule said this in `when`/`then`/`never` and nothing executed it:

```yaml
- id: net_revenue.default.a_price_is_revenue_per_article
  kind: mac.concept.rule.aggregation
  binds: [net_amount]                          # ← net_price LEFT binds; see below
  why: >
    the operator ruled the average is what the customer paid per article, so the denominator is
    articles sold and not sale lines. THREE READINGS LOOK LIKE A UNIT PRICE AND ONE ANSWERS THE
    QUESTION: sum(net_amount) over UnitsSold is 310,98; averaging `net_price` weights a one-unit sale
    like a fifty-unit one and gives 309,87; averaging `net_amount` gives 976,96, the value of a LINE
    and not of an article.
  realized_by:
    - udf: mac.canon.ratio_select
      params:
        default: price_per_article
        ratios:
          price_per_article:
            denominator: UnitsSold
            surfaces: [price, average price, unit price, price per unit, per unit,
                       price per article, per article]
```

No `when:`, no `then:`, no `never:`. The body states the condition and the action executably; prose
beside a body is a second home that can drift from it. `why:` stays — no parameter encodes "a person
ruled this, on this date, against this measurement".

## Demonstration

```python
R = {"margin_percent": {"denominator": "NetRevenue"},
     "markup_percent": {"denominator": "SalesCost"}}
S = {"margin_percent": ("margin %", "net margin"),
     "markup_percent": ("markup", "margin on cost")}

ratio_select(ratios=R, default=None, asked="markup", surfaces=S)
# → Selection(name='markup_percent', denominator='SalesCost', named_by_question=True)   126,79 %

ratio_select(ratios=R, default=None, asked=None, surfaces=S)
# → Selection(name=None, candidates=('margin_percent','markup_percent'))    "margin?" → ASK, both offered

ratio_select(ratios=R, default="margin_percent", asked=None, surfaces=S)
# → Selection(name='margin_percent', denominator='NetRevenue', by_default=True)          55,91 %
```

## The role of `default`

It decides one thing: **what happens when the question does not name a reading.** Declaring it says
*someone ruled*; omitting it says *nobody has, so ask*. It is the resolution ladder's third rung made
declarative, and it is where a ruling lands rather than being re-typed as prose.

| declared ratios | `default` | question names a surface | question names nothing |
|---|---|---|---|
| two | absent | that ratio, `named=True` | **ASK**, both candidates offered |
| two | present | that ratio, `named=True` | the default, `by_default=True` |
| one | absent | that ratio, `named=True` | **ASK**, the one candidate offered |
| one | present | that ratio, `named=True` | the default, `by_default=True` |

**A single declared ratio and no `default` still asks** — measured, and worth stating because it
reads as redundant and is not:

```python
ONE = {"price_per_article": {"denominator": "UnitsSold"}}

ratio_select(ratios=ONE, default=None, asked=None, surfaces=...)
# → Selection(name=None, candidates=('price_per_article',))        "the price?" → ASK

ratio_select(ratios=ONE, default="price_per_article", asked=None, surfaces=...)
# → Selection(name='price_per_article', by_default=True)                       → commit, 310,98
```

A concept may declare one reading without claiming it is what an unqualified question means. So
`default` is never implied by there being nothing to choose between.

## Why matching is EXACT, and why `%` is not folded

Folding is case, space and underscore — nothing else. A reader writes `margin %`, a bundle declares
`margin_percent`, and neither spelling is more correct than the other. No stemming, no synonyms, no
string distance; the measurement that settles it is on
[`population_select`](population_select.md#why-matching-is-exact-with-the-measurement), where a typo
scores *between* two antonyms.

**`%` is deliberately not stripped, and a first cut stripped it.** That made the declared surface
`margin %` fold to exactly `margin`, so the bare word matched by accident of the fold function rather
than by any declaration — fuzzy matching through the back door. Measured when written: `asked="margin"`
selected `margin_percent` and divided by NetRevenue, a surface the bundle had never declared.

```python
fold("margin %")  ->  "margin%"          # NOT "margin"
fold("margin")    ->  "margin"

# surfaces: margin_percent -> ("margin %",),  markup_percent -> ("markup",)
asked="margin"    ->  ASK, candidates=('margin_percent','markup_percent')
asked="margin %"  ->  margin_percent / NetRevenue    named=True
asked="MARGIN%"   ->  margin_percent / NetRevenue    named=True
asked="markup"    ->  markup_percent / SalesCost     named=True
```

If a bundle wants the bare word to name a ratio it must **say so** by declaring it as a surface.
Otherwise two ratios and no default means ask, which is the point.

## Where the numerator comes from, and what that costs an author

`binds` **is** the numerator: the column every one of the rule's named readings divides. The reader
refuses a ratio rule that declares no `binds`, and refuses a bound column the concept's relation does
not declare.

This has a consequence worth stating, because it caught a real conversion. NetRevenue's price rule
bound two columns — `net_amount`, the column it divides, and `net_price`, the column its `never`
clause **forbids**. Under a prose rule nothing distinguished the two. Under the binding, naming the
forbidden column in `binds` would declare it as part of the figure being divided, so it has to go.

Nothing is lost, because both warnings were already declared elsewhere and the rule was restating
them:

| the prose forbade | the declaration that already forbids it |
|---|---|
| averaging `net_price` | `net_price`'s aggregate carries `type: intensive` |
| averaging `net_amount` | its aggregate's `default: true` against a key of one row per sale line — which is what makes 976,96 a per-line figure |

A ratio rule selects a denominator. It does not forbid an alternative numerator, and should not be
asked to.

## Determinism & honest limits (AUTHORING A5)

- **Deterministic.** Same declaration + same asked word → same selection. Pure: no ontology types, no
  I/O, no SQL.
- **It selects, it does not render.** Which denominator is this canon's; building the division,
  guarding a zero and formatting a percentage are the planner's and the presenter's.
- **A denominator names a CONCEPT, not a column.** `NetRevenue`, not `net_amount`. The canon does not
  resolve it — nothing here checks that the named concept exists, so a typo is a dangling reference
  this canon will not catch.
- **`by_default` fires for any unmatched token, not only for silence.** `asked="margin"` against
  NetRevenue's ratios returns `price_per_article` with `by_default=True`. The flag is what keeps that
  honest — the answer must disclose that the reading was assumed — and it depends on the planner
  routing a question to the concept it is about. The canon cannot tell "nothing was said" from "something
  was said that I do not recognise".
- **No synonyms and no inheritance.** A reading declared on one concept is not available on another;
  cross-concept wording belongs to the reader that shows the model the names.
- **One rule may declare several ratios; it cannot express a dependency between them** ("markup only
  when the question also said cost"). That would be a constraint, not a reading.
- **Its parameters are validated by a hand-written reader, not by a declared contract.**
  `mac_vocabulary.yaml#canon.terms.ratio_select` declares no `params`, and its term body is a bare
  string where its twenty siblings are mappings — so it carries no `serves`, no `needs_sqlglot` and no
  `doc` key. That malformation also empties `check_canon_binding._params_from()` for *every* canon, via
  a bare `except`. Both are outstanding.
