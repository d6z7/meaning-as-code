#!/usr/bin/env python3
"""Offline (no-AWS, no-billing) proof of the right-first-time harvest hardening
(HARVEST_RIGHT_FIRST_TIME.md). Each test pins ONE default-not-opt-in behaviour:

  (a) CANONICAL NAME — canonicalization drops the `_clean` divergence so file-stem == table.name ==
      transform.pipeline == produces.relation tail, all bound to the OWN view_schema.
  (b) SQL EXTRACTED — persist_descriptors (the SOLE writer) writes the view body to a sibling
      data/transforms/<name>.sql and leaves ONLY a `produces.sql_file` pointer — never inline SQL.
  (c) OWN-SCHEMA SCAFFOLD — scaffold defaults connection.example.yaml view_database/view_schema to the
      source's OWN dataset name (never a shared/gold schema) + declares/creates the lookups plane.
  (d) MATERIALIZE / LOOKUPS — the plan builders emit the exact own-schema DDL + name->code SQL WITHOUT
      any Athena call; the own-schema guardrail refuses a shared/empty schema; the execute path drives
      an injected executor (and _new_athena_client is boto3-only / stubbable — no network).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest
import yaml


def _declare_bundle(content_root):
    """Mark a fixture tree as a real bundle.

    `operations._assert_in_sources` used to accept any path with a component CONTAINING "sources",
    so `tmp_path/sources/acme/widgets` passed by accident. The guard now requires the declaration a
    bundle actually carries -- `mac.project.yaml` at its root -- because the old test judged by
    directory NAME and therefore refused two of the three real bundles. A fixture standing in for a
    bundle has to declare itself like one.
    """
    cr = Path(content_root)
    cr.mkdir(parents=True, exist_ok=True)
    (cr / "mac.project.yaml").write_text(
        "spec_version: mac.container/1\nmetadata:\n  project: fixture\n", encoding="utf-8"
    )
    return cr


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root -> `sdk` importable
from sdk.authoring import materialize, operations
from sdk.authoring.data_plane import _canonicalize_names, canonical_relation_name
from sdk.cli import harvest


@pytest.fixture(autouse=True)
def _no_deployment_override(monkeypatch):
    # keep connection resolution deterministic (no out-of-band overlay leaking from the shell)
    monkeypatch.delenv("DEPLOYMENT_CONFIG", raising=False)


# ------------------------------------------------------------------ (a) canonical name
def test_canonical_relation_name_strips_clean_affix():
    assert canonical_relation_name("dim_country_clean") == "dim_country"
    assert canonical_relation_name("clean_dim_model") == "dim_model"
    assert canonical_relation_name("v_orders-clean") == "v_orders"
    assert canonical_relation_name("dim_country") == "dim_country"  # no affix -> unchanged
    assert canonical_relation_name("clean_x_clean") == "x"  # both ends
    assert canonical_relation_name("dim_country_clean") == canonical_relation_name(
        canonical_relation_name("dim_country_clean")
    )  # idempotent


def test_canonicalization_aligns_stem_tablename_and_relation():
    """The model emitted a `_clean` divergence + wrong schema; canonicalization forces the ONE base
    name across dataset.table.name / metadata.table / derived_from / transform.pipeline / relation,
    and the file stem the harvest uses (res['table'] == base) equals table.name — no `_clean`."""
    view_schema, raw_table = "acme2", "dim_country"
    doc = {
        "dataset": {
            "metadata": {"table": "dim_country_clean"},
            "table": {"name": "dim_country_clean", "schema": "wrong", "type": "view"},
            "derived_from": {"pipeline": "data/transforms/dim_country_clean.yaml"},
        },
        "transform": {
            "metadata": {"pipeline": "dim_country_clean"},
            "produces": {"relation": "wrong.dim_country_clean", "grain": "one per country"},
        },
    }
    base = canonical_relation_name(raw_table)  # the harvest's res["table"] == this
    _canonicalize_names(doc, base, view_schema)
    assert base == "dim_country"
    assert doc["dataset"]["table"]["name"] == base
    assert doc["dataset"]["metadata"]["table"] == base
    assert doc["dataset"]["table"]["schema"] == view_schema
    assert doc["dataset"]["derived_from"]["pipeline"] == f"data/transforms/{base}.yaml"
    assert doc["transform"]["metadata"]["pipeline"] == base
    assert doc["transform"]["produces"]["relation"] == f"{view_schema}.{base}"
    stem = base  # persist_descriptors names the file from res["table"]
    assert stem == doc["dataset"]["table"]["name"]  # file-stem == table.name
    assert "_clean" not in stem and "clean_" not in stem


# ------------------------------------------------------------------ (b) SQL extracted
def test_persist_extracts_sql_to_sibling_and_leaves_only_pointer(tmp_path):
    _declare_bundle(tmp_path / "sources" / "acme" / "widgets")
    data = tmp_path / "sources" / "acme" / "widgets" / "data"
    stem = "dim_country"
    body = (
        "CREATE OR REPLACE VIEW acme2.dim_country AS\n"
        "SELECT acme_brand_country_code, market, iso2\n"
        "FROM raw.dim_country_eav\nGROUP BY 1, 2, 3\n"
    )
    files = {
        "transform": {
            "obj": {
                "metadata": {"pipeline": stem},
                "produces": {"relation": f"acme2.{stem}", "grain": "one row per country"},
                "inputs": [{"relation": "raw.dim_country_eav"}],
                "transforms": [
                    {"id": "eav-pivot", "rule": "pivot", "sql": "max(case when a=b then v end)"}
                ],
            },
            "sql_body": body,
        },
        "dataset": {"obj": {"table": {"name": stem}, "columns": []}},
    }
    out = operations.persist_descriptors(
        data, stem, files, {"transform": "valid", "dataset": "valid"}
    )

    sqlp = data / "transforms" / f"{stem}.sql"
    assert sqlp.exists() and sqlp.read_text() == body  # full CREATE-able body -> sibling .sql
    assert f"{stem}.sql" in out["sql_files"]

    ty = yaml.safe_load((data / "transforms" / f"{stem}.yaml").read_text())
    assert ty["produces"]["sql_file"] == f"{stem}.sql"  # only a POINTER in the YAML
    assert "sql" not in ty["produces"]
    dumped = (data / "transforms" / f"{stem}.yaml").read_text()
    assert "CREATE OR REPLACE VIEW" not in dumped  # NO inline multi-line SQL body
    assert ty["transforms"][0]["sql"] == "max(case when a=b then v end)"  # short fragment kept


def test_persist_drains_inline_produces_sql_defensively(tmp_path):
    """Even if the model leaks the body inline under produces.sql (which would fail validation), the
    sole writer drains it to the sibling .sql and replaces it with the pointer."""
    _declare_bundle(tmp_path / "sources" / "acme" / "widgets")
    data = tmp_path / "sources" / "acme" / "widgets" / "data"
    stem = "v_orders"
    files = {
        "transform": {
            "obj": {
                "produces": {
                    "relation": f"acme.{stem}",
                    "sql": "CREATE OR REPLACE VIEW acme.v_orders AS SELECT 1\n",
                },
                "inputs": [],
            }
        }
    }
    operations.persist_descriptors(data, stem, files, {"transform": "valid"})
    assert (data / "transforms" / f"{stem}.sql").exists()
    ty = yaml.safe_load((data / "transforms" / f"{stem}.yaml").read_text())
    assert ty["produces"]["sql_file"] == f"{stem}.sql" and "sql" not in ty["produces"]


# ------------------------------------------------------------------ (c) own-schema scaffold
def test_scaffold_defaults_view_schema_to_own_dataset(tmp_path):
    # NOT _declare_bundle(): scaffold_source is the thing that DECLARES the bundle, and
    # pre-creating mac.project.yaml makes it skip the declaration this test asserts.
    cr = tmp_path / "sources" / "acme" / "widgets"
    cr.mkdir(parents=True, exist_ok=True)
    sc = harvest.scaffold_source(cr)
    assert sc["dataset"] == "widgets"

    conn = yaml.safe_load((cr / "connection.example.yaml").read_text())
    assert conn["view_database"] == "widgets"  # OWN schema, defaulted from the dataset
    assert conn["view_schema"] == "widgets"
    assert conn["view_database"] not in materialize.known_shared_schemas()

    assert (cr / "data" / "lookups").is_dir()  # lookups plane scaffolded
    proj = yaml.safe_load((cr / "mac.project.yaml").read_text())
    assert proj.get("lookups") == "data/lookups"  # ... and declared


# ------------------------------------------------------------------ (d) materialize / lookups
def _make_source(root: Path, view_schema="acme2") -> Path:
    cr = _declare_bundle(root / "sources" / "acme" / "acme2")
    (cr / "data" / "datasets").mkdir(parents=True, exist_ok=True)
    (cr / "data" / "transforms").mkdir(parents=True, exist_ok=True)
    (cr / "connection.yaml").write_text(
        f"engine: athena\nview_schema: {view_schema}\nview_database: {view_schema}\n"
    )
    (cr / "data" / "datasets" / "dim_country.yaml").write_text(
        yaml.safe_dump(
            {
                "table": {"name": "dim_country", "schema": view_schema, "type": "view"},
                "columns": [
                    {"name": "acme_brand_country_code", "role": "primary_key"},
                    {"name": "market", "role": "value"},
                    {"name": "iso2", "role": "value"},
                ],
            }
        )
    )
    (cr / "data" / "transforms" / "dim_country.sql").write_text(
        "-- provenance header comment\n"
        "CREATE OR REPLACE VIEW someschema.dim_country AS\n"
        "SELECT market, iso2 FROM raw.eav GROUP BY 1, 2\n"
    )
    return cr


def test_plan_materialization_builds_own_schema_ddl_no_aws(tmp_path):
    cr = _make_source(tmp_path, "acme2")
    plan = materialize.plan_materialization(cr)  # PURE — no Athena
    assert plan["view_schema"] == "acme2"
    v = plan["views"][0]
    assert v["name"] == "dim_country"
    assert v["ddl"].startswith(
        "CREATE OR REPLACE VIEW acme2.dim_country AS\n"
    )  # re-targeted to OWN schema
    assert "someschema" not in v["ddl"]  # the .sql's hardcoded schema is dropped
    assert "SELECT market, iso2 FROM raw.eav GROUP BY 1, 2" in v["ddl"]
    assert v["verify_sql"] == "SELECT 1 FROM acme2.dim_country LIMIT 1"


def test_materialize_refuses_shared_and_empty_schema(tmp_path):
    with pytest.raises(materialize.MaterializeRefused):
        # "gold" is a GENERIC shared-schema name, built into materialize — no estate register
        # needed, and no instance name in an SDK test.
        materialize.plan_materialization(_make_source(tmp_path / "shared", "gold"))
    with pytest.raises(materialize.MaterializeRefused):
        materialize.plan_materialization(_make_source(tmp_path / "empty", ""))  # empty


def test_run_materialize_execute_drives_injected_executor_no_athena(tmp_path):
    cr = _make_source(tmp_path, "acme2")
    recorded = []

    def stub(sql):
        recorded.append(sql)
        return []  # SHOW TABLES / verify -> empty rows

    assert materialize.run_materialize(cr, execute=True, executor=stub) == 0
    assert any(s.startswith("SHOW TABLES IN acme2") for s in recorded)  # collision-check first
    assert any(s.startswith("CREATE OR REPLACE VIEW acme2.dim_country AS") for s in recorded)
    assert "SELECT 1 FROM acme2.dim_country LIMIT 1" in recorded  # verified queryable


def test_plan_lookups_builds_name_to_code_sql_no_aws(tmp_path):
    cr = _make_source(tmp_path, "acme2")
    plan = materialize.plan_lookups(cr)  # PURE — no Athena
    lk = plan["lookups"][0]
    assert lk["dataset"] == "dim_country"
    assert lk["code_col"] == "iso2"  # exact iso2 preferred over the primary_key
    assert lk["name_col"] == "market"
    assert lk["csv"] == "data/lookups/dim_country.lookup.csv"
    assert lk["source_view"] == "acme2.dim_country"
    assert lk["sql"] == (
        'SELECT DISTINCT "market" AS name, "iso2" AS "iso2" '
        "FROM acme2.dim_country "
        'WHERE "market" IS NOT NULL AND "iso2" IS NOT NULL ORDER BY 1'
    )


def test_run_lookups_execute_writes_csv_from_injected_rows(tmp_path):
    cr = _make_source(tmp_path, "acme2")
    rows = [{"name": "SINGAPORE", "iso2": "SG"}, {"name": "BRAZIL", "iso2": "BR"}]
    assert materialize.run_lookups(cr, execute=True, executor=lambda sql: rows) == 0
    csvp = cr / "data" / "lookups" / "dim_country.lookup.csv"
    assert csvp.exists()
    lines = csvp.read_text().splitlines()
    assert lines[0] == "name,iso2"  # gold convention: name,<code_col>
    assert "SINGAPORE,SG" in lines and "BRAZIL,BR" in lines


def test_new_athena_client_is_boto3_only_and_stubbable(monkeypatch):
    """The live seam is boto3-only (no chat.sql import) so it is trivially stubbable — proving the
    execute path constructs a client with NO network."""
    calls = {}

    class FakeClient:
        pass

    class FakeSession:
        def __init__(self, **kw):
            calls["session_kw"] = kw

        def client(self, svc, region_name=None):
            calls["client"] = (svc, region_name)
            return FakeClient()

    monkeypatch.setitem(sys.modules, "boto3", types.SimpleNamespace(Session=FakeSession))
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("MAC_GLUE_REGION", "eu-west-1")
    client = materialize._new_athena_client("/some/cr")
    assert isinstance(client, FakeClient)
    assert calls["client"] == ("athena", "eu-west-1")
