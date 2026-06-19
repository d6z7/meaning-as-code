#!/usr/bin/env python3
"""
mac_to_mermaid.py — project a MAC model onto a Mermaid diagram (THE Mermaid exporter).

Where mac_to_rdf/graph/okf/shacl/osi target machines, this targets HUMANS: a diagram that renders inline
on GitHub (and any Mermaid viewer) straight from the model, so the picture never goes stale. ONE exporter,
the VIEW chosen by an explicit mode flag (named, like every other mac_to_<format> tool — no magic default):

  --ontology   ontology flowchart  — concepts (coloured by class) grounded to the data plane (datasets)   <name>.mmd
  --er         object ER           — one box per node-class concept; attributes = its grounded columns     <name>.er.mmd
  --physical   physical ER         — one box per PRODUCED table; FK edges (every table, incl. bridges)      <name>.physical.er.mmd
  --lineage    data-plane lineage  — sources -> transforms -> datasets (production flow)                    <name>.data_lineage.mmd

Flowchart modes (--ontology, --lineage) accept --direction TB|LR (LR for wide projects -> portrait). Every
view carries a `name · description` title. Layout is automatic (Mermaid's job); for a hand-laid hero image
use the drawio companion.

Usage:  python3 tools/mac_to_mermaid.py <root> (--ontology|--er|--physical|--lineage) [--direction TB|LR] [-o out.mmd]
"""
import argparse
import re
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
CARD_L = {"1": "||", "0..1": "|o", "1..n": "}|", "0..n": "}o"}   # crow's-foot (erDiagram), left/right forms
CARD_R = {"1": "||", "0..1": "o|", "1..n": "|{", "0..n": "o{"}
NODE_CLASSES = {"entity", "event", "reference", "grouping"}
SEED = "s__seed"


def load(p):
    return yaml.safe_load(Path(p).read_text()) or {}


def esc(s):
    return str(s).replace('"', "'").strip()


def nid(s):
    return re.sub(r"\W", "_", str(s))


def bare(rel):
    return str(rel).split(".")[-1]


def gtable(d):
    g = d.get("grounding") or {}
    if isinstance(g.get("table"), str):
        return g["table"]
    return next((s.get("relation", "").split(".")[-1]
                 for s in (g.get("sources") or []) if isinstance(s, dict)), None)


def er_type(t):
    """Mermaid erDiagram attribute types must be a SINGLE bare token — collapse generics: array<string> ->
    array_string, decimal(10,2) -> decimal_10_2."""
    s = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in str(t or "string"))
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_") or "string"


# ── readers ───────────────────────────────────────────────────────────────────────────────────────────
def gather(root):
    """Ontology plane + seam: (name, concepts, datasets, grounded, edges)."""
    L = resolve(root)
    name = Path(root).name
    docs = []
    for f in sorted((L.ontology / "concepts").glob("**/*.yaml")):
        d = load(f)
        docs.append(d)
        src = (d.get("metadata") or {}).get("source")
        if src and name == Path(root).name:
            name = str(src).lower()
    concepts = {(d.get("concept") or {}).get("name"): d for d in docs if (d.get("concept") or {}).get("name")}
    datasets = {}
    for f in sorted(L.descriptors.glob("*.yaml")):
        doc = load(f)
        t = doc.get("table") or {}
        if t.get("name"):
            datasets[t["name"]] = doc
    grounded = {nm: gtable(d) for nm, d in concepts.items()}
    ef = L.ontology / "edges.yaml"
    edges = (load(ef).get("edges") or []) if ef.exists() else []
    return name, concepts, datasets, grounded, edges


def gather_dataplane(root):
    """Data plane: (name, datasets, sources, transforms) — for the lineage view."""
    L = resolve(root)
    name = Path(root).name
    datasets, sources, transforms = {}, {}, []
    for f in sorted(L.descriptors.glob("*.yaml")):
        d = load(f)
        t = d.get("table") or {}
        if t.get("name"):
            datasets[t["name"]] = d
    if getattr(L, "sources", None):
        for f in sorted(L.sources.glob("*.yaml")):
            d = load(f)
            t = d.get("table") or {}
            if t.get("name"):
                sources[t["name"]] = d
    if getattr(L, "transforms", None):
        for f in sorted(L.transforms.glob("*.yaml")):
            d = load(f)
            if d.get("produces"):
                transforms.append(d)
    for d in transforms or list(datasets.values()):
        s = (d.get("metadata") or {}).get("source")
        if s:
            name = str(s).lower()
            break
    return name, datasets, sources, transforms


# ── builders ──────────────────────────────────────────────────────────────────────────────────────────
def build_ontology(name, concepts, datasets, grounded, edges, direction="TB"):
    """Ontology flowchart: concepts (coloured by class) + edges, grounded to the data plane (the seam)."""
    out = [f"---\ntitle: {name} — ontology flowchart · concepts grounded to the data plane\n---",
           '%%{init: {"flowchart": {"curve": "basis"}}}%%',
           f"flowchart {direction}",
           f'  subgraph ONT["ONTOLOGY PLANE — {name}: what it means (concepts · edges · rules)"]',
           "    direction LR"]
    by_class = {}
    for nm, d in concepts.items():
        cls = (d.get("concept") or {}).get("class", "")
        out.append(f'    {nm}["{nm}<br/><i>«{cls}»</i>"]')
        by_class.setdefault(cls, []).append(nm)
    for e in edges:
        ep = e.get("endpoints") or {}
        fr, to = (ep.get("from") or {}), (ep.get("to") or {})
        fc, tc = fr.get("concept"), to.get("concept")
        if fc in concepts and tc in concepts:
            out.append(f'    {fc} -->|"{esc(fr.get("role") or e.get("edge_id"))} ({esc(to.get("cardinality",""))})"| {tc}')
    out.append("  end")
    if datasets:
        out.append('  subgraph DATA["DATA PLANE — how the data is made (datasets = structure only)"]')
        out.append("    direction LR")
        for tname, t in datasets.items():
            key = next((c["name"] for c in (t.get("columns") or [])
                        if isinstance(c, dict) and c.get("role") == "primary_key"), "")
            label = tname + (f"<br/>{key} pk" if key else "")
            out.append(f'    t_{tname}[("{label}")]')
        out.append("  end")
        for nm, tbl in grounded.items():
            if tbl in datasets:
                out.append(f"  {nm} -. grounds .-> t_{tbl}")
    for cls, style in CLASS_STYLE.items():
        out.append(f"  classDef {cls} {style};")
    out.append("  classDef dataset fill:#ffffff,stroke:#999,color:#333;")
    for cls, members in by_class.items():
        if cls in CLASS_STYLE and members:
            out.append(f"  class {','.join(members)} {cls};")
    if datasets:
        out.append(f"  class {','.join('t_' + t for t in datasets)} dataset;")
    n_e = sum(1 for e in edges if (e.get('endpoints', {}).get('from', {}).get('concept') in concepts
                                   and e.get('endpoints', {}).get('to', {}).get('concept') in concepts))
    return "\n".join(out) + "\n", len(concepts), n_e, len(datasets)


def build_er(name, concepts, datasets, grounded, edges):
    """Object ER: entities = grounded node-class concepts, attributes = their dataset columns, relations = edges."""
    nodes = {nm: d for nm, d in concepts.items()
             if (d.get("concept") or {}).get("class") in NODE_CLASSES}
    out = [f"---\ntitle: {name} — object ER · entities are node-class concepts\n---", "erDiagram"]
    n_r = 0
    for e in edges:
        ep = e.get("endpoints") or {}
        fr, to = (ep.get("from") or {}), (ep.get("to") or {})
        fc, tc = fr.get("concept"), to.get("concept")
        if fc in nodes and tc in nodes:
            lc = CARD_L.get(str(to.get("cardinality", "")).lower().replace(" ", ""), "||")
            rc = CARD_R.get(str(fr.get("cardinality", "")).lower().replace(" ", ""), "o{")
            out.append(f'  {tc} {lc}--{rc} {fc} : "{esc(fr.get("role") or e.get("edge_id"))}"')
            n_r += 1
    for nm, d in nodes.items():
        cols = (datasets.get(grounded.get(nm)) or {}).get("columns") or []
        out.append(f"  {nm} {{")
        for c in cols:
            if not (isinstance(c, dict) and c.get("name")):
                continue
            role = c.get("role")
            key = " PK" if role in ("primary_key", "composite_key_part") else (" FK" if role == "foreign_key" else "")
            out.append(f"    {er_type(c.get('type'))} {c['name']}{key}")
        out.append("  }")
    return "\n".join(out) + "\n", len(nodes), n_r


def build_physical_er(name, datasets):
    """Physical ER: one box per PRODUCED table (data/datasets), FK edges inferred from `references` or
    PK-name matching. EVERY table is a box — incl. bridge/variant/serving tables the object ER omits. A
    schema that renames keys across tables (TPC-H c_nationkey->n_nationkey) must declare `references`, else
    the join shows only in the object ER (which reads edges.yaml)."""
    pk_owner = {}
    for tname, doc in datasets.items():
        for c in (doc.get("columns") or []):
            if isinstance(c, dict) and c.get("role") in ("primary_key", "composite_key_part"):
                pk_owner.setdefault(c["name"], tname)
    out = [f"---\ntitle: {name} — physical ER · one box per produced table\n---", "erDiagram"]
    seen, rels = set(), []
    for tname, doc in datasets.items():
        for c in (doc.get("columns") or []):
            if not (isinstance(c, dict) and c.get("name")):
                continue
            ref = c.get("references")
            owner = (str(ref).split(".")[0] if ref else None) or pk_owner.get(c["name"])
            if owner in datasets and owner != tname and (owner, tname, c["name"]) not in seen:
                seen.add((owner, tname, c["name"]))
                rels.append(f'  {owner} ||--o{{ {tname} : "{c["name"]}"')
    out.extend(rels)
    for tname, doc in datasets.items():
        out.append(f"  {tname} {{")
        for c in (doc.get("columns") or []):
            if not (isinstance(c, dict) and c.get("name")):
                continue
            role = c.get("role")
            key = " PK" if role in ("primary_key", "composite_key_part") else (" FK" if role == "foreign_key" else "")
            out.append(f"    {er_type(c.get('type'))} {c['name']}{key}")
        out.append("  }")
    return "\n".join(out) + "\n", len(datasets), len(rels)


def build_lineage(name, datasets, sources, transforms, direction="LR"):
    """Data-plane lineage as a depth-ranked DAG in PRODUCTION FLOW: sources -> transforms -> datasets (every
    edge points toward the produced output). ONE node per named object (datasets, transforms, sources never
    collapsed). Input `kind` drives the source node: raw_source -> [/source/], dataset -> upstream ([dataset])
    dashed view-on-view, authored_seed -> [\\seed\\], external -> [/external/]. Completeness (inputs[] mirror
    the SQL) is the lineage-complete profile (CONFORMANCE.md) — this reads inputs[], so gaps show as gaps."""
    ds_ids = {b: f"d_{nid(b)}" for b in datasets}
    src_ids = {b: f"s_{nid(b)}" for b in sources}
    ext_ids, seed_used, tfm_ids, edges, warns = {}, False, {}, [], []
    for d in transforms:
        produced = bare((d.get("produces") or {}).get("relation", ""))
        if not produced:
            continue
        d_id = ds_ids.setdefault(produced, f"d_{nid(produced)}")
        t_id = f"t_{nid(produced)}"
        tfm_ids[produced] = (t_id, (d.get("metadata") or {}).get("pipeline") or produced)
        edges.append((t_id, d_id, "", False))                  # transform PRODUCES dataset
        for inp in (d.get("inputs") or []):
            b, kind, role = bare(inp.get("relation", "")), inp.get("kind"), inp.get("role")
            if kind == "dataset":
                tgt = ds_ids.setdefault(b, f"d_{nid(b)}")
                edges.append((tgt, t_id, role or "feeds", True))    # upstream dataset FEEDS transform (view-on-view)
            elif kind == "authored_seed":
                seed_used = True
                edges.append((SEED, t_id, role or "authoring_source", False))
            elif kind == "external":
                edges.append((ext_ids.setdefault(b, f"e_{nid(b)}"), t_id, role or "external", False))
            else:                                                   # raw_source (or omitted)
                edges.append((src_ids.setdefault(b, f"s_{nid(b)}"), t_id, role or "consumes", False))
                if b not in sources:
                    warns.append(f"input '{inp.get('relation','')}' (kind={kind}) has no data/sources/ descriptor")

    L = [f"---\ntitle: {name} — data-plane lineage · sources → transforms → datasets (production flow)\n---",
         f"flowchart {direction}",
         "  %% GENERATED by mac_to_mermaid --lineage. Production flow: every edge points toward the produced output.",
         "  %% Shapes: ([dataset]) {{transform}} [/source/] [\\seed\\] [/external/].  Dashed = view-on-view dependency.",
         "  %% datasets (the seam)"]
    L += [f'  {i}[("{b}")]' for b, i in ds_ids.items()]
    L.append("  %% transforms (pipelines)")
    L += [f'  {i}{{{{"pipeline: {pipe}"}}}}' for _, (i, pipe) in tfm_ids.items()]
    if src_ids:
        L.append("  %% sources (every named raw input = its own node)")
        L += [f'  {i}[/"{b}"/]' for b, i in src_ids.items()]
    L += [f'  {i}[/"{b} (external)"/]' for b, i in ext_ids.items()]
    if seed_used:
        L.append(f'  {SEED}[\\"authored seed — from the ontology"\\]')
    L.append("  %% edges (production flow: source/seed/upstream -> transform -> dataset)")
    for a, b, label, dashed in edges:
        arrow = "-.->" if dashed else "-->"
        L.append(f"  {a} {arrow}|{label}| {b}" if label else f"  {a} {arrow} {b}")
    L += [
        "  classDef dataset fill:#dae8fc,stroke:#6c8ebf,color:#000;",
        "  classDef transform fill:#ffe6cc,stroke:#d79b00,color:#000;",
        "  classDef source fill:#d5e8d4,stroke:#82b366,color:#000;",
        "  classDef external fill:#f8cecc,stroke:#b85450,color:#000;",
        "  classDef seed fill:#fff2cc,stroke:#d6b656,color:#000;",
    ]
    if ds_ids:
        L.append(f"  class {','.join(ds_ids.values())} dataset;")
    if tfm_ids:
        L.append(f"  class {','.join(i for i, _ in tfm_ids.values())} transform;")
    if src_ids:
        L.append(f"  class {','.join(src_ids.values())} source;")
    if ext_ids:
        L.append(f"  class {','.join(ext_ids.values())} external;")
    if seed_used:
        L.append(f"  class {SEED} seed;")
    return "\n".join(L) + "\n", len(ds_ids), len(tfm_ids), len(src_ids) + len(ext_ids) + (1 if seed_used else 0), warns


def main():
    ap = argparse.ArgumentParser(description="Project a MAC model onto a Mermaid diagram (the Mermaid exporter).")
    ap.add_argument("root")
    ap.add_argument("-o", "--out")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--ontology", action="store_true", help="ontology flowchart (concepts grounded to datasets)")
    mode.add_argument("--er", action="store_true", help="object ER (one box per node-class concept)")
    mode.add_argument("--physical", action="store_true", help="physical ER (one box per produced table, FK edges)")
    mode.add_argument("--lineage", action="store_true", help="data-plane lineage (sources -> transforms -> datasets)")
    ap.add_argument("--direction", choices=["TB", "LR"], default="TB",
                    help="flowchart direction for --ontology/--lineage (TB default; LR for wide projects -> portrait)")
    a = ap.parse_args()
    root = Path(a.root)

    def emit(text, summary):
        if a.out:
            Path(a.out).write_text(text)
            print(f"wrote {a.out}: {summary}")
        else:
            sys.stdout.write(text)

    if a.lineage:
        name, datasets, sources, transforms = gather_dataplane(root)
        if not transforms:
            print(f"(no data/transforms/ in {root} — declare `transforms:` in mac.project.yaml)", file=sys.stderr)
            return
        text, nd, nt, ns, warns = build_lineage(name, datasets, sources, transforms, a.direction)
        emit(text, f"data-plane lineage — {nd} datasets, {nt} transforms, {ns} sources")
        for w in warns:
            print(f"  [WARN] {w}", file=sys.stderr)
        return

    name, concepts, datasets, grounded, edges = gather(root)
    if a.physical:
        text, n_tbl, n_rel = build_physical_er(name, datasets)
        emit(text, f"physical ER — {n_tbl} tables, {n_rel} foreign keys")
    elif a.er:
        text, n_ent, n_rel = build_er(name, concepts, datasets, grounded, edges)
        emit(text, f"object ER — {n_ent} entities, {n_rel} relationships")
    else:  # a.ontology
        text, n_c, n_e, n_d = build_ontology(name, concepts, datasets, grounded, edges, a.direction)
        emit(text, f"ontology flowchart — {n_c} concepts, {n_e} edges, {n_d} datasets")


if __name__ == "__main__":
    main()
