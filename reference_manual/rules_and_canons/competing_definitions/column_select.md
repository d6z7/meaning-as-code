---
title: "Canon — column_select"
part_of: reference_manual/canon
status: reference   # implemented in mac-runtime/canons/column_select.py; the decision only, not the rendering
scope: GENERIC — domain-neutral. Measurements from example/contoso5.
---

# Canon — `column_select`

> A **pure** canon and the third member of one family. [`population_select`](population_select.md)
> maps a word a reader says to the **rows** a concept has; [`ratio_select`](ratio_select.md) maps it
> to the **figure** a ratio divides by; this one maps it to the **column that answers**. It decides;
> it does not render.

## Serves

[`competing_definitions`](../../patterns/competing_definitions.md) — the case where one word a person
says could be answered from more than one column of the same concept, and the choice changes the
number rather than the presentation.

**Measured on contoso5.** `order.default.period_is_order_date` declared in prose that an order's
period is `order_date` and not `delivery_date`. An order counted on its delivery date falls in a
different month, so the reading is the answer — and it was a `then` clause only a model read.

`axis_default` could not hold it: that canon injects a **value into a column**, and nothing selected
**between columns**.

## Contract (the pluggable interface)

- **Signature:** `column_select(*, columns, default=None, asked=None, surfaces=None) -> Selection`
- **Params:**
  - `columns` — name → `{column, surfaces}`, the declared readings. The column must be one **this
    concept declares**; the reader refuses a reading pointing anywhere else, at load time.
  - `default` — the reading that applies when the question names none, or `None`.
  - `asked` — a word the question used.
  - **The axis is the rule's own `binds`** — the columns the reading chooses between. Declared once,
    not twice, as for a population and a ratio.
- **Guarantee**, in this order:

  | the question | the selection |
  |---|---|
  | named a declared surface **or the column itself** | that reading, matched exactly |
  | named nothing recognisable, with a `default` | the default, flagged `by_default=True` |
  | named nothing recognisable, no `default` | **none** — `candidates` carries every name, so the caller can ASK |
  | the concept declares no readings | `None` — this canon does not apply |

- **Returns:** `Selection(name, column, by_default, named_by_question, candidates)`.
- **Reads no rows.** The decision is made against the intent and the declarations.

### One thing its twins do not do

**Naming the column outright selects its reading.** `by delivery_date` is the least ambiguous thing
a person can say, and a population or a ratio has no equivalent — their names are not columns.

## How a concept plugs in

```yaml
- id: order.default.period_is_order_date
  kind: mac.concept.rule.default
  binds: [order_date, delivery_date]          # ← the axis: what it chooses between
  why: >-
    Dated and measured; the argument is in knowledge/order.md.
  realized_by:
    - udf: mac.canon.column_select
      params:
        default: ordered                      # ← the ruling
        columns:
          ordered:
            column: order_date
            surfaces: [ordered, order date, placed, when it was ordered]
          delivered:
            column: delivery_date
            surfaces: [delivered, delivery date, shipped, when it arrived]
```

## Demonstration

```python
asked="shipped"          -> delivered / delivery_date   named=True
asked="delivery_date"    -> delivered / delivery_date   named=True    # the column itself
asked="when it arrived"  -> delivered / delivery_date   named=True
asked=None               -> ordered   / order_date      by_default=True
asked="deliverd"         -> ordered   / order_date      by_default=True    # a typo is not a match
no default, nothing asked -> ASK, candidates ('ordered', 'delivered')
```

## It fits fewer rules than it looks like it should

Three contoso5 rules read as the same shape and are not. This is recorded because the mistake was
made out loud first:

| rule | why it is not this canon |
|---|---|
| `net_revenue.default.revenue_means_net` | the alternative column is on **another concept** (GrossRevenue) — it chooses between concepts |
| `country.default.a_sales_question_means_the_store_country` | the choice is a **join path**, `store_key` vs `customer_key`, columns of the fact and not of Country |
| `order.default.an_unscoped_question_covers_all_time` | no alternative column at all — it is about the **window** |

Widening this canon to dotted cross-concept refs would make it "which path", a different decision.

## Determinism & honest limits (AUTHORING A5)

- **Deterministic.** Same declaration + same asked word → same selection. Pure: no I/O, no SQL.
- **It selects, it does not render.** Putting the chosen column into the statement is the planner's.
- **`by_default` fires for any unmatched token, not only for silence.** The canon cannot tell
  "nothing was said" from "something was said that I do not recognise" — the flag is what keeps that
  honest, and the answer must disclose it.
- **Matching is exact**, case/space/underscore folded. `population_select`'s measurement is why: a
  typo sat *between* two antonyms by string distance, so no threshold separates them.
- **First declaration wins on a colliding surface**, and a collision is the bundle's to fix —
  silently rebinding would make the answer depend on dict order.
- **One rule is one axis.** It cannot express a dependency between two column choices.
