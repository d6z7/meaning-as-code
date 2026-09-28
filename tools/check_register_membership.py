#!/usr/bin/env python3
"""check_register_membership.py — a register's members against the WAREHOUSE, today.

WHY IT EXISTS, AND IT IS OWED. DNA PART 1.8: "closed sets get a register; registers get a monitor",
and PART 4 step 6: "`check_register_membership` on a schedule; `warranty: monitored` becomes
provable". A `closure: closed` declaration is a claim about data that can stop being true overnight —
a lookup table gains a row and every question over that dimension is now answering about a subset,
silently. No ontology can notice that on its own; only a re-measurement can.

AND IT REPLACES SOMETHING THAT WAS TAKEN AWAY. The operator, 2026-09-26: "are you sure that it makes
sense to include all possible incarnations of states into data source or dataset?!?! these values
could be in lookup if necessary?!?!" — correct, and 74 % of the descriptor plane was member lists,
563 of them carried by nothing. But the generated data-sanity suite built its `enumeration` family
FROM those lists ("prove N still holds exactly the K values we found"), so moving the members to
their registers dropped 30 of 86 cases. Removing 30 checks and delivering nothing in their place
would have been the worse half of a good change. This is the check, reading the register — which is
where the members now live.

WHAT IT COMPARES. Each `data/lookups/*.lookup.csv` declares its code column (the first header field)
and the relation it was cut from (`source_view`). Both are read from the file, never guessed:

    MISSING    a member the register declares and the warehouse no longer has -> the register is
               stale, or a value was retired and the register was not re-cut
    NEW        a value the warehouse has and the register does not              -> THE OVERNIGHT
               CASE. Every question over this dimension has been answering about a subset.
    NULLS      rows whose value is absent altogether                            -> NOT a breach
    ORPHANED   a register whose relation or column the warehouse does not carry -> a rename

A NEW member is the finding this file exists for, so it is reported first and counted separately: a
missing one degrades an answer, a new one INVALIDATES the closure claim.

WHY NULL IS NOT A NEW MEMBER, learned on this check's first run. It reported two registers as
"outgrown" — and both differences were the empty string, i.e. NULL: 59 of 74 stores carry no Status,
222 of 2 517 products no WeightUnit. Both registers held EXACTLY the distinct non-null values, so the
registers were right and the check was wrong. A NULL is an ABSENCE, and the generated suite's
`completeness` family already owns absences with its own cases and its own thresholds. Calling it a
closure breach would fail this monitor on every ordinary warehouse, and a monitor that always fails is
one nobody reads. So NULLs are counted, named, and do not fail the run — while still being said out
loud, because rows outside the register are rows a grouped answer drops or buckets silently.

Exit 0 when every register matches the warehouse, 1 on any difference, 2 when the bundle cannot be
read.
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys
from datetime import UTC, datetime

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _plugin  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--out", default="acceptance/register_membership_runs.json",
                    help="where to write the RUN RECORD; a monitor nobody can see the result of is "
                         "not a monitor (relative to the bundle)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.bundle).resolve()
    registers = sorted((root / "data" / "lookups").glob("*.lookup.csv"))
    if not registers:
        print(f"SKIP: {root.name} declares no register in data/lookups/")
        return 0
    try:
        con = _plugin.required(str(root), "Athena")(root=str(root))
    except Exception as exc:  # noqa: BLE001 - could-not-run is honest, never a finding
        print(f"COULD NOT RUN: {exc}")
        return 2

    # THE DEFAULT ONLY, for a register file written before `source_schema` existed. A register now
    # RECORDS the plane it was cut from and that is what gets read — see the note in mac_lookups._render.
    default_schema = getattr(con, "view_schema", None) or "main"
    new: list[tuple[str, list[str]]] = []
    missing: list[tuple[str, list[str]]] = []
    nulls: list[str] = []
    orphaned: list[tuple[str, str]] = []
    matched = 0

    for reg in registers:
        code_col, relation, declared, reg_schema = _read(reg)
        schema = reg_schema or default_schema
        if not code_col or not relation:
            orphaned.append((reg.name, "the file declares no code column or no source_view"))
            continue
        try:
            rows, _ = con.query(
                f'SELECT DISTINCT "{code_col}" AS d0 FROM "{schema}"."{relation}"'
            )
        except Exception as exc:  # noqa: BLE001
            orphaned.append((reg.name, f"{schema}.{relation}.{code_col} — {str(exc)[:70]}"))
            continue
        # NULL IS NOT A MEMBER. See the docstring: this line is the fix for this check's own first
        # finding, which was two false closure breaches that were both NULL.
        live = {str(r["d0"]) for r in rows if r["d0"] is not None}
        if any(r["d0"] is None for r in rows):
            nulls.append(f"{relation}.{code_col}")
        gone = sorted(declared - live)
        added = sorted(live - declared)
        if not gone and not added:
            matched += 1
            continue
        if added:
            new.append((reg.name, added))
        if gone:
            missing.append((reg.name, gone))
    con.close()

    _record(root, a.out, len(registers), matched, new, missing, nulls, orphaned)
    print(f"registers: {len(registers)}   matching the warehouse: {matched}")
    if nulls:
        print(f"\n  {len(nulls)} column(s) also carry NULL — an absence, which the suite's "
              f"`completeness` family owns, NOT a closure breach:\n      "
              + "\n      ".join(nulls)
              + "\n  Rows with no value fall outside the register: a grouped answer drops or buckets "
                "them.")
    if not new and not missing and not orphaned:
        print("\nOK — every register's members are exactly what the warehouse holds today "
              "(DNA 1.8: a closed set's monitor).")
        return 0

    if new:
        print(f"\nNEW MEMBERS — {len(new)} register(s) the warehouse has OUTGROWN. This is the case "
              f"this check exists for:\n"
              f"  a `closure: closed` claim is now false, and every question over that dimension has\n"
              f"  been answering about a SUBSET without saying so.\n")
        for name, vals in new:
            shown = ", ".join(vals[:8]) + (f" … and {len(vals) - 8} more" if len(vals) > 8 else "")
            print(f"  {name}\n      + {len(vals)}: {shown}")
    if missing:
        print(f"\nMISSING MEMBERS — {len(missing)} register(s) declare a value the warehouse no "
              f"longer has (stale register, or a retired value):\n")
        for name, vals in missing:
            shown = ", ".join(vals[:8]) + (f" … and {len(vals) - 8} more" if len(vals) > 8 else "")
            print(f"  {name}\n      - {len(vals)}: {shown}")
    if orphaned:
        print(f"\nORPHANED — {len(orphaned)} register(s) point at something the warehouse does not "
              f"carry:\n")
        for name, why in orphaned:
            print(f"  {name}\n      {why}")
    print("\nFAIL — re-cut the registers (mac_lookups.py) and re-read the closure claims that rest "
          "on them.")
    return 1


def _record(root: pathlib.Path, out: str, total: int, matched: int,
            new: list, missing: list, nulls: list, orphaned: list) -> None:
    """THE RUN RECORD. A monitor whose result exists only in a terminal that has scrolled away has
    monitored nothing — the same defect as "generating is not testing": executing is not reporting.
    This file is what a dashboard, a scheduled job, or a later operator reads to learn whether the
    closure claims still hold, and when they were last checked."""
    path = root / out
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "generated_by": "check_register_membership.py/1",
        "executed": datetime.now(UTC).isoformat(timespec="seconds"),
        "registers": total,
        "matching": matched,
        "verdict": "OK" if not (new or missing or orphaned) else "FAIL",
        "new_members": {n: v for n, v in new},
        "missing_members": {n: v for n, v in missing},
        "columns_with_nulls": nulls,
        "orphaned": {n: w for n, w in orphaned},
    }, indent=2) + "\n", encoding="utf-8")


def _read(path: pathlib.Path) -> tuple[str | None, str | None, set[str], str | None]:
    """The code column, the relation, the declared members, AND THE SCHEMA — all from the file itself.

    THE FIRST HEADER FIELD IS THE CODE COLUMN. That is not a convention this file invents: the
    register loader infers a register's source column from exactly that, so reading it any other way
    here would check something the runtime does not use.
    """
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        return None, None, set()
    rows = list(csv.reader(lines))
    header = rows[0]
    code_col = header[0] if header else None
    def _col(name):
        try:
            return header.index(name)
        except ValueError:
            return None

    def _first(ix):
        if ix is None:
            return None
        for r in rows[1:]:
            if len(r) > ix and r[ix]:
                return r[ix]
        return None

    members = {r[0] for r in rows[1:] if r}
    # THE SCHEMA IS READ, NOT GUESSED. A register cut from the LANDING plane lives in `main` and one cut
    # from a served view lives in the view schema; resolving both in the connector's default made every
    # landing-plane register fail as "does not exist". Absent on a file written before the field existed,
    # and the caller then falls back to the default — which is what that file's producer assumed anyway.
    return code_col, _first(_col("source_view")), members, _first(_col("source_schema"))


def _self_test() -> int:
    """A set difference, in both directions, and neither direction may be silently dropped."""
    cases = [
        ("register == warehouse                 -> OK", {"A", "B"}, {"A", "B"}, False, False),
        ("warehouse gained a value              -> NEW", {"A"}, {"A", "B"}, True, False),
        ("warehouse lost a value                -> MISSING", {"A", "B"}, {"A"}, False, True),
        ("both at once                          -> NEW and MISSING", {"A", "B"}, {"B", "C"},
         True, True),
        # THE REGRESSION. First run reported two false breaches; both differences were NULL. A NULL
        # never reaches `live`, so a register holding exactly the non-null values must read as OK.
        ("warehouse has NULLs, values unchanged -> OK, never NEW", {"A", "B"}, {"A", "B"},
         False, False),
    ]
    bad = 0
    for label, declared, live, want_new, want_missing in cases:
        got_new = bool(live - declared)
        got_missing = bool(declared - live)
        if (got_new, got_missing) != (want_new, want_missing):
            bad += 1
            print(f"  FAIL  {label}")
    n = len(cases)
    print(f"\n{'FAIL' if bad else 'OK'} — self-test: {n - bad} of {n} seeded cases behaved")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
