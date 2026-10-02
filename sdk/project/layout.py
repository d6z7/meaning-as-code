"""A PROJECTED DOCUMENT'S LAYOUT IS A DECLARATION — and this is the one place that reads it.

Operator, 2026-10-02: *"i cannto stand that you every time invent new layout for the same document
!?!?!? it is either you define mandatory rules for the layout or crate tempalte that you will only
populate."*

RULES, NOT A TEMPLATE, for the reason `tests/test_concept_page_layout.py` already gives: a template
for these pages would carry a conditional table and a two-direction join list, which makes it a
second program and moves the drift rather than stopping it. So the layout is DATA — a
`delivers.<artifact>.shape` in `guardrails/` — and a renderer asks for it instead of carrying
constants of its own.

WHY A MODULE AND NOT A CONSTANT PER RENDERER. `concept_page_content` grew its own loader for
`delivers.concept_page.shape`, and `knowledge.py` grew a `SECTIONS` tuple in Python. Two documents,
two mechanisms, and the second one could drift by construction because nothing declared it. This is
the lookup both of them now make, so a third document costs a guardrails entry and no code.

WHAT A DECLARATION LOOKS LIKE — `guardrails/<topic>.yaml`:

    delivers:
      <artifact>:
        shape:
          empty_section_says: "_No content available — ..."
          sections: [{heading: Details, required: always}, ...]
          fields_table_columns: [column, type, ...]        # optional, any `*_columns` key
        producers:
          - {tool: sdk/project/<module>.py, role: ..., renders: <callable>}

`renders` is what makes an artifact CHECKABLE: the callable takes a bundle root and returns
`{document name: markdown}`. Its module is the producer's own `tool:` path, so the module has one
home and the entry point sits beside it. An artifact that declares `sections` and no `renders` is a
delivered FILE (`tools/check_page_shape.py` holds those against the same declaration); one that
declares `renders` is a live rendering, and `tools/check_document_layout.py` holds it.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path

import yaml

HEADING = "## "


class LayoutUndeclared(RuntimeError):
    """An artifact was asked for its layout and the guardrails declare none."""


@dataclass(frozen=True)
class Layout:
    """One artifact's declared layout. `sections` IS the order; `always` is the required subset."""

    artifact: str
    topic: str
    sections: tuple[str, ...]
    always: tuple[str, ...]
    empty_section_says: str
    tables: dict[str, tuple[str, ...]]
    renders: tuple[str, str] | None

    def columns(self, key: str = "fields_table_columns") -> tuple[str, ...]:
        """One declared table's columns, in order. `()` where the shape declares no such table."""
        return self.tables.get(key, ())

    def render(self, bundle: Path) -> dict[str, str]:
        """`{document name: markdown}` from the declared renderer. Writes nothing."""
        if self.renders is None:
            raise LayoutUndeclared(
                f"{self.artifact} declares no `renders` on any producer, so nothing can render it; "
                f"add `renders: <callable>` to the producer that builds the document"
            )
        module, callable_name = self.renders
        fn = getattr(importlib.import_module(module), callable_name, None)
        if fn is None:
            raise LayoutUndeclared(
                f"{self.artifact} declares `renders: {callable_name}` on {module}, and that module "
                f"has no such callable — the declaration names a reader that does not exist"
            )
        return fn(Path(bundle))


def framework_root(start: Path | None = None) -> Path:
    """The nearest ancestor holding `guardrails/` — this repo, from wherever the caller sits."""
    here = Path(start or __file__).resolve()
    for parent in (here, *here.parents):
        if (parent / "guardrails").is_dir():
            return parent
    raise LayoutUndeclared(f"no `guardrails/` directory above {here}")


def declarations(root: Path | None = None) -> dict[str, tuple[str, dict]]:
    """`{artifact: (topic, declaration)}` over every `delivers` entry of every guardrails topic.

    RECURSIVE, because `guardrails/` files by group: a flat glob reads four topics as zero.
    """
    base = Path(root) if root else framework_root()
    out: dict[str, tuple[str, dict]] = {}
    for path in sorted((base / "guardrails").rglob("*.yaml")):
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue  # an unreadable topic is check_guardrails.py's refusal, not a layout fact
        if not isinstance(doc, dict):
            continue
        topic = str(doc.get("topic") or path.stem)
        for name, item in (doc.get("delivers") or {}).items():
            if isinstance(item, dict):
                out[str(name)] = (topic, item)
    return out


def _renders(item: dict, artifact: str) -> tuple[str, str] | None:
    """`(module, callable)` from the producer that declares `renders`. Two of them is a refusal."""
    found = [
        (str(p.get("tool") or "").removesuffix(".py").replace("/", "."), str(p["renders"]))
        for p in (item.get("producers") or [])
        if isinstance(p, dict) and p.get("renders")
    ]
    if len(found) > 1:
        raise LayoutUndeclared(
            f"{artifact} declares `renders` on {len(found)} producers — one document has one author: "
            + ", ".join(m for m, _ in found)
        )
    return found[0] if found else None


def _layout(artifact: str, topic: str, item: dict) -> Layout:
    shape = item.get("shape") or {}
    sections = [s for s in (shape.get("sections") or []) if isinstance(s, dict) and s.get("heading")]
    if not sections:
        raise LayoutUndeclared(
            f"`delivers.{artifact}.shape.sections` is not declared in guardrails/{topic}.yaml, so "
            f"this document has no layout. It is NOT defaulted: a renderer that invents a layout "
            f"when the declaration is missing is how a document comes to have a new shape every "
            f"session."
        )
    return Layout(
        artifact=artifact,
        topic=topic,
        sections=tuple(str(s["heading"]) for s in sections),
        always=tuple(str(s["heading"]) for s in sections if s.get("required") == "always"),
        empty_section_says=str(shape.get("empty_section_says") or ""),
        tables={
            k: tuple(str(c) for c in v)
            for k, v in shape.items()
            if k.endswith("_columns") and isinstance(v, list)
        },
        renders=_renders(item, artifact),
    )


def layout(artifact: str, root: Path | None = None) -> Layout:
    """One artifact's declared layout, or `LayoutUndeclared` naming what is missing."""
    declared = declarations(root)
    if artifact not in declared:
        raise LayoutUndeclared(
            f"no guardrails topic declares `delivers.{artifact}` — the document is undeclared, "
            f"which is a different gap from an undeclared layout"
        )
    return _layout(artifact, *declared[artifact])


def layouts(root: Path | None = None) -> dict[str, Layout]:
    """THE POPULATION: every artifact whose guardrails entry declares `shape.sections`."""
    out: dict[str, Layout] = {}
    for artifact, (topic, item) in declarations(root).items():
        if ((item.get("shape") or {}).get("sections")):
            out[artifact] = _layout(artifact, topic, item)
    return out


def headings(markdown: str) -> list[str]:
    """The document's `## ` headings, in the order it emits them."""
    return [
        line[len(HEADING):].strip()
        for line in (markdown or "").splitlines()
        if line.startswith(HEADING)
    ]


def bodies(markdown: str) -> dict[str, list[str]]:
    """`{heading: its non-blank body lines}` — what a reader finds under each `## `."""
    out: dict[str, list[str]] = {}
    current: str | None = None
    for line in (markdown or "").splitlines():
        if line.startswith(HEADING):
            current = line[len(HEADING):].strip()
            out.setdefault(current, [])
            continue
        if current is not None and line.strip():
            out[current].append(line.rstrip())
    return out


def section(heading: str, body: list, empty_says: str) -> list[str]:
    """One section, ALWAYS emitted: its heading, then its body or the declared empty sentence."""
    lines = [ln for ln in body if ln is not None]
    while lines and not str(lines[-1]).strip():
        lines.pop()
    return [f"{HEADING}{heading}", ""] + (lines if lines else [empty_says]) + [""]


__all__ = [
    "Layout",
    "LayoutUndeclared",
    "bodies",
    "declarations",
    "framework_root",
    "headings",
    "layout",
    "layouts",
    "section",
]
