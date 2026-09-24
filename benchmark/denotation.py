"""DENOTATION — do two queries return the same ANSWER, on the same database?

WHAT THIS IS FOR. `encodability.py` measures whether a query's SHAPE maps onto the Intent. It
never runs anything, so it is a statement about grammar and nothing else. This is the other half:
run OUR SQL and the corpus's GOLD SQL against the SAME database and compare what comes back.

IT IS THE FIRST INSTRUMENT IN THIS ESTATE THAT IS NOT SELF-GRADED. Every other number here is
measured against something we wrote: our anchors, our oracles, our classifier. Gold SQL was
written by someone else, for a published benchmark, and it does not care what our ontology says.

SAME ENGINE, AND THAT IS NOT A DETAIL. BIRD and Spider gold is written for SQLite, and engines
disagree on exactly what gold is full of -- measured on california_schools, `7/2` is 3 in SQLite
and 3.5 in DuckDB, and a NULL sorts first in one and not the other. Run gold on one engine and
ours on another and every difference is ambiguous between "the ontology got it wrong" and "the
engines round differently", which is not a measurement at all. Both sides run here, on the file
the benchmark shipped.

WHAT "THE SAME ANSWER" MEANS, stated rather than assumed, because every text-to-SQL paper means
something slightly different by it:

  * COLUMN NAMES ARE IGNORED. Gold says `MAX(CAST(...))`, ours says `enrollmentk12`. Comparing
    names would reject correct answers for a cosmetic reason -- and the estate's own oracle-check
    already works this way ("by MEANING, not by matching column-name strings").
  * ROW ORDER IS IGNORED UNLESS THE QUESTION ORDERED IT. A query with no ORDER BY has no defined
    row order, and two engines may legitimately differ. Where EITHER side has an ORDER BY, order
    is compared, because then it was asked for.
  * VALUES ARE COMPARED AFTER NUMERIC COERCION. `67` and `67.0` and `Decimal("67")` are one
    answer. `"67"` is too -- SQLite has type affinity and a gold query may return a number as
    text through a CAST the ontology had no reason to make.
  * FLOATS COMPARE WITHIN A TOLERANCE. A rate computed as `a*1.0/b` and one computed as `a/b*1.0`
    differ in the last bits and mean the same thing.

WHAT IT IS NOT. It cannot say our answer is RIGHT -- only that it denotes what gold denotes. Gold
is one implementation of one reading of the question, and BIRD's own authors ship an `evidence`
hint per question precisely because the questions are ambiguous without it. A disagreement is a
FINDING to read, not automatically our defect.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sqlite3
import sys
from dataclasses import dataclass
from decimal import Decimal

#: Float comparison tolerance. Relative, because the corpus mixes counts with rates and money.
_REL_TOL = 1e-6
_ABS_TOL = 1e-9

#: How long one query may take. BIRD ships databases up to 260 MB and a cartesian mistake on one
#: of those does not finish -- a comparator that hangs is a comparator nobody runs.
_TIMEOUT_S = 30.0


@dataclass(frozen=True)
class Run:
    """One query's result, or why there isn't one."""

    ok: bool
    rows: tuple[tuple, ...] = ()
    error: str = ""

    @property
    def shape(self) -> str:
        if not self.ok:
            return "error"
        return f"{len(self.rows)}x{len(self.rows[0]) if self.rows else 0}"


@dataclass(frozen=True)
class Verdict:
    """Whether two runs denote the same answer, and why not when they do not."""

    same: bool
    reason: str
    gold: Run
    ours: Run


def norm(value):
    """One value, comparable across engines and types.

    NUMBERS FIRST: SQLite has type affinity, so a gold query can return `'67'` where ours returns
    `67`, and both are the same answer. Text that is not a number keeps its own identity, cased
    and stripped -- `'Alameda'` and `'alameda '` are the same county.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return repr(value)
    if isinstance(value, str):
        s = value.strip()
        try:
            return float(s)
        except ValueError:
            return s.casefold()
    return repr(value)


def values_equal(a, b) -> bool:
    a, b = norm(a), norm(b)
    if a is None or b is None:
        return a is b or (a is None and b is None)
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        return math.isclose(a, b, rel_tol=_REL_TOL, abs_tol=_ABS_TOL)
    return a == b


def rows_equal(a: tuple, b: tuple) -> bool:
    return len(a) == len(b) and all(values_equal(x, y) for x, y in zip(a, b, strict=True))


def _sorted_rows(rows: tuple[tuple, ...]) -> list[tuple]:
    """A canonical order for an unordered comparison. Sorted on the NORMALISED values, so the
    order does not depend on whether an engine returned 67 or '67'."""
    return sorted(rows, key=lambda r: tuple(repr(norm(v)) for v in r))


def has_order_by(sql: str) -> bool:
    """Did the query ASK for an order? Parsed, not grepped -- `ORDER BY` inside a string literal
    or a column name is not an ordering, and a substring test would call it one."""
    try:
        import sqlglot
        from sqlglot import exp

        return bool(list(sqlglot.parse_one(sql, read="sqlite").find_all(exp.Order)))
    except Exception:  # noqa: BLE001 - an unparseable query is treated as unordered
        return " order by " in f" {' '.join(sql.split()).lower()} "


def execute(db: pathlib.Path, sql: str) -> Run:
    """Run one query, read-only, with a timeout.

    READ-ONLY WITH A FALLBACK, for the reason the SQLite adapter documents: `mode=ro` refuses a
    WAL-mode database because opening one may need to recover its `-wal`, which is a write. One
    of BIRD's eleven dev databases fails exactly there, and a comparator that skips a database
    because of how it was last closed is silently measuring ten of eleven.
    """
    con = None
    for uri in (f"file:{db}?mode=ro", f"file:{db}?immutable=1"):
        try:
            con = sqlite3.connect(uri, uri=True, timeout=_TIMEOUT_S)
            con.execute("SELECT 1").fetchone()
            break
        except sqlite3.Error:
            con = None
    if con is None:
        return Run(False, error=f"cannot open {db.name}")
    # A DEADLINE, not a hope. `set_progress_handler` fires every N opcodes; raising from it
    # aborts the statement, which is the only portable way to bound a SQLite query.
    import time

    deadline = time.monotonic() + _TIMEOUT_S

    def _tick():
        return 1 if time.monotonic() > deadline else 0

    con.set_progress_handler(_tick, 10_000)
    try:
        rows = tuple(tuple(r) for r in con.execute(sql).fetchall())
        return Run(True, rows=rows)
    except sqlite3.Error as exc:
        return Run(False, error=f"{type(exc).__name__}: {exc}"[:200])
    finally:
        con.close()


def compare(db: pathlib.Path, gold_sql: str, our_sql: str) -> Verdict:
    """Do these two queries denote the same answer on this database?"""
    gold, ours = execute(db, gold_sql), execute(db, our_sql)
    if not gold.ok:
        # A GOLD QUERY THAT WILL NOT RUN IS NOT OUR FAILURE, and must never be scored as one.
        return Verdict(False, f"gold did not run: {gold.error}", gold, ours)
    if not ours.ok:
        return Verdict(False, f"ours did not run: {ours.error}", gold, ours)
    if len(gold.rows) != len(ours.rows):
        return Verdict(False, f"row count {len(gold.rows)} vs {len(ours.rows)}", gold, ours)
    if not gold.rows:
        return Verdict(True, "both empty", gold, ours)
    width_g = len(gold.rows[0])
    width_o = len(ours.rows[0])
    if width_g != width_o:
        return Verdict(False, f"column count {width_g} vs {width_o}", gold, ours)

    ordered = has_order_by(gold_sql) or has_order_by(our_sql)
    g = list(gold.rows) if ordered else _sorted_rows(gold.rows)
    o = list(ours.rows) if ordered else _sorted_rows(ours.rows)
    for i, (rg, ro) in enumerate(zip(g, o, strict=True)):
        if not rows_equal(rg, ro):
            return Verdict(
                False,
                f"row {i} differs{' (order compared: a query asked for one)' if ordered else ''}"
                f": {rg!r} vs {ro!r}",
                gold,
                ours,
            )
    return Verdict(True, "ordered match" if ordered else "same rows, any order", gold, ours)


# --------------------------------------------------------------------------- self-test

#: ONE MUTANT PER REJECT CLASS. A comparator that cannot reject cannot report, and this one will
#: be quoted as an external number -- so it is seeded against a database built here, with no
#: corpus and no network, and every case names the defect it stands for.
_SELF_TEST = [
    ("identical queries",            "SELECT a FROM t",                  "SELECT a FROM t",                  True),
    ("column NAMES differ",          "SELECT a AS x FROM t",             "SELECT a AS zzz FROM t",           True),
    ("int vs float",                 "SELECT 67 AS n",                   "SELECT 67.0 AS n",                 True),
    ("number returned as TEXT",      "SELECT '67' AS n",                 "SELECT 67 AS n",                   True),
    ("float within tolerance",       "SELECT 1.0/3.0 AS r",              "SELECT 0.333333333333 AS r",       True),
    ("row order, nothing ordered",   "SELECT a FROM t",                  "SELECT a FROM t ORDER BY a DESC",  False),
    ("a WRONG VALUE",                "SELECT sum(a) FROM t",             "SELECT sum(a)+1 FROM t",           False),
    ("a MISSING ROW",                "SELECT a FROM t",                  "SELECT a FROM t WHERE a > 1",      False),
    ("an EXTRA COLUMN",              "SELECT a FROM t",                  "SELECT a, a FROM t",               False),
    ("empty vs empty",               "SELECT a FROM t WHERE 0",          "SELECT a FROM t WHERE 0",          True),
    ("empty vs non-empty",           "SELECT a FROM t WHERE 0",          "SELECT a FROM t",                  False),
    ("OURS does not run",            "SELECT a FROM t",                  "SELECT nosuch FROM t",             False),
    ("GOLD does not run",            "SELECT nosuch FROM t",             "SELECT a FROM t",                  False),
    ("NULL vs a value",              "SELECT NULL AS n",                 "SELECT 0 AS n",                    False),
    ("NULL vs NULL",                 "SELECT NULL AS n",                 "SELECT NULL AS n",                 True),
    ("text case and padding",        "SELECT 'Alameda' AS c",            "SELECT ' alameda ' AS c",          True),
]


def _self_test() -> int:
    import tempfile

    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        db = pathlib.Path(tmp) / "t.sqlite"
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE t (a INTEGER)")
        con.executemany("INSERT INTO t VALUES (?)", [(1,), (2,), (3,)])
        con.commit()
        con.close()
        for label, gold, ours, want in _SELF_TEST:
            got = compare(db, gold, ours)
            if got.same != want:
                bad += 1
                print(f"  FAIL  {label}: wanted same={want}, got same={got.same} ({got.reason})")
    n = len(_SELF_TEST)
    print(f"\n{'FAIL' if bad else 'OK'} — denotation self-test: {n - bad} of {n} seeded cases behaved")
    print("  (one mutant per reject class; a comparator that cannot reject cannot report)")
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", help="the SQLite database both queries run against")
    ap.add_argument("--gold", help="the corpus's gold SQL")
    ap.add_argument("--ours", help="our SQL")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    if not (a.db and a.gold and a.ours):
        ap.error("--db, --gold and --ours are required (or --self-test)")
    v = compare(pathlib.Path(a.db), a.gold, a.ours)
    print(json.dumps({
        "same": v.same, "reason": v.reason,
        "gold": v.gold.shape, "ours": v.ours.shape,
    }, indent=1))
    return 0 if v.same else 1


if __name__ == "__main__":
    sys.exit(main())
