---
title: "Canon — path_select"
part_of: reference_manual/canon
status: reference   # implemented in mac-runtime/canons/path_select.py; the decision only, not the join
scope: GENERIC — domain-neutral. Measurements from example/contoso5.
---

# Canon — `path_select`

> A **pure** canon and the fourth member of one family. [`population_select`](population_select.md)
> maps a word a reader says to the **rows** a concept has; [`ratio_select`](ratio_select.md) maps it to
> the **figure** a ratio divides by; [`column_select`](column_select.md) maps it to the **column that
> answers**; this one maps it to the **relation the answer is reached through**. It decides; it does not
> build the join.

## Serves

`competing_definitions` — one term, several named readings, and nothing in the figure revealing which
one a reader was given.

## Why it exists

A dimension's key can sit on more than one relation. When it does, "revenue by X" is not one question,
and the readings do not differ by a rounding.

**Measured on contoso5.** `country_code` is carried by **three** relations — `dim_customer`,
`dim_store`, `dim_location` — so three edges terminate at `Country`:

| edge | from | level | predicate |
|---|---|---|---|
| `customer__based_in__country` | Customer | physical | `dim_customer.country_code = dim_country.country_code` |
| `store__trades_in__country` | Store | physical | `dim_store.country_code = dim_country.country_code` |
| `location__in__country` | Location | physical | `dim_location.country_code = dim_country.country_code` |

The readings answer different business questions. *"How much did our German shops sell"* includes a
visitor who walks into a Berlin shop and **excludes the online channel entirely**, because the online
store is a sentinel row — `location_code = -1`, `country_code = '--'` — and belongs to no country.
*"How much did our German customers buy"* includes a German buying online or abroad.

Online is **40 % of net revenue**, so the gap is structural rather than marginal. The bundle's own rule
records it: Germany's 2025 growth is **+18.07 % through the customer and +49.65 % through the store**.

A person ruled on it. `country.default.a_sales_question_means_the_store_country`, **`confidence: C`**
(the bundle's term for a human judgement, against `P` for a provisional reading), 2026-09-30:

```yaml
then:  join through the store — country_code on the store's row — and say in the answer that the
       figures are by the country the store trades in
never: pick between the store and the customer silently, and never average the two
```

### And the ruling was inverted on every question, for a week

Measured 2026-10-06 against the live bundle, all seven measures:

```
NetRevenue    -> net_revenue__by__customer   + customer__based_in__country
GrossRevenue  -> gross_revenue__by__customer + customer__based_in__country
UnitsSold     -> units_sold__by__customer    + customer__based_in__country
Margin        -> margin__by__customer        + customer__based_in__country
Discount      -> discount__by__customer      + customer__based_in__country
SalesCost     -> sales_cost__by__customer    + customer__based_in__country
Order         -> order__placed_by__customer  + customer__based_in__country
```

Seven for seven, the opposite of the ruling. **Three causes stack, and the third is the one that is
easy to miss.**

**One — the directive has no reader.** `when:` and `then:` appear **zero** times in the runtime. The
sentence is text in a YAML file that no code opens.

**Two — only `never:` reaches the model**, as prose in the system prompt, so the model *is* told the
store reading is default.

**Three — and the model could not comply even if it wanted to.** The intent it produces carries
`subject`, `operation`, `slices`, `filters`, `join_filters`, `any_of`, `all_of`, `having`, `also`,
`denominator_scope`, `confidence`. **There is no field for a join path.** The model says "group by
Country" and the planner chooses the route afterwards, alone. So this was never a disobedient model:
**the instruction was unfollowable, because there was nowhere to put the answer.**

**What chose instead.** `ontology/graph.py` runs unweighted breadth-first search and returns the *first
shortest path* it finds, over an adjacency built by walking `edges.yaml` in **declaration order**. Both
candidate paths are two hops, so the tie broke on a line number:

```
net_revenue__by__customer   edges.yaml:276
net_revenue__by__store      edges.yaml:289
```

Cut and paste those two blocks in the other order and every country figure in the business changes,
with nothing to warn anyone.

### Why no gate caught it

`check_plan_replay` asks *did anything that used to plan now refuse?* All seven **still plan**, so it
reported `0 gained over 58` and was **correct**: nothing was lost. The answer was simply wrong. A
success/failure tally cannot see a plan that succeeds down a different route — which is why
`check_rule_baseline` freezes `edges_used` and `rules_used` per question.

### Why its twin cannot do this

`column_select` looks like the answer and is not; its own docstring disqualifies this case by name —
*"the choice is a **JOIN PATH** through `store_key` vs `customer_key`, columns of the FACT and not of
Country."* That canon chooses among columns **the concept itself declares**; Country declares
`country_code` and `country_name`, and the thing being chosen lives one hop away on the fact. Widening
it would turn "which column" into "which path": a different decision wearing the same name.

### And there was no slot for the answer

Measured: **38 edges, 0 carrying any `default` or `preferred` key**, and no vocabulary term for one. So
the ruling lived only in prose — **1 105 characters of `Country.contract.default_reading`, the single
largest prose item in the estate** — telling the model something the planner then overrode.

## Contract (the pluggable interface)

Pure, offline, deterministic. Same `(paths, asked, reachable)` in, same decision out. It reads no
warehouse, parses no SQL, and builds no join.

```
path_select(asked, *, paths, default=None, reachable=None) -> Selection
```

| | |
|---|---|
`paths` | `{name: {via: <edge_id>, surfaces: [words a person may say]}}`, at least one |
`default` | a name in `paths`, or absent — **absence is a declaration** |
`asked` | the word the question used, or `None` |
`reachable` | the edge ids that actually reach the target from this subject; `None` means "do not filter" |

| situation | decision |
|---|---|
`asked` matches a declared surface, or a path's own name | `RESOLVE` that path, `named=True` |
`asked` names nothing and a `default` is declared | `RESOLVE` the default, `named=False`, **and disclose** |
`asked` names nothing and no `default` | `ASK` with every reachable name offered |
exactly one path is reachable | `RESOLVE` it, whatever `asked` said — there is no choice to make |
no path is reachable | **does not apply**; the caller falls through to ordinary path finding |

Matching is **exact**, case/space/underscore folded, and nothing else — no stemming, no synonyms. The
reason is `population_select`'s measurement: asked to separate a typo from an antonym by string
distance, the typo sat *between* two antonyms (`activ`→`active` 0.9091, `neaktivan`→`aktivan` 0.8750,
`inactive`→`active` 0.8571), so no threshold separates them and the guard has to be structural.

### Disclosure is not a parameter

The ruling requires it — *"say in the answer that the figures are by the country the store trades in."*
A `disclose: true` parameter could be set `false`, which would let an author switch off the thing the
ruling demands. So the canon discloses whenever it resolves a path the question did not name, the way
`label_of`'s reader does, and there is no flag.

## How a concept plugs in

On the concept the readings **meet** — the one whose key the several relations carry — as an ordinary
`contract.rules[]` entry:

```yaml
    - id: country.default.a_sales_question_means_the_store_country
      subject: which of three relations carrying country_code a sales question means
      kind: mac.concept.rule.default
      confidence: C
      scope: CONTOSO5
      binds:
        - country_code
      why: >
        Germany 2025 is +18.07% through the customer and +49.65% through the store, because the store
        path excludes the online channel and online is 40% of net revenue. Operator ruling 2026-09-30.
      realized_by:
        - udf: mac.canon.path_select
          params:
            default: store
            paths:
              store:    {via: store__trades_in__country,   surfaces: [store country, where we trade]}
              customer: {via: customer__based_in__country, surfaces: [customer country, where our customers are]}
              location: {via: location__in__country,       surfaces: [site country]}
```

`binds: [country_code]` is the field-anchoring every contract rule carries, checked cross-file against
the concept's own grounded columns by the `rule-binds-grounded` shape.

### Why the declaration names EDGES and not CHAINS

The first draft of this canon named whole chains —
`[net_revenue__by__store, store__trades_in__country]`. **Measured, that is wrong in two ways.**

**It does not scale.** Three edges terminate at Country; **thirteen** first hops of the two kinds exist
(`discount__by__customer`, `discount__by__store`, `gross_revenue__by__…`, `margin__by__…`,
`net_revenue__by__…`, `order__placed_by__customer`, `sales_cost__by__…`, `units_sold__by__…`). A
chain-based params block needs an entry per measure per reading, and must be edited whenever a measure
or an edge is added or renamed. An edge-based one is **three entries**, intrinsic to Country, and adding
a measure never touches it.

**And it would encode a path that does not exist.** `Order` has `order__placed_by__customer` and **no
store edge at all**. A chain declaration would assert a store chain for Order that cannot be built. An
edge declaration cannot make that mistake: when only one of the three is reachable there is no choice,
the canon resolves it and says nothing.

The first hop is not a decision. It is forced — it is the measure's own edge to its dimension. **The
only decision is the last hop into the target**, and that is what the params name.

### Why the concept and not the edges

A `default: true` flag on `store__trades_in__country` is the obvious alternative and it fails three
ways. The default is **conditional** — *a sales question* means the store — and an edge has nowhere to
state a condition. The **surfaces**, which let a reader name the other readings on purpose, have nowhere
to live. And each of the three edges would have to know about the other two. The concept is where
competing readings meet, which is where all four members of this family sit.

### Why the concept and not the seven measures

The fact is about Country: three relations carry its code. Declared on the measures, one fact would have
seven homes that can disagree — the defect this family exists to remove.

## Demonstration

Against contoso5's declaration above, subject `NetRevenue`:

| the question says | reachable | decision | what the answer carries |
|---|---|---|---|
| *"revenue by country"* | store, customer, location | `RESOLVE store`, `named=False` | the figures, and *"by the country the store trades in"* |
| *"revenue by customer country"* | store, customer, location | `RESOLVE customer`, `named=True` | the figures; nothing to disclose, the reader chose |
| *"revenue by store country"* | store, customer, location | `RESOLVE store`, `named=True` | as asked |
| *"revenue by site country"* | store, customer, location | `RESOLVE location`, `named=True` | as asked |

And with subject `Order`, where only the customer edge exists:

| the question says | reachable | decision |
|---|---|---|
| *"orders by country"* | customer only | `RESOLVE customer` — one path, no choice, no disclosure of a default that was never in play |

Were the `default` removed from the declaration, the first row becomes
`ASK ["customer", "location", "store"]` — the reader is asked rather than given one of three numbers.

## Where it is consulted

`planner/joins.py::resolve_join`, **before** `index.find_join_path`. The order matters: the canon
answers the cases a person has ruled on, and `find_join_path` keeps answering everything else, which is
honest, because for the rest nobody has stated a preference. The line-order tie-break is not removed —
it stops deciding questions that have been ruled on.

## It fits fewer rules than it looks like it should

Worth recording, because three other rules look like this shape and are not:

* **`net_revenue.default.revenue_means_net`** — the alternative is on **another concept**
  (`GrossRevenue`), not another relation reaching the same one. That is a concept choice.
* **`order.default.period_is_order_date`** — two **columns of the same relation**, which is
  [`column_select`](column_select.md).
* **`order.default.an_unscoped_question_covers_all_time`** — no alternative path at all; it is about the
  time **window**.

The test is sharp: `path_select` applies when **several declared edges terminate at the same concept**
and a reader's plain word does not say which.

## Determinism & honest limits (AUTHORING A5)

**Deterministic.** Pure function of its parameters and the asked word; same inputs, same decision. No
clock, no warehouse, no model.

**It does not validate the edges.** A `via:` naming an edge that does not exist, or one that does not
terminate at this concept, is a defect for the load-time reader to refuse — the canon is handed names
and trusts them, the way its twins are handed column names.

**It does not measure the readings.** That the store path and the customer path return different numbers
is a fact about the warehouse, and `check_edge_joins_measured` owns the cardinality claims on each edge.
This canon only chooses which claim the answer rests on.

**It cannot rescue an unreachable reading.** If the ruled default is not reachable from the subject —
Order, above — the canon resolves what is reachable rather than refusing. A reader who asked a plain
question gets the only answer there is; a reader who asked for the store reading explicitly gets an
`ASK`, because the alternative is answering a different question silently.

**What it deliberately does not do:** rank paths, score them by length or cardinality, average two
readings, or pick between two unnamed candidates. The last is the whole point — that is what the line
order was doing.
