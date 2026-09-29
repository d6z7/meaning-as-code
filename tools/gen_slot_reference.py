#!/usr/bin/env python3
"""gen_slot_reference.py — the PER-SLOT reference, generated from the schema and the vocabulary.

WHY, IN ONE SENTENCE: a hand-written synopsis can document a grammar that does not exist, and ours does.

MEASURED 2026-09-28. `reference_manual/column_rulings.md` opens with a man-page SYNOPSIS — the shape the
operator asked for, already in the tree — and every line of it is unimplemented:

    columns:
      <column>:
        rulings:                          <- "rulings" appears 0 times in mac.schema.json
          never_axis: privacy|grain|derived   <- those 3 values are in NO vocabulary block
          evidence:   <dq-id>             <- not a key the column map admits

The column map admits exactly `role`, `identity`, `measure` with `additionalProperties: false`, so every
ruling in that synopsis would be REFUSED by validate_schema. The page is not wrong about what the
grammar SHOULD be; it is wrong about what it IS, and nothing could tell the difference. That is the same
defect as a schema enum drifting from its vocabulary, one surface over — and the same fix: derive it.

WHAT IT DERIVES, AND FROM WHERE (nothing here holds a copy):
    mac.schema.json      which keys a slot admits, their types, what is required, what is closed
    mac_vocabulary.yaml  the TERMS of any vocabulary governing a key, and each term's meaning

SHAPE: Ansible's module-reference layout, because it is the one an operator already reads elsewhere —
SYNOPSIS, then a parameter table (key · type · required · choices · comment), then notes. A choices cell
is the vocabulary's term list, so a page cannot advertise a term the framework does not close.

`--check` fails when a page is stale, the same contract gen_vocabulary_terms.py and gen_schema_shapes.py
already use: a generator nobody re-runs is prose again within a week.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import textwrap

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_vocabulary_parity as parity  # noqa: E402 — the ONE home of the slot -> vocabulary table

#: (page, title, JSON path to the object, prose). WHICH KEYS A PAGE'S OBJECT GOVERNS, AND BY WHICH
#: VOCABULARY, IS NOT DECLARED HERE: it is derived from check_vocabulary_parity.PAIRS — the one home of
#: the slot -> vocabulary table — so a slot the parity gate checks is a slot this page documents, and
#: the two cannot drift. Until 2026-09-29 this file carried its own `governs` map beside PAIRS ("the
#: parity gate declares three pairs, this declares the rest"): two tables of one fact.
PAGES = (
    ("column_map", "The column map — everything about one column, on the column",
     ["$defs", "grounding", "properties", "sources", "items", "properties", "columns",
      "oneOf", 1, "additionalProperties"],
     "Keyed by column name; each value is that column's flags, or `null` to serve the column and say "
     "nothing more. This is the CONCEPT plane's view of a column — what a query may do with it. The "
     "relation's own physical shape is a different slot (see the data plane) and the two routinely "
     "differ: measured on the reference bundle, 16 of 16 concept/relation pairings had a physical "
     "primary key that was NOT the concept's identity, because an inline dimension is never keyed by "
     "its host's row key."),

    ("relation_column", "The relation's column — the data plane's physical shape",
     ["$defs", "TableFile", "properties", "columns", "items"],
     "One entry per column of a described relation, in data/sources (a raw landing) or data/datasets (a "
     "served relation). This is what the relation IS, MEASURED from the warehouse rather than declared "
     "by a person — which is why it is a different slot from the concept plane's column map and why the "
     "two routinely disagree: a relation's primary key identifies a ROW, a concept's canonical key "
     "identifies a MEMBER, and an inline dimension is never keyed by its host's row key.\n\n"
     "`role` + `key_position` are TWO FIELDS, not one token. The position is a number, so it compares "
     "and a gate can check that a relation's positions are exactly 1..n; `primary_key_2` would put "
     "string surgery in every consumer that wants the order. The rendered page composes them as `PK2` "
     "for reading — CONFORMANCE.md §2.4."),
)

#: (page, title, path, {key -> vocabulary block}, prose) — the shape `render` reads. The governs map
#: is DERIVED, per page, from the parity table.
SLOTS = tuple((page, title, path, parity.governs_under(path), prose)
              for page, title, path, prose in PAGES)


def dig(doc, path):
    return parity.dig(doc, path)


def terms_of(vocab: dict, block: str) -> list:
    return parity.terms_of(vocab, block)


def _cell(s: str, width: int = 92) -> str:
    """One table cell: collapse whitespace, escape the pipe, and keep it readable."""
    s = " ".join(str(s or "").split()).replace("|", "\\|")
    return (s[: width - 1] + "…") if len(s) > width else s


def render(slot, schema: dict, vocab: dict) -> str:
    page, title, path, governs, prose = slot
    obj = dig(schema, path)
    props = obj.get("properties") or {}
    required = set(obj.get("required") or [])
    closed = obj.get("additionalProperties") is False

    L = [f"# {title}", ""]
    L.append("> GENERATED by `tools/gen_slot_reference.py` from `mac.schema.json` and "
             "`mac_vocabulary.yaml`. Do not edit: a hand-written synopsis can describe a grammar that "
             "does not exist, which is exactly what this file replaces.")
    L += ["", textwrap.fill(prose, 98), "", "## SYNOPSIS", "", "```yaml"]
    # THE TWO PLANES SHAPE THE SAME IDEA DIFFERENTLY and the skeleton must say which: the concept plane
    # keys columns BY NAME (a map), the data plane is an ordered LIST with `name` as a field. A page that
    # rendered both the same way would teach a reader to write one as the other.
    is_list = page.startswith("relation")
    L.append("columns:")
    if not is_list:
        L.append("  <column-name>:")

    def _val(k, v, block):
        if block:
            ts = terms_of(vocab, block)
            return " | ".join(ts) if ts else f"<mac.{block}.*>"
        if v.get("enum"):
            return " | ".join(str(x) for x in v["enum"])
        return f"<{v.get('type') or 'any'}>"

    def _emit(props, required, indent, governs):
        """EXPAND ONE LEVEL OF NESTING. Collapsing a nested block to `{ … }` hides exactly what a reader
        came for — the first version of this page rendered `rulings: { … }`, which is less informative
        than the hand-written synopsis it replaced."""
        for k in sorted(props):
            v = props[k] or {}
            sub = v.get("properties")
            if (v.get("type") == "object") and isinstance(sub, dict) and sub:
                L.append(f"{indent}{k}:")
                _emit(sub, set(v.get("required") or []), indent + "  ",
                      {kk: governs.get(f"{k}.{kk}") for kk in sub})
                dep = v.get("dependentRequired") or {}
                for trig, needs in dep.items():
                    L.append(f"{indent}  # `{trig}` REQUIRES {', '.join('`' + n + '`' for n in needs)}")
                continue
            L.append(f"{indent}{k + ':':14}{_val(k, v, governs.get(k))}"
                     + ("      # REQUIRED" if k in required else ""))

    _emit(props, required, "    ", governs)
    if is_list:
        # A LIST ITEM'S FIRST FIELD CARRIES THE DASH. Marking it after the fact keeps _emit free of the
        # two planes' shapes — it renders fields, not YAML dialects.
        for i, ln in enumerate(L):
            if ln.startswith("    ") and not ln.lstrip().startswith("#"):
                L[i] = "  - " + ln[4:]
                break
    L += ["```", ""]
    L.append(f"**{len(props)} key(s)**, and the map is "
             + ("**CLOSED** — any other key is a conformance error (MAC012)." if closed
                else "open: other keys are admitted."))
    L += ["", "## PARAMETERS", "",
          "| key | type | required | choices | comment |",
          "|---|---|---|---|---|"]
    for k in sorted(props):
        v = props[k] or {}
        block = governs.get(k)
        ts = terms_of(vocab, block) if block else (v.get("enum") or [])
        ch = ("<br>".join(f"`{t}`" for t in ts) if ts else "—")
        if block:
            ch += f"<br>*from* `mac.{block}`"
        ty = v.get("type") or ("enum" if v.get("enum") else "any")
        if isinstance(ty, list):
            ty = " \\| ".join(ty)
        L.append(f"| `{k}` | {ty} | {'**yes**' if k in required else 'no'} | {ch} | "
                 f"{_cell(v.get('description'))} |")
    L += ["", "## TERM MEANINGS", ""]
    for k in sorted(governs):
        block = governs[k]
        body = vocab.get(block) or {}
        t = body.get("terms") if body.get("terms") is not None else body.get("members")
        L.append(f"### `{k}` — `mac.{block}`"
                 + ("  ·  CLOSED" if body.get("closed") else "  ·  open"))
        L.append("")
        L.append(f"> {_cell(body.get('description'), 400)}")
        L.append("")
        if isinstance(t, dict):
            for term, meaning in t.items():
                L.append(f"- **`{term}`** — {_cell(meaning, 320)}")
        L.append("")
    return "\n".join(L).rstrip() + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="fail if any page is stale; write nothing")
    ap.add_argument("--stdout", action="store_true", help="print instead of writing")
    a = ap.parse_args(argv)
    try:
        import yaml
    except ImportError as exc:
        print(f"COULD NOT RUN: {exc}")
        return 2
    schema = json.loads((ROOT / "mac.schema.json").read_text(encoding="utf-8"))
    vocab = yaml.safe_load((ROOT / "mac_vocabulary.yaml").read_text(encoding="utf-8")) or {}
    stale, wrote = [], []
    for slot in SLOTS:
        text = render(slot, schema, vocab)
        if a.stdout:
            print(text)
            continue
        out = ROOT / "reference_manual" / f"{slot[0]}.generated.md"
        cur = out.read_text(encoding="utf-8") if out.is_file() else None
        if a.check:
            if cur != text:
                stale.append(out.name)
            continue
        out.write_text(text, encoding="utf-8")
        wrote.append(out.name)
    if a.stdout:
        return 0
    if a.check:
        if stale:
            print(f"FAIL: gen_slot_reference — {len(stale)} page(s) stale: {', '.join(stale)}; "
                  f"re-run tools/gen_slot_reference.py")
            return 1
        print(f"PASS: gen_slot_reference — {len(SLOTS)} page(s) current")
        return 0
    print(f"PASS: gen_slot_reference — wrote {len(wrote)} page(s): {', '.join(wrote)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
