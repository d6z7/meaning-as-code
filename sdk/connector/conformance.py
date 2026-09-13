#!/usr/bin/env python3
"""conformance.py — does a connector satisfy the contract, and is the contract still generic?

RECORD: §3.2 (the falsifier and its honest limit), §4.3, §4.4, §10.3 (G3's fixture table).

WHAT THIS IS NOT. It is NOT G3 (`sdk/gate/check_connector_contract.py`). G3 is TRACK B, gated on
Rulings 12 and 14, and it runs THIRTEEN hostile classes -- including four that need a subprocess
(exits at import, hangs at import, ghost distribution, driver at import) and one, registry cache
poisoning, that is a property of `resolve()` rather than of any connector. None of that is here:
this instrument runs IN PROCESS, discovers nothing, imports no driver, opens no socket and costs
nothing. It is the acceptance test for the CLASSES, and it is the thing that has to exist before G3
has anything to be hostile towards.

WHY IT IS GATE-SHAPED ANYWAY: one PASS/FAIL line, exit 0/1 with 2 reserved for could-not-run, a
PRINTED DENOMINATOR, and `--self-test` seeding a mutant per reject class. A rule worth stating is
worth a gate; a rule stated in a docstring is a rule nobody has run.

THE TWO ASSERTIONS THAT ACTUALLY DECIDE SOMETHING are K1 and K2, and both exist because the first
draft's kill criterion could not fire:

  K1  The NON-SQL fixture conforms to `Connector` without implementing one `SqlConnector` verb.
      Two SQL engines cannot detect a SQL assumption (§3.2). If K1 fails, the interface is a rename
      of the hole and the correct response is to stop, not to patch the fixture.
  K2  `base.py` contains no identifier named `sql`, `statement`, `query`, `ddl` or `view`. This is
      the record's own criterion -- "if `Connector` grows a parameter named `sql`, the interface is
      a rename of the hole" -- made mechanical by putting `SqlConnector` in a different file.

THE VERDICT PRINTS ITS UNIT, and the unit names the non-SQL count, because a conformance line that
says "3 connectors, 0 violations" while all three are SQL engines is a PASS whose denominator hides
the only thing it was asked to establish.
"""

from __future__ import annotations

import argparse
import ast
import io
import sys
import tempfile
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from sdk.connector.base import (
    EXIT_COULD_NOT_RUN,
    EXIT_FINDING,
    EXIT_OK,
    ColumnSpec as ColumnSpecT,
    ConfigProblem,
    Connector,
    ConnectorCapabilityMissing,
    ConnectorContractViolation,
    CredentialPlan,
    PERMISSIONS,
    PROBE_COSTS,
    RelationRef,
    AdapterError,
    AdapterErrorReason,
    exit_code_for,
    worst_exit,
)
from sdk.connector.sql import SqlConnector

_HERE = Path(__file__).resolve().parent

#: Identifiers `base.py` may not contain. The record's kill criterion, as a name set.
#: Only IDENTIFIERS are walked -- argument names, attribute names, def/class names, assignment
#: targets. Prose in a docstring is free to say "SQL", and must be: the file has to be able to
#: EXPLAIN what it is keeping out.
FORBIDDEN_IN_BASE = ("sql", "statement", "query", "ddl", "view", "dialect")

#: Modules whose presence at a module's TOP LEVEL makes that module unimportable on a host without
#: the driver. Measured on this host: `duckdb` is NOT installed and `boto3` IS -- which is why a
#: top-level driver import is caught by an AST walk and not by "did the import work here".
DRIVER_MODULES = ("duckdb", "boto3", "botocore", "pyathena", "snowflake", "psycopg2", "pyodbc")

#: The verbs that belong to the statement-language tier. A connector claiming to be non-SQL may not
#: define any of them.
SQL_TIER_NAMES = (
    "quote_identifier", "render_view_ddl", "render_profile_sql", "orderable",
    "explain", "create_or_replace_view", "param_style", "read_verbs", "head_verb",
    "assert_params_placed", "placeholder", "approx_distinct_fn", "cast_to_text",
)


@dataclass(frozen=True)
class Finding:
    subject: str
    reject_class: str
    message: str

    def __str__(self) -> str:
        return f"  [{self.reject_class}] {self.subject}: {self.message}"


@dataclass
class Report:
    findings: list
    connectors: int = 0
    assertions: int = 0
    probes: int = 0
    non_sql: int = 0
    identifiers_walked: int = 0
    unrunnable: list = None

    def __post_init__(self) -> None:
        if self.unrunnable is None:
            self.unrunnable = []


# --------------------------------------------------------------------------------------------------
# Per-connector assertions — all DRY. No socket, no driver, no credential, no money.
# --------------------------------------------------------------------------------------------------


def check_connector(cls: type, conn: Mapping, *, build: Any = None) -> tuple:
    """A1..A8 over one connector class. Returns (findings, assertions_run).

    Everything here is offline and free by construction, which is what makes it runnable on a host
    with no driver installed -- the state of this one for `duckdb`. A conformance suite that needed
    the driver would examine zero connectors on the machine the gates run on, and report green.
    """
    out: list = []
    n = 0
    name = getattr(cls, "__name__", str(cls))

    # A1 · the required surface exists and is not the abstract base's.
    n += 1
    if not (isinstance(cls, type) and issubclass(cls, Connector)):
        return [Finding(name, "not-a-connector", "does not subclass Connector")], n
    for verb in ("read", "qualify", "config_schema", "validate_config", "credential_plan"):
        n += 1
        fn = getattr(cls, verb, None)
        if fn is None:
            out.append(Finding(name, "missing-required-verb", f"{verb!r} is absent"))
        elif getattr(fn, "__isabstractmethod__", False):
            out.append(Finding(name, "missing-required-verb",
                               f"{verb!r} is still abstract; the class cannot be constructed"))

    # A2 · `supports` declares a verb IFF the class overrides it, plus the rest of the declaration.
    # Each problem carries its OWN reject class; see declaration_problems' docstring for the
    # self-test finding that forced that.
    n += 1
    for reject_class, problem in cls.declaration_problems():
        out.append(Finding(name, reject_class, problem))

    # A3 · construction touches no network and no driver.
    #
    # The socket guard is installed around the CONSTRUCTOR only. boto3's default chain reaches IMDS
    # at client construction, so a connector that builds its client in __init__ turns an assignment
    # into a multi-second hang with a credential lookup attached.
    n += 1
    import socket as _socket

    real_socket = _socket.socket
    opened: list = []

    class _Guard(real_socket):  # type: ignore[misc,valid-type]
        def __init__(self, *a: Any, **k: Any) -> None:
            opened.append(1)
            raise AssertionError("a connector opened a socket during construction")

    instance = None
    _socket.socket = _Guard  # type: ignore[assignment]
    try:
        instance = build() if build else cls(conn)
    except AssertionError as exc:
        out.append(Finding(name, "network-at-construction", str(exc)))
    except Exception as exc:  # noqa: BLE001 — any construction failure is a finding, reported as one
        out.append(Finding(name, "construction-failed", f"{type(exc).__name__}: {exc}"))
    finally:
        _socket.socket = real_socket  # type: ignore[assignment]
    if opened:
        out.append(Finding(name, "network-at-construction", f"{len(opened)} socket(s) opened"))

    # A4 · no driver import at the module's top level.
    n += 1
    module_file = getattr(sys.modules.get(cls.__module__), "__file__", None)
    if module_file:
        out.extend(_check_no_module_level_driver(Path(module_file), name))

    # A5 · validate_config returns a SEQUENCE of ConfigProblem. Never None, never a bool, never str.
    n += 1
    try:
        problems = cls.validate_config(conn)
    except Exception as exc:  # noqa: BLE001
        out.append(Finding(name, "validate-config-raised",
                           f"validate_config raised {type(exc).__name__}: {exc}"))
        problems = []
    if isinstance(problems, (str, bytes)) or not isinstance(problems, Sequence):
        out.append(Finding(name, "validate-config-garbage",
                           f"returned {type(problems).__name__}, not a sequence of ConfigProblem"))
    else:
        for p in problems:
            if not isinstance(p, ConfigProblem):
                out.append(Finding(name, "validate-config-garbage",
                                   f"yielded {type(p).__name__}, not a ConfigProblem"))
                break

    # A5b · a KNOWN-BAD config must produce at least one problem. Without this, a validate_config
    # that returns [] unconditionally passes A5 -- the zero-denominator defect, one level down.
    n += 1
    try:
        if not cls.validate_config({"config": {}, "credentials": {"mode": "definitely-not-a-mode"}}):
            out.append(Finding(name, "validate-config-blind",
                               "returned no problems for an empty config with an invalid "
                               "credential mode; a validator that never rejects is not a validator"))
    except Exception as exc:  # noqa: BLE001
        out.append(Finding(name, "validate-config-raised",
                           f"validate_config raised on a bad config: {type(exc).__name__}: {exc}"))

    # A6 · credential_plan carries no secret-shaped value, and its repr is the redacted view.
    n += 1
    try:
        plan = cls.credential_plan(conn)
    except Exception as exc:  # noqa: BLE001 — an unwired mechanism raises by design (exit 2)
        plan = None
        if exit_code_for(exc) != EXIT_COULD_NOT_RUN:
            out.append(Finding(name, "credential-plan-exit",
                               f"credential_plan raised {type(exc).__name__}, which maps to exit "
                               f"{exit_code_for(exc)}; an unresolvable mechanism is exit 2"))
    if plan is not None:
        if not isinstance(plan, CredentialPlan):
            out.append(Finding(name, "credential-plan-shape",
                               f"returned {type(plan).__name__}, not a CredentialPlan"))
        else:
            try:
                plan.assert_no_secret()
            except ConnectorContractViolation as exc:
                out.append(Finding(name, "credential-secret", str(exc)))
            if any(tok in repr(plan) for tok in ("AKIA", "ASIA", "PRIVATE KEY")):
                out.append(Finding(name, "credential-secret",
                                   "repr() exposes a secret-shaped value"))

    # A7 · every optional verb NOT in `supports` raises ConnectorCapabilityMissing -> exit 2, and a
    # degradation line exists for it. THE MUST-PASS CASE: this is a degradation, never a rejection.
    if instance is not None:
        for verb in cls.OPTIONAL_VERBS:
            if verb in cls.supports:
                continue
            n += 1
            try:
                _call_optional(instance, verb)
            except ConnectorCapabilityMissing as exc:
                if exit_code_for(exc) != EXIT_COULD_NOT_RUN:
                    out.append(Finding(name, "degradation-exit",
                                       f"{verb!r} absent maps to exit {exit_code_for(exc)}, not 2"))
                line = cls.degradation_line(verb)
                if verb not in line or "degraded" not in line:
                    out.append(Finding(name, "degradation-unprinted",
                                       f"{verb!r} has no usable degradation line"))
            except Exception as exc:  # noqa: BLE001
                out.append(Finding(name, "degradation-wrong-error",
                                   f"{verb!r} absent raised {type(exc).__name__}, not "
                                   f"ConnectorCapabilityMissing"))

    # A9 · for a SQL connector, the DRY HALF actually runs and is correct.
    #
    # This is what makes "the dry half is testable offline" a MEASUREMENT rather than a claim, and it
    # is the only coverage the Athena connector has or can have: every wet method there is billed and
    # Ruling 8 is open. It also re-asserts §4.2's invariant -- plan_materialization and plan_lookups
    # are pure today and must stay pure -- by rendering DDL and profile statements with no driver
    # installed, no client, and no socket.
    if instance is not None and isinstance(instance, SqlConnector):
        dry, dn = check_sql_dry_half(instance, name)
        out.extend(dry)
        n += dn

    # A8 · the error taxonomy maps totally, and a genuine finding outranks a could-not-run.
    n += 1
    for reason in AdapterErrorReason:
        code = exit_code_for(AdapterError(reason, "probe"))
        if code not in (EXIT_FINDING, EXIT_COULD_NOT_RUN):
            out.append(Finding(name, "taxonomy-incomplete",
                               f"reason {reason.value!r} maps to exit {code}"))
    if worst_exit([EXIT_COULD_NOT_RUN, EXIT_FINDING]) != EXIT_FINDING:
        out.append(Finding(name, "precedence-inverted",
                           "a could-not-run outranked a finding"))
    return out, n


def check_sql_dry_half(instance: Any, name: str) -> tuple:
    """The pure renderers of a SQL connector: they run, offline and free, and they are correct.

    Returns (findings, assertions_run). Every assertion here executes real code with NO driver
    installed -- which is the whole reason the dry/wet split exists, and the only way the Athena
    connector can be covered at all without spending money.
    """
    out: list = []
    n = 0
    ref = RelationRef(namespace=("ns_a", "ns_b"), name="rel")

    # 1 · an embedded quote is DOUBLED, not deleted. This seeds the exact live defect at
    #     data_plane.py:229, which does `name.replace('"', "")` and thereby addresses a DIFFERENT
    #     column -- silently, and in a statement whose results are reported under the original name.
    n += 1
    quoted = instance.quote_identifier('a"b')
    if quoted != '"a""b"':
        out.append(Finding(name, "identifier-escaping",
                           f'quote_identifier(\'a"b\') returned {quoted!r}; an embedded quote must '
                           f'be doubled, never deleted -- deleting it addresses another column'))

    # 2 · qualify uses every segment, in order.
    n += 1
    address = instance.qualify(ref)
    if not all(seg in address for seg in ref.segments):
        out.append(Finding(name, "qualify-drops-segments",
                           f"qualify({ref.segments}) -> {address!r} does not carry every segment"))

    # 3 · the view DDL targets the qualified address and carries the body.
    n += 1
    ddl = instance.render_view_ddl(ref, "SELECT 1 AS x")
    if address not in ddl or "SELECT 1 AS x" not in ddl:
        out.append(Finding(name, "view-render-broken",
                           f"render_view_ddl did not compose the address and the body: {ddl!r}"))

    # 4 · the profile statement counts the relation and every column, and asks for extremes only on
    #     a type this connector itself calls orderable.
    n += 1
    cols = (ColumnSpecT(name="k", type=_ORDERABLE_PROBE_TYPE(instance)),
            ColumnSpecT(name="s", type="varchar"))
    profile = instance.render_profile_sql(ref, cols)
    for needle in ("count(*)", instance.quote_identifier("k"), instance.quote_identifier("s")):
        if needle not in profile:
            out.append(Finding(name, "profile-render-broken",
                               f"render_profile_sql omitted {needle!r}"))
    n += 1
    if instance.orderable("varchar"):
        out.append(Finding(name, "orderable-too-permissive",
                           "calls a text type orderable; min/max over it is not a fact"))

    # 5 · the read contract rejects a write at read(), and rejects a bound-but-unplaced parameter.
    n += 1
    if instance.head_verb("-- a leading comment\n SELECT 1") != "select":
        out.append(Finding(name, "head-verb-broken",
                           "a statement behind a leading comment was not read as its real verb"))
    n += 1
    try:
        instance.assert_params_placed("SELECT 1", {"unused": 1})
        out.append(Finding(name, "unplaced-param-accepted",
                           "a parameter that was bound but never placed was accepted; that is a "
                           "value which got formatted into the statement instead"))
    except ConnectorContractViolation:
        pass
    return out, n


def _ORDERABLE_PROBE_TYPE(instance: Any) -> str:
    """A type THIS connector calls orderable, so assertion 4 exercises the min/max branch.

    Asking the connector rather than hardcoding a type name is the same principle the contract is
    built on: MAC never parses a type name, and a suite that hardcoded `bigint` would be asserting
    one engine's vocabulary inside the generic instrument -- the defect being removed.
    """
    for candidate in ("bigint", "integer", "int", "double", "date", "timestamp", "decimal(18,2)"):
        if instance.orderable(candidate):
            return candidate
    return "bigint"


def _call_optional(instance: Connector, verb: str) -> Any:
    """Call an optional verb with the cheapest legal arguments. Never reaches I/O: the base raises."""
    ref = RelationRef(namespace=("ns",), name="rel")
    if verb == "list_relations":
        return instance.list_relations([()])
    if verb == "describe_relation":
        return instance.describe_relation(ref)
    if verb == "profile_relation":
        return instance.profile_relation(ref, ())
    if verb == "list_objects":
        return instance.list_objects(())
    if verb == "probe":
        return instance.probe()
    if verb == "explain":
        return instance.explain("x")
    if verb == "create_or_replace_view":
        return instance.create_or_replace_view(ref, "x")
    raise AssertionError(f"no call recipe for optional verb {verb!r}")


def _check_no_module_level_driver(path: Path, subject: str) -> list:
    """AST walk: no driver import at nesting depth 0. Mirrors sdk/gate/check_engine_coupling.

    A top-level scan of TEXT would report a lazy import inside a function as a violation and a
    module-level one as fine if it were spelled `importlib.import_module`. Walking the tree with the
    depth recorded is what distinguishes the deliverable (a driver import inside a method) from the
    defect (one that runs at import).
    """
    out: list = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        return [Finding(subject, "unparseable", f"{path.name}: {exc}")]
    for node in tree.body:                      # body only == module level, by construction
        roots: list = []
        if isinstance(node, ast.Import):
            roots = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots = [node.module.split(".")[0]]
        for root in roots:
            if root in DRIVER_MODULES:
                out.append(Finding(subject, "driver-at-import",
                                   f"{path.name}:{node.lineno} imports {root!r} at module level; "
                                   f"the dry half must stay importable with no driver installed"))
    return out


# --------------------------------------------------------------------------------------------------
# K1 / K2 — the two assertions that can falsify the interface
# --------------------------------------------------------------------------------------------------


def check_non_sql(cls: type) -> tuple:
    """K1: a non-SQL connector conforms WITHOUT implementing one SqlConnector verb.

    If this fails, do not patch the fixture. The record is explicit: "if the non-SQL fixture cannot
    conform to `Connector` without implementing a `SqlConnector` verb, or if `Connector` grows a
    parameter named `sql`, the interface is a rename of the hole." Finding that now is worth more
    than shipping it.
    """
    out: list = []
    n = 0
    name = getattr(cls, "__name__", str(cls))

    n += 1
    if issubclass(cls, SqlConnector):
        out.append(Finding(name, "non-sql-is-sql",
                           "subclasses SqlConnector, so it cannot falsify a SQL assumption"))

    for verb in SQL_TIER_NAMES:
        n += 1
        # `vars()` over the MRO up to Connector: an attribute inherited from `object` or from
        # `Connector` is not this class implementing a SQL verb.
        for klass in cls.__mro__:
            if klass is Connector:
                break
            if verb in vars(klass):
                out.append(Finding(name, "non-sql-uses-sql-verb",
                                   f"{klass.__name__} defines the statement-language verb {verb!r}"))
                break
    return out, n


def check_base_has_no_statement_language(path: Path | None = None) -> tuple:
    """K2: no IDENTIFIER in base.py is named sql / statement / query / ddl / view / dialect.

    Returns (findings, identifiers_walked). The walked count is printed as this check's own
    denominator: "0 forbidden identifiers" over an unstated population is the estate's dominant
    defect, and a typo in the path would otherwise produce a serene green over zero names.
    """
    target = path or (_HERE / "base.py")
    out: list = []
    try:
        tree = ast.parse(target.read_text(encoding="utf-8"), filename=str(target))
    except (OSError, SyntaxError) as exc:
        return [Finding(target.name, "unparseable", str(exc))], 0

    seen = 0
    for node in ast.walk(tree):
        names: list = []
        if isinstance(node, ast.arg):
            names = [node.arg]
        elif isinstance(node, ast.Name):
            names = [node.id]
        elif isinstance(node, ast.Attribute):
            names = [node.attr]
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.keyword) and node.arg:
            names = [node.arg]
        for ident in names:
            seen += 1
            low = ident.lower().strip("_")
            if low in FORBIDDEN_IN_BASE:
                out.append(Finding(
                    target.name, "statement-language-in-the-contract",
                    f"line {getattr(node, 'lineno', 0)}: identifier {ident!r} — the contract has "
                    f"grown a statement-language name, which is the kill criterion",
                ))
    return out, seen


# --------------------------------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------------------------------

_DUCKDB_CONN = {"spec_version": "mac.connector/1", "credentials": {"mode": "none"},
                "config": {"database": "bundle.duckdb", "read_only": True}}
_ATHENA_CONN = {"spec_version": "mac.connector/1", "credentials": {"mode": "ambient"},
                "config": {"region": "<region handle>", "workgroup": "<workgroup handle>",
                           "output": "<output location>"}}
_CSV_CONN = {"spec_version": "mac.connector/1", "credentials": {"mode": "none"},
             "config": {"directory": "csv"}}


def _subjects() -> list:
    """The three connectors, imported HERE so an import failure is a could-not-run, not a crash."""
    from sdk.connector.athena import AthenaConnector
    from sdk.connector.duckdb import DuckDbConnector
    from sdk.connector.fixtures.csv_dir import CsvDirectoryConnector

    return [
        (DuckDbConnector, _DUCKDB_CONN, False),
        (AthenaConnector, _ATHENA_CONN, False),
        (CsvDirectoryConnector, _CSV_CONN, True),      # the non-SQL one
    ]


def run(subjects: Sequence | None = None) -> Report:
    rep = Report(findings=[])
    try:
        items = list(subjects) if subjects is not None else _subjects()
    except Exception as exc:  # noqa: BLE001
        rep.unrunnable.append(f"could not import the connector set: {type(exc).__name__}: {exc}")
        return rep

    for cls, conn, is_non_sql in items:
        rep.connectors += 1
        findings, n = check_connector(cls, conn)
        rep.findings.extend(findings)
        rep.assertions += n
        rep.probes += n
        if is_non_sql:
            rep.non_sql += 1
            k1, kn = check_non_sql(cls)
            rep.findings.extend(k1)
            rep.assertions += kn
            rep.probes += kn

    k2, walked = check_base_has_no_statement_language()
    rep.findings.extend(k2)
    rep.identifiers_walked = walked
    rep.assertions += 1
    rep.probes += 1
    return rep


def verdict(rep: Report) -> tuple:
    """The one line, and the code. Zero connectors is EXIT 2, not a pass.

    "A machine where meaning-as-code is not installed discovers nothing; without this the gate
    reports serene green having examined zero connectors." §10.3, applied to this instrument.
    A zero-identifier K2 walk is the same defect and gets the same answer.
    """
    unit = (f"{rep.connectors} connector(s) × {rep.assertions} assertion(s) = {rep.probes} probe(s), "
            f"{rep.non_sql} non-SQL; K2 walked {rep.identifiers_walked} identifier(s) in base.py")
    if rep.unrunnable:
        return (f"could not run: connector-conformance — {'; '.join(rep.unrunnable)}",
                EXIT_COULD_NOT_RUN)
    if rep.connectors == 0:
        return ("could not run: connector-conformance examined 0 connector(s), which is not the "
                "same as clean", EXIT_COULD_NOT_RUN)
    if rep.non_sql == 0:
        return ("could not run: connector-conformance examined 0 non-SQL connector(s); two SQL "
                "engines cannot detect a SQL assumption, so this run establishes nothing about "
                "genericity", EXIT_COULD_NOT_RUN)
    if rep.identifiers_walked == 0:
        return ("could not run: connector-conformance walked 0 identifier(s) in base.py",
                EXIT_COULD_NOT_RUN)
    if rep.findings:
        return (f"FAIL: connector-conformance — {len(rep.findings)} violation(s) over {unit}",
                EXIT_FINDING)
    return (f"PASS: connector-conformance — 0 violation(s) over {unit}", EXIT_OK)


# --------------------------------------------------------------------------------------------------
# --self-test: a mutant per reject class, plus the must-pass fixtures
# --------------------------------------------------------------------------------------------------


def _clean_fixture() -> type:
    from sdk.connector.fixtures.csv_dir import CsvDirectoryConnector

    return CsvDirectoryConnector


def _mutants() -> list:
    """One seeded defect per reject class. Each MUST be rejected, and by the RIGHT class.

    Asserting only "it was rejected" would pass an implementation that rejects everything, which is
    the false-green G3 names: "a harness asserting only rc != 0 passes an implementation that
    converts every hostile connector into exit 1". So every entry names the class it must produce.
    """
    from sdk.connector.fixtures.csv_dir import CsvDirectoryConnector as C

    class SupportsDrift(C):
        """Declares a verb it does not override."""
        supports = frozenset({"list_relations", "describe_relation", "list_objects",
                              "profile_relation"})

    class SupportsUndeclared(C):
        """Overrides a verb it does not declare."""
        def profile_relation(self, ref, cols):    # noqa: D102
            return None

    class BadId(C):
        id = "fixture/connector/csvdir"

    class BadPermission(C):
        permissions = frozenset({"read", "root"})

    class BadProbeCost(C):
        probe_cost = "cheap"

    class GarbageValidate(C):
        @classmethod
        def validate_config(cls, conn):           # noqa: D102
            return "yes"

    class BlindValidate(C):
        @classmethod
        def validate_config(cls, conn):           # noqa: D102
            return []

    class SecretPlan(C):
        @classmethod
        def credential_plan(cls, conn):           # noqa: D102
            return CredentialPlan(mode="none", ref="AKIAIOSFODNN7EXAMPLE")

    class NetworkAtConstruction(C):
        def __init__(self, conn=None, **kw):      # noqa: D107
            import socket
            socket.socket()
            super().__init__(conn, **kw)

    class WrongDegradation(C):
        """An absent optional verb raises the wrong error, so a host cannot degrade."""
        supports = frozenset({"list_relations", "describe_relation", "list_objects"})

        def probe(self):                          # noqa: D102
            raise RuntimeError("boom")

    class NonSqlUsesSqlVerb(C):
        """The K1 mutant: a 'non-SQL' connector that grew a statement-language verb."""
        def quote_identifier(self, name):         # noqa: D102
            return f'"{name}"'

    from sdk.connector.duckdb import DuckDbConnector as D

    class DeletesEmbeddedQuote(D):
        """THE LIVE DEFECT, SEEDED. This is data_plane.py:229 exactly:

            q = '"' + c["name"].replace('"', "") + '"'

        A column named  a"b  is addressed as "ab" -- a different column. If A9 assertion 1 ever
        stops firing on this, the profile path has quietly regained the ability to report one
        column's statistics under another column's name.
        """
        def quote_identifier(self, name):         # noqa: D102
            return '"' + str(name).replace('"', "") + '"'

    class TextIsOrderable(D):
        """min/max over a text type reported as a fact about the data."""
        def orderable(self, engine_type):         # noqa: D102
            return True

    return [
        ("identifier-escaping", DeletesEmbeddedQuote, _DUCKDB_CONN, False),
        ("orderable-too-permissive", TextIsOrderable, _DUCKDB_CONN, False),
        ("supports-drift", SupportsDrift, _CSV_CONN, False),
        ("supports-undeclared", SupportsUndeclared, _CSV_CONN, False),
        ("bad-id", BadId, _CSV_CONN, False),
        ("bad-permission", BadPermission, _CSV_CONN, False),
        ("bad-probe-cost", BadProbeCost, _CSV_CONN, False),
        ("validate-config-garbage", GarbageValidate, _CSV_CONN, False),
        ("validate-config-blind", BlindValidate, _CSV_CONN, False),
        ("credential-secret", SecretPlan, _CSV_CONN, False),
        ("network-at-construction", NetworkAtConstruction, _CSV_CONN, False),
        ("degradation-wrong-error", WrongDegradation, _CSV_CONN, False),
        ("non-sql-uses-sql-verb", NonSqlUsesSqlVerb, _CSV_CONN, True),
    ]


#: Reject classes whose mutant is a FILE rather than a class: they are properties of source text.
_FILE_MUTANTS = {
    "statement-language-in-the-contract": (
        "class Connector:\n"
        "    def read(self, sql: str):\n"
        "        return sql\n"
    ),
    "driver-at-import": (
        "import duckdb\n"
        "class X:\n"
        "    pass\n"
    ),
}


def self_test() -> int:
    """Every mutant is rejected BY ITS OWN CLASS; every must-pass fixture passes. Prints its unit."""
    failures: list = []
    seeded = 0

    # --- in-process class mutants ---
    for expect, cls, conn, is_non_sql in _mutants():
        seeded += 1
        findings, _ = check_connector(cls, conn)
        if is_non_sql:
            k1, _ = check_non_sql(cls)
            findings = list(findings) + list(k1)
        classes = {f.reject_class for f in findings}
        if not findings:
            failures.append(f"mutant {expect!r} was NOT rejected")
        elif expect not in classes:
            # Rejected for the wrong reason is a false green wearing a red hat: the check that
            # would have caught the real defect is still unproven.
            failures.append(f"mutant {expect!r} was rejected as {sorted(classes)}, not {expect!r}")

    # --- file-shaped mutants ---
    with tempfile.TemporaryDirectory() as td:
        for expect, source in _FILE_MUTANTS.items():
            seeded += 1
            p = Path(td) / f"mutant_{expect.replace('-', '_')}.py"
            p.write_text(source, encoding="utf-8")
            if expect == "statement-language-in-the-contract":
                findings, walked = check_base_has_no_statement_language(p)
                if walked == 0:
                    failures.append(f"mutant {expect!r} walked 0 identifiers")
            else:
                findings = _check_no_module_level_driver(p, p.name)
            classes = {f.reject_class for f in findings}
            if expect not in classes:
                failures.append(f"mutant {expect!r} was not rejected ({sorted(classes)})")

    # --- must-pass C1: an absent optional verb DEGRADES. It must not be a finding. ---
    seeded += 1
    clean = _clean_fixture()
    findings, _ = check_connector(clean, _CSV_CONN)
    k1, _ = check_non_sql(clean)
    if findings or k1:
        failures.append(
            "must_pass C1/C2 (the non-SQL fixture, with profile_relation and probe deliberately "
            f"absent) was REJECTED: {[str(f) for f in list(findings) + list(k1)]}"
        )

    # --- must-pass C1b: the degradation is exit 2 AND the line is printable (an expect_line check).
    seeded += 1
    inst = clean(_CSV_CONN)
    try:
        inst.profile_relation(RelationRef(namespace=("ns",), name="rel"), ())
        failures.append("must_pass C1b: profile_relation did not raise on a connector lacking it")
    except ConnectorCapabilityMissing as exc:
        line = clean.degradation_line("profile_relation")
        if exit_code_for(exc) != EXIT_COULD_NOT_RUN:
            failures.append("must_pass C1b: the capability miss did not map to exit 2")
        if "profile-grounded DQ" not in line or "profiled 0 of" not in line:
            failures.append(f"must_pass C1b: degradation line does not disclose the degradation: {line}")

    # --- must-pass C3: the real base.py is clean, over a non-zero population. ---
    seeded += 1
    findings, walked = check_base_has_no_statement_language()
    if findings:
        failures.append(f"must_pass C3: base.py carries a statement-language identifier: "
                        f"{[str(f) for f in findings]}")
    if walked == 0:
        failures.append("must_pass C3: walked 0 identifiers in base.py")

    unit = f"{seeded} seeded case(s): {len(_mutants())} class mutant(s), {len(_FILE_MUTANTS)} file " \
           f"mutant(s), 3 must-pass fixture(s)"
    if failures:
        print(f"FAIL: connector-conformance --self-test — {len(failures)} harness defect(s) over {unit}")
        for f in failures:
            print(f"  {f}")
        return EXIT_FINDING
    print(f"PASS: connector-conformance --self-test — 0 harness defect(s) over {unit}")
    return EXIT_OK


def main(argv: Sequence | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--self-test", action="store_true",
                    help="seed a mutant per reject class and prove each is rejected by its own class")
    ap.add_argument("--verbose", action="store_true", help="print the degradation table")
    args = ap.parse_args(list(argv) if argv is not None else None)

    if args.self_test:
        return self_test()

    rep = run()
    for f in rep.findings:
        print(str(f))
    if args.verbose:
        for cls, _conn, _ in _subjects():
            for verb in cls.OPTIONAL_VERBS:
                if verb not in cls.supports:
                    print(f"  degraded: {cls.degradation_line(verb)}")
    line, code = verdict(rep)
    print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
