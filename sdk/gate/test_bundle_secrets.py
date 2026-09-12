"""Unit tests for check_bundle_secrets — it must CATCH real leaks (incl. novel keys) and stay
quiet on a clean connection config where reference handles legitimately travel."""

from sdk.gate import check_bundle_secrets as g


def _w(p, s):
    p.write_text(s)
    return p


def test_catches_novel_aws_access_key(tmp_path):
    _w(tmp_path / "a.yaml", "key: AKIAZZ1234567890ABCD\n")
    assert any(k == "aws_access_key_id" for _, _, k, _ in g.check(tmp_path))


def test_catches_infra_handle_outside_config(tmp_path):
    _w(tmp_path / "data.yaml", "cut_by: acme-prod-operator\n")
    assert any(k.startswith("infra_handle") for _, _, k, _ in g.check(tmp_path))


def test_allows_reference_handle_inside_connection_yaml(tmp_path):
    _w(tmp_path / "connection.yaml", "credentials:\n  mode: aws-chain\n  ref: acme-prod-operator\n")
    assert not any(k.startswith("infra_handle") for _, _, k, _ in g.check(tmp_path))


def test_blocks_account_id_even_inside_connection_yaml(tmp_path):
    _w(tmp_path / "connection.yaml", "account: 123456789012\n")
    assert any("account" in k for _, _, k, _ in g.check(tmp_path))


def test_catches_private_key_and_inline_password(tmp_path):
    _w(tmp_path / "x.txt", "-----BEGIN RSA PRIVATE KEY-----\npassword: hunter2xyz\n")
    kinds = {k for _, _, k, _ in g.check(tmp_path)}
    assert "private_key_block" in kinds and "password_inline" in kinds


def test_clean_connection_config_is_silent(tmp_path):
    _w(tmp_path / "connection.yaml", "engine: athena\nregion: eu-west-1\nworkgroup: primary\n")
    _w(tmp_path / "data.yaml", "cut_by: athena-profile  # handle lives in connection.yaml\n")
    assert g.check(tmp_path) == []


def test_skips_nonshipped_context_and_artifacts(tmp_path):
    (tmp_path / ".context").mkdir()
    _w(tmp_path / ".context" / "doc.md", "account: 123456789012\n")
    (tmp_path / "artifacts" / "v1").mkdir(parents=True)
    _w(tmp_path / "artifacts" / "v1" / "d.yaml", "cut_by: acme-prod-operator\n")
    assert g.check(tmp_path) == []
