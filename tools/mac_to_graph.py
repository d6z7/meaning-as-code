#!/usr/bin/env python3
"""
mac_to_graph.py — project a MAC ontology onto a property-graph schema (openCypher).

The second projector (alongside mac_to_osi.py): backs the "projects onto a graph DB" half of the thesis.
A MAC ontology maps cleanly to a labelled property graph —
  Concepts (entity / event / reference / grouping)  -> node labels   (key = grounded PK, properties = grounded columns)
  Edges    (edges.yaml endpoints + role)             -> relationship types  (:From)-[:ROLE]->(:To)
`measure` and `enumeration` concepts are NOT nodes (a measure is a derived metric, an enumeration a value set).
The FK columns become graph *relationships* (you traverse, not join) — the join_rule is kept as a comment.

Emits a runnable Cypher schema (node-key constraints) + the topology as schema comments, and runs a
self-consistency check (every relationship endpoint is a declared node; every node key is a grounded column).

Usage:  python3 tools/mac_to_graph.py <ontology_root> [-o out.cypher]
"""
import argparse, re, sys
from pathlib import Path
import yaml
import mac_project as P
from mac_project import resolve

NODE_CLASSES = {"entity", "event", "reference", "grouping"}


def load(p): return yaml.safe_load(Path(p).read_text()) or {}
def upper_snake(s): return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s or "").upper().replace(" ", "_")


def table_cols(root, name):
    f = resolve(root).descriptors / f"{name}.yaml"
    if not f.exists():
        return [], None
    d = load(f)
    cols = [c for c in (d.get("columns") or []) if isinstance(c, dict) and c.get("name")]
    pk = next((c["name"] for c in cols if c.get("role") == "primary_key"), None)
    return [c["name"] for c in cols], pk


def nodes(root):
    out = {}
    for f in sorted((resolve(root).ontology / "concepts").glob("**/*.yaml")):
        d = load(f); c = d.get("concept") or {}
        if c.get("class") not in NODE_CLASSES or not c.get("name"):
            continue
        g = d.get("grounding") or {}
        tbl = g.get("table") or next((s.get("relation", "").split(".")[-1]
                                      for s in (g.get("sources") or []) if isinstance(s, dict)), None)
        cols, pk = table_cols(root, tbl) if tbl else ([], None)
        ident = c.get("identity") or {}
        # THE CONCEPT'S OWN KEY BEATS THE RELATION'S PK. This read the PK first and the concept's key
        # last, so every concept grounding a SHARED relation at a different grain was keyed by the fact
        # table's PK: measured on contoso4 2026-09-28, 6 of 10 nodes were wrong — ProductCategory and
        # ProductSubCategory keyed by ProductKey, Location and Region by StoreKey. A graph that keys
        # category by product draws category AT PRODUCT GRAIN, which is the one thing the Location /
        # Store distinction exists to prevent. The canonical column is read from its single home
        # (CONFORMANCE §2.1) with `identity.canonical_key` still honoured as a migration fallback.
        key = g.get("key_column") or P.canonical_key(d) or pk
        out[c["name"]] = {"label": c["name"], "table": tbl, "key": key, "props": cols, "class": c["class"],
                          "concept.identity": ident.get("kind")}
    return out


def rels(root):
    f = resolve(root).ontology / "edges.yaml"
    if not f.exists():
        return []
    out = []
    for e in (load(f).get("edges") or []):
        ep = e.get("endpoints") or {}
        frm, to = (ep.get("from") or {}), (ep.get("to") or {})
        fc, tc = frm.get("concept"), to.get("concept")
        if not fc or not tc:
            continue
        rtype = upper_snake(frm.get("role") or "__".join(e.get("edge_id", "").split("__")[1:-1]) or "RELATES_TO")
        out.append({"type": rtype, "from": fc, "to": tc, "on": e.get("join_rule", ""), "edge_id": e.get("edge_id", "")})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root"); ap.add_argument("-o", "--out")
    a = ap.parse_args(); root = Path(a.root)

    N, R = nodes(root), rels(root)
    name = root.name
    for f in (resolve(root).ontology / "concepts").glob("**/*.yaml"):
        src = ((load(f).get("metadata") or {}).get("source"))
        if src: name = str(src).lower(); break

    # --- self-consistency check (the rigor analog of OSI schema-validation) ---
    # keyless-by-design kinds (mac.concept.identity) legitimately have no single-column key — a fact grain
    # or an unresolved SME identity — so they are NOT flagged. `resolved_axis` ("a pinned/resolved axis")
    # was RETIRED from mac_vocabulary.yaml#concept.identity on 2026-09-28 — 0 of 62 concepts used it —
    # and the schema enum no longer admits it, so a concept spelling it fails validate_schema before it
    # reaches this check.
    KEYLESS_KINDS = {"composite", "sme_pending"}
    problems = []
    for n in N.values():
        if not n["key"] and n.get("concept.identity") not in KEYLESS_KINDS:
            problems.append(f'node :{n["label"]} has no key (no grounding key_column, no column '
                            f'declaring identity: canonical, no table PK)')
        elif n["key"] and n["props"] and n["key"] not in n["props"]:
            problems.append(f'node :{n["label"]} key "{n["key"]}" is not a grounded column')
    for r in R:
        for side in ("from", "to"):
            if r[side] not in N:
                problems.append(f'relationship {r["edge_id"]} {side}=:{r[side]} is not a node label (class not in {sorted(NODE_CLASSES)})')

    L = []
    L.append(f"// MAC -> property-graph (openCypher) projection of '{name}'. Generated by mac_to_graph.py — do not edit.")
    L.append(f"// {len(N)} node labels, {len(R)} relationship types. Concepts of class measure/enumeration are not nodes.")
    L.append("")
    L.append("// --- node key constraints (runnable Cypher) ---")
    for n in N.values():
        if n["key"]:
            L.append(f"CREATE CONSTRAINT {n['label'].lower()}_key IF NOT EXISTS FOR (n:{n['label']}) REQUIRE n.{n['key']} IS UNIQUE;")
    L.append("")
    L.append("// --- node properties (schema; * = key) ---")
    for n in N.values():
        props = ", ".join((f"{p}*" if p == n["key"] else p) for p in n["props"]) or "(no grounded columns)"
        L.append(f"//   (:{n['label']} {{{props}}})   <- {n['table']}")
    L.append("")
    L.append("// --- relationships (from MAC edges; FK columns become traversals) ---")
    for r in R:
        L.append(f"//   (:{r['from']})-[:{r['type']}]->(:{r['to']})" + (f"   on {r['on']}" if r['on'] else ""))
    text = "\n".join(L) + "\n"

    if a.out:
        Path(a.out).write_text(text)
        print(f"wrote {a.out}: {len(N)} nodes, {len(R)} relationships")
    else:
        sys.stdout.write(text)
    if problems:
        print(f"\n✗ self-consistency: {len(problems)} problem(s):", file=sys.stderr)
        for p in problems: print("   -", p, file=sys.stderr)
        sys.exit(1)
    print(f"✓ self-consistency OK — every relationship endpoint is a node, every node key is a grounded column", file=sys.stderr)


if __name__ == "__main__":
    main()
