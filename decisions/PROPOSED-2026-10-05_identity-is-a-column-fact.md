---
state: implemented
genre: proposal
ruled: 2026-10-05
implemented_by:
  - mac.schema.json
  - mac_vocabulary.yaml
  - mac_shapes.yaml
  - tools/check_vocabulary_parity.py
  - tools/check_canon_binding.py
  - tools/mac_project.py
  - tools/mac_to_graph.py
  - tools/canon/rules.py
  - sdk/authoring/authoring.py
  - mac-platform#packages/mac-runtime/src/mac_runtime/ontology/models.py
  - mac-platform#packages/mac-runtime/src/mac_runtime/ontology/parser.py
  - mac-platform#packages/mac-runtime/src/mac_runtime/planner/grounded_columns.py
  - mac-platform#packages/mac-runtime/src/mac_runtime/models.py
  - mac-platform#packages/mac-console/src/mac_console/console_api.py
  - cap-ontology-sources#example/contoso5
---
# IMPLEMENTED — 2026-10-05 · identity is a column fact, and the class vocabulary shrinks

> **Paths.** `planner/…`, `ontology/…` are under `mac-platform/packages/mac-runtime/src/mac_runtime/`;
> bare paths are in `meaning-as-code`; `ontology/concepts/…` is inside `cap-ontology-sources/example/contoso5`.

**The operator's rule, which both decisions follow from:**

> *"declare on concept level only what belongs to the concept level. keys etc belong to the column
> level and we list all columns anyway so the key is there. identity of the concept is given by
> column combination and it belongs there."*

---

## D1 · `concept.identity` IS REMOVED, NOT SHRUNK

The block was `{kind, canonical_key, note, counts_as}`. **Every field holds a column name or restates
a column fact**, so by the rule above none of them is a concept-level fact.

| field | contoso5 | measured | outcome |
|---|---|---|---|
| `canonical_key` | **0 of 17** | already migrated to `identity: canonical` by CONFORMANCE §2.1 | fallback branch deleted |
| `note` | **0 of 17** | **no reader anywhere** | deleted |
| `counts_as` | 1 of 17 (Store) | 5 real readers | → new column flag `counts: true` |
| `kind` | 10 of 17 | see below | deleted with its six-term vocabulary |

**`kind`, term by term, against runtime read sites:**

- `composite` — 4 sites, but the parser DERIVES it from `identity: part` columns and both real readers
  re-check `len(cell_key) >= 2` anyway. 7 of 7 contoso5 measures authored nothing.
- `iso`, `namespace_code`, `fk_name`, `sme_pending` — **zero** readers. Two have strictly better
  column homes: `namespace_code` ≈ `ruling.scoped_by` and `fk_name` ≈ `ruling.label_of`, both of which
  NAME the companion column where the kind only hinted at one.
- `code` — one reader, `grounded_columns.variant_selector`, **and it was misfiring** (D1a).

### D1a · the one live reader was reading the wrong declaration

`variant_selector` restricts a measure on a tall fact to its own rows. It triggered on
`identity.kind == "code"` plus "declares any measure column". Both halves were wrong. contoso5's
**Location** — a dimension keyed on `location_code`, carrying the rollup `units_ever_here` — raised
*"nothing declares which code is Location's"*, naming a code it would never have. The trigger is now
`class: measure`, which is what the function's own docstring always claimed the case was.

contoso5 has **no tall fact at all** (`v_contoso5_sales_line` is wide: six measures, six columns), so
the single live read of `identity.kind` in the playground was a false refusal.

### D1b · the two-homes argument that was taken the wrong way

`ontology/parser.py` refused any concept whose column said `canonical` without a concept-level `kind`, because
a first version GUESSED the kind from the column and was wrong (2026-09-26, Store read as `code` when
it was `fk_name`). That incident proved **do not infer**. It was read as **keep it on the concept**.
Different conclusions; the estate took the second. The refusal is deleted: with nothing inferring a
kind there is nothing to refuse.

### D1c · `counts` is a flag, not a fourth `identity` term

Store's `location_code` already carries `identity: reference` and is also what one store is counted
by (74 trading-period rows over 67 codes). One slot could hold only one of those, so `counts: true`
sits beside `identity`, not inside it.

### D1d · a bug this introduced, and the rule it produced

A first cut read the legacy `key:` list whenever it held one name and **overrode an explicit
`identity: part`** — the sort fixture's `Tally` is `key: [event_id]` with `event_id: {identity: part}`,
keyless by design, and was handed a canonical key. 11 tests went red. **The columns win; the legacy
list is consulted only when they say nothing.**

---

## D2 · `concept.class` SHRINKS 7 → 5, AND IS DECLARED FOR THE FIRST TIME

Asked of class, the same question gives the **opposite** answer, which is the part worth keeping.

**Class is NOT derivable from columns.** Measured on contoso5:

| concept | class | measure columns |
|---|---|---|
| `UnitsSold` | measure | `quantity` |
| `Store` | entity | `square_metres` |
| `SalesCost` | measure | `cost_amount`, `unit_cost` |
| `Product` | entity | `list_cost`, `list_price` |

Those pairs are **column-identical**. Only a person can say that the floor area is *about* a store
while the quantity *is* units sold. Class stays.

### D2a · it lived in one home and had already drifted

`concept.class` was declared **only in `mac.schema.json`**, so `check_vocabulary_parity` could not
police it — and the two homes had diverged: the schema admitted **seven** terms, mac-runtime's
`ConceptClass` admitted **six**. A concept writing the seventh (`meta`) validated and then failed to
load. It is now declared in `mac_vocabulary.yaml`, landed into the schema by `--write`, and added to
`PAIRS`.

### D2b · what went and why

- `reference` → **renamed `entity`**. Both named the set-with-identity structure (`02_building_blocks`
  §2.2 already gave them ONE table row). And `reference` was taken one plane down:
  `concept.column.identity.reference` means a POINTER AT such a thing — a class and a column flag at
  opposite ends of one arrow, which is the `dimension` collision again.
- `meta` → **dropped**. In the schema, never in the runtime enum; the meaning plane synthesises its
  own concepts as entities.

### D2c · `grouping` was proposed for removal and KEPT — the first measurement was wrong

`mac_to_graph`'s `NODE_CLASSES` lumps `entity`/`reference`/`grouping` into one set, which read as
proof that nothing told them apart. It was one blind reader, not no reader: **`mac.schema.json` makes
`members.over` MANDATORY for a grouping**, and mac-platform's `console_api.py:5019-5140` draws the **containment
channel** from it — whole→part membership that FRAMEWORK.md deliberately keeps on the concept instead
of in `edges.yaml`, with its own test file and its own top-level key in the graph API.

### D2d · one misclassification, two divergent outputs

Country was `reference` while Brand/Color/Currency/ProductCategory were `enumeration` — all five
register-backed, same shape. Not cosmetic: Country **became a graph node** and Currency did not;
Currency's values **were inlined into the manual** and Country's were not. Fixed to `enumeration`.

---

## Measured outcome

| check | before | after |
|---|---|---|
| mac-platform suite | 1866 passed | **1866 passed** |
| `validate_schema` contoso5 | 14 findings | 15 — Country joining the four enumerations already caught by **OWED 2** (schema requires `values`, the ruling bans it) |
| `check_vocabulary_parity` | 11 of 11 | **12 of 12** (the class slot is new) |
| `check_semantic_currency` | 10 new findings | **0 new** |
| `check_shapes` | 32 violations | **26** — the retired `concept-declares-identity` shape had been warning on the 7 measure concepts all along |
| `run_framework_gates` | **13** undeclared red | **12** |

Baselines were taken by STASHING the change and re-running, not from the previous protocol's numbers:
that record said 13 red over **96** gates and the population is now **99**, so its figures could not
have been attributed.

---

## D3 · THE CONCEPT HEADER LOSES FOUR MORE KEYS

Operator: *"we dont need metadata and concept … status / owner unnecessary, concept redundant."*
Measured across all 17 before removing anything:

| key | measured | outcome |
|---|---|---|
| `metadata.concept` | duplicated `concept.name` **17 of 17**; every reader took it only as a fallback | removed |
| `metadata.status` | the constant `draft` on all 17 | removed |
| `metadata.owner` | the constant `operator`, reaching only a display row | removed |
| `concept.label` | **9 of 17** identical to `name` | removed on those 9 |
| `metadata.confidence` | **varies** (3 C, 14 I), parser REQUIRES it, `min_confidence` stamps it on every answer | **kept** |

`status` had one reader and it was not a check: `mac_checks_semantic` appended a clause to a MAC006
witness message, while the diagnostic itself keys on `provenance` + `confidence` +
`governance.ratified_by`. A field with one value bundle-wide cannot discriminate anything.

### D3a · `metadata` is NOT retired, and the reason is worth recording

The operator asked for the whole block to fold into `concept:`. It did not, because `metadata:` is an
**estate-wide file header**: 15 `$defs` declare one and 4 require it — `TableFile` has
`metadata.table`, `ProjectFile` has `metadata.project`, the same subject-naming shape. Folding it for
ConceptFile alone would make concepts the only type without the header. The operator accepted this;
`source`, `version`, `schema_version`, `confidence` and `provenance` stay on it.

### D3b · `label` earns its place, and the schema already said when

`mac.schema.json` describes it as *"the concept's name as a reader says it, WHERE THAT DIFFERS from
its identifier"*, and it is optional — so the 9 concepts repeating `name` were already against the
standard. The 8 that differ stay, because the field does two jobs and only one is derivable:
`registers.py` already derives the spaced form of a CamelCase name (`GrossRevenue` → `gross revenue`)
for RESOLUTION, but `display = concept.label or name` is not derivable — without it an answer reads
*"GrossRevenue"*. Two carry a fact nothing derives: `Colour`, and `Margin (gross profit)`.

### D3c · a bug this introduced

The first pass removed **34** `owner:` lines where 17 was correct: the filter matched two-space
indentation and took `governance.owner` with `metadata.owner`. Caught by diffing the removal COUNTS
against the expected 17, not by reading the files, and restored on all 17.

---

## Owed

- **`schema_version` is not a bump, it is a drift.** `RELEASING.md` requires the same value in every
  model file. contoso5's 91 files carry **four**: `'0.1.14'` quoted ×8, `0.1.14` ×32, `0.1.15` ×16,
  `0.1.16` ×35. The schema's own `version` (0.1.16), its `title` (v0.1.18-develop) and
  `validate_schema.CURRENT` (0.1.16-develop) are three more. 539 files across three repos. This is a
  deliberate release action and is NOT folded into this change.
- `mac-ontology-contoso` carries 5 `class: reference` → `entity` concepts migrated here because the
  platform suite loads that bundle — outside the contoso5-only scope. Accept or revert.
