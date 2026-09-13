#!/usr/bin/env python3
"""Is the work accounted for? Every code-bearing commit must be covered by a protocol entry.

WHY THIS EXISTS. The operator's own diagnosis of working without a record:

    "so far we we working on adhock basis. i ask you do. but the donwside is that no ruling remains
     what we did and why and what is requested and expected functionality."

A protocol nobody is obliged to write is one that gets written on good days and skipped on the days
that most need explaining — the days with a defect, a reversal, or a decision somebody will question
in six months. Structure alone does not fix that. This estate's own rule, stated in
`tools/check_extension_keys.py` and again in the compile gate: A CHECK THAT DOES NOT BLOCK IS NOT
ENFORCEMENT.

WHAT IT MEASURES, and the denominator is the point:

    commits examined      every commit in the range that touches code
    covered               named by some entry's `commits:` list
    orphaned              changed code and nothing says why      <- the number that matters
    entries untagged      an entry with no `topics:` is INVISIBLE to the wiki compiler, so it is
                          coverage that nobody will ever read. Counted separately and reported,
                          because "covered" and "compiled" are different claims.

WHAT IT DELIBERATELY DOES NOT DO. It does not judge an entry's quality — that is unjudgeable by
machine and pretending otherwise produces a gate people satisfy rather than obey. It checks the
four structural fields exist (what forced it, evidence, what changed, what it does not prove) and
counts what is orphaned. Whether the evidence is any good is a human's read.

THE RATCHET. It lands RED on a history that predates it, which is honest — the backlog is real.
`protocol_floor.txt` declares how many orphans this tree may carry. Lower it as the backlog is paid;
never raise it.

Contract: one PASS:/FAIL: line, exit 0 or 1, exit 2 when it could not run, a printed denominator,
and `--self-test` with a mutant per reject class.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROTOCOL = ROOT / "protocol"
FLOOR_FILE = Path(__file__).resolve().parent / "protocol_floor.txt"

#: A commit that changes none of these is documentation or bookkeeping and needs no entry of its own.
CODE_SUFFIXES = {".py", ".js", ".jsx", ".sh", ".json", ".yaml", ".yml", ".toml"}

#: The four sections that make a claim checkable. Their ABSENCE is structural and machine-visible;
#: their QUALITY is not, and this gate does not pretend to judge it.
REQUIRED_SECTIONS = ("WHAT FORCED IT", "EVIDENCE", "WHAT CHANGED", "WHAT IT DOES NOT PROVE")


def declared_floor() -> int | None:
    if not FLOOR_FILE.is_file():
        return None
    for line in FLOOR_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            try:
                return int(line)
            except ValueError:
                return None
    return None


def _git(*args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=60)
        return r.stdout if r.returncode == 0 else ""
    except Exception:                                                   # noqa: BLE001
        return ""


def code_commits(rev_range: str) -> list[tuple[str, str]]:
    """(short_sha, subject) for commits in range that touch code.

    `git log --name-only` emits `<header>`, a BLANK line, then the paths — so splitting the output on
    a blank line puts each commit's header in the SAME block as the previous commit's last file. That
    parse found zero commits and the gate correctly reported could-not-run rather than a false pass,
    which is the only reason the bug was visible at all. Walk the lines instead.
    """
    out: list[tuple[str, str]] = []
    sha = subject = None
    touches_code = False

    def flush():
        if sha and touches_code:
            out.append((sha, subject or ""))

    for line in _git("log", "--format=%h\x1f%s", "--name-only", rev_range).splitlines():
        if "\x1f" in line:
            flush()
            sha, subject = line.split("\x1f", 1)
            touches_code = False
            continue
        line = line.strip()
        if line and Path(line).suffix in CODE_SUFFIXES:
            touches_code = True
    flush()
    return out


def entries() -> list[tuple[Path, dict, str]]:
    """(path, front-matter, body) for every protocol entry."""
    found = []
    if not PROTOCOL.is_dir():
        return found
    for p in sorted(PROTOCOL.rglob("*.md")):
        if p.name == "README.md":
            continue
        text = p.read_text(encoding="utf-8")
        fm: dict = {}
        body = text
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
        if m:
            body = m.group(2)
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.strip()
        found.append((p, fm, body))
    return found


def _shas(fm: dict) -> set[str]:
    raw = fm.get("commits", "")
    return {s.strip().strip("'\"") for s in re.split(r"[\[\],]", raw) if s.strip().strip("'\"")}


def judge(rev_range: str) -> tuple[int, list[str], str]:
    """(exit, errors, denominator)."""
    ents = entries()
    commits = code_commits(rev_range)

    if not commits:
        return 2, [f"no code-bearing commit in {rev_range} — 0 examined is not the same as accounted for"], ""
    if not ents:
        return 2, [f"no protocol entry under {PROTOCOL} — 0 entries cannot account for "
                   f"{len(commits)} commit(s)"], ""

    covered: set[str] = set()
    for _p, fm, _b in ents:
        covered |= _shas(fm)

    orphans = [(s, subj) for s, subj in commits if s not in covered]
    untagged = [p for p, fm, _ in ents if not fm.get("topics")]
    malformed = []
    for p, _fm, body in ents:
        missing = [s for s in REQUIRED_SECTIONS if s.lower() not in body.lower()]
        if missing:
            malformed.append((p, missing))

    denom = (f"{len(commits)} code-bearing commit(s) examined, {len(commits) - len(orphans)} covered, "
             f"{len(orphans)} orphaned, over {len(ents)} entr(y/ies)")
    if untagged:
        denom += f"; {len(untagged)} entr(y/ies) carry NO topic and are invisible to the wiki"

    errs: list[str] = []
    floor = declared_floor()
    if floor is None:
        errs.append(f"no floor declared in {FLOOR_FILE.name} — any orphan would fail")
    elif len(orphans) > floor:
        errs.append(f"{len(orphans)} orphaned commit(s), ABOVE the declared floor of {floor}:")
        errs.extend(f"    {s}  {subj[:88]}" for s, subj in orphans[:12])
    for p, missing in malformed:
        # `relative_to` assumes the entry lives under this repo. The self-test drives synthetic
        # trees in a temp dir — a gate that cannot be driven over a fixture cannot have a mutant per
        # reject class, so the display path degrades instead of raising.
        try:
            shown = p.relative_to(ROOT)
        except ValueError:
            shown = p
        errs.append(f"{shown} omits {', '.join(missing)} — a claim without them is an opinion")
    return (1 if errs else 0), errs, denom


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("range", nargs="?", default="HEAD~40..HEAD",
                    help="git revision range to account for (default HEAD~40..HEAD)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()

    code, errs, denom = judge(a.range)
    if code == 2:
        print(f"could not run: check_protocol — {errs[0]}", file=sys.stderr)
        return 2
    for e in errs:
        print(f"  [ERROR] {e}" if not e.startswith("    ") else e, file=sys.stderr)
    floor = declared_floor()
    if code:
        print(f"\nFAIL: check_protocol — {denom}")
        return 1
    slack = (floor - len([1 for _ in ()])) if floor is not None else 0
    print(f"PASS: check_protocol — {denom}, at or below the declared floor of {floor} "
          f"({FLOOR_FILE.name} — lower it, never raise it)")
    return 0


def _self_test() -> int:
    """A mutant per reject class, driven over synthetic trees — the gate must be drivable without
    this repo's real history, or it cannot be tested at all."""
    import tempfile

    failures: list[str] = []
    good_body = "\n".join(f"## {s}\nsomething\n" for s in REQUIRED_SECTIONS)

    def fixture(tmp: Path, *, commits: str = "[aaa1111]", topics: str = "[gates]",
                body: str | None = None) -> None:
        d = tmp / "protocol" / "2026-09-13"
        d.mkdir(parents=True, exist_ok=True)
        (d / "001-x.md").write_text(
            f"---\nwhen: 2026-09-13T10:00:00\nwhat: did a thing\ntopics: {topics}\n"
            f"track: core\nkind: build\ncommits: {commits}\n---\n{body if body is not None else good_body}",
            encoding="utf-8")

    global PROTOCOL, FLOOR_FILE
    real_p, real_f = PROTOCOL, FLOOR_FILE

    def drive(tmp: Path, orphan_floor: int, commits_seen):
        globals()["PROTOCOL"] = tmp / "protocol"
        globals()["FLOOR_FILE"] = tmp / "floor.txt"
        (tmp / "floor.txt").write_text(f"{orphan_floor}\n", encoding="utf-8")
        globals()["code_commits"] = lambda _r: commits_seen
        return judge("ignored")

    try:
        # clean: one commit, one entry naming it, floor 0
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t); fixture(tmp)
            if drive(tmp, 0, [("aaa1111", "a change")])[0] != 0:
                failures.append("clean fixture did not pass")

        # mutant: an ORPHANED commit above the floor
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t); fixture(tmp)
            if drive(tmp, 0, [("aaa1111", "a"), ("bbb2222", "unaccounted")])[0] != 1:
                failures.append("mutant not caught: an orphaned commit passed")

        # must-pass: the SAME orphan, under a floor that admits it
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t); fixture(tmp)
            if drive(tmp, 1, [("aaa1111", "a"), ("bbb2222", "unaccounted")])[0] != 0:
                failures.append("a declared floor did not admit the orphan it declares")

        # mutant: an entry missing a required section
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t); fixture(tmp, body="## EVIDENCE\nonly this\n")
            if drive(tmp, 0, [("aaa1111", "a")])[0] != 1:
                failures.append("mutant not caught: an entry missing required sections passed")

        # mutant: NO entries at all -> could-not-run, never a pass
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t); (tmp / "protocol").mkdir()
            if drive(tmp, 0, [("aaa1111", "a")])[0] != 2:
                failures.append("mutant not caught: zero entries did not report could-not-run")

        # mutant: NO commits -> could-not-run. 0 examined is not 0 orphans.
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t); fixture(tmp)
            if drive(tmp, 0, [])[0] != 2:
                failures.append("mutant not caught: zero commits examined reported a verdict")

        # reported-not-failed: an untagged entry is invisible to the wiki, and must be DISCLOSED
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t); fixture(tmp, topics="")
            code, _errs, denom = drive(tmp, 0, [("aaa1111", "a")])
            if "invisible to the wiki" not in denom:
                failures.append("an untagged entry was not disclosed in the denominator")

        # no floor declared -> any orphan fails
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t); fixture(tmp)
            globals()["PROTOCOL"] = tmp / "protocol"
            globals()["FLOOR_FILE"] = tmp / "absent.txt"
            globals()["code_commits"] = lambda _r: [("aaa1111", "a")]
            if judge("ignored")[0] != 1:
                failures.append("an undeclared floor did not fail")
    finally:
        globals()["PROTOCOL"], globals()["FLOOR_FILE"] = real_p, real_f
        globals()["code_commits"] = code_commits

    total = 8
    if failures:
        print(f"FAIL: check_protocol self-test — {len(failures)} of {total} assertions failed")
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"PASS: check_protocol self-test — {total}/{total} (5 mutants reject as their own class: "
          f"orphan above floor, missing sections, zero entries, zero commits, undeclared floor; "
          f"1 must-pass fixture the floor admits; 1 disclosure assertion; clean fixture passes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
