# Product — knowledge

## What it is

A thing Contoso sells, at the level the shelf knows it: a SKU. 2,517 of them. Read from the rows — "Contoso 4G MP3 Player E400 Green" and "... E400 Orange" are two product keys — so a product here is a colour variant of a model, and the name carries brand, capacity, type, model and colour all at once.

A2: a keyed dimension that facts point at → `reference`. Not `entity`: it has no life of its own in this data beyond being sold.

ITS PRICES ARE LIST, NOT SOLD. `list_price` and `list_cost` are the catalogue; what a sale actually charged is on [[Sale]]. Revenue from list price is the revenue Contoso would have had if nobody ever discounted.

IT IS NOT ITS BRAND, CATEGORY OR COLOUR. Those are words a question uses and they will be lifted to concepts of their own once the centre's direct needs are grounded — MODELLING-LOG entry 6. Here they are the columns those concepts will be computed from.

## What the configuration states

- Its grain is **one row per product (product_key)**.
- One row is identified by `product_key`.
- `list_cost` is a intensive USD measure.
- `list_price` is a intensive USD measure.
- `product_code` is another name for `product_key`'s thing, in the code register — group on the named column and show this one.
- `product_name` is another name for `product_key`'s thing, in the common register — group on the named column and show this one.
- `manufacturer` is another name for `brand`'s thing, in the legal register — group on the named column and show this one.
- Its identity is established as `fk_name`.

## Rules that govern it

- **product.ambiguity.list_price_is_not_revenue** (ambiguity)
    - _when_ — a question asks what a product sold for, or what it earned
    - _then_ — read the amounts on [[NetRevenue]] and [[GrossRevenue]] — they are what was charged
    - _never_ — multiply `{list_price}` by the quantity sold

## Where its values come from

_Nothing declared for this section._

## SME sources

_Nothing declared for this section._
