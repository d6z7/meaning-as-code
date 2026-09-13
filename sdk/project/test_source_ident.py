"""Unit tests for the de-ACME source-identity resolver: <domain>/<dataset> resolves to the exact strings
that used to be hardcoded (so the projection stays byte-identical), and a bare/new source falls
back gracefully with no source literal baked in."""

from pathlib import Path

from sdk.project import source_ident as si


def _w(p: Path, s: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s)
    return p


def test_a_declared_bundle_resolves_to_its_manifest_strings():
    repo = Path(__file__).resolve().parents[2]
    ident = si.resolve(repo / "sources" / "acme" / "acme")
    # exactly the values that were literals in data_plane / project_data / edges before Phase 6
    assert ident.data_domain == "acme"
    assert ident.dataset == "acme"
    assert ident.label == "ACME"
    assert ident.view_schema == "acme"


def test_label_from_runtime_source_wins(tmp_path):
    cr = tmp_path / "acme" / "widgets"
    _w(
        cr / "mac.project.yaml",
        "metadata:\n  data_domain: acme\n  dataset: widgets\nruntime:\n  source: ACME_SALES\n",
    )
    _w(cr / "connection.yaml", "view_schema: acme_curated\n")
    ident = si.resolve(cr)
    assert ident.data_domain == "acme" and ident.dataset == "widgets"
    assert ident.label == "ACME_SALES"  # runtime.source
    assert ident.view_schema == "acme_curated"  # connection.view_schema


def test_label_falls_back_to_sources_yaml_then_dataset(tmp_path):
    cr = tmp_path / "d" / "orders"
    _w(cr / "mac.project.yaml", "metadata:\n  data_domain: d\n  dataset: orders\n")
    _w(cr / "sources.yaml", "sources:\n  ORDERS_SRC:\n    label: x\n")
    assert si.resolve(cr).label == "ORDERS_SRC"  # first key under sources:

    cr2 = tmp_path / "d" / "returns"
    _w(cr2 / "mac.project.yaml", "metadata:\n  data_domain: d\n  dataset: returns\n")
    ident = si.resolve(cr2)
    assert ident.label == "RETURNS"  # dataset upper-cased
    assert ident.view_schema == "returns"  # no connection.yaml -> dataset


def test_bare_dir_never_crashes(tmp_path):
    cr = tmp_path / "domainX" / "dsY"
    cr.mkdir(parents=True)
    ident = si.resolve(cr)  # no manifest at all
    assert ident.data_domain == "domainX" and ident.dataset == "dsY" and ident.label == "DSY"
