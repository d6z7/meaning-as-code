"""Unit tests for the de-source contract: the generic instrument carries NO source literal. The
data-plane system prompt and the edges file take their source strings from the resolved identity,
and BOTH REFUSE to render without one -- there is no default identity to fall back to."""

import pytest

from sdk.authoring import data_plane, edges
from sdk.authoring.data_plane import dp_sys_prompt


def test_dp_prompt_is_deterministic_for_a_given_identity():
    p1 = dp_sys_prompt("ACME_SALES", "acme_curated")
    assert p1 == dp_sys_prompt("ACME_SALES", "acme_curated")  # deterministic
    assert "source: ACME_SALES," in p1 and "schema: acme_curated, type: view" in p1


def test_dp_prompt_has_no_default_identity_and_no_frozen_rendering():
    """The prompt used to default to one ontology's identity, and a module constant froze that
    rendering at import. A generic instrument that ships a specific source's name is not generic."""
    with pytest.raises(TypeError):
        dp_sys_prompt()                                   # identity is required, not defaulted
    assert not hasattr(data_plane, "DP_SYS_PROMPT")       # no frozen per-source rendering


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
    p = dp_sys_prompt("ACME_SALES", "acme_curated")
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
    with pytest.raises(TypeError):
        edges.make_edges_file([])  # missing required kw-only 'source'
