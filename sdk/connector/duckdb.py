#!/usr/bin/env python3
"""duckdb.py — the DuckDB connector. REAL, and the one connector in this package that is TESTED.

RECORD: §3.2 (the falsifier), §7.5b (cost class), §9.4 (the contoso config shape).

WHY THIS ONE IS THE FALSIFIER. `mac-ontology-contoso` is a DuckDB bundle with no connection.yaml, no
credentials, no region, no workgroup and no catalog, and it validates today with
`ok=True, errors=[], warnings=[]`. The record's test: "if DuckDB cannot satisfy the interface without
an Athena word appearing in the base class, the interface is wrong." Nothing in base.py or sql.py
names a region, a workgroup, an output location or an account, and this class needs none of them.

AND WHY IT IS NOT SUFFICIENT, stated here so nobody quotes it as the acceptance test. DuckDB and
Athena are BOTH SQL engines with quoted identifiers, namespace qualification, CREATE OR REPLACE
VIEW, column types and EXPLAIN. Two SQL engines can detect an AWS assumption and are structurally
incapable of detecting a SQL assumption. The fixture that can is `fixtures/csv_dir.py`, and the
verdict that counts prints its unit: "3 connectors x N assertions, 1 non-SQL".

COST CLASS: FREE. A DuckDB probe is a local file open -- not metered, not rate-limited, and recorded
in no audit log an operator maintains. It MAY therefore run automatically on open. Treating every
engine as expensive would teach operators that the confirmation prompt is noise to click through,
which is how a real billing guard gets trained away (§7.5b).

THE DRIVER IMPORT IS LAZY, AND THE MEASUREMENT THAT FORCES IT: on this host the `duckdb` module is
NOT installed (`python3 -m pip show duckdb` -> "Package(s) not found"). A module-level
`import duckdb` would therefore make this file unimportable, which would make the DRY half -- config
validation, DDL rendering, profile rendering, all of it offline and free -- unreachable on the very
machine the gates run on. Record H9 seeds exactly that as a hostile class.

A NOTE ON THIS MODULE'S NAME. This file is `sdk/connector/duckdb.py` and it contains
`import duckdb`. Under Python 3's absolute imports that resolves to the top-level `duckdb`
distribution, never to this module; the shadowing hazard is a Python 2 memory. The name is kept
because `sdk.connector.duckdb` is what a reader looks for.
"""

from __future__ import annotations

import json
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
    AdapterError,
    AdapterErrorReason,
)
from sdk.connector.sql import SqlConnector

_SCHEMA_FILE = Path(__file__).resolve().parent / "schemas" / "duckdb.1.json"

#: DuckDB type-name prefixes over which MIN/MAX means something. MEASURED against the types this
#: connector actually reads back from a real bundle (BIGINT, VARCHAR, DOUBLE, DATE, TIMESTAMP,
#: DECIMAL(p,s), BOOLEAN) plus the rest of DuckDB's numeric/temporal family. It is a prefix match
#: because DECIMAL and TIMESTAMP carry parameters.
#:
#: This list lives HERE and not in the generic instrument. data_plane.py:48-58 holds eleven
#: Hive/Presto type names (`_ORDERABLE`) applied to every engine the SDK might reach; three of
#: DuckDB's most common types -- HUGEINT, UTINYINT, TIMESTAMP_NS -- are absent from it, so profiling
#: a DuckDB bundle through the generic list would silently drop min/max for those columns and report
#: a narrower profile as if it were complete.
_ORDERABLE_PREFIXES = (
    "tinyint", "smallint", "integer", "int", "bigint", "hugeint",
    "utinyint", "usmallint", "uinteger", "ubigint", "uhugeint",
    "decimal", "numeric", "double", "float", "real",
    "date", "time", "timestamp", "interval",
)

#: duckdb exception CLASS NAME -> the reason. Keyed by name, not by class, so the taxonomy can be
#: read with the driver absent -- which is the state of this host.
_REASON_BY_EXC_NAME: Mapping[str, AdapterErrorReason] = {
    "CatalogException": AdapterErrorReason.QUERY_FAILED,     # relation/column not found
    "BinderException": AdapterErrorReason.QUERY_FAILED,
    "ParserException": AdapterErrorReason.QUERY_FAILED,
    "ConversionException": AdapterErrorReason.QUERY_FAILED,
    "InvalidInputException": AdapterErrorReason.QUERY_FAILED,
    "ConstraintException": AdapterErrorReason.QUERY_FAILED,
    "OutOfMemoryException": AdapterErrorReason.EXECUTION_LIMIT,
    "InterruptException": AdapterErrorReason.QUERY_CANCELLED,
    "IOException": AdapterErrorReason.UNREACHABLE,             # the file moved / permissions
    "PermissionException": AdapterErrorReason.UNAUTHORIZED,
}


class DuckDbConnector(SqlConnector):
    """DuckDB over a local database file. No credentials, no network, no account.

    `config` is `{database: <bundle-relative path>, read_only: bool}` -- §9.4's contoso shape, and a
    block with ZERO key overlap with the Athena connector's, which is the point being demonstrated.
    """

    id: ClassVar[str] = "mac.connector.duckdb"

    #: "none" is a real mode, not an absence: a local file needs no credential, and the schema's
    #: `credentials` block is legally absent for this connector (§5.4: "absent is legal and means
    #: 'no credential required'").
    credential_modes: ClassVar[frozenset] = frozenset({"none"})

    #: `fs` because it opens a local file; `net` is deliberately absent. A connector that declares
    #: {read, fs} and opens a socket is lying, and that is the lie this field makes attributable.
    permissions: ClassVar[frozenset] = frozenset({"read", "fs"})

    probe_cost: ClassVar[str] = "free"

    supports: ClassVar[frozenset] = frozenset({
        "list_relations", "describe_relation", "profile_relation", "list_objects",
        "create_or_replace_view", "explain", "probe",
    })

    #: MEASURED against duckdb 1.5.5: a dict of parameters binds with `$name` placeholders.
    param_style: ClassVar[str] = "$name"

    #: DuckDB's read verbs, and two of them are NOT in the generic default: `from` (DuckDB accepts a
    #: FROM-first statement, `FROM t SELECT x`, as a complete query) and `pragma`/`summarize`.
    #: Inheriting the generic list would have made a legal DuckDB read raise
    #: ConnectorContractViolation -- exit 1, a finding about the bundle -- for using its own engine's
    #: syntax. This is the concrete form of "MAC owns what is asked; the connector owns how".
    read_verbs: ClassVar[tuple] = (
        "select", "with", "from", "show", "describe", "desc", "explain",
        "pragma", "summarize", "values", "table", "call",
    )

    # ---- TIER 1 · DRY ----

    @classmethod
    def config_schema(cls) -> Mapping[str, Any]:
        """The shipped JSON Schema, loaded from the file §6.3's mount tier validates against.

        One authority: the mount tier reads the FILE with zero imports, this classmethod reads the
        same file. A schema written twice is a schema that disagrees with itself by the second
        release.
        """
        try:
            return json.loads(_SCHEMA_FILE.read_text(encoding="utf-8"))
        except OSError as exc:
            # A missing shipped schema is not a bundle finding -- it is a broken installation.
            raise ConnectorUnavailable(f"{cls.id}: shipped config schema unreadable: {exc}") from exc

    @classmethod
    def validate_config(cls, conn: Mapping) -> Sequence[ConfigProblem]:
        """Offline, free, no socket, no driver. Returns findings; never raises for a bad config."""
        problems: list = []
        cfg = conn.get("config")
        if cfg is None:
            cfg = {}
        if not isinstance(cfg, Mapping):
            return [ConfigProblem(("config",), f"must be a mapping, got {type(cfg).__name__}")]

        db = cfg.get("database")
        if not db or not isinstance(db, str):
            problems.append(ConfigProblem(("config", "database"),
                                          "required: the path to the DuckDB database file"))
        elif Path(db).is_absolute():
            # A SHIPPED bundle carrying an absolute path has pinned one machine's filesystem into a
            # published artifact. The legal home for a machine-specific path is the out-of-band
            # deployment overlay (connection.local.yaml / $DEPLOYMENT_CONFIG), which is gitignored
            # for exactly this reason -- sdk/authoring/connection.py's discovery order.
            #
            # THE LIMIT: this classmethod sees the MERGED config and cannot tell which layer a key
            # arrived from, so a host validating a merged overlay should read this finding as
            # advisory. It is reported rather than dropped because a bundle is published far more
            # often than an overlay is merged, and the silent case is the damaging one.
            problems.append(ConfigProblem(
                ("config", "database"),
                f"{db!r} is an absolute path; a shipped bundle declares a bundle-relative path and "
                f"leaves the absolute one to the deployment overlay",
            ))

        ro = cfg.get("read_only", True)
        if not isinstance(ro, bool):
            problems.append(ConfigProblem(("config", "read_only"),
                                          f"must be a boolean, got {type(ro).__name__}"))

        creds = conn.get("credentials") or {}
        mode = (creds.get("mode") or "none") if isinstance(creds, Mapping) else "none"
        if mode not in cls.credential_modes:
            problems.append(ConfigProblem(
                ("credentials", "mode"),
                f"{mode!r} is not offered by {cls.id}; this connector reads a local file and its "
                f"only mode is 'none'",
            ))
        return problems

    @classmethod
    def credential_plan(cls, conn: Mapping) -> CredentialPlan:
        """No credential. `wired=True` because "none" is a mechanism that works, not one that is
        missing -- the distinction that separates exit 0 from exit 2."""
        return CredentialPlan(mode="none", ref=None,
                              detail="local file; no credential is resolved or required")

    def orderable(self, engine_type: str) -> bool:
        """The CONNECTOR's verdict on its OWN verbatim type names. See _ORDERABLE_PREFIXES."""
        t = (engine_type or "").strip().lower()
        return t.startswith(_ORDERABLE_PREFIXES)

    def approx_distinct_fn(self) -> str:
        # MEASURED: DuckDB spells it `approx_count_distinct`; Trino/Athena spell it
        # `approx_distinct`. This one function name is the entire dialect difference between the two
        # engines' profile statements, which is why the renderer is shared and this is a hook.
        return "approx_count_distinct"

    def cast_to_text(self, expr: str) -> str:
        return f"TRY_CAST({expr} AS VARCHAR)"

    # ---- construction: no driver import, no file open ----

    def __init__(
        self,
        conn: Mapping | None = None,
        *,
        client: Any | None = None,
        base_dir: Any | None = None,
    ) -> None:
        """Holds config only. Opens nothing.

        `base_dir` is the BUNDLE ROOT, supplied by the host at construction. It is a parameter and
        not a config key because an absolute path is a deployment fact: MAC is a public repository
        and carries no estate path, and a bundle that shipped one would carry one machine's
        filesystem into every checkout of it.
        """
        super().__init__(conn, client=client)
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()

    @property
    def database_path(self) -> Path:
        """The resolved database file. Relative paths resolve against the bundle root."""
        cfg = self.conn.get("config") or {}
        db = cfg.get("database")
        if not db:
            raise ConnectorConfigError(f"{self.id}: config.database is required")
        p = Path(db)
        return p if p.is_absolute() else (self.base_dir / p)

    @property
    def read_only(self) -> bool:
        cfg = self.conn.get("config") or {}
        return bool(cfg.get("read_only", True))

    def redacted_target(self) -> str:
        """What a host may PRINT about where this connects. A file name, never a full path.

        The directory is a deployment fact (a home directory, a mount point, a customer name in a
        path segment); the basename is the thing an operator needs in order to recognise which
        database answered.
        """
        try:
            return self.database_path.name
        except ConnectorConfigError:
            return "(no database declared)"

    def _connection(self):
        """The driver connection, opened LAZILY and cached. The one place `duckdb` is imported."""
        if self._client is not None:
            return self._client
        try:
            import duckdb  # noqa: PLC0415 — lazy on purpose; see the module docstring (H9)
        except Exception as exc:
            # ANY import failure, not just ImportError: a driver that raises at import must not take
            # the host down with it, and this is exit 2 (could not run), never exit 1.
            raise ConnectorUnavailable(
                f"{self.id}: the duckdb driver is not importable ({exc}); "
                f"install it with: pip install 'meaning-as-code[duckdb]'"
            ) from exc

        path = self.database_path
        if self.read_only and not path.exists():
            # Offline, free, and knowable: a finding ABOUT THE BUNDLE -> exit 1. Reporting it as
            # could-not-run would hide a broken bundle behind an infrastructure excuse.
            raise ConnectorConfigError(
                f"{self.id}: config.database {path.name!r} does not exist under the bundle root"
            )
        try:
            self._client = duckdb.connect(str(path), read_only=self.read_only)
        except Exception as exc:
            raise self._adapter_error(exc, f"opening {path.name!r}") from exc
        return self._client

    @staticmethod
    def _adapter_error(exc: BaseException, what: str) -> AdapterError:
        """Map a driver exception to the closed reason vocabulary, by CLASS NAME.

        By name because the taxonomy must be readable with the driver absent (this host), and
        because duckdb's exception classes are not a stable public import surface across versions.
        An unrecognised exception becomes QUERY_FAILED only when the driver itself raised it;
        anything else keeps exit 2 through the caller's own handling.
        """
        name = type(exc).__name__
        reason = _REASON_BY_EXC_NAME.get(name, AdapterErrorReason.QUERY_FAILED)
        return AdapterError(reason, f"duckdb {name} while {what}: {exc}")

    # ---- TIER 1 · WET ----

    def _execute(
        self,
        body: str,
        params: Mapping[str, Any],
        *,
        limit: int | None = None,
        timeout_s: float | None = None,
    ) -> ReadResult:
        """One read-only statement with BOUND params -> ReadResult.

        `timeout_s` is accepted and NOT honoured: DuckDB runs in-process and has no per-statement
        server-side timeout to set. Saying so here is deliberate -- silently accepting a timeout
        argument and ignoring it is how a caller comes to believe it has a guarantee it does not
        have. A caller that needs one must interrupt the connection itself.
        """
        con = self._connection()
        try:
            cur = con.execute(body, dict(params)) if params else con.execute(body)
            desc = cur.description or []
            columns = tuple(d[0] for d in desc)
            # Fetch one MORE than the limit, so "there were exactly `limit` rows" and "we stopped at
            # `limit`" are distinguishable. A truncated flag derived from `len(rows) == limit` is
            # wrong exactly half the time it matters.
            if limit is not None:
                raw = cur.fetchmany(limit + 1)
                truncated = len(raw) > limit
                raw = raw[:limit]
            else:
                raw = cur.fetchall()
                truncated = False
        except Exception as exc:
            raise self._adapter_error(exc, "executing a read") from exc
        rows = tuple(dict(zip(columns, r)) for r in raw)
        return ReadResult(columns=columns, rows=rows, row_count=len(rows), truncated=truncated)

    # ---- OPTIONAL verbs ----

    def _namespace_predicate(self, namespace: Sequence[str]) -> tuple:
        """Segment list -> (predicate text, params). 0, 1 or 2 segments, engine-neutrally supplied.

        DuckDB addresses a relation as catalog.schema.name, so a two-segment namespace is
        (catalog, schema), a one-segment namespace is (schema) in the current catalog, and an empty
        namespace is everything. §5.5's "a single-namespace engine like DuckDB uses one" is true of
        the common case and not of all of them -- an ATTACHed second database gives contoso two --
        so all three lengths are supported rather than one being assumed.
        """
        segs = tuple(namespace or ())
        if len(segs) >= 2:
            return ("table_catalog = $cat AND table_schema = $sch",
                    {"cat": segs[-2], "sch": segs[-1]})
        if len(segs) == 1:
            return ("table_schema = $sch", {"sch": segs[0]})
        return ("table_schema NOT IN ('information_schema', 'pg_catalog')", {})

    def list_relations(self, namespaces: Sequence[Sequence[str]]) -> Sequence[RelationRef]:
        """Op 2. information_schema, one read per namespace."""
        out: list = []
        for ns in (namespaces or [()]):
            pred, params = self._namespace_predicate(ns)
            body = (
                "SELECT table_catalog, table_schema, table_name FROM information_schema.tables "
                f"WHERE {pred} ORDER BY table_catalog, table_schema, table_name"
            )
            res = self.read(ReadRequest(body=body, params=params, purpose="list_relations"))
            for r in res.rows:
                out.append(RelationRef(
                    namespace=(str(r["table_catalog"]), str(r["table_schema"])),
                    name=str(r["table_name"]),
                ))
        return out

    def describe_relation(self, ref: RelationRef) -> RelationSchema:
        """Op 3. Columns and their VERBATIM DuckDB type strings -- never parsed by MAC."""
        segs = ref.namespace
        pred, params = self._namespace_predicate(segs)
        params = {**params, "tbl": ref.name}
        body = (
            "SELECT column_name, data_type FROM information_schema.columns "
            f"WHERE {pred} AND table_name = $tbl ORDER BY ordinal_position"
        )
        res = self.read(ReadRequest(body=body, params=params, purpose="describe_relation"))
        if not res.rows:
            # An empty column list is not an empty relation: it means the relation was not found.
            # Returning RelationSchema(columns=()) would let a caller profile nothing and report it
            # as a clean result -- the zero-denominator defect, one layer down.
            raise AdapterError(
                AdapterErrorReason.QUERY_FAILED,
                f"{self.id}: no such relation {'.'.join(ref.segments)}",
            )
        return RelationSchema(
            ref=ref,
            columns=tuple(ColumnSpec(name=str(r["column_name"]), type=str(r["data_type"]))
                          for r in res.rows),
        )

    def list_objects(self, namespace: Sequence[str]) -> set:
        """Op 4, the collision snapshot. Raises rather than returning an empty set on failure.

        materialize._show_tables' `except Exception: return set()` returns "no collisions" when it
        could not look, inside the very step whose guardrail exists because of a real overwrite.
        Here a failure propagates as AdapterError and the host prints that it did not check.
        """
        pred, params = self._namespace_predicate(namespace)
        body = f"SELECT table_name FROM information_schema.tables WHERE {pred}"
        res = self.read(ReadRequest(body=body, params=params, purpose="list_objects"))
        return {str(r["table_name"]) for r in res.rows}

    def explain(self, body: str, params: Mapping[str, Any] | None = None) -> None:
        """Op 10. Raises AdapterError on an invalid plan; returns nothing and mutates nothing."""
        self.read(ReadRequest(body=f"EXPLAIN {body}", params=dict(params or {}),
                              purpose="explain"))

    def create_or_replace_view(self, ref: RelationRef, select_body: str) -> None:
        """Op 8, the ONLY write verb. Refuses on a read-only connection.

        The refusal is ConnectorConfigError (exit 1, a finding about the bundle) and not a capability
        miss: the connector CAN write, and this configuration said not to. Calling that "capability
        missing" would report a deliberate safety setting as a broken connector.
        """
        if self.read_only:
            raise ConnectorConfigError(
                f"{self.id}: config.read_only is true; refusing to create "
                f"{'.'.join(ref.segments)}. A shipped bundle is read-only by default and DDL is "
                f"enabled only in the deployment overlay."
            )
        con = self._connection()
        try:
            con.execute(self.render_view_ddl(ref, select_body))
        except Exception as exc:
            raise self._adapter_error(exc, f"creating view {ref.name!r}") from exc

    def probe(self) -> ProbeResult:
        """FREE: open the local file and read one catalog row. No metering, no audit log, no socket.

        Still not automatic. §7.5d gives `open_container()` no code path to any `probe()`, whatever
        its cost class; "free" decides whether an operator command needs a billing confirmation, not
        whether the call happens behind their back.
        """
        try:
            res = self.read(ReadRequest(
                body="SELECT count(*) AS n FROM information_schema.tables",
                purpose="probe",
            ))
        except (AdapterError, ConnectorConfigError, ConnectorUnavailable) as exc:
            return ProbeResult(ok=False, cost=self.probe_cost, target=self.redacted_target(),
                               detail=str(exc))
        n = res.rows[0]["n"] if res.rows else 0
        return ProbeResult(ok=True, cost=self.probe_cost, target=self.redacted_target(),
                           detail=f"opened read_only={self.read_only}; {n} relation(s) in catalog")


__all__ = ["DuckDbConnector"]
