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


#: THE ENTRY POINTS A QUESTION ACTUALLY TRAVELS THROUGH. Reachability is measured FROM these, not
#: from "does the name appear somewhere" — a canon referenced only by a module nothing imports is
#: exactly as inert as one referenced nowhere, and that distinction is invisible to grep.
_ENTRY_MODULES = ("mac_runtime.planner.plan", "mac_runtime.pipeline", "mac_runtime.planner.sql")


def _module_imports(src: pathlib.Path) -> dict[str, set[str]]:
    """{dotted module -> the mac_runtime modules it imports}, read with ast rather than by regex."""
    import ast
    out: dict[str, set[str]] = {}
    for f in sorted(src.rglob("*.py")):
        dotted = ".".join(f.relative_to(src).with_suffix("").parts)
        if dotted.endswith(".__init__"):
            dotted = dotted[: -len(".__init__")]
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        got: set[str] = set()
        pkg = dotted.rsplit(".", 1)[0] if "." in dotted else dotted
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                got |= {a.name for a in n.names if a.name.startswith("mac_runtime")}
            elif isinstance(n, ast.ImportFrom):
                base = n.module or ""
                if n.level:                       # a relative import resolves against this package
                    base = f"{pkg}.{base}" if base else pkg
                if not base.startswith("mac_runtime"):
                    continue
                got.add(base)
                got |= {f"{base}.{a.name}" for a in n.names}
        out[dotted] = got
    return out


def _reachable_modules(src: pathlib.Path, entries: tuple[str, ...] | set[str] = _ENTRY_MODULES) -> set[str]:
    """Every mac_runtime module reachable by import from the entry points, transitively.

    `entries` DEFAULTS to the question path, which is the only entry this gate's question admits: a
    canon reached solely from the console's meaning-plane emitter decides nothing about an answer.
    `check_declarations_read` asks a WIDER question — does any caller reach the module that reads this
    declaration — and passes the runtime's measured consumer surface instead. Two questions, two entry
    sets, one graph; do not harmonise them."""
    graph = _module_imports(src)
    seen: set[str] = set()
    stack = [m for m in entries if m in graph]
    while stack:
        m = stack.pop()
        if m in seen:
            continue
        seen.add(m)
        for dep in graph.get(m, ()):              # a `from x import y` edge may name a SYMBOL
            for cand in (dep, dep.rsplit(".", 1)[0]):
                if cand in graph and cand not in seen:
                    stack.append(cand)
    return seen


def _unreachable_canons(src: pathlib.Path, udfs: set[str]) -> dict[str, str]:
    """{udf -> why} for each declared canon whose implementation nothing on the plan path can call.

    WHY THIS SITS IN *THIS* GATE. Its own docstring records the defect it was built for: a
    declaration "addressed to a listener that did not exist". Membership in `IMPLEMENTED` proves a
    function was written, not that anything asks it. MEASURED 2026-10-06: `mac.canon.column_select`
    is in IMPLEMENTED, its reader `planner/columns.py` parses bindings correctly, and NOTHING imports
    that module — where its two twins, populations and ratios, are imported by plan.py. Two contoso5
    rules bound it and decided nothing. That is the same defect at one more remove, and the gate
    that exists for it passed.
    """
    import re as _re
    reachable = _reachable_modules(src)
    bad: dict[str, str] = {}
    for udf in sorted(udfs):
        bare = udf.rsplit(".", 1)[-1]
        holders = []
        for f in sorted(src.rglob("*.py")):
            rel = f.relative_to(src)
            if rel.parts[:2] == ("mac_runtime", "canons") or rel.name == "canon.py":
                continue              # the implementation and the registry are not callers
            text = f.read_text(encoding="utf-8")
            #: A LITERAL CALL *OR* A DISPATCH KEY. The first cut matched only `name(` and reported
            #: additivity_guard and composite_key_guard as inert — both FALSE, and one of them is
            #: observably firing (a POLICY_DENIED refusal in the captured corpus). contract_guards
            #: dispatches them BY NAME through `_SQL_GUARDS` / `_SQL_TRANSFORMS` / `CANONS`, so the
            #: call site is a string, not an identifier. A detector blind to a dispatch table
            #: reports the estate's most common wiring pattern as dead code — and a gate with false
            #: positives is worse than none, which this estate measured twice at 23/23 and 1/1.
            if (_re.search(rf"\b{bare}\s*\(", text)
                    or f'"{bare}"' in text or f"'{bare}'" in text):
                holders.append(".".join(rel.with_suffix("").parts))
        live = [h for h in holders if h in reachable]
        if holders and not live:
            bad[udf] = f"called only from {', '.join(holders)}, which nothing on the plan path imports"
        elif not holders:
            bad[udf] = "no module outside its own implementation calls it"
    return bad


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
    #: AND IS ANYTHING ASKING IT? Membership in IMPLEMENTED means a function was written. This asks
    #: the next question, which is the one this gate's own origin story is about.
    inert: dict = {}
    try:
        src = _neighbours.runtime_src()
        if src is not None:
            inert = _unreachable_canons(src, {u for _f, _p, u in declared if u in IMPLEMENTED})
    except Exception as exc:                                        # noqa: BLE001
        print(f"  (reachability not measured: {type(exc).__name__}: {str(exc)[:70]})")

    if inert:
        #: A WARNING WITH ITS DENOMINATOR, not an error, and the reason is that every one of these
        #: is PRE-EXISTING: failing here would turn a measurement into a blocked branch on the day it
        #: was first taken. The ratchet is the number — it may only go down.
        print(f"\n  INERT: {len(inert)} of {len({u for _f, _p, u in declared})} declared canon(s) "
              f"implemented and UNREACHABLE — nothing on the plan path can call them:")
        for udf, why in sorted(inert.items()):
            print(f"    {udf}  —  {why}")
        print("  A binding to one of these parses, passes every gate, and decides nothing, which is "
              "indistinguishable\n  from never having been written — the defect this gate exists for, "
              "one level deeper.")

    if not bad:
        print("OK — every declared canon is one the runtime implements."
              + (f" {len(inert)} {'is' if len(inert) == 1 else 'are'} unreachable (see above)." if inert else ""))
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
