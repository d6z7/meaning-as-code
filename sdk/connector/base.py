#!/usr/bin/env python3
"""base.py — the connector contract: everything true of ANY source.

RECORD: decisions/PROPOSED-2026-09-13_connector-plugin-architecture.md §4 (TRACK B).

WHAT THIS FILE MAY NOT CONTAIN, AND WHY IT IS THE WHOLE POINT.
The record's kill criterion 1 (§11.3), restated in the unit that can actually fire:

    "if the NON-SQL fixture cannot conform to `Connector` without implementing a `SqlConnector`
     verb, or if `Connector` grows a parameter named `sql`, the interface is a rename of the hole."

So `SqlConnector` does NOT live here. The record's own §4.2 sketch drew both classes in this file;
that is the one place this package deviates from it, deliberately, and the reason is mechanical:
with both classes in one module the kill criterion is prose, and prose is what this record exists to
replace. Split across two modules it becomes an AST walk over THIS file's identifiers —
`conformance.py` K2 — which fails the moment a parameter, attribute or method here is named `sql`,
`statement`, `query`, `ddl` or `view`. A criterion nobody can run is a criterion nobody has met.

DERIVED, NOT INVENTED (§4.1). The verbs below are the ELEVEN operations the SDK performs today and
nothing else. Measured at the call sites, in this repository:

  #   operation                                  call site today                 lands as
  1   build an authenticated session             harvest.py:146 _session()       __init__ + credential_plan()
                                                 materialize.py:287
  2   enumerate relations in a namespace         harvest.py:152 _tables()        list_relations()      OPTIONAL
  3   describe columns + verbatim types          the same glue.get_tables call   describe_relation()   OPTIONAL
  4   enumerate the serving namespace            materialize.py:345 _show_tables list_objects()        OPTIONAL
  5   profile a relation                         data_plane.py:212 profile_table profile_relation()    OPTIONAL
  6   quote an identifier                        data_plane.py:229               SqlConnector          (sql.py)
  7   read-only query                            AthenaSQL.run()                 read()                REQUIRED
  8   create or replace a serving view (DDL)     materialize.py:298 _ddl()       SqlConnector          (sql.py)
  9   verify a created view selects              SELECT 1 FROM vs.n LIMIT 1      *no verb* — see below
  10  explain / dry-run a plan                   GroundingAdapter.validate       SqlConnector          (sql.py)
  11  execute a plan with bound params           AthenaAdapter.execute           read()                REQUIRED

Eleven operations, NINE methods. Two collapses, both recorded here so a later reader does not
"restore" a capability nobody calls:
  * 9 is not a verb. It is #8 followed by #7. A `verify_view()` on the contract would be a
    capability with zero call sites, which is the defect §4.1 names ("do not invent capabilities
    nobody calls").
  * 11 IS 7. An answering plan and an authoring read are one read-only request with bound params;
    they differ in who composed the body, which is not the connector's business.

THE ONE REQUIRED I/O VERB is `read`. Everything else that touches the source is OPTIONAL and its
absence degrades a NAMED capability (`DEGRADATION`, below) instead of crashing a host — §4.4's
governing rule: "a missing optional verb is never a crash and never a FAIL."

THE DRY HALF / WET HALF INVARIANT (§4.2). `materialize.plan_materialization()` and `plan_lookups()`
are pure today — they return the exact SQL with zero AWS calls, and test_harvest_hardening.py proves
it offline. Any interface that loses that is a regression however clean it looks. So every wet verb
here is split: a pure renderer and an executor that takes the rendered request.
`DuckDbConnector.profile_relation` is the worked example — it is `render_profile_sql()` (pure,
testable with the driver blocked) plus one `read()`.

CONSTRUCTION MUST NOT TOUCH THE NETWORK. boto3's default chain reaches IMDS at client construction,
so the engine client is built lazily on first I/O. `mac_runtime.adapters.athena` already holds this
property and tests it (test_construction_is_network_free); this contract makes it a rule for every
connector, and `conformance.py` A3 seeds a socket guard to prove it.

WHAT MAC DOES NOT DO HERE: parse a statement, own a placeholder syntax, or read a type name.
`assert_bound_params_only` (mac_runtime/adapters/safety.py) STAYS WHERE IT IS — it pins one bind
syntax (`:name`, its own docstring says so) and rejects any single-quoted literal as "presumptively
interpolated", which would make `date '2024-01-01'` and `read_csv('…')` illegal inside the generic
instrument. §4.2a. MAC's half of that precondition is `bind()`, below, and it reads zero characters
of the request body.
"""

from __future__ import annotations

import abc
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Mapping, Sequence

# --------------------------------------------------------------------------------------------------
# Exit codes — the ONE mapping. §4.6.
# --------------------------------------------------------------------------------------------------
#
# WHY A FUNCTION AND NOT A `reason` FIELD. The record rejected "a single ConnectorError with a reason
# field" on the ground that it "puts the 0/1/2 decision at every call site, which is how a
# could-not-run becomes a FAIL". The exit code is therefore a property of the RAISE, not of the
# catcher: a host catches `ConnectorError` and calls `exit_code_for(exc)` once.
#
# This is tools/_plugin.py's founding rule applied verbatim: "could not run is the one honest answer
# available, and it is never a finding."

EXIT_OK = 0
EXIT_FINDING = 1
EXIT_COULD_NOT_RUN = 2


class ConnectorError(Exception):
    """Base of the taxonomy. A host catches THIS and calls `exit_code_for` once."""


class ConnectorConfigError(ConnectorError):
    """The BUNDLE's config is wrong. Detectable offline and free -> a finding ABOUT THE BUNDLE.

    exit 1. Examples: a required key absent, a path that does not exist, a credential mode this
    connector does not offer, a write asked of a read-only connection.
    """


class ConnectorUnavailable(ConnectorError):
    """The connector could not be used. Not the bundle's fault, not the source's -> exit 2.

    The declared id resolves to nothing installed; the extra is missing
    ("pip install meaning-as-code[duckdb]"); an import raised ANYTHING, SystemExit included; or a
    declared credential mechanism is not wired -- today `secretsmanager` / `ssm`, which
    sdk/authoring/connection.py:45 raises NotImplementedError for rather than silently degrading to
    the ambient chain (which would mis-target a different account).
    """


class ConnectorCapabilityMissing(ConnectorUnavailable):
    """An OPTIONAL verb this connector does not implement was called -> exit 2, per §4.4.

    A subclass of Unavailable and not of ConfigError on purpose: a source that cannot be profiled is
    not a bundle that is wrong. `DEGRADATION` says which capability is lost and whether the host may
    continue (exit 0, degradation PRINTED) or must stop (exit 2).
    """

    def __init__(self, connector_id: str, verb: str) -> None:
        self.connector_id = connector_id
        self.verb = verb
        super().__init__(f"{connector_id} does not implement the optional verb {verb!r}")


class ConnectorAmbiguous(ConnectorUnavailable):
    """Two distributions claim one (id, major) -> exit 2. §6.5: refused, never won.

    Unreachable today by construction -- `registry.py` resolves from a shipped dict and discovers
    nothing -- and defined here anyway so the taxonomy is total before Ruling 14 is answered. A host
    that already handles it needs no edit on the day discovery lands.
    """


class ConnectorContractViolation(ConnectorError):
    """The connector or its caller broke THIS contract. Never softened, never degraded -> exit 1.

    A user value formatted into a request instead of travelling in `params`; a non-read verb at
    `read()`; `supports` claiming a verb the class does not override; a CredentialPlan carrying a
    secret-shaped value; a connector name that is path-shaped.

    Loudly, always: this is the one class that must never be caught and continued from, because
    every member of it is a defect in software, not a state of the world.
    """


class AdapterErrorReason(str, Enum):
    """Why the SOURCE refused. Closed vocabulary; the exit code is per-member (`_REASON_EXIT`).

    (str, Enum) and not StrEnum: pyproject pins requires-python >=3.10 and StrEnum arrives in 3.11.
    mac_runtime's copy of this enum uses StrEnum because that package sets its own floor. That is a
    LANGUAGE-LEVEL difference and not a vocabulary one: the member names and the wire values below
    are mac_runtime's, verbatim, and `.value` is the same string on both.

    THIS IS NO LONGER A FORWARD DECLARATION. §4.6 always said this enum IS
    `mac_runtime.adapters.base.AdapterErrorReason` "extended in place (not duplicated into MAC)",
    and the earlier `SourceErrorReason` spelling existed only because Ruling 12 (movement of code
    between repositories) was unanswered and this file could not depend on that one. The
    consolidation ruling has since landed: ONE repository, several distributions, and mac_runtime's
    existing vocabulary is the SURVIVOR. So the class, its member names and its values are
    mac_runtime's, and `ADAPTER_REASON_ALIASES` below no longer records renames -- it records the
    only thing still true of the two member SETS, which is the extension and the two retirements.
    Nothing here imports that package; the names simply agree now.

    THE MEMBER SET IS DELIBERATELY NOT IDENTICAL, and that is a design decision the vocabulary
    ruling did not touch (see `ADAPTER_REASON_ALIASES`):
      * EXTENDED by `unauthorized` and `unreachable` -- §4.6's "extended in place".
      * NARROWED by mac_runtime's `config_error` and `unbound_literal`, which are exit-1 cases and
        became EXCEPTION CLASSES here rather than reasons. A caller porting from mac_runtime must
        catch `ConnectorConfigError` / `ConnectorContractViolation` instead of matching a reason.
    """

    QUERY_FAILED = "query_failed"        # bad request, relation not found, type error
    QUERY_CANCELLED = "query_cancelled"
    TIMEOUT = "timeout"
    EXECUTION_LIMIT = "execution_limit"
    UNAUTHORIZED = "unauthorized"            # EXTENSION: credentials resolved, not permitted
    UNREACHABLE = "unreachable"              # EXTENSION: endpoint / DNS / network


#: EVERY mac_runtime member -> its disposition here. Measured 2026-09-13 by reading
#: mac-platform/packages/mac-runtime/src/mac_runtime/adapters/base.py, and kept TOTAL over that
#: file's six members on purpose: a reconciliation table that lists only the interesting rows cannot
#: be read as evidence that the rest were considered.
#:
#: The four adopted rows are IDENTITY now, and they are listed rather than deleted because
#: "unchanged" and "never looked at" are different claims and only one of them is checkable.
#:
#: The two RETIRED members are not renames and never were: both are detectable offline and both are
#: exit 1, and a reason field that carries an exit-1 case inside an exit-2 class is how a
#: could-not-run becomes a FAIL.
ADAPTER_REASON_ALIASES: Mapping[str, str] = {
    "query_failed": "query_failed",
    "query_cancelled": "query_cancelled",
    "timeout": "timeout",
    "execution_limit": "execution_limit",
    "config_error": "<retired> ConnectorConfigError (exit 1)",
    "unbound_literal": "<retired> ConnectorContractViolation (exit 1)",
}

#: §4.6's table, as data. `query_failed` is the ONLY reason that is a finding: something was
#: judged and the answer is "no". Every other member means nothing was judged.
_REASON_EXIT: Mapping[AdapterErrorReason, int] = {
    AdapterErrorReason.QUERY_FAILED: EXIT_FINDING,
    AdapterErrorReason.QUERY_CANCELLED: EXIT_COULD_NOT_RUN,
    AdapterErrorReason.TIMEOUT: EXIT_COULD_NOT_RUN,
    AdapterErrorReason.EXECUTION_LIMIT: EXIT_COULD_NOT_RUN,
    AdapterErrorReason.UNAUTHORIZED: EXIT_COULD_NOT_RUN,
    AdapterErrorReason.UNREACHABLE: EXIT_COULD_NOT_RUN,
}


class AdapterError(ConnectorError):
    """A genuine error FROM THE SOURCE. The exit code comes from `reason`, never from the catcher."""

    def __init__(
        self,
        reason: AdapterErrorReason,
        message: str,
        *,
        engine_query_id: str | None = None,
    ) -> None:
        self.reason = reason
        # mac_runtime's name, kept. This field spent one day spelled `engine_request_id`, on the
        # argument that "not every source has queries"; the consolidation ruling settled it the other
        # way and mac_runtime's spelling survives. The argument was real and is now recorded where it
        # can do no damage: a source with no queries carries whatever id it does have in this field,
        # and the docstring says so rather than a second name saying it.
        # Its job is unchanged -- 04 §7's "provenance still recorded" needs the engine's own id to be
        # recoverable from the error, not just the reason, and `AdapterProvenance.engine_query_id`
        # (mac_runtime.models) is the field it is read back into.
        self.engine_query_id = engine_query_id
        super().__init__(f"[{reason.value}] {message}")


def exit_code_for(exc: BaseException) -> int:
    """The taxonomy -> 0/1/2. The single home of that decision. §4.6.

    An exception OUTSIDE the taxonomy is exit 2, never 1. An unexpected error means the check did not
    run; reporting it as a finding about the bundle is the exact damage _plugin.py exists to prevent
    (a could-not-run published as a FAIL).
    """
    if isinstance(exc, AdapterError):
        return _REASON_EXIT[exc.reason]
    if isinstance(exc, (ConnectorConfigError, ConnectorContractViolation)):
        return EXIT_FINDING
    if isinstance(exc, ConnectorUnavailable):
        return EXIT_COULD_NOT_RUN
    return EXIT_COULD_NOT_RUN


def worst_exit(codes: Sequence[int]) -> int:
    """Combine exit codes under §4.6's precedence rule, stated once so the codes cannot race:

        A GENUINE FINDING OUTRANKS A COULD-NOT-RUN.

    A bundle that both leaks an account id and names an uninstalled connector is a FAIL. Absent a
    finding, unrunnable beats PASS. Written as a function because `max()` gets this backwards -- it
    would return 2 for a bundle that has a real finding, publishing a FAIL as a could-not-run.
    """
    if not codes:
        return EXIT_OK
    if EXIT_FINDING in codes:
        return EXIT_FINDING
    if EXIT_COULD_NOT_RUN in codes:
        return EXIT_COULD_NOT_RUN
    return EXIT_OK


# --------------------------------------------------------------------------------------------------
# Data shapes — MAC's, not the engine's. §4.2a.
# --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RelationRef:
    """One relation, addressed as ORDERED NAMESPACE SEGMENTS plus a name. Engine-neutral.

    §5.5: `serving.namespace: [<segment>, ...]`. The first draft used `serving.schema` /
    `serving.database`, which would have made "database" core manifest grammar inherited by every
    bundle regardless of engine -- including a bundle grounded on a file lake, an API or a graph
    store, none of which has a database. A two-handle warehouse becomes a two-segment list; a
    single-namespace engine uses one; a CSV directory uses zero or one.

    `Connector.qualify(ref)` is the verb that turns segments into an engine address, which is also
    why a view renderer never needs to know what a database is.
    """

    namespace: tuple[str, ...] = ()
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ConnectorContractViolation("RelationRef.name is empty")
        if not isinstance(self.namespace, tuple):
            # A list here compares unequal to an otherwise identical ref and would silently defeat
            # assert_own_schema's segment-list comparison (§4.5 guard 1) -- the guardrail that
            # exists because of the 2026-08-13 gold overwrite.
            raise ConnectorContractViolation("RelationRef.namespace must be a tuple of segments")

    @property
    def segments(self) -> tuple[str, ...]:
        return self.namespace + (self.name,)


@dataclass(frozen=True)
class ColumnSpec:
    """A column, and the engine's VERBATIM type string.

    `type` is never parsed by MAC. That retires data_plane.py:48-58 `_ORDERABLE` -- eleven
    Hive/Presto type names living in the generic instrument -- and moves the verdict to
    `SqlConnector.orderable()`, which is the connector's to give.

    A CORRECTION THE RECORD MAKES AGAINST ITSELF (§4.2a): the first draft justified verbatim types
    by claiming TableFile.columns[].type "is already documented as 'verbatim glue type'". Measured:
    that property is `{"type": "string"}` with NO description at all. The string `<verbatim glue
    type>` lives at sdk/authoring/data_plane.py:77 -- inside `_DP_SYS_TEMPLATE`, the system prompt
    MAC ships to a model. This field is where that becomes true instead of assumed.
    """

    name: str
    type: str = ""
    description: str = ""


@dataclass(frozen=True)
class RelationSchema:
    ref: RelationRef
    columns: tuple[ColumnSpec, ...] = ()


@dataclass(frozen=True)
class ColumnStat:
    null_frac: float | None = None
    distinct: int = 0
    min: str | None = None
    max: str | None = None
    has_extremes: bool = False


@dataclass(frozen=True)
class RelationProfile:
    """`as_dict()` returns TODAY'S EXACT SHAPE, so data_plane._profile_md is untouched.

    Measured from data_plane.profile_table's return value:
        {"row_count": int, "columns": {col: {"null_frac", "distinct", "min"?, "max"?}}}
    `min`/`max` are PRESENT-OR-ABSENT, not None -- _profile_md reads them with `d.get('min', '')`.
    Emitting an explicit None would render the string "None" into the profile markdown a model then
    grounds DQ findings in, so `has_extremes` (not `min is None`) decides the key's presence.
    """

    row_count: int = 0
    columns: Mapping[str, ColumnStat] = field(default_factory=dict)

    def as_dict(self) -> dict:
        out: dict = {"row_count": self.row_count, "columns": {}}
        for col, st in self.columns.items():
            cd: dict = {"null_frac": st.null_frac, "distinct": st.distinct}
            if st.has_extremes:
                cd["min"], cd["max"] = st.min, st.max
            out["columns"][col] = cd
        return out


@dataclass(frozen=True)
class ReadRequest:
    """ONE read-only request. Engine-neutral by construction.

    `body` IS OPAQUE TO MAC AND IS DELIBERATELY NOT NAMED `sql`. That name is the record's kill
    criterion ("if `Connector` grows a parameter named `sql`, the interface is a rename of the
    hole"), and `body` is not a euphemism for it: for `SqlConnector` the body is a statement string,
    for the CSV-directory fixture it is a `CsvScan` dataclass, and NOTHING in this module inspects
    it. What a request MEANS is the connector's; how it is spelled is the connector's.

    `params` is MAC's half of the precondition (§4.2a): every user-derived value travels here.

    NOT RENAMED TO mac_runtime's `ExecutablePlan` under the consolidation ruling, because they are
    not one concept. Measured field by field: `ExecutablePlan` is {sql, params, concepts_used,
    rules_used, edges_used} -- three of its five fields are ONTOLOGY PROVENANCE, which is the one
    thing this seam must not know about, and its first is a REQUIRED `str`. This is {body, params,
    limit, timeout_s, purpose} -- `body` is `Any` and is a `CsvScan` dataclass for the non-SQL
    fixture, and `limit`/`timeout_s` are execution controls `ExecutablePlan` has nowhere to put.
    One field, `params`, is shared. Taking the name without the fields would publish one name
    standing for two different shapes in one repository, which is worse than two honest names.
    """

    body: Any = None
    params: Mapping[str, Any] = field(default_factory=dict)
    limit: int | None = None
    timeout_s: float | None = None
    purpose: str = ""          # free text for the trace; never interpreted


@dataclass(frozen=True)
class ReadResult:
    """Byte-compatible with AthenaSQL.run()'s `{columns, rows, row_count, truncated}` (op 7).

    `truncated` is not cosmetic: it is the difference between "there were 5 rows" and "we stopped at
    5", and a caller that cannot tell them apart will report a max() over a truncated window as a
    fact about the source.

    NOT RENAMED TO mac_runtime's `ExecutionResult`, for the same reason as `ReadRequest` above and
    with the same measurement. `ExecutionResult` is {rows, row_count, bytes_scanned, started_at,
    finished_at, engine_query_id}: it is a result PLUS the answer object's physical provenance
    (04 §5 `provenance.adapter`), which it can require because every one of its sources is a billed
    engine that reports scanned bytes. This is {columns, rows, row_count, truncated}: it has
    `columns` (the engine's column ORDER, which `ExecutionResult` loses by keying rows into dicts)
    and `truncated`, and it has no `bytes_scanned` to give -- the CSV fixture meters nothing. Two
    rows are shared out of six and four. The provenance fields belong on whatever the runtime
    records at the answer boundary, not on the one required verb of every source.
    """

    columns: tuple[str, ...] = ()
    rows: tuple[Mapping[str, Any], ...] = ()
    row_count: int = 0
    truncated: bool = False

    def as_dict(self) -> dict:
        return {
            "columns": list(self.columns),
            "rows": [dict(r) for r in self.rows],
            "row_count": self.row_count,
            "truncated": self.truncated,
        }


@dataclass(frozen=True)
class ConfigProblem:
    """One finding about the BUNDLE's config block. Offline, free.

    SEVERITY IS NOT COSMETIC, and its absence was a real defect. The Athena connector's own
    `validate_config` docstring says one of its findings is "stated as a WARNING-shaped finding
    rather than a hard one, because whether the workgroup manages its output is a fact only the
    account knows and asking costs an API call" — and there was no field in which to state it. So
    every finding read as blocking, and a bundle whose config was merely UNPROVABLE could not be
    probed at all: the page reported `could_not_run` over a connection that was very likely fine.

    `blocking` means this config CANNOT work. `advisory` means something could not be established
    offline and is reported rather than assumed either way — which is the same discipline as a gate
    printing its denominator instead of a bare pass.

    The default is `blocking`, deliberately: a connector author who does not think about severity
    gets the SAFE answer, not the permissive one.
    """

    path: tuple[str, ...] = ()
    message: str = ""
    severity: str = "blocking"

    @property
    def blocking(self) -> bool:
        return self.severity != "advisory"

    def __str__(self) -> str:
        where = ".".join(self.path) if self.path else "config"
        tag = "" if self.blocking else " (advisory)"
        return f"{where}: {self.message}{tag}"


#: Anything that looks like a live credential. Seeded by conformance A6 (record H11 / G3 R5) against
#: `CredentialPlan`, because the ONE thing that type must never do is carry a value.
_SECRET_SHAPED = re.compile(
    r"(AKIA[0-9A-Z]{8,})|(ASIA[0-9A-Z]{8,})|(-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)


@dataclass(frozen=True)
class CredentialPlan:
    """HOW to authenticate. NEVER a secret value -- not fetched here, not logged, not persisted.

    This is sdk/authoring/connection.py's `{mode, ref}` seam generalised off AWS. `mode` is the
    connector's own vocabulary ("none" for a local file, "ambient"/"profile" for a cloud chain);
    `ref` is a HANDLE (a profile name, a secret id), never a value.

    `__repr__` IS the redacted view -- there is no second `redacted()` to forget to call, because the
    measured failure mode is a secret reaching a log through an f-string somebody wrote in a hurry.
    `assert_no_secret()` is the gate's hook and raises ConnectorContractViolation (exit 1, loudly):
    a credential inside a declaration is a defect in software, never a degraded state.
    """

    mode: str = "none"
    ref: str | None = None
    detail: str = ""           # e.g. "ambient chain: env / SSO / task role"
    wired: bool = True         # False => the mechanism is declared but has no resolver (exit 2)

    def __repr__(self) -> str:
        return f"CredentialPlan(mode={self.mode!r}, ref={self.ref!r}, wired={self.wired!r})"

    __str__ = __repr__

    def assert_no_secret(self) -> None:
        for slot in (self.mode, self.ref, self.detail):
            if slot and _SECRET_SHAPED.search(str(slot)):
                raise ConnectorContractViolation(
                    "CredentialPlan carries a secret-shaped value; it may carry only a handle"
                )


@dataclass(frozen=True)
class ProbeResult:
    """The result of the ONE tier that may cost money. See `Connector.probe_cost`."""

    ok: bool = False
    cost: str = "free"
    target: str = ""           # the REDACTED address, never a credential
    detail: str = ""


# --------------------------------------------------------------------------------------------------
# The plan-boundary precondition — MAC's half, and only MAC's half. §4.2a.
# --------------------------------------------------------------------------------------------------


def bind(
    body: Any,
    *,
    params: Mapping[str, Any] | None = None,
    user_values: Sequence[Any] = (),
    limit: int | None = None,
    timeout_s: float | None = None,
    purpose: str = "",
) -> ReadRequest:
    """Compose a ReadRequest and assert the ONE structural fact MAC owns.

    THE ASSERTION: every value the planner was HANDED travelled in `params`. That is checkable at
    the plan boundary by comparing two collections the planner already holds -- WITHOUT READING ONE
    CHARACTER OF `body`. This function contains no regex over the request and no notion of a quote,
    a placeholder or a verb.

    WHY NOT THE OBVIOUS SCAN. mac_runtime/adapters/safety.py's `_QUOTED_STRING_RE` rejects any
    single-quoted literal as "presumptively an interpolated value". Promoted into MAC that makes
    legal requests illegal -- an Athena `date '2024-01-01'`, a DuckDB `read_csv('...')`, or any
    connector-rendered view body with a quoted constant -- and it makes MAC the owner of one
    dialect's parameter style, which that module's own docstring admits is a local choice ("04 §3/§4
    mandate bound params but do not pin a placeholder syntax"). It stays in mac_runtime as the
    Athena adapter's own precondition: not promoted, not duplicated.

    THE HONEST LIMIT, because a precondition oversold is worse than none. This catches the planner
    that OMITTED a user value from `params` (it formatted it in instead). It cannot see a value that
    was BOTH interpolated and bound, because from here those two cases are the same two collections.
    The second line of defence is the connector's own `read()`, which may scan its own dialect
    because it owns it. Two narrow checks that each say what they cover beat one broad one that
    claims what it cannot do.
    """
    p = dict(params or {})
    bound = list(p.values())
    missing = []
    for v in user_values:
        # Equality, not string containment: a user value of `1` must not be judged "present" because
        # the digit 1 appears somewhere inside another bound parameter.
        if not any(v == b for b in bound):
            missing.append(v)
    if missing:
        raise ConnectorContractViolation(
            f"{len(missing)} user-derived value(s) did not travel in params; a planner formatted "
            f"them into the request instead of binding them"
        )
    return ReadRequest(body=body, params=p, limit=limit, timeout_s=timeout_s, purpose=purpose)


# --------------------------------------------------------------------------------------------------
# The contract
# --------------------------------------------------------------------------------------------------

#: §8.4's closed vocabulary `mac.connector_permission`. Declared here as a tuple and NOT registered
#: in mac_vocabulary.yaml: that registration is Track A's and Ruling 14's, and a canon member added
#: by a Track B package is exactly the "three designs for one seam" failure the record names.
#:
#: THE HONEST LIMIT, in the field's own home so it cannot be mis-sold: this is a declaration the
#: operator admits or refuses. It is NOT a sandbox; CPython has no in-process capability
#: enforcement. A connector that declares {read} and opens a socket is lying, and this field is what
#: makes that lie a reviewable, attributable claim rather than an invisible one.
PERMISSIONS = ("read", "write", "net", "fs", "exec")

#: §7.5c, and the definition is engine-neutral ON PURPOSE:
#:   "billed" = the call is metered, rate-limited, or recorded in an audit log the source's operator
#:              maintains.  "free" = none of those.
#: The first draft defined it as "touches the account and appears in CloudTrail" -- an AWS audit
#: product and an AWS account, named inside a field on the generic base class. The honesty was
#: right; the home was wrong. The per-engine reasoning lives in each connector's own docstring.
PROBE_COSTS = ("free", "billed")

_ID_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


def capability_backstop(fn):
    """Mark a method as the RAISING BACKSTOP for an optional verb, not an implementation of it.

    WHY THE MARKER IS ON THE FUNCTION AND NOT ON THE CLASS. The first cut of `implements()` asked
    "did a contract base define this verb?", which is wrong the moment a refinement ships a SHARED
    implementation: `SqlConnector.profile_relation` is render-then-read, real code every SQL engine
    inherits, and under a class-level marker every subclass of it would have been reported as "does
    not implement" while its `supports` said otherwise -- the drift check firing on the correct
    pattern, which §4.3's own precedent (`check_no_fabricated_identifiers`, "a checker that punishes
    the correct pattern is worse than no checker") says is the worse failure.

    With the marker on the function, "implemented" means exactly "the resolved function is not a
    backstop", which is the question being asked.
    """
    fn._capability_backstop = True
    return fn


class Connector(abc.ABC):
    """Everything true of ANY source. No SQL, no DDL, no identifier quoting.

    AN ABC AND NOT A typing.Protocol, although this package's brief calls it "the Connector
    Protocol". A Protocol cannot carry the two things §4.3 requires:
      * the base implementation of each optional verb as `raise ConnectorCapabilityMissing`, which is
        the BACKSTOP turning a forgotten `supports` check into exit 2 with the verb named, instead of
        an AttributeError three frames deeper;
      * the drift check -- `supports` declares a verb IFF the class overrides it -- which needs a
        base method object to compare against. Duck-typed `hasattr` sniffing was rejected because it
        cannot be gated and it drifts silently, and this is the check it cannot support.
    The structural shape a Protocol would give is still available and still checked:
    `conformance.check_surface()` verifies it without requiring inheritance.

    SUBCLASS THIS for a source that is not addressed in a statement language. Subclass
    `sql.SqlConnector` for one that is.
    """

    # ---- identity + declaration: PURE DATA, readable without instantiating anything ----
    #
    # WHY CLASSVARS AND NOT INSTANCE STATE. §6.3's mount tier validates a bundle's config with ZERO
    # imports of the connector, and the tier above it needs the declaration WITHOUT a connection. A
    # declaration that requires construction is a declaration that costs a credential to read.
    #
    # `id` IS NOT mac_runtime's `GroundingAdapter.kind`, and the two were NOT merged under the
    # consolidation ruling. The measurement that decides it: `kind` is a bare provenance LABEL with
    # no grammar -- its shipped values are "athena" and "fake" -- and `id` is a RESOLUTION KEY with
    # one, `_ID_RE` below, which requires a dotted namespace and would REJECT both of those values.
    # A name whose own grammar rejects the other name's data is not the same name spelled twice. The
    # relationship is derivation, not identity: `AdapterProvenance.kind` is fed FROM `id`, and a
    # consolidated runtime should record `id` there rather than invent a second short token.
    id: ClassVar[str] = ""
    credential_modes: ClassVar[frozenset] = frozenset()
    permissions: ClassVar[frozenset] = frozenset({"read"})
    probe_cost: ClassVar[str] = "free"

    #: The OPTIONAL verbs this class implements. The single declaration (§4.3): a host checks
    #: `supports` BEFORE calling; the raise is the backstop, not the mechanism.
    supports: ClassVar[frozenset] = frozenset()

    #: The optional verbs this contract defines. A refinement EXTENDS this (see SqlConnector) rather
    #: than mutating it, so the set is inherited and no third party can edit it at runtime.
    OPTIONAL_VERBS: ClassVar[tuple] = (
        "list_relations",
        "describe_relation",
        "profile_relation",
        "list_objects",
        "probe",
    )

    #: §4.4 AS DATA, not prose, because every "prints" in that table is meant to be a checked
    #: assertion and the first draft specified none. verb -> (capability degraded, host behaviour,
    #: exit code). exit 2 here means "this verb's absence stops the step"; exit 0 means "continue,
    #: and PRINT the degradation". `degradation_line()` is the one renderer, so the printed
    #: disclosure cannot drift from the record.
    DEGRADATION: ClassVar[Mapping[str, tuple]] = {
        "list_relations": (
            "harvestable, collision snapshot",
            "--mode data requires explicit --relations; materialize prints "
            "'SHOW TABLES: unavailable - collision check NOT performed' and proceeds",
            EXIT_OK,
        ),
        "describe_relation": (
            "harvestable",
            "--mode data refuses: it is the input",
            EXIT_COULD_NOT_RUN,
        ),
        "profile_relation": (
            "profile-grounded DQ",
            "authoring proceeds profile-free; the prompt receives '(no live profile available)'; "
            "every emitted dq_issues[].confidence is forced to Q; the run line prints "
            "'profiled 0 of N relation(s)'",
            EXIT_OK,
        ),
        "list_objects": (
            "collision snapshot",
            "materialize proceeds and PRINTS that no collision check was performed",
            EXIT_OK,
        ),
        "probe": (
            "live liveness evidence",
            "'probe: not implemented by <id>'; answerable rests on offline evidence",
            EXIT_OK,
        ),
    }

    # ---- TIER 1 · DRY: offline, free, no socket. REQUIRED. ----

    @classmethod
    @abc.abstractmethod
    def config_schema(cls) -> Mapping[str, Any]:
        """The JSON Schema for this connector's OPAQUE `config:` block (§5.3).

        MAC never reads a key inside it. The schema ships as a FILE so §6.3's mount tier can validate
        a bundle with zero imports; this classmethod is that same file, loaded, so there is one
        authority and not two.
        """

    @classmethod
    @abc.abstractmethod
    def validate_config(cls, conn: Mapping) -> Sequence[ConfigProblem]:
        """Offline, free, no socket. Returns findings; NEVER raises for a bad config.

        A SEQUENCE, AND NEVER None: record H6 seeds `validate_config` returning "yes" / None / {} as
        a hostile class, because each of those is truthy-or-falsy in a way that reads as "valid" at a
        call site. `[]` means "no problems found"; raising means the CHECK broke, which is a
        different fact with a different exit code.

        This is also where cross-field rules JSON Schema cannot express live -- §6.3's honest limit
        ("a rule it cannot express is NOT silently skipped at mount: it belongs to validate_config").
        """

    @classmethod
    @abc.abstractmethod
    def credential_plan(cls, conn: Mapping) -> CredentialPlan:
        """HOW this connection would authenticate. Never a value; never a fetch. See CredentialPlan.

        Raises ConnectorUnavailable (exit 2) when the declared mechanism has no resolver -- the
        connection.py:45 case. Failing loud beats degrading to the ambient chain, which would
        mis-target a different account.
        """

    @abc.abstractmethod
    def qualify(self, ref: RelationRef) -> str:
        """Namespace segments -> ONE engine address. The only verb that knows how a source is named.

        For a statement language this is a quoted dotted path; for a file source a path; for an API a
        route. Because it exists, a view renderer never needs to know what a database is, and
        `assert_own_schema` can compare SEGMENT LISTS (§5.5) instead of strings.
        """

    def __init__(self, conn: Mapping | None = None, *, client: Any | None = None) -> None:
        """MUST NOT TOUCH THE NETWORK, and must not import a driver.

        boto3's default chain reaches IMDS at client construction, so the engine client is built
        lazily on first I/O. `client` is the injection seam the offline tests use -- the same shape
        materialize.py already relies on ("constructed only when actually executing; the offline
        tests inject their own executor").
        """
        self.conn: Mapping = dict(conn or {})
        self._client = client

    # ---- TIER 1 · WET: the ONE required I/O verb ----

    @abc.abstractmethod
    def read(self, request: ReadRequest) -> ReadResult:
        """One read-only request. The only I/O every connector must have.

        The connector enforces ITS OWN preconditions in here -- that the request matches its own
        parameter style, that the head verb is one it considers read-only -- and raises
        ConnectorContractViolation (exit 1) when the caller broke them. MAC's half was asserted at
        the plan boundary by `bind()` and is not re-asserted here, because re-asserting it would
        require reading the body, which is the connector's.

        NOT RENAMED TO mac_runtime's `GroundingAdapter.execute`, though both occupy the seam
        position "the one verb that returns rows". Two reasons, and the first is decisive:
          * SCOPE. `read` is ops 7 AND 11 collapsed -- an authoring read (list, describe, profile)
            and an answering plan are one read-only request here. `execute` is op 11 alone; every
            catalog read above goes through `read`, and there is no `ExecutablePlan` behind them to
            execute. Renaming would claim `list_relations` executes a plan.
          * THE READ-ONLY GUARANTEE IS IN THE NAME, and it is enforced: `read_verbs` gates the head
            verb here, and the single write verb is a DIFFERENT method with a different guard
            (`create_or_replace_view`). `execute` is verb-neutral, and a verb-neutral I/O method is
            precisely the `executor(sql)`-dispatching-on-`is_read_only(sql)` shape (materialize.py
            :298) that this split exists to retire.
        A consolidated runtime wanting `GroundingAdapter` should get it from a shim that maps
        execute(ExecutablePlan) -> read(ReadRequest); that is four lines and it converts the shapes
        too, which a rename would not.
        """

    # ---- TIER 1 · OPTIONAL: the base raises; the absence degrades a NAMED capability ----
    #
    # Each of these is a real method (not a stub) so `supports` can be cross-checked against
    # overrides, and so a host that forgets to check `supports` gets exit 2 with the verb named.

    @capability_backstop
    def list_relations(self, namespaces: Sequence[Sequence[str]]) -> Sequence[RelationRef]:
        raise ConnectorCapabilityMissing(self.id, "list_relations")

    @capability_backstop
    def describe_relation(self, ref: RelationRef) -> RelationSchema:
        raise ConnectorCapabilityMissing(self.id, "describe_relation")

    @capability_backstop
    def profile_relation(self, ref: RelationRef, cols: Sequence[ColumnSpec]) -> RelationProfile:
        raise ConnectorCapabilityMissing(self.id, "profile_relation")

    @capability_backstop
    def list_objects(self, namespace: Sequence[str]) -> set:
        """The collision snapshot (op 4).

        materialize._show_tables' `except Exception: return set()` is specifically upgraded under
        §4.4's rule: an empty set reads as "no collisions" inside the very step whose guardrail
        exists because of a real overwrite (2026-08-13, gold's dim_country / dim_model). Absent
        means ABSENT, and the host prints that it did not check.
        """
        raise ConnectorCapabilityMissing(self.id, "list_objects")

    # ---- TIER 2 · BILLED on some engines. Never automatic. ----

    @capability_backstop
    def probe(self) -> ProbeResult:
        """Live liveness evidence. NOTHING CALLS THIS AUTOMATICALLY.

        §7.5d: `open_container()` has no code path to `probe()` -- not a flag that defaults off, no
        path. The single entry point is an explicit operator command that prints the cost class, the
        connector, the redacted target and the credential mode, THEN acts. The confirmation is
        deliberately not readable from an environment variable, because a pre-confirming env var is
        how "nothing unprompted" quietly becomes "everything, in CI".
        """
        raise ConnectorCapabilityMissing(self.id, "probe")

    # ---- declaration hygiene ----

    @classmethod
    def degradation_line(cls, verb: str) -> str:
        """The ONE renderer of §4.4's printed disclosure, so the words cannot drift from the record."""
        capability, behaviour, code = cls.DEGRADATION.get(
            verb, ("(undeclared capability)", "(undeclared behaviour)", EXIT_COULD_NOT_RUN)
        )
        return (
            f"{verb}: unavailable on {cls.id or '<unnamed connector>'} — "
            f"{capability} degraded — {behaviour} — exit {code}"
        )

    @classmethod
    def declaration_problems(cls) -> list:
        """Every way this class's DECLARATION can be wrong, offline and free.

        Returns `(reject_class, message)` PAIRS, not bare strings. The reject class is not
        decoration: a harness that seeds four different declaration defects and receives one label
        for all four has proved that ONE of its checks works and cannot say which. Its own self-test
        found exactly that here -- four mutants (a path-shaped id, a permission outside the
        vocabulary, an invalid probe cost, a `supports` claim with no override) all came back as
        "declaration-drift", so three of the four checks were unproven while the suite read green.

        The `supports` drift check (§4.3) is the load-bearing one: `verb in supports` IFF the method
        is overridden. It needs a base method object to compare against, which is the concrete
        reason `Connector` is an ABC.
        """
        problems: list = []
        if "/" in cls.id or "\\" in cls.id:
            # §4.6 names a path-shaped connector name as a contract violation in its own right.
            problems.append(("bad-id", f"id {cls.id!r} is path-shaped"))
        elif not cls.id or not _ID_RE.match(cls.id):
            problems.append(("bad-id", f"id {cls.id!r} is not a dotted lowercase identifier"))
        if cls.probe_cost not in PROBE_COSTS:
            problems.append(("bad-probe-cost",
                             f"probe_cost {cls.probe_cost!r} not in {PROBE_COSTS}"))
        bad_perm = sorted(set(cls.permissions) - set(PERMISSIONS))
        if bad_perm:
            problems.append(("bad-permission",
                             f"permissions {bad_perm} outside mac.connector_permission"))
        if not isinstance(cls.supports, frozenset):
            problems.append(("supports-not-frozenset", "supports must be a frozenset"))
        unknown = sorted(set(cls.supports) - set(cls.OPTIONAL_VERBS))
        if unknown:
            problems.append(("supports-unknown-verb",
                             f"supports names verbs this contract does not define: {unknown}"))
        for verb in cls.OPTIONAL_VERBS:
            declared = verb in cls.supports
            overridden = cls.implements(verb)
            if declared and not overridden:
                problems.append(("supports-drift",
                                 f"supports claims {verb!r} but the class does not override it"))
            if overridden and not declared:
                problems.append(("supports-undeclared",
                                 f"{verb!r} is overridden but not declared in supports"))
        return problems

    @classmethod
    def implements(cls, verb: str) -> bool:
        """Is `verb` implemented here, or is the resolved method a raising backstop?

        One attribute lookup and one marker test -- see `capability_backstop` for why the marker
        sits on the function. A refinement may therefore ship a SHARED implementation of an optional
        verb (SqlConnector.profile_relation) and every subclass that inherits it is correctly read
        as implementing it.
        """
        own = getattr(cls, verb, None)
        if own is None:
            return False
        return not getattr(own, "_capability_backstop", False)


__all__ = [
    "EXIT_OK", "EXIT_FINDING", "EXIT_COULD_NOT_RUN",
    "ConnectorError", "ConnectorConfigError", "ConnectorUnavailable",
    "ConnectorCapabilityMissing", "ConnectorAmbiguous", "ConnectorContractViolation",
    "AdapterError", "AdapterErrorReason", "ADAPTER_REASON_ALIASES",
    "exit_code_for", "worst_exit",
    "RelationRef", "ColumnSpec", "RelationSchema", "ColumnStat", "RelationProfile",
    "ReadRequest", "ReadResult", "ConfigProblem", "CredentialPlan", "ProbeResult",
    "bind", "Connector", "capability_backstop", "PERMISSIONS", "PROBE_COSTS",
]
