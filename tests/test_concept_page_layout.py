#!/usr/bin/env python3
"""THE CONCEPT PAGE'S LAYOUT IS CONSTANT — every section, always, in one order.

TWO OPERATOR RULINGS, 2026-10-02, and the second is cured by the first:

    "i cannto stand that you every time invent new layout for the same document !?!?!? it is either
     you define mandatory rules for the layout or crate tempalte that you will only populate."

    "i want ALL tabs on the Concept page to ALWAYS be present. if some of them has no content ...
     then just inform that no content available"

WHAT WAS WRONG. Eight sections each carried their own `if` and vanished when empty, so the page's
SHAPE was a function of the bundle's completeness -- a concept with no edges rendered seven
sections, one with no grain six, and no two concepts produced the same document. There was nothing
to drift FROM, because there was no single layout to begin with.

WHY RULES AND NOT A TEMPLATE. A template for this page would have to carry a conditional table, a
two-direction join list and the frontmatter, which makes it a second program in a templating
language -- the drift moves rather than stops. `PAGE_SECTIONS` is the layout as data, the renderer
reads it, and this file holds every page to it. The section list is also the thing a person reviews:
one tuple, eight names, in order.

IT IS THE GRID-OF-BLANKS RULING ONE LEVEL UP: "grid of blanks hints on the error or incompletenes.
it is much better then hiding it." A missing section hides exactly what a missing column hides --
WHICH fact the bundle lacks -- and substitutes the impression of a complete page.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sdk.project.concept_page_content import (  # noqa: E402
    FIELDS_COLUMNS,
    NOTHING_DECLARED,
    PAGE_SECTIONS,
    concept_body,
)

EXEMPLARS = Path(__file__).resolve().parents[1] / "sdk/authoring/exemplars/bundle/ontology/concepts"
WORKED = Path("/Users/<operator>/dev/archive-sources/example/contoso5/ontology/concepts")


def _pages() -> list[tuple[str, str]]:
    """(name, rendered body) for every concept this machine can reach. Both bundles, because the
    claim is about the RENDERER and a layout that held on one bundle only would not be a layout."""
    out: list[tuple[str, str]] = []
    for root in (EXEMPLARS, WORKED):
        if not root.exists():
            continue
        for f in sorted(root.glob("*.yaml")):
            try:
                obj = yaml.safe_load(f.read_text()) or {}
            except Exception:  # noqa: BLE001 - an unparseable concept is another test's business
                continue
            if not (obj.get("concept") or {}).get("name"):
                continue
            name = (obj.get("concept") or {}).get("name")
            out.append(
                (
                    f"{root.parent.parent.parent.name}/{f.stem}",
                    concept_body(obj, f, name, {}),
                )
            )
    return out


@pytest.fixture(scope="module")
def pages() -> list[tuple[str, str]]:
    found = _pages()
    if not found:
        pytest.skip("no concept bundles reachable on this machine")
    return found


def _headings(body: str) -> list[str]:
    return [ln[3:].strip() for ln in body.splitlines() if ln.startswith("## ")]


def test_every_page_carries_EVERY_section(pages) -> None:
    """THE RULING, directly. Not "the sections it has are in order" — all of them, every time."""
    missing = {
        name: [s for s in PAGE_SECTIONS if s not in _headings(body)] for name, body in pages
    }
    missing = {k: v for k, v in missing.items() if v}
    assert not missing, f"sections absent from a page: {missing}"


def test_every_page_carries_them_in_ONE_order(pages) -> None:
    """The order is `PAGE_SECTIONS`, for every concept, whatever the bundle declares. This is the
    assertion that makes the layout a fact rather than an outcome."""
    wrong = {
        name: _headings(body) for name, body in pages if _headings(body) != list(PAGE_SECTIONS)
    }
    assert not wrong, f"pages whose section order is not PAGE_SECTIONS: {wrong}"


def test_no_page_has_a_section_the_LIST_does_not_declare(pages) -> None:
    """A heading the layout does not name is the drift this file exists to stop — it would be a new
    section nobody reviewed, invisible until someone noticed the document had changed again."""
    undeclared = {
        name: [h for h in _headings(body) if h not in PAGE_SECTIONS] for name, body in pages
    }
    undeclared = {k: v for k, v in undeclared.items() if v}
    assert not undeclared, f"headings outside PAGE_SECTIONS: {undeclared}"


def test_an_empty_section_SAYS_SO_rather_than_vanishing(pages) -> None:
    """The empty sentence must actually appear somewhere across the estate, or this whole mechanism
    is untested: a layout that is constant only because every bundle happens to be complete would
    pass the tests above and fail the first sparse concept."""
    assert any(NOTHING_DECLARED in body for _, body in pages), (
        "no page exercises the empty-section path — the marker is never rendered, so the rulings "
        "above are asserted against a case that does not occur"
    )


def test_the_empty_sentence_is_the_SAME_everywhere(pages) -> None:
    """One sentence for all of them, so "nothing is declared here" reads identically wherever it
    appears — the same reason an em dash means one thing across a Fields row."""
    for name, body in pages:
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("_No content available"):
                assert stripped == NOTHING_DECLARED, f"{name}: variant empty sentence {stripped!r}"


def test_the_LAYOUT_COMES_FROM_THE_GUARDRAILS_not_from_code() -> None:
    """THE LAYOUT IS A DECLARATION. A first cut wrote the section tuple in Python — a layout living
    in code, which is the defect the rest of this estate spent the day removing. This asserts the
    renderer's constants ARE the guardrails' declaration, so editing the page's shape means editing
    `delivers.concept_page.shape` and nothing else.
    """
    declared = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "guardrails/unfiled.yaml").read_text()
    )
    shape = declared["delivers"]["concept_page"]["shape"]
    assert PAGE_SECTIONS == tuple(s["heading"] for s in shape["sections"])
    assert FIELDS_COLUMNS == tuple(shape["fields_table_columns"])
    assert NOTHING_DECLARED == shape["empty_section_says"]


def test_EVERY_declared_section_is_required_always(pages) -> None:
    """The operator's ruling as the guardrails carry it. A section declared `required: when_present`
    would reintroduce exactly the conditional emission this replaced, so the declaration itself is
    held to the rule."""
    declared = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "guardrails/unfiled.yaml").read_text()
    )
    sections = declared["delivers"]["concept_page"]["shape"]["sections"]
    assert sections, "no sections declared"
    assert all(s.get("required") == "always" for s in sections), sections


def test_the_FIELDS_table_has_no_column_for_a_whole_object_fact(pages) -> None:
    """Operator, having said it several times: "i dont want to have column for somehting that
    applies for the whole object like grounded-in". `grounded in` repeated one relation on every row
    of a single-source concept. Its slot carries `identity` now, which varies per column."""
    for name, body in pages:
        for line in body.splitlines():
            if line.startswith("| column |"):
                assert "grounded in" not in line, f"{name}: {line}"
                assert "identity" in line, f"{name}: {line}"


def test_a_MULTI_SOURCE_concept_states_each_relation_as_a_HEADING(pages) -> None:
    """Where a concept IS M:N over relations the relation genuinely varies per column — and the
    answer is a sub-heading per relation, never a column that is pure repetition everywhere else."""
    for name, body in pages:
        grounded = [
            ln for ln in body.splitlines() if ln.startswith("- `") and "key `" in ln or ln.startswith("- `")
        ]
        if len(grounded) > 1 and "## Fields" in body:
            fields = body.split("## Fields", 1)[1].split("## Axes", 1)[0]
            assert "### `" in fields, f"{name}: several sources but no per-relation heading"
