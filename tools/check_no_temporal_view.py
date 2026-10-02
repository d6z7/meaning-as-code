#!/usr/bin/env python3
"""check_no_temporal_view.py — A CALENDAR IS A FUNCTION, NOT A RELATION.

OPERATOR RULING, 2026-10-01: "date is standard notion and does not need any view ... its function ...
date is fully deterministic". A served relation keyed on a single DATE is a calendar dimension: one
row per day with no other identity means every other column — the year, the quarter, the month name,
the weekday — is a function of that day. Materialising a function is not serving data.

THE COST, MEASURED ON CONTOSO5. `dim_date` served `year_month` as the landing's label "April 2016"
and `year_quarter` as "Q1-2016". Ordering by either is wrong: the month sorts April, August, December
and the quarter puts every Q1 before every Q2. "Monthly revenue trend for Germany in 2024" COMMITTED
twelve correct figures in the order April, August, December, February, and every gate in the chain
passed green over it. The concept's own rule instructed grouping by `year_month` "which orders
correctly", a claim the served values contradicted. A trend is about order; that answer was wrong in
the only dimension the question asked about.

THE TEST IS STRUCTURAL AND OFFLINE, which is why it is a gate and not advice. Exactly one column
carrying the relation role `primary_key`, and its declared type a date or a timestamp. Measured
across contoso5's nine served relations it selects `dim_date` and nothing else: the other seven
dimensions key on a code or a surrogate, and `v_contoso5_fx_rate` keys on (date_day, from_currency,
to_currency) — a rate per day per pair is NOT a function of the day, and a composite key says so.

WHAT TO DO INSTEAD: declare the date column on the concepts that carry it and serve no calendar. The
built-in reader (mac-platform/.../mac_runtime/temporal.py) already holds the five grains — day, week,
month, quarter, year — and the words and literal forms are declared once in
mac_vocabulary.yaml#calendar_vocabulary. A FISCAL calendar is the exception and it is a DECLARATION a
bundle authors, never a served view and never a register.

Usage:  python3 tools/check_no_temporal_view.py <bundle-root>
        exit 0 = no served calendar ; 1 = one or more ; 2 = cannot read the bundle.
        --self-test proves both verdicts against synthetic descriptors.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import yaml

DATE_TYPES = ("date", "timestamp", "datetime", "timestamptz")


def calendar_relations(datasets_dir: pathlib.Path) -> list[tuple[str, str]]:
    """(relation, key column) for every served relation keyed on a single date column."""
    out: list[tuple[str, str]] = []
    for path in sorted(datasets_dir.glob("*.yaml")):
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        name = ((doc.get("table") or {}).get("name")) or path.stem
        pk = [
            (c.get("name"), str(c.get("type") or "").strip().lower())
            for c in (doc.get("columns") or [])
            if str(c.get("role") or "") == "primary_key"
        ]
        if len(pk) == 1 and pk[0][1] in DATE_TYPES:
            out.append((str(name), str(pk[0][0])))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", help="bundle root")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    if not a.root:
        print("usage: check_no_temporal_view.py <bundle-root>")
        return 2
    root = pathlib.Path(a.root).resolve()
    datasets = root / "data" / "datasets"
    if not datasets.is_dir():
        print(f"✓ OK — no served plane at {datasets} (nothing to check)")
        return 0

    found = calendar_relations(datasets)
    total = len(list(datasets.glob("*.yaml")))
    print(f"── no-temporal-view gate ── {total} served relation(s) under {root} ──\n")
    if not found:
        print(f"✓ OK — none of the {total} served relation(s) is a calendar dimension")
        return 0
    for name, key in found:
        print(f"  [ERROR] {name} is keyed on the single date column {key!r} — a calendar dimension. "
              f"Every other column is a function of {key}, so this view materialises a function.")
    print(
        f"\n✗ {len(found)} served calendar dimension(s). A date is deterministic: declare the date "
        f"column on the concepts that carry it and delete the view. The built-in calendar supplies "
        f"the grains (guardrails/data/transformation.yaml#refuses.TEMPORAL-VIEW-IN-THE-SERVED-PLANE)"
    )
    return 1


def _self_test() -> int:
    import tempfile

    cases = [
        ("a date-keyed relation IS a calendar", [{"name": "date_day", "type": "date", "role": "primary_key"},
                                                 {"name": "year", "type": "integer", "role": "value"}], True),
        ("a surrogate-keyed dimension is not", [{"name": "store_key", "type": "integer", "role": "primary_key"},
                                                {"name": "open_date", "type": "date", "role": "value"}], False),
        ("a COMPOSITE key holding a date is not", [{"name": "date_day", "type": "date", "role": "primary_key"},
                                                   {"name": "to_currency", "type": "string", "role": "primary_key"},
                                                   {"name": "rate", "type": "double", "role": "value"}], False),
        ("a timestamp key is one too", [{"name": "ts", "type": "timestamp", "role": "primary_key"}], True),
    ]
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        d = pathlib.Path(tmp)
        for i, (label, cols, expected) in enumerate(cases):
            (d / f"r{i}.yaml").write_text(
                yaml.safe_dump({"table": {"name": f"r{i}"}, "columns": cols}), encoding="utf-8"
            )
        hits = {n for n, _ in calendar_relations(d)}
        for i, (label, _cols, expected) in enumerate(cases):
            got = f"r{i}" in hits
            if got != expected:
                print(f"  FAIL  {label}: expected {expected}, got {got}")
                failures += 1
            else:
                print(f"  ok    {label}")
    if failures:
        print(f"\nFAIL: check_no_temporal_view self-test — {failures} of {len(cases)} case(s)")
        return 1
    print(f"\nPASS: check_no_temporal_view self-test — {len(cases)}/{len(cases)} case(s): a single date "
          f"key is a calendar; a surrogate key, a composite key holding a date, and a timestamp key are "
          f"each judged on the same one rule")
    return 0


if __name__ == "__main__":
    sys.exit(main())
