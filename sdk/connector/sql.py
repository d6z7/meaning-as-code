#!/usr/bin/env python3
"""sql.py — `SqlConnector`: everything true only of a source you address in a statement language.

RECORD: §4.2 ("the dry half / wet half split — the invariant that must survive"), §4.5.

WHY THIS IS A SEPARATE MODULE FROM base.py. The record's §4.2 sketch drew `Connector` and
`SqlConnector` in one file. Splitting them is this package's one deliberate deviation, and it buys
exactly one thing: the kill criterion becomes MECHANICAL. `conformance.py` K2 walks base.py's AST
and fails if any identifier there is named `sql`, `statement`, `query`, `ddl` or `view`. In a single
file that check is impossible to write, and the criterion the record calls decisive
("if `Connector` grows a parameter named `sql`, the interface is a rename of the hole") would have
stayed what it has been since the first draft: a sentence.

WHAT LANDS HERE, AND WHY EACH ONE WOULD BE A DEFECT ONE LEVEL UP. The first draft put
`quote_identifier`, `qualify`, `render_view_ddl` and `render_profile_sql` in the REQUIRED tier of
the generic base, so a connector to a source with no DDL and no identifier quoting had to implement
view-DDL rendering in order to conform. Its one required I/O verb was `read(self, sql: str, ...)` --
the parameter literally named `sql`. That is the hole this module exists to keep base.py out of.

THE DRY HALF IS THE POINT. `render_view_ddl`, `render_profile_sql`, `quote_identifier` and `qualify`
are PURE: no socket, no driver, no credential. `materialize.plan_materialization()` and
`plan_lookups()` are pure today and test_harvest_hardening.py proves it offline; an interface that
loses that is a regression however clean it looks. So the wet verbs here are thin: each is a pure
render followed by `read()`.

WHAT THIS MODULE STILL DOES NOT DO: own a placeholder syntax on MAC's behalf. `param_style` is the
CONNECTOR's declaration. `assert_bound_params_only` stays in `mac_runtime.adapters` as the Athena
adapter's own precondition -- not promoted, not duplicated (§4.2a).

VOCABULARY, AFTER THE CONSOLIDATION RULING (mac_runtime's names are the survivor). The error
taxonomy this module raises is mac_runtime's verbatim now -- `AdapterError`, `AdapterErrorReason`,
`engine_query_id`; the `SourceError` spelling is gone. What did NOT collapse, and why each is two
concepts rather than one misnamed one:
  * `assert_params_placed` (here) is NOT `assert_bound_params_only` (mac_runtime.adapters.safety).
    Measured check for check: that function runs THREE -- (1) no single-quoted literal anywhere in
    the statement, (2) no placeholder without a param, (3) no param without a placeholder. This
    method runs (3) ALONE. (2) is unenforceable here without a parse, and (1) is the check whose
    quoted-literal scan makes `date '2024-01-01'` and `read_csv('a.csv')` illegal -- see
    `assert_params_placed`'s own docstring for the DuckDB 1.5.5 measurement. One check is not the
    same obligation as three, and the honest name for a one-check assertion is not the name of the
    three-check one.
  * `explain` (here) is NOT `validate` -- argued at that method.
"""

from __future__ import annotations

import abc
import re
from typing import Any, ClassVar, Mapping, Sequence

from sdk.connector.base import (
    EXIT_COULD_NOT_RUN,
    EXIT_OK,
    ColumnSpec,
    ColumnStat,
    Connector,
    ConnectorContractViolation,
    ReadRequest,
    ReadResult,
    RelationProfile,
    RelationRef,
    RelationSchema,
    capability_backstop,
)

#: The verbs a statement-language source considers read-only, as a DEFAULT a connector may narrow or
#: widen. It is a ClassVar and not a module constant because "is SHOW read-only" is an engine's
#: answer, not MAC's.
_DEFAULT_READ_VERBS = ("select", "with", "show", "describe", "desc", "explain", "values", "table")

#: Strips leading line comments and whitespace so the head verb of a statement can be read without a
#: parser. Deliberately NOT a SQL parser: this finds the first word, nothing more.
_LEADING_NOISE = re.compile(r"^(?:\s|--[^\n]*\n|/\*.*?\*/)+", re.S)


class SqlConnector(Connector):
    """A source addressed in a statement language. Athena and DuckDB subclass THIS.

    A CSV-directory connector subclasses `Connector` and never sees one line of this module -- which
    is the acceptance test the whole design turns on (§3.2: "two SQL engines can detect an AWS
    assumption and are structurally incapable of detecting a SQL assumption").
    """

    #: The connector's own read-verb vocabulary, enforced in its own `read()` (§4.2a).
    read_verbs: ClassVar[tuple] = _DEFAULT_READ_VERBS

    #: The CONNECTOR's placeholder convention -- ":name", "?", "$1", "$name". MAC owns none of these.
    #:
    #: CONFIRMED AGAINST mac_runtime, 2026-09-13, and the DEFAULT BELOW ALREADY AGREED -- there was
    #: nothing to rename here. mac_runtime pins `:name` in three independent places, which is why it
    #: is the survivor and the default: `planner/templates.py::bind_positional_placeholders` emits
    #: `f":{name}"`, `adapters/safety.py::_PLACEHOLDER_RE` is `:([a-zA-Z_][a-zA-Z0-9_]*)`, and
    #: `adapters/athena.py::_PARAM_TOKEN_RE` is the same pattern again. Its own docstring still calls
    #: that choice unpinned by the spec ("04 §3/§4 mandate bound params but do not pin a placeholder
    #: syntax"); the ruling pins it de facto, as the emitted form of every plan the planner produces.
    #:
    #: THE FIELD STAYS, because agreeing with a default is not the same as inheriting it. This is the
    #: one place a connector states its own convention, and one already differs: DuckDB declares
    #: `$name` (measured against duckdb 1.5.5). THAT IS A LIVE INCONSISTENCY AND NOT A RENAME -- a
    #: plan the mac_runtime planner emitted in `:name` form cannot be bound by a connector whose
    #: engine spells placeholders `$name`, so a consolidated runtime must re-spell at the seam (the
    #: connector's `placeholder()`, below, is the only function that knows how) rather than assume
    #: the planner's form reaches every engine intact.
    param_style: ClassVar[str] = ":name"

    #: §4.5: `create_or_replace_view` is the ONLY write verb, and it lives HERE, not on `Connector`.
    #: Deliberately not `execute_write(sql)`: a generic write verb re-opens the 2026-08-13 gold
    #: overwrite on every connector including third-party ones, and it makes "can this connector
    #: write?" a property of a string the caller passed -- so nothing can gate it and nothing can
    #: answer it offline. Today's hybrid `executor(sql)` dispatching on `is_read_only(sql)`
    #: (materialize.py:298) has exactly that shape and is retired by this split.
    OPTIONAL_VERBS: ClassVar[tuple] = Connector.OPTIONAL_VERBS + (
        "create_or_replace_view",
        "explain",
    )

    DEGRADATION: ClassVar[Mapping[str, tuple]] = {
        **Connector.DEGRADATION,
        "create_or_replace_view": (
            "materializable",
            "dry-run still works (the planner is pure); --accept refuses",
            EXIT_COULD_NOT_RUN,
        ),
        "explain": (
            "plan pre-validation",
            "validate() is a no-op; the trace records 'validated: false'",
            EXIT_OK,
        ),
    }

    # ---- DRY: pure. No socket, no driver, no credential. ----

    def quote_identifier(self, name: str) -> str:
        """SQL-standard quoting: wrap in double quotes, DOUBLE any embedded quote.

        A MEASURED DEFECT THIS FIXES, recorded because the connector seam is where it stops being
        repeated. data_plane.py:229 builds its profile identifiers as

            q = '"' + c["name"].replace('"', "") + '"'

        which DELETES an embedded quote instead of doubling it: a column named  a"b  is addressed as
        "ab", a different identifier. The failure is silent in both directions -- either the column
        does not exist and the whole profile scan fails for a reason that names the wrong column, or
        (worse) "ab" exists and the profile reports another column's null rate under this one's name.
        Doubling is the standard escape and both engines in scope accept it.

        Overridable: an engine that quotes with backticks says so here, and nothing above it changes.
        """
        return '"' + str(name).replace('"', '""') + '"'

    def qualify(self, ref: RelationRef) -> str:
        """Namespace segments -> a quoted, dotted engine address. Pure.

        This is the verb that lets `render_view_ddl` stay ignorant of what a "database" is (§5.5),
        and it is why a two-handle warehouse and a single-namespace engine differ by the LENGTH of a
        list rather than by a branch in MAC.
        """
        return ".".join(self.quote_identifier(s) for s in ref.segments)

    def render_view_ddl(self, ref: RelationRef, select_body: str) -> str:
        """Pure. The DDL text for op 8 -- rendered here, executed (if at all) by the wet verb.

        THE LIMIT, stated plainly because the contract cannot enforce it (§4.5): this hands the
        connector a SELECT body it composes into DDL, and a careless connector can append anything.
        `materialize.assert_own_schema` guards the TARGET, not the body, and it STAYS IN MAC -- "a
        source materializes only into its own namespace" is a policy about ontologies, not about one
        engine. If it followed the SQL down here, a DuckDB bundle would get no guardrail and the
        2026-08-13 incident would be reachable again on a second engine. DDL through a third-party
        connector is a trust decision, not a technical guarantee.
        """
        return f"CREATE OR REPLACE VIEW {self.qualify(ref)} AS\n{select_body.strip()}"

    # The two engine-specific hooks the shared profile renderer needs. They exist so that ONE
    # profile renderer serves every SQL engine: everything else in that statement is standard.
    def approx_distinct_fn(self) -> str:
        """The engine's approximate-distinct function name."""
        return "approx_distinct"

    def cast_to_text(self, expr: str) -> str:
        """Wrap `expr` in the engine's non-throwing cast to a text type."""
        return f"try_cast({expr} as varchar)"

    def orderable(self, engine_type: str) -> bool:
        """Does a MIN/MAX over this VERBATIM engine type mean anything? The CONNECTOR's verdict.

        This method is why MAC never parses a type name again, and it retires data_plane.py:48-58
        `_ORDERABLE` -- eleven Hive/Presto type names sitting in the generic instrument, applied to
        every engine the SDK might ever reach. Abstract on purpose: a type vocabulary has no
        engine-neutral default, and a wrong default here is a silently wrong profile rather than an
        error.
        """
        raise NotImplementedError("a SQL connector must give its own verdict on its own type names")

    def render_profile_sql(self, ref: RelationRef, cols: Sequence[ColumnSpec]) -> str:
        """Pure. ONE statement producing op 5's counts. Structurally identical to profile_table.

        Kept structurally identical to data_plane.profile_table's statement (count(*), count(col),
        approx-distinct per column, min/max per ORDERABLE column) so that routing profiling through
        a connector is a change of address and not a change of numbers. The two engine-specific
        pieces -- the approximate-distinct function name and the non-throwing cast -- are the only
        hooks, which is the measured extent of the difference between the two engines in scope.

        `distinct` IS AN ESTIMATE AND MAY EXCEED `row_count`. MEASURED 2026-09-13 against a real
        DuckDB bundle: column ProductKey over 2517 rows, min 1, max 2517 -- a dense unique key --
        profiled as distinct = 2558, i.e. 101.6% of the rows. That is ordinary HyperLogLog error,
        not a defect, and it is recorded HERE because this number is fed verbatim into the model
        prompt that authors DQ findings (data_plane._profile_md). A consumer that reads
        distinct > row_count as evidence of anything -- a duplicate key, a grain violation -- is
        reading noise as a finding. An exact count(DISTINCT) was NOT substituted: it is the
        expensive scan the approximation exists to avoid, and on a billed engine that choice costs
        money per column per harvest.
        """
        sel = ["count(*) n"]
        for i, c in enumerate(cols):
            q = self.quote_identifier(c.name)
            sel += [f"count({q}) nn{i}", f"{self.approx_distinct_fn()}({q}) d{i}"]
            if self.orderable(c.type):
                sel += [f"{self.cast_to_text(f'min({q})')} mn{i}",
                        f"{self.cast_to_text(f'max({q})')} mx{i}"]
        return f"SELECT {', '.join(sel)} FROM {self.qualify(ref)}"

    # ---- the read contract: shared enforcement, engine-specific execution ----

    def read(self, request: ReadRequest) -> ReadResult:
        """The CONNECTOR's half of §4.2a, written once for every SQL engine, then `_execute`.

        Two preconditions, both the connector's to hold because both are about ITS dialect:
          1. the head verb is in `read_verbs` -- `read()` is read-only, and the one write verb is
             `create_or_replace_view`, which is a different method with a different guard;
          2. every declared parameter actually appears as a placeholder in `param_style`.

        A violation is `ConnectorContractViolation` (exit 1, loudly), never a degradation: the caller
        broke the contract, and softening that is how an interpolated value reaches a warehouse.
        """
        body = request.body
        if not isinstance(body, str):
            raise ConnectorContractViolation(
                f"{self.id}: a SQL connector's request body must be a statement string, got "
                f"{type(body).__name__}"
            )
        verb = self.head_verb(body)
        if verb not in self.read_verbs:
            raise ConnectorContractViolation(
                f"{self.id}: read() received the verb {verb!r}, which is not in read_verbs "
                f"{tuple(self.read_verbs)}"
            )
        self.assert_params_placed(body, request.params)
        return self._execute(body, dict(request.params), limit=request.limit,
                             timeout_s=request.timeout_s)

    @classmethod
    def head_verb(cls, body: str) -> str:
        """The first word, after leading whitespace and leading comments. NOT a parser.

        A leading comment is stripped because a statement that begins `-- built by materialize\\n
        SELECT ...` is a SELECT, and a head-verb check that calls it `--` would reject the correct
        pattern. Anything beyond that is the engine's own business.
        """
        cleaned = _LEADING_NOISE.sub("", body or "")
        head = cleaned.strip().split(None, 1)
        return head[0].lower().strip("(") if head else ""

    def assert_params_placed(self, body: str, params: Mapping[str, Any]) -> None:
        """Every declared parameter appears in the statement, spelled in THIS connector's style.

        WHAT THIS DELIBERATELY DOES NOT DO, and the measurement that decided it. The obvious check is
        the mirror: scan for placeholders of a FOREIGN style and reject them. Measured against DuckDB
        1.5.5, that check is unsafe in both directions:

          * `SELECT x::INTEGER FROM t` is ordinary DuckDB. A `:(\\w+)` scanner reads `:INTEGER` as a
            named placeholder and rejects a legal cast.
          * `SELECT '?' AS q` and `read_csv('a?b.csv')` put a `?` inside a string literal, so a
            positional-style scanner rejects those too -- which is the same defect
            `_QUOTED_STRING_RE` already has in mac_runtime/adapters/safety.py, arriving from the
            opposite direction.

        A scanner that must not read string literals is a scanner that must parse, and MAC does not
        parse SQL (§4.2a). So the check is the narrow one that needs no parse: what the caller
        DECLARED must be findable. It catches the real case -- a parameter that was bound but never
        placed, i.e. a value that got formatted into the statement instead -- and it claims nothing
        about values it cannot see.
        """
        missing = [k for k in params if self.placeholder(k) not in body]
        if missing:
            raise ConnectorContractViolation(
                f"{self.id}: parameter(s) {sorted(missing)} were bound but do not appear in the "
                f"statement in this connector's param_style {self.param_style!r}; a value bound but "
                f"not placed is a value that was formatted in"
            )

    def placeholder(self, name: str) -> str:
        """How this connector spells a bound parameter named `name`."""
        style = self.param_style
        if style == ":name":
            return f":{name}"
        if style == "$name":
            return f"${name}"
        if style == "?":
            # Positional styles cannot be located by name, so the placement check above is vacuous
            # for them and must SAY so rather than pass silently -- a check that cannot fire is the
            # zero-denominator defect in miniature.
            raise ConnectorContractViolation(
                f"{self.id}: param_style '?' is positional; placement cannot be checked by name. "
                f"Declare a named style, or override assert_params_placed with a check that fires."
            )
        raise ConnectorContractViolation(f"{self.id}: unknown param_style {style!r}")

    @abc.abstractmethod
    def _execute(
        self,
        body: str,
        params: Mapping[str, Any],
        *,
        limit: int | None = None,
        timeout_s: float | None = None,
    ) -> ReadResult:
        """Run one read-only statement with BOUND params. The only engine-specific I/O a SQL
        connector must write. Raises AdapterError with a typed reason; never returns a partial result
        without setting `truncated`."""

    # ---- shared optional verbs: a pure render plus one read ----

    def profile_relation(self, ref: RelationRef, cols: Sequence[ColumnSpec]) -> RelationProfile:
        """Op 5 for ANY SQL engine: render (pure) + one read + the exact shape data_plane expects.

        Shared rather than per-engine because the difference between the two engines in scope is two
        function names (see the hooks above), and a per-engine copy of this arithmetic is how the
        `min`/`max`-present-or-absent convention drifts between connectors and starts writing the
        string "None" into a model's profile table.
        """
        res = self.read(ReadRequest(body=self.render_profile_sql(ref, cols), purpose="profile"))
        row = dict(res.rows[0]) if res.rows else {}
        n = int(row.get("n") or 0)
        out: dict = {}
        for i, c in enumerate(cols):
            nn = int(row.get(f"nn{i}") or 0)
            has_ext = f"mn{i}" in row
            out[c.name] = ColumnStat(
                # round(...) to 4 places and the n==0 -> None convention are data_plane's, kept
                # byte-for-byte so a profile does not change value when it changes address.
                null_frac=round(1 - nn / n, 4) if n else None,
                distinct=int(row.get(f"d{i}") or 0),
                min=row.get(f"mn{i}"),
                max=row.get(f"mx{i}"),
                has_extremes=has_ext,
            )
        return RelationProfile(row_count=n, columns=out)

    # ---- optional verbs whose backstops belong to this tier ----

    @capability_backstop
    def explain(self, body: str, params: Mapping[str, Any] | None = None) -> None:
        """Op 10. Dry-run / EXPLAIN. MUST NOT mutate the data plane and MUST NOT return rows.

        Absent, `validate()` is a no-op and the trace records `validated: false` -- exit 0, printed.

        NOT RENAMED TO mac_runtime's `GroundingAdapter.validate`, and this is the CLOSEST call of the
        reconciliation -- the two docstrings are near-verbatim ("Dry-run / EXPLAIN ... MUST NOT
        mutate the data plane or return rows"), and base.py's own op table pairs them. It was left
        alone for two reasons:
          * THE TWO NAMES SIT AT TWO LAYERS, and this package already says so: the DEGRADATION entry
            for `explain` reads "validate() is a no-op". `validate()` is the CALLER's verb, whose
            absence-behaviour is defined in terms of this connector capability backing it.
            Collapsing them deletes the distinction that entry is written in.
          * `validate` WOULD SIT BESIDE `validate_config`, MEANING SOMETHING ELSE. `validate_config`
            is offline, free, returns findings and never raises; this is wet, billed on Athena, and
            raises. Two methods one underscore apart with opposite cost and opposite failure
            conventions is a footgun neither name had before.
        If a later ruling merges them the surviving name is `validate` and the rename is mechanical:
        this method, `OPTIONAL_VERBS`, `DEGRADATION`, both connectors' `supports`, and
        `conformance.SQL_TIER_NAMES`. Recorded as debt, not resolved by guess.
        """
        from sdk.connector.base import ConnectorCapabilityMissing

        raise ConnectorCapabilityMissing(self.id, "explain")

    @capability_backstop
    def create_or_replace_view(self, ref: RelationRef, select_body: str) -> None:
        """Op 8, and the ONLY write verb in this contract. Off by default (§4.5).

        `allow_ddl` defaults to false and lives only in the deployment overlay, so a published,
        shipped bundle can never be used to write. A connector that implements this MUST check that
        its own configuration permits a write before issuing one.
        """
        from sdk.connector.base import ConnectorCapabilityMissing

        raise ConnectorCapabilityMissing(self.id, "create_or_replace_view")

    # `describe_relation` / `list_relations` / `list_objects` are NOT shared here: every SQL engine
    # answers them from a different catalog surface (information_schema, SHOW, a Glue API call), and
    # a "shared" implementation would be a guess about which one, wearing generic clothes.


__all__ = ["SqlConnector", "RelationSchema", "ColumnSpec"]
