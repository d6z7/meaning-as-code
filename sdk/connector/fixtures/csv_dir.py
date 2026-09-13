#!/usr/bin/env python3
"""csv_dir.py — THE FALSIFIER. A connector over a directory of CSV files, with no SQL anywhere.

RECORD: §3.2 ("the honest limit of that falsifier"), §10.3 fixture C2, §11.3 kill criterion 1.

WHAT THIS FIXTURE IS FOR, in one sentence: it is the only connector in this package that can prove
the interface is not SQL-shaped, because it is the only one that is not a SQL engine.

    "Athena and DuckDB are BOTH SQL engines with quoted identifiers, catalog/schema qualification,
     CREATE OR REPLACE VIEW, column types and EXPLAIN. Two SQL engines can detect an AWS assumption
     and are structurally incapable of detecting a SQL assumption. The first draft's kill criterion
     1 was written in the narrow unit -- it fires on Optional[workgroup] and would sail straight
     past read(sql: str)."                                                            -- §3.2

THE CLAIM THIS FILE MAKES, and `conformance.py` K1 checks every clause of it mechanically:

  1. it subclasses `Connector` and NOT `SqlConnector`;
  2. it implements NO verb that lives on `SqlConnector` -- no `quote_identifier`, no
     `render_view_ddl`, no `render_profile_sql`, no `orderable`, no `explain`, no
     `create_or_replace_view`, no `param_style`, no `read_verbs`;
  3. its `ReadRequest.body` is a `CsvScan` DATACLASS, not a string. Nothing in `base.py` inspects it,
     which is the operative meaning of "MAC owns what is asked, the connector owns how";
  4. it declares NO credential mechanism (`mode: none`) and opens no socket;
  5. it conforms.

IT ALSO CARRIES THE OPTIONAL-ABSENT CASE (§10.3 fixture C1, "the one class that must NOT be
rejected"): `profile_relation` and `probe` are deliberately NOT implemented and NOT declared in
`supports`. Calling one must produce `ConnectorCapabilityMissing` -> exit 2 with the degradation
PRINTED, and the conformance run must still PASS. A suite that rejected this fixture would be
rejecting the majority case: 19 of the estate's 24 manifests declare no connection at all.

NOTE WHAT IS ABSENT AND CAUSES NO TROUBLE: there is no placeholder syntax here at all. A filter
names a COLUMN and a PARAM NAME, and the value is looked up in `request.params` at read time. That
is what "MAC owns no placeholder convention" means when the source has no statement text to put one
in -- and it is why `assert_bound_params_only`, which scans statement text for `:name`, could never
have been the generic precondition.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Mapping, Sequence

from sdk.connector.base import (
    ColumnSpec,
    ConfigProblem,
    Connector,
    ConnectorConfigError,
    ConnectorContractViolation,
    CredentialPlan,
    ReadRequest,
    ReadResult,
    RelationRef,
    RelationSchema,
    AdapterError,
    AdapterErrorReason,
)


@dataclass(frozen=True)
class CsvScan:
    """A read request for this source. NOT A STRING, and that is the entire point.

    `filters` binds a COLUMN to a PARAM NAME; the value is read from `ReadRequest.params` inside
    `read()`. So a user-derived value never appears in the request body in any form, and the source
    needs no placeholder convention for MAC to stay out of -- there is no text to place one in.
    """

    ref: RelationRef = field(default_factory=lambda: RelationRef(name="_"))
    columns: tuple = ()                  # () means every column
    filters: tuple = ()                  # ((column_name, param_name), ...) — equality only
    limit: int | None = None


class CsvDirectoryConnector(Connector):
    """A directory of CSV files. One file is one relation; a subdirectory is one namespace segment.

    `config` is `{directory, delimiter, encoding}` -- zero key overlap with the DuckDB connector's
    block and zero with Athena's, over three connectors that share one envelope.
    """

    id: ClassVar[str] = "fixture.connector.csvdir"

    #: Not a `mac.*` id, and `registry.resolve()` refuses to let it claim one. A fixture that could
    #: impersonate a first-party connector could make a conformance run pass for the wrong class.

    credential_modes: ClassVar[frozenset] = frozenset({"none"})
    permissions: ClassVar[frozenset] = frozenset({"read", "fs"})
    probe_cost: ClassVar[str] = "free"

    #: DELIBERATELY OMITS `profile_relation` AND `probe`. See the module docstring: this fixture is
    #: also the must-pass optional-absent case, and a suite that rejects it is rejecting the
    #: majority state of the estate.
    supports: ClassVar[frozenset] = frozenset({
        "list_relations", "describe_relation", "list_objects",
    })

    # ---- TIER 1 · DRY ----

    @classmethod
    def config_schema(cls) -> Mapping[str, Any]:
        """Inline rather than shipped: a fixture is not in `index.json`, so no mount tier ever
        reaches for a file on its behalf."""
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["directory"],
            "properties": {
                "directory": {"type": "string", "minLength": 1},
                "delimiter": {"type": "string", "minLength": 1, "maxLength": 1, "default": ","},
                "encoding": {"type": "string", "default": "utf-8"},
            },
        }

    @classmethod
    def validate_config(cls, conn: Mapping) -> Sequence[ConfigProblem]:
        problems: list = []
        cfg = conn.get("config") or {}
        if not isinstance(cfg, Mapping):
            return [ConfigProblem(("config",), f"must be a mapping, got {type(cfg).__name__}")]
        if not cfg.get("directory"):
            problems.append(ConfigProblem(("config", "directory"), "required"))
        delim = cfg.get("delimiter", ",")
        if not isinstance(delim, str) or len(delim) != 1:
            problems.append(ConfigProblem(("config", "delimiter"),
                                          "must be a single character"))
        creds = conn.get("credentials") or {}
        mode = (creds.get("mode") or "none") if isinstance(creds, Mapping) else "none"
        if mode not in cls.credential_modes:
            problems.append(ConfigProblem(("credentials", "mode"),
                                          f"{mode!r} is not offered by {cls.id}"))
        return problems

    @classmethod
    def credential_plan(cls, conn: Mapping) -> CredentialPlan:
        return CredentialPlan(mode="none", ref=None, detail="local files; no credential")

    def qualify(self, ref: RelationRef) -> str:
        """Segments -> an address in THIS source's terms: a relative file path.

        There is no quoting here and nothing to escape, which is exactly why `quote_identifier` had
        to leave the generic tier. A source that addresses by path has no identifier grammar, and
        under the first draft's contract it would have had to implement one in order to conform.
        """
        return str(Path(*ref.namespace) / f"{ref.name}.csv") if ref.namespace else f"{ref.name}.csv"

    # ---- construction ----

    def __init__(
        self,
        conn: Mapping | None = None,
        *,
        client: Any | None = None,
        base_dir: Any | None = None,
    ) -> None:
        super().__init__(conn, client=client)
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()

    @property
    def root(self) -> Path:
        cfg = self.conn.get("config") or {}
        d = cfg.get("directory")
        if not d:
            raise ConnectorConfigError(f"{self.id}: config.directory is required")
        p = Path(d)
        return p if p.is_absolute() else (self.base_dir / p)

    @property
    def _delimiter(self) -> str:
        return (self.conn.get("config") or {}).get("delimiter", ",")

    @property
    def _encoding(self) -> str:
        return (self.conn.get("config") or {}).get("encoding", "utf-8")

    def _path(self, ref: RelationRef) -> Path:
        p = (self.root / self.qualify(ref)).resolve()
        root = self.root.resolve()
        # A relation name is not a path. `..` in a segment would otherwise read any file on the host
        # through a source that declares `permissions={read, fs}` and means the directory it names.
        if root not in p.parents and p != root:
            raise ConnectorContractViolation(
                f"{self.id}: {'.'.join(ref.segments)} resolves outside the declared directory"
            )
        return p

    # ---- TIER 1 · WET: the ONE required verb ----

    def read(self, request: ReadRequest) -> ReadResult:
        """One read. The body is a `CsvScan`; the values come from `request.params`.

        NO STATEMENT IS PARSED because there is no statement. The read-only guarantee here is
        structural rather than checked: `CsvScan` can express a projection, an equality filter and a
        limit, and there is no shape it can take that writes anything. A contract that had required
        a read-verb check would have forced this connector to invent a verb vocabulary in order to
        have one to check.
        """
        scan = request.body
        if not isinstance(scan, CsvScan):
            raise ConnectorContractViolation(
                f"{self.id}: request body must be a CsvScan, got {type(scan).__name__}"
            )
        path = self._path(scan.ref)
        if not path.is_file():
            raise AdapterError(AdapterErrorReason.QUERY_FAILED,
                              f"{self.id}: no such relation {'.'.join(scan.ref.segments)}")

        wanted: list = []
        for column, param_name in scan.filters:
            if param_name not in request.params:
                # The filter names a parameter nobody bound. Exit 1, loudly: the alternative is to
                # treat "absent" as "matches everything", which silently widens a filtered read into
                # a full scan and reports the result as if it had been filtered.
                raise ConnectorContractViolation(
                    f"{self.id}: filter on {column!r} names param {param_name!r}, which was not bound"
                )
            wanted.append((column, str(request.params[param_name])))

        limit = scan.limit if scan.limit is not None else request.limit
        rows: list = []
        truncated = False
        try:
            with path.open(newline="", encoding=self._encoding) as fh:
                reader = csv.DictReader(fh, delimiter=self._delimiter)
                header = tuple(reader.fieldnames or ())
                columns = tuple(scan.columns) if scan.columns else header
                missing = [c for c in columns if c not in header]
                if missing:
                    raise AdapterError(AdapterErrorReason.QUERY_FAILED,
                                      f"{self.id}: no such column(s) {missing} in "
                                      f"{'.'.join(scan.ref.segments)}")
                for rec in reader:
                    if any(rec.get(c) != v for c, v in wanted):
                        continue
                    if limit is not None and len(rows) >= limit:
                        # Stop having SEEN one more matching row, so `truncated` is a fact and not a
                        # guess from `len(rows) == limit`.
                        truncated = True
                        break
                    rows.append({c: rec.get(c) for c in columns})
        except OSError as exc:
            raise AdapterError(AdapterErrorReason.UNREACHABLE,
                              f"{self.id}: reading {path.name!r}: {exc}") from exc
        return ReadResult(columns=columns, rows=tuple(rows), row_count=len(rows),
                          truncated=truncated)

    # ---- OPTIONAL verbs this fixture DOES implement ----

    def list_relations(self, namespaces: Sequence[Sequence[str]]) -> Sequence[RelationRef]:
        out: list = []
        for ns in (namespaces or [()]):
            segs = tuple(str(s) for s in (ns or ()))
            directory = self.root / Path(*segs) if segs else self.root
            if not directory.is_dir():
                continue
            for f in sorted(directory.glob("*.csv")):
                out.append(RelationRef(namespace=segs, name=f.stem))
        return out

    def describe_relation(self, ref: RelationRef) -> RelationSchema:
        """Columns from the header row. Every type is the string "text".

        A CSV HAS NO TYPES, and this connector says so rather than guessing. It is safe to say
        because nothing above the connector parses a type name: `orderable()` is a `SqlConnector`
        verb and this class does not have one. Under the first draft's contract -- where MAC held
        eleven Hive/Presto type names and decided orderability itself -- "text" would have silently
        disabled min/max for every column of every CSV relation, and the profile would have looked
        complete.
        """
        path = self._path(ref)
        if not path.is_file():
            raise AdapterError(AdapterErrorReason.QUERY_FAILED,
                              f"{self.id}: no such relation {'.'.join(ref.segments)}")
        with path.open(newline="", encoding=self._encoding) as fh:
            header = next(csv.reader(fh, delimiter=self._delimiter), [])
        return RelationSchema(ref=ref,
                              columns=tuple(ColumnSpec(name=str(h), type="text") for h in header))

    def list_objects(self, namespace: Sequence[str]) -> set:
        segs = tuple(str(s) for s in (namespace or ()))
        directory = self.root / Path(*segs) if segs else self.root
        if not directory.is_dir():
            raise AdapterError(AdapterErrorReason.QUERY_FAILED,
                              f"{self.id}: no such namespace {'/'.join(segs) or '<root>'}")
        return {f.stem for f in directory.glob("*.csv")}

    # `profile_relation` and `probe` are NOT implemented and NOT declared. Inherited from Connector,
    # they raise ConnectorCapabilityMissing -> exit 2, with the degradation PRINTED by the host.
    # This is the must-pass case, not a gap to be filled in later.


__all__ = ["CsvDirectoryConnector", "CsvScan"]
