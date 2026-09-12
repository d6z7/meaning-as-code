#!/usr/bin/env python3
"""check_boundaries.py — enforce the three-plane directory contract (boundaries.yaml).

Adversary-hardened. Import-AST checks alone are NOT sufficient, so this gate:
  * walks ALL import nodes at ANY nesting depth (function/method/try bodies) — the
    current violation is a FUNCTION-LOCAL `from mac_bridge import ...`, invisible to a
    top-level-only scan;
  * flags `sys.path` mutation and dynamic/computed imports in the GUI tree (the exact
    idiom console_api.py uses today to reach the writer via a computed path);
  * (path-egress/ingress read/write checks are enforced by sibling gates
    check_read_paths.py / check_write_paths.py — built in Stage 1).

Two modes over the SAME contract:
  --mode legacy   pre-migration layout: gui=local_harvest, writer=mac_bridge.
                  MUST RED today — proving the gate catches the code it will replace.
  --mode target   post-migration layout: gui=wiki, writer=sdk. Goes GREEN once the
                  refactor severs the coupling.

Exit 0 = clean, 1 = violations. No third-party deps (stdlib ast only).
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

from sdk.gate import contract

# role -> {dir, forbid_import_roots, forbid_sys_path, forbid_dynamic_import}
CONFIGS = {
    "legacy": {
        "gui (local_harvest)": {
            "dir": "local_harvest",
            "forbid_import_roots": {"mac_bridge", "services"},
            "forbid_sys_path": True,
            "forbid_dynamic_import": True,
        },
        "sdk (mac_bridge)": {
            "dir": "mac_bridge",
            "forbid_import_roots": {"local_harvest", "wiki"},
            "forbid_sys_path": False,
            "forbid_dynamic_import": False,
        },
    },
    "target": {
        "gui (wiki)": {
            "dir": "wiki",
            "forbid_import_roots": {"sdk", "mac_bridge", "services", "local_harvest"},
            "forbid_sys_path": True,
            "forbid_dynamic_import": True,
        },
        "sdk": {
            "dir": "sdk",
            "forbid_import_roots": {"wiki", "local_harvest"},
            "forbid_sys_path": False,
            "forbid_dynamic_import": False,
        },
    },
}

_SKIP_DIRS = {"node_modules", ".venv", "venv", "dist", "__pycache__", "build", ".git"}


def _iter_py(root: Path):
    for p in sorted(root.rglob("*.py")):
        if _SKIP_DIRS & set(p.parts):
            continue
        yield p


def _import_roots(node):
    out = []
    if isinstance(node, ast.Import):
        for a in node.names:
            out.append((a.name.split(".")[0], node.lineno))
    elif isinstance(node, ast.ImportFrom):
        if node.module and node.level == 0:  # absolute import only
            out.append((node.module.split(".")[0], node.lineno))
    return out


def _sys_path_hits(tree):
    hits = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and n.attr == "path":
            v = n.value
            if isinstance(v, ast.Name) and v.id == "sys":
                hits.append(n.lineno)
    return sorted(set(hits))


def _dynamic_import_hits(tree):
    hits = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            name = (
                f.id
                if isinstance(f, ast.Name)
                else (f.attr if isinstance(f, ast.Attribute) else None)
            )
            if name in {"__import__", "import_module"}:
                hits.append((name, n.lineno))
    return hits


def check(root: Path, mode: str):
    cfg = CONFIGS[mode]
    violations = []  # (relpath, lineno, message)
    warnings = []  # sys.path reaches: flagged, non-fatal (the real coupling is an sdk import)
    for role, rc in cfg.items():
        rdir = root / rc["dir"]
        if not rdir.exists():
            continue
        for py in _iter_py(rdir):
            try:
                tree = ast.parse(py.read_text(), filename=str(py))
            except SyntaxError as e:
                violations.append((py.relative_to(root), e.lineno or 0, f"unparseable: {e.msg}"))
                continue
            rel = py.relative_to(root)
            for node in ast.walk(tree):
                for mod, lineno in _import_roots(node):
                    if mod in rc["forbid_import_roots"]:
                        violations.append(
                            (
                                rel,
                                lineno,
                                f"[{role}] imports forbidden module '{mod}' — cross-boundary coupling",
                            )
                        )
            if rc["forbid_sys_path"]:
                for ln in _sys_path_hits(tree):
                    warnings.append(
                        (
                            rel,
                            ln,
                            f"[{role}] touches sys.path — computed-import vector (review; real coupling = an sdk import)",
                        )
                    )
            if rc["forbid_dynamic_import"]:
                for nm, ln in _dynamic_import_hits(tree):
                    violations.append(
                        (rel, ln, f"[{role}] dynamic import {nm}() — evades the import ratchet")
                    )
    return (
        sorted(violations, key=lambda v: (str(v[0]), v[1])),
        sorted(warnings, key=lambda v: (str(v[0]), v[1])),
    )


def examined(root: Path, mode: str) -> tuple[int, list[str]]:
    """Files parsed, and the configured roles whose directory is MISSING.

    This is the gate that produced this estate's canonical false green. Both modes printed
    `PASS - no cross-boundary import coupling (0 sys.path warning(s) to review)` in a repository
    where NONE of the configured directories exist -- `check()` does `if not rdir.exists():
    continue`, so it examined zero files and reported the strongest possible verdict. "0 import
    violations" meant "0 files examined". The denominator is the whole fix.
    """
    n, missing = 0, []
    for role, rc in CONFIGS[mode].items():
        rdir = root / rc["dir"]
        if not rdir.exists():
            missing.append(f"{role} -> {rc['dir']}")
            continue
        n += sum(1 for _ in _iter_py(rdir))
    return n, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["legacy", "target"], default="legacy")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return _self_test()

    root = Path(a.root).resolve()
    if not root.is_dir():
        return contract.could_not_run("check_boundaries", f"{root} is not a directory")
    n, missing = examined(root, a.mode)
    if n == 0:
        return contract.could_not_run(
            "check_boundaries",
            f"mode={a.mode} over {root}: none of the configured directories exist "
            f"({'; '.join(missing)}) — 0 examined is not the same as uncoupled",
        )

    violations, warnings = check(root, a.mode)

    print(f"check_boundaries [mode={a.mode}] over {root}")
    for rel, ln, msg in warnings:
        print(f"  WARN {rel}:L{ln}: {msg}")
    if missing:
        # Stated rather than silently skipped: a role whose directory is absent contributes no
        # evidence, and the reader must be able to see which half of the contract was measured.
        print(f"  NOTE: {len(missing)} configured role(s) absent, unmeasured: {'; '.join(missing)}")
    if not violations:
        print(
            f"PASS: check_boundaries — 0 cross-boundary import(s) over {n} file(s) examined "
            f"({len(warnings)} sys.path warning(s) to review)"
        )
        return 0
    last = None
    for rel, ln, msg in violations:
        if rel != last:
            print(f"\n  {rel}")
            last = rel
        print(f"    L{ln}: {msg}")
    print(
        f"\nFAIL: check_boundaries — {len(violations)} boundary violation(s) over "
        f"{n} file(s) examined"
    )
    if a.mode == "legacy":
        print("(Expected: this proves the gate catches the coupling the refactor must sever.)")
    return 1


# -------------------------------------------------------------------------------------------------
# self-test
# -------------------------------------------------------------------------------------------------

_MODE = "target"


def _bd_dirs() -> tuple[str, str]:
    """The gui role's dir and one root it must not import, read from CONFIGS rather than typed."""
    roles = CONFIGS[_MODE]
    gui = next(r for r in roles.values() if r["forbid_sys_path"])
    return gui["dir"], sorted(gui["forbid_import_roots"])[0]


def _bd_clean(root: Path) -> None:
    gui_dir, _forbidden = _bd_dirs()
    contract.write(root / gui_dir / "view.py", "def render(data):\n    return data\n")


def _bd_run(root: Path):
    """Counts violations AND warnings.

    A sys.path reach is a reject CLASS at warning severity -- deliberately non-fatal, because the
    real coupling is an import. But "non-fatal" is not "undetected": the self-test must still prove
    the gate SEES it, or the class is untested and could be silently lost in a refactor. The
    verdict logic keeps it non-fatal; only this harness counts it.
    """
    violations, warnings = check(root, _MODE)
    n, _missing = examined(root, _MODE)
    return contract.Outcome(len(violations) + len(warnings), n)


def _self_test() -> int:
    gui_dir, forbidden = _bd_dirs()
    c = contract.GateContract(
        name="check_boundaries",
        clean=_bd_clean,
        mutants={
            "gui-imports-across-the-boundary": lambda r: contract.write(
                r / gui_dir / "coupled.py", f"import {forbidden}\n"
            ),
            "gui-reaches-via-sys-path": lambda r: contract.write(
                r / gui_dir / "reach.py", "import sys\nsys.path.insert(0, '../..')\n"
            ),
            "gui-imports-dynamically": lambda r: contract.write(
                r / gui_dir / "dyn.py",
                "import importlib\nm = importlib.import_module('" + forbidden + "')\n",
            ),
            "unparseable": lambda r: contract.write(r / gui_dir / "broken.py", "def (\n"),
        },
        run=_bd_run,
        extra={
            "a tree with no configured directory must refuse": lambda base: (
                ""
                if examined(base / "absent", _MODE)[0] == 0
                else "examined() counted files where no configured dir exists"
            ),
        },
    )
    return contract.run_self_test(c)


if __name__ == "__main__":
    sys.exit(main())
