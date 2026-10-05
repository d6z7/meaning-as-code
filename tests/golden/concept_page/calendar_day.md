One day, with the parts of it a question names: year, quarter, month, weekday. 4,018 days, 2016-01-01 onward.

A2: a keyed dimension that facts point at → `reference`. Every date in the bundle points here — a sale twice, a rate once — so "last March" means one thing everywhere.

NAMES RESOLVE THROUGH `data/lookups/contoso5_year_month.lookup.csv` and `data/lookups/contoso5_year_quarter.lookup.csv` — a question says "January 2016" or "Q1 2016", and those are the registers that turn the words into the day set.

## Details

- **Identity** — iso
- **Version** — 1.0
- **Schema version** — 0.1.16
- **Governance owner** — operator
- **Last reviewed** — 2026-09-29

## How to answer

_No content available — the bundle declares nothing for this section._

## Grounded in

- `dim_date` — key `['date_day']`

## Grain

one row per calendar day (date_day)

## Fields

| column | type | role | identity | measure | rulings | register | description | joins → |
|---|---|---|---|---|---|---|---|---|
| `date_day` | — | key | canonical | — | — | — | — | — |
| `date_key` | — | housekeeping | — | — | — | — | — | — |
| `year` | — | dimension | — | — | — | — | — | — |
| `year_quarter` | — | dimension | — | — | finer_than `year` | — | — | — |
| `year_month` | — | dimension | — | — | finer_than `year_quarter` | — | — | — |
| `month_name` | — | dimension | — | — | — | — | — | — |
| `day_of_week` | — | dimension | — | — | — | — | — | — |

_Declared per column, over 7 columns: type 0 of 7 · role 7 of 7 · identity 1 of 7 · measure 0 of 7 · rulings 2 of 7 · register 0 of 7 · description 0 of 7 · joins → 0 of 7. An em dash is a column for which nothing is declared._

## Axes

_No content available — the bundle declares nothing for this section._

## Relationships

_No content available — the bundle declares nothing for this section._

## Source of record

- Full MAC concept: `calendar_day.yaml` — open the **YAML** tab for the complete typed definition.
