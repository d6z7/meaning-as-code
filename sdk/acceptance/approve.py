"""Write the APPROVED ANSWER — the plane the whole board grades against.

WHY THIS EXISTS. Operator, 2026-10-02, after re-approving a question and finding nothing had
changed: there was NO route and NO control that writes `acceptance/reference/`. Measured that day:
no POST/PUT in `console_api` touches it, and `sdk.acceptance.run` offered only
`grade-batch | upsert | patch | explain`. The detail page DISPLAYS "approved by <x> · <date>" and
offered no way to set it.

So the one step the strategy calls the verdict -- "the SME approves the answer; pass/fail is the
only verdict, and the approved number is the reference" -- existed only as a YAML file edited by
hand. The engine could answer and the board could grade, and the approving in between was not
implemented. Five of eleven open failures on that day were re-approvals or rulings, every one of
them blocked on hand-editing.

THE FORMAT IS AUTHORED, SO IT IS WRITTEN BY HAND AND NEVER BY `safe_dump`. These files carry a
header comment and `>-` block scalars that a dumper destroys (the same rule `run.py` already states
for oracles). Long prose is folded at 96 columns, and nothing re-wraps what it is given beyond that.

SUPERSEDING IS THE EXISTING CONVENTION, not a new one: `RC05` already records
`superseded_value` + `superseded_reason` for a number re-approved the same day. When `expected`
moves, the previous value is carried into `superseded_value` and a reason is REQUIRED -- an approved
number that changes without a stated reason is the one thing a reference plane must not allow,
because the board's whole claim is that a person signed this figure.
"""

from __future__ import annotations

import textwrap
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from sdk.acceptance import bundleio as _io

HEADER = (
    "# THE APPROVED ANSWER. A person ran the query, read the number and said yes.\n"
    "# The next run either returns this or it does not. PASS or FAIL, nothing else.\n"
)

#: Written in this order, because a reader opens the file to see the number and who signed it.
ORDER = (
    "id", "question", "expected", "sql", "note",
    "approved_by", "approved_at", "approved_here",
    "ruling", "superseded_value", "superseded_reason", "basis", "cloned_from",
)

#: Plain scalars; everything else is folded as a block.
SCALARS = {"id", "expected", "approved_by", "approved_at", "approved_here", "superseded_value"}


def _scalar(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    s = str(v)
    # QUOTE A DATE OR A DATE-LIKE STRING, or yaml reads it back as a `datetime.date` and the grader
    # compares a date object against a string. Measured on the existing files: every one quotes it.
    needs = (not s) or s[0] in "&*?|->!%@`'\"[{" or s.strip() != s
    if needs or (s[:4].isdigit() and "-" in s[:8]):
        return "'" + s.replace("'", "''") + "'"
    return s


def _block(key: str, text: str) -> str:
    body = " ".join(str(text).split()) if "\n" not in str(text) else str(text)
    wrapped = []
    for para in str(body).split("\n\n"):
        wrapped.append("\n".join(textwrap.wrap(" ".join(para.split()), width=96) or [""]))
    joined = "\n\n".join(wrapped)
    return f"{key}: >-\n" + "\n".join("  " + l if l else "" for l in joined.split("\n")) + "\n"


def render(doc: dict[str, Any]) -> str:
    """The file text, in the authored format."""
    out = [HEADER]
    for key in ORDER:
        if key not in doc or doc[key] is None:
            continue
        v = doc[key]
        # A STRUCTURED VALUE IS DUMPED AS YAML, WHATEVER ITS KEY. This checked `key in SCALARS`
        # FIRST, and `expected` is in that set -- so a BREAKDOWN reference
        # (`{rows, ordered, values}`) was written as `_scalar(dict)`, i.e. python's repr inside a
        # quoted string. MEASURED 2026-10-02 approving AGG-15: the file read
        # `expected: '{''rows'': 88, ...}'`, it round-tripped as a `str`, and the grader's grid
        # comparison never fired -- it took the text path and reported the whole repr as "the
        # approved value does not appear in the answer". The shape of the VALUE decides how it is
        # written; the key only decides whether a string is folded as a block.
        if isinstance(v, (dict, list)):
            out.append(yaml.safe_dump({key: v}, sort_keys=False, allow_unicode=True))
        elif key in SCALARS:
            out.append(f"{key}: {_scalar(v)}\n")
        elif isinstance(v, (dict, list)):
            # `cloned_from` is structured; dumped as a nested block, which it already is today.
            out.append(yaml.safe_dump({key: v}, sort_keys=False, allow_unicode=True))
        else:
            out.append(_block(key, v))
    return "".join(out)


def approve(bundle: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Write `acceptance/reference/<id>.yaml`. Returns `{ok, id, path, superseded}`."""
    bundle = Path(bundle)
    qid = _io.check_qid(payload.get("id"), where="approve id")
    acc = bundle / "acceptance"
    path = acc / "reference" / f"{qid}.yaml"
    before: dict[str, Any] = {}
    if path.is_file():
        before = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if "expected" not in payload:
        raise ValueError("approve needs `expected` — the number or value being approved")
    new_expected = payload["expected"]
    old_expected = before.get("expected")
    superseding = bool(before) and str(old_expected) != str(new_expected)
    if superseding and not str(payload.get("superseded_reason") or "").strip():
        # THE ONE THING THIS REFUSES. An approved figure that changes silently destroys the board's
        # only claim -- that a person signed this number, for a reason, on a date.
        raise ValueError(
            f"{qid} is already approved at {old_expected!r}; changing it to {new_expected!r} needs "
            f"`superseded_reason` saying why"
        )

    doc: dict[str, Any] = dict(before)
    doc["id"] = qid
    for key in ("question", "sql", "note", "ruling", "approved_by", "basis", "approved_here"):
        if payload.get(key) is not None:
            doc[key] = payload[key]
    doc["expected"] = new_expected
    doc["approved_at"] = payload.get("approved_at") or datetime.now(UTC).date().isoformat()
    doc.setdefault("approved_by", "operator")
    if superseding:
        doc["superseded_value"] = old_expected
        doc["superseded_reason"] = payload["superseded_reason"]
        # A RE-APPROVAL IS AN APPROVAL *HERE*, and `cloned_from`'s claim stops being true.
        # 32 of this bundle's 46 references were CLONED from a sibling on the basis that "main.* is
        # identical in both bundles, so the approved value is the value here too". The moment the
        # value is changed on this bundle, that sentence is false about the CURRENT figure -- so
        # `approved_here` is set, which is the flag the detail page reads for provenance. The
        # `cloned_from` block is KEPT, because it is now accurate history: it is where the
        # SUPERSEDED value came from, and deleting it would erase why the old number existed.
        doc["approved_here"] = True
    for required in ("question", "sql", "note"):
        doc.setdefault(required, "")

    path.parent.mkdir(parents=True, exist_ok=True)
    _io.atomic_write(path, render(doc))
    return {
        "ok": True,
        "id": qid,
        "path": str(path.relative_to(bundle)),
        "superseded": old_expected if superseding else None,
    }


__all__ = ["approve", "render"]
