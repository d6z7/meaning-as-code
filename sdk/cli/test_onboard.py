"""Unit tests for the Phase-6 onboarding surface in harvest.py: --scaffold skeleton, the
model-swap config resolution (precedence + startup validation), the reproducibility SIDECAR
(and its exclusion from the served/published tree), and the resume-aware onboard dry-run
proving it makes NO AWS call. Offline — the billed stages are monkeypatched, never executed."""

import pytest

from sdk.cli import harvest, publish
from sdk.gate import check_bundle_secrets

# --- --scaffold: stamp a new source skeleton, idempotently -----------------------------------


def test_scaffold_stamps_skeleton_and_is_idempotent(tmp_path):
    cr = tmp_path / "acme" / "widgets"
    sc = harvest.scaffold_source(cr)
    assert sc["data_domain"] == "acme" and sc["dataset"] == "widgets" and sc["label"] == "WIDGETS"
    for f in ("mac.project.yaml", "connection.example.yaml", "harvest.yaml"):
        assert (cr / f).is_file()
    for d in ("data/sources", "data/datasets", "ontology/concepts", "runtime", "references"):
        assert (cr / d).is_dir()
    # the manifest records the resolved domain/dataset so source_ident later resolves them
    mp = (cr / "mac.project.yaml").read_text()
    assert "data_domain: acme" in mp and "dataset: widgets" in mp and "source: WIDGETS" in mp

    # re-scaffold: never overwrites, reports the files it kept
    sc2 = harvest.scaffold_source(cr)
    # The scaffold writes the GOVERNANCE plane too (1e54121 "scaffold a GOVERNED source"):
    # PHASE + lock, the SME ledger, the intervention ledger, the vanilla delta and warehouse
    # properties. They are kept on re-scaffold like every other manifest file.
    assert set(sc2["skipped"]) == {
        "mac.project.yaml",
        "connection.example.yaml",
        "harvest.yaml",
        "governance/PHASE.yaml",
        "governance/ledger.yaml",
        "governance/properties.yaml",
        "governance/sme_ledger.yaml",
        "governance/vanilla_delta.yaml",
    }


# --- config resolution: CLI > harvest.yaml > env > default, validated at startup --------------


def test_config_precedence_harvest_yaml_over_env(tmp_path, monkeypatch):
    cr = tmp_path / "d" / "ds"
    cr.mkdir(parents=True)
    (cr / "harvest.yaml").write_text(
        "model: us.anthropic.claude-haiku-4-5-v1\neffort: xhigh\nthinking_budget: 2048\n"
    )
    monkeypatch.setenv("MAC_HARVEST_MODEL", "eu.anthropic.claude-sonnet-4-5-v1")
    monkeypatch.setenv("MAC_EFFORT", "low")
    cfg = harvest._resolve_harvest_config(cr)
    assert cfg["model"] == "us.anthropic.claude-haiku-4-5-v1"  # harvest.yaml beats env
    assert cfg["effort"] == "xhigh"
    assert cfg["thinking_budget"] == 2048


def test_config_cli_flag_wins_and_env_fallback(tmp_path, monkeypatch):
    cr = tmp_path / "d" / "ds"
    cr.mkdir(parents=True)
    monkeypatch.setenv("MAC_HARVEST_MODEL", "eu.anthropic.claude-sonnet-4-5-v1")
    monkeypatch.delenv("MAC_EFFORT", raising=False)
    cfg = harvest._resolve_harvest_config(cr, cli_model="global.anthropic.claude-opus-4-6-v1")
    assert cfg["model"] == "global.anthropic.claude-opus-4-6-v1"  # CLI beats env
    assert cfg["effort"] == "medium"  # falls through to the default


def test_config_fails_loud_on_bad_model_at_startup(tmp_path):
    cr = tmp_path / "d" / "ds"
    cr.mkdir(parents=True)
    with pytest.raises(ValueError):
        harvest._resolve_harvest_config(cr, cli_model="garbage-no-prefix")


# --- reproducibility SIDECAR: written, but NEVER served / hashed / published ------------------


def test_manifest_is_a_sidecar_excluded_from_publish_and_gate(tmp_path):
    cr = tmp_path / "acme" / "widgets"
    harvest.scaffold_source(cr)
    path = harvest.write_harvest_manifest(
        cr,
        {
            "stage": "data",
            "model": "eu.anthropic.claude-sonnet-4-5-v1",
            "region": "eu-west-1",
            "databases": ["catalog_gaps_prd_fpl_gaps_redshift"],
            "cache": {"hits": 0, "misses": 3},
        },
    )
    assert path.name == ".harvest_manifest.yaml" and path.is_file()

    # NOT part of the served surface publish.py freezes (publish.include never names it)
    assert harvest._MANIFEST_SIDECAR not in publish._compile_items(cr)
    # and the secret gate skips it (it records glue db handles that only belong in connection config)
    assert harvest._MANIFEST_SIDECAR in check_bundle_secrets._SKIP_FILES
    # a source-tree scan therefore stays clean even though the sidecar names a denylisted handle
    assert check_bundle_secrets.check(cr) == []


# --- onboard DRY-RUN makes NO AWS call; --accept resumes present stages ------------------------


@pytest.fixture
def no_aws(monkeypatch):
    """Fail hard if any billed stage or boto session is touched; record the offline project run."""
    ran = {"project": 0}

    def _boom(*a, **k):
        raise AssertionError("an AWS-billed path was reached during a dry-run")

    monkeypatch.setattr(harvest, "harvest_data", _boom)
    monkeypatch.setattr(harvest, "harvest_concepts", _boom)
    monkeypatch.setattr(harvest, "_session", _boom)
    monkeypatch.setattr(
        harvest, "project_source", lambda cr, **kw: ran.__setitem__("project", ran["project"] + 1)
    )
    return ran


def test_onboard_dry_run_makes_no_aws_call(tmp_path, no_aws):
    cr = tmp_path / "acme" / "widgets"
    harvest.scaffold_source(cr)  # skeleton present; data/ontology empty
    cfg = harvest._resolve_harvest_config(cr)  # default model (valid)
    rc = harvest.onboard(cr, [], cfg=cfg, accept=False)
    assert rc == 0
    assert no_aws["project"] == 1  # offline projection ran
    man = harvest._read_yaml(cr / harvest._MANIFEST_SIDECAR)
    assert man["dry_run"] is True
    # Onboarding STOPS at the data plane -- 1e54121 ("...and stop chaining concepts")
    # deliberately unchained the concepts stage; it is now an explicit second invocation.
    assert set(man["planned_stages"]) == {"data"}


def test_onboard_accept_resumes_when_outputs_present(tmp_path, no_aws):
    cr = tmp_path / "acme" / "widgets"
    harvest.scaffold_source(cr)
    # simulate an already-harvested source: datasets + concepts present -> both stages resume
    (cr / "data" / "datasets" / "d.yaml").write_text("table: {name: d}\n")
    (cr / "ontology" / "concepts" / "c.yaml").write_text("concept: {name: C}\n")
    cfg = harvest._resolve_harvest_config(cr)
    rc = harvest.onboard(cr, [], cfg=cfg, accept=True)  # accept, but nothing to bill
    assert rc == 0  # _boom never fired (both resumed)
    assert no_aws["project"] == 1
    man = harvest._read_yaml(cr / harvest._MANIFEST_SIDECAR)
    assert man["dry_run"] is False and man["planned_stages"] == []
