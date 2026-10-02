---
title: "Canon — population_select"
part_of: reference_manual/canon
status: reference   # implemented in mac-runtime/canons/population_select.py; the decision only, not the rendering
scope: GENERIC — domain-neutral. Measurements from example/contoso5.
---

# Canon — `population_select`

> A **pure** canon: given a concept's declared populations and what the question already said, it
> selects **which rows the concept has for this question** — or states that the question's own
> filters govern and none applies. It decides; it does not render. Lowering the chosen predicate to
> bound SQL is the predicate reader's job.

## Serves

[`competing_definitions`](../patterns/competing_definitions.md) — and, more precisely, the case that
pattern does not reach: a business state that is a **column combination** rather than a stored value.
A store is *closed* when `close_date IS NOT NULL`; a sale is *online* when its store's
`location_code = -1`. No column holds the words `closed` or `online`.

That fact has no home on a concept (it does not say what a store *is*) and none on an edge (it joins
nothing). It is a statement about which rows the concept HAS under a given reading — so it is a rule,
and a rule's body is a canon.

## Contract (the pluggable interface)

- **Signature:** `population_select(*, populations, default, binds, constrained_columns=(), asked=None) -> Selection`
- **Params:**
  - `populations` — the declared names.
  - `default` — the name that applies when the question says nothing about this axis, or `None`.
  - `binds` — the columns this axis is stated by. **This is the trigger condition**, and it is the
    rule's own `binds`, not a second list beside it.
  - `constrained_columns` — every column the question's own filters land on, for this concept.
  - `asked` — a value or term the question used, which may NAME a population.
- **Guarantee**, in this order:

  | the question | the selection |
  |---|---|
  | named a population | that one, matched **exactly**, never fuzzily |
  | constrained a column in `binds` | **none** — the question's own statement governs; `displaced_by` names the columns |
  | neither | the `default`, if one is declared |
  | neither, and no `default` | none — this axis has no "unless told otherwise" reading |

- **Returns:** `Selection(name, by_default, named_by_question, displaced_by)`. `name is None` means
  nothing applies.
- **Reads no rows.** The condition is tested against the INTENT and the DECLARATIONS, because no SQL
  may run to decide which SQL to write.

## How a concept plugs in

One rule is one **axis**, and axes are independent. A concept with two states declares two rules.

```yaml
# the trading state
- id: store.resolution.active_is_the_absent_close_date
  kind: mac.concept.rule.resolution
  binds: [close_date, status_annotation]        # ← the condition
  why: >
    two columns state one thing; a person ruled the close date is the truth on 2026-09-30
  realized_by:
    - udf: mac.canon.population_select
      params:                                   # ← the action
        default: active
        populations:
          active:       {all: [{column: close_date, op: is_null}]}
          ended:        {all: [{column: close_date, op: is_not_null}]}
          closed:       {all: [{column: status_annotation, op: eq, value: Closed}]}
          restructured: {all: [{column: status_annotation, op: eq, value: Restructured}]}

# the channel, on the same relation and orthogonal to it
- id: store.resolution.the_channel_is_the_location_sentinel
  kind: mac.concept.rule.resolution
  binds: [location_code]
  realized_by:
    - udf: mac.canon.population_select
      params:
        default: physical
        populations:
          physical: {all: [{column: location_code, op: ne, value: -1}]}
          online:   {all: [{column: location_code, op: eq, value: -1}]}
```

No `when:`, no `then:`, no `never:`. The body states the condition and the action executably; prose
beside a body is a second home that can drift from it. `why:` stays — no predicate encodes "a person
ruled this, on this date, against this measurement".

**A `default:` is optional and its absence is a declaration**, not an omission: the axis has no
"unless told otherwise" reading, so a question silent about it means the whole range.

## Demonstration

```python
POPS  = ["active", "ended", "closed", "restructured"]
BINDS = ["close_date", "status_annotation"]

population_select(populations=POPS, default="active", binds=BINDS)
# → Selection(name='active', by_default=True)                      "how many stores?"            → 57

population_select(populations=POPS, default="active", binds=BINDS, asked="closed")
# → Selection(name='closed', named_by_question=True)               "how many are closed?"        → 9

population_select(populations=POPS, default="active", binds=BINDS,
                  constrained_columns=["close_date"])
# → Selection(name=None, displaced_by=('close_date',))             "which closed after 2020?"    → the question governs

population_select(populations=POPS, default="active", binds=BINDS,
                  constrained_columns=["country_code"])
# → Selection(name='active', by_default=True)                      "how many in Germany?"        → default still applies
```

## Why the condition is DECLARED and not inferred

The first attempt compared **column names**: drop a declared conjunct when the question names a
column that conjunct mentions. Measured on contoso5, it cannot work. The question constrains
`status_annotation`; the declaration constrained `close_date`; the intersection is empty, so nothing
fired — and `status_annotation = 'Closed' AND close_date IS NULL` shipped. A closed store always
carries a close date, so the conjunction can never be true: **0 rows against a truth of 9, with every
stage reporting ok.** Those two columns are two statements of ONE fact, and no reader can derive that
from their names. `binds` is the author stating it.

## Why matching is EXACT, with the measurement

Asked to separate a typo from an antonym by string distance:

```
activ     → active    0.9091   typo
neaktivan → aktivan   0.8750   antonym (Croatian)
inactive  → active    0.8571   antonym (English)
```

The typo sits **between** the two antonyms, and substring containment holds for all three. No
threshold and no affix rule separates them, and an affix rule would be English-only in any case. So
the guard is **structural**: a population resolves on an exact (case-, space- and underscore-folded)
name or not at all. A typo costs one clarification turn; the alternative is answering `inactive` with
the `active` rows, which is the opposite of the question.

A population name is also checked **before** any value ladder, so it cannot lose a tie to a
coincidental value match. Measured: `online` resolved as a *value* to four candidates at score 1.0 and
not one was the channel — the sentinel country code `'--'` on three concepts, and `'Online'` on a
state column.

## Determinism & honest limits (AUTHORING A5)

- **Deterministic.** Same declaration + same constrained columns + same asked word → same selection.
  Pure: no ontology types, no I/O, no SQL.
- **It selects, it does not render.** Lowering a population to bound SQL — and the ruling that `ne`
  is `IS DISTINCT FROM` rather than `<>` — belongs to the predicate reader. A predicate written as SQL
  *text* cannot carry a string at all: the adapter gate refuses raw literals, and five of the ten
  predicates contoso5 needs are string-valued.
- **One rule is one axis.** This canon is asked once per rule. It cannot express a dependency between
  axes ("online stores are never restructured"); that would be a constraint, not a population.
- **Conjunctions only** inside a population: `all:` of clauses, with `in` as the same-column
  disjunction. An `any:` block is a declared gap — admitting one costs the narrow answer to "which
  clause did the question contradict".
- **No synonyms.** `inactive` is not a population if `ended` already is the same rows; mapping a
  surface word onto a declared name is a separate concern and belongs to the reader that shows the
  model the names.
- **Every population must only test columns its rule `binds`.** `stray_columns()` is the invariant: a
  population testing an unbound column could never be displaced by a question about that column, so
  the trigger would be blind on exactly the axis it claims to own.
