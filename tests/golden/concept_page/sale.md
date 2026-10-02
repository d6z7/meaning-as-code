One product sold to one person on one day: the thing this whole warehouse is a record of. 223,974 of them over ten years, 2016-05 to 2025-12. Read from the rows: on 2016-05-18 customer 1293529 bought 2 of product 153 at store 430 for 751.95 USD — every other relation in this bundle exists to describe one of those five facts.

THE CENTRE, deliberately. Customer says to whom, Product says what, Store and Channel say where, CalendarDay says when, Currency and ExchangeRate say in what money. None of them is of interest here on its own; a customer with no sales is a directory entry. So this concept comes first and the others are built outward from what it needs — MODELLING-LOG.md, entries 3 and 4.

NOT "SalesLine". That is the structure's name — a line of an order, a row of a view. The landing table is already called `sales`, and a row of it is one product sold.

IT IS NOT AN ORDER. An order is the basket this belongs to — one to seven sales, median two — and it carries no measure of its own; every amount is here. [[Order]] is the grouping.

IT RESTS ON A PROPOSAL, NOT A RULING. The relation serving it declares `driven_by: proposed` against DQ-DUP-ORDERROWS-SALES: `orderrows` delivers the same 223,974 rows with one column fewer, and `sales` was chosen as the fact of record. Until a person answers that finding this concept stands on a recommendation.

IT CARRIES NO MEASURE OF ITS OWN. A sale has four things worth summing, and each folds by its own law, so each is a concept in its own right — [[UnitsSold]], [[NetRevenue]], [[GrossRevenue]], [[SalesCost]] — carrying its amount and the per-unit price it composes from. This is the event they hang off: its keys, its two dates, and the dimensions they are sliced by.

## Details

- **Version** — 1.0
- **Schema version** — 0.1.16
- **Status** — draft
- **Owner** — operator
- **Governance owner** — operator
- **Last reviewed** — 2026-09-29

## How to answer

_No content available — the bundle declares nothing for this section._

## Grounded in

- `v_contoso5_sales_line` — key `['order_key', 'line_number']`

## Grain

one row per sale (order_key, line_number)

## Fields

| column | type | role | identity | measure | rulings | register | description | joins → |
|---|---|---|---|---|---|---|---|---|
| `order_key` | — | key | part | — | — | — | — | — |
| `line_number` | — | key | part | — | — | — | — | — |
| `order_date` | — | period | — | — | — | — | — | — |
| `delivery_date` | — | dimension | — | — | — | — | — | — |
| `customer_key` | — | key | reference | — | — | — | — | — |
| `store_key` | — | key | reference | — | — | — | — | — |
| `product_key` | — | key | reference | — | — | — | — | — |
| `currency_code` | — | dimension | — | — | — | — | — | — |

_Declared per column, over 8 columns: type 0 of 8 · role 8 of 8 · identity 5 of 8 · measure 0 of 8 · rulings 0 of 8 · register 0 of 8 · description 0 of 8 · joins → 0 of 8. An em dash is a column for which nothing is declared._

## Axes

_No content available — the bundle declares nothing for this section._

## Relationships

_No content available — the bundle declares nothing for this section._

## Source of record

- Full MAC concept: `sale.yaml` — open the **YAML** tab for the complete typed definition.
