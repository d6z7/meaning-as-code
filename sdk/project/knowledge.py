#!/usr/bin/env python3
"""sdk.project.knowledge — KNOWLEDGE: the CONFIGURATION and the SME-PROVIDED SOURCES.

Operator's definition, 2026-10-02: *"knowledge is something that is a combination from the
configuration and SME provided sources"*. Both halves live here, and neither is an authoring surface:

  `build(content_root)`  — THE SME HALF. Renders every `knowledge/*.sections.yaml` register into
                           sibling wiki pages. VERBATIM OR NOTHING: every span is quoted from the
                           extraction, never paraphrased, so a gate can assert it still appears in
                           the source — impossible once someone has summarised it. The source
                           documents stay out of reach (`.context/`); what is published is what they
                           SAY, attributed to the section it came from, so a reader can challenge a
                           claim without being handed a 111-page PDF. Where a diagram was lost in
                           extraction the page says so rather than filling the hole with prose.

  `project(root)`        — THE CONFIGURATION HALF. One page per concept, stating what that concept's
                           own declarations MEAN. Derived, never written by hand.

Judgement about WHICH statements are normative belongs in a separate claims layer, so extraction and
interpretation never blur. Why a thing was configured as it is belongs in `decisions/`, not here.

The register is built by a mechanical slice on the document's own heading numbering; this module only
renders it. Layout: `guardrails/unfiled.yaml#delivers.knowledge_page.shape`.
"""

from __future__ import annotations

import re
import re as _re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

ASPECT_ORDER = (
    "definition",
    "measure_evaluation_logic",
    "table_evaluation_context",
    "table_mapping",
    "warehouse_calculation",
    "bi_formula",
)


#: Acronyms that must not be title-cased into nonsense. GENERIC ones only — an estate's own domain
#: acronym is an instance specific and belongs in its bundle, not compiled into the instrument.
_ACRONYMS = ("dax", "sql", "api", "kpi", "etl")


def _pretty(key: str) -> str:
    out = key.replace("_", " ").capitalize()
    for a in _ACRONYMS:
        out = _re.sub(rf"\b{a}\b", a.upper(), out, flags=_re.I)
    return out


def _order(aspects: dict) -> list:
    known = [k for k in ASPECT_ORDER if k in aspects]
    return known + [k for k in aspects if k not in known]


def _page(entry: dict, src_doc: str) -> str:
    a = entry.get("aspects") or {}
    out = [f"# {entry['title']}", ""]
    out += [
        f"> Knowledge extracted from **{src_doc}**, section {entry.get('section')}. "
        f"Every block below is **quoted verbatim** from that source — nothing on this page is "
        f"paraphrased, so any statement can be checked against the original.",
        "",
    ]
    definition = (a.get("definition") or {}).get("text", "").strip()
    if definition:
        out += ["## Definition", "", f"*§{a['definition']['section']}*", "", definition, ""]
    for key in _order(a):
        if key == "definition":
            continue
        blk = a[key]
        text = (blk.get("text") or "").strip()
        if not text:
            continue
        out += [
            f"## {_pretty(key)}",
            "",
            f"*§{blk.get('section')} — {blk.get('title')}*",
            "",
            text,
            "",
        ]
    out += [
        "---",
        "",
        "*Source document held out of reach by design; this page is the structured knowledge "
        "taken from it. Diagrams and screenshots do not survive extraction — where the source "
        "carries one, it is not reproduced here.*",
        "",
    ]
    return "\n".join(out)


def build(content_root) -> dict:
    """Render every knowledge register under <root>/knowledge/*.sections.yaml into sibling pages."""
    root = Path(content_root)
    kdir = root / "knowledge"
    if not kdir.is_dir() or yaml is None:
        return {"registers": 0, "pages": 0}

    registers = sorted(kdir.glob("*.sections.yaml"))
    pages, index = 0, []
    for reg in registers:
        try:
            doc = yaml.safe_load(reg.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        meta = doc.get("metadata") or {}
        src_doc = meta.get("source_doc", reg.stem)
        for entry in doc.get("sections") or []:
            slug = entry.get("slug") or re.sub(r"[^a-z0-9]+", "-", entry["title"].lower()).strip(
                "-"
            )
            (kdir / f"{slug}.md").write_text(_page(entry, src_doc), encoding="utf-8")
            pages += 1
            n = len(entry.get("aspects") or {})
            index.append(f"| [{entry['title']}]({slug}.md) | §{entry.get('section')} | {n} |")

    if index:
        (kdir / "index.md").write_text(
            "\n".join(
                [
                    "# Source knowledge",
                    "",
                    "Structured knowledge extracted from the source documents. The documents themselves are "
                    "held out of reach by design — what is published here is what they *say*, quoted verbatim "
                    "and attributed to its section, so a reader can challenge a statement without needing the "
                    "original.",
                    "",
                    "Nothing here is paraphrased. Diagrams and screenshots do not survive extraction and are "
                    "not reproduced.",
                    "",
                    "| Topic | Section | Aspects |",
                    "|---|---|---|",
                    *index,
                    "",
                ]
            ),
            encoding="utf-8",
        )
    return {"registers": len(registers), "pages": pages}


from sdk.project import layout as _layout_reader

#: THE LAYOUT IS READ, NOT TYPED. These five headings were a tuple here, which is a layout living in
#: code — the drift the concept page's declaration exists to stop, in a second document.
#: `guardrails/unfiled.yaml#delivers.knowledge_page.shape` is the home.
LAYOUT = _layout_reader.layout("knowledge_page")

#: Every section of a knowledge page, in order, all of them always present.
SECTIONS: tuple[str, ...] = LAYOUT.sections

NOTHING: str = LAYOUT.empty_section_says


def _section(heading: str, body: list[str]) -> list[str]:
    return _layout_reader.section(heading, body, NOTHING)


def _columns(grounding: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for source in (grounding.get("sources") or []):
        if isinstance(source, dict) and isinstance(source.get("columns"), dict):
            for name, body in source["columns"].items():
                out.setdefault(str(name), body if isinstance(body, dict) else {})
    return out


def _configuration(obj: dict) -> list[str]:
    """What the declarations STATE, in sentences — the configuration half."""
    concept = obj.get("concept") or {}
    grounding = obj.get("grounding") or {}
    columns = _columns(grounding)
    out: list[str] = []
    if grounding.get("grain"):
        out.append(f"- Its grain is **{str(grounding['grain']).strip()}**.")
    key = [n for n, b in columns.items() if b.get("identity") in ("canonical", "part")]
    if key:
        out.append(f"- One row is identified by {', '.join(f'`{k}`' for k in key)}.")
    measures = {n: b["measure"] for n, b in columns.items() if isinstance(b.get("measure"), dict)}
    for name, measure in measures.items():
        bits = [str(measure.get("type", "")).rsplit(".", 1)[-1], str(measure.get("unit") or "")]
        word = " ".join(b for b in bits if b)
        canonical = " — the number a question about this concept folds" if measure.get("canonical") else ""
        out.append(f"- `{name}` is a {word} measure{canonical}.")
    axes = {n: b["axis_kind"] for n, b in columns.items() if b.get("axis_kind")}
    if axes:
        out.append(
            "- It is aggregated along "
            + ", ".join(f"`{n}` ({str(k).rsplit('.', 1)[-1]})" for n, k in axes.items())
            + "."
        )
    for name, body in columns.items():
        rulings = body.get("rulings") if isinstance(body.get("rulings"), dict) else None
        if not rulings:
            continue
        if rulings.get("label_of"):
            out.append(
                f"- `{name}` is another name for `{rulings['label_of']}`'s thing"
                + (f", in the {rulings['register']} register" if rulings.get("register") else "")
                + " — group on the named column and show this one."
            )
        if rulings.get("never_axis"):
            out.append(
                f"- `{name}` must never be grouped on: {rulings['never_axis']}"
                + (f" ({rulings['evidence']})" if rulings.get("evidence") else "")
                + "."
            )
    if concept.get("identity", {}).get("kind"):
        out.append(f"- Its identity is established as `{concept['identity']['kind']}`.")
    return out


def _rules(obj: dict) -> list[str]:
    out: list[str] = []
    for rule in ((obj.get("contract") or {}).get("rules") or []):
        if not isinstance(rule, dict):
            continue
        kind = str(rule.get("kind", "")).rsplit(".", 1)[-1]
        out.append(f"- **{rule.get('id')}** ({kind})")
        for key, label in (("when", "when"), ("then", "then"), ("never", "never")):
            value = rule.get(key)
            if isinstance(value, str) and value.strip():
                out.append(f"    - _{label}_ — {value.strip()}")
        for binding in (rule.get("realized_by") or []):
            if isinstance(binding, dict) and binding.get("udf"):
                out.append(f"    - _executed by_ — `{binding['udf']}`")
    return out


def _values(obj: dict) -> list[str]:
    """Where the members come from — a register, or (banned) an inline list."""
    out: list[str] = []
    for name, body in _columns(obj.get("grounding") or {}).items():
        if body.get("register"):
            out.append(f"- `{name}` takes its members from `{body['register']}`.")
    inline = ((obj.get("values") or {}) if isinstance(obj.get("values"), dict) else {}).get("items")
    if inline:
        out.append(
            f"- **{len(inline)} members are inlined in the concept**, which is banned: values "
            f"belong in a register and the column points at it "
            f"(tools/check_no_inline_values.py)."
        )
    return out


def _sme_sources(sections: list[dict], concept_name: str) -> list[str]:
    """The SME half — verbatim sections that name this concept. Attributed, never paraphrased."""
    out: list[str] = []
    needle = concept_name.casefold()
    for section in sections or []:
        if not isinstance(section, dict):
            continue
        text = " ".join(str(section.get(k, "")) for k in ("title", "section", "body", "text"))
        if needle and needle not in text.casefold():
            continue
        out.append(f"- **{section.get('id')}** · {section.get('title')}")
        body = str(section.get("body") or section.get("text") or "").strip()
        if body:
            out += ["", "  > " + body.replace("\n", "\n  > "), ""]
    return out


def load_sme_sections(root: Path) -> list[dict[str, Any]]:
    """Every SME-provided section in the bundle, from `knowledge/*.sections.yaml`.

    THE SAME CONVENTION `build` RENDERS. A second glob here would be a second answer to "where does
    SME knowledge live", and the two would drift the first time one moved.
    """
    out: list[dict[str, Any]] = []
    if yaml is None:
        return out
    for path in sorted((Path(root) / "knowledge").glob("*.sections.yaml")):
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001 - a malformed register is `build`'s business to report
            continue
        if isinstance(doc, dict) and isinstance(doc.get("sections"), list):
            out.extend(s for s in doc["sections"] if isinstance(s, dict))
    return out


def knowledge_body(obj: dict, *, sme_sections: list[dict] | None = None) -> str:
    """One concept's knowledge page: the declared sections, in the declared order, populated.

    THE ORDER IS THE DECLARATION'S. A section this module cannot populate RAISES rather than
    quietly going missing — a declared heading with no builder is the drift, not a blank.
    """
    concept = obj.get("concept") or {}
    name = str(concept.get("name") or "")
    definition = str(concept.get("definition") or "").strip()
    built: dict[str, list[str]] = {
        "What it is": [definition] if definition else [],
        "What the configuration states": _configuration(obj),
        "Rules that govern it": _rules(obj),
        "Where its values come from": _values(obj),
        "SME sources": _sme_sources(sme_sections or [], name),
    }
    missing = [h for h in SECTIONS if h not in built]
    if missing:
        raise _layout_reader.LayoutUndeclared(
            f"guardrails declares knowledge_page section(s) {missing} and this module builds no "
            f"body for them — declare the builder here or remove the section from the declaration"
        )
    parts: list[str] = [f"# {concept.get('label') or name} — knowledge", ""]
    for heading in SECTIONS:
        parts += _section(heading, built[heading])
    return "\n".join(parts)


def project(root: Path, *, out_dir: Path | None = None) -> dict[str, str]:
    """`{concept stem: knowledge page}` for every concept of the bundle. Writes only if `out_dir`."""
    root = Path(root)
    sme = load_sme_sections(root)
    pages: dict[str, str] = {}
    concepts = root / "ontology" / "concepts"
    for path in sorted(concepts.glob("*.yaml")):
        try:
            obj = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(obj, dict) or not (obj.get("concept") or {}).get("name"):
            continue
        pages[path.stem] = knowledge_body(obj, sme_sections=sme)
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for stem, body in pages.items():
            (out_dir / f"{stem}.md").write_text(body, encoding="utf-8")
    return pages


__all__ = [
    "ASPECT_ORDER",
    "LAYOUT",
    "NOTHING",
    "SECTIONS",
    "build",
    "knowledge_body",
    "load_sme_sections",
    "project",
]
