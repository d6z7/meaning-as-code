#!/usr/bin/env python3
"""annotation_isolation.py — prove plane-3 (`annotations/`) NEVER enters a compiled or
served artifact.

The compilers/servers read an ALLOWLIST of inputs (sources/*/*/{data,ontology}); they must
never reference or glob the annotations tree. This ratchet fails if any of them references
the annotations PATH (a string literal / path segment — not the Python `from __future__
import annotations` feature), and (once artifacts exist) if any published artifact tree
contains an annotation file. Exit 0 clean, 1 on leak. Stdlib only.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from sdk.gate import contract

_ROOT = Path(__file__).resolve().parents[2]
# modules that COMPILE or SERVE — none may touch annotations/
_GUARDED = ["sdk/project", "sdk/cli/publish.py", "sdk/cli/harvest.py", "wiki/local_serve.py"]
# a PATH reference to the annotations dir — quotes or a slash adjacent; NOT `import annotations`.
_PATHISH = re.compile(r"""["'/.]annotations|annotations["'/]""")


def _leaks(path: Path):
    hits = []
    for i, line in enumerate(path.read_text().splitlines(), 1):
        s = line.strip()
        if s.startswith("#") or "from __future__ import" in s:
            continue
        if _PATHISH.search(s):
            hits.append((i, s[:100]))
    return hits


def _iter(target: Path):
    if target.is_file():
        yield target
    elif target.is_dir():
        for p in sorted(target.rglob("*.py")):
            if "__pycache__" not in p.parts:
                yield p


def check(root: Path):
    violations = []
    for rel in _GUARDED:
        t = root / rel
        if not t.exists():
            continue
        for py in _iter(t):
            for ln, txt in _leaks(py):
                violations.append((py.relative_to(root), ln, txt))
    for artdir in root.glob("sources/*/*/artifacts/*/"):
        for f in artdir.rglob("*"):
            if f.is_file() and "annotation" in f.name.lower():
                violations.append(
                    (f.relative_to(root), 0, "annotation file inside a published artifact")
                )
    return violations


def examined(root: Path) -> int:
    """How many files the gate actually looked at. Printed, because a numerator alone cannot be read
    -- and because this gate went green over a tree where none of `_GUARDED` existed, which is a
    pass for the wrong reason."""
    n = 0
    for rel in _GUARDED:
        t = root / rel
        if t.exists():
            n += sum(1 for _ in _iter(t))
    for artdir in root.glob("sources/*/*/artifacts/*/"):
        n += sum(1 for f in artdir.rglob("*") if f.is_file())
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(_ROOT))
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return _self_test()

    root = Path(a.root).resolve()
    # Exit 2 lives HERE, in main(), and never in check(): publish.py:88 calls `check(repo)` in
    # process and reads a truthy return as a FINDING, so a 2 from check() would publish
    # "could not judge" as "plane-3 leaked".
    if not root.is_dir():
        return contract.could_not_run("annotation_isolation", f"{root} is not a directory")

    violations = check(root)
    n = examined(root)
    if n == 0:
        return contract.could_not_run(
            "annotation_isolation",
            f"{root} holds none of the guarded trees ({', '.join(_GUARDED)}) and no published "
            f"artifact — 0 examined is not the same as clean",
        )

    for rel, ln, txt in violations:
        print(f"  {rel}:{ln}: {txt}")
    line, code = contract.verdict(
        "annotation_isolation",
        contract.Outcome(len(violations), n),
        detail="no compiler/server references annotations/; no artifact carries plane-3"
        if not violations
        else "plane-3 leak",
    )
    print(line)
    return code


# -------------------------------------------------------------------------------------------------
# self-test
# -------------------------------------------------------------------------------------------------

_CLEAN_PY = "def build(bundle):\n    return bundle.compile()\n"


def _clean(root: Path) -> None:
    """`_GUARDED` mixes directories with single files, and `_iter` treats them differently -- a
    fixture that made every entry a directory would leave the file entries unexamined."""
    for rel in _GUARDED:
        target = root / rel
        if target.suffix == ".py":
            contract.write(target, _CLEAN_PY)
        else:
            contract.write(target / "mod.py", _CLEAN_PY)
    contract.write(root / "sources" / "s" / "b" / "artifacts" / "v1" / "MANIFEST.json", "{}\n")


def _self_test() -> int:
    c = contract.GateContract(
        name="annotation_isolation",
        clean=_clean,
        mutants={
            "compiler-references-annotations": lambda r: contract.write(
                r / _GUARDED[0] / "leak.py",
                # _PATHISH requires path punctuation: a BARE `from annotations import` does not
                # match, which the first draft of this mutant got wrong.
                'notes = open("annotations/notes.yaml").read()\n',
            ),
            "annotation-file-inside-a-published-artifact": lambda r: contract.write(
                r / "sources" / "s" / "b" / "artifacts" / "v1" / "annotation_notes.yaml", "x: 1\n"
            ),
        },
        run=lambda r: contract.Outcome(len(check(r)), examined(r)),
    )
    return contract.run_self_test(c)


if __name__ == "__main__":
    sys.exit(main())
