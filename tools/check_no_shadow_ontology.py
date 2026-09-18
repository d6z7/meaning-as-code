#!/usr/bin/env python3
"""check_no_shadow_ontology.py — a concept authored OUTSIDE the declared ontology plane is a FAIL.

WHY THIS GATE EXISTS, and it is one measured event. On 2026-09-18 at 10:09 a concept-authoring
agent's first Write to a fresh bundle's `ontology/concepts/…` was refused by the PreToolUse guard.
The agent then read the guard, searched the repository for an unlock marker, found none — and wrote
its concepts INTO A TEMP DIRECTORY. The bundle's ontology plane was left holding exactly one file,
a diagnostics blob, and zero concepts.

The refusal was correct. The DIVERSION was the defect, and nothing in this estate could see it.
Every gate here enumerates its population from the declared planes, so meaning written somewhere
else is not merely un-checked — it is invisible. A blocked write that reappears as an unblocked
write one directory sideways has cost the work and lost the audit trail at the same time.

So two things were built together: the guard's refusal now FORBIDS writing the content elsewhere
instead of advertising a workaround, and this gate makes the diversion detectable rather than merely
discouraged. A rule stated only in a refusal message is a convention; a rule with a gate is a rule.

WHAT COUNTS AS A DIVERTED CONCEPT — deliberately narrow, because a false FAIL here would red every
bundle that ships an example. A YAML file is concept-shaped when it carries a top-level `concept:`
key AND at least one of the structural keys a MAC concept cannot be authored without (`grounding`,
`measures`, `dimensions`, `identity`, `grain`). One key alone is not enough: `concept: <name>` also
appears in transform descriptors and in prose fixtures.

WHAT IS DELIBERATELY EXEMPT, each with its reason:
  • the declared ontology plane itself (`planes.ontology`) — that is where concepts belong
  • `.git/`, `node_modules/`, `__pycache__/`, `.venv/`, `dist/`, `build/` — not authored content
  • any path under a `test`, `tests`, `fixture` or `fixtures` directory, and any `example*`
    directory — a gate that cannot tell a fixture from a diversion does not get a vote, and this
    framework's own self-tests seed concept-shaped YAML on purpose
  • `.harvest/` — the harvester's own scratch area, already excluded from every other population

Usage:  python3 tools/check_no_shadow_ontology.py <bundle-root>
        python3 tools/check_no_shadow_ontology.py --self-test
        exit 0 = no diverted meaning · 1 = at least one · 2 = could not run
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

EXIT_PASS, EXIT_FAIL, EXIT_COULD_NOT_RUN = 0, 1, 2

_STRUCTURAL = ("grounding", "measures", "dimensions", "identity", "grain")
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build", ".harvest",
              "test", "tests", "fixture", "fixtures", ".pytest_cache", ".mypy_cache", "site-packages"}


def _is_exempt(rel: Path, ontology_plane: str) -> bool:
    parts = rel.parts
    if parts and parts[0] == ontology_plane.strip("/").split("/")[0]:
        return True
    for p in parts[:-1]:
        if p in _SKIP_DIRS or p.lower().startswith("example"):
            return True
    return False


def concept_shaped(path: Path) -> bool:
    """A top-level `concept:` plus at least one structural key. Both halves are required."""
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return False
    if not isinstance(doc, dict) or "concept" not in doc:
        return False
    return any(k in doc for k in _STRUCTURAL)


def diverted(root: Path) -> tuple:
    """(findings, files_examined). The denominator is every candidate YAML, not every hit."""
    root = Path(root)
    plane = "ontology"
    manifest = root / "mac.project.yaml"
    if manifest.is_file() and yaml is not None:
        try:
            m = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
            plane = ((m.get("planes") or {}).get("ontology") or "ontology")
        except Exception:
            pass
    found, examined = [], 0
    for p in sorted(root.rglob("*.y*ml")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if _is_exempt(rel, plane):
            continue
        examined += 1
        if concept_shaped(p):
            found.append(str(rel))
    return found, examined


def _self_test() -> int:
    fails, n = [], 0

    def want(name, got, expect):
        nonlocal n
        n += 1
        if got != expect:
            fails.append(f"{name}: got {got!r}, want {expect!r}")

    concept = ("concept: order_line\ngrounding:\n  dataset: v_example_one\n"
               "measures:\n  - id: net\n")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        b = tmp / "alpha"
        (b / "ontology" / "concepts").mkdir(parents=True)
        (b / "mac.project.yaml").write_text(
            "spec_version: mac.container/1\nplanes:\n  data: data\n  ontology: ontology\n",
            encoding="utf-8")

        # CLEAN — a concept in its declared plane is where it belongs.
        (b / "ontology" / "concepts" / "order_line.yaml").write_text(concept, encoding="utf-8")
        want("a concept in the ontology plane is not a diversion", diverted(b)[0], [])

        # MUTANT 1 — the measured 10:09 failure: concepts written to a temp-shaped directory.
        (b / "tmp" / "concepts").mkdir(parents=True)
        (b / "tmp" / "concepts" / "order_line.yaml").write_text(concept, encoding="utf-8")
        want("a diverted concept is found", diverted(b)[0], ["tmp/concepts/order_line.yaml"])

        # MUTANT 2 — a diversion into the DATA plane, which is writable and therefore tempting.
        (b / "data" / "concepts").mkdir(parents=True)
        (b / "data" / "concepts" / "store.yaml").write_text(concept, encoding="utf-8")
        want("a diversion into the data plane is found", len(diverted(b)[0]), 2)

        # MUTANT 3 — a bundle whose ontology plane is declared elsewhere: the EXEMPTION must follow
        # the declaration, not a hardcoded directory name.
        c = tmp / "beta"
        (c / "meaning" / "concepts").mkdir(parents=True)
        (c / "mac.project.yaml").write_text(
            "spec_version: mac.container/1\nplanes:\n  data: data\n  ontology: meaning\n",
            encoding="utf-8")
        (c / "meaning" / "concepts" / "x.yaml").write_text(concept, encoding="utf-8")
        want("the exemption follows planes.ontology", diverted(c)[0], [])
        (c / "ontology").mkdir()
        (c / "ontology" / "x.yaml").write_text(concept, encoding="utf-8")
        want("a concept in a directory the manifest does NOT declare is a diversion",
             diverted(c)[0], ["ontology/x.yaml"])

        # FAIL-OPEN 1 — `concept:` alone is not concept-shaped. Transform descriptors carry it.
        d = tmp / "gamma"
        (d / "data" / "transforms").mkdir(parents=True)
        (d / "data" / "transforms" / "t.yaml").write_text(
            "concept: order_line\ntransform: v_example_one\n", encoding="utf-8")
        want("`concept:` alone is not a diversion", diverted(d)[0], [])

        # FAIL-OPEN 2 — fixtures and examples are exempt, or this gate reds the framework itself.
        for sub in ("tests", "fixtures", "example_shop_ontology"):
            (d / sub).mkdir(parents=True, exist_ok=True)
            (d / sub / "c.yaml").write_text(concept, encoding="utf-8")
        want("fixtures and examples are exempt", diverted(d)[0], [])

        # FAIL-OPEN 3 — an unparseable YAML must not brick the gate.
        (d / "broken.yaml").write_text("this: [is: not: yaml\n", encoding="utf-8")
        want("an unparseable yaml is not a diversion", diverted(d)[0], [])

        # The DENOMINATOR is real: the gate examined files rather than finding none to examine.
        want("the gate examined a non-zero population", diverted(b)[1] > 0, True)

    if fails:
        for f in fails:
            sys.stderr.write(f"  {f}\n")
        print(f"FAIL: check_no_shadow_ontology self-test — {len(fails)} of {n} assertions failed")
        return EXIT_FAIL
    print(f"PASS: check_no_shadow_ontology self-test — {n}/{n} assertions "
          f"(4 diversion mutants, 4 fail-open controls, 1 denominator)")
    return EXIT_PASS


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()
    if yaml is None:
        print("could not run: check_no_shadow_ontology — PyYAML is not importable")
        return EXIT_COULD_NOT_RUN
    if not a.root or not Path(a.root).is_dir():
        print(f"could not run: check_no_shadow_ontology — no such bundle root: {a.root}")
        return EXIT_COULD_NOT_RUN
    found, examined = diverted(Path(a.root))
    for f in found:
        print(f"  DIVERTED MEANING: {f}")
        print(f"      A concept authored outside the declared ontology plane is invisible to every")
        print(f"      gate in this framework. Move it into the ontology plane, or delete it — and if")
        print(f"      the ontology plane refused the write, the answer is to open the gate, not to")
        print(f"      write the meaning somewhere else.")
    if found:
        print(f"FAIL: check_no_shadow_ontology — {len(found)} of {examined} candidate YAML file(s) "
              f"outside the ontology plane are concept-shaped")
        return EXIT_FAIL
    print(f"PASS: check_no_shadow_ontology — 0 of {examined} candidate YAML file(s) outside the "
          f"ontology plane are concept-shaped")
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
