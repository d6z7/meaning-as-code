#!/usr/bin/env python3
"""check_measure_additivity_registry.py — the additivity law must not be restated, only projected.

THE LAW
-------
How a measure aggregates is defined ONCE, in this framework's closed value domain
``mac_vocabulary.yaml#MeasureType``: each member (Flow / Stock / Intensive / Target) carries an
``additivity`` map over the two axes (``time``, ``categorical``) whose values are
``mac.aggregation_effect.*`` terms.

A source may MATERIALIZE that law into its measure registry (a lookup CSV carrying ``measure_type`` +
``additivity_time`` + ``additivity_categorical``) so consumers can read SUM-vs-point-in-time without
resolving the vocabulary. Materializing is fine; DIVERGING is not.

WHY THIS EXISTS
---------------
On 2026-08-16 the fpl2 registry was populated by HAND rather than derived, and drifted immediately:
Stock's time axis was written ``non_additive`` instead of ``point_in_time``, and Target was written
additive on the categorical axis when the law says a Target is ``non_aggregable`` on BOTH — i.e. the
registry claimed Ideal Stock could be summed across markets. Nothing caught it, because the only
additivity gate in the estate checks a different artifact (the gold's ``dim_measure`` view).

This gate recomputes every registry row from the value domain and asserts equality, so the projection
can never silently disagree with the law it projects.

OFFLINE + pure-structural. Usage:  python3 tools/check_measure_additivity_registry.py <bundle-root>
    exit 0 = the registry matches the law (or declares no measure_type) ; exit 1 = drift.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import yaml

REQUIRED = ("measure_type", "additivity_time", "additivity_categorical")


def main(argv) -> int:
    if len(argv) != 2:
        print("usage: check_measure_additivity_registry.py <bundle-root>")
        return 2
    root = Path(argv[1]).resolve()
    vocab = Path(__file__).resolve().parent.parent / "mac_vocabulary.yaml"
    print(f"── measure-additivity-registry gate ── the law lives in {vocab.name}#MeasureType ── {root} ──\n")
    if not vocab.exists():
        print(f"  [ERROR] framework value domain not found at {vocab}")
        return 1
    members = ((yaml.safe_load(vocab.read_text()) or {}).get("MeasureType") or {}).get("members") or {}
    if not members:
        print("  [ERROR] mac_vocabulary.yaml#MeasureType declares no members")
        return 1

    lookups = sorted((root / "data" / "lookups").glob("*.csv")) if (root / "data" / "lookups").exists() else []
    errors: list[str] = []
    checked = rows_checked = 0
    for lk in lookups:
        try:
            rows = list(csv.DictReader(lk.read_text(encoding="utf-8").splitlines()))
        except Exception as e:  # noqa: BLE001
            print(f"  [WARN]  cannot read {lk.name}: {e}")
            continue
        if not rows or not all(c in rows[0] for c in REQUIRED):
            continue                                   # not a measure registry — nothing to check
        checked += 1
        for i, r in enumerate(rows, start=2):          # +2: header is line 1
            rows_checked += 1
            term = (r.get("measure_type") or "").strip()
            name = term.split(".")[-1]
            if name not in members:
                errors.append(f"{lk.name}:{i} measure_type '{term}' is not a member of the closed "
                              f"domain {sorted(members)}")
                continue
            law = (members[name].get("additivity") or {})
            for axis, col in (("time", "additivity_time"), ("categorical", "additivity_categorical")):
                want, got = str(law.get(axis, "")).strip(), (r.get(col) or "").strip()
                if want != got:
                    errors.append(f"{lk.name}:{i} {name}.{axis} — registry says '{got}', "
                                  f"the law says '{want}'")

    for e in errors:
        print(f"  [ERROR] {e}")
    print()
    if errors:
        print(f"✗ {len(errors)} registry cell(s) disagree with mac.MeasureType — derive the columns from "
              f"the value domain instead of writing them by hand")
        return 1
    if not checked:
        print("✓ OK — no measure registry declares measure_type/additivity (nothing to project)")
        return 0
    print(f"✓ OK — {rows_checked} registry row(s) in {checked} lookup(s) project mac.MeasureType exactly")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
