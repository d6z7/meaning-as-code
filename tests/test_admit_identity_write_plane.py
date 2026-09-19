#!/usr/bin/env python3
"""mac_admit_identity.py --write must record its verdicts in the plane the SCHEMA defines for them.

WHAT THIS PINS. `identity_evidence` and `columns[].determined_by` are MEASURED blocks, and
mac.schema.json puts both on `ProfileFile` (data/profiles/<stem>.yaml). `TableFile` — the definition
validate_schema.py routes data/datasets/ and data/sources/ to — is `additionalProperties: false`
with neither field, and its `columns[]` items are `additionalProperties: false` with no `profile`.
So a `--write` that records either one on the descriptor does not merely put it where no consumer
looks; it writes a file the validator rejects.

The loop that made this worth a test: every reader takes the measured key from
`data/profiles/<stem>.yaml#identity_evidence.key`, so evidence written to the descriptor leaves
check_grain_key_consistency still printing "no relation in this bundle carries a measured key… run
mac_admit_identity.py" — the command the operator just ran.

Only `columns[].role` stays on the descriptor: a role is an AUTHORED design fact, and TableFile
defines it.

THE FIXTURE IS SYNTHETIC and stands on stdlib sqlite3, so the test needs no warehouse. The
descriptor carries the census INLINE (`profile`, `_profile`, `columns[].profile`) because that is
the only shape the tool's READ path accepts — `candidates()` and the main() gate were not migrated
to the split plane and `load_profile()` is still uncalled. That is a separate defect; it is why the
fixture looks pre-split, and it is deliberately not what this test pins.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest
import yaml

FW = pathlib.Path(__file__).resolve().parent.parent
TOOL = FW / "tools" / "mac_admit_identity.py"
SCHEMA = FW / "mac.schema.json"

RELATION = "alpha"

#: (beta_id, gamma_code, delta_axis, zeta_id, amount). Built so the admission test has one of each
#: verdict to find: `amount` is a function of (beta_id, zeta_id), so omitting either makes the
#: measure DISAGREE (IDENTITY); `delta_axis` splits every group without changing the measure
#: (COLLAPSIBLE — the residue, which the tool must leave unruled); `gamma_code` is functionally
#: determined by beta_id and refines nothing (the `determined_by` case).
ROWS = [(b, g, d, z, amt)
        for b, g, amts in (("b1", "g1", (10.0, 11.0)),
                           ("b2", "g1", (20.0, 21.0)),
                           ("b3", "g2", (30.0, 31.0)))
        for z, amt in (("z1", amts[0]), ("z2", amts[1]))
        for d in ("d1", "d2")]

PLUGIN = '''\
"""A synthetic bundle plugin: the framework's `query(sql) -> (rows, meta)` contract over sqlite3."""
import pathlib
import sqlite3


class _Meta:
    scanned_bytes = 0


class Athena:  # noqa: N801 — the name the framework asks for
    def __init__(self, profile=None, region=None, workgroup=None, database=None):
        self._con = sqlite3.connect(str(pathlib.Path(__file__).resolve().parent.parent / "wh.db"))
        self._con.create_function("chr", 1, chr)

    def query(self, sql):
        cur = self._con.execute(sql)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()], _Meta()


def source_watermark(ath, relations):
    """No column on this relation carries a write stamp, so None is the measured answer."""
    return {rel: {"newest_write": None, "audit_column": None} for rel in relations}
'''


def _bundle(tmp_path: pathlib.Path) -> pathlib.Path:
    import sqlite3

    root = tmp_path / "bundle"
    for d in ("tools", "acceptance", "data/sources", "data/profiles"):
        (root / d).mkdir(parents=True)

    con = sqlite3.connect(str(root / "wh.db"))
    con.execute(f"CREATE TABLE {RELATION}"
                "(beta_id TEXT, gamma_code TEXT, delta_axis TEXT, zeta_id TEXT, amount REAL)")
    con.executemany(f"INSERT INTO {RELATION} VALUES(?,?,?,?,?)", ROWS)
    con.commit()
    con.close()

    (root / "tools" / "run_properties.py").write_text(PLUGIN, encoding="utf-8")
    (root / "acceptance" / "properties.yaml").write_text(yaml.safe_dump(
        {"engine": {"profile": "local", "region": "local",
                    "workgroup": "local", "database": "synthetic"}}), encoding="utf-8")

    census = {"beta_id": 3, "gamma_code": 2, "delta_axis": 2, "zeta_id": 2, "amount": 6}
    table_profile = {"measured_at": "2026-01-01T00:00:00+00:00", "rows": len(ROWS),
                     "method": "fixture/1"}
    doc = {
        "metadata": {"schema_version": "0.1.14-develop"},
        "table": {"name": RELATION, "type": "table"},
        # Pre-split shape: see the module docstring — the tool's read path accepts nothing else.
        "profile": dict(table_profile),
        "_profile": dict(table_profile),
        "columns": [{"name": n, "type": "double" if n == "amount" else "varchar",
                     "role": "value", "profile": {"distinct": d}}
                    for n, d in census.items()],
        # Residue a previous run of the BUGGY tool would have left here. A re-run must clear it,
        # or the descriptor stays schema-invalid on exactly the bundles the defect touched.
        "identity_evidence": {"key": ["stale"]},
    }
    doc["columns"][1]["profile"]["determined_by"] = ["stale"]
    (root / "data" / "sources" / f"{RELATION}.yaml").write_text(
        yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    (root / "data" / "profiles" / f"{RELATION}.yaml").write_text(yaml.safe_dump(
        {"metadata": {"schema_version": "0.1.14-develop", "generated_by": "fixture/1"},
         "of": RELATION, "relation": RELATION,
         "profile": dict(table_profile),
         "columns": [{"name": n, "distinct": d} for n, d in census.items()]},
        sort_keys=False), encoding="utf-8")
    return root


def _validate(path: pathlib.Path, definition: str) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    defs = schema.get("$defs") or schema.get("definitions")
    sub = dict(defs[definition])
    sub["$defs"] = defs
    jsonschema.validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {}, sub)


@pytest.fixture(scope="module")
def written(tmp_path_factory):
    root = _bundle(tmp_path_factory.mktemp("admit"))
    proc = subprocess.run([sys.executable, str(TOOL), str(root), RELATION,
                           "--measure", "amount", "--write"],
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"tool exited {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
    return {
        "root": root,
        "descriptor": root / "data" / "sources" / f"{RELATION}.yaml",
        "profile": root / "data" / "profiles" / f"{RELATION}.yaml",
        "stdout": proc.stdout,
    }


def test_evidence_lands_on_the_profile(written):
    """The measured key goes where every consumer reads it: profile#identity_evidence.key."""
    prof = yaml.safe_load(written["profile"].read_text(encoding="utf-8")) or {}
    ie = prof.get("identity_evidence") or {}
    assert ie, "no identity_evidence on the ProfileFile"
    assert ie.get("key") == ["beta_id", "zeta_id"], ie.get("key")
    assert ie.get("measure") == "amount"
    assert ie.get("method")
    assert "measured_at" in ie and "source_watermark" in ie
    assert {c["name"]: c["verdict"] for c in ie.get("columns") or []} == {
        "beta_id": "IDENTITY", "zeta_id": "IDENTITY", "delta_axis": "COLLAPSIBLE"}


def test_no_evidence_on_the_descriptor(written):
    """TableFile is additionalProperties:false with no identity_evidence and no columns[].profile."""
    doc = yaml.safe_load(written["descriptor"].read_text(encoding="utf-8")) or {}
    assert "identity_evidence" not in doc, "identity_evidence written into the descriptor"
    for col in doc.get("columns") or []:
        assert "determined_by" not in (col.get("profile") or {}), \
            f"determined_by written under descriptor columns[{col['name']}].profile"


def test_determined_by_lands_on_the_profile(written):
    """A functional determinant is a MEASURED fact — ProfileFile.columns[].determined_by."""
    prof = yaml.safe_load(written["profile"].read_text(encoding="utf-8")) or {}
    by = {str(c["name"]): c for c in prof.get("columns") or []}
    assert by["gamma_code"].get("determined_by") == ["beta_id"], by["gamma_code"]
    assert "determined_by" not in by["beta_id"]


def test_roles_stay_on_the_descriptor(written):
    """A role is an AUTHORED design fact and TableFile defines it. The split moves only measurement."""
    doc = yaml.safe_load(written["descriptor"].read_text(encoding="utf-8")) or {}
    roles = {str(c["name"]): c.get("role") for c in doc.get("columns") or []}
    assert roles["beta_id"] == "composite_key_part"
    assert roles["zeta_id"] == "composite_key_part"
    # COLLAPSIBLE is the residue: the machine must not settle it.
    assert roles["delta_axis"] == "value"


def test_both_files_still_validate(written):
    """The whole point: neither plane may be left in a shape validate_schema.py rejects."""
    _validate(written["profile"], "ProfileFile")
    doc = yaml.safe_load(written["descriptor"].read_text(encoding="utf-8")) or {}
    # The fixture's own pre-split census is not a TableFile field either; drop what the fixture put
    # there so this asserts on what the TOOL wrote, not on what the read path forced us to supply.
    doc.pop("profile", None)
    doc.pop("_profile", None)
    for col in doc.get("columns") or []:
        col.pop("profile", None)
    scrubbed = written["root"] / "scrubbed.yaml"
    scrubbed.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    _validate(scrubbed, "TableFile")


def test_it_says_where_it_wrote(written):
    """The success message must name the profile, or the operator cannot tell the loop is closed."""
    assert "data/profiles" in written["stdout"], written["stdout"]
