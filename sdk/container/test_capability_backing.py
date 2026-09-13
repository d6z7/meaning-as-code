"""A capability is a claim. A filename is not evidence for it.

These are regression tests for a defect that sat live for a month: `_backed_capabilities` checked
`.exists()`, so a ZERO-BYTE connection.yaml backed `answerable: true`, and an UNDECLARED file
silently became the container's connection via a `or "connection.yaml"` fallback. Both are the
zero-denominator pass wearing capability clothing — a check that reports success having examined
nothing of substance.
"""

import pytest
import yaml

from sdk.container import spec

MANIFEST = {
    "spec_version": "mac.container/1",
    "metadata": {"project": "x/y", "data_domain": "x", "dataset": "y"},
    "planes": {"data": "data", "ontology": "ontology"},
}


def _bundle(root, *, interp=None, conn=None, conn_bytes=b"engine: something\n", interp_bytes=b"# an interpreter\n"):
    (root / "ontology").mkdir(parents=True)
    (root / "data").mkdir(parents=True)
    m = dict(MANIFEST)
    rt = {}
    if interp:
        (root / interp).parent.mkdir(parents=True, exist_ok=True)
        (root / interp).write_bytes(interp_bytes)
        rt["interpreter"] = interp
    if conn:
        (root / conn).write_bytes(conn_bytes)
        rt["connection"] = conn
    if rt:
        m["runtime"] = rt
    (root / "mac.project.yaml").write_text(yaml.safe_dump(m), encoding="utf-8")
    return root


def _answerable(root):
    return spec.validate(str(root))["capabilities"]["backed"]["answerable"]


def test_a_complete_bundle_backs_answerable(tmp_path):
    assert _answerable(_bundle(tmp_path / "ok", interp="runtime/i.md", conn="connection.yaml")) is True


def test_empty_connection_does_not_back_answerable(tmp_path):
    """FAILED BEFORE THE FIX. A zero-byte file satisfied `.exists()`."""
    b = _bundle(tmp_path / "empty", interp="runtime/i.md", conn="connection.yaml", conn_bytes=b"")
    assert _answerable(b) is False


def test_empty_interpreter_does_not_back_answerable(tmp_path):
    b = _bundle(tmp_path / "ei", interp="runtime/i.md", conn="connection.yaml", interp_bytes=b"")
    assert _answerable(b) is False


def test_an_undeclared_connection_file_does_not_count(tmp_path):
    """FAILED BEFORE THE FIX. `rt.get("connection") or "connection.yaml"` meant a file nobody
    declared became the container's connection — which is how a manifest came to 'declare' a
    connection whose value was byte-identical to the fallback, carrying no information at all."""
    b = _bundle(tmp_path / "undecl", interp="runtime/i.md")
    (b / "connection.yaml").write_text("engine: something\n", encoding="utf-8")   # present, undeclared
    assert _answerable(b) is False


def test_no_interpreter_does_not_back_answerable(tmp_path):
    assert _answerable(_bundle(tmp_path / "ni", conn="connection.yaml")) is False


def test_a_bundle_with_no_connection_is_still_readable(tmp_path):
    """The tri-state must survive: no connection means NOT ANSWERABLE, never NOT OPENABLE. A bundle
    without a warehouse is browsable, and that is the whole point of separating the capabilities."""
    r = spec.validate(str(_bundle(tmp_path / "read", interp="runtime/i.md")))
    backed = r["capabilities"]["backed"]
    assert backed["readable"] is True and backed["answerable"] is False


@pytest.mark.parametrize("cap", ["readable", "renderable", "answerable"])
def test_every_checkable_capability_is_a_bool_not_a_truthy_path(tmp_path, cap):
    """`bool(interp) and (cr/interp).exists()` returned a Path-ish truthiness in some branches. A
    capability that is a truthy object rather than True is a capability no `is False` guard can read."""
    v = spec.validate(str(_bundle(tmp_path / f"t{cap}", interp="runtime/i.md", conn="connection.yaml")))
    assert v["capabilities"]["backed"][cap] in (True, False)
