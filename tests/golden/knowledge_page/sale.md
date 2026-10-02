# Sale — knowledge

## What it is

One product sold to one person on one day: the thing this whole warehouse is a record of. 223,974 of them over ten years, 2016-05 to 2025-12. Read from the rows: on 2016-05-18 customer 1293529 bought 2 of product 153 at store 430 for 751.95 USD — every other relation in this bundle exists to describe one of those five facts.

THE CENTRE, deliberately. Customer says to whom, Product says what, Store and Channel say where, CalendarDay says when, Currency and ExchangeRate say in what money. None of them is of interest here on its own; a customer with no sales is a directory entry. So this concept comes first and the others are built outward from what it needs — MODELLING-LOG.md, entries 3 and 4.

NOT "SalesLine". That is the structure's name — a line of an order, a row of a view. The landing table is already called `sales`, and a row of it is one product sold.

IT IS NOT AN ORDER. An order is the basket this belongs to — one to seven sales, median two — and it carries no measure of its own; every amount is here. [[Order]] is the grouping.

IT RESTS ON A PROPOSAL, NOT A RULING. The relation serving it declares `driven_by: proposed` against DQ-DUP-ORDERROWS-SALES: `orderrows` delivers the same 223,974 rows with one column fewer, and `sales` was chosen as the fact of record. Until a person answers that finding this concept stands on a recommendation.

IT CARRIES NO MEASURE OF ITS OWN. A sale has four things worth summing, and each folds by its own law, so each is a concept in its own right — [[UnitsSold]], [[NetRevenue]], [[GrossRevenue]], [[SalesCost]] — carrying its amount and the per-unit price it composes from. This is the event they hang off: its keys, its two dates, and the dimensions they are sliced by.

## What the configuration states

- Its grain is **one row per sale (order_key, line_number)**.
- One row is identified by `order_key`, `line_number`.

## Rules that govern it

- **sale.resolution.rate_on_order_date** (resolution)
    - _when_ — a sale's USD amount is wanted in the customer's currency
    - _then_ — join `{v_contoso5_fx_rate}` on `{order_date}` against the rate's day AND `{currency_code}` against its to-currency, with the from-currency fixed at USD — the whole rate key minus the unit the amounts are already in.
    - _never_ — join on currency alone
- **sale.default.period_is_order_date** (default)
    - _when_ — sales are put in a period and the question does not say which date
    - _then_ — bind the period to `{order_date}` — the column declared `period` — and say so in the answer; `{delivery_date}` is used only when the question asks about delivery
    - _never_ — bind the period to `{delivery_date}` unasked, or to `{order_date}` without saying so

## Where its values come from

_Nothing declared for this section._

## SME sources

_Nothing declared for this section._
