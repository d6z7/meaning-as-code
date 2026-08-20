#!/usr/bin/env python3
"""Turn a run-level total repeated on every row into a PER-ROW fact.

Operator: *"you cannot have cumulative value in every column."*

M-BRAND-KPI-01 returns 42 rows — one per brand x measure, and its own statement says "Each row IS a
test". It then puts `cases_with_no_figure: 2` on ALL of them, so the table shows "2" beside Audi,
which is true of the run and meaningless of the row. The reader cannot see WHICH case failed, which
is the only thing the table exists to show. It also fails the assertion 42 times instead of twice.

    (SELECT COUNT(*) FROM cases WHERE n_cells = 0) AS cases_with_no_figure      -- same on every row
    CASE WHEN n_cells = 0 THEN 1 ELSE 0 END        AS case_has_no_figure        -- about THIS row

The assertion is unchanged in meaning: must_be_zero over a per-row flag is satisfied exactly when no
case failed, and now the failing ROW is visible.

ONLY where the counted CTE is the row source. A total over a DIFFERENT relation than the one the
outer query iterates has no per-row equivalent, and is reported rather than mangled.
"""
from __future__ import annotations

import argparse
import glob
import pathlib
import re

import yaml

# (SELECT COUNT(*) FROM <cte> WHERE <cond>) AS <name>
COUNT_WHERE = re.compile(
    r"\(\s*SELECT\s+COUNT\(\*\)\s+FROM\s+(\w+)\s+WHERE\s+(.+?)\)\s*(?:AS\s+)?(\w+)",
    re.I | re.S)
# (SELECT COUNT(*) FROM <cte>) AS <name>   — the bare row count
COUNT_ALL = re.compile(r"\(\s*SELECT\s+COUNT\(\*\)\s+FROM\s+(\w+)\s*\)\s*(?:AS\s+)?(\w+)", re.I)


def outer_source(sql: str) -> str | None:
    """The CTE the final SELECT iterates. Everything after the last top-level FROM."""
    m = None
    for m in re.finditer(r"\bFROM\s+(\w+)", sql, re.I):
        pass
    return m.group(1) if m else None


def rewrite(sql: str, asserted: set[str]) -> tuple[str, list[str], list[str]]:
    src = outer_source(sql)
    done, skipped = [], []

    def sub_where(m):
        cte, cond, name = m.group(1), m.group(2).strip(), m.group(3)
        if src and cte.lower() == src.lower():
            done.append(name)
            return f"CASE WHEN {cond} THEN 1 ELSE 0 END AS {name}"
        skipped.append(f"{name} (counts {cte}, rows come from {src})")
        return m.group(0)

    out = COUNT_WHERE.sub(sub_where, sql)

    def sub_all(m):
        cte, name = m.group(1), m.group(2)
        # the bare row count of the source IS the number of rows returned — it tells a reader
        # nothing the table does not already show, and repeats on every line
        if src and cte.lower() == src.lower() and name not in asserted:
            done.append(f"{name} (dropped — the row count is the table's own length)")
            return "NULL AS _dropped_" + name
        return m.group(0)

    out = COUNT_ALL.sub(sub_all, out)
    out = re.sub(r"\s*NULL AS _dropped_\w+,?", "", out)
    return out, done, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--only", default="", help="comma-separated property ids")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    only = {x.strip() for x in a.only.split(",") if x.strip()}

    for f in sorted(glob.glob(str(pathlib.Path(a.root) / "acceptance" / "*.yaml"))):
        p = pathlib.Path(f)
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or not doc.get("properties"):
            continue
        touched = False
        for prop in doc["properties"]:
            if not isinstance(prop, dict) or (only and prop.get("id") not in only):
                continue
            sql = str(prop.get("sql") or "")
            asserted = set((prop.get("assertion") or {}).get("columns") or [])
            new, done, skipped = rewrite(sql, asserted)
            if new == sql:
                continue
            print(f"  {prop['id']}")
            for d in done:
                print(f"     -> per row: {d}")
            for s in skipped:
                print(f"     !! left alone: {s}")
            prop["sql"] = new
            touched = True
        if touched and a.apply:
            p.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100),
                         encoding="utf-8")
    if not a.apply:
        print("\n  (report only — pass --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
