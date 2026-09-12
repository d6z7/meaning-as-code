"""sdk.acceptance.sqlfacts — source-agnostic structural facts about executed SQL statements.

WHAT THIS IS FOR
    The acceptance ``pins`` flag asks one question of a capture: were the reading axes the oracle
    names actually CONSTRAINED in the statement that computed the answer? That is a question about
    the SQL, not about the prose, so it is answered by parsing the SQL. This module is the fact
    sheet; it renders no judgement. ``flags.py`` decides what the facts mean.

WHY A FACT SHEET AND NOT A CHECKER
    The facts here are neutral: "``x`` appears in a WHERE equality", "``y`` appears in a window's
    ORDER BY". Which of those SATISFIES a pin is a policy decision, and policy that lives next to
    parsing gets quietly widened whenever a check goes red. Keeping the seam means a widening has
    to be argued in ``flags.py``, where the rollup rules are written down.

NO BUNDLE LITERALS, EVER
    Not one column name, relation name, brand letter or question id appears in the CODE below. The
    vocabulary of what to look for arrives at runtime from the bundle's own oracles
    (``expected.must_pin``). A framework that knows one source's column names is not a framework.
    Where the prose here cites a measured count or a file from one bundle, that is historical
    evidence for a rule — no code path reads it, and swapping the source does not touch this file.

THE MEASURED TRAP THIS MODULE EXISTS TO AVOID  (do not "simplify" the role table)
    A checker that reads only ``WHERE`` false-reds roughly half the corpus, because the prescribed
    way to pin the snapshot vintage is NOT an equality predicate. Measured against the 24 committed
    captures, the engine pins it in two forms, both correct and both prescribed by
    ``ontology/protosql/snapshot.pin_latest_per_cell.yaml`` (which explicitly FORBIDS a scalar MAX
    over the whole fact and requires the per-cell latest vintage):

      1. ``ROW_NUMBER() OVER (PARTITION BY <cell key> ORDER BY <vintage> DESC) ... WHERE rn = 1``
         — the vintage column sits in the window's **ORDER BY**, never in its PARTITION BY.
         Reading ``partition_by`` alone marked 8 of 20 questions as failing a flag they satisfy.
      2. a ``JOIN`` back to a ``MAX(<vintage>)`` CTE — the equality lives in ``JOIN ... ON``, and
         the vintage is additionally the argument of ``MAX``.

    That is why ``collapsed`` covers BOTH a window ORDER BY and a MAX/MIN argument, and why
    ``joined`` covers JOIN..ON equality. The corpus's flagship question (whose answer is
    independently known correct) fails a naive WHERE-only check on exactly this axis.

SCOPE OF A STATEMENT
    Roles are computed over the WHOLE statement AST **including its CTEs**. Every CTE in this
    corpus is defined in the same statement that uses it, so no cross-statement name resolution is
    attempted — and none is faked. Column names are reduced to their bare identifier (qualifier
    stripped, lowercased), because an oracle names an axis, not a table alias.

Depends only on ``sqlglot``. Pure: no filesystem, no network, no clock.
"""

from __future__ import annotations

# The dialect the engine actually executes against (Athena/Trino). Callers may override per call;
# nothing here is dialect-specific beyond the parse itself.
DIALECT = "trino"

# The complete vocabulary of structural roles a column may carry in one statement. Frozen: it is
# read by `flags.py` (which decides which subset SATISFIES a pin) and rendered by the detail page's
# per-statement fact chips. Adding a role here without deciding its policy in flags.py is how a
# fact silently becomes an exoneration.
ROLES = ("filtered", "joined", "grouped", "collapsed", "aggregated", "projected")

try:  # pragma: no cover - exercised by whichever environment lacks the dependency
    import sqlglot
    from sqlglot import exp

    _IMPORT_ERROR: str | None = None
except Exception as _e:
    sqlglot = None  # type: ignore[assignment]
    exp = None  # type: ignore[assignment]
    _IMPORT_ERROR = f"{type(_e).__name__}: {_e}"


def available() -> bool:
    """True iff ``sqlglot`` imported successfully.

    ``flags.py`` calls this BEFORE parsing so the ``pins`` flag can degrade to ``unchecked`` with
    an honest reason. Absence of the parser is an incomplete fact sheet, and an incomplete fact
    sheet can neither exonerate nor convict — it must never read as ``pass`` and never as ``fail``.
    """
    return sqlglot is not None


# --------------------------------------------------------------------------- #
# AST predicates, resolved lazily so this module still imports without sqlglot
# --------------------------------------------------------------------------- #


def _predicate_types() -> tuple:
    """Comparison / membership operators that count as constraining an operand.

    Exactly the set named in the spec: ``=  <>  >  >=  <  <=  IN  BETWEEN  LIKE``. Deliberately
    NOT widened (no ILIKE, no IS NULL, no function-call predicates): every operator added here can
    only turn a red into a green, so widening is the one direction that manufactures false
    confidence. ``IS NOT NULL`` is handled separately below because sqlglot models it as a NOT
    wrapping an IS, not as a comparison operator.
    """
    return (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.In, exp.Between, exp.Like)


def _agg_types() -> dict:
    """sqlglot node class -> the aggregate name reported in ``aggregates``."""
    return {exp.Sum: "SUM", exp.Avg: "AVG", exp.Count: "COUNT", exp.Min: "MIN", exp.Max: "MAX"}


# Containers that decide WHICH role a predicate confers. `Join` first is not an ordering
# requirement (find_ancestor returns the nearest match regardless) but records the intent: a
# predicate in `JOIN ... ON` is a join key, the same predicate in `WHERE` is a filter, and the two
# must not be conflated — the vintage pin uses the first form, the dimension pins use the second.
def _container_types() -> tuple:
    return (exp.Join, exp.Where, exp.Having, exp.Qualify)


# --------------------------------------------------------------------------- #
# Column-name reduction and operand traversal
# --------------------------------------------------------------------------- #


def _bare(column) -> str | None:
    """A column reference reduced to its bare lowercase identifier.

    ``k.config_reporting_month`` and ``"F"."config_reporting_month"`` both reduce to
    ``config_reporting_month``, because an oracle names a reading AXIS and has no opinion about
    which alias the engine happened to choose. ``t.*`` carries no identifier and is dropped.
    """
    name = getattr(column, "name", None)
    if not isinstance(name, str):
        return None
    name = name.strip().lower()
    if not name or name == "*":
        return None
    return name


def _operand_walk(node):
    """Depth-first over ``node`` in source order, NOT descending into a nested query.

    Pruning at a nested SELECT/subquery is what keeps "operand of" honest. In
    ``x IN (SELECT y FROM t WHERE z = 1)`` only ``x`` is an operand of the IN; ``y`` and ``z``
    belong to the inner query and are scored on their OWN container by the caller's full-tree
    walk, which visits that inner WHERE in its own right. Without the prune, a pin column that
    merely appears in a subquery's projection would be credited as filtered by the outer
    predicate — a green bought with a coincidence.
    """
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        children = [
            c
            for c in n.iter_expressions()
            if not isinstance(c, (exp.Subquery, exp.Select, exp.SetOperation))
        ]
        stack.extend(reversed(children))  # reversed => LIFO stack pops in source order


def _operand_columns(node):
    """The column references that are operands of ``node`` (see ``_operand_walk``)."""
    for n in _operand_walk(node):
        if isinstance(n, exp.Column):
            yield n


def _has_star(node) -> bool:
    """True when ``node``'s own operands include ``*`` (``COUNT(*)``, ``COUNT(t.*)``)."""
    return any(isinstance(n, exp.Star) for n in _operand_walk(node))


def _outermost_selects(root) -> list:
    """The SELECT(s) whose projection list is what the STATEMENT returns.

    A CTE's projection is not the statement's output, so ``projected`` deliberately does not
    reach into ``WITH`` — sqlglot hangs the WITH clause off the outer Select's args rather than
    off its ``expressions``, so simply reading ``expressions`` gets this right. A set operation
    contributes every branch, because each branch projects part of the same result.
    """
    if isinstance(root, exp.Select):
        return [root]
    if isinstance(root, exp.SetOperation):
        out: list = []
        for side in (root.this, root.expression):
            if side is not None:
                out.extend(_outermost_selects(side))
        return out
    if isinstance(root, exp.Subquery):
        inner = root.this
        return _outermost_selects(inner) if inner is not None else []
    return []  # DDL, SHOW, DESCRIBE, ... — nothing is projected


def _is_not_null(node) -> bool:
    """True when ``node`` is the ``NOT (x IS NULL)`` shape sqlglot builds for ``x IS NOT NULL``."""
    if not isinstance(node, exp.Not):
        return False
    inner = node.this
    return isinstance(inner, exp.Is) and isinstance(inner.expression, exp.Null)


# --------------------------------------------------------------------------- #
# The fact extractor
# --------------------------------------------------------------------------- #


def _facts(root) -> tuple[dict, list, list]:
    """``(roles, aggregates, relations)`` for one parsed statement. Assumes sqlglot is present."""
    roles: dict[str, set] = {}

    def mark(column, role: str) -> None:
        name = _bare(column)
        if name:
            roles.setdefault(name, set()).add(role)

    def mark_operands(node, role: str) -> None:
        for column in _operand_columns(node):
            mark(column, role)

    predicates = _predicate_types()
    containers = _container_types()
    aggs_by_type = _agg_types()
    aggregates: list[dict] = []

    # ONE walk over the whole tree, CTEs included. Every node is scored on the container it
    # actually sits in, which is what makes a `GROUP BY` inside a CTE count for that statement and
    # for no other.
    for node in root.walk():
        # --- filtered / joined -------------------------------------------------------------
        if isinstance(node, predicates) or _is_not_null(node):
            container = node.find_ancestor(*containers)
            if isinstance(container, exp.Join):
                # Only an EQUALITY join key constrains a column to another column's value; an
                # inequality join (`a.d > b.d`) narrows a range and is not a pin.
                if isinstance(node, exp.EQ):
                    mark_operands(node, "joined")
            elif container is not None:
                mark_operands(node, "filtered")

        # --- grouped / collapsed via a window ----------------------------------------------
        elif isinstance(node, exp.Window):
            for part in node.args.get("partition_by") or []:
                mark_operands(part, "grouped")
            order = node.args.get("order")
            if order is not None:
                # THE MEASURED TRAP: the prescribed vintage pin puts the column HERE, in the
                # window's ORDER BY, and never in its PARTITION BY. Reading partition_by alone
                # false-failed 8 of 20 captured questions. Read from `node.args`, never by
                # searching for Order nodes — a statement-level `ORDER BY value DESC` is also an
                # Order node and collapses nothing.
                mark_operands(order, "collapsed")

        # --- grouped via GROUP BY ------------------------------------------------------------
        elif isinstance(node, exp.Group):
            mark_operands(node, "grouped")

        # --- aggregated (+ collapsed for MIN/MAX) --------------------------------------------
        kind = aggs_by_type.get(type(node))
        if kind:
            args: list[str] = []
            for column in _operand_columns(node):
                name = _bare(column)
                if not name:
                    continue
                mark(column, "aggregated")
                if kind in ("MIN", "MAX"):
                    # The OTHER prescribed vintage pin: `MAX(<vintage>)` in a CTE the answering
                    # statement joins back to. The column is resolved to a single value per cell,
                    # which is exactly what "pinned" means, so it collapses.
                    mark(column, "collapsed")
                if name not in args:
                    args.append(name)
            aggregates.append({"func": kind, "args": args, "star": _has_star(node)})

    # --- projected -------------------------------------------------------------------------
    for select in _outermost_selects(root):
        for projection in select.expressions:
            mark_operands(projection, "projected")

    relations = sorted(
        {
            t.name.strip().lower()
            for t in root.find_all(exp.Table)
            if isinstance(getattr(t, "name", None), str) and t.name.strip()
        }
    )

    return ({k: sorted(v) for k, v in sorted(roles.items())}, aggregates, relations)


def _one_line(text: str) -> str:
    """sqlglot's parse errors are multi-line with a caret ruler; a flag ``reason`` is one line."""
    return " ".join(str(text).split())[:400]


def parse_statements(sql_list, dialect: str = DIALECT) -> list[dict]:
    """Structural facts for each non-empty statement in ``sql_list``.

    Returns, per statement::

        {
          "index":      int,          # position in the ORIGINAL list
          "sql":        str,          # verbatim, unformatted
          "ok":         bool,
          "error":      str | None,   # one-line sqlglot message when ok is False
          "roles":      {str: [str]}, # bare lowercase column name -> sorted subset of ROLES
          "aggregates": [{"func": "SUM"|"AVG"|"COUNT"|"MIN"|"MAX",
                          "args": [str],   # bare column names; [] for COUNT(*)
                          "star": bool}],
          "relations":  [str],        # bare table/view names referenced, sorted and deduped
        }

    Empty and whitespace-only statements are skipped ENTIRELY — they are not returned. ``index``
    therefore equals the position in the list that was passed in, which is not necessarily the
    position in the returned list. Callers that index the returned list by an ``index`` value (as
    ``flags.py`` does, via ``answering_indexes``) must pass a list that has already had its blanks
    removed; ``flags.py`` does exactly that when it computes ``n_sql``.

    THIS FUNCTION NEVER RAISES. A statement sqlglot rejects — or one whose AST has a shape the
    extractor does not anticipate — comes back ``ok=False`` with a message and empty facts. That
    is deliberate and load-bearing: the ``pins`` flag maps a parse failure to ``unchecked``, never
    to ``pass`` and never to ``fail``. An incomplete fact sheet cannot exonerate and cannot
    convict, and a checker that crashes on one odd statement takes the whole board down with it.
    """
    if not isinstance(sql_list, (list, tuple)):
        return []

    out: list[dict] = []
    for index, raw in enumerate(sql_list):
        if not isinstance(raw, str) or not raw.strip():
            continue

        record = {
            "index": index,
            "sql": raw,
            "ok": False,
            "error": None,
            "roles": {},
            "aggregates": [],
            "relations": [],
        }

        if sqlglot is None:
            record["error"] = f"sqlglot is unavailable ({_IMPORT_ERROR})"
            out.append(record)
            continue

        try:
            tree = sqlglot.parse_one(raw, read=dialect)
        except Exception as err:
            record["error"] = _one_line(str(err) or type(err).__name__)
            out.append(record)
            continue

        if tree is None:
            record["error"] = "sqlglot parsed no expression from this statement"
            out.append(record)
            continue

        try:
            roles, aggregates, relations = _facts(tree)
        except Exception as err:
            # Not `ok`: we parsed it but cannot describe it, so we know nothing about its pins.
            # Reporting ok=True with partial facts would let a missing role read as a real miss.
            record["error"] = f"fact extraction failed: {_one_line(str(err) or type(err).__name__)}"
            out.append(record)
            continue

        record.update(ok=True, roles=roles, aggregates=aggregates, relations=relations)
        out.append(record)

    return out


def answering_indexes(stmts: list[dict], pin_columns) -> list[int]:
    """The statements whose pins are worth grading — the ones that COMPUTE a measure.

    A capture is a transcript, not a query: the engine typically probes the dimensions first
    (``SELECT DISTINCT ...``, ``COUNT(*) ...``, a LIMIT 20 look at a register) and only then
    composes the statement that answers the question. Grading the probes would demand that a
    lookup of a country register pin the reporting month, which is nonsense and would paint the
    board red for correct work.

    The rule, in order (spec §4.1):

      1. Candidates are ``ok`` statements carrying at least one ``SUM``/``AVG`` whose arguments
         include a column that is NOT one of the pins. Summing something other than an axis is
         what "computing a measure" looks like; ``COUNT`` is excluded because ``COUNT(*)`` and
         ``COUNT(DISTINCT <axis>)`` are how the probes count rows and members.
      2. If there is at least one candidate, those are the answering statements.
      3. Otherwise, if anything parsed, the LAST ok statement — a question answered by a plain
         projection (a list, a comparison grid) still has an answering statement, and it is the
         final one the engine ran.
      4. Otherwise none.

    Returns ``index`` values (positions in the list handed to ``parse_statements``), ascending.
    """
    pins = {c.strip().lower() for c in (pin_columns or []) if isinstance(c, str) and c.strip()}

    ok_stmts = [s for s in (stmts or []) if s.get("ok")]

    measure_stmts: list[int] = []
    for stmt in ok_stmts:
        for agg in stmt.get("aggregates") or []:
            if agg.get("func") not in ("SUM", "AVG"):
                continue
            # `any(...)` over an EMPTY arg list is False, which is correct: `SUM(1)` and a bare
            # `SUM(<pinned axis>)` compute no measure this question could be about.
            if any(name not in pins for name in (agg.get("args") or [])):
                measure_stmts.append(stmt["index"])
                break

    if measure_stmts:
        return measure_stmts
    if ok_stmts:
        return [ok_stmts[-1]["index"]]
    return []
