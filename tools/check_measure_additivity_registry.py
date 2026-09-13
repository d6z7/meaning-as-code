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
On 2026-08-16 the <dataset> registry was populated by HAND rather than derived, and drifted immediately:
Stock's time axis was written ``non_additive`` instead of ``point_in_time``, and Target was written
additive on the categorical axis when the law says a Target is ``non_aggregable`` on BOTH — i.e. the
registry claimed Ideal Stock could be summed across markets. Nothing caught it, because the only
additivity gate in the estate checks a different artifact (the gold's ``dim_measure`` view).

This gate recomputes every registry row from the value domain and asserts equality, so the projection
can never silently disagree with the law it projects.

WHAT WAS MISSING, found by the 2026-09-12 framework-gate review
-----------------------------------------------------------------
This gate took `sys.argv[1]` as the root with no existence check and printed a bare "usage:" line only
on the WRONG argument count. A nonexistent root and "this bundle legitimately has no measure registry"
produced the byte-identical verdict — `PASS (nothing to project)`, exit 0 — so a typo'd path read as a
clean bundle. The two are now told apart: a root that is not a directory is COULD-NOT-RUN (exit 2); a
root that genuinely carries no lookup shaped like a measure registry is still a real, zero-denominator
PASS, printed as one.

OFFLINE + pure-structural. Usage:  python3 tools/check_measure_additivity_registry.py [bundle-root]
    exit 0 = the registry matches the law (or declares no measure_type)
    exit 1 = drift
    exit 2 = could not run (root missing, or the framework's own law is unreadable)
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import yaml

REQUIRED = ("measure_type", "additivity_time", "additivity_categorical")
NAME = "check_measure_additivity_registry"


class LawUnavailable(RuntimeError):
    """The framework's own MeasureType law could not be read — a setup failure, not a bundle defect."""


def measure_type_law(vocab_path: Path) -> dict:
    """{member_name: {"time": ..., "categorical": ...}} from mac_vocabulary.yaml#MeasureType.

    Takes the vocabulary PATH as a parameter, rather than reaching for the framework's own file
    directly, so a self-test can prove the refusal fires without touching the real vocabulary --
    the same principle _plugin.py uses for a bundle's declared plugin.
    """
    if not vocab_path.is_file():
        raise LawUnavailable(f"framework value domain not found at {vocab_path}")
    try:
        doc = yaml.safe_load(vocab_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        raise LawUnavailable(f"{vocab_path} did not parse: {exc}") from None
    members = (doc.get("MeasureType") or {}).get("members") or {}
    if not members:
        raise LawUnavailable(f"{vocab_path}#MeasureType declares no members")
    return members


def scan(root: Path, members: dict) -> tuple[list[str], int, int]:
    """errors, rows_checked, lookups_checked over every CSV shaped like a measure registry."""
    lookups_dir = root / "data" / "lookups"
    lookups = sorted(lookups_dir.glob("*.csv")) if lookups_dir.is_dir() else []
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
    return errors, rows_checked, checked


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()

    root = Path(a.root).resolve()
    vocab = Path(__file__).resolve().parent.parent / "mac_vocabulary.yaml"
    print(f"── measure-additivity-registry gate ── the law lives in {vocab.name}#MeasureType ── {root} ──\n")

    if not root.is_dir():
        print(f"could not run: {root} is not a directory", file=sys.stderr)
        return 2
    try:
        members = measure_type_law(vocab)
    except LawUnavailable as exc:
        print(f"could not run: {exc}", file=sys.stderr)
        return 2

    errors, rows_checked, checked = scan(root, members)

    for e in errors:
        print(f"  [ERROR] {e}")
    print()
    if errors:
        print(f"FAIL: {NAME} — {len(errors)} drift(s) over {rows_checked} row(s) in {checked} "
              f"lookup(s) examined — derive the columns from the value domain instead of writing "
              f"them by hand")
        return 1
    if not checked:
        print(f"PASS: {NAME} — 0 lookup(s) under data/lookups match the measure-registry shape "
              f"(measure_type/additivity_time/additivity_categorical) — nothing to project")
        return 0
    print(f"PASS: {NAME} — 0 drift(s) over {rows_checked} row(s) in {checked} lookup(s) examined")
    return 0


# ---------------------------------------------------------------------------------------------
# self-test: one mutant per reject class, plus a clean fixture that must pass and the liveness
# check that a real drift still fires. Rows are derived from the framework's OWN vocabulary
# (mac_vocabulary.yaml#MeasureType, public and generic) rather than typed, so the fixture cannot
# drift from the law it exercises.
# ---------------------------------------------------------------------------------------------

def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _row(name: str, law: dict, *, mutate_axis: str | None = None) -> dict:
    time_v, cat_v = law.get("time", ""), law.get("categorical", "")
    if mutate_axis == "time":
        time_v = time_v + "-MUTATED"
    elif mutate_axis == "categorical":
        cat_v = cat_v + "-MUTATED"
    return {"code": name.upper(), "measure_type": f"mac.MeasureType.{name}",
            "additivity_time": time_v, "additivity_categorical": cat_v}


def _run(root: str) -> int:
    argv = sys.argv
    sys.argv = ["check_measure_additivity_registry.py", root]
    try:
        return main()
    finally:
        sys.argv = argv


def _self_test() -> int:
    import tempfile

    fw_vocab = Path(__file__).resolve().parent.parent / "mac_vocabulary.yaml"
    try:
        members = measure_type_law(fw_vocab)
    except LawUnavailable as exc:
        print(f"could not run: {NAME} self-test needs the framework's own vocabulary: {exc}",
              file=sys.stderr)
        return 2
    # Two REAL members, read from the law rather than typed, so a rename in the vocabulary cannot
    # leave this fixture silently testing a member that no longer exists.
    names = sorted(n for n in members if (members[n].get("additivity") or {}).get("time")
                    and (members[n].get("additivity") or {}).get("categorical"))
    if len(names) < 1:
        print("could not run: mac_vocabulary.yaml#MeasureType has no fully-specified member to "
              "derive a fixture from", file=sys.stderr)
        return 2
    clean_name = names[0]
    clean_law = members[clean_name].get("additivity") or {}

    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # 1 · not a directory at all.
        missing = base / "does-not-exist"
        got = _run(str(missing))
        if got != 2:
            failures.append(f"not-a-directory: expected exit 2, got {got}")

        # 2 · a real directory with NO data/lookups plane at all — must be a PASS with an explicit
        #     zero denominator, never the same silent tick a nonexistent root used to produce, and
        #     never confused with class 1 by returning the same exit code for a different reason.
        empty = base / "empty-bundle"
        empty.mkdir()
        got = _run(str(empty))
        if got != 0:
            failures.append(f"no-lookups-plane: expected exit 0, got {got}")

        # 3 · a lookups plane that exists but holds nothing shaped like a measure registry —
        #     the checked=0 population must stay 0, not be inferred from row count.
        unrelated = base / "unrelated-lookup"
        _write_csv(unrelated / "data" / "lookups" / "country.csv",
                   [{"code": "A", "name": "somewhere"}])
        if measure_type_law(fw_vocab) != members:
            failures.append("fixture setup changed the real vocabulary — aborting")
        got = _run(str(unrelated))
        if got != 0:
            failures.append(f"unrelated-lookup-shape: expected exit 0, got {got}")

        # 4 · a registry that projects the law exactly — the clean fixture that must pass, over a
        #     NON-zero denominator this time.
        clean = base / "clean-registry"
        _write_csv(clean / "data" / "lookups" / "measure_type.csv", [_row(clean_name, clean_law)])
        got = _run(str(clean))
        if got != 0:
            failures.append(f"clean-registry: expected exit 0, got {got}")

        # 5 · liveness: a registry that DIVERGES from the law must still be caught.
        drifted = base / "drifted-registry"
        _write_csv(drifted / "data" / "lookups" / "measure_type.csv",
                   [_row(clean_name, clean_law, mutate_axis="time")])
        # prove the mutant actually mutated relative to the clean row
        clean_csv_row = _row(clean_name, clean_law)
        drift_csv_row = _row(clean_name, clean_law, mutate_axis="time")
        if clean_csv_row["additivity_time"] == drift_csv_row["additivity_time"]:
            failures.append("fixture 'drifted-registry' did not actually mutate additivity_time")
        got = _run(str(drifted))
        if got != 1:
            failures.append(f"drifted-registry: expected exit 1, got {got}")

    total = 5
    if failures:
        print(f"FAIL: {NAME} self-test — {len(failures)} of {total} assertions failed")
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"PASS: {NAME} self-test — {total}/{total} (not-a-directory refuses, an empty/unrelated "
          f"lookups plane is a real zero-denominator pass, a law-derived clean registry passes, a "
          f"mutated one is still caught)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
