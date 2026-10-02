#!/usr/bin/env python3
"""A concept may not declare a canon the runtime does not implement.

WHY THIS GATE EXISTS, measured on contoso 2026-09-25. Six `realized_by.udf` bindings named a verb
the runtime has never spoken:

    4 x mac.canon.grouping_from_register     (Continent, Brand, ProductCategory, ProductSubcategory)
    2 x mac.canon.refuse_measure_no_row      (GrossSalesAmount, NetSalesAmount)

Every one of them parses as valid YAML, passes every other gate, and does NOTHING. The loader
recognised two names and dropped the rest with a bare `continue`.

WHAT IT COST. ProductSubcategory could not resolve a single one of its 32 members -- 'Camcorders',
'Air Conditioners', any of them -- while its sibling ProductCategory resolved all 8. The only
difference was that ProductCategory ALSO carried a `resolve_by_register` rule. Continent had the
same shape, so `Continent='Europe'` refused a value DuckDB returns from SELECT DISTINCT.

AND THE DIAGNOSIS WENT WRONG BECAUSE OF IT. Reading "no values for Continent", an agent concluded
the REGISTERS were missing and cut fifteen new ones from the warehouse. Thirteen duplicated files
the bundle already had, each strictly worse -- country_country labelled DE as 'DE' where
contoso_country labels it 'Germany' and carries the continent roll-up. A whole day of work
treating a symptom, because an unimplemented declaration is indistinguishable from an absent one.

The declarations were not careless. They were careful, correct, named the right files, and were
addressed to a listener that did not exist.

WHAT IT CHECKS. Every `realized_by` ANYWHERE in a concept document -- contoso puts four under a
top-level `members:` block that nothing reads -- against `mac_runtime.canon.IMPLEMENTED`.

Exit 0 when every declared canon is implemented, 1 when any is not, 2 when the bundle or the
runtime cannot be read (REFUSED, never PASS -- a gate that cannot see its subject must not report
success).
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _neighbours  # noqa: E402  — ONE home for the sibling runtime's location


def _bindings(node: Any, path: str = "") -> list[tuple[str, str]]:
    """Every ``(yaml path, udf)`` in a document, wherever the binding sits."""
    out: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "realized_by":
                items = value if isinstance(value, list) else [value]
                for item in items:
                    if isinstance(item, dict) and isinstance(item.get("udf"), str):
                        out.append((f"{path}.{key}" if path else key, item["udf"]))
            out.extend(_bindings(value, f"{path}.{key}" if path else str(key)))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            out.extend(_bindings(item, f"{path}[{i}]"))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)

    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.bundle).resolve()
    concepts = root / "ontology" / "concepts"
    if not concepts.is_dir():
        print(f"SKIP: no ontology/concepts in {root.name}")
        return 0

    try:
        import yaml
    except ImportError as exc:
        print(f"REFUSED: PyYAML is not importable ({exc}).")
        return 2

    try:
        _neighbours.ensure_runtime_on_path()
        from mac_runtime.canon import IMPLEMENTED, KNOWN_UNIMPLEMENTED
    except ImportError as exc:
        print(
            f"REFUSED: mac_runtime.canon is not importable ({exc}). A gate that cannot ask the "
            f"runtime what it implements must not report PASS."
        )
        return 2

    declared: list[tuple[str, str, str]] = []  # (concept file, yaml path, udf)
    for path in sorted(concepts.rglob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - an unreadable concept is REFUSED, not passed
            print(f"REFUSED: {path.relative_to(root)} is not readable — {type(exc).__name__}: {exc}")
            return 2
        for yaml_path, udf in _bindings(raw):
            declared.append((str(path.relative_to(root)), yaml_path, udf))

    if not declared:
        print(f"SKIP: {root.name} declares no canon bindings")
        return 0

    bad = [(f, p, u) for f, p, u in declared if u not in IMPLEMENTED]
    print(
        f"canon bindings declared: {len(declared)}   implemented: {len(declared) - len(bad)}   "
        f"UNIMPLEMENTED: {len(bad)}"
    )
    if not bad:
        print("OK — every declared canon is one the runtime implements.")
        return 0

    print("\nThese declarations name a verb the runtime does not speak. They parse, they pass")
    print("every other gate, and they do NOTHING — which is indistinguishable, from inside the")
    print("bundle, from never having been written.\n")
    for file, yaml_path, udf in bad:
        note = KNOWN_UNIMPLEMENTED.get(udf)
        print(f"  {file}")
        print(f"      {yaml_path}.udf = {udf}")
        print(f"      {'known, unimplemented: ' + note[:100] if note else 'NOT RECOGNISED AT ALL'}")
    print(f"\nFAIL — {len(bad)} of {len(declared)} canon bindings are not implemented.")
    print("  Either implement the canon and add it to mac_runtime.canon.IMPLEMENTED, or")
    print("  express the meaning with one that exists — resolve_by_register binds EVERY code a")
    print("  name covers, which is already a group over its members.")
    return 1


def _self_test() -> int:
    """The gate must REJECT an unimplemented canon and PASS an implemented one.

    A gate whose discrimination is never demonstrated is indistinguishable from one that always
    passes, and this file exists because a silent pass cost four registers and a day of work.
    """
    nested = {
        "concept": {"name": "X"},
        "members": {"realized_by": {"udf": "mac.canon.grouping_from_register"}},
        "contract": {"rules": [{"realized_by": [{"udf": "mac.canon.resolve_by_register"}]}]},
    }
    found = {u: p for p, u in _bindings(nested)}
    cases = [
        ("finds a binding under a top-level members: block",
         "mac.canon.grouping_from_register" in found),
        ("finds a binding inside a contract rule LIST",
         "mac.canon.resolve_by_register" in found),
        ("reports the yaml path, not just the udf",
         found.get("mac.canon.grouping_from_register") == "members.realized_by"),
        ("finds nothing in a document with no bindings", not _bindings({"concept": {"name": "Y"}})),
    ]
    bad = sum(1 for _, ok in cases if not ok)
    for label, ok in cases:
        if not ok:
            print(f"  FAIL  {label}")
    print(f"\n{'FAIL' if bad else 'OK'} — self-test: {len(cases) - bad} of {len(cases)} behaved")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
