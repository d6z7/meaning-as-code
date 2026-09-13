# TOPOLOGY — where each capability lives, and nowhere else

Every duplication this estate has paid for was invisible until it was a defect: a vendored grammar
fork, a whole SDK copied instead of moved, a credential vocabulary in two spellings, a liveness rule
fixed in one of two scripts. In each case both homes were individually defensible. Nothing anywhere
said which was THE home.

This file says. It is the answer to "where does X belong?" and it is meant to be read BEFORE writing
something, not after discovering it exists twice.

**It is machine-checkable on purpose.** `tools/check_topology.py` reads the table below and asserts no
capability is implemented outside its declared home. A diagram nobody checks drifts from the code it
describes — the same defect `mac_resources.py` exists to prevent for bundle descriptions.

---

## The shape

```
                    BUILD TIME                          ANSWER TIME
                    author · compile · project           intent → SQL → value
                 ┌──────────────────────────┐        ┌──────────────────────┐
                 │  meaning-as-code         │        │  mac-runtime         │
                 │    the STANDARD          │        │    the ENGINE        │
                 │    + mac-sdk             │        │                      │
                 └────────────┬─────────────┘        └──────────┬───────────┘
                              │                                 │
                              └───────────┬─────────────────────┘
                                          │
                              ┌───────────▼───────────┐
                              │  sdk/connector/       │   THE SEAM
                              │  one adapter          │   reach a data source
                              └───────────┬───────────┘
                                          │
                              ┌───────────▼───────────┐
                              │  a data source        │   Athena · DuckDB · …
                              └───────────────────────┘

     mac-console   the HOST. Renders what a runner recorded. Computes no verdict, imports no sdk.
     a BUNDLE      the CONTENT. Its own ontology, connection config, interpreter, tests.
```

## The homes

| capability | THE home | and nowhere else |
|---|---|---|
| the grammar (schema, vocabularies, diagnostic taxonomy) | `meaning-as-code/*.json`, `*.yaml` | one file per artefact; `check_grammar_home` asserts exactly one grammar in the tree |
| conformance checking | `meaning-as-code/tools/check_*.py` | 34 checkers, one home |
| authoring / harvest / projection | `sdk/authoring/`, `sdk/cli/`, `sdk/project/` | build-time only |
| **reaching a data source** | **`sdk/connector/`** | **ONE adapter. See the open question below.** |
| container open / trust / capabilities | `sdk/container/` | |
| the gate harness | `sdk/gate/contract.py` | every gate uses it; no gate rolls its own |
| **answer-time resolution and execution** | **`mac-platform/packages/mac-runtime`** | intent → score → SQL → value |
| the host / rendering | `mac-platform/packages/mac-console` | renders recorded results; `boundaries.yaml` forbids importing sdk |
| an estate's own values (tokens, handles, schemas) | gitignored registers, `registers/` + `sdk/gate/*.txt` | never in MAC; only `.example` files ship |
| a bundle's connection config | the BUNDLE's `connection.yaml` | never in MAC, never in the tooling's defaults |
| a bundle's identity | the BUNDLE's `mac.project.yaml` | the manifest is not overridable; the connection file is |
| a bundle's own documentation | the BUNDLE's derived read-view | never in MAC — instance knowledge |
| the method (skills, seats, hooks) | `mac-integration-kit`, projected | never authored in a workspace it governs |

## Open question this diagram exposes

**Two execution abstractions exist.** `mac_runtime/adapters/base.py::GroundingAdapter` declares
`execute(plan) -> rows`; `sdk/connector/base.py::Connector` declares `read(request) -> ReadResult`.
They are the same capability with two homes — the pattern this file exists to prevent, created on
2026-09-13 by building the connector without first drawing this map.

The rest of the connector does NOT overlap: `list_relations`, `describe_relation`,
`profile_relation`, `validate_config` and `credential_plan` have no counterpart, because harvest
needs them and answer-time never did.

**Proposed resolution, needing a ruling:** `GroundingAdapter.execute` becomes a thin call into
`Connector.read`, making the connector the single seam both halves use. `okf_core/sources.py` is a
third thing but not an adapter — it normalises source config, which the connection envelope now
describes; it should be read for overlap before anything is merged.

## Findings on the first run

The gate ran against this diagram twenty minutes after the diagram was written, and found a real one.

**`schema_path` is two functions answering "which grammar governs".** `meaning_as_code/__init__.py`
locates a framework FILE by name; `sdk/grammar/resolve.py` decides which grammar governs THIS
PROCESS, honouring `$MAC_SCHEMA`. Same name, different responsibilities. They agree today only
because no override is set — proved to diverge:

    with $MAC_SCHEMA set:
      meaning_as_code.schema_path() -> <the repo's own mac.schema.json>
      resolve.schema_path()         -> the override

That is the vendored-fork defect class in miniature: two answers to one question, agreeing by
coincidence. Not a duplicate implementation — a name collision on two responsibilities — so the
marker now pins the POLICY (the override lookup) rather than the name. The collision itself is worth
renaming and is recorded here rather than fixed silently.

## How to use this

Before adding a capability, find its row. If there is no row, the capability is new — add the row in
the same change, and say what its single home is. If a row exists and you are about to implement it
somewhere else, you have found a fork before it cost anything, which is the whole point.
