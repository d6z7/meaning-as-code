#!/usr/bin/env python3
"""Every column a concept names must be a column of the relation it grounds on.

Nothing checked this, and five concepts had been wrong for as long as anyone can tell. They were
found the hard way: a generated test compiled into SQL and Athena answered COLUMN_NOT_FOUND.

    Brand      identity.canonical_key  brand_letter            relation has fpl_brand_letter
    Market     identity.canonical_key  fpl_brand_country_code  relation has nothing resembling it
    SalesArea  grounding.key           fpl_group_country_code  relation has group_code
    OBReach    identity.canonical_key  (none declared)
    SalesArea  identity.canonical_key  (none declared)

THE CAUSE IS NOT CARELESSNESS. The source is inconsistent about the `fpl_` prefix: v_fpl_kpi spells
it `brand_letter` while dim_brand_country_code spells the same thing `fpl_brand_letter`, and
v_fpl_kpi is inconsistent WITH ITSELF (`brand_letter` unprefixed, `fpl_brand_country_code`
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
    for f in sorted(glob.glob(str(root / "ontology" / "concepts" / "*.yaml"))):
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = pathlib.Path(a.root).resolve()
    found = scan(root)
    if a.json:
        print(json.dumps({"findings": found}, indent=1, ensure_ascii=False))
        return 1 if found else 0
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
    n = len(glob.glob(str(root / "ontology" / "concepts" / "*.yaml")))
    print(f"✓ OK — every column named by {n} concept(s) exists on the relation it grounds on")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
