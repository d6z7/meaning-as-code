# ADR — Packaging the framework: what `pip install` should mean

STATUS: awaiting-operator · DATE: 2026-09-10 · BRANCH: `init/packaging`
CONTEXT: the MAC Integration Kit programme (`cap-ontology-workbench/specs/integration-kit/`)
needs downstream bundles and the GUI to **pin** the framework by version. Today they cannot.

## The problem, measured

- There is **no Python packaging of any kind** — no `pyproject.toml`, `setup.py` or `setup.cfg`.
- The last tag is `epic-85-baseline`; there is no `v0.1.x` tag. `origin/main` is **98 commits**
  behind `develop`. `VERSION` reads `0.1.14-develop`.
- Consumers therefore bind by **filesystem path**: the GUI hardcodes
  `_REPO.parent / "meaning-as-code"` in five places, three source repos vendor a whole checkout
  under `<repo>/schema`, and `run_checks.sh` resolves `MEANING_AS_CODE` by env-or-sibling.
- **971 files** across the estate reference the framework by path or via `MEANING_AS_CODE`.

So "pin the framework" currently means "hope the sibling directory is the right one", which is
precisely what makes two operators' results incomparable.

## Why this is not a quick fix

The repo is **flat**: no importable package exists, and every tool resolves its own data with
`Path(__file__).resolve().parent.parent`, i.e. each script assumes it sits in `<root>/tools/`
directly beside `mac.schema.json`, `mac_vocabulary.yaml`, `mac_rules.yaml`, `mac_shapes.yaml`.
Any packaging choice fixes the **public import surface** of a public repo, and unpicking it later
breaks consumers a second time. It is a one-way door, so it is the operator's call.

## Options

**A — Flat repo mapped as one package** (`package-dir = {meaning_as_code = "."}`).
Zero source moves; `parent.parent` still resolves because the installed package directory *is* the
old root. Cheapest and reversible. Costs: the wheel needs a careful include/exclude list or it
ships `articles/`, `tests/` and `.git`; `import meaning_as_code.tools.check_shapes` is an odd
shape; namespace collisions are easy to create later.

**B — Real package layout** (`src/meaning_as_code/{schema,tools,vocab}/…`).
The honest structure: an explicit public API, data files as package data, entry points that are
functions rather than scripts. Costs: moves every tool, breaks the `parent.parent` idiom in ~40
checkers, and invalidates path-based invocations across 971 files. Highest quality, highest cost,
and it cannot be done incrementally.

**C — Package the CLI only, keep paths for data.**
Ship console scripts (`mac-compile`, `mac-regen-projections`, `mac-lineage-project`) plus one
`meaning_as_code.framework_root()` helper that returns the installed payload path. Consumers stop
hardcoding sibling paths and call the helper; the tools keep their current shape. Costs: the
payload still has to be shipped as package data, so it is option A's include/exclude problem in a
smaller box.

**Recommendation: C, then A's include-list discipline.** It removes the five hardcoded welds and
the vendored checkouts — the things actually blocking asks C and F — without moving 40 checkers or
touching 971 call sites. B is the right end state and should be scheduled deliberately, not
smuggled in under a packaging ticket.

## Second finding, independent of the option chosen

`tools/version.py --check` passes and prints *"every current-version claim agrees (3 checked)"* —
but it only knows about three claims, and **five documents assert a different, older version**:

| file | asserts | VERSION says |
| --- | --- | --- |
| `CONFORMANCE.md:2` | `v0.1.9` in the title | `0.1.14-develop` |
| `README.md:129,130,131` | `v0.1.9` for schema, conformance, validator | `0.1.14-develop` |
| `mac_vocabulary.yaml:1` | `MAC v0.1.12` | `0.1.14-develop` |
| `FRAMEWORK.md:13,14` | `v0.1.9` for schema and conformance | `0.1.14-develop` |

These are current-version claims ("the schema IS v0.1.9"), not the changelog prose that
`version.py` deliberately excludes ("new in v0.1.6", which stays true forever). A reader pinning
against CONFORMANCE.md today would believe they are on 0.1.9. Extending `CLAIMS` to cover them
turns the gate red until the five are corrected — which is the point of a gate.

**Not done here, deliberately:** the values are not rewritten and no tag is cut. `tools/version.py`
documents the branch discipline as *"the release number moves only on promotion to main, by the
operator's decision"*, so tagging `v0.1.14` and fast-forwarding `main` is the operator's act, not
an agent's. The programme's step 3 as originally drafted assumed otherwise; this ADR corrects it.

## What the operator decides

1. Option A, B or C.
2. Whether to extend `version.py`'s `CLAIMS` to the five uncovered claims now (the gate reds until
   the docs are corrected) or after the packaging choice lands.
3. Whether `v0.1.14` is cut and `main` fast-forwarded to `develop` — and under what release act.
