#!/usr/bin/env python3
"""
mac_to_mermaid.py — project a MAC ontology onto a Mermaid flowchart (the 6th projector).

Where mac_to_rdf/graph/okf/shacl/osi target machines, this targets HUMANS: a diagram that renders inline
on GitHub (and in any Mermaid-aware viewer) straight from the model, so the picture never goes stale. It
draws the two planes when the project is two-plane (data/ontology):

  ontology plane  — one node per concept, coloured by class (entity/event/reference/grouping/measure/enumeration)
  edges           — solid arrows (role + cardinality)
  data plane      — one cylinder per dataset descriptor (structure only)
  the seam        — dashed "grounds" links from each concept to the dataset it grounds

Layout is automatic (Mermaid's job); for a hand-laid hero image use the drawio companion.

Usage:  python3 tools/mac_to_mermaid.py <ontology_root> [-o out.mmd]
"""
import argparse
import sys
from pathlib import Path

import yaml
from mac_project import resolve

CLASS_STYLE = {
    "entity":      "fill:#dae8fc,stroke:#6c8ebf,color:#000",
    "event":       "fill:#ffe6cc,stroke:#d79b00,color:#000",
    "reference":   "fill:#d5e8d4,stroke:#82b366,color:#000",
    "grouping":    "fill:#e1d5e7,stroke:#9673a6,color:#000",
    "measure":     "fill:#fff2cc,stroke:#d6b656,color:#000",
    "enumeration": "fill:#f5f5f5,stroke:#666,color:#000",
}


def load(p):
    return yaml.safe_load(Path(p).read_text()) or {}


def gtable(d):
    g = d.get("grounding") or {}
    if isinstance(g.get("table"), str):
        return g["table"]
    return next((s.get("relation", "").split(".")[-1]
                 for s in (g.get("sources") or []) if isinstance(s, dict)), None)


def esc(s):
    return str(s).replace('"', "'").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    root = Path(a.root)
    L = resolve(root)

    name = root.name
    docs = []
    for f in sorted((L.ontology / "concepts").glob("**/*.yaml")):
        d = load(f)
        docs.append(d)
        src = (d.get("metadata") or {}).get("source")
        if src and name == root.name:
            name = str(src).lower()

    concepts = {(d.get("concept") or {}).get("name"): d for d in docs if (d.get("concept") or {}).get("name")}

    # datasets present in the data plane (descriptor files), and which concept grounds which
    datasets = {}
    for f in sorted(L.descriptors.glob("*.yaml")):
        t = load(f).get("table") or {}
        if t.get("name"):
            datasets[t["name"]] = t
    grounded = {nm: gtable(d) for nm, d in concepts.items()}

    ef = L.ontology / "edges.yaml"
    edges = (load(ef).get("edges") or []) if ef.exists() else []

    out = [f'%%{{init: {{"flowchart": {{"curve": "basis"}}}}}}%%',
           "flowchart TB",
           f'  subgraph ONT["ONTOLOGY PLANE — {name}: what it means (concepts · edges · rules)"]',
           "    direction LR"]
    by_class = {}
    for nm, d in concepts.items():
        cls = (d.get("concept") or {}).get("class", "")
        out.append(f'    {nm}["{nm}<br/><i>«{cls}»</i>"]')
        by_class.setdefault(cls, []).append(nm)
    # edges (solid, role + cardinality from the `to` endpoint)
    for e in edges:
        ep = e.get("endpoints") or {}
        fr, to = (ep.get("from") or {}), (ep.get("to") or {})
        fc, tc = fr.get("concept"), to.get("concept")
        if fc in concepts and tc in concepts:
            role = fr.get("role") or e.get("edge_id")
            card = to.get("cardinality", "")
            out.append(f'    {fc} -->|"{esc(role)} ({esc(card)})"| {tc}')
    out.append("  end")

    if datasets:
        out.append('  subgraph DATA["DATA PLANE — how the data is made (datasets = structure only)"]')
        out.append("    direction LR")
        for tname, t in datasets.items():
            key = next((c["name"] for c in (t.get("columns") or [])
                        if isinstance(c, dict) and c.get("role") == "primary_key"), "")
            label = f"{tname}" + (f"<br/>{key} pk" if key else "")
            out.append(f'    t_{tname}[("{label}")]')
        out.append("  end")
        # the seam: concept -. grounds .-> dataset
        for nm, tbl in grounded.items():
            if tbl in datasets:
                out.append(f"  {nm} -. grounds .-> t_{tbl}")

    # colour by class
    for cls, style in CLASS_STYLE.items():
        out.append(f"  classDef {cls} {style};")
    out.append("  classDef dataset fill:#ffffff,stroke:#999,color:#333;")
    for cls, members in by_class.items():
        if cls in CLASS_STYLE and members:
            out.append(f"  class {','.join(members)} {cls};")
    if datasets:
        out.append(f"  class {','.join('t_' + t for t in datasets)} dataset;")

    text = "\n".join(out) + "\n"
    n_e = sum(1 for e in edges if (e.get('endpoints', {}).get('from', {}).get('concept') in concepts
                                   and e.get('endpoints', {}).get('to', {}).get('concept') in concepts))
    if a.out:
        Path(a.out).write_text(text)
        print(f"wrote {a.out}: {len(concepts)} concepts, {n_e} edges, {len(datasets)} datasets")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
