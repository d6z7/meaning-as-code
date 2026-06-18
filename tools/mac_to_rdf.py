#!/usr/bin/env python3
"""
mac_to_rdf.py — project a MAC ontology onto an RDF/OWL ontology (Turtle).

The third projector (with mac_to_osi.py and mac_to_graph.py): backs the RDF/OWL / triple-store target
(Stardog, Neptune-RDF, any SHACL/OWL tool). Maps the MAC layers onto OWL —
  Concepts (entity/event/reference/grouping) -> owl:Class
  grounded columns                            -> owl:DatatypeProperty (rdfs:domain class, rdfs:range xsd:*)
  Edges (endpoints + role)                    -> owl:ObjectProperty   (rdfs:domain From, rdfs:range To)
measure/enumeration concepts are not classes here (a measure is a derived metric). Property URIs are
class-qualified (`:Class.col`, `:From.role`) so a name reused across tables stays a distinct property
with a single domain/range — not an accidental OWL intersection.

Built with rdflib, so the output is valid RDF by construction and re-parses cleanly (the validation).

Usage:  python3 tools/mac_to_rdf.py <ontology_root> [-o out.ttl]
"""
import argparse, sys
from pathlib import Path
import yaml
from mac_project import resolve, meaning_by_table


def gtable(d):
    """The relation name a concept grounds to (grounding.table or sources[].relation tail)."""
    gr = d.get("grounding") or {}
    return gr.get("table") or next((s.get("relation", "").split(".")[-1]
                                    for s in (gr.get("sources") or []) if isinstance(s, dict)), None)
from rdflib import Graph, Namespace, Literal, URIRef, RDF, RDFS, OWL, XSD

NODE_CLASSES = {"entity", "event", "reference", "grouping"}
XSD_OF = {"string": XSD.string, "integer": XSD.integer, "int": XSD.integer, "decimal": XSD.decimal,
          "numeric": XSD.decimal, "number": XSD.decimal, "float": XSD.double, "double": XSD.double,
          "boolean": XSD.boolean, "date": XSD.date, "timestamp": XSD.dateTime, "datetime": XSD.dateTime}


def load(p): return yaml.safe_load(Path(p).read_text()) or {}


def table_cols(root, name):
    f = resolve(root).descriptors / f"{name}.yaml"
    if not f.exists():
        return []
    return [c for c in (load(f).get("columns") or []) if isinstance(c, dict) and c.get("name")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root"); ap.add_argument("-o", "--out")
    a = ap.parse_args(); root = Path(a.root)

    name = root.name
    for f in (resolve(root).ontology / "concepts").glob("**/*.yaml"):
        src = ((load(f).get("metadata") or {}).get("source"))
        if src: name = str(src).lower(); break

    MAC = Namespace(f"https://meaning-as-code.dev/onto/{name}#")
    g = Graph(); g.bind("", MAC); g.bind("owl", OWL); g.bind("rdfs", RDFS); g.bind("xsd", XSD)
    onto = URIRef(str(MAC)[:-1])           # the ontology IRI (drop the trailing '#')
    g.add((onto, RDF.type, OWL.Ontology)); g.add((onto, RDFS.label, Literal(name)))

    all_docs = [load(f) for f in sorted((resolve(root).ontology / "concepts").glob("**/*.yaml"))]
    mbt = meaning_by_table(all_docs, gtable)   # Option B: column meaning comes from field-anchored rules

    classes = {}   # concept name -> class URI
    for d in all_docs:
        c = d.get("concept") or {}
        if c.get("class") not in NODE_CLASSES or not c.get("name"):
            continue
        label = c["name"]; cls = MAC[label]; classes[label] = cls
        g.add((cls, RDF.type, OWL.Class)); g.add((cls, RDFS.label, Literal(label)))
        if c.get("definition"):
            g.add((cls, RDFS.comment, Literal(" ".join(str(c["definition"]).split()))))
        tbl = gtable(d)
        for col in (table_cols(root, tbl) if tbl else []):
            dp = URIRef(f"{MAC}{label}.{col['name']}")   # class-qualified -> unique, single domain
            g.add((dp, RDF.type, OWL.DatatypeProperty)); g.add((dp, RDFS.label, Literal(col["name"])))
            g.add((dp, RDFS.domain, cls))
            g.add((dp, RDFS.range, XSD_OF.get(str(col.get("type", "")).lower(), XSD.string)))
            meaning = mbt.get((tbl, col["name"])) or col.get("description")  # field rule first, then descriptor
            if meaning:
                g.add((dp, RDFS.comment, Literal(" ".join(str(meaning).split()))))

    for e in (load(resolve(root).ontology / "edges.yaml").get("edges") or []) if (resolve(root).ontology / "edges.yaml").exists() else []:
        ep = e.get("endpoints") or {}; frm, to = (ep.get("from") or {}), (ep.get("to") or {})
        fc, tc, role = frm.get("concept"), to.get("concept"), frm.get("role") or e.get("edge_id")
        if fc not in classes or tc not in classes:
            continue
        op = URIRef(f"{MAC}{fc}.{role}")     # class-qualified object property
        g.add((op, RDF.type, OWL.ObjectProperty)); g.add((op, RDFS.label, Literal(role)))
        g.add((op, RDFS.domain, classes[fc])); g.add((op, RDFS.range, classes[tc]))
        if e.get("join_rule"):
            g.add((op, RDFS.comment, Literal(f"grounded join: {e['join_rule']}")))

    ttl = g.serialize(format="turtle")
    # validation: re-parse what we emitted (rdflib guarantees validity, but prove the round-trip)
    Graph().parse(data=ttl, format="turtle")
    n_cls = sum(1 for _ in g.subjects(RDF.type, OWL.Class))
    n_op = sum(1 for _ in g.subjects(RDF.type, OWL.ObjectProperty))
    n_dp = sum(1 for _ in g.subjects(RDF.type, OWL.DatatypeProperty))
    header = (f"# MAC -> RDF/OWL projection of '{name}' (Turtle). Generated by mac_to_rdf.py — do not edit.\n"
              f"# {n_cls} owl:Class, {n_op} owl:ObjectProperty, {n_dp} owl:DatatypeProperty; {len(g)} triples.\n")
    out = header + ttl
    if a.out:
        Path(a.out).write_text(out)
        print(f"wrote {a.out}: {n_cls} classes, {n_op} object props, {n_dp} datatype props, {len(g)} triples")
    else:
        sys.stdout.write(out)
    print(f"✓ valid RDF — re-parsed {len(g)} triples cleanly", file=sys.stderr)


if __name__ == "__main__":
    main()
