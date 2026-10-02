What Contoso actually charged: quantity times the discounted price, per sale, summed. Read from the rows: 681.72 net against 717.60 gross on one sale — the gap is the discount.

THE DEFAULT READING OF "REVENUE", and it is after discount. [[GrossRevenue]] is the same figure before it. Answering one when a question meant the other moves every derived figure — margin most of all — in a direction somebody will like.

IT IS IN USD. The sale's `currency_code` names what the customer paid in, not what this is stated in; conversion goes through [[ExchangeRate]] at the sale's own order date.

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
| `net_amount` | — | measure | — | flow · USD | — | — | — | — |
| `net_price` | — | measure | — | intensive · USD | — | — | — | — |
| `order_date` | — | period | — | — | — | — | — | — |
| `delivery_date` | — | dimension | — | — | — | — | — | — |
| `customer_key` | — | key | reference | — | — | — | — | — |
| `store_key` | — | key | reference | — | — | — | — | — |
| `product_key` | — | key | reference | — | — | — | — | — |
| `currency_code` | — | dimension | — | — | — | — | — | — |

_Declared per column, over 10 columns: type 0 of 10 · role 10 of 10 · identity 5 of 10 · measure 2 of 10 · rulings 0 of 10 · register 0 of 10 · description 0 of 10 · joins → 0 of 10. An em dash is a column for which nothing is declared._

## Axes

Measure type: `flow` — `mac.concept.column.measure_type.flow`.

| axis | axis kind | fold |
|---|---|---|
| `currency_code` | categorical | additive |
| `customer_key` | categorical | additive |
| `delivery_date` | time | additive |
| `order_date` | time | additive |
| `product_key` | categorical | additive |
| `store_key` | categorical | additive |

_The fold is read from the framework registry (`measure_type.<type>.additivity.<axis kind>`), not declared on this concept. An em dash means the crossing is not declared there._

## Relationships

_No content available — the bundle declares nothing for this section._

## Source of record

- Full MAC concept: `net_revenue.yaml` — open the **YAML** tab for the complete typed definition.
