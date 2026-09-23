<!-- STATUS: companion to QUERY_GRAMMAR.md. Every trace below is REAL OUTPUT from the landed
     planner on 2026-09-23, produced by acceptance/tools/trace_question.py in a worked bundle.
     Nothing here is illustrative or reconstructed. Where a trace shows a refusal, that is what
     the runtime really answers today. -->

# A QUESTION, END TO END
### Seven worked examples: what the model produces, what the planner reads, and where the SQL comes from

`QUERY_GRAMMAR.md` is a reference — it answers questions you already know to ask. This one starts
from zero and follows single questions all the way through. Read this first.

---

## 0. THE SHAPE OF THE WHOLE THING

One question makes one trip. Only the first step involves a model; everything after it is
arithmetic on declarations.

```
  the question (English)
        │
        │   ①  INTERPRET — the only non-deterministic step
        │       the model is handed the VOCABULARY (names + prose, never tables)
        ▼
  Intent { subject, operation, slices, filters, period, ordering, limit, denominator }
        │
        │   ②  SUBJECT      which concept is this about? what does it declare?
        │   ③  ANCHOR       which relation is the FROM?
        │   ④  TERMS        each slice/filter name → a concept; each value → a code
        │   ⑤  JOINS        walk edges from the anchor to every term
        │   ⑥  PLACEMENT    does this predicate sit on the fact or the dimension?
        │   ⑦  ASSEMBLE     fold the contributions into one SELECT
        ▼
  SQL + bound parameters + the caveats the ontology insisted on
```

**Steps ② to ⑦ never read the question's words.** They read the Intent and the ontology. That is
the whole claim, and the traces below are what it looks like when it is true.

---

## 1. WHAT THE MODEL IS GIVEN

Not the database. Three lists, built from the ontology at load time:

```
MEASURES (4) — what `subject` may be for sum/average
   NetSalesAmount     The money value of sales AFTER discount: per order line, Quantity x NetPrice…
   GrossSalesAmount   The money value of sales BEFORE discount: per order line, Quantity x UnitPrice…
   QuantitySold       The number of units on an order line. SUM(Quantity) over the lines in scope…
   ExchangeRate       The rate at which one currency converted into another on one calendar day…

COUNTABLES (19) — a subject for `count`, and the key it will be counted by
   Brand              key=Brand          class=grouping
   CalendarDay        key=Date           class=reference
   Color              key=Color          class=enumeration
   …

DIMENSIONS (23) — what a slice or filter `term` may be
   AgeBand, Brand, CalendarDay, Color, Continent, Country, Currency, Customer, …
```

**There are no table names and no column names in any of it.** `grounding` is never read here, so
the model cannot name a table even by accident. It picks names out of a closed list; the planner
turns names into tables. That separation is why a wrong answer is nearly always a wrong *name*
rather than wrong SQL.

---

## 2. W1 · THE SIMPLE ONE — a count with a filter

> **"How many customers are in Germany?"**

```
[1] INTENT            subject='Customer'  operation=count
      filter          Country eq 'Germany'

[2] SUBJECT           Customer  class=entity
      declares        canonical_key='CustomerKey'  rule=None
      grounded on     dim_contoso_customer

[3] ANCHOR            Customer -> FROM dim_contoso_customer
      chosen because  the subject's own relation

[4] TERMS
      filter Country       -> Country  value 'Germany' -> codes ['DE']  (via register)

[5] JOINS/EDGES       (none — single relation)

[6] SQL
      SELECT COUNT(DISTINCT dim_contoso_customer.CustomerKey) AS customer
      FROM contoso_served.dim_contoso_customer
      WHERE dim_contoso_customer.Country = :country
    PARAMS            {'country': 'DE'}
```

**The three things to notice.**

`COUNT(DISTINCT CustomerKey)` was not chosen by the word "count". It came from `[2]`: Customer
declares `identity.canonical_key: CustomerKey`. The operation only licensed a non-measure subject
to be counted at all — **the key decided what to count**.

**`Germany` became `DE` before any SQL existed.** The `Country` concept declares a register, and the
register maps the search key `germany` to the code `DE` offline. No query was run to find that out,
and a country the bundle does not carry would have refused here, from a closed list, rather than
returning zero rows and looking like an answer.

No join, because `Country` is a column on the customer dimension. Nothing declared a hop, so none
was walked.

---

## 3. W2 · THE ONE THAT EXPLAINS THE DESIGN — the anchor moves

> **"How many different products did customers in France buy in Q1 2024?"**

This is the question that used to fail, and it is the best single illustration of what the planner
is for.

```
[1] INTENT            subject='Product'  operation=count
      filter          Country eq 'France'
      period          [2024-01-01 .. 2024-04-01)

[2] SUBJECT           Product  class=reference
      declares        canonical_key='ProductKey'  rule=None
      grounded on     dim_contoso_product

[3] ANCHOR            OrderLine -> FROM v_contoso_order_line          ← NOT the subject's relation
      chosen because  an event concept carries the counted key

[4] TERMS
      filter Country       -> Country  value 'France' -> codes ['FR']  (via register)

[5] JOINS/EDGES       ['order_line__sells__product',
                       'order_line__placed_by__customer',
                       'customer__resides_in__country']

[6] SQL
      SELECT COUNT(DISTINCT v_contoso_order_line.ProductKey) AS product
      FROM contoso_served.v_contoso_order_line
      JOIN contoso_served.dim_contoso_product  ON v_contoso_order_line.ProductKey  = dim_contoso_product.ProductKey
      JOIN contoso_served.dim_contoso_customer ON v_contoso_order_line.CustomerKey = dim_contoso_customer.CustomerKey
      WHERE v_contoso_order_line.OrderDate >= :period_start
        AND v_contoso_order_line.OrderDate <  :period_end
        AND dim_contoso_customer.Country    = :country
    PARAMS            {'period_start': 2024-01-01, 'period_end': 2024-04-01, 'country': 'FR'}
```

**The subject is `Product`, and the query does not start at the product table.** It starts at the
order line. Step ③ made that swap, and here is the reasoning, entirely from declarations:

> The question is a count *with a period and a filter*. The product dimension has no date — a
> product does not happen, it just *is*. But `OrderLine` is declared `class: event`, it declares
> `OrderDate` with the `period` field role, and its `field_roles` carry `ProductKey`. So the thing
> being counted is reachable from a relation that **does** have a date. Anchor there.

That is why *"products sold in 2024"* is answerable and *"products in 2024"* is not. The difference
is not in the English — it is in whether an event concept carries the key.

**The period landed on the fact, not on the dimension.** Step ⑥ places each predicate on the
relation that declares the column. `OrderDate` is the anchor's; `Country` belongs to the customer
dimension and went there, two hops away.

**Three edges were walked, and none was written by hand.** The path `OrderLine → Customer → Country`
came from a breadth-first search over `edges.yaml`. Add a fourth hop to the ontology and this
question keeps working; delete one and it refuses `no_join_path` — *the hop is undeclared*, which is
a different statement from *the data cannot answer it*.

---

## 4. W3 · A RULE DOES THE ARITHMETIC

> **"Show net revenue by customer country"**

```
[1] INTENT            subject='NetSalesAmount'  operation=sum
      slice           Country column=Country

[2] SUBJECT           NetSalesAmount  class=measure
      declares        canonical_key=None  rule='net_sales_amount'
      grounded on     v_contoso_order_line

[3] ANCHOR            OrderLine -> FROM v_contoso_order_line
      chosen because  the rule names it in `over`

[5] RULES             ['net_sales_amount']
    EDGES             ['order_line__placed_by__customer', 'customer__resides_in__country']

[6] SQL
      SELECT dim_contoso_customer.Country,
             SUM(f."Quantity" * f."NetPrice") AS net_sales_amount
      FROM contoso_served.v_contoso_order_line f
      JOIN contoso_served.dim_contoso_customer ON f.CustomerKey = dim_contoso_customer.CustomerKey
      GROUP BY dim_contoso_customer.Country
```

**`Quantity * NetPrice` is not in the planner.** It is the `template` of the `net_sales_amount`
rule in the ontology. The planner asked the concept what derives it, got a rule, and used the rule's
own expression and its own `over: [OrderLine]` to pick the anchor. Change the arithmetic in the
ontology and this SQL changes with no code touched — which is the entire point of the exercise.

**The slice became a `GROUP BY` and nothing else did.** Everything the question did *not* name —
store, product, day, currency — folded silently into each row. That is the fold grammar's sentence,
and it is where `FOLD_GRAMMAR.md` picks up: *what may legitimately be folded* is a different
question from *what SQL to write*, and the two are deliberately separate documents.

---

## 5. W4 · THE ONTOLOGY ADDS SQL NOBODY ASKED FOR

> **"How many stores are closed?"**

```
[1] INTENT            subject='Store'  operation=count
      filter          StoreStatus eq 'Closed'

[4] TERMS
      filter StoreStatus   -> StoreStatus  value 'Closed' -> codes ['Closed']  (via identity)

[6] SQL
      SELECT COUNT(DISTINCT cycle.StoreKey) AS store
      FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY StoreKey ORDER BY OpenDate DESC)
                      AS _mac_cycle_rank
            FROM contoso_served.dim_contoso_store) cycle
      WHERE cycle._mac_cycle_rank = 1
        AND cycle.Status = :storestatus
```

**Where did the window function come from?** Nobody asked for one. The `Store` concept declares a
`grounding.snapshot_rule`, because the store dimension is slowly-changing: 74 version rows over 67
store codes. Counting `StoreKey` straight would count *versions*, not stores.

So step ⑦ wrapped the relation in a collapse to the latest version per store **before** counting.
The declaration did that, not a code path, and a bundle whose dimension is not versioned gets no
subquery at all.

This is the clearest case of the ontology earning its keep: the naive SQL is not *wrong-looking*.
It would return a number, and the number would be silently too big.

---

## 6. W5 · A NEGATIVE QUESTION

> **"Which products were NOT sold in 2024?"**

```
[1] INTENT            subject='Product'  operation=exists
      period          [2024-01-01 .. 2025-01-01)

[3] ANCHOR            Product -> FROM dim_contoso_product     ← back to the dimension

[6] SQL
      SELECT DISTINCT dim_contoso_product.ProductCode AS product
      FROM contoso_served.dim_contoso_product
      WHERE dim_contoso_product.ProductKey NOT IN (
            SELECT DISTINCT v_contoso_order_line.ProductKey
            FROM contoso_served.v_contoso_order_line
            WHERE v_contoso_order_line.OrderDate >= :period_start
              AND v_contoso_order_line.OrderDate <  :period_end)
```

**Compare the anchor with W2.** Same subject, same period, opposite anchor. In W2 the question was
*which products did happen*, so the fact is the population. Here it is *which products did not*, so
the **dimension** is the population and the fact is the exclusion set.

`exists` is one of the four operations the planner tests for by name, and this is why: it also turns
off the period gate on the outer query. The period belongs inside the subquery. A period on the
outer query would filter the product catalogue by a date it does not have.

---

## 7. W6 · A REFUSAL THAT IS THE BUNDLE'S FAULT

> **"What is the revenue from the online store?"**

```
[4] TERMS
      filter Store         -> REFUSED ontology_gap ['Store: resolve_by_register']

[5] PLAN              REFUSED ontology_gap: ['Store: resolve_by_register']
      reason          The ontology declares no register for Store, so a name like 'Online'
                      cannot be resolved to a code.
```

Nothing was executed. The refusal names the **declaration that would fix it** — `Store` needs a
register, and a register CSV for stores already sits in the bundle undeclared by any concept.

This is the second axis of the grammar doing its job. The question is well-formed, the Intent is
well-formed, the data is there. What is missing is a statement, and the runtime says which.

---

## 8. W7 · A REFUSAL THAT IS THE GRAMMAR'S FAULT

> **"Countries where average order value exceeds 500"**

```
[1] INTENT            subject='NetSalesAmount'  operation=ratio
      slice           Country
      filter          NetSalesAmount gt 500.0            ← a filter on a MEASURE

[4] TERMS
      filter NetSalesAmount -> REFUSED unresolved_term ['NetSalesAmount']
      reason          No known dimension matches the term 'NetSalesAmount'.
```

**This one is not the bundle's fault and no declaration fixes it.** The filter wants to compare an
*aggregate* — `HAVING AVG(...) > 500` — and every filter the Intent can carry lands in `WHERE`. So
the term is looked up among dimensions, where a measure is correctly not found.

It is the single question of seventy that no hand-written intent could encode, and it is recorded
as such in `grammar/query_grammar.yaml#not_expressible`. The error message is honest but misleading
to a newcomer: the term *is* known, just not as a dimension.

---

## 9. WHAT THE SEVEN CASES SHOW TOGETHER

| | the SQL came from | not from |
|---|---|---|
| W1 | `identity.canonical_key`, and a register | the word "count" |
| W2 | an event concept carrying the key + a BFS over edges | the question's phrasing |
| W3 | a rule's `template` and its `over` | arithmetic in the planner |
| W4 | `grounding.snapshot_rule` | anything the question said |
| W5 | the operation, genuinely — one of four that branch | declarations alone |
| W6 | — refused, naming the missing declaration | — |
| W7 | — refused, and the grammar is the gap | — |

**Six of seven get their shape from declarations.** That is the measured claim of
`QUERY_GRAMMAR.md` §1, shown rather than asserted: the operation is not what decides the SQL.

---

## 10. TRACE ONE YOURSELF

The traces above are unedited output. To produce them for any question:

```bash
# in a bundle that has the harness (acceptance/tools/)
<platform>/.venv/bin/python acceptance/tools/trace_question.py cases.json
```

where `cases.json` is `{"<id>": {"question": "...", "intent": { … }}}`. Write the intent by hand to
ask *"could the planner do this if the model got it right?"* — which is the question that separates
an interpretation bug from a planner bug, and the one nothing else answers.

The intents for a whole corpus, with what each produced, live in `acceptance/intents.yaml`.
