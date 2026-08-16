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

OFFLINE + pure-structural (files on disk, no AWS).
Usage:  python3 tools/check_dq_resolution_sync.py <bundle-root>
        exit 0 = the three planes are in sync ; exit 1 = a drift (error) was found.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

COVERAGE = {"resolved", "partial", "gap"}


def _load(p: Path):
    if not p.exists():
        return None
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"  [ERROR] cannot parse {p}: {e}")
        return None


def main(argv) -> int:
    if len(argv) != 2:
        print("usage: check_dq_resolution_sync.py <bundle-root>")
        return 2
    root = Path(argv[1]).resolve()
    data = root / "data"
    qdir = data / "quality"
    tdir = data / "transforms"

    reg = _load(qdir / "data_quality_register.yaml") or {}
    issue_ids = {i.get("id") for i in (reg.get("issues") or reg.get("findings") or []) if i.get("id")}
    resmap = _load(qdir / "impurity_resolution_map.yaml") or {}
    resolutions = resmap.get("resolutions") or []
    transforms = {p.stem: (_load(p) or {}) for p in sorted(tdir.glob("*.yaml"))} if tdir.exists() else {}

    print(f"── dq-resolution-sync gate ── {len(issue_ids)} registered issue(s), {len(resolutions)} "
          f"resolution(s), {len(transforms)} transform(s) under {root} ──\n")

    errors: list[str] = []
    warnings: list[str] = []

    # index resolutions by finding for the round-trip check
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

    def _ids(rule):
        declared = rule.get("resolves") or rule.get("finding_id")
        return [declared] if isinstance(declared, str) else list(declared or [])

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

    for w in warnings:
        print(f"  [WARN]  {w}")
    for e in errors:
        print(f"  [ERROR] {e}")
    print()
    if errors:
        print(f"✗ {len(errors)} drift(s) between the DQ register, transforms, and resolution map "
              f"({len(warnings)} warning(s))")
        return 1
    print(f"✓ OK — DQ register ↔ transforms ↔ resolution map are in sync"
          + (f" ({len(warnings)} warning(s) — impurity rules not yet linked)" if warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
