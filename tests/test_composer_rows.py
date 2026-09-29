"""The composer is handed the ROWS of every grounding relation (2026-09-29).

guardrails/ontology/concepts.yaml#concept_sample names sdk/authoring/authoring.py as a consumer:
a concept is authored from its rows, never from the schema alone. This holds the seam: the
harvest's relation input ends with a sample of the served relation's rows, rendered as a table.
"""
from __future__ import annotations

import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sdk.cli.harvest import _rows_md  # noqa: E402


def test_rows_md_renders_the_sample_and_skips_provenance() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "dim_store.sample.csv"
        p.write_text("# provenance: seeded draw\nstore_key,store_name\n10,Contoso Store A|B\n20,Contoso Store C\n")
        md = _rows_md(p, limit=1)
    assert md.splitlines()[0] == "| store_key | store_name |"
    assert "| 10 | Contoso Store A\\|B |" in md
    assert "(1 of 2 sampled rows shown)" in md


def test_rows_md_is_empty_without_a_sample() -> None:
    assert _rows_md(pathlib.Path("/nonexistent/x.sample.csv")) == ""
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "h.sample.csv"
        p.write_text("a,b\n")
        assert _rows_md(p) == ""


def test_the_concept_prompt_says_the_rows_decide() -> None:
    src = (ROOT / "sdk" / "authoring" / "authoring.py").read_text()
    assert "read FROM THE ROWS" in src and "## Rows — a seeded sample" in (ROOT / "sdk" / "cli" / "harvest.py").read_text()
