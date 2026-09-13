#!/usr/bin/env python3
"""Every column a concept names must be a column of the relation it grounds on.

Nothing checked this, and five concepts had been wrong for as long as anyone can tell. They were
found the hard way: a generated test compiled into SQL and Athena answered COLUMN_NOT_FOUND.

    Brand      identity.canonical_key  brand_code                   relation has <source>_brand_code
    Market     identity.canonical_key  <source>_brand_country_code  relation has nothing resembling it
    SalesArea  grounding.key           <source>_group_country_code  relation has group_code
    Reach      identity.canonical_key  (none declared)
    SalesArea  identity.canonical_key  (none declared)

THE CAUSE IS NOT CARELESSNESS. The source is inconsistent about its `<source>_` prefix: v_<source>_kpi
spells it `brand_code` while dim_brand_country_code spells the same thing `<source>_brand_code`, and
v_<source>_kpi is inconsistent WITH ITSELF (`brand_code` unprefixed, `<source>_brand_country_code`
prefixed). A concept written against the fact's spelling and grounded on the dimension is wrong in a
way no reader would notice, because both names look right.

Which is exactly why it belongs in a gate rather than in anyone's attention. Offline: reads the
concept and the descriptor, touches no warehouse.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mac_diag as D          # noqa: E402
import mac_project as P       # noqa: E402


def columns_of(root: pathlib.Path, relation: str) -> set[str] | None:
    stem = relation.split(".")[-1]
    for d in ("datasets", "sources"):
        f = root / "data" / d / f"{stem}.yaml"
        if f.exists():
            return {str(c.get("name")) for c in
                    (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("columns") or []}
    return None


def nearest(have: set[str], want: str) -> str:
    tail = want.split("_")[-1]
    near = sorted(c for c in have if tail and tail in c)
    return ", ".join(near[:3]) or "nothing similar"


def scan(root: pathlib.Path) -> list[dict]:
    out = []
    # DISCOVERY GOES THROUGH THE LAYOUT RESOLVER — flat and foldered concepts, in whichever plane
    # the project declares (mac_project.concept_files).
    for f in P.concept_files(root):
        d = yaml.safe_load(pathlib.Path(f).read_text(encoding="utf-8")) or {}
        c = d.get("concept") or {}
        name = str(c.get("name") or pathlib.Path(f).stem)
        srcs = ((d.get("grounding") or {}).get("sources") or [])
        if not srcs:
            continue
        rel = str(srcs[0].get("relation") or "")
        have = columns_of(root, rel) if rel else None
        if not have:
            continue
        ident = (c.get("identity") or {}).get("canonical_key")
        if ident and ident not in have:
            out.append({"concept": name, "field": "identity.canonical_key", "relation": rel,
                        "names": str(ident), "nearest": nearest(have, str(ident))})
        for i, s in enumerate(srcs):
            r = str(s.get("relation") or "")
            h = columns_of(root, r) if r else None
            if not h:
                continue
            k = s.get("key")
            for col in ([k] if isinstance(k, str) else list(k or ())):
                if col not in h:
                    out.append({"concept": name, "field": f"grounding.sources[{i}].key",
                                "relation": r, "names": str(col), "nearest": nearest(h, str(col))})
            for col in (s.get("columns") or []):
                if col not in h:
                    out.append({"concept": name, "field": f"grounding.sources[{i}].columns",
                                "relation": r, "names": str(col), "nearest": nearest(h, str(col))})
    return out


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# SELF-TEST FIXTURES — the subject this gate's own rule needs, and a mutant per reject class
# ══════════════════════════════════════════════════════════════════════════════════════════════════
# WHAT WAS WRONG WITH 5/5, MEASURED 2026-09-13.
# `mac_project.selftest_discovery` seeds a concept and no descriptor. `columns_of()` then returns
# None, `scan()` does `if not have: continue`, and this gate printed
#
#     ✓ OK — every column named by 1 concept(s) exists on the relation it grounds on
#
# having checked ZERO columns. Three clean layout fixtures scored three ticks for a rule with an
# empty population, and nothing in the suite could tell that green apart from a real one.
#
# THE FIX IS TWO PIECES, and neither touches anything that judges a real bundle:
#   `_subject`  gives the rule a population — the descriptor the seeded concept grounds on. With it,
#               the clean fixtures check 1 concept against 2 real columns and the harness raises the
#               bar on them from "did not refuse" to "exited 0".
#   `_MUTANTS`  one per reject class this gate can attribute, named by the FIELD it prints. Each
#               must exit 1 (a finding, not a refusal) AND print its own field name, which is what
#               turns "something was rejected" into "this class was rejected" — the difference
#               between these gates and the three fully attributed sdk ones.
_REL = "widget_register"        # the relation mac_project's shared _CONCEPT_DOC grounds on
_DESCRIPTOR = """relation: widget_register
columns:
  - name: widget_code
  - name: widget_name
"""


def _subject(root) -> None:
    """Seed the descriptor the fixture concept grounds on, so this gate's rule has a subject.

    `columns_of` looks in data/datasets/ then data/sources/, by relation stem, in BOTH layouts —
    it does not go through the plane resolver — so one path serves every fixture case."""
    d = pathlib.Path(root) / "data" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{_REL}.yaml").write_text(_DESCRIPTOR, encoding="utf-8")


def _concept_text(root, replace: tuple[str, str]) -> None:
    f = pathlib.Path(P.concept_files(root)[0])
    old, new = replace
    text = f.read_text(encoding="utf-8")
    assert old in text, f"fixture drift: {old!r} is no longer in the shared concept doc"
    f.write_text(text.replace(old, new), encoding="utf-8")


# (name, mutate, marker that must appear in the output, what it proves)
_MUTANTS = (
    ("identity-key-missing",
     lambda r: _concept_text(r, ("canonical_key: widget_code", "canonical_key: widget_id")),
     "identity.canonical_key",
     "the concept's canonical key names a column the relation does not have (Brand/Market, "
     "the prefix disagreement this gate was built for)"),
    ("grounding-key-missing",
     lambda r: _concept_text(r, ("\n      key: widget_code", "\n      key: widget_id")),
     "grounding.sources[0].key",
     "the grounding key names a column the relation does not have (SalesArea.grounding.key)"),
    ("grounding-column-missing",
     lambda r: _concept_text(r, ("columns: [widget_code, widget_name]",
                                 "columns: [widget_code, widget_name, widget_colour]")),
     "grounding.sources[0].columns",
     "a projected column is not on the relation — the class a COLUMN_NOT_FOUND from Athena is"),
)


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return P.selftest_discovery(__file__, subject=_subject, mutants=_MUTANTS)
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = pathlib.Path(a.root).resolve()
    # ZERO IS NOT A SCORE. "every column named by 0 concept(s) exists" was this gate's verdict on
    # every foldered bundle — a sentence that is true of any directory on earth.
    n = len(P.concept_files(root))
    found = scan(root) if n else []
    if a.json:
        print(json.dumps({"findings": found, "concepts": n, "measured_nothing": not n},
                         indent=1, ensure_ascii=False))
        return D.EMPTY_EXIT if not n else (1 if found else 0)
    if not n:
        return D.refuse_empty("check_concept_columns_exist", P.concepts_dir(root))
    for x in found:
        print(f"  [ERROR] {x['concept']}.{x['field']}")
        print(f"          names {x['names']!r}, which {x['relation']} does not have")
        print(f"          nearest: {x['nearest']}")
    if found:
        print(f"\n✗ {len(found)} concept field(s) name a column their relation does not have.")
        pref = []
        for x in found:
            near = (x["nearest"].split(",")[0].strip() if x["nearest"] else "")
            if near and (x["names"].endswith(near) or near.endswith(x["names"])):
                pref.append((x["names"], near))
        if pref:
            print("  Most are a PREFIX disagreement between relations — the same thing spelled two")
            print("  ways, so both look right and only a machine notices which one is carried:")
            for a_, b_ in pref[:3]:
                print(f"     {a_}  vs  {b_}")
        return 1
    print(f"✓ OK — every column named by {n} concept(s) exists on the relation it grounds on")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
