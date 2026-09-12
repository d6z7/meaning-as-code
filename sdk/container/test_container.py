"""Unit tests for the container spec validator + open_container loader (ADR 2026-08-13)."""

import io
import tarfile
from pathlib import Path

import pytest

from sdk.container import loader, spec


def _mk(cr: Path, *, spec_version="mac.container/1", caps=None, objects=True, interp=True):
    """Author a minimal valid container dir (unpublished — no MANIFEST)."""
    (cr / "ontology").mkdir(parents=True)
    (cr / "data").mkdir()
    (cr / "runtime").mkdir()
    m = [
        "metadata: {project: t/x, data_domain: t, dataset: x}",
        "planes: {data: data, ontology: ontology}",
    ]
    if spec_version:
        m.insert(0, f"spec_version: {spec_version}")
    if interp:
        (cr / "runtime" / "interp.md").write_text("# interp")
        (cr / "connection.yaml").write_text(
            "engine: athena\ncredentials: {mode: aws-chain, ref: p}\n"
        )
        m.append(
            "runtime: {source: X, interpreter: runtime/interp.md, connection: connection.yaml}"
        )
    if caps is not None:
        m.append(
            "capabilities: {" + ", ".join(f"{k}: {str(v).lower()}" for k, v in caps.items()) + "}"
        )
    if objects:
        (cr / "objects.json").write_text("{}")
    (cr / "mac.project.yaml").write_text("\n".join(m) + "\n")


def test_valid_unpublished_container(tmp_path):
    _mk(tmp_path)
    r = spec.validate(tmp_path)
    assert r["ok"] and r["trust"] == "unpublished-ssot" and r["spec_version"] == "mac.container/1"


def test_missing_manifest_is_not_a_container(tmp_path):
    assert not spec.validate(tmp_path)["ok"]


def test_declared_plane_must_exist(tmp_path):
    _mk(tmp_path)
    (tmp_path / "mac.project.yaml").write_text(
        "spec_version: mac.container/1\nplanes: {data: data, ontology: MISSING}\n"
    )
    r = spec.validate(tmp_path)
    assert not r["ok"] and any("MISSING" in e for e in r["errors"])


def test_capability_claimed_but_unbacked_fails(tmp_path):
    # claim answerable but ship no interpreter/connection
    _mk(tmp_path, caps={"answerable": True}, interp=False)
    r = spec.validate(tmp_path)
    assert not r["ok"] and any("answerable" in e for e in r["errors"])


def test_account_portable_claim_warns(tmp_path):
    _mk(tmp_path, caps={"account_portable": True})
    assert any("account_portable" in w for w in spec.validate(tmp_path)["warnings"])


def test_unknown_spec_version_errors(tmp_path):
    _mk(tmp_path, spec_version="mac.container/999")
    assert not spec.validate(tmp_path)["ok"]


def test_open_container_on_directory(tmp_path):
    cr = tmp_path / "c"
    _mk(cr)
    r = loader.open_container(cr)
    assert r["ok"] and r["metadata"]["dataset"] == "x"


def test_require_trust_refuses_below_floor(tmp_path):
    cr = tmp_path / "c"
    _mk(cr)  # unpublished -> trust 'unpublished-ssot', below 'signed-verified'
    r = loader.open_container(cr, require_trust="signed-verified")
    assert not r["ok"] and any("below the required floor" in e for e in r["errors"])


def test_open_container_rejects_zip_slip(tmp_path):
    # craft a tar with a member that escapes the extraction dir
    bad = tmp_path / "evil.tar.gz"
    with tarfile.open(bad, "w:gz") as tar:
        data = b"pwned"
        ti = tarfile.TarInfo(name="../escape.txt")
        ti.size = len(data)
        tar.addfile(ti, io.BytesIO(data))
    with pytest.raises(ValueError):
        loader.open_container(bad, workspace=tmp_path / "ws")
    assert not (tmp_path / "escape.txt").exists()


# -------------------------------------------------------------------------------------------------
# READING a container is not ANSWERING from one.
#
# `open_container` used to apply answering-grade strictness to every mount, so a bundle whose
# `readable` capability is backed and whose `answerable` is not came back ok=False and could not be
# opened in order to be LOOKED at. The `require_trust` parameter already expressed the difference;
# it governed only the trust rank. These cases pin the split so it cannot quietly close again.
# -------------------------------------------------------------------------------------------------


def _bundle(root: Path, *, handle: bool = False, account: bool = False) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "mac.project.yaml").write_text(
        "spec_version: mac.container/1\n"
        "metadata:\n  project: fixture\n  data_domain: dom\n  dataset: ds\n"
        "planes:\n  data: data\n  ontology: ontology\n",
        encoding="utf-8",
    )
    (root / "ontology").mkdir(exist_ok=True)
    (root / "data").mkdir(exist_ok=True)
    (root / "ontology" / "concept.yaml").write_text("concept:\n  name: Thing\n", encoding="utf-8")
    if handle:
        # a credential HANDLE outside its declared home: a real finding, but not a value
        (root / "notes.md").write_text("run with profile acme-prod-operator\n", encoding="utf-8")
    if account:
        # a VALUE. Forbidden at every strictness, including a read-only mount.
        (root / "deploy.md").write_text("account 123456789012 in eu-west-1\n", encoding="utf-8")
    return root


def test_a_clean_bundle_opens_for_reading(tmp_path: Path) -> None:
    r = loader.open_container(_bundle(tmp_path / "clean"))
    assert r["ok"] is True
    assert r["readable"] is True


def test_a_leaked_handle_warns_a_reader_but_refuses_an_answering_host(tmp_path: Path) -> None:
    root = _bundle(tmp_path / "handle", handle=True)

    read = loader.open_container(root)
    assert read["ok"] is True, read["errors"]
    assert any("acme-prod-operator" in str(w) for w in read["warnings"])

    answer = loader.open_container(root, require_trust="signed-verified")
    assert answer["ok"] is False
    assert any("secret leak" in str(e) for e in answer["errors"])


def test_an_account_id_refuses_even_a_read_only_mount(tmp_path: Path) -> None:
    """The one class that is never softened: an account id is a VALUE, not a handle."""
    r = loader.open_container(_bundle(tmp_path / "account", account=True))
    assert r["ok"] is False
    assert any("aws_account_id" in str(e) for e in r["errors"])


def test_an_unbacked_capability_claim_does_not_block_a_read(tmp_path: Path) -> None:
    root = _bundle(tmp_path / "claim")
    (root / "mac.project.yaml").write_text(
        (root / "mac.project.yaml").read_text(encoding="utf-8")
        + "capabilities:\n  readable: true\n  answerable: true\n",
        encoding="utf-8",
    )
    read = loader.open_container(root)
    answer = loader.open_container(root, require_trust="signed-verified")
    # `answerable` is claimed and cannot be backed (no interpreter/connection in the fixture)
    assert read["ok"] is True, read["errors"]
    assert answer["ok"] is False
