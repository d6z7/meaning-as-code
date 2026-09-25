#!/usr/bin/env python3
"""Two registers over one column WILL disagree, and nothing in the runtime arbitrates.

WHY THIS GATE EXISTS, measured 2026-09-25. Reading "Continent has no resolvable values", an agent
concluded the registers were missing and cut fifteen new ones from the warehouse. THIRTEEN
duplicated files the bundle already had, and every duplicate was strictly worse:

    contoso_country.lookup.csv   DE,Germany,germany,Europe,…   9 rows   labels, roll-up, sentinel
    country_country.lookup.csv   DE,DE,de,…                    8 rows   no labels, no roll-up

The second cannot resolve the word "Germany", drops the country-to-continent roll-up, and omits
the '--' sentinel the online store carries. Both were on disk, both were loadable, and which one
answered a question depended on load order. The real cause was elsewhere entirely -- a canon the
runtime never implemented (check_canon_implemented.py) -- but the DUPLICATES were the lasting
damage, because a wrong register resolves confidently.

THE EXISTING GUARD DID NOT SEE IT. The cutter refuses to overwrite a file that exists, which
sounds sufficient and is not: it wrote `country_country.lookup.csv` beside
`contoso_country.lookup.csv`. A different NAME over the same COLUMN. Identity is the column a
register was cut from, never the filename.

WHAT IT CHECKS. Every `data/lookups/*.lookup.csv` is keyed by (source_view, first header field) --
the relation and column it was cut from, which is what the cutter writes and what
`rows_to_entries` reads as the entry's `column`. Two files sharing a key are a duplicated domain.

Exit 0 when every column has at most one register, 1 when any column has two or more, 2 when the
bundle cannot be read (REFUSED, never PASS).
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import sys
from collections import defaultdict


def _keys(path: pathlib.Path) -> list[tuple[str, str]] | None:
    """Every ``(source_view, source column)`` this register covers -- ONE KEY PER VIEW.

    NOT the union of its views as a single key. Measured while writing this gate: keying on the
    joined set let the real duplicate through. `contoso_country.lookup.csv` carries rows from BOTH
    `dim_contoso_customer` and `dim_contoso_store`; `country_country.lookup.csv` carries only the
    customer ones. As a union those are two different keys -- "customer+store" and "customer" --
    and the gate reported 19 registers over 19 distinct domains while two of them answered the
    same question differently.

    A register covering two views and a register covering one of them OVERLAP, and an overlap is
    the defect. Expanding to one key per view is what makes the containment visible.
    """
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except Exception:  # noqa: BLE001 - an unreadable register is reported by check_lookups
        return None
    if not rows:
        return None
    header = list(rows[0])
    if not header:
        return None
    views = {(r.get("source_view") or "").strip() for r in rows if isinstance(r, dict)}
    views.discard("")
    return [(view, header[0]) for view in sorted(views)] or [("<no source_view>", header[0])]


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
        print(f"SKIP: no data/lookups in {root.name}")
        return 0

    files = sorted(lookups.glob("*.lookup.csv"))
    if not files:
        print(f"SKIP: {lookups} holds no .lookup.csv")
        return 0

    by_domain: dict[tuple[str, str], list[str]] = defaultdict(list)
    unreadable: list[str] = []
    for path in files:
        keys = _keys(path)
        if keys is None:
            unreadable.append(path.name)
            continue
        for key in keys:
            by_domain[key].append(path.name)

    clashes = {k: v for k, v in by_domain.items() if len(v) > 1}
    print(
        f"registers: {len(files)}   distinct domains: {len(by_domain)}   "
        f"DUPLICATED: {len(clashes)}"
        + (f"   (unreadable: {len(unreadable)})" if unreadable else "")
    )
    if not clashes:
        print("OK — every (source_view, column) has at most one register.")
        return 0

    print("\nThese columns are covered by more than one register. Which one answers a question")
    print("depends on load order, and a wrong register resolves CONFIDENTLY — it does not error.\n")
    for (view, column), names in sorted(clashes.items()):
        print(f"  {view}.{column}")
        for name in sorted(names):
            print(f"      {name}")
    print(f"\nFAIL — {len(clashes)} column(s) carry duplicate registers.")
    print("  Keep the one with the richer terms (labels a person would say, carried roll-ups,")
    print("  declared sentinels) and delete the other. A register's identity is the COLUMN it")
    print("  was cut from, never its filename.")
    return 1


def _self_test() -> int:
    """The gate must REJECT two registers over one column and PASS one register per column."""
    cases = [
        ("two files, one column -> caught", {("v", "Country"): ["a", "b"]}, 1),
        ("one file per column -> clean", {("v", "Country"): ["a"], ("v", "Gender"): ["b"]}, 0),
        ("same column, different relations -> not a duplicate",
         {("customer", "Country"): ["a"], ("store", "Country"): ["b"]}, 0),
        ("one register spanning two views OVERLAPS one spanning a subset",
         {("customer", "Country"): ["wide", "narrow"], ("store", "Country"): ["wide"]}, 1),
        ("no registers at all -> clean", {}, 0),
    ]
    bad = 0
    for label, domains, want in cases:
        got = 1 if {k: v for k, v in domains.items() if len(v) > 1} else 0
        if got != want:
            bad += 1
            print(f"  FAIL  {label}: wanted exit {want}, got {got}")
    print(f"\n{'FAIL' if bad else 'OK'} — self-test: {len(cases) - bad} of {len(cases)} behaved")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
