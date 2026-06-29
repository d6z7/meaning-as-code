#!/usr/bin/env python3
"""
mac_to_shacl.py — project a MAC ontology onto SHACL shapes (the *validation* companion to mac_to_rdf.py).

Where mac_to_rdf.py emits the OWL schema (classes + properties), this emits the SHACL shapes that say
what INSTANCE DATA of that schema must satisfy — so an RDF/triple-store deployment of a MAC ontology can
be validated by any SHACL engine. The mapping (all of it derived from data already in the MAC files):

  node-class concept (entity/event/reference/grouping) -> sh:NodeShape  (sh:targetClass :Class)
  grounded column                                      -> sh:property   (sh:path :Class.col ; sh:datatype xsd:* ;
                                                                          primary_key -> sh:minCount 1 ; sh:maxCount 1)
  edge (From -> To, role)                               -> sh:property   (sh:path :From.role ; sh:class :To ;
                                                                          cardinality from the `to` endpoint)
  enumeration (closure: closed) grounding a column      -> sh:property   (sh:path :Owner.col ; sh:in ( codes… ))

Property/path URIs are class-qualified (`:Class.col`, `:From.role`) — identical to mac_to_rdf.py, so the
shapes target exactly the OWL the sibling tool emits.

Built with rdflib; the shapes graph is valid RDF by construction. `--selftest` goes further: it runs a
real SHACL engine (pySHACL) over auto-synthesised instance data and asserts the shapes ACCEPT a conforming
graph and REJECT a deliberately-broken one (missing keys, out-of-enum codes) — the answer to "is it
actually working?".

Usage:
  python3 tools/mac_to_shacl.py <ontology_root> [-o out.shacl.ttl]
  python3 tools/mac_to_shacl.py <ontology_root> --selftest        # validate with pySHACL (good vs bad data)
"""
import argparse
import sys
from pathlib import Path

import yaml
from mac_project import resolve
from rdflib import Graph, Namespace, Literal, URIRef, BNode, RDF, RDFS, XSD
from rdflib.collection import Collection

SH = Namespace("http://www.w3.org/ns/shacl#")
NODE_CLASSES = {"entity", "event", "reference", "grouping"}
XSD_OF = {"string": XSD.string, "integer": XSD.integer, "int": XSD.integer, "decimal": XSD.decimal,
          "numeric": XSD.decimal, "number": XSD.decimal, "float": XSD.double, "double": XSD.double,
          "boolean": XSD.boolean, "date": XSD.date, "timestamp": XSD.dateTime, "datetime": XSD.dateTime}
# minCount, maxCount per `to`-endpoint cardinality string
CARD = {"1": (1, 1), "0..1": (0, 1), "1..n": (1, None), "0..n": (0, None), "n": (0, None)}


def load(p):
    return yaml.safe_load(Path(p).read_text()) or {}


def table_cols(root, name):
    f = resolve(root).descriptors / f"{name}.yaml"
    if not f.exists():
        return []
    return [c for c in (load(f).get("columns") or []) if isinstance(c, dict) and c.get("name")]


def ground_table(d):
    """The single table a concept grounds to (grounding.table, or sources[].relation tail)."""
    g = d.get("grounding") or {}
    if isinstance(g.get("table"), str):
        return g["table"]
    for s in (g.get("sources") or []):
        if isinstance(s, dict) and isinstance(s.get("relation"), str):
            return s["relation"].split(".")[-1]
    return None


def build_shapes(root):
    """Return (graph, MAC namespace, ontology-name). Pure projection — no validation."""
    name = root.name
    for f in (resolve(root).ontology / "concepts").glob("**/*.yaml"):
        src = (load(f).get("metadata") or {}).get("source")
        if src:
            name = str(src).lower()
            break

    MAC = Namespace(f"https://meaning-as-code.dev/onto/{name}#")
    g = Graph()
    g.bind("", MAC)
    g.bind("sh", SH)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)

    concepts = [load(f) for f in sorted((resolve(root).ontology / "concepts").glob("**/*.yaml"))]
    node_concepts = {(d.get("concept") or {}).get("name"): d
                     for d in concepts if (d.get("concept") or {}).get("class") in NODE_CLASSES
                     and (d.get("concept") or {}).get("name")}
    table_to_class = {ground_table(d): nm for nm, d in node_concepts.items() if ground_table(d)}
    shape_of = {}            # class name -> NodeShape URI (so edges/enums can hang property shapes on it)

    _bn = [0]                       # deterministic, build-order blank-node ids: BNode() mints RANDOM ids
    def _bid(prefix):               # each run, so the Turtle serialization order churns. Stable ids fix it.
        _bn[0] += 1
        return BNode(f"{prefix}{_bn[0]:04d}")

    def prop(shape, path, **kw):
        b = _bid("ps")
        g.add((shape, SH.property, b))
        g.add((b, SH.path, path))
        if "name" in kw:
            g.add((b, SH.name, Literal(kw["name"])))
        if "datatype" in kw:
            g.add((b, SH.datatype, kw["datatype"]))
            g.add((b, SH.nodeKind, SH.Literal))
        if "cls" in kw:
            g.add((b, SH["class"], kw["cls"]))
            g.add((b, SH.nodeKind, SH.IRI))
        if kw.get("min") is not None:
            g.add((b, SH.minCount, Literal(int(kw["min"]))))
        if kw.get("max") is not None:
            g.add((b, SH.maxCount, Literal(int(kw["max"]))))
        if "members" in kw:
            lst = _bid("in")
            Collection(g, lst, [Literal(m, datatype=XSD.string) for m in kw["members"]])
            g.add((b, SH["in"], lst))
        if "message" in kw:
            g.add((b, SH.message, Literal(kw["message"])))
        g.add((b, SH.severity, kw.get("severity", SH.Violation)))
        return b

    # 1) one NodeShape per node-class concept; one property shape per grounded column
    for nm, d in node_concepts.items():
        shape = MAC[f"{nm}Shape"]
        shape_of[nm] = shape
        g.add((shape, RDF.type, SH.NodeShape))
        g.add((shape, SH.targetClass, MAC[nm]))
        g.add((shape, RDFS.label, Literal(f"{nm} shape")))
        for col in table_cols(root, ground_table(d)):
            is_pk = col.get("role") == "primary_key"
            prop(shape, MAC[f"{nm}.{col['name']}"], name=col["name"],
                 datatype=XSD_OF.get(str(col.get("type", "")).lower(), XSD.string),
                 min=(1 if is_pk else None), max=1,
                 message=(f"{nm}.{col['name']} is the identity key — exactly one required" if is_pk else None))

    # 2) edges -> object-property shapes on the From shape (range + cardinality from the `to` endpoint)
    ef = resolve(root).ontology / "edges.yaml"
    for e in (load(ef).get("edges") or []) if ef.exists() else []:
        ep = e.get("endpoints") or {}
        frm, to = (ep.get("from") or {}), (ep.get("to") or {})
        fc, tc = frm.get("concept"), to.get("concept")
        role = frm.get("role") or e.get("edge_id")
        if fc not in shape_of or tc not in shape_of:
            continue
        mn, mx = CARD.get(str(to.get("cardinality", "")).lower().replace(" ", ""), (0, 1))
        prop(shape_of[fc], MAC[f"{fc}.{role}"], cls=MAC[tc], min=mn, max=mx,
             message=f"{fc}.{role} -> {tc} (grounded: {e.get('join_rule', '')})")

    # 3) closed enumerations -> sh:in on the discriminator column, hung on the owning class's shape
    for d in concepts:
        c = d.get("concept") or {}
        if c.get("class") != "enumeration":
            continue
        vals = d.get("values") or {}
        if vals.get("closure") != "closed":
            continue
        codes = [i.get("code") for i in (vals.get("items") or []) if isinstance(i, dict) and i.get("code")]
        col = (d.get("grounding") or {}).get("grounds_column")
        owner = table_to_class.get(ground_table(d))
        if not (codes and col and owner in shape_of):
            continue
        prop(shape_of[owner], MAC[f"{owner}.{col}"], members=codes, datatype=XSD.string,
             message=f"{c.get('name')} is a closed code list ({len(codes)} values): {', '.join(codes)}")

    return g, MAC, name


# ── selftest: prove the shapes accept good data and reject broken data, via a real SHACL engine ──
SAMPLE = {XSD.string: Literal("x"), XSD.integer: Literal(1), XSD.decimal: Literal("1.5", datatype=XSD.decimal),
          XSD.double: Literal(1.5), XSD.boolean: Literal(True),
          XSD.date: Literal("2020-01-01", datatype=XSD.date),
          XSD.dateTime: Literal("2020-01-01T00:00:00", datatype=XSD.dateTime)}


def _instances(shapes, MAC, broken):
    """Synthesise one fully-populated instance per NodeShape. broken=False -> conforming;
    broken=True -> omit every required value and set an out-of-enum literal where sh:in exists."""
    EX = Namespace("https://example.org/data/")
    g = Graph()
    inst = {}
    for s in shapes.subjects(RDF.type, SH.NodeShape):
        cls = shapes.value(s, SH.targetClass)
        node = EX[("bad_" if broken else "good_") + str(cls).split("#")[-1]]
        inst[cls] = (node, s)
        g.add((node, RDF.type, cls))
    for cls, (node, s) in inst.items():
        for ps in shapes.objects(s, SH.property):
            required = (shapes.value(ps, SH.minCount) is not None and int(shapes.value(ps, SH.minCount)) >= 1)
            path = shapes.value(ps, SH.path)
            members = shapes.value(ps, SH["in"])
            if members is not None:
                # enum: good -> first valid code; bad -> a value not in the set
                code = list(Collection(shapes, members))[0] if not broken else Literal("__INVALID__")
                g.add((node, path, code))
                continue
            if broken:
                continue  # omit required literals/edges -> triggers minCount violations
            tgt = shapes.value(ps, SH["class"])
            if tgt is not None:
                g.add((node, path, inst.get(tgt, (EX["ph"],))[0]))
            elif required:
                dt = shapes.value(ps, SH.datatype) or XSD.string
                g.add((node, path, SAMPLE.get(dt, Literal("x"))))
    return g


def selftest(shapes, MAC):
    import pyshacl
    good = _instances(shapes, MAC, broken=False)
    bad = _instances(shapes, MAC, broken=True)
    ok_g, _, _ = pyshacl.validate(good, shacl_graph=shapes, inference="none")
    ok_b, report, _ = pyshacl.validate(bad, shacl_graph=shapes, inference="none")
    n_viol = sum(1 for _ in report.subjects(RDF.type, SH.ValidationResult))
    print(f"  conforming instance graph  -> conforms={ok_g}  (expected True)")
    print(f"  broken instance graph      -> conforms={ok_b}  (expected False; {n_viol} violations reported)")
    passed = ok_g and not ok_b and n_viol > 0
    print(("✓ SHACL self-test PASSED — shapes accept valid data and reject invalid data"
           if passed else "✗ SHACL self-test FAILED"), file=sys.stderr)
    return passed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("-o", "--out")
    ap.add_argument("--selftest", action="store_true", help="validate shapes with pySHACL (good vs bad data)")
    a = ap.parse_args()
    root = Path(a.root)

    g, MAC, name = build_shapes(root)
    Graph().parse(data=g.serialize(format="turtle"), format="turtle")   # round-trip: valid RDF
    n_ns = sum(1 for _ in g.subjects(RDF.type, SH.NodeShape))
    n_ps = sum(1 for _ in g.objects(None, SH.property))
    n_in = sum(1 for _ in g.subject_objects(SH["in"]))
    header = (f"# MAC -> SHACL shapes for '{name}'. Generated by mac_to_shacl.py — do not edit.\n"
              f"# {n_ns} sh:NodeShape, {n_ps} property shapes ({n_in} closed-enum sh:in); {len(g)} triples.\n")
    out = header + g.serialize(format="turtle")
    if a.out:
        Path(a.out).write_text(out)
        print(f"wrote {a.out}: {n_ns} node shapes, {n_ps} property shapes, {n_in} closed-enum constraints, {len(g)} triples")
    elif not a.selftest:
        sys.stdout.write(out)

    if a.selftest:
        print(f"self-test '{name}': {n_ns} node shapes, {n_ps} property shapes, {n_in} sh:in constraints")
        if not selftest(g, MAC):
            sys.exit(1)


if __name__ == "__main__":
    main()
