#!/usr/bin/env python3
"""
mac_to_osi.py — project a MAC ontology onto an OSI (Open Semantic Interchange) semantic model.

Backs the positioning claim ("MAC can speak OSI for the part OSI covers") with running code: it maps the
MAC layers onto OSI 0.2.0.dev0 —
  MAC Physical (tables/<t>.yaml)        -> OSI datasets[] + fields[]   (source, primary_key, columns)
  MAC Edges    (edges.yaml join_rule)   -> OSI relationships[]         (from/to + from_columns/to_columns)
  MAC Rules    (rules.yaml sql_expression) -> OSI metrics[]            (aggregate expression)
MAC keys OSI cannot express (the typed contract.rules, additivity law, closure, six classes) are dropped
by design — OSI covers the measure/dimension/relationship slice; MAC keeps the rest. That asymmetry is the
point of "formalize the closed, govern the open; export to the standards for the slice they own."

Usage:  python3 tools/mac_to_osi.py <ontology_root> [-o out.osi.yaml]
Output validates against core-spec/osi-schema.json (version 0.2.0.dev0).
"""
import argparse, re, sys
from pathlib import Path
import yaml
from mac_project import resolve

OSI_VERSION = "0.2.0.dev0"
DIALECT = "ANSI_SQL"
TIME_TYPES = {"date", "timestamp", "datetime"}


def expr(sql):  # OSI Expression: a list of per-dialect expressions
    return {"dialects": [{"dialect": DIALECT, "expression": sql}]}


def load(p):
    return yaml.safe_load(Path(p).read_text()) or {}


def datasets(root):
    out = []
    for f in sorted((resolve(root).descriptors).glob("*.yaml")):
        d = load(f)
        t = d.get("table") or {}
        cols = [c for c in (d.get("columns") or []) if isinstance(c, dict) and c.get("name")]
        if not t.get("name"):
            continue
        ds = {
            "name": t["name"],
            "source": f"{t['schema']}.{t['name']}" if t.get("schema") else t["name"],
        }
        pk = [c["name"] for c in cols if c.get("role") in ("primary_key", "composite_key_part")]
        if pk:
            ds["primary_key"] = pk
        fields = []
        for c in cols:
            fld = {"name": c["name"], "expression": expr(c["name"])}
            is_time = c.get("type") in TIME_TYPES or c.get("x-subrole") == "temporal"
            if is_time:
                fld["dimension"] = {"is_time": True}
            if c.get("description"):
                fld["description"] = c["description"]
            fields.append(fld)
        if fields:
            ds["fields"] = fields
        out.append(ds)
    return out


def relationships(root):
    f = resolve(root).ontology / "edges.yaml"
    if not f.exists():
        return []
    out = []
    for e in (load(f).get("edges") or []):
        jr = e.get("join_rule")
        if not jr:
            continue  # an un-enriched edge has no physical join → not an OSI relationship
        froms, tos, ftab, ttab = [], [], None, None
        for clause in re.split(r"\s+AND\s+", jr):
            m = re.match(r"\s*([\w.]+)\.(\w+)\s*=\s*([\w.]+)\.(\w+)\s*", clause)
            if not m:
                continue
            lt, lc, rt, rc = m.groups()
            ftab, ttab = lt.split(".")[-1], rt.split(".")[-1]   # strip any schema/catalog prefix
            froms.append(lc); tos.append(rc)
        if froms and tos:
            out.append({"name": e.get("edge_id", f"{ftab}__{ttab}"),
                        "from": ftab, "to": ttab, "from_columns": froms, "to_columns": tos})
    return out


def metrics(root):
    f = resolve(root).ontology / "rules.yaml"     # two-plane aware (was root/rules.yaml)
    if not f.exists():
        return []
    out = []
    for r in (load(f).get("rules") or []):
        if r.get("render_kind") != "sql_expression" or not r.get("template"):
            continue  # only renderable aggregate expressions become OSI metrics
        name = (r.get("derives") or r.get("rule") or "metric")
        out.append({"name": str(name).lower(),
                    "expression": expr(r["template"].strip().splitlines()[0].split("--")[0].strip()),
                    "description": (r.get("logic") or "").strip()[:300] or r.get("rule", "")})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="MAC ontology root (dir with tables/, edges.yaml, rules.yaml)")
    ap.add_argument("-o", "--out", help="output file (default: stdout)")
    a = ap.parse_args()
    root = Path(a.root)

    # model name: the source label off any table's metadata, else the dir name
    name = root.name
    for f in (resolve(root).descriptors).glob("*.yaml"):
        src = ((load(f).get("metadata") or {}).get("source"))
        if src:
            name = str(src).lower(); break

    sm = {"name": name, "description": f"OSI projection of the MAC ontology at {root.name}",
          "datasets": datasets(root)}
    rels, mets = relationships(root), metrics(root)
    if rels:
        sm["relationships"] = rels
    if mets:
        sm["metrics"] = mets
    osi = {"version": OSI_VERSION, "semantic_model": [sm]}

    text = "# Generated by mac_to_osi.py — OSI %s projection of a MAC ontology. Do not edit by hand.\n%s" % (
        OSI_VERSION, yaml.safe_dump(osi, sort_keys=False, width=120, allow_unicode=True))
    if a.out:
        Path(a.out).write_text(text)
        print(f"wrote {a.out}: {len(sm['datasets'])} datasets, {len(rels)} relationships, {len(mets)} metrics")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
