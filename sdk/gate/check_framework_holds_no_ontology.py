#!/usr/bin/env python3
"""
check_framework_holds_no_ontology.py — the framework is GENERIC, so it owns no ontology instance.

Operator, 2026-10-08: "mac cannot contain any ontology as it is overarching generic framework ...
delete or migrate everyting 'ontology configuration' from mac", and on the principle that this gate
exists to keep true: "from ontology perspective mac is imutable".

WHY A GATE AND NOT A RULE SOMEBODY REMEMBERS. The day before this was written the framework held
TWELVE complete ontology bundles -- eleven under bundlegen/generated/ (394 files, 350 concepts, 11
constitutions, 11 connection.yaml, 11 vocabulary.yaml) plus the authoring exemplar -- and ELEVEN OF
THE TWELVE failed this repository's own validator:

    mac.project.yaml   'planes' is a required property
    concept            'identity' was unexpected          <- retired 2026-10-05
    concept/class      'reference' is not one of [...]    <- renamed to entity, 2026-10-05
    grounding/sources  should not be valid under {}       <- became `source`, 2026-10-07

Three column-surface shapes were retired under them in four days and NOTHING NOTICED, because
nothing enumerated them. That is the failure this gate is built from: not the bundles, but the
absence of a denominator. A count nobody takes is the precondition for every one of those eleven.

AND THE HONEST COUNTER DECIDES THE DESIGN. The exemplar that survives is INDISTINGUISHABLE IN SHAPE
from the eleven that went, and shape-indistinguishable is exactly how eleven unvalidated bundles
accumulated. So what separates a kept golden from an accumulated instance must not be anyone's
judgement. It is two measurements, both checkable here:

    1. it is DECLARED below, with a reason and its readers, so adding one is a visible act; and
    2. it is CLEAN under validate_schema, so it cannot rot the way the eleven did.

A bundle that is declared but dirty FAILS. A bundle that is clean but undeclared FAILS. Neither is
an opinion.

WHAT COUNTS AS A BUNDLE: a directory holding `mac.project.yaml`. That is the ontology's CONSTITUTION
-- the file a framework mechanism must read to know how the bundle is built (the operator's fourth
principle). Keying on the constitution rather than on a directory NAME is deliberate: the ontology
guard keys on the literal path segment `/ontology/` and therefore cannot see a bundle that declares
`planes.ontology: model`, which is the hole reported separately. This gate does not inherit it.

Usage:
    python3 -m sdk.gate.check_framework_holds_no_ontology [<repo-root>]
    python3 -m sdk.gate.check_framework_holds_no_ontology --self-test

Exit: 0 = PASS · 1 = FAIL (an undeclared bundle, or a declared one that does not validate) · 2 = could not run
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

#: THE DECLARED SET. One entry per bundle the framework is allowed to carry, each with the reason it
#: is not an instance of meaning and the readers that resolve through it. An entry is a standing
#: claim: adding one is a visible act in a diff, which is the half the eleven never had.
DECLARED = {
    "sdk/authoring/exemplars/bundle": (
        "THE COMPOSER ROUND-TRIP GOLDEN, not a managed ontology. tools/check_document_layout.py "
        "calls it \"a golden cut from a private estate\" and treats it as FROZEN INPUT: its only job "
        "is to let the layout gate prove the concept-page projector's output is byte-stable. Same "
        "category as a .sql fixture. Readers: tests/test_concept_page_layout.py:47, "
        "tools/check_document_layout.py:63 (FREEZE_BUNDLE), tests/test_column_roundtrip.py, "
        "guardrails/strategy.yaml:295. SECOND HOME, NAMED RATHER THAN RESOLVED: mac-platform's "
        "packages/mac-runtime/tests/fixtures/column_standard_bundle is asserted byte-identical to "
        "it, and two copies of a golden is the one case where drift is silent by construction -- "
        "each repository's gate passes against its own copy."
    ),
}

#: Trees whose files are SCHEMA TEST INPUTS, not bundles: single malformed documents fed to
#: test_negative, and flat trees with no constitution at all. None carries a `mac.project.yaml`, so
#: none is a bundle by this gate's definition; they are listed only so the concept-file count below
#: has a stated population rather than an unexplained remainder.
TEST_INPUT_TREES = ("tests/fixtures/",)

#: THE STANDARD IS NOT AN INSTANCE. mac_vocabulary.yaml carries a top-level `concept:` key because
#: that is the TERM NAMESPACE -- `concept.class`, `concept.column.role` and the rest, folded -- and a
#: naive scan for a `concept:` line counts it as a concept file. It is the framework's own standard
#: and the one thing here that MUST live in the framework. Named rather than silently skipped: an
#: unexplained remainder in a gate's population is how a denominator stops meaning anything.
STANDARD_FILES = ("mac_vocabulary.yaml",)

SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".pytest_cache", "build", "dist"}
CONSTITUTION = "mac.project.yaml"


def find_bundles(root: Path) -> list[str]:
    """Every directory under `root` holding a constitution, repo-relative, sorted."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        if CONSTITUTION in filenames:
            rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
            if rel != ".":
                out.append(rel)
    return sorted(out)


def count_concept_files(root: Path) -> tuple[int, list[str]]:
    """How many files in the tree declare a top-level `concept:`, and in which trees they sit."""
    n, trees = 0, set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for f in filenames:
            if not f.endswith((".yaml", ".yml")):
                continue
            p = Path(dirpath) / f
            try:
                head = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
            if (rel == "." and f in STANDARD_FILES):
                continue                       # the standard, not an instance — see STANDARD_FILES
            if any(line.startswith("concept:") for line in head.splitlines()):
                n += 1
                trees.add(next((t for t in TEST_INPUT_TREES if rel.startswith(t.rstrip("/"))), rel))
    return n, sorted(trees)


def validates(root: Path, rel: str) -> tuple[bool, str]:
    """Run validate_schema over one bundle. Returns (clean, the verdict line)."""
    tool = root / "tools" / "validate_schema.py"
    if not tool.is_file():
        return False, f"no {tool}"
    pr = subprocess.run([sys.executable, str(tool), str(root / rel)],
                        capture_output=True, text=True)
    line = next((l.strip() for l in reversed(pr.stdout.splitlines())
                 if l.startswith(("PASS:", "FAIL:"))), pr.stdout.strip()[-160:])
    return pr.returncode == 0 and line.startswith("PASS:"), line


def run(root: Path) -> int:
    found = find_bundles(root)
    declared = sorted(DECLARED)
    undeclared = [b for b in found if b not in DECLARED]
    missing = [b for b in declared if b not in found]
    concepts, trees = count_concept_files(root)

    print(f"── the framework's ontology content ── {root} ──")
    print(f"  bundles found (dirs holding {CONSTITUTION}): {len(found)}")
    for b in found:
        print(f"      {b}{'' if b in DECLARED else '   <- UNDECLARED'}")
    print(f"  declared: {len(declared)}   ·   concept files in the tree: {concepts} "
          f"over {len(trees)} tree(s)")
    for t in trees:
        print(f"      {t}")

    findings = []
    for b in undeclared:
        findings.append(
            f"UNDECLARED BUNDLE  {b}\n"
            f"      A generic framework ships no ontology instance. Either delete it, or move it to a\n"
            f"      bundle repository, or — if it is a frozen golden like the one declared above —\n"
            f"      declare it in DECLARED with its reason and its readers. Eleven bundles reached\n"
            f"      this repository without that step and all eleven rotted unvalidated.")
    for b in missing:
        findings.append(
            f"DECLARED BUT ABSENT  {b}\n"
            f"      The declaration outlived the bundle. Remove the entry — a declaration that\n"
            f"      names nothing is an exemption over nothing.")

    # EVERY DECLARED BUNDLE MUST VALIDATE. This is the half that would have caught the eleven: they
    # were not dirty-and-ignored, they were dirty-and-UNMEASURED.
    print("  declared bundles under validate_schema:")
    for b in declared:
        if b in missing:
            continue
        clean, line = validates(root, b)
        print(f"      {'✓' if clean else '✗'} {b}")
        print(f"          {line[:150]}")
        if not clean:
            findings.append(
                f"DECLARED BUNDLE DOES NOT VALIDATE  {b}\n"
                f"      {line[:200]}\n"
                f"      A golden the framework keeps must conform to the framework's own standard,\n"
                f"      or it is the eleven again: an instance frozen at a generation the schema has\n"
                f"      moved past, passing nothing because nobody asked it.")

    print()
    if findings:
        for f in findings:
            print(f"  [ERROR] {f}")
        print(f"\nFAIL: check_framework_holds_no_ontology — {len(findings)} finding(s) over "
              f"{len(found)} bundle(s) found, {len(declared)} declared, {concepts} concept file(s) "
              f"in the tree")
        return 1
    print(f"PASS: check_framework_holds_no_ontology — {len(found)} of {len(found)} bundle(s) are "
          f"declared and validate clean; {concepts} concept file(s) in the tree, all in declared "
          f"bundles or schema test inputs ({', '.join(trees) or 'none'})")
    return 0


# ── self-test ─────────────────────────────────────────────────────────────────────────────────────

def _self_test() -> int:
    import shutil
    import tempfile
    fails = 0

    def case(cond, msg):
        nonlocal fails
        print(("✓ " if cond else "✗ ") + msg)
        fails += 0 if cond else 1

    tmp = Path(tempfile.mkdtemp(prefix="holds_no_ontology_"))
    try:
        # an empty tree holds no bundle
        case(find_bundles(tmp) == [], "an empty tree reports no bundle")

        # a constitution anywhere IS a bundle, whatever the plane is called — the point of keying on
        # the constitution rather than on the string "ontology"
        for plane in ("ontology", "model", "semantics"):
            d = tmp / f"b_{plane}"
            (d / plane / "concepts").mkdir(parents=True)
            (d / CONSTITUTION).write_text(f"planes:\n  data: data\n  ontology: {plane}\n")
            (d / plane / "concepts" / "x.yaml").write_text("concept:\n  name: X\n")
        found = find_bundles(tmp)
        case(len(found) == 3, f"a bundle is found by its CONSTITUTION, not its plane name ({found})")
        case(all(f.startswith("b_") for f in found),
             "a plane called model/ or semantics/ is seen exactly like ontology/")

        n, trees = count_concept_files(tmp)
        case(n == 3, f"concept files counted: {n} (want 3)")

        # the nested case the walker must not miss: a bundle inside another directory
        deep = tmp / "a" / "b" / "c"
        (deep).mkdir(parents=True)
        (deep / CONSTITUTION).write_text("planes:\n  ontology: ontology\n")
        case("a/b/c" in find_bundles(tmp), "a nested bundle is found")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{'all assertions passed' if not fails else str(fails) + ' FAILED'}")
    return 1 if fails else 0


def main() -> int:
    # EVERY FLAG IS DECLARED, NOT SNIFFED. The first cut read `if "--self-test" in sys.argv` and
    # never defined the flag on a parser — and check_seam_agreement caught it within the hour:
    #   [subprocess-argv-divergence] caller passes ['--self-test'] which this file does not define
    #                                (parser defines [])
    # run_gates.sh passes `--self-test`, so the flag WORKED; it worked by accident of a substring
    # test rather than by declaration, which is the shape this estate calls declared-but-unread
    # pointed the other way: read-but-undeclared. An argv nobody declares cannot be checked against
    # its callers, and that seam class exists precisely to compare the two.
    ap = argparse.ArgumentParser(
        prog="check_framework_holds_no_ontology",
        description="assert the framework owns no ontology instance beyond its declared goldens")
    ap.add_argument("root", nargs="?", default=None,
                    help="repository root to judge (default: this gate's own repository)")
    ap.add_argument("--self-test", action="store_true",
                    help="prove the gate can still reject an undeclared or rotted bundle")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()
    # sdk/gate/<this>.py -> parents[2] is the repository root. run_gates.sh invokes every gate as
    # `python3 -m sdk.gate.<name>`, which is why this lives here and not in tools/.
    root = Path(a.root).resolve() if a.root else Path(__file__).resolve().parents[2]
    if not root.is_dir():
        print(f"could not run: check_framework_holds_no_ontology — {root} is not a directory",
              file=sys.stderr)
        return 2
    return run(root)


if __name__ == "__main__":
    sys.exit(main())
