---
title: Connection — how a bundle reaches its data
status: both vocabularies are read by the connector seam
audience: anyone wiring a bundle to a warehouse
---

# Connection

A bundle declares **how it reaches its data** in `connection.yaml`, and MAC deliberately learns as
little as possible about it.

```yaml
spec_version: mac.connector/1
label: Contoso (local DuckDB)
config:
  database: contoso.duckdb
```

**The envelope is MAC's; the payload is the connector's.** The grammar defines who the connector
is, how a credential is obtained, and where the payload starts — then delegates the payload to a
schema the connector ships. *MAC never learns what a `database` is.*

That is tested rather than asserted: contoso is DuckDB, a file with **no credential at all**, which
is where the contract gets checked against a source that has nothing to authenticate.

---

## `mac.connector` — the namespace

<!-- BEGIN GENERATED:vocabulary-terms:connector (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> The `mac.connector.*` NAMESPACE. A `mac.`-prefixed connector id is a framework reference; any
other namespace is not, by this file's header rule, and needs nothing from MAC. This block
registers the NAMESPACE ONLY. It lists NO members: which first-party connectors exist is a fact
about the MAC DISTRIBUTION, not about meaning, and lives in the shipped index
(sdk/connector/index.json). A member list here would be a vendor product catalogue inside the
canon — the same list that `$defs/connectorRef` refuses to be an enum of, relocated into the one
file that defines meaning, and load-bearing, because a third first-party engine would then be a
canon bump forever. It would also not validate: mac.vocabulary.schema.json closes a member
object over exactly six keys (definition, additivity, serves, needs_sqlglot, doc, params_from),
so the packaging keys such a list needs — config_majors, entry_point, status — are all three
illegal, and an entry_point is a Python module path, a fact about MAC's own wheel layout,
written into the file that defines meaning. AND tools/check_vocabulary_drift.py IS DELIBERATELY
NOT PATCHED TO SEE THIS BLOCK. Measured: its _vocabularies() at :53-56 collects `kind:
vocabulary` (with terms) and `kind: value_domain` (with members) and nothing else, so a
`registry` is invisible to it — by omission, not by accident. Patching it to collect registries
would buy a green line and not a check: :68 iterates (_ROOT / "tools").rglob("*.py") and :38
_LITERAL matches a dotted mac.NAMESPACE.TERM literal in MAC'S OWN PYTHON SOURCE, while connector
ids live in mac.project.yaml#runtime.connector, in bundles, and in other repos — never in
tools/*.py. The gate would then report clean over ZERO occurrences, permanently, while the typo
it exists to catch (`mac.connector.athna` in a bundle manifest) stayed invisible. Worse: with
the namespace registered and no members, `voc in vocab and term not in vocab[voc]` is true of
EVERY `mac.connector.*` literal, so any MAC docstring narrating a hypothetical
`mac.connector.postgres` would become a MAC008 ERROR ON PROSE — the exact false FAIL that gate's
own docstring says it was designed to avoid. A registry the drift gate openly skips is honest;
one it counts and structurally cannot see is a green line over nothing. Enforcement of connector
ids lives entirely in `$defs/connectorRef`'s pattern (every bundle, every run) and in the
shipped index. This paragraph exists so nobody later "fixes" the omission.

*`mac.connector` · registry · no enumerated members*
<!-- END GENERATED:vocabulary-terms:connector -->

A **registry**, not a closed list: a `mac.`-prefixed connector id is a framework reference, and a
bundle may bring its own. Nothing here enumerates warehouses, because enumerating them would make
the framework responsible for a list it cannot keep.

---

## `mac.credential_mode` — how the credential is obtained

<!-- BEGIN GENERATED:vocabulary-terms:credential_mode (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> The way a connector OBTAINS its credential, as a closed and BRAND-FREE set. Referenced by
mac.schema.json#/$defs/credentialMode, which is the schema-side restatement of this set (the
same idiom $defs/confidence and $defs/status already use); this file is the single home. WHY
BRAND-FREE: the measured set in sdk/authoring/connection.py:48-68 is `aws-chain | profile |
secretsmanager | ssm` — four AWS product names doing the work of three ideas, which is one
cloud's credential chain promoted into the framework's grammar. A connector may keep its own
spellings as ALIASES and report them MAC003 (fact-restated); the framework does not learn them.
WHY SIX AND NOT FOUR: one resolution mode plus one opaque handle fits password-shaped auth and
fails exactly where THE MECHANISM IS THE AUTH and there is no secret to fetch — interactive or
browser SSO, mTLS client certificates, Kerberos/GSSAPI. None of those is ambient, named_profile,
secret_manager or none, and a set that cannot spell them forces the connector to lie about which
mode it is in. A NEW MEMBER HERE IS A FRAMEWORK RELEASE, not a bundle's choice. That is the
price of `closed`, and it is the point: the alternative is a per-connector credentials schema,
and the moment a connector may declare its own credential fields, one of them will be a password
field and the structural guarantee that there is nowhere to put a secret is gone.

*`mac.credential_mode` · 6 terms · closed — these are all of them*

#### `mac.credential_mode.ambient`

The host environment already carries the identity — an instance/task role, an ambient session,
an environment chain. Nothing to fetch and nothing to name, so `ref` must be null or absent.

#### `mac.credential_mode.named_profile`

A named local profile selects the identity. `ref` is the profile name — a handle, never a
secret.

#### `mac.credential_mode.secret_manager`

The credential is fetched at call time from the deployment's secret manager. `ref` is the
path/id in that manager; MAC never resolves it and never sees the value.

#### `mac.credential_mode.interactive`

The human authenticates at connect time — browser SSO, a device code, an MFA prompt. There is no
secret to fetch, so `ref` must be null or absent. Unattended answering cannot use this mode, and
a host that needs one will fail loudly rather than hang on a prompt nobody can see.

#### `mac.credential_mode.client_certificate`

A client certificate (mTLS) is the credential. `ref` locates the certificate material in the
deployment's own store; the certificate itself never enters the bundle.

#### `mac.credential_mode.none`

No credential is required — the engine is local or open. Distinct from the block being ABSENT
only in that it says so out loud; both are legal, and absent is the honest spelling when a
connector has no credential concept at all.
<!-- END GENERATED:vocabulary-terms:credential_mode -->

### Brand-free, and that is the point

Six modes, none of which names a vendor. `named_profile` is a *named local profile*, not an AWS
profile; `secret_manager` is *the deployment's secret manager*, not a product. A vocabulary that
named brands would need editing every time a cloud renamed a service, and every bundle that joined
on the old spelling would break.

### `ref` — a handle, never a secret

Every mode but `ambient` and `none` carries a `ref`, and it is always **a locator**: a profile name,
a secret path, a certificate location. **The credential itself is never in the bundle.** That is
what makes a bundle safe to publish — contoso is public at leak floor 0, and its connection block
says only `database: contoso.duckdb`.

### `none` is not "unspecified"

| | meaning |
|---|---|
| `none` | no credential is required — the engine is local or open |
| block absent | **nobody has said**, which is a gap |

Declaring `none` is a statement; omitting the block is a silence. The gate can tell them apart only
because the vocabulary has a term for the first.

---

## The write surface

A connection may be read-write, and when it is, the bundle says exactly what it may write. Contoso:

> *"READ-WRITE SINCE 2026-09-18, AUTHORISED BY THE OPERATOR, AND FOR EXACTLY ONE PURPOSE: this
> pipeline materialises ITS OWN declared views into ITS OWN `view_schema`. All six transforms are
> `CREATE OR REPLACE VIEW contoso_served.<name>` and every dataset descriptor's `produces.relation`
> names `contoso_served.<name>`, so the write surface is the six relations this bundle declares and
> the schema it declares them in. Nothing here writes `main`."*

**The write surface is bounded by declarations the bundle already makes** — six transforms, six
descriptors, one schema — rather than by a permission flag. Anything outside them is outside what
was authorised, and that is checkable.
