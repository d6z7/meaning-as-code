"""sdk.acceptance.sme_authority — read a reviewer spreadsheet and resolve it against the corpus.

WHAT THIS MODULE IS FOR

    TRUTH is the only acceptance category whose oracle must come from OUTSIDE the system, and it
    is the one category with no instrument. A reviewer workbook is the estate's only channel that
    already carries named human rulings. This module is the missing reader: it turns one sheet into
    a ``question_id -> {expected_value, authority, ruled_by, ruled_on}`` mapping and PRINTS ITS
    DENOMINATOR, so the mapping can be reviewed before anything is stamped onto an oracle.

    It writes a reviewable artefact. It NEVER writes an oracle. Stamping ``authority: sme`` is a
    claim about what a named human ruled; if the link were wrong it would launder a guess into the
    one channel that is supposed to be independent. So the linkage is produced, printed and handed
    to an operator, and applying it is a separate, accepted act.

TWO LINKAGES, AND ONLY ONE OF THEM IS SOUND

    Linking a ROW to a QUESTION is exact. The sheet carries an ``ID`` column holding the corpus id
    verbatim (``<CORPUS>_C<n>.<m>``), and the corpus stores one oracle per id. So the join is a set
    membership test on a literal, with nothing inferred. This is NOT the situation the anchors
    plane is in: ``anchors.py`` must scan English parentheticals because the anchors carry no
    ``question_id:`` key. Here the key exists. Nothing in this module fuzzy-matches, and there is
    no edit-distance, prefix, substring or title-similarity path anywhere in it.

    Linking an ANSWER to a VALUE is NOT sound, and the module refuses it in most rows. The answer
    column is free prose written by six people in two decimal conventions — ``5.072`` (dot as a
    thousands separator, so five thousand) sits a few rows from ``1,255,377`` (comma as a thousands
    separator) and from ``21.2%`` (dot as a decimal point). A reader that picked one convention
    would silently mis-scale answers by 1000x on the estate's only independent channel. So
    ``expected_value`` is set ONLY when a single numeric token is present AND its convention is
    forced by its own shape; every other row is classified and left null with its candidates shown.

    That asymmetry is the finding, not a defect of this reader: the question key is real, the
    value key is not, and the value has to be authored per row by a human reading the prose.

THE FOUR REJECT CLASSES (every row lands in exactly one bucket, nothing is dropped)

    linked      the ID cell holds a literal that IS a member of the corpus id set.
    unlinked    empty ID cell with other content, an ID cell that is not id-shaped (the live sheet
                ends with a ``Total questions: 68`` footer, which lands here rather than being
                quietly skipped), or an id-shaped literal that is NOT in the corpus.
    ambiguous   the same id appears on more than one row. EVERY such row is ambiguous and NONE is
                linked — picking one would be a guess about which reviewer's ruling stands.
    blank       no content in the id, answer or reviewer cell. Counted and reported separately,
                because a trailing empty row is not a linkage failure and must not inflate the
                numerator or the denominator.

    linked + unlinked + ambiguous + blank == rows scanned. The CLI prints all four.

REVIEWER NAMES ARE PSEUDONYMISED BY DEFAULT

    The sheet's reviewer column holds personal names. The emitted artefact carries stable
    pseudonymous ids (``sme:R1`` ...) assigned by first appearance, and the roster is reported as a
    COUNT. ``--reveal-reviewers`` opts in to real names for a local, uncommitted review. The
    default exists so a generated mapping can be read, diffed and discussed without carrying
    personal data into a repository.

``ruled_on`` IS A WORKBOOK DATE, NOT A ROW DATE

    The sheet has no per-row date column, so no row can carry its own ruling date. The only date
    the artefact can honestly carry is the workbook's own ``dcterms:modified``, and it is emitted
    with ``ruled_on_precision: workbook`` next to it so nobody reads it as a per-ruling timestamp.
    Authoring a real per-row date means asking the reviewers, not improving this parser.

NO THIRD-PARTY DEPENDENCY

    An ``.xlsx`` is an OOXML zip. This module reads it with ``zipfile`` + ``xml.etree`` from the
    standard library, so it runs in a pristine clone with nothing installed. (The numbers it
    produces on the live sheet were cross-checked against an independent ``openpyxl`` read.)

CLI

    python -m sdk.acceptance.sme_authority --xlsx <file> --oracle-dir <dir> [--out map.yaml]
    python -m sdk.acceptance.sme_authority --self-test

    ``--self-test`` builds a synthetic workbook seeding ONE row per reject class and asserts each
    is rejected, so a clean run is evidence the refusals can actually fire rather than evidence
    that nothing was examined.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------------------
# OOXML reading (stdlib only)
# ---------------------------------------------------------------------------

_NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_NS_REL_DOC = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_NS_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_NS_DCTERMS = "{http://purl.org/dc/terms/}"
_NS_DC = "{http://purl.org/dc/elements/1.1/}"

_CELL_REF = re.compile(r"^([A-Z]+)([0-9]+)$")


def _col_to_index(letters: str) -> int:
    """``A`` -> 1, ``Z`` -> 26, ``AA`` -> 27."""
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


def _index_to_col(index: int) -> str:
    """1 -> ``A``. Inverse of :func:`_col_to_index`, for printing cell evidence."""
    out = ""
    while index > 0:
        index, rem = divmod(index - 1, 26)
        out = chr(65 + rem) + out
    return out


def _si_text(si: ET.Element) -> str:
    """Flatten one shared-string item. Rich text splits a run per format; join every ``<t>``."""
    return "".join(t.text or "" for t in si.iter(f"{_NS_MAIN}t"))


def read_workbook(path: Path) -> dict:
    """Read an ``.xlsx`` into ``{"sheets", "sheet_rows", "props", "sheet_order"}``.

    ``sheets[name]`` maps ``(row, col) -> value``; ``sheet_rows[name]`` lists every row number the
    sheet DECLARES, including rows whose every cell is empty. A declared-but-empty row is invisible
    in the cell map, and the denominator must still count it -- otherwise the tool's "rows scanned"
    would silently differ from what a person sees in the spreadsheet.

    Values are ``str`` for text cells and ``float``/``int`` for numeric cells. Formula results are
    read from the cached ``<v>``; a formula with no cached value reads as ``None`` (absent), which
    is the honest answer — this reader does not evaluate formulas and must not pretend to.
    """
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())

        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            shared = [_si_text(si) for si in root.findall(f"{_NS_MAIN}si")]

        rels: dict[str, str] = {}
        if "xl/_rels/workbook.xml.rels" in names:
            root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
            for rel in root.findall(f"{_NS_PKG_REL}Relationship"):
                target = rel.get("Target", "")
                target = target[1:] if target.startswith("/") else f"xl/{target.lstrip('/')}"
                rels[rel.get("Id", "")] = target.replace("xl/xl/", "xl/")

        order: list[tuple[str, str]] = []
        root = ET.fromstring(zf.read("xl/workbook.xml"))
        for sheet in root.iter(f"{_NS_MAIN}sheet"):
            rid = sheet.get(f"{_NS_REL_DOC}id", "")
            order.append((sheet.get("name", ""), rels.get(rid, "")))

        sheets: dict[str, dict[tuple[int, int], object]] = {}
        sheet_rows: dict[str, list[int]] = {}
        for name, target in order:
            if target not in names:
                continue
            cells: dict[tuple[int, int], object] = {}
            root = ET.fromstring(zf.read(target))
            declared = set()
            for row in root.iter(f"{_NS_MAIN}row"):
                try:
                    declared.add(int(row.get("r") or 0))
                except ValueError:
                    pass
            sheet_rows[name] = sorted(r for r in declared if r > 0)
            for c in root.iter(f"{_NS_MAIN}c"):
                m = _CELL_REF.match(c.get("r") or "")
                if not m:
                    continue
                key = (int(m.group(2)), _col_to_index(m.group(1)))
                ctype = c.get("t") or "n"
                if ctype == "inlineStr":
                    node = c.find(f"{_NS_MAIN}is")
                    value: object | None = _si_text(node) if node is not None else None
                elif ctype == "s":
                    v = c.find(f"{_NS_MAIN}v")
                    idx = int(v.text) if v is not None and v.text else -1
                    value = shared[idx] if 0 <= idx < len(shared) else None
                else:
                    v = c.find(f"{_NS_MAIN}v")
                    raw = v.text if v is not None else None
                    if raw is None:
                        value = None
                    elif ctype in ("str", "e"):
                        value = raw
                    else:
                        try:
                            f = float(raw)
                            value = int(f) if f.is_integer() else f
                        except ValueError:
                            value = raw
                if value is not None and value != "":
                    cells[key] = value
            sheets[name] = cells

        props: dict[str, str] = {}
        if "docProps/core.xml" in names:
            root = ET.fromstring(zf.read("docProps/core.xml"))
            for tag, key in (
                (f"{_NS_DCTERMS}modified", "modified"),
                (f"{_NS_DCTERMS}created", "created"),
                (f"{_NS_DC}creator", "creator"),
            ):
                node = root.find(tag)
                if node is not None and node.text:
                    props[key] = node.text

    return {
        "sheets": sheets,
        "sheet_rows": sheet_rows,
        "props": props,
        "sheet_order": [n for n, _ in order],
    }


# ---------------------------------------------------------------------------
# Value classification — conservative by construction
# ---------------------------------------------------------------------------

# A run of digits that may carry grouping separators and/or a fractional tail. Anchored on a digit
# boundary so tokens embedded in identifiers (``ID.3``, ``EU27+4``, ``MQB 37``) are still SEEN --
# being seen is what pushes a prose row to `numeric_multiple` and therefore to a REFUSAL. Missing
# them would be the dangerous direction: it could leave one incidental number looking like the
# answer.
_NUM = re.compile(r"(?<![0-9A-Za-z.,])([0-9]+(?:[.,][0-9]+)*)(?![0-9])")

# Closed set. Exact match after whitespace/case normalisation only -- never a substring test.
_REFUSAL_FORMS = frozenset({"unable to answer", "not answerable", "n/a", "none"})


def classify_value(text: str) -> dict:
    """Classify one answer cell. Returns ``value_status`` and, only when forced, ``expected_value``.

    ``value_status``:

    ``resolved``              exactly one numeric token and its convention is forced by its shape.
    ``ambiguous_convention``  one token whose single ``.``/``,`` separator precedes exactly three
                              digits -- ``5.072`` is 5072 under a German convention and 5.072 under
                              an English one, and the cell alone cannot say which. REFUSED.
    ``multiple_candidates``   more than one numeric token; which one is "the" answer is a reading,
                              not a parse. REFUSED.
    ``refusal``               the reviewer declined; there is no value to expect.
    ``none``                  prose with no numeric token.
    """
    norm = " ".join(str(text).split())
    if norm.lower().strip(" .\"'") in _REFUSAL_FORMS:
        return {"value_status": "refusal", "expected_value": None, "value_candidates": []}

    tokens = _NUM.findall(norm)
    if not tokens:
        return {"value_status": "none", "expected_value": None, "value_candidates": []}
    if len(tokens) > 1:
        return {
            "value_status": "multiple_candidates",
            "expected_value": None,
            "value_candidates": tokens,
        }

    token = tokens[0]
    reading = _read_number(token)
    if reading is None:
        return {
            "value_status": "ambiguous_convention",
            "expected_value": None,
            "value_candidates": [token],
            "readings": _both_readings(token),
        }
    out = {"value_status": "resolved", "expected_value": reading, "value_candidates": [token]}
    if "%" in norm:
        out["unit"] = "percent"
    return out


def _read_number(token: str) -> float | int | None:
    """Return the ONE forced reading of ``token``, or ``None`` when its convention is ambiguous.

    Forced: no separator at all (``3750``); two or more separators of one kind, which can only be
    grouping (``1.567.250``); a single separator followed by anything other than exactly three
    digits, which can only be a decimal point (``21.2``, ``4.6``).

    Not forced: a single separator followed by exactly three digits (``5.072``, ``1,355``). Both a
    grouped integer and a three-decimal fraction produce that shape.
    """
    seps = [ch for ch in token if ch in ".,"]
    if not seps:
        return int(token)
    if len(set(seps)) > 1:
        # Mixed separators: the last one is the decimal point, the rest group. ``1.234,56``/
        # ``1,234.56`` are both unambiguous once both kinds are present.
        dec = seps[-1]
        grp = "," if dec == "." else "."
        return float(token.replace(grp, "").replace(dec, "."))
    if len(seps) > 1:
        return int(token.replace(seps[0], ""))
    tail = token.split(seps[0])[1]
    if len(tail) == 3:
        return None
    return float(token.replace(seps[0], "."))


def _both_readings(token: str) -> dict:
    """The two candidate readings of an ambiguous token, shown so a human can pick."""
    sep = next(ch for ch in token if ch in ".,")
    return {
        "as_grouped_integer": int(token.replace(sep, "")),
        "as_decimal_fraction": float(token.replace(sep, ".")),
    }


# ---------------------------------------------------------------------------
# Linkage
# ---------------------------------------------------------------------------

# The shape a corpus id has in this estate. Used ONLY to tell "this cell was meant to be an id and
# is not in the corpus" apart from "this cell is a footer/heading". It never relaxes membership:
# a literal must still be IN the corpus id set to link.
_ID_SHAPE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Za-z0-9.+]+)+$")

_HEADER_ID = "id"
_HEADER_ANSWER_HINTS = ("human answer",)


def _find_header(cells: dict, max_scan: int = 12) -> dict:
    """Locate the header row by CONTENT, not by a hardcoded row number.

    Requires a cell equal to ``ID`` and a cell containing ``human answer``; the workbook's banner
    row and any leading spacer rows are therefore skipped without being assumed away.
    """
    rows = sorted({r for r, _ in cells})[:max_scan]
    for r in rows:
        labels = {c: " ".join(str(v).split()).lower() for (rr, c), v in cells.items() if rr == r}
        id_col = next((c for c, t in labels.items() if t == _HEADER_ID), None)
        ans_col = next(
            (c for c, t in labels.items() if any(h in t for h in _HEADER_ANSWER_HINTS)), None
        )
        if id_col and ans_col:
            return {
                "header_row": r,
                "id_col": id_col,
                "answer_col": ans_col,
                "reviewer_col": min({c for _, c in cells} | {1}),
                "labels": labels,
            }
    raise ValueError(
        "no header row found: need a cell equal to 'ID' and a cell containing 'Human Answer' "
        f"within the first {max_scan} rows"
    )


def resolve(xlsx: Path, corpus_ids, sheet: str | None = None, reveal: bool = False) -> dict:
    """Resolve a reviewer workbook against the corpus id set.

    Returns ``{"counts", "linked", "unlinked", "ambiguous", "blank", "source", "reviewers"}``.
    ``linked`` maps ``question_id -> proposed stamp + evidence``. Nothing is written.
    """
    ids = {i for i in (corpus_ids or []) if isinstance(i, str) and i.strip()}
    if not ids:
        raise ValueError("corpus id set is empty — every row would be unlinked for the wrong reason")

    wb = read_workbook(xlsx)
    name = sheet or (wb["sheet_order"][0] if wb["sheet_order"] else "")
    if name not in wb["sheets"]:
        raise ValueError(f"sheet {name!r} not in workbook; sheets are {wb['sheet_order']}")
    cells = wb["sheets"][name]
    hdr = _find_header(cells)

    modified = (wb["props"].get("modified") or "")[:10] or None

    # Pass 1: bucket every row below the header.
    staged: list[dict] = []
    blank = 0
    declared = set(wb.get("sheet_rows", {}).get(name, []))
    data_rows = sorted({r for r in declared | {r for r, _ in cells} if r > hdr["header_row"]})
    for r in data_rows:
        id_raw = cells.get((r, hdr["id_col"]))
        ans_raw = cells.get((r, hdr["answer_col"]))
        rev_raw = cells.get((r, hdr["reviewer_col"]))
        id_text = " ".join(str(id_raw).split()) if id_raw is not None else ""
        ans_text = " ".join(str(ans_raw).split()) if ans_raw is not None else ""
        rev_text = " ".join(str(rev_raw).split()) if rev_raw is not None else ""

        if not (id_text or ans_text or rev_text):
            blank += 1
            continue

        evidence = {
            "sheet_row": r,
            "id_cell": f"{_index_to_col(hdr['id_col'])}{r}",
            "id_cell_text": id_text,
            "answer_cell": f"{_index_to_col(hdr['answer_col'])}{r}",
        }
        if not id_text:
            staged.append({"reason": "empty_id_cell", "evidence": evidence})
        elif not _ID_SHAPE.match(id_text):
            staged.append({"reason": "not_id_shaped", "evidence": evidence})
        elif id_text not in ids:
            staged.append({"reason": "id_not_in_corpus", "evidence": evidence})
        elif not ans_text:
            staged.append({"reason": "no_human_answer", "evidence": evidence})
        else:
            staged.append(
                {"id": id_text, "answer": ans_text, "reviewer": rev_text, "evidence": evidence}
            )

    # Pass 2: a duplicated id makes EVERY row carrying it ambiguous. None of them links.
    seen: dict[str, int] = {}
    for row in staged:
        if "id" in row:
            seen[row["id"]] = seen.get(row["id"], 0) + 1
    dupes = {k for k, n in seen.items() if n > 1}

    # Reviewer pseudonyms, assigned by first appearance so the mapping is reproducible.
    pseudo: dict[str, str] = {}
    for row in staged:
        rev = row.get("reviewer")
        if rev and rev not in pseudo:
            pseudo[rev] = f"sme:R{len(pseudo) + 1}"

    linked: dict[str, dict] = {}
    unlinked: list[dict] = []
    ambiguous: list[dict] = []
    for row in staged:
        if "id" not in row:
            unlinked.append({"reason": row["reason"], **row["evidence"]})
            continue
        if row["id"] in dupes:
            ambiguous.append(
                {"reason": "duplicate_id", "question_id": row["id"], **row["evidence"]}
            )
            continue
        stamp = {
            "authority": "sme",
            "ruled_by": row["reviewer"] if reveal else pseudo.get(row["reviewer"], "sme:unnamed"),
            "ruled_on": modified,
            "ruled_on_precision": "workbook",
            "ruled_on_basis": "docProps/core.xml dcterms:modified",
            "answer_text": row["answer"],
            **classify_value(row["answer"]),
            "evidence": {**row["evidence"], "link_mode": "exact_id_cell", "corpus_member": True},
        }
        if "?" in row["answer"] and not stamp["value_candidates"]:
            # ADVISORY ONLY. Never affects linkage or value; flags rows where the reviewer appears
            # to have asked for clarification rather than ruled. Under-claims by design.
            stamp["advisory_asks_clarification"] = True
        linked[row["id"]] = stamp

    digest = hashlib.sha256(Path(xlsx).read_bytes()).hexdigest()
    return {
        "source": {
            "file": str(xlsx),
            "sha256": digest,
            "sheet": name,
            "header_row": hdr["header_row"],
            "workbook_modified": modified,
            "workbook_created": (wb["props"].get("created") or "")[:10] or None,
            "workbook_generator": wb["props"].get("creator"),
        },
        "reviewers": {
            "count": len(pseudo),
            "ids": sorted(pseudo.values(), key=lambda s: int(s.split("R")[1])),
            "names_revealed": bool(reveal),
        },
        "counts": {
            "rows_scanned": len(staged) + blank,
            "linked": len(linked),
            "unlinked": len(unlinked),
            "ambiguous": len(ambiguous),
            "blank": blank,
            "corpus_ids": len(ids),
            "corpus_ids_covered": len(linked),
            "corpus_ids_uncovered": len(ids) - len(linked),
        },
        "linked": linked,
        "unlinked": unlinked,
        "ambiguous": ambiguous,
    }


# ---------------------------------------------------------------------------
# Emit
# ---------------------------------------------------------------------------


def _yaml_dump(obj) -> str:
    try:
        import yaml
    except ImportError:  # pragma: no cover - yaml is present throughout this estate
        import json

        return json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, width=100)


_BANNER = (
    "# GENERATED by sdk.acceptance.sme_authority — a PROPOSAL, not an applied stamp.\n"
    "# Nothing here has been written to any oracle. `authority: sme` below is what WOULD be\n"
    "# claimed if an operator accepts this mapping. Review `expected_value` per row first:\n"
    "# `value_status: resolved` is the only row where a value was forced by the cell's own shape.\n"
    "# Reviewer names are pseudonymised unless --reveal-reviewers was passed.\n"
)


def report(result: dict, stream=sys.stdout, samples: int = 5) -> None:
    """Print the denominator, then the buckets. The counts line is the point of the tool."""
    c = result["counts"]
    s = result["source"]
    w = stream.write
    w(f"SME AUTHORITY CHANNEL — {s['file']}\n")
    w(f"  sheet                 {s['sheet']!r} (header row {s['header_row']})\n")
    w(f"  sha256                {s['sha256'][:16]}…\n")
    w(f"  workbook created      {s['workbook_created']} (generator: {s['workbook_generator']})\n")
    w(f"  workbook modified     {s['workbook_modified']}  <- the only date any row can carry\n")
    w(f"  reviewers             {result['reviewers']['count']}")
    w(" (names shown)\n" if result["reviewers"]["names_revealed"] else " (pseudonymised)\n")
    w("\n")
    w(f"  LINKED                {c['linked']}\n")
    w(f"  UNLINKED              {c['unlinked']}\n")
    w(f"  AMBIGUOUS             {c['ambiguous']}\n")
    w(f"  blank rows skipped    {c['blank']}\n")
    w(f"  ---- rows scanned     {c['rows_scanned']}")
    total = c["linked"] + c["unlinked"] + c["ambiguous"] + c["blank"]
    w(f"   (sums: {total == c['rows_scanned']})\n")
    w(f"  corpus ids            {c['corpus_ids']} — covered {c['corpus_ids_covered']}, ")
    w(f"uncovered {c['corpus_ids_uncovered']}\n")

    by_status: dict[str, int] = {}
    for stamp in result["linked"].values():
        by_status[stamp["value_status"]] = by_status.get(stamp["value_status"], 0) + 1
    w("\n  expected_value extractable from the answer prose:\n")
    for status in sorted(by_status, key=lambda k: -by_status[k]):
        mark = "VALUE" if status == "resolved" else "refused"
        w(f"    {status:22s} {by_status[status]:4d}   {mark}\n")
    resolved = by_status.get("resolved", 0)
    w(f"    -> {resolved} of {c['linked']} linked rows yield a machine-comparable value\n")

    if result["unlinked"]:
        w("\n  UNLINKED ROWS (every one, never dropped):\n")
        for row in result["unlinked"]:
            w(f"    row {row['sheet_row']:>3} {row['id_cell']:>5}  {row['reason']:18s} ")
            w(f"{row['id_cell_text'][:60]!r}\n")
    if result["ambiguous"]:
        w("\n  AMBIGUOUS ROWS (duplicate id — none linked):\n")
        for row in result["ambiguous"]:
            w(f"    row {row['sheet_row']:>3} {row['id_cell']:>5}  {row['question_id']}\n")

    if samples and result["linked"]:
        w(f"\n  SAMPLE of {samples} linked rows with linkage evidence:\n")
        for qid, stamp in list(result["linked"].items())[:samples]:
            ev = stamp["evidence"]
            w(f"    {qid}\n")
            w(f"      evidence      {ev['id_cell']} == {ev['id_cell_text']!r} ")
            w(f"(mode {ev['link_mode']}, in corpus: {ev['corpus_member']})\n")
            w(f"      ruled_by      {stamp['ruled_by']}   ruled_on {stamp['ruled_on']} ")
            w(f"({stamp['ruled_on_precision']})\n")
            w(f"      value_status  {stamp['value_status']}  ")
            w(f"expected_value={stamp['expected_value']!r}\n")
            w(f"      answer        {stamp['answer_text'][:96]!r}\n")


# ---------------------------------------------------------------------------
# Self-test — one seeded mutant per reject class
# ---------------------------------------------------------------------------


def _synth_xlsx(path: Path, rows: list[tuple[str, str, str]]) -> None:
    """Write a minimal but real OOXML workbook, so the self-test exercises the actual reader."""
    strings: list[str] = []

    def sref(text: str) -> int:
        if text not in strings:
            strings.append(text)
        return strings.index(text)

    body = []
    table = [("Reviewer", "ID", "Human Answer")] + rows
    for r, (a, b, c) in enumerate(table, start=1):
        cs = []
        for col, val in (("A", a), ("B", b), ("C", c)):
            if val != "":
                cs.append(f'<c r="{col}{r}" t="s"><v>{sref(val)}</v></c>')
        body.append(f'<row r="{r}">{"".join(cs)}</row>')

    def esc(t: str) -> str:
        return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    sst = "".join(f"<si><t>{esc(s)}</t></si>" for s in strings)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/'
            'content-types"><Default Extension="xml" ContentType="application/xml"/></Types>',
        )
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package'
            '/2006/relationships"><Relationship Id="rId1" Type="x" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        zf.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships"><sheets><sheet name="Review" sheetId="1" r:id="rId1"/></sheets>'
            "</workbook>",
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package'
            '/2006/relationships"><Relationship Id="rId1" Type="x" Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        zf.writestr(
            "xl/sharedStrings.xml",
            '<?xml version="1.0"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/'
            f'2006/main" count="{len(strings)}" uniqueCount="{len(strings)}">{sst}</sst>',
        )
        zf.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/'
            f'spreadsheetml/2006/main"><sheetData>{"".join(body)}</sheetData></worksheet>',
        )
        zf.writestr(
            "docProps/core.xml",
            '<?xml version="1.0"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/'
            'package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:dcterms="http://purl.org/dc/terms/"><dc:creator>selftest</dc:creator>'
            "<dcterms:modified>2026-01-02T03:04:05Z</dcterms:modified></cp:coreProperties>",
        )


def self_test(stream=sys.stdout) -> int:
    """Seed one row per reject class and assert each is rejected. Exit 0 only if all fire."""
    import tempfile

    w = stream.write
    failures: list[str] = []
    corpus = ["X_C1.1", "X_C1.2", "X_C1.3", "X_C2.1", "X_C2.2", "X_C2.3", "X_C2.4"]
    rows = [
        ("Ann", "X_C1.1", "3750"),  # accept: forced integer
        ("Ann", "X_C1.2", "21.2%"),  # accept: forced decimal
        ("Bob", "X_C1.3", "5.072"),  # accept but value REFUSED: ambiguous convention
        ("Bob", "X_C2.1", "unable to answer"),  # accept, refusal form
        ("Cyd", "X_C2.2", "1.567.250"),  # accept: two separators -> grouped
        ("Cyd", "X_NOPE.9", "1234"),  # reject: id_not_in_corpus
        ("Cyd", "Total questions: 6", ""),  # reject: not_id_shaped
        ("Dee", "", "orphan answer"),  # reject: empty_id_cell
        ("Dee", "X_C2.3", ""),  # reject: no_human_answer
        ("Eve", "X_C2.4", "first ruling"),  # reject: duplicate_id (both rows)
        ("Fay", "X_C2.4", "second ruling"),  # reject: duplicate_id (both rows)
        ("", "", ""),  # blank: counted, not a rejection
    ]

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "selftest.xlsx"
        _synth_xlsx(path, rows)
        res = resolve(path, corpus)

    def want(label: str, got, expect) -> None:
        ok = got == expect
        w(f"  {'ok  ' if ok else 'FAIL'} {label:44s} got {got!r} want {expect!r}\n")
        if not ok:
            failures.append(label)

    c = res["counts"]
    w("SELF-TEST — one seeded mutant per reject class\n")
    want("linked", c["linked"], 5)
    want("unlinked", c["unlinked"], 4)
    want("ambiguous (both duplicate rows)", c["ambiguous"], 2)
    want("blank", c["blank"], 1)
    want("buckets sum to rows scanned", c["linked"] + c["unlinked"] + c["ambiguous"] + c["blank"], c["rows_scanned"])
    reasons = sorted(r["reason"] for r in res["unlinked"])
    want(
        "each unlinked class fires exactly once",
        reasons,
        ["empty_id_cell", "id_not_in_corpus", "no_human_answer", "not_id_shaped"],
    )
    want("duplicate id is in NEITHER linked bucket", "X_C2.4" in res["linked"], False)
    want("reviewers pseudonymised", res["linked"]["X_C1.1"]["ruled_by"], "sme:R1")
    want("ruled_on is the workbook date", res["linked"]["X_C1.1"]["ruled_on"], "2026-01-02")
    want("forced integer resolves", res["linked"]["X_C1.1"]["expected_value"], 3750)
    want("forced decimal resolves", res["linked"]["X_C1.2"]["expected_value"], 21.2)
    want("dot+3-digits REFUSES", res["linked"]["X_C1.3"]["value_status"], "ambiguous_convention")
    want("...and carries no value", res["linked"]["X_C1.3"]["expected_value"], None)
    want("...and shows both readings", res["linked"]["X_C1.3"]["readings"]["as_grouped_integer"], 5072)
    want("two separators are grouping", res["linked"]["X_C2.2"]["expected_value"], 1567250)
    want("refusal form classified", res["linked"]["X_C2.1"]["value_status"], "refusal")
    want("multi-number prose REFUSES", classify_value("a 5.072 in 2024")["value_status"], "multiple_candidates")
    want("no-number prose yields none", classify_value("each country must be assigned")["value_status"], "none")
    want("empty corpus is refused", _raises(lambda: resolve(Path("x"), [])), True)

    w(f"\n{'PASS' if not failures else 'FAIL'}: sme_authority --self-test — ")
    w(f"{20 - len(failures)}/20 assertions green over 5 reject classes\n")
    return 1 if failures else 0


def _raises(fn) -> bool:
    try:
        fn()
    except Exception:
        return True
    return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _corpus_ids(oracle_dir: Path) -> list[str]:
    """Corpus ids are the oracle filenames — the population that would receive the stamp."""
    return sorted(p.stem for p in Path(oracle_dir).glob("*.yaml"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m sdk.acceptance.sme_authority",
        description="Resolve a reviewer .xlsx into a reviewable question_id -> SME authority "
        "mapping. Prints linked/unlinked/ambiguous. Writes no oracle.",
    )
    ap.add_argument("--xlsx", type=Path, help="the reviewer workbook")
    ap.add_argument("--oracle-dir", type=Path, help="corpus oracle dir; filenames are the ids")
    ap.add_argument("--corpus-id", action="append", default=[], help="an explicit corpus id")
    ap.add_argument("--sheet", help="sheet name (default: the first sheet)")
    ap.add_argument("--out", type=Path, help="write the proposed mapping here (YAML)")
    ap.add_argument(
        "--reveal-reviewers",
        action="store_true",
        help="emit real reviewer names instead of pseudonyms (local review only)",
    )
    ap.add_argument(
        "--strict", action="store_true", help="exit 1 if any row is unlinked or ambiguous"
    )
    ap.add_argument("--self-test", action="store_true", help="seed one row per reject class")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    if not args.xlsx:
        ap.error("--xlsx is required (or use --self-test)")

    ids = list(args.corpus_id)
    if args.oracle_dir:
        ids += _corpus_ids(args.oracle_dir)
    if not ids:
        ap.error("no corpus ids: pass --oracle-dir and/or --corpus-id")

    try:
        result = resolve(args.xlsx, ids, sheet=args.sheet, reveal=args.reveal_reviewers)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1

    report(result)

    if args.out:
        Path(args.out).write_text(_BANNER + _yaml_dump(result), encoding="utf-8")
        print(f"\n  proposed mapping -> {args.out}")

    c = result["counts"]
    if args.strict and (c["unlinked"] or c["ambiguous"]):
        print(
            f"\nFAIL: {c['unlinked']} unlinked + {c['ambiguous']} ambiguous of "
            f"{c['rows_scanned']} rows scanned"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
