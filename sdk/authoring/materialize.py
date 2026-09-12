#!/usr/bin/env python3
"""materialize.py — the harvest steps that turn AUTHORED intent into a QUERYABLE, no-probe
serving surface, in the source's OWN schema:

  * MATERIALIZE — for each produced dataset, run its transform `.sql` as
    ``CREATE OR REPLACE VIEW <view_schema>.<name>`` and verify it ``SELECT``s. This closes the
    "transform authored but the view was never materialized (runtime falls back to raw)" gap.
  * LOOKUPS — profile every resolvable dim view to a ``data/lookups/<name>.lookup.csv`` (name->code)
    register so a consumer resolves an entity name to its stable code from the FLAT register ALONE,
    never by probing the raw EAV at runtime.

BOTH are OWN-SCHEMA ONLY. The hard guardrail (``assert_own_schema``) REFUSES to touch a schema
that is empty or a KNOWN SHARED / gold schema — the durable fix for the 2026-08-13 incident where a
new source (acme2) left its ``view_database`` at the shared gold ``acme`` and its
``CREATE OR REPLACE VIEW`` OVERWROTE gold's ``dim_country`` / ``dim_model``.

OFFLINE-FIRST + testable: the planning functions (``plan_materialization`` / ``plan_lookups``) and the
DDL/SQL builders are PURE — they read the descriptors + connection.yaml and return the exact SQL
strings WITHOUT any AWS call. Execution is a thin, injectable step (``run_*(execute=True, executor=…)``)
so a unit test proves the SQL the harvest WOULD run without ever calling Athena. The CLI wires
``--mode materialize`` / ``--mode lookups`` (DRY-RUN by default; ``--accept`` executes live).
"""

from __future__ import annotations

import csv
import io
import os
import re
from pathlib import Path

import yaml

from sdk.authoring.connection import load_connection
from sdk.authoring.data_plane import canonical_relation_name

# Schemas a source may NOT materialize into: empty, or a shared/gold schema owned by another source.
# The 2026-08-13 incident (acme2 -> shared `acme`) is why this is a HARD refuse, not a warning. A source
# owns exactly ONE schema (default its dataset name, e.g. `acme2`); it never writes to a shared one.
# GENERIC shared-schema names only. An estate's own shared schemas are instance specifics and are
# declared in the source-token register, never listed here.
_GENERIC_SHARED_SCHEMAS = frozenset({"gold", "default", "public", "information_schema"})


def known_shared_schemas() -> frozenset:
    """Generic shared-schema names, plus any this estate declares.

    NOT the source-token register: that one lists instance names which must not appear in the
    generic instrument, and a source's OWN name is exactly the schema it is supposed to materialize
    into. Conflating the two made `assert_own_schema` refuse every source by its own name.
    """
    from sdk import registers

    return _GENERIC_SHARED_SCHEMAS | {t.lower() for t in registers.load("shared_schemas")}

_CREATE_VIEW_RE = re.compile(r"(?is)\bCREATE\s+(?:OR\s+REPLACE\s+)?VIEW\b.*?\bAS\b\s*")


class MaterializeRefused(Exception):
    """A materialize/lookups run was refused (bad target schema, etc.) — nothing was executed."""


def _read_yaml(p: Path) -> dict:
    try:
        return yaml.safe_load(Path(p).read_text()) or {}
    except Exception:
        return {}


# --------------------------------------------------------------------------------------------------
# Target-schema resolution + the own-schema guardrail
# --------------------------------------------------------------------------------------------------


def load_view_schema(cr) -> str:
    """The source's OWN serving-view schema from connection.yaml (``view_schema`` else
    ``view_database``). Empty string if unset — the guardrail then refuses."""
    conn = load_connection(cr)
    vs = conn.get("view_schema") or conn.get("view_database") or ""
    return str(vs).strip()


def assert_own_schema(view_schema: str) -> None:
    """REFUSE unless ``view_schema`` is a real, source-owned schema. Empty or a KNOWN SHARED schema
    raises — so materialize can only ever CREATE into the source's own dedicated schema."""
    vs = (view_schema or "").strip()
    if not vs:
        raise MaterializeRefused(
            "connection.yaml view_schema/view_database is EMPTY — refusing to materialize (no "
            "own target schema). Set it to this source's own schema (default the dataset name)."
        )
    if vs.lower() in known_shared_schemas():
        raise MaterializeRefused(
            f"view_schema {vs!r} is a KNOWN SHARED schema — refusing to CREATE views there. "
            f"Incident (2026-08-13): a new source left view_database at a shared GOLD schema and "
            f"its CREATE OR REPLACE VIEW OVERWROTE gold's dim_country/dim_model. A source must "
            f"materialize ONLY into its OWN dedicated schema (default: the dataset name). "
            f"Set connection.yaml view_schema to this source's own schema."
        )


# --------------------------------------------------------------------------------------------------
# Pure DDL / SQL builders (no AWS)
# --------------------------------------------------------------------------------------------------


def view_select_body(sql_text: str) -> str:
    """The SELECT body of a transform `.sql`: strip any leading comment header + a
    ``CREATE [OR REPLACE] VIEW <x> AS`` so we can re-target the view to the OWN schema. If the file
    is already a bare SELECT (no CREATE), it is returned as-is (trimmed)."""
    m = _CREATE_VIEW_RE.search(sql_text or "")
    if m:
        return (sql_text[m.end() :]).strip()
    return (sql_text or "").strip()


def build_view_ddl(view_schema: str, name: str, sql_text: str) -> str:
    """``CREATE OR REPLACE VIEW <view_schema>.<name> AS <select body>`` — always re-targeted to the
    OWN ``view_schema`` (never whatever schema the `.sql` may have hardcoded), so we can ONLY ever
    create in the guarded own schema."""
    return f"CREATE OR REPLACE VIEW {view_schema}.{name} AS\n{view_select_body(sql_text)}"


def _dataset_name(ds_path: Path) -> str:
    d = _read_yaml(ds_path)
    nm = ((d.get("table") or {}).get("name")) or ds_path.stem
    return canonical_relation_name(nm)


def plan_materialization(cr) -> dict:
    """PURE plan (no AWS): for every produced dataset, the OWN-schema CREATE-view DDL (built from the
    sibling `.sql`) + a ``SELECT 1`` verify probe. Raises ``MaterializeRefused`` if the target schema
    is not own. ``missing_sql`` lists datasets with no sibling `.sql` (nothing to materialize)."""
    cr = Path(cr)
    view_schema = load_view_schema(cr)
    assert_own_schema(view_schema)
    views, missing = [], []
    for ds in sorted((cr / "data" / "datasets").glob("*.yaml")):
        name = _dataset_name(ds)
        sqlp = cr / "data" / "transforms" / f"{name}.sql"
        if not sqlp.exists():
            missing.append(name)
            continue
        ddl = build_view_ddl(view_schema, name, sqlp.read_text())
        views.append(
            {
                "name": name,
                "sql_file": f"data/transforms/{name}.sql",
                "ddl": ddl,
                "verify_sql": f"SELECT 1 FROM {view_schema}.{name} LIMIT 1",
            }
        )
    return {"view_schema": view_schema, "views": views, "missing_sql": missing}


# --------------------------------------------------------------------------------------------------
# Lookups: resolve which datasets carry a name->code register + the profiling SQL
# --------------------------------------------------------------------------------------------------

_CODE_RE = re.compile(r"(?i)(^iso2$|^iso3$|_code$|_id$|^code$|^id$)")
_NAME_RE = re.compile(r"(?i)(name|label|market|title|description|_de$|_en$)")


def lookup_columns(ds_obj: dict):
    """Pick (name_col, code_col) for a name->code register, or None if the dataset has no resolvable
    pair. Priority for the code: an exact iso2, then iso3, then any *_code/*_id/code/id, then the
    declared primary_key. The name is the first label-ish column that is not the code column. A
    best-effort DEFAULT (flagged, never silent) — genuine SME picks stay reviewable."""
    cols = ds_obj.get("columns") or []
    names = [c.get("name") for c in cols if c.get("name")]
    roles = {c.get("name"): (c.get("role") or "") for c in cols}

    def _first(pred):
        return next((n for n in names if pred(n)), None)

    code = (
        _first(lambda n: n.lower() == "iso2")
        or _first(lambda n: n.lower() == "iso3")
        or _first(lambda n: bool(_CODE_RE.search(n)))
        or _first(lambda n: roles.get(n) == "primary_key")
    )
    name = _first(lambda n: n != code and bool(_NAME_RE.search(n)))
    if code and name:
        return name, code
    return None


def build_lookup_sql(view_schema: str, name: str, name_col: str, code_col: str) -> str:
    """DISTINCT name->code profiling SELECT over the OWN-schema view (both sides non-null)."""
    return (
        f'SELECT DISTINCT "{name_col}" AS name, "{code_col}" AS "{code_col}" '
        f"FROM {view_schema}.{name} "
        f'WHERE "{name_col}" IS NOT NULL AND "{code_col}" IS NOT NULL '
        f"ORDER BY 1"
    )


def plan_lookups(cr) -> dict:
    """PURE plan (no AWS): for every dataset that has a resolvable name->code pair, the profiling SQL
    + the target ``data/lookups/<name>.lookup.csv``. Raises ``MaterializeRefused`` if the target
    schema is not own. ``skipped`` lists datasets with no name->code pair."""
    cr = Path(cr)
    view_schema = load_view_schema(cr)
    assert_own_schema(view_schema)
    lookups, skipped = [], []
    for ds in sorted((cr / "data" / "datasets").glob("*.yaml")):
        d = _read_yaml(ds)
        name = _dataset_name(ds)
        picks = lookup_columns(d)
        if not picks:
            skipped.append(name)
            continue
        name_col, code_col = picks
        lookups.append(
            {
                "dataset": name,
                "csv": f"data/lookups/{name}.lookup.csv",
                "name_col": name_col,
                "code_col": code_col,
                "header": ["name", code_col],
                "source_view": f"{view_schema}.{name}",
                "sql": build_lookup_sql(view_schema, name, name_col, code_col),
            }
        )
    return {"view_schema": view_schema, "lookups": lookups, "skipped": skipped}


def rows_to_lookup_csv(lk: dict, rows) -> str:
    """Serialize profiled rows to the ``name,<code_col>`` CSV (gold convention). Accepts dict rows
    ({name, <code_col>}) or 2-tuples."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(lk["header"])
    code_col = lk["code_col"]
    for r in rows or []:
        if isinstance(r, dict):
            w.writerow([r.get("name", ""), r.get(code_col, r.get("code", ""))])
        elif isinstance(r, (list, tuple)) and len(r) >= 2:
            w.writerow([r[0], r[1]])
    return buf.getvalue()


def _write_lookup_csv(cr, relpath: str, text: str) -> Path:
    """Persist a generated lookup CSV THROUGH the declared sole writer.

    This was the one remaining illegal SSOT write in the tree: a bare `.write_text()` into the
    content root, bypassing `operations.py` and therefore bypassing its containment guard. It is the
    same shape as every defect in this phase -- a second path to a thing that is supposed to have
    exactly one -- and the write-path gate reported it as `sdk/authoring/materialize.py:232`.
    """
    from sdk.authoring import operations

    return operations.write_lookup_csv(Path(cr) / relpath, text)


# --------------------------------------------------------------------------------------------------
# Live execution seam (thin; injectable — NEVER touched by the offline tests)
# --------------------------------------------------------------------------------------------------


def _conn(cr) -> dict:
    """The bundle's own connection contract. The warehouse a bundle is served from is a fact ABOUT
    THAT BUNDLE, never a constant in the tooling."""
    from sdk.authoring.connection import load_connection

    return load_connection(cr)


def _conn_region(cr) -> str:
    r = _conn(cr).get("region")
    if not r:
        raise RuntimeError(f"no region: set $AWS_REGION or declare `region:` in {cr}/connection.yaml")
    return r


def _conn_workgroup(cr) -> str:
    w = _conn(cr).get("workgroup")
    if not w:
        raise RuntimeError(
            f"no Athena workgroup: set $MAC_ATHENA_WORKGROUP or declare `workgroup:` in "
            f"{cr}/connection.yaml -- the tooling ships no default, because a workgroup belongs to "
            f"the ontology being served, not to the SDK serving it"
        )
    return w


def _new_athena_client(cr):
    """A boto3 Athena client from the ambient chain (Glue/Athena region). Isolated + boto3-only so
    it is trivially stubbable in a test; imports boto3 lazily so the module loads with no AWS SDK."""
    import boto3

    region = os.environ.get("MAC_GLUE_REGION") or os.environ.get("AWS_REGION") or _conn_region(cr)
    profile = os.environ.get("AWS_PROFILE")
    sess = boto3.Session(profile_name=profile) if profile else boto3.Session()
    return sess.client("athena", region_name=region)


def _athena_executor(cr, view_schema: str):
    """Build a live ``executor(sql) -> list[rows]`` over Athena. Constructed only when actually
    executing; the offline tests inject their own executor.

    HYBRID by verb: the ask-path ``AthenaSQL.run()`` is DELIBERATELY read-only (so /ask can never
    mutate) — it rejects ``CREATE OR REPLACE VIEW``. But materialize is the ONE build step whose job
    IS to issue DDL. So reads (SHOW TABLES, verify SELECT, lookups profiling) keep flowing through the
    tested ``AthenaSQL.run()`` (header-stripping + typing), while WRITE statements are driven straight
    through boto3 ``start_query_execution`` — the sole sanctioned DDL seam, own-schema-guarded upstream."""
    import sys as _sys

    _chat = str(Path(__file__).resolve().parents[1].parent / "services" / "chat" / "src")
    if _chat not in _sys.path:
        _sys.path.insert(0, _chat)
    from chat.sql import AthenaSQL, is_read_only

    athena = _new_athena_client(cr)
    wg = os.environ.get("MAC_ATHENA_WORKGROUP") or _conn_workgroup(cr)
    eng = AthenaSQL(
        athena=athena, workgroup=wg, output_location=None, max_rows=100000, timeout_s=300
    )

    def _ddl(sql):
        """Drive a WRITE statement (CREATE OR REPLACE VIEW / DROP) directly via boto3 + poll to
        terminal state. DDL returns no result set, so nothing is fetched."""
        import time

        qid = athena.start_query_execution(QueryString=sql, WorkGroup=wg)["QueryExecutionId"]
        while True:
            st = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
            state = st["State"]
            if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
            time.sleep(0.5)
        if state != "SUCCEEDED":
            raise RuntimeError(
                f"Athena {state}: {st.get('StateChangeReason', '')} "
                f":: {sql.strip().splitlines()[0][:120]}"
            )
        return []

    def _run(sql):
        return (eng.run(sql) or {}).get("rows", []) if is_read_only(sql) else _ddl(sql)

    return _run


def _show_tables(executor, view_schema: str) -> set:
    """Best-effort SHOW TABLES collision snapshot; tolerant of the driver's row shape."""
    try:
        rows = executor(f"SHOW TABLES IN {view_schema}") or []
    except Exception:
        return set()
    out = set()
    for r in rows:
        if isinstance(r, dict):
            out |= {str(v) for v in r.values() if v}
        elif isinstance(r, (list, tuple)):
            out |= {str(v) for v in r if v}
        elif r:
            out.add(str(r))
    return out


# --------------------------------------------------------------------------------------------------
# CLI-wired runners (DRY-RUN by default; execute=True runs live via the injected/live executor)
# --------------------------------------------------------------------------------------------------


def run_materialize(cr, *, execute: bool = False, executor=None) -> int:
    """Plan + (optionally) CREATE OR REPLACE each own-schema view, then verify it SELECTs. DRY-RUN
    by default (prints the plan, no AWS). ``execute=True`` runs live; ``executor`` is injectable."""
    plan = plan_materialization(cr)  # raises MaterializeRefused on a non-own schema
    vs = plan["view_schema"]
    print(
        f"materialize {Path(cr).name}: view_schema={vs}; {len(plan['views'])} view(s); "
        f"missing .sql: {plan['missing_sql'] or 'none'}"
    )
    for v in plan["views"]:
        print(f"  - {vs}.{v['name']}  <- {v['sql_file']}")
    if not execute:
        print(
            "  DRY-RUN (no AWS) — re-run with --accept to CREATE OR REPLACE + verify the views live."
        )
        return 0
    if executor is None:
        executor = _athena_executor(cr, vs)
    existing = _show_tables(executor, vs)  # collision snapshot
    collide = [v["name"] for v in plan["views"] if v["name"] in existing]
    print(
        f"  SHOW TABLES {vs}: {len(existing)} existing object(s); will REPLACE: {collide or 'none'}"
    )
    created = 0
    for v in plan["views"]:
        executor(v["ddl"])  # CREATE OR REPLACE VIEW <vs>.<name> AS ...
        executor(v["verify_sql"])  # SELECT 1 ... — prove it is queryable
        created += 1
        print(f"  created + verified {vs}.{v['name']}")
    print(f"materialize: {created} view(s) created + verified in {vs}.")
    return 0


def run_lookups(cr, *, execute: bool = False, executor=None) -> int:
    """Plan + (optionally) profile each resolvable dim view to ``data/lookups/<name>.lookup.csv``.
    DRY-RUN by default (prints the plan, no AWS). ``execute=True`` runs live; ``executor`` injectable."""
    plan = plan_lookups(cr)  # raises MaterializeRefused on a non-own schema
    vs = plan["view_schema"]
    print(
        f"lookups {Path(cr).name}: view_schema={vs}; {len(plan['lookups'])} lookup(s); "
        f"skipped (no name->code pair): {plan['skipped'] or 'none'}"
    )
    for lk in plan["lookups"]:
        print(f"  - {lk['csv']}  <- {lk['name_col']}->{lk['code_col']} on {lk['source_view']}")
    if not execute:
        print("  DRY-RUN (no AWS) — re-run with --accept to profile + write the lookup CSVs.")
        return 0
    if executor is None:
        executor = _athena_executor(cr, vs)
    written = 0
    for lk in plan["lookups"]:
        rows = executor(lk["sql"]) or []
        _write_lookup_csv(cr, lk["csv"], rows_to_lookup_csv(lk, rows))
        written += 1
        print(f"  wrote {lk['csv']} ({len(rows)} row(s))")
    print(f"lookups: {written} CSV(s) written.")
    return 0
