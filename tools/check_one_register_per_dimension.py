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


def members(path: pathlib.Path) -> frozenset | None:
    """The register's VALUE SET — its code column, which is the first header field.

    THE OTHER HALF OF P4, AND THE HALF THE TITLE MEANT. `_keys` above answers "do two registers
    cover one column", which is a real defect and not this one. P4's TITLE rules ONE REGISTER PER
    DIMENSION; its BODY rules "refuse to write where a register already covers that source column";
    the cutter keys on (relation, column) and this gate counted the same pair and called it a
    "domain". Every layer agreed with itself and none did what the title said.

    Measured on contoso5, 2026-09-29: 48 register files holding 25 DISTINCT value sets — 23
    redundant copies, 47 %, the five currency codes stored EIGHT times. The gate read:

        registers: 48   distinct domains: 48   DUPLICATED: 0
        OK — every (source_view, column) has at most one register.

    A gate is only as true as its denominator. Two files holding the same members ARE one register
    however they are named and whatever column each was cut from — that is what a dimension is.
    """
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except Exception:  # noqa: BLE001 - an unreadable register is reported by check_lookups
        return None
    if not rows:
        return None
    code = list(rows[0])[0] if list(rows[0]) else None
    if not code:
        return None
    vals = {(r.get(code) or "").strip() for r in rows if isinstance(r, dict)}
    vals.discard("")
    return frozenset(vals) or None


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
    by_members: dict[frozenset, list[str]] = defaultdict(list)
    unreadable: list[str] = []
    for path in files:
        keys = _keys(path)
        if keys is None:
            unreadable.append(path.name)
            continue
        for key in keys:
            by_domain[key].append(path.name)
        vals = members(path)
        if vals is not None:
            by_members[vals].append(path.name)

    clashes = {k: v for k, v in by_domain.items() if len(v) > 1}
    copies = {k: v for k, v in by_members.items() if len(v) > 1}
    redundant = sum(len(v) - 1 for v in copies.values())
    print(
        f"registers: {len(files)}   distinct VALUE SETS: {len(by_members)}   "
        f"redundant copies: {redundant}   two-over-one-column: {len(clashes)}"
        + (f"   (unreadable: {len(unreadable)})" if unreadable else "")
    )
    if not clashes and not copies:
        print("OK — one register per value set, and no column covered twice.")
        return 0

    if copies:
        print("\nONE VALUE SET, MANY FILES. A register IS its members: these hold the same domain")
        print("under different names, so the same question resolves against whichever loads.\n")
        for vals, names in sorted(copies.items(), key=lambda kv: (-len(kv[1]), sorted(kv[1])[0])):
            sample = ", ".join(sorted(vals)[:4]) + (" …" if len(vals) > 4 else "")
            print(f"  {len(vals)} member(s) in {len(names)} files:  {sample}")
            for name in sorted(names):
                print(f"      {name}")
    if clashes:
        print("\nTWO REGISTERS OVER ONE COLUMN. Which one answers a question depends on load")
        print("order, and a wrong register resolves CONFIDENTLY — it does not error.\n")
        for (view, column), names in sorted(clashes.items()):
            print(f"  {view}.{column}")
            for name in sorted(names):
                print(f"      {name}")
    print(f"\nFAIL — {redundant} redundant copy(ies) of {len(copies)} value set(s); "
          f"{len(clashes)} column(s) covered twice.")
    print("  A register's identity is its VALUE SET. One file per set, attached to every column")
    print("  that carries it — see decisions/PROPOSED-2026-09-29_register-policy.md.")
    return 1


def _self_test() -> int:
    """The gate must REJECT one value set stored twice, and two registers over one column.

    IT RUNS `main` OVER REAL FILES. The previous version of this function restated the clash rule
    inline —

        got = 1 if {k: v for k, v in domains.items() if len(v) > 1} else 0

    — so it exercised neither `_keys` nor `members` nor `main`, and would have gone on passing
    through any change to either. It is the same tautology this estate has written before: a test
    that asserts its own restatement of the rule proves the restatement.
    """
    import tempfile

    ok = [0, 0]

    def case(what, files, want):
        ok[0] += 1
        with tempfile.TemporaryDirectory() as tmp:
            look = pathlib.Path(tmp) / "data" / "lookups"
            look.mkdir(parents=True)
            for name, body in files.items():
                (look / name).write_text(body, encoding="utf-8")
            import contextlib
            import io
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                got = main([tmp])
        good = got == want
        ok[1] += good
        print(("  ✓ " if good else f"  ✗ (exit {got}, wanted {want}) ") + what)

    def reg(code, vals, view="v"):
        head = f"{code},label,search_key,source_view,source_schema,confidence,note\n"
        return head + "".join(f"{v},{v},{v.lower()},{view},main,I,measured\n" for v in vals)

    CUR = ["AUD", "CAD", "EUR", "GBP", "USD"]

    case("one register per value set is clean",
         {"a.lookup.csv": reg("Country", ["DE", "FR"]),
          "b.lookup.csv": reg("Gender", ["female", "male"])}, 0)
    # THE DEFECT THIS GATE COULD NOT SEE. Same five members, two spellings of the column, two
    # relations — contoso5 ships EIGHT of these and the gate read `DUPLICATED: 0`.
    case("MUTANT one value set under two column names and two relations is REFUSED",
         {"sales_currencycode.lookup.csv": reg("CurrencyCode", CUR, view="sales"),
          "dim_currency_currency_code.lookup.csv": reg("currency_code", CUR, view="dim_currency")}, 1)
    case("MUTANT the same set in eight files is REFUSED",
         {f"r{i}.lookup.csv": reg(f"c{i}", CUR, view=f"v{i}") for i in range(8)}, 1)
    case("two registers over ONE column is still REFUSED — the original defect",
         {"rich.lookup.csv": reg("Country", ["DE", "FR"], view="customer"),
          "poor.lookup.csv": reg("Country", ["DE", "FR", "GB"], view="customer")}, 1)
    # NOT A DUPLICATE, and this is the case the value-set rule must not over-reach into: `state`
    # is 67 NAMES on dim_location and 565 CODES on customer. Same notion, different members, two
    # registers — refusing these would force one of them to be wrong.
    case("one notion with DIFFERENT members is two registers, not a duplicate",
         {"state_names.lookup.csv": reg("state", ["Alaska", "Arkansas"], view="dim_location"),
          "state_codes.lookup.csv": reg("State", ["AK", "AL"], view="customer")}, 0)
    case("no registers at all is clean", {}, 0)

    print(("PASS" if ok[1] == ok[0] else "FAIL")
          + f": check_one_register_per_dimension self-test — {ok[1]}/{ok[0]} case(s), run through "
            f"`main` over real files, not through a restatement of the rule.")
    return 0 if ok[1] == ok[0] else 1


if __name__ == "__main__":
    sys.exit(main())
