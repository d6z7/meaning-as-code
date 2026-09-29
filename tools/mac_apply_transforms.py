#!/usr/bin/env python3
"""mac_apply_transforms.py — put this bundle's transforms INTO the warehouse. The one writer.

THE OPERATOR, 2026-09-29: "you apply sql ... always !!! all communication to the data and DB goes
through you."

WHY IT DID NOT EXIST, AND WHAT THAT COST. `data/transforms/*.sql` is the only authored artifact in
the data plane, and the declaration says `«the warehouse», role: build.sh applies it` — a bundle-local
shell script, outside the pipeline. So the chain GENERATE -> APPLY -> MEASURE had a hole in the
middle, and the hole is not theoretical: dropping contoso5 and regenerating it produced eight
passthrough `.sql` describing eight views THAT WERE NEVER CREATED, while the warehouse still held the
eight curated views whose `.sql` had just been deleted. Ten transform files, eight views, and a
delivery that reported 39 of 39 complete over the mismatch. A file that describes a view nobody
created is a claim, not a transform.

IT IS THE ONLY WRITER, AND DELIBERATELY NOT THROUGH THE MEASURING SEAM. `duckdb_seam` opens
read-only and says why: "READ-ONLY, ALWAYS. A measurement that can write is not a measurement." That
rule is right and this tool does not bend it — it opens its own connection, writes, and closes.
Everything else in the estate keeps reading through a connection that cannot write, so there is
exactly one place where the warehouse changes and it is named.

ORDER IS DISCOVERED, NOT DECLARED. A view may select from another view, and nothing in the bundle
records which. Rather than ask an author to maintain a dependency list — a second home for a fact the
SQL already states — this applies what it can and retries what failed, until a pass changes nothing.
What is still failing then is a real error and is reported per statement.

    python3 mac_apply_transforms.py <bundle-root> [--check]
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def statements(sql_text: str) -> str:
    """The SQL, with the comment banner stripped — what the warehouse is actually asked to run."""
    body = "\n".join(ln for ln in sql_text.splitlines() if not ln.strip().startswith("--"))
    return body.strip().rstrip(";").strip()


def target_of(sql_text: str) -> str | None:
    """The relation a statement creates, for reporting — read from the statement, never guessed."""
    m = re.search(r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:VIEW|TABLE)\s+([A-Za-z0-9_.\"]+)",
                  sql_text, re.I)
    return m.group(1).replace('"', "") if m else None


def apply_all(root: pathlib.Path, check: bool = False) -> tuple:
    """(applied, failed, skipped) — applied in dependency order, discovered by retrying."""
    import duckdb_seam

    conn = duckdb_seam.connection_of(root)
    if conn is None:
        return None, [("«connector»", "not a DuckDB bundle — this applier writes DuckDB only; "
                                      "an Athena/Trino bundle applies through its own deployment")], []
    db, _read_only, view_schema = conn

    files = sorted((root / "data" / "transforms").glob("*.sql"))
    if not files:
        return [], [], []

    plan = []
    for f in files:
        body = statements(f.read_text(encoding="utf-8"))
        if not body:
            continue
        plan.append((f.name, target_of(body) or f.stem, body))

    if check:
        return [(n, t) for n, t, _ in plan], [], []

    import duckdb
    con = duckdb.connect(str(db), read_only=False)
    try:
        con.execute(f'CREATE SCHEMA IF NOT EXISTS "{view_schema}"')
        pending, applied, failed = list(plan), [], []
        while pending:
            progressed = False
            still: list = []
            for name, tgt, body in pending:
                try:
                    con.execute(body)
                    applied.append((name, tgt))
                    progressed = True
                except Exception as exc:  # noqa: BLE001 - may simply depend on a later statement
                    still.append((name, tgt, body, str(exc).splitlines()[0][:150]))
            if not progressed:
                failed = [(n, f"{t}: {e}") for n, t, _b, e in still]
                break
            pending = [(n, t, b) for n, t, b, _e in still]
        return applied, failed, []
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--check", action="store_true", help="name what would be applied; write nothing")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.root).resolve()
    applied, failed, _ = apply_all(root, check=a.check)
    if applied is None:
        for name, why in failed:
            print(f"COULD NOT RUN: {name} — {why}")
        return 2
    if not applied and not failed:
        print("SKIP: no data/transforms/*.sql — the served plane is declared empty")
        return 0
    if a.check:
        print(f"WOULD APPLY {len(applied)} transform(s):")
        for name, tgt in applied:
            print(f"  {name:44} -> {tgt}")
        return 0
    for name, tgt in applied:
        print(f"  {name:44} -> {tgt}")
    print(f"applied {len(applied)} transform(s) to the warehouse"
          + (f"; {len(failed)} FAILED" if failed else ""))
    if failed:
        print("\nFAIL — a transform the warehouse refused. A `.sql` that does not apply describes a "
              "view nobody can read:")
        for name, why in failed:
            print(f"  {name}: {why}")
        return 1
    return 0


def _self_test() -> int:
    ok = [0, 0]

    def case(what, cond):
        ok[0] += 1
        ok[1] += bool(cond)
        print(("  ✓ " if cond else "  ✗ ") + what)

    SQL = ("-- a banner a person reads\n"
           "-- GRAIN: one row per code.\n"
           'CREATE OR REPLACE VIEW contoso_served.dim_currency AS\n'
           'SELECT DISTINCT s."CurrencyCode" AS currency_code FROM main.sales s;\n')
    case("the comment banner is stripped — the warehouse never sees the prose",
         "--" not in statements(SQL))
    case("the trailing semicolon goes, so one statement is sent as one statement",
         not statements(SQL).endswith(";"))
    case("the target is READ from the statement",
         target_of(SQL) == "contoso_served.dim_currency")
    case("a quoted target is unquoted",
         target_of('CREATE VIEW "s"."t" AS SELECT 1') == "s.t")
    case("MUTANT a file with only comments yields nothing to run",
         statements("-- just a note\n-- and another\n") == "")
    case("a CREATE TABLE is a target too, not only a view",
         target_of("CREATE TABLE s.t AS SELECT 1") == "s.t")

    print(("PASS" if ok[1] == ok[0] else "FAIL")
          + f": mac_apply_transforms self-test — {ok[1]}/{ok[0]} case(s)")
    return 0 if ok[1] == ok[0] else 1


if __name__ == "__main__":
    raise SystemExit(main())
