#!/usr/bin/env python3
"""A PROJECTED DOCUMENT'S LAYOUT IS DECLARED, SHARED, AND FROZEN.

Operator, 2026-10-02: *"i cannto stand that you every time invent new layout for the same document
!?!?!? it is either you define mandatory rules for the layout or crate tempalte that you will only
populate."*

`tests/test_concept_page_layout.py` holds ONE document to its declaration. This holds the
FRAMEWORK: that the lookup has one home (`sdk/project/layout.py`), that the population is
discovered from the guardrails rather than listed anywhere, that the second document
(`knowledge_page`) now reads its layout instead of carrying a Python tuple, and that each rendered
document is byte-identical to a committed golden — so an unintended change fails and an intended
one is `--accept` plus a reviewable `git diff tests/golden/`.

Run: `python3 -m pytest tests/test_document_layout.py -q`
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import _neighbours  # noqa: E402  — one home for the checkouts beside this repository

from sdk.project import knowledge as K  # noqa: E402
from sdk.project import layout as L  # noqa: E402
from sdk.project.concept_page_content import (  # noqa: E402
    FIELDS_COLUMNS,
    NOTHING_DECLARED,
    PAGE_SECTIONS,
)
from tools import check_document_layout as C  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / C.FREEZE_BUNDLE
#: DISCOVERED, NOT NAMED — the estate checkout's name is an identity this public repo must not
#: carry. `$MAC_WORKED_BUNDLES` overrides; a machine with none skips the worked-bundle arm.
WORKED = _neighbours.worked_bundles()

#: The five headings `sdk/project/knowledge.py` carried as a Python tuple before the migration.
#: Behaviour identical means THIS list, in THIS order, still comes out of the declaration.
KNOWLEDGE_SECTIONS_BEFORE = (
    "What it is",
    "What the configuration states",
    "Rules that govern it",
    "Where its values come from",
    "SME sources",
)


@pytest.fixture(scope="module")
def rendered() -> dict[str, dict[str, str]]:
    """{artifact: {document: markdown}} for every artifact whose declaration names a renderer."""
    return {
        name: lay.render(BUNDLE)
        for name, lay in L.layouts(ROOT).items()
        if lay.renders is not None
    }


# ── the reader is the one home ────────────────────────────────────────────────────────────────
def test_the_concept_page_reads_its_LAYOUT_through_the_shared_reader() -> None:
    """The constants the renderer exports ARE the declaration, via `layout.py` and nothing else."""
    lay = L.layout("concept_page", ROOT)
    assert PAGE_SECTIONS == lay.sections
    assert NOTHING_DECLARED == lay.empty_section_says
    assert FIELDS_COLUMNS == lay.columns("fields_table_columns")


def test_the_KNOWLEDGE_page_reads_its_sections_from_the_guardrails() -> None:
    """The migration: a `SECTIONS` tuple in Python became `delivers.knowledge_page.shape`."""
    declared = yaml.safe_load((ROOT / "guardrails/unfiled.yaml").read_text())
    shape = declared["delivers"]["knowledge_page"]["shape"]
    assert K.SECTIONS == tuple(s["heading"] for s in shape["sections"])
    assert K.NOTHING == shape["empty_section_says"]


def test_the_KNOWLEDGE_page_behaves_EXACTLY_as_before_the_migration() -> None:
    """Same five headings, same order. A migration that changed the document would be the defect."""
    assert K.SECTIONS == KNOWLEDGE_SECTIONS_BEFORE


def test_a_declared_section_the_renderer_cannot_populate_RAISES(monkeypatch) -> None:
    """A heading added to the declaration and to no builder must stop, not render as a blank."""
    monkeypatch.setattr(K, "SECTIONS", K.SECTIONS + ("Provenance",))
    with pytest.raises(L.LayoutUndeclared):
        K.knowledge_body({"concept": {"name": "Thing"}})


def test_an_UNDECLARED_artifact_has_no_defaulted_layout() -> None:
    """A renderer that invents a layout when the declaration is missing is the whole defect."""
    with pytest.raises(L.LayoutUndeclared):
        L.layout("no_such_document", ROOT)


def test_two_producers_claiming_to_render_one_document_is_REFUSED() -> None:
    """One document, one author — the estate's standing rule, enforced where it is declared."""
    with pytest.raises(L.LayoutUndeclared):
        L._renders(
            {"producers": [{"tool": "a/b.py", "renders": "x"}, {"tool": "c/d.py", "renders": "y"}]},
            "two_authors",
        )


# ── the population is discovered, never listed ────────────────────────────────────────────────
def test_EVERY_artifact_that_declares_sections_is_in_the_POPULATION() -> None:
    """Measured independently off `guardrails/**/*.yaml`, because a checker that hard-codes its
    list cannot report the one artifact somebody forgot to add to it."""
    expected = set()
    for path in sorted((ROOT / "guardrails").rglob("*.yaml")):
        doc = yaml.safe_load(path.read_text()) or {}
        for name, item in ((doc.get("delivers") or {}) if isinstance(doc, dict) else {}).items():
            if isinstance(item, dict) and ((item.get("shape") or {}).get("sections")):
                expected.add(name)
    assert set(L.layouts(ROOT)) == expected
    assert len(expected) >= 9, expected


def test_a_declared_section_of_a_RENDERED_document_is_required_always(rendered) -> None:
    """`required: when_present` would reintroduce the conditional emission this replaced."""
    for artifact in rendered:
        lay = L.layout(artifact, ROOT)
        assert lay.always == lay.sections, artifact


# ── the rules, over every rendered document ───────────────────────────────────────────────────
def test_every_rendered_document_IS_its_declared_layout(rendered) -> None:
    findings = [
        f
        for artifact, docs in rendered.items()
        for document, text in docs.items()
        for f in C.check_rules(L.layout(artifact, ROOT), document, text)
    ]
    assert not findings, findings


def test_the_rules_hold_on_a_WORKED_bundle_too() -> None:
    """A layout that held on the exemplars alone would be a property of four small concepts."""
    if not WORKED:
        pytest.skip("no worked bundle reachable on this machine")
    findings = []
    for bundle in WORKED:
        for artifact, lay in L.layouts(ROOT).items():
            if lay.renders is None:
                continue
            for document, text in lay.render(bundle).items():
                findings += C.check_rules(lay, document, text)
    assert not findings, findings


def test_the_empty_sentence_is_actually_EXERCISED(rendered) -> None:
    """A layout constant only because every bundle is complete would pass everything above."""
    for artifact, docs in rendered.items():
        says = L.layout(artifact, ROOT).empty_section_says
        assert any(says in text for text in docs.values()), artifact


# ── the freeze ────────────────────────────────────────────────────────────────────────────────
def test_the_rendering_is_BYTE_IDENTICAL_to_the_frozen_document(rendered) -> None:
    """THE FREEZE. The rules above cannot see a sentence reworded or a cell reordered; this can."""
    findings = [
        f
        for artifact, docs in rendered.items()
        for f in C.check_freeze(ROOT / C.GOLDEN_DIR, artifact, docs)
    ]
    assert not findings, findings


def test_every_rendered_document_HAS_a_frozen_copy(rendered) -> None:
    """A document with no golden is unfrozen and free to drift — `--accept` is the deliberate act."""
    for artifact, docs in rendered.items():
        for document in docs:
            assert (ROOT / C.GOLDEN_DIR / artifact / f"{document}.md").is_file(), (
                f"{artifact}/{document} is not frozen"
            )


def test_the_checker_SELF_TEST_passes() -> None:
    """One seeded mutant per reject class, including the word-level rewrite only a golden catches."""
    assert C._self_test() == 0
