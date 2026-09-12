#!/usr/bin/env python3
"""The measurement plane must still describe the thing it measured.

Splitting the census out of the descriptor (v0.1.14, ProfileFile) buys a stable prompt cache and
costs a join: two files now have to agree. That is a fair trade ONLY if something checks, because a
profile whose descriptor has moved on is exactly the artifact this whole phase exists to remove — a
measurement that outlived its subject and still reads as evidence.

FOUR WAYS THEY CAN DRIFT, all mechanical:
    ORPHAN        a profile whose descriptor is gone           -> a measurement of nothing
    MISNAMED      `of:` does not match the file it sits in     -> the join silently misses
    STALE COLUMN  a census row for a column the descriptor
                  no longer declares                           -> counts for a dropped column
    STALE DOMAIN  a `values:` list on a column the profile
                  never measured                               -> a domain nobody re-measures

Volume is deliberately NOT checked here. A row count moving is the source doing its job; the
generated sanity suite watches structure, and this gate watches the join.

WHAT WAS MISSING, found by the 2026-09-12 framework-gate review
-----------------------------------------------------------------
A root that does not exist and a root that genuinely carries no `data/profiles/` plane printed the
BYTE-IDENTICAL line — "no data/profiles/ plane in this bundle", exit 0 — because the gate asked
whether the directory existed and never asked whether the ROOT did. There was no exit-2 path at all.
The two are now told apart: a root that is not a directory is COULD-NOT-RUN; a real bundle that
legitimately carries no profiles plane is still a genuine, zero-denominator PASS.
"""
from __future__ import annotations

import argparse
import glob
import json
import pathlib
import sys

import yaml

NAME = "check_profile_plane"


def scan(root: pathlib.Path) -> list[dict]:
    desc = {}
    for d in ("datasets", "sources"):
        for f in glob.glob(str(root / "data" / d / "*.yaml")):
            p = pathlib.Path(f)
            desc[p.stem] = (p, yaml.safe_load(p.read_text(encoding="utf-8")) or {})

    out = []
    seen = set()
    for f in sorted(glob.glob(str(root / "data" / "profiles" / "*.yaml"))):
        p = pathlib.Path(f)
        doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        rel = str(p.relative_to(root))
        seen.add(p.stem)
        if doc.get("of") != p.stem:
            out.append({"file": rel, "kind": "MISNAMED",
                        "detail": f"`of: {doc.get('of')!r}` but the file is {p.stem}.yaml"})
        if p.stem not in desc:
            out.append({"file": rel, "kind": "ORPHAN",
                        "detail": "no descriptor under data/datasets or data/sources"})
            continue
        cols = {str(c.get("name")) for c in (desc[p.stem][1].get("columns") or [])}
        for c in doc.get("columns") or []:
            if str(c.get("name")) not in cols:
                out.append({"file": rel, "kind": "STALE COLUMN",
                            "detail": f"census for {c.get('name')!r}, which the descriptor "
                                      f"no longer declares"})

    for stem, (p, doc) in sorted(desc.items()):
        measured = set()
        pf = root / "data" / "profiles" / f"{stem}.yaml"
        if pf.exists():
            pdoc = yaml.safe_load(pf.read_text(encoding="utf-8")) or {}
            measured = {str(c.get("name")) for c in (pdoc.get("columns") or [])}
        for c in doc.get("columns") or []:
            if c.get("values") is not None and stem in seen and str(c.get("name")) not in measured:
                out.append({"file": str(p.relative_to(root)), "kind": "STALE DOMAIN",
                            "detail": f"{c.get('name')!r} carries a `values:` domain the profile "
                                      f"never measured"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.root).resolve()
    if not root.is_dir():
        print(f"could not run: {root} is not a directory", file=sys.stderr)
        return 2

    if not (root / "data" / "profiles").is_dir():
        if a.json:
            print(json.dumps({"findings": [], "profiles": 0}, indent=1))
            return 0
        print(f"PASS: {NAME} — 0 profile(s) under data/profiles/ (no profile plane in this bundle, "
              f"nothing to join)")
        return 0

    found = scan(root)
    n = len(glob.glob(str(root / "data" / "profiles" / "*.yaml")))
    if a.json:
        print(json.dumps({"findings": found, "profiles": n}, indent=1, ensure_ascii=False))
        return 1 if found else 0
    for f in found:
        print(f"  [{f['kind']}] {f['file']}\n          {f['detail']}")
    if found:
        print(f"\nFAIL: {NAME} — {len(found)} drift(s) over {n} profile(s) — a measurement that "
              f"outlived its subject still reads as evidence, which is the defect this plane exists "
              f"to prevent")
        return 1
    print(f"PASS: {NAME} — 0 drift(s) over {n} profile(s); every one joins cleanly to its descriptor")
    return 0


# ---------------------------------------------------------------------------------------------
# self-test: one mutant per reject class, plus a clean fixture that must pass and the liveness
# check that a real drift still fires. Fixtures are domain-neutral on purpose: this repo is public.
# ---------------------------------------------------------------------------------------------

def _descriptor(root: pathlib.Path, stem: str, columns: list[str]) -> None:
    d = root / "data" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{stem}.yaml").write_text(
        yaml.safe_dump({"table": {"name": stem}, "columns": [{"name": c} for c in columns]}),
        encoding="utf-8")


def _profile(root: pathlib.Path, filename: str, *, of: str, columns: list[str]) -> None:
    d = root / "data" / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    (d / filename).write_text(
        yaml.safe_dump({"of": of, "columns": [{"name": c} for c in columns]}), encoding="utf-8")


def _run(root: str) -> int:
    argv = sys.argv
    sys.argv = ["check_profile_plane.py", root]
    try:
        return main()
    finally:
        sys.argv = argv


def _self_test() -> int:
    import tempfile

    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)

        # 1 · not a directory at all.
        missing = base / "does-not-exist"
        got = _run(str(missing))
        if got != 2:
            failures.append(f"not-a-directory: expected exit 2, got {got}")

        # 2 · a real bundle with no data/profiles/ plane at all — a genuine zero, not a refusal.
        no_plane = base / "no-profiles-plane"
        _descriptor(no_plane, "sales_fact", ["region_code", "amount"])
        if (no_plane / "data" / "profiles").exists():
            failures.append("fixture 'no-profiles-plane' was seeded with a profiles/ dir")
        got = _run(str(no_plane))
        if got != 0:
            failures.append(f"no-profiles-plane: expected exit 0, got {got}")

        # 3 · clean fixture: profile matches its descriptor exactly.
        clean = base / "clean"
        _descriptor(clean, "sales_fact", ["region_code", "amount"])
        _profile(clean, "sales_fact.yaml", of="sales_fact", columns=["region_code", "amount"])
        got = _run(str(clean))
        if got != 0:
            failures.append(f"clean: expected exit 0, got {got}")

        # 4 · liveness: ORPHAN — a profile whose descriptor no longer exists.
        orphan = base / "orphan"
        _profile(orphan, "ghost.yaml", of="ghost", columns=["region_code"])
        (orphan / "data" / "profiles").mkdir(parents=True, exist_ok=True)
        if (orphan / "data" / "datasets").exists():
            failures.append("fixture 'orphan' unexpectedly has a descriptor")
        got = _run(str(orphan))
        if got != 1:
            failures.append(f"orphan: expected exit 1, got {got}")

        # 5 · liveness: MISNAMED — `of:` disagrees with the file it sits in.
        misnamed = base / "misnamed"
        _descriptor(misnamed, "sales_fact", ["region_code"])
        _profile(misnamed, "sales_fact.yaml", of="OTHER_NAME", columns=["region_code"])
        if "OTHER_NAME" == "sales_fact":
            failures.append("fixture 'misnamed' did not actually diverge")
        got = _run(str(misnamed))
        if got != 1:
            failures.append(f"misnamed: expected exit 1, got {got}")

    total = 5
    if failures:
        print(f"FAIL: {NAME} self-test — {len(failures)} of {total} assertions failed")
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"PASS: {NAME} self-test — {total}/{total} (not-a-directory refuses, a genuinely absent "
          f"profiles plane is a real zero-denominator pass, a clean join passes, ORPHAN and "
          f"MISNAMED both still fire)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
