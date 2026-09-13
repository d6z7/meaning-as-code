# `sdk/connector/` — the shipped index and the connectors' own config contracts

This directory holds the **payload half** of the connection seam. The **envelope half** lives in the
core grammar (`mac.schema.json#/$defs/ConnectionFile`, `credentialRef`, `connectorRef`) and in
`mac_vocabulary.yaml` (`connector`, `credential_mode`).

Only the schema half of the seam is here. There is no connector CODE in this directory yet — see
"What is deliberately not here" below.

## `index.json` is the authority for exactly one question

**Which `mac.`-prefixed connector ids are real, and where is the JSON Schema that validates each
one's `config:` block.**

It is data. No imports, no entry points, diffable across releases by an ordinary snapshot test, and
released with the wheel.

It exists because **the canon must not hold this list.** `mac_vocabulary.yaml#connector` registers
the *namespace* and lists no members, and `$defs/connectorRef` validates by *pattern* and never by
an enum — both for the same reason: which first-party connectors exist is a fact about the MAC
**distribution**, not about **meaning**. A member list in the canon would be a vendor product
catalogue inside the file that defines meaning, and it would be load-bearing, so a third first-party
engine would be a canon bump forever. Putting it here instead costs one JSON file and buys back the
property that a new engine is a *release*, not a *grammar change*.

It is also what lets a mount validate a `config:` block with **zero imports**: the dry half of the
connector contract is a pure function of the config mapping, so first-party mount-time validation is
`jsonschema.validate(config, <a file in this repository>)` — no entry-point load, no import deadline,
no ambiguity to resolve.

`index.json` carries no comments because it is data and JSON has none. This file is its comment.

## The two config schemas, and why there are two

| id | schema | what it proves |
|---|---|---|
| `mac.connector.athena/1` | `schemas/athena.1.json` | the real, remote, credentialed, billed case |
| `mac.connector.duckdb/1` | `schemas/duckdb.1.json` | **the falsifier** — local, free, no credential |

The second one is the point. The standing kill criterion for this whole seam is: *if making a second
engine fit forces an Athena concept into the shared contract — an `Optional[workgroup]`, an
`Optional[output_location]`, an `engine == …` branch — then it was never a seam.* Read the two
schemas side by side and check what `duckdb.1.json` does **not** contain: no region, no workgroup, no
catalog, no output, no account, and no credentials block at all. Nothing in the core grammar bends to
say that, and the envelope mentions none of those nouns.

DuckDB also makes the contract **testable in CI without a billed call**, which is why it is a shipped
connector and not a test fixture.

## The line this directory is on the far side of

`mac.schema.json` describes the **envelope**: who the connector is, how the credential is obtained,
and *where the connector's payload begins*. It stops there. `region`, `workgroup`, `catalog`,
`database`, `read_only` are nouns that appear **only** in this directory — never in
`mac.schema.json`, never in `mac_vocabulary.yaml`.

`config:` being *opaque to MAC* means MAC does not **know** these keys. It does not mean nobody
checks them. That is precisely the distinction that got `x-` extension keys ruled out and lets this
one stand: an `x-` key was checked by **nobody**; a `config:` block is checked by a JSON Schema a
**named party ships**, and when that party is absent MAC prints what went **unchecked with its
denominator** and withholds the claim that depended on it.

**Honest limit, recorded rather than hidden.** JSON Schema expresses most cross-field rules
(`if`/`then`, `dependentRequired`) and not all. A rule it cannot express — e.g. *"`output` is
required unless the workgroup carries a managed output location"*, which only the live service can
answer — is **not** silently skipped. It belongs to the connector's `validate_config()`, and the
mount reports **which tier it reached** rather than implying it reached this one.

## What is deliberately not here

* **Connector classes and the `Connector` / `SqlConnector` contract.** Blocked on the ruling over
  which SDK is live; the two trees have already diverged, so nothing is moved and nothing is deleted.
* **Entry-point discovery** (`importlib.metadata`, `guarded_import`, collision refusal). Blocked on
  the ruling over whether third-party connectors are a requirement at all. On today's measurements
  the default is a **plain registry resolved from this index** — the full plugin architecture is the
  exception that needs a ruling, not the baseline.
* **`x-mac-sensitivity` annotations** on config keys. The gate that would read them does not exist
  yet, and a declaration nothing enumerates is a declaration nothing applies.
* **Routing.** Nothing yet routes a connection file to `$defs/ConnectionFile`, so these schemas are
  reachable by id but not yet applied by `validate_schema.py`. That wiring is tracked separately and
  named in the handover, because a half-wired definition is worse than none — a file routed, matched
  and then skipped reports as zero-undefined while nothing is checked.
