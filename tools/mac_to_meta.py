#!/usr/bin/env python3
"""mac_to_meta — reflect a `model.introspection.json` into flat `meta_*` tables + Athena DDL.

The meaning-plane twin of the data warehouse (epic #85, A1). It reads the model's self-description
(A0's projection) and emits one NDJSON table per section, plus `CREATE EXTERNAL TABLE` DDL — so an
introspection question ("what measures / dimensions / regions / rules exist", "countries in VW's VE")
runs as deterministic SQL over the model STRUCTURE, never LLM-authored.

Generic: names no source; a section that is absent/empty yields an empty table. NDJSON is Athena-native
(JSON SerDe) and loads straight into SQLite/DuckDB for offline validation.

  usage:  python3 tools/mac_to_meta.py <model.introspection.json> --out-dir DIR
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _j(x):
    """Nested value → compact JSON string (Athena reads it as a string col; SQLite json_extract works)."""
    return None if x is None else json.dumps(x, ensure_ascii=False, sort_keys=True)


# --- table extractors: introspection dict -> list[row dict]. One per meta_* table. ------------------

def t_measures(d):
    for m in d.get("measures", []):
        add = m.get("additivity") or {}
        yield {"measure": m.get("measure"), "stem": m.get("stem"), "source_kind": m.get("source_kind"),
               "measure_type": m.get("measure_type"), "type": m.get("type"),
               "additivity_time": add.get("time"), "additivity_categorical": add.get("categorical"),
               "closure": m.get("closure"), "grounds_relation": m.get("grounds_relation"),
               "realized_from": m.get("realized_from"), "definition": m.get("definition"),
               "kpi_codes": _j(m.get("kpi_codes")), "surface": _j(m.get("surface")),
               "axis_kinds": _j(m.get("axis_kinds"))}


def t_kpi_variants(d):
    defaults = {v.get("variant"): v.get("default") for v in (d.get("kpi_variants", {}).get("values") or [])}
    for m in d.get("measures", []):
        for code in (m.get("kpi_codes") or []):
            variant = code.split(".")[-1] if "." in code else None
            yield {"stem": m.get("stem"), "kpi_code": code, "variant": variant,
                   "suffix": f".{variant}" if variant else None,
                   "is_default": bool(defaults.get(variant, False))}


def t_dimensions(d):
    for dim in d.get("dimensions", []):
        ident = dim.get("identity") or {}
        yield {"dimension": dim.get("dimension"), "concept": dim.get("concept"),
               "grain": dim.get("grain"), "identity_kind": ident.get("kind"),
               "canonical_key": ident.get("canonical_key"), "realized_from": dim.get("realized_from"),
               "cardinality": _j(dim.get("cardinality"))}


def t_brand_members(d):
    for dim in d.get("dimensions", []):
        for mem in (dim.get("members") or []):
            yield {"dimension": dim.get("dimension"), "cluster_code": mem.get("code"),
                   "brand": mem.get("brand"), "multi_brand": mem.get("multi_brand"),
                   "in_fact_data": mem.get("in_fact_data"), "confidence": mem.get("confidence")}


def t_region_definitions(d):
    for r in d.get("region_definitions", []):
        yield {**{k: r.get(k) for k in ("region_definition_used", "namespace", "code", "brand", "label",
                                        "member_count", "member_kind", "confidence", "brand_relative")},
               "collides_with": _j(r.get("collides_with"))}


def t_region_members(d):
    for m in d.get("region_members", []):
        yield {k: m.get(k) for k in ("region_definition_used", "namespace", "code", "member",
                                     "member_kind", "iso2", "fpl_brand_country_code")}


def t_rules(d):
    for r in d.get("rules", {}).get("catalog", []):
        home = r.get("home") or {}
        yield {"rule_id": r.get("id"), "family": r.get("family"), "kind_term": r.get("kind_term"),
               "scope": r.get("scope"), "subject": r.get("subject"), "when_text": r.get("when"),
               "then_text": r.get("then"), "never_text": r.get("never"), "confidence": r.get("confidence"),
               "home_file": home.get("file"), "home_concept": home.get("concept")}


def t_rule_refs(d):
    for r in d.get("rules", {}).get("catalog", []):
        for kind in ("binds", "over", "refs", "validated_against", "applies_from", "cited_by"):
            for v in (r.get(kind) or []):
                yield {"rule_id": r.get("id"), "ref_kind": kind, "ref_value": v}


def t_decision_policy(d):
    for s in d.get("rules", {}).get("decision_policy", {}).get("slots", []):
        yield {"slot": s.get("slot"), "policy": s.get("policy"), "governing_rule": s.get("governing_rule"),
               "rule_id": s.get("rule_id"), "on_missing": s.get("on_missing")}


def t_rule_kinds(d):
    for k in d.get("rules", {}).get("kinds", []):
        yield {"term": k.get("term"), "governs": k.get("governs"), "closed": k.get("closed")}


def t_edges(d):
    for e in d.get("edges", []):
        fr, to = e.get("from") or {}, e.get("to") or {}
        rb = e.get("realized_by") or {}
        yield {"edge_id": e.get("edge_id"), "level": e.get("level"), "type": e.get("type"),
               "from_concept": fr.get("concept"), "to_concept": to.get("concept"),
               "cardinality": e.get("cardinality"), "join_rule": e.get("join_rule"),
               "realized_by_register": rb.get("via_register") if isinstance(rb, dict) else None,
               "verified_by": _j(e.get("verified_by")), "confidence": e.get("confidence")}


def t_edge_join_clauses(d):
    for e in d.get("edges", []):
        for i, c in enumerate((e.get("join") or {}).get("clauses") or []):
            lt, rt = c.get("left") or {}, c.get("right") or {}
            yield {"edge_id": e.get("edge_id"), "ordinal": i,
                   "left_relation": lt.get("relation"), "left_column": lt.get("column"),
                   "right_relation": rt.get("relation"), "right_column": rt.get("column")}


def t_provenance(d):
    meta = d.get("meta") or {}
    for inp in (meta.get("inputs") or []):
        yield {"source": meta.get("source"), "mac_version": meta.get("mac_version"),
               "schema_version": meta.get("schema_version"), "input_path": inp.get("path"),
               "input_sha256": inp.get("sha256")}


TABLES = {
    "meta_measures": t_measures, "meta_kpi_variants": t_kpi_variants, "meta_dimensions": t_dimensions,
    "meta_brand_members": t_brand_members, "meta_region_definitions": t_region_definitions,
    "meta_region_members": t_region_members, "meta_rules": t_rules, "meta_rule_refs": t_rule_refs,
    "meta_decision_policy": t_decision_policy, "meta_rule_kinds": t_rule_kinds, "meta_edges": t_edges,
    "meta_edge_join_clauses": t_edge_join_clauses, "meta_provenance": t_provenance,
}


def reflect(introspection: dict):
    """{table_name: [row, …]} for every meta_* table. Empty list when the section is absent."""
    return {name: list(fn(introspection)) for name, fn in TABLES.items()}


def athena_ddl(tables: dict, db: str = "meaning", s3: str = "s3://<bucket>/meta/") -> str:
    """CREATE EXTERNAL TABLE DDL (JSON SerDe). All columns string — the meaning plane is descriptive;
    numeric casts happen in the query. A source-agnostic, deploy-time artifact."""
    out = []
    for name, rows in tables.items():
        cols = sorted({k for r in rows for k in r.keys()}) or ["_empty"]
        coldefs = ",\n  ".join(f"`{c}` string" for c in cols)
        out.append(f"CREATE EXTERNAL TABLE IF NOT EXISTS {db}.{name} (\n  {coldefs}\n)\n"
                   f"ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'\n"
                   f"LOCATION '{s3}{name}/';")
    return "\n\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("introspection")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    d = json.loads(Path(args.introspection).read_text(encoding="utf-8"))
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tables = reflect(d)

    for name, rows in tables.items():
        (out / f"{name}.ndjson").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    (out / "meta_tables.ddl.sql").write_text(athena_ddl(tables), encoding="utf-8")

    print(f"reflected {d.get('meta', {}).get('source', '?')}: "
          + " ".join(f"{n}={len(r)}" for n, r in tables.items()) + f" → {out}")


if __name__ == "__main__":
    sys.exit(main())
