"""Unit tests for the connection contract reader + {mode,ref} credentials seam."""

import pytest

from sdk.authoring import connection as cx


def _w(p, s):
    p.write_text(s)
    return p


def test_aws_chain_returns_empty_spec_never_a_value(tmp_path):
    _w(
        tmp_path / "connection.yaml",
        "region: eu-west-1\ncredentials:\n  mode: aws-chain\n  ref: some-profile\n",
    )
    conn = cx.load_connection(tmp_path)
    assert cx.resolve_credentials(conn) == {}  # ambient chain; ref is documentation only


def test_profile_mode_uses_named_profile(tmp_path):
    _w(tmp_path / "connection.yaml", "credentials:\n  mode: profile\n  ref: zz-example-profile-zz\n")
    assert cx.resolve_credentials(cx.load_connection(tmp_path)) == {
        "profile_name": "zz-example-profile-zz"
    }


def test_secretsmanager_fails_loud_not_silently(tmp_path):
    _w(tmp_path / "connection.yaml", "credentials:\n  mode: secretsmanager\n  ref: prod/athena\n")
    with pytest.raises(NotImplementedError):
        cx.resolve_credentials(cx.load_connection(tmp_path))


def test_override_overlays_base(tmp_path):
    _w(tmp_path / "connection.yaml", "region: eu-west-1\nworkgroup: base-wg\naccount: null\n")
    _w(tmp_path / "connection.local.yaml", "workgroup: override-wg\naccount: '123456789012'\n")
    conn = cx.load_connection(tmp_path)
    assert conn["workgroup"] == "override-wg" and conn["account"] == "123456789012"


def test_redacted_hides_account_derives_via_sts(tmp_path):
    _w(
        tmp_path / "connection.yaml",
        "region: eu-west-1\nworkgroup: wg\naccount: null\ncredentials:\n  mode: aws-chain\n  ref: p\n",
    )
    r = cx.redacted(cx.load_connection(tmp_path))
    assert r["account"] == "(derived at runtime via STS)" and r["credentials_ref"] == "p"
