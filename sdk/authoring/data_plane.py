#!/usr/bin/env python3
"""Data-plane authoring — the harvest's "step 1": turn a raw Glue table (+ live Athena
profiling + SME context) into the MAC DATA PLANE, matching cap-ontology-fpl/data:

  data/sources/<t>.yaml     observed raw schema-of-record  (TableFile)
  data/quality/register     the DQ issues found            (free YAML)
  data/transforms/<t>.yaml  proposed cleansing             (TransformFile)
  data/datasets/<t>.yaml    the AI-friendly clean shape    (TableFile)

One Bedrock call per table emits all four (kept mutually consistent), then each is
validated against mac.schema.json (sources/datasets→TableFile, transforms→Transform-
File; quality is free YAML) with the generic enum autofix. Live profiling (null-share,
distinct, min/max, row count) is injected so the model can ground DQ findings in data,
not just names.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import yaml
from jsonschema import validators as jsv

from sdk.authoring.authoring import _SEMANTIC, _strip_fences, grep_context

_ROOT = Path(__file__).resolve().parent.parent
# chat.sql (the AthenaSQL executor) lives at REPO-ROOT services/chat/src (not under sdk/),
# and is not pip-installed — _ROOT is the sdk/ dir, so go up one level to the repo root.
_CHAT_SRC = str(_ROOT.parent / "services" / "chat" / "src")
if _CHAT_SRC not in sys.path:
    sys.path.insert(0, _CHAT_SRC)
from sdk.grammar.resolve import load_schema as _load_schema  # ONE schema home

SCHEMA = _load_schema()


def _validator(defname: str):
    sub = dict(SCHEMA["$defs"][defname])
    sub["$defs"] = SCHEMA["$defs"]
    return jsv.validator_for(SCHEMA)(sub)


_TABLEFILE = _validator("TableFile")
_TRANSFORMFILE = _validator("TransformFile")
_ORDERABLE = (
    "int",
    "bigint",
    "double",
    "float",
    "decimal",
    "date",
    "timestamp",
    "smallint",
    "tinyint",
    "real",
    "numeric",
)

# DE-FPL'd (Phase 6): the source LABEL and the curated view SCHEMA are no longer hardcoded —
# they are read from mac.project.yaml via sdk.project.source_ident and substituted into the two
# `{{SOURCE_LABEL}}` / `{{VIEW_SCHEMA}}` sentinels below by dp_sys_prompt(). `.replace()` (not an
# f-string / %-format) is used deliberately: the prompt body carries literal `{` `}` (YAML dict
# examples) and a literal `%` ("null in 9.8% of rows"), either of which would break format-string
# interpolation. For gaps/fpl the sentinels resolve to `FPL` / `fpl`, so the emitted shape is
# byte-identical to the prior hardcoded prompt.
_DP_SYS_TEMPLATE = """You are a MAC data-engineer. Given ONE raw Glue table (its schema, LIVE column profile, and SME context), author the MAC DATA PLANE for it: the observed source, the data-quality issues, the proposed cleansing transform, the produced clean dataset, and the full realizing view SQL. Emit ONE YAML document with exactly these five top-level keys: `source`, `dq_issues`, `transform`, `dataset`, `transform_sql`.

Every file carries metadata.schema_version: '0.1.13'.

`source`  (the raw schema-of-record — validated as a TableFile):
  metadata: {table: <bare_name>, source: {{SOURCE_LABEL}}, kind: raw_source, external: true, observed: <date>, provenance: "Glue + Athena profile", schema_version: '0.1.13', status: observed, owner: data-platform-team}
  table: {name: <bare_name>, schema: <catalog>.<db>, description: "...", confidence: C}
  columns:                       # EVERY column; role is ALWAYS 'value' for a raw source ("observed, no claim")
    - {name: <col>, type: <verbatim glue type>, role: value, description: <business meaning if known, else "">, confidence: C|I|Q}

`dq_issues`  (a list of data-quality findings — free shape, ground each in the PROFILE or SME docs; empty list if none):
    - id: DQ-<DOMAIN>-<NN>-<slug>
      title: "..."
      severity: high|medium|low          # high=wrong value can reach a consumer; medium=coverage/precision gap; low=cosmetic
      confidence: C|I|Q                  # C=measured live (cite the profile number), I=spot-checked/inferred, Q=needs-SME
      finding: "<what, with the measured count/percent from the profile>"
      current_handling: "<what the proposed transform does, or 'NOT fixed — NEEDS_SME'>"
      residual_risk: "..."
      sme_owner: "<role> — <what they must ratify>"

`transform`  (proposed cleansing — validated as a TransformFile):
  metadata: {schema_version: '0.1.13', pipeline: <bare_name>, source: {{SOURCE_LABEL}}, layer: data-transformation, status: draft, owner: data-platform-team}
  produces:
    relation: {{VIEW_SCHEMA}}.<bare_name>   # OWN-schema serving view; name == the raw table's BASE name, NO _clean affix
    grain: "one row per (...)"
    sql_file: <bare_name>.sql               # the writer creates this sibling .sql from `transform_sql` (below) — do NOT inline SQL here
  inputs:
    - {relation: <catalog>.<db>.<bare_name>, kind: raw_source, role: raw_source, descriptor: data/sources/<bare_name>.yaml}
  transforms:                    # ONE entry per DQ issue you can cleanse; [] if the raw table is already clean
    - id: <kebab-id>
      impurity_class: <one of: eav_shape | identifier_sprawl | master_coverage_gap | opaque_code | missing_attribute | orphan_value | nonproduction_noise | axis_conflation | date_literal_trap | type_truncation | vintage_mixing | multi_vintage_inflation | role_duplication | label_vs_identity | identity_ambiguity>
      raw_defect: "..."
      rule: "<the cleansing rule in prose>"
      sql: "<a SHORT single-line SQL fragment realizing JUST this rule (documentation; the FULL view body goes in the top-level transform_sql)>"
      establishes_guarantee: "<the clean fact the ontology may then rely on>"
      status: authored
  open_transforms:               # issues you CANNOT safely cleanse without SME — carried, not hidden ([] if none)
    - {id: <kebab-id>, impurity_class: <taxon>, raw_defect: "...", proposed_rule: "...", status: PROPOSED}

`dataset`  (the produced clean shape — validated as a TableFile):
  metadata: {table: <bare_name>, source: {{SOURCE_LABEL}}, schema_version: '0.1.13', status: authored, date: <date>, owner: data-platform-team}
  table: {name: <bare_name>, schema: {{VIEW_SCHEMA}}, type: view, confidence: C}
  columns:                       # the POST-cleansing columns + types + roles
    - {name: <col>, description: "...", type: <post-cast type>, role: primary_key|foreign_key|value|discriminator|composite_key_part|audit, confidence: C}
  derived_from: {pipeline: data/transforms/<bare_name>.yaml}
  foreign_keys:                  # [] if none
    - {name: fk_<col>, from_column: <col>, to_table: <other_dataset_bare_name>, to_column: <col>, notes: "..."}

`transform_sql`  (the FULL, materializable view body — a plain multi-line string at the TOP LEVEL, NOT nested in `transform`):
  ONE CREATE-able statement — `CREATE OR REPLACE VIEW {{VIEW_SCHEMA}}.<bare_name> AS <SELECT ...>` — that realizes the
  entire cleansing (CTEs allowed), one row per the grain declared above. The writer extracts it VERBATIM to the sibling
  data/transforms/<bare_name>.sql and points the transform at it via produces.sql_file. Emit a real, runnable view body
  (the same shape the warehouse would deploy), never a describe-only sketch. If the raw table is already clean, emit a
  pass-through `CREATE OR REPLACE VIEW {{VIEW_SCHEMA}}.<bare_name> AS SELECT <cols> FROM <catalog>.<db>.<bare_name>`.

RULES:
- Ground in the REAL columns + the LIVE profile. Cite profile numbers in DQ findings (e.g. "iso2 is null in 9.8% of rows (105 of 1076)"). NEVER invent a column or a statistic.
- Classify each defect with the closest impurity_class from the closed list above. If you cannot safely propose SQL, put it in open_transforms with status: PROPOSED, not transforms.
- A CODE/LOOKUP table is usually already flat (transforms may be []). A raw EAV/wide/fact table usually needs transforms.
- NO-PROBE MANDATE (always): the produced clean shape MUST let a consumer resolve any entity name -> code and read any attribute from the FLAT view + a name->code lookup register ALONE — NEVER by scanning the raw EAV at runtime. So for an EAV/wide table the transform MUST flatten it to ONE ROW PER ENTITY with every attribute as a plain column AND expose the stable name->code key columns (so the ontology can ship a data/lookups/<bare_name>.lookup.csv register + a no_probe_guarantee). Write CREATE-able view DDL (materializable), not describe-only SQL.
- CANONICAL NAME (the cross-reference rule): the produced serving relation carries the raw table's BASE name in ALL of — the dataset file stem, dataset.table.name, transform.metadata.pipeline, the produces.relation tail, and any lookup — with NO `clean_`/`_clean` prefix or suffix. The own view-schema ({{VIEW_SCHEMA}}) already separates serving from raw, so a _clean affix is exactly the cross-reference bug. Use <bare_name> everywhere; the writer additionally FORCES this.
- SQL LIVES IN A SIBLING FILE: emit the full materializable view body ONCE, in the top-level `transform_sql`; the transform YAML carries only a `produces.sql_file` pointer + prose (impurity_class/rule/guarantee). NEVER a multi-line inline `sql:` scalar in the YAML.
- Output ONLY the YAML document (the five keys), no prose, no fences."""


def dp_sys_prompt(source_label: str = "FPL", view_schema: str = "fpl") -> str:
    """The data-plane system prompt with the source LABEL + curated view SCHEMA substituted
    from mac.project.yaml (via sdk.project.source_ident). Defaults preserve the historical
    gaps/fpl text for any caller that doesn't pass an identity."""
    return _DP_SYS_TEMPLATE.replace("{{SOURCE_LABEL}}", source_label).replace(
        "{{VIEW_SCHEMA}}", view_schema
    )


# Backward-compatible module constant (the gaps/fpl rendering) for external importers.
DP_SYS_PROMPT = dp_sys_prompt()


def canonical_relation_name(name: str) -> str:
    """The ONE canonical serving-relation name: the raw table's base name with any
    ``clean_`` / ``_clean`` (or ``clean-`` / ``-clean``) affix stripped. The own view-schema
    already separates serving from raw, so a `_clean` affix is redundant divergence — it was
    exactly the cross-reference bug (stem `v_x` vs physical `v_x_clean` vs grounding tail). This
    makes file-stem == table.name == produces.relation tail == lookup source_view identical.
    Idempotent; a name with no affix is returned unchanged."""
    n = (name or "").strip()
    prev = None
    while n != prev:
        prev = n
        n = re.sub(r"(?i)^clean[_-]+", "", n)
        n = re.sub(r"(?i)[_-]+clean$", "", n)
    return n or (name or "").strip()


def _canonicalize_names(doc: dict, base: str, view_schema: str) -> None:
    """Force the canonical serving-relation ``base`` name across the emitted data-plane doc so
    that file-stem == dataset.table.name == transform.metadata.pipeline == produces.relation tail
    == ``base`` (the raw table's BASE name, NO `_clean` affix) and the dataset binds to the OWN
    ``view_schema``. Mutates ``doc`` in place; tolerates a partial/missing doc."""
    ds = doc.get("dataset")
    if isinstance(ds, dict):
        tbl = ds.get("table")
        if isinstance(tbl, dict):
            tbl["name"] = base
            tbl["schema"] = view_schema
        meta = ds.get("metadata")
        if isinstance(meta, dict) and "table" in meta:
            meta["table"] = base
        dfrom = ds.get("derived_from")
        if isinstance(dfrom, dict):
            dfrom["pipeline"] = f"data/transforms/{base}.yaml"
    tr = doc.get("transform")
    if isinstance(tr, dict):
        meta = tr.get("metadata")
        if isinstance(meta, dict):
            meta["pipeline"] = base
        prod = tr.get("produces")
        if isinstance(prod, dict):
            prod["relation"] = f"{view_schema}.{base}"


def _lift_transform_sql(doc: dict) -> str | None:
    """Pull the FULL materializable view body OUT of the doc BEFORE validation and return it.

    The body is authored at the top level as ``transform_sql`` (a plain string). Defensively we
    also strip any inline ``sql`` / ``x-sql`` the model may have leaked into ``transform.produces``
    — ``produces`` is ``additionalProperties: false`` (only relation/grain/serves_ontology/
    sql_file), so an inline body there would FAIL validation and refuse the whole transform. Returns
    the body text (or None); the sole writer materializes it to the sibling ``.sql``."""
    body = doc.get("transform_sql")
    tr = doc.get("transform")
    if isinstance(tr, dict):
        prod = tr.get("produces")
        if isinstance(prod, dict):
            for k in ("sql", "x-sql"):
                leaked = prod.pop(k, None)
                if not body and leaked:
                    body = leaked
    return str(body) if body and str(body).strip() else None


def profile_table(athena, db: str, table: str, cols: list[dict], timeout_s: float = 150.0) -> dict:
    """One Athena scan -> {row_count, columns:{col:{null_frac,distinct,min?,max?}}}."""
    from chat.sql import AthenaSQL

    wg = os.environ.get("MAC_ATHENA_WORKGROUP") or "acme-analytics-wg"
    eng = AthenaSQL(
        athena=athena, workgroup=wg, output_location=None, max_rows=5, timeout_s=timeout_s
    )
    sel = ["count(*) n"]
    for i, c in enumerate(cols):
        q = '"' + c["name"].replace('"', "") + '"'
        sel += [f"count({q}) nn{i}", f"approx_distinct({q}) d{i}"]
        if any(str(c.get("type", "")).lower().startswith(o) for o in _ORDERABLE):
            sel += [f"try_cast(min({q}) as varchar) mn{i}", f"try_cast(max({q}) as varchar) mx{i}"]
    sql = f'SELECT {", ".join(sel)} FROM "{db}"."{table}"'
    res = eng.run(sql)
    row = (res.get("rows") or [{}])[0]
    n = int(row.get("n") or 0)
    out = {"row_count": n, "columns": {}}
    for i, c in enumerate(cols):
        nn = int(row.get(f"nn{i}") or 0)
        cd = {
            "null_frac": round(1 - nn / n, 4) if n else None,
            "distinct": int(row.get(f"d{i}") or 0),
        }
        if f"mn{i}" in row:
            cd["min"], cd["max"] = row.get(f"mn{i}"), row.get(f"mx{i}")
        out["columns"][c["name"]] = cd
    return out


def _profile_md(prof: dict) -> str:
    lines = [
        f"row_count: {prof['row_count']}",
        "| column | null% | distinct | min | max |",
        "|---|---|---|---|---|",
    ]
    for col, d in prof["columns"].items():
        nf = "" if d["null_frac"] is None else f"{d['null_frac'] * 100:.1f}%"
        lines.append(
            f"| {col} | {nf} | {d['distinct']} | {d.get('min', '')} | {d.get('max', '')} |"
        )
    return "\n".join(lines)


def _autofix(obj, validator) -> list[str]:
    """Generic conformance autofix (spelling→schema enum, SEMANTIC map, null-key drop)."""
    fixes = []
    for err in sorted(validator.iter_errors(obj), key=lambda e: list(e.path)):
        parts = list(err.path)
        path = "/".join(str(x) for x in parts)
        if getattr(err, "validator", None) != "enum" or not parts:
            continue
        allowed = list(err.validator_value or [])
        bad = err.instance
        if not isinstance(bad, str):
            continue
        newv = next(
            (
                c
                for c in (
                    bad.replace("_", "-"),
                    bad.replace("-", "_"),
                    bad.lower(),
                    bad.replace("_", "-").lower(),
                    _SEMANTIC.get(bad),
                )
                if c and c in allowed
            ),
            None,
        )
        if newv is None:
            continue
        cur = obj
        for p in parts[:-1]:
            cur = cur[p]
        if cur.get(parts[-1]) == bad:
            cur[parts[-1]] = newv
            fixes.append(f"{path}: '{bad}' -> '{newv}'")
    return fixes


def _errs(obj, validator) -> list[str]:
    return [
        f"{'/'.join(str(x) for x in e.path) or '(root)'}: {e.message[:140]}"
        for e in sorted(validator.iter_errors(obj), key=lambda e: list(e.path))[:6]
    ]


def author(
    db: str,
    table: str,
    schema_md: str,
    profile: dict,
    context: str,
    *,
    model: str,
    effort: str,
    region: str,
    thinking_budget: int | None = None,
    source_label: str = "FPL",
    view_schema: str = "fpl",
    cache=None,
) -> dict:
    """Author the four-key data-plane YAML for one table via ONE LLM call.

    The system prompt is DE-FPL'd — the source label + view schema are substituted from the
    caller (resolved from mac.project.yaml). The Bedrock call routes through the shared
    harvest_model layer: a single model-swappable builder (dispatch on id prefix, thinking_budget
    knob) wrapped by an optional content-addressed ``cache`` so an unchanged input re-runs
    byte-identically. When ``cache`` is None the call runs live (uncached) — the legacy path.
    """
    from sdk.authoring.harvest_model import make_invoker

    system = dp_sys_prompt(source_label, view_schema)
    human = (
        f"## RAW TABLE\n\ncatalog.db = {db}\n\n{schema_md}\n\n"
        f"## LIVE COLUMN PROFILE (Athena)\n\n{_profile_md(profile)}\n\n"
        f"## SME CONTEXT (use what's relevant)\n\n{context or '(none)'}\n\n"
        f"Author the four-key data-plane YAML for `{table}` now. Output only YAML."
    )
    from botocore.config import Config

    cfg = Config(
        read_timeout=900, connect_timeout=20, retries={"max_attempts": 4, "mode": "adaptive"}
    )
    invoke = make_invoker(
        model, effort, 16000, region=region, thinking_budget=thinking_budget, botocore_config=cfg
    )
    if cache is not None:
        raw = cache.complete(
            system,
            human,
            model=model,
            effort=effort,
            thinking_budget=thinking_budget,
            invoke_fn=invoke,
        )
    else:
        raw = invoke(system, human)
    doc = yaml.safe_load(_strip_fences(raw))
    return doc if isinstance(doc, dict) else {}


def process(
    db: str,
    table: str,
    schema_md: str,
    cols: list[dict],
    athena,
    ctx_dir: Path | None,
    terms: list[str],
    *,
    model: str,
    effort: str,
    region: str,
    thinking_budget: int | None = None,
    source_label: str = "FPL",
    view_schema: str = "fpl",
    cache=None,
) -> dict:
    """Profile + author + validate the 4 data-plane files for one table."""
    prof = profile_table(athena, db, table, cols)
    context = grep_context(ctx_dir, terms) if ctx_dir else ""
    doc = author(
        db,
        table,
        schema_md,
        prof,
        context,
        model=model,
        effort=effort,
        region=region,
        thinking_budget=thinking_budget,
        source_label=source_label,
        view_schema=view_schema,
        cache=cache,
    )

    # CANONICALIZE first (drop any `_clean` divergence, bind the dataset to the OWN view_schema)
    # and LIFT the full view body out of the doc BEFORE validation. `base` is the one canonical
    # serving-relation name and becomes the descriptor file stem (persist_descriptors), so
    # file-stem == dataset.table.name == produces.relation tail == lookup source_view.
    base = canonical_relation_name(table)
    sql_body = _lift_transform_sql(doc)  # strips any inline produces.sql that would fail validation
    _canonicalize_names(doc, base, view_schema)

    files, statuses = {}, {}
    for key, validator, kind in (
        ("source", _TABLEFILE, "source"),
        ("dataset", _TABLEFILE, "dataset"),
        ("transform", _TRANSFORMFILE, "transform"),
    ):
        obj = doc.get(key)
        if not isinstance(obj, dict):
            statuses[kind] = "missing"
            continue
        fixes = _autofix(obj, validator)
        errs = _errs(obj, validator)
        statuses[kind] = "valid" if not errs and not fixes else "fixed" if not errs else "invalid"
        files[kind] = {"obj": obj, "errors": errs, "fixes": fixes}
    if "transform" in files:
        files["transform"]["sql_body"] = sql_body  # the sole writer extracts this to <base>.sql
    dq = doc.get("dq_issues") or []
    if isinstance(dq, list) and dq:
        files["dq"] = {"obj": dq}
        statuses["dq"] = f"{len(dq)} issues"
    return {
        "table": base,
        "relation_bare": base,
        "row_count": prof["row_count"],
        "statuses": statuses,
        "files": files,
        "profile": prof,
    }
