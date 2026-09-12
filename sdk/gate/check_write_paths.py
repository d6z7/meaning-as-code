#!/usr/bin/env python3
"""check_write_paths.py — enforce the single-writer invariant for the ontology SSOT.

Adversary finding #1 (critical): the harvest wrote authored YAML to the SSOT directly,
bypassing validation. The fix: `sdk/authoring/operations.py` is the ONLY module that
writes planes 1-2, and the harvest heads (`sdk/authoring/{authoring,data_plane}.py`,
`sdk/engine/**`) write NOTHING — they emit candidates that operations persists (or refuses).

This gate walks the AST for write primitives — `open(..., 'w'|'a'|'x')`, `.write_text(...)`,
`.write_bytes(...)` — and fails if any appears where it must not:
  * sdk/authoring/**  — allowed ONLY in operations.py
  * sdk/engine/**     — never (candidates only)
`sdk/project/**` writes the deterministic DERIVED read-view (md / objects.json), which is
gitignored output, not SSOT — reported as ALLOWED (info), never a violation.

Exit 0 = clean, 1 = violation. Stdlib only.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

from sdk.gate import contract

_WRITE_ATTRS = {"write_text", "write_bytes"}
_SKIP = {"__pycache__", ".venv", "venv", "node_modules", "dist", "build"}


def _write_calls(tree):
    """Return [(lineno, primitive)] for every write primitive in the module."""
    hits = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Attribute) and f.attr in _WRITE_ATTRS:
            hits.append((n.lineno, f".{f.attr}()"))
        elif isinstance(f, ast.Name) and f.id == "open":
            mode = ""
            if len(n.args) >= 2 and isinstance(n.args[1], ast.Constant):
                mode = str(n.args[1].value)
            for kw in n.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = str(kw.value.value)
            if any(c in mode for c in ("w", "a", "x", "+")):
                hits.append((n.lineno, f"open(mode={mode!r})"))
    return hits


def _iter_py(root: Path):
    if not root.exists():
        return
    for p in sorted(root.rglob("*.py")):
        if _SKIP & set(p.parts):
            continue
        yield p


def check(repo: Path):
    violations, allowed = [], []
    # sdk/authoring: writes only in operations.py (tests write FIXTURES to tmp_path, never SSOT — exempt)
    for py in _iter_py(repo / "sdk" / "authoring"):
        if py.name == "operations.py" or py.name.startswith("test_"):
            continue
        for ln, prim in _write_calls(ast.parse(py.read_text(), filename=str(py))):
            violations.append(
                (py.relative_to(repo), ln, f"write {prim} — only operations.py may write SSOT")
            )
    # sdk/engine: no writes at all (candidates only)
    for py in _iter_py(repo / "sdk" / "engine"):
        for ln, prim in _write_calls(ast.parse(py.read_text(), filename=str(py))):
            violations.append(
                (
                    py.relative_to(repo),
                    ln,
                    f"write {prim} — sdk/engine must emit candidates, write nothing",
                )
            )
    # sdk/project: derived read-view — allowed, reported for transparency
    for py in _iter_py(repo / "sdk" / "project"):
        for ln, prim in _write_calls(ast.parse(py.read_text(), filename=str(py))):
            allowed.append((py.relative_to(repo), ln, prim))
    return violations, allowed


def examined(repo: Path) -> int:
    """Files the gate actually parsed. Printed, because at the repository root this gate examines
    ZERO files and prints PASS -- and a record of this review once cited that pass as the good case,
    with the semantically correct default root labelled the wrong one. A denominator makes the
    difference visible without having to know which root is which."""
    n = 0
    for sub in ("authoring", "engine", "project"):
        n += sum(1 for _ in _iter_py(repo / "sdk" / sub))
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return _self_test()

    repo = Path(a.root).resolve()
    # Exit 2 lives HERE, never in check(): publish.py:85 does `wp, _ = check_write_paths.check(repo)`
    # in process and treats a non-empty list as findings, so a 2 from check() would be unreadable.
    if not repo.is_dir():
        return contract.could_not_run("check_write_paths", f"{repo} is not a directory")
    n = examined(repo)
    if n == 0:
        return contract.could_not_run(
            "check_write_paths",
            f"{repo} holds no sdk/authoring, sdk/engine or sdk/project to parse — 0 examined is "
            f"not the same as clean (try the default --root)",
        )

    violations, allowed = check(repo)

    print(f"check_write_paths over {repo}")
    if allowed:
        print(f"  (allowed derived writes in sdk/project: {len(allowed)} — read-view/objects.json)")
    if not violations:
        print(
            f"PASS: check_write_paths — 0 violation(s) over {n} file(s) examined — "
            f"operations.py is the sole SSOT writer; authoring/engine heads write nothing"
        )
        return 0
    last = None
    for rel, ln, msg in violations:
        if rel != last:
            print(f"\n  {rel}")
            last = rel
        print(f"    L{ln}: {msg}")
    print(
        f"\nFAIL: check_write_paths — {len(violations)} illegal SSOT-write site(s) over "
        f"{n} file(s) examined"
    )
    return 1


# -------------------------------------------------------------------------------------------------
# self-test
# -------------------------------------------------------------------------------------------------

_CLEAN_OPERATIONS = "def write_ssot(p, text):\n    p.write_text(text)\n"
_CLEAN_READER = "def read(p):\n    return p.read_text()\n"


def _wp_clean(root: Path) -> None:
    """operations.py may write; every other head reads. sdk/project writes are ALLOWED-but-reported,
    so the clean fixture gives it one, to prove the allowed path is not counted as a violation."""
    contract.write(root / "sdk" / "authoring" / "operations.py", _CLEAN_OPERATIONS)
    contract.write(root / "sdk" / "authoring" / "author_concept.py", _CLEAN_READER)
    contract.write(root / "sdk" / "engine" / "candidates.py", _CLEAN_READER)
    contract.write(root / "sdk" / "project" / "read_view.py", _CLEAN_OPERATIONS)


def _wp_run(root: Path):
    violations, _allowed = check(root)
    return contract.Outcome(len(violations), examined(root))


def _self_test() -> int:
    c = contract.GateContract(
        name="check_write_paths",
        clean=_wp_clean,
        mutants={
            "authoring-head-writes-ssot": lambda r: contract.write(
                r / "sdk" / "authoring" / "rogue.py", _CLEAN_OPERATIONS
            ),
            "engine-writes-at-all": lambda r: contract.write(
                r / "sdk" / "engine" / "rogue.py", _CLEAN_OPERATIONS
            ),
        },
        run=_wp_run,
        extra={
            "a tree with nothing to parse must refuse, not pass": lambda base: (
                "" if examined(base / "empty") == 0 else "examined() found files in an empty tree"
            ),
        },
    )
    return contract.run_self_test(c)


if __name__ == "__main__":
    sys.exit(main())
