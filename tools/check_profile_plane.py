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
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import pathlib
import sys

import yaml


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
    a = ap.parse_args()
    root = pathlib.Path(a.root).resolve()
    if not (root / "data" / "profiles").is_dir():
        print("✓ OK — no data/profiles/ plane in this bundle (nothing to join)")
        return 0
    found = scan(root)
    if a.json:
        print(json.dumps({"findings": found}, indent=1, ensure_ascii=False))
        return 1 if found else 0
    for f in found:
        print(f"  [{f['kind']}] {f['file']}\n          {f['detail']}")
    if found:
        print(f"\n✗ {len(found)} drift(s) between the descriptor and its profile — a measurement that "
              f"outlived\n  its subject still reads as evidence, which is the defect this plane exists "
              f"to prevent.")
        return 1
    n = len(glob.glob(str(root / "data" / "profiles" / "*.yaml")))
    print(f"✓ OK — {n} profile(s) join cleanly to their descriptors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
