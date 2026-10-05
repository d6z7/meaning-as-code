A thing Contoso sells, at the level the shelf knows it: a SKU. 2,517 of them. Read from the rows — "Contoso 4G MP3 Player E400 Green" and "... E400 Orange" are two product keys — so a product here is a colour variant of a model, and the name carries brand, capacity, type, model and colour all at once.

A2: a keyed dimension that facts point at → `reference`. Not `entity`: it has no life of its own in this data beyond being sold.

ITS PRICES ARE LIST, NOT SOLD. `list_price` and `list_cost` are the catalogue; what a sale actually charged is on [[Sale]]. Revenue from list price is the revenue Contoso would have had if nobody ever discounted.

IT IS NOT ITS BRAND, CATEGORY OR COLOUR. Those are words a question uses and they will be lifted to concepts of their own once the centre's direct needs are grounded — MODELLING-LOG entry 6. Here they are the columns those concepts will be computed from.

## Details

- **Identity** — fk_name
- **Version** — 1.0
- **Schema version** — 0.1.16
- **Governance owner** — operator
- **Last reviewed** — 2026-09-29

## How to answer

_No content available — the bundle declares nothing for this section._

## Grounded in

- `dim_product` — key `['product_key']`

## Grain

one row per product (product_key)

## Fields

| column | type | role | identity | measure | rulings | register | description | joins → |
|---|---|---|---|---|---|---|---|---|
| `product_key` | — | key | canonical | — | — | — | — | — |
| `product_code` | — | dimension | — | — | label_of `product_key` (code) | — | — | — |
| `product_name` | — | dimension | — | — | label_of `product_key` (common) | — | — | — |
| `manufacturer` | — | dimension | — | — | label_of `brand` (legal) | — | — | — |
| `brand` | — | dimension | — | — | — | — | — | — |
| `color` | — | dimension | — | — | — | — | — | — |
| `category_name` | — | dimension | — | — | — | — | — | — |
| `sub_category_name` | — | dimension | — | — | — | — | — | — |
| `list_cost` | — | measure | — | intensive · USD | — | — | — | — |
| `list_price` | — | measure | — | intensive · USD | — | — | — | — |

_Declared per column, over 10 columns: type 0 of 10 · role 10 of 10 · identity 1 of 10 · measure 2 of 10 · rulings 3 of 10 · register 0 of 10 · description 0 of 10 · joins → 0 of 10. An em dash is a column for which nothing is declared._

## Axes

_No content available — the bundle declares nothing for this section._

## Relationships

_No content available — the bundle declares nothing for this section._

## Source of record

- Full MAC concept: `product.yaml` — open the **YAML** tab for the complete typed definition.
