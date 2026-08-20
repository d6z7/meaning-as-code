#!/usr/bin/env python3
"""P6 — a concept INHERITS its key from the relation's measured grain instead of declaring one.

Operator: *"you told me before that ontology concepts can inherit keys from datasets … if the last
is correct (not inherited) then we need mechanism to precisely determine # of keys."*

Both statements reconcile, and the reconciliation IS the mechanism. A concept's key is not a copy of
the relation's grain — it is derived from it:

    concept key  =  measured grain
                    − columns the concept PINS to a constant (its own identity code)
                    with any column substitutable by one that FUNCTIONALLY DETERMINES it

Every term is measured, not assumed: the grain by mac_admit_identity, the substitutions by the same
tool's dependence probe, the pin by the concept's own `identity.canonical_key`.

WHY IT MATTERS RIGHT NOW. DtC declares [fpl_brand_country_code, fpl_model_code, fpl_date, kpi]
against a measured grain of six. The first two are the same axes in a different ENCODING —
`fpl_model_code` is determined by `fpl_model_code_id`, measured — so they are not errors. But `role`
and `config_data_status` are absent outright, and a SUM over a key missing them counts the Group
restatement and the second expectation round as separate figures. Nine measure concepts carry that.

WHAT THIS TOOL WILL NOT DECIDE. Whether a PINNED column should leave the key. DtC identifies itself
by `kpi` and pins it to its own code, so `kpi` is arguably the concept's identity rather than part of
the figure's key inside it. That is a modelling ruling, not a measurement, and it is reported.
"""
from __future__ import annotations

import argparse
import glob
import pathlib
import sys

import yaml


def measured(root: pathlib.Path, rel: str) -> tuple[list[str], dict[str, list[str]]]:
    """(grain, determined_by) for a relation, from the measurement plane."""
    f = root / "data" / "profiles" / f"{rel.split('.')[-1]}.yaml"
    if not f.exists():
        return [], {}
    d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    grain = list((d.get("identity_evidence") or {}).get("key") or [])
    det: dict[str, list[str]] = {}
    for c in d.get("columns") or []:
        if c.get("determined_by"):
            det[str(c["name"])] = list(c["determined_by"])
    return grain, det


def substitutable(a: str, b: str, det: dict[str, list[str]]) -> bool:
    """a and b name the same axis when one functionally determines the other. MEASURED."""
    return b in det.get(a, ()) or a in det.get(b, ())


def derive(concept: dict, grain: list[str], det: dict[str, list[str]], declared: list[str]):
    """Return (derived_key, missing, pinned). ADDITIVE ONLY — a declared column is never dropped.

    The first cut rebuilt the key FROM the grain and let anything unmatched fall out. It would have
    deleted `fpl_brand_country_code` from six measure concepts on the grounds that the grain names
    `market` instead — but those are not the same axis (310 values against 206) and nothing measured
    says they are interchangeable. It would also have stripped `abstraction_level`, `segment` and
    `brand_letter` from OBReach.

    Inheriting a MISSING axis is a mechanical, safe repair. Removing a declared one is a modelling
    decision about what a concept means, and no measurement authorises it. So this only ever adds,
    and reports the columns the grain does not account for rather than deleting them."""
    pin = ((concept.get("identity") or {}).get("canonical_key"))
    missing = []
    for g in grain:
        if any(d == g or substitutable(g, d, det) for d in declared):
            continue
        if pin and (g == pin or substitutable(g, pin, det)):
            continue
        missing.append(g)
    unaccounted = [d for d in declared
                   if d != pin and not any(d == g or substitutable(g, d, det) for g in grain)]
    return declared + missing, missing, unaccounted


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    root = pathlib.Path(a.root).resolve()

    changed, pins, nogrāin = [], [], []
    for f in sorted(glob.glob(str(root / "ontology" / "concepts" / "*.yaml"))):
        p = pathlib.Path(f)
        doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        con = doc.get("concept") or {}
        name = str(con.get("name") or p.stem)
        touched = False
        for s in ((doc.get("grounding") or {}).get("sources") or []):
            rel = str(s.get("relation") or "")
            key = s.get("key")
            declared = [key] if isinstance(key, str) else list(key or ())
            if not rel or not declared:
                continue
            # ONLY A MEASURE CONCEPT INHERITS THE GRAIN. Its key identifies a FIGURE, so it must
            # be the grain. An enumeration or reference concept grounded on the same fact keys on a
            # DISCRIMINATOR — Perspective's key IS `role`, and expanding it to the six-column grain
            # (which the first cut did) turns an axis into a figure identity. The ontology-test
            # generator learned the same distinction the same way.
            if str(con.get("class")) != "measure":
                continue
            grain, det = measured(root, rel)
            if not grain:
                nogrāin.append((name, rel))
                continue
            derived, missing, pinned = derive(con, grain, det, declared)
            if pinned:
                pins.append((name, rel, ", ".join(pinned)))
            if missing:
                changed.append((name, rel, declared, derived, missing))
                s["key"] = derived
                s["key_inherited_from"] = f"data/profiles/{rel.split('.')[-1]}.yaml#identity_evidence.key"
                touched = True
        if touched and a.apply:
            p.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100),
                         encoding="utf-8")

    print(f"  {len(changed)} concept(s) declare a key MISSING an axis the grain measures:\n")
    for name, rel, declared, derived, missing in changed:
        print(f"     {name:<14}{rel}")
        print(f"        was {declared}")
        print(f"        now {derived}")
        print(f"        +   {', '.join(missing)}  <- SUM over the old key double-counts on these")
    if pins:
        print(f"\n  {len(pins)} concept(s) keep a column they PIN to their own identity code — kept, and")
        print(f"  reported, because whether a pinned column belongs in the key is a ruling not a")
        print(f"  measurement: {chr(10) + '     '.join(f"{n:<14}{c}" for n, r, c in pins[:12])}")
    if nogrāin:
        print(f"\n  {len(nogrāin)} grounding(s) have no measured grain yet (run mac_admit_identity):")
        for n, r in nogrāin[:8]:
            print(f"     {n:<14}{r}")
    if not a.apply:
        print("\n  (report only — pass --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
