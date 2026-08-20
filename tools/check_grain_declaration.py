#!/usr/bin/env python3
"""MAC008 — the cell key DECLARATION must be well-formed, complete, and honest about its evidence.

`x-grain.cell_key` states the columns at which exactly one row of a fact relation exists. Five tools,
eight canon bindings and every generated concept view now read it. Its declaration in
mac.project.yaml#profile.extensions buys one thing only — silence from MAC009's undeclared-extension
check — and constrains nothing:

  · no shape        cell_key could be a string, a number, or []
  · not required    a fact relation carrying none violates nothing
  · no column tie   nothing required it to name columns the relation actually has
  · "VERIFIED"      the descriptions SAY they were checked against Athena; that is prose

All four holes produced real defects before this existed. fpl_ob_reach_kpi declared
`excludes_vintage: true` and put the reporting cycle INSIDE its own key, so a collapse partitioned on
it would separate every cycle into its own group and collapse nothing at all — caught only when
protosql_render refused to render it. v_fpl_kpi.yaml still carries "VERIFIED 2026-08-16: 12.345.098
cells, 0 multi-row" while the data now says 944.308 figures are multi-row: the word VERIFIED is a
sentence, not a test, and it went stale the moment a second business status arrived.

WHAT THIS ENFORCES, all offline:
  1. SHAPE            cell_key is a non-empty list of unique, non-blank column names
  2. COLUMNS EXIST    every name appears in the dataset's own columns[]
  3. VINTAGE          excludes_vintage: true is CONSISTENT — the key holds no republication column
  4. REQUIRED         a relation any measure concept grounds on must declare one
  5. EVIDENCE         a description claiming VERIFIED must carry a date, and a claim older than the
                      last edit to the key is a stale claim, not evidence

(5) is the interesting one: it cannot prove the key is right — only a warehouse sweep does that, which
is what S-GRAIN is for. What it CAN prove is that the claim has not outlived the thing it describes.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys

import yaml

# Columns that identify WHEN a figure was published rather than WHICH figure it is. A key containing
# one of these makes every republication its own group, so the collapse collapses nothing.
CYCLE_HINTS = ("reporting_month", "reporting_cycle", "config_key", "vintage", "snapshot",
               "created_at", "loaded_at", "ingested_at")


def _git(root: str, *a: str) -> str:
    try:
        return subprocess.run(["git", "-C", root, *a], capture_output=True, text=True,
                              timeout=20).stdout.strip()
    except Exception:
        return ""


def check(root: str) -> list[dict]:
    out: list[dict] = []

    def bad(sev, where, msg, fix):
        out.append({"severity": sev, "where": where, "msg": msg, "fix": fix})

    # which relations a measure concept grounds on — those MUST declare a key
    needed: dict[str, str] = {}
    for f in sorted(glob.glob(os.path.join(root, "ontology", "concepts", "*.yaml"))):
        d = yaml.safe_load(open(f, encoding="utf-8")) or {}
        if ((d.get("concept") or {}).get("class")) != "measure":
            continue
        for s in ((d.get("grounding") or {}).get("sources") or []):
            rel = str(s.get("relation") or "")
            if rel:
                needed.setdefault(rel.split(".")[-1], os.path.basename(f)[:-5])

    seen = set()
    for f in sorted(glob.glob(os.path.join(root, "data", "datasets", "*.yaml"))):
        doc = yaml.safe_load(open(f, encoding="utf-8")) or {}
        rel = os.path.relpath(f, root)
        stem = os.path.basename(f)[:-5]
        seen.add(stem)
        grain = doc.get("x-grain")
        cols = {c.get("name") for c in (doc.get("columns") or []) if isinstance(c, dict)}

        if grain is None:
            if stem in needed:
                bad("ERROR", rel,
                    f"no x-grain.cell_key, but concept:{needed[stem]} grounds a MEASURE on it",
                    "declare the columns at which exactly one row exists, and verify them")
            continue

        if not isinstance(grain, dict):
            bad("ERROR", rel, "x-grain is not a mapping", "it must carry cell_key")
            continue

        key = grain.get("cell_key")
        # 1. SHAPE
        if not isinstance(key, list) or not key:
            bad("ERROR", f"{rel}#x-grain.cell_key",
                f"is {type(key).__name__}, not a non-empty list", "give it the column tuple")
            continue
        if any(not isinstance(c, str) or not c.strip() for c in key):
            bad("ERROR", f"{rel}#x-grain.cell_key", "holds a non-string or blank entry",
                "every entry is a column name")
        dupes = sorted({c for c in key if key.count(c) > 1})
        if dupes:
            bad("ERROR", f"{rel}#x-grain.cell_key", f"repeats {dupes}",
                "a column cannot identify a figure twice")

        # 2. COLUMNS EXIST
        if cols:
            missing = [c for c in key if c not in cols]
            if missing:
                bad("ERROR", f"{rel}#x-grain.cell_key",
                    f"names {missing}, which the relation does not have",
                    "a key over columns that do not exist partitions nothing")

        # 3. VINTAGE CONSISTENCY
        cyc = [c for c in key if any(h in str(c).lower() for h in CYCLE_HINTS)]
        if cyc:
            sev = "ERROR" if grain.get("excludes_vintage") else "WARNING"
            bad(sev, f"{rel}#x-grain.cell_key",
                f"contains {cyc} — a column identifying WHEN the figure was published"
                + (" while excludes_vintage says it does not" if grain.get("excludes_vintage") else ""),
                "partition on it and every republication becomes its own group, so nothing collapses")

        # 5. EVIDENCE NOT STALE
        note = str(grain.get("note") or "") + " " + str(grain.get("description") or "")
        if re.search(r"\bVERIFIED\b", note, re.I):
            m = re.search(r"(20\d\d-\d\d-\d\d)", note)
            if not m:
                bad("WARNING", f"{rel}#x-grain",
                    "claims VERIFIED with no date", "an undated claim cannot be shown to be current")
            else:
                claimed = m.group(1)
                last = _git(root, "log", "-1", "--format=%cs", "--", rel)
                if last and last > claimed:
                    bad("WARNING", f"{rel}#x-grain",
                        f"claims VERIFIED {claimed} but the descriptor was edited {last}",
                        "re-verify against the warehouse, or drop the claim — a claim that has "
                        "outlived the thing it describes is not evidence")

    for stem, concept in sorted(needed.items()):
        if stem not in seen:
            bad("ERROR", f"data/datasets/{stem}.yaml",
                f"concept:{concept} grounds a measure on it and no descriptor exists",
                "every relation the ontology reads must be described")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    f = check(a.root)
    if a.json:
        print(json.dumps({"findings": f}, indent=1, ensure_ascii=False))
        return 1 if any(x["severity"] == "ERROR" for x in f) else 0

    for x in f:
        print(f"  [{x['severity']:<7}] {x['where']}")
        print(f"            {x['msg']}")
        print(f"            {x['fix']}")
    errs = sum(1 for x in f if x["severity"] == "ERROR")
    warns = len(f) - errs
    if errs:
        print(f"\n✗ {errs} malformed cell-key declaration(s) ({warns} warning(s)) — five tools, eight "
              f"canon bindings and every generated view read this")
        return 1
    print(f"✓ OK — every declared cell key is well-formed and complete ({warns} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
