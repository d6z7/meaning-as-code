#!/usr/bin/env python3
"""gen_slot_reference.py — the PER-SLOT reference, generated from the schema and the vocabulary.

WHY, IN ONE SENTENCE: a hand-written synopsis can document a grammar that does not exist, and ours did.

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

THE FALSE STATEMENT THIS FILE PRINTED, MEASURED 2026-10-04. `--check` said `PASS: gen_slot_reference —
2 page(s) current` while `column_map.generated.md` leaked FIVE raw Python dict reprs into its TERM
MEANINGS section:

    - **`key`** — {'query_use': ['identity'], 'definition': 'IDENTITY OR JOIN COLUMN. A name resolve…

CAUSE: a vocabulary term is written in two shapes — a bare sentence (`concept.column.identity`) or a
RECORD of fields (`concept.column.role`, each member carrying `query_use` + `definition`) — and the
TERM MEANINGS loop `str()`d the value either way. The three `identity` terms three lines above rendered
correctly, so the bug sat beside its own fix. It now reads `definition` (then `doc`, `description`) and
renders the record's remaining fields as what they are, the way `gen_vocabulary_terms.render` already did.

AND `--check` COULD NOT HAVE SEEN IT, because the comparator and the renderer were the same code: it
re-rendered and byte-compared, so a renderer that mangles a value writes a page that is mangled
identically. Agreement by construction is not evidence. `--check` now asks a SECOND question of the
SOURCE — every term the vocabulary declares for a governed slot, and the opening words of its meaning,
must appear under that slot's heading; every key the schema admits must appear in the table; and no
Python container repr may appear anywhere on a page. Five reject classes, five mutants, and
`--self-test` asserts that each mutant CHANGED the page: in `gen_key_reference.py` a mutant that
deleted a table row silently stopped deleting anything when the emitter stopped emitting tables, and
the self-test reported 6/6 over a reject it was no longer exercising.

    python3 tools/gen_slot_reference.py              # write the pages
    python3 tools/gen_slot_reference.py --check      # exit 1 if stale, incomplete or mangled
    python3 tools/gen_slot_reference.py --self-test  # one mutant per reject class + a clean fixture
"""

from __future__ import annotations

import argparse
import json
import pathlib

import mac_vocab  # noqa: E402  — ONE reader of mac_vocabulary.yaml, fold-agnostic
import re
import sys
import tempfile
import textwrap

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS = ROOT / "reference_manual"
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

#: A PYTHON CONTAINER REPR, which is never a thing a reference manual means to print. `{'k': …` and
#: `[{'k': …` are what `str()` on a dict or a list of dicts produces; `OrderedDict(` and `None`-as-a-
#: whole-cell are the other two shapes this estate has leaked. Measured 2026-10-04: five of them on
#: column_map.generated.md, every one a vocabulary member rendered with `str()` instead of `.definition`.
REPR_RE = re.compile(r"\{'[^']*':|\[\{'|OrderedDict\(|\bdict_keys\(|\bdict_values\(")


def dig(doc, path):
    return parity.dig(doc, path)


def terms_of(vocab: dict, block: str) -> list:
    return parity.terms_of(vocab, block)


def _cell(s: str, width: int = 92) -> str:
    """One table cell: collapse whitespace, escape the pipe, and keep it readable."""
    s = " ".join(str(s or "").split()).replace("|", "\\|")
    return (s[: width - 1] + "…") if len(s) > width else s


#: THE FIELDS THAT HOLD A MEMBER'S PROSE, in the order gen_vocabulary_terms.py already reads them.
#: One home for "where a term's meaning lives".
PROSE_FIELDS = ("definition", "doc", "description")


def members_of(vocab: dict, block: str) -> list[tuple[str, str, dict]]:
    """[(term, its meaning in prose, its remaining fields)] for one vocabulary block.

    A TERM IS WRITTEN IN TWO SHAPES AND BOTH MUST READ THE SAME WAY. `concept.column.identity`
    writes `canonical: <a sentence>`; `concept.column.role` writes `key: {query_use: […],
    definition: <a sentence>}` — a RECORD, because a role's query_use is data the planner reads.
    The TERM MEANINGS loop used to `str()` the value whichever shape it was, which printed
    `{'query_use': ['identity'], 'definition': 'IDENTITY OR JOIN COLUMN…` into the manual five times.
    The record's own fields are not noise either: `query_use` is WHERE a query may use the column,
    which is most of what the term means, so it is rendered rather than dropped.
    """
    body = vocab.get(block) or {}
    t = body.get("terms") if body.get("terms") is not None else body.get("members")
    rows: list[tuple[str, str, dict]] = []
    if isinstance(t, dict):
        pairs = list(t.items())
    elif isinstance(t, list):
        # The older row shape: a list of {term: …, definition: …} records.
        pairs = [((x.get("term") if isinstance(x, dict) else x), x) for x in t]
    else:
        pairs = []
    for name, val in pairs:
        if not name:
            continue
        if isinstance(val, dict):
            prose = next((val[k] for k in PROSE_FIELDS if val.get(k)), "")
            rest = {k: v for k, v in val.items()
                    if k not in PROSE_FIELDS and k != "term" and v is not None}
        else:
            prose, rest = val, {}
        rows.append((str(name), str(prose or ""), rest))
    return rows


def _flat(v) -> str:
    """A structured field as text. AN EMPTY CONTAINER IS A FACT, NOT A BLANK: `housekeeping` declares
    `query_use: []`, which means a query may use it NOWHERE — printing nothing there would read as a
    field the vocabulary forgot to fill."""
    if isinstance(v, dict):
        return " · ".join(f"{k}: {_flat(x)}" for k, x in v.items()) if v else "none"
    if isinstance(v, (list, tuple)):
        return ", ".join(_flat(x) for x in v) if v else "none"
    return str(v)


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
        L.append(f"### `{k}` — `mac.{block}`"
                 + ("  ·  CLOSED" if body.get("closed") else "  ·  open"))
        L.append("")
        L.append(f"> {_cell(body.get('description'), 400)}")
        L.append("")
        for term, meaning, rest in members_of(vocab, block):
            extra = ("  ·  " + "  ·  ".join(f"*{f}:* {_cell(_flat(x), 80)}" for f, x in rest.items())
                     if rest else "")
            L.append(f"- **`{term}`** — {_cell(meaning, 320)}{extra}")
        L.append("")
    return "\n".join(L).rstrip() + "\n"


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# THE INDEPENDENT ASSERTIONS — read the source, grep the page; never re-render
# ──────────────────────────────────────────────────────────────────────────────────────────────────

def page_path(docs: pathlib.Path, page: str) -> pathlib.Path:
    return docs / f"{page}.generated.md"


def term_sections(text: str) -> dict[str, str]:
    """{the `### `key` — `mac.block`` subsection's KEY -> its text}, read off the page on disk."""
    out: dict[str, str] = {}
    cur, buf = None, []
    for ln in text.splitlines():
        m = re.match(r"^### `([^`]+)`", ln)
        if m:
            if cur:
                out[cur] = "\n".join(buf)
            cur, buf = m.group(1), []
        elif cur is not None:
            buf.append(ln)
    if cur:
        out[cur] = "\n".join(buf)
    return out


def _opening(meaning: str, words: int = 6) -> str:
    return " ".join(" ".join(str(meaning or "").split()).split()[:words])


def check(schema: dict, vocab: dict, docs: pathlib.Path) -> list[str]:
    """Five reject classes. Only the first re-renders; the rest read the SOURCE and grep the PAGE."""
    rejects: list[str] = []
    for slot in SLOTS:
        page, _title, path, governs, _prose = slot
        out = page_path(docs, page)
        if not out.is_file():
            rejects.append(f"[missing-page] {out.name} — the slot has a declaration and no page; "
                           f"run `python3 tools/gen_slot_reference.py`")
            continue
        cur = out.read_text(encoding="utf-8")

        # QUESTION ONE — did the page drift from the declarations?
        if cur != render(slot, schema, vocab):
            rejects.append(f"[stale-page] {out.name} — the declarations moved and the page did not; "
                           f"run `python3 tools/gen_slot_reference.py`")

        # QUESTION TWO — is what is ON THE PAGE what the source says? Nothing below re-renders.
        for m in REPR_RE.finditer(cur):
            line = cur[:m.start()].count("\n") + 1
            rejects.append(f"[python-repr] {out.name}:{line} — a Python container repr is in the "
                           f"manual ({cur[m.start():m.start() + 28]!r}); a renderer str()'d a "
                           f"structured value instead of reading its field")
            break                                    # one per page is the finding; the count is noise

        obj = dig(schema, path)
        for k in sorted(obj.get("properties") or {}):
            if f"`{k}`" not in cur:
                rejects.append(f"[uncovered-key] {out.name} — the schema admits `{k}` at this slot "
                               f"and the page never names it")

        sections = term_sections(cur)
        for k in sorted(governs):
            block = governs[k]
            sec = sections.get(k)
            if sec is None:
                rejects.append(f"[uncovered-term] {out.name} — `{k}` is governed by `mac.{block}` "
                               f"and the page has no `### `{k}`` section")
                continue
            for term, meaning, _rest in members_of(vocab, block):
                if f"`{term}`" not in sec:
                    rejects.append(f"[uncovered-term] {out.name} — `mac.{block}` declares the term "
                                   f"`{term}` and the `{k}` section does not list it")
                elif meaning and _opening(meaning) not in " ".join(sec.split()):
                    rejects.append(f"[uncovered-term] {out.name} — `mac.{block}.{term}` is listed "
                                   f"but its meaning is not: the vocabulary opens "
                                   f"{_opening(meaning)!r} and the page does not say it")
    return rejects


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# self-test — one mutant per reject class, plus a clean fixture that must pass
# ──────────────────────────────────────────────────────────────────────────────────────────────────

def self_test(schema: dict, vocab: dict) -> int:
    checks = 0
    failures: list[str] = []

    def expect(cond, msg):
        nonlocal checks
        checks += 1
        if not cond:
            failures.append(msg)

    with tempfile.TemporaryDirectory() as tmp:
        docs = pathlib.Path(tmp)
        for slot in SLOTS:
            page_path(docs, slot[0]).write_text(render(slot, schema, vocab), encoding="utf-8")
        target = page_path(docs, "column_map")
        clean = target.read_text(encoding="utf-8")

        expect(check(schema, vocab, docs) == [], "freshly written pages must be clean")

        def mutate(new_text: str, cls: str, why: str):
            """Seed one mutant, assert it REJECTS — and assert it CHANGED THE PAGE.

            THE SECOND ASSERTION IS NOT CEREMONY. gen_key_reference.py's `uncovered-key` mutant
            deleted a TABLE ROW; when the emitter stopped emitting tables the mutant deleted
            nothing, every check stayed clean, and the self-test still reported 6/6 — green over a
            reject class it was no longer testing.
            """
            expect(new_text != clean, f"the {cls} mutant must actually change the page ({why})")
            target.write_text(new_text, encoding="utf-8")
            rs = check(schema, vocab, docs)
            expect(any(r.startswith(f"[{cls}]") for r in rs),
                   f"{why} must reject as {cls} (got: {[r.split(']')[0] + ']' for r in rs] or 'clean'})")
            target.write_text(clean, encoding="utf-8")

        # stale-page — a hand edit
        mutate(clean.replace("## PARAMETERS", "## PARAMETERS (edited)", 1),
               "stale-page", "a hand-edited page")

        # python-repr — THE measured defect: a vocabulary record str()'d into the manual.
        mutate(re.sub(r"^- \*\*`key`\*\* — .*$",
                      "- **`key`** — {'query_use': ['identity'], 'definition': 'IDENTITY OR JOIN "
                      "COLUMN. A name resolves TO it'}", clean, count=1, flags=re.M),
               "python-repr", "a Python dict repr rendered into the manual")

        # uncovered-term — the renderer dropping a term the vocabulary closes
        drop_term = re.compile(r"^- \*\*`housekeeping`\*\*")
        mutate("\n".join(ln for ln in clean.splitlines() if not drop_term.match(ln)) + "\n",
               "uncovered-term", "a term the vocabulary closes and the page omits")

        # uncovered-key — the renderer dropping a key the schema admits at this slot
        mutate("\n".join(ln for ln in clean.splitlines() if "`axis_kind`" not in ln) + "\n",
               "uncovered-key", "a key the schema admits and the page omits")

        # missing-page — a declared slot with no page at all
        keep = target.read_text(encoding="utf-8")
        target.unlink()
        rs = check(schema, vocab, docs)
        expect(any(r.startswith("[missing-page]") for r in rs),
               f"a deleted page must reject as missing-page (got: "
               f"{[r.split(']')[0] + ']' for r in rs] or 'clean'})")
        target.write_text(keep, encoding="utf-8")

        expect(check(schema, vocab, docs) == [], "restoring every mutant must return to clean")

    if failures:
        for f in failures:
            print(f"  [SELF-TEST] {f}")
        print(f"FAIL: gen_slot_reference self-test — {len(failures)} of {checks} check(s) failed "
              f"over 5 reject class(es)")
        return 1
    print(f"PASS: gen_slot_reference self-test — {checks}/{checks} check(s) over 5 reject class(es)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any page is stale, incomplete or mangled; write nothing")
    ap.add_argument("--self-test", action="store_true",
                    help="one mutant per reject class, plus a clean fixture that must pass")
    ap.add_argument("--stdout", action="store_true", help="print instead of writing")
    a = ap.parse_args(argv)
    try:
        import yaml
    except ImportError as exc:
        print(f"COULD NOT RUN: pyyaml is not importable ({exc})", file=sys.stderr)
        return 2
    for p in (ROOT / "mac.schema.json", ROOT / "mac_vocabulary.yaml"):
        if not p.is_file():
            print(f"COULD NOT RUN: no {p.name} at {p}", file=sys.stderr)
            return 2
    schema = json.loads((ROOT / "mac.schema.json").read_text(encoding="utf-8"))
    #: FOLD-AGNOSTIC. `mac_vocab.flatten` returns vocabularies keyed by their DOTTED name whether
    #: the file nests them (`concept: column: role:`) or spells them flat (`concept.column.role:`),
    #: so every lookup below keeps working and the file's shape stays an authoring choice. Measured
    #: 2026-10-04: folding the file broke exactly 3 gates of 14, all of them here at a dotted-key
    #: dict index — 35 modules parse this file with their own `yaml.safe_load` and none had a reader.
    vocab = mac_vocab.flatten(yaml.safe_load((ROOT / "mac_vocabulary.yaml").read_text(encoding="utf-8")) or {})

    if a.self_test:
        return self_test(schema, vocab)

    terms = sum(len(members_of(vocab, b)) for _p, _t, _pa, g, _pr in SLOTS for b in g.values())
    keys = sum(len(dig(schema, path).get("properties") or {}) for _p, _t, path, _g, _pr in SLOTS)

    if a.stdout:
        for slot in SLOTS:
            print(render(slot, schema, vocab))
        return 0

    if a.check:
        rejects = check(schema, vocab, DOCS)
        if rejects:
            for r in rejects[:40]:
                print(f"  {r}")
            if len(rejects) > 40:
                print(f"  … and {len(rejects) - 40} more")
            print(f"FAIL: gen_slot_reference — {len(rejects)} reject(s) over {len(SLOTS)} page(s), "
                  f"{keys} admitted key(s) and {terms} declared term(s); "
                  f"run `python3 tools/gen_slot_reference.py`")
            return 1
        print(f"PASS: gen_slot_reference — {len(SLOTS)} page(s) current against mac.schema.json and "
              f"mac_vocabulary.yaml: every one of {keys} admitted key(s) and {terms} declared term(s) "
              f"present, no container repr on any page")
        return 0

    wrote = []
    for slot in SLOTS:
        out = page_path(DOCS, slot[0])
        out.write_text(render(slot, schema, vocab), encoding="utf-8")
        wrote.append(out.name)
    print(f"PASS: gen_slot_reference — wrote {len(wrote)} page(s) ({', '.join(wrote)}): "
          f"{keys} admitted key(s), {terms} declared term(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
