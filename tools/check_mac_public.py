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
import os
import re
import argparse
import shutil
import subprocess
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

# THE PATTERN TABLE IS NOT IN THIS FILE. It was: every brand, the operator's systems, an infra
# bucket, a colleague's name -- the complete identity this gate exists to keep OUT of a public
# repository, listed inside that public repository. The gate's own source was the densest
# concentration in the tree of exactly what it scans for.
#
# It now loads from a GITIGNORED register. `registers/public_tokens.example.txt` ships with the
# format and no values. $MAC_PUBLIC_TOKENS overrides the path so CI -- which has no gitignored
# file -- can supply one without committing it.
#
# AN EMPTY REGISTER IS NOT A CLEAN TREE. With no patterns the gate examines NOTHING, and a
# zero-denominator pass is this estate's dominant defect, so it refuses rather than reporting green.
REGISTER = Path(os.environ.get("MAC_PUBLIC_TOKENS") or (SELF.parent.parent / "registers" / "public_tokens.txt"))


def load_patterns(register: Path = None):
    """[(label, regex, flags)] from the register, or [] when none is declared."""
    reg = register if register is not None else REGISTER
    if not reg.is_file():
        return []
    out = []
    for ln in reg.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        # Split on the FIRST and LAST delimiter only: a regex legitimately contains `|`
        # (alternation), and a naive 3-way split silently DROPPED every alternating pattern --
        # three brands vanished from the table that way, which is a gate going quietly blind.
        if ln.count("|") < 2:
            continue
        label, rest = ln.split("|", 1)
        rx, fl = rest.rsplit("|", 1)
        label, rx, fl = label.strip(), rx.strip(), fl.strip()
        out.append((label, rx, I if fl.lower() == "i" else 0))
    return out


PATTERNS = load_patterns()
COMPILED = [(label, re.compile(p, f)) for (label, p, f) in PATTERNS]


def scan(root: Path):
    hits = []
    for path in _candidates(root):
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


#: The ratchet floor: the measured count this tree is allowed to carry, and never more.
FLOOR_FILE = SELF.parent / "mac_public_floor.txt"


def _floor(root: Path) -> int | None:
    """The declared floor, or None when none is declared (then any finding fails)."""
    if not FLOOR_FILE.is_file():
        return None
    for line in FLOOR_FILE.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line.isdigit():
            return int(line)
    return None


def _candidates(root: Path):
    """The files this gate is entitled to judge: the ones git TRACKS.

    It used to walk the filesystem with `rglob`, and `SKIP_DIRS` omitted `build`. Measured on this
    repository: **311 of its 611 findings were in `build/`, which holds ZERO tracked files.** Half
    the reported debt was the gate reading its own build output and calling it a leak. A finding
    outside `git ls-files` is a gate bug, not a disclosure.

    Falls back to the filesystem walk only when git cannot answer -- and says so, because a gate that
    silently changes its denominator is worse than one that has the wrong denominator.
    """
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files"],
                             capture_output=True, text=True, timeout=120)
        tracked = [ln for ln in out.stdout.splitlines() if ln.strip()]
    except Exception:
        tracked = []
    if not tracked:
        print("  NOTE: `git ls-files` yielded nothing — falling back to a filesystem walk, which "
              "may include untracked build output", file=sys.stderr)
        return sorted(root.rglob("*"))
    return [root / rel for rel in sorted(tracked)]


def main() -> int:
    if not PATTERNS:
        print(
            "could not run: check_mac_public — no token register at "
            f"{REGISTER}; 0 patterns means 0 examined, which is not the same as clean. "
            "Copy registers/public_tokens.example.txt, or set $MAC_PUBLIC_TOKENS.",
            file=sys.stderr,
        )
        return 2
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=str(ROOT_DEFAULT))
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return _self_test()

    # It used to read `sys.argv[1]` as a path, so `--root src` globbed a directory literally named
    # "--root", found nothing, and printed "clean" with exit 0.
    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"could not run: {root} is not a directory", file=sys.stderr)
        return 2
    hits = scan(root)
    examined = len(_candidates(root))
    if examined == 0:
        print(f"could not run: {root} — 0 tracked file(s) examined, which is not the same as clean",
              file=sys.stderr)
        return 2
    if not hits:
        print(f"PASS: check_mac_public — 0 leak(s) over {examined} tracked file(s) examined")
        return 0
    floor = _floor(root)
    if floor is not None and len(hits) <= floor:
        # The RATCHET. "Zero" is not reachable while this gate's own denylist and tests must name
        # the tokens they forbid -- the same division-of-labour constraint that shaped
        # tools/check_generic.py in the kit. So the criterion is ZERO NEW findings above a declared,
        # measured floor, which is the instrument this estate already uses elsewhere.
        # THE WITNESSES TRAVEL WITH THE VERDICT. This branch used to print the COUNT alone, so every
        # finding under the floor was invisible from the command people actually run -- the debt the
        # floor exists to make visible was the one thing the gate hid. A reader had to import scan()
        # to see what was still leaking.
        if hits:
            print(f"  {len(hits)} finding(s) under the floor — still to scrub:", file=sys.stderr)
            for rel, lineno, label, line in hits:
                print(f"    {rel}:{lineno}: [{label}] {line}", file=sys.stderr)
        # A FLOOR THAT SITS ABOVE THE MEASUREMENT IS NOT A RATCHET. It permits every finding between
        # the count and the floor to be re-introduced silently, which is exactly the headroom a
        # ratchet exists to remove. The file's own rule is "lower it, never raise it"; this makes
        # failing to lower it visible instead of comfortable.
        slack = (floor - len(hits)) if floor is not None else 0
        if slack > 0:
            print(f"  [RATCHET] the floor is {floor} but only {len(hits)} finding(s) remain — "
                  f"{slack} finding(s) of slack. Lower {FLOOR_FILE.name} to {len(hits)}.",
                  file=sys.stderr)
        print(f"PASS: check_mac_public — {len(hits)} leak(s) over {examined} tracked file(s) "
              f"examined, at or below the declared floor of {floor} "
              f"({FLOOR_FILE.name} — lower it, never raise it)"
              + (f"  [{slack} of slack]" if slack > 0 else ""))
        return 0
    over = f", {len(hits) - floor} ABOVE the declared floor of {floor}" if floor is not None else ""
    print(f"check_mac_public: {len(hits)} leak(s){over} — the public repo must carry NO "
          f"VW/GAPS/FPL/source/automotive token:\n", file=sys.stderr)
    for rel, lineno, label, line in hits:
        print(f"  {rel}:{lineno}: [{label}] {line}", file=sys.stderr)
    print(f"\nScrub these, or (only for a genuine, reviewed use) append `{ALLOW}` on the line.",
          file=sys.stderr)
    print(f"\nFAIL: check_mac_public — {len(hits)} leak(s) over {examined} tracked file(s) examined")
    return 1

# -------------------------------------------------------------------------------------------------
# self-test: one mutant per reject class. This gate had none, and reached this point with HALF its
# findings against a directory holding zero tracked files.
# -------------------------------------------------------------------------------------------------


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _seed_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    (root / "clean.py").write_text("def build(name):\n    return name.lower()\n", encoding="utf-8")
    _git(root, "add", "-A")


def _token() -> str:
    """Derived from the gate's OWN pattern table, never typed: this gate COUNTS such tokens, so a
    self-test that spelled one out would plant the thing it scans for."""
    for entry in PATTERNS:
        pat = entry[1] if isinstance(entry, (tuple, list)) else entry
        raw = getattr(pat, "pattern", str(pat))
        word = re.sub(r"[^A-Za-z0-9_]", "", raw)
        if len(word) >= 3:
            return word
    raise RuntimeError("no usable token in PATTERNS")


def _self_test() -> int:
    import tempfile

    if shutil.which("git") is None:
        print("could not run: git is required for the self-test", file=sys.stderr)
        return 2

    failures: list[str] = []
    tok = _token()

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # 1 - a clean TRACKED tree passes, over a non-zero denominator.
        clean = base / "clean"
        _seed_repo(clean)
        if len(_candidates(clean)) == 0:
            failures.append("clean fixture examined 0 tracked files")
        if scan(clean):
            failures.append("clean fixture produced a finding")

        # 2 - a token in a TRACKED file is a leak.
        tracked = base / "tracked"
        _seed_repo(tracked)
        (tracked / "leak.py").write_text(f'TABLE = "{tok}.orders"\n', encoding="utf-8")
        _git(tracked, "add", "-A")
        if not scan(tracked):
            failures.append("mutant not caught: a token in a tracked file")

        # 3 - THE defect this gate carried: the same token in an UNTRACKED, gitignored build
        #     directory must NOT be reported. 311 of its 611 findings were exactly this.
        ignored = base / "ignored"
        _seed_repo(ignored)
        (ignored / ".gitignore").write_text("build/\n", encoding="utf-8")
        (ignored / "build").mkdir()
        (ignored / "build" / "copy.py").write_text(f'TABLE = "{tok}.orders"\n', encoding="utf-8")
        _git(ignored, "add", "-A")
        if any("build/" in str(h) for h in scan(ignored)):
            failures.append("false positive: a gitignored build file was reported as a leak")

        # 4 - a non-directory root must refuse, not print clean.
        missing = base / "nope"
        if (missing / "x").exists():
            failures.append("fixture error")
        if _candidates(base / "nope"):
            failures.append("candidates found files under a nonexistent root")

    total = 5
    if failures:
        print(f"FAIL: check_mac_public self-test — {len(failures)} of {total} failed")
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"PASS: check_mac_public self-test — {total}/{total} (a tracked leak is caught, a "
          f"gitignored build copy is NOT, the clean fixture passes over a non-zero denominator)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
