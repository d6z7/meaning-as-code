#!/usr/bin/env python3
"""check_query_grammar.py — the query grammar against the runtime it describes.

WHY THIS EXISTS. `grammar/query_grammar.yaml` is a declaration, and a declaration nothing reads is
this estate's recorded defect: "the runtime does not read the declarations it has". The grammar is
not yet an INPUT to the planner, so without this gate it would be prose in YAML clothing — stale
the first time an operation is added and nobody edits it.

WHAT IT PROVES, and each is a way the two can drift apart:
  R1  the vocabularies agree ......... every operation the runtime has is described, and no
                                       operation is described that the runtime does not have
  R2  the branch claims are true ..... `branches_in_runtime: true` means the planner really does
                                       test for that operation by name, and false means it does not
  R3  the fold-gate set agrees ....... the operations listing `non_fold_ops` in `branches` are
                                       exactly the members of the planner's own `_NON_FOLD_OPS`

WHAT IT DOES NOT PROVE. That the CONTRIBUTIONS are right — that `list` really emits SELECT
DISTINCT. That is what the corpus replay is for (acceptance/tools/intent_killtest.py in a bundle),
and this gate deliberately does not restate it: a gate that re-derives its subject cannot fail.

Usage:  python3 tools/check_query_grammar.py [--runtime <path to mac-runtime>] [--self-test]
Exit:   0 = grammar and runtime agree · 1 = they disagree · 2 = the runtime could not be read
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
GRAMMAR = HERE.parent / "grammar" / "query_grammar.yaml"


def _runtime_root(explicit: str | None) -> Path | None:
    """The planner package: --runtime, then $MAC_RUNTIME, then the usual sibling checkout."""
    for cand in (explicit, os.environ.get("MAC_RUNTIME"),
                 HERE.parents[1] / "mac-platform/packages/mac-runtime/src/mac_runtime"):
        if cand and Path(cand).is_dir():
            return Path(cand)
    return None


def runtime_facts(root: Path) -> tuple[set[str], set[str], set[str]]:
    """(every operation, the ones named in planner code, the `_NON_FOLD_OPS` members).

    READ AS TEXT, NOT IMPORTED. The gate must run in a checkout that cannot import the runtime
    (no venv, no install), and an import would also run module-level code this gate has no
    business running.
    """
    models = (root / "models.py").read_text()
    tree = ast.parse(models)
    members: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "OperationKind":
            for stmt in node.body:
                if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant):
                    members.add(str(stmt.value.value))
    planner = "\n".join(
        p.read_text() for p in sorted((root / "planner").glob("*.py"))
    )
    # a branch is a test BY NAME: `OperationKind.LIST`, `_OpK.EXISTS`, `_OpK2.COUNT`
    named = {m.lower() for m in re.findall(r"(?:OperationKind|_OpK2?)\.([A-Z_]+)", planner)}
    non_fold: set[str] = set()
    if m := re.search(r"_NON_FOLD_OPS\s*=\s*\{([^}]*)\}", planner):
        non_fold = {x.lower() for x in re.findall(r"\.([A-Z_]+)", m.group(1))}
    return members, named & members, non_fold


def check(grammar: dict, members: set[str], named: set[str], non_fold: set[str]) -> list[str]:
    ops = {o["name"]: o for o in grammar["operations"]}
    bad: list[str] = []

    for missing in sorted(members - set(ops)):
        bad.append(f"R1 the runtime has operation {missing!r} and the grammar does not describe it")
    for extra in sorted(set(ops) - members):
        bad.append(f"R1 the grammar describes operation {extra!r} and the runtime does not have it")

    for name in sorted(set(ops) & members):
        claimed = bool(ops[name].get("branches_in_runtime"))
        actual = name in named
        if claimed != actual:
            bad.append(
                f"R2 {name!r} claims branches_in_runtime={claimed} and the planner "
                f"{'does' if actual else 'does not'} test for it by name"
            )

    claimed_nf = {n for n, o in ops.items() if "non_fold_ops" in (o.get("branches") or [])}
    if non_fold and claimed_nf != non_fold:
        bad.append(
            f"R3 branch: non_fold_ops is {sorted(claimed_nf)} and the planner's _NON_FOLD_OPS "
            f"is {sorted(non_fold)}"
        )
    return bad


def self_test() -> int:
    """One mutant per reject class. A gate that cannot go red is the zero-denominator pass."""
    base = {
        "operations": [
            {"name": "count", "branches_in_runtime": True, "branches": ["non_fold_ops"]},
            {"name": "sum", "branches_in_runtime": False},
        ]
    }
    members, named, non_fold = {"count", "sum"}, {"count"}, {"count"}
    cases = [
        ("clean", base, members, named, non_fold, 0),
        ("R1 runtime has one the grammar lacks", base, members | {"rank"}, named, non_fold, 1),
        ("R1 grammar has one the runtime lacks", base, {"count"}, named, {"count"}, 1),
        ("R2 branch claimed and absent",
         {"operations": [{"name": "count", "branches_in_runtime": True, "branches": ["non_fold_ops"]},
                         {"name": "sum", "branches_in_runtime": True}]},
         members, named, non_fold, 1),
        ("R3 fold-gate set disagrees",
         {"operations": [{"name": "count", "branches_in_runtime": True},
                         {"name": "sum", "branches_in_runtime": False}]},
         members, named, non_fold, 1),
    ]
    fails = 0
    for label, g, m, n, nf, want in cases:
        got = 1 if check(g, m, n, nf) else 0
        ok = got == want
        print(("  ✓ " if ok else "  ✗ ") + label)
        fails += 0 if ok else 1
    print(f"\n{'self-test passed' if not fails else str(fails) + ' SELF-TEST FAILED'}")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runtime")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        print("── check_query_grammar --self-test ──")
        return self_test()

    root = _runtime_root(args.runtime)
    if root is None:
        print("SKIP: mac-runtime not found — pass --runtime <path> or set MAC_RUNTIME.")
        print("      The grammar was NOT checked. This is not a pass.")
        return 2
    grammar = yaml.safe_load(GRAMMAR.read_text())
    members, named, non_fold = runtime_facts(root)
    bad = check(grammar, members, named, non_fold)
    print(f"── query grammar vs runtime ── {len(grammar['operations'])} described · "
          f"{len(members)} in the runtime · {len(named)} branched · {len(non_fold)} in the fold gate ──")
    for line in bad:
        print(f"  [DRIFT] {line}")
    print("\n" + ("✗ " + str(len(bad)) + " disagreement(s)" if bad
                  else "✓ OK — the grammar and the runtime agree"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
