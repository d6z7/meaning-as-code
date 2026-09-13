#!/usr/bin/env python3
"""Is each capability implemented only in its declared home? A diagram nobody checks drifts.

WHY THIS EXISTS. Every duplication this estate has paid for was invisible until it was a defect: a
vendored grammar fork; a whole SDK copied rather than moved, which diverged 54 files in one day; a
credential vocabulary in two spellings, where a bundle that validated against the grammar was
rejected by the connector; a liveness rule fixed in one of two scripts so a watchdog could never
fire. In every case BOTH homes were individually defensible, and nothing anywhere said which was THE
home.

TOPOLOGY.md now says. This reads it and checks the code agrees.

The operator's own framing, which is why this is a table and not prose: "this can from my perspective
better be solved with topology diagram. eg. where exactly is the home of specific functionality. i
never seen you doing this."

WHAT IT CAN AND CANNOT DO, stated plainly because the difference is the honest part. It checks that
each declared home EXISTS and that each capability's MARKER — a distinctive symbol the capability
cannot be implemented without — appears only under that home. It cannot detect a capability
re-implemented under a different name; that is what the seam inventory is for. So this gate proves
"the declared homes are real and not obviously duplicated", never "there is no duplication".

Contract: one PASS:/FAIL: line, exit 0 or 1, exit 2 when it could not run, a printed denominator, and
`--self-test` with a mutant per reject class.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOPOLOGY = ROOT / "TOPOLOGY.md"

#: capability -> (home path prefix, marker regex, why this marker)
#: A MARKER is a symbol the capability cannot be implemented without. `class Connector` can be
#: renamed, so a marker is evidence rather than proof — see the docstring's limits.
MARKERS: dict[str, tuple[str, str, str]] = {
    "gate-harness": ("sdk/gate/contract.py", r"class GateContract", "every gate binds to this one harness"),
    "connector-contract": ("sdk/connector/", r"def read\(self, request", "the one execution seam"),
    "container-open": ("sdk/container/", r"def open_container", "trust and capabilities are judged once"),
    # The marker is the POLICY, not the name. `def schema_path` also matches
    # meaning_as_code/__init__.py's file locator — a different responsibility wearing the same name.
    # That collision is real and recorded in TOPOLOGY.md; it is not a second implementation of the
    # policy, so the marker pins the thing that decides: the $MAC_SCHEMA override.
    "grammar-resolution": ("sdk/grammar/", r'os\.environ\.get\("MAC_SCHEMA"\)',
                           "one process, one governing grammar"),
    "credential-plan": ("sdk/connector/", r"def credential_plan", "a handle, never a value"),
}

#: Paths that legitimately NAME a capability without implementing it: tests exercise it, gates scan
#: for it, and documentation quotes it. Counting those is the false positive that makes a topology
#: gate unusable.
EXEMPT = re.compile(r"(^|/)(test_|conftest|check_topology\.py$)|(^|/)(build|dist|\.venv|__pycache__|\.claude)/")


def declared_homes() -> list[str]:
    """Home paths named in TOPOLOGY.md's table, as backtick-quoted paths."""
    if not TOPOLOGY.is_file():
        return []
    out: list[str] = []
    for line in TOPOLOGY.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 3:
            continue
        for m in re.finditer(r"`([A-Za-z0-9_./*-]+)`", cells[2]):
            out.append(m.group(1))
    return sorted(set(out))


def _tracked() -> list[Path]:
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True, timeout=60)
        if r.returncode == 0 and r.stdout.strip():
            return [ROOT / p for p in r.stdout.splitlines() if p.strip()]
    except Exception:                                                   # noqa: BLE001
        pass
    return []


def judge() -> tuple[int, list[str], str]:
    if not TOPOLOGY.is_file():
        return 2, [f"no {TOPOLOGY.name} — there is no declared topology to check against"], ""
    homes = declared_homes()
    files = _tracked()
    if not files:
        return 2, ["git ls-files yielded nothing — 0 examined is not the same as clean"], ""

    errs: list[str] = []

    # 1 · a declared home that does not exist is a diagram describing a tree that is not there.
    #
    # THE TOPOLOGY SPANS REPOSITORIES, which the first version of this check did not know: it
    # resolved every home against THIS repo and so reported mac-platform/packages/mac-runtime as
    # missing while it sat one directory up, alive, and imported by the console. A gate that
    # mis-resolves its own subject produces confident nonsense.
    #
    # Three kinds of home, and only the first two are paths:
    #   * in THIS repo            -> must exist here
    #   * in a SIBLING repo       -> must exist under the estate root
    #   * in a BUNDLE             -> a per-bundle filename (connection.yaml, mac.project.yaml). It
    #                                has no single location by design, so it is NOT path-checked —
    #                                and the count of those is printed, never silently dropped.
    ESTATE = ROOT.parent
    bundle_local = {"connection.yaml", "mac.project.yaml", "registers/"}
    missing, unlocatable = [], []
    for h in homes:
        if "*" in h or h in bundle_local:
            unlocatable.append(h)
            continue
        if (ROOT / h).exists() or (ESTATE / h).exists():
            continue
        missing.append(h)
    for h in missing:
        errs.append(f"TOPOLOGY.md declares a home that exists in neither this repo nor the estate: {h}")

    # 2 · a capability's marker outside its home
    strays: list[str] = []
    checked = 0
    for cap, (home, marker, why) in MARKERS.items():
        rx = re.compile(marker)
        checked += 1
        for f in files:
            rel = str(f.relative_to(ROOT))
            if rel.startswith(home) or EXEMPT.search(rel) or f.suffix not in {".py"}:
                continue
            try:
                if rx.search(f.read_text(encoding="utf-8")):
                    strays.append(f"{cap}: implemented outside its home — {rel} (home: {home}; {why})")
            except Exception:                                           # noqa: BLE001
                continue
    errs.extend(strays)

    denom = (f"{checked} capabilit(y/ies) with a marker checked over {len(files)} tracked file(s), "
             f"{len(homes)} declared home(s) of which {len(unlocatable)} are per-bundle and not "
             f"path-checked")
    return (1 if errs else 0), errs, denom


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()
    code, errs, denom = judge()
    for e in errs:
        print(f"  [ERROR] {e}", file=sys.stderr)
    if code == 2:
        print(f"could not run: check_topology — {errs[0]}", file=sys.stderr)
        return 2
    if code:
        print(f"\nFAIL: check_topology — over {denom}")
        return 1
    print(f"PASS: check_topology — every capability in its declared home, over {denom}")
    return 0


def _self_test() -> int:
    import tempfile

    failures: list[str] = []
    global TOPOLOGY, MARKERS
    real_t, real_m = TOPOLOGY, MARKERS

    def drive(tmp: Path, table: str, markers: dict, files: dict) -> tuple:
        # The home is the SECOND cell, matching TOPOLOGY.md's "| capability | THE home | ... |".
        # My first fixture put it third and the missing-home mutant went uncaught — a test that
        # disagrees with the file it tests proves nothing about the file.
        (tmp / "TOPOLOGY.md").write_text("| capability | home | note |\n|---|---|---|\n" + table,
                                         encoding="utf-8")
        for rel, body in files.items():
            p = tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")
        globals()["ROOT"] = tmp
        globals()["TOPOLOGY"] = tmp / "TOPOLOGY.md"
        globals()["MARKERS"] = markers
        globals()["_tracked"] = lambda: sorted(tmp.rglob("*.py"))
        return judge()

    real_root, real_tracked = ROOT, _tracked
    try:
        M = {"cap": ("home/", r"def the_marker", "because")}
        # clean: the marker only in its home
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            if drive(tmp, "| cap | `home/` | x |\n", M, {"home/a.py": "def the_marker(): pass\n"})[0] != 0:
                failures.append("clean fixture did not pass")

        # mutant: the marker OUTSIDE its home
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            if drive(tmp, "| cap | `home/` | x |\n", M,
                     {"home/a.py": "def the_marker(): pass\n",
                      "elsewhere/b.py": "def the_marker(): pass\n"})[0] != 1:
                failures.append("mutant not caught: a marker outside its declared home passed")

        # must-pass: a TEST naming the marker is not an implementation
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            if drive(tmp, "| cap | `home/` | x |\n", M,
                     {"home/a.py": "def the_marker(): pass\n",
                      "elsewhere/test_b.py": "def the_marker(): pass\n"})[0] != 0:
                failures.append("false positive: a test naming the marker was counted as a second home")

        # mutant: a declared home that does not exist
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            if drive(tmp, "| cap | `nowhere/` | x |\n", M, {"home/a.py": "def the_marker(): pass\n"})[0] != 1:
                failures.append("mutant not caught: a home that does not exist passed")

        # mutant: no TOPOLOGY.md at all -> could-not-run, never a pass
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            globals()["ROOT"] = tmp
            globals()["TOPOLOGY"] = tmp / "absent.md"
            globals()["_tracked"] = lambda: []
            if judge()[0] != 2:
                failures.append("mutant not caught: no topology file did not report could-not-run")

        # mutant: no tracked files -> could-not-run. 0 examined is not 0 strays.
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            (tmp / "TOPOLOGY.md").write_text("| a | b | c |\n|---|---|---|\n| cap | `home/` | x |\n")
            (tmp / "home").mkdir()
            globals()["ROOT"] = tmp
            globals()["TOPOLOGY"] = tmp / "TOPOLOGY.md"
            globals()["_tracked"] = lambda: []
            if judge()[0] != 2:
                failures.append("mutant not caught: zero tracked files produced a verdict")
    finally:
        globals()["ROOT"], globals()["TOPOLOGY"], globals()["MARKERS"] = real_root, real_t, real_m
        globals()["_tracked"] = real_tracked

    total = 6
    if failures:
        print(f"FAIL: check_topology self-test — {len(failures)} of {total} assertions failed")
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"PASS: check_topology self-test — {total}/{total} (4 mutants reject: stray marker, "
          f"missing home, no topology file, zero tracked files; 1 test-file false positive stays "
          f"green; clean fixture passes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
