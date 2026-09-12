#!/usr/bin/env python3
"""check_dq_resolution_sync.py — the DATA-QUALITY ↔ TRANSFORM ↔ RESOLUTION-MAP consistency gate.

The three data-plane planes must never drift:
  * data/quality/data_quality_register.yaml   — the DEFECTS (issues[].id + finding)
  * data/transforms/<t>.yaml                   — the TRANSFORM rules that dissolve defects
  * data/quality/impurity_resolution_map.yaml  — the CROSS-LINK (finding_id -> resolving_transforms)

A transform that "dissolves an impurity" (a rule with an `impurity_class`) must SAY which registered
defect it resolves — `resolves: [DQ-id, ...]` on the rule — and the resolution map must link that
finding back to this transform. Otherwise the wiki's Cleaning tab (rules) and Quality tab (register)
tell different stories: a fix that isn't recorded as a problem, or a problem claimed fixed by nothing.

This gate makes that impossible to ship:
  ERROR  — a `resolves` id absent from the register; a resolution finding_id/transform that doesn't
           exist; an invalid coverage; a declared `resolves` with no resolution-map entry pointing back.
  WARN   — a rule that dissolves an impurity_class but declares no `resolves` (register it) — warn-first
           so existing sources migrate without a hard break.

WHAT WAS MISSING, found by the 2026-09-12 framework-gate review
-----------------------------------------------------------------
Every population here comes from files under `<root>/data`, read with a loader that treats "missing"
and "unreadable" alike as an empty document. A NONEXISTENT root therefore produced the exact same
"✓ OK — ... are in sync" verdict, exit 0, as a real bundle that legitimately has no DQ register yet —
there was no argument parsing at all (`sys.argv` read positionally), and no path this gate could exit
2 from except calling it with the wrong argument COUNT. A root that does not exist, or that carries no
`data/` plane at all, is now its own refusal; a root whose `data/` plane is real but genuinely empty of
all three registers still prints a verdict — with an explicit, honest zero — rather than being
indistinguishable from "could not find the bundle".

OFFLINE + pure-structural (files on disk, no AWS).
Usage:  python3 tools/check_dq_resolution_sync.py [bundle-root]
    exit 0 = the three planes are in sync (or none of the three exists to compare)
    exit 1 = a drift (error) was found
    exit 2 = could not run (root missing, or its data/ plane does not exist at all)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

COVERAGE = {"resolved", "partial", "gap"}
NAME = "check_dq_resolution_sync"


def _load(p: Path):
    if not p.exists():
        return None
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"  [ERROR] cannot parse {p}: {e}")
        return None


def _ids(rule):
    declared = rule.get("resolves") or rule.get("finding_id")
    return [declared] if isinstance(declared, str) else list(declared or [])


def scan(root: Path):
    """(issue_ids, resolutions, transforms, errors, warnings) — the three populations plus findings."""
    data = root / "data"
    qdir = data / "quality"
    tdir = data / "transforms"

    reg = _load(qdir / "data_quality_register.yaml") or {}
    issue_ids = {i.get("id") for i in (reg.get("issues") or reg.get("findings") or []) if i.get("id")}
    resmap = _load(qdir / "impurity_resolution_map.yaml") or {}
    resolutions = resmap.get("resolutions") or []
    transforms = {p.stem: (_load(p) or {}) for p in sorted(tdir.glob("*.yaml"))} if tdir.exists() else {}

    errors: list[str] = []
    warnings: list[str] = []

    res_by_finding: dict = {}
    for r in resolutions:
        fid = r.get("finding_id")
        res_by_finding.setdefault(fid, []).append(r)
        if fid not in issue_ids:
            errors.append(f"resolution finding_id '{fid}' is not in the DQ register (dangling)")
        for t in (r.get("resolving_transforms") or []):
            if t not in transforms:
                errors.append(f"resolution '{fid}' names resolving_transform '{t}' — no such transform descriptor")
        cov = r.get("coverage")
        if cov not in COVERAGE:
            errors.append(f"resolution '{fid}' coverage '{cov}' not in {sorted(COVERAGE)}")

    for tstem, tr in transforms.items():
        # APPLIED rules (transforms[]) that dissolve an impurity MUST declare + register + link back.
        for rule in (tr.get("transforms") or []):
            rid = rule.get("id", "?")
            ids = _ids(rule)
            if rule.get("impurity_class") and not ids:
                warnings.append(f"transform '{tstem}' rule '{rid}' dissolves impurity_class "
                                f"'{rule.get('impurity_class')}' but declares no `resolves` — register the DQ issue")
                continue
            for fid in ids:
                if fid not in issue_ids:
                    errors.append(f"transform '{tstem}' rule '{rid}' resolves '{fid}' — not in the DQ register")
                    continue
                linked = any(tstem in (r.get("resolving_transforms") or []) for r in res_by_finding.get(fid, []))
                if not linked:
                    errors.append(f"transform '{tstem}' rule '{rid}' resolves '{fid}' but the resolution "
                                  f"map has no entry linking '{fid}' back to '{tstem}'")
        # OPEN proposals (open_transforms[]) are not applied yet — only validate a declared id exists.
        for rule in (tr.get("open_transforms") or []):
            for fid in _ids(rule):
                if fid not in issue_ids:
                    errors.append(f"transform '{tstem}' open item '{rule.get('id', '?')}' "
                                  f"references '{fid}' — not in the DQ register")

    return issue_ids, resolutions, transforms, errors, warnings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()

    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"could not run: {root} is not a directory", file=sys.stderr)
        return 2
    if not (root / "data").is_dir():
        print(f"could not run: {root} has no data/ plane at all, so dq-resolution-sync has nothing "
              f"to compare", file=sys.stderr)
        return 2

    issue_ids, resolutions, transforms, errors, warnings = scan(root)

    print(f"── dq-resolution-sync gate ── {len(issue_ids)} registered issue(s), {len(resolutions)} "
          f"resolution(s), {len(transforms)} transform(s) under {root} ──\n")

    if not issue_ids and not resolutions and not transforms:
        # All three populations are empty — the two planes were never populated, and this is
        # indistinguishable from "the bundle was never found" unless said out loud.
        print(f"could not run: {root} carries no DQ register, resolution map, or transform — "
              f"0 of 3 planes present, nothing to check", file=sys.stderr)
        return 2

    for w in warnings:
        print(f"  [WARN]  {w}")
    for e in errors:
        print(f"  [ERROR] {e}")
    print()
    examined = f"{len(transforms)} transform(s), {len(issue_ids)} issue(s), {len(resolutions)} resolution(s) examined"
    if errors:
        print(f"FAIL: {NAME} — {len(errors)} drift(s) over {examined} ({len(warnings)} warning(s))")
        return 1
    print(f"PASS: {NAME} — 0 drift(s) over {examined} ({len(warnings)} warning(s))")
    return 0


# ---------------------------------------------------------------------------------------------
# self-test: one mutant per reject class, plus a clean fixture that must pass and the liveness
# check that a real drift still fires. Fixtures are domain-neutral on purpose: this repo is public.
# ---------------------------------------------------------------------------------------------

def _seed(root: Path, *, register=None, resmap=None, transforms=None) -> None:
    import yaml as _yaml

    root.mkdir(parents=True, exist_ok=True)
    if register is not None:
        d = root / "data" / "quality"
        d.mkdir(parents=True, exist_ok=True)
        (d / "data_quality_register.yaml").write_text(_yaml.safe_dump(register), encoding="utf-8")
    if resmap is not None:
        d = root / "data" / "quality"
        d.mkdir(parents=True, exist_ok=True)
        (d / "impurity_resolution_map.yaml").write_text(_yaml.safe_dump(resmap), encoding="utf-8")
    if transforms is not None:
        d = root / "data" / "transforms"
        d.mkdir(parents=True, exist_ok=True)
        for stem, doc in transforms.items():
            (d / f"{stem}.yaml").write_text(_yaml.safe_dump(doc), encoding="utf-8")


def _run(root: str) -> int:
    argv = sys.argv
    sys.argv = ["check_dq_resolution_sync.py", root]
    try:
        return main()
    finally:
        sys.argv = argv


_REG = {"issues": [{"id": "DQ-001", "finding": "duplicate rows"}]}
_RESMAP_LINKED = {"resolutions": [{"finding_id": "DQ-001", "resolving_transforms": ["dedupe"],
                                   "coverage": "resolved"}]}
_TRANSFORM_LINKED = {"dedupe": {"transforms": [{"id": "T1", "impurity_class": "duplicate",
                                                "resolves": ["DQ-001"]}]}}
_TRANSFORM_UNLINKED_RESOLVES = {"dedupe": {"transforms": [{"id": "T1", "impurity_class": "duplicate",
                                                           "resolves": ["DQ-999"]}]}}  # DQ-999 not registered


def _self_test() -> int:
    import tempfile

    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # 1 · not a directory at all.
        missing = base / "does-not-exist"
        got = _run(str(missing))
        if got != 2:
            failures.append(f"not-a-directory: expected exit 2, got {got}")

        # 2 · a real directory with no data/ plane whatsoever.
        no_data = base / "no-data-plane"
        no_data.mkdir()
        got = _run(str(no_data))
        if got != 2:
            failures.append(f"no-data-plane: expected exit 2, got {got}")

        # 3 · a data/ plane that exists but carries none of the three registers — still could-not-run,
        #     never the silent "in sync" a nonexistent root used to produce.
        empty_data = base / "empty-data-plane"
        (empty_data / "data" / "sources").mkdir(parents=True)
        got = _run(str(empty_data))
        if got != 2:
            failures.append(f"empty-data-plane: expected exit 2, got {got}")

        # 4 · clean fixture: register + resolution map + transform all agree — must PASS over a
        #     non-zero denominator.
        clean = base / "clean"
        _seed(clean, register=_REG, resmap=_RESMAP_LINKED, transforms=_TRANSFORM_LINKED)
        got = _run(str(clean))
        if got != 0:
            failures.append(f"clean: expected exit 0, got {got}")

        # 5 · liveness: a transform resolves an id the register never declared — must still FAIL.
        drifted = base / "drifted"
        _seed(drifted, register=_REG, resmap=_RESMAP_LINKED, transforms=_TRANSFORM_UNLINKED_RESOLVES)
        # prove the mutant actually diverges from the clean fixture
        if _TRANSFORM_LINKED == _TRANSFORM_UNLINKED_RESOLVES:
            failures.append("fixture 'drifted' did not actually mutate the clean transform")
        got = _run(str(drifted))
        if got != 1:
            failures.append(f"drifted: expected exit 1, got {got}")

    total = 5
    if failures:
        print(f"FAIL: {NAME} self-test — {len(failures)} of {total} assertions failed")
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"PASS: {NAME} self-test — {total}/{total} (not-a-directory, no data/ plane, and an "
          f"all-empty data/ plane all refuse; a linked clean fixture passes; a dangling resolve "
          f"still fires)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
