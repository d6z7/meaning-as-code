---
title: "Pattern — Impurity disposition (bake / register / block) — partial: edges canon-able, curation-layer deferred"
part_of: reference_manual/patterns
status: gap   # the FRAMEWORK PRIMITIVE (curation layer + typed DQ register) is deferred; the query-time edges are canon-backed
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (illustrative shop scenario).
---

# Pattern — Impurity disposition  🟡 *edges canon-able; the curation-layer abstraction is the residual gap*

> This entry documents a **frontier that is now partly built** — which is why it is 🟡, not 🔴. The query-time
> *edges* of the disposition are canon-backed: [`exclusion_filter`](../canon/exclusion_filter.md) realizes the
> **bake** exclusion, and abstaining on a NEEDS_SME flag realizes **block**. What remains a genuine framework
> **gap (🔴)** is the *abstraction itself* — two primitives, both deferred (COOKBOOK B8):
>
> - a first-class **curation layer** — baking the fix into the served *view*, so the ontology describes a
>   clean state (`exclusion_filter` does it at *query time*; the framework's intended home is the view); and
> - a **typed data-quality register** — the home for the **register** caveat and the NEEDS_SME flag.
>
> And the disposition *choice* — judging how separable an impurity is — is SME judgement, irreducibly prose.
> So: the pattern is recognized and partly canon-able; the framework *primitive* is the residual 🔴. Writing
> that distinction down honestly is itself part of the manual's contract (Ch.01 §4; AUTHORING A5).

## Initial state — what you're handed

You query the `product` table to answer "how many products do we sell?" and find non-products mixed in:

```sql
SELECT product_id, name FROM product;
```

| product_id | name |
| --- | --- |
| P-100 | Trail Mug |
| P-TEST-09 | (QA test fixture) |
| P-MISC | Miscellaneous / Other |
| P-200 | Alpine Jacket |

**Why this is dangerous.** A `COUNT(*)` returns **4**, but two rows are not sellable products: `P-TEST-09` is
a QA fixture, and `P-MISC` is a catch-all bucket. The impurity is *real* — you cannot pretend it away — and,
crucially, **how to handle it depends on how reliably you can tell junk from valid data**, which is not
always decidable from the rows alone. `P-TEST-09` is obviously a fixture; is `P-MISC` a data artifact, or a
real "miscellaneous" line customers actually buy? You may not know.

## The question, and the answer

> **The question** (what the data can't tell you): *This value is impure — can the impurity be removed
> reliably, only partially, or not without a human?*
>
> **The answer** (the **disposition** we choose): *one of three — (1) reliably separable → **bake** the fix
> into the served view; (2) partially separable → fix what you can and **register** the residual as a
> caveat; (3) not separable without domain knowledge → **block** the affected question and escalate
> (NEEDS_SME). Choosing among them is the disposition — and the framework only partly supports it yet.*

## The pattern (the structured entry)

```yaml
pattern: impurity_disposition
also_known_as: [data-quality disposition, cleanse-vs-caveat-vs-block, curation decision, raw→curated normalisation]
tradition: cross-cutting   # the framework's frontier — a deliberately deferred abstraction
constellation: >
  The served data carries a KNOWN impurity (test / rollup / unmapped rows, rebadged codes, miscaptured
  values), and the modelling decision is not "what IS this" but "what do we DO about it" — and the right
  action depends on how reliably the impurity can be separated from valid data.
prior_art:
  relational: >
    A `WHERE` filter someone remembers to add — or doesn't. The impurity is undocumented and re-discovered
    per query; the residual uncertainty ("we catch most test SKUs, not all") is recorded nowhere.
  dimensional: >
    A cleansing step buried in the ETL pipeline. The rule lives in pipeline code; what it FAILS to clean is
    usually invisible downstream, so a partially-cleaned number is presented as if it were clean.
  rdf: >
    Generally assumes clean input. No native notion of "this is impure, and here is our disposition."
mac_expression: >
  THREE dispositions, chosen by how separable the impurity is:
    (a) reliably separable     → BAKE the fix into the served view (an `exclusion` rule realised in the
                                 view); the ontology then describes the CLEAN state, no query-time workaround.
    (b) partially separable    → fix what is possible AND REGISTER the residual in a data-quality register
                                 as a caveat the consumer inherits (the number is "clean to within X").
    (c) not separable w/o SME  → BLOCK: abstain on the affected question and escalate (NEEDS_SME) rather
                                 than return a confident wrong (or falsely-clean) number.
  HONEST LIMIT: today the framework gives only PARTIAL tooling for this — `open_questions` + rules +
  scope/closure honesty (MODELLERS_COOKBOOK B8). A first-class CURATION LAYER and a typed data-quality
  register are DEFERRED until the impurity catalogue is large enough to design the abstraction from pattern
  rather than from a handful of cases. This is the known frontier, not a finished primitive.
why_better: >
  Even partially, making the disposition EXPLICIT — and forcing the honest third option (block + escalate) —
  beats the alternatives' silent-WHERE-or-not. The target state: a consumer always knows whether a number is
  clean, caveated, or unanswerable, instead of receiving an inflated count with no signal. The framework
  states plainly where that target is not yet reached.
projects_to:
  rdf: "data-quality / provenance annotations (when built)"
  graph: "a quality / confidence property on the node (when built)"
  relational: "a curated view + a data-quality register table (when built)"
antipattern: >
  Silently adding (or forgetting) a cleansing `WHERE`; presenting a caveated number as clean; 'fixing' impure
  data inside the concept DEFINITION instead of recording the disposition; treating an undecidable case as if
  it were decidable (skipping the block/escalate option).
status: gap   # the disposition SHAPE is described; the curation layer + typed DQ register are not yet framework primitives
canon_ref: [MODELLERS_COOKBOOK.md B8 (curation-layer scope note), CONCEPT_SPEC.md §6 (open_questions / scope / closure)]
```

## The determinism border

Per [AUTHORING.md](../AUTHORING.md) A4 — this is the pattern whose border sits **mostly on the prose side, by
nature**. That is not a failure to canonize; it is the honest shape of a frontier (`status: gap`).

| Behaviour | Kind | How |
| --- | --- | --- |
| Choosing the disposition (reliably / partly / not separable) | **prose-fallback** (SME judgement) | irreducibly human — the framework does not pretend otherwise |
| Excluding *reliably-identifiable* junk (the **bake** disposition) | **canon-backed** | [`exclusion_filter`](../canon/exclusion_filter.md) |
| Abstaining when an impurity is flagged unresolved (the **block** disposition) | **canon-backed** (given the flag) | flagged NEEDS_SME → return ⊥ is deterministic |
| The residual caveat (the **register** disposition) | **data, not query-behaviour** | attached to the result ("clean to within X") |

Only the *mechanical edges* canonize — apply a known exclusion, abstain on a set flag. The **core** —
judging how separable an impurity is — is SME work, and forcing it to be *explicit* (not a silent `WHERE`)
is the win available even before the curation layer exists. A pattern's border is allowed to be mostly
prose; what is **not** allowed is pretending that prose is deterministic. The determinism-coverage metric
([content model §6](../the_content_model.md)) simply reports this pattern low — honestly.

## The footgun, concretely

```sql
-- Q: "How many products do we sell?"
-- GUESS (plausible, and wrong): counts everything in the table
SELECT COUNT(*) FROM product;        -- 4  — includes the QA fixture and the Misc bucket  ❌
```

The grounded answer depends on the **disposition**, and the manual's point is that *the disposition is the
modelling act*:

| Disposition | Result | What the consumer is told |
| --- | --- | --- |
| **bake** (P-TEST-* reliably excluded in the view) | `COUNT = 3` | a clean count; the fixture never appears |
| **register** (Misc partly identifiable) | `COUNT = 2` real + caveat | "≈ 2, up to 1 ambiguous bucket row pending review" |
| **block** (P-MISC status undecidable w/o SME) | abstain / ranged answer | "the exact count is NEEDS_SME — `P-MISC` unresolved" |

The wrong move in every prior tradition is the same: return `4`, silently, as if it were clean. The right
move — even before the full curation layer exists — is to make the disposition, and any residual doubt,
*visible*.
