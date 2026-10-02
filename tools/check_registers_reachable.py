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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _neighbours  # noqa: E402  — ONE home for the sibling runtime's location


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
        _neighbours.ensure_runtime_on_path()
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

    declared = {pathlib.Path(r.declaration.register).name for r in load.loaded}
    undeclared = sorted(on_disk - declared)

    # THREE STATES, NOT TWO. This gate used to compute "named by a declaration" and print
    # "NOTHING CAN RESOLVE THROUGH THEM" -- a true measurement with a false conclusion attached,
    # which is worse than a wrong measurement because the number is right so nobody re-reads the
    # sentence. Measured on contoso 2026-09-25: of the 9 files it called unreachable, EIGHT
    # resolve a real word. They load through the undeclared path -- the register's first header
    # field matches a column of some concept, and the loader attributes it there.
    #
    # Reading that false sentence is what caused the duplicate-register episode: "9 of 17
    # orphaned" was believed to mean unusable, and fifteen new registers were cut to replace
    # files that already worked.
    #
    # So an undeclared register that RESOLVES is a different finding from one that does not:
    # it is a working, UNDECLARED DEPENDENCY. Renaming its first column, or the file, breaks a
    # live behaviour with no error. That is the risk worth reporting, and it is not orphanhood.
    by_file: dict[str, int] = {}
    for entry in load.entries:
        if entry.identity == entry.concept:
            continue  # a self-entry is not evidence that a register resolved
        by_file[entry.column or ""] = by_file.get(entry.column or "", 0) + 1

    def resolves(name: str) -> bool:
        """Does anything resolve through this file? Keyed on the column it was cut from."""
        first = _first_column(lookups / name)
        return bool(first) and by_file.get(first, 0) > 0

    conventional = [o for o in undeclared if resolves(o)]
    orphans = [o for o in undeclared if not resolves(o)]

    print(f"registers on disk: {len(on_disk)}   declared: {len(on_disk & declared)}   "
          f"UNDECLARED but resolving: {len(conventional)}   TRUE ORPHANS: {len(orphans)}")

    if conventional:
        print("\nUNDECLARED DEPENDENCIES — these resolve, and nothing declares them. They work")
        print("because the file's FIRST COLUMN happens to match a column of some concept, so the")
        print("loader attributes it there. Rename either side and a live behaviour stops, silently.\n")
        for c in conventional:
            print(f"  {c:<44} {_row_count(lookups / c)} row(s), via column "
                  f"{_first_column(lookups / c)!r}")

    if orphans:
        print("\nTRUE ORPHANS — nothing resolves through these at all. A question naming one of")
        print("their values REFUSES, naming whichever register was searched instead, which reads")
        print("as 'that value does not exist in the data'.\n")
        for o in orphans:
            print(f"  {o:<44} {_row_count(lookups / o)} row(s) unreachable")

    if not conventional and not orphans:
        print("OK — every register is declared by the concept that uses it.")
        return 0
    print(f"\nFAIL — {len(conventional)} undeclared dependency(ies), {len(orphans)} true orphan(s).")
    print("  Declare a register on the column that uses it. Until `columns:` exists, that is a")
    print("  contract rule whose `realized_by` is `udf: mac.canon.resolve_by_register` with")
    print("  `params.register` naming the file.")
    return 1


def _first_column(path: pathlib.Path) -> str:
    """The register's first header field — the column it was cut from, and the only link the
    undeclared path has to a concept."""
    try:
        with path.open(encoding="utf-8-sig") as handle:
            for line in handle:
                if line.startswith("#") or not line.strip():
                    continue
                return line.split(",")[0].strip()
    except OSError:
        pass
    return ""


def _row_count(path: pathlib.Path) -> int:
    try:
        return max(0, len(path.read_text(encoding="utf-8").splitlines()) - 1)
    except OSError:
        return 0


def _self_test() -> int:
    """The gate must separate THREE states, and the test must exercise the split it actually makes.

    The previous self-test passed 4 of 4 while checking `on_disk - reachable` — the two-state logic
    this gate no longer has. A green self-test over code that is gone is worse than none: it reads
    as proof. Measured on contoso when the split landed: 10 declared, 8 undeclared-but-resolving,
    1 true orphan — and the old gate reported all 9 of the last two groups identically.
    """
    def classify(on_disk: set[str], declared: set[str], resolves: set[str]) -> tuple[int, int]:
        undeclared = on_disk - declared
        return (
            len([f for f in undeclared if f in resolves]),
            len([f for f in undeclared if f not in resolves]),
        )

    cases = [
        ("all declared -> clean",
         {"a"}, {"a"}, set(), (0, 0), 0),
        ("undeclared AND resolving -> an undeclared DEPENDENCY, not an orphan",
         {"a", "b"}, {"a"}, {"b"}, (1, 0), 1),
        ("undeclared and resolving nothing -> a TRUE orphan",
         {"a", "b"}, {"a"}, set(), (0, 1), 1),
        ("both kinds at once, counted separately",
         {"a", "b", "c"}, {"a"}, {"b"}, (1, 1), 1),
        ("declared but absent from disk is neither",
         {"a"}, {"a", "ghost"}, set(), (0, 0), 0),
        ("no registers at all -> clean",
         set(), set(), set(), (0, 0), 0),
    ]
    bad = 0
    for label, on_disk, declared, resolves, want_counts, want_exit in cases:
        got_counts = classify(on_disk, declared, resolves)
        got_exit = 1 if any(got_counts) else 0
        if got_counts != want_counts or got_exit != want_exit:
            bad += 1
            print(f"  FAIL  {label}: wanted {want_counts} exit {want_exit}, "
                  f"got {got_counts} exit {got_exit}")
    n = len(cases)
    print(f"\n{'FAIL' if bad else 'OK'} — self-test: {n - bad} of {n} seeded cases behaved")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
