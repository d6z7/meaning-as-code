---
state: recorded
genre: protocol
---
# PROTOCOL — 2026-10-06 · rules as form: what was measured, what was fixed, what is owed

> **Paths in this document.** `tools/…`, `guardrails/…`, `decisions/…`, `sdk/…` and
> `mac_vocabulary.yaml` are in `meaning-as-code`. `planner/…`, `interpret/…`, `resolver/…`,
> `canons/…`, `mac_runtime/canon.py` and `mac_runtime/framework.py` are under
> `mac-platform/packages/mac-runtime/src/`. `ontology/…`, `acceptance/…`,
> `knowledge/…`, `data/…` and `references/…` are inside the bundle,
> `cap-ontology-sources/example/contoso5`. A `:line` suffix is where a measurement was read.

## The objective, and the thing nobody noticed

The operator, 2026-10-06: *"i dont want to have any rules with when then else never … except for human
readable md part that will completely translate into formal definition. any rule that does not translate
into formal composition is useless."*

**That ruling already existed, five days old, written down, and unenforced.**
`guardrails/ontology/concepts.yaml`, smell `STATE-AS-PROSE`:

> **Operator ruling, 2026-10-01: *"i believe there is no reason anymore for when then never"*.**
> *instead:* … *"Drop `when`/`then`/`never` and keep `why:` — no predicate encodes who ruled it, when,
> against what measurement."*

and, in the same entry, its own diagnosis:

> **NOT ENFORCED, AND IT MUST SAY SO.** *`check_canon_binding` is the nearest gate and does not reach
> this: it reads `realized_by` only in the DICT form … while `canonBinding` is `oneOf [canonRef,
> array]` and every population rule written so far uses the LIST form — so all three are skipped,
> silently.* **What is owed is two things in that gate: walk a list binding, and REFUSE a
> `when`/`then`/`never` sitting beside a body.**

A full session was spent re-deriving that from its symptoms. **The first thing to read, before
reasoning about a rule, is `guardrails/`** — the ruling, its measurement, and the owed work were all
there.

The guardrail also carries the argument, with a duration attached:

> *"Prose beside a body is a second home for one fact, and the prose home is the one that rots.
> MEASURED on the rule this mechanism was built for: its `never:` read "`{status_annotation}` … is
> empty on all 58 rows that never closed" — true when written, **FALSE for hours** after the operator's
> impurity fix filled one row, corrected by hand only because a human happened to re-read it. **No gate
> caught it, because there is nothing in prose to catch.**"*

## THE ONE TO READ FIRST: every measurement before `mac-platform beda501` was taken blindfolded

`framework.located()` documents four candidates, the last being *"the sibling checkout beside this
repository"*:

```python
Path(__file__).resolve().parents[4] / "meaning-as-code"
```

`parents[4]` **is** this repository's root, so that resolves to `mac-platform/meaning-as-code` — inside
it, not beside it. It has never existed. Every tool that did not set `$MAC_FRAMEWORK_ROOT` ran with no
framework, and `mac_runtime/framework.py`'s own docstring says *"ABSENT IS A STATE, NOT AN ERROR"* — true, and it
was being entered by accident, by default, in the safe-looking direction.

Same tree, same commit, the variable the only difference:

| | unlocated | located |
|---|---|---|
`check_plan_replay` | `0 gained, 58 in the floor` | `1 capability lost` |
interpreter system prompt | 18 343 chars | 19 332 |
captured intents that plan | 59 | 62 |
`axis_columns()` | `()` for **every** concept | 47 columns offered |

With no framework the role vocabulary resolves nothing, so no column is an axis: the prompt offers none
and every refusal reads *"declares no groupable column at all"*. **Any number in this session's
transcript dated before `beda501` should be re-measured before it is relied on.** The conclusions
re-checked after the fix held; the rest is unverified.

### And the capability the floor was protecting was a guess

`MQ-10` — *"Which stores closed after 2020?"* Store declares **both** `open_date` and `close_date`, and
the captured intent is `{term: Store, op: gte, value: '2021-01-01'}`: it never pinned which date. With
the framework located the planner returns a **Clarification offering both candidates**. With it absent
neither column was temporal, the ambiguity was invisible, and it produced a Plan — **it picked a date.**
Its own recorded route in `acceptance/answers` was already `refusal`, so the capture and the floor had
never agreed. The floor was re-recorded: `56 planning / 58 entries` → `62 / 65`, one loosening (that
guess) and seven tightenings (`STORE-07`…`-14`, absent → planning, invisible while nothing resolved an
axis). `check_plan_replay` now reports the identical verdict with the variable set and unset.

## Fixed this session

| what | where |
|---|---|
the sibling fallback that never fired | `mac-platform#packages/mac-runtime/src/mac_runtime/framework.py` (`beda501`) |
`check_canon_binding` read only the dict form — **11 of 11 bindings skipped, gate printed "no findings"** | `tools/check_canon_binding.py` (`fd4fdf2`) |
`_params_from_registry` read `canon.members`; the block has only `terms` — `{}` for every canon, always | `tools/canon/__init__.py` (`075199c`) |
the canon registry stale **both** ways: 7 `HOOK PENDING` labels on hooked canons, and `column_select` claiming implementation | `mac-platform#…/mac_runtime/canon.py` (`6f88c60`) |
`_WIKI` compiled and referenced only by its own definition — the `[[Concept]]` half of a coverage claim had no code | `tools/check_concept_narrative.py` (`17b4e75`) |
`check_canon_implemented` asked only whether a canon was written, never whether anything calls it | `tools/check_canon_implemented.py` (`98c2e9e`) |
the behavioural freeze, and its environment pin | `tools/check_rule_baseline.py` (`9ffe7a5`, `f14fa41`) |

## Measurements that stand

**Nothing reads `when:` or `then:`.** Zero occurrences in the runtime. `never:` is read only by
`interpret/prompt.py`, which sends every clause to the model verbatim: **675 chars over 12 clauses in a
19 293-char prompt — 3.5 %, the smallest ontology-prose slot.** `concept.definition` (3 blocks) plus
`contract.default_reading` is **twelve times** bigger.

**`then:` appears on exactly the unbound rules and on none of the bound ones.** It is not prose that
happens to be there; it is the placeholder for a missing mechanism, every time.

**5 of 16 registered canons are inert.** 11 reachable from `plan()`; `column_select` reachable only
through `planner/columns.py`, which **nothing imports**, where its two twins are imported by `planner/plan.py`;
and `alias_resolve`, `densify`, `hierarchy_rollup`, `scoped_latest` referenced nowhere outside their own
files. `column_select` is the canon built on 2026-10-05 **specifically to replace prose**, and its two
contoso5 bindings decide nothing.

**Three gates stayed green on a bundle with all 30 directives deleted** — `check_concept_narrative`,
`check_canon_binding`, `check_prose_moved` — because `ontology/concepts/*.md` and `rules/*.md` are
*generated from the YAML being checked* by `sdk/project/mac_okf.py`, which rmtree's the rules subtree
first. Coverage was true by construction. Held against the **authored** plane, `knowledge/`, which that
gate does not open: **59 of 112** columns mentioned, **0 of 20** rule ids.

**The prose problem is already largely solved and the plan for it is stale.** `check_prose_ratio`
measured 2.05x overall with 9 031 comment bytes on 2026-10-05 morning; it is now **0.51x with 0 comment
bytes**, worst concept 2.28x against 8.00x. And `knowledge/` is already the authored home — 17 pages,
three commits, and `knowledge/country.md` opens with the operator's own workflow: *"The human account.
The declaration is `ontology/concepts/country.yaml`; read this first, whole, then compare it against
that file."*

**A confirmed ruling is inverted on every country question.**
`country.default.a_sales_question_means_the_store_country` is `confidence: C`, ruled 2026-09-30, and says
a sales question means the country the **store** trades in. All seven measures take the **customer**
path. Both paths are two hops, so the graph ties, and `ontology/graph.py` breaks it with unweighted BFS
over an adjacency built in `edges.yaml` **declaration order** — `net_revenue__by__customer` at line 276,
`net_revenue__by__store` at 289. The rule's own `why` records the cost: Germany 2025 growth **+18.07 %
through the customer, +49.65 % through the store**, because the store path excludes the online channel
and online is 40 % of net revenue. Re-verified after `beda501`; it is graph traversal and independent of
role resolution. `acceptance/rule_baseline.json` pins the **11 affected questions**, so the fix arrives
as 11 reviewable `[edges_used]` diffs rather than a silent change in published numbers.

## The rule corpus: 24 → 19

Five retired and one converted, each against a declaration that already runs:

| rule | why it went |
|---|---|
`brand.resolution.by_grouping_products` | `columns.brand` carries `identity: canonical` + `register:`, which `resolver/registers.py:447` synthesises into a live `enum_from_register` binding (loaded, 11 rows) |
`brand.exclusion.is_not_manufacturer` | the data refuses its premise: 11 brands, 11 manufacturers, **6 byte-identical, 5 differing only by a corporate suffix, 0 with a different stem**. Manufacturer is the registered name of the same companies, which is what `rulings: {label_of: brand, register: legal}` already declares and `planner/sql.py:1288` already runs |
`customer.ambiguity.as_of_now_or_as_of_sale` | asked to filter `valid_from`/`valid_to`, both `role: housekeeping`, whose vocabulary term declares `query_use: []` and *"not filtered on"*. And `dim_customer` is 104 990 rows over 104 990 distinct keys — no version to choose |
`color.ambiguity.blue_is_spelled_twice` | the register pins 16 members; the concept grounds only to the served relation; the one live hazard is already in `color.resolution`'s `never` |
`order.resolution.by_grouping_its_lines` | `cell_key == ('order_key',)`; the raw `orders` landing is in no grounding, and `DQ-ORPHAN-ORDERS` carries the `why` |
`product_category.ambiguity.which_level` | **converted** to `column_select` — and see above: that canon is inert, so it currently decides nothing |

Of the 19 remaining, **11 carry a canon body and 8 are prose only.** Those 8 cannot comply with the
objective until a mechanism exists: their prose *is* the rule.

### The v0.1.17 ask is WITHDRAWN

Mid-session this record's author proposed relaxing `mac.schema.json`'s *"a rule is either WRITTEN or
BOUND — never neither"* so a `never`-only rule could validate. That was wrong. The three rules it was
for forbid reaching `main.product."Color"`, the raw `orders` landing, and `CategoryKey` — **none of
which is a declared relation or column**, and the planner can only name what the grounding declares. They
are unenforceable *and* unviolatable, so they retire whole, and the clause needs no change.

## Owed, with the decision each needs

| | owed | needs |
|---|---|---|
1 | **`path_select`** — a canon choosing between declared edge chains, consulted in `planner/joins.py` before `find_join_path`. 38 edges carry **0** defaults. This is not cleanup; it is a wrong published number | operator yes — a new canon is a framework extension |
2 | **the `column_select` planner hook** — wiring a canon that is declared, tested and inert | operator yes; it is a behaviour change |
3 | **the four fully inert canons** — wire them, or move them to `KNOWN_UNIMPLEMENTED` and stop claiming them | operator yes |
4 | **the prose renderer: 3 of 22.** `population_select`, `ratio_select` and `column_select` — the three contoso5 binds most — exist in neither MAC registry, so `check_canon_binding` can hold **0 of 11** bindings against their canon | — |
5 | **brand's edge has no `resolved_by`** — the one validator finding this session added (16, of which 15 pre-date it). `mac.schema.json allOf/3` requires it of a `business`/`shared_attribute` edge; the retired rule was the anchor. The operator's position: an edge should never point at a rule | operator yes |
6 | **`grounding.grain`** — written by **17 of 17** concepts, and `Grounding` has **no such field**. The meaning plane publishes `grounding.note` under the label *grain* | a ruling: give it a reader, or stop requiring it |
7 | **`rulings.evidence` is never resolved** against `issues[].id`, so `evidence: DQ-MADE-UP` loads and refuses citing nothing. **3 of 10** register ids are cited by anything; 7 by nothing | — |
8 | **the translation gate** must point at `knowledge/` and refuse a projector-written directory. `knowledge/store.md` already invented the mechanism by hand — a *"Where each fact is declared"* table of claim→address pairs, on **1 of 17** pages | a ruling on the claim-register shape |
9 | **`check_delivery_consistency`'s `REGISTER-ORPHAN` fails 17 of 17** — it wants a descriptor-column pointer where the column standard puts it on the concept's column. A 100 % failure rate is an instrument, not 17 defects | — |

## How to work on this safely

`tools/check_rule_baseline.py` freezes five artefacts — per-question behaviour (outcome, SQL, params,
`edges_used`, `rules_used`, caveats, refusal text), the prompt by digest, the generated rule pages, the
meaning plane's rows, and the environment — and compares. `check_plan_replay` reports a capability
*lost*; this reports one **changed**, which is the class a rule migration risks and the class that hid
the Country inversion.

Its `--self-test` deletes all directives on a copy, re-projects, and **requires the gate to go red**.
That mutation is the one that left three existing gates green, and it found two bugs in this harness on
its first two runs: a page assertion that tested nothing because the mutation never re-ran the
projector, and two in-process captures that both reported the *pre*-mutation state because something on
the register path caches parsed YAML by path. It now drives the CLI in fresh subprocesses.

**And set `$MAC_FRAMEWORK_ROOT`, or confirm the fix above is in your checkout.** A degraded freeze looks
healthy: 59 planned instead of 62, a 989-char smaller prompt, and no error anywhere.
