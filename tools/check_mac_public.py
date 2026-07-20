#!/usr/bin/env python3
"""
check_mac_public.py — public-repo cleanliness gate for meaning-as-code.

meaning-as-code is a PUBLIC framework repo (see mac-public-no-private-info): it must never carry a
VW / GAPS / FPL / source-specific or automotive-domain token. This gate greps the whole tree for a
denylist of such tokens and fails (exit 1) on any hit, so a private string can never be pinned into
the public repo — or a downstream deploy image built from it — unnoticed.

It is domain-NEUTRAL by construction: the only source-specific strings in this file are the DENYLIST
patterns themselves, and the file excludes ITSELF from the scan.

Usage:
  tools/check_mac_public.py [ROOT]     # ROOT defaults to the repo root (this file's parent's parent)
Exit 0 = clean; 1 = at least one leak (each printed as path:line: [rule] text).

Escape hatch: append `mac-public-allow` in a comment on a line to whitelist a genuine, reviewed use.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

SELF = Path(__file__).resolve()
ROOT_DEFAULT = SELF.parent.parent

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", ".mypy_cache", ".ruff_cache"}
TEXT_EXT = {
    ".py", ".md", ".json", ".yaml", ".yml", ".html", ".htm", ".txt", ".sh",
    ".toml", ".cfg", ".ini", ".csv", ".sql", ".j2", ".jinja", ".xml", ".rst", "",
}
ALLOW = "mac-public-allow"

I = re.IGNORECASE
# (rule-label, regex, flags). Case-SENSITIVE where the token collides with an English word
# (VW / SEAT / GAPS) so "seat", "gaps" etc. never false-positive.
PATTERNS = [
    # --- source / product identity ---
    ("fpl-token",            r"fpl",                        I),   # fpl, FPL_C…, v_fpl, fpl_date
    ("ob-reach",             r"ob[\-_ ]?reach",             I),
    ("dtc-measure",          r"\bdtc\b",                    I),
    ("brand-letter",         r"brand[_ ]letters?",          I),
    ("region-partition-col", r"region_definition_used",     I),
    ("nadin-source",         r"\bnadin\b",                  I),
    ("vwdfive-org",          r"vwdfive",                    I),
    # --- VW / brands ---
    ("volkswagen",           r"volkswagen",                 I),
    ("brand-name",           r"\b(sk[oó]da|cupra|audi)\b",  I),
    ("vw-abbrev",            r"\bVW\b",                     0),   # case-sensitive: the brand, not a word
    ("seat-brand",           r"\bSEAT\b",                   0),   # case-sensitive: the brand, not "seat"
    ("gaps-system",          r"\bGAPS\b",                   0),   # case-sensitive: the system, not "gaps"
    # --- infra / secrets shapes ---
    ("athena-bucket",        r"cat-prd-athena",             I),
    ("nadin-catalog",        r"catalog_vorraum",            I),
    # --- automotive domain vocab ---
    ("powertrain",           r"powertrain",                 I),
    ("fuel-electrification", r"\b(bev|phev|mhev)\b",        I),
    ("fuel-type",            r"\b(diesel|petrol)\b",        I),
]
COMPILED = [(label, re.compile(p, f)) for (label, p, f) in PATTERNS]


def scan(root: Path):
    hits = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.resolve() == SELF:                       # never flag our own denylist
            continue
        if path.suffix.lower() not in TEXT_EXT:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):            # binary / unreadable → skip
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if ALLOW in line:
                continue
            for label, rx in COMPILED:
                if rx.search(line):
                    hits.append((path.relative_to(root), lineno, label, line.strip()))
    return hits


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT_DEFAULT
    hits = scan(root)
    if not hits:
        print(f"check_mac_public: clean — no VW/GAPS/FPL/source/automotive token under {root}")
        return 0
    print(f"check_mac_public: {len(hits)} leak(s) — the public repo must carry NO "
          f"VW/GAPS/FPL/source/automotive token:\n", file=sys.stderr)
    for rel, lineno, label, line in hits:
        print(f"  {rel}:{lineno}: [{label}] {line}", file=sys.stderr)
    print(f"\nScrub these, or (only for a genuine, reviewed use) append `{ALLOW}` on the line.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
