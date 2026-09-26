#!/usr/bin/env python3
"""check_bundle_isolation.py — TWO BUNDLES SHARE NOTHING. No path of one may reach another.

THE OPERATOR'S RULING, 2026-09-26: "two bundles are prohibited to share anything. please keep them
absolutely isolated from each other. the only allowed thing would be YOU checking for the reference
across the border ... but ontology should not be allowed in any case there."

WHY IT IS A RULE AND NOT A PREFERENCE — two measured defects from ONE relative path. A bundle's
`connection.yaml` named `../../../mac-ontology-contoso/contoso.duckdb`, and:

  1. THAT WAREHOUSE CARRIED ANOTHER ONTOLOGY'S MEANING PLANE. The import measured its 8 `meta_*`
     relations as business data — 32 artifacts, including `data/samples/meta_concept.sample.csv`
     holding rows like `('AgeBand','enumeration')`: the other bundle's CONCEPT NAMES as this one's
     data. The billed concept stage would then have been asked what notion `meta_concept` is, and the
     honest answer is "a concept" — an ontology about an ontology, every gate passing.
  2. A CHANGE OVER THERE MOVES THE NUMBERS OVER HERE, silently. A bundle whose warehouse is someone
     else's cannot prove its own state: re-run it a week later and a difference is unattributable.

THE ONE PERMITTED CROSS-BORDER ACT is comparing a reference ANSWER — a human, or an agent, checking
that two bundles agree on a number. That is an act of REVIEW, performed from outside both, and it
leaves no path inside either. What is never permitted is a FILE of one bundle naming another.

WHAT IT CHECKS, and it is deliberately blunt: every text artifact a bundle owns, for a path that
escapes its own root.

  * `..` in any declared path            -> ESCAPES  (the shape that caused both defects)
  * an absolute path outside the root    -> ESCAPES
  * the NAME of a sibling bundle         -> NAMES ANOTHER BUNDLE (found by walking the parent of the
                                           bundle's own container, so it needs no list to maintain)

ONTOLOGY IS HELD TO THE SAME RULE AND SAID SO EXPLICITLY. The operator's sentence singles it out —
"ontology should not be allowed in any case there" — so a hit under `ontology/` is reported as a
BREACH rather than a finding, because a concept that reads across a border has made another bundle's
meaning part of its own.

Exit 0 when nothing escapes, 1 on any escape, 2 when the bundle cannot be read.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

#: THE FRAMEWORK IS WHERE THIS TOOL LIVES — derived, not listed. A bundle calling a framework tool by
#: absolute path is every bundle by definition, and a rule forbidding it would forbid being a bundle.
FRAMEWORK_ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Files worth reading. A `.duckdb` or `.parquet` is bytes, not a declaration.
_TEXT = {".yaml", ".yml", ".json", ".md", ".sql", ".csv", ".py", ".sh", ".mac", ".txt"}
#: Artifacts that are RECORDS OF A RUN rather than declarations of the bundle. A tool's absolute path
#: appearing in a log or a run record is provenance, not a dependency — and rewriting history to hide
#: it would be worse than reporting it.
#: PROVENANCE IS NOT A DEPENDENCY. `governance/sme-history/` records WHERE an SME document was
#: extracted from — OneDrive paths on one operator's machine — and `.context_src/` holds the imported
#: source documents themselves. Both are the history of how the bundle came to be, and rewriting them
#: to satisfy a path rule would destroy the record. `documentation/` and `decisions/` are prose about
#: the estate, which legitimately names other repositories.
_SKIP_DIRS = {".git", ".harvest", ".context", ".context_src", "__pycache__", "artifacts",
              "documentation", "decisions", "sme-history"}
#: Generated REPORTS, which quote the paths of the tools that ran. The repo's own .gitignore calls
#: compile.json "compiler output — a report, never bundle content", and a report naming a tool's
#: absolute path is provenance, not a dependency.
_SKIP_NAMES = {"suite_history.jsonl", ".harvest_manifest.yaml", "compile.json",
               "diagnostics.json", "ontology_quality.json"}
#: A COMMENT DECLARES NOTHING. The rule is about what a bundle DECLARES, and prose ABOUT a border is
#: how a removed dependency is explained — this bundle's own build.sh quotes the path it used to name,
#: in order to say why it no longer does. Flagging that would punish the record of the fix.
_COMMENT = re.compile(r"^\s*(#|--|//|\*|/\*)")
#: `../` in a path, or a token that BEGINS an absolute path. The lookbehind excludes a slash that
#: follows a closing quote or a shell variable: `"$DATA"/transforms` is one path, not two, and two
#: versions of this pattern reported it as an escape before the lookbehind was right.
#: THE WHOLE RELATIVE PATH, not its first segment. A version that matched only `\.\./` resolved
#: every relative path ONE level up whatever its depth, so `../../../../other/w.duckdb` was judged as
#: if it were `../` — and a four-level escape read as an internal reference. Caught by the self-test.
_ESCAPE = re.compile(
    r"(?<![\w.])((?:\.\./)+[\w./-]*)"
    r"|(?:^|(?<=[\s=:]))[\"']?(/[A-Za-z][\w/.-]+)"
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.bundle).resolve()
    if not root.is_dir():
        print(f"REFUSED: {root} is not a directory")
        return 2

    siblings = _siblings(root)
    breaches: list[tuple[str, int, str, str]] = []
    findings: list[tuple[str, int, str, str]] = []
    scanned = 0
    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in _TEXT:
            continue
        rel = f.relative_to(root)
        if any(p in _SKIP_DIRS for p in rel.parts) or f.name in _SKIP_NAMES:
            continue
        scanned += 1
        for n, line in enumerate(_lines(f), 1):
            if _COMMENT.match(line):
                continue
            for name in siblings:
                # A BUNDLE NAME AS A PATH SEGMENT, not as a word. `example` is a bundle's container
                # AND an ordinary English noun: matched bare, it reported 180 lines of prose
                # ("the full column definitions with example data") as naming another bundle. A
                # reference to a bundle looks like `example/` or `/example`.
                if re.search(rf"(?:^|[\s\"'(/]){re.escape(name)}/", line):
                    hit = (str(rel), n, f"names the bundle {name!r} as a path", line.strip()[:96])
                    (breaches if rel.parts[0] == "ontology" else findings).append(hit)
                    break
            else:
                escaped, why = _escapes(line, root, here=f.parent)
                if escaped:
                    hit = (str(rel), n, why, line.strip()[:96])
                    (breaches if rel.parts[0] == "ontology" else findings).append(hit)

    print(f"isolation — {root.name}: {scanned} text artifact(s) scanned, "
          f"{len(siblings)} sibling bundle(s) known")
    if not breaches and not findings:
        print("OK — nothing in this bundle reaches outside it.")
        return 0

    if breaches:
        print(f"\nBREACH — {len(breaches)} line(s) UNDER ontology/ reach across a bundle border.\n"
              f"  The operator: \"ontology should not be allowed in any case there.\" A concept that\n"
              f"  reads across a border has made another bundle's meaning part of its own.\n")
        for path, n, why, text in breaches[:20]:
            print(f"  {path}:{n}  {why}\n      {text}")
    crossings = [f for f in findings if "ANOTHER BUNDLE" in f[2]]
    portability = [f for f in findings if "ANOTHER BUNDLE" not in f[2]]
    if crossings:
        print(f"\n{len(crossings)} line(s) outside ontology/ reach INTO ANOTHER BUNDLE:\n")
        for path, n, why, text in crossings[:20]:
            print(f"  {path}:{n}  {why}\n      {text}")
    if portability:
        print(f"\n{len(portability)} line(s) leave this bundle for somewhere that is neither a "
              f"bundle nor the framework — not the ruling's breach, but a bundle that reads an "
              f"arbitrary path on one machine cannot be rebuilt on another:\n")
        for path, n, why, text in portability[:20]:
            print(f"  {path}:{n}  {why}\n      {text}")
    print("\nFAIL — a bundle must hold its own landings, its own transforms and its own warehouse.\n"
          "       The one permitted cross-border act is comparing a reference ANSWER, which is a\n"
          "       review performed from OUTSIDE both bundles and leaves no path inside either.")
    return 1


def _siblings(root: pathlib.Path) -> set[str]:
    """The other bundles this machine holds, found rather than listed.

    A bundle lives at `<repo>/<domain>/<dataset>` or is a repo of its own, so the candidates are the
    directory names two levels up and one level up that carry a `mac.project.yaml`. Deriving them
    means no list to maintain — a bundle added tomorrow is checked for today.
    """
    names: set[str] = set()
    # A BUNDLE'S OWN ANCESTORS ARE NOT SIBLINGS. A first version walked the parents and accepted any
    # directory holding a `*/mac.project.yaml`, which accepted `example/` — contoso2's OWN container
    # — so every line containing the word "example" was reported as naming another bundle.
    mine = {p.name for p in (root, *root.parents)}
    for base in (root.parent, root.parent.parent):
        if not base.is_dir():
            continue
        for d in base.iterdir():
            try:
                if not d.is_dir() or d.resolve() == root or d.name in mine:
                    continue
                if (d / "mac.project.yaml").is_file() or any(d.glob("*/mac.project.yaml")):
                    names.add(d.name)
            except OSError:
                continue
    return {n for n in names if len(n) > 3}


def _escapes(line: str, root: pathlib.Path,
             here: pathlib.Path | None = None) -> tuple[bool, str]:
    """A path in this line that leaves the bundle FOR ANOTHER BUNDLE. Returns (escaped, why).

    A PATH TO THE FRAMEWORK IS NOT A BUNDLE BORDER, and getting that wrong was the last false
    positive: this bundle's `build.sh` calls
    `/Users/<operator>/meaning-as-code/tools/mac_descriptors.py`, which is the PLATFORM — every bundle uses
    it by definition, and a rule that forbade it would forbid being a bundle at all.

    So the test is not "does this path leave the root" but "does it land in ANOTHER BUNDLE": a
    directory that is, or contains, a `mac.project.yaml`. That needs no allowlist of framework
    paths — a new tool repository is fine on the day it appears, and a new bundle is caught on the
    day it appears.

    A RELATIVE PATH IS RESOLVED AGAINST THE FILE THAT WRITES IT, not reported on sight. A first
    version reported every `../` and produced 62 BREACHES on a real bundle whose rule pages link
    their own concept as `../brand.md` — which resolves to `ontology/concepts/brand.md`, INSIDE the
    bundle. A gate that calls an internal cross-reference a border crossing would have had every one
    of those 62 lines edited to satisfy it.
    """
    # BOTH SIDES RESOLVED, or the comparison is a coin toss. On macOS `/tmp` is a symlink to
    # `/private/tmp`, so a resolved candidate never matches an unresolved root and an INTERNAL link
    # reads as an escape — which is exactly how the self-test caught this.
    root = root.resolve()
    here = here.resolve() if here else None
    for m in _ESCAPE.finditer(line):
        raw = (m.group(1) or m.group(0)).strip().strip("\"'()[]")
        if raw.startswith("../"):
            landed = (here / raw).resolve() if here else None
            if landed is None or str(landed).startswith(str(root)):
                continue
            if _is_bundle_path(landed):
                return True, f"a relative path into ANOTHER BUNDLE ({landed})"
            return True, f"a relative path that leaves this bundle ({landed})"
        abs_path = m.group(2)
        if not abs_path:
            continue
        got = pathlib.Path(abs_path)
        if str(got).startswith(str(root)):
            continue
        if _is_bundle_path(got):
            return True, f"a path into ANOTHER BUNDLE ({got})"
        if str(got).startswith(str(FRAMEWORK_ROOT)):
            continue  # the framework, which every bundle uses
        # OUTSIDE THE BUNDLE, NOT A BUNDLE, NOT THE FRAMEWORK. Not the ruling's breach, and not
        # nothing: a bundle that reads an arbitrary path on one machine cannot be rebuilt on another.
        # Reported as a portability finding so the two are never confused.
        return True, f"a path outside this bundle, neither a bundle nor the framework ({got})"
    return False, ""


def _is_bundle_path(path: pathlib.Path) -> bool:
    """Does this path lie in, or name, a MAC bundle? A framework checkout does not."""
    for p in (path, *path.parents):
        try:
            if (p / "mac.project.yaml").is_file():
                return True
        except OSError:
            return False
        if p.parent == p:
            break
    return False


def _lines(f: pathlib.Path) -> list[str]:
    try:
        return f.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _self_test() -> int:
    """An escape is `../`, or an absolute path outside the root. Inside the root is not an escape."""
    # RESOLVED, because the function resolves both sides and a fixture that does not is comparing
    # two spellings of one place: on macOS `/tmp` is a symlink to `/private/tmp`, and an unresolved
    # fixture root made the "inside the bundle" case read as an escape.
    root = pathlib.Path("/tmp/b/example/contoso2").resolve()
    cases = [
        ("database: ../../../../other/w.duckdb     -> ESCAPES",
         "database: ../../../../other/w.duckdb", True),
        ("database: contoso2.duckdb                -> fine", "database: contoso2.duckdb", False),
        ("an absolute path inside the bundle       -> fine",
         f'path: "{root}/data/x.parquet"', False),
        ("an absolute path outside the bundle      -> ESCAPES",
         'path: "/Users/<operator>/other/x.parquet"', True),
        ("prose mentioning .. mid-sentence         -> fine", "see the note above ... and below", False),
    ]
    cases.append(("`../brand.md` from ontology/concepts/rules  -> fine (lands inside)",
                  "applies_to: ../brand.md", False))
    cases.append(("an absolute path into the FRAMEWORK          -> fine",
                  "python3 /Users/<operator>/dev/meaning-as-code/tools/mac_descriptors.py x", False))
    cases.append(('a shell variable then a slash                -> fine',
                  'for f in "$DATA"/transforms/*.sql; do', False))
    here = root / "ontology" / "concepts" / "rules"
    bad = 0
    for label, line, want in cases:
        if _escapes(line, root, here=here)[0] != want:
            bad += 1
            print(f"  FAIL  {label}")
    n = len(cases)
    print(f"\n{'FAIL' if bad else 'OK'} — self-test: {n - bad} of {n} seeded cases behaved")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
