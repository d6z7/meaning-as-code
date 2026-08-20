#!/usr/bin/env python3
"""Does each asserted column actually depend on the WAREHOUSE, or only on what the SQL typed itself?

Operator, after finding one: *"you should inspect all tests and verify we do not have more such
test."*

THE ONE THAT PROMPTED IT. R-ALIAS-01 embeds the ontology's alias map as a 38-row VALUES block, then
asserts `n_alias_surfaces_total: 38` — computed as SUM(n_alias_surfaces) OVER () across the rows it
had just written. It counts a list it authored and checks the count matches. It cannot fail.

And the tautology was hiding a real defect. The ontology declares `Produktionsanträge`; the copied
block types `Produktionsantraege`. Both sides count 38, so the assertion passed for as long as it
existed — while the test checked a DIFFERENT alias from the one the model declares. A count is
structurally blind to a rename, which is the same lesson the profiler learned about value sets.

── WHAT COUNTS AS VACUOUS ──────────────────────────────────────────────────────────────────────
    LITERAL-ONLY   every source the asserted column traces back to is an inline VALUES CTE or a
                   constant. Nothing in the warehouse can move it.
    CONSTANT       the column IS a literal — `SELECT 0 AS violations` with must_be_zero on it.
    ABSENT         the assertion names a column the SQL never returns. It cannot fail either, and
                   for a different reason: there is nothing to compare.

A property may legitimately JOIN a literal CTE — that is how a declared set is checked against the
data. What is never legitimate is an assertion whose value depends on NO relation at all.

Static analysis only: the SQL is parsed, never executed, so this runs offline and blocks in the gate.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import yaml

try:
    import sqlglot
    from sqlglot import exp
    from sqlglot.lineage import lineage as sql_lineage
except ImportError:
    sqlglot = None

DIALECT = "trino"


def literal_ctes(tree) -> set[str]:
    """CTE names whose body is nothing but typed rows — VALUES, or a SELECT over VALUES."""
    out = set()
    for cte in tree.find_all(exp.CTE):
        body = cte.this
        has_values = bool(list(body.find_all(exp.Values)))
        has_table = any(t.name for t in body.find_all(exp.Table))
        if has_values and not has_table:
            out.add(cte.alias_or_name.lower())
    return out


def cte_deps(tree) -> dict[str, set[str]]:
    """cte name -> the names it selects FROM (tables or other CTEs)."""
    deps: dict[str, set[str]] = {}
    for cte in tree.find_all(exp.CTE):
        deps[cte.alias_or_name.lower()] = {t.name.lower() for t in cte.this.find_all(exp.Table)}
    return deps


def base_tables(names: set[str], deps: dict[str, set[str]], seen=None) -> set[str]:
    """Expand CTE references transitively down to base relations."""
    seen = seen or set()
    out = set()
    for n in names:
        if n in seen:
            continue
        seen.add(n)
        if n in deps:
            out |= base_tables(deps[n], deps, seen)
        else:
            out.add(n)
    return out


def traces_to_warehouse(col: str, sql: str, tree, lit: set[str]) -> bool | None:
    """Does this output column depend on a real relation, or only on rows the SQL typed?

    COLUMN-LEVEL, and it took three attempts to get right — each failure worth keeping:
      1. CTE-level: asked whether a CTE was purely literal. MISSED R-ALIAS-01, whose
         `n_alias_surfaces` comes from the typed alias map inside a CTE that also joins the fact.
      2. Leaf-table lineage: required the chain to reach an exp.Table. Flagged 362 of 300 properties,
         because `count(*)` carries no column reference, so lineage stops at the CTE whether or not
         that CTE reads a real relation.
      3. This: walk the lineage, and where it stops, resolve THAT SCOPE's own sources transitively
         through the CTE graph down to base relations.
    """
    try:
        node = sql_lineage(col, sql, dialect=DIALECT)
    except Exception:
        return None
    deps = cte_deps(tree)
    reached: set[str] = set()
    for n in node.walk():
        src = getattr(n, "source", None)
        if isinstance(src, exp.Table):
            reached.add(src.name.lower())
        elif src is not None:
            # a scope: take the relations IT selects from, then expand through the CTE graph
            frm = {t.name.lower() for t in src.find_all(exp.Table)}
            if frm and len(frm) <= 4:      # a narrow scope attributable to this column
                reached |= base_tables(frm, deps)
    real = {t for t in reached if t and t not in lit}
    if not reached:
        return None
    return bool(real)


def audit(prop: dict, resolve, n_rows: int | None = None) -> list[str]:
    # A conformance property is not valid SQL until its declarations are rendered — `@n:` and
    # `@cols:` are substitution slots. Parsing before resolving reports the whole generated suite as
    # unparseable, which is a bug in the CHECKER masquerading as a finding about the tests.
    sql = resolve(str(prop.get("sql") or ""))
    a = prop.get("assertion") or {}
    want = list(a.get("columns") or [])
    if a.get("type") == "equals" and isinstance(a.get("expect"), dict):
        want += list(a["expect"].keys())
    if not sql or not want:
        return []
    try:
        tree = sqlglot.parse_one(sql, dialect=DIALECT)
    except Exception as e:
        return [f"UNPARSEABLE: {str(e)[:70]}"]

    lit = literal_ctes(tree)
    # every output column of the OUTERMOST select
    outer = tree.find(exp.Select)
    produced = {}
    if outer:
        for e in outer.expressions:
            nm = e.alias_or_name
            if nm:
                produced[nm] = e

    findings = []
    # ── A ROW-PER-CASE TABLE MUST CARRY ROW FACTS ─────────────────────────────────────────────
    # Operator: "you cannot have cumulative value in every column". M-BRAND-KPI-01 returns 42 rows,
    # one per brand x measure, and puts `cases_with_no_figure: 2` on ALL of them — so the table says
    # "2" beside Audi, which is true of the run and meaningless of the row. A reader cannot see WHICH
    # case failed, which is the only thing the table exists to show. It also fails the assertion 42
    # times over instead of twice.
    for col, e in produced.items():
        if col not in want:
            continue
        sub = next((x for x in e.find_all(exp.Subquery)), None)
        win = next((x for x in e.find_all(exp.Window)), None)
        constant = False
        if win is not None and not (win.args.get("partition_by") or win.args.get("order")):
            constant = True
        if sub is not None:
            outer_tables = {t.name.lower() for t in (outer.args.get("from").find_all(exp.Table)
                                                    if outer and outer.args.get("from") else [])}
            inner_tables = {t.name.lower() for t in sub.find_all(exp.Table)}
            if not (inner_tables & outer_tables):        # uncorrelated -> same value every row
                constant = True
        # ONLY WHERE THE PROPERTY EMITS MANY ROWS. A single-row summary may legitimately report a
        # total — there is no other row for it to be wrong beside. Judged on the RECORDED RUN, which
        # knows exactly how many rows came back; the first cut guessed from the SQL shape and flagged
        # 318 of 300, most of them one-row generated properties.
        if constant and (n_rows or 0) > 1:
            findings.append(f"WHOLE-RESULT: `{col}` is the same on every row — a run-level total "
                            f"repeated per row, so the table cannot show WHICH row failed")

    for col in want:
        if col not in produced:
            findings.append(f"ABSENT: assertion names `{col}`, which the SQL never returns")
            continue
        e = produced[col]
        if not list(e.find_all(exp.Column)) and not any(
                isinstance(f, exp.Count) for f in e.find_all(exp.Func)):
            findings.append(f"CONSTANT: `{col}` is a literal — it cannot fail")
            continue
        reaches = traces_to_warehouse(col, sql, tree, lit)
        if reaches is False:
            findings.append(f"LITERAL-ONLY: `{col}` traces back only to rows the SQL typed — "
                            f"nothing in the warehouse can move it")
        elif reaches is None:
            findings.append(f"UNRESOLVED: `{col}` — lineage could not be traced, so it is NOT "
                            f"established that the warehouse can move it")
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if sqlglot is None:
        print("sqlglot not installed — cannot analyse SQL statically", file=sys.stderr)
        return 0

    # MAC owns the analysis; the BUNDLE owns how its declarations resolve. Same split as mac_profile.
    resolve = lambda x: x
    tools = os.path.join(os.path.abspath(a.root), "tools")
    if os.path.isdir(tools):
        sys.path.insert(0, tools)
        try:
            from run_properties import resolve_declared as resolve   # noqa: F401
        except Exception:
            pass

    # how many rows each property actually returned, from the recorded runs
    runs: dict[str, int] = {}
    for rf in glob.glob(os.path.join(a.root, "acceptance", "*_runs.json")):
        try:
            doc = json.load(open(rf, encoding="utf-8"))
        except Exception:
            continue
        for r in doc.get("results") or []:
            rows = r.get("rows")
            if isinstance(rows, list):
                runs[r.get("id")] = len(rows)

    out, n = [], 0
    for f in sorted(glob.glob(os.path.join(a.root, "acceptance", "*.yaml"))):
        doc = yaml.safe_load(open(f, encoding="utf-8"))
        if not isinstance(doc, dict) or not doc.get("properties"):
            continue
        for p in doc["properties"]:
            if not isinstance(p, dict):
                continue
            n += 1
            for msg in audit(p, resolve, runs.get(p.get("id"))):
                out.append({"file": os.path.basename(f), "id": p.get("id"), "finding": msg})
    if a.json:
        print(json.dumps({"findings": out}, indent=1, ensure_ascii=False))
        return 1 if out else 0
    by = {}
    for o in out:
        by.setdefault(o["finding"].split(":")[0], []).append(o)
    for kind in ("ABSENT", "CONSTANT", "LITERAL-ONLY", "UNPARSEABLE"):
        rows = by.get(kind) or []
        if not rows:
            continue
        print(f"\n  {kind} — {len(rows)}")
        for o in rows:
            print(f"     {o['file']:<26}{str(o['id']):<18}{o['finding'].split(': ',1)[1][:66]}")
    if out:
        print(f"\n✗ {len(out)} assertion(s) over {n} properties cannot fail for the reason stated.")
        print("  A test that cannot fail is not evidence — and it hides whatever it was meant to catch:")
        print("  R-ALIAS-01 counted its own typed alias list to 38 while checking a German alias the")
        print("  ontology does not declare.")
        return 1
    print(f"✓ OK — every assertion over {n} properties depends on the warehouse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
