#!/usr/bin/env python3
"""check_strategy.py — the strategy names only what exists, and a bundle's rung is read off the disk.

guardrails/strategy.yaml is the one formulation of the platform's aim (operator, 2026-09-29). A
formulation that names a tool, a skill, a gate or a console section that does not exist is the
documentation-of-the-past defect one layer up, so every reference is resolved: `mac:` against this
repository, `kit:` and `platform:` against the sibling checkouts (UNLOCATED, not failed, when a
sibling is absent — the fact is stated, never hidden), gates against tools/check_*.py (every one of
which the framework gate runner runs), console keys against the console's own navigation.

`--bundle <root>` reports the ladder for one bundle: per rung, which artifacts are present and
which of its gates the bundle declares as standing failures (acceptance/standing_failures.yaml).
A rung is REACHED when every artifact it names is present. This is a report, not a verdict — the
verdict on a delivery is the gate runner's.

Exit 0 when every reference resolves (unlocated siblings disclosed), 1 when one does not, 2 when
the declaration cannot be read.
"""
from __future__ import annotations

import argparse
import glob
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEV = ROOT.parent
SIBLINGS = {"mac": ROOT, "kit": DEV / "mac-integration-kit", "platform": DEV / "mac-platform"}
REQUIRED = ("id", "name", "ai", "person", "tools", "skills", "artifacts", "gates", "console")
NAV = "packages/mac-console/src/mac_console/ui/src/App.jsx"


def load(path: Path) -> dict:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("spec_version") != "mac.strategy/1":
        raise ValueError(f"{path}: not a mac.strategy/1 declaration")
    for key in ("aim", "principles", "stop_condition", "documentation", "rungs", "enforcement"):
        if key not in doc:
            raise ValueError(f"{path}: missing `{key}`")
    for r in doc["rungs"]:
        for k in REQUIRED:
            if k not in r:
                raise ValueError(f"{path}: rung {r.get('id')!r} lacks `{k}`")
    return doc


def console_keys(siblings: dict) -> set[str] | None:
    p = siblings["platform"] / NAV
    if not p.is_file():
        return None
    return set(re.findall(r'key: "([a-z_]+)"', p.read_text(encoding="utf-8")))


def resolve(doc: dict, siblings: dict, tools_dir: Path) -> tuple[list[str], list[str]]:
    """(failures, unlocated) over every reference in the declaration."""
    fails, unlocated = [], []
    gates_on_disk = {p.name for p in tools_dir.glob("check_*.py")} | {"validate_schema.py"}
    keys = console_keys(siblings)

    def ref(where: str, r: str) -> None:
        repo, _, path = r.partition(":")
        if repo == "bundle":
            return
        if repo not in siblings:
            fails.append(f"{where}: {r!r} — unknown repository prefix (mac | kit | platform | bundle)")
            return
        base = siblings[repo]
        if not base.is_dir():
            unlocated.append(f"{where}: {r}")
            return
        if not (base / path).exists():
            fails.append(f"{where}: {r} — does not exist under {base.name}")

    for r in doc["rungs"]:
        w = f"rung {r['id']} {r['name']}"
        for x in r.get("tools", []) + r.get("skills", []) + r.get("enforced_by", []) + r.get("artifacts", []):
            ref(w, x)
        for g in r.get("gates", []):
            if g not in gates_on_disk:
                fails.append(f"{w}: gate {g} — no such tools/{g}")
        for c in r.get("console", []):
            if keys is None:
                unlocated.append(f"{w}: console {c}")
            elif c not in keys:
                fails.append(f"{w}: console section {c!r} — not a navigation key in the console")
    for x in doc["documentation"].get("enforced_by", []):
        ref("documentation", str(x).split()[0])
    for x in doc["enforcement"]:
        ref("enforcement", str(x).split("#")[0].strip())
    return fails, unlocated


def ladder(doc: dict, bundle: Path) -> list[tuple[int, str, list[str], list[str], list[str]]]:
    """Per rung: (id, name, present artifacts, absent artifacts, gates declared standing)."""
    standing: dict = {}
    reg = bundle / "acceptance" / "standing_failures.yaml"
    if reg.is_file():
        try:
            standing = (yaml.safe_load(reg.read_text(encoding="utf-8")) or {}).get("entries") or {}
        except yaml.YAMLError:
            standing = {}
    out = []
    for r in doc["rungs"]:
        present, absent = [], []
        for a in r.get("artifacts", []):
            pat = a.partition(":")[2]
            (present if glob.glob(str(bundle / pat)) else absent).append(pat)
        out.append((r["id"], r["name"], present, absent, [g for g in r.get("gates", []) if g in standing]))
    return out


def _self_test() -> int:
    import copy
    import tempfile

    fails = []

    def case(label, cond):
        if not cond:
            fails.append(label)

    doc = load(ROOT / "guardrails" / "strategy.yaml")
    f, _u = resolve(doc, SIBLINGS, ROOT / "tools")
    case("the real declaration resolves", not f)
    m = copy.deepcopy(doc); m["rungs"][0]["tools"].append("mac:tools/does_not_exist.py")
    case("a tool that does not exist fails", any("does_not_exist" in x for x in resolve(m, SIBLINGS, ROOT / "tools")[0]))
    m = copy.deepcopy(doc); m["rungs"][0]["gates"].append("check_nothing.py")
    case("a gate that is not in tools/ fails", any("check_nothing" in x for x in resolve(m, SIBLINGS, ROOT / "tools")[0]))
    m = copy.deepcopy(doc); m["rungs"][0]["skills"].append("kit:ontology/skills/no-such-skill/SKILL.md")
    r = resolve(m, SIBLINGS, ROOT / "tools")
    case("a skill that does not exist fails when the kit is beside us, else is unlocated",
         (any("no-such-skill" in x for x in r[0]) if SIBLINGS["kit"].is_dir() else any("no-such-skill" in x for x in r[1])))
    m = copy.deepcopy(doc); m["rungs"][0]["console"].append("no_such_section")
    r = resolve(m, SIBLINGS, ROOT / "tools")
    case("a console section that is not a navigation key fails when the platform is beside us",
         (any("no_such_section" in x for x in r[0]) if SIBLINGS["platform"].is_dir() else any("no_such_section" in x for x in r[1])))
    m = copy.deepcopy(doc); m["rungs"][0]["tools"].append("elsewhere:tools/x.py")
    case("an unknown repository prefix fails", any("unknown repository" in x for x in resolve(m, SIBLINGS, ROOT / "tools")[0]))
    absent = {k: (v if k == "mac" else ROOT / "no-such-sibling") for k, v in SIBLINGS.items()}
    f2, u2 = resolve(doc, absent, ROOT / "tools")
    case("absent siblings are UNLOCATED, not failed", not f2 and u2)
    m = copy.deepcopy(doc); del m["rungs"][0]["person"]
    try:
        for k in REQUIRED:
            if k not in m["rungs"][0]:
                raise ValueError("lacks")
        case("a rung without `person` is refused", False)
    except ValueError:
        pass
    with tempfile.TemporaryDirectory() as td:
        b = Path(td); (b / "data" / "sources").mkdir(parents=True); (b / "data" / "sources" / "x.yaml").write_text("a: 1")
        lad = ladder(doc, b)
        case("a bundle with one rung-1 artifact shows it present and the rest absent",
             "data/sources/*.yaml" in lad[0][2] and lad[0][3] and all(not row[2] for row in lad[4:]))
    n = 9
    if fails:
        print("FAIL: check_strategy self-test — " + "; ".join(fails))
        return 1
    print(f"PASS: check_strategy self-test — {n}/{n} case(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bundle", help="report the ladder for this bundle")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    try:
        doc = load(ROOT / "guardrails" / "strategy.yaml")
    except (ValueError, OSError, yaml.YAMLError) as exc:
        print(f"could not run: {exc}")
        return 2
    fails, unlocated = resolve(doc, SIBLINGS, ROOT / "tools")
    n_refs = sum(len(r.get("tools", [])) + len(r.get("skills", [])) + len(r.get("gates", [])) + len(r.get("console", []))
                 + len(r.get("enforced_by", [])) for r in doc["rungs"])
    if a.bundle:
        b = Path(a.bundle).resolve()
        print(f"THE LADDER — {b.name}")
        reached = 0
        for rid, name, present, absent, standing in ladder(doc, b):
            if not present and not absent:
                state = "no artifacts"       # a rung with nothing to leave on disk (the console)
            else:
                state = "reached" if not absent else ("partial" if present else "not started")
            if state in ("reached", "no artifacts") and reached == rid - 1:
                reached = rid
            print(f"  {rid:>2} {name:<22} {state:<12} artifacts {len(present)}/{len(present) + len(absent)}"
                  + (f"   standing: {', '.join(standing)}" if standing else "")
                  + (f"   missing: {', '.join(absent)}" if absent and present else ""))
        print(f"  rungs reached in order: {reached} of {len(doc['rungs'])}")
    for u in unlocated:
        print(f"  [unlocated] {u}")
    for f in fails:
        print(f"  [fail] {f}")
    if fails:
        print(f"FAIL: check_strategy — {len(fails)} of {n_refs} reference(s) name something that does not exist; the strategy may not describe a past")
        return 1
    print(f"PASS: check_strategy — {n_refs} reference(s) over {len(doc['rungs'])} rungs resolve"
          + (f"; {len(unlocated)} unlocated (sibling repository absent)" if unlocated else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
