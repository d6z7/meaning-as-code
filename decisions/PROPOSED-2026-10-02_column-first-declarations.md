---
state: implemented
genre: proposal
ruled: 2026-10-02
implemented_by:
  - tools/check_no_inline_values.py
  - guardrails/unfiled.yaml
  - tests/test_concept_page_layout.py
  - mac-platform#packages/mac-runtime/src/mac_runtime/column_facts.py
  - mac-platform#packages/mac-runtime/src/mac_runtime/canons/ratio_select.py
  - mac-platform#packages/mac-runtime/src/mac_runtime/planner/plan.py
  - mac-platform#packages/mac-runtime/src/mac_runtime/resolver/registers.py
---
# IMPLEMENTED — 2026-10-02 · column-first declarations, and what it cost

> **Paths in this document.** `planner/…`, `interpret/…` and `canons/…` are under
> `mac-platform/packages/mac-runtime/src/mac_runtime/`; `packages/…` is under `mac-platform/`;
> `data/…` and `ontology/…` are inside the bundle (`example/contoso5`). A `:line` suffix is the
> line the measurement was read at.


**Status: IMPLEMENTED 2026-10-02** — written and shipped the same day; the rulings below are the
operator's, taken as the work went. Per CORE §3 an agent may only write `PROPOSED`, which is what the
filename records; the state is in this file's front matter. This record exists so the REASONING lives here and the source stays readable — operator, 2026-10-02:
*"my problem with inline comments is that they make source lesser readable. i dont mind one line of
comments ... but i do 20 lines for one line of code."* Measured on the files changed that day:
`mac_runtime/column_facts.py` carried 91 comment lines against 55 of code (1.65:1), `canons/ratio_select.py`
1.49:1, and 54 blocks of 6+ consecutive comment lines held 662 lines across five files.

**The rule this record serves:** inline comments say WHAT and name the one non-obvious constraint, in
one to three lines. The measurement, the history and the alternative not taken come here, cited from
the code by file name.

---

## D1 · THE FACT GOES ON THE COLUMN

`semantics.measure_type`, `semantics.unit` and `semantics.axis_kinds` sat above a grounding that
already declared the same columns. Operator: *"would it not be more user friendly and reasonable to
have (some of) this together with grounding ... then you list column and define all what is to be
defined per one column."*

Measured over 37 concepts: `axis_kinds` carried **47 entries** and the fold law read **zero** of
them — its keys are COLUMN names, the planner looked them up by a lowercased CONCEPT name, so no key
could ever match and a two-branch guess (`"time" if axis == "time" else "categorical"`) decided every
fold in the estate. 10 columns repeated `semantics.unit` verbatim. `measure_type` was **not**
duplication: on a multi-measure concept it is a DISAMBIGUATOR ("of my measure columns, fold the flow
one"), which `grounded_columns._by_declared_measure_type` reads.

**Readers go column-first with a fallback to the old slot** (`mac_runtime/column_facts.py`), so an
unmigrated bundle reads identically. `ConceptSemantics` is `extra="forbid"` and 13 locked files stop
parsing if a field disappears: **deprecate, never delete.**

New flags: `axis_kind` on a column; `measure.canonical` (the column the concept IS, stated directly
instead of inferred from a type match, which cannot work when two columns share a type).

**Measured outcome:** 8 real dimension axes now resolve from the declaration, 0 before; 157 planned
queries byte-identical before and after (`be8a974dddc5b091`).

## D2 · THE KEY IS A COLUMN FACT

`sources[].key` duplicated the columns' own `identity: canonical | part`. Operator: *"is this not
redundancy? ... what i would say is that one colum denoted with key is mandatory."* Measured: **38 of
38** sources agreed with what their columns declared, and all 10 composite keys matched in ORDER —
which is what made deriving `cell_key` safe, since its order reaches the SQL. `key:` removed from 17
concepts; digest unchanged.

The invariant is **"the grain is declared"**, not "declared in the new place": a first cut demanded
the column flag outright and broke 262 tests on a fixture bundle using the map form without it.

## D3 · A DECLARED REGISTER MUST NOT BE MUTER THAN AN UNDECLARED ONE

The worst defect of the day, and self-inflicted in direction: I read
`check_registers_reachable.py`'s "16 orphans" as broken behaviour. It was not — this module says so
itself: *"an undeclared register is still readable … a declaration gives a register its MEANING, never
permission to read it."* `Germany → DE` worked the whole time.

But attaching a register **declared-side** then made things worse: the entry builder skips any file in
`declared_files`, and the `value_domain` declaration path produced no entries at all. **Brand went
from 11 resolvable members to 0**; `Contoso` stopped resolving to a brand. Fixed — a loaded
value-domain register now contributes its rows through the same `rows_to_entries` the undeclared path
uses. Two sub-bugs on the way: a tuple where a column string belonged, and a local shadowing the
enclosing `declared_columns` dict.

Also fixed: the value-domain key column defaulted to the literal `code`, which **no** contoso5 lookup
has — their first column is named for the dimension (`Brand`, `CountryCode`). Now `code` where the
file has one, else the register's first column, read from the file rather than restated in the
ontology.

## D4 · VALUES DO NOT BELONG IN A CONCEPT

Operator, twice: *"i want a RULE which prohibits creation of values in concepts ... make sure that it
cannot creap IN."* Measured: 5 concepts inlined **49 values** byte-for-byte identical to 5 lookup
files, with no reference between them — and `ontology/concepts/color.yaml` already carried **17** members where its
register had **16**. One fact, two homes, already disagreeing.

`tools/check_no_inline_values.py` is the gate, wired into `mac-platform/tools/gate.py` as a BUNDLE
RULES plane. `brand`, `currency`, `product_category` migrated. `Country` and `Color` are declared
standing failures with owners: Country's attachment fights its own `label_of: country_code` ruling,
and Color's two copies are not the same set.

## D5 · THE PAGE'S LAYOUT IS DECLARED, NOT INVENTED

Operator: *"i cannto stand that you every time invent new layout for the same document."* Eight
sections each carried their own `if` and vanished when empty, so the page's shape was a function of
the bundle's completeness — there was no layout to drift FROM. `delivers.concept_page.shape` in
`guardrails/unfiled.yaml` is the layout; the renderer reads it; `tests/test_concept_page_layout.py`
holds every page to it.

`grounded in` removed from the Fields table (a whole-object fact repeated per row); `role` fixed (it
was em-dashed on every map-form concept because the renderer read only the legacy `field_roles:`
block); `axis kind` deliberately NOT added, because `## Axes` already carries it per axis — operator:
*"WHY DONT YOU GO AND LOOK HOW IT LOOKED LIKE BEFORE TRANSITION."*

## OWED

- The 13 lookup files still undeclared (read, so resolution works — a bookkeeping gap, not a broken one).
- `Country` / `Color` standing failures above.
- The 17 stale projected `.md` pages, which still show the pre-transition layout.
- Whether an aggregate's dimensions should break ties in the ORDER BY.
