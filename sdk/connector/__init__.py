#!/usr/bin/env python3
"""sdk.connector — the seam between MAC and data it must not know about.

RECORD: decisions/PROPOSED-2026-09-13_connector-plugin-architecture.md (TRACK B, §4).

    <data source of xy type>  --  <MAC's plug-in connector to ontology>  --  <generic ontology>

MAC owns WHAT is asked and what the answer must look like. The connector owns HOW it is asked and OF
WHOM. Every string that is SQL, every dict key that is a vendor API shape, every placeholder
convention and every module that imports a vendor driver is on the far side of this package's
`base.py`; every plan, schema, file layout, refusal and verdict stays on MAC's side of it.

THIS PACKAGE IMPORTS NO DRIVER AND NO ENGINE MODULE. `base`, `sql` and `registry` are re-exported
here; `duckdb` and `athena` are NOT, and importing this package must stay free of both. That is what
lets §6.3's mount tier validate a bundle's config on a machine where neither driver is installed --
which is the state of this host for `duckdb` (measured: `pip show duckdb` -> not found).

WHAT IS DELIBERATELY ABSENT, AND UNDER WHICH OPEN RULING:
  * ENTRY-POINT DISCOVERY, `guarded_import`, an import deadline, collision corroboration — RULING 14
    is unanswered, and on today's measurements the record's own default (§11.2) is a plain dict of
    first-party classes resolved from a shipped index. That is `registry.py`, at roughly one fifth
    of the effort. The full plugin architecture is the exception requiring a ruling, not the base
    case. `ConnectorAmbiguous` is defined anyway so the taxonomy is total on the day it lands.
  * ANY CHANGE TO WHAT `answerable` EVALUATES TO — RULING 11 is unanswered. Nothing in this package
    is imported by `sdk/container/spec.py`, reachable from `open_container()`, or registered in
    `mac_vocabulary.yaml`. It is additive and inert until something calls it.
  * ANY MOVEMENT OF CODE BETWEEN REPOSITORIES. Still none: nothing here imports, moves or deletes
    from mac-platform. But RULING 12 IS ANSWERED — one repository, several distributions — and
    with it the vocabulary question it blocked: mac_runtime's existing names are the SURVIVOR, and
    the forward-declared spellings this package coined while that ruling was open are RETIRED.
    `AdapterErrorReason` / `AdapterError` / `engine_query_id` are mac_runtime's, verbatim; they were
    `SourceErrorReason` / `SourceError` / `engine_request_id` here for exactly one day.
    `ADAPTER_REASON_ALIASES` is no longer a rename table: it now records the only difference that
    survives the rename, which is the member SET (two extensions, two retirements to exception
    classes). The names agree; the taxonomy is deliberately not identical, and it says so in place.

    WHAT WAS NOT MERGED, and the reason each pair is TWO concepts rather than one badly-named one:
      - `Connector` / `SqlConnector` are NOT `GroundingAdapter`. That protocol is two methods
        (execute, validate); this contract is nine, covering catalog enumeration, profiling, config
        validation and credential planning, none of which a GroundingAdapter has. base.py's own op
        table maps GroundingAdapter onto ops 10 and 11 only.
      - `ReadRequest` / `ReadResult` are NOT `ExecutablePlan` / `ExecutionResult`. Those carry
        ontology provenance (concepts_used / rules_used / edges_used) and a REQUIRED `sql: str`;
        these carry `limit` / `timeout_s` / `truncated` and a `body: Any` that is a CsvScan for the
        non-SQL fixture. Adopting the names without the fields would put one name on two shapes,
        which is strictly worse than two names on two shapes.
      - `read()` is NOT `execute()`, `explain()` is NOT `validate()`, `id` is NOT `kind`, and
        `assert_params_placed` is NOT `assert_bound_params_only`. Each is argued at its own site.

MODULES:
  base        the contract every source can satisfy. No SQL, no DDL, no identifier quoting.
  sql         SqlConnector — the statement-language refinement. Separate FILE so the kill criterion
              ("if Connector grows a parameter named sql, the interface is a rename of the hole")
              is an AST walk rather than a sentence.
  duckdb      a real, working, TESTED connector. Free and offline.
  athena      structurally complete and NEVER INVOKED. Its execution path in this repo is already
              dead; see that module's docstring for the measurement and the untested surface.
  registry    id -> class, from a shipped index. No entry points, no import hooks, no loader.
  fixtures    csv_dir — the NON-SQL fixture, and the only one that can falsify the interface.
  conformance the acceptance instrument: one PASS/FAIL line, a printed denominator, --self-test.
"""

from sdk.connector.base import (  # noqa: F401
    EXIT_COULD_NOT_RUN,
    EXIT_FINDING,
    EXIT_OK,
    ADAPTER_REASON_ALIASES,
    ColumnSpec,
    ColumnStat,
    ConfigProblem,
    Connector,
    ConnectorAmbiguous,
    ConnectorCapabilityMissing,
    ConnectorConfigError,
    ConnectorContractViolation,
    ConnectorError,
    ConnectorUnavailable,
    CredentialPlan,
    ProbeResult,
    ReadRequest,
    ReadResult,
    RelationProfile,
    RelationRef,
    RelationSchema,
    AdapterError,
    AdapterErrorReason,
    bind,
    capability_backstop,
    exit_code_for,
    worst_exit,
)
from sdk.connector.sql import SqlConnector  # noqa: F401

__all__ = [
    "EXIT_OK", "EXIT_FINDING", "EXIT_COULD_NOT_RUN",
    "ConnectorError", "ConnectorConfigError", "ConnectorUnavailable",
    "ConnectorCapabilityMissing", "ConnectorAmbiguous", "ConnectorContractViolation",
    "AdapterError", "AdapterErrorReason", "ADAPTER_REASON_ALIASES",
    "exit_code_for", "worst_exit",
    "RelationRef", "ColumnSpec", "RelationSchema", "ColumnStat", "RelationProfile",
    "ReadRequest", "ReadResult", "ConfigProblem", "CredentialPlan", "ProbeResult",
    "bind", "Connector", "SqlConnector", "capability_backstop",
]
