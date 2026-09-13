#!/usr/bin/env python3
"""Fill `validates` and `test_kind` on a property suite — by DERIVATION, and never by guess.

Both fields became required and 59 properties across four <dataset> suites stood without them, which is
126 of the bundle's validator errors from one cause. The temptation is to write them in by hand, 59
times. That is how the interventions ledger acquired 65 defects in a single day, twelve of which
asserted the operator's approval in a closed-vocabulary field.

── `validates` IS DERIVABLE, so it is derived ──────────────────────────────────────────────────
It names the CONCEPTS a property holds to account. A property's SQL names relations; the ontology
declares which concepts ground on each relation. So the attribution is a join, not a judgement, and
a property validating nothing is a legal and useful answer — a warehouse invariant no concept
depends on is worth knowing about.

── `test_kind` IS DERIVABLE ONLY IN PART, so the rest is REPORTED ──────────────────────────────
The two kinds have opposite obligations and a property that is both can be trusted for neither:

    conformance   every asserted value is RENDERED from a declaration at run time.
                  A typed literal IS the defect.
    ground_truth  measures the world, and must NOT be generated from the declaration's own claims,
                  because its whole purpose is to DISAGREE when the declaration has gone stale.

Two signals decide it mechanically:
    the SQL renders a declaration (`@cols:` / `@n:` substitution)   -> conformance
    the assertion is `must_be_zero`                                 -> ground_truth, because a
                                                                      zero-count carries no literal
                                                                      that could come from anywhere
An assertion carrying a LITERAL — equals, min_value, max_value — is decided by where that literal
came from, and nothing in the file records that. Those are printed, not filled. Filling them would
be inventing the one fact the field exists to state.
"""
from __future__ import annotations

import argparse
import collections
import glob
import os
import pathlib
import re
import sys

import yaml

RENDERED = re.compile(r"@(?:cols|n):")
LITERAL_ASSERTIONS = ("equals", "min_value", "max_value")


def relation_concepts(root: pathlib.Path) -> dict[str, set[str]]:
    """relation stem -> the concepts grounding on it. The join `validates` is derived from."""
    out: dict[str, set[str]] = collections.defaultdict(set)
    for f in glob.glob(str(root / "ontology" / "concepts" / "*.yaml")):
        d = yaml.safe_load(open(f, encoding="utf-8")) or {}
        name = ((d.get("concept") or {}).get("name"))
        if not name:
            continue
        for s in ((d.get("grounding") or {}).get("sources") or []):
            rel = str(s.get("relation") or "")
            if rel:
                out[rel.split(".")[-1]].add(str(name))
    return out


def relations_in(sql: str, known: set[str]) -> list[str]:
    """Which known relations this SQL touches. Substring-free: matched on word boundaries only, so
    `dim_model` does not also claim `dim_model_code`."""
    return sorted(r for r in known if re.search(rf"\b{re.escape(r)}\b", sql))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--apply", action="store_true", help="without this it only reports")
    a = ap.parse_args()
    root = pathlib.Path(a.root).resolve()
    r2c = relation_concepts(root)
    known = set(r2c) | {os.path.basename(f)[:-5]
                        for f in glob.glob(str(root / "data" / "datasets" / "*.yaml"))}

    filled_v = filled_k = 0
    undecided: list[tuple[str, str, str, str]] = []
    for f in sorted(glob.glob(str(root / "acceptance" / "*.yaml"))):
        doc = yaml.safe_load(open(f, encoding="utf-8"))
        if not isinstance(doc, dict) or not doc.get("properties"):
            continue
        touched = False
        for p in doc["properties"]:
            if not isinstance(p, dict):
                continue
            sql = str(p.get("sql") or "")
            if "validates" not in p:
                rels = relations_in(sql, known)
                concepts = sorted({c for r in rels for c in r2c.get(r, ())})
                p["validates"] = concepts
                filled_v += 1
                touched = True
            if "test_kind" not in p:
                atype = (p.get("assertion") or {}).get("type")
                if RENDERED.search(sql):
                    p["test_kind"] = "mac.test_kind.conformance"
                elif atype == "must_be_zero":
                    p["test_kind"] = "mac.test_kind.ground_truth"
                else:
                    undecided.append((os.path.basename(f), str(p.get("id")), str(atype),
                                      str((p.get("assertion") or {}).get("expect") or
                                          (p.get("assertion") or {}).get("value") or "")[:40]))
                    continue
                filled_k += 1
                touched = True
        if touched and a.apply:
            pathlib.Path(f).write_text(
                yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")

    print(f"  validates  derived for {filled_v} propert(ies) from the grounding join")
    print(f"  test_kind  derived for {filled_k} propert(ies) mechanically")
    if undecided:
        print(f"\n  {len(undecided)} carry a LITERAL, and where it came from is not recorded anywhere.")
        print(f"  NOT filled — that is the one fact the field exists to state:\n")
        print(f"     {'suite':<20}{'property':<22}{'assertion':<12}expected")
        for f, pid, atype, exp in undecided:
            print(f"     {f:<20}{pid:<22}{atype:<12}{exp}")
    if not a.apply:
        print("\n  (report only — pass --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
