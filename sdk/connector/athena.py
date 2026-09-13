#!/usr/bin/env python3
"""athena.py — the Athena connector. STRUCTURALLY COMPLETE AND NEVER INVOKED.

RECORD: §4.1 (the eleven operations), §7.5c (why this engine's probe is billed), §11.3 kill
criterion 2 (the dependency closure).

READ THIS BEFORE TRUSTING ONE LINE OF IT.
Not one wet method in this file has ever run. No AWS call was made while writing it, deliberately:
every call this module can make is billed, and Ruling 8 ("nobody measured the money cost, because
measuring it means making the call") is open. `UNTESTED` at the bottom of this module enumerates the
surface that carries that status, as data, so a later gate can require the list to SHRINK rather
than require a reader to notice it stopped being true.

THIS IS NOT A PORT. There was nothing runnable to port, and the measurement says so:

  * `sdk/authoring/data_plane.py:30` computes `_CHAT_SRC = <repo root>/services/chat/src` and inserts
    it on `sys.path`, then `profile_table()` does `from chat.sql import AthenaSQL`. MEASURED on this
    tree: `services/` DOES NOT EXIST, and `importlib.util.find_spec("chat")` returns `None`. The
    import cannot resolve. Every Athena read in this repository is downstream of it.
  * `sdk/authoring/materialize.py:312` repeats the same `sys.path` hack for the same module in the
    DDL seam.
  * Because that path is unimportable, nothing could execute it and no test could cover it. The
    consequence is recorded in `data_plane.process()`'s own docstring: `workgroup` "was NOT a
    parameter for eight hours on 2026-09-13, and the body referenced the bare name `workgroup`
    anyway: every call raised NameError before reaching Athena. Nothing caught it."

So this file is what that code SHOULD have been, written against the contract, with the failure mode
above designed out: the dry half is pure and importable with no boto3 installed, and the wet half is
one narrow method whose absence is visible rather than latent.

KILL CRITERION 2, and this file is the evidence for it. "If `AthenaSQL` cannot be vendored or
re-implemented (~120 lines of start_query_execution + poll + header-strip) without dragging
mac-chat in, the connector is not a driver, it is an application." `_execute` below is that
re-implementation, and its dependency closure is boto3 and nothing else. No `mac-chat`, no
`chat.sql`, no `services/` tree, no `sys.path` insertion.

THE HEADER-STRIP, because it is the one non-obvious piece. `get_query_results` returns the column
header as ROW 0 of the first page for a SELECT, and only for the first page. Dropping "the first row
of every page" loses one real row per page after the first; not dropping it at all reports the
header as data -- a row of column names that type-checks as strings and silently becomes a value in
a profile. The rule is: drop row 0 of page 0 only.

WHY THIS ENGINE'S PROBE IS BILLED (§7.5c says this reasoning belongs here, not on the base class):
an Athena call is metered and rate-limited, it is recorded in the account's own audit trail, and a
`SELECT 1` writes a result object to the workgroup's S3 output location and enters that workgroup's
scan accounting. The probe below is therefore CONTROL-PLANE ONLY -- `athena:GetWorkGroup` plus
`glue:GetDatabase` -- deliberately not `SELECT 1`. It still costs an API call and still appears in
the audit log, which is why `probe_cost` is "billed" and why nothing calls it automatically.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, ClassVar, Mapping, Sequence

from sdk.connector.base import (
    ColumnSpec,
    ConfigProblem,
    ConnectorConfigError,
    ConnectorUnavailable,
    CredentialPlan,
    ProbeResult,
    ReadRequest,
    ReadResult,
    RelationRef,
    RelationSchema,
    SourceError,
    SourceErrorReason,
)
from sdk.connector.sql import SqlConnector

_SCHEMA_FILE = Path(__file__).resolve().parent / "schemas" / "athena.1.json"

#: The eleven Hive/Presto type names from data_plane.py:48-58 `_ORDERABLE`, moved to the connector
#: that owns them. This is the WHOLE POINT of `orderable()`: the list did not get better, it got a
#: correct home. In the generic instrument it was applied to every engine the SDK might reach --
#: including DuckDB, whose HUGEINT / UTINYINT / TIMESTAMP_NS columns it silently excludes from
#: min/max. Here it governs exactly one engine's type vocabulary, which is the only scope on which
#: it was ever true.
_ORDERABLE_PREFIXES = (
    "int", "bigint", "double", "float", "decimal", "date", "timestamp",
    "smallint", "tinyint", "real", "numeric",
)

#: Athena terminal states -> the closed reason vocabulary. `FAILED` is REQUEST_FAILED (exit 1: the
#: engine judged the request and refused it); `CANCELLED` is exit 2 (nothing was judged). The split
#: is §4.6's, and it is the reason a single error class with a `reason` field was rejected.
_STATE_REASON: Mapping[str, SourceErrorReason] = {
    "FAILED": SourceErrorReason.REQUEST_FAILED,
    "CANCELLED": SourceErrorReason.CANCELLED,
}

#: botocore error code -> reason. Keyed by STRING so this module's taxonomy is readable with boto3
#: absent. (On this host boto3 IS installed, which is precisely why a top-level import here would
#: have gone unnoticed -- record H9 pairs that with duckdb's absence for the same reason.)
_ERROR_CODE_REASON: Mapping[str, SourceErrorReason] = {
    "AccessDeniedException": SourceErrorReason.UNAUTHORIZED,
    "UnauthorizedException": SourceErrorReason.UNAUTHORIZED,
    "ExpiredTokenException": SourceErrorReason.UNAUTHORIZED,
    "ThrottlingException": SourceErrorReason.EXECUTION_LIMIT,
    "TooManyRequestsException": SourceErrorReason.EXECUTION_LIMIT,
    "EndpointConnectionError": SourceErrorReason.UNREACHABLE,
    "ConnectTimeoutError": SourceErrorReason.UNREACHABLE,
    "InvalidRequestException": SourceErrorReason.REQUEST_FAILED,
    "ResourceNotFoundException": SourceErrorReason.REQUEST_FAILED,
    "EntityNotFoundException": SourceErrorReason.REQUEST_FAILED,
}


class AthenaConnector(SqlConnector):
    """Athena + Glue. UNTESTED — see the module docstring and `UNTESTED` below.

    `config` is `{region, workgroup, catalog, output, glue_databases}` (§5.3). Every one of those
    keys is this connector's; none of them appears in MAC's grammar, in `Connector`, or in the
    DuckDB connector's config block -- the two blocks have ZERO key overlap, which is the
    demonstration §9.4 asks for.

    WHAT IS NOT A CONFIG KEY: the account id. It is derived at runtime via STS and never shipped
    (`sdk/authoring/connection.py:redacted` already treats it that way: "(derived at runtime via
    STS)"). A bundle that carries one has leaked a deployment identity into a published artifact,
    and `validate_config` reports it.
    """

    id: ClassVar[str] = "mac.connector.athena"

    #: `secretsmanager` and `ssm` are DECLARED and NOT WIRED. sdk/authoring/connection.py:45 raises
    #: NotImplementedError for both rather than silently falling back to the ambient chain, which
    #: would mis-target a different account. `credential_plan` below preserves that: exit 2 with the
    #: ref named, never a quiet degrade.
    # THE GRAMMAR'S CLOSED SET, not this connector's own spelling. These were `profile`,
    #: `secretsmanager` and `ssm` — one cloud's vocabulary — while mac_vocabulary.yaml declares the
    #: engine-neutral set. Two agents wrote the two halves in parallel and neither read the other, so
    #: a bundle that validated against the grammar was rejected by the connector as an "unknown
    #: credentials.mode". A closed vocabulary with two spellings is not closed.
    credential_modes: ClassVar[frozenset] = frozenset(
        {"ambient", "named_profile", "secret_manager", "interactive", "client_certificate", "none"}
    )

    permissions: ClassVar[frozenset] = frozenset({"read", "net"})

    #: BILLED. See the module docstring for the engine-specific reasoning; the base class carries
    #: only the engine-neutral definition (metered / rate-limited / recorded in an audit log).
    probe_cost: ClassVar[str] = "billed"

    supports: ClassVar[frozenset] = frozenset({
        "list_relations", "describe_relation", "profile_relation", "list_objects",
        "create_or_replace_view", "explain", "probe",
    })

    #: Matches the placeholder syntax mac_runtime/adapters/safety.py already adopted for this engine
    #: ("This module adopts named :param_name placeholders"). Declared here as the CONNECTOR's
    #: choice; MAC owns no placeholder syntax (§4.2a).
    param_style: ClassVar[str] = ":name"

    # ---- TIER 1 · DRY: pure, offline, free, and importable with no boto3 present ----

    @classmethod
    def config_schema(cls) -> Mapping[str, Any]:
        try:
            return json.loads(_SCHEMA_FILE.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ConnectorUnavailable(f"{cls.id}: shipped config schema unreadable: {exc}") from exc

    @classmethod
    def validate_config(cls, conn: Mapping) -> Sequence[ConfigProblem]:
        """Offline, free, no socket, no boto3. The cross-field rules JSON Schema cannot express.

        §6.3 names this exact case: "a rule it cannot express -- e.g. 'output is required unless the
        workgroup carries a managed output location' -- is NOT silently skipped at mount: it belongs
        to validate_config()". That rule is below, and it is stated as a WARNING-shaped finding
        rather than a hard one, because whether the workgroup manages its output is a fact only the
        account knows and asking costs an API call.
        """
        problems: list = []
        cfg = conn.get("config")
        if cfg is None:
            cfg = {}
        if not isinstance(cfg, Mapping):
            return [ConfigProblem(("config",), f"must be a mapping, got {type(cfg).__name__}")]

        for key in ("region", "workgroup"):
            if not cfg.get(key):
                problems.append(ConfigProblem(("config", key), "required"))

        if cfg.get("account"):
            # A shipped bundle carrying an account id has put a deployment identity into a published
            # artifact. It is derived at runtime via STS; there is no reason for it to be in a file.
            problems.append(ConfigProblem(
                ("config", "account"),
                "must not be shipped; the account is derived at runtime via STS",
            ))

        if not cfg.get("output"):
            problems.append(ConfigProblem(
                ("config", "output"),
                "absent: this is legal ONLY if the workgroup enforces a managed output location. "
                "Whether it does is a fact of the account, not of this file, and establishing it "
                "costs a billed API call -- so it is reported here rather than assumed either way",
                # ADVISORY: unprovable offline is not the same as wrong. Blocking on it stopped the
                # probe of a connection that was very likely fine, which is the opposite of what
                # "reported rather than assumed" means.
                severity="advisory",
            ))

        gdb = cfg.get("glue_databases")
        if gdb is not None and not isinstance(gdb, Mapping):
            problems.append(ConfigProblem(("config", "glue_databases"),
                                          "must be a mapping of role -> database name"))

        creds = conn.get("credentials") or {}
        mode = (creds.get("mode") or "ambient") if isinstance(creds, Mapping) else "ambient"
        if mode not in cls.credential_modes:
            problems.append(ConfigProblem(("credentials", "mode"),
                                          f"{mode!r} is not offered by {cls.id}"))
        if mode == "named_profile" and not (isinstance(creds, Mapping) and creds.get("ref")):
            problems.append(ConfigProblem(("credentials", "ref"),
                                          "mode=profile requires a ref (the profile name)"))
        return problems

    @classmethod
    def credential_plan(cls, conn: Mapping) -> CredentialPlan:
        """HOW this connection would authenticate. Never a value. Never a fetch. Never a socket.

        Preserves connection.py:45's behaviour EXACTLY for the two unwired modes: fail loud, with
        the ref named, as exit 2 (could not run) -- not exit 1, because a mechanism nobody has wired
        is not a defect in the bundle that declared it.
        """
        creds = conn.get("credentials") or {}
        if not isinstance(creds, Mapping):
            raise ConnectorConfigError(f"{cls.id}: credentials must be a mapping")
        mode = creds.get("mode") or "ambient"
        ref = creds.get("ref")
        if mode == "ambient":
            return CredentialPlan(mode="ambient", ref=None,
                                  detail="ambient chain: env / SSO profile / task role")
        if mode == "named_profile":
            if not ref:
                raise ConnectorConfigError(f"{cls.id}: mode=profile requires a ref")
            return CredentialPlan(mode="named_profile", ref=str(ref),
                                  detail="explicit named SSO/CLI profile")
        if mode in ("secret_manager"):
            raise ConnectorUnavailable(
                f"{cls.id}: credentials.mode={mode!r} (ref={ref!r}) resolver not wired -- set mode "
                f"profile/ambient, or wire the {mode} fetch-at-call-time before answering. Falling "
                f"back to the ambient chain here would mis-target a different account."
            )
        raise ConnectorConfigError(f"{cls.id}: unknown credentials.mode {mode!r}")

    def orderable(self, engine_type: str) -> bool:
        """This ENGINE's verdict on its own type names. See _ORDERABLE_PREFIXES."""
        return (engine_type or "").strip().lower().startswith(_ORDERABLE_PREFIXES)

    def approx_distinct_fn(self) -> str:
        return "approx_distinct"          # Trino/Presto spelling

    def cast_to_text(self, expr: str) -> str:
        return f"try_cast({expr} as varchar)"

    # ---- construction: NO boto3 import, NO client, NO socket ----

    def __init__(self, conn: Mapping | None = None, *, client: Any | None = None) -> None:
        """Holds config only.

        boto3's default credential chain reaches IMDS AT CLIENT CONSTRUCTION, so building a client
        here would make merely constructing a connector a network call with a timeout attached --
        on a laptop with no route to IMDS that is a multi-second hang inside what a caller believes
        is an assignment. mac_runtime.adapters.athena already holds this property and tests it
        (test_construction_is_network_free); conformance A3 re-asserts it with a socket guard.
        """
        super().__init__(conn, client=client)

    @property
    def _cfg(self) -> Mapping:
        cfg = self.conn.get("config") or {}
        if not isinstance(cfg, Mapping):
            raise ConnectorConfigError(f"{self.id}: config must be a mapping")
        return cfg

    def redacted_target(self) -> str:
        """What a host may PRINT. Region and workgroup are handles; the account never appears."""
        return f"athena workgroup={self._cfg.get('workgroup')} region={self._cfg.get('region')}"

    def _clients(self) -> tuple:
        """(athena, glue), built LAZILY on first I/O. The one place boto3 is imported. UNTESTED."""
        if self._client is not None:
            return self._client
        try:
            import boto3  # noqa: PLC0415 — lazy on purpose: see __init__ and record H9
        except Exception as exc:
            raise ConnectorUnavailable(
                f"{self.id}: boto3 is not importable ({exc}); "
                f"install it with: pip install 'meaning-as-code[athena]'"
            ) from exc
        plan = self.credential_plan(self.conn)
        region = self._cfg.get("region")
        if not region:
            raise ConnectorConfigError(f"{self.id}: config.region is required")
        try:
            session = (boto3.Session(profile_name=plan.ref) if plan.mode == "named_profile"
                       else boto3.Session())
            self._client = (session.client("athena", region_name=region),
                            session.client("glue", region_name=region))
        except Exception as exc:
            raise self._source_error(exc, "building a session") from exc
        return self._client

    @staticmethod
    def _source_error(exc: BaseException, what: str, *, request_id: str | None = None) -> SourceError:
        """botocore exception -> the closed reason vocabulary. By error-code STRING; see the table."""
        code = ""
        resp = getattr(exc, "response", None)
        if isinstance(resp, Mapping):
            code = str((resp.get("Error") or {}).get("Code") or "")
        reason = _ERROR_CODE_REASON.get(code) or _ERROR_CODE_REASON.get(type(exc).__name__)

        # TLS TRUST IS A LOCAL FACT, NOT A SOURCE FAILURE, and reporting it as "unreachable" sends
        # the reader to look at the warehouse when the problem is on their own machine. Measured on
        # one operator's laptop: 15 corporate root certificates in the macOS system keychain, and
        # Python verifying against certifi's public-CA bundle, which never consults that keychain —
        # so a TLS-intercepting corporate proxy presents a chain Python cannot verify. The endpoint
        # answered; the handshake did not complete.
        #
        # The remedy is one environment variable, so the message carries it rather than leaving a
        # raw `[SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate`.
        if "SSL" in type(exc).__name__ or "CERTIFICATE_VERIFY_FAILED" in str(exc):
            return SourceError(
                SourceErrorReason.UNREACHABLE,
                f"athena TLS trust failure while {what}: this machine's Python cannot verify the "
                f"endpoint's certificate chain. That is a LOCAL trust-store fact, not a fact about "
                f"the warehouse — the endpoint answered. If a TLS-intercepting proxy is in the path, "
                f"its root is in the OS keychain and Python does not read that store: build a bundle "
                f"(certifi's cacert.pem + `security find-certificate -a -p`) and set $AWS_CA_BUNDLE "
                f"to it. Underlying: {exc}",
                engine_request_id=request_id,
            )

        if reason is None:
            # Unknown => could-not-run, never a finding. An unrecognised failure means we do not
            # know that the source judged anything, and publishing that as exit 1 is the exact
            # damage tools/_plugin.py exists to prevent.
            reason = SourceErrorReason.UNREACHABLE
        return SourceError(reason, f"athena {code or type(exc).__name__} while {what}: {exc}",
                           engine_request_id=request_id)

    # ---- TIER 1 · WET · UNTESTED FROM HERE DOWN ----

    def _execute(
        self,
        body: str,
        params: Mapping[str, Any],
        *,
        limit: int | None = None,
        timeout_s: float | None = None,
    ) -> ReadResult:
        """start_query_execution -> poll -> get_query_results -> ReadResult. UNTESTED.

        The ~120-line re-implementation kill criterion 2 asks for. Dependency closure: boto3. That
        is the whole claim being made here, and it is the one part of this method a reader can
        verify without an account.

        Params travel as `ExecutionParameters`, which is Athena's own bound-parameter mechanism --
        the values are never formatted into the statement. Athena binds POSITIONALLY (`?`) while
        this connector declares `:name`, so the named placeholders are rewritten to `?` in a fixed
        order HERE, inside the connector that owns both conventions. MAC sees neither.
        """
        athena, _glue = self._clients()
        statement, ordered = self._positional(body, params)
        kwargs: dict = {"QueryString": statement,
                        "WorkGroup": self._cfg.get("workgroup")}
        output = self._cfg.get("output")
        if output:
            kwargs["ResultConfiguration"] = {"OutputLocation": output}
        catalog, database = self._cfg.get("catalog"), self._cfg.get("database")
        if catalog or database:
            ctx = {}
            if catalog:
                ctx["Catalog"] = catalog
            if database:
                ctx["Database"] = database
            kwargs["QueryExecutionContext"] = ctx
        if ordered:
            kwargs["ExecutionParameters"] = [str(v) for v in ordered]

        try:
            qid = athena.start_query_execution(**kwargs)["QueryExecutionId"]
        except Exception as exc:
            raise self._source_error(exc, "starting a query") from exc

        deadline = time.time() + (timeout_s if timeout_s else 300.0)
        delay = 0.2
        while True:
            try:
                st = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
            except Exception as exc:
                raise self._source_error(exc, "polling", request_id=qid) from exc
            state = st.get("State")
            if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
            if time.time() > deadline:
                # The query is still RUNNING and still accruing scan cost. Cancel it: a timeout that
                # abandons a running query bills for a result nobody will read.
                try:
                    athena.stop_query_execution(QueryExecutionId=qid)
                except Exception:  # noqa: BLE001 — a failed cancel must not mask the timeout
                    pass
                raise SourceError(SourceErrorReason.TIMEOUT,
                                  f"athena query exceeded {deadline}s and was cancelled",
                                  engine_request_id=qid)
            time.sleep(delay)
            # Backoff, capped: get_query_execution is itself a metered API call, and a tight poll
            # loop turns one query into hundreds of billed control-plane calls.
            delay = min(delay * 1.5, 2.0)

        if state != "SUCCEEDED":
            raise SourceError(_STATE_REASON.get(state, SourceErrorReason.REQUEST_FAILED),
                              f"athena {state}: {st.get('StateChangeReason', '')}",
                              engine_request_id=qid)

        columns: tuple = ()
        rows: list = []
        truncated = False
        token = None
        first_page = True
        try:
            while True:
                kw: dict = {"QueryExecutionId": qid}
                if token:
                    kw["NextToken"] = token
                page = athena.get_query_results(**kw)
                meta = ((page.get("ResultSet") or {}).get("ResultSetMetadata") or {})
                if not columns:
                    columns = tuple(c.get("Name") for c in (meta.get("ColumnInfo") or []))
                raw = (page.get("ResultSet") or {}).get("Rows") or []
                # THE HEADER STRIP: row 0 of page 0 ONLY. Dropping the first row of EVERY page loses
                # one real row per page after the first; dropping none reports the column names as a
                # data row, which type-checks as strings and lands in a profile as a value.
                if first_page and raw:
                    raw = raw[1:]
                    first_page = False
                for r in raw:
                    vals = [d.get("VarCharValue") for d in (r.get("Data") or [])]
                    rows.append(dict(zip(columns, vals)))
                    if limit is not None and len(rows) > limit:
                        rows = rows[:limit]
                        truncated = True
                        break
                if truncated:
                    break
                token = page.get("NextToken")
                if not token:
                    break
        except SourceError:
            raise
        except Exception as exc:
            raise self._source_error(exc, "fetching results", request_id=qid) from exc

        return ReadResult(columns=columns, rows=tuple(rows), row_count=len(rows),
                          truncated=truncated)

    def _positional(self, body: str, params: Mapping[str, Any]) -> tuple:
        """`:name` placeholders -> Athena's positional `?`, in first-appearance order. UNTESTED.

        Deliberately NOT a SQL parse: it replaces the exact placeholder tokens this connector's own
        `placeholder()` produces, in the order they appear. Its honest limit is the same one
        mac_runtime's regex has -- a `:name`-shaped substring inside a string literal would be
        rewritten -- and it is bounded here by only rewriting names the caller actually BOUND, so an
        arbitrary colon-word in a literal is untouched. A caller that needs a literal `:bound_name`
        inside a string in Athena has a genuine ambiguity, and it belongs to this engine, not to MAC.
        """
        ordered: list = []
        out = body
        if not params:
            return out, ordered
        for name in sorted(params, key=lambda n: (out.find(f":{n}") if f":{n}" in out else 1 << 30)):
            token = f":{name}"
            if token not in out:
                continue
            out = out.replace(token, "?")
            ordered.append(params[name])
        return out, ordered

    def list_relations(self, namespaces: Sequence[Sequence[str]]) -> Sequence[RelationRef]:
        """Op 2 via `glue.get_tables`, paginated. UNTESTED.

        This is harvest.py:152 `_tables()` with the pagination kept intact and the shape changed
        from `(db, raw_glue_dict)` to RelationRef -- so nothing above the connector learns the word
        Glue or the shape of its response.
        """
        _athena, glue = self._clients()
        out: list = []
        for ns in (namespaces or []):
            segs = tuple(ns or ())
            if not segs:
                raise ConnectorConfigError(
                    f"{self.id}: list_relations requires a database; this engine has no "
                    f"'enumerate everything' call that is safe to issue by default"
                )
            database = segs[-1]
            token = None
            while True:
                kw: dict = {"DatabaseName": database, "MaxResults": 100}
                if token:
                    kw["NextToken"] = token
                try:
                    resp = glue.get_tables(**kw)
                except Exception as exc:
                    raise self._source_error(exc, f"listing tables in {database!r}") from exc
                for t in resp.get("TableList", []):
                    out.append(RelationRef(namespace=segs, name=str(t.get("Name"))))
                token = resp.get("NextToken")
                if not token:
                    break
        return out

    def describe_relation(self, ref: RelationRef) -> RelationSchema:
        """Op 3 via `glue.get_table`, with VERBATIM Glue types. UNTESTED."""
        _athena, glue = self._clients()
        if not ref.namespace:
            raise ConnectorConfigError(f"{self.id}: describe_relation requires a database segment")
        try:
            tbl = glue.get_table(DatabaseName=ref.namespace[-1], Name=ref.name)["Table"]
        except Exception as exc:
            raise self._source_error(exc, f"describing {ref.name!r}") from exc
        sd = tbl.get("StorageDescriptor") or {}
        cols = list(sd.get("Columns") or [])
        # Partition keys are columns of the relation and are NOT in StorageDescriptor.Columns.
        # Omitting them describes a relation whose partition column "does not exist", and the first
        # thing a generated query does with it is filter on it.
        cols += list(tbl.get("PartitionKeys") or [])
        return RelationSchema(
            ref=ref,
            columns=tuple(ColumnSpec(name=str(c.get("Name")), type=str(c.get("Type") or ""),
                                     description=str(c.get("Comment") or ""))
                          for c in cols),
        )

    def list_objects(self, namespace: Sequence[str]) -> set:
        """Op 4, the collision snapshot, via SHOW TABLES. UNTESTED.

        Failure PROPAGATES. materialize._show_tables' `except Exception: return set()` reports "no
        collisions" when it could not look, inside the step whose guardrail exists because of the
        2026-08-13 overwrite of gold's dim_country / dim_model.
        """
        segs = tuple(namespace or ())
        if not segs:
            raise ConnectorConfigError(f"{self.id}: list_objects requires a namespace")
        res = self.read(ReadRequest(body=f"SHOW TABLES IN {self.quote_identifier(segs[-1])}",
                                    purpose="list_objects"))
        out: set = set()
        for r in res.rows:
            out |= {str(v) for v in r.values() if v}
        return out

    def explain(self, body: str, params: Mapping[str, Any] | None = None) -> None:
        """Op 10. UNTESTED. EXPLAIN is itself a billed call on this engine, however cheap."""
        self.read(ReadRequest(body=f"EXPLAIN {body}", params=dict(params or {}), purpose="explain"))

    def create_or_replace_view(self, ref: RelationRef, select_body: str) -> None:
        """Op 8, the ONLY write verb. UNTESTED, and off by default.

        DDL goes through `start_query_execution` directly and polls to a terminal state: DDL returns
        no result set, so nothing is fetched. That much is materialize.py:298's `_ddl()`, kept. What
        is NOT kept is its sibling `_run(sql)`, which dispatched on `is_read_only(sql)` -- a write
        capability decided by inspecting a string the caller passed, which nothing can gate and
        nothing can answer offline (§4.5).
        """
        if not self._cfg.get("allow_ddl", False):
            raise ConnectorConfigError(
                f"{self.id}: allow_ddl is not enabled. It defaults to false and lives only in the "
                f"deployment overlay, so a published, shipped bundle can never be used to write."
            )
        athena, _glue = self._clients()
        statement = self.render_view_ddl(ref, select_body)
        try:
            qid = athena.start_query_execution(
                QueryString=statement, WorkGroup=self._cfg.get("workgroup")
            )["QueryExecutionId"]
        except Exception as exc:
            raise self._source_error(exc, "starting DDL") from exc
        while True:
            st = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
            state = st.get("State")
            if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
            time.sleep(0.5)
        if state != "SUCCEEDED":
            raise SourceError(_STATE_REASON.get(state, SourceErrorReason.REQUEST_FAILED),
                              f"athena {state}: {st.get('StateChangeReason', '')}",
                              engine_request_id=qid)

    def probe(self) -> ProbeResult:
        """BILLED. CONTROL-PLANE ONLY: GetWorkGroup + GetDatabase. Never `SELECT 1`. UNTESTED.

        `SELECT 1` would write a result object to the workgroup's S3 output location and enter that
        workgroup's scan accounting -- it makes a liveness check into a data-plane write. These two
        calls are metered and appear in the account's audit trail, which is enough to make this
        connector's probe_cost "billed", and nothing invokes it without an explicit operator act.
        """
        athena, glue = self._clients()
        wg = self._cfg.get("workgroup")
        try:
            athena.get_work_group(WorkGroup=wg)
        except Exception as exc:
            return ProbeResult(ok=False, cost=self.probe_cost, target=self.redacted_target(),
                               detail=str(self._source_error(exc, f"reading workgroup {wg!r}")))
        dbs = list((self._cfg.get("glue_databases") or {}).values())
        for db in dbs:
            try:
                glue.get_database(Name=db)
            except Exception as exc:
                return ProbeResult(ok=False, cost=self.probe_cost, target=self.redacted_target(),
                                   detail=str(self._source_error(exc, f"reading database {db!r}")))
        return ProbeResult(ok=True, cost=self.probe_cost, target=self.redacted_target(),
                           detail=f"workgroup reachable; {len(dbs)} database(s) readable")


#: THE UNTESTED SURFACE, AS DATA. Every name here has never executed: no AWS call was made while
#: writing this module, deliberately, because every one of them is billed and Ruling 8 is open.
#:
#: It is a list rather than a paragraph so that it can only get SHORTER, and so a later gate can
#: assert that. A paragraph saying "this is untested" goes stale the day one method is exercised and
#: nobody edits the prose; a list is diffable and a count is quotable with its denominator.
UNTESTED: tuple = (
    "AthenaConnector._clients",
    "AthenaConnector._execute",
    "AthenaConnector._positional",
    "AthenaConnector.list_relations",
    "AthenaConnector.describe_relation",
    "AthenaConnector.list_objects",
    "AthenaConnector.explain",
    "AthenaConnector.create_or_replace_view",
    "AthenaConnector.probe",
    "AthenaConnector.profile_relation",   # inherited from SqlConnector; its render half IS tested
)

#: WHAT IS TESTED HERE TODAY, offline, free, with no boto3 client ever built: the whole DRY half.
#: `conformance.check_sql_dry_half` (assertion A9) EXECUTES this class's quote_identifier, qualify,
#: render_view_ddl, render_profile_sql, orderable, head_verb and assert_params_placed against a
#: synthetic relation, and `check_connector` executes config_schema, validate_config,
#: credential_plan (including both unwired modes and their exit-2 mapping) and the declaration
#: itself. That is the payoff of §4.2's dry/wet split stated as a measurement rather than a promise:
#: the half of a BILLED connector that can be proved for free, is.

__all__ = ["AthenaConnector", "UNTESTED"]
