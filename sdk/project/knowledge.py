#!/usr/bin/env python3
"""sdk.project.knowledge — surface SOURCE KNOWLEDGE in the wiki, structured.

THE POINT, and the thing that took a while to say clearly: the source documents themselves stay
hidden and out of reach (``.context/``, excluded from every wiki listing). What belongs in the wiki is
the KNOWLEDGE extracted from them — structured, addressable, and attributed to the section it came
from, so a reader can challenge a claim without being handed a 111-page PDF.

VERBATIM OR NOTHING. Every span rendered here is quoted from the extraction, never paraphrased. That
is not stylistic: it makes the register mechanically verifiable — a gate can assert that each span
still appears in the source, which is impossible once someone has summarised it. Where a diagram or a
screenshot was lost in extraction, the page says so rather than filling the hole with prose.

The register is built by a mechanical slice on the document's own heading numbering (see
``knowledge/*.sections.yaml``); this module only renders it. Judgement about WHICH statements are
normative belongs in a separate claims layer, so that extraction and interpretation never blur.
"""

from __future__ import annotations

import re
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

ASPECT_ORDER = (
    "definition",
    "measure_evaluation_logic",
    "table_evaluation_context",
    "table_mapping",
    "redshift_calculation",
    "dax_codes",
)


def _pretty(key: str) -> str:
    return key.replace("_", " ").replace("gaps", "GAPS").replace("dax", "DAX").capitalize()


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
