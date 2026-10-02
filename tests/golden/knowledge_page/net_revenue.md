# Net Revenue — knowledge

## What it is

What Contoso actually charged: quantity times the discounted price, per sale, summed. Read from the rows: 681.72 net against 717.60 gross on one sale — the gap is the discount.

THE DEFAULT READING OF "REVENUE", and it is after discount. [[GrossRevenue]] is the same figure before it. Answering one when a question meant the other moves every derived figure — margin most of all — in a direction somebody will like.

IT IS IN USD. The sale's `currency_code` names what the customer paid in, not what this is stated in; conversion goes through [[ExchangeRate]] at the sale's own order date.

## What the configuration states

- Its grain is **one row per sale (order_key, line_number)**.
- One row is identified by `order_key`, `line_number`.
- `net_amount` is a flow USD measure.
- `net_price` is a intensive USD measure.

## Rules that govern it

- **net_revenue.aggregation.never_from_unit_prices** (aggregation)
    - _when_ — revenue is asked for over any set of sales
    - _then_ — sum `{net_amount}` — it is already quantity x `{net_price}` on the row
    - _never_ — sum or average `{net_price}`
- **net_revenue.default.revenue_means_net** (default)
    - _when_ — a question says "revenue" or "sales" without saying net or gross
    - _then_ — answer with `{net_amount}` and say NET — it is after discount; the figure before discount is [[GrossRevenue]]
    - _never_ — pick one silently

## Where its values come from

_Nothing declared for this section._

## SME sources

_Nothing declared for this section._
