"""The compile gate — projection REFUSES a bundle that does not conform.

These tests exist because the operator's ruling is specifically about ENFORCEMENT, not detection:
"a check that does not block is not enforcement." The findings already existed before this gate; what
did not exist was anything that stopped a projection from running over them. So every test here is
about the BLOCK, and one of them (`test_gate_runs_before_any_artifact_is_written`) is about the block
happening BEFORE work, not after — a gate that refuses at the end has already written the artifact.

The bundles are built here rather than pointed at a real source: the gate must be true of any bundle,
and a test pinned to one corpus stops being a test of the gate and becomes a test of that corpus.
"""

from __future__ import annotations

import json

import pytest

from sdk.cli import harvest


def _bundle(tmp_path, name="minimal"):
    """A bundle that COMPILES: a manifest and nothing MAC has no definition for."""
    cr = tmp_path / name
    cr.mkdir(parents=True)
    (cr / "mac.project.yaml").write_text(
        "spec_version: mac.container/1\n"
        f"metadata:\n  project: t/{name}\n  kind: mac_project\n"
        f"  data_domain: t\n  dataset: {name}\n  label: {name.upper()}\n"
        # `planes` is a REQUIRED property of ProjectFile (mac.schema.json). Without it the
        # compiler reports MAC002 invalid-artifact and this "conformant" fixture does not
        # compile -- which made the gate look broken when it was the fixture that was stale.
        "planes:\n  data: data\n  ontology: ontology\n"
    )
    return cr


def _make_nonconformant(cr):
    """One yaml file MAC has no definition for → MAC001, error severity. This is the SMALLEST real
    non-conformance available: no key had to be malformed, only present and undefined."""
    (cr / "invented_artifact.yaml").write_text("kind: something_mac_never_defined\nrows: []\n")
    return cr


def _record(cr):
    return json.loads((cr / harvest._COMPILE_RECORD).read_text())


def test_conformant_bundle_passes_and_persists_its_verdict(tmp_path):
    cr = _bundle(tmp_path)
    rec = harvest.compile_gate(cr)
    assert rec["verdict"] == "COMPILES"
    assert rec["summary"]["errors"] == 0
    on_disk = _record(cr)
    assert on_disk["verdict"] == "COMPILES"
    assert on_disk["gate"]["override"] is None
    # the dashboard contract: EVERY code in the closed taxonomy is present, each saying whether it was
    # computed — so "clean" and "never computed" can never be rendered as the same thing.
    # Completeness is asserted against the framework's OWN closed taxonomy, not a literal
    # count: the taxonomy grew from 11 to 12 codes when meaning-as-code added one, and a
    # magic number turns every framework addition into a false failure here. compile_gate
    # has already put the framework tools on sys.path by this point.
    import mac_diag

    assert set(on_disk["codes"]) == set(mac_diag.CODES)
    assert all("computed" in v for v in on_disk["codes"].values())


def test_nonconformant_bundle_is_refused(tmp_path):
    cr = _make_nonconformant(_bundle(tmp_path))
    with pytest.raises(harvest.CompileRefused) as exc:
        harvest.compile_gate(cr)
    msg = str(exc.value)
    assert "REFUSED" in msg and "DOES NOT COMPILE" in msg
    assert "MAC001" in msg  # the compiler's OWN finding, not a paraphrase
    assert harvest._OVERRIDE_FLAG in msg  # and the documented way past it
    rec = _record(cr)  # the refusal is persisted, not just printed
    assert rec["verdict"] == "DOES_NOT_COMPILE"
    assert rec["summary"]["errors"] >= 1
    assert rec["gate"]["override"] is None


def test_override_proceeds_and_is_recorded_with_identity(tmp_path):
    cr = _make_nonconformant(_bundle(tmp_path))
    rec = harvest.compile_gate(cr, project_anyway="remediation in flight; demo needs the read view")
    ov = rec["gate"]["override"]
    assert ov["flag"] == harvest._OVERRIDE_FLAG
    assert ov["reason"] == "remediation in flight; demo needs the read view"
    assert ov["by"] and ov["at"]  # who, and when — an override is attributable
    assert ov["errors_overridden"] == rec["summary"]["errors"]
    assert "MAC001" in ov["codes_overridden"]
    assert _record(cr)["gate"]["override"]["reason"] == ov["reason"]  # survives the process


def test_blank_reason_is_not_an_override(tmp_path):
    """The flag's VALUE is the reason. Whitespace is not a reason, and accepting it would turn the
    override back into a bare switch somebody can leave on."""
    cr = _make_nonconformant(_bundle(tmp_path))
    with pytest.raises(harvest.CompileRefused):
        harvest.compile_gate(cr, project_anyway="   ")


def test_unknown_conformance_refuses_too(tmp_path, monkeypatch):
    """A compiler that cannot run leaves conformance UNKNOWN — which is not clean. Degrading to
    silence here would report an unchecked bundle as an acceptable one."""
    cr = _bundle(tmp_path)
    import sys

    sys.path.insert(0, str(harvest._MAC_TOOLS))
    import mac_compile

    def _boom(*a, **k):
        raise RuntimeError("framework unavailable")

    monkeypatch.setattr(mac_compile, "compile_bundle", _boom)
    with pytest.raises(harvest.CompileRefused) as exc:
        harvest.compile_gate(cr)
    assert "UNKNOWN, not clean" in str(exc.value)
    # …and the same documented override applies, so an unreachable framework is not a hard stop.
    rec = harvest.compile_gate(cr, project_anyway="framework repo not checked out on this machine")
    assert rec["verdict"] == "NOT_COMPILED"
    assert rec["gate"]["compiler_reachable"] is False


def test_gate_runs_before_any_artifact_is_written(tmp_path, monkeypatch):
    """The whole point of the wiring: the refusal happens BEFORE projection does work. If the gate ran
    after `_lineage_flows`, this test would raise AssertionError instead of CompileRefused."""
    cr = _make_nonconformant(_bundle(tmp_path))

    def _must_not_run(*a, **k):
        raise AssertionError("projection work started on a bundle that does not compile")

    monkeypatch.setattr(harvest, "_lineage_flows", _must_not_run)
    with pytest.raises(harvest.CompileRefused):
        harvest.project_source(cr)
