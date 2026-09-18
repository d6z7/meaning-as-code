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

# THE PRE-RELEASE ALPHABET, declared ONCE — and the grammar is BUILT FROM IT, not the other way
# round. Scraping the alphabet back out of a compiled regex was the obvious shortcut and it is
# wrong in three separate ways: `(-develop|-rc)?` yields a bogus member, `(-[a-z]+)?` is not
# enumerable at all, and `(-develop)?(\+\w+)?` hands back the WRONG GROUP — silently dropping
# '-develop' and, with it, every file carrying the outgoing pre-release spelling. Inverting the
# dependency is the only formulation in which "derived, not typed" is actually true of the suffixes.
PRERELEASE = ("", "-develop")
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)("
                    + "|".join(re.escape(s) for s in PRERELEASE if s) + r")?$")

# ── THE SCHEMA-VERSION FLOOR ──────────────────────────────────────────────────────────────────────
# The oldest generation whose content this framework still agrees to validate. It is DECLARED, once,
# and it is the only hand-set datum in the recognized-version machinery — everything else is derived
# from it and from CURRENT by the order predicate below.
#
# WHY A FLOOR AND NOT A LIST. tools/validate_schema.py used to carry a hand-typed literal:
#     RECOGNIZED = {CURRENT, CURRENT.split('-')[0], '0.1.13', '0.1.12', '0.1.11', '0.1.10', '0.1.9'}
# which required someone to remember, on EVERY bump, to add the OUTGOING version to it. That was
# forgotten once already — commit eda1fae, "0.1.12 was dropped from the RECOGNIZED literal when
# CURRENT last bumped", which left the schema gate and the version pre-flight as inverses around the
# boundary. A floor is declared once and touched only when the estate deliberately stops supporting
# a generation. Forgetting THAT is loud (exit 2), not silent.
#
# WHY IT IS LOAD-BEARING. Measured 2026-09-18 across the estate: 0.1.13 carries the largest cohort of
# stamped files, 0.1.9 the next. A floor above either changes thousands of files' state in one
# commit, so it must sit at or below 0.1.9 to change nothing today.
#
# WHY IT CANNOT RISE YET, and this is the coupling that is invisible from validate_schema.py: the SDK
# is STILL MINTING 0.1.13. sdk/authoring/authoring.py, sdk/authoring/data_plane.py and
# tools/mac_to_meta.py template new files at that stamp. Raise the floor above 0.1.13 before sweeping
# those template sites and newly, correctly authored files become findings on the day they are written.
#
# VALUES THIS FLOOR HAS HELD (append here, never rewrite — this is the record, in the
# tools/mac_public_floor.txt style, whose own lesson was "a floor above the measurement is not a
# ratchet, it is silent headroom"):
#   0.1.9   2026-09-18  initial declaration; chosen to be a superset of the literal it replaced, so
#                       that zero files changed state at the moment the derivation landed.
SCHEMA_VERSION_FLOOR = "0.1.9"


class VersionLineError(Exception):
    """A version string that cannot be placed on the line — malformed, or below the floor.

    A real exception class, NOT `parse()`'s SystemExit: the recognized range is built at
    `import validate_schema`, and a SystemExit there would take down mac_checks_structure.py,
    check_conformance.py and mac_compile.py with exit 1 — the SAME code the gate uses for schema
    violations, so a setup mistake would masquerade as a content red. Callers catch this and exit 2.
    """


def base_key(v: str) -> tuple:
    """The ORDER key: (major, minor, patch), with any pre-release marker discarded.

    A pre-release sorts AS ITS BASE, deliberately. '0.1.14' and '0.1.14-develop' name the same
    generation — bundle files carry the released number while develop is open on the pre-release —
    and the incident that created this rule ("63 files silently skipped, which is worse than a red")
    was exactly the two being separated.
    """
    m = SEMVER.match(str(v))
    if not m:
        raise VersionLineError(f"not a version: {v!r} — expected a.b.c or a.b.c-develop")
    return int(m[1]), int(m[2]), int(m[3])


class RecognizedVersions:
    """The recognized set, as an ORDER rather than a list: FLOOR <= base(sv) <= base(CURRENT).

    Membership is a comparison, so the set CANNOT NARROW when CURRENT moves — a bump only ever
    raises the ceiling. That is what makes the bump trap unarmable rather than merely detected, and
    it is why nothing here enumerates. Three consequences worth stating, because each one killed a
    previous design:

      * THE OUTGOING PRE-RELEASE SURVIVES. Both spellings of every generation in range are members,
        so nobody has to remember to keep the pair. The literal kept the pair only for CURRENT and
        evicted the outgoing one on every bump.
      * A LINE MIGRATION COSTS NOTHING. At CURRENT 0.2.0, 0.1.13 still sorts inside [0.1.9, 0.2.0],
        so the whole closed 0.1.x line stays recognized with no registry of closed lines to maintain
        and no estate-wide red. An enumeration would have yielded {0.2.0} and turned every 0.1.x
        file into a finding in one commit.
      * A MALFORMED STAMP IS NOT A MEMBER. A bare '0.1' does not parse, so it is unrecognized —
        which is the correct answer for it, and the answer the UNCHECKED class exists to report.

    The known looseness, stated plainly: a range admits a patch number MAC never shipped (a stamp of
    '0.1.11' when '0.1.13' was meant is inside the range and passes). A typo OUTSIDE the range is
    caught. Closing the inside-the-range case needs a real shipped-version registry, which this
    repository does not have — there is no CHANGELOG, git tags stop at v0.1.9, and CONFORMANCE.md §6
    omits 0.1.10 entirely. Manufacturing one would be a second hand-maintained literal, which is the
    defect being removed.
    """

    __slots__ = ("floor", "current", "ceiling", "_floor_k", "_ceiling_k")

    def __init__(self, floor: str, current: str):
        self.floor, self.current = str(floor), str(current)
        self.ceiling = self.current.split("-")[0]
        self._floor_k = base_key(self.floor)
        self._ceiling_k = base_key(self.ceiling)
        if self._ceiling_k < self._floor_k:
            # WITHOUT THIS the range is simply empty and NOTHING is recognized — every routed file
            # falls out at once while the old fraction re-normalised to a perfect N/N. The hand-typed
            # literal had no such failure mode, so the derivation must not introduce one.
            raise VersionLineError(
                f"CURRENT {self.current} is BELOW the declared floor {self.floor} — a version "
                f"cannot precede its own floor; fix CURRENT or re-declare SCHEMA_VERSION_FLOOR")

    def __contains__(self, sv) -> bool:
        try:
            k = base_key(sv)
        except VersionLineError:
            return False                      # malformed, or absent — never silently admitted
        return self._floor_k <= k <= self._ceiling_k

    def describe(self) -> str:
        """The phrase every consumer prints, so the gate and the compiler state the same contract.

        A LIST would be 12 members today, 22 at 0.1.19 and 182 at 0.1.99 — a diagnostic that
        degrades as the set grows. A range does not.
        """
        return f"{self.floor} … {self.current} inclusive, both spellings (floor {self.floor})"

    def __iter__(self):
        """The enumerable spellings OF THE CURRENT LINE, for display and for older callers.

        Membership is `__contains__`, not this: across a closed minor line there is no way to know
        how many patches it held, and inventing one is exactly the registry this design refuses to
        maintain. Print `describe()`; iterate only when you want examples.
        """
        maj, mi, ceil_p = self._ceiling_k
        lo = self._floor_k[2] if self._floor_k[:2] == (maj, mi) else 0
        for p in range(lo, ceil_p + 1):
            for s in PRERELEASE:
                yield f"{maj}.{mi}.{p}{s}"

    def __len__(self):
        return sum(1 for _ in self)

    def __repr__(self):
        return f"RecognizedVersions({self.describe()})"


def recognized(current: str, floor: str = SCHEMA_VERSION_FLOOR) -> RecognizedVersions:
    """The recognized versions when CURRENT is `current`.

    `current` is REQUIRED and has no default, and this never falls back to `read()`. VERSION-vs-claims
    disagreement is precisely what `--check` exists to police and it is RED on this tree today; a
    defaulted `current` would make the ceiling depend on a file already known to disagree, which is a
    new silent path for the ceiling to move. The caller states what it thinks CURRENT is.
    """
    return RecognizedVersions(floor, current)

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
    # THE FLOOR REPORTS ITS OWN SLACK. tools/mac_public_floor.txt's lesson, transferred: "a floor
    # above the measurement is not a ratchet — it is silent headroom". A floor several generations
    # below CURRENT is grace being extended to old content, and grace nobody counts is just a hole.
    try:
        rec = recognized(src)
        grace = rec._ceiling_k[2] - rec._floor_k[2] if rec._floor_k[:2] == rec._ceiling_k[:2] else None
        print(f"  schema-version floor  {SCHEMA_VERSION_FLOOR}   (recognized: {rec.describe()})")
        print(f"  {' ' * 2}slack                                  "
              + (f"{grace} generation(s) of grace below CURRENT" if grace is not None
                 else f"spans a line boundary — {SCHEMA_VERSION_FLOOR} is not in {src}'s line"))
    except VersionLineError as e:
        print(f"  ✗ schema-version floor  {SCHEMA_VERSION_FLOOR}   {e}")
        bad.append({"what": "schema-version floor"})
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
    ap.add_argument("--force", action="store_true",
                    help="with --set: allow the version to go BACKWARDS (it refuses by default)")
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
        # --set validated only the GRAMMAR, so it would happily move the version backwards. That is
        # the one input that can push CURRENT below the floor, and a ceiling below its floor means
        # NOTHING is recognized. Refuse a decrease; --force is the deliberate escape hatch.
        if base_key(a.set) < base_key(cur) and not a.force:
            print(f"  ✗ refusing to go backwards: {cur} -> {a.set}. A lower CURRENT lowers the "
                  f"recognized ceiling and can drop it below the floor ({SCHEMA_VERSION_FLOOR}), "
                  f"at which point nothing is validated. Pass --force if you mean it.")
            return 1
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
