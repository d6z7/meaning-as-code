# ADR — The connector seam: how MAC reaches data it must not know about

STATUS: **PROPOSED** · DATE: 2026-09-13 · **REVISED 2026-09-13 after adversarial review**
SUPERSEDES: nothing · MEASURED AT: `meaning-as-code` @ `cadb2bd`, re-measured at revision time

> Per CORE.md, an agent may write only PROPOSED. Ratification is the maintainer's act. Nothing in
> this record has been built; no file outside `decisions/` was modified in producing it or in
> revising it. Every measurement below was re-taken read-only. Nothing reached AWS or Bedrock.

> **Read §0 first.** The recommendation in this revision is not the recommendation in the first
> draft. §15 records the review that changed it, including the objections that were rejected.

---

## 0 · THE RECOMMENDATION CHANGED

Three adversaries attacked the first draft along three lenses — *instance specifics leaking into
MAC*, *false greens in every proposed check*, and *is this too much*. All three returned **does not
survive**. Six fatal objections were raised. Five are answered by changes made in this revision.

**The sixth is not answerable by any edit to this document**, and this estate's own rule then
applies: when a fatal stands and no change to the spec answers it, the correct outcome is a
different recommendation, not a patched one.

### 0.1 The fatal that changed the recommendation

**The code this record proposed to refactor is dead in the repository the record targets, and alive
in another repository that already contains two competing designs for the same seam.** Measured:

| Fact | Measurement |
|---|---|
| `from chat.sql import AthenaSQL` (`sdk/authoring/materialize.py:312`, `sdk/authoring/data_plane.py:221`) is unimportable in `meaning-as-code` | `ls services` → no such directory; `importlib.util.find_spec("chat")` → `None` |
| It **is** importable in `mac-platform` | `mac-platform/packages/mac-chat/src/chat/sql.py` exists |
| The two SDK copies have **already diverged** | `meaning-as-code/sdk/authoring/data_plane.py:212 profile_table(…, *, workgroup: str)` (required kwarg) vs `mac-platform/packages/mac-sdk/src/sdk/authoring/data_plane.py:210 profile_table(athena, db, table, cols, timeout_s=150.0)` (no such kwarg) |
| …and on their dependency contracts | `mac-platform/packages/mac-sdk/pyproject.toml:12-17` declares `boto3`/`botocore` as hard deps; `meaning-as-code/pyproject.toml` declares neither |
| `mac-platform` already ships an **engine-agnostic adapter protocol** | `packages/mac-runtime/src/mac_runtime/adapters/` — `base.py` (73 lines, `GroundingAdapter`, closed `AdapterErrorReason`), `athena.py` (302), `fake.py` (54), `safety.py` (74): **527 lines, two implementations, no plugin system, working** |
| …and a **third, competing** design for the same question | `mac-platform/packages/mac-okf-core/src/okf_core/sources.py`, 201 lines, whose docstring states it exists so "new source types (Redshift, BigQuery, …) can be added later WITHOUT a schema migration" via a closed `SUPPORTED_SOURCE_TYPES` allowlist, backed by deployed DynamoDB rows. The first draft never mentioned it. |

Adding a third home for this seam, in the repository holding the dead copy, is this estate's own
one-fact-one-home rule broken **in the act of fixing a boundary**. No wording in this document
repairs that. Only Ruling 12 can.

### 0.2 The second thing that changed it: the served denominator is one

Measured across every working directory including the OneDrive mirrors: **four `connection*.yaml`
trees exist in the entire estate, all in the private bundle repository** — `<domain>/<bundle-legacy>` and `<domain>/<bundle>`
(live), plus two published copies under `<domain>/<bundle-legacy>/artifacts/v*/`. Both live files are Athena, same
region, same workgroup family, same catalog, same two Glue databases, same `credentials.mode`.
Zero connection files exist in `meaning-as-code`, `mac-ontology-contoso`, `mac-platform`,
`mac-integration-kit`, `cap-ontology-workbench`, or the OneDrive DEV tree (21 further manifests, 0
connection files). The "second engine" does not use the SDK: contoso reaches DuckDB through
bundle-local scripts (`ask_server.py:30 duckdb.connect(...)`, `ask.py:53 subprocess.run(["duckdb", …])`)
and §9.4 gives it **zero required edits**. The word "connector" appears **zero** times in
`mac-integration-kit`'s `BOARD.md`, `ROADMAP.md` and `TARGET.md` — the estate's governing plan.

So the first draft's 8–10 day build served **one production connection file and one connector built
to be its own falsifier**.

### 0.3 The third: the checks that were supposed to make it safe do not work yet

The false-green lens built and **ran** a passing-but-wrong gate on this tree. The shared harness
every proposed gate rests on — `sdk/gate/contract.py`, which the first draft made the foundation
("None re-implements the verdict line") — **cannot attribute a finding to a reject class**.
Verified by reading it: `Outcome` is `(findings: int, examined: int, unit: str)` with no class
label, and the per-mutant assertion at `contract.py:157-159` is `out = contract.run(root); if
out.clean: failures.append(...)` — i.e. *"produced at least one finding, for any reason"*. Its own
docstring at line 122 promises "assert each is rejected **AS ITS OWN CLASS**". It does not.

**Every mutant table in the first draft was therefore an unverified claim.** That is not a reason to
abandon the gates; it is a reason to fix the harness **first**, and to stop quoting mutant counts as
coverage until it is fixed.

### 0.4 The recommendation, restated

**SPLIT THE RECORD INTO TWO TRACKS.**

> **TRACK A — build now, in `meaning-as-code`, ≈3.5–4.5 working days plus a 2-week soak.**
> The grammar, the security posture, the `answerable` repair, and the harness that makes any of it
> checkable. Every item is **repo-stable**: it is correct wherever the live SDK turns out to be,
> because it touches `mac.schema.json`, `mac_vocabulary.yaml`, `tools/`, `sdk/gate/` and
> `sdk/container/` — none of which is duplicated in `mac-platform`'s divergence.
>
> **TRACK B — do not build until Rulings 12 and 14 are answered.**
> The `Connector` base class, entry-point discovery, `guarded_import`, the hostile-connector suite,
> the permission surface, probes and receipts, and the extraction of engine coupling out of the SDK.
> When it is built, it is built **against whichever SDK Ruling 12 declares live**, and it **extends
> `GroundingAdapter`** and reconciles with `okf_core/sources.py` rather than adding a third protocol.

| First draft | Now | Why |
|---|---|---|
| Stage 0 — fix the live crash, land the coupling gate RED | **Track A** | independent of everything; the crash is live today |
| Stage 1a — declare `runtime.connector` | **Track A** | one line, free under today's schema |
| Stage 1b — the `$defs`, the gates, the security posture | **Track A** | the whole value of the record |
| Stage 5 — back `answerable` with something real | **Track A, folded into 1b** | it is the headline defect; the first draft repaired it **last**, 6.5–7.5 days in, behind machinery it does not need |
| Stage 2 — interface + two implementations + conformance | **Track B** | needs Ruling 14 (is a third-party connector a requirement now?) |
| Stages 3–4 — route materialize/harvest, extract coupling | **Track B, and re-filed against the live SDK** | needs Ruling 12 (§0.1) |
| Stage 6 — enforce after soak | **Track A** | soak is on the grammar, not the loader |
| Stage 7 — the billed probe | **Track B** | needs Ruling 8 |

**What Track A still commits the bundle to**, so Track B costs nothing extra when it lands: the
namespaced connector id (`§6.1`'s `ID_RE`), declared in the manifest, validated by pattern. A bundle
written today against Track A is already correct under Track B. **The part bundles commit to is the
identifier. The part that loads code is host-local and adds zero migration cost whenever it arrives.**

### 0.5 What Track A costs and closes

≈3.5–4.5 working days (up from the reviewer's 3, because the harness repair in §0.3 is now a
prerequisite rather than an assumption), ≈550–700 lines, 2 calendar weeks of soak, **zero billed
calls**. It closes:

- `connection.yaml` undefined by the standard → defined, routed, enumerated, validated.
- The secrets exemption you can claim by naming a file → a manifest-derived declaration.
- `credentials` with nowhere legal to put a secret → a schema fact, not a convention.
- `answerable` backed by `Path.exists()` → backed by named, printed conditions, with the tri-state.
- The serving address read out of a file the bundle may legally not ship → the manifest.
- `check_schema_isolation`'s silent skip, `run_gates.sh`'s array-shaped denominator, and the gate
  harness that cannot tell one reject class from another.

---

## 1 · What this decides, in five sentences

MAC becomes the JDK and a connector becomes the JDBC driver: the file that says *how to reach the
data* becomes a `$def` in `mac.schema.json` — an envelope MAC owns (`connector`,
`credentials {mode, ref}`, `config`) wrapping a payload MAC never reads — and a bundle **names** its
connector in `mac.project.yaml`, where the name is a dictionary key, never a path and never an
import target. `capabilities.answerable` stops being backed by `Path.exists()`
(`sdk/container/spec.py:47`, where a zero-byte file backs the claim today) and becomes backed by
named conditions, with a third state — *undetermined* — for the case where the bundle is fine and
this host cannot judge. **In Track A the first-party connector set is resolved as DATA — a shipped
index of JSON Schema files — so a mount validates a config with zero imports and zero network**;
loading connector *code* is Track B, behind an operator ruling. MAC's canon registers the
`connector` **namespace** and **no vendor product names**; the identifier is validated by pattern so
a third party needs nothing from MAC. Nothing here reaches the network, and the one billed call
(`probe`) is Track B and has no code path from `open_container` at all.

---

## 2 · The problem, measured

Every number below was re-measured on 2026-09-13 against the working tree, not recalled.

| # | Measurement | Command / site |
|---|---|---|
| 1 | `mac.schema.json` has **37 `$defs`** and a root `oneOf` of **16** members. **None** defines a connection file. The string `connection` occurs **0** times in the entire grammar. | `grep -c connection mac.schema.json` → `0` |
| 2 | `$defs/ProjectFile.properties.runtime` is literally `{"type": "object"}` — no `properties`, no `required`, no `additionalProperties`. | verified by loading the schema |
| 3 | `$defs/ProjectFile.properties.publish` is **also** bare `{"type": "object"}`. `publish.include` is returned verbatim by `sdk/cli/publish.py::_compile_items()` and copied with `shutil.copytree`. Nothing stops a bundle shipping `.py` inside a signed container. | same |
| 4 | `sdk/container/spec.py:47` backs `answerable` with file existence. **A zero-byte `connection.yaml` backs `answerable: true`.** | read at line 47 |
| 5 | `sdk/container/spec.py:43` falls back to the literal filename: `conn = rt.get("connection") or "connection.yaml"`. An undeclared file silently becomes the bundle's connection. | read at line 43 |
| 6 | `mac_vocabulary.yaml` registers nine namespaces. **`connector` is not among them.** `grep -rn connector mac_vocabulary.yaml mac.schema.json` → **0 hits**. | `grep` |
| 7 | `mac.schema.json` carries **exactly one** vendor token — `"Glue + Athena profile"` in `TableFile.profiled_via.description`. `aws` → 0, `boto` → 0, lowercase `glue` → 0. | `grep -ci` |
| 8 | Engine **driver coupling** lives in 4 SDK modules, half of it invisible to a module-level scan: `import boto3` at `sdk/cli/harvest.py:147` and `sdk/authoring/materialize.py:290`; **function-local** `from chat.sql import AthenaSQL` at `sdk/authoring/materialize.py:312` and `sdk/authoring/data_plane.py:221`; plus `sdk/authoring/test_harvest_hardening.py`. | `grep -rn` over `sdk/` |
| 9 | Engine **nouns** — the far larger population — live in **17 files** across `sdk/` and `tools/` (gates and tests excluded). | `grep -rlniE "athena\|glue\|boto3\|workgroup" --include="*.py" sdk tools \| grep -v '^sdk/gate/' \| grep -v test_ \| wc -l` → **17** |
| 10 | `sdk/gate/` holds **8** `check_*.py`; `tools/` holds **34**. `sdk/gate/run_gates.sh:15` names its gates in a **hardcoded 9-entry array** rather than deriving them from disk. | `ls … \| wc -l` |
| 11 | `_CONFIG_ALLOWLIST` (`sdk/gate/check_bundle_secrets.py:93-98`) is a hardcoded set of four **basenames**, applied as `in_config = p.name in _CONFIG_ALLOWLIST` at line 211. Anyone can claim the exemption by naming a file `connection.yaml`. | read |
| 12 | `sdk/gate/contract.py` — the harness under every gate in this record — **cannot attribute a finding to a reject class**. `Outcome` has no class field; the mutant assertion is `if out.clean: fail`. | read, lines 40-50 and 157-159 |

### 2.1 Three corrections to the briefing, each of which changes the design

**(a) "No manifest declares the connection" is false, and the true version is worse.**
`<domain>/<bundle>/mac.project.yaml:29-31` carries `runtime: {source: <BUNDLE>, connection: connection.yaml}`,
and `<domain>/<bundle-legacy>` carries the same plus `interpreter` and `model_catalog`. So the declaration exists —
and is **dead twice over**: `sdk/authoring/connection.py:35` hardcodes `_read(cr / "connection.yaml")`
and never opens the manifest, and <bundle>'s declared value is byte-identical to `spec.py:43`'s
fallback, so the only manifest in the estate that declares a connection declares no information.
The gap is not "nobody declares it". It is **"a declaration that looks governed and is not."**

**(b) <bundle> is already failing validation, and nobody noticed.** Executed:

```
<bundle>      ok=False  errors=["capability 'answerable' claimed but NOT backed by contents"]
contoso   ok=True   errors=[]  answerable=False
tpch      ok=True   errors=[]  answerable=False
```

<bundle> declares `answerable: true` at `mac.project.yaml:13` with a five-line comment asserting the
claim is "HONEST", and `_backed_capabilities` returns `False` because <bundle> declares no
`runtime.interpreter`. It has been served anyway, because `open_container(require_trust=None)`
downgrades exactly `"claimed but NOT backed"` to a warning on the reader path. **The capability
checker has been red on the estate's flagship bundle and the reader path has been swallowing it.**

**(c) The Athena path in this repo is dead — and what that does and does not justify.**
`sdk/authoring/data_plane.py:28-33` inserts `<repo>/services/chat/src` onto `sys.path`; that
directory does not exist here. `data_plane.py:381` calls
`profile_table(athena, db, table, cols, workgroup=workgroup)` where `workgroup` is AST-verified
unbound in `process()` and is not a module global — every call raises `NameError` before reaching
the unimportable executor.

> **REVISED.** The first draft inferred from this that a *contract* rather than a cleanup was
> needed. That inference is withdrawn. Its origin is commit `93ca8a6` (2026-09-13 01:26), which made
> `profile_table(..., *, workgroup: str)` required precisely to stop one ontology's workgroup being
> compiled into the tooling — and did not thread it through the caller. **An eight-hour-old keyword
> regression with no test covering `process()` is evidence for a missing test.** It is Stage A1's
> whole content and it justifies nothing beyond itself. What the dead path *does* remove is most of
> the "don't break the working thing" risk in this repo — and what it *adds*, per §0.1, is the
> question of whether this repo is where the refactor belongs at all.

### 2.2 The defect class, named

This estate's dominant defect is the **zero-denominator pass**: a check that reports clean having
examined nothing. `spec.py:47` is that defect sitting inside the function whose docstring promises
capabilities are "enforceable, not decorative". Live instances in the blast radius:

- `tools/check_schema_isolation.py:120` returns **0 (PASS)** when no file declares a serving schema.
  `ontology/planes/serving.md:26` already names this: *"a missing connection.yaml silently disables
  the collision gate"* — the gate that exists because one source's views overwrote gold's
  `dim_country`/`dim_model` on 2026-08-13.
- `sdk/authoring/materialize.py:345 _show_tables()` swallows its exception and returns `set()`,
  which reads to the operator as *"no collisions"*.
- `sdk/gate/run_gates.sh` prints `9/9 gate self-tests green` where the denominator is the hardcoded
  array, not the directory.
- **NEW, and it is the one that matters most:** `sdk/gate/contract.py` counts a mutant as caught
  when the gate produces *any* finding. A gate implementing none of its declared reject classes
  passes its own self-test (§0.3). The instrument this estate uses to prove gates work is itself an
  instance of the defect it exists to prevent.

Any design that closes `spec.py:47` while leaving those four is a net loss, because it will be
quoted as progress. They are therefore in Track A, each bound to a specific commit in §11.

---

## 3 · The architecture

The operator's picture, unchanged:

```
  <data source of xy type>  ──  <MAC's plug-in connector to ontology>  ──  <generic ontology>
```

Three parts, and the whole design is the answer to *what does each one own*.

| Part | Analogy | Owns | Must never contain |
|---|---|---|---|
| **MAC** (`meaning-as-code`, public) | the JDK | the connection **envelope** schema, the identifier grammar, the error taxonomy, the connector protocol, the gates, the own-schema policy | a source name, a warehouse schema, a brand, a domain measure, a credential — **and no vendor product name in `mac_vocabulary.yaml` or `mac.schema.json`** |
| **The connector** (first-party extra, or a third-party wheel) | the JDBC driver | the engine's dialect, its auth mechanics, its config schema, its API shapes, its cost class | any value belonging to one deployment — a region default, a workgroup, an account |
| **The bundle** (`<domain>/<bundle>`, `mac-ontology-contoso`) | the application's config | *which* connector (in `mac.project.yaml`), and *how to reach it* (in the connector config file): non-secret reference handles only | a credential **value** — there is no legal slot for one, by schema |

And the thing none of them owns: **credential values resolve at runtime**, from an ambient chain or
a key manager, given a handle. They exist in no file this design writes.

> **REVISED — the MAC row lost the word "registry".** The first draft's §6.6 put `athena` and
> `duckdb` into `mac_vocabulary.yaml` as canon members, which is the exact act this row forbids and
> which §6.1 of the same draft argued against one page earlier. The canon now registers the
> **namespace** and nothing else; the first-party set is a shipped, diffable **index file**, which is
> software, not canon. See §6.4 and §15.1.

### 3.1 The rule that decides every boundary question

> **MAC owns *what* is asked and what the answer must look like. The connector owns *how* it is
> asked and *of whom*.**

Operationally: every string that is SQL, every dict key that is a vendor API shape, every parameter
placeholder convention, and every module that imports a vendor SDK crosses into the connector. Every
plan, every schema, every file layout, every refusal and every verdict stays in MAC.

**The scope of v1, stated because the artifact must match the claim.** The connector contract in §4
is split so that a source with no SQL, no DDL and no identifier quoting can conform. But **the only
sources in scope for v1 are relational**: Athena and DuckDB, both SQL. A REST endpoint, a Parquet
directory, a SharePoint list or a graph store is *permitted* by the contract and *unbuilt*. Saying
this here is the point: the first draft promised "MAC owns *what* is asked" while its base class
fixed the language it is asked in.

### 3.2 The falsifier, and what it can and cannot falsify

`mac-ontology-contoso` is DuckDB, has **no `connection.yaml`, no credentials, no region, no
workgroup, no catalog**, and validates today with `ok=True, errors=[], warnings=[]`.

> **If DuckDB cannot satisfy the interface without an Athena word appearing in the base class, the
> interface is wrong.**

> **REVISED — the honest limit of that falsifier.** Athena and DuckDB are *both SQL engines* with
> quoted identifiers, catalog/schema qualification, `CREATE OR REPLACE VIEW`, column types and
> `EXPLAIN`. **Two SQL engines can detect an AWS assumption and are structurally incapable of
> detecting a SQL assumption.** The first draft's kill criterion 1 was written in the narrow unit —
> it fires on `Optional[workgroup]` and would sail straight past `read(sql: str)`. So when Track B
> builds the conformance suite, it ships a **third fixture: a non-SQL connector over a directory of
> CSV/Parquet files** — no SQL, no DDL, no credentials (`mode: none`), `supports` omitting
> `create_or_replace_view` and `explain`. It costs nothing, runs offline, ships no driver, and it is
> the only fixture that can answer the question the suite claims to answer. **The conformance verdict
> prints its unit: `3 connectors × N assertions, 1 non-SQL`.**

And the constraint that outranks everything else in this document:

> **A bundle with no connection is browsable, renderable, and simply not answerable. That is a
> correct state, not an error, not a warning, and no gate may report it as one.** 19 of the estate's
> 24 manifests are in that state. It is the majority case, not the edge case.

**That constraint is now testable.** In the first draft it could only be written as an `extra`
lambda in the gate harness, where `lambda base: ""` passes — i.e. the single property the document
called non-negotiable was the one property the harness could not check. §10.0 fixes the harness
before any gate is written.

---

## 4 · The connector contract

**This whole section is TRACK B.** It is specified here so Track A's identifier and envelope are
forward-compatible, and so Ruling 14 can be answered against a real shape rather than a gesture.
Nothing in §4 is built until Rulings 12 and 14 are answered.

### 4.1 Derived, not invented: the eleven operations the SDK performs today

| # | Operation | Call site today |
|---|---|---|
| 1 | Build an authenticated session | `sdk/cli/harvest.py:146 _session()`; `sdk/authoring/materialize.py:287 _new_athena_client()` |
| 2 | Enumerate relations in a namespace | `harvest.py:152 _tables()` → `glue.get_tables` (paginated) |
| 3 | Describe a relation's columns + verbatim types | same call |
| 4 | Enumerate the serving namespace (collision snapshot) | `materialize.py:345 _show_tables()` |
| 5 | Profile a relation (rows, null share, distinct, min/max) | `data_plane.py:212 profile_table()` |
| 6 | Quote an identifier | `data_plane.py:229`; `materialize.build_lookup_sql` |
| 7 | Read-only query | `AthenaSQL.run()` → `{columns, rows, row_count, truncated}` |
| 8 | Create or replace a serving view (DDL) | `materialize.py:298 _athena_executor._ddl()` |
| 9 | Verify a created view selects | `SELECT 1 FROM vs.n LIMIT 1` |
| 10 | Explain / dry-run a plan | `mac_runtime.adapters.base.GroundingAdapter.validate` → `EXPLAIN` |
| 11 | Execute an answering plan with bound params | `mac_runtime.adapters.athena.AthenaAdapter.execute` |

Operations 10–11 are already specified in `mac-platform` as `GroundingAdapter` — **527 lines, two
implementations, working.** The first draft called it "prior art and this contract is its superset".
**REVISED: that is not a licence to write a rival.** Per §0.1, when Track B is built it is built as
an *extension of* `GroundingAdapter` in whichever repo Ruling 12 declares live, and it reconciles
with `okf_core/sources.py`'s `SUPPORTED_SOURCE_TYPES` rather than ignoring it. Three designs for one
seam is the failure mode; this record must not become the third.

### 4.2 The dry half / wet half split — the invariant that must survive

`materialize.plan_materialization()` and `plan_lookups()` are **pure** today: they read descriptors
and `connection.yaml` and return the exact SQL with zero AWS calls, and `test_harvest_hardening.py`
proves it offline. Any interface that loses this is a regression however clean it looks.

> **REVISED — the contract is split in two, because the first draft's single base class was
> SQL-warehouse-shaped in its REQUIRED tier.** Its one required I/O verb was `read(self, sql: str,
> …)` — the parameter is literally named `sql` — and `quote_identifier`, `qualify`,
> `render_view_ddl` and `render_profile_sql` sat under "REQUIRED", so a connector to a source with
> no DDL and no identifier quoting had to implement view-DDL rendering to conform. `explain(sql, …)`,
> `SourceError.engine_query_id` and `SourceErrorReason.query_cancelled` carried the same assumption
> into the error taxonomy. The operator's picture is `<data source of xy type>`; that contract said
> every data source is a SQL warehouse, **inside the generic instrument**.

```python
# sdk/connector/base.py   (TRACK B)

class Connector(abc.ABC):
    """Everything true of ANY source. No SQL, no DDL, no identifier quoting."""

    # ---- identity + declaration: pure data, read without instantiating ----
    id: ClassVar[str]                        # "mac.connector.athena"
    credential_modes: ClassVar[frozenset[str]]
    permissions: ClassVar[frozenset[str]]    # mac.connector_permission — see §8.4
    probe_cost: ClassVar[str]                # "free" | "billed" — defined in §7.5c
    supports: ClassVar[frozenset[str]]       # the OPTIONAL verbs this class implements

    # ---- TIER 1 · DRY: offline, free, no socket. REQUIRED. ----
    @classmethod
    def config_schema(cls) -> Mapping[str, Any]: ...
    @classmethod
    def validate_config(cls, conn: Mapping) -> Sequence[ConfigProblem]: ...
    @classmethod
    def credential_plan(cls, conn: Mapping) -> CredentialPlan: ...
    def qualify(self, ref: RelationRef) -> str: ...   # segments -> an engine address

    def __init__(self, conn: Mapping, *, client: Any | None = None) -> None: ...
        """MUST NOT touch the network. boto3's default chain reaches IMDS at client
           construction, so the engine client is built lazily on first I/O — the property
           mac_runtime.adapters.athena already holds and tests (test_construction_is_network_free)."""

    # ---- TIER 1 · WET: the ONE required I/O verb, engine-neutral ----
    @abc.abstractmethod
    def read(self, request: ReadRequest) -> ReadResult: ...
        """One read-only request. MAC asserts exactly one precondition about it (§4.2a).
           What a request MEANS is the connector's; how it is spelled is the connector's."""

    # ---- TIER 1 · OPTIONAL: base raises ConnectorCapabilityMissing ----
    def list_relations(self, namespaces: Sequence[Sequence[str]]) -> Sequence[RelationRef]: ...
    def describe_relation(self, ref: RelationRef) -> RelationSchema: ...
    def profile_relation(self, ref: RelationRef, cols: Sequence[ColumnSpec]) -> RelationProfile: ...
    def list_objects(self, namespace: Sequence[str]) -> set[str]: ...

    # ---- TIER 2 · BILLED on some engines. Never automatic. ----
    def probe(self) -> ProbeResult: ...


class SqlConnector(Connector):
    """Everything true only of a source you address in a statement language.
       Athena and DuckDB subclass THIS. A CSV-directory connector subclasses Connector."""

    read_verbs: ClassVar[tuple[str, ...]]    # ("select","with","show","describe","explain")
    param_style: ClassVar[str]               # ":name" | "?" | "$1" — the CONNECTOR's, not MAC's

    def quote_identifier(self, name: str) -> str: ...
    def render_view_ddl(self, ref: RelationRef, select_body: str) -> str: ...
    def render_profile_sql(self, ref: RelationRef, cols: Sequence[ColumnSpec]) -> str: ...
    def orderable(self, engine_type: str) -> bool: ...
    def explain(self, statement: str, params: Mapping = {}) -> None: ...
    def create_or_replace_view(self, ref: RelationRef, select_body: str) -> None: ...
```

#### 4.2a MAC does not parse SQL — including parameter syntax

> **REVISED, and this was a real contradiction.** The first draft retired `_ORDERABLE` on the ground
> that **"MAC never parses a type name again"** — and then, two paragraphs later, moved
> `adapters.safety.assert_bound_params_only` into the generic contract as "the shared precondition".
> That function, read at `mac-platform/packages/mac-runtime/src/mac_runtime/adapters/safety.py`, is a
> regex scanner over statement text that (a) **pins one bind syntax** — its own module docstring
> says *"04 §3/§4 mandate bound params but do not pin a placeholder syntax … This module adopts named
> `:param_name` placeholders"* — and (b) rejects **any** single-quoted string literal as
> "presumptively an interpolated value" (`_QUOTED_STRING_RE = re.compile(r"'[^']*'")`). Promoting it
> into MAC makes MAC the owner of one dialect's parameter style and makes legal SQL illegal: an
> Athena `date '2024-01-01'`, a DuckDB `read_csv('…')`, or any connector-rendered view body with a
> quoted constant.

The split, by the same principle that retires `_ORDERABLE`:

| Who | Asserts |
|---|---|
| **MAC** | the **structural** fact it owns: every user-derived value travelled in `request.params`, and none was formatted into the statement by the planner. Checkable at the **plan boundary**, without reading one character of SQL. |
| **The connector** | that the statement matches its own `param_style`, and that the head verb is in its own `read_verbs`. Enforced **inside its own `read()`**, raising `ConnectorContractViolation`. |

`assert_bound_params_only` therefore **stays where it is**, in `mac_runtime.adapters`, as the Athena
adapter's own precondition — not promoted, not duplicated.

**Data shapes** are MAC's, not the engine's. `RelationProfile.as_dict()` returns today's exact
`{"row_count": int, "columns": {col: {"null_frac","distinct","min?","max?"}}}` so
`data_plane._profile_md` is untouched. `ColumnSpec.type` is the engine's **verbatim** type string and
`orderable()` is the connector's verdict about it, so **MAC never parses a type name again** — which
retires `data_plane.py:48-58 _ORDERABLE`, eleven Hive/Presto type names living in the generic
instrument.

> **CORRECTION.** The first draft justified the verbatim-type decision by writing that
> "`TableFile.columns[].type` is already documented as 'verbatim glue type'". **It is not.** Measured:
> that property is `{"type": "string"}` with **no description at all**. The string
> `<verbatim glue type>` lives at `sdk/authoring/data_plane.py:77`, inside `_DP_SYS_TEMPLATE` — **the
> system prompt MAC ships to a model** — three lines below `provenance: "Glue + Athena profile"` at
> line 75 and one line below *"Given ONE raw **Glue** table"* at line 68. The consequence of the
> misattribution is that the prompt appeared on **no removal list**: the first draft's Stage 4 deleted
> `_ORDERABLE` and the `services/chat/src` `sys.path` hack and left the prompt alone, so MAC would
> still have instructed a model to emit Glue nouns on the day the coupling floor printed `0`. All
> three strings now join the deletion list (§12, G4 class 5), using the template's existing
> `{{SOURCE_LABEL}}` / `{{VIEW_SCHEMA}}` sentinel mechanism: two more sentinels,
> `{{CATALOG_NOUN}}` and `{{PROFILE_PROVENANCE}}`, filled from the resolved connector.

`CredentialPlan.__repr__` **is** the redacted view; no field may hold a secret, and a gate seeds an
`AKIA…`-shaped value to prove it (§10, G3/R5).

### 4.3 `supports`, not `hasattr`

`supports` is the single declaration; the base class implements each optional verb as
`raise ConnectorCapabilityMissing(self.id, verb)`. The conformance suite asserts
`verb in supports` ⟺ the method is overridden, so **the declaration cannot drift from the
implementation**. A host checks `supports` *before* calling; the raise is the backstop, not the
mechanism. Duck-typed `hasattr` sniffing was rejected: it cannot be gated and it drifts silently.
*(The false-green lens endorsed this device explicitly; it is unchanged.)*

### 4.4 What a host does when an optional verb is absent

| Verb | Capability degraded | Host behaviour | Exit |
|---|---|---|---|
| `list_relations` | `harvestable`, collision snapshot | `--mode data` requires explicit `--relations`; materialize prints `SHOW TABLES: unavailable — collision check NOT performed` and proceeds | 0 |
| `describe_relation` | `harvestable` | `--mode data` refuses: it is the input | **2** |
| `profile_relation` | profile-grounded DQ | authoring proceeds **profile-free**; the prompt receives `(no live profile available)`; every emitted `dq_issues[].confidence` is forced to `Q`; the run line prints `profiled 0 of 14 relation(s)` | 0 |
| `create_or_replace_view` | `materializable` | dry-run still works (the planner is pure); `--accept` refuses | **2** |
| `explain` | plan pre-validation | `validate()` is a no-op; the trace records `validated: false` | 0 |
| `probe` | live liveness evidence | `probe: not implemented by <id>`; `answerable` rests on offline evidence | 0 |

**The governing rule, stated once: a missing optional verb is never a crash and never a FAIL. It is
either a degraded capability (exit 0, with the degradation *printed*) or a could-not-run (exit 2). It
is never silently absorbed.** `materialize._show_tables`'s `except Exception: return set()` is
specifically upgraded under this rule — an empty set reads as "no collisions" inside the very step
whose guardrail exists because of a real overwrite.

> **Every "prints" in that table is now a checked assertion, not prose.** The first draft relied on
> at least seven printed disclosures and specified no assertion anywhere that reads a gate's output
> or its exit code — `run_self_test` never calls `main()`, never captures stdout, never checks a
> code. §10.0 adds `expect_line` to the harness for exactly this.

### 4.5 The write seam is one narrow verb, off by default

`create_or_replace_view(ref, select_body)` is the **only** write verb, and it lives on
`SqlConnector`, not on `Connector`. Deliberately not `execute_write(sql)`: a generic write verb
re-opens the 2026-08-13 gold-overwrite incident on every connector including third-party ones, and it
makes "can this connector write?" a property of a string the caller passed — so nothing can gate it
and nothing can answer it offline. Today's hybrid `executor(sql)` dispatching on `is_read_only(sql)`
(`materialize.py:298`) has exactly that shape and is retired.

Two guards keep their single home in front of it:

1. `materialize.assert_own_schema(...)` (`materialize.py:71-99`) — **stays in MAC**. *"A source
   materializes only into its own namespace"* is a policy about ontologies, not about Athena. If it
   followed the SQL into the connector, a DuckDB bundle would get no guardrail and the incident would
   be reachable again on a second engine. (It now compares **namespace segment lists**, §5.5.)
2. **`allow_ddl` defaults to `false`**, and lives only in the deployment overlay. A published,
   shipped bundle can never be used to write.

Stated plainly, because the contract cannot enforce it: `create_or_replace_view` hands the connector
a SELECT body it composes into DDL, and a careless connector can append anything. `assert_own_schema`
guards the **target**, not the body. **DDL through a third-party connector is a trust decision, not a
technical guarantee.**

### 4.6 Error taxonomy → exit codes

Four classes. The mapping is the whole point: *"could not run" is the one honest answer available,
and it is never a finding* — `tools/_plugin.py`'s founding rule, applied verbatim. *(The false-green
lens singled this out as one of the devices that holds: the exit code is a property of the raise, not
of the catcher.)*

```python
class ConnectorError(Exception): ...

class ConnectorConfigError(ConnectorError):
    """The BUNDLE's config is wrong. Detectable offline and free."""
    # -> EXIT 1. A finding ABOUT THE BUNDLE.

class ConnectorUnavailable(ConnectorError):
    """The connector could not be used. Not the bundle's fault, not the source's.
       - the declared id resolves to nothing installed
       - the extra is missing ("pip install meaning-as-code[athena]")
       - import raised ANYTHING, SystemExit included
       - a declared credential mechanism is not wired
         (today: secretsmanager/ssm, sdk/authoring/connection.py:45 raises NotImplementedError)"""
    # -> EXIT 2. COULD NOT RUN.

class ConnectorCapabilityMissing(ConnectorUnavailable): ...   # -> EXIT 2, per §4.4
class ConnectorAmbiguous(ConnectorUnavailable): ...           # -> EXIT 2, per §6.5

class ConnectorContractViolation(ConnectorError):
    """The connector or its caller broke THIS contract. Never softened, never degraded:
       a user value formatted into a statement instead of travelling in params; a non-read
       verb at read(); `supports` claiming a verb the class does not override; an entry point
       declaring a mac.* id; a CredentialPlan carrying a secret-shaped value; a connector name
       that is path-shaped."""
    # -> EXIT 1, loudly, always.

class SourceError(ConnectorError):
    reason: SourceErrorReason
    engine_request_id: str | None      # renamed from engine_query_id — not every source has queries
```

`SourceErrorReason` is `mac_runtime.adapters.base.AdapterErrorReason` **extended in place** (not
duplicated into MAC — §0.1), plus two additions:

| reason | meaning | exit |
|---|---|---|
| `request_failed` | bad request, relation not found, type error | **1** — a real finding |
| `cancelled` / `timeout` / `execution_limit` | nothing was judged | **2** |
| `unauthorized` *(new)* | credentials resolved, not permitted | **2** |
| `unreachable` *(new)* | endpoint / DNS / network | **2** |
| `config_error` | *retired* → `ConnectorConfigError` (exit 1) | — |
| `unbound_literal` | *retired* → `ConnectorContractViolation` (exit 1) | — |

A single `ConnectorError` with a `reason` field was rejected: it puts the 0/1/2 decision at every
call site, which is how a could-not-run becomes a FAIL.

**Precedence, stated once so the codes cannot race: a genuine finding outranks a could-not-run.** A
bundle that both leaks an account id and names an uninstalled connector is a FAIL. Absent a finding,
unrunnable beats PASS.

---

## 5 · The bundle declaration — **TRACK A**

### 5.1 The split, and the disagreement it settles

> **ARCHITECT DISAGREEMENT.** Four of the eight put the connector identity in `connection.yaml`; two
> put it in `mac.project.yaml`. The argument *for* the config file is real:
> `sdk/authoring/connection.py::load_connection` already overlays `connection.local.yaml`, which is
> what would let a site run Athena in production and DuckDB locally without touching the manifest.
>
> **CHOSEN: the manifest.** The overlay argument is exactly what defeats it. `connection.local.yaml`
> is gitignored and `$DEPLOYMENT_CONFIG` is an arbitrary path from the environment. If the connector
> identity lives in the overridable file, **an out-of-band file can substitute the code that loads
> into the host process.** An override chain must be able to change *where you point*, never *what
> code runs*. Independently: which engine a bundle grounds on is a fact about the bundle — contoso
> *is* DuckDB — and the manifest alone should answer "what does this bundle need?" without opening a
> file the bundle may not ship.

```
mac.project.yaml#runtime.connector    →  BUNDLE.      Not overridable. MAC reads all of it.
mac.project.yaml#runtime.connection   →  BUNDLE.      The PATH to the config file.
<that path>                           →  DEPLOYMENT.  Overridable. MAC reads the envelope only.
  .credentials                        →  MAC defines the SHAPE. Never a value.
  .config                             →  OPAQUE. Handed verbatim to the connector's config schema.
```

One sentence: **MAC reads the whole manifest and three keys of the config file.**

### 5.2 The manifest

```yaml
runtime:
  source: <BUNDLE>
  connector: mac.connector.athena       # NEW. Namespaced. Not overridable.
  connection: connection.yaml           # already present in <domain>/<bundle-legacy> and <domain>/<bundle>
  interpreter: runtime/<bundle>_interpreter.md
  model_catalog: runtime/model_catalog.yaml
serving:
  namespace: [<database>, <schema>]     # MOVED here from connection.yaml — see §5.5
```

`$defs/ProjectFile.properties.runtime` stops being `{"type": "object"}` and closes on exactly the
**four keys measured across all 26 manifests in the estate** (`source`, `interpreter`, `connection`,
`model_catalog`) plus `connector`. Closing it costs nothing today and makes a sixth key arguable
rather than silent — and it is what shuts the measured hole where
`runtime: {conection: …, credentials: {mode: plaintext, value: hunter2xyz}}` validates **clean**
against today's schema *and* returns zero findings from `check_bundle_secrets`, because
`mac.project.yaml` is in `_CONFIG_ALLOWLIST` and the key is spelled `value`, not `password`.

> **REVISED — the MAC005 derivation claim is withdrawn.** The first draft claimed that *"a bundle
> has a connection.yaml and the manifest never says so"* becomes a MAC005 warning **with no emitter
> written**, derived by the adoption register. Measured, the derivation does the opposite on both
> sides. The slot derivation is correct (`tools/mac_checks_adoption.py:248-263 dotted()` →
> `runtime.connection`; `:293` routes it to `dated` because the description carries `OPTIONAL`), but
> severity is `D.WARNING if a.applicable else D.INFO` (`:832`) and `a.applicable` counts only sites
> where the **parent object exists** (`:641-646`, `o.parent` → `runtime`). The adoption register
> never looks at the filesystem for a connection document. So:
>
> - a bundle carrying `connection.yaml` with **no `runtime:` block** — the shape an author who never
>   learned the key actually writes — has `applicable = 0` and is reported **INFO, i.e. silent**;
> - a bundle **with** a `runtime:` block and **no connection file at all** is reported **WARNING** —
>   the "nagged for declining a mechanism it has no use for" case §9.4 says must not happen.
>
> **G1 owns this instead**, through its `undeclared-connection` reject class, which has the
> filesystem predicate the adoption register lacks. The adoption register stays an adoption register.

**A bundle with no `runtime:` block is well-formed, readable, renderable, and not answerable.** That
is contoso, tpch, shop, and 16 others.

### 5.3 The connector config file — envelope and payload

Basename stays `connection.yaml`. It appears in the secrets allowlist, in two bundles'
`publish.include`, in `check_schema_isolation.CONN_CANDIDATES`, in the harvest scaffold, and — per
`sdk/authoring/connection.py:4` — in separate copies of the contract held by the wiki backend and
mac-runtime. A rename forces cross-repo coordination for nothing the declared path does not already
buy. **The content is versioned instead.**

```yaml
spec_version: mac.connector/1      # the connector-protocol generation
credentials:                       # MAC-DEFINED SHAPE. Exactly two keys. additionalProperties: false.
  mode: ambient
  ref: null
config:                            # OPAQUE TO MAC. Validated by the connector's config schema.
  region: eu-west-1
  workgroup: <workgroup handle>
  catalog: AwsDataCatalog
  output: null
  glue_databases: {fact: …, dims: …}
  account: null                    # derived at runtime via STS. NEVER shipped.
```

> **ARCHITECT DISAGREEMENT (naming).** `config:` vs `settings:` vs `engine_config:`.
> **CHOSEN: `config:`.** `settings` is vaguer; `engine_config` is redundant inside a file whose whole
> subject is the engine. No technical consequence — recorded so the choice is not re-litigated.

A file with **no `spec_version`** is read as the legacy flat shape (today's <bundle-legacy>/<bundle> file, verbatim)
by a compatibility reader, for exactly one spec version. The gate reports the legacy count as a
**denominator**, not a failure.

### 5.4 Credentials: one slot, and it is a handle

> **`credentials` has exactly two keys — `mode` and `ref` — `additionalProperties: false`. There is
> no third key, ever, for any connector. Absent is legal and means "no credential required".**

That one constraint does all the work. Athena gets `{mode, ref}` unchanged. DuckDB omits the block. A
future Postgres connector wanting user + password + client cert does **not** get three keys; it gets
one `ref` resolving to a compound secret in whatever manager the deployment runs. *Richer auth needs
a richer secret, not a richer file.* A per-connector credentials schema was rejected outright: the
moment a connector may declare its own fields, one of them will be a password field and the
structural guarantee is gone. *(All three lenses endorsed this envelope. It is the record's strongest
device and it is unchanged.)*

**The security posture stops being a convention enforced by a pattern-matcher and becomes a schema
fact: there is nowhere to put a secret.**

> **REVISED — but that sentence is true of `credentials` only, and the first draft over-claimed the
> fallback.** It said `check_bundle_secrets` "remains as defence in depth over the opaque `config:`
> block, where account ids and generic secrets stay blocked everywhere". Measured by **executing**
> `check_bundle_secrets._scan_text(..., in_config=True)` on this tree:
>
> | probe | result |
> |---|---|
> | `password: hunter2xyz` | **CAUGHT** |
> | `secret: hunter2xyz` | **CAUGHT** |
> | `client_secret: abc123def456` | **MISSED** — the `\b` at `check_bundle_secrets.py:50` cannot match after `_` |
> | `api_key: sk_live_abcdef123456` | **MISSED** |
> | `token: ghp_abcdefghijklmnop12345` | **MISSED** |
> | `auth_token: …` · `passphrase: …` · `private_key_path: …` | **MISSED** |
>
> And the detectors that do fire on account ids are **AWS-shaped by construction**: `aws_access_key_id`,
> `aws_secret_access_key`, `aws_session_token`, `_ARN_ACCOUNT = arn:aws…(\d{12})`, and
> `_BARE_ACCOUNT = \b\d{12}\b` gated by `_ACCOUNT_CONTEXT`. A GCP project id, an Azure subscription
> GUID, a Snowflake account locator, or a JDBC URL with an inline password passes all of them. **So
> for every non-AWS connector — the ones this design exists to enable — the opaque payload had no
> defence at all, and MAC's own secret-detection is itself an instance specific.**
>
> Three changes, all in Track A:
> 1. **Say the limit out loud** wherever the `config:` guarantee is quoted: *"the residual scan over
>    `config:` is AWS-shaped and catches nothing else."*
> 2. **Widen `_GENERIC`**: `password_inline`'s alternation becomes
>    `(?:password|passwd|pwd|secret|token|api[_-]?key|passphrase|credential)` and its leading `\b`
>    becomes `(?<![a-z0-9])` so `client_secret` and `auth_token` match. One mutant per new key name.
> 3. **Give the connector the job only it can do** (Track B): the connector's config schema marks
>    each of its own keys `x-mac-sensitivity: handle | value | public`, and G6 gains a reject class
>    for any `config` key its connector declares `value`-bearing. That keeps MAC ignorant of vendor
>    secret shapes — the point — while making the guarantee real for engines MAC has never heard of.

> **ARCHITECT DISAGREEMENT (mode spellings), and a revision.** One architect proposed keeping the
> measured `aws-chain | profile | secretsmanager | ssm` (`sdk/authoring/connection.py:48-68`).
> Another proposed a brand-free closed vocabulary. **CHOSEN: brand-free** — the measured set is four
> AWS product names doing the work of three ideas.
>
> **REVISED: the four-member set was too small, and it was derived from one cloud's chain.** One
> resolution mode plus one opaque handle fits password-shaped auth and fails where **the mechanism
> IS the auth and there is no secret to fetch**: interactive/browser SSO (Snowflake external browser,
> Azure device code), mTLS client certificate, Kerberos/GSSAPI. None of those is `ambient`,
> `named_profile`, `secret_manager` or `none`.
>
> **`mac.credential_mode` is now: `ambient` · `named_profile` · `secret_manager` · `interactive` ·
> `client_certificate` · `none`**, closed, with the vocabulary description stating plainly that a new
> member is a **framework release**. The AWS spellings are accepted by the Athena connector as its
> own aliases under `mac.connector/1` and reported MAC003 (`fact-restated`, warning).

### 5.5 What leaves the config file: the serving address

`<domain>/<bundle>/mac.project.yaml` declares `connection.yaml` `out_of_scope` with the reason *"Deployment
configuration, carries no meaning."* Two MAC components then read meaning out of it:

- `tools/check_schema_isolation.py:66` reads `view_schema`/`view_database` to derive a gate's entire
  acceptance test — the gate that exists because of the gold overwrite.
- `sdk/project/source_ident.py:64` reads the same keys to resolve the bundle's identity.

**You cannot call a file meaningless and then ground a collision gate on it.**

> **ARCHITECT DISAGREEMENT (three-way).** `view_schema` was placed (a) as a MAC-owned top-level key
> in the config file, (b) inside the opaque payload, (c) in `mac.project.yaml#serving`.
> **CHOSEN: (c).** (a) leaves one documented exception inside the boundary, and one exception is how
> a boundary stops being a boundary. (b) leaves the collision gate reading a file the bundle is
> permitted not to ship — which is how the gate silently turns itself off today.

> **REVISED — the spelling, not the destination.** The first draft chose `serving.schema` and
> `serving.database`. Measured: `$defs/ProjectFile.properties.serving` is
> `{type: object, additionalProperties: false, properties: ['naming']}`, so those two keys become
> **core manifest grammar inherited by every bundle regardless of engine** — including a bundle
> grounded on a file lake, an API or a graph store, none of which has a "database". The motive was
> right and the destination is right; the nouns were the engine's.
>
> **`serving.namespace: [<segment>, …]`** — an ordered list of namespace segments, engine-neutral.
> `assert_own_schema` and `check_schema_isolation` compare **segment lists**, unchanged in substance;
> `own_view_schema()` keeps returning the last segment for its existing string callers.
> `Connector.qualify(ref)` — already in §4.2 — is exactly the verb that turns segments into an engine
> address, which also removes any need for `render_view_ddl` to know what a database is.
> <bundle> (measured: `view_database` and `view_schema` are two distinct handles) becomes a two-segment
> list; a single-namespace engine like DuckDB uses one.

**This move is only safe if one other change lands with it, and it is not separable.**
`check_schema_isolation.py:120` returns **0 (PASS)** when no file declares a schema (verified:
`if not own: print("… (skip)"); return 0`). Under `sdk/gate/contract.py::verdict`, examined-zero is
**exit 2**. Moving the key while leaving the skip at exit 0 would convert a live gate into a
zero-denominator pass **by this change's own hand**. One commit, with a mutant seeding a bundle whose
serving address has moved.

### 5.6 Multiple connectors: declarable, not federatable

`runtime.connector` is a string today because every manifest in the estate that declares a connection
declares exactly one. The plural form (`runtime.connectors: {name: id}` plus `table.connector` on
`$defs/TableFile.table`) is specified as a **later additive bump** and is not built now.

**Out of scope, explicitly: cross-connector query execution.** A rule or edge whose two sides resolve
through different bindings would be a **FAIL**, not a silently-attempted federation — because nothing
in the estate executes a federated join, and specifying a join planner nobody has built is exactly
the "prose guarantee nothing checks" defect this record exists to remove.

---

## 6 · Identifier, registration, versioning

### 6.1 The identifier — **TRACK A**

```
<namespace>.connector.<name>[/<config-major>]

mac.connector.athena/2          first-party, config contract major 2
mac.connector.duckdb/1          first-party
acme.connector.snowflake/1      third-party
```

```python
ID_RE = re.compile(r"^(?P<ns>[a-z][a-z0-9_]*)\.connector\.(?P<name>[a-z][a-z0-9_]*)(?:/(?P<major>[0-9]+))?$")
```

Validated by **pattern**, never by an enum: an enum would put a vendor product list in the canon and
make every new engine a schema bump. The namespace rule is already published in
`mac_vocabulary.yaml`'s header — *"a token whose namespace is not registered here is not a framework
reference"* — so `acme.connector.snowflake` **already means** "not framework-supported", with no new
rule invented.

**A name that looks like a path is a `ConnectorContractViolation` (exit 1), not a typo.**
`connector: ./tools/conn.py` is code injection wearing a spelling mistake.

**This is the whole of the bundle's forward commitment.** A bundle written against Track A is already
correct under Track B; nothing it declares changes when the loader arrives.

### 6.2 What the canon registers — **TRACK A**, and it is a subtraction

> **REVISED, and this was the first draft's first fatal.** Its §6.6 proposed:
>
> ```yaml
> members:
>   athena: {config_majors: [1], entry_point: sdk.connector.athena, status: active}
>   duckdb: {config_majors: [1], entry_point: sdk.connector.duckdb, status: active}
> ```
>
> Two objections, both measured, both decisive:
>
> 1. **It is the enum, relocated.** §3's own MAC row forbids "a vendor noun in `mac_vocabulary.yaml`
>    or `mac.schema.json`", and §6.1 one page earlier rejects "an enum \[that] would put a vendor
>    product list in the canon and make every new engine a schema bump". The member list *is* that
>    list, in another canon file — and it was **load-bearing**, because §7.3's mount tier and §6.4's
>    Authority test both required the canon to know every first-party engine name. A third
>    first-party engine would have been a canon bump forever.
> 2. **It does not validate.** Measured from `mac.vocabulary.schema.json`: the member object is
>    `additionalProperties: false` over exactly six keys — `definition, additivity, serves,
>    needs_sqlglot, doc, params_from`. `config_majors`, `entry_point` and `status` are **all three
>    illegal**. That is the identical argument the first draft used to *reject* the `members_from:`
>    alternative ("it needs a new key in `mac.vocabulary.schema.json`"): the chosen option needed
>    three. And `entry_point: sdk.connector.athena` is a Python module path — a fact about MAC's own
>    wheel layout — written into the file that defines meaning.

**What is registered is the namespace, and nothing else:**

```yaml
connector:
  kind: registry
  closed: false
  description: >
    The `mac.connector.*` NAMESPACE. A `mac.`-prefixed connector id is a framework reference; any
    other namespace is not, by this file's header rule, and needs nothing from MAC. This block
    registers the namespace only. It lists NO members: which first-party connectors exist is a fact
    about the MAC distribution, not about meaning, and lives in the shipped index (§6.3). A member
    list here would be a vendor product catalogue inside the canon.
```

No `members:`. No packaging keys. **Nothing widens `mac.vocabulary.schema.json`** — that is how the
canon becomes a build file.

**And `tools/check_vocabulary_drift._vocabularies()` is deliberately NOT patched.**

> **REVISED.** The first draft added a one-line patch so `kind: registry` blocks would be collected,
> warning that leaving it unpatched "creates a zero-denominator blind spot in the very gate meant to
> police it". Measured, the patch buys a green line and not a check: `check_vocabulary_drift.py:68`
> iterates `(_ROOT / "tools").rglob("*.py")` and `:37 _LITERAL` matches `mac.<voc>.<term>` **in
> MAC's own Python source**. Connector ids live in `mac.project.yaml#runtime.connector`, in bundles,
> in other repos — **never in `tools/*.py`**. After the patch the gate would count `connector` among
> its vocabularies and report clean over zero occurrences, permanently, while the typo it exists to
> catch (`mac.connector.athna` in <bundle>'s manifest) stayed invisible. Worse, with the namespace
> registered and **no** members, `voc in vocab and term not in vocab[voc]` is true of *every*
> `mac.connector.*` literal, so any MAC docstring narrating a hypothetical `mac.connector.postgres`
> becomes a MAC008 **ERROR on prose** — the exact false FAIL the gate's own docstring (`:20-25`) says
> it was designed to avoid.
>
> **A registry the drift gate openly skips is honest; one it counts and structurally cannot see is a
> green line over nothing.** The enforcement of connector ids lives entirely in
> `$defs/connectorRef`'s pattern (every bundle, every run) and in G2's `unregistered-mac-token`
> class. That is stated here so nobody later "fixes" the omission.

### 6.3 The first-party set is a shipped index, not canon — **TRACK A**

```
sdk/connector/index.json        # data. no imports. diffable. released with the wheel.
{
  "mac.connector.athena/1": {"config_schema": "schemas/athena.1.json"},
  "mac.connector.duckdb/1":  {"config_schema": "schemas/duckdb.1.json"}
}
```

This is the authority for exactly one question: **which `mac.`-prefixed connector ids are real, and
where is the JSON Schema that validates each one's `config:` block.** It is software, shipped with
the distribution, versioned with it, and diffable across releases by an ordinary snapshot test — the
one property the first draft's `members_from:` rejection correctly demanded and the member list did
not actually provide.

**And it is what lets a mount validate a config with zero imports.** The dry half of the contract is
`@classmethod` — pure functions of the config mapping — so for a first-party connector, mount-time
validation is `jsonschema.validate(config, <a file in the repo>)`. No `EntryPoint.load()`, no
`guarded_import`, no import deadline, no `ConnectorAmbiguous`, no squatting corroboration. Code is
genuinely needed only for `qualify`, dialect rendering and the wet verbs — and those are called by
`harvest` and `materialize`, author tools the operator invokes explicitly, **never by
`open_container`**.

**Honest limit, recorded rather than hidden.** JSON Schema expresses most cross-field rules
(`if`/`then`, `dependentRequired`) and not all. A rule it cannot express — e.g. *"`output` is
required unless the workgroup carries a managed output location"* — is **not** silently skipped at
mount: it belongs to `validate_config()`, which is Tier 1-code and runs at publish and at answer.
The mount tier validates what the schema expresses and **says which tier it reached**.

### 6.4 Discovery of third-party connectors — **TRACK B**

Registration is a Python entry point in the group **`mac.connectors`**:

```toml
[project.entry-points."mac.connectors"]
"acme.connector.snowflake/1" = "acme_conn.snowflake:V1"
```

The justification is one property: **`entry_points()` is a metadata read; it does not import the
target.** Measured offline (two fabricated `.dist-info` directories, no network, no build):
entry-point names may contain `.` and `/`; duplicates across two distributions are **both** returned
rather than deduped; and `importlib.metadata.distributions()` yields distribution name and version
structurally. `grep -rn "entry_points\|importlib.metadata"` over `meaning-as-code` returns **0 hits**,
so nothing is displaced.

**The loading half needs containment.** `EntryPoint.load()` is a bare `importlib` call.
`issubclass(SystemExit, Exception)` is `False`, so a connector calling `sys.exit()` at import takes
the host's exit code — and this is not hypothetical: `<domain>/<bundle>/tools/run_properties.py:39` **is
literally** `sys.exit(f"missing dependency: {exc}. Need boto3 and PyYAML.")`. So `tools/_plugin.py`
gains one function and the registry is its only new caller:

```python
def guarded_import(target: str, *, why: str):
    """Import 'module:attr' with the containment this module exists for.
    BaseException deliberately: SystemExit is the failure mode. Raises PluginUnavailable."""
```

> **A metadata hit is NOT evidence that code exists.** Measured on this machine: a `.dist-info`
> directory containing only `METADATA` and a two-line `entry_points.txt` naming
> `module_that_does_not_exist:V1` is **discovered** by `entry_points(group="mac.connectors")` while
> `importlib.util.find_spec("module_that_does_not_exist")` returns `None`. A forged connector made of
> two text files satisfied every mount-tier condition in the first draft. Therefore, in Track B:
> a third-party token must additionally satisfy `find_spec(<module part>) is not None` (still
> metadata + filesystem, still importing nothing) — **and, per §7.3, a third-party connector at mount
> never returns `True` for `answerable` at all.** See §15.2.

### 6.5 Collisions and squatting — **TRACK B**

`importlib.metadata` does not dedupe across distributions — **measured**. So collision is a real
state and needs a ruling.

**A duplicate `(id, major)` is refused, never won.** `resolve()` raises `ConnectorAmbiguous` naming
both distributions and versions; the host exits **2**. No "first wins", no sort order, no precedence.
This is `tools/mac_resources.py`'s rule about `*.mac` applied verbatim: *"two is ambiguous and must
be refused rather than guessed at."* *(The false-green lens endorsed this device.)*

**Namespace squatting** is caught by one test, now that the canon holds no member list: a
`mac.`-prefixed id that is **not a key in the shipped index** (§6.3) is refused at resolve, **MAC008**.
A fixture `mac.connector.athena/9` published by a distribution named `acme-conn` fails it, because
`meaning-as-code`'s own index is the only place a `mac.*` id can be real. Distribution-provenance
("the entry point came from the `meaning-as-code` distribution") stays as **corroboration only**,
because if MAC is ever split across distributions the provenance test breaks and the index test does
not.

**No allowlist of vendors is needed anywhere.** That is the point of the namespace rule.

### 6.6 Versioning: two things move, and the repo already has a mechanism for each

| What moves | Mechanism | Repo's existing idiom | Bundle's relationship |
|---|---|---|---|
| **The config contract** — which keys the config file may carry and what they mean | `mac.connector.athena/2` — id + integer major | `spec_version: mac.container/1`, pattern `^mac\.[a-z]+/[0-9]+$` | **PINNED** and checked |
| **The implementation** — the code that opens the session | the installed distribution's version, read from metadata | `grammar_id: mac/0.1.14-develop+d08fa3084aac78af` | **RECORDED**, never pinned |

**Record, don't pin.** A bundle does not pin `mac.schema.json`; the `.mac` file records which grammar
judged it and `--check` refuses on a difference. Pinning an implementation version inside a data
artifact is dependency management, and `pip` already owns it.

In Track A the supported major set is a fact of the **shipped index** (one key per `(name, major)`).
In Track B a third-party connector declares its range by **publishing one entry point per supported
major** — so the supported set is a fact of the installation readable from metadata, not a claim made
after import.

**Major vs minor, stated once:** a **major** bump means *an old config stops working* (a key removed,
retyped, or re-meant). A **minor** release means *a new config stops working on an old connector* (an
optional key added). Both failures are loud and look different: a major out of range names the major;
a new optional key against an old installed connector fails `additionalProperties: false` and names
the key **and** the installed distribution version.

**Unpinned** (`mac.connector.athena`, no `/N`) resolves to the **highest** available major and is
**disclosed** on a read mount (`mac.connector.athena/2 (unpinned; highest available)`) — the
disclose-rather-than-ask posture already ruled twice on this repo (period default; Spain split). An
answering host (`require_trust` set) **refuses** it. Assuming the lowest major would silently answer
under a config contract the author never wrote against.

### 6.7 Packaging

First-party connectors ship **in the wheel**, with their engine SDKs as **extras**:
`pip install meaning-as-code[athena]`, `[duckdb]`. The base install stays `PyYAML + jsonschema`. That
is the operator's *"plug-in connectors as binaries and as source"* with one release train and one
`VERSION` file.

Recorded as a live defect this exposes: `meaning-as-code/pyproject.toml` declares only `PyYAML` and
`jsonschema`, so **`boto3` is an undeclared import today** — a clean install of the public framework
ships an Athena harvest that `ImportError`s. Meanwhile `mac-platform/packages/mac-sdk/pyproject.toml:12-17`
declares `boto3` and `botocore` as **hard** dependencies. The same module tree has two contradictory
dependency contracts. **Ruling 12 addresses the root cause, and per §0.1 it now gates Track B.**

---

## 7 · The tiers, and the billing tension

### 7.1 The governing distinction

> **`capabilities.answerable` is a claim about the CONTAINER. `reachable` is a claim about the WORLD.
> A container validator may only evaluate the former.**

Forced by two existing contracts, not by taste:

- **Determinism.** `spec.validate()`'s verdict is frozen into a published, tree-hashed, signed
  artifact. If it depended on whether Athena answered, the same bytes would validate differently at
  09:00 and 09:05 and `tree-verified` would stop meaning anything.
- **Cost.** `validate()` is called by `open_container()`, which is called on **every** mount — the
  wiki, VS Code, the runtime, CI. A billed call on that path is a billed call on a page refresh.

A source being momentarily down does not make a bundle **unfit to answer from**. It makes it **unable
to answer right now**. Two predicates, two homes.

### 7.2 The tiers — `mac.capability_tier`, a new closed vocabulary — **TRACK A**

```
unconnected  — below the tiers. The bundle declares no connection. NOT a failure. 19 of 24 bundles.
declared     — a connector is named, and the name is well-formed.
resolvable   — that connector is known here, its config satisfies the connector's own config schema,
               and a credential PLAN assembles. NO NETWORK, NO SOCKET, NO VALUE.
reachable    — the source answered a trivial control-plane probe, at a stated instant.  [TRACK B]
```

**A 0-byte `connection.yaml` does not reach `declared`.** That is the mechanical repair of
`spec.py:47`.

**A bundle that declares a connector MAC cannot judge stops at `declared` with a reason. It is NEVER
silently downgraded to `unconnected`.** That is `_plugin.py`'s `required()` vs `optional()` split
verbatim: declaring nothing is fine and gets the documented behaviour; declaring something and
failing to supply it is a stop, because a degraded connector produces a green badge for a connection
that does not exist.

### 7.3 Which tier `answerable` binds to

> **ARCHITECT DISAGREEMENT.** One architect binds `answerable` to `resolvable` (config validated
> against the connector's own schema). Another binds it to metadata-only resolution and forbids
> importing a connector at mount, on the ground that importing a third-party connector to verify a
> *claim made by an untrusted bundle* is arbitrary code execution during a read-only mount.
> **Both are right, about different hosts.**
>
> **REVISED — and §6.3 dissolves most of the conflict.** Because the first-party config schema is a
> **file**, a mount reaches `resolvable` for a first-party connector **without importing anything at
> all**. The remaining conflict is only about third-party connectors, and it is resolved by refusing
> to answer rather than by importing.

| Host | Evidence for `answerable` | Imports connector code? |
|---|---|---|
| **Mount** (`spec.validate()` / `open_container`, every page load) — first-party (`mac.*`) | envelope parses and is non-empty; token matches `ID_RE`; token is a key in the shipped index; `config:` validates against that index's schema **file**; `runtime.interpreter` names an existing **non-empty** file | **no** |
| **Mount** — third-party (any other namespace) | token matches `ID_RE`; nothing more is knowable offline → **`answerable` is `None` (undetermined), NEVER `True`** | **no** |
| **Publish** (`sdk/cli/publish.py:80`, already imports MAC and already runs gates in-process) | the above **plus** `validate_config()` cross-field rules and `credential_plan()` — code, first-party in Track A, third-party in Track B | first-party yes |
| **Answer** (`require_trust` set) | Publish evidence, plus a pin that is not unpinned, plus — if the host demands it — a fresh receipt (§7.5, Track B) | yes |

> **REVISED — why third-party is `None` and never `True`.** The first draft let a third-party token
> back `answerable: true` at mount on the evidence that "a non-`mac.*` token is present in the
> `mac.connectors` entry-point index". Measured (§6.4): **that index is satisfiable with two text
> files and no code.** The full evidence chain would then have been *four presence checks and one
> regex* — better than `spec.py:47`'s two `Path.exists()`, and **the same class of evidence**. A
> host that cannot verify a third-party config offline does not know whether the bundle is
> answerable; the honest value for "I cannot judge" already exists in this design and it is `None`.
>
> **Consequence, stated because it is a real limitation:** until Track B lands, **only a bundle
> naming a first-party connector can be `answerable: true`**. A third-party bundle is `undetermined`
> — a warning, exit 2 at the CLI, never a bundle defect. Given the estate's served denominator of one
> Athena bundle (§0.2), that is the correct trade; it is recorded here so it is a decision and not a
> surprise.

### 7.4 The replacement for `spec.py:47`, and the tri-state — **TRACK A**

```python
# before — sdk/container/spec.py:47
"answerable": bool(interp) and (cr / str(interp)).exists() and (cr / str(conn)).exists(),

# after
"answerable": tiers.backs_answering(cr, m),     # True | False | None
```

| Value | Meaning | `validate()` | Process |
|---|---|---|---|
| `True` | interpreter present and non-empty; connection declared, present, non-empty, schema-valid; first-party token in the shipped index; `config` validates against its schema file | backed | 0 |
| `False` | the **bundle** is wrong: no connector named, empty or missing config, unregistered `mac.*` token, missing or empty interpreter | `capability 'answerable' claimed but NOT backed: <the condition that failed>` | 1 |
| `None` | this **host** cannot judge: a third-party connector, or (Track B) a registered connector whose module will not import here | **warning**, not error: `answerable: undetermined — <why>` | **2** at the CLI |

**Line 43's fallback `rt.get("connection") or "connection.yaml"` is deleted.** An undeclared
connection is not a connection.

`_backed_capabilities` also starts naming *which* condition failed — today it says only
`"capability 'answerable' claimed but NOT backed by contents"`, which is why <bundle>'s real defect (a
`runtime:` block with `source` and `connection` but no `interpreter`) has been invisible for a month.

**The tri-state carries its own trap, and it needs its own mutant.** `spec.py`'s existing loop is
`if declared.get(cap) and not backed.get(cap)`, and `None` is falsy — so without an explicit
`is False` guard, this change **silently produces the exact false "claimed but NOT backed" error it
exists to prevent.** G2/R6 seeds it.

### 7.5 `reachable`: the billed tier — **TRACK B**

The operator's requirement — *"when this ontology gets opened the connection is tested and it's
working"* — lands on `reachable`. The standing rule is that nothing reaches AWS unprompted.

**(a) The free tiers run on every open, unconditionally.** Most of what "is it working" means is
answered here, for free, every time — and, new, *before publish*, in CI. The failure modes an
operator actually hits — wrong profile name, missing region, a `secret_manager` ref against an
unwired resolver, a connector typo, a config key that moved — are **100% `resolvable`-tier failures.**

**(b) Cost class is a property of the CONNECTOR, not of the tier.** `Connector.probe_cost` is `free`
or `billed`. contoso's DuckDB probe is a local file open — free, it **may** run automatically on
open. Athena's cannot, ever, without a human act. Treating every engine as expensive would teach
operators that the confirmation prompt is noise to click through, which is how a real billing guard
gets trained away.

**(c) The definition of `billed` is MAC's, so it must be engine-neutral.**

> **REVISED.** The first draft defined it as *"touches the account and appears in CloudTrail"* — an
> AWS audit product and an AWS account, naming one cloud inside a field on the generic base class.
> The honesty was right; the home was wrong.
>
> **On the base class:** *"`billed` means the call is metered, rate-limited, or recorded in an audit
> log the source's operator maintains. `free` means none of those."*
> **In `sdk/connector/athena.py`'s own docstring:** the CloudTrail / S3-output / workgroup-scan
> reasoning, and the note that the probe is **control-plane only** (`athena:GetWorkGroup` +
> `glue:GetDatabase`), deliberately not `SELECT 1`, which writes a result object to the S3 output
> location and enters the workgroup's scan accounting. **Nobody measured the money cost, because
> measuring it means making the call — Ruling 8, and it may collapse this whole tension.**

**(d) `open_container()` has no code path to `Connector.probe()`.** Not a flag that defaults off — no
path. The single entry point is `python3 -m sdk.cli.probe <container> --i-accept-billing`, which
prints the cost class, the connector, the redacted target and the credential mode, **then** acts.
**The confirmation is not readable from an environment variable**, because a pre-confirming env var
is how "nothing unprompted" quietly becomes "everything, in CI".

**(e) A host that *requires* reachability gets an enforceable floor that bills nothing.**
`open_container(path, *, require_trust=None, require_tier=None, receipts=None)`. An answering host
passes `require_tier="reachable"`; the mount refuses unless a **fresh receipt** is on file, and the
refusal carries the remedy command verbatim. That is **stronger** than an auto-probe on open: an
auto-probe proves the connection worked *at mount* and then says nothing for the rest of a six-hour
session, while billing once per mount.

### 7.6 Receipts — **TRACK B**

Receipts live in **host workspace state**,
`~/.mac/receipts/<container-identity>/<config-fingerprint>.json`, **never inside the container** —
three independently fatal reasons: a published container is write-once and tree-hashed (a receipt
breaks `integrity.tree_ok`); a receipt is one operator's session observation and must not ship to
another operator as a property of the artifact; and `check_bundle_secrets` scans the staged tree,
where probe detail is exactly where an account id would leak into a frozen artifact.

```python
def freshness(receipt, fingerprint, identity, connector, now) -> str:
    if receipt is None:                                return "absent"
    if receipt["config_fingerprint"] != fingerprint:   return "void"
    if receipt["container"]["identity"] != identity:   return "void"
    if receipt["connector"] != connector:              return "void"
    if receipt["verdict"] != "ok":                     return "failed"
    if now - parse(receipt["at"]) <= receipt["ttl_s"]: return "fresh"
    return "stale"
```

> **`void` is deliberately not `stale`.** *Stale* means: this was true, an hour ago, of **this**
> thing. *Void* means: this was about **a different thing**. Collapse them and a config edit inherits
> the previous config's green badge — someone repoints `workgroup` at production, the receipt is two
> minutes old, the badge stays green, and the system has lied in the one way this whole design exists
> to prevent. *(The false-green lens endorsed this distinction.)*

The bundle may **lower** the connector's `probe_ttl_s`, never raise it. Defaults (`billed` 3600 s,
`free` 60 s) are **invented, not measured**: Ruling 9.

**No gate reads a receipt as evidence of `answerable`.** A gate whose PASS depends on a file a human
wrote is a new zero-denominator pass wearing a date. `require_tier` is a *host mount policy*, not a
gate.

---

## 8 · Trust and the safety boundary

### 8.1 Two trusts, two questions, never one number

| | **Bundle trust** | **Connector trust** |
|---|---|---|
| Question | Are these the bytes the author sealed? | Is this code the operator chose to run? |
| Subject | content / declarations | installed software |
| Ladder | `signed-verified > tree-verified > unpublished-ssot > unverified` (`spec.py:118-131`) | binary + policy: installed / not installed / installed-but-refused |
| Travels with the bundle? | yes | **never** |

**Conflation failure #1 — trust laundering upward.** `spec.py:118` verifies with
`hmac.new(signing_key.encode(), tree.encode(), "sha256")`, keyed from `MAC_SIGNING_KEY`
(`loader.py:167`). HMAC is **symmetric**: every party who can *verify* can also *mint*. If
`signed-verified` ever authorised loading bundle-supplied code, every holder of the verification key
would silently become a code-signing authority for this host. **The trust ladder is an integrity
claim about declarations and confers zero execution rights.**

**Conflation failure #2 — refusal laundering downward.** If "connector not installed" is expressed on
the bundle-trust axis, a valid signed bundle is reported as *invalid* and the author is sent to fix a
correct file. `_plugin.py:23-27` documents that exact damage in this estate's own history: the silent
fallback turned "could not run" into "a confident FALSE report of an invariant breach", and **3
findings became 56**.

They compose as a **conjunction with different exit codes**: below trust floor → exit 1; connector
not installed → exit 2; connector installed but policy-refused → exit 1.

**Connectors are never loaded from inside a bundle.** `sdk/container/loader.py::open_container`
unpacks arbitrary `.tar.gz`. If a connector could ship in a container, *opening* an ontology would
execute code carried by it, and the trust ranking governs bytes, not execution.

> **ARCHITECT DISAGREEMENT.** Two architects proposed resolving third-party connectors through
> `tools/_plugin.required(root, "CONNECTOR")` — i.e. **from the bundle**, on the principle that "the
> BUNDLE owns how its declarations resolve". **CHOSEN: never from the bundle.** `_plugin.py`'s
> *hardening* is copied; its *seam* is not. `_plugin` takes its path from the **subject**, correct for
> an author tool the operator invokes explicitly against their own bundle, catastrophic for a
> connector loaded during a mount of an archive from elsewhere. The invariant:
>
> > **THE OPERATOR INSTALLS CONNECTORS; THE BUNDLE ONLY NAMES ONE.** A bundle's connector declaration
> > is a dictionary key. It is never a path, never an import target, never a file the host executes.
>
> This is not yet true: `tools/mac_admit_identity.py:216` and `tools/mac_profile.py:206` both do
> `Athena = _plugin.required(root, "Athena")` — **a bundle supplying a warehouse connection, in
> production, today**. They are author tools, explicitly CLI-invoked; §8.2 quarantines them off the
> open path by boundary gate, but they remain a live instance of the pattern this record forbids.

### 8.2 What a bundle may ship: declarations only — **TRACK A**

Blocked in a **staged publish tree** and in a **mounted container** — not in an authoring source
tree: `.py .pyc .pyo .pyw .so .dylib .dll .pyd .sh .bash .zsh .ps1 .bat .cmd .rb .pl .php .jar .exe
.wasm`, plus any file whose first two bytes are `#!`, plus the executable bit.

The hole is real and measured: `publish` is bare `{"type": "object"}`, `_compile_items()` returns
`publish.include` verbatim, and `publish()` copies whole directories with `shutil.copytree`. Bundles
already carry code — `<domain>/<bundle>/tools/run_properties.py`, contoso's `ask.py` / `ask_server.py` /
`build_site.py` / `setup.sh` / `validate.sh`. Measured: `<domain>/<bundle-legacy>/artifacts/vb0b8e3398ec0` contains
**0** `.py`/`.sh` files — **by the author's choice of `publish.include`, not by any rule.**

Honest limit, stated not hidden: the exec-bit half is unreliable through a tarball, because
`loader._safe_extract` passes `filter="data"`, which clamps member modes. Extension and shebang carry
the weight; an extensionless, shebang-less executable would pass.

**And make it a boundary, not a convention.** `sdk/container/loader.py`, `sdk/container/spec.py` and
everything they import must not import `tools/_plugin.py`.

> **REVISED — the first draft's role could not fire against any natural spelling of the import it
> forbids.** It proposed `"forbid_import_roots": {"_plugin"}`. Measured:
> `sdk/gate/check_boundaries.py:73-81 _import_roots()` takes `a.name.split(".")[0]` for `ast.Import`
> and `node.module.split(".")[0]` for `ast.ImportFrom`, and the test at `:126` is
> `if mod in rc["forbid_import_roots"]`. So `from tools import _plugin` → root `"tools"`;
> `import tools._plugin` → `"tools"`; `from tools._plugin import guarded_import` → `"tools"`. **All
> three MISS.** Only a bare `import _plugin` after a `sys.path` insert would match — and `sys.path`
> hits go to `warnings` (`:134-141`), not `violations`. The boundary the draft called "a boundary,
> not a convention" was **green by construction.**

```python
"container-open": {"dir": "sdk/container", "forbid_import_roots": {"tools"},
                   "forbid_sys_path": True, "forbid_dynamic_import": True},
```

Two further measured defects in the same gate, fixed in the same commit:

- **Double counting.** `CONFIGS` already carries a role with `"dir": "sdk"` (`:55`), so adding
  `dir: sdk/container` makes `examined()` (`:153-169`) count those files **twice** — it sums per-role
  counts. The verdict line must print **per-role** denominators.
- **A silent per-class zero.** `main()` (`:186-192`) exits 2 only when the **total** is 0, so a
  `container-open` role whose directory is absent is absorbed into a large aggregate and reported as
  nothing. That is the exact shape §10.6 fixes for G6's class 4; it gets the same fix here, with a
  mutant proving a role examining zero files is reported as its own zero.

**And the one new directory in MAC designed to hold engine code must be readable by the gate that
exists to keep instance specifics out of MAC.**

> **REVISED.** §3 states that a connector "must never contain any value belonging to one deployment —
> a region default, a workgroup, an account", and the first draft specified **no gate that checks
> it**. `sdk/connector/athena.py` is the single likeliest place in the repository for
> `region = "eu-west-1"` or a default workgroup to be typed. Meanwhile
> `sdk/gate/check_source_coupling.py` — the estate's existing generic-instrument gate — has
> **`SCAN_DIRS = ("sdk/project", "sdk/authoring", "sdk/cli", "sdk/container")`** (measured at line
> 43). `sdk/connector` is not in it, and the first draft never added it: `check_source_coupling`
> appeared exactly once, as a one-off measurement to run "before ruling".
>
> **One line, in Stage A3:** add `"sdk/connector"` to `SCAN_DIRS`, with a mutant seeding
> `region = "eu-west-1"` and one `infra_handles` value inside a fixture connector module. Extend
> `check_bundle_secrets`' infra-handle scan over `sdk/connector/**` the same way. The sibling
> register `sdk/gate/infra_handles.txt` currently holds exactly the class of values §3 forbids a
> connector to carry.

### 8.3 The secrets exemption becomes manifest-derived — **TRACK A**

`_CONFIG_ALLOWLIST` is a **self-service exemption**: `in_config = p.name in _CONFIG_ALLOWLIST` at
line 211 means **anyone can claim it by naming a file `connection.yaml`** (false PASS), while a
bundle organising configs under `conn/athena.yaml` has its legitimate handles reported as leaks
(false FAIL) — and "a checker that punishes the correct pattern is worse than no checker" is this
estate's own sentence, from `tools/check_no_fabricated_identifiers.py`.

```python
def config_paths(root: Path) -> tuple[set[str], int]:
    """Paths the MANIFEST declares as connector configs, and how many it declared.
    Declared paths ONLY — no basename heuristic. An exemption you can claim by naming a file
    is not an exemption. Each path is resolved against root and must remain INSIDE it after
    realpath — the containment check loader._safe_extract already applies to tar members."""
```

New FAIL class **`undeclared_connector_config`**: a file matching `connection*.y*ml`, or any YAML
carrying a `credentials:` mapping with a `mode:` key, at a path the manifest does not declare. A
bundle with no declaration falls back to the legacy basename set **and the verdict line says so** —
`[legacy basename allowlist — bundle declares no connector config]`, never silently. **That printed
string is now an `expect_line` assertion in the gate's self-test (§10.0), not prose.**

> **ORDERING RISK, highest in this record.** This change must land **before or with** the path
> declaration. Landing them in the wrong order breaks `publish` for any bundle using the new naming.

### 8.4 The permission surface — **TRACK B**

> **ARCHITECT DISAGREEMENT.** One architect committed to a permission surface; the others were
> silent, and the case against is strong: two connectors exist, both first-party, one of them a local
> file read; CPython has no in-process capability enforcement; a field that enforces nothing but
> *reads* like a guarantee is decoration.
>
> **CHOSEN: declare it — but only when third-party connectors actually land, i.e. in Track B.** The
> durable value is **admission control** plus a **diff surface**: a connector that declared
> `{read, net}` at v1.2 and declares `{read, net, write, fs, exec}` at v1.3 is a *reviewable event*.
> Building it in Track A would be a declaration surface over a population of two first-party classes.

New closed vocabulary `mac.connector_permission`: `read` · `write` · `net` · `fs` · `exec`.
`load(name, allow=...)`, default `frozenset({"read", "net"})`; **`write` is never in a default**;
operator policy at `~/.mac/connectors.policy.yaml`, on the host, never in a bundle, never in MAC;
absent policy means the default **and the host prints which default it used**. A permission outside
`allow` is `ConnectorRefused` → exit 1.

The honest limit goes in the field's own docstring so it cannot be mis-sold:

> *"`permissions` is a declaration the operator admits or refuses. It is not a sandbox; Python has no
> in-process capability enforcement. A connector that declares `{read}` and opens a socket is lying,
> and this field is what makes that lie a reviewable, attributable claim rather than an invisible
> one."*

**One thing it does enforce mechanically, for free:** a connector without `write` is handed to
callers through a wrapper exposing only `read`. Not a sandbox — but it removes the accidental case,
which is the common case.

---

## 9 · Grammar and vocabulary changes, and the migration cost — **TRACK A**

### 9.1 `mac.schema.json`: 37 → **40** `$defs`, root `oneOf` 16 → 17

| `$def` | Purpose |
|---|---|
| **`ConnectionFile`** (new, in the root `oneOf`) | the envelope: `spec_version`, `credentials`, `config`, `label`, `note`. `required: [credentials]` is **not** set — DuckDB omits it. `additionalProperties: false`. |
| **`credentialRef`** (new) | `{mode, ref}` only, `additionalProperties: false`, with conditionals: `named_profile` / `secret_manager` / `client_certificate` **require** `ref`; `ambient` / `interactive` / `none` **forbid** it. |
| **`connectorRef`** (new) | the `ID_RE` pattern, used by `runtime.connector`. Pattern, never enum. |
| `ProjectFile.runtime` | retyped from `{"type": "object"}` to closed `{source, connector, connection, interpreter, model_catalog}` |
| `ProjectFile.serving` | gains `namespace` (§5.5) |
| `ProjectFile.publish` | retyped from `{"type": "object"}` — it is what makes §8.2 checkable |
| `TableFile.profiled_via.description` | `"e.g. 'Glue + Athena profile'"` → `"e.g. 'catalog metadata + a live column profile'"`. **The single instance-specific token in the grammar** (verified: `Glue` occurs once in `mac.schema.json`; `aws` and `boto` zero times). |

> **REVISED — `connectionProbe` is DELETED.** The first draft added a fourth `$def`,
> `connectionProbe: {command, billed}`, "recorded, never executed". Three objections, all correct:
> it puts an **executable instruction into the bundle grammar** in the same record that bans
> executables from bundles (§8.2 blocks `.py .sh …` + shebang + exec bit from staged and mounted
> trees precisely because "opening an ontology would execute code carried by it"); the only
> protection was the prose *"recorded, never executed"*, i.e. the "prose guarantee nothing checks"
> defect this record exists to remove; and the field is **instance-specific by construction** — the
> only thing anyone can write in it is a concrete invocation against a concrete deployment
> (`aws athena get-work-group --work-group <a real workgroup>`), which then sits inside a published,
> tree-hashed artifact. The cost class is already `Connector.probe_cost` (a connector fact, not a
> bundle claim) and the probe is already `Connector.probe()` — code the operator installed. A bundle
> that needs a shorter TTL uses the lower-only scalar §7.6 already specifies.

`additionalProperties: false` on the envelope is the load-bearing half: it is what leaves
`aws_secret_access_key:` nowhere legal to sit, and what forces every vendor key down into `config`
where a named party owns its meaning.

> **ARCHITECT DISAGREEMENT — and the operator ruled on this shape once already.** `config:` is an
> opaque object MAC cannot check, which is the sentence that killed `x-` (*"an extension is not a
> small schema, it is an UNCHECKED one"*). The distinction offered, and it must be confirmed rather
> than assumed (Ruling 3): an `x-` key was checked by **nobody**, whereas `config` is checked by a
> JSON Schema a **named party ships** — in Track A, a file in this repository resolved from the
> shipped index — and when that party is absent MAC prints **what went unchecked, with its
> denominator**, and **withholds the claim that depended on it**. If that distinction does not hold,
> this design is `x-` with a driver attached and must be rebuilt as per-engine core schemas — which
> would put `region` and `workgroup` in the canon.

### 9.2 Wiring — four edits, each individually fatal to omit

This framework has recorded, twice in one file, that a half-wired definition is worse than none.

1. `tools/validate_schema.py::_pick_def` — route the declared config path (**by realpath, not by
   basename**) to `ConnectionFile`, plus the two legacy basenames.
2. `tools/validate_schema.py::enumerate_bundle` — collect declared config + example paths. *"A
   definition nothing enumerates is a definition nothing applies"* — that file's own comment.
3. `tools/validate_schema.py::UNVERSIONED_DEFS` — add `ConnectionFile`. A deployment config carries
   no `schema_version`. Without this it is routed, matched, then **skipped**, producing coverage that
   reads as zero-undefined while nothing is checked. The comment above that set records this exact
   outcome happening in v0.1.14.
4. `tools/mac_compile.py::PHASES` — register the phase. `check_extension_keys` sat unwired for a
   month, and that is why `LEGACY` exists.

### 9.3 Zero new diagnostic codes

`mac.diagnostic_code` is closed and it already carried this whole surface; the codes could not fire
because the file had no definition.

| Failure | Code | Severity |
|---|---|---|
| envelope invalid — no connector named, unknown key, malformed `credentials`, **an empty file** | **MAC002** | error |
| `runtime.connection` names a path that is not there | **MAC008** | error |
| `mac.connector.<x>` absent from the shipped index | **MAC008** | error |
| a connection file exists and the manifest never declares it | — | **G1 `undeclared-connection`, exit 1** — *not* a derived MAC005 (§5.2) |
| `answerable: true` the contents cannot back | **MAC006** | error¹ |
| third-party connector cannot be judged here | **MAC005** | **info** — not a bundle defect |
| connector raises or `sys.exit()`s at import *(Track B)* | — | **exit 2**, no diagnostic |
| a stale `out_of_scope` waiver matching zero unknown files | **MAC007** | error — a dead guard, literally |
| `connection.local.yaml` found **inside** the bundle root | **MAC002** | error — a gitignored override about to be sealed into an immutable artifact |

¹ MAC006's registry default is `warning`, and `spec.py` treats an unbacked capability as an **error**
and must continue to. Raising with a stated reason is explicitly sanctioned by the vocabulary — but
it is an inconsistency worth the operator seeing rather than papering over (Ruling 10).

**A new code was considered and rejected.** The candidate was `connector-unresolvable`. It fails the
taxonomy's own bar: every code in the closed set names something wrong with the **subject**, and this
names the framework reporting the limits of its own reach on this host. **A code whose meaning is
"nothing is wrong" gets counted, dashboarded and burned down by someone who assumed otherwise.**

### 9.4 Migration cost, for the three real bundles

**`<domain>/<bundle>`** — Athena, the only bundle with a real connection file.

| Edit | Size |
|---|---|
| `mac.project.yaml`: add `runtime.connector: mac.connector.athena` | 1 line |
| `mac.project.yaml`: `runtime.connection: connection.yaml` | **already present — 0 edits** |
| `mac.project.yaml`: add `serving.namespace: [<view_database>, <view_schema>]` | 1 line |
| `mac.project.yaml`: delete the two `conformance.out_of_scope` waivers for the connection files | 2 entries, ~6 lines |
| `mac.project.yaml`: add `runtime.interpreter:` **or** drop `answerable: true` | Ruling 11 |
| `connection.yaml`: `engine: athena` → deleted (identity moved to the manifest) | 1 key |
| `connection.yaml`: `region · workgroup · output · catalog · glue_databases{fact,dims}` → under `config:` | **6 values re-homed, 0 values changed** |
| `connection.yaml`: `view_database` / `view_schema` → `serving.namespace` in the manifest | 2 keys moved |
| `connection.yaml`: `credentials.mode: aws-chain` → `ambient` | 1 value |
| `connection.yaml`: `credentials.ref: <profile handle>` | **deleted** — read by nothing, Ruling 4 |
| `connection.example.yaml` | same restructure |

Net: **1 manifest edited, 2 config files restructured, no ontology file touched, no concept touched,
no value changed.** Enumeration: routed **105 → 107**, waived **151 → 149**, unknown **0 → 0**.

On deleting `credentials.ref` under `ambient`: `sdk/authoring/connection.py::resolve_credentials()`
returns `{}` for the ambient chain — **the `ref` is read by nothing** (verified at lines 55-56).
Deleting it removes a shipped identity string at zero functional cost; the human hint about which
profile to have active moves to an optional `note:` field.

**`mac-ontology-contoso`** — DuckDB, no connection. **Zero required edits.** Verified: no `runtime:`
block, no `capabilities:` block, no connection file. Stays `ok=True`, `answerable: false`, zero
errors, zero warnings — **openable, readable, browsable, not answerable, by construction rather than
by exemption.**

> **REVISED — and this is why G5's subject is NOT contoso.** The first draft's zero-change acceptance
> test required `spec.validate(contoso)["capabilities"]["backed"]["answerable"]` to be `True` at
> head, which contradicts the zero-edit guarantee on this very page: contoso has no `runtime:` block
> and no `capabilities:` block, so making it `True` means **adding an interpreter and a connection
> config** — exactly the edits §9.4 calls optional. The contradiction is resolved by giving G5 a
> **built-in DuckDB fixture bundle shipped inside `meaning-as-code`** as its subject. contoso stays
> at zero edits and stays the falsifier for genericity; the fixture is the subject of the acceptance
> test. See §10.5 and §15.2.

An optional, *separate* commit may still add a connection to contoso as documentation:

```yaml
# contoso/connection.yaml — the proof the seam is not Athena-shaped
spec_version: mac.connector/1
credentials: {mode: none}
config: {database: data/contoso.duckdb, read_only: true}
```

A second engine, a different credential mode, a `config` block with **zero overlap** with <bundle>'s, and
a grammar that changed not one character to accept it.

**`example_tpch_ontology`** (and `example_shop_ontology`) — **zero edits, byte-identical
enumeration.** The phase prints `0 declared · 0 file(s) examined`, exit 0, and the bundle is not
nagged for declining a mechanism it has no use for.

**`<domain>/<bundle-legacy>`** (gold, for completeness): 6 files move `unknown → routed` out of 1620, i.e. **0.37%**
of its MAC001 debt. Stated so nobody quotes this change as progress on that bundle.

---

## 10 · Gates and acceptance

### 10.0 G-1 · The harness repair — **TRACK A, and it BLOCKS every other gate**

> **This section replaces a foundation, not a paragraph.** The first draft built every gate on
> `sdk/gate/contract.py` and said "None re-implements the verdict line". An adversary **built and ran**
> a passing-but-wrong gate on this tree to show why that foundation does not hold. Until this lands,
> **no mutant table in this record may be cited as coverage.**

**Defect 1 — the harness cannot attribute a finding to a reject class.** Measured:
`Outcome` (`contract.py:40-50`) is `(findings: int, examined: int, unit: str)`. `run_self_test`'s
per-mutant assertion (`contract.py:157-159`) is `out = contract.run(root); if out.clean:
failures.append(f"mutant not caught: {cls}")` — i.e. *at least one finding, for any reason*. Its own
docstring at line 122 promises "assert each is rejected **AS ITS OWN CLASS**".

*Demonstrated:* a `GateContract` whose `run()` merely counts YAML files, implementing **none** of
three declared reject classes, printed
`PASS: demo-gate self-test — 7/7 (3 mutant(s) rejected as their own class...)`.
Concretely for G1: a gate that never implements the realpath containment check of §8.3 still passes
`config-path-escapes-bundle`, because `../../etc/creds.yaml` also fails the `declared-missing`
predicate.

**Defect 2 — a must-PASS fixture is structurally inexpressible.** `mutants` requires every entry to
be *rejected*, so "contoso with no connection must PASS" cannot be a mutant; `clean` is a **single
callable**, so G1's two clean fixtures cannot both be it. The overflow lands in
`extra: Mapping[str, Callable[[Path], str]]`, checked at `:162-165` as `err = assertion(base); if
err: fail` — **`lambda base: ""` passes** — and `:167` counts extras into `total`, the printed
denominator. In the demonstration, two no-op lambdas labelled with this record's own non-negotiable
properties took the printed score from `5/5` to `7/7`. **The property §3.2 calls the constraint that
outranks everything else in this document was the one property the harness could not check.**

**Defect 3 — nothing reads a gate's printed line or its exit code.** `run_self_test` calls
`contract.run(root)` and reads an `Outcome`. It never invokes `main()`, never captures stdout, never
checks an exit code. At least seven guarantees in this record are **entirely about what gets
printed**: `profiled 0 of 14 relation(s)`; `SHOW TABLES: unavailable — collision check NOT
performed`; `[legacy basename allowlist …]`; which permission default the host used; the coupling
**delta**; `class 4 examined 0 connector(s)`; the suite naming which bundles it examined. Each is the
difference between a disclosed degradation and a silent one.

**The repair — four additive changes to `sdk/gate/contract.py`:**

```python
@dataclass(frozen=True)
class Outcome:
    findings: int
    examined: int
    unit: str = "file(s)"
    classes: frozenset[str] = frozenset()          # NEW: which reject classes fired
    secondary: tuple[int, str] | None = None       # NEW: the second denominator, rendered by verdict()

@dataclass(frozen=True)
class GateContract:
    name: str
    clean: Callable[[Path], None]
    mutants: Mapping[str, Seeder]
    run: Callable[[Path], Outcome]
    must_pass: Mapping[str, Callable[[Path], None]] = ...   # NEW: fixtures that MUST come back clean
    expect_line: Mapping[str, str] = ...                    # NEW: class -> required stdout fragment
    extra: Mapping[str, Callable[[Path], tuple[int, int]]] = ...   # CHANGED: returns (checked, total)
```

| # | Rule | Why |
|---|---|---|
| 1 | For each mutant, `run_self_test` asserts **`cls in out.classes`**, and that **no other class fired**. | A finding of the wrong kind is not coverage. |
| 2 | `must_pass` fixtures are seeded like mutants and asserted **`out.clean and out.examined > 0`**. | "contoso with no connection must PASS" and "C1 optional-absent-degrades must NOT be rejected" become checkable. |
| 3 | `run_self_test` invokes **`main()`**, capturing stdout and the exit code, and asserts the `expect_line` fragment and the code per class. | Every printed disclosure in this record becomes an assertion. |
| 4 | `extra` returns `(checked, total)`; a no-op is visible as `checked 0`, not counted as an assertion. | A lambda that returns `""` can no longer inflate a denominator. |

**Backwards compatibility:** the new fields default empty, so the eight existing `check_*.py` gates
keep working unchanged. Class attribution is **asserted only for gates that declare `classes`** — and
every gate in this record declares them.

**And `verdict()` gains one refusal:** when a gate **declares** a `secondary` denominator and that
denominator is **zero**, the verdict is **exit 2**, not PASS.

> **This rule is only safe together with the next one, and the first draft's version of it would have
> broken the estate's most important property.** If G1 declared `documents validated` as a secondary
> and a bundle legitimately has no connection, a bare "secondary zero → exit 2" rule turns contoso
> into a failure — destroying the constraint §3.2 says outranks everything. The resolution is that
> **`meaning-as-code` ships two fixture bundles** (one Athena-shaped, one DuckDB-shaped) and G1/G2
> **always include them in the examined population**, in every environment, including a
> single-bundle invocation. The secondary is then never zero unless the fixtures themselves are lost
> — which is precisely when exit 2 is the right answer. See §10.8 and §15.2.

**Two rules the shared contract keeps:**

- **A gate's non-zero denominator binds on the population it was asked to judge, not on what it found
  there.** For the connection gate the primary unit is *bundles examined* (≥ 1), **not** *connection
  documents found*. Getting this backwards makes `verdict()` turn contoso into exit 2.
- **Could-not-run belongs to the host; findings belong to the bundle.** A connector *term the standard
  does not know* is a bundle FAIL. A registered connector *whose module will not import here* is
  exit 2.

### 10.1 G1 · `tools/check_connection_governed.py` — **TRACK A**

Home `tools/` (stdlib + pyyaml + `mac.schema.json` only — **no `sdk` import**, preserving the measured
zero coupling in both directions). Auto-wired: `run_framework_gates.sh` globs `check_*.py`.

```
PASS: connection-governed — 0 violation(s) over 5 bundle(s) examined
      — 1 declaring a connection, 3 document(s) validated, 9 key(s) checked, 1 legacy-flat
        [population includes 2 built-in fixture bundle(s)]
```
```
PASS: connection-governed — 0 violation(s) over 3 bundle(s) examined
      — 2 document(s) validated [built-in fixtures]; subject bundle declares no connection —
        readable, not answerable, and that is a correct state.
```

**Exit 2 when:** zero bundles examined; **or** `mac.schema.json` carries no `$defs/ConnectionFile`;
**or** the declared `documents validated` secondary is zero. The second clause is what stops this gate
being a tautology — without the grammar it has no yardstick, and it says so instead of passing.

| Reject class | Mutant | `expect_line` fragment |
|---|---|---|
| `connection-file-unrouted` | a connection document the router does not map to `ConnectionFile` | `unrouted` |
| `undeclared-connection` | file present, `runtime.connection` absent (the fallback fires) | `undeclared` |
| `declared-missing` | `runtime.connection: deploy/prod.yaml`, no such file | `declared but missing` |
| `config-path-escapes-bundle` | `connection: ../../etc/creds.yaml` | `escapes the bundle root` |
| `schema-invalid` | `credentials: {mode: vault, ref: x}` | `credentials.mode` |
| `credentials-third-key` | `password:` beside `{mode, ref}` — no legal slot | `additionalProperties` |
| `ref-required-absent` | `{mode: named_profile}` with no `ref` | `requires a ref` |
| `ref-forbidden-present` | `{mode: ambient, ref: p}` | `forbids a ref` |
| `engine-keys-at-top-level` | <bundle>'s real shape today: `region`/`workgroup`/`glue_databases` at the root | `legacy flat` |
| `local-override-inside-root` | `connection.local.yaml` inside the bundle | `override sealed into` |
| `legacy-allowlist-silent` | a bundle with no declaration — the gate must **print** the fallback notice | `[legacy basename allowlist` |

| **must_pass** fixture | Why |
|---|---|
| clean, Athena-shaped | the positive case |
| **clean, no connection at all** | **the contoso regression test, non-negotiable — now a real assertion, not an `extra` lambda** |

**FALSE GREEN, and how it is now killed:** a gate that validates only files literally named
`connection.yaml` reports green over the one file the bundle does not use while
`runtime.connection: deploy/prod.yaml` points at a completely ungoverned file. Class attribution
(§10.0 rule 1) is what forces `declared-missing` and `config-path-escapes-bundle` to be **different
predicates** rather than one catch-all.

### 10.2 G2 · `sdk/gate/check_answerable_backed.py` — **TRACK A**

Home `sdk/gate/` — it must import `sdk.container.spec`, and `tools/` may not. It **replaces the
body** of `_backed_capabilities()`; `spec.py` delegates rather than re-implementing. Wired into
`sdk/cli/publish.py::_gate_failures()`.

```
PASS: answerable-backed — 0 violation(s) over 5 bundle(s) examined
      — 3 declaring capabilities, 2 claiming answerable, 2 claim(s) checked at MOUNT tier,
        2 at PUBLISH tier, 0 undetermined
```

> **REVISED — the mutants run TWICE, once per tier.** The first draft claimed *"'backed' has one
> definition and it is the mutation-tested one"* while §7.3's own table gave **two** evidence sets
> under one name (Tier 0 at mount, Tier 1 at publish) — and its mutants all ran at the publish tier.
> The path that runs on **every page load** had zero mutants. A passing-but-wrong implementation:
> `backs_answering(cr, m, *, tier="publish")` with full publish checks, called by `spec.py` with
> `tier="mount"` where the config-schema branch is skipped; every seeded mutant runs at the default
> tier and passes. **The self-test now runs the whole mutant set at each tier and prints a separate
> denominator per tier**, plus a mutant proving a mount-tier evaluation cannot return `True` for a
> config it did not verify.

| Reject class | Mutant |
|---|---|
| `empty-connection-backs-answerable` | 0-byte config + `answerable: true` — **today's live defect; the gate must be RED on it before any code changes** |
| `unregistered-mac-token` | `mac.connector.athna`, `answerable: true` |
| `connector-rejects-config` | a config the connector's schema file rejects |
| `interpreter-missing` | `runtime.interpreter` names a file that does not exist |
| `interpreter-empty` | a 0-byte interpreter file — the second half of the same defect |
| `mount-tier-returns-true-unverified` | **NEW** — a mount-tier evaluation returning `True` for a config it did not validate |
| `third-party-returns-true` | **NEW** — `acme.connector.snowflake` + `answerable: true` must yield `None`, never `True` (§7.3) |
| `ghost-index-entry` | **NEW** — a token present in an index/entry-point listing whose module does not exist (`find_spec` is `None`) must not yield `True` |

| **must_pass** fixture | Why |
|---|---|
| `undetermined-is-not-a-finding` | third-party connector + `answerable: true` → tri-state `None`, a **warning**, exit 2 — **must NOT produce `claimed but NOT backed`** |
| clean, contoso-shaped | no `capabilities:` block at all → must PASS, counted and named |

**`connector-rejects-config` is the false-green killer, and it only works as a mutant.** An
implementation that calls `validate()` and ignores the returned dict passes every other class.

### 10.3 G3 · `sdk/gate/check_connector_contract.py` — the hostile connector — **TRACK B**

```
PASS: connector-contract — 0 violation(s) over 3 connector(s) × 13 hostile class(es)
      = 39 probe(s), plus 3 clean fixture(s); 2 first-party, 1 non-SQL, 0 third-party discovered
```

**Exit 2 when zero connectors are discovered.** A machine where `meaning-as-code` is not installed
discovers nothing; without this the gate reports serene green having examined zero connectors.

| # | Hostile class | Mutant |
|---|---|---|
| H1 | exits at import | `import sys; sys.exit(3)` |
| H2 | raises at import | `raise RuntimeError("boom")` |
| H3 | import error | imports a module that is not installed |
| H4 | missing required method | no `read` |
| H5 | `supports` claims an unimplemented verb | declares `profile_relation`, does not override it |
| H6 | garbage return | `validate_config` returns `"yes"` / `None` / `{}` |
| H7 | hangs at import | `while True: pass` |
| H8 | hangs in a dry method | `time.sleep(10**6)` |
| H9 | **driver at import** | `import duckdb` at module top — measured: on this host `boto3` **is** installed and `duckdb` **is not**, so a top-level driver import makes offline validation impossible |
| H10 | **reaches the network** | `validate_config()` opens a socket — the billing class |
| H11 | `credential_plan` returns a value | seeds an `AKIA…`-shaped string; `check_bundle_secrets`'s generic patterns must fire |
| H12 | **ghost distribution** | metadata names a module `find_spec` cannot find → `ConnectorUnavailable`, exit 2, never `answerable: true` |
| **H13** | **registry cache poisoning** | **NEW** — a `resolve()` that memoizes by id **without clearing on failure**: after a broken connector, a second, good connector must still resolve |
| R1 | `read` accepts a write | must raise `ConnectorContractViolation` |
| R2 | `read` receives an interpolated value | MAC's plan-boundary precondition holds (§4.2a) |

| **must_pass** fixture | Why |
|---|---|
| **C1 `optional-absent-degrades`** | a connector without `profile_relation` yields **exit 0 and a printed degradation line** — the one class that must **NOT** be rejected. Now a `must_pass` entry with an `expect_line` fragment, not an `extra` lambda. |
| **C2 non-SQL clean** | the CSV/Parquet fixture of §3.2 conforms to `Connector` without implementing one `SqlConnector` verb |

**Execution mode, published as a table because two assertions cannot share one.**

> **REVISED — the first draft named this contradiction and did not resolve it.** It required every
> mutant to run "in a subprocess with a hard wall-clock cap", asserted **(e)** *"a second, good
> connector loaded in the same process still validates afterwards"*, and then listed as FALSE GREEN #2
> "running every mutant in a fresh subprocess, which makes assertion (e) unreachable". No class was
> assigned to either mode, and **no fixture could produce the (e) failure** — registry cache
> poisoning is a property of `resolve()`, not of any connector. So (e) would have landed in `extra` as
> `lambda base: ""` and passed. `tools/_plugin.py:228-236` already gets this right: its self-test
> seeds two roots and asserts the second, broken one is not served the first's module.
>
> **H1–H12 run in a fresh subprocess** (so assertion (a) — H1's exit code `3` must appear nowhere in
> the host's verdict — is checkable). **H13 and C1 run in-process**, and H13 is the seeded mutant
> that makes assertion (e) reachable. The table is printed by the gate.

**FALSE GREEN #1:** a harness asserting only `rc != 0` — it passes an implementation that converts
every hostile connector into **exit 1**, reporting a broken *plugin* as a broken *bundle*, the
precise damage `_plugin.py` exists to prevent. Killed by §10.0 rule 3 (`expect_line` + exit code per
class).

The loader declares its own limit rather than dropping it silently: `SIGALRM` cannot be armed off the
main thread or on Windows, so `load()` raises `ConnectorUnavailable("import deadline cannot be armed
on this thread")` unless the caller passes `allow_unbounded_import=True`. **An unenforceable guarantee
is declared unenforceable.**

### 10.4 G4 · `sdk/gate/check_engine_coupling.py` + `engine_coupling_floor.txt` — **TRACK A (as a ratchet)**

**This gate lands RED on purpose**, following the `check_boundaries --mode legacy` precedent: a gate
that goes green on the day it lands has never been shown to reject anything real.

> **REVISED TWICE, and both revisions matter.**
>
> **(i) The floor is a SET, not a number.** The first draft cited `mac_public_floor.txt` as the
> ratchet idiom. Measured, that file is a comment block plus a bare `0`, and
> `tools/check_mac_public.py:108-116 _floor()` returns the first `isdigit()` line as an **int**, with
> `:176 if floor is not None and len(hits) <= floor: PASS`. The rule "lower it, never raise it" is a
> **string inside the PASS line** enforced by nobody (`grep -rn mac_public_floor` returns exactly one
> hit — the gate reading it). A numeric floor is **identity-blind**: fix one driver import and add
> another elsewhere in the same commit → still 4 → green. Worse, the first draft's own Stage 4
> **scheduled that move**, relocating `botocore.config.Config` out of `data_plane.py:340` into
> `harvest_model.py` so "the `4 → 3 → 1 → 0` delta stays readable" — reducing a count by moving an
> import into a file the gate does not track. *(That file's own comment block, it should be said,
> documents exactly this failure mode from its own history: a floor of 146 over a measurement of 4
> was "141 findings of silent headroom".)* **`engine_coupling_floor.txt` therefore holds the SET of
> coupled module paths, compared by identity.** Any path outside the set is a finding regardless of
> total. New reject class **`coupling-relocated`**: a mutant removing one tracked import and adding
> one untracked import must **FAIL**. The floor file carries a **date and a named owner**, or it is a
> permanent exemption (Risk 8).
>
> **(ii) The unit is wrong, and a `0` with the wrong unit is the thing this record exists to remove.**
> Four reject classes that are all import- or exec-shaped would have printed `4 → 0`, to be quoted as
> "MAC no longer knows Athena" — while measured, **17 files** across `sdk/` and `tools/` carry an
> engine noun. The gate sees none of the thirteen it does not import:
> `sdk/acceptance/run.py:253` writes `"athena": <bool>` into **every persisted acceptance evidence
> document**; `run.py:171` routes to the literal `"wiki+athena"`; `run.py:210`,
> `sdk/project/questions.py:257` and `sdk/acceptance/grade.py:344` all read `eng.get("athena")`;
> `sdk/acceptance/sqlfacts.py:52` pins `DIALECT = "trino"` with the comment "the dialect the engine
> actually executes against (Athena/Trino)", so **a DuckDB bundle's acceptance SQL is graded in
> Athena's dialect**; `tools/mac_to_meta.py:679` ships `athena_ddl(…, s3="s3://<bucket>/meta/")`;
> and `sdk/authoring/data_plane.py:68,75,77` is the model prompt (§4.2). §12 named none of these.

**Five reject classes, and the verdict line prints both denominators:**

```
FAIL: engine-coupling — 4 driver-coupling finding(s) over 143 tracked .py file(s), floor set of 4
      — 2 module-level, 2 function-local, 0 shell-out, 0 dynamic, 0 relocated
      — SECOND UNIT: 17 file(s) carry an engine noun (string literal / prompt / persisted key);
        13 are out of scope for this gate — see §12, which names each with its count
```

| Reject class | Mutant / live instance |
|---|---|
| `engine-import-outside-connector` | **live: `harvest.py:147`, `materialize.py:290`** |
| `lazy-import-evasion` (any AST nesting depth) | **live: `materialize.py:312`, `data_plane.py:221`** |
| `shell-out` | **live in the wild: `mac-ontology-contoso/ask.py:53` — `subprocess.run(["duckdb", …])`, coupling with no import at all** |
| `dynamic-import` | `importlib.import_module("bo" + "to3")` outside the loader |
| **`coupling-relocated`** | **NEW** — remove one tracked import, add one untracked import: must FAIL |
| **`engine-noun-in-the-instrument`** | **NEW, second unit** — a vendor product name in a string literal, a prompt template, or a persisted evidence key, inside `sdk/` or `tools/` outside `sdk/connector/` |

**FALSE GREEN:** a top-level-only import scan. It reports 2 today and still reports 2 after someone
moves an import inside a function — and `materialize.py` **already has that shape, twice.**

The gate must print the **delta** (`4 → 3 → 1 → 0`), never the bare count — **and the delta must be
between two floor SETS, not two integers.**

### 10.5 G5 · `sdk/gate/check_zero_change.py` — the acceptance test — **TRACK B**

**Both limbs are required, and each alone is a tautology.**

**Negative limb — the core surface did not move.** `CORE_SURFACE` is every git-tracked path matching
`^sdk/.*\.py$`, `^tools/.*\.py$`, `^mac[._].*\.(json|yaml)$` — **150 files today** — minus
`sdk/connector/**` (the new package *is* the deliverable) and minus the permitted registration hunk,
**asserted structurally**: parse `mac_vocabulary.yaml` at base and head, and require byte-identity
after removing the permitted hunk. A line budget is trivially satisfiable by a three-line loader hack
smuggled into the same file; structural equality cannot be gamed. *(With §6.2's subtraction, the
permitted hunk for a second connector is now **empty** — adding an engine touches the shipped index,
which is software, not the canon. That strengthens this limb.)*

**Positive limb — the capability actually arrived.**

- **P1 (anti-tautology):** at `base`, the subject's `answerable` is not `True`, or the term does not
  resolve. **If it is already `True` at base, the test is vacuous → exit 2.** *(This is the one check
  in the first draft the false-green lens could not defeat. Unchanged.)*
- **P2 — REVISED, because the first draft's version was satisfiable by creating two nearly empty
  files and never executed one line of DuckDB.** Its P2 required
  `spec.validate(contoso)[…]["answerable"] is True` at head — which (a) contradicts §9.4's zero-edit
  guarantee for contoso, and (b) goes green the moment `runtime/interp.md` (one character) and
  `connection.yaml` (`credentials: {mode: none}`) exist, because P3 blocks every driver import and P4
  blocks every socket. **New P2:** the subject is the **built-in DuckDB fixture bundle**, and the
  assertion is that the DuckDB connector's `render_view_ddl` + `qualify` + `render_profile_sql`,
  driven from that bundle's config, produce output **byte-equal to a committed golden file**, with
  the `duckdb` module blocked by P3. That is the dry half — offline and free — and it is the only P2
  that cannot be satisfied by touching files.
- **P3:** the limb runs in a subprocess with a `sys.meta_path` finder raising `ImportError` for every
  driver module. **Measured justification: the `duckdb` module is not installed on this host anyway**
  — the block makes that deliberate rather than lucky.
- **P4:** the same socket guard as H10. Zero sockets. **This gate never costs money.**

```
PASS: zero-change — 0 violation(s) over 150 core-surface file(s) compared
      — 0 permitted registration hunks, 0 other changed; 4 limb assertion(s),
        1 golden file byte-equal, 0 driver(s) importable, 0 socket(s) opened
```

**Honest boundary:** registering the `connector:` **namespace** in `mac_vocabulary.yaml` is a
grammar-file edit, once, in Track A. **G5 measures the second and every later connector.** Anyone
quoting "adding a connector requires zero changes to MAC" without that qualifier is quoting a PASS
without its denominator.

### 10.6 G6 · `sdk/gate/check_connector_trust.py` — **TRACK A for classes 1–3, TRACK B for class 4**

Reject classes: `host_process_code_in_container` (`.py` in a staged or mounted tree) ·
`connector_name_is_a_path` · `undeclared_connector_config` · **`connector_schema_admits_a_secret`** ·
`entry_point_declares_a_mac_id`.

> **REVISED — class 4 pointed at an object §5.4 forbids from existing.** The first draft defined it
> as "an installed connector whose **`credentials` sub-schema** is open" — but §5.4 forbids a
> connector from declaring a credentials sub-schema **at all**. The class could only ever fire on its
> own synthetic fixture and would report clean over every real connector forever: **a class whose
> real-world denominator is structurally zero, inside the gate written to prevent zero-denominator
> passes.** It now points at the surface that exists: **the connector's `config_schema` must be
> closed AND must declare no property whose name matches a secret-shaped pattern** (the widened
> `_GENERIC` alternation of §5.4), plus any key the connector itself marks
> `x-mac-sensitivity: value`.

```
PASS: connector-trust — 0 violation(s) over 41 file(s) examined, 1 connector(s) declared,
      1 connector schema(s) inspected
```

**Two denominators, deliberately.** Classes 1–3 and 5 are **bundle** properties and run with nothing
installed. Class 4 is a **host/distribution** property; when no connector schema is present it is
reported with its own printed zero — `class 4 examined 0 connector schema(s)` — **never silently
skipped**, and never the gate's own exit 2, because the others ran over a real denominator. Its
self-test seeds a **synthetic** connector schema rather than relying on a real one.

**Exit 2 only when** there is no `mac.project.yaml`, or the tree holds no scannable file. **Never**
exit 2 for "connector not installed".

### 10.7 G0 · hygiene, and it is not optional — **TRACK A**

`sdk/gate/run_gates.sh:15` hardcodes a 9-entry `GATES` array over a directory holding 8 `check_*.py`
plus `annotation_isolation`. Consistent *today*; silently wrong the moment a gate is added — and this
record adds several. Derive `GATES` from disk, and print
`N/N gate self-tests green over M gate file(s) discovered`, **failing when `M != N`**.

**FALSE GREEN of the current script:** it prints `PASS: run_gates — 9/9 gate self-tests green` while
a tenth gate file sits in the directory, never invoked. **The denominator was the array, not the
directory** — this estate's signature defect, inside the suite that exists to catch it.

`run_gates.sh` also runs **self-tests only**, so a bundle-facing `sdk/gate` gate would never see a
bundle in any suite. It gains an optional `--bundle ROOT` second pass for gates declaring one.

### 10.8 The suite-level false green, and what now prevents it

**The whole suite can be green while `<domain>/<bundle>`'s live connection file is excluded from every run,
because it lives in a private repo.** CI covers `example_tpch_ontology` and `mac-ontology-contoso` —
neither of which has a connection — so the connection gates would run over **zero real connection
documents**. The first draft deferred this to Ruling 13 and proposed **naming** the exclusion. **A
named zero is still green.**

**The fix is structural, and it is in Track A:** `meaning-as-code` ships **two fixture bundles** —
one Athena-shaped, one DuckDB-shaped — under `sdk/gate/fixtures/`, and G1/G2 **always** include them
in the examined population. Every environment, including a laptop with no private repo and a CI box
with no credentials, then validates at least two real connection documents on every run. Combined
with §10.0's "declared secondary of zero → exit 2", the zero-denominator suite green becomes
unreachable rather than merely disclosed. **Every suite verdict still names which bundles were
examined**, and marks which were fixtures.

---

## 11 · Staging

### 11.1 TRACK A — build now, in `meaning-as-code`

Five commits on `feat/connection-grammar`, each revertible with `git revert`. Each ends at a **named
check that fails if the stage went wrong** — not one that passes if everything eventually works.

| # | Stage | Effort | Named check | Reverts by |
|---|---|---|---|---|
| **A0** | **Repair the harness (§10.0).** `Outcome.classes`, `Outcome.secondary`, `GateContract.must_pass`, `GateContract.expect_line`, `extra` returning `(checked, total)`; `run_self_test` asserts class attribution, invokes `main()`, captures stdout and exit codes. Additive: the eight existing gates are unchanged. | 0.5–1 d | a deliberately-wrong demo gate implementing **none** of three declared reject classes must now **FAIL** its own self-test — the exact gate that printed `PASS: demo-gate self-test — 7/7` today | `git revert`; the fields are additive |
| **A1** | **Fix the live crash, and start the ratchet.** `sdk/authoring/test_data_plane_callable.py::test_process_has_no_unbound_globals` — the AST check. **It fails today.** Thread `workgroup` through `harvest_data → process → profile_table`. Land `check_engine_coupling` RED with its **path-set** floor and its second unit (§10.4). | 0.5 d | the AST test goes green; `check_engine_coupling --self-test` exits 0 including `coupling-relocated`; its real run prints the 4-path set **and** `17 file(s) carry an engine noun` | delete two files, one kwarg |
| **A2** | **Declare, with zero schema change.** Add `runtime.connector: mac.connector.athena` to `<domain>/<bundle>/mac.project.yaml`. **Nothing else.** Free because `ProjectFile.runtime` is `{"type": "object"}` today. The declaration can sit unread for the whole soak. | 0.5 d | `validate_schema.py` on <bundle> still green; <bundle>'s `compile.json` verdict **byte-identical** to before | delete one line |
| **A3** | **Type it, govern it, and back `answerable` — one commit, because these are not separable.** The three `$defs`; `runtime`, `publish`, `serving` retyped; `connector` **namespace only** + `credential_mode` (six members) in `mac_vocabulary.yaml`; **`check_vocabulary_drift` deliberately NOT patched** (§6.2); `check_bundle_secrets._CONFIG_ALLOWLIST → config_paths(root)`; `_GENERIC` widened (§5.4); `check_schema_isolation` skip → **exit 2**; `serving.namespace` migration; `check_source_coupling.SCAN_DIRS += "sdk/connector"`; `check_boundaries` role with `forbid_import_roots: {"tools"}` + per-role denominators; the two fixture bundles; `sdk/connector/index.json` + two config schema files; **G2 replaces `_backed_capabilities`, the tri-state lands with its explicit `is False` guard, and `spec.py:43`'s filename fallback is deleted**; G1 lands in report mode; G0's `run_gates.sh` derives from disk. | 2 d | G1 `--self-test` rejects all eleven mutants **as their own class** and passes both `must_pass` fixtures; G2 does the same **at both tiers**; `test_empty_connection_does_not_back_answerable` — **fails today** — goes green; `spec.validate()` on all four bundles prints `capabilities.backed` with the connector named and the failing condition named | `git revert`; the schema addition is purely **additive**, so an un-reverted manifest still validates under the old schema. **Exception:** a manifest edited to satisfy the new `answerable` check must be reverted with it — **gate this stage on Ruling 11 having been answered** |
| **A4** | **Enforce.** G1 moves to `--enforce` in CI; delete the `engine:`-inference compatibility reader. Minimum **2 calendar weeks** after A3. | 0.5 d | G1 `--enforce` over every bundle exits 0, printing both denominators | re-add the reader; bundles edited in the soak stay edited, which is harmless |

**The compatibility window has one rule, and it is committal.** From A3 to A4: `runtime.connector`
present → **authoritative**. Absent with `engine:` present → infer, **WARN**, and count it in the
verdict line. **Both present and disagreeing → ERROR, refuse.** Never a silent precedence: two
declarations disagreeing about which warehouse you answer from is the 2026-08-13 gold-overwrite
incident wearing a different hat. The inference reader carries a literal `# DELETE AT STAGE A4`
marker that the enforce gate greps for.

**Track A total: 3.5–4.5 working days plus a 2-week soak, zero billed calls.**

### 11.2 TRACK B — do not start until Rulings 12 and 14 are answered

| # | Stage | Gated on | Where it is built |
|---|---|---|---|
| **B0** | Answer **Ruling 12** (which SDK is live) and **Ruling 14** (is a third-party connector a requirement now). Read `mac-platform/packages/mac-runtime/src/mac_runtime/adapters/` and `mac-platform/packages/mac-okf-core/src/okf_core/sources.py` **in full** before answering — neither was read in producing the first draft. | — | — |
| **B1** | `Connector` / `SqlConnector` (§4.2), two implementations, the **non-SQL third fixture**, the conformance suite | Ruling 14 = yes | **whichever SDK Ruling 12 declares live**, extending `GroundingAdapter` |
| **B2** | Entry-point discovery, `guarded_import`, `ConnectorAmbiguous`, G3's 13 hostile classes | Ruling 14 = yes | same |
| **B3** | Route materialize/lookups, then harvest/profiling; delete `_ORDERABLE`, the `services/chat/src` `sys.path` hack, and the three vendor strings in `_DP_SYS_TEMPLATE`; drive the coupling path-set floor down | **Ruling 12** | the live SDK's repo |
| **B4** | Permissions (§8.4), probe, receipts, `--i-accept-billing`, G5, G6 class 4 | Rulings 8, 9, 14 | same |
| **B5** | The one billed probe, by hand, once | Ruling 8 | operator |

> **If Ruling 14 is "no third party now"**, B1–B2 collapse to what the first draft's own kill
> criterion 4 already prescribes: **a dict of two classes in `sdk/connector/registry.py`**, resolved
> from the shipped index, at roughly one-fifth the effort. That is not a fallback; on today's
> measurements (§0.2) it is the **default**, and the full plugin architecture is the exception
> requiring a ruling.

### 11.3 Kill criteria — what makes abandoning this correct

1. **The DuckDB connector forces an Athena concept into the base class.** If `Connector` grows an
   `Optional[workgroup]`, an `Optional[output_location]`, or an `engine == "athena"` branch to make
   DuckDB fit — **stop**. **REVISED — and restated in the unit that can actually fire:** *if the
   **non-SQL** fixture (§3.2) cannot conform to `Connector` without implementing a `SqlConnector`
   verb, or if `Connector` grows a parameter named `sql`, the interface is a rename of the hole.*
   Two SQL engines cannot detect a SQL assumption; the criterion written against them was unfirable.
2. **The Athena connector's dependency closure is the chat service.** If `AthenaSQL` cannot be
   vendored or re-implemented (~120 lines of `start_query_execution` + poll + header-strip) without
   dragging `mac-platform/packages/mac-chat` in, the connector is not a driver, it is an application.
3. **The boundary produces a cycle.** If B3 cannot reduce the coupling set without the connector
   importing from `sdk.authoring`, the seam is in the wrong place.
4. **Third-party connectors turn out to have no buyer.** Then the entry-point path, the namespace
   grammar's loader half and most of the conformance suite are cost against nothing. **This is
   Ruling 14, it is answered in B0, and on today's measurements the burden of proof has moved: it
   must be shown that a buyer exists, not that one is absent.**
5. **B1 overruns 3 working days.** The interface is being designed against unknowns. Cut it to the
   six methods `materialize` actually calls today.
6. **NEW — Ruling 12 is answered "mac-platform is the live SDK".** Then Track B is not this record's
   to stage at all; it is re-filed there, against `GroundingAdapter`, and this record ends at Track A.

---

## 12 · Out of scope, with reasons **and with their measured counts**

> **REVISED.** The first draft's out-of-scope table named no measurement, so a `0` from
> `check_engine_coupling` could have been quoted as "MAC no longer knows Athena" while thirteen files
> it never looked at carried engine nouns. Each row that excludes a population now states **how big
> that population is**, and G4's verdict line prints both units (§10.4).

| Out | Measured size | Why |
|---|---|---|
| **`sdk/acceptance/` engine nouns** — `run.py:171` routes to the literal `"wiki+athena"`; `run.py:253` writes `"athena": <bool>` into every persisted acceptance evidence document; `run.py:210`, `sdk/project/questions.py:257`, `grade.py:344` read `eng.get("athena")`; `sqlfacts.py:52` pins `DIALECT = "trino"` | **4 files** (`acceptance/run.py`, `acceptance/grade.py`, `acceptance/sqlfacts.py`, `project/questions.py`) | A **persisted evidence format**, not a code path. Changing a key that appears in every stored acceptance document is a data migration with its own compatibility window. **But `sqlfacts.DIALECT` is a live correctness defect independent of this record — a DuckDB bundle's acceptance SQL is graded in Athena's dialect — and it should be filed separately and now.** |
| **`tools/mac_to_meta.py:679 athena_ddl(…, s3="s3://<bucket>/meta/")`** | **1 file, 5 hits** | The meta-plane emitter is a deploy-time artifact generator on a different axis. Named here so its `0` is never borrowed by G4's. |
| **`tools/mac_profile.py`, `tools/mac_admit_identity.py`** — `_plugin.required(root, "Athena")` | **2 files** | Author tools, explicitly CLI-invoked, quarantined off the open path by §8.2's boundary role. A live instance of the pattern §8.1 forbids; they should eventually migrate. |
| **The LLM / Bedrock seam.** `harvest_model.make_invoker`, `botocore.config.Config` at `data_plane.py:340`, `authoring.py:194,335`, model-id prefix dispatch | **2 files** | A **different axis**. Folding it in would make "the connector" mean "everything that touches AWS". The `botocore` import moves down into `harvest_model.py` **in its own commit, labelled model-axis** — and under §10.4's path-set floor that move is now **visible as a relocation** rather than a free reduction. |
| **Credential value resolution.** `sdk/authoring/connection.py:45` raises `NotImplementedError` for `secretsmanager` and `ssm` | 1 file | That refusal is correct and stays. Under this contract it becomes `ConnectorUnavailable` → exit 2, a loud could-not-run, never a silent fall-back. (Ruling 6.) |
| **Cross-connector query execution.** | 0 | Declared (§5.6), gated, and left unbuilt. |
| **Asymmetric signing.** `signed-verified` rests on symmetric HMAC | — | Nothing here depends on it, **because this design gives signatures zero execution authority** (§8.1). But the label overstates what it proves. |
| **The answering runtime and the no-hallucination invariant.** `mac_runtime/ask.py`, `mac-console/local_ask.py` | — | The 2026-09-12 topology review ranks that above this work and found the invariant breached in production. **A connector seam does nothing about it, and a green connector suite must not be reported as an answering-quality improvement.** |
| **Any repo restructuring.** | — | Same review: don't. Note that §0.1 asks *which existing repo*, which is not a restructuring. |
| **`mac_vocabulary.yaml#metadata.defines` staleness** (omits `test_kind`, `diagnostic_code`) | 1 entry, becoming 2 | A pre-existing defect, enforced by no tool. Track A adds the `connector` namespace and deliberately does not touch `defines`, leaving it one entry staler. Recorded so it is a decision rather than a discovery. |
| **Renaming `answerable`.** | — | After this change the capability means *declared, defined, and the config is well-formed against a schema a named party ships* — much stronger than file existence, and still **not** a claim that the source is up. |

---

## 13 · Operator rulings required

Numbered. Each states the recommendation, and the consequence of **each** option.
**Rulings 12 and 14 now gate Track B in its entirety. Ruling 11 gates Stage A3.**

**1 · BRAND PLACEMENT.**
Does `sdk/connector/athena.py` — a vendor product name, as a filename, in the public
`meaning-as-code` repo — satisfy *"NO INSTANCE SPECIFICS LIVE IN MAC"*?
*Measured:* `athena`, `duckdb`, `snowflake`, `postgres`, `bigquery`, `trino` are all **clean**
against the 17 patterns in `registers/public_tokens.txt` today.
**Recommend: yes.** A driver is a generic instrument; naming an **engine** is what `java.sql.Driver`
does. **REVISED — the question narrowed.** The first draft also asked you to accept `athena` and
`duckdb` as **members of a canon vocabulary**; that half is withdrawn (§6.2). What remains is a
**filename** and a key in a shipped **index file**, both software.
· *If no:* MAC ships **no** connectors and every connector is third-party — which contradicts "what
we provide lives in mac" and makes MAC's own reference bundle unanswerable from a stock install.
Run `check_mac_public` and `check_source_coupling` against a draft connector module **before** ruling.

**2 · NORMATIVE HOME FOR THE CONNECTOR ID.**
`mac.project.yaml#runtime.connector` (my choice, §5.1) or `connection.yaml#connector`?
· *Manifest:* the override chain can never substitute loaded code. **Cost:** a site can no longer run
Athena in prod and DuckDB locally by editing one gitignored file.
· *Config file:* per-environment engine swap works out of the box. **Cost:** `connection.local.yaml`
and `$DEPLOYMENT_CONFIG` become a code-substitution channel into the host process.

**3 · `config:` VERSUS THE `x-` RULING.**
You ruled that *"an extension is not a small schema, it is an UNCHECKED one."* The distinction
offered: an `x-` key was checked by **nobody**; `config` is checked by a JSON Schema a **named party
ships** — in Track A, a file in this repository — and when that party is absent MAC prints what went
unchecked **with its denominator** and **withholds the claim that depended on it**.
**Recommend: the distinction holds.** · *If it does not:* the design is `x-` with a driver attached
and must be rebuilt as per-engine core schemas — putting `region` and `workgroup` in the canon.

**4 · `credentials.ref` FORBIDDEN UNDER `ambient`.**
Deletes one shipped profile handle from <bundle>'s `connection.yaml`. Functional loss is **zero** —
`resolve_credentials()` returns `{}` for the chain and never reads it (verified).
**Recommend: forbid**, with the human hint moved to `note:`.

**5 · THIRD-PARTY IMPORT ON MOUNT.**
**Recommend: NEVER**, and **REVISED — the recommendation is now stronger than "do not import"**: a
third-party connector at mount does not merely skip Tier 1, it **cannot return `answerable: true` at
all** (§7.3), because a metadata hit is satisfiable with two text files and no code (measured, §6.4).
· *Consequence:* until Track B lands, only first-party-connector bundles can be `answerable: true`.
· *Against:* `spec.validate()` becoming a code-execution surface for any bundle opened merely to look
at.

**6 · UNWIRED CREDENTIAL MECHANISMS.** `secret_manager` (today `secretsmanager`/`ssm`) raises
`NotImplementedError`. Under this contract that becomes `ConnectorUnavailable` → exit 2, never a
silent fall-back. **Recommend: stays unwired**, out of scope (§12).

**7 · `allow_ddl: false` BY DEFAULT.** A shipped bundle can then never be used to write.
**This adds one step to every legitimate materialize run.** **Recommend: yes**, given 2026-08-13.
· *If no:* a published container plus a stolen credential is a write primitive.

**8 · WHAT THE ATHENA CONTROL-PLANE PROBE ACTUALLY COSTS.**
`athena:GetWorkGroup` + `glue:GetDatabase` — zero, or a metered API call? **Not measured, because
measuring it means making the call.** · *If genuinely free:* the Athena connector is reclassified
`probe_cost: free` and §7.5's whole tension collapses. **Gates Track B stage B4.**

**9 · TTL DEFAULTS AND THE RECEIPT STORE.** 3600 s / 60 s are **invented, not measured**, and
`~/.mac/receipts/` is per-user, per-machine. · **Related:** does `--i-accept-billing` exist in v1 at
all, and may CI **ever** run it? A nightly verification job needs an explicit, narrow, written
exception — **and you should write it, not me.** **Gates B4.**

**10 · MAC006 SEVERITY.** `mac.diagnostic_code` declares MAC006 (`claim-unearned`) as `warning`;
`spec.py` treats an unbacked capability as an **error** and must continue to. · *Either* MAC006's
severity becomes contextual, *or* a new error-severity code is minted into a set declared closed.
**I decline to mint one unilaterally.** **Gates A3.**

**11 · <bundle>'s `answerable: true` — BLOCKS STAGE A3.**
It is unbacked **today** (measured: `ok=False`), because no `runtime.interpreter` is declared. Two
honest fixes: add `runtime.interpreter: runtime/<bundle>_interpreter.md` (the file exists), or drop the
claim. · *Either way*, the first run of the new gate turns at least one green bundle red, **and that
is correct.** The pressure will be to loosen the tier rather than fix the config; rule before the
gate is wired into `_gate_failures()`, not after the first red build.

**12 · WHICH SDK IS LIVE — now the largest open question in this record, and it GATES TRACK B.**
> **REVISED — the first draft said "three live SDK copies". Measured, it is three on disk and two
> live.** `cap-ontology-mac-wiki/sdk/` still exists as a directory, but that repository's
> `ARCHIVED.md` (2026-09-11) states *"This repository is retired. Do not commit to it"* and records
> **391 of 391 tracked files migrated** into `mac-platform`. So the live pair is `meaning-as-code/sdk`
> and `mac-platform/packages/mac-sdk`, **and they have already diverged** — `profile_table`'s
> signature and their dependency contracts (§0.1). Risk 6's wiki half is retired by that document;
> its `mac-platform` half is not, because `mac-platform/packages/mac-chat/src/chat/sql.py` exists.
>
> · *If `mac-platform` stays a live SDK:* every Track B stage is done twice or the fork diverges
> further, and `GroundingAdapter` + `okf_core/sources.py` are two existing answers this record would
> be adding a third to.
> · *If it becomes a consumer:* one migration, one contract.
> **Nobody may start Track B before this is answered, and whoever answers it must first read
> `mac-platform/packages/mac-runtime/src/mac_runtime/adapters/` (527 lines) and
> `mac-platform/packages/mac-okf-core/src/okf_core/sources.py` (201 lines) in full.**

**13 · MAY CI RUN THE CONNECTION GATES OVER `<domain>/<bundle>`?**
> **REVISED — the zero-denominator risk this ruling was carrying is now closed structurally, so the
> ruling is no longer load-bearing.** §10.8 ships two fixture bundles inside `meaning-as-code` and
> always includes them in G1/G2's population, so the connection gates never run over zero real
> connection documents in any environment. <bundle> in CI would add **coverage of a real production
> shape**, which is still worth having. · *If no:* the suite verdict names the exclusion and the
> fixtures carry the denominator. · *If yes:* a private, billed bundle enters CI's read path, and
> `--enforce` must be scoped so no gate can reach `probe`.

**14 · IS A THIRD-PARTY CONNECTOR A REQUIREMENT NOW? — GATES TRACK B.**
> **REVISED — the burden of proof has moved.** Measured (§0.2): one production connection file, one
> falsifier, and the word "connector" appears **zero** times in the estate's governing plan
> (`mac-integration-kit`'s `BOARD.md`, `ROADMAP.md`, `TARGET.md`).
> · *Yes:* B1–B2 are 2–3 days (namespace loader, entry-point resolution, `guarded_import`, the
> 13-class hostile suite, unrunnable-vs-fail semantics), and §8.4's permission surface earns its cost.
> · *No:* the correct build is a dict of two classes in `sdk/connector/registry.py` resolved from the
> shipped index, at roughly one-fifth the effort — and kill criterion 4 fires on everything else.
> **Track A is unaffected either way**, because the bundle's only forward commitment is the
> namespaced identifier (§6.1).
> · **Related:** if yes, should answer-time loading be gated on container trust level, and what is
> the floor? Nothing today refuses to load a bundle plugin from an `unverified` container.

**15 · NEW — DOES THE HARNESS REPAIR (§10.0) LAND FIRST, AS ITS OWN COMMIT?**
Every mutant table in this record is an unverified claim until `sdk/gate/contract.py` can attribute a
finding to a reject class, express a must-PASS fixture, and read a gate's printed line. **Recommend:
yes, Stage A0, before any new gate is written.** · *If no:* the first draft's demonstrated failure
mode stands — a gate implementing **none** of its declared reject classes prints
`PASS: … 7/7 (3 mutant(s) rejected as their own class…)` — and this record's gate count becomes the
next zero-denominator pass, inside the record that exists to name them.

---

## 14 · Risks carried, stated rather than mitigated

1. **Entry points reduce connector trust to `pip` trust** *(Track B)*. Whoever controls the Python
   environment controls what `mac.connector.athena` resolves to. That is the correct place for the
   decision — the operator's install — but **this record must not be read as claiming the connector
   supply chain is solved.**
2. **`permissions` is a declaration, not an enforcement** *(Track B)*. A connector declaring `{read}`
   that opens a socket is lying and nothing here detects it. The mitigation is that the lie is
   attributable and diffable.
3. **Profile-free authoring is a quality cliff.** A connector without `profile_relation` authors the
   whole data plane with no measured evidence, and the DQ prompt's own rule (*"cite the profile
   number; NEVER invent a statistic"*) then has nothing to cite. The spec forces confidence `Q` and
   prints `profiled 0 of N` — **and that print is now an `expect_line` assertion (§10.0)**. Consider
   making the profile denominator part of the harvest manifest, not just stdout.
4. **The socket guard is not airtight.** A connector can fork+exec or use `ctypes`. The gate raises
   the cost of an accidental billed call; it does not **prove** offline.
5. **Two protocols for one seam — and this record's own contribution to the problem is now the
   largest risk it carries.** `GroundingAdapter` lives in another repo on another release train, and
   `okf_core/sources.py` is a third design for the same question. §0.1 makes this Ruling 12's
   subject rather than a risk to absorb, but until that ruling lands, **anyone reading §4 should read
   it as a proposal to extend `GroundingAdapter`, not to replace it.**
6. **The dead code may be load-bearing somewhere else.** `data_plane.profile_table` and
   `materialize._athena_executor` are unimportable **here**, but
   `mac-platform/packages/mac-chat/src/chat/sql.py` exists. **Deleting them without checking every
   host's `sys.path` assembly could break a live runtime path this session did not measure.** (The
   `cap-ontology-mac-wiki` half of this risk is retired by that repo's `ARCHIVED.md`; the
   `mac-platform` half is not.)
7. **The shallow overlay merge is already a live hazard.** `load_connection` does `{**base, **ov}`,
   so a `connection.local.yaml` carrying `credentials: {mode: named_profile}` with no `ref` silently
   produces a credentials block with no ref, rejected at **use** time, after the harvest has started.
   Under the nested `config:` envelope a shallow merge becomes **destructive** — an overlay setting
   one key replaces the whole block. The merge must become deep-for-mappings,
   replace-for-scalars-and-sequences, with `spec_version` required to match across layers, and **it
   needs its own mutant in Stage A3.**
8. **Ratchets become permanent exemptions.** A floor with no date and no named owner is a permanent
   exemption. §10.4 makes `engine_coupling_floor.txt` a **path set** with a date and an owner, which
   removes the "satisfied by different findings" failure — but not the "nobody ever lowers it"
   failure. `tools/mac_public_floor.txt`'s own comment block records that exact history (a floor of
   146 standing over a measurement of 4: *"141 findings of silent headroom"*), and it is the
   precedent to check before trusting the mechanism.
9. **This work will look like progress on answerability. It is not.** Nothing here is exercised by
   `connect()`; everything proven is about **validation**. A connector can pass every gate and still
   be unable to open a session. That gap is structural — it follows from the no-AWS rule — and it
   must be stated wherever this suite's green is quoted.
10. **NEW — Track A's `answerable: true` is reachable only by first-party-connector bundles until
    Track B lands** (§7.3). That is a deliberate, recorded narrowing, not an oversight; a third-party
    bundle is `undetermined`, which is a warning and never a bundle defect.

---

## 15 · What the adversaries found

Three adversaries attacked the first draft of this record on 2026-09-13, each along one lens. All
three returned **does not survive**. This section records every objection, what changed, and — where
an objection was rejected in whole or in part — **why**. A specification that hides its own review is
worth less than one that publishes it.

| Lens | Question | Verdict | Fatals | Majors | Minors |
|---|---|---|---|---|---|
| 1 | Does this put instance specifics back into MAC? | does not survive | 2 | 8 | 3 |
| 2 | For every gate proposed, a wrong implementation that passes it | does not survive | 3 | 9 | 1 |
| 3 | Is this too much — would a `$def` plus validation capture most of the value? | does not survive | 1 | 4 | 2 |

**The headline outcome: the recommendation changed** (§0). Lens 3's fatal — the seam is being built
in the repository where the coupled code is dead, while the live, diverged copy sits in another
repository that already holds two competing designs for the same seam — is not answerable by any
edit to this document. Under this estate's rule, the correct response is a different recommendation,
and that is the Track A / Track B split.

### 15.1 Lens 1 — instance specifics in MAC

| # | Objection | Disposition |
|---|---|---|
| **F1** | §6.6 writes `athena` and `duckdb` into `mac_vocabulary.yaml` as canon members — the exact act §3's own MAC row forbids and §6.1 argues against one page earlier, and it was load-bearing (mount tier + Authority test), so a third first-party engine was a canon bump forever | **ACCEPTED, fatal.** The member list is **deleted**. §6.2 registers the **namespace only**; §6.3 makes the first-party set a shipped, diffable **index file** — software, not canon. The fix is subtractive. |
| **F2** | The proposed vocabulary block does not validate: the member object is `additionalProperties: false` over six keys and all three proposed keys (`config_majors`, `entry_point`, `status`) are illegal — the identical argument the draft used to reject `members_from:` | **ACCEPTED, fatal.** Verified against `mac.vocabulary.schema.json`. Dissolves with F1. **`mac.vocabulary.schema.json` is not widened** — that is how the canon becomes a build file. |
| M1 | The one REQUIRED I/O verb takes `sql: str`; `render_view_ddl` / `quote_identifier` / `render_profile_sql` sit under REQUIRED, so a source with no DDL cannot conform. MAC, the generic instrument, is where that assumption lived | **ACCEPTED.** §4.2 splits `Connector` (identity, config, `read(ReadRequest)`) from `SqlConnector` (verbs, quoting, DDL, `explain`). **And** §3.1 states the v1 scope out loud — only relational sources are built — because the claim must match the artifact. |
| M2 | §4.2 retires MAC parsing types and two paragraphs later moves `assert_bound_params_only` into MAC — a regex scanner that pins `:name` by its own admission and rejects every quoted literal, making `date '2024-01-01'` illegal | **ACCEPTED.** §4.2a: `param_style` is the connector's ClassVar and the connector enforces it in its own `read()`. MAC asserts only the plan-boundary structural fact. `assert_bound_params_only` **stays where it is** and is not promoted. |
| M3 | `serving.schema` / `serving.database` put relational nouns into core manifest grammar every bundle inherits | **ACCEPTED.** §5.5 → `serving.namespace: [<segment>, …]`, engine-neutral; `qualify()` turns segments into an engine address. |
| M4 | `check_engine_coupling` counts driver imports, but instance specifics in MAC are mostly **strings** — 17 files, not 4 — so `4 → 0` would be quoted as "MAC no longer knows Athena" while a vendor name is a persisted key in MAC's own evidence format | **ACCEPTED.** Re-measured: **17 files**. §10.4 gains a fifth reject class over string literals, prompt templates and persisted keys, with its **own printed unit**; §12 names each excluded population **with its count**. |
| M5 | §3 states a rule for connector contents and specifies no gate; `sdk/connector/` falls outside `check_source_coupling.SCAN_DIRS` — the one new directory for engine code is the one no generic-instrument gate reads | **ACCEPTED.** Verified `SCAN_DIRS = ("sdk/project","sdk/authoring","sdk/cli","sdk/container")`. §8.2 adds `"sdk/connector"` plus a mutant seeding a region default and an infra handle; `check_bundle_secrets` extends over `sdk/connector/**`. |
| M6 | `mac.credential_mode` is a closed four-member enum derived from one cloud's chain; interactive SSO, mTLS and Kerberos have no legal `mode` | **ACCEPTED IN SUBSTANCE, REMEDY PARTLY REJECTED.** The set is widened to six (`+ interactive`, `+ client_certificate`) and the vocabulary says plainly that a new member is a framework release. **Rejected: validating `mode` by pattern.** An open credential-mode token means MAC cannot answer *"does this bundle need a secret?"* offline — the one question the field exists to answer — and credential mechanisms are a decades-stable taxonomy of about six, whereas engines are an open commercial space. **The asymmetry with §6.1 is deliberate and is now stated in the document rather than left to be discovered.** |
| M7 | The falsifier cannot falsify the assumption that got smuggled in: Athena and DuckDB are both SQL, so they can detect an AWS assumption and are structurally incapable of detecting a SQL assumption; kill criterion 1 would sail past `read(sql: str)` | **ACCEPTED.** §3.2 adds a **third, non-SQL fixture** (CSV/Parquet directory); the conformance verdict prints `3 connectors × N assertions, 1 non-SQL`; **kill criterion 1 is rewritten in the unit that can fire** (§11.3). |
| M8 | §4.2 misattributes "verbatim glue type" to the grammar — it is a bare `{"type":"string"}`; the string lives in `_DP_SYS_TEMPLATE`, the prompt MAC ships to a model, and therefore appeared on no removal list | **ACCEPTED.** Verified. The parenthetical is corrected in §4.2 and the template's **three** vendor strings (`data_plane.py:68,75,77`) join the deletion list via two new sentinels. |
| m1 | `connectionProbe: {command, billed}` puts an executable instruction into the bundle grammar, in the record that bans executables from bundles, protected only by prose | **ACCEPTED.** The `$def` is **deleted** (§9.1). 37 → **40** `$defs`, not 41. |
| m2 | §5.4's "the security posture becomes a schema fact" holds for `credentials` and fails for `config:`, and the fallback detectors are AWS-only | **ACCEPTED.** Verified by executing the scanner: `client_secret`, `api_key`, `token`, `auth_token`, `passphrase`, `private_key_path` all **MISSED**. §5.4 states the limit out loud, widens `_GENERIC`, and gives the connector per-key sensitivity marking in Track B. |
| m3 | `billed` is defined in CloudTrail terms on a generic base class | **ACCEPTED.** §7.5c: generic definition on the base, Athena's reasoning in Athena's own docstring. |

### 15.2 Lens 2 — false greens

| # | Objection | Disposition |
|---|---|---|
| **F3** | `sdk/gate/contract.py` cannot attribute a finding to a reject class; the only per-mutant assertion is `if out.clean: fail`. A gate implementing **none** of three declared classes was built and **run**, printing `PASS: demo-gate self-test — 7/7`. All 40+ mutants are unverified claims | **ACCEPTED, fatal.** Verified by reading `contract.py:40-50, 157-159`. §10.0 is new: `Outcome.classes`, per-class assertion, and *no other class fired*. **It is Stage A0 and it blocks every other gate.** Rule 3 of the brief applies: the check was **replaced**, not wrapped. |
| **F4** | The two properties the record calls non-negotiable — contoso-with-no-connection must PASS, and C1 optional-absent must NOT be rejected — are structurally inexpressible: `mutants` requires rejection, `clean` is one callable, and `extra` accepts `lambda base: ""` **and inflates the printed denominator** | **ACCEPTED, fatal.** §10.0 adds `must_pass` and changes `extra` to return `(checked, total)`. Both properties are now real assertions (§10.1, §10.3). |
| **F5** | `answerable` at mount remains a presence check: a forged "resolvable" third-party connector made of two text files with no module satisfies every mount-tier condition — `entry_points()` discovers it while `find_spec` returns `None` | **ACCEPTED, fatal.** Independently reproduced on this machine. §7.3: a third-party connector at mount yields **`None`, never `True`**; §6.4 adds the `find_spec` requirement for Track B; G2 gains `third-party-returns-true` and `ghost-index-entry` mutants. |
| M9 | G2 is mutation-tested on the publish path and silent on the mount path, while the record claims "backed" has one definition and it is the mutation-tested one | **ACCEPTED.** §10.2: the mutant set runs **at each tier**, with a separate printed denominator per tier, plus `mount-tier-returns-true-unverified`. |
| M10 | The `secondary` denominator is rendered but never enforced, and the record's own "bundles examined, not documents found" rule legalizes a permanent zero-denominator PASS in CI | **ACCEPTED, WITH THE REMEDY TIGHTENED AND ONE HALF REJECTED.** Accepted: `verdict()` exits 2 when a **declared** secondary is zero. **Rejected as a standalone rule** — on its own it converts the contoso property (a bundle with no connection must PASS) into exit 2 the moment a gate declares a document denominator, destroying the constraint §3.2 says outranks everything. It is therefore adopted **only together with** the lens's other half: `meaning-as-code` ships two fixture bundles always included in G1/G2's population (§10.8), so the secondary is never zero unless the fixtures are lost. |
| M11 | Nothing anywhere reads a gate's printed line or exit code, yet at least seven guarantees are entirely about what gets printed | **ACCEPTED.** §10.0 rule 3: `expect_line` per class; `run_self_test` invokes `main()`, captures stdout and the exit code. |
| M12 | A numeric `engine_import_floor` is identity-blind — coupling that MOVES still passes — and Stage 4 schedules exactly that move | **ACCEPTED IN SUBSTANCE, ONE CITATION CORRECTED.** Verified: `check_mac_public._floor()` is a bare int compare and "lower it, never raise it" is enforced by nobody. §10.4 makes the floor a **path SET** and adds `coupling-relocated`. **Corrected:** the lens described `mac_public_floor.txt` as "304 path lines"; measured, it is **17 lines — a comment block and a bare `0`.** That strengthens rather than weakens the objection: the file's own comments record a floor of 146 standing over a measurement of 4, *"141 findings of silent headroom"*. |
| M13 | G3 assertion (e) has no mutant that can make it fail, and it contradicts the subprocess isolation the same section mandates — the draft names the contradiction and does not resolve it | **ACCEPTED.** §10.3 seeds **H13, registry cache poisoning**, and publishes the execution-mode table: H1–H12 in a fresh subprocess, H13 and C1 in-process. |
| M14 | G5's positive limb is satisfied by creating two nearly empty files, never executes one line of DuckDB, and contradicts §9.4's zero-edit guarantee for contoso | **ACCEPTED, WITH A DIFFERENT RESOLUTION OF THE CONTRADICTION.** Accepted: P2 becomes golden-file byte-equality over `render_view_ddl` + `qualify` + `render_profile_sql` with the driver blocked. **Rejected: driving it from *contoso's* config** — that is precisely what forces contoso to gain an interpreter and a connection file and breaks §9.4. The subject is instead the **built-in DuckDB fixture bundle**; contoso stays at zero edits and stays the falsifier. |
| M15 | `forbid_import_roots: {"_plugin"}` cannot match any natural spelling of the import it forbids, since `_import_roots()` takes `split(".")[0]`; plus a double-counted denominator and a silent per-class zero | **ACCEPTED.** Verified all three. §8.2 uses `{"tools"}`, adds per-role denominators, and adds a mutant proving a role examining zero files is reported as its own zero. |
| M16 | §5.4's "nowhere to put a secret" is true of `credentials` only; G6's class 4 checks a `credentials` sub-schema §5.4 forbids from existing — a class whose real-world denominator is structurally zero | **ACCEPTED.** §10.6 re-points class 4 at the connector's **`config_schema`**; `_GENERIC` is widened (§5.4). |
| M17 | The §6.6 one-line patch points the drift gate at a population where a connector id can never appear, and adds a false-positive surface on prose | **ACCEPTED.** §6.2 **does not patch** `check_vocabulary_drift._vocabularies()`, and says so explicitly so nobody later "fixes" the omission. Enforcement lives in `$defs/connectorRef` and G2. |
| m4 | The derived MAC005 is silent on a bundle that has a connection file and never declares it, and nags a bundle that legitimately has none | **ACCEPTED.** Verified the `applicable`/severity logic. §5.2 **withdraws the MAC005 derivation claim**; G1's `undeclared-connection` class owns it, because it has the filesystem predicate the adoption register lacks. |

### 15.3 Lens 3 — is this too much

| # | Objection | Disposition |
|---|---|---|
| **F6** | The seam is being built in the repo where the coupled code is **dead**, while the live, diverged copy sits in another repo that already has a working engine-agnostic protocol (`GroundingAdapter`, 527 lines, two implementations) **and** a competing source-type registry (`okf_core/sources.py`, 201 lines) never mentioned in the draft. Stages 3–4 refactor a path that cannot execute here | **ACCEPTED, fatal, and it changed the recommendation.** All measurements independently verified. **No edit to this document answers it**, so §0 splits the record: Track A is repo-stable grammar/security/`answerable` work; Track B is gated on **Ruling 12** and, when built, extends `GroundingAdapter` and reconciles with `okf_core/sources.py` in whichever repo is live. |
| M18 | The mount path needs no code loading at all — the dry half is classmethods, pure functions of data — and routing it through an imported class is what manufactures the entry-point registry, `guarded_import`, SIGALRM deadlines, `ConnectorAmbiguous`, squatting corroboration and the tri-state trap | **ACCEPTED.** §6.3: the first-party set is a shipped **index of JSON Schema files**; mount-time validation is `jsonschema` over a file in the repo, **zero imports**. §6.3 also records the honest limit: a cross-field rule JSON Schema cannot express belongs to `validate_config()` at publish, and the tier reached is printed. |
| M19 | The headline defect (`answerable` backed by `Path.exists()`) is repaired **last**, 6.5–7.5 days in, behind machinery it does not need — a self-inflicted dependency on the registry | **ACCEPTED.** Stage 5 is **folded into Stage A3**, in the same commit as the `$def`. No registry, no import, and the tri-state lands with its `is False` guard. |
| M20 | The served denominator is one: four `connection*.yaml` trees in the estate, two of them published copies; both live files Athena; the "second engine" does not use the SDK; "connector" appears zero times in the governing plan | **ACCEPTED.** Stated in §0.2 next to the effort figure, and it is what moves the burden of proof on Ruling 14 (§13). |
| m5 | The crash used to argue "a contract rather than a cleanup" is an eight-hour-old unthreaded kwarg — evidence for a missing test, not for a plugin architecture | **ACCEPTED.** §2.1(c) **withdraws the inference** and keeps Stage A1 exactly as it was: one kwarg, one AST test, 0.5 d. |
| m6 | The stated remedy for "our gates pass having examined nothing" is seven more gates, and the record concedes the suite can still be green over zero real connection documents | **ACCEPTED, WITH ONE SCOPE DISAGREEMENT RECORDED.** G3, G5 and G6-class-4 move to Track B with the machinery they test; `check_schema_isolation:120` and `run_gates.sh`'s denominator are fixed in Track A. **Not deferred: G4.** The lens's list did not name it, and it should not be deferred — its *measurement* is independent of the extraction, and its value is the ratchet that stops the 17-file engine-noun population growing while Ruling 12 is open. Only the **reduction** stages move to Track B. |

### 15.4 What the adversaries said holds, and must not be lost in a later edit

Recorded because a revision is also a chance to break something that worked:

- **`credentials: {mode, ref}` with `additionalProperties: false` wrapping an opaque `config:`** —
  called "the strongest anti-smuggle device in the estate": there is no legal slot for a vendor key
  or a credential value at MAC level, **by schema rather than by convention**.
- **Validating connector ids by pattern, never by enum** (§6.1).
- **Refusing bundle-supplied connectors** (§8.1) and **refusing a per-connector credentials schema**
  (§5.4).
- **`unconnected` as a first-class non-failure tier**, so contoso stays browsable (§3.2, §7.2).
- **The exit-code-as-a-property-of-the-raise taxonomy** (§4.6).
- **`supports` ⟺ overridden, instead of `hasattr`** (§4.3).
- **`ConnectorAmbiguous` refusing rather than picking** (§6.5).
- **`void` vs `stale` receipts** (§7.6).
- **"No gate reads a receipt as evidence of `answerable`"** (§7.6).
- **G3 assertion (a):** H1's exit code `3` must appear nowhere in the host's verdict.
- **G5's P1 anti-tautology clause** — named as the one check in the document an adversary could not
  defeat.
- **Removing `Glue` from `TableFile.profiled_via.description`** — verified as the single vendor token
  in the grammar (`Glue` = 1, `aws` = 0, `boto` = 0).
- **Retiring `_ORDERABLE`**, eleven Hive/Presto type names sitting in the generic instrument.

### 15.5 The standing caution

The first draft named the zero-denominator pass as this estate's dominant defect and then proposed
seven gates resting on a harness that could not tell one reject class from another. **Until Stage A0
lands, no number in §10 may be quoted as coverage** — not the mutant counts, not the class counts,
not the conformance arithmetic. That is the same rule this estate already applies to any gate's PASS:
never without its denominator.

STOPPING.

---

## Addendum — the console's Connection page

Operator requirement, 2026-09-13, recorded separately at
[`REQ-2026-09-13_console-connection-page.md`](REQ-2026-09-13_console-connection-page.md). This
specification covers the grammar, the contract and the host; it did not cover the UI, and the UI has
the same defect one layer up.

`packages/mac-console/.../views/ConnectionView.jsx` hardcodes **thirteen fields of one engine** —
Engine, Region, Account, Workgroup, Output location, Catalog, View database, View schema, Glue
Fact/Dimensions, Credentials Mode and handle. A second engine renders as eleven empty rows.

The operator's ruling is to RECYCLE that page rather than replace it, and the file supports it: its
`Field({label, value, hint})` and `Section({label, children})` primitives are already generic and
survive verbatim. The defect is entirely in the CALL SITES. Roughly 200 of its 259 lines stand.

Three things the page must gain, all of which this specification already defines:

  * **the connector itself** — which one, its version, first-party or third-party, and whether it is
    installed on this host (a bundle may name a connector nobody has);
  * **the tier reached**, not a boolean — `declared`, `resolvable`, `reachable` mean different
    things, and the page currently shows none of them;
  * **a "Test connection" button** — the `reachable` probe, and the only way it ever runs. Never on
    page load, mount or refresh. The probe's result carries its timestamp, because a connection that
    answered an hour ago is evidence and not a guarantee.

Its acceptance test is this document's zero-change test, seen from the UI: **a DuckDB bundle and an
Athena bundle must both render correctly with no console change between them.**
