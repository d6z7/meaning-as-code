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


_MAC_VOCAB = Path(__file__).resolve().parent.parent / "mac_vocabulary.yaml"


def _framework_schema_version(default: str = "0.1.13") -> str:
    """The MAC framework's CURRENT schema version, read generically from mac_vocabulary.yaml
    (metadata.version) — the same source validate_schema.py's CURRENT tracks and the version pre-flight
    gate enforces. Generated meta concepts declare it so they are gated (not silently skipped). Falls
    back to `default` if the vocab is absent/unreadable, so emit never crashes offline."""
    try:
        import yaml
        doc = yaml.safe_load(_MAC_VOCAB.read_text(encoding="utf-8")) or {}
        v = (doc.get("metadata") or {}).get("version")
        return str(v) if v else default
    except Exception:
        return default


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


def t_enum(d):
    """Enum value domains (body types, fuel classes, segments, platforms) — one row per (concept, value)."""
    for dim in d.get("dimensions", []):
        for v in (dim.get("enum_values") or []):
            yield {"concept": dim.get("dimension"), "value": v.get("value"), "label": v.get("label")}


TABLES = {
    "meta_measures": t_measures, "meta_kpi_variants": t_kpi_variants, "meta_dimensions": t_dimensions,
    "meta_brand_members": t_brand_members, "meta_region_definitions": t_region_definitions,
    "meta_region_members": t_region_members, "meta_enum": t_enum, "meta_rules": t_rules,
    "meta_rule_refs": t_rule_refs, "meta_decision_policy": t_decision_policy, "meta_rule_kinds": t_rule_kinds,
    "meta_edges": t_edges, "meta_edge_join_clauses": t_edge_join_clauses, "meta_provenance": t_provenance,
}


def reflect(introspection: dict):
    """{table_name: [row, …]} for every meta_* table. Empty list when the section is absent."""
    return {name: list(fn(introspection)) for name, fn in TABLES.items()}


# Semantic annotations for the meaning-plane grounding: which introspection question each relation
# serves + a canonical example query. The relation set is fixed; columns are auto-derived from the data,
# so the grounding can never drift from the tables. Edit here if the question-mapping changes.
_GROUNDING = {
 "meta_measures": ("what measures / KPIs exist; a measure's type, additivity, and DEFINITION — what a KPI like Order Book (OB) or Prodant MEANS",
                   "SELECT measure, type, additivity_time, definition, surface FROM fpl.meta_measures WHERE stem IN ('ob','prodant')"),
 "meta_kpi_variants": ("the tracking variants (actual / plan / budget) of a measure — the budget-vs-plan distinction",
                   "SELECT DISTINCT variant, suffix, is_default FROM fpl.meta_kpi_variants ORDER BY variant"),
 "meta_dimensions": ("what dimensions exist and their cardinality (e.g. how many model families, how many markets)",
                   "SELECT dimension, json_extract_scalar(cardinality,'$.families') AS families FROM fpl.meta_dimensions WHERE dimension='VehicleModel'"),
 "meta_brand_members": ("the brand clusters, their brands, and which are served — the brand-count distinctions (cluster vs brand vs served)",
                   "SELECT count(DISTINCT cluster_code) AS clusters, count(DISTINCT CASE WHEN lower(in_fact_data) IN ('true','1') THEN cluster_code END) AS served FROM fpl.meta_brand_members"),
 "meta_region_definitions": ("the region / structure DEFINITIONS per brand + member counts + cross-brand collisions (VW's Europe vs Audi's Europe)",
                   "SELECT namespace, member_count FROM fpl.meta_region_definitions WHERE code='VE' ORDER BY namespace"),
 "meta_region_members": ("which countries / markets are IN a named region or structure (e.g. VW's VE, Skoda's Region 3). region_definition_used = 'namespace:code'",
                   "SELECT member FROM fpl.meta_region_members WHERE region_definition_used='vw_bereich:VE'"),
 "meta_rules": ("what business rules exist and what a rule SAYS (its when/then/never) — e.g. how planning accuracy is defined",
                   "SELECT then_text FROM fpl.meta_rules WHERE rule_id LIKE '%variance%'"),
 "meta_rule_refs": ("the concepts / columns a rule binds or derives over",
                   "SELECT ref_value FROM fpl.meta_rule_refs WHERE ref_kind='over' AND rule_id LIKE '%variance%'"),
 "meta_decision_policy": ("the ASK / COMMIT / REFUSE routing slots and their policies", "SELECT slot, policy FROM fpl.meta_decision_policy"),
 "meta_rule_kinds": ("the closed rule-kind vocabulary", "SELECT term, governs FROM fpl.meta_rule_kinds"),
 "meta_edges": ("the relationships / joins declared between concepts", "SELECT edge_id, from_concept, to_concept, cardinality FROM fpl.meta_edges"),
 "meta_edge_join_clauses": ("the join columns for a relationship edge", "SELECT * FROM fpl.meta_edge_join_clauses WHERE edge_id=?"),
 "meta_provenance": ("which ontology bytes (sha256) produced this meaning-plane reflection", "SELECT input_path, input_sha256 FROM fpl.meta_provenance"),
}


def grounding_yaml(tables: dict, source: str = "fpl") -> str:
    """The meaning-plane GROUNDING the interpreter inlines — one grounded relation per meta_* table with
    its columns, what question it answers, and a canonical example query. Generated (never hand-edited)."""
    import yaml as _yaml
    rels = []
    for name, rows in tables.items():
        cols = sorted({k for r in rows for k in r.keys()})
        answers, example = _GROUNDING.get(name, ("(introspection relation)", f"SELECT * FROM {source}.{name}"))
        rels.append({"relation": f"{source}.{name}", "answers": answers, "columns": cols, "example": example})
    doc = {
      "metadata": {"concept": "MeaningPlane", "source": source.upper(), "kind": "meaning-plane-grounding",
                   "generated_by": "meaning-as-code/tools/mac_to_meta.py::grounding_yaml",
                   "note": "GENERATED — do not hand-edit; regenerate from model.introspection.json."},
      "meaning_plane": {
        "purpose": ("Questions ABOUT the model itself — what measures/dimensions/regions/rules exist; a "
                    "measure's or dimension's DEFINITION; the MEMBERSHIP of a named region/structure; a "
                    "COMPARISON of definitions — are answered by a deterministic SELECT over these meta_* "
                    "relations (governing rule: meta.model_property_channel). NEVER author the answer as a "
                    "SQL string literal, and NEVER query a warehouse fact/dim view for these — the fact "
                    "tables do not carry the model's self-description. All columns are VARCHAR; nested "
                    "values are JSON strings (use json_extract_scalar)."),
        "relations": rels,
      },
    }
    return _yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100)


def dataset_descriptors(tables: dict, source: str = "fpl") -> dict:
    """{table_name: yaml_text} — a Physical-layer schema-of-record descriptor per meta_* relation, the
    twin of the warehouse dim descriptors (data/datasets/<rel>.yaml). The shapes gate resolves a grounded
    concept's columns CROSS-FILE from these (check_shapes.grounded_columns_for_relation); without them the
    meaning-plane concepts fail field-roles-grounded. Columns AUTO-derived from the reflection in DDL
    order; all VARCHAR (the meaning plane is descriptive). Generated — never hand-edited."""
    import yaml as _yaml
    sv = _framework_schema_version()
    out = {}
    for name, rows in tables.items():
        doc = {
          "metadata": {
            "table": name, "source": source.upper(), "schema_version": sv, "status": "deployed",
            "generated_by": "meaning-as-code/tools/mac_to_meta.py::dataset_descriptors",
            "note": "GENERATED — do not hand-edit; regenerate from model.introspection.json.",
            "owner": "data-platform-team"},
          "table": {"name": name, "schema": source, "type": "view", "confidence": "C"},
          "columns": [{"name": c, "type": "string", "confidence": "C"} for c in _ordered_columns(rows)],
        }
        out[name] = _yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100)
    return out


# ============================================================================================
# MEANING-PLANE CONCEPTS (epic #86) — the model as 7 first-class MAC concepts.
#
# Each meta_* relation is grouped into a natural concept; the concept is a NORMAL MAC concept
# (same shape as geography/region.yaml, kpi/obreach.yaml) whose SUBJECT is the model itself. Its
# COLUMNS are auto-derived from the reflection (`reflect()` output) — they can never drift from the
# tables. Its SEMANTICS (class / identity / definition / the field-role of each column / the
# answers·example·never contract) are FIXED per-concept annotations, authored once below.
#
# GENERIC: `source` is a parameter — no source literal appears in the emit LOGIC. Every place a
# source token is needed (relation prefix, class prefix, field_role prefix, an example's FROM) uses
# the `{src}` placeholder, substituted at emit time. Constants that hold for EVERY meta concept
# (class suffix `.class.meta`, kind `meta-ontology`, the generated banner, the governing rule) are
# shared. A column present in the reflection but absent from a concept's `roles:` map safely defaults
# to `attribute`, so a newly-reflected column never silently becomes a measure.
# ============================================================================================

_META_KIND = "meta-ontology"
_META_CLASS = "meta"                             # the framework's meaning-plane concept class (epic #86);
#                                                  the guardrail keys on the meta_ prefix + route, not this
_META_GOVERNING_RULE = "meta.model_property_channel"
_META_GENERATED_BY = "meaning-as-code/tools/mac_to_meta.py::emit_meta_concepts"
_META_NOTE = "GENERATED — do not hand-edit; regenerate from model.introspection.json."
_META_ROLE_DEFAULT = "attribute"                 # any un-annotated reflection column lands here (safe, non-aggregating)

# Per-concept FIXED annotation table. `relations` (with per-relation `key`) selects & orders the
# reflection tables; `roles` maps each column to dimension|attribute|measure; the prose carries the
# meaning-plane guidance. `{src}` is substituted with the source parameter. Grouped by NATURAL
# concept (not one-per-physical-table): 7 concepts across all 13 meta_* relations.
_META_CONCEPTS = {
 "Measure": {
   "label": "Measure (a KPI the model defines)",
   "identity": {"kind": "code", "canonical_key": "measure"},
   "relations": [("meta_measures", ["measure"]), ("meta_kpi_variants", ["kpi_code"])],
   "roles": {
     "measure": "dimension", "stem": "dimension", "measure_type": "dimension", "type": "dimension",
     "source_kind": "dimension", "additivity_time": "dimension", "additivity_categorical": "dimension",
     "kpi_code": "dimension", "variant": "dimension",
     "definition": "attribute", "surface": "attribute", "kpi_codes": "attribute", "axis_kinds": "attribute",
     "grounds_relation": "attribute", "realized_from": "attribute", "closure": "attribute",
     "suffix": "attribute", "is_default": "attribute"},
   "definition": (
     "A KPI/measure that the FPL model itself defines — its measure_type (Flow / Stock / Target), its "
     "additivity behaviour on the time and categorical axes, the serving relation it grounds on, its "
     "natural-language surface terms, its tracking variants (actual / plan / budget), and its prose "
     "DEFINITION (what Order Book, Prodant, DtC actually MEAN). The subject is the MODEL, not the "
     "warehouse: this is the model's own register of measures, reflected as a queryable relation "
     "(meta_measures + meta_kpi_variants). A measure's type, additivity and meaning are READ from "
     "meta_measures — never authored as a SQL literal in an answer."),
   "grain": (
     "one row per measure ({src}.meta_measures); its tracking variants fan out to one row per "
     "(stem × variant) = kpi_code in {src}.meta_kpi_variants, joined back on `stem`. No numeric fact — "
     "all columns are VARCHAR."),
   "answers": (
     "what measures/KPIs the model defines, and — for a named measure — its type (Flow/Stock/Target), "
     "its additivity on the time and categorical axes, its serving relation and surface terms, its "
     "tracking variants (the actual/plan/budget distinction), and its DEFINITION: what a KPI like Order "
     "Book (OB), Prodant or DtC actually MEANS."),
   "example": (
     "SELECT measure, type, additivity_time, additivity_categorical, definition, surface\n"
     "FROM {src}.meta_measures\n"
     "WHERE stem IN ('ob', 'prodant');\n"
     "SELECT DISTINCT variant, suffix, is_default\n"
     "FROM {src}.meta_kpi_variants\n"
     "WHERE stem = 'ob'\n"
     "ORDER BY variant;"),
   "never": (
     "Authoring a measure's definition, type or additivity as a SQL string literal — these are READ from "
     "{src}.meta_measures (definition, measure_type, additivity_time), never written into the answer. "
     "Querying a warehouse fact/dim view (v_fpl_kpi_current, dim_*) for the model's self-description — "
     "those carry the KPI NUMBERS, not the KPI's MEANING (two-planes-never-mixed): a measure-definition "
     "question stays on meta_*, and a warehouse-number question never routes here."),
 },
 "Dimension": {
   "label": "Dimension (model axis)",
   "identity": {"kind": "code", "canonical_key": "dimension"},
   "relations": [("meta_dimensions", ["dimension"]), ("meta_brand_members", ["cluster_code", "brand"])],
   "roles": {
     "dimension": "dimension", "concept": "dimension", "cluster_code": "dimension", "brand": "dimension",
     "identity_kind": "attribute", "grain": "attribute", "canonical_key": "attribute",
     "realized_from": "attribute", "cardinality": "measure",
     "multi_brand": "attribute", "in_fact_data": "attribute", "confidence": "attribute"},
   "definition": (
     "A named DIMENSION the FPL model defines — an axis the model can slice by (Brand, VehicleModel, "
     "Region, Country, BrandCluster), together with the concept it realizes, its grain, identity kind, "
     "canonical key, the register it is realized_from, and its CARDINALITY: how many families / model "
     "codes / clusters / markets it spans (a JSON payload, e.g. VehicleModel -> "
     '{"families": 218, "model_codes": 1084}). It also carries brand-cluster MEMBERSHIP — which brands '
     "roll up into each BrandCluster and whether a cluster is served in the fact data. The subject is "
     "the MODEL itself: this is the model's own dimension register, reflected as a queryable relation, "
     "never the warehouse dim_* tables."),
   "grain": (
     "one row per dimension ({src}.meta_dimensions); one row per (cluster_code × brand) for brand-cluster "
     "membership ({src}.meta_brand_members, dimension = 'BrandCluster'). Cardinality is a JSON string — "
     "read a count with json_extract_scalar(cardinality, '$.<key>')."),
   "answers": (
     "what dimensions the model defines and their CARDINALITY (how many model families, markets, "
     "clusters); and brand-cluster membership — the clusters, their brands, and which are served (the "
     "cluster-vs-brand-vs-served distinction)."),
   "example": (
     "SELECT dimension, json_extract_scalar(cardinality, '$.families') AS families\n"
     "FROM {src}.meta_dimensions WHERE dimension = 'VehicleModel';\n"
     "SELECT count(DISTINCT cluster_code) AS clusters,\n"
     "       count(DISTINCT CASE WHEN lower(in_fact_data) IN ('true','1') THEN cluster_code END) AS served\n"
     "FROM {src}.meta_brand_members;"),
   "never": (
     "authoring a dimension's cardinality, grain, or brand membership as a SQL string literal; querying a "
     "warehouse fact/dim view (dim_model, dim_country, v_fpl_kpi_current) to count families / markets / "
     "clusters — these are READ from {src}.meta_dimensions / {src}.meta_brand_members, never hand-written "
     "and never computed off the warehouse plane."),
 },
 "Enum": {
   "label": "Enum value (closed value domain)",
   "identity": {"kind": "code", "canonical_key": "value"},
   "relations": [("meta_enum", ["concept", "value"])],
   "roles": {
     "concept": "dimension", "value": "dimension", "label": "attribute"},
   "definition": (
     "A member of a closed VALUE DOMAIN the FPL model defines — the actual enumerable values of a "
     "categorical dimension (the body types, fuel classes, vehicle segments, platforms, brands, plan "
     "stages, …), each with its human LABEL. The subject is the MODEL's own value register, reflected as "
     "a queryable relation ({src}.meta_enum): one row per (concept, value). The set of valid values for a "
     "dimension is READ from meta_enum — never enumerated as SQL string literals in an answer, and never "
     "scraped with SELECT DISTINCT off a warehouse fact/dim."),
   "grain": (
     "one row per (concept, value) in {src}.meta_enum; `concept` is the dimension name (e.g. 'BodyType', "
     "'FuelType', 'VehicleSegment', 'VehicleModelPlatform'), `value` its code, `label` the description. "
     "All columns VARCHAR."),
   "answers": (
     "what values a categorical dimension can take — which body types / fuel classes / segments / "
     "platforms / brands / plan stages EXIST, how many there are, and what each code MEANS (its label)."),
   "example": (
     "SELECT value, label FROM {src}.meta_enum WHERE concept = 'BodyType' ORDER BY value;\n"
     "SELECT concept, count(*) AS n FROM {src}.meta_enum GROUP BY concept ORDER BY concept;"),
   "never": (
     "Enumerating a dimension's valid values as SQL string literals, or scraping them with SELECT DISTINCT "
     "off a warehouse fact/dim (dim_model, the fact) — the closed value domain is READ from {src}.meta_enum "
     "(the meaning plane), never off the data plane (two-planes-never-mixed)."),
 },
 "RegionDefinition": {
   "label": "Region Definition",
   "identity": {"kind": "namespace_code", "canonical_key": "region_definition_used"},
   "relations": [("meta_region_definitions", ["region_definition_used"])],
   "roles": {
     "region_definition_used": "dimension", "namespace": "dimension", "code": "dimension",
     "brand": "dimension", "member_count": "measure",
     "label": "attribute", "member_kind": "attribute", "confidence": "attribute",
     "brand_relative": "attribute", "collides_with": "attribute"},
   "definition": (
     "A named region or structure scheme OF THE FPL MODEL — one brand's own way of grouping countries "
     "into a region, identified as namespace:code (e.g. vw_bereich:VE = 'Europe excl. Germany', 34 "
     "member countries), plus the absolute cross-brand sets (standard:/political:). Each brand-relative "
     "definition is disclosed WITH its member_count and its cross-brand collisions: the SAME code means "
     "DIFFERENT country sets across brands (vw_bereich:VE=34 vs audi_region:VE=32 — same 'VE' label, "
     "different membership), which is exactly why the model identifies a definition by (namespace, code). "
     "This is the model's own scheme register, reflected as a queryable relation "
     "({src}.meta_region_definitions) — never the warehouse, and never authored as a literal."),
   "grain": (
     "one row per region definition (namespace × code) — the definitions across all namespaces in "
     "{src}.meta_region_definitions. member_count is the model's DECLARED size — read it, do not "
     "recompute it by rolling up countries from a fact view. collides_with is a JSON-array string."),
   "answers": (
     "which region/structure definitions the model carries and for which brand, how many countries each "
     "contains (member_count), and where the SAME code collides across brands (VW's Europe vs Audi's "
     "Europe) — a question ABOUT the model's structure."),
   "example": (
     "SELECT namespace, code, brand, member_count, collides_with\n"
     "FROM {src}.meta_region_definitions\n"
     "WHERE code = 'VE'\n"
     "ORDER BY namespace"),
   "never": (
     "authoring a region definition, its member_count, or a collision as a SQL string literal (the answer "
     "is READ from {src}.meta_region_definitions, never hand-written); querying a warehouse fact/dim view "
     "(dim_fpl_lm_country, v_fpl_region_rollup, v_fpl_region_membership) for the model's region SCHEMES — "
     "those views carry country facts and memberships, not the model's self-description of its "
     "definitions. Two-planes: this concept lives on meta_* only."),
 },
 "RegionMember": {
   "label": "Region Member",
   "identity": {"kind": "composite", "key": ["region_definition_used", "member"]},
   "relations": [("meta_region_members", ["region_definition_used", "member"])],
   "roles": {
     "region_definition_used": "dimension", "namespace": "dimension", "code": "dimension",
     "member": "dimension",
     "member_kind": "attribute", "iso2": "attribute", "fpl_brand_country_code": "attribute"},
   "definition": (
     "A country or market that belongs to a NAMED region or structure definition (namespace:code) of the "
     "FPL MODEL — e.g. a country in VW's VE (Europe excl. Germany, vw_bereich:VE) or a market in Skoda's "
     "Region 3 (skoda_structure:Region 3). This is the model's OWN membership register, reflected as a "
     "queryable relation, never the warehouse. Membership is scoped by region_definition_used = "
     "'namespace:code' (the collision-proof identity: vw_bereich:VE and audi_region:VE are DIFFERENT "
     "country sets); member_kind tells how the member is expressed — 'raw_token' brand-scheme markets "
     "(carrying fpl_brand_country_code) vs 'iso2' standard/political sets (carrying iso2). The answer is "
     "READ from this relation, never hand-listed as a literal."),
   "grain": (
     "one row per (region_definition_used × member) — the exploded membership register in "
     "{src}.meta_region_members. 'raw_token' rows are brand-scheme markets keyed by "
     "fpl_brand_country_code (iso2 null); 'iso2' rows are cross-brand standard/political sets keyed by "
     "iso2 (fpl_brand_country_code null). Parent definitions live in RegionDefinition; join on "
     "region_definition_used."),
   "answers": (
     "which countries/markets are in a named region or structure (VW VE, Audi VE, Skoda Region 3), and — "
     "via region_definition_used = 'namespace:code' — under WHICH brand's definition."),
   "example": "SELECT member FROM {src}.meta_region_members WHERE region_definition_used = 'vw_bereich:VE'",
   "never": (
     "authoring a region's membership as a SQL string literal (the members are READ from this reflection "
     "— never hand-enumerated in the answer, which would fabricate/omit countries and mask the VW-VE vs "
     "Audi-VE collision); querying a warehouse fact/dim view for membership (the fact tables do not carry "
     "the model's region definitions — a two-planes breach; RegionMember grounds only on "
     "{src}.meta_region_members)."),
 },
 "Rule": {
   "label": "Rule (model behaviour / derived-measure law)",
   "identity": {"kind": "qualified_id", "canonical_key": "rule_id"},
   "relations": [("meta_rules", ["rule_id"]), ("meta_rule_refs", ["rule_id", "ref_kind", "ref_value"]),
                 ("meta_decision_policy", ["slot"]), ("meta_rule_kinds", ["term"])],
   "roles": {
     "rule_id": "dimension", "family": "dimension", "kind_term": "dimension", "scope": "dimension",
     "confidence": "dimension", "home_concept": "dimension",
     "subject": "attribute", "when_text": "attribute", "then_text": "attribute", "never_text": "attribute",
     "home_file": "attribute",
     "ref_kind": "dimension", "ref_value": "dimension",
     "slot": "dimension", "policy": "dimension", "governing_rule": "attribute", "on_missing": "attribute",
     "term": "dimension", "governs": "attribute", "closed": "attribute"},
   "definition": (
     "A Rule of the FPL model — one behavioural or derived-measure law the model enforces, identified by "
     "its dotted rule_id (e.g. region.collision, measure.period_mandatory, plan_vs_actual_variance). It "
     "carries the rule's own when/then/never clauses, its subject line, its KIND (from the closed rule-"
     "kind vocabulary — resolution / aggregation / default / ambiguity / exclusion / guarantee), its "
     "family (behavioural vs derived_measure), its scope and confidence, and the home concept/file that "
     "owns it. It also exposes the concepts and columns a rule BINDS or derives OVER (via "
     "meta_rule_refs) and, for the routing rules, the ASK / COMMIT / REFUSE policy (via "
     "meta_decision_policy). This is the model's OWN rule register, reflected as a queryable relation — "
     "the rule's text is READ from meta_rules, never the warehouse and never a hand-authored literal."),
   "grain": (
     "ONE ROW PER RULE (rule_id) in {src}.meta_rules. Companions fan out: {src}.meta_rule_refs is one row "
     "per (rule_id × ref_kind × ref_value); {src}.meta_decision_policy one row per routing slot (joined "
     "back on rule_id); {src}.meta_rule_kinds one row per kind term (joined on term = kind_term). All "
     "columns are VARCHAR text reflected from the ontology source."),
   "answers": (
     "What rules the FPL model enforces and what a rule SAYS (its when/then/never/subject); what KIND a "
     "rule is and the closed kind vocabulary; the concepts and columns a rule BINDS or derives OVER; and "
     "the ASK / COMMIT / REFUSE decision policy — e.g. 'how is planning accuracy / plan-vs-actual "
     "variance defined?', 'which rules govern Order Book?', 'which axes MUST be asked for (no default)?'."),
   "example": (
     "SELECT rule_id, subject, when_text, then_text, never_text\n"
     "FROM {src}.meta_rules\n"
     "WHERE rule_id LIKE '%variance%';\n"
     "SELECT ref.ref_value\n"
     "FROM {src}.meta_rules r\n"
     "JOIN {src}.meta_rule_refs ref ON ref.rule_id = r.rule_id\n"
     "WHERE r.rule_id = 'plan_vs_actual_variance' AND ref.ref_kind = 'over';\n"
     "SELECT slot, on_missing FROM {src}.meta_decision_policy WHERE policy = 'mandatory_no_default';\n"
     "SELECT term, governs FROM {src}.meta_rule_kinds;"),
   "never": (
     "Authoring a rule's text (its when/then/never/subject), its routing policy, or the kind vocabulary "
     "as a SQL string literal — the answer is READ from meta_rules / meta_rule_refs / "
     "meta_decision_policy / meta_rule_kinds, never invented, paraphrased-as-fact, or hardcoded. And "
     "NEVER querying a warehouse fact/dim view for the model's rules: the fact tables do not carry the "
     "rule register; a Rule question that hits the warehouse is a two-planes breach."),
 },
 "Edge": {
   "label": "Edge (declared concept relationship)",
   "identity": {"kind": "code", "canonical_key": "edge_id"},
   "relations": [("meta_edges", ["edge_id"]), ("meta_edge_join_clauses", ["edge_id", "ordinal"])],
   "roles": {
     "edge_id": "dimension", "from_concept": "dimension", "to_concept": "dimension", "type": "dimension",
     "level": "dimension", "cardinality": "dimension",
     "confidence": "attribute", "join_rule": "attribute", "realized_by_register": "attribute",
     "verified_by": "attribute",
     "ordinal": "attribute", "left_relation": "attribute", "left_column": "attribute",
     "right_relation": "attribute", "right_column": "attribute"},
   "definition": (
     "An Edge is a DECLARED relationship between two concepts of the FPL model — the join that lets one "
     "concept be read alongside another (e.g. Measurement —N:1→ Country, joined on "
     "fpl_brand_country_code). Each edge names its from_concept / to_concept, its type (foreign_key, "
     "shared_attribute), cardinality (N:1, N:N), and level (physical, business), and carries the join "
     "predicate; a multi-hop join decomposes into ORDERED join clauses. This is the model's OWN "
     "relationship graph — the same edges authored in edges.yaml — reflected as a queryable relation, "
     "never a warehouse view. There is no 'edge' in the domain data; there is the model's declaration of "
     "how its concepts connect."),
   "grain": (
     "one row per declared edge (edge_id) in {src}.meta_edges; each edge decomposes into its ordered join "
     "clauses (edge_id × ordinal) in {src}.meta_edge_join_clauses. ordinal is stored as a string — CAST "
     "it to integer to order multi-hop clauses."),
   "answers": (
     "how the model's concepts relate — the declared joins/edges between concepts, their type, "
     "cardinality, level, and the exact columns each edge joins on (including multi-hop bridges)."),
   "example": (
     "SELECT e.edge_id, e.from_concept, e.to_concept, e.cardinality, e.type,\n"
     "       jc.ordinal, jc.left_relation, jc.left_column, jc.right_relation, jc.right_column\n"
     "FROM {src}.meta_edges e\n"
     "LEFT JOIN {src}.meta_edge_join_clauses jc ON jc.edge_id = e.edge_id\n"
     "WHERE e.to_concept = 'VehicleModel'\n"
     "ORDER BY e.edge_id, CAST(jc.ordinal AS integer)"),
   "never": (
     "authoring an edge/join as a SQL literal — hand-writing how two concepts relate instead of reading "
     "it from {src}.meta_edges/{src}.meta_edge_join_clauses; querying a warehouse fact/dim view to answer "
     "how concepts relate — the join graph is the model's self-description on the meaning plane, not a "
     "fact in the data plane; inventing an edge, cardinality, or join column absent from meta_edges."),
 },
 "Provenance": {
   "label": "Provenance (ontology byte-provenance / freshness ledger)",
   "identity": {"kind": "composite", "key": ["source", "input_path"]},
   "relations": [("meta_provenance", ["source", "input_path"])],
   "roles": {
     "source": "dimension", "input_path": "dimension",
     "input_sha256": "attribute", "mac_version": "attribute", "schema_version": "attribute"},
   "definition": (
     "A single ontology INPUT byte-source of the FPL model — a concept file or register CSV — together "
     "with the sha256 of its bytes and the mac/schema version that produced this reflection. Provenance "
     "is the model's own FRESHNESS/DRIFT ledger: it records WHICH bytes were reflected into the meaning "
     "plane, so a reader can tell whether the meta_* views are current with the ontology sources or a "
     "file has drifted since the last projection. Its subject is the MODEL itself (the reflection run), "
     "never the domain. Read from the reflection (meta_provenance) — never a warehouse view, never "
     "authored as a literal."),
   "grain": "one row per (source × input_path) — one ontology input byte-source (file) per reflection run.",
   "answers": (
     "which ontology bytes (files) produced this reflection of the model, and whether the meaning plane "
     "is FRESH or has DRIFTED from its sources — the sha256 per input file, plus the mac_version / "
     "schema_version that generated the reflection."),
   "example": (
     "SELECT input_path, input_sha256, mac_version, schema_version\n"
     "FROM {src}.meta_provenance ORDER BY input_path"),
   "never": (
     "authoring a file's sha256 or the mac/schema version as a SQL string literal (the answer is a SELECT "
     "over the reflection, never a hand-written constant); querying a warehouse fact/dim view for "
     "provenance — the warehouse carries domain DATA, not the model's own byte-provenance, which lives "
     "ONLY in {src}.meta_provenance."),
 },
}


def _ordered_columns(rows):
    """Column list of a reflected table, preserving first-seen (DDL) order — never sorted."""
    cols = []
    for r in rows:
        for k in r.keys():
            if k not in cols:
                cols.append(k)
    return cols


def _sub(x, source):
    """Substitute the {src} source placeholder in any string (leaves JSON braces untouched)."""
    return x.replace("{src}", source) if isinstance(x, str) else x


def _concept_doc(name, spec, tables, source):
    """Build the concept dict for one meta concept from its FIXED spec + AUTO reflection columns."""
    # AUTO: per-relation column lists (from the reflection) + the union role-map keys, in DDL order.
    rel_cols = {rel: _ordered_columns(tables.get(rel, [])) for rel, _ in spec["relations"]}
    union_cols = []
    for rel, _ in spec["relations"]:
        for c in rel_cols[rel]:
            if c not in union_cols:
                union_cols.append(c)
    # field_roles: every reflection column -> its FIXED role (default attribute), source-prefixed.
    field_roles = {c: f"{source}.field_role.{spec['roles'].get(c, _META_ROLE_DEFAULT)}" for c in union_cols}
    sources = [{"relation": f"{source}.{rel}", "key": key, "columns": rel_cols[rel]}
               for rel, key in spec["relations"]]
    identity = dict(spec["identity"])
    return {
      "metadata": {
        "concept": name, "source": source.upper(), "schema_version": _framework_schema_version(),
        "kind": _META_KIND, "generated_by": _META_GENERATED_BY, "note": _META_NOTE},
      "concept": {
        "name": name, "label": spec["label"], "class": _sub(_META_CLASS, source),
        "identity": identity, "definition": _sub(spec["definition"], source)},
      "grounding": {"field_roles": field_roles, "sources": sources, "grain": _sub(spec["grain"], source)},
      "contract": {
        "governing_rule": _META_GOVERNING_RULE,
        "answers": _sub(spec["answers"], source),
        "example": _sub(spec["example"], source),
        "never": _sub(spec["never"], source)},
      "governance": {"owner": "data-platform-team", "generated": True},
    }


def _meta_str_representer(dumper, data):
    """Multi-line strings (examples) -> literal block '|'; everything else default."""
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


def emit_meta_concepts_from_tables(tables: dict, source: str = "fpl") -> dict:
    """{ConceptName: yaml_text} for the 7 meaning-plane concepts, from a `reflect()` tables dict.
    Columns AUTO-derived from `tables`; semantics FIXED in _META_CONCEPTS; `source` a parameter."""
    import yaml
    Dumper = type("_MetaDumper", (yaml.SafeDumper,), {})
    Dumper.add_representer(str, _meta_str_representer)
    Dumper.add_representer(bool, lambda d, x: d.represent_scalar("tag:yaml.org,2002:bool",
                                                                 "true" if x else "false"))
    out = {}
    for name, spec in _META_CONCEPTS.items():
        doc = _concept_doc(name, spec, tables, source)
        banner = (f"# {source.upper()} > meta > {name}  (META-ONTOLOGY — the model described in its own "
                  f"language; epic #86)\n#\n"
                  f"# GENERATED by the projector from model.introspection.json — do NOT hand-edit; "
                  f"regenerate.\n"
                  f"# The SUBJECT of this concept is the MODEL ITSELF, not the domain. TWO-PLANES: "
                  f"class = {source}.class.meta\n"
                  f"# and it grounds ONLY on {source}.meta_* — the guardrail keys on the class. A "
                  f"definition/rule/edge is READ\n"
                  f"# from the reflection, never authored as a SQL literal and never fetched from a "
                  f"warehouse view.\n#\n")
        body = yaml.dump(doc, Dumper=Dumper, sort_keys=False, allow_unicode=True, width=100,
                         default_flow_style=False)
        out[name] = banner + body
    return out


def emit_meta_concepts(introspection: dict, source: str = "fpl") -> dict:
    """{ConceptName: yaml_text} for the 7 meaning-plane concepts, from a model.introspection.json dict.
    Reflects the introspection into meta_* tables, then emits — columns can never drift from the tables.
    GENERIC: `source` is a parameter; no source literal appears in the logic (invariant #4)."""
    return emit_meta_concepts_from_tables(reflect(introspection), source)


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
