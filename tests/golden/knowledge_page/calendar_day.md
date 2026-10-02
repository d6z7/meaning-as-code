# Calendar Day — knowledge

## What it is

One day, with the parts of it a question names: year, quarter, month, weekday. 4,018 days, 2016-01-01 onward.

A2: a keyed dimension that facts point at → `reference`. Every date in the bundle points here — a sale twice, a rate once — so "last March" means one thing everywhere.

NAMES RESOLVE THROUGH `data/lookups/contoso5_year_month.lookup.csv` and `data/lookups/contoso5_year_quarter.lookup.csv` — a question says "January 2016" or "Q1 2016", and those are the registers that turn the words into the day set.

## What the configuration states

- Its grain is **one row per calendar day (date_day)**.
- One row is identified by `date_day`.
- Its identity is established as `iso`.

## Rules that govern it

- **calendar_day.aggregation.month_name_does_not_sort** (aggregation)
    - _when_ — a monthly series is asked for
    - _then_ — group by `{year_month}`, which orders correctly and keeps years apart
    - _never_ — group by `{month_name}`

## Where its values come from

_Nothing declared for this section._

## SME sources

_Nothing declared for this section._
