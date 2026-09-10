# ADR — Packaging: what `pip install meaning-as-code` should mean

STATUS: ACCEPTED (option C) · DATE: 2026-09-10

## Context

The framework had no Python packaging of any kind — no `pyproject.toml`, `setup.py` or
`setup.cfg` — and no `v0.1.x` tag. A downstream project therefore could not depend on a *version*
of MAC; it could only depend on a **directory**, found by convention or by an environment
variable, with whatever contents that directory happened to have.

That is a correctness problem, not an ergonomics one. Two projects claiming conformance to "MAC"
may be checked by different generations of the checkers, and neither can prove which. Reproducible
conformance requires a resolvable, stated version.

## The constraint that shapes the answer

The repo is deliberately **flat**. The checkers in `tools/` resolve their own data with
`Path(__file__).resolve().parent.parent` — each assumes it sits directly beside
`mac.schema.json` and the closed vocabularies. Any packaging that moves files breaks that idiom in
every checker at once, and it fixes the public import surface of a public repo, which is a
one-way door.

## Options considered

**A — Map the flat repo as one package.** No source moves; `parent.parent` still resolves because
the installed package directory *is* the old root. Cheap. Needs an explicit include list or the
wheel ships the articles, tests and example ontologies.

**B — A real `src/meaning_as_code/…` layout** with an explicit public API and data as package
data. The honest end state. It moves every checker, breaks the `parent.parent` idiom, and
invalidates path-based invocation for every existing consumer. Cannot be done incrementally.

**C — Ship the CLI and a locator.** Console entry points plus a `framework_root()` helper, so
consumers stop guessing a path. The checkers keep their current shape.

## Decision — C, implemented as A's mapping

Adopt **C**. Consumers get `meaning_as_code.framework_root()` and console scripts; the payload
travels in the wheel via the root-as-package mapping from A, with an explicit allowlist so only
the schema, the closed vocabularies, the checkers and the normative documents ship.

`framework_root()` resolves `$MEANING_AS_CODE` first — a developer checkout must win, since that
is how the framework is overridden during development — then the installed package, and **raises**
if the resolved directory carries no `mac.schema.json`, rather than returning a plausible path
that fails later inside a checker.

**B remains the right end state** and should be scheduled deliberately as its own change, not
smuggled in under a packaging ticket.

### Versioning

`VERSION` stays the single home for the generation. PEP 440 rejects the pre-release grammar this
project uses (`0.1.14-develop`), so `__pep440_version__` **derives** `0.1.14.dev0` from it. This
is a derivation, not a second home: `tools/version.py` exists to stop version claims multiplying,
and packaging must not add one.

### Release remains a human act

No tag is cut and no promotion happens as part of this change. `tools/version.py` documents the
discipline — *the release number moves only on promotion to main, by the maintainer's decision* —
and packaging does not alter it.

## Consequence — a defect this exposes

`tools/version.py --check` passes, reporting *"every current-version claim agrees"*, because it
knows about three claims. Four normative documents assert a **different, older** generation:

| file | asserts |
| --- | --- |
| `CONFORMANCE.md` (title) | `v0.1.9` |
| `README.md` (schema, conformance, validator rows) | `v0.1.9` |
| `mac_vocabulary.yaml` (header) | `MAC v0.1.12` |
| `FRAMEWORK.md` (schema, conformance lines) | `v0.1.9` |

These are current-version claims ("the schema IS v0.1.9"), not the changelog prose that
`version.py` deliberately excludes ("new in v0.1.6", which stays true forever). A reader pinning
against `CONFORMANCE.md` today would believe they are on 0.1.9.

Extending `CLAIMS` to cover them turns the gate red until the four are corrected — which is what a
gate is for. Deferred to a separate change so that packaging and a documentation correction are
not entangled in one commit.
