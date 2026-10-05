---
state: proposed
genre: proposal
---
# PROPOSED — 2026-10-05 · separating prose from the formal declaration

> **Paths in this document.** `ontology/…` and `data/…` are inside the bundle
> (`cap-ontology-sources/example/contoso5`); `tools/…`, `guardrails/…` and `reference_manual/…` are
> in `meaning-as-code`; `packages/…` is under `mac-platform`. A `:line` suffix is the line a
> measurement was read at.

## The complaint, and the measurement that confirms it

The operator, 2026-10-05: *"some of them which were heavily worked on have 2x more prosa then the
fomal text. this is unreadabl for human … when i am reading prosa i make myself opionion not as each
line translates into something but how the whole something work … then i compare yaml formal format
with my understanding of the rule. the way how it is now … it is hardly possible."*

Measured across contoso5's 17 concepts by `tools/check_prose_ratio.py` (Phase 0, now written),
counting YAML comment bytes, long-scalar prose bytes, and structural bytes separately. The figures
below are the TOOL'S, which supersede the throwaway script this record first quoted — it counted
list-item keys slightly differently and read 94 bytes more as formal:

| concept | comment | prose | formal | prose+comment : formal |
|---|---|---|---|---|
| `store` | 6 042 | 7 776 | 1 728 | **8,00x** |
| `country` | 911 | 4 847 | 1 075 | **5,36x** |
| `order` | 0 | 5 010 | 1 477 | **3,39x** |
| `brand` | 282 | 1 542 | 1 033 | 1,77x |
| … | | | | |
| `sales_cost` | 0 | 279 | 1 041 | 0,27x |
| `gross_revenue` | 0 | 264 | 1 052 | 0,25x |
| **TOTAL** | **9 031** | **31 847** | **19 926** | **2,05x** |

Three facts follow, and the plan is built on them:

1. **The claim is exact.** 2,05x, against a stated 2x.
2. **The damage concentrates where the work went.** `store`, `country` and `order` carry **60 %** of
   all prose in the bundle. The concepts nobody has fought over sit at **0,25x** and read fine — so
   0,25x is a demonstrated floor, not an aspiration.
3. **9 031 bytes are YAML comments**, 6 042 of them in `ontology/concepts/store.yaml` alone. A comment is prose with no
   reader: not data, not projected, unreachable from every gate, and impossible to compare against
   anything.

## What this is really for, and why it is not a readability preference

The operator's workflow is a **verification**: read the prose as a whole to form a view of what the
rule does, then read the formal notation and compare. Interleaving does not merely make that
unpleasant — it makes it infeasible, because neither half can be read as a whole.

That same check exists mechanically. `tools/check_canon_binding.py` holds a bound rule's prose against
what its canon renders, by MEANING rather than string similarity — measured across thirteen copies of
one law, string fit was 0,88 while meaning was preserved 13 of 13. It covers **3 of 21** canons. So a
person is performing by hand, across every concept, the check that exists for three canons.

## The design, as agreed

The framework already drew the line this rests on. `reference_manual/rules_and_canons/the_content_model.md`
§2 asks one question of every slot — *"if two competent models read this slot, could they produce
different query behaviour?"* — and sorts the answers into **skeleton**, **UDF**, **behaviour-bearing
prose** (*"the danger zone; it needs a UDF seam"*) and **pure prose** (*"it drives no behaviour, only
informs a human — leave it; this is the good prose"*). It names `definition`, `purpose`, `closure_why`
and *"every `*_why`"* as pure prose. **Pure prose is the half with no discipline at all**: nothing
bounds it, nothing homes it, no gate reads it.

| artifact | home of | read |
|---|---|---|
| `ontology/concepts/<concept>.md`, `ontology/concepts/rules/<rule>.md` | the **authored narrative** — what this concept is, what the rule does, continuous prose | **first**, as a whole |
| `ontology/concepts/<concept>.yaml` | the **formal declaration** — skeleton, bindings, parameters, a one-line `why` | **second**, compared against that view |

**The narrative files already exist**: 17 concept pages and 24 rule pages under
`ontology/concepts/rules/`. They point the wrong way — `ontology/concepts/net_revenue.md` repeats `concept.definition`
verbatim, so each is a *projection of the interleaved prose* rather than the prose's home. The change
is a direction reversal, not new machinery.

### Ruled out, deliberately

* **No generated or composed page.** Operator, 2026-10-05: *"exception: the generated page — for the
  momemt i would not do it."* The composer would serve a reader who has both files open anyway.
* **No split of rules out of the concept file.** A split separates by LOCATION; this problem is one of
  KIND, and a file boundary does not distinguish a typed `class:` from a three-paragraph `definition:`.
  It also costs the adjacency that makes `binds` resolvable against the concept's own declared
  columns — the check that caught `net_price` sitting in a ratio rule's `binds`, where it was the
  column the rule FORBIDS.

### How the pair stays true

Both artifacts are produced in one act, from the VS Code + LLM dialog; a change touches both. That is
a property of the FIRST WRITE and not of the pair over time, so two gates hold it:

* **pairing** — a concept with no narrative, or a narrative with no concept, fails.
* **coverage, both directions** — every rule id and declared column in the YAML is mentioned in the
  narrative; every column and `[[Concept]]` the narrative names exists in the YAML. Coverage, never
  string similarity, for the reason `check_canon_binding` records.

A model producing both artifacts makes these matter MORE, not less: measured in the PCA spike, **6 of
59** generated rule functions invented a `raise` their source rule never had. Two artifacts can agree
with each other and both be wrong.

**And the YAML must actually be emptied.** Our split is defensible only because the two artifacts hold
different content. A YAML that keeps `definition` as a paragraph while the narrative also carries it
is one fact in two homes — the defect this estate keeps removing, at a count of two.

## Execution

### Phase 0 — make the measurement a tool (half a day, no bundle change)

`tools/check_prose_ratio.py` — the table above, re-runnable, per concept, with `--self-test`.

* It reports the ratio and PRINTS THE DENOMINATOR. A gate with no denominator is the failure this
  estate names most often.
* **No threshold yet.** It exits 0 and reports. The threshold is set from the corpus after Phase 2,
  not from taste.
* **DONE** — written, `--self-test` 8/8 over 4 measurement classes, and it reproduces
  2,05x / 8,00x / 0,25x. It refuses rather than reporting 0,00x over an empty population, and it
  discovers concepts through `mac_project.concept_files` rather than a glob, for the reason
  `check_canon_binding` records: a hand-written glob "measured ZERO on every foldered bundle and
  printed a clean verdict".

### Phase 1 — the two gates, against today's tree (1 day)

A second new gate, proposed and not yet written — `tools/check_concept_narrative.py`, three
reject classes:

| reject | fires when |
|---|---|
| `unpaired-concept` | a `*.yaml` under `ontology/concepts/` has no `*.md` beside it, or the reverse |
| `uncovered-declaration` | a rule id or declared column in the YAML appears in no narrative |
| `phantom-reference` | a column or `[[Concept]]` the narrative names is not declared |

Run it BEFORE moving any prose, and **record what it finds on the current tree**. If today's generated
pages already fail coverage, that is a finding about the projection and belongs in the record.

* `--self-test` with one mutant per reject class, per the suite's contract.
* Exit criterion: green on today's tree, or its failures declared with an owner.

### Phase 2 — the pilot: `store`, `country`, `order` (1–2 days)

60 % of the prose, and enough to know whether the split delivers the workflow before fourteen more
files move.

Per concept, in one VS Code + LLM act:

1. Comments out of the YAML wholesale — 6 042 bytes in `ontology/concepts/store.yaml` alone, read by nothing.
2. Long `definition` / `doc` / `notes` paragraphs into the narrative; **one sentence stays** in the
   YAML. contoso5's own `ontology/concepts/net_revenue.md` frontmatter already carries that sentence form.
3. `why:` to one line per rule; the argument moves to `rules/<id>.md`.
4. The narrative becomes AUTHORED — continuous, read end to end, not a field dump.
5. Both gates green; the ratio recorded before and after.

**The operator reads the three narratives and then the three YAMLs, and says whether the comparison
is now possible.** That judgement is the phase's exit criterion — not the ratio, which is a proxy for
it.

### Phase 3 — set the threshold, then the remaining fourteen (2–3 days)

* Set the ratio gate's threshold from the pilot's achieved numbers against the 0,25x floor.
* Convert the remaining fourteen. They are small: eleven are already under 1,8x.
* Exit criterion: ratio gate green bundle-wide at the declared threshold, both narrative gates green,
  and the full suite's red list IDENTICAL to `develop` — measured both ways by stash, as every change
  in this session has been.

### Phase 4 — the one thing that makes the prose unreachable at execution (deferred, needs its own ruling)

Extend the canon prose renderer past 3 of 21 and point the interpreter prompt at the RENDER rather
than at `rule.never`. **Deliberately not in this plan**, because `interpret/prompt.py:450` sends
`never:` clauses to the model on purpose — *"until now the model never saw one — the runtime enforced
them AFTER an intent was formed, so a question could only be rescued by a refusal it had already
earned"* — and changing what reaches the model changes answers. It is a separate record.

## What this plan does NOT fix, stated plainly

* **Parameters remain unvalidated.** 13 of 18 implemented canons have no authored-parameter reader,
  and NO gate measures a parameter against the data. Separating prose makes the formal half readable;
  it does not make it correct.
* **L2 is untouched.** Nothing here reaches a person typing a question. That remains the standing
  bottleneck.
* **The ratio is a proxy.** A YAML can hit 0,25x and still be unreadable. The operator's read-then-
  compare judgement in Phase 2 is the real test; the gate only stops regression.

## Risks

| risk | why it is real | what contains it |
|---|---|---|
| the narrative becomes a field dump | it is what the generated pages are today | Phase 2's exit criterion is a person's judgement, not a ratio |
| prose is moved and silently lost | 9 031 bytes of comments have no reader to miss them | coverage gate, both directions, before and after |
| the pair drifts after the first write | one artifact edited alone, which will happen | the pairing and coverage gates are Phase 1, BEFORE any prose moves |
| the ratio gate is gamed by shortening good prose | shorter is not the goal; separation is | the threshold is per concept and set from the achieved corpus, and the narrative has no cap at all |

## Owed before Phase 2 starts

* **Operator ruling on this record.** Phases 0 and 1 add tools and change no bundle content, so they
  can begin on the strength of the agreement already given; Phase 2 edits the ontology plane.
* **contoso5 currently carries another session's uncommitted work** — `ontology/concepts/brand.yaml`, `ontology/concepts/color.yaml`,
  `ontology/concepts/currency.yaml`, `ontology/concepts/discount.yaml`, `ontology/concepts/exchange_rate.yaml`, `ontology/concepts/gross_revenue.yaml`, `ontology/concepts/margin.yaml`,
  `ontology/concepts/net_revenue.yaml`, `ontology/concepts/product.yaml`, `ontology/concepts/product_category.yaml`, `ontology/concepts/sales_cost.yaml`, `ontology/concepts/units_sold.yaml`
  on `bundle/column-first-declarations`. **None of the three pilot files is among them**, which is
  partly why they were chosen, but Phase 3 collides with all twelve and must wait for that branch.
