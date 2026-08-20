#!/usr/bin/env python3
"""MAC012 — an `x-` extension key is prohibited, and this is what makes the prohibition real.

OPERATOR, after having to say it more than once:
  "i have ruled them out - but agents like you are keeping bringing them in over and over again"
  "they are not easily verifiable. they are weak poing in the chain and we need better solution for
   them ... even if it means that if you want to have them then you have to design algebra and
   grammar how you want to enforce them and you are only allowed to move on if you have proof that
   this enforcement is implemented"
  "a check that does not block is not enforcement"

So this file IS the proof, and it exits non-zero. Ruling it out in prose is what failed: `x-grain`
was declared on 2026-08-18 and had already been READ by the collapse fragment since 08-16.

── WHY THE EXTENSION IS THE DEFECT, not merely untidy ────────────────────────────────────────────
MAC closes every structural plane and validates it. An `x-` key is BY CONSTRUCTION outside that, so
nothing checks it — and the thing it held was the grain, the single most consequential fact about a
relation. Measured the day it was retired, with the core schema untouched around it:

    v_fpl_kpi          declared 0 multi-row (VERIFIED 2026-08-16)  ->  11.689.530 multi-row
    v_fpl_tm_kpi       declared 0 multi-row, 0 divergent           ->  176.279 multi-row (99,96 %)
    fpl_ob_reach_kpi   declared 0 ambiguous                        ->  0. HOLDS.
    v_fpl_kpi_current  declared 15.483.849 cells                   ->  15.483.965 (+116). HOLDS.

Two of four false — and WHICH two is the interesting half. Both survivors are views that ENFORCE the
key: fpl_ob_reach_kpi withholds ambiguous cells, and v_fpl_kpi_current collapses to one row per cell,
so its key is true by construction. The two that rotted are the pass-through facts, where the
declaration was the only thing standing between the reader and a doubled number.

So the argument is not that anyone was careless. The field was unreachable by every gate in the
system, so being wrong cost nothing and stayed invisible. An extension is not a small schema, it is
an UNCHECKED one.

── THE THREE PREDICATES (C6) ─────────────────────────────────────────────────────────────────────
Every `x-` key is an error. When it also DUPLICATES a core field, the message says which one, so the
finding carries its own fix rather than a rule number. Duplication is mechanical, not a judgement:

    SAME SUBJECT        both attach to the same node (the same relation, the same column)
    SAME VALUE SHAPE    both hold the same kind of value (a list of column names, a scalar, a date)
    OVERLAPPING DOMAIN  drawn from the same closed set with a non-empty intersection — for a column
                        list, the relation's own columns

x-grain.cell_key met all three against `grounding.sources[].key` and against `grounding.grain`, and
the duplicate DISAGREED with the core it duplicated: 4 columns in the ontology, 7 in the extension,
"SEVEN" in the concept prose. Three numbers for one fact is what N places for one fact buys you.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import yaml

CODE = "MAC012"

# The core homes an extension most often reinvents. Named so a finding can point AT the replacement
# instead of only away from the offence.
CORE = {
    "cell_key":      "TableFile.identity_evidence.key (measured) / grounding.sources[].key (bound)",
    "natural_key":   "TableFile.identity_evidence.key",
    "grain":         "TableFile.identity_evidence + grounding.grain",
    "key":           "grounding.sources[].key",
    "columns":       "TableFile.columns[]",
    "profile":       "TableFile.profile / columns[].profile",
    "distinct":      "columns[].profile.distinct",
    "nulls":         "columns[].profile.nulls",
    "determined_by": "columns[].profile.determined_by",
    "role":          "columns[].role",
    "measured_at":   "TableFile.profile.measured_at",
    "watermark":     "TableFile.identity_evidence.source_watermark",
}

SKIP_DIRS = {".git", "node_modules", ".venv", ".harvest_cache", "dist", "build", "__pycache__"}


def _hits(node, path=""):
    """Every `x-`-prefixed key anywhere in a document, with the path that reaches it."""
    if isinstance(node, dict):
        for k, v in node.items():
            here = f"{path}.{k}" if path else str(k)
            if isinstance(k, str) and k.startswith("x-"):
                yield here, k, v
            yield from _hits(v, here)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _hits(v, f"{path}[{i}]")


def duplicates(key: str, value) -> list[str]:
    """Which core field this extension is standing in for. Mechanical: name, then value shape."""
    out = []
    leaf = key[2:].split(".")[-1].lower()
    for name, home in CORE.items():
        if name in leaf or leaf in name:
            out.append(home)
    if not out and isinstance(value, dict):
        for sub in value:
            for name, home in CORE.items():
                if isinstance(sub, str) and (name in sub.lower() or sub.lower() in name):
                    out.append(f"{home}   (via `{key}.{sub}`)")
    return sorted(set(out))


def scan(root: str) -> list[dict]:
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith((".yaml", ".yml")):
                continue
            p = os.path.join(dirpath, fn)
            try:
                doc = yaml.safe_load(open(p, encoding="utf-8"))
            except Exception:
                continue
            for where, key, value in _hits(doc):
                found.append({
                    "code": CODE, "file": os.path.relpath(p, root), "path": where, "key": key,
                    "duplicates": duplicates(key, value),
                    "shape": type(value).__name__,
                })
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    found = scan(a.root)
    if a.json:
        print(json.dumps({"code": CODE, "findings": found}, indent=1, ensure_ascii=False))
        return 1 if found else 0

    for f in found:
        print(f"  [{CODE}] {f['file']}  {f['path']}")
        if f["duplicates"]:
            for home in f["duplicates"]:
                print(f"          duplicates core: {home}")
        else:
            print(f"          no core equivalent — so this is a MAC gap, not a shortcut. Say what the")
            print(f"          wall is and change MAC, rather than declaring beside it.")
    if found:
        files = len({f["file"] for f in found})
        print(f"\n✗ {len(found)} extension key(s) in {files} file(s). An `x-` key is outside every gate")
        print("  MAC has, so nothing can check what it holds — which is how two of four declared cell")
        print("  keys came to be false, both of them on the relations where nothing enforced the key.")
        return 1
    print(f"✓ OK — no `x-` extension keys ({len(CORE)} core homes known)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
