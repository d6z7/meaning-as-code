#!/usr/bin/env python3
"""One grammar governs this process, and this tree holds exactly one copy of it.

THE DEFECT THIS REPLACES. `sdk/` used to live in a different repository from the grammar it
validates against, so it had to FIND that repository at runtime. It guessed a sibling checkout;
when the packages layout absorbed the SDK the guess pointed at a path that does not exist,
resolution fell through IN SILENCE to a vendored fork, and:

    fork       25 $defs  ->  22 of 22 reference concepts FAIL
    framework  37 $defs  ->   0 of 22 fail

The authoring path could not validate the bundle it had itself produced, and nothing said which
schema had judged it. The old version of this gate policed that fallback.

WHAT IT CHECKS NOW. The SDK lives inside the framework repository, so the fallback is gone and the
question changed. It is no longer "did the framework win the resolution?" -- there is no contest.
It is the stronger and cheaper invariant:

    1. this tree contains EXACTLY ONE mac.schema.json
    2. the grammar that actually governs IS that one
    3. it is not stale (>= MIN_DEFS $defs)

(1) is what makes a fork impossible rather than merely detected: a second copy anywhere in the tree
turns this red on the commit that introduces it, before anything can resolve to it.

BUILD OUTPUT IS NOT A FORK. `build/lib/...` carries a copy of the grammar by construction, and so
does any wheel unpacked in-tree. Counting those as second homes is the same false positive that had
`check_mac_public` reporting 311 findings against build output. They are excluded by path, and the
self-test seeds BOTH cases: a build-output copy must stay green, a real second copy must go red.

Contract: one PASS:/FAIL: line, exit 0 or 1, a printed denominator, exit 2 when it could not run,
and `--self-test` with a mutant per reject class.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sdk.gate import contract

#: The grammar's own count on the framework's `develop`. A copy that has fallen behind is exactly
#: what this number detects.
MIN_DEFS = 30

SCHEMA_NAME = "mac.schema.json"

#: Derived, never authored: anything under these is a BUILD PRODUCT or a foreign tree, and a copy of
#: the grammar there is expected rather than a second home for it.
EXCLUDED_PARTS = frozenset(
    {".git", "build", "dist", "node_modules", "__pycache__", ".venv", ".tox", "site-packages"}
)

TREE_ROOT = Path(__file__).resolve().parents[2]


def _excluded(p: Path, root: Path) -> bool:
    parts = set(p.relative_to(root).parts)
    return bool(parts & EXCLUDED_PARTS) or any(x.endswith(".egg-info") for x in parts)


def grammars_in_tree(root: Path) -> list[Path]:
    """Every AUTHORED copy of the grammar in this tree. Build products are not copies."""
    return sorted(p for p in root.rglob(SCHEMA_NAME) if not _excluded(p, root))


def governing() -> tuple[Path | None, int, str]:
    """(path, $defs, error) of the grammar that actually governs this process."""
    from sdk.grammar import resolve

    try:
        p = Path(resolve.schema_path())
    except Exception as exc:                                            # noqa: BLE001
        return None, 0, f"{type(exc).__name__}: {exc}"
    if not p.exists():
        return None, 0, f"resolved to {p}, which does not exist"
    try:
        n = len(json.loads(p.read_text(encoding="utf-8")).get("$defs", {}))
    except Exception as exc:                                            # noqa: BLE001
        return p, 0, f"unreadable: {type(exc).__name__}"
    return p, n, ""


def judge(root: Path, gov: tuple | None = None) -> tuple[int, list[str], str]:
    """(exit, errors, denominator).

    `gov` is the (path, $defs, error) triple of the grammar that governs. It is INJECTABLE so the
    self-test can build a fixture tree and ask what the gate would say about it -- without that seam
    every fixture is judged against the real process's resolution, which is this tree, and every
    fixture then reads as "the governor is outside the tree". A gate that cannot be driven over a
    synthetic tree cannot have a mutant per reject class.
    """
    found = grammars_in_tree(root)
    denom = f"{len(found)} authored grammar cop{'y' if len(found) == 1 else 'ies'} in {root}"

    if not found:
        return 2, [f"no {SCHEMA_NAME} anywhere in {root} — 0 examined is not the same as clean"], denom

    errs: list[str] = []
    if len(found) > 1:
        errs.append(f"{len(found)} copies of the grammar in one tree — a second home for the standard:")
        errs.extend(f"    {p.relative_to(root)}" for p in found)
        errs.append("    the last fork drifted to 25 $defs and failed 22 of 22 reference concepts")

    path, n, err = gov if gov is not None else governing()
    if err:
        errs.append(f"the governing grammar could not be established — {err}")
    else:
        if path.resolve() not in {p.resolve() for p in found}:
            errs.append(f"the governing grammar is OUTSIDE this tree: {path}")
        if n < MIN_DEFS:
            errs.append(f"the governing grammar declares only {n} $defs (expected >= {MIN_DEFS})")
        denom += f"; governing = {path} ({n} $defs)"

    return (1 if errs else 0), errs, denom


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=TREE_ROOT)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()

    code, errs, denom = judge(a.root)
    for e in errs:
        print(f"  [ERROR] {e}" if not e.startswith("    ") else e)
    if code == 2:
        return contract.could_not_run("check_grammar_home", errs[0] if errs else "nothing examined")
    if code:
        print(f"\nFAIL: check_grammar_home — over {denom}")
        return 1
    print(f"PASS: check_grammar_home — one grammar, and it governs, over {denom}")
    return 0


# -------------------------------------------------------------------------------------------------
# self-test — a mutant per reject class, plus the false positive that must STAY green
# -------------------------------------------------------------------------------------------------


def _self_test() -> int:
    import shutil
    import tempfile

    failures: list[str] = []
    real = TREE_ROOT / SCHEMA_NAME

    # 0 - the real tree must pass.
    code, errs, _ = judge(TREE_ROOT)
    if code != 0:
        failures.append(f"clean fixture (this tree) did not pass: {errs}")

    n_real = len(json.loads(real.read_text(encoding="utf-8")).get("$defs", {}))

    def fixture(tmp: Path) -> Path:
        """A minimal tree that looks like the merged repo to this gate."""
        shutil.copy(real, tmp / SCHEMA_NAME)
        (tmp / "sdk" / "grammar").mkdir(parents=True)
        return tmp

    def gov_of(root: Path) -> tuple:
        """The governor a merged repo would resolve: its own single in-tree grammar."""
        return (root / SCHEMA_NAME, n_real, "")

    with tempfile.TemporaryDirectory() as t:
        root = fixture(Path(t))
        if judge(root, gov_of(root))[0] != 0:
            failures.append("clean fixture (synthetic one-grammar tree) did not pass")

    # 1 - a SECOND authored copy is a fork returning. Must go red.
    with tempfile.TemporaryDirectory() as t:
        root = fixture(Path(t))
        shutil.copy(real, root / "sdk" / "grammar" / SCHEMA_NAME)
        if judge(root, gov_of(root))[0] != 1:
            failures.append("mutant not caught: a second authored grammar copy passed")

    # 2 - build OUTPUT carrying a copy is NOT a fork. Must stay green.
    with tempfile.TemporaryDirectory() as t:
        root = fixture(Path(t))
        (root / "build" / "lib" / "meaning_as_code").mkdir(parents=True)
        shutil.copy(real, root / "build" / "lib" / "meaning_as_code" / SCHEMA_NAME)
        if judge(root, gov_of(root))[0] != 0:
            failures.append("false positive: a build-output copy was counted as a second home")

    # 3 - an egg-info copy is likewise derived. Must stay green.
    with tempfile.TemporaryDirectory() as t:
        root = fixture(Path(t))
        (root / "meaning_as_code.egg-info").mkdir(parents=True)
        shutil.copy(real, root / "meaning_as_code.egg-info" / SCHEMA_NAME)
        if judge(root, gov_of(root))[0] != 0:
            failures.append("false positive: an egg-info copy was counted as a second home")

    # 4 - NO grammar at all is could-not-run, never a pass.
    with tempfile.TemporaryDirectory() as t:
        if judge(Path(t), (None, 0, "nothing to resolve"))[0] != 2:
            failures.append("mutant not caught: an empty tree did not report could-not-run")

    # 5 - a STALE grammar must fail the $defs floor.
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        (root / SCHEMA_NAME).write_text(json.dumps({"$defs": {f"d{i}": {} for i in range(3)}}))
        if judge(root, (root / SCHEMA_NAME, 3, ""))[0] != 1:
            failures.append("mutant not caught: a stale grammar passed the $defs floor")

    # 6 - a governing grammar OUTSIDE the tree must fail.
    with tempfile.TemporaryDirectory() as t, tempfile.TemporaryDirectory() as outside:
        root = fixture(Path(t))
        shutil.copy(real, Path(outside) / SCHEMA_NAME)
        if judge(root, (Path(outside) / SCHEMA_NAME, n_real, ""))[0] != 1:
            failures.append("mutant not caught: a grammar outside the tree governed and passed")

    total = 8
    if failures:
        print(f"FAIL: check_grammar_home self-test — {len(failures)} of {total} assertions failed")
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(
        f"PASS: check_grammar_home self-test — {total}/{total} "
        "(4 mutants reject: second copy, empty tree, stale grammar, out-of-tree governor; "
        "2 derived-copy false positives stay green; 2 clean fixtures pass)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
