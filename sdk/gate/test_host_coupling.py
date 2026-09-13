"""Unit tests for the source-neutral host-coupling gate (ADR 2026-08-13)."""

from sdk.gate import check_host_coupling as g
from sdk.testing import assert_clean_over


def _repo_with_source(tmp_path, domain="acme", dataset="sales"):
    (tmp_path / "sources" / domain / dataset).mkdir(parents=True)
    (tmp_path / "sources" / domain / dataset / "mac.project.yaml").write_text(
        f"metadata: {{data_domain: {domain}, dataset: {dataset}, label: ACME}}\n"
    )
    return tmp_path


def test_clean_host_is_separated(tmp_path):
    repo = _repo_with_source(tmp_path)
    host = tmp_path / "host"
    host.mkdir()
    (host / "server.py").write_text(
        "def serve(content_root):\n    return content_root  # reads the mount, no literal\n"
    )
    r = g.check(host, repo)
    assert not r["infra_handles"] and not r["source_pins"]


def test_infra_handle_literal_is_coupling(tmp_path):
    repo = _repo_with_source(tmp_path)
    host = tmp_path / "host"
    host.mkdir()
    (host / "server.py").write_text("PROFILE = 'zz-synthetic-infra-handle-zz'  # hardcoded infra handle\n")
    assert any(k.startswith("infra_handle") for _, _, k, _ in g.check(host, repo)["infra_handles"])


def test_source_pin_literal_is_coupling(tmp_path):
    repo = _repo_with_source(tmp_path, domain="acme", dataset="sales")
    host = tmp_path / "host"
    host.mkdir()
    (host / "server.py").write_text("DEFAULT_DATASET = 'sales'  # pins this host to one source\n")
    assert any(t == "sales" for _, _, t in g.check(host, repo)["source_pins"])


def test_gate_and_test_files_are_not_flagged(tmp_path):
    repo = _repo_with_source(tmp_path)
    host = tmp_path / "host"
    host.mkdir()
    # a denylist/gate file names the handle by design — must NOT be counted as host coupling
    (host / "check_secrets.py").write_text("DENY = ['zz-synthetic-infra-handle-zz']\n")
    from sdk.gate import check_bundle_secrets as _bs

    assert_clean_over(
        g.check(host, repo)["infra_handles"],
        examined=len(list(_bs._DEFAULT_DENY)),
        what="declared handle",
    )
