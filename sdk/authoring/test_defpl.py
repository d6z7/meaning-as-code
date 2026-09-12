"""Unit tests for the Phase-6 de-FPL contract: the generic instrument carries NO source
literal — the data-plane system prompt and the edges file take their source strings from the
resolved identity — yet the gaps/fpl rendering is BYTE-IDENTICAL (a refactor, not a change)."""

from sdk.authoring import edges
from sdk.authoring.data_plane import DP_SYS_PROMPT, dp_sys_prompt


def test_dp_prompt_gaps_fpl_render_is_stable_and_matches_the_module_constant():
    """The gaps/fpl rendering is deterministic and IS the exported DP_SYS_PROMPT constant.
    (The one-time byte-identity-vs-pre-refactor check was verified during Phase 6 by a stash-diff of the
    full served surface; a `git show HEAD` baseline is not durable — HEAD moved once Phase 6 committed.)"""
    p1 = dp_sys_prompt("FPL", "fpl")
    assert p1 == dp_sys_prompt("FPL", "fpl")  # deterministic
    assert p1 == DP_SYS_PROMPT  # the module constant is the FPL rendering
    assert "source: FPL," in p1 and "schema: fpl, type: view" in p1


def test_dp_prompt_swaps_source_and_schema_with_no_fpl_residue():
    p = dp_sys_prompt("ACME_SALES", "acme_curated")
    assert "source: ACME_SALES," in p
    assert "relation: acme_curated.<bare_name>" in p  # canonical: BASE name (no _clean), own schema
    assert "schema: acme_curated, type: view" in p
    assert "FPL" not in p and "fpl" not in p  # no source literal leaks through
    assert "{{" not in p and "}}" not in p  # every sentinel was substituted


def test_dp_prompt_mandates_canonical_name_and_extracted_sql():
    """The right-first-time mandates are STANDING defaults in the prompt: the serving relation uses
    the raw BASE name everywhere (no _clean divergence), the full view body is a top-level
    `transform_sql` (extracted to a sibling .sql — never inline), and the lookup register is named."""
    p = dp_sys_prompt("FPL", "fpl")
    assert "clean_view_name" not in p  # the _clean divergence is gone from the shape
    assert "transform_sql" in p  # the 5th key carries the full view body
    assert "sql_file: <bare_name>.sql" in p  # the YAML keeps only a pointer
    assert "CANONICAL NAME" in p and "NO `clean_`/`_clean`" in p
    assert "data/lookups/<bare_name>.lookup.csv" in p  # the no-probe register the ontology ships
    assert "five top-level keys" in p


def test_dp_prompt_preserves_literal_percent():
    # the "% formatting would break here" hazard: a literal % must survive substitution
    assert "null in 9.8% of rows" in dp_sys_prompt("X", "y")


def test_edges_file_requires_an_explicit_source_label():
    ef = edges.make_edges_file([], source="ACME_SALES")
    assert ef["obj"]["metadata"]["source"] == "ACME_SALES"
    # the generic module carries no default source literal — it MUST be passed in
    import pytest

    with pytest.raises(TypeError):
        edges.make_edges_file([])  # missing required kw-only 'source'
