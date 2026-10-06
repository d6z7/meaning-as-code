---
state: ruled
genre: ruling
---
# RULING — 2026-09-30 · an unqualified sales question means the country the STORE trades in

> **Paths in this document.** `ontology/…`, `data/…` and `acceptance/…` are inside the bundle
> (`cap-ontology-sources/example/contoso5`); `tools/…` and `reference_manual/…` are in
> `meaning-as-code`; `planner/…` is under `mac-platform/packages/mac-runtime/src/mac_runtime/`.
>
> **Ruled 2026-09-30. Written up 2026-10-06**, when the slot to cite it from was built — until then
> this ruling existed only as a sentence inside the rule it produced.

## The question put

`country_code` is carried by **three** relations. So "revenue by country" is three questions, and
nothing in the figure says which one a reader was handed:

| relation | the question it answers |
|---|---|
| `dim_store` | where we TRADE — the shop the sale happened in |
| `dim_customer` | where our CUSTOMERS are — the buyer's home |
| `dim_location` | the geography of a SITE, which is about places rather than trade |

## What was measured before ruling

The readings do not differ by a rounding. The online store is a sentinel row — `location_code = -1`,
`country_code = '--'` — belonging to no country, so **the store reading excludes the online channel
entirely**, and online is **40 % of net revenue**.

On Germany's 2025 growth: **+18.07 % through the customer, +49.65 % through the store.**

## The ruling

**Both readings are legitimate for sales.** An unqualified sales question means the country the
**STORE** trades in. The customer reading is reached by NAMING the customer — *"revenue by customer
country"*, *"where our customers are"* — never by guessing. The location reading answers questions
about places.

**And every answer that groups or filters by country must disclose which path it took**, because the
reader cannot tell from the number which of the three they were given.

Ruled by the operator. The rule it produced carries `confidence: C` for that reason.

## Alternatives weighed, and why they lost

| | |
|---|---|
pick the customer reading as default | it is the larger population, and it is not what a sales question is about; the store reading is the one that answers "where did we sell this" |
average the two | arithmetic over two different questions. The rule's `never:` forbids it in as many words |
refuse an unqualified question | correct where nobody has ruled, and wasteful where somebody has. The default exists so the common question is answered, and the disclosure exists so the reader can tell |
leave it to the shortest join path | **this is what was happening, and it is what the ruling exists to stop.** See below |

## What this ruling produced, and the six days it took to produce it

**The rule:** `country.default.a_sales_question_means_the_store_country`, on
`ontology/concepts/country.yaml`, binding `country_code`.

For the first six days it was **prose that nothing read**. `when:` and `then:` have zero readers in
the runtime; only `never:` reaches the model, as text in the prompt; and the intent the model produces
has **no field for a join path**, so the instruction was unfollowable rather than disobeyed.

`Graph.find_join_path` decided instead: unweighted breadth-first search returning the first shortest
path, over an adjacency built in `edges.yaml` **declaration order**. Both candidate paths are two hops,
so the tie broke on a line number — `net_revenue__by__customer` at 276 against `net_revenue__by__store`
at 289 — and **all seven measures took the customer path**, the opposite of this ruling, on every
country question, for six days. `check_plan_replay` reported `0 gained` throughout and was correct:
nothing was lost. The answer was wrong.

**2026-10-06 — the ruling became executable.** `mac.canon.path_select` was built for it
(`reference_manual/rules_and_canons/competing_definitions/path_select.md`), the rule now binds it, and
`planner/joins.resolve_join` consults it before `find_join_path`. Measured after binding: all seven
measures take the store path, and `check_rule_baseline` reported the change as **47 differences over
10 questions** rather than letting it happen quietly.

## What is still owed against this ruling

1. **The disclosure.** The ruling requires every country answer to say which path it took. The canon
   flags `by_default` for exactly that and `JoinPath` is a frozen dataclass of concepts and edges with
   nowhere to carry it. **Not done.**
2. **ADV-09** — *"Countries where average order value exceeds 500"* — still answers through the
   customer. Its intent is `subject: Country` with the measure in a `having` clause, so Country is the
   ANCHOR and not the target, and the hook looks up the target's declaration. One sales question in
   eleven still disagrees with the other ten.
3. **`location`** is declared as a reading with surfaces and has never been asked for. That is fine —
   a declared reading nobody uses is a reading available, not a defect — but it is unexercised.
