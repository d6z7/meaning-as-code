#!/usr/bin/env python3
"""
check_shapes.py — MAC constraint validator (the "shapes" layer).

The third MAC gate, alongside validate_schema.py (structural) and check_references.py (referential):
this one enforces CONSTRAINTS that are themselves DATA. Shapes are declared in YAML (built-in
mac_shapes.yaml + any application-supplied files), not in code, and this one generic engine runs them
all. A shape says: for nodes matching `target` (+ optional `where`), a `constraint` must hold.

It is SHACL-shaped (target · path · constraint · severity) but YAML-native over MAC files — no RDF.
Domain-neutral: point it at any MAC ontology root (a dir containing concepts/).

Usage:
  tools/check_shapes.py <ontology_root> [--shapes FILE ...]   # built-in shapes always load
Exit 0 = all shapes satisfied (no error-severity violations); 1 = at least one error.
"""
import argparse
import sys
from pathlib import Path

import yaml
from mac_project import resolve

REPO = Path(__file__).resolve().parents[1]
BUILTIN = REPO / "mac_shapes.yaml"


def extract(node, path):
    """Resolve a dotted path; `[]` flattens a list. Returns a flat list of leaf values."""
    cur = [node]
    for p in path.split("."):
        flat, key = p.endswith("[]"), (p[:-2] if p.endswith("[]") else p)
        nxt = []
        for c in cur:
            if isinstance(c, dict) and c.get(key) is not None:
                v = c[key]
                nxt.extend(v) if (flat and isinstance(v, list)) else nxt.append(v)
        cur = nxt
    out = []
    for c in cur:
        out.extend(c) if isinstance(c, list) else out.append(c)
    return out


def matches_where(doc, where):
    """Optional target filter, e.g. {concept.class: measure} — apply the shape only to those nodes."""
    for path, want in (where or {}).items():
        if want not in extract(doc, path):
            return False
    return True


def grounded_columns(doc, root):
    """The columns of the table(s) a concept grounds to — resolved CROSS-FILE from the Physical layer,
    where columns are single-homed (v0.5 dropped grounding.columns). Supports both grounding forms:
    grounding.table (sql_table adapter) and grounding.sources[].relation (the v0.5-agnostic form)."""
    g = doc.get("grounding") or {}
    names = []
    if isinstance(g.get("table"), str):
        names.append(g["table"])
    for s in (g.get("sources") or []):
        if isinstance(s, dict) and isinstance(s.get("relation"), str):
            names.append(s["relation"].split(".")[-1])   # strip schema/catalog prefix
    descriptors = resolve(root).descriptors      # flat: root/tables; two-plane: root/data/datasets
    cols = set()
    for t in names:
        f = descriptors / f"{t}.yaml"
        if f.exists():
            tdoc = yaml.safe_load(f.read_text()) or {}
            for col in (tdoc.get("columns") or []):
                if isinstance(col, dict) and col.get("name"):
                    cols.add(col["name"])
    return cols


def check(shape, doc, focus, out, root):
    if not matches_where(doc, shape.get("where")):
        return
    c, sev, sid = shape["constraint"], shape.get("severity", "error"), shape["id"]
    k = c["kind"]
    if k == "required":
        if len(extract(doc, c["path"])) < c.get("min", 1):
            out.append((sev, focus, sid, f'{c["path"]} is required'))
    elif k == "in":
        allowed = set(c["values"])
        for v in extract(doc, c["path"]):
            if v not in allowed:
                out.append((sev, focus, sid, f'{c["path"]}: "{v}" not in closed set'))
    elif k == "subset_of":
        left = set(extract(doc, c["left"]))
        rights = c["right"] if isinstance(c["right"], list) else [c["right"]]
        right = set().union(*[set(extract(doc, r)) for r in rights]) if rights else set()
        for v in sorted(left - right):
            out.append((sev, focus, sid, f'{c["left"]}: "{v}" not in {c["right"]}'))
    elif k == "rule_binds_grounded":
        # CROSS-FILE relational invariant: every rule.binds must be a column of the table the concept
        # grounds to (the field-anchoring). Columns are single-homed in the Physical layer.
        cols = grounded_columns(doc, root)
        for b in sorted(set(extract(doc, c.get("path", "contract.rules[].binds")))):
            if b not in cols:
                out.append((sev, focus, sid, f'rule binds "{b}" — not a column of the grounded table'))
    elif k == "field_roles_grounded":
        # v0.1.7: every column WHITELISTED in grounding.field_roles must be a real grounded column
        # (the role VALUE's resolution is check_references' job; this proves the KEY exists).
        cols = grounded_columns(doc, root)
        fr = (doc.get("grounding") or {}).get("field_roles") or {}
        for col in sorted(fr if isinstance(fr, dict) else {}):
            if col not in cols:
                out.append((sev, focus, sid, f'field_roles whitelists "{col}" — not a column of the grounded table'))
    else:
        out.append(("error", focus, sid, f'unknown constraint kind "{k}"'))


def load_shapes(extra):
    shapes = yaml.safe_load(BUILTIN.read_text())["shapes"] if BUILTIN.exists() else []
    for f in extra or []:
        shapes += (yaml.safe_load(Path(f).read_text()) or {}).get("shapes", [])
    return shapes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="MAC ontology root (a dir containing concepts/)")
    ap.add_argument("--shapes", nargs="*", default=[], help="extra application shape files")
    a = ap.parse_args()

    shapes = load_shapes(a.shapes)
    concepts_dir = resolve(a.root).ontology / "concepts"     # flat: root/concepts; two-plane: root/ontology/concepts
    files = sorted(concepts_dir.glob("*/*.yaml")) + \
            sorted(concepts_dir.glob("*.yaml"))
    viol = []
    for f in files:
        doc = yaml.safe_load(f.read_text())
        if isinstance(doc, dict):
            for s in shapes:
                check(s, doc, f.name, viol, a.root)

    print(f"── MAC shapes gate ── {len(shapes)} shape(s) × {len(files)} concept(s) "
          f"under {a.root} ──")
    for sev, focus, sid, msg in viol:
        print(f"  [{sev.upper()}] {focus} :: {sid}: {msg}")
    errs = sum(1 for v in viol if v[0] == "error")
    print("\n" + (f"✗ {len(viol)} violation(s) ({errs} error)" if viol
                  else "✓ OK — all shapes satisfied"))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
