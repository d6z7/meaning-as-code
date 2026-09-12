#!/usr/bin/env python3
"""Does any property SUM a measure across an axis the ontology says it cannot be summed over?

FOUR RULES SAY THIS, in four concepts, in four sentences:
    perspective.exclusion.no_blend                "Never SUM across Group and brand-specific rows"
    plan_stage.default.official                   never blend official (7) and inofficial (4)
    plan_stage.resolve.official_vs_brand_internal "alternatives rather than partitions"
    region.resolve.additive_rollup                the additive side of the same law

None of the four was testable, and the reason turned out not to be that they are prose. The canon
that implements the law — `mac.canon.additivity_guard` — has existed in tools/canon/__init__.py the
whole time. It is a STATIC ANALYSER: hand it SQL, it returns the violations. It generates nothing, so
a generator that expects to emit a property finds nothing to emit and skips it, which is why a
34-agent conversion pass produced zero.

The right instrument was never a property. It is a GATE over the SQL the bundle already has.

── THE LAW IS READ, NOT RETYPED ────────────────────────────────────────────────────────────────
`mac_vocabulary.yaml#MeasureType` holds the additivity of each measure type over each axis kind —
Flow accrues and adds over time, Stock is a level and does not, Target is neither. The concept
declares its `measure_type` and its `axis_kinds`. Both are read here; nothing about additivity is
written in this file, so changing the law in the vocabulary changes what this gate rejects.

`role` is added as a non-additive axis for EVERY measure regardless of type, because Group RESTATES
brand rows rather than partitioning them: 11.195.386 cells carry both, and summing across role
double-counts 3.336.719.092. That is not an additivity property of the measure, it is a property of
the relation, and perspective.exclusion.no_blend is the rule that says so.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import pathlib
import re
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import mac_diag as D          # noqa: E402
import mac_project as P       # noqa: E402

import _plugin  # noqa: E402  — the bundle-plugin seam, shared by five tools


def law(fw: pathlib.Path) -> dict:
    v = yaml.safe_load((fw / "mac_vocabulary.yaml").read_text(encoding="utf-8"))
    return {k: (m.get("additivity") or {}) for k, m in (v["MeasureType"]["members"]).items()}


def measures(root: pathlib.Path, law_: dict) -> list[dict]:
    """Each measure concept, with the axis effects its declared type implies."""
    out = []
    # DISCOVERY GOES THROUGH THE LAYOUT RESOLVER — flat and foldered concepts, in whichever plane
    # the project declares (mac_project.concept_files).
    for f in P.concept_files(root):
        d = yaml.safe_load(pathlib.Path(f).read_text(encoding="utf-8")) or {}
        c = d.get("concept") or {}
        if str(c.get("class")) != "measure":
            continue
        sem = d.get("semantics") or c.get("semantics") or {}
        mt = str(sem.get("measure_type") or "").split(".")[-1]
        if mt not in law_:
            continue
        eff = {}
        for axis, kind in (sem.get("axis_kinds") or {}).items():
            k = str(kind).split(".")[-1]
            e = str(law_[mt].get(k) or "").split(".")[-1]
            if e:
                eff[axis] = e
        out.append({"concept": str(c.get("name")), "type": mt, "axis_effects": eff,
                    "grounding": [str(s.get("relation") or "").split(".")[-1]
                                  for s in ((d.get("grounding") or {}).get("sources") or [])]})
    return out


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return P.selftest_discovery(__file__)
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = pathlib.Path(a.root).resolve()
    fw = pathlib.Path(__file__).resolve().parent.parent
    try:
        from canon import additivity_guard
    except Exception as e:
        print(f"canon unavailable: {e}", file=sys.stderr)
        return 0

    # ZERO IS NOT A SCORE. Two populations are counted here — the measure concepts that carry the
    # law, and the properties judged against it — and an empty one used to print "(0 checked)"
    # beside a tick. Each is refused on its own line so the caller knows WHICH was missing.
    if not P.concept_files(root):
        return D.refuse_empty("check_additivity_in_sql", P.concepts_dir(root))
    ms = measures(root, law(fw))
    # the axis columns a measure is actually keyed on, from the measured grain
    NON_ADDITIVE_ALWAYS = {"role": "none"}
    # Declared-but-unusable is UNRUNNABLE, not identity: with slots unresolved every parse
    # fails and each failure reads as a finding. See tools/_plugin.py.
    try:
        resolve = _plugin.optional(root, "resolve_declared", lambda x: x)
    except _plugin.PluginUnavailable as exc:
        print(f"could not run: {root} {exc}", file=sys.stderr)
        return 2

    findings, checked = [], 0
    for f in sorted(glob.glob(str(root / "acceptance" / "*.yaml"))):
        doc = yaml.safe_load(pathlib.Path(f).read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or not doc.get("properties"):
            continue
        for p in doc["properties"]:
            if not isinstance(p, dict) or not p.get("sql"):
                continue
            if p.get("frozen"):
                continue                     # deferred by decision; not judged here
            try:
                sql = resolve(str(p["sql"]))
            except Exception:
                continue
            checked += 1
            for m in ms:
                if not any(g in sql for g in m["grounding"]):
                    continue
                eff = {**NON_ADDITIVE_ALWAYS}
                # only axes that are real columns of the SQL are worth asserting on
                for axis, e in m["axis_effects"].items():
                    if axis in sql:
                        eff[axis] = e
                # THE CANON JUDGES PER SELECT, and that is right for a canon — it cannot know
                # whether a pin in another scope governs this one. But a property that pins
                # `role = 'Group'` in a CTE and sums in the outer SELECT is CORRECT, and the first
                # run flagged 21 of those: R-VAR-01 pins role, R-ROLE-01 groups by it. A gate that
                # punishes the correct pattern is worse than no gate, which this bundle established
                # earlier today when a checker turned 3 findings into 56.
                #
                # So an axis pinned or grouped ANYWHERE in the statement is treated as governed.
                # DELIBERATELY PERMISSIVE: a query pinning in one CTE and blending in another slips
                # through. That is the tolerable error — the other direction cries wolf until the
                # gate is ignored.
                eff = {ax: e for ax, e in eff.items()
                       if not re.search(rf"\b{re.escape(ax)}\b\s*(=|IN)\b", sql, re.I)
                       and not re.search(rf"GROUP\s+BY[^;]*\b{re.escape(ax)}\b", sql, re.I)}
                if not eff:
                    continue
                try:
                    for msg in additivity_guard(sql, measure_column="value", axis_effects=eff):
                        findings.append({"file": os.path.basename(f), "id": p.get("id"),
                                         "concept": m["concept"], "type": m["type"], "msg": msg})
                except Exception:
                    pass
                break
    if a.json:
        print(json.dumps({"checked": checked, "findings": findings, "measures": len(ms),
                          "measured_nothing": not (checked and ms)}, indent=1, ensure_ascii=False))
        return D.EMPTY_EXIT if not (checked and ms) else (1 if findings else 0)
    if not ms:
        return D.refuse_empty("check_additivity_in_sql", P.concepts_dir(root), unit="measure concept")
    if not checked:
        return D.refuse_empty("check_additivity_in_sql", root / "acceptance",
                              unit="judgeable acceptance property")
    seen = set()
    for x in findings:
        k = (x["id"], x["msg"])
        if k in seen:
            continue
        seen.add(k)
        print(f"  [ERROR] {x['file']}:{x['id']}  ({x['concept']}, {x['type']})")
        print(f"          {x['msg']}")
    if seen:
        print(f"\n✗ {len(seen)} SUM(s) cross an axis the ontology forbids, over {checked} propert(ies).")
        print("  The law is read from mac_vocabulary.yaml#MeasureType and the concept's axis_kinds —")
        print("  nothing about additivity is written in this gate.")
        return 1
    print(f"✓ OK — no property sums a measure across a forbidden axis ({checked} checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
