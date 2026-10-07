---
state: recorded
genre: protocol
---
# PROTOCOL — 2026-10-05 · removing the pre-column standard: what is done, what is owed

> **Paths in this document.** `planner/…`, `ontology/…`, `canons/…` are under
> `mac-platform/packages/mac-runtime/src/mac_runtime/`; `packages/…` is under `mac-platform/`;
> bare paths are in `meaning-as-code`; `ontology/concepts/…` inside a bundle is
> `cap-ontology-sources/example/contoso5`. A `:line` suffix is where a measurement was read.

## The objective, in the operator's words

> "we have established column base logic recently on contoso5 … this one obsoletes many previous keys
> and patterns. objective is to take the last one from contoso5 on column base and check what
> everything can be deprecated and removed from the previous work. **we cannot have two standards and
> cannot stay in the vocabulary** … because next time you will start doing new ontology you will most
> likely see old definitions and then do what we dont want."

So contoso5 is the measuring stick. The question is NOT "which keys does contoso5 not use" — that sweeps
in other planes and shapes it has not reached. It is: **which declarations are the pre-column way of
saying something contoso5 now says on the column, and are they still visible to whoever authors next?**

## DONE — contoso5 is column-only

`cap-ontology-sources` `1e562e3` on branch `bundle/column-first-declarations`. **This repository has no
remote; the commit exists on this machine only.**

| removed | from | replaced by | uses of the replacement |
|---|---|---|---|
| `grounding.sources[].key` | 4 concepts — brand, color, currency, product_category | `columns.<n>.identity: canonical` | 50 |
| `concept.semantics.unit` | product | `columns.<n>.measure.unit` + unanimity | 14 |
| `concept.semantics:` (empty key) | 7 concepts | — | — |

All four `key:` entries agreed with the column that already declared `identity: canonical`, so the grain
had two homes that could disagree. `PROPOSED-2026-10-02_column-first-declarations` measured 38 of 38
agreeing and removed `key:` from 17 concepts; **these four were missed**, which is worth knowing because
that record reads as complete.

**Verified, not assumed:** 17 of 17 concepts load; Product resolves `unit=USD` with `canonical=None`;
every measure concept resolves unit and type from its columns; `check_plan_replay` 0 gained over 58 in
the floor, so **no plan changed**; `validate_schema` 14 errors before and 14 after.

## DONE — the parser change that made Product's removal possible

`mac-platform` `b9fac01`. `ontology/parser.py::_column_measure` now resolves a multi-carrier concept's
unit by UNANIMITY when the carriers agree, which is the rule `measure_type` and `additivity` beside it
already use. The refusal survives for a genuine DISAGREEMENT and now names `measure.canonical` as the way
out instead of the concept-level slot.

Why it was needed: Product is a `reference` concept with `list_price` and `list_cost` both intensive USD
and neither canonical — no column IS the concept's number, so `canonical` could not settle it. That made
`semantics.unit` load-bearing on exactly one concept. The one case that genuinely needed a composed unit
(four carriers, three units) was tpch's `revenue`, and that bundle was removed 2026-10-04.

Suite 1850 passed. One test's premise was wrong and is re-made: it asserted `Net: USD` + `Gross: USD`
were refused, which cannot be order-dependent.

## OWED 1 — `concept.semantics` is REQUIRED and nothing can satisfy it

The sharpest finding, and it is in the schema, not the bundle. `mac.schema.json`
`#/$defs/ConceptFile/properties/concept/properties/semantics` → `$ref: #/$defs/semantics`, defined at
**`mac.schema.json:181`**, with five keys: `additivity`, `axis_kinds`, `measure_type`, `purpose`, `unit`.
It is listed in that block's `required`.

`validate_schema` on contoso5, before and after the cleanup:

```
BEFORE  discount.yaml  @concept/semantics: None is not of type 'object'
AFTER   discount.yaml  @concept: 'semantics' is a required property
```

**Invalid in both directions.** An empty key fails as a non-object; its absence fails as a missing
requirement. contoso5 has been failing validation on this block the whole time, and the seven empty keys
existed to satisfy a requirement with nothing in it.

Measured usage across contoso5's 17 concepts, before the cleanup: `additivity` 0, `axis_kinds` 0,
`measure_type` 0, `purpose` 0, `unit` 1. Against column homes: 112 `role`, 50 `identity`, 39 `axis`,
14 `measure.type`, 14 `measure.unit`, 11 `rulings`, 5 `register`, 3 `measure.canonical`.

**The replacement for each, and why it is a replacement rather than a move:**

| key | replaced by | note |
|---|---|---|
| `measure_type` | `columns.<n>.measure.type` | on a multi-measure concept it was a DISAMBIGUATOR, read by `planner/grounded_columns._by_declared_measure_type`; `measure.canonical` now states it directly |
| `unit` | `columns.<n>.measure.unit` + unanimity | done, see above |
| `axis_kinds` | `columns.<n>.axis` | the record measured **47 entries and the fold law read ZERO of them** — the keys were column names and the planner looked them up by a lowercased CONCEPT name, so no key could match and "a two-branch guess decided every fold in the estate" |
| `additivity` | `columns.<n>.measure.additivity`, and the LAW | the concept-level map RESTATED the law: `mac_vocabulary.yaml#concept.column.measure_type.flow.additivity` is `{time: additive, categorical: additive}`, which reproduces the hand-written `{time, customer, product}` exactly, since customer and product are categorical |
| `purpose` | `concept.definition` | `ontology/retrieval.py:62` tokenises both as separate sets; 0 of 17 wrote `purpose`, so that half scored nothing on every query |

### What blocks removal, and it is not the ontology

`PROPOSED-2026-10-02` says: *"`ConceptSemantics` is `extra="forbid"` and **13 locked files stop parsing**
if a field disappears: **deprecate, never delete.**"*

**That rule is a concession to FIXTURE bundles, not an ontology decision.** Measured 2026-10-04, the
files carrying a non-empty `semantics:` block, excluding another session's worktree:

| bundle | files |
|---|---|
| `example_shop_ontology` (meaning-as-code) | 8 |
| `packages/mac-runtime/tests/fixtures/example_shop_ontology` | 6 |
| `mac-platform/tests/fixtures/ask/ontology` | 6 |
| `sdk/authoring/exemplars/bundle` (meaning-as-code) | 2 |
| `packages/mac-runtime/tests/fixtures/column_standard_bundle` | 2 |
| `packages/mac-runtime/tests/fixtures/additivity_fixture` | 1 |
| `packages/mac-runtime/tests/fixtures/spike_meta` | 1 |
| **total** | **26** |

**26, not 13.** And `packages/mac-runtime/tests/fixtures/column_standard_bundle` is held byte-identical to
`sdk/authoring/exemplars/bundle` by `tests/test_column_roundtrip.py::test_the_hermetic_copy_matches_the_framework_fixture`,
so those two migrate together or neither.

**THE TRAP IN MIGRATING THEM, and the reason this was not attempted:** across those 26 files, **0 of 69
axis columns declare `axis`**. Dropping `axis_kinds` without authoring those 69 leaves the fold law
unconsultable for 26 concepts — `axis` absent returns None by design, never a default — so tests
asserting folds go red. And `axis` is a judgement per column, not a text transform:
`customer.yaml:created_at(dimension)` is a date and wants `time`; `customer.yaml:email(dimension)` wants
`categorical`. Inferring 69 is how a wrong `axis` silently changes a fold.

There IS a safe oracle for that migration, and it should be used: the old hand-written `additivity` maps
state what each concept's fold was. Derive `axis`, recompute the fold from
`measure_type × axis`, and require it to match the old map. The thing being deleted validates its
own replacement.

**Two of those files are ALREADY schema-invalid** and that is a separate bug introduced 2026-10-04 when
`scope` and `null_semantics` were removed from `#/$defs/semantics`: `null_semantics` is still declared in
4 fixture files and `scope` in 1. Nothing caught it because **nothing in the suite validates a fixture or
exemplar bundle against the schema** — `check_framework_selfconform` validates MAC's own files only. That
hole is owed independently of this work and is how the tpch break went unseen all day.

## OWED 2 — `values` is REQUIRED by the schema and BANNED by operator ruling

`validate_schema` on contoso5 reports, pre-existing and unrelated to the cleanup:

```
ERROR  ontology/concepts/{brand,color,currency,product_category}.yaml [ConceptFile] @(root):
       'values' is a required property
```

Those four are enumerations whose values live in registers — `columns.<n>.register` (5 uses) plus
`data/lookups/*.lookup.{yaml,csv}` — which is what the ruling requires (`values.items` is BANNED; values
live in a register and the column points at it). **So the schema requires a block the ruling forbids.**
The operator's position on 2026-10-04: *"i would approve values but only in lookups / lookup yaml is
either bounding values or csv table … depending on the size."*

`values` and its subtree is 14 declared keys written by 0 of 17.

## OWED 3 — the schema_version bump, and what it reaches

`RELEASING.md:16`: *"**Any change to `mac.schema.json`** — a new/renamed/removed key, a tightened
constraint, a changed enum — **bumps `schema_version`.**"* So removing `semantics` or `values` is
**0.1.16 → 0.1.17**, and the operator has approved the bump.

What a bump reaches, from CONFORMANCE's own release procedure: the schema `version`, the schema title and
`description`, the validator's `CURRENT`, every example's `schema_version`, and CONFORMANCE's changelog.
In the bundle, `metadata.schema_version: 0.1.16` appears on every concept file and on all 17
`*.lookup.yaml`.

**Two second homes for the version will fight the bump and should be fixed in the same change:**
`mac.schema.json`'s top-level `description` narrates *"current generation v0.1.14-develop"*, and four
pages declare their own `version:` in frontmatter (`CONCEPT_SPEC.md` 0.1.6, `shape_reference.md` 0.1.0,
`CONFORMANCE.md` 0.1.14, `SEAM_CONTRACT.md` 0.1.14). All are declared standing in
`guardrails/semantic_currency.yaml` with the ruling owed: should a page declare a schema version at all?
Recommended there, and still: drop `version:` from page frontmatter and let `mac.schema.json` be the only
home.

## OWED 4 — two vocabularies competing for one fact

`mac_vocabulary.yaml#concept.column.query_use` describes itself as *"the machine-readable half of
`concept.column.role`"*; `concept.column.role` describes itself as *"where a query may use it, and the
default guardrail."* **Two vocabularies, both claiming to say where a question may use a column.** `role`
has 112 uses in contoso5; `query_use` has **0** and **no declared slot** in
`check_vocabulary_parity.PAIRS`. This is the two-standards problem inside the vocabulary and the one
genuine case there — retiring it is small.

**Do NOT confuse it with the other unreferenced vocabularies.** Of the 15 contoso5 does not reference,
four are simply other planes (`relation.column.role`, `transform.driven_by`, `dq_status`,
`credential_mode`) and five are engine-side (`outcome_class`, `test_status`, `test_kind`,
`diagnostic_code`, `data_plane_gate`); `concept.aggregation_effect` is the fold law's OUTPUT, never
authored. Asking whether a concept references those is the wrong test, and removing them would be a
different mistake. **Only 9 of 23 vocabularies have a declared slot at all**, which is why usage counts
here must come from `PAIRS` and not from guessing a vocabulary's key from its name.

## OWED 5 — `concept.identity` is a six-term vocabulary doing a two-term job

Not superseded by the column standard — it answers a different question (`kind` = HOW identity is
established; `columns.<n>.identity` = WHICH column holds it), so it cannot be dropped. But measured:

| term | branched on | where |
|---|---|---|
| `composite` | 4 sites | `planner/plan.py:1287`, `planner/sql.py:2263,2270` — decides whether a count counts rows or things |
| `code` | 1 site | `planner/grounded_columns.py:522`, and only for a MEASURE with `canonical_key` — a shape contoso5 has **0** of |
| `fk_name` | 1 site | |
| `iso`, `namespace_code`, `sme_pending` | **nowhere** | |

And `planner/grounded_columns.py:509-528` carries this, which answers "what is `kind: code` for on Brand":

> *"A CODE THAT ENUMERATES MEMBERS IS NOT A CODE THAT DISCRIMINATES MEASURES. Brand on contoso5 says
> `identity.kind: code` … and carries no measure; "what brands do we sell" was refused as a tall fact
> with no variant code (RC01, 2026-09-29)."*

So on an enumeration the declaration's only effect was a wrong refusal, and the fix was to teach the
reader to ignore it. `identity.note` (10 of 17) has **no reader**. `identity.counts_as` (1 of 17, three
readers) earns its place — an SCD-2 dimension counts versions, not things, and nothing in the result says
which. `identity.canonical_key` is read by `planner/joins.py:89,104` and written **0 of 17**.

## Also settled, so it is not re-litigated

* `properties.doc` — **no reader**. The `.doc` hits are `console_api` using `plan["doc"]` and the literal
  `".doc"` file extension. Droppable.
* `properties.value_domain` — **no reader**. The model's `value_domain` is filled by
  `ontology/parser.py:841` from `raw.get("values")` — the concept's `values:` block, a different path.
  Droppable. Operator agreed both.
* `properties.required` — operator: NO.
* `grounding` and `contract` — operator: keep. Note 14 and 6 of their keys are written by 0 of 17, so
  they are carried for shapes contoso5 has not reached.
* `constraints` — 5 keys, 0 of 17, **not yet investigated**. Readers unknown.
* The register corpus is the cleanest in the estate: `ValueRegisterFile` declares 13 keys and all 13 are
  written by all 17 lookups. What is ungoverned is the CSV half — all 17 share the header
  `<code>, label, search_key, source_view, source_schema, confidence, note` and **no schema, vocabulary
  or gate declares those seven columns**. `confidence` carries `I`, from the `[C, I, Q]` alphabet that
  exists at six schema sites and in no vocabulary.

## How to verify anything claimed here

```
# the bundle is column-only, and still plans the same
python3 tools/validate_schema.py   <contoso5>      # expect 14 findings, unchanged by the cleanup
python3 tools/check_plan_replay.py <contoso5>      # expect 0 gained over 58 in the floor
cd mac-platform && .venv/bin/python -m pytest -q   # expect 1850 passed

# the suite, against the morning-of-2026-10-04 baseline
bash tools/run_framework_gates.sh <contoso5>       # expect 13 undeclared red, 64/96 green
```

**A warning about measuring this estate, paid for several times on 2026-10-04.** Gate exit codes are
meaningless without the right invocation: several `tools/check_*.py` take a bundle root and several judge
THIS repository and refuse one — exit 2 is could-not-run, not red. Reading those wrong produced three
different wrong answers to "how much does this change break" in one session (30 lookups, then 6 gates,
then 3) before a correct run gave 11 modules. And a raw `grep '\.field'` is not a reader count: `scope`
once measured "150 readers" that way and had **zero**. Use the attribute chain, or
`check_declarations_read` while remembering its own caveat — it credits a reader by matching `.<field>`
anywhere, so its finding set is a floor, not a measurement.

## BLOCKING THE PUSH — an identity leak in this branch's HISTORY

`meaning-as-code` is public and its leak floor is 0. The branch `docs/canon-ratio-select` is **11
commits ahead of `develop` and has never been pushed**, so this was still catchable at source, and the
working tree is now clean. **The HISTORY is not.**

`tools/gen_canon_index.py` was authored on this branch holding the sibling runtime's location as an
absolute path under the operator's home directory. `tools/_neighbours.py` exists precisely for that
fact — its own docstring records that the path was once typed **eleven times**, and that each copy was
*"two defects at once: an identity leak in a PUBLIC repository … and a gate that could not run on any
machine but one."* This was the twelfth. Fixed at source in `9eb2389`: `RUNTIME` now comes from
`_neighbours.runtime_package()` and is None-able, the guard says so before reading, the runtime still
resolves (18 implemented, 3 known-unimplemented) and `reference_manual/rules_and_canons/README.md` is
byte-identical.

**What is still owed, and it needs the operator's yes because it rewrites history:** the line survives
in two patches in the unpushed range — `7327f6a` which introduced it and `9eb2389` which removes it.
Pushing publishes both. Measured over `origin/develop..HEAD`: **0 hits in 11 commit messages, 2 hits
across the patches**, using the 8 built-in shapes of `mac-platform/tools/check_secrets.py`.

The scrub is one idempotent substitution — the file has four distinct pre-fix versions on this branch
and **all four carry the identical three-line block**, so a `--tree-filter` replacing it with the
`_neighbours` form rewrites every one of them, and `--prune-empty` then drops `9eb2389` because it
touches nothing else. Take a backup ref first. Verify afterwards with: the range scan back to 0 hits,
and `git diff <backup> HEAD` empty — the tree must be unchanged.

**Three leaks remain in the working tree and they are NOT news from this branch:** two deliberate fake
AWS keys and one fake private-key block inside `sdk/gate/test_bundle_secrets.py` and
`sdk/connector/conformance.py`, both already on `origin/develop`. They are a secret-scanner's own test
fixtures. The gate's instruction is to append `secret-scan-allow` on the line or allowlist the path with
a written justification — a change to MAC, so it needs a yes, and it should get one: a scanner whose own
tests trip it will be ignored.
