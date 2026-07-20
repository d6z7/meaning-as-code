#!/usr/bin/env python3
"""project_model — project an applied MAC ontology into a human/machine model catalog.

The ontology is the source of truth; this is a PROJECTION of it — a generated view of every measure
(KPI) and dimension the applied model defines, plus the additivity law each measure obeys. Nothing here
is authored by hand: it is read from the concept files, the derived-measure rules, and the framework's
mac.MeasureType additivity matrix. Regenerate it any time the ontology changes; never edit the output.

Reads (all under <source_root>):
  ontology/concepts/**/*.yaml   — concepts: `concept.{name,class,...}`, `grounding`, closed `values`/`enumerations`
  ontology/rules.yaml           — derived measures (rule/derives/over/logic)
  <mac>/mac_vocabulary.yaml      — the MeasureType additivity law (Flow/Stock/Target × time/categorical)

Emits  <source_root>/projections/model.md  and  model.json  (override with --out-dir).

  usage:  python3 tools/project_model.py <source_root> [--out-dir DIR] [--print]
  e.g.    python3 tools/project_model.py ../<applied-ontology-repo>
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
MAC_VOCAB = HERE.parent / "mac_vocabulary.yaml"

EFFECT = {  # mac.aggregation_effect term -> short label for the projection
    "mac.aggregation_effect.additive":      "additive (sum)",
    "mac.aggregation_effect.point_in_time": "point-in-time (as-of)",
    "mac.aggregation_effect.averageable":   "averageable (avg / percentile)",
    "mac.aggregation_effect.non_aggregable":"non-additive",
    "mac.aggregation_effect.semi_additive": "semi-additive",
}


def load(p: Path):
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as e:                                     # keep going; report the bad file
        return {"__error__": f"{p}: {e}"}


def measure_law() -> dict:
    """The additivity matrix from mac.MeasureType: {Flow: {time,categorical}, Stock:…, Target:…}."""
    doc = load(MAC_VOCAB)
    mt = (doc.get("MeasureType") or {}).get("members") or {}
    out = {}
    for name, spec in mt.items():
        add = (spec or {}).get("additivity") or {}
        out[name] = {
            "definition": (spec or {}).get("definition", ""),
            "time":        EFFECT.get(add.get("time"), add.get("time", "?")),
            "categorical": EFFECT.get(add.get("categorical"), add.get("categorical", "?")),
        }
    return out


def grounding_of(doc: dict) -> dict:
    """Extract {relations, key, columns} from a concept's grounding block (tolerant of variants)."""
    g = doc.get("grounding") or {}
    relations, key, cols = [], None, []
    for s in (g.get("sources") or []):
        if isinstance(s, dict):
            if s.get("relation"): relations.append(s["relation"])
            key = key or s.get("key")
            cols += s.get("columns") or []
    if isinstance(g.get("table"), str):
        relations.append(g["table"])
    for t in (g.get("primary_tables") or g.get("tables") or []):
        relations.append(t["name"] if isinstance(t, dict) else t)
    fr = g.get("field_roles") or {}
    if not key:
        key = next((c for c, r in fr.items() if isinstance(r, str) and r.endswith(".key")), None)
    return {"relations": sorted(set(relations)), "key": key, "columns": sorted(set(cols))}


def values_of(doc: dict) -> list[dict]:
    """Collect the closed value set of a concept, from top-level `values.items` or `enumerations[].values`."""
    out = []
    v = doc.get("values")
    if isinstance(v, dict):
        for it in (v.get("items") or []):
            if isinstance(it, dict):
                out.append({"code": it.get("code", it.get("value")), "closure": v.get("closure"), **it})
    for en in (doc.get("enumerations") or []):
        if isinstance(en, dict):
            for it in (en.get("values") or en.get("items") or []):
                if isinstance(it, dict):
                    out.append({"code": it.get("code", it.get("value")), "closure": en.get("closure"), **it})
    return out


def project(root: Path) -> dict:
    law = measure_law()
    concepts = sorted((root / "ontology" / "concepts").rglob("*.yaml"))
    measures, dimensions = [], []

    for p in concepts:
        doc = load(p)
        c = doc.get("concept") or {}
        name = c.get("name") or p.stem
        rec = {
            "name": name, "class": c.get("class"), "label": c.get("label"),
            "german": c.get("german"), "definition": (c.get("definition") or "").strip(),
            "file": str(p.relative_to(root)), "grounding": grounding_of(doc),
            "values": values_of(doc), "identity": (c.get("identity") or {}),
        }
        if c.get("class") == "measure":
            measures.append(rec)
        else:
            dimensions.append(rec)

    # base measures = the KpiCode-style enumeration whose items carry `measure_type`
    base = {}
    for m in measures:
        for it in m["values"]:
            mt = it.get("measure_type")
            if not mt:
                continue
            meas = it.get("measure") or (it["code"].split(".")[0] if it.get("code") else "?")
            variant = it["code"].split(".")[1] if it.get("code") and "." in it["code"] else None
            tkey = str(mt).split(".")[-1]           # Flow|Stock|Target
            b = base.setdefault(meas, {"measure": meas, "type": tkey, "variants": []})
            if variant and variant not in b["variants"]:
                b["variants"].append(variant)

    # derived measures from rules.yaml
    derived = []
    rp = root / "ontology" / "rules.yaml"
    if rp.exists():
        for r in (load(rp).get("rules") or []):
            if isinstance(r, dict):
                derived.append({
                    "rule": r.get("rule"), "derives": r.get("derives"),
                    "over": r.get("over"), "logic": (str(r.get("logic") or "")).strip().split("\n")[0],
                    "confidence": r.get("confidence"),
                })

    return {"law": law, "base_measures": base, "measure_concepts": measures,
            "derived": derived, "dimensions": dimensions}


def to_markdown(root: Path, model: dict) -> str:
    L, law = [], model["law"]
    L.append(f"# Model projection — `{root.name}`\n")
    L.append("_Generated by `meaning-as-code/tools/project_model.py` — a projection of the ontology. "
             "Do not edit; regenerate._\n")

    L.append("## Measures (KPIs)\n")
    L.append("The measure **type** fixes how it may be aggregated (mac.MeasureType):\n")
    L.append("| Type | over time | over geography/model |")
    L.append("|---|---|---|")
    for t, spec in law.items():
        L.append(f"| **{t}** | {spec['time']} | {spec['categorical']} |")
    L.append("")
    if model["base_measures"]:
        L.append("### Base measures\n")
        L.append("| Measure | Type | Variants |")
        L.append("|---|---|---|")
        for b in sorted(model["base_measures"].values(), key=lambda x: (x["type"], x["measure"])):
            L.append(f"| `{b['measure']}` | {b['type']} | {', '.join(b['variants'])} |")
        ncodes = sum(len(b["variants"]) for b in model["base_measures"].values())
        L.append(f"\n_{len(model['base_measures'])} base measures × variants = {ncodes} KpiCodes._\n")
    for m in model["measure_concepts"]:
        if not any(it.get("measure_type") for it in m["values"]):     # a standalone measure concept (no typed KpiCode enumeration)
            g = ", ".join(m["grounding"]["relations"]) or "—"
            L.append(f"### {m['name']} (special measure)\n")
            L.append(f"{m['definition']}\n")
            L.append(f"_grounding: `{g}`_\n")

    if model["derived"]:
        L.append("### Derived measures (rules.yaml)\n")
        L.append("| Rule | Derives | Over |")
        L.append("|---|---|---|")
        for d in model["derived"]:
            over = ", ".join(f"`{o}`" for o in (d["over"] or []))
            L.append(f"| {d['rule']} | {d['derives']} | {over} |")
        L.append("")

    L.append("## Dimensions\n")
    L.append("| Dimension | Class | Identity | Key | Serving relation | #Values | Values (closed sets) |")
    L.append("|---|---|---|---|---|---|---|")
    for d in sorted(model["dimensions"], key=lambda x: (x["class"] or "", x["name"])):
        g = d["grounding"]
        codes = [str(v["code"]) for v in d["values"] if v.get("code")]
        closed = any(v.get("closure") == "closed" for v in d["values"])
        vlist = ", ".join(f"`{c}`" for c in codes[:20]) + (" …" if len(codes) > 20 else "")
        if not codes:
            vlist = "_derived / open_"
        n = f"{len(codes)}{'*' if closed else ''}" if codes else "—"
        rel = ", ".join(f"`{r}`" for r in g["relations"]) or "—"
        kv = g["key"]
        key = ", ".join(f"`{k}`" for k in kv) if isinstance(kv, list) else (f"`{kv}`" if kv else "—")
        ik = (d.get("identity") or {}).get("kind") or "—"
        L.append(f"| **{d['name']}** | {d['class']} | {ik} | {key} | {rel} | {n} | {vlist} |")
    L.append("\n_`*` = closed enumeration (exactly these values; anything else is `__unmapped__`)._")
    L.append("_Identity = `mac.identity_kind`: iso · code · namespace_code · fk_name · composite · resolved_axis · sme_pending._")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Project an applied MAC ontology into a model catalog.")
    ap.add_argument("source_root", help="applied-ontology repo root (contains ontology/)")
    ap.add_argument("--out-dir", default=None, help="output dir (default: <source_root>/projections)")
    ap.add_argument("--print", action="store_true", help="also print the Markdown to stdout")
    a = ap.parse_args()

    root = Path(a.source_root).resolve()
    if not (root / "ontology" / "concepts").is_dir():
        print(f"ERROR: {root}/ontology/concepts not found", file=sys.stderr); return 2

    model = project(root)
    md = to_markdown(root, model)
    out = Path(a.out_dir) if a.out_dir else (root / "projections")
    out.mkdir(parents=True, exist_ok=True)
    (out / "model.md").write_text(md, encoding="utf-8")
    (out / "model.json").write_text(json.dumps(model, indent=2, default=str, ensure_ascii=False), encoding="utf-8")

    nmeas = len(model["base_measures"]); ncodes = sum(len(b["variants"]) for b in model["base_measures"].values())
    print(f"projected {root.name}: {nmeas} base measures ({ncodes} KpiCodes), "
          f"{len(model['derived'])} derived, {len(model['dimensions'])} dimensions "
          f"→ {out / 'model.md'}")
    if a.print:
        print("\n" + md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
