#!/usr/bin/env python3
"""
canon — the MAC canon library (the deterministic UDFs a concept's `realized_by:` names).

This is the EXECUTABLE single-home of the canon logic the reference manual documents in
reference_manual/canon/*.md. Each canon is generic and parameterized: the logic lives here ONCE; a
concept binds it to its own columns via `realized_by: { udf: mac.canon.<name>, params: {...} }`
(schema v0.1.9 — see mac.schema.json $defs/canonBinding and mac_vocabulary.yaml `canon:`).

"A canon that doesn't run is prose in a code costume" (reference_manual/04_discipline.md §4.4): every
canon here is runnable and demonstrated in tests/test_canon.py.

Two families:
  - pure (no dependency): densify, scoped_latest, closure_anomaly_check, hierarchy_rollup,
    snapshot_collapse, ambiguity_gate
  - sqlglot-backed (parse/rewrite SQL): composite_key_guard, additivity_guard, exclusion_filter,
    axis_default  — these import sqlglot lazily; calling one without sqlglot installed raises a clear
    error (the manual flags them "reference, not finished — needs a SQL parser").

The reference-manual canon/*.md files remain the prose companions (contract · honest limits · demo);
they should be kept in step with this module (or generated from it) so logic stays single-homed.

CANONS maps each registered name -> its callable; CANON_NAMES is the set check tooling resolves
`mac.canon.*` against.
"""
from __future__ import annotations

from dataclasses import dataclass

try:                              # the SQL-parsing canons need sqlglot; the pure ones do not
    import sqlglot
    from sqlglot import exp
except ImportError:               # keep the module importable; sqlglot canons error only when called
    sqlglot = None
    exp = None


def _require_sqlglot(canon: str):
    if sqlglot is None:
        raise RuntimeError(
            f"canon '{canon}' needs sqlglot to parse/rewrite SQL (a reference dependency); "
            f"install it (pip install sqlglot) to run this canon. The pure canons run without it."
        )


# ----------------------------------------------------------------------------- pure canons

def densify(fact, measure, *, keys, grid, dialect="trino"):
    """For null_semantics == genuine_zero: LEFT JOIN `fact` onto the complete `grid` of cells and COALESCE
    the measure to 0, so absent cells count as zero (not excluded). `keys` are the join columns; `grid` is a
    relation enumerating every cell that SHOULD exist. Realizes null_semantics=genuine_zero."""
    on = " AND ".join(f"g.{k} = f.{k}" for k in keys)
    sel_keys = ", ".join(f"g.{k}" for k in keys)
    return (f"SELECT {sel_keys}, COALESCE(f.{measure}, 0) AS {measure} "
            f"FROM ({grid}) g LEFT JOIN {fact} f ON {on}"), []


def scoped_latest(table, date_column, *, scope=None, dialect="trino"):
    """Return a scalar subquery for 'now' = MAX(date_column) over the SCOPED subset (e.g. scenario='ACTUAL'),
    never the whole table — so forward-dated plan/budget rows can't pose as the latest actual.
    Scope values BOUND (?), never interpolated (FRAMEWORK §6)."""
    scope = scope or {}
    where, params = "", []
    if scope:
        where = " WHERE " + " AND ".join(f"{c} = ?" for c in scope)
        params = list(scope.values())
    return f"(SELECT MAX({date_column}) FROM {table}{where})", params


def closure_anomaly_check(table, column, *, closure, known_values):
    """For a CLOSED enumeration, return the anomaly query (rows with an unknown value).
    For open/unknown closure, return None — an unseen value is expected, not an anomaly.
    Values BOUND (?), never interpolated (FRAMEWORK §6). The skeleton `closure` flag decides."""
    if closure != "closed":
        return None
    placeholders = ", ".join("?" for _ in known_values)
    sql = f"SELECT DISTINCT {column} FROM {table} WHERE {column} NOT IN ({placeholders})"
    return sql, list(known_values)


def hierarchy_rollup(table, *, id_col, parent_col, root, dialect="trino"):
    """Return a relation of `id_col` for `root` and ALL its descendants, via a recursive CTE over the
    self-referencing (id_col, parent_col) key. Root BOUND (?), never interpolated (FRAMEWORK §6).
    Realizes containment traversal: 'a node means its subtree'."""
    sql = (f"WITH RECURSIVE subtree({id_col}) AS ("
           f"SELECT {id_col} FROM {table} WHERE {id_col} = ? "
           f"UNION ALL "
           f"SELECT c.{id_col} FROM {table} c JOIN subtree s ON c.{parent_col} = s.{id_col}"
           f") SELECT {id_col} FROM subtree")
    return sql, [root]


def snapshot_collapse(table, *, natural_key, order_by, valid_from=None, valid_to=None, as_of=None):
    """Collapse a versioned relation to one row per natural_key: the version valid AS OF a bound date,
    else the latest. Values BOUND (?), never interpolated (FRAMEWORK §6). Query-shape canon."""
    if as_of is not None:
        pred = f"{valid_from} <= ? AND ({valid_to} IS NULL OR {valid_to} > ?)"
        return f"(SELECT * FROM {table} WHERE {pred})", [as_of, as_of]
    sql = (f"(SELECT * FROM (SELECT *, ROW_NUMBER() OVER "
           f"(PARTITION BY {natural_key} ORDER BY {order_by} DESC) AS _rn "
           f"FROM {table}) WHERE _rn = 1)")
    return sql, []


@dataclass
class Decision:
    action: str            # "resolve" | "ask"
    chosen: str | None
    options: list


def ambiguity_gate(term, *, candidates, pinned=None) -> Decision:
    """Deterministic ambiguity detection for competing_definitions.
    Resolve iff the question pinned a valid candidate, or exactly one candidate exists.
    Otherwise (0 or >1, unpinned) → ASK. Detecting ambiguity is mechanical; CHOOSING is interpretation."""
    if pinned and pinned in candidates:
        return Decision("resolve", pinned, candidates)
    if len(candidates) == 1:
        return Decision("resolve", candidates[0], candidates)
    return Decision("ask", None, candidates)


# ----------------------------------------------------------------------------- sqlglot-backed canons

def composite_key_guard(sql: str, *, code_column: str, scope_columns, dialect: str = "trino"):
    """Generic canon for the context_dependent_meaning pattern.
    A parent-scoped code may be CONSTRAINED or GROUPED only together with its scope columns.
    Rejects any SELECT scope that touches `code_column` without all `scope_columns` present.
    The logic lives here ONCE; a concept supplies only (code_column, scope_columns)."""
    _require_sqlglot("composite_key_guard")
    out = []
    for select in sqlglot.parse_one(sql, read=dialect).find_all(exp.Select):
        if _constrained(select, code_column):
            missing = [s for s in scope_columns if not _constrained(select, s)]
            if missing:
                out.append(f"`{code_column}` used without its scope {missing}; "
                           f"identity is ({code_column}, {scope_columns}).")
    return out


def _constrained(select, col: str) -> bool:
    """True if `col` appears in WHERE / HAVING / GROUP BY / a JOIN condition of this SELECT."""
    zones = [select.args.get("where"), select.args.get("having"), select.args.get("group"),
             *[j.args.get("on") for j in select.find_all(exp.Join)]]
    return any(any(c.name == col for c in z.find_all(exp.Column)) for z in zones if z)


NON_ADDITIVE = {"point_in_time", "non_aggregable"}


def additivity_guard(sql: str, *, measure_column: str, axis_effects, dialect: str = "trino"):
    """Generic canon for the semi_additive_balance pattern.
    axis_effects: axis column -> mac.aggregation_effect ('additive'|'point_in_time'|'non_aggregable').
    Rejects SUM(measure_column) that crosses a non-additive axis without pinning it to one value
    or grouping by it. Logic lives here once; a measure supplies (measure_column, axis_effects)."""
    _require_sqlglot("additivity_guard")
    out = []
    for select in sqlglot.parse_one(sql, read=dialect).find_all(exp.Select):
        if not _sums(select, measure_column):
            continue
        for axis, effect in axis_effects.items():
            if effect in NON_ADDITIVE and not (_pinned(select, axis) or _grouped(select, axis)):
                out.append(f"SUM(`{measure_column}`) crosses {effect} axis `{axis}`; "
                           f"pin it to one value or GROUP BY it.")
    return out


def _sums(select, col):
    return any(any(c.name == col for c in s.find_all(exp.Column))
               for s in select.find_all(exp.Sum))


def _grouped(select, col):
    g = select.args.get("group")
    return bool(g) and any(c.name == col for c in g.find_all(exp.Column))


def _pinned(select, col):
    """col = <literal / scalar subquery> in WHERE → pinned to a single value."""
    w = select.args.get("where")
    return bool(w) and any(col in {c.name for c in eq.find_all(exp.Column)}
                           for eq in w.find_all(exp.EQ))


def exclusion_filter(sql: str, *, column: str, not_in=None, not_like=None, dialect: str = "trino"):
    """Inject an exclusion predicate removing reliably-identifiable junk on `column` (the BAKE disposition).
    Values BOUND (?), never interpolated (FRAMEWORK §6). Transform canon — it rewrites the query."""
    _require_sqlglot("exclusion_filter")
    not_in, not_like = not_in or [], not_like or []
    conds, params = [], []
    if not_in:
        conds.append(f"{column} NOT IN ({', '.join('?' for _ in not_in)})")
        params += list(not_in)
    conds += [f"{column} NOT LIKE ?" for _ in not_like]
    params += list(not_like)
    if not conds:
        return sql, []
    top = sqlglot.parse_one(sql, read=dialect).find(exp.Select)
    top = top.where(" AND ".join(conds), append=True, dialect=dialect)
    return top.sql(dialect=dialect), params


def axis_default(sql: str, *, axis_column: str, default_value, dialect: str = "trino"):
    """If the query does not constrain `axis_column`, inject `axis_column = ?` bound to default_value.
    The value is BOUND, never interpolated (FRAMEWORK §6). Transform canon — it rewrites the query."""
    _require_sqlglot("axis_default")
    tree = sqlglot.parse_one(sql, read=dialect)
    top = tree.find(exp.Select)
    where = top.args.get("where")
    present = bool(where) and any(c.name == axis_column for c in where.find_all(exp.Column))
    if present:
        return sql, []
    top = top.where(f"{axis_column} = ?", append=True, dialect=dialect)
    return top.sql(dialect=dialect), [default_value]


# ----------------------------------------------------------------------------- registry

CANONS = {
    "densify": densify,
    "scoped_latest": scoped_latest,
    "closure_anomaly_check": closure_anomaly_check,
    "hierarchy_rollup": hierarchy_rollup,
    "snapshot_collapse": snapshot_collapse,
    "ambiguity_gate": ambiguity_gate,
    "composite_key_guard": composite_key_guard,
    "additivity_guard": additivity_guard,
    "exclusion_filter": exclusion_filter,
    "axis_default": axis_default,
}

# the canons that need sqlglot (skipped by tests when it is absent)
NEEDS_SQLGLOT = {"composite_key_guard", "additivity_guard", "exclusion_filter", "axis_default"}

CANON_NAMES = frozenset(CANONS)
