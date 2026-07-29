#!/usr/bin/env python3
"""
mac_to_explorer.py — project a MAC ontology onto ONE self-contained, offline drill-down HTML explorer.

A companion to the other projectors (mac_to_okf / mac_to_mermaid / mac_to_rdf …): where those emit
machine or single-view artifacts, this emits a browsable human view of the whole model —

  map (all concepts) -> concept card -> rule cards (when/then/never + ASK/COMMIT/REFUSE badge)
                     -> authoring prose collapsed behind expanders
  + a relationship graph (force-directed), a slot-coverage grid, and the decision-policy routing index.

It reads the RAW concept YAML directly (not the projected object model), because the human view needs the
rule text (when/then/never) and the '# PURPOSE —' / '# GENESIS —' authoring comments, which only the source
files carry. Source-agnostic: branding, domains and rule scope are all derived from the data. Any authoring
convention a given project doesn't use (PURPOSE/GENESIS comments, data/lookups registers) degrades to empty,
never to an error.

Usage:
  python3 tools/mac_to_explorer.py <ontology_root> [-o out.html]   # default: <root>/projections/<name>.explorer.html
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "explorer_template.html"

# A register preview embeds up to this many rows (the concept page renders them in a scrollable frame).
# High enough that every enum-scale register (measures, brands, segments…) is COMPLETE; capped so a large
# data-dimension register (thousands of rows) does not bloat the self-contained HTML — its caption stays honest.
REGISTER_PREVIEW_CAP = 200

# ASK / COMMIT / REFUSE : the decision lane derived from a rule's kind (the closed MAC rule-kind vocabulary)
DECISION = {
    "mac.rule_kind.ambiguity":   "ASK",
    "mac.rule_kind.resolution":  "COMMIT",
    "mac.rule_kind.aggregation": "COMMIT",
    "mac.rule_kind.default":     "COMMIT",
    "mac.rule_kind.exclusion":   "REFUSE",
    "mac.rule_kind.guarantee":   "INVARIANT",
}


def decision_of(kind):
    return DECISION.get((kind or "").strip(), "OTHER")


def concepts_dir(root):
    for cand in (root / "ontology" / "concepts", root / "concepts"):
        if cand.is_dir():
            return cand
    return None


def find_file(root, *names):
    for n in names:
        for base in (root / "ontology", root):
            p = base / n
            if p.exists():
                return p
    return None


def extract_prose(text):
    """Pull '# PURPOSE -' / '# GENESIS -' comment blocks and attach each to the '- id:' line below it.
    A project that doesn't use this convention simply yields no prose (handled downstream)."""
    prose = {}
    purpose, genesis, mode = [], [], None
    for raw in text.splitlines():
        s = raw.strip()
        mid = re.match(r"-\s*id:\s*(\S+)", s)
        if mid:
            prose[mid.group(1)] = {"purpose": " ".join(purpose).strip(),
                                   "genesis": " ".join(genesis).strip()}
            purpose, genesis, mode = [], [], None
            continue
        if s.startswith("#"):
            body = s.lstrip("#").strip()
            mp = re.match(r"PURPOSE\s*[—–:\-]\s*(.*)", body)
            mg = re.match(r"GENESIS\s*[—–:\-]\s*(.*)", body)
            if mp:
                mode, purpose = "purpose", [mp.group(1)]
            elif mg:
                mode, genesis = "genesis", [mg.group(1)]
            elif mode and body and not re.match(r"^[=\-─—•·]{3,}", body):
                (purpose if mode == "purpose" else genesis).append(body)
        elif s:
            mode = None
    return prose


def load_register(lookups_dir, register):
    if not lookups_dir:
        return None
    for cand in (lookups_dir / (register + ".csv"),
                 lookups_dir / (register.replace(".lookup", "") + ".csv")):
        if cand.exists():
            try:
                rows = list(csv.reader(cand.open(newline="", encoding="utf-8")))
                if not rows:
                    return None
                return {"file": cand.name, "columns": rows[0],
                        "rows": rows[1:1 + REGISTER_PREVIEW_CAP], "total": len(rows) - 1}
            except Exception:
                return None
    return None


def find_registers(node, found):
    if isinstance(node, dict):
        rb = node.get("realized_by")
        if isinstance(rb, dict):
            reg = (rb.get("params") or {}).get("register")
            if reg:
                found.append(reg)
        for v in node.values():
            find_registers(v, found)
    elif isinstance(node, list):
        for v in node:
            find_registers(v, found)


def extract_constraints(data):
    """concept.constraints[] — the config/data invariants (constraintEntry: assert + severity + enforcer)."""
    out = []
    for c in data.get("constraints", []) or []:
        if isinstance(c, dict):
            out.append({
                "assert": (c.get("assert", "") or "").strip(),
                "severity": c.get("severity", ""),
                "enforced_by": c.get("x-enforced_by", c.get("sql_assertion", "")),
                "machine_executable": bool(c.get("machine_executable")),
                "notes": (c.get("notes", "") or "").strip(),
            })
    return out


def extract_aliases(data):
    """Normalize the NL-trigger vocabulary to [{target, terms[], kind}] across the two alias shapes:
    enum values.aliases.map (two-tier CODE -> {lang: [terms]}) and a flat surface->target map
    (region members.aliases.global)."""
    out = []
    amap = ((data.get("values") or {}).get("aliases") or {}).get("map") or {}
    for code, spec in amap.items():
        terms = []
        ml = (spec or {}).get("multilingual") or {}
        for arr in ml.values():
            if isinstance(arr, list):
                terms += [str(t) for t in arr]
        # also scope_relative tier, if present, is code-keyed maps — collect its surfaces too
        for arr in ((spec or {}).get("scope_relative") or {}).values():
            if isinstance(arr, list):
                terms += [str(t) for t in arr]
        if terms:
            out.append({"target": code, "terms": terms, "kind": "value"})

    def flatten(m):
        for k, v in (m or {}).items():
            if isinstance(v, str):
                out.append({"target": v, "terms": [str(k)], "kind": "surface"})
            elif isinstance(v, dict):
                flatten(v)
    flatten((data.get("members") or {}).get("aliases") or {})
    # merge same-target surface rows
    merged = {}
    for a in out:
        key = (a["kind"], a["target"])
        merged.setdefault(key, {"target": a["target"], "kind": a["kind"], "terms": []})
        for t in a["terms"]:
            if t not in merged[key]["terms"]:
                merged[key]["terms"].append(t)
    return list(merged.values())


def norm_rules(rules, prose):
    out = []
    for r in rules or []:
        if not isinstance(r, dict):
            continue
        rid = r.get("id", "")
        binds = r.get("binds", [])
        if isinstance(binds, str):
            binds = [binds]
        p = prose.get(rid, {})
        out.append({
            "id": rid, "kind": r.get("kind", ""), "decision": decision_of(r.get("kind", "")),
            "scope": r.get("scope", ""), "confidence": r.get("confidence", ""),
            "when": (r.get("when", "") or "").strip(), "then": (r.get("then", "") or "").strip(),
            "never": (r.get("never", "") or "").strip(), "binds": binds,
            "subject": (r.get("subject", "") or "").strip(),  # the one-line email-subject headline (MAC v0.1.13)
            "purpose": p.get("purpose", ""), "genesis": p.get("genesis", ""),
        })
    return out


def parse_concept(path, lookups_dir, cdir):
    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    prose = extract_prose(text)
    concept = data.get("concept", {}) or {}
    meta = data.get("metadata", {}) or {}
    grounding = data.get("grounding", {}) or {}
    contract = data.get("contract", {}) or {}

    regs = []
    find_registers(data, regs)
    previews = []
    for reg in dict.fromkeys(regs):
        prev = load_register(lookups_dir, reg)
        if prev:
            prev["register"] = reg
            previews.append(prev)

    sources = []
    for s in grounding.get("sources", []) or []:
        if isinstance(s, dict):
            cols = s.get("columns", [])
            sources.append({"relation": s.get("relation", ""), "key": s.get("key", ""),
                            "columns": cols if isinstance(cols, list) else [cols]})

    members = data.get("members")
    values = data.get("values")
    domain = os.path.basename(os.path.dirname(path))
    if domain == os.path.basename(cdir):
        domain = "general"
    return {
        "id": concept.get("name", meta.get("concept", os.path.basename(path))),
        "label": concept.get("label", concept.get("name", "")),
        "german": concept.get("german", ""),
        "klass": concept.get("class", ""),
        "definition": (concept.get("definition", "") or "").strip(),
        "identity": concept.get("identity", {}) or {},
        "confidence": meta.get("confidence", ""),
        "version": str(meta.get("version", "")),
        "domain": domain,
        "file": os.path.relpath(path, cdir.parent.parent if cdir else os.path.dirname(path)),
        "slots_present": list(data.keys()),
        "grain": grounding.get("grain", ""),
        "field_roles": grounding.get("field_roles", {}) or {},
        "sources": sources,
        "members_over": (members or {}).get("over", "") if isinstance(members, dict) else "",
        "values_closure": (values or {}).get("closure", "") if isinstance(values, dict) else "",
        "registers": previews,
        "constraints": extract_constraints(data),
        "aliases": extract_aliases(data),
        "rules": norm_rules(contract.get("rules", []), prose),
    }


def parse_edges(root):
    ep = find_file(root, "edges.yaml")
    if not ep:
        return []
    data = yaml.safe_load(ep.read_text(encoding="utf-8")) or {}
    out = []
    for e in data.get("edges", []) or []:
        if not isinstance(e, dict):
            continue
        eps = e.get("endpoints", {}) or {}
        frm, to = eps.get("from", {}) or {}, eps.get("to", {}) or {}
        out.append({"id": e.get("edge_id", ""), "level": e.get("level", ""), "type": e.get("type", ""),
                    "from": frm.get("concept", ""), "to": to.get("concept", ""),
                    "role": frm.get("role", ""), "join_rule": e.get("join_rule", e.get("resolved_by", "")),
                    "card_from": str(frm.get("cardinality", "")), "card_to": str(to.get("cardinality", ""))})
    return out


def parse_query_rules(root):
    qp = find_file(root, "query_rules.yaml")
    if not qp:
        return [], []
    text = qp.read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    general = norm_rules(data.get("rules", []), extract_prose(text))
    policy = []
    for s in (data.get("decision_policy", {}) or {}).get("slots", []) or []:
        if isinstance(s, dict):
            pol = s.get("policy", "")
            policy.append({"slot": s.get("slot", ""), "policy": pol,
                           "lane": {"mandatory_no_default": "ASK", "assumable_default": "COMMIT",
                                    "blocked": "REFUSE"}.get(pol, "OTHER"),
                           "governing_rule": s.get("governing_rule", ""),
                           "on_missing": (s.get("on_missing", "") or "").strip()})
    return general, policy


def parse_rules(root):
    """Optional top-level derived-measure registry — a `rules.yaml` at the ontology root (distinct from a
    concept's contract.rules[] and from query_rules.yaml). Each entry DERIVES a named measure computed OVER
    a set of base concepts / measure-codes. Generic and additive: an absent file, or a rules.yaml with a
    different shape, degrades to [] (missing keys -> "" / []). No source literals."""
    rp = find_file(root, "rules.yaml")
    if not rp:
        return []
    data = yaml.safe_load(rp.read_text(encoding="utf-8")) or {}
    out = []
    for r in data.get("rules", []) or []:
        if not isinstance(r, dict):
            continue
        over = r.get("over", [])
        over = [over] if isinstance(over, str) else [str(o) for o in (over or [])]
        out.append({
            "id": r.get("rule", ""),
            "derives": (r.get("derives", "") or "").strip(),        # the OBJECT / measure name this rule produces
            "over": over,                                            # base concepts + measure-codes it computes from
            "logic": (r.get("logic", "") or "").strip(),
            "render_kind": r.get("render_kind", ""),
            "template": (r.get("template", "") or "").strip(),
            "relative_template": (r.get("relative_template", "") or "").strip(),
            "confidence": r.get("confidence", ""),
            "conditions": [str(c).strip() for c in (r.get("conditions", []) or [])],
            "validated_against": [str(v) for v in (r.get("validated_against", []) or [])],
        })
    return out


def build_graph(concepts, edges):
    ids = {c["id"] for c in concepts}
    nodes = [{"id": c["id"], "label": c["label"], "klass": c["klass"],
              "rules": len(c["rules"]), "domain": c["domain"]} for c in concepts]
    node_by = {n["id"]: n for n in nodes}
    links, seen = [], set()

    def add(s, t, kind, label, cf="", ct=""):
        if s == t:
            if s in node_by:
                node_by[s]["self"] = label
            return
        if s not in ids or t not in ids:
            return
        key = (s, t, kind)
        if key in seen:
            return
        seen.add(key)
        links.append({"source": s, "target": t, "kind": kind, "label": label,
                      "card_from": cf, "card_to": ct})

    for e in edges:
        add(e["from"], e["to"], "fk", e.get("role") or e.get("type") or "",
            e.get("card_from", ""), e.get("card_to", ""))
    for c in concepts:
        if c["members_over"]:
            add(c["id"], c["members_over"], "hierarchy", "rolls up to")
    rel_map = {}
    for c in concepts:
        for s in c["sources"]:
            if s["relation"]:
                rel_map.setdefault(s["relation"], []).append(c)
    for rel, cs in rel_map.items():
        if len(cs) < 2:
            continue
        anchor = None
        for pref in ("entity", "measure", "reference"):
            for c in cs:
                if c["klass"] == pref:
                    anchor = c
                    break
            if anchor:
                break
        anchor = anchor or cs[0]
        for c in cs:
            if c["id"] != anchor["id"]:
                add(c["id"], anchor["id"], "coground", "same relation")
    return {"nodes": nodes, "links": links}


def _rel_leaf(rel):
    """Reconcile a namespaced relation ('schema.dim_widget'), a bare name ('dim_widget') or a
    descriptor path ('data/datasets/dim_widget.yaml') to its bare table token, so a concept's
    grounding.sources relation reliably matches a dataset's table.name. Generic: strips any schema
    prefix and any path/extension; never hardcodes a schema name."""
    if not rel:
        return ""
    rel = str(rel)
    if "/" in rel or rel.endswith(".yaml") or rel.endswith(".yml"):
        rel = os.path.splitext(os.path.basename(rel))[0]
    return rel.split(".")[-1]


def parse_data_plane(root, concepts):
    """Project the served relations (datasets/views/dims, own-view measures, lookup registers) as
    first-class objects so the explorer can browse object<->data-source bindings BOTH ways. It reads
    root/data/{datasets,transforms,lookups} + root/data/manifest.yaml#resolver_score purely by
    CONVENTION (like the concepts/ and data/lookups walks already do); an absent data plane degrades
    to [] and the Data view self-hides. No source literals — paths and roles come from the data."""
    ddir, tdir, ldir = root / "data" / "datasets", root / "data" / "transforms", root / "data" / "lookups"
    manifest_p = root / "data" / "manifest.yaml"

    # reverse binding index: relation leaf -> [concept bindings]  (the discarded build_graph rel_map, kept)
    rev = {}
    for c in concepts:
        for s in c.get("sources", []) or []:
            leaf = _rel_leaf(s.get("relation"))
            if leaf:
                rev.setdefault(leaf, []).append({"id": c["id"], "label": c["label"], "klass": c["klass"],
                                                 "key": s.get("key", ""), "columns": s.get("columns", [])})
    # register reverse index: register name -> [concepts that read it]
    rev_reg = {}
    for c in concepts:
        for rg in c.get("registers", []) or []:
            nm = rg.get("register")
            if nm:
                rev_reg.setdefault(nm, []).append({"id": c["id"], "label": c["label"], "klass": c["klass"]})

    # transforms indexed by PRODUCED relation leaf. Deliberately match produces.relation and NOT the
    # dataset's derived_from.pipeline pointer — at least one descriptor points its pipeline at a sibling's
    # transform, so following the pointer would render the wrong lineage.
    tf = {}
    if tdir.is_dir():
        for tp in sorted(glob.glob(str(tdir / "*.yaml"))):
            try:
                td = yaml.safe_load(Path(tp).read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            prod = td.get("produces", {}) or {}
            leaf = _rel_leaf(prod.get("relation") or Path(tp).stem)
            inputs = [{"relation": i.get("relation", ""), "leaf": _rel_leaf(i.get("relation")),
                       "kind": i.get("kind", ""), "role": i.get("role", "")}
                      for i in (td.get("inputs", []) or []) if isinstance(i, dict)]
            steps = [{"id": s.get("id", ""), "impurity": s.get("impurity_class", ""),
                      "rule": (s.get("rule", "") or "").strip(),
                      "establishes": (s.get("establishes_guarantee", "") or "").strip()}
                     for s in (td.get("transforms", []) or []) if isinstance(s, dict)]
            tf[leaf] = {"grain": prod.get("grain", ""), "sql_file": prod.get("sql_file", ""),
                        "inputs": inputs, "steps": steps, "file": os.path.relpath(tp, root)}

    # manifest enrichment: resolver role (for rail grouping) + own-view measure semantics (non-additivity etc.)
    role_of, mv_meta = {}, {}
    if manifest_p.exists():
        try:
            rs = (yaml.safe_load(manifest_p.read_text(encoding="utf-8")) or {}).get("resolver_score", {}) or {}
            fact = rs.get("fact", {}) or {}
            if fact.get("descriptor"):
                role_of[_rel_leaf(fact["descriptor"])] = "fact"
            for d in (rs.get("dims", []) or []):
                if isinstance(d, dict) and d.get("descriptor"):
                    role_of[_rel_leaf(d["descriptor"])] = "dimension"
            serving = (rs.get("regions") or {}).get("serving") or {}
            for k in ("rollup", "membership"):
                if serving.get(k):
                    role_of[_rel_leaf(serving[k])] = "region view"
            for stem, mv in (rs.get("measure_views", {}) or {}).items():
                if not isinstance(mv, dict):
                    continue
                leaf = _rel_leaf(mv.get("relation", ""))
                if not leaf:
                    continue
                role_of[leaf] = "measure view"
                mv_meta[leaf] = dict({"stem": stem}, **{k: mv[k] for k in (
                    "non_additive", "measure_type", "level_col", "default_level", "latest", "geo_col",
                    "region_col", "family_col", "measure_col", "measure_cols", "variants") if k in mv})
        except Exception:
            pass

    relations = []
    if ddir.is_dir():
        for dp in sorted(glob.glob(str(ddir / "*.yaml"))):
            try:
                dd = yaml.safe_load(Path(dp).read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            tbl, meta = dd.get("table", {}) or {}, dd.get("metadata", {}) or {}
            name = tbl.get("name") or Path(dp).stem
            leaf = _rel_leaf(name)
            cols = [{"name": co.get("name", ""), "type": co.get("type", ""), "role": co.get("role", ""),
                     "confidence": co.get("confidence", "")}
                    for co in (dd.get("columns", []) or []) if isinstance(co, dict)]
            fwd, revj = [], []
            for fk in (dd.get("foreign_keys", []) or []):
                if not isinstance(fk, dict):
                    continue
                edge = {"from_column": fk.get("from_column", ""), "to_table": _rel_leaf(fk.get("to_table")),
                        "to_column": fk.get("to_column", ""), "notes": (fk.get("notes", "") or "").strip()}
                (revj if re.search(r"reverse", edge["notes"], re.I) else fwd).append(edge)
            relations.append({
                "name": name, "leaf": leaf, "schema": tbl.get("schema", ""), "type": tbl.get("type", ""),
                "status": meta.get("status", ""), "confidence": tbl.get("confidence", ""),
                "group": role_of.get(leaf, "view"), "grain": (tf.get(leaf) or {}).get("grain", ""),
                "columns": cols, "foreign_keys": fwd, "reverse_joins": revj,
                "lineage": tf.get(leaf, {}), "measure_view": mv_meta.get(leaf, {}),
                "bound_concepts": rev.get(leaf, []), "file": os.path.relpath(dp, root)})

    if ldir.is_dir():
        for lp in sorted(glob.glob(str(ldir / "*.lookup.csv"))):
            try:
                rows = list(csv.reader(Path(lp).open(newline="", encoding="utf-8")))
            except Exception:
                continue
            if not rows:
                continue
            regname = os.path.basename(lp)[:-4]  # strip .csv -> e.g. 'measures.lookup'
            relations.append({
                "name": regname, "leaf": regname, "schema": "", "type": "register",  # full name IS the id; _rel_leaf('brands.lookup')->'lookup' would collide ALL *.lookup registers onto one node/pos key
                "status": "register", "confidence": "", "group": "registers", "grain": "",
                "columns": [{"name": h, "type": "", "role": "", "confidence": ""} for h in rows[0]],
                "foreign_keys": [], "reverse_joins": [], "lineage": {}, "measure_view": {},
                "rowcount": len(rows) - 1, "sample": rows[1:6],
                "bound_concepts": rev_reg.get(regname, []), "file": os.path.relpath(lp, root)})
    return relations


def load_manual(root):
    """Optional source-authored operator manual (markdown), rendered as a Manual tab. Convention-only:
    the first of these paths that exists wins; absent -> the tab self-hides. Generic across sources."""
    for cand in ("docs/manual.md", "docs/ontology_manual.md", "MANUAL.md"):
        p = root / cand
        if p.exists():
            try:
                return {"markdown": p.read_text(encoding="utf-8"), "file": cand}
            except Exception:
                return None
    return None


def build_model(root):
    cdir = concepts_dir(root)
    if not cdir:
        sys.exit("mac_to_explorer: no concepts/ dir under %s" % root)
    files = sorted(glob.glob(str(cdir / "**" / "*.yaml"), recursive=True))
    lookups = root / "data" / "lookups"
    lookups = lookups if lookups.is_dir() else None

    concepts = [parse_concept(p, lookups, cdir) for p in files]

    # source name from metadata.source (first that declares one) -> branding + output filename
    source = "MAC"
    for p in files:
        d = yaml.safe_load(Path(p).read_text(encoding="utf-8")) or {}
        s = (d.get("metadata") or {}).get("source")
        if s:
            source = str(s)
            break

    # domains derived dynamically, ordered by first appearance in the sorted file walk
    domains = []
    for c in concepts:
        if c["domain"] not in domains:
            domains.append(c["domain"])
    concepts.sort(key=lambda c: (domains.index(c["domain"]), c["label"]))

    edges = parse_edges(root)
    general, policy = parse_query_rules(root)
    derived = parse_rules(root)

    lanes = {"ASK": 0, "COMMIT": 0, "REFUSE": 0, "INVARIANT": 0, "OTHER": 0}
    for c in concepts:
        for r in c["rules"]:
            lanes[r["decision"]] += 1
    for r in general:
        lanes[r["decision"]] += 1

    preferred = ["metadata", "concept", "identity", "members", "values", "grounding",
                 "contract", "edges", "governance", "open_questions"]
    seen = []
    for c in concepts:
        for s in c["slots_present"]:
            if s not in seen:
                seen.append(s)
    slots = [s for s in preferred if s in seen] + [s for s in seen if s not in preferred]

    return {
        "meta": {"source": source, "concept_count": len(concepts),
                 "rule_count": sum(len(c["rules"]) for c in concepts) + len(general),
                 "edge_count": len(edges), "general_rule_count": len(general),
                 "derived_count": len(derived)},
        "domains": domains, "lanes": lanes, "slots": slots,
        "concepts": concepts, "edges": edges, "graph": build_graph(concepts, edges),
        "general_rules": general, "decision_policy": policy, "derived_measures": derived,
        # additive: the data plane (relations the concepts bind to) + an optional operator manual.
        # Both self-hide when absent, so a source with no data/ plane renders exactly as before.
        "relations": parse_data_plane(root, concepts),
        "manual": load_manual(root),
    }


def main():
    ap = argparse.ArgumentParser(description="Project a MAC ontology onto a self-contained HTML explorer.")
    ap.add_argument("root", help="ontology project root (contains ontology/concepts/ or concepts/)")
    ap.add_argument("-o", "--out", help="output .html path (default: <root>/projections/<name>.explorer.html)")
    ap.add_argument("--ask-base", default="",
                    help="origin for the explorer's '/ask' cross-link when it is opened as a local file, "
                         "e.g. http://localhost:8000 . When the explorer is instead SERVED over http(s) a "
                         "port-agnostic relative link (ask.html?src=<source>) is always used; this base is "
                         "only the file:// fallback. Empty (default) -> the link appears only when served.")
    a = ap.parse_args()

    root = Path(a.root).resolve()
    model = build_model(root)
    name = model["meta"]["source"].lower()
    out = Path(a.out) if a.out else (root / "projections" / (name + ".explorer.html"))
    out.parent.mkdir(parents=True, exist_ok=True)

    if not TEMPLATE.exists():
        sys.exit("mac_to_explorer: template not found at %s" % TEMPLATE)
    tpl = TEMPLATE.read_text(encoding="utf-8")
    # inject the shared graph engine verbatim into its marker (same IIFE scope as before)
    tpl = tpl.replace("/*__GRAPH_ENGINE__*/", (HERE / "graph_engine.js").read_text(encoding="utf-8"))
    # inject the /ask base FIRST, on the model-free template, so nothing in the model JSON can collide
    tpl = tpl.replace("/*__ASK_BASE__*/", (a.ask_base or "").strip().replace("\\", "\\\\").replace('"', '\\"'))
    data = json.dumps(model, ensure_ascii=False).replace("</", "<\\/")
    out.write_text(tpl.replace("/*__MODEL_JSON__*/null", data), encoding="utf-8")

    sys.stderr.write("mac_to_explorer: %s — %d concepts, %d rules, %d derived, %d edges, %d relations, manual=%s; lanes=%s -> %s\n" % (
        model["meta"]["source"], model["meta"]["concept_count"], model["meta"]["rule_count"],
        model["meta"]["derived_count"], model["meta"]["edge_count"], len(model.get("relations") or []),
        "yes" if model.get("manual") else "no", model["lanes"], out))


if __name__ == "__main__":
    main()
