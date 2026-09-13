#!/usr/bin/env python3
"""The version, in ONE place — read it, bump it, or prove everything agrees with it.

RELEASING.md opens with "MAC has one version number … they move together. A release whose tag does
not match the files is a bug." It happened once and was caught. It has since happened four more
times and was not, because nothing checked:

    git tags stop at            v0.1.9      <- the last actual release
    mac.schema.json title       v0.1.10
    mac.schema.json description v0.1.13
    tools/validate_schema.py      0.1.13
    64 <dataset> bundle files          0.1.13
    mac_shapes.yaml mentions      0.1.18

Four generations shipped in prose with no tag. And validate_schema.py:119 documents its own source
as "mac_vocabulary.yaml `version`" — a field that DOES NOT EXIST. The chain of custody was a comment.

WHY A BUMP TOOL AND NOT A CONVENTION. 115 files mention a version and 14 distinct versions are in
play, but almost every mention is CHANGELOG PROSE — "v0.1.12 adds the relationAliasBlock", "Prior:
v0.1.11" — which must NEVER move, because rewriting history is how a changelog stops being evidence.
So a blind find-and-replace is wrong, and a human doing it by hand is wrong differently. Only the
CURRENT-VERSION CLAIMS move, they are enumerated below, and the gate proves they agree.

BRANCH DISCIPLINE (operator, 2026-08-20): feature -> develop -> main, and the release number moves
only on promotion to main, by the operator's decision. Develop carries a PRE-RELEASE marker:

    main      0.1.13            what is released
    develop   0.1.14-develop    what is being assembled, not yet ratified
    feature   0.1.14-develop    inherited; a feature branch never bumps

So `--next` is what you run when develop opens a new generation, and `--release` is what the
operator runs when promoting. Nothing bumps per commit.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)(-develop)?$")

# THE CURRENT-VERSION CLAIMS. Every entry is a place that asserts "the version IS x". Changelog prose
# is deliberately absent: it asserts "version x DID y", which stays true forever.
CLAIMS = [
    {"file": "mac.schema.json",
     "find": re.compile(r"(Meaning-as-Code \(MAC\) — formal schema v)(\d+\.\d+\.\d+(?:-develop)?)"),
     "what": "schema title"},
    {"file": "mac.schema.json",
     "find": re.compile(r"(current generation v)(\d+\.\d+\.\d+(?:-develop)?)"),
     "what": "schema description — current generation"},
    {"file": "tools/validate_schema.py",
     "find": re.compile(r"(CURRENT = ')(\d+\.\d+\.\d+(?:-develop)?)(')"),
     "what": "the validator's notion of current"},
]


def read() -> str:
    if VERSION_FILE.exists():
        v = VERSION_FILE.read_text(encoding="utf-8").strip()
        if v:
            return v
    # bootstrap from the validator, which is the only claim anything actually reads
    m = re.search(r"CURRENT = '([^']+)'", (ROOT / "tools/validate_schema.py").read_text(encoding="utf-8"))
    return m.group(1) if m else "0.0.0"


def parse(v: str):
    m = SEMVER.match(v)
    if not m:
        raise SystemExit(f"not a version: {v!r} — expected a.b.c or a.b.c-develop")
    return int(m[1]), int(m[2]), int(m[3]), bool(m[4])


def claims_found() -> list[dict]:
    out = []
    for c in CLAIMS:
        p = ROOT / c["file"]
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8")
        for m in c["find"].finditer(txt):
            out.append({**c, "path": p, "value": m.group(2)})
    return out


def write(new: str) -> list[str]:
    changed = []
    for c in CLAIMS:
        p = ROOT / c["file"]
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8")
        def sub(m):
            return m.group(1) + new + (m.group(3) if m.lastindex and m.lastindex >= 3 else "")
        new_txt, n = c["find"].subn(sub, txt)
        if n:
            p.write_text(new_txt, encoding="utf-8")
            changed.append(f"{c['file']}  ({c['what']}) x{n}")
    VERSION_FILE.write_text(new + "\n", encoding="utf-8")
    changed.append("VERSION")
    return changed


def check() -> int:
    src = read()
    found = claims_found()
    bad = [f for f in found if f["value"] != src]
    tag = subprocess.run(["git", "-C", str(ROOT), "describe", "--tags", "--abbrev=0"],
                         capture_output=True, text=True).stdout.strip()
    print(f"  VERSION           {src}")
    for f in found:
        mark = "  " if f["value"] == src else "✗ "
        print(f"  {mark}{f['what']:<38} {f['value']}   {f['file']}")
    released = src.endswith("-develop")
    if tag:
        want = "v" + src
        ok = (tag == want) or released
        print(f"  {'  ' if ok else '✗ '}latest git tag                         {tag}"
              + ("   (pre-release, tag not expected)" if released else f"   (expected {want})"))
        if not ok:
            bad.append({"what": "git tag"})
    if bad:
        print(f"\n✗ {len(bad)} claim(s) disagree with VERSION — 'a release whose tag does not match "
              f"the files is a bug' (RELEASING.md)")
        return 1
    print(f"\n✓ OK — every current-version claim agrees ({len(found)} checked)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="prove every claim agrees (default)")
    g.add_argument("--next", action="store_true",
                   help="open the next generation on develop: a.b.c -> a.b.(c+1)-develop")
    g.add_argument("--release", action="store_true",
                   help="promote: strip -develop. The OPERATOR runs this, on the way to main.")
    g.add_argument("--set", metavar="VERSION", help="set explicitly")
    a = ap.parse_args()

    cur = read()
    if a.next:
        maj, mi, pa, dev = parse(cur)
        new = f"{maj}.{mi}.{pa + (0 if dev else 1)}-develop"
    elif a.release:
        maj, mi, pa, dev = parse(cur)
        if not dev:
            print(f"  already released: {cur}")
            return 0
        new = f"{maj}.{mi}.{pa}"
    elif a.set:
        parse(a.set)
        new = a.set
    else:
        return check()

    print(f"  {cur}  ->  {new}")
    for c in write(new):
        print(f"     {c}")
    print("\n  now run --check, and remember the bundles: metadata.schema_version in every model file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
