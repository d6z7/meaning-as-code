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

    commits examined      every commit in the DECLARED range that touches code
    covered               named by some entry's `commits:` list
    orphaned              changed code and nothing says why      <- the number that matters
    entries untagged      an entry with no `topics:` is INVISIBLE to the wiki compiler, so it is
                          coverage that nobody will ever read. Counted separately and reported,
                          because "covered" and "compiled" are different claims.

THE DEFECT THIS FILE WAS REWRITTEN TO REMOVE, measured 2026-09-13 on this tree. The gate took its
revision range from the CALLER and compared the orphan count against ONE INTEGER in a file. So the
same tree, the same entries, the same floor of 9 produced:

    HEAD~12..HEAD    12 examined,  7 orphaned   PASS   (7 <= 9)
    HEAD~20..HEAD    29 examined,  7 orphaned   PASS   (7 <= 9)
    HEAD~25..HEAD    38 examined, 10 orphaned   FAIL
    HEAD~40..HEAD    52 examined, 24 orphaned   FAIL
    example_tpch_ontology
                      7 examined,  2 orphaned   PASS   <- not a range at all. `git log` reads a bare
                                                          token as a PATHSPEC, so the runner was
                                                          judging a seven-commit population against
                                                          a floor measured over thirty-eight.

Three separate things were wrong, and all three are fixed here.

  1. THE POPULATION WAS THE CALLER'S CHOICE. Widen the range and the orphan count rises without
     anything changing in the tree. A floor that moves with the question it is asked cannot ratchet,
     and any PASS it prints is uninterpretable. The range is now keyed to a `BASE:` sha DECLARED IN
     THE FLOOR FILE. A caller may name the range only by a spelling that resolves to that same
     population; anything else is refused with exit 2, not answered.

  2. `HEAD~N` IS NOT A FIXED RANGE EVEN AS A STRING. The floor was declared as "9 over HEAD~25..HEAD"
     and recorded 37 commits. One commit later the identical string measures 38 and 10, because the
     window slid. A declared range has to have an IMMUTABLE base, so `BASE:` is a sha.

  3. AN INTEGER FLOOR IS IDENTITY-BLIND. `len(orphans) <= floor` cannot tell "one orphan paid off"
     from "one paid off and another one introduced". The estate ruled today (see
     `sdk/gate/engine_coupling_floor.txt`) that every floor should be an ID SET, and this floor is
     now the SET of orphaned commit SHAs. Progress is a set difference, printed in both directions
     as `cleared` and `added by identity`.

The floor-file shape — DECLARED / OWNER / RECORD / REVIEW BY / STANDING, and exit 2 rather than a
shrug when a header is missing — is `sdk/gate/check_engine_coupling.load_floor`, reused rather than
reinvented, plus one key that gate does not need: `BASE:`, the range key.

WHAT IT DELIBERATELY DOES NOT DO. It does not judge an entry's quality — that is unjudgeable by
machine and pretending otherwise produces a gate people satisfy rather than obey. It checks the
four structural fields exist (what forced it, evidence, what changed, what it does not prove) and
counts what is orphaned. Whether the evidence is any good is a human's read.

THE RATCHET. It lands RED on a history that predates it, which is honest — the backlog is real.
`protocol_floor.txt` NAMES the orphans this tree may carry. Remove shas as the backlog is paid;
never add one.

Contract: one PASS:/FAIL: line, exit 0 or 1, exit 2 when it could not run, a printed denominator,
and `--self-test` with a mutant per reject class — including the swap mutant that the old
integer floor could not see.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROTOCOL = ROOT / "protocol"
FLOOR_FILE = Path(__file__).resolve().parent / "protocol_floor.txt"

#: A commit that changes none of these is documentation or bookkeeping and needs no entry of its own.
CODE_SUFFIXES = {".py", ".js", ".jsx", ".sh", ".json", ".yaml", ".yml", ".toml"}

#: The four sections that make a claim checkable. Their ABSENCE is structural and machine-visible;
#: their QUALITY is not, and this gate does not pretend to judge it.
REQUIRED_SECTIONS = ("WHAT FORCED IT", "EVIDENCE", "WHAT CHANGED", "WHAT IT DOES NOT PROVE")

#: Shortest citation this gate will treat as identifying a commit. Coverage is matched by PREFIX
#: against the FULL sha, because `git log --format=%h` picks its abbreviation length from the size of
#: the object database — it is 7 here today and will be 8 one day, and on that day every entry in
#: `protocol/` would have gone from covering a commit to covering nothing if this gate had kept
#: comparing abbreviations to abbreviations. A prefix below 7 cannot pick one commit out of a
#: repository this size, so it is IGNORED and DISCLOSED rather than counted as coverage.
MIN_CITE = 7


# --------------------------------------------------------------------------------------------------
# git, and the seam the self-test drives
# --------------------------------------------------------------------------------------------------


def _git(*args: str) -> tuple[bool, str, str]:
    """(ok, stdout, stderr). The old version returned `""` for BOTH "git failed" and "git found
    nothing", so a mistyped range arrived at the verdict as an empty population and left as
    `could not run: no code-bearing commit` — the right exit code for the wrong reason, which is how
    the pathspec defect stayed invisible. The two are now distinguishable at the call site."""
    try:
        r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                           timeout=60)
        return r.returncode == 0, r.stdout, r.stderr.strip()
    except Exception as exc:                                                        # noqa: BLE001
        return False, "", f"{type(exc).__name__}: {exc}"


def rev_parse(spec: str) -> str:
    """The full 40-char sha for `spec`, or "" if git does not know it."""
    ok, out, _ = _git("rev-parse", "--verify", "--quiet", f"{spec}^{{commit}}")
    return out.strip() if ok else ""


@dataclass(frozen=True)
class Commit:
    sha: str                                    # FULL sha, never an abbreviation — see MIN_CITE
    subject: str


def code_commits(rev_range: str) -> list[Commit] | str:
    """Commits in range that touch code, or a string saying why we could not look.

    `git log --name-only` emits `<header>`, a BLANK line, then the paths — so splitting the output on
    a blank line puts each commit's header in the SAME block as the previous commit's last file. That
    parse found zero commits and the gate correctly reported could-not-run rather than a false pass,
    which is the only reason the bug was visible at all. Walk the lines instead.

    BLIND SPOT, disclosed on every verdict rather than left for a reader to discover: `--name-only`
    prints NO path list for a merge commit, so a merge can never be code-bearing here and is never
    examined. That is defensible — a merge's content arrives with the commits it merges — but it is
    a hole in the denominator and the gate says how big it is.
    """
    ok, out, err = _git("log", "--format=%H\x1f%s", "--name-only", rev_range)
    if not ok:
        return (f"git could not read `{rev_range}` as a revision range: "
                f"{err or 'no reason given'}")
    found: list[Commit] = []
    sha = subject = None
    touches_code = False

    def flush() -> None:
        if sha and touches_code:
            found.append(Commit(sha, subject or ""))

    for line in out.splitlines():
        if "\x1f" in line:
            flush()
            sha, subject = line.split("\x1f", 1)
            touches_code = False
            continue
        line = line.strip()
        if line and Path(line).suffix in CODE_SUFFIXES:
            touches_code = True
    flush()
    return found


def _count(*args: str) -> int:
    ok, out, _ = _git("rev-list", "--count", *args)
    return int(out.strip()) if ok and out.strip().isdigit() else -1


# --------------------------------------------------------------------------------------------------
# the entries and what they cite
# --------------------------------------------------------------------------------------------------


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


@dataclass(frozen=True)
class Citations:
    local: frozenset[str]     # usable hex prefixes, >= MIN_CITE — these are what cover a commit
    foreign: frozenset[str]   # `<repo>:<sha>` — another repository's commit, disclosed, never cover
    unusable: frozenset[str]  # too short, or not hex — IGNORED for coverage, and DISCLOSED


def citations(ents: list[tuple[Path, dict, str]]) -> Citations:
    """Every sha any entry claims to account for, split by whether it CAN account for one here.

    The `commits:` column in `protocol/README.md`'s template carries an inline `# why` comment, and
    the old splitter fed that comment text straight into the coverage set as if it were a sha. It
    happened to be harmless — no commit starts with `# what this entry accounts for` — but a
    coverage set containing prose is a coverage set nobody can audit, so the comment is stripped.
    """
    local: set[str] = set()
    foreign: set[str] = set()
    unusable: set[str] = set()
    for _p, fm, _b in ents:
        raw = fm.get("commits", "").split("#", 1)[0]
        for tok in re.split(r"[\[\],]", raw):
            tok = tok.strip().strip("'\"")
            if not tok or tok.lower() == "none":
                continue
            if ":" in tok:
                foreign.add(tok)
            elif len(tok) >= MIN_CITE and re.fullmatch(r"[0-9a-fA-F]+", tok):
                local.add(tok.lower())
            else:
                unusable.add(tok)
    return Citations(frozenset(local), frozenset(foreign), frozenset(unusable))


# --------------------------------------------------------------------------------------------------
# the floor file — the shape is sdk/gate/check_engine_coupling.load_floor, reused
# --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Floor:
    #: The ID SET. Orphaned commits this tree may carry, BY IDENTITY, not by count.
    shas: frozenset[str]
    why: dict[str, str]
    #: The range key: an IMMUTABLE sha. The judged population is `BASE..HEAD` and nothing else.
    base: str
    declared: str
    owner: str
    record: str
    review_by: str
    #: How many orphans stood on the day the floor was declared. It must AGREE with `len(shas)`;
    #: a floor whose two statements of its own size disagree has been hand-edited carelessly and is
    #: refused rather than half-believed.
    standing: int = -1


_HEADER_KEYS = ("DECLARED:", "OWNER:", "RECORD:", "REVIEW BY:", "STANDING:", "BASE:")


def load_floor(path: Path) -> Floor | str:
    """The declared sha SET, or a string saying why this gate cannot judge.

    A FLOOR WITHOUT A DATE AND AN OWNER IS A PERMANENT EXEMPTION. Every ratchet in this estate that
    lost its owner stopped being lowered; `mac_public_floor.txt`'s own comment block records a floor
    of 146 standing over a measurement of 4 — "141 findings of silent headroom". So a floor file
    missing a required header is refused with exit 2, not read with a shrug. Refusing to judge is a
    verdict; reading an ownerless exemption as a licence is not.
    """
    if not path.is_file():
        return f"no floor file at {path} — a ratchet with no declared SET has nothing to ratchet"
    values = {k: "" for k in _HEADER_KEYS}
    shas: set[str] = set()
    why: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#"):
            body = line.lstrip("#").strip()
            for key in _HEADER_KEYS:
                if body.upper().startswith(key):
                    values[key] = body[len(key):].strip()
                    break
            continue
        if not line:
            continue
        # `sha  # why` — the inline column exists so each carried orphan is recorded WITH ITS REASON,
        # the way sdk/gate/engine_coupling_floor.txt records a tolerated path.
        sha, _, reason = line.partition("#")
        sha = sha.strip().lower()
        if sha:
            shas.add(sha)
            if reason.strip():
                why[sha] = reason.strip()

    declared, owner = values["DECLARED:"], values["OWNER:"]
    base = values["BASE:"].split()[0] if values["BASE:"] else ""
    standing_raw = values["STANDING:"].split()[0] if values["STANDING:"] else ""
    standing = int(standing_raw) if standing_raw.isdigit() else -1

    missing = [k for k, v in (("DECLARED:", declared), ("OWNER:", owner), ("BASE:", base)) if not v]
    if standing < 0:
        missing.append("STANDING:")
    if missing:
        return (f"{path.name} declares no {', no '.join(missing)} — a floor with no date, no named "
                f"owner, no immutable range base and no standing count is a permanent exemption over "
                f"an unknown population, and this gate will not enforce one")
    if standing != len(shas):
        return (f"{path.name} says STANDING: {standing} but lists {len(shas)} sha(s) — the floor's "
                f"two statements of its own size disagree, so one of them is stale and neither can "
                f"be enforced")
    bad = sorted(s for s in shas if not re.fullmatch(r"[0-9a-f]{7,40}", s))
    if bad:
        return (f"{path.name} lists {len(bad)} entr(y/ies) that cannot identify a commit "
                f"({', '.join(bad[:4])}) — a floor is an ID SET and every member must be an "
                f"unambiguous sha of at least {MIN_CITE} hex digits")
    return Floor(frozenset(shas), why, base, declared, owner, values["RECORD:"],
                 values["REVIEW BY:"], standing)


# --------------------------------------------------------------------------------------------------
# the range is NOT the caller's parameter
# --------------------------------------------------------------------------------------------------


def resolve_range(spec: str | None, floor: Floor) -> tuple[str, str] | str:
    """The DECLARED population `(base, head)`, or a string saying why we refuse to judge.

    A caller may still SPELL the range however they like — `HEAD~25..HEAD`, `aca8a4d^..HEAD`, the
    bare sha — as long as it resolves to the population the floor was declared over. Any other
    range, and any bare token (which `git log` would read as a pathspec), is refused. The point is
    not to be awkward: it is that a floor measured over one population cannot judge another, and the
    old gate answered anyway.
    """
    head = rev_parse("HEAD")
    if not head:
        return "git could not resolve HEAD — this is not a repository this gate can judge"
    base = rev_parse(floor.base)
    if not base:
        return (f"the floor's BASE: {floor.base} does not resolve to a commit here — the declared "
                f"range has no base, so there is no population to judge")
    if spec is None:
        return base, head
    if "..." in spec:
        return (f"`{spec}` is a symmetric-difference range; this floor is declared over "
                f"{floor.base}..HEAD. Use --survey for a count with NO verdict")
    if ".." not in spec:
        if Path(spec).is_dir():
            # `tools/run_framework_gates.sh:104` hands every gate the bundle root as argv[1]. For
            # this gate that argument is meaningless — its subject is THIS repository's commit
            # history, not a bundle — and git read it as a pathspec, which is how the runner came to
            # judge a seven-commit population against a floor measured over thirty-eight and print
            # PASS. Refusing is the verdict; the runner is what needs fixing, and the message says so
            # rather than leaving a reader to work out why the gate went amber.
            return (f"`{spec}` is a DIRECTORY, not a revision range — this looks like "
                    f"run_framework_gates.sh's <bundle-root>, handed to every gate as argv[1]. "
                    f"check_protocol's subject is this repository's own commit history, not a "
                    f"bundle: invoke it with NO argument. Passed as a range, git read it as a "
                    f"PATHSPEC and the gate judged 7 commits against a floor measured over 38, and "
                    f"printed PASS.")
        return (f"`{spec}` is not a revision range — `git log` reads a bare token as a PATHSPEC, and "
                f"a pathspec silently substitutes a different population for the declared one "
                f"(measured: `example_tpch_ontology` yielded 7 commits and PASSED against a floor "
                f"measured over 38). This floor is keyed to {floor.base}..HEAD; pass that, or "
                f"--survey {spec} for a count with NO verdict")
    left, _, right = spec.partition("..")
    lb, rb = rev_parse(left.strip() or "HEAD"), rev_parse(right.strip() or "HEAD")
    if not lb or not rb:
        side = "left" if not lb else "right"
        return f"`{spec}` does not resolve: its {side} endpoint is unknown to git"
    if (lb, rb) != (base, head):
        return (f"`{spec}` resolves to {lb[:7]}..{rb[:7]}, but this floor is DECLARED over "
                f"{base[:7]}..{head[:7]} (BASE: {floor.base}). A floor measured over one population "
                f"cannot judge another — that is precisely the range-dependence this gate was "
                f"rewritten to remove. Use --survey for a count with NO verdict")
    return base, head


# --------------------------------------------------------------------------------------------------
# the verdict
# --------------------------------------------------------------------------------------------------


@dataclass
class Verdict:
    code: int                                     # 0 pass, 1 fail, 2 could not run
    errs: list[str] = field(default_factory=list)  # witnesses, to stderr
    line: str = ""                                 # the ONE PASS:/FAIL: line, minus its prefix
    notes: list[str] = field(default_factory=list)  # provenance and ratchet instructions, to stdout
    #: Exposed for the self-test, which asserts on identity rather than on formatted text.
    orphans: frozenset[str] = frozenset()


def judge(arg: str | None) -> Verdict:
    floor = load_floor(FLOOR_FILE)
    if isinstance(floor, str):
        return Verdict(2, [floor])
    rng = resolve_range(arg, floor)
    if isinstance(rng, str):
        return Verdict(2, [rng])
    base, head = rng
    pop = code_commits(f"{base}..{head}")
    if isinstance(pop, str):
        return Verdict(2, [pop])
    ents = entries()
    if not pop:
        return Verdict(2, [f"no code-bearing commit in the declared range {base[:7]}..{head[:7]} — "
                           f"0 examined is not the same as accounted for"])
    if not ents:
        return Verdict(2, [f"no protocol entry under {PROTOCOL} — 0 entries cannot account for "
                           f"{len(pop)} commit(s)"])

    cites = citations(ents)
    covered = {c.sha for c in pop if any(c.sha.startswith(p) for p in cites.local)}
    orphans = [c for c in pop if c.sha not in covered]
    orphan_shas = {c.sha for c in orphans}
    subject = {c.sha: c.subject for c in pop}

    # THE FLOOR IS LOCATED IN THE SAME POPULATION IT IS JUDGING. A floor sha that matches no commit
    # in the declared range is granting an exemption to something this gate never looks at.
    hits = {f: {c.sha for c in pop if c.sha.startswith(f)} for f in floor.shas}
    ambiguous = sorted(f for f, h in hits.items() if len(h) > 1)
    if ambiguous:
        return Verdict(2, [f"{FLOOR_FILE.name} lists {len(ambiguous)} sha(s) that match more than "
                           f"one commit in the declared range ({', '.join(ambiguous[:4])}) — an ID "
                           f"set whose members are not identities cannot be ratcheted"])
    stale = sorted(f for f, h in hits.items() if not h)
    on_floor = {s for h in hits.values() for s in h}
    cleared = sorted(on_floor - orphan_shas)     # a declared orphan that an entry now accounts for
    added = sorted(orphan_shas - on_floor)       # NEW orphans. This is the failure.

    untagged = [p for p, fm, _ in ents if not fm.get("topics")]
    malformed = []
    for p, _fm, body in ents:
        missing = [s for s in REQUIRED_SECTIONS if s.lower() not in body.lower()]
        if missing:
            malformed.append((p, missing))

    denom = (f"{len(pop)} code-bearing commit(s) examined over the DECLARED range "
             f"{base[:7]}..{head[:7]}, {len(covered)} covered, {len(orphan_shas)} orphaned, over "
             f"{len(ents)} entr(y/ies); floor SET of {len(floor.shas)} sha(s) — {len(cleared)} "
             f"cleared, {len(added)} added by identity")
    if untagged:
        denom += f"; {len(untagged)} entr(y/ies) carry NO topic and are invisible to the wiki"

    errs: list[str] = []
    for sha in added:
        errs.append(f"NEW ORPHAN, not on the declared floor: {sha[:7]}  "
                    f"{subject.get(sha, '')[:80]}")
    if added:
        errs.append(f"{len(added)} commit(s) changed code since the floor was declared and nothing "
                    f"says why. Write the entry — do NOT add the sha to {FLOOR_FILE.name}: a floor "
                    f"is lowered, never raised.")
    for p, missing in malformed:
        # `relative_to` assumes the entry lives under this repo. The self-test drives synthetic
        # trees in a temp dir — a gate that cannot be driven over a fixture cannot have a mutant per
        # reject class, so the display path degrades instead of raising.
        try:
            shown = p.relative_to(ROOT)
        except ValueError:
            shown = p
        errs.append(f"{shown} omits {', '.join(missing)} — a claim without them is an opinion")

    notes = [
        f"    range — DECLARED BASE: {floor.base} ({base[:7]}) .. HEAD ({head[:7]}). The range is "
        f"NOT the caller's parameter; any other range is refused with exit 2.",
        f"    floor — declared {floor.declared}, review by "
        f"{floor.review_by or 'NEVER (no expiry declared)'}, owner: {floor.owner}",
        f"    record — {floor.record or 'NONE CITED (a floor with no record is an assertion)'}",
    ]
    merges = _count("--merges", f"{base}..{head}")
    total = _count(f"{base}..{head}")
    if total >= 0 and merges >= 0:
        notes.append(f"    blind spots — {total} commit(s) in the range, {len(pop)} examined: "
                     f"{merges} merge(s) emit no path list under `--name-only` and CANNOT be "
                     f"code-bearing here, {max(total - merges - len(pop), 0)} touch no "
                     f"code suffix ({', '.join(sorted(CODE_SUFFIXES))})")
    notes.append(f"    citations — {len(cites.local)} usable, {len(cites.foreign)} name another "
                 f"repo (`<repo>:<sha>`) and can never cover a commit here, {len(cites.unusable)} "
                 f"unusable (below {MIN_CITE} hex digits or not a sha) and IGNORED"
                 + (f": {', '.join(sorted(cites.unusable)[:4])}" if cites.unusable else ""))
    for sha in cleared:
        cite = next((f for f, h in hits.items() if sha in h), sha[:7])
        notes.append(f"    [RATCHET] {sha[:7]} is now accounted for — remove `{cite}` from "
                     f"{FLOOR_FILE.name} and lower STANDING to {len(floor.shas) - len(cleared)}. "
                     f"Lower it, never raise it.")
    for f in stale:
        notes.append(f"    [RATCHET] {FLOOR_FILE.name} carries `{f}`, which matches NO commit in "
                     f"the declared range — it is silent headroom over a population this gate never "
                     f"examines. Remove it.")
    if not added and not malformed and len(orphan_shas) < floor.standing:
        notes.append(f"    [RATCHET] {floor.standing - len(orphan_shas)} orphan(s) gone since the "
                     f"floor was declared — lower STANDING to {len(orphan_shas)}. A floor above the "
                     f"measurement is silent headroom.")

    if errs:
        return Verdict(1, errs, denom, notes, frozenset(orphan_shas))
    return Verdict(0, [], denom + ", EXACTLY the declared floor set (no orphan added by identity)",
                   notes, frozenset(orphan_shas))


# --------------------------------------------------------------------------------------------------
# measurement without a verdict
# --------------------------------------------------------------------------------------------------


def survey(spec: str) -> int:
    """Count orphans over an ARBITRARY range and exit 2. Always.

    The range-dependent numbers are still worth measuring — they are how the backlog was sized. What
    they may never do is produce a PASS, because no floor is declared over them. So this prints the
    count and reports could-not-judge, which is the honest verdict for a population nothing was
    declared against.
    """
    pop = code_commits(spec)
    if isinstance(pop, str):
        print(f"could not run: check_protocol --survey — {pop}", file=sys.stderr)
        return 2
    ents = entries()
    cites = citations(ents)
    covered = {c.sha for c in pop if any(c.sha.startswith(p) for p in cites.local)}
    orphans = {c.sha for c in pop if c.sha not in covered}
    floor = load_floor(FLOOR_FILE)
    extra = ""
    if isinstance(floor, Floor):
        on_floor = {s for s in orphans if any(s.startswith(f) for f in floor.shas)}
        extra = (f"; {len(on_floor)} of them are on the declared floor set, "
                 f"{len(orphans) - len(on_floor)} are NOT")
    print(f"SURVEY (no verdict): check_protocol — {len(pop)} code-bearing commit(s) over `{spec}`, "
          f"{len(covered)} covered, {len(orphans)} orphaned, over {len(ents)} entr(y/ies){extra}")
    print(f"    exit 2, DELIBERATELY. No floor is declared over `{spec}`, so there is nothing to "
          f"judge it against. A count is not a verdict.")
    return 2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("range", nargs="?", default=None,
                    help="optional: a spelling of the range the floor DECLARES (BASE..HEAD). Any "
                         "other range, or a bare pathspec, is refused with exit 2.")
    ap.add_argument("--survey", metavar="RANGE",
                    help="count orphans over an arbitrary range and exit 2 — a measurement, never "
                         "a verdict")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()
    if a.survey:
        return survey(a.survey)

    v = judge(a.range)
    if v.code == 2:
        print(f"could not run: check_protocol — {v.errs[0]}", file=sys.stderr)
        for extra in v.errs[1:]:
            print(f"  {extra}", file=sys.stderr)
        return 2
    for e in v.errs:
        print(f"  [ERROR] {e}", file=sys.stderr)
    print(f"{'FAIL' if v.code else 'PASS'}: check_protocol — {v.line}")
    for n in v.notes:
        print(n)
    return 1 if v.code else 0


# --------------------------------------------------------------------------------------------------
# the self-test
# --------------------------------------------------------------------------------------------------

#: Fake shas are full length, because the gate matches a citation PREFIX against a FULL sha and a
#: fixture that used abbreviations everywhere would not exercise that.
def _S(prefix: str) -> str:
    return (prefix + "0" * 40)[:40]


_A, _B, _C = _S("aaa1111"), _S("bbb2222"), _S("ccc3333")
_BASE, _HEAD = _S("b0be000"), _S("d0d4444")

_GOOD_HEADER = ("# DECLARED: 2026-09-13\n# OWNER: the self-test fixture\n"
                "# RECORD: the fixture's own docstring\n# REVIEW BY: 2026-12-13\n")


def _self_test() -> int:
    """A mutant per reject class, driven over synthetic trees — the gate must be drivable without
    this repo's real history, or it cannot be tested at all.

    The assertion this whole rewrite exists for is `swap`: a tree whose orphan COUNT equals the
    floor's but whose orphan IDENTITIES do not. The old rule was `len(orphans) <= floor`, so that
    tree PASSED; `_legacy_verdict` below restates that rule verbatim and the test asserts it passes
    while the gate fails. A mutant that would have slipped through the old logic now rejects.

    THE TALLY IS COUNTED, NOT TYPED. The previous revision printed `8/8` from a hardcoded `total`
    that a later edit would have silently falsified — a gate quoting a denominator it did not
    measure, which is the one thing this estate will not let a gate do. Every assertion registers
    itself, so the printed denominator is the number of assertions that actually ran.
    """
    import contextlib
    import tempfile

    failures: list[str] = []
    asserted: list[str] = []
    trees = 0
    good_body = "\n".join(f"## {s}\nsomething\n" for s in REQUIRED_SECTIONS)

    def ok(name: str, condition: bool) -> None:
        asserted.append(name)
        if not condition:
            failures.append(name)

    def expect(name: str, got: int, want: int) -> None:
        ok(f"{name} -> exit {want}", got == want)
        if got != want:
            failures[-1] += f" (got {got})"

    def _legacy_verdict(orphan_count: int, floor_count: int) -> int:
        """The rule this file used until today, restated so the mutant it missed is provable."""
        return 1 if orphan_count > floor_count else 0

    @contextlib.contextmanager
    def tree():
        nonlocal trees
        with tempfile.TemporaryDirectory() as t:
            trees += 1
            yield Path(t)

    def entry(tmp: Path, *, commits: str, topics: str = "[gates]", body: str | None = None) -> None:
        d = tmp / "protocol" / "2026-09-13"
        d.mkdir(parents=True, exist_ok=True)
        (d / "001-x.md").write_text(
            f"---\nwhen: 2026-09-13T10:00:00\nwhat: did a thing\ntopics: {topics}\n"
            f"track: core\nkind: build\ncommits: {commits}\n---\n"
            f"{body if body is not None else good_body}", encoding="utf-8")

    def floor_file(tmp: Path, *, header: str = _GOOD_HEADER, base: str | None = _BASE,
                   standing: int | None = None, shas: tuple[str, ...] = ()) -> Path:
        text = header
        if base is not None:
            text += f"# BASE: {base}   the fixture's declared range key\n"
        count = len(shas) if standing is None else standing
        text += f"# STANDING: {count}   orphans on the day declared\n\n"
        text += "".join(f"{s}  # a fixture orphan\n" for s in shas)
        p = tmp / "floor.txt"
        p.write_text(text, encoding="utf-8")
        return p

    def revs(extra: dict[str, str] | None = None):
        table = {"HEAD": _HEAD, _HEAD: _HEAD, _HEAD[:7]: _HEAD,
                 _BASE: _BASE, _BASE[:7]: _BASE, "HEAD~9": _BASE, "some-tag": _BASE}
        table.update(extra or {})
        return lambda spec: table.get(spec, "")

    real = (PROTOCOL, FLOOR_FILE, code_commits, rev_parse, _count)

    def drive(tmp: Path, pop, *, arg=None, rev=None, floor_path=None):
        globals()["PROTOCOL"] = tmp / "protocol"
        globals()["FLOOR_FILE"] = floor_path if floor_path is not None else tmp / "floor.txt"
        globals()["code_commits"] = lambda _r: pop
        globals()["rev_parse"] = rev or revs()
        globals()["_count"] = lambda *_a: -1
        return judge(arg)

    try:
        # ---- must-pass: the orphan set IS the declared floor set -------------------------------
        with tree() as tmp:
            entry(tmp, commits=f"[{_A[:7]}]")
            floor_file(tmp, shas=(_B[:7],))
            v = drive(tmp, [Commit(_A, "covered"), Commit(_B, "declared orphan")])
            expect("must-pass: a tree exactly at its declared floor", v.code, 0)

        # ---- mutant: a NEW orphan, not on the floor --------------------------------------------
        with tree() as tmp:
            entry(tmp, commits=f"[{_A[:7]}]")
            floor_file(tmp, shas=(_B[:7],))
            v = drive(tmp, [Commit(_A, "covered"), Commit(_B, "declared"), Commit(_C, "NEW")])
            expect("mutant new-orphan", v.code, 1)
            ok("mutant new-orphan NAMES the commit", any(_C[:7] in e for e in v.errs))

        # ---- THE MUTANT THIS REWRITE EXISTS FOR: same count, different identity ----------------
        # floor declares {B}; the tree's orphan is {C}. One orphan either way, so the old integer
        # rule passed. Under an ID set this is one cleared and one added, and it must FAIL.
        with tree() as tmp:
            entry(tmp, commits=f"[{_A[:7]}, {_B[:7]}]")
            floor_file(tmp, shas=(_B[:7],))
            v = drive(tmp, [Commit(_A, "covered"), Commit(_B, "now covered"),
                            Commit(_C, "swapped in")])
            expect("mutant SWAP: same orphan COUNT, different IDENTITY", v.code, 1)
            ok("mutant SWAP is genuinely a mutant: the OLD integer rule passed it",
               _legacy_verdict(1, 1) == 0)
            ok("mutant SWAP prints the delta in BOTH directions",
               "1 cleared, 1 added by identity" in v.line)

        # ---- must-pass: RANGE-INDEPENDENCE. Four spellings of the declared range, one verdict ---
        with tree() as tmp:
            entry(tmp, commits=f"[{_A[:7]}]")
            floor_file(tmp, shas=(_B[:7],))
            pop = [Commit(_A, "covered"), Commit(_B, "declared orphan")]
            seen = {(v.code, v.line, v.orphans) for v in
                    (drive(tmp, pop, arg=s) for s in
                     (None, "HEAD~9..HEAD", f"{_BASE}..HEAD", "some-tag..HEAD"))}
            ok("RANGE-INDEPENDENCE: 4 spellings of the declared range -> ONE "
               "(exit, line, orphan-set) triple", len(seen) == 1)
            ok("RANGE-INDEPENDENCE: and that one verdict is the PASS",
               len(seen) == 1 and next(iter(seen))[0] == 0)

        # ---- mutant: a DIFFERENT range is refused, not answered --------------------------------
        with tree() as tmp:
            entry(tmp, commits=f"[{_A[:7]}]")
            floor_file(tmp, shas=(_B[:7],))
            other = _S("eee5555")
            v = drive(tmp, [Commit(_A, "a")], arg=f"{other}..HEAD",
                      rev=revs({other: other, other[:7]: other}))
            expect("mutant off-range: a floor judging a population it was not declared over",
                   v.code, 2)

        # ---- mutant: a bare token — git would read it as a PATHSPEC ----------------------------
        with tree() as tmp:
            entry(tmp, commits=f"[{_A[:7]}]")
            floor_file(tmp, shas=(_B[:7],))
            v = drive(tmp, [Commit(_A, "a")], arg="example_tpch_ontology")
            expect("mutant pathspec-as-range", v.code, 2)
            ok("mutant pathspec-as-range says WHY", "PATHSPEC" in v.errs[0])

        # ---- mutant: the runner's <bundle-root>, which is a real directory ---------------------
        with tree() as tmp:
            entry(tmp, commits=f"[{_A[:7]}]")
            floor_file(tmp, shas=(_B[:7],))
            v = drive(tmp, [Commit(_A, "a")], arg=str(tmp))
            expect("mutant bundle-root-as-range (run_framework_gates.sh's argv[1])", v.code, 2)
            ok("mutant bundle-root names the runner", "run_framework_gates" in v.errs[0])

        # ---- mutant: a symmetric-difference range ----------------------------------------------
        with tree() as tmp:
            entry(tmp, commits=f"[{_A[:7]}]")
            floor_file(tmp, shas=(_B[:7],))
            expect("mutant triple-dot range",
                   drive(tmp, [Commit(_A, "a")], arg="HEAD~9...HEAD").code, 2)

        # ---- mutant: an entry missing a required section ---------------------------------------
        with tree() as tmp:
            entry(tmp, commits=f"[{_A[:7]}]", body="## EVIDENCE\nonly this\n")
            floor_file(tmp, shas=())
            expect("mutant missing-sections", drive(tmp, [Commit(_A, "a")]).code, 1)

        # ---- mutant: NO entries at all -> could-not-run, never a pass --------------------------
        with tree() as tmp:
            (tmp / "protocol").mkdir()
            floor_file(tmp, shas=())
            expect("mutant zero-entries", drive(tmp, [Commit(_A, "a")]).code, 2)

        # ---- mutant: NO commits examined. 0 examined is not 0 orphans. -------------------------
        with tree() as tmp:
            entry(tmp, commits=f"[{_A[:7]}]")
            floor_file(tmp, shas=())
            expect("mutant zero-denominator", drive(tmp, []).code, 2)

        # ---- mutant: git itself failed -> distinguishable from an empty range ------------------
        with tree() as tmp:
            entry(tmp, commits=f"[{_A[:7]}]")
            floor_file(tmp, shas=())
            v = drive(tmp, "git could not read `x` as a revision range: fatal")
            expect("mutant git-failed", v.code, 2)
            ok("mutant git-failed is NOT mislabelled as an empty range",
               "no code-bearing commit" not in v.errs[0])

        # ---- mutant: no floor FILE -------------------------------------------------------------
        with tree() as tmp:
            entry(tmp, commits=f"[{_A[:7]}]")
            expect("mutant no-floor-file",
                   drive(tmp, [Commit(_A, "a")], floor_path=tmp / "absent.txt").code, 2)

        # ---- mutants: each required header, missing ---------------------------------------------
        for name, kw in (("no OWNER", dict(header="# DECLARED: 2026-09-13\n")),
                         ("no DECLARED", dict(header="# OWNER: the fixture\n")),
                         ("no BASE", dict(base=None))):
            with tree() as tmp:
                entry(tmp, commits=f"[{_A[:7]}]")
                floor_file(tmp, shas=(_B[:7],), **kw)
                expect(f"mutant floor header: {name}",
                       drive(tmp, [Commit(_A, "a"), Commit(_B, "b")]).code, 2)
        with tree() as tmp:
            entry(tmp, commits=f"[{_A[:7]}]")
            (tmp / "floor.txt").write_text(_GOOD_HEADER + f"# BASE: {_BASE}\n\n{_B[:7]}\n",
                                           encoding="utf-8")
            expect("mutant floor header: no STANDING",
                   drive(tmp, [Commit(_A, "a"), Commit(_B, "b")]).code, 2)

        # ---- mutant: STANDING disagrees with the set it stands over -----------------------------
        with tree() as tmp:
            entry(tmp, commits=f"[{_A[:7]}]")
            floor_file(tmp, shas=(_B[:7],), standing=9)
            expect("mutant standing-disagrees-with-its-own-set",
                   drive(tmp, [Commit(_A, "a"), Commit(_B, "b")]).code, 2)

        # ---- mutant: the floor's BASE does not resolve here -------------------------------------
        with tree() as tmp:
            entry(tmp, commits=f"[{_A[:7]}]")
            floor_file(tmp, base=_S("f0f6666"), shas=())
            expect("mutant unresolvable-BASE", drive(tmp, [Commit(_A, "a")]).code, 2)

        # ---- mutant: a floor member that is not an identity ------------------------------------
        with tree() as tmp:
            entry(tmp, commits=f"[{_A[:7]}]")
            floor_file(tmp, shas=("abc",))
            expect("mutant floor-member-too-short-to-be-an-identity",
                   drive(tmp, [Commit(_A, "a")]).code, 2)

        # ---- mutant: a floor member matching MORE than one commit ------------------------------
        with tree() as tmp:
            entry(tmp, commits="[none]")
            floor_file(tmp, shas=("aaa1111",))
            v = drive(tmp, [Commit(_S("aaa1111"), "one"), Commit("aaa1111ff" + "0" * 31, "two")])
            expect("mutant ambiguous-floor-member", v.code, 2)

        # ---- mutant: a sha named only in the `commits:` INLINE COMMENT is not coverage ---------
        with tree() as tmp:
            entry(tmp, commits=f"[{_A[:7]}]   # {_B[:7]} is mentioned in PROSE here")
            floor_file(tmp, shas=())
            expect("mutant sha-named-only-in-a-commits-comment",
                   drive(tmp, [Commit(_A, "a"), Commit(_B, "named only in a comment")]).code, 1)

        # ---- reported-not-failed: a cleared floor sha PASSES and prints the ratchet -------------
        with tree() as tmp:
            entry(tmp, commits=f"[{_A[:7]}, {_B[:7]}]")
            floor_file(tmp, shas=(_B[:7],))
            v = drive(tmp, [Commit(_A, "a"), Commit(_B, "now covered")])
            expect("must-pass: a cleared floor sha", v.code, 0)
            ok("a cleared floor sha prints a [RATCHET] instruction",
               any("[RATCHET]" in n and "remove" in n.lower() for n in v.notes))
            ok("a cleared floor sha is reported by identity on the PASS line",
               "1 cleared, 0 added by identity" in v.line)

        # ---- reported-not-failed: a STALE floor sha (outside the population) is disclosed -------
        with tree() as tmp:
            entry(tmp, commits=f"[{_A[:7]}]")
            floor_file(tmp, shas=(_C[:7],))
            v = drive(tmp, [Commit(_A, "a")])
            ok("a stale floor sha is disclosed as silent headroom",
               any("matches NO commit" in n for n in v.notes))

        # ---- reported-not-failed: an untagged entry is invisible to the wiki, and disclosed -----
        with tree() as tmp:
            entry(tmp, commits=f"[{_A[:7]}]", topics="")
            floor_file(tmp, shas=())
            ok("an untagged entry is disclosed in the denominator",
               "invisible to the wiki" in drive(tmp, [Commit(_A, "a")]).line)

        # ---- reported-not-failed: a citation too short to identify a commit is IGNORED ---------
        with tree() as tmp:
            entry(tmp, commits="[aaa]")
            floor_file(tmp, shas=(_A[:7],))
            v = drive(tmp, [Commit(_A, "a 3-char citation must not cover this")])
            expect("must-pass: a sub-7-char citation does not count as coverage", v.code, 0)
            ok("an unusable citation is disclosed", any("unusable" in n for n in v.notes))
    finally:
        (globals()["PROTOCOL"], globals()["FLOOR_FILE"], globals()["code_commits"],
         globals()["rev_parse"], globals()["_count"]) = real

    total = len(asserted)
    mutants = sum(1 for a in asserted if a.startswith("mutant") and "-> exit" in a)
    musts = sum(1 for a in asserted if a.startswith("must-pass"))
    if failures:
        print(f"FAIL: check_protocol self-test — {len(failures)} of {total} assertion(s) failed "
              f"over {trees} synthetic tree(s)")
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"PASS: check_protocol self-test — {total}/{total} assertions over {trees} synthetic "
          f"trees: {mutants} mutants, each rejecting as its own class, {musts} must-pass fixtures, "
          f"and {total - mutants - musts} disclosure/behaviour assertions. The class the old "
          f"integer floor could NOT see is asserted both ways: mutant SWAP (same orphan count, "
          f"different identity) fails here, and the restated old rule is shown to have passed it. "
          f"RANGE-INDEPENDENCE is asserted positively — four spellings of the declared range yield "
          f"ONE (exit, line, orphan-set) triple — and negatively, by four refusal classes: "
          f"off-range, pathspec, bundle-root, triple-dot.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
