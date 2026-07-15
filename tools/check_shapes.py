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
import re
import sys
from pathlib import Path

import yaml
from mac_project import resolve

try:                                   # the SQL-parsing kinds (join_rule_grounded, no_predicate_restatement)
    import sqlglot                     # need sqlglot; the set-relational kinds do not. Import lazily so the
    from sqlglot import exp as _exp    # module stays importable without it (mirrors tools/canon).
except ImportError:
    sqlglot = None
    _exp = None

REPO = Path(__file__).resolve().parents[1]
BUILTIN = REPO / "mac_shapes.yaml"

# a bare column-equality inside a free-prose `then` (fallback when the string is not parseable SQL)
_PROSE_EQ_RE = re.compile(r"([A-Za-z_]\w*\.[A-Za-z_]\w*)\s*=\s*([A-Za-z_]\w*\.[A-Za-z_]\w*)")


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


def grounded_columns_for_relation(relation, root):
    """The columns of ONE Physical-layer relation, resolved by RELATION NAME against its table
    descriptor (root/tables/<t>.yaml flat, root/data/datasets/<t>.yaml two-plane). Tolerates a
    schema/catalog prefix (relA.col's `relA` may be a bare or qualified relation name)."""
    descriptors = resolve(root).descriptors      # flat: root/tables; two-plane: root/data/datasets
    f = descriptors / f"{str(relation).split('.')[-1]}.yaml"
    cols = set()
    if f.exists():
        tdoc = yaml.safe_load(f.read_text()) or {}
        for col in (tdoc.get("columns") or []):
            if isinstance(col, dict) and col.get("name"):
                cols.add(col["name"])
    return cols


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
            names.append(s["relation"])
    cols = set()
    for t in names:
        cols |= grounded_columns_for_relation(t, root)
    return cols


def edges_doc(root):
    """Load the ontology's edges file (root/edges.yaml flat, root/ontology/edges.yaml two-plane).
    The shapes engine otherwise iterates concept files only; the edges layer is loaded here so
    edge-targeted and edge-aware kinds (join_rule_grounded, no_predicate_restatement) can read it."""
    ef = resolve(root).ontology / "edges.yaml"
    if ef.exists():
        d = yaml.safe_load(ef.read_text())
        return d if isinstance(d, dict) else {}
    return {}


def eq_colpairs(text, structured_only=False):
    """Parse `text` as SQL; return the set of column=column predicates it contains, each as an
    order-independent frozenset{'t.c', 't.c'}. `structured_only` requires the WHOLE string to be a
    boolean condition (a pure predicate) — a prose sentence yields the empty set."""
    if sqlglot is None:
        return set()
    try:
        tree = sqlglot.parse_one(text)
    except Exception:               # noqa: BLE001 — free prose is not parseable SQL; caller falls back to regex
        return set()
    if tree is None:
        return set()
    if structured_only and not isinstance(tree, (_exp.EQ, _exp.And, _exp.Or, _exp.Paren, _exp.Not)):
        return set()
    pairs = set()
    for eq in tree.find_all(_exp.EQ):
        l, r = eq.this, eq.expression
        if isinstance(l, _exp.Column) and isinstance(r, _exp.Column):
            lt = f"{l.table}.{l.name}" if l.table else l.name
            rt = f"{r.table}.{r.name}" if r.table else r.name
            pairs.add(frozenset({lt, rt}))
    return pairs


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
    elif k == "join_rule_grounded":
        # target: edges. Each edges[].join_rule is "relA.col = relB.col"; resolve BOTH columns against
        # their endpoint relation's grounded columns (the Physical-layer descriptor). Unresolved → error.
        if sqlglot is None:
            out.append(("warning", focus, sid, "join_rule_grounded needs sqlglot (pip install sqlglot)"))
        else:
            for e in extract(doc, "edges[].join_rule"):
                try:
                    expr = sqlglot.parse_one(e)
                except Exception:   # noqa: BLE001
                    out.append((sev, focus, sid, f'join_rule "{e}": unparseable predicate'))
                    continue
                if expr is None:
                    continue
                for col in expr.find_all(_exp.Column):
                    rel, name = col.table, col.name
                    if not rel:
                        continue   # unqualified column — no relation to resolve against
                    if name not in grounded_columns_for_relation(rel, root):
                        out.append((sev, focus, sid, f'join_rule "{e}": column {rel}.{name} not grounded'))
    elif k == "partition":
        # PER-GROUP uniqueness: values at member_key must be unique WITHIN each group_by group, never
        # globally. The same member in two DIFFERENT groups is fine; twice in ONE group is a violation.
        groups = {}
        for row in extract(doc, c["group_by_root"]):
            if not isinstance(row, dict):
                continue
            g = row.get(c["group_key"])
            for m in (row.get(c["member_key"]) or []):
                groups.setdefault(g, []).append(m)
        for g, members in groups.items():
            dupes = sorted({m for m in members if members.count(m) > 1})
            if dupes:
                out.append((sev, focus, sid,
                            f'partition {c["member_key"]} not unique within {c["group_key"]}={g}: {dupes}'))
    elif k == "no_predicate_restatement":
        # ANTI-DUPLICATION: with the edges file loaded, a concept contract.rules[].then must not RESTATE
        # an edge's join_rule predicate (it may CITE the edge_id, not re-express the join). A structured
        # `then` (a pure predicate) that matches an edge join_rule = error; a free-prose match = warning.
        edge_preds = {}
        for e in (edges_doc(root).get("edges") or []):
            jr = e.get("join_rule") if isinstance(e, dict) else None
            if not jr:
                continue
            for p in eq_colpairs(jr):
                edge_preds[p] = e.get("edge_id")
        if edge_preds:
            for rule in extract(doc, c.get("path", "contract.rules")):
                if not isinstance(rule, dict):
                    continue
                then = rule.get("then")
                if not isinstance(then, str) or not then.strip():
                    continue
                rid = rule.get("id") or rule.get("rule") or "<rule>"
                hit = next((p for p in eq_colpairs(then, structured_only=True) if p in edge_preds), None)
                if hit:
                    out.append(("error", focus, sid,
                                f'rule "{rid}" restates edge {edge_preds[hit]} join_rule {sorted(hit)} — '
                                f'cite the edge, do not restate the predicate'))
                    continue
                for m in _PROSE_EQ_RE.finditer(then):
                    p = frozenset({m.group(1), m.group(2)})
                    if p in edge_preds:
                        out.append(("warning", focus, sid,
                                    f'rule "{rid}" prose restates edge {edge_preds[p]} join_rule {sorted(p)} — '
                                    f'cite the edge instead'))
                        break
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
    ap.add_argument("--baseline", default=None,
                    help="accept the ERRORs listed in this file (logged debt); fail only on NEW errors "
                         "beyond it. Each line is a violation signature — the text after '[ERROR] ' — "
                         "matched exactly (same contract as check_references.py --baseline).")
    a = ap.parse_args()

    accepted = set()
    if a.baseline and Path(a.baseline).is_file():
        accepted = {ln.strip() for ln in Path(a.baseline).read_text(encoding="utf-8").splitlines()
                    if ln.strip() and not ln.lstrip().startswith("#")}

    shapes = load_shapes(a.shapes)
    L = resolve(a.root)
    concepts_dir = L.ontology / "concepts"                   # flat: root/concepts; two-plane: root/ontology/concepts
    files = sorted(concepts_dir.glob("*/*.yaml")) + \
            sorted(concepts_dir.glob("*.yaml"))
    # a shape is dispatched to its target: concept files (default) vs the edges file.
    concept_shapes = [s for s in shapes if s.get("target", "concept") != "edges"]
    edge_shapes = [s for s in shapes if s.get("target") == "edges"]
    viol = []
    for f in files:
        doc = yaml.safe_load(f.read_text())
        if isinstance(doc, dict):
            for s in concept_shapes:
                check(s, doc, f.name, viol, a.root)

    # target: edges — the edges file is never scanned as a concept; load it and run edge-targeted shapes.
    if edge_shapes:
        ef = L.ontology / "edges.yaml"
        edoc = yaml.safe_load(ef.read_text()) if ef.exists() else None
        if isinstance(edoc, dict):
            for s in edge_shapes:
                check(s, edoc, ef.name, viol, a.root)

    print(f"── MAC shapes gate ── {len(shapes)} shape(s) × {len(files)} concept(s) "
          f"(+edges) under {a.root} ──")
    baselined = new_errs = 0
    for sev, focus, sid, msg in viol:
        sig = f"{focus} :: {sid}: {msg}"
        if sev == "error" and sig in accepted:
            baselined += 1
            print(f"  [ERROR·baselined] {sig}")
        else:
            if sev == "error":
                new_errs += 1
            print(f"  [{sev.upper()}] {sig}")
    errs = sum(1 for v in viol if v[0] == "error")
    if viol:
        tail = f"✗ {len(viol)} violation(s) ({errs} error)"
        if baselined:
            tail += f" — {baselined} accepted-baseline, {new_errs} new"
        print("\n" + tail)
    else:
        print("\n✓ OK — all shapes satisfied")
    return 1 if new_errs else 0


if __name__ == "__main__":
    sys.exit(main())
