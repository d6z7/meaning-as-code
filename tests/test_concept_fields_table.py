"""THE FIELDS TABLE PROJECTED THREE OF THE FACTS IT HAD AND CALLED THE REST ABSENT.

The operator, reading a generated concept page:

    "on your pages for concepts there is a table with all columns. but not all of what you declare
     being defined above is projected to the table. can you correct this please?"

Measured on a live bundle at that moment: **117 column rows across 17 concept pages, 0 carrying a
description, 5 carrying a join, and no type column at all** — while `type` was declared on 167 of
167 descriptor columns and prose sat on disk in two places the builder never read.

FOUR CAUSES, ALL LOOKUPS THAT MISSED, none of them a missing declaration:

  1. `_column_descriptions` read `c["description"]`, a key present on **0 of 167** columns. The
     prose that existed was in `notes` (35 of 167). A blank rendered as "nothing is declared" when
     the truth was "the reader looked in the wrong place" — the two states a reader most needs kept
     apart, collapsed into one glyph.
  2. The concept's OWN `properties[].doc` — the richest prose in the bundle — was never joined,
     because it is keyed camelCase (`productKey`) against a table keyed by the physical column
     (`ProductKey`).
  3. Metadata was looked up for ONE relation while the table lists the union of ALL of a concept's
     sources, so every column of a second source came back blank: 6 of 117 once `type` landed.
  4. The join column was parsed only out of `join_rule`, which **12 of 17 edges do not carry** —
     correctly, because both concepts ground on one relation and a predicate there would be an
     invented self-join. Those edges declare `realized_by` instead, and were simply dropped.

WHAT THESE TESTS REFUSE TO LET BACK IN, in order of how much damage each did:

  · A BLANK THAT LIES. Every assertion here is about a cell being filled FROM A NAMED SOURCE, or
    being empty because nothing declares it. The operator's rule on emptiness — "grid of blanks
    hints on the error or incompletenes. it is much better then hiding it" — means the fix was
    never to hide a column; it was to make the blank honest and to count it.
  · A GUESSED MATCH. The casefold join is a narrow claim: same letters, different capitalisation.
    Two properties colliding under it withhold BOTH docs, because attaching either would state
    something the concept did not say. That is tested, because a silent mismatch is worse than the
    blank it replaces.
  · A BUSINESS EDGE DRESSED AS A FOREIGN KEY. The operator ruled the two planes must read as two.
    A bare link would tell a reader the concepts are joined in the warehouse; for 11 of 17 edges
    that is false.

Run: python3 -m pytest tests/test_concept_fields_table.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sdk.project.concept_page_content import (  # noqa: E402
    _column_descriptions,
    _edge_joins,
    _merged_col_meta,
    _property_docs,
)


# --------------------------------------------------------------------------------------------
# 1 · the descriptor: description OR notes, and the type that was never shown
# --------------------------------------------------------------------------------------------


def _bundle(tmp_path: Path, columns: list[dict], relation: str = "srv_alpha") -> Path:
    data = tmp_path / "data" / "datasets"
    data.mkdir(parents=True)
    (data / f"{relation}.yaml").write_text(
        yaml.safe_dump({"table": {"name": relation}, "columns": columns})
    )
    return tmp_path / "data"


def test_description_is_read_from_description_when_declared(tmp_path: Path) -> None:
    d = _column_descriptions(_bundle(tmp_path, [{"name": "a", "type": "varchar", "description": "D"}]))
    assert d["srv_alpha"]["a"]["description"] == "D"


def test_notes_is_the_fallback_not_a_synonym(tmp_path: Path) -> None:
    """`description` wins when both are present: the schema declares it, so a bundle that fills it
    means it. This is the assertion that keeps `notes` a fallback rather than a second home."""
    cols = [
        {"name": "a", "type": "varchar", "notes": "from notes"},
        {"name": "b", "type": "varchar", "description": "from description", "notes": "ignored"},
    ]
    d = _column_descriptions(_bundle(tmp_path, cols))["srv_alpha"]
    assert d["a"]["description"] == "from notes"
    assert d["b"]["description"] == "from description"


def test_the_type_is_carried_because_the_table_never_showed_it(tmp_path: Path) -> None:
    d = _column_descriptions(_bundle(tmp_path, [{"name": "a", "type": "decimal(20,5)"}]))
    assert d["srv_alpha"]["a"]["type"] == "decimal(20,5)"


def test_a_column_declaring_neither_yields_an_empty_string_not_a_guess(tmp_path: Path) -> None:
    d = _column_descriptions(_bundle(tmp_path, [{"name": "a", "type": "integer"}]))
    assert d["srv_alpha"]["a"]["description"] == ""


# --------------------------------------------------------------------------------------------
# 1b · a descriptor that will not parse is REPORTED, not dropped
#
# The `except` here used to `continue` in silence. Measured by tools/check_seam_contract.py against
# the public example bundle: corrupting each of the concept-page seam's traced inputs in turn, 8 of
# 17 changed the payload NOT AT ALL — a quarter of the Fields table can vanish through this line
# while the page renders as a clean derivation. The read site is the one place that knows, so it is
# the one place that reports; SEAM_CONTRACT.md §5 leaves what to DO about it to the caller.
# --------------------------------------------------------------------------------------------


def test_an_unparseable_descriptor_is_reported_to_a_caller_that_asks(tmp_path: Path) -> None:
    data = _bundle(tmp_path, [{"name": "a", "type": "varchar", "description": "D"}])
    (data / "datasets" / "srv_broken.yaml").write_text("{{{ not yaml ]]]\n\t:- :\n")
    errors: list = []
    out = _column_descriptions(data, errors=errors)
    assert [e["path"] for e in errors] == ["data/datasets/srv_broken.yaml"], (
        "the path is ROOT-relative, because a seam that forwards it must not leak a disk path"
    )
    assert errors[0]["error"], "and it carries the parse error, not just the fact of one"
    assert out["srv_alpha"]["a"]["description"] == "D", (
        "and what COULD be read is still returned — reporting is not refusing"
    )


def test_the_report_is_additive_so_every_existing_caller_is_unchanged(tmp_path: Path) -> None:
    """No out-list, no change: `build` still projects what it can. The one behaviour this adds is
    that a caller may now ASK, which is the difference between a swallowed read and a reported one."""
    data = _bundle(tmp_path, [{"name": "a", "type": "varchar", "description": "D"}])
    (data / "datasets" / "srv_broken.yaml").write_text("{{{ not yaml ]]]\n\t:- :\n")
    assert _column_descriptions(data) == _column_descriptions(data, errors=[])


def test_a_clean_data_plane_reports_nothing(tmp_path: Path) -> None:
    """The negative control: the refusal the page seam builds on this must not be a constant."""
    errors: list = []
    _column_descriptions(_bundle(tmp_path, [{"name": "a", "type": "varchar"}]), errors=errors)
    assert errors == []


# --------------------------------------------------------------------------------------------
# 2 · the concept's own properties[].doc, joined across a spelling difference
# --------------------------------------------------------------------------------------------


def test_a_camelcase_property_matches_its_pascalcase_column() -> None:
    docs = _property_docs({"properties": [{"name": "alphaKey", "doc": "the identity"}]})
    assert docs["alphakey".casefold()] == "the identity"
    assert docs.get("AlphaKey".casefold()) == "the identity"


def test_a_collision_withholds_BOTH_docs_rather_than_picking_one() -> None:
    """Two properties casefolding to one key make the mapping ambiguous. Attaching either doc to a
    column would state something the concept did not, so the cell must read as undeclared — which
    is true — instead of as wrong, which is worse and invisible."""
    docs = _property_docs(
        {"properties": [{"name": "alphaKey", "doc": "one"}, {"name": "AlphaKey", "doc": "two"}]}
    )
    assert "alphakey" not in docs


def test_the_same_doc_twice_is_not_a_collision() -> None:
    docs = _property_docs(
        {"properties": [{"name": "alphaKey", "doc": "same"}, {"name": "AlphaKey", "doc": "same"}]}
    )
    assert docs["alphakey"] == "same"


def test_a_property_with_no_doc_contributes_nothing() -> None:
    docs = _property_docs({"properties": [{"name": "alphaKey", "type": "integer"}]})
    assert docs == {}


# --------------------------------------------------------------------------------------------
# 3 · every source, not just the first
# --------------------------------------------------------------------------------------------


def test_a_column_of_a_SECOND_source_is_resolved() -> None:
    """The measured symptom: 6 of 117 rows blank once the type column landed, every one of them a
    column belonging to a concept's second grounding source."""
    col_desc = {
        "rel_one": {"a": {"description": "from one", "type": "integer"}},
        "rel_two": {"b": {"description": "from two", "type": "varchar"}},
    }
    obj = {"grounding": {"sources": [{"relation": "rel_one"}, {"relation": "srv.rel_two"}]}}
    merged = _merged_col_meta(col_desc, obj, "stem", "rel_one")
    assert merged["a"]["description"] == "from one"
    assert merged["b"]["description"] == "from two"


def test_the_first_declared_source_wins_a_name_collision() -> None:
    col_desc = {
        "rel_one": {"shared": {"description": "first", "type": "integer"}},
        "rel_two": {"shared": {"description": "second", "type": "varchar"}},
    }
    obj = {"grounding": {"sources": [{"relation": "rel_one"}, {"relation": "rel_two"}]}}
    assert _merged_col_meta(col_desc, obj, "stem", "rel_one")["shared"]["description"] == "first"


def test_a_concept_grounding_on_nothing_yields_an_empty_map() -> None:
    assert _merged_col_meta({}, {"grounding": {}}, "stem", None) == {}


# --------------------------------------------------------------------------------------------
# 4 · the edges: a business edge carries a column too, and must not read as a foreign key
# --------------------------------------------------------------------------------------------


def _edges_bundle(tmp_path: Path, edges: list[dict]) -> tuple[Path, list]:
    ont = tmp_path / "ontology"
    (ont / "concepts").mkdir(parents=True)
    (ont / "edges.yaml").write_text(yaml.safe_dump({"edges": edges}))
    concepts = [
        ("alpha", ont / "concepts" / "alpha.yaml", {"concept": {"name": "Alpha", "label": "Alpha"}}, {}),
        ("beta", ont / "concepts" / "beta.yaml", {"concept": {"name": "Beta", "label": "Beta"}}, {}),
    ]
    return ont / "concepts", concepts


def test_a_physical_edge_takes_its_column_from_the_join_rule(tmp_path: Path) -> None:
    src, concepts = _edges_bundle(
        tmp_path,
        [{
            "edge_id": "alpha__x__beta", "level": "physical",
            "endpoints": {"from": {"concept": "Alpha"}, "to": {"concept": "Beta"}},
            "join_rule": "rel_a.BetaKey = rel_b.BetaKey",
        }],
    )
    out = _edge_joins(src, concepts)["Alpha"]["out"]
    assert [(j["on"], j["level"]) for j in out] == [("BetaKey", "physical")]


def test_a_business_edge_with_NO_join_rule_takes_its_column_from_realized_by(tmp_path: Path) -> None:
    """12 of 17 declared edges carry no join_rule — correctly, because both concepts ground on one
    relation. Reading the column only from join_rule dropped every one of them from the table."""
    src, concepts = _edges_bundle(
        tmp_path,
        [{
            "edge_id": "alpha__x__beta", "level": "business",
            "endpoints": {"from": {"concept": "Alpha"}, "to": {"concept": "Beta"}},
            "realized_by": "rel_a.GammaCode",
        }],
    )
    out = _edge_joins(src, concepts)["Alpha"]["out"]
    assert [(j["on"], j["level"]) for j in out] == [("GammaCode", "business")]


def test_a_key_to_value_realisation_puts_the_KEY_on_the_from_side(tmp_path: Path) -> None:
    src, concepts = _edges_bundle(
        tmp_path,
        [{
            "edge_id": "alpha__x__beta", "level": "business",
            "endpoints": {"from": {"concept": "Alpha"}, "to": {"concept": "Beta"}},
            "realized_by": "rel_a.AlphaKey -> rel_a.BetaStatus",
        }],
    )
    joins = _edge_joins(src, concepts)
    assert joins["Alpha"]["out"][0]["on"] == "AlphaKey"
    assert joins["Beta"]["in"][0]["on"] == "BetaStatus"


def test_an_edge_declaring_neither_is_dropped_rather_than_guessed(tmp_path: Path) -> None:
    src, concepts = _edges_bundle(
        tmp_path,
        [{
            "edge_id": "alpha__x__beta", "level": "business",
            "endpoints": {"from": {"concept": "Alpha"}, "to": {"concept": "Beta"}},
        }],
    )
    assert _edge_joins(src, concepts)["Alpha"]["out"][0]["on"] is None
