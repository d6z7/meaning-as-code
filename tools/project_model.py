#!/usr/bin/env python3
"""project_model — project an applied MAC ontology into a human/machine model catalog.

The ontology is the source of truth; this is a PROJECTION of it — a generated view of every measure
(KPI) and dimension the applied model defines, plus the additivity law each measure obeys. Nothing here
is authored by hand: it is read from the concept files, the derived-measure rules, and the framework's
mac.MeasureType additivity matrix. Regenerate it any time the ontology changes; never edit the output.

Reads (all under <source_root>):
  ontology/concepts/**/*.yaml   — concepts: `concept.{name,class,...}`, `grounding`, closed `values`/`enumerations`
  ontology/rules.yaml           — derived measures (rule/derives/over/logic)
  <mac>/mac_vocabulary.yaml      — the MeasureType additivity law (Flow/Stock/Target × time/categorical)

Emits  <source_root>/projections/model.md  and  model.json  (override with --out-dir).

  usage:  python3 tools/project_model.py <source_root> [--out-dir DIR] [--print]
  e.g.    python3 tools/project_model.py ../<applied-ontology-repo>
"""
from __future__ import annotations
import argparse, csv, hashlib, json, re, sys
from collections import defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
MAC_VOCAB = HERE.parent / "mac_vocabulary.yaml"

EFFECT = {  # mac.aggregation_effect term -> short label for the projection
    "mac.aggregation_effect.additive":      "additive (sum)",
    "mac.aggregation_effect.point_in_time": "point-in-time (as-of)",
    "mac.aggregation_effect.averageable":   "averageable (avg / percentile)",
    "mac.aggregation_effect.non_aggregable":"non-additive",
    "mac.aggregation_effect.semi_additive": "semi-additive",
}


def load(p: Path):
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as e:                                     # keep going; report the bad file
        return {"__error__": f"{p}: {e}"}


def measure_law() -> dict:
    """The additivity matrix from mac.MeasureType: {Flow: {time,categorical}, Stock:…, Target:…}."""
    doc = load(MAC_VOCAB)
    mt = (doc.get("MeasureType") or {}).get("members") or {}
    out = {}
    for name, spec in mt.items():
        add = (spec or {}).get("additivity") or {}
        out[name] = {
            "definition": (spec or {}).get("definition", ""),
            "time":        EFFECT.get(add.get("time"), add.get("time", "?")),
            "categorical": EFFECT.get(add.get("categorical"), add.get("categorical", "?")),
        }
    return out


def grounding_of(doc: dict) -> dict:
    """Extract {relations, key, columns} from a concept's grounding block (tolerant of variants)."""
    g = doc.get("grounding") or {}
    relations, key, cols = [], None, []
    for s in (g.get("sources") or []):
        if isinstance(s, dict):
            if s.get("relation"): relations.append(s["relation"])
            key = key or s.get("key")
            cols += s.get("columns") or []
    if isinstance(g.get("table"), str):
        relations.append(g["table"])
    for t in (g.get("primary_tables") or g.get("tables") or []):
        relations.append(t["name"] if isinstance(t, dict) else t)
    fr = g.get("field_roles") or {}
    if not key:
        key = next((c for c, r in fr.items() if isinstance(r, str) and r.endswith(".key")), None)
    return {"relations": sorted(set(relations)), "key": key, "columns": sorted(set(cols))}


def values_of(doc: dict) -> list[dict]:
    """Collect the closed value set of a concept, from top-level `values.items` or `enumerations[].values`."""
    out = []
    v = doc.get("values")
    if isinstance(v, dict):
        for it in (v.get("items") or []):
            if isinstance(it, dict):
                out.append({"code": it.get("code", it.get("value")), "closure": v.get("closure"), **it})
    for en in (doc.get("enumerations") or []):
        if isinstance(en, dict):
            for it in (en.get("values") or en.get("items") or []):
                if isinstance(it, dict):
                    out.append({"code": it.get("code", it.get("value")), "closure": en.get("closure"), **it})
    return out


def project(root: Path) -> dict:
    law = measure_law()
    concepts = sorted((root / "ontology" / "concepts").rglob("*.yaml"))
    measures, dimensions = [], []

    for p in concepts:
        doc = load(p)
        c = doc.get("concept") or {}
        name = c.get("name") or p.stem
        rec = {
            "name": name, "class": c.get("class"), "label": c.get("label"),
            "german": c.get("german"), "definition": (c.get("definition") or "").strip(),
            "file": str(p.relative_to(root)), "grounding": grounding_of(doc),
            "values": values_of(doc), "identity": (c.get("identity") or {}),
        }
        if c.get("class") == "measure":
            measures.append(rec)
        else:
            dimensions.append(rec)

    # base measures = the KpiCode-style enumeration whose items carry `measure_type`
    base = {}
    for m in measures:
        for it in m["values"]:
            mt = it.get("measure_type")
            if not mt:
                continue
            meas = it.get("measure") or (it["code"].split(".")[0] if it.get("code") else "?")
            variant = it["code"].split(".")[1] if it.get("code") and "." in it["code"] else None
            tkey = str(mt).split(".")[-1]           # Flow|Stock|Target
            b = base.setdefault(meas, {"measure": meas, "type": tkey, "variants": []})
            if variant and variant not in b["variants"]:
                b["variants"].append(variant)

    # derived measures from rules.yaml
    derived = []
    rp = root / "ontology" / "rules.yaml"
    if rp.exists():
        for r in (load(rp).get("rules") or []):
            if isinstance(r, dict):
                derived.append({
                    "rule": r.get("rule"), "derives": r.get("derives"),
                    "over": r.get("over"), "logic": (str(r.get("logic") or "")).strip().split("\n")[0],
                    "confidence": r.get("confidence"),
                })

    return {"law": law, "base_measures": base, "measure_concepts": measures,
            "derived": derived, "dimensions": dimensions}


def to_markdown(root: Path, model: dict) -> str:
    L, law = [], model["law"]
    L.append(f"# Model projection — `{root.name}`\n")
    L.append("_Generated by `meaning-as-code/tools/project_model.py` — a projection of the ontology. "
             "Do not edit; regenerate._\n")

    L.append("## Measures (KPIs)\n")
    L.append("The measure **type** fixes how it may be aggregated (mac.MeasureType):\n")
    L.append("| Type | over time | over geography/model |")
    L.append("|---|---|---|")
    for t, spec in law.items():
        L.append(f"| **{t}** | {spec['time']} | {spec['categorical']} |")
    L.append("")
    if model["base_measures"]:
        L.append("### Base measures\n")
        L.append("| Measure | Type | Variants |")
        L.append("|---|---|---|")
        for b in sorted(model["base_measures"].values(), key=lambda x: (x["type"], x["measure"])):
            L.append(f"| `{b['measure']}` | {b['type']} | {', '.join(b['variants'])} |")
        ncodes = sum(len(b["variants"]) for b in model["base_measures"].values())
        L.append(f"\n_{len(model['base_measures'])} base measures × variants = {ncodes} KpiCodes._\n")
    for m in model["measure_concepts"]:
        if not any(it.get("measure_type") for it in m["values"]):     # a standalone measure concept (no typed KpiCode enumeration)
            g = ", ".join(m["grounding"]["relations"]) or "—"
            L.append(f"### {m['name']} (special measure)\n")
            L.append(f"{m['definition']}\n")
            L.append(f"_grounding: `{g}`_\n")

    if model["derived"]:
        L.append("### Derived measures (rules.yaml)\n")
        L.append("| Rule | Derives | Over |")
        L.append("|---|---|---|")
        for d in model["derived"]:
            over = ", ".join(f"`{o}`" for o in (d["over"] or []))
            L.append(f"| {d['rule']} | {d['derives']} | {over} |")
        L.append("")

    L.append("## Dimensions\n")
    L.append("| Dimension | Class | Identity | Key | Serving relation | #Values | Values (closed sets) |")
    L.append("|---|---|---|---|---|---|---|")
    for d in sorted(model["dimensions"], key=lambda x: (x["class"] or "", x["name"])):
        g = d["grounding"]
        codes = [str(v["code"]) for v in d["values"] if v.get("code")]
        closed = any(v.get("closure") == "closed" for v in d["values"])
        vlist = ", ".join(f"`{c}`" for c in codes[:20]) + (" …" if len(codes) > 20 else "")
        if not codes:
            vlist = "_derived / open_"
        n = f"{len(codes)}{'*' if closed else ''}" if codes else "—"
        rel = ", ".join(f"`{r}`" for r in g["relations"]) or "—"
        kv = g["key"]
        key = ", ".join(f"`{k}`" for k in kv) if isinstance(kv, list) else (f"`{kv}`" if kv else "—")
        ik = (d.get("identity") or {}).get("kind") or "—"
        L.append(f"| **{d['name']}** | {d['class']} | {ik} | {key} | {rel} | {n} | {vlist} |")
    L.append("\n_`*` = closed enumeration (exactly these values; anything else is `__unmapped__`)._")
    L.append("_Identity = `mac.identity_kind`: iso · code · namespace_code · fk_name · composite · resolved_axis · sme_pending._")
    return "\n".join(L) + "\n"


# ===========================================================================
# A0 — model.introspection.json : an additive, generic, tolerant self-description
# of everything model.json omits. NOTHING below touches the model.json path.
# Reuses the shared tolerant helpers load / grounding_of / values_of /
# measure_law / EFFECT. Names no source; a source declaring nothing new yields
# empty sections; a missing/bad file skips, never crashes.
# ===========================================================================

# ---- shared introspection helpers -----------------------------------------
def _read_csv(path: Path) -> list[dict]:
    """Tolerant CSV read -> list of ordered row dicts; missing/bad file -> []."""
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    except Exception:
        return []


def _read_register(root: Path, name) -> list[dict]:
    """Tolerant read of data/lookups/<name>.csv -> rows (name carries no extension)."""
    if not name:
        return []
    return _read_csv(root / "data" / "lookups" / f"{name}.csv")


def _rel(root: Path, p):
    return str(p.relative_to(root)) if p else None


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes", "t")


def _iter_concepts(root: Path):
    """Yield (path, doc) for every concept file under the source; tolerant of a missing tree."""
    base = root / "ontology" / "concepts"
    if not base.is_dir():
        return
    for p in sorted(base.rglob("*.yaml")):
        yield p, load(p)


# ---------------------------------------------------------------------------
# §1.1  measures[] — measure catalog + resolved additivity law
# ---------------------------------------------------------------------------
def _register_enum(doc: dict):
    """The enumeration whose value set is realized from an external register
    (realized_by.udf == mac.canon.enum_from_register). Returns (enum, register, key_col) or None.
    Names no source — reads whatever the concept declares."""
    for en in (doc.get("enumerations") or []):
        if not isinstance(en, dict):
            continue
        rb = en.get("realized_by") or {}
        if rb.get("udf") == "mac.canon.enum_from_register":
            params = rb.get("params") or {}
            reg = params.get("register")
            if reg:
                return en, str(reg), params.get("key_column", "code")
    return None


def _surface_for_stem(doc: dict, stem):
    """Multilingual surface synonyms for a measure stem, from any enumeration's aliasBlock.
    Generic: matches on the stem part of each alias key (no hardcoded default variant); None if absent."""
    if not stem:
        return None
    for en in (doc.get("enumerations") or []):
        if not isinstance(en, dict):
            continue
        amap = ((en.get("aliases") or {}).get("map")) or {}
        for code, entry in amap.items():
            if isinstance(code, str) and code.split(".")[0] == stem and isinstance(entry, dict):
                ml = entry.get("multilingual")
                if isinstance(ml, dict):
                    return ml
    return None


def _additivity_from_type(law: dict, measure_type):
    """Resolve (type_key, {time, categorical}) from a mac.MeasureType token via the framework law.
    (None, None) when no type is declared; (type_key, None) when the law lacks that member."""
    if not measure_type:
        return None, None
    tkey = str(measure_type).split(".")[-1]        # Flow|Stock|Target|Intensive
    spec = law.get(tkey)
    if not spec:
        return tkey, None
    return tkey, {"time": spec["time"], "categorical": spec["categorical"]}


def _measure_record(**kw) -> dict:
    """Assemble one measure record with a stable key order (A0 §1.1 schema)."""
    keys = ["measure", "stem", "source_kind", "concept", "concept_file", "measure_type", "type",
            "additivity", "additivity_source", "axis_kinds", "variants", "kpi_codes", "closure",
            "grounds_relation", "identity", "realized_from", "surface", "definition"]
    return {k: kw.get(k) for k in keys}


def measures_of(root: Path, model: dict | None = None) -> list[dict]:
    """A0 §1.1 measures[] — one record per measure stem the source declares, unioning three
    provenance kinds: register (enum_from_register), inline_enum (typed inline values), and
    concept_only (additivity on the concept). Additivity is RESOLVED by joining each measure's
    mac.MeasureType through the framework law. Generic + tolerant; never mutates `model`."""
    law = measure_law()
    out: list[dict] = []

    for p, doc in _iter_concepts(root):
        c = doc.get("concept") or {}
        if c.get("class") != "measure":
            continue
        rel = str(p.relative_to(root))
        concept_name = c.get("name") or p.stem
        sem = c.get("semantics") or {}
        axis_kinds = sem.get("axis_kinds")
        ident_raw = c.get("identity") or {}
        identity = {"kind": ident_raw.get("kind"), "canonical_key": ident_raw.get("canonical_key")}
        grels = grounding_of(doc)["relations"]
        grounds_relation = grels[0] if grels else None
        definition = (c.get("definition") or "").strip() or None

        # ---- kind 1: register-backed enumeration ----
        reg = _register_enum(doc)
        if reg:
            en, register, _key = reg
            rows = _read_register(root, register)
            by_measure: dict[str, dict] = {}
            for r in rows:                                # group by measure, CSV first-seen order
                meas = (r.get("measure") or "").strip()
                code = (r.get("code") or "").strip()
                if not meas or not code:
                    continue
                mt = (r.get("measure_type") or "").strip() or None
                b = by_measure.setdefault(meas, {"codes": [], "variants": [],
                                                 "measure_type": mt, "stem": code.split(".")[0]})
                b["codes"].append(code)
                variant = (r.get("variant") or (code.split(".", 1)[1] if "." in code else None))
                if variant and variant not in b["variants"]:
                    b["variants"].append(variant)
            for meas, b in by_measure.items():
                tkey, add = _additivity_from_type(law, b["measure_type"])
                out.append(_measure_record(
                    measure=meas, stem=b["stem"], source_kind="register",
                    concept=concept_name, concept_file=rel,
                    measure_type=b["measure_type"], type=tkey,
                    additivity=add, additivity_source=b["measure_type"],
                    axis_kinds=axis_kinds, variants=b["variants"], kpi_codes=b["codes"],
                    closure=en.get("closure"), grounds_relation=grounds_relation,
                    identity=identity, realized_from=f"data/lookups/{register}.csv",
                    surface=_surface_for_stem(doc, b["stem"]), definition=None))
            continue

        # ---- kind 2: inline typed enumeration ----
        typed = [v for v in values_of(doc) if v.get("measure_type")]
        if typed:
            by_measure = {}
            for v in typed:
                code = v.get("code")
                meas = v.get("measure") or (code.split(".")[0] if code else concept_name)
                b = by_measure.setdefault(meas, {"codes": [], "variants": [],
                                                 "measure_type": v.get("measure_type"),
                                                 "stem": (code.split(".")[0] if code and "." in code else None),
                                                 "closure": v.get("closure")})
                if code:
                    b["codes"].append(code)
                    variant = code.split(".", 1)[1] if "." in code else None
                    if variant and variant not in b["variants"]:
                        b["variants"].append(variant)
            for meas, b in by_measure.items():
                mt = str(b["measure_type"]) if b["measure_type"] else None
                tkey, add = _additivity_from_type(law, b["measure_type"])
                out.append(_measure_record(
                    measure=meas, stem=b["stem"], source_kind="inline_enum",
                    concept=concept_name, concept_file=rel,
                    measure_type=mt, type=tkey,
                    additivity=add, additivity_source=mt,
                    axis_kinds=axis_kinds, variants=b["variants"], kpi_codes=b["codes"],
                    closure=b["closure"], grounds_relation=grounds_relation,
                    identity=identity, realized_from=rel,
                    surface=_surface_for_stem(doc, b["stem"]), definition=definition))
            continue

        # ---- kind 3: concept-only measure ----
        add = sem.get("additivity") if isinstance(sem.get("additivity"), dict) else None
        out.append(_measure_record(
            measure=concept_name, stem=None, source_kind="concept_only",
            concept=concept_name, concept_file=rel,
            measure_type=None, type=None,
            additivity=add, additivity_source=("concept:semantics.additivity" if add else None),
            axis_kinds=axis_kinds, variants=[], kpi_codes=[],
            closure=None, grounds_relation=grounds_relation,
            identity=identity, realized_from=rel,
            surface=_surface_for_stem(doc, (concept_name or "").lower()), definition=definition))

    return out


# ---------------------------------------------------------------------------
# §1.2  dimensions[] — enriched dims + register-backed counts/members
# ---------------------------------------------------------------------------
_SENTINEL    = re.compile(r"^__.*__$")                                    # MAC placeholder tokens
_SERVED_FLAG = re.compile(r"(?:^|_)(?:in_fact|served|present|in_data|has_data)(?:$|_)", re.I)
_TRIM_KEY    = re.compile(r"_(?:code|key|id)$", re.I)                     # id-column -> noun


def _plural(noun: str) -> str:
    if not noun:
        return noun
    if noun.endswith("y") and noun[-2:-1] not in "aeiou":
        return noun[:-1] + "ies"
    return noun if noun.endswith("s") else noun + "s"


def _noun(col: str) -> str:
    return _TRIM_KEY.sub("", col or "")


def _strip_source(name: str, source: str) -> str:
    """Drop a leading '<source>_' / '<source>.' qualifier (generic — no hardcoded source)."""
    for sep in (".", "_"):
        pre = f"{source}{sep}"
        if source and name.lower().startswith(pre.lower()):
            return name[len(pre):]
    return name


def _distinct(rows: list[dict], col, drop_sentinel: bool = False) -> int:
    seen = set()
    for r in rows:
        v = (r.get(col) or "").strip()
        if not v or (drop_sentinel and _SENTINEL.match(v)):
            continue
        seen.add(v)
    return len(seen)


def _lookups_dir(root: Path) -> Path:
    return root / "data" / "lookups"


def _register_csv(root: Path, register_name: str):
    """'brands.lookup' -> <root>/data/lookups/brands.lookup.csv (or None)."""
    if not register_name:
        return None
    p = _lookups_dir(root) / f"{register_name}.csv"
    return p if p.exists() else None


def _manifest(root: Path, register_name: str) -> dict:
    if not register_name:
        return {}
    p = _lookups_dir(root) / f"{register_name}.yaml"
    return load(p) if p.exists() else {}


def _values_grouping(doc: dict):
    rb = ((doc.get("values") or {}).get("realized_by") or {})
    if isinstance(rb, dict) and str(rb.get("udf", "")).endswith("grouping_from_register"):
        return rb.get("params") or {}, rb.get("udf")
    return None, None


def _grouping_section(root: Path, params: dict):
    """Cardinality + folded member rows for a value-set grouping (e.g. BrandCluster)."""
    reg = _register_csv(root, params.get("register") or "")
    rows = _read_csv(reg) if reg else []
    gk    = params.get("group_key")
    mem   = params.get("member")
    bools = list(params.get("bool") or [])
    carry = list(params.get("carry") or [])
    as_map = params.get("as") or {}

    g_noun, m_noun = _noun(gk), _noun(mem)
    card = {
        _plural(g_noun):  _distinct(rows, gk),                       # clusters
        f"{m_noun}_rows": len(rows),                                 # brand_rows
        _plural(m_noun):  _distinct(rows, mem, drop_sentinel=True),  # brands (sentinels dropped)
    }
    served_col = next((c for c in (carry + [b for b in bools if b not in carry])
                       if _SERVED_FLAG.search(c or "")), None)
    if served_col:
        card[f"served_{_plural(g_noun)}"] = len({
            (r.get(gk) or "").strip() for r in rows
            if (r.get(gk) or "").strip() and _truthy(r.get(served_col))
        })

    out_gk = as_map.get(gk, gk)
    bset = set(bools)
    members = []
    for r in rows:
        rec = {out_gk: (r.get(gk) or "").strip()}
        for c, v in r.items():
            if c == gk:
                continue
            rec[c] = _truthy(v) if c in bset else v
        members.append(rec)
    return card, members, _rel(root, reg)


def _members_grouping(doc: dict):
    rb = ((doc.get("members") or {}).get("realized_by") or {})
    if isinstance(rb, dict) and str(rb.get("udf", "")).endswith("grouping_from_register"):
        return rb.get("params") or {}, rb.get("udf")
    return None, None


def _family_col(manifest: dict):
    md = (manifest.get("metadata") or {}) if isinstance(manifest, dict) else {}
    for k, v in md.items():
        if isinstance(k, str) and k.endswith("_is_family") and _truthy(v):
            return k[: -len("_is_family")]
    return None


def _served_gate_rule(doc: dict):
    """A rule declaring a SERVED-vs-CATALOG distinction — i.e. the offline register is the catalog
    surface and the served count is a fact-plane measure. Requires the served/catalog contrast
    together with a fact-join signal, so a rule that merely uses 'served' as an adjective does NOT gate."""
    for r in ((doc.get("contract") or {}).get("rules") or []):
        blob = " ".join(str(r.get(k, "")) for k in ("id", "subject", "then", "never")).lower()
        if "served" in blob and "catalog" in blob and (
                "fact" in blob or "warehouse" in blob or "count(distinct" in blob):
            return r.get("id")
    return None


def _register_from_grounding(root: Path, doc: dict, canonical_key: str):
    """A snapshot register is 'keyed by' this concept iff its identity key is one of its columns.
    Derived from the grounding relation: 'src.dim_x' -> data/lookups/dim_x.lookup.csv."""
    for rel in (grounding_of(doc).get("relations") or []):
        base = rel.split(".")[-1]
        reg = _register_csv(root, f"{base}.lookup")
        if not reg:
            continue
        rows = _read_csv(reg)
        if rows and canonical_key and canonical_key in rows[0]:
            return f"{base}.lookup", reg, rows
    return None, None, None


def _reference_section(root: Path, doc: dict, identity: dict, register_name: str, reg: Path, rows: list):
    manifest = _manifest(root, register_name)
    source = ((doc.get("metadata") or {}).get("source")) or ""
    ck = identity.get("canonical_key")
    fam = _family_col(manifest)
    served_rule = _served_gate_rule(doc)

    card, grain = {}, ck
    if fam and rows and fam in rows[0]:                     # e.g. name_norm_is_family -> families
        grain = fam
        card["families"] = _distinct(rows, fam)
    if ck and rows and ck in rows[0]:
        distinct_ck = _distinct(rows, ck)
        if served_rule:                                    # offline register is a CATALOG SURFACE
            card[f"{ck}_surface"] = distinct_ck            # iso2_surface
            card["served_markets"] = None
        else:
            card[_plural(_strip_source(ck, source))] = distinct_ck   # fpl_model_code -> model_codes

    complete = served_rule is None
    note = None
    if served_rule:
        note = (f"served count is a fact-plane measure (rule '{served_rule}'), not materialised in the "
                f"offline register '{register_name}'; that register is the ISO/catalog surface "
                f"(see data/lookups/{register_name}.yaml).")
    return grain, card, complete, note, _rel(root, reg)


def dimensions_of(root: Path, model: dict) -> list[dict]:
    """A0 §1.2 dimensions[] — enrich each dimension concept with identity / grain / backing
    register + a distinct cardinality; fold members for value-set groupings. Generic and
    tolerant. Never mutates `model`."""
    out = []
    for d in (model.get("dimensions") or []):
        doc = load(root / d["file"]) if d.get("file") else {}
        ident = (doc.get("concept") or {}).get("identity") or {}
        identity = {k: ident.get(k) for k in ("kind", "canonical_key") if ident.get(k) is not None}
        rec = {
            "dimension":    d.get("name"),
            "concept":      d.get("name"),
            "concept_file": d.get("file"),
            "identity":     identity,
        }

        # (a) value-set grouping -> fold members  (BrandCluster)
        gparams, gudf = _values_grouping(doc)
        if gparams:
            card, members, realized = _grouping_section(root, gparams)
            rec.update(grain=gparams.get("group_key"), realized_from=realized,
                       backing=gudf, cardinality=card, members=members)
            out.append(rec); continue

        # (b) membership-relation grouping -> surfaced as a top-level section  (Region)
        mparams, mudf = _members_grouping(doc)
        if mparams:
            reg = _register_csv(root, mparams.get("register") or "")
            rows = _read_csv(reg) if reg else []
            gk = mparams.get("group_key")
            defs = (len({tuple((r.get(c) or "") for c in gk) for r in rows})
                    if isinstance(gk, list) else _distinct(rows, gk))
            rec.update(grain=gk, realized_from=_rel(root, reg), backing=mudf,
                       cardinality={"definitions": defs, "members": len(rows)},
                       members_surfaced_as="region_definitions / region_members (top-level)")
            out.append(rec); continue

        # (c) reference dim backed by a snapshot register  (VehicleModel / Country)
        register_name, reg, rows = _register_from_grounding(root, doc, identity.get("canonical_key"))
        if register_name:
            grain, card, complete, note, realized = _reference_section(
                root, doc, identity, register_name, reg, rows)
            rec.update(grain=grain, realized_from=realized, cardinality=card,
                       count_offline_complete=complete)
            if note:
                rec["count_note"] = note
            out.append(rec); continue

        # (d) plain enumeration / open dim -> cardinality from the inline closed value set
        vals = [v for v in (d.get("values") or []) if v.get("code")]
        rec.update(grain=identity.get("canonical_key"), realized_from=None,
                   cardinality={"values": len(vals)})
        out.append(rec)
    return out


# ---------------------------------------------------------------------------
# §1.3 / §1.4  region_definitions[] + region_members[]
# ---------------------------------------------------------------------------
_GROUPING_UDF = "mac.canon.grouping_from_register"


def _member_join_key(doc: dict):
    """Membership-grain join-key column = the concept's grounding field_role whose value ends in '.key'.
    Read from the ontology, never hardcoded."""
    fr = ((doc.get("grounding") or {}).get("field_roles")) or {}
    for col, role in fr.items():
        if isinstance(role, str) and role.endswith(".key"):
            return col
    return None


def _coerce(val, empty_to_null: bool, as_int: bool):
    """Apply the register's declared casting flags to one carried cell."""
    if val is None:
        return None
    s = str(val)
    if empty_to_null and s == "":
        return None
    if as_int and s != "":
        try:
            return int(s)
        except (TypeError, ValueError):
            return s
    return s


def _composite_groupings(root: Path):
    """Yield (doc, params) for every concept realizing members via grouping_from_register under a
    COMPOSITE (list) group_key — the namespace_code rollups surfaced at top level. Scalar-group_key
    groupings (brand clusters) are folded into dimensions[].members elsewhere, not here."""
    for _p, doc in _iter_concepts(root):
        if not isinstance(doc, dict):
            continue
        rb = ((doc.get("members") or {}).get("realized_by")) or {}
        if rb.get("udf") != _GROUPING_UDF:
            continue
        params = rb.get("params") or {}
        if not isinstance(params.get("group_key"), list):   # composite identity only
            continue
        yield doc, params


def region_grouping(root: Path) -> dict:
    """A0 §1.3/§1.4 — {region_definitions, region_members} for every composite-key grouping the
    source declares. All params (register, group_key, member, member_kind, carry, int, null_if_empty)
    read from the concept's OWN members.realized_by. Generic + tolerant."""
    definitions: list[dict] = []
    members: list[dict] = []

    for doc, params in _composite_groupings(root):
        register   = params.get("register")
        group_key  = params.get("group_key") or []
        member_col = params.get("member", "member")
        kind_col   = params.get("member_kind")
        carry      = params.get("carry") or []
        int_cols   = set(params.get("int") or [])
        empty_null = bool(params.get("null_if_empty"))
        join_key   = _member_join_key(doc)          # e.g. fpl_brand_country_code — from the grounding

        rows = _read_register(root, register)
        if not rows:
            continue

        def ident(r):   # identity string = group_key column values joined by ':'
            return ":".join(str(r.get(k, "")) for k in group_key)

        # ---- region_members[] : one row per register row, CSV order ----
        for r in rows:
            mk = r.get(kind_col) if kind_col else None
            member = r.get(member_col)
            rec = {"region_definition_used": ident(r)}
            for k in group_key:
                rec[k] = r.get(k)
            rec["member"] = member
            rec["member_kind"] = mk
            rec["iso2"] = member if mk == "iso2" else None
            if join_key:                            # brand-scheme rows carry the fact join key
                rec[join_key] = member if (mk is not None and mk != "iso2") else None
            members.append(rec)

        # ---- region_definitions[] : one row per definition, first-appearance order ----
        first: dict[str, dict] = {}
        order: list[str] = []
        for r in rows:
            key = ident(r)
            if key not in first:
                first[key] = r
                order.append(key)

        code_key = group_key[-1] if group_key else None     # collision component (the 'code')
        code_index: dict[str, set] = defaultdict(set)
        for key in order:
            code_index[str(first[key].get(code_key, ""))].add(key)

        for key in order:
            r = first[key]
            carried = {c: _coerce(r.get(c), empty_null, c in int_cols) for c in carry}
            brand = carried.get("brand")
            rec = {"region_definition_used": key}
            for k in group_key:
                rec[k] = r.get(k)
            rec["brand"] = brand
            rec["label"] = carried.get("label")
            rec["member_count"] = carried.get("n_declared")   # A0 renames n_declared -> member_count
            rec["member_kind"] = r.get(kind_col) if kind_col else None
            rec["confidence"] = carried.get("confidence")
            rec["assumption_note"] = carried.get("assumption_note")
            rec["brand_relative"] = bool(brand)
            rec["collides_with"] = sorted(code_index[str(r.get(code_key, ""))] - {key})
            definitions.append(rec)

    return {"region_definitions": definitions, "region_members": members}


# ---------------------------------------------------------------------------
# §1.5  kpi_variants — the tracking-variant axis, disjoint from firmness
# ---------------------------------------------------------------------------
def _register_variant_axis(root: Path):
    """Locate the MEASURE concept whose codes carry a `<stem>.<variant>` axis realized from a
    register (mac.canon.enum_from_register), and resolve that axis STRUCTURALLY from the register
    bytes. Generic; None when the source declares no such measure register."""
    for p, doc in _iter_concepts(root):
        if (doc.get("concept") or {}).get("class") != "measure":
            continue
        for en in (doc.get("enumerations") or []):
            rb = (en or {}).get("realized_by") or {}
            if rb.get("udf") != "mac.canon.enum_from_register":
                continue
            params = rb.get("params") or {}
            reg = params.get("register")
            if not reg:
                continue
            rows = _read_register(root, reg)
            if not rows:
                continue
            key_col = params.get("key_column") or en.get("grounds_column") or "code"
            codes = [str(r.get(key_col, "")).strip() for r in rows]
            codes = [c for c in codes if "." in c]                 # only dotted <stem>.<variant> codes
            if not codes:
                continue
            variants, seen = [], set()
            for code in codes:
                v = code.split(".", 1)[1]
                if v and v not in seen:
                    seen.add(v); variants.append(v)
            dotted = [r for r in rows if "." in str(r.get(key_col, ""))]
            grounds_column = None
            for col in (list(rows[0].keys()) if rows else []):
                if col == key_col:
                    continue
                if dotted and all(str(r.get(col, "")).strip()
                                  == str(r.get(key_col, "")).split(".", 1)[-1] for r in dotted):
                    grounds_column = col
                    break
            return {
                "concept_path": p, "doc": doc, "rows": rows, "codes": codes, "variants": variants,
                "grounds_column": grounds_column, "closure": en.get("closure"),
                "n_codes": len(codes), "n_stems": len({c.split('.', 1)[0] for c in codes}),
            }
    return None


def _contract_rules(doc: dict) -> list:
    return (((doc.get("contract") or {}).get("rules")) or [])


def _find_default_rule(doc: dict, grounds_column: str):
    """The measure concept's contract rule that DEFAULTS the variant axis. Generic — no variant literal."""
    for r in _contract_rules(doc):
        if not isinstance(r, dict):
            continue
        if str(r.get("kind", "")).endswith(".default") and grounds_column in (r.get("binds") or []):
            return r.get("id"), r
    return None, None


def _default_variant(rule: dict | None, variants: list):
    """Which variant the default rule points to — DERIVED from the rule prose, never hardcoded."""
    if not rule:
        return None
    then = str(rule.get("then", "")).lower()
    i = then.find("default")
    scan = then[i:] if i >= 0 else then
    best, best_pos = None, None
    for v in variants:
        pos = scan.find("." + v.lower())
        if pos >= 0 and (best_pos is None or pos < best_pos):
            best, best_pos = v, pos
    return best


def _find_variant_derived_measure(root: Path, variant_set: set):
    """The derived-measure rule whose `over` spans MULTIPLE variants of the SAME stem -> its `derives`."""
    for r in (load(root / "ontology" / "rules.yaml").get("rules") or []):
        if not isinstance(r, dict):
            continue
        pairs = []
        for o in (r.get("over") or []):
            if isinstance(o, str) and "." in o:
                stem, var = o.rsplit(".", 1)
                if var in variant_set:
                    pairs.append((stem, var))
        if len({v for _, v in pairs}) >= 2 and len({s for s, _ in pairs}) == 1:
            return r.get("derives")
    return None


def _find_orthogonal_axis(root: Path, variants: list, measure_path: Path):
    """The axis the tracking-variant axis is declared ORTHOGONAL to (the firmness / plan-stage axis),
    found structurally: a concept whose enum values collide BY NAME with a variant AND are excluded
    from the default reading, and which owns a contract rule asserting separateness."""
    variant_set = {v.lower() for v in variants}
    for p, doc in _iter_concepts(root):
        if p == measure_path:
            continue
        colliding: dict[str, list] = {}
        for it in (((doc.get("values") or {}).get("items")) or []):
            if not isinstance(it, dict):
                continue
            code = str(it.get("code", ""))
            cls = str(it.get("stage_class") or (code.split(".", 1)[0] if "." in code else "")).lower()
            if cls in variant_set and it.get("in_default_view") is False:
                colliding.setdefault(cls, []).append(it.get("code"))
        if not colliding:
            continue
        rule = None
        for r in _contract_rules(doc):
            if not isinstance(r, dict):
                continue
            text = " ".join(str(r.get(k, "")) for k in ("subject", "when", "then", "never")).lower()
            rid = str(r.get("id", "")).lower()
            if "tracking variant" in text and (
                    "orthogonal" in rid or "orthogonal" in text
                    or "separate" in text or "two different axes" in text):
                rule = r
                break
        if rule is None:
            continue
        return {"concept_path": p, "concept": doc.get("concept") or {}, "doc": doc,
                "rule": rule, "colliding": colliding}
    return None


def _firmness_axis_label(concept: dict, doc: dict) -> str:
    """Compose the human label for the orthogonal axis from real fields."""
    name = concept.get("name") or "?"
    m = re.search(r"\(([^)]+)\)\s*$", str(concept.get("label", "")))
    firmness = m.group(1) if m else "firmness"
    text = " ".join([str(concept.get("definition", "")),
                     str((doc.get("grounding") or {}).get("note", ""))])
    m2 = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s+column", text)
    raw = m2.group(1) if m2 else None
    return f"{name} / {firmness}" + (f" ({raw})" if raw else "")


def kpi_variants_of(root: Path, model: dict | None = None) -> dict:
    """A0 §1.5 — the tracking-variant axis (actual/plan/budget), disjoint from PlanStage firmness.
    Fully generic + tolerant; every token sourced from the real files. Returns {} when the source
    declares no register-backed variant axis."""
    axis_info = _register_variant_axis(root)
    if not axis_info:
        return {}

    variants = axis_info["variants"]
    variant_set = set(variants)
    grounds_column = axis_info["grounds_column"]

    default_rule_id, default_rule = _find_default_rule(axis_info["doc"], grounds_column)
    default_v = _default_variant(default_rule, variants)

    section = {
        "axis": None,
        "grounds_column": grounds_column,
        "closure": axis_info["closure"],
        "values": [{"variant": v, "suffix": "." + v, "default": (v == default_v)} for v in variants],
        "default_rule": default_rule_id,
        "derived_measure": _find_variant_derived_measure(root, variant_set),
    }

    orth = _find_orthogonal_axis(root, variants, axis_info["concept_path"])
    if orth:
        rid = str(orth["rule"].get("id") or "")
        section["axis"] = rid.split("orthogonal_to_", 1)[1] if "orthogonal_to_" in rid else "tracking_variant"
        cname = orth["concept"].get("name") or "?"
        coll_variant = next((v for v in variants if v != default_v and v in orth["colliding"]),
                            next(iter(orth["colliding"]), None))
        vintages = [c for c in (orth["colliding"].get(coll_variant) or []) if c]
        non_default = [v for v in variants if v != default_v]
        non_default_caps = "/".join(f"'{v.capitalize()}'" for v in non_default)
        note = (f"{cname}'s '{coll_variant}.*' firmness vintages ({', '.join(vintages)}) are NOT the "
                f".{coll_variant} tracking variant; there is no {non_default_caps} {cname} value.")
        section["distinct_from"] = {
            "axis": _firmness_axis_label(orth["concept"], orth["doc"]),
            "concept_file": str(orth["concept_path"].relative_to(root)),
            "rule": rid,
            "note": note,
        }
    else:
        section["axis"] = "tracking_variant"
        section["distinct_from"] = None

    return section


# ---------------------------------------------------------------------------
# §1.6  rules — flat catalog[] + decision_policy + kinds + index
# ---------------------------------------------------------------------------
def _kind_term(kind):
    """'mac.rule_kind.resolution' -> 'resolution'; tolerant of missing/odd values."""
    if not isinstance(kind, str) or not kind:
        return None
    return kind.rsplit(".", 1)[-1]


def _rule_kinds(mac_vocab: Path) -> list[dict]:
    """The closed rule-type taxonomy, read from the framework vocab (mac.rule_kind)."""
    rk = load(mac_vocab).get("rule_kind") or {}
    closed = bool(rk.get("closed"))
    return [{"term": t, "governs": g, "closed": closed}
            for t, g in (rk.get("terms") or {}).items()]


def _rule_ids_in(text, catalog_ids: set) -> list[str]:
    """Every catalog rule id that occurs as a whole token inside a free-text ref string."""
    if not isinstance(text, str) or not text:
        return []
    hits = []
    for rid in catalog_ids:
        i = text.find(rid)
        while i != -1:
            before = text[i - 1] if i > 0 else " "
            after = text[i + len(rid)] if i + len(rid) < len(text) else " "
            if not (before.isalnum() or before in "._") and not (after.isalnum() or after in "._"):
                hits.append(rid)
                break
            i = text.find(rid, i + 1)
    return hits


def rules_catalog(root: Path, concepts: list[Path] | None = None,
                  mac_vocab: Path = MAC_VOCAB) -> dict:
    """A0 §1.6 — union three rule homes into ONE flat catalog[] with a `family` discriminator,
    plus decision_policy (governing_rule -> rule_id + reverse cited_by), kinds (framework closed
    vocab), an index, and provenance. Full rule text (no truncation). Generic + tolerant."""
    ont = root / "ontology"
    if concepts is None:
        cdir = ont / "concepts"
        concepts = sorted(cdir.rglob("*.yaml")) if cdir.is_dir() else []

    catalog: list[dict] = []
    cited_by: dict[str, list[str]] = {}
    _RESERVED = {"family", "id", "kind_term", "home", "applies_from", "cited_by"}

    def _emit_behavioural(raw: dict, home: dict) -> None:
        if not isinstance(raw, dict):
            return
        kind = raw.get("kind")
        rec = {
            "family": "behavioural",
            "id": raw.get("id"),
            "subject": raw.get("subject"),
            "kind": kind,
            "kind_term": _kind_term(kind),
            "scope": raw.get("scope"),
            "when": raw.get("when"),
            "then": raw.get("then"),
            "never": raw.get("never"),
            "confidence": raw.get("confidence"),   # passed through as-is
            "binds": raw.get("binds", []),
            "home": home,
            "applies_from": [],
            "cited_by": [],
        }
        for k, v in raw.items():                   # pass unknown keys through verbatim
            if k not in rec and k not in _RESERVED:
                rec[k] = v
        catalog.append(rec)

    # (1) behavioural registry — query_rules.yaml
    qr_doc = load(ont / "query_rules.yaml")
    qr_meta = qr_doc.get("metadata") or {}
    qr_home = {"file": "ontology/query_rules.yaml",
               "registry": qr_meta.get("registry", "query_rules")}
    for raw in (qr_doc.get("rules") or []):
        _emit_behavioural(raw, dict(qr_home))

    # (2) source contract rules — every concept's contract.rules[]
    for p in concepts:
        doc = load(p)
        cname = ((doc.get("concept") or {}).get("name")) or p.stem
        try:
            rel = str(p.relative_to(root))
        except ValueError:
            rel = str(p)
        for raw in ((doc.get("contract") or {}).get("rules") or []):
            _emit_behavioural(raw, {"file": rel, "concept": cname})

    # (3) derived-measure rules — rules.yaml (FULL text; verbatim passthrough)
    r_doc = load(ont / "rules.yaml")
    r_meta = r_doc.get("metadata") or {}
    r_home = {"file": "ontology/rules.yaml", "layer": r_meta.get("layer", "rules")}
    for raw in (r_doc.get("rules") or []):
        if not isinstance(raw, dict):
            continue
        rec = {"family": "derived_measure", "id": raw.get("rule"), "home": dict(r_home)}
        for k, v in raw.items():
            if k not in rec:
                rec[k] = v
        catalog.append(rec)

    catalog_ids = {r["id"] for r in catalog if r.get("id")}

    # decision_policy — resolve governing_rule -> rule_id, build reverse cited_by
    dp_raw = qr_doc.get("decision_policy") or {}
    slots_out = []
    for slot in (dp_raw.get("slots") or []):
        if not isinstance(slot, dict):
            continue
        s = dict(slot)
        ids = _rule_ids_in(slot.get("governing_rule"), catalog_ids)
        s["rule_id"] = ids[0] if ids else None
        s["rule_ids"] = ids                        # additive: some slots govern several rules
        for rid in ids:
            cited_by.setdefault(rid, [])
            if slot.get("slot") not in cited_by[rid]:
                cited_by[rid].append(slot.get("slot"))
        slots_out.append(s)
    decision_policy = {k: v for k, v in dp_raw.items() if k != "slots"}
    decision_policy["slots"] = slots_out

    for r in catalog:
        if r.get("id") in cited_by and "cited_by" in r:
            r["cited_by"] = cited_by[r["id"]]

    def _index_by(keyfn):
        out: dict[str, list[str]] = {}
        for r in catalog:
            k = keyfn(r)
            if k is None or not r.get("id"):
                continue
            out.setdefault(str(k), []).append(r["id"])
        return out

    index = {
        "by_kind": _index_by(lambda r: r.get("kind_term")),
        "by_scope": _index_by(lambda r: r.get("scope")),
        "by_concept": _index_by(lambda r: (r.get("home") or {}).get("concept")),
        "by_family": _index_by(lambda r: r.get("family")),
    }

    provenance = {"sources": [
        {"file": "ontology/query_rules.yaml", "registry": qr_meta.get("registry"),
         "version": qr_meta.get("version")},
        {"file": "ontology/rules.yaml", "layer": r_meta.get("layer"),
         "schema_version": r_meta.get("schema_version")},
        {"file": "ontology/concepts/**", "kind": "contract.rules"},
    ]}

    return {
        "provenance": provenance,
        "kinds": _rule_kinds(mac_vocab),
        "catalog": catalog,
        "decision_policy": decision_policy,
        "index": index,
    }


# ---------------------------------------------------------------------------
# §1.7  edges[] + edges_meta — lossless relationship records
# ---------------------------------------------------------------------------
_EDGE_KEYS = ("realized_by", "resolved_by", "aliases", "verified_by", "confidence", "notes")


def _endpoint(ep: dict | None) -> dict:
    """Normalize an edges.yaml endpoint to {source,concept,ref,role,cardinality}, carrying extras."""
    ep = ep or {}
    out = {
        "source":      ep.get("source"),
        "concept":     ep.get("concept"),
        "ref":         ep.get("ref"),
        "role":        ep.get("role"),
        "cardinality": ep.get("cardinality"),
    }
    for k, v in ep.items():
        if k not in out:
            out[k] = v
    return out


def _card_side(c) -> str:
    """Reduce a UML multiplicity ('0..N', '1', '0..1', '*') to a single 'N' | '1' label."""
    tail = str(c or "").split("..")[-1].strip()
    if tail.upper() == "N" or tail == "*":
        return "N"
    return tail or "?"


def _cardinality_label(from_ep: dict, to_ep: dict) -> str:
    return f"{_card_side(from_ep.get('cardinality'))}:{_card_side(to_ep.get('cardinality'))}"


def _parse_join(join_rule):
    """Parse `join_rule` SQL into {clauses:[{left,right}], relations:[...]}, or None.
    Regex from mac_to_osi.py: split on ` AND `, match `<rel>.<col> = <rel>.<col>`, strip prefix."""
    if not join_rule or not isinstance(join_rule, str):
        return None
    clauses: list[dict] = []
    relations: list[str] = []
    for clause in re.split(r"\s+AND\s+", join_rule):
        m = re.match(r"\s*([\w.]+)\.(\w+)\s*=\s*([\w.]+)\.(\w+)\s*", clause)
        if not m:
            continue
        lt, lc, rt, rc = m.groups()
        lrel, rrel = lt.split(".")[-1], rt.split(".")[-1]
        clauses.append({
            "left":  {"relation": lrel, "column": lc},
            "right": {"relation": rrel, "column": rc},
        })
        for rel in (lrel, rrel):
            if rel not in relations:
                relations.append(rel)
    if not clauses:
        return None
    return {"clauses": clauses, "relations": relations}


def _edge_record(e: dict) -> dict:
    """Lossless single-edge projection. Never raises: a malformed edge yields a stub with __error__."""
    try:
        eps = e.get("endpoints") or {}
        from_ep = _endpoint(eps.get("from"))
        to_ep = _endpoint(eps.get("to"))
        join_rule = e.get("join_rule")
        rec = {
            "edge_id":     e.get("edge_id"),
            "level":       e.get("level"),
            "type":        e.get("type"),
            "from":        from_ep,
            "to":          to_ep,
            "cardinality": _cardinality_label(from_ep, to_ep),
            "join_rule":   join_rule,
            "join":        _parse_join(join_rule),
        }
        for k in _EDGE_KEYS:
            rec[k] = e.get(k)
        known = set(rec) | {"endpoints"}
        for k, v in e.items():
            if k not in known:
                rec[k] = v
        return rec
    except Exception as ex:
        return {"edge_id": (e or {}).get("edge_id"), "__error__": str(ex)}


def edges_of(root: Path) -> list[dict]:
    """A0 §1.7 edges[] — lossless, order-preserved read of ontology/edges.yaml. [] when absent."""
    p = root / "ontology" / "edges.yaml"
    if not p.exists():
        return []
    doc = load(p)
    if not isinstance(doc, dict) or "__error__" in doc:
        return []
    return [_edge_record(e) for e in (doc.get("edges") or []) if isinstance(e, dict)]


def edges_meta_of(root: Path) -> dict:
    """A0 §1.7 edges_meta — provenance from the edges.yaml header + governance + count. {} when absent."""
    p = root / "ontology" / "edges.yaml"
    if not p.exists():
        return {}
    doc = load(p)
    if not isinstance(doc, dict) or "__error__" in doc:
        return {}
    meta = dict(doc.get("metadata") or {})
    meta["governance"] = doc.get("governance")
    meta["count"] = len([e for e in (doc.get("edges") or []) if isinstance(e, dict)])
    return meta


# ---------------------------------------------------------------------------
# §1.0  meta header + assembler
# ---------------------------------------------------------------------------
def _mac_version():
    """mac_version from mac_vocabulary.yaml, else the meaning-as-code git SHA (diff-stable, no timestamp)."""
    doc = load(MAC_VOCAB)
    if isinstance(doc, dict):
        for k in ("version", "schema_version", "mac_version"):
            v = doc.get(k)
            if v:
                return str(v)
    try:
        import subprocess
        sha = subprocess.check_output(["git", "-C", str(HERE), "rev-parse", "HEAD"],
                                      stderr=subprocess.DEVNULL).decode().strip()
        return sha or None
    except Exception:
        return None


def _input_manifest(root: Path) -> list[dict]:
    """Deterministic sha256/bytes manifest of every source file the introspection reads: the three
    ontology registries, every concept, and every data/lookups CSV. Diff-stable (sorted, no timestamp)."""
    files: list[Path] = []
    ont = root / "ontology"
    for name in ("edges.yaml", "rules.yaml", "query_rules.yaml"):
        p = ont / name
        if p.exists():
            files.append(p)
    cdir = ont / "concepts"
    if cdir.is_dir():
        files += sorted(cdir.rglob("*.yaml"))
    ldir = root / "data" / "lookups"
    if ldir.is_dir():
        files += sorted(ldir.glob("*.csv"))
    seen, manifest = set(), []
    for p in files:
        if p in seen or not p.exists():
            continue
        seen.add(p)
        try:
            b = p.read_bytes()
        except Exception:
            continue
        manifest.append({"path": _rel(root, p), "sha256": hashlib.sha256(b).hexdigest(),
                         "bytes": len(b)})
    manifest.sort(key=lambda x: x["path"])
    return manifest


def _meta_header(root: Path, measures, dimensions, region, rules, edges) -> dict:
    """A0 §1.0 — source/versions/input hashes/counts. generated_at intentionally OMITTED (diff-stable)."""
    ont = root / "ontology"
    edges_doc = load(ont / "edges.yaml")
    rules_doc = load(ont / "rules.yaml")
    qr_doc = load(ont / "query_rules.yaml")
    src = ((edges_doc.get("metadata") or {}).get("source")) if isinstance(edges_doc, dict) else None
    src = src or root.name
    return {
        "$projection": "model.introspection",
        "schema_version": "0.1.0",
        "source": str(src).lower(),
        "generated_by": "meaning-as-code/tools/project_model.py::emit_introspection",
        "mac_version": _mac_version(),
        "ontology_versions": {
            "rules": (rules_doc.get("metadata") or {}).get("schema_version") if isinstance(rules_doc, dict) else None,
            "edges": (edges_doc.get("metadata") or {}).get("schema_version") if isinstance(edges_doc, dict) else None,
            "query_rules": (qr_doc.get("metadata") or {}).get("version") if isinstance(qr_doc, dict) else None,
        },
        "inputs": _input_manifest(root),
        "counts": {
            "measures": len(measures),
            "dimensions": len(dimensions),
            "region_definitions": len(region.get("region_definitions") or []),
            "region_members": len(region.get("region_members") or []),
            "rules": len((rules or {}).get("catalog") or []),
            "edges": len(edges),
        },
    }


def emit_introspection(root: Path, model: dict) -> dict:
    """A0 assembler — the additive, generic self-description model.json omits. Reads whatever the
    source declares; a source declaring nothing new yields empty sections. Never mutates `model`
    and never touches the model.json / model.md path."""
    measures = measures_of(root, model)
    dimensions = dimensions_of(root, model)
    region = region_grouping(root)
    variants = kpi_variants_of(root, model)
    rules = rules_catalog(root)
    edges = edges_of(root)
    edges_meta = edges_meta_of(root)
    return {
        "meta": _meta_header(root, measures, dimensions, region, rules, edges),
        "measures": measures,
        "dimensions": dimensions,
        "region_definitions": region.get("region_definitions") or [],
        "region_members": region.get("region_members") or [],
        "kpi_variants": variants,
        "rules": rules,
        "edges": edges,
        "edges_meta": edges_meta,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Project an applied MAC ontology into a model catalog.")
    ap.add_argument("source_root", help="applied-ontology repo root (contains ontology/)")
    ap.add_argument("--out-dir", default=None, help="output dir (default: <source_root>/projections)")
    ap.add_argument("--print", action="store_true", help="also print the Markdown to stdout")
    a = ap.parse_args()

    root = Path(a.source_root).resolve()
    if not (root / "ontology" / "concepts").is_dir():
        print(f"ERROR: {root}/ontology/concepts not found", file=sys.stderr); return 2

    model = project(root)
    md = to_markdown(root, model)
    out = Path(a.out_dir) if a.out_dir else (root / "projections")
    out.mkdir(parents=True, exist_ok=True)
    (out / "model.md").write_text(md, encoding="utf-8")
    (out / "model.json").write_text(json.dumps(model, indent=2, default=str, ensure_ascii=False), encoding="utf-8")

    # A0 — additive sibling projection; the model.json/model.md path above is untouched.
    introspection = emit_introspection(root, model)
    (out / "model.introspection.json").write_text(
        json.dumps(introspection, indent=2, default=str, ensure_ascii=False), encoding="utf-8")

    nmeas = len(model["base_measures"]); ncodes = sum(len(b["variants"]) for b in model["base_measures"].values())
    print(f"projected {root.name}: {nmeas} base measures ({ncodes} KpiCodes), "
          f"{len(model['derived'])} derived, {len(model['dimensions'])} dimensions "
          f"→ {out / 'model.md'}")
    if a.print:
        print("\n" + md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
