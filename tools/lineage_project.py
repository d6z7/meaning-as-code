#!/usr/bin/env python3
"""
lineage_project.py — project the MAC data plane onto a COLUMN-LEVEL lineage model (offline).

A data-plane sibling of the model/mermaid projectors. Where mac_to_mermaid --lineage draws TABLE-level
production flow (source -> transform -> dataset), this descends one level deeper: it reads each
TransformFile's `inputs[].consumes` map ({src_col: rule_id}) plus each rule's `.sql` fragment and resolves
every (src_col, rule) into a COLUMN edge classified by a CLOSED 9-kind vocabulary:

    passthrough · transform(cast) · rename · reshape(wide->long) · union(multi-source) · seed · const · filter · open

It is a PROJECTION of the governed descriptors, not a parse of the warehouse: it reads YAML descriptors only
(data/sources, data/transforms, data/datasets) — NO warehouse / DB / network call. The emitted model
{flows[], datasets[], ontology[]} is the contract in specs/column-lineage-er-spike/blueprint.md §1; the
frozen golden lineage_model.sample.json (3 flows) is the conformance fixture.

Usage:
  python3 tools/lineage_project.py [roots...] [--check <golden.json>] [--out <path>]

  (no args)         emit the aggregated model for the default sibling roots to stdout
  --out <path>      write the aggregated full model (all FPL+HIFA flows) as JSON
  --check <golden>  emit ONLY the 3 golden flows and compare to <golden> on the 5-key edge subset
                    {src_table,src_col,to_col,rule_id,kind} + kinds + predicates + derived. HARD-HALT
                    (exit 1) if the 3 golden flows do not conform.

Default roots (relative to CWD): ../cap-ontology-fpl ../cap-ontology-hifa
"""
import argparse
import json
import re
import sys
from pathlib import Path

import yaml
from mac_project import resolve

MIDDOT = "·"
ELLIPSIS = "…"

# The closed edge-kind vocabulary (H2). An edge kind outside this set is a hard error.
CLOSED_KINDS = {"passthrough", "transform", "rename", "reshape", "union", "seed", "const", "filter", "open"}
DERIVED_KINDS = {"seed", "const"}

DEFAULT_ROOTS = ["../cap-ontology-fpl", "../cap-ontology-hifa"]

# The 3 golden flows (by produced relation) — the frozen conformance set.
GOLDEN_TRANSFORMS = [
    "fpl.v_fpl_ob_reach_current",
    "hifa.v_hifa_checkpoint_events",
    "hifa.v_hifa_kpi_scheduling",
]


# ── helpers ─────────────────────────────────────────────────────────────────────────────────────────────
def load(p):
    return yaml.safe_load(Path(p).read_text()) or {}


def bare(rel):
    return str(rel or "").split(".")[-1]


def seed_name(rel):
    """Seed display name: a path -> its basename (dim_checkpoint.lookup.csv); a relation -> as-is (hifa.dim_kpi)."""
    rel = str(rel or "")
    return Path(rel).name if "/" in rel else rel


def resolve_to_col(src_col, sql):
    """Resolve the OUTPUT column a (src_col, rule.sql) maps to, and whether the .sql confirms it.

    Handles the `ch_<N>` representative convention: a consumed `ch_1` whose rule sql writes `ch_<N> AS actual_ts`
    resolves via the digit-run template `ch_<N>`. Returns (to_col, sql_confirmed)."""
    sql = sql or ""
    # cast(<col> AS <type>) keeps the name (a retype, not a rename)
    if re.search(r"cast\(\s*" + re.escape(src_col) + r"\s+as\s", sql, re.I):
        return src_col, True
    # <col> AS <name>
    m = re.search(r"\b" + re.escape(src_col) + r"\s+AS\s+(\w+)", sql, re.I)
    if m:
        return m.group(1), True
    # templated ch_<N> slot -> collapse only the LEADING checkpoint index, never a digit inside a suffix
    # (ch_1 -> ch_<N>; ch_1_eta_first -> ch_<N>_eta_first; ch_1_eta_zp8 -> ch_<N>_eta_zp8, NOT ch_<N>_eta_zp<N>)
    tmpl = re.sub(r"^(ch_)\d+", r"\1<N>", src_col)
    if tmpl != src_col:
        m = re.search(re.escape(tmpl) + r"\s+AS\s+(\w+)", sql, re.I)
        if m:
            return m.group(1), True
    return src_col, False


def classify(src_col, rule, is_open, is_union):
    """Assign one of the closed 9 kinds to a (src_col, rule) IN THE SPECIFIED ORDER.

    Returns "filter" for a WHERE predicate (caller routes it to predicates[], not edges[])."""
    sql = "" if is_open else (rule.get("sql") or "")
    imp = str(rule.get("impurity_class") or "")
    rid = str(rule.get("id") or "")
    # (1) filter — rule sql starts WHERE  -> a predicate, no column edge
    if sql.strip().lower().startswith("where"):
        return "filter"
    # (2) open — rule came from open_transforms[] (PROPOSED, sql null) -> carry, flagged
    if is_open:
        return "open"
    # (3) transform — cast(<col> AS <type>)
    if re.search(r"cast\(\s*" + re.escape(src_col) + r"\s+as\s", sql, re.I):
        return "transform"
    # (4) union — >1 raw-source branches share the consumes shape (overrides rename/passthrough)
    if is_union:
        return "union"
    # (5) reshape — a bare ch_<N> wide slot under a wide_*/unpivot rule (many->few)
    if re.fullmatch(r"ch_\d+", src_col) and (imp.startswith("wide") or "unpivot" in rid):
        return "reshape"
    # (6) rename — <col> AS <name>, name != col
    to_col, _ = resolve_to_col(src_col, sql)
    if to_col != src_col:
        return "rename"
    # (7) passthrough — bare identity
    return "passthrough"


def provenance(kind, sql_confirmed):
    """descriptor_only for open rules + bare passthroughs; sql_confirmed when the .sql names the mapping."""
    if kind in ("open", "passthrough"):
        return "descriptor_only"
    return "sql_confirmed" if sql_confirmed else "descriptor_only"


# ── gather ──────────────────────────────────────────────────────────────────────────────────────────────
def gather(root):
    """Read a source's data plane offline: (sys, transforms[], sources{name:doc}, datasets{name:doc}, concepts[])."""
    L = resolve(root)
    sources, datasets, transforms, concepts = {}, {}, [], []
    if getattr(L, "descriptors", None) and L.descriptors.exists():
        for f in sorted(L.descriptors.glob("*.yaml")):
            d = load(f)
            t = (d.get("table") or {})
            if t.get("name"):
                datasets[t["name"]] = d
    if getattr(L, "sources", None) and L.sources.exists():
        for f in sorted(L.sources.glob("*.yaml")):
            d = load(f)
            t = (d.get("table") or {})
            if t.get("name"):
                sources[t["name"]] = d
    if getattr(L, "transforms", None) and L.transforms.exists():
        for f in sorted(L.transforms.glob("*.yaml")):
            d = load(f)
            if d.get("produces"):
                transforms.append(d)
    cdir = L.ontology / "concepts"
    if cdir.exists():
        for f in sorted(cdir.glob("**/*.yaml")):
            d = load(f)
            if (d.get("concept") or {}).get("name"):
                concepts.append((f.relative_to(cdir).with_suffix("").as_posix(), d))
    return sources, datasets, transforms, concepts


def concept_ids_for(relation, concepts):
    """Concept ids (path under concepts/, minus .yaml) whose grounding binds to `relation`."""
    rel, rbare = str(relation), bare(relation)
    out = []
    for cid, d in concepts:
        g = d.get("grounding") or {}
        rels = set()
        if isinstance(g.get("table"), str):
            rels.add(g["table"])
        for s in (g.get("sources") or []):
            if isinstance(s, dict) and s.get("relation"):
                rels.add(str(s["relation"]))
        if rel in rels or rbare in {bare(r) for r in rels}:
            out.append(cid)
    return out


# ── flow builder ────────────────────────────────────────────────────────────────────────────────────────
def build_flow(tf, sources, datasets, concepts, unclassifiable):
    md = tf.get("metadata") or {}
    produces = tf.get("produces") or {}
    produced = produces.get("relation", "")
    sysname = str(md.get("source") or "").upper()
    view_short = bare(produced)

    applied = {t["id"]: t for t in (tf.get("transforms") or []) if isinstance(t, dict) and t.get("id")}
    opens = {o["id"]: o for o in (tf.get("open_transforms") or []) if isinstance(o, dict) and o.get("id")}

    def rule_lookup(rid):
        if rid in applied:
            return applied[rid], False
        if rid in opens:
            return opens[rid], True
        return None, None

    inputs = tf.get("inputs") or []
    raw_inputs = [i for i in inputs if (i.get("kind") == "raw_source")]
    seed_inputs = [i for i in inputs if (i.get("kind") != "raw_source")]

    # union = >1 raw-source branch sharing the same consumes key-set
    consume_shapes = [tuple(sorted((i.get("consumes") or {}).keys())) for i in raw_inputs]
    is_union = len(raw_inputs) > 1 and len(set(consume_shapes)) == 1

    dcols = [c for c in ((datasets.get(view_short) or {}).get("columns") or []) if isinstance(c, dict) and c.get("name")]
    dcol_out = [{"name": c["name"], "type": c.get("type"), "role": c.get("role")} for c in dcols]
    dcol_names = {c["name"] for c in dcols}

    edges, predicates, sources_out, produced_cols = [], [], [], set()

    for inp in raw_inputs:
        srel = inp.get("relation", "")
        sshort = bare(srel)
        sdoc = sources.get(sshort) or {}
        stable = sdoc.get("table") or {}
        scols = [c for c in (sdoc.get("columns") or []) if isinstance(c, dict) and c.get("name")]
        scol_names = [c["name"] for c in scols]
        n_reshape = sum(1 for n in scol_names if re.fullmatch(r"ch_\d+", n))
        total_cols = len(scol_names)
        consumes = inp.get("consumes") or {}
        display, actual = [], 0

        for src_col, rid_raw in consumes.items():
            # a col may be read by ONE rule (scalar) or several (list) — one edge per (src_col, rule);
            # the col is shown / counted ONCE regardless of how many rules read it.
            rids = rid_raw if isinstance(rid_raw, list) else [rid_raw]
            col_shown = False
            for rid in rids:
                rule, is_open = rule_lookup(rid)
                if rule is None:
                    unclassifiable.append((produced, src_col, rid, "rule not found"))
                    continue
                kind = classify(src_col, rule, is_open, is_union)
                sql = "" if is_open else (rule.get("sql") or "")
                if kind == "filter":
                    predicates.append({"rule_id": rid, "from_table": sshort, "from_col": src_col, "sql": rule.get("sql")})
                    if not col_shown:
                        display.append({"name": src_col, "badge": None}); actual += 1; col_shown = True
                    continue
                to_col, sql_ok = resolve_to_col(src_col, sql)
                if kind == "reshape":
                    shown = f"{src_col} {ELLIPSIS} ch_{n_reshape}"
                    edges.append({"src_table": sshort, "src_col": shown, "to_col": to_col, "rule_id": rid,
                                  "kind": kind, "provenance": provenance(kind, sql_ok)})
                    if not col_shown:
                        display.append({"name": shown, "badge": str(n_reshape)}); actual += n_reshape; col_shown = True
                else:
                    edges.append({"src_table": sshort, "src_col": src_col, "to_col": to_col, "rule_id": rid,
                                  "kind": kind, "provenance": provenance(kind, sql_ok)})
                    if not col_shown:
                        display.append({"name": src_col, "badge": None}); actual += 1; col_shown = True
                produced_cols.add(to_col)

        # bare passthroughs — a source column NOT consumed but present in the dataset, carried unchanged
        for name in scol_names:
            if name in consumes or name not in dcol_names or name in produced_cols:
                continue
            edges.append({"src_table": sshort, "src_col": name, "to_col": name, "rule_id": None,
                          "kind": "passthrough", "provenance": "descriptor_only"})
            produced_cols.add(name)
            display.append({"name": name, "badge": None})
            actual += 1

        sources_out.append({"rel": srel, "short": sshort, "schema": stable.get("schema"),
                            "columns": display, "extra": max(0, total_cols - actual), "role": inp.get("role")})

    # derived — dataset columns with no incoming raw-source edge (seed if a branch_map is present, else const)
    branch_map = next((s for s in seed_inputs if s.get("role") == "branch_map"), None)
    derived = []
    for c in dcols:
        if c["name"] in produced_cols:
            continue
        if branch_map is not None:
            derived.append({"to_col": c["name"], "via": seed_name(branch_map.get("relation")), "kind": "seed"})
        else:
            derived.append({"to_col": c["name"], "via": "literal per branch", "kind": "const"})

    seeds = [{"name": seed_name(s.get("relation")), "role": s.get("role"), "note": (s.get("note") or "")[:150]}
             for s in seed_inputs]

    rules = []
    for t in (tf.get("transforms") or []):
        if not (isinstance(t, dict) and t.get("id")):
            continue
        rules.append({"id": t["id"], "impurity": t.get("impurity_class"), "sql": t.get("sql"),
                      "rule": t.get("rule"), "guarantee": t.get("establishes_guarantee"),
                      "status": t.get("status"), "open": False})
    for o in (tf.get("open_transforms") or []):
        if not (isinstance(o, dict) and o.get("id")):
            continue
        rules.append({"id": o["id"], "impurity": o.get("impurity_class"), "sql": None,
                      "rule": o.get("proposed_rule"), "guarantee": o.get("raw_defect"),
                      "status": o.get("status"), "open": True})

    kinds_here = sorted({e["kind"] for e in edges} | {d["kind"] for d in derived} | ({"filter"} if predicates else set()))
    kindl = (" " + MIDDOT + " ").join(kinds_here)

    dataset = {"name": produced, "columns": dcol_out}
    flow = {
        "id": f"{sysname} {MIDDOT} {view_short}",
        "sys": sysname,
        "kindl": kindl,
        "transform": produced,
        "grain": produces.get("grain"),
        "sources": sources_out,
        "dataset": dataset,
        "rules": rules,
        "edges": edges,
        "predicates": predicates,
        "derived": derived,
        "seeds": seeds,
    }
    return flow


def project(roots):
    flows, ds_out, onto_out = [], [], []
    unclassifiable = []
    for root in roots:
        if not Path(root).exists():
            continue
        sources, datasets, transforms, concepts = gather(root)
        for tf in transforms:
            flow = build_flow(tf, sources, datasets, concepts, unclassifiable)
            flows.append(flow)
            ds_out.append({"name": flow["dataset"]["name"], "columns": flow["dataset"]["columns"],
                           "sys": flow["sys"], "grain": flow["grain"]})
            onto_out.append({"dataset": flow["transform"], "sys": flow["sys"],
                             "concepts": concept_ids_for(flow["transform"], concepts)})
    model = {"flows": flows, "datasets": ds_out, "ontology": onto_out}
    return model, unclassifiable


# ── golden conformance ──────────────────────────────────────────────────────────────────────────────────
EDGE_KEYS = ("src_table", "src_col", "to_col", "rule_id", "kind")


def _edge5(e):
    return {k: e.get(k) for k in EDGE_KEYS}


def _sortkey(d):
    return json.dumps(d, sort_keys=True, ensure_ascii=False)


def compare_flow(got, want):
    """Compare one flow to the golden on the gated subset: 5-key edges + predicates + derived (order-insensitive)."""
    diffs = []
    ge = sorted((_edge5(e) for e in got.get("edges", [])), key=_sortkey)
    we = sorted((_edge5(e) for e in want.get("edges", [])), key=_sortkey)
    if ge != we:
        diffs.append("edges")
        gset, wset = {_sortkey(e) for e in ge}, {_sortkey(e) for e in we}
        for x in sorted(wset - gset):
            diffs.append("   MISSING " + x)
        for x in sorted(gset - wset):
            diffs.append("   EXTRA   " + x)
    gp = sorted((dict(p) for p in got.get("predicates", [])), key=_sortkey)
    wp = sorted((dict(p) for p in want.get("predicates", [])), key=_sortkey)
    if gp != wp:
        diffs.append("predicates")
        diffs.append("   got=" + _sortkey(gp) + " want=" + _sortkey(wp))
    gd = sorted((dict(d) for d in got.get("derived", [])), key=_sortkey)
    wd = sorted((dict(d) for d in want.get("derived", [])), key=_sortkey)
    if gd != wd:
        diffs.append("derived")
        diffs.append("   got=" + _sortkey(gd) + " want=" + _sortkey(wd))
    return diffs


def run_check(roots, golden_path):
    golden = json.load(open(golden_path))
    want_by_tf = {f["transform"]: f for f in golden["flows"]}
    model, unclassifiable = project(roots)
    got_by_tf = {f["transform"]: f for f in model["flows"]}

    ok = True
    print(f"lineage_project --check against {golden_path}")
    print(f"  projected {len(model['flows'])} flows across roots; comparing the {len(GOLDEN_TRANSFORMS)} golden flows\n")
    for tf in GOLDEN_TRANSFORMS:
        want = want_by_tf.get(tf)
        got = got_by_tf.get(tf)
        if want is None:
            print(f"  [SKIP] {tf}: not in golden"); continue
        if got is None:
            print(f"  [FAIL] {tf}: NOT PRODUCED by projector"); ok = False; continue
        diffs = compare_flow(got, want)
        # golden flows must contribute no unclassifiable edges
        gaps = [u for u in unclassifiable if u[0] == tf]
        if gaps:
            diffs.append(f"unclassifiable: {gaps}")
        if diffs:
            ok = False
            print(f"  [FAIL] {tf}")
            for d in diffs:
                print("      " + d)
        else:
            ne = len(got.get("edges", []))
            npd = len(got.get("predicates", []))
            nde = len(got.get("derived", []))
            print(f"  [ OK ] {tf}  ({ne} edges, {npd} predicate(s), {nde} derived)")
    print()
    if ok:
        print("CONFORMS: all 3 golden flows match the golden on {5-key edges, predicates, derived}.")
        return 0
    print("DOES NOT CONFORM — golden mismatch. HARD HALT.")
    return 1


# ── main ────────────────────────────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Project the MAC data plane onto a column-level lineage model (offline).")
    ap.add_argument("roots", nargs="*", help="source repo roots (default: ../cap-ontology-fpl ../cap-ontology-hifa)")
    ap.add_argument("--check", metavar="GOLDEN", help="compare the 3 golden flows to GOLDEN and HARD-HALT on mismatch")
    ap.add_argument("--out", metavar="PATH", help="write the aggregated full model JSON")
    a = ap.parse_args()
    roots = a.roots or DEFAULT_ROOTS

    if a.check:
        sys.exit(run_check(roots, a.check))

    model, unclassifiable = project(roots)
    # closed-vocabulary hard gate: every emitted kind must be in the closed set
    bad = [(f["transform"], e) for f in model["flows"] for e in f["edges"] if e["kind"] not in CLOSED_KINDS]
    bad += [(f["transform"], d) for f in model["flows"] for d in f["derived"] if d["kind"] not in DERIVED_KINDS]
    if bad:
        print(f"ERROR: {len(bad)} edge(s) outside the closed kind vocabulary: {bad[:5]}", file=sys.stderr)
        sys.exit(1)

    text = json.dumps(model, ensure_ascii=False, indent=2)
    if a.out:
        outp = Path(a.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(text + "\n")
        kinds = sorted({e["kind"] for f in model["flows"] for e in f["edges"]}
                       | {d["kind"] for f in model["flows"] for d in f["derived"]})
        print(f"wrote {a.out}: {len(model['flows'])} flows, kinds={kinds}, unclassifiable={len(unclassifiable)}")
        if unclassifiable:
            for u in unclassifiable:
                print(f"  [unclassifiable] {u}", file=sys.stderr)
    else:
        sys.stdout.write(text + "\n")


if __name__ == "__main__":
    main()
