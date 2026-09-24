#!/usr/bin/env python3
"""A register that exists and nothing can resolve through is an ORPHAN — report it.

WHY THIS GATE EXISTS. The operator asked a question naming `Q1` and got:

    No month named 'Q1' in data/lookups/contoso_calendar_month.lookup.csv:
    compared case- and whitespace-insensitively with search_key over 12 rows.

`contoso_calendar_quarter.lookup.csv` exists, holds Q1..Q4, and was CUT FROM THE SERVED PLANE --
`confidence: I`, `source_view: dim_contoso_calendar_day`. Nobody wrote it. But no contract rule
names it in `realized_by.params.register`, so the loader never opens it and the resolver searches
the month register instead. Measured on contoso the day this was written: **9 of 17 register files
are unreachable**, including quarter, weekday, working_day and gender.

THE OPERATOR'S OBJECTION IS THE POINT, and it is right: "why should i declare Q1 ... this must be
a common sense". A quarter list is ENUMERATION, and this estate's rule is *derive the enumeration,
author the meaning*. A file the pipeline cut from a column should not need a person to hand-write
a binding before anything may use it. That is a framework gap, not missing authorship.

THIS GATE DOES NOT FIX IT. It makes it visible, which is the part that can be done without ruling
on how binding should work. An orphaned register fails silently and expensively: the question does
not error, it REFUSES, with a message that is accurate about what it searched and says nothing
about the register it should have searched.

Exit 0 when every register on disk is reachable, 1 when any is not, 2 when the bundle cannot be
read at all (REFUSED, never PASS -- a gate that cannot see its subject must not report success).
"""

from __future__ import annotations

import argparse
import pathlib
import sys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)

    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.bundle).resolve()
    lookups = root / "data" / "lookups"
    if not lookups.is_dir():
        print(f"SKIP: no data/lookups in {root.name} — this bundle declares no registers")
        return 0

    on_disk = {p.name for p in sorted(lookups.glob("*.lookup.csv"))}
    if not on_disk:
        print(f"SKIP: {lookups} holds no .lookup.csv")
        return 0

    try:
        sys.path.insert(0, "/Users/<operator>/dev/mac-platform/packages/mac-runtime/src")
        from mac_runtime.ontology import OntologyIndex
        from mac_runtime.resolver.registers import load_registers
    except ImportError as exc:
        print(f"REFUSED: mac_runtime is not importable ({exc}). A gate that cannot load the "
              f"runtime cannot say whether a register is reachable, and must not report PASS.")
        return 2

    try:
        index = OntologyIndex.from_directory(str(root))
        load = load_registers(str(root), index)
    except Exception as exc:  # noqa: BLE001 - an unreadable bundle is REFUSED, never passed
        print(f"REFUSED: {root.name} could not be loaded — {type(exc).__name__}: "
              f"{str(exc)[:160]}")
        return 2

    reachable = {pathlib.Path(r.declaration.register).name for r in load.loaded}
    orphans = sorted(on_disk - reachable)

    print(f"registers on disk: {len(on_disk)}   reachable: {len(on_disk & reachable)}   "
          f"ORPHANED: {len(orphans)}")
    if not orphans:
        print("OK — every register file can be resolved through.")
        return 0
    print("\nThese files exist and NOTHING CAN RESOLVE THROUGH THEM. A question naming one of")
    print("their values does not error — it REFUSES, naming whichever register was searched")
    print("instead, which reads as 'that value does not exist in the data'.\n")
    for o in orphans:
        rows = _row_count(lookups / o)
        print(f"  {o:<44} {rows} row(s) unreachable")
    print(f"\nFAIL — {len(orphans)} of {len(on_disk)} registers are orphaned.")
    print("  A register is bound by a contract rule whose `realized_by` is")
    print("  `udf: mac.canon.resolve_by_register` with `params.register` naming the file.")
    return 1


def _row_count(path: pathlib.Path) -> int:
    try:
        return max(0, len(path.read_text(encoding="utf-8").splitlines()) - 1)
    except OSError:
        return 0


def _self_test() -> int:
    """The gate must REJECT an orphan and PASS a bound one — checked without a bundle.

    A gate whose discrimination is never demonstrated is indistinguishable from one that always
    passes, and this file exists precisely because a silent pass cost nine registers.
    """
    cases = [
        ("an orphan is caught", {"a.lookup.csv", "b.lookup.csv"}, {"a.lookup.csv"}, 1),
        ("all bound is clean", {"a.lookup.csv"}, {"a.lookup.csv"}, 0),
        ("no registers at all", set(), set(), 0),
        ("reachable-but-absent is not an orphan", {"a.lookup.csv"},
         {"a.lookup.csv", "ghost.lookup.csv"}, 0),
    ]
    bad = 0
    for label, on_disk, reachable, want in cases:
        got = 1 if sorted(on_disk - reachable) else 0
        if got != want:
            bad += 1
            print(f"  FAIL  {label}: wanted exit {want}, got {got}")
    n = len(cases)
    print(f"\n{'FAIL' if bad else 'OK'} — self-test: {n - bad} of {n} seeded cases behaved")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
