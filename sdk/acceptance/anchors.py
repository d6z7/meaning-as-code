"""sdk.acceptance.anchors — read the anchors plane and decide which anchor may GRADE which question.

WHAT AN ANCHOR IS
    ``acceptance/anchors/ANCHOR_NN.yaml`` holds a number derived independently of the engine, twice
    (a derivation and a cross-check, with the author's own ``agree`` verdict on whether the two
    lines met). It is the only artefact in the bundle capable of saying an answer's NUMBER is
    right. Everything else in acceptance says the question was ROUTED right, which is a different
    and much weaker claim.

WHY LINKING NEEDS RULES AT ALL
    The anchors do not carry a ``question_id:`` key yet — adding one is authored content and is a
    separate, operator-accepted change. Today an anchor names its question in free text, usually
    with the corpus id in a trailing parenthetical. So the link has to be inferred, and inference
    on the one axis that is supposed to be honest is exactly where a false green would do the most
    damage.

    A naive "does any corpus id appear in the text" search links 16 of 21 — and grades two of them
    against questions they explicitly say they DIFFER from. ``ANCHOR_09`` is "(variant of
    FPL_C5.1, pinned to a single model x country cell **instead of** the model-family x VD-region
    reading the question literally names…)" and ``ANCHOR_12`` is "(FPL_C3.3, family variant)".
    Grading those numbers against those questions asserts agreement the author explicitly denied.

    Hence TWO TIERS: GRADED links may move the ``value`` flag; ADVISORY links are displayed beside
    it and never graded. An unlinked anchor is counted and named so the gap is visible.

THE EXCLUSION LIST IS A DOCUMENTED BUNDLE-CONVENTION HEURISTIC
    ``variant`` / ``instead of`` / ``different``, scanned ONLY inside the parenthetical that
    encloses the id (or the text following it), lowercased. It is the single English-scanning
    heuristic in the whole grader, it exists only because ``question_id:`` does not exist yet, and
    it is structurally incapable of turning anything green: every path through it either leaves an
    anchor GRADED or DEMOTES it to advisory. Nothing here can promote.

    The narrow scope is load-bearing, not tidiness. ``ANCHOR_04``'s ``assumptions`` prose contains
    the sentence "This is a genuinely **different** reading from ANCHOR_03" — a remark about
    another anchor, not about its own question. Scanning the whole document would demote the most
    valuable red in the corpus (``FPL_C1.9``: the engine reads 209.391 where the anchor derives
    173.704) into a footnote nobody grades. ``ANCHOR_04`` must come out GRADED, and a test pins it.

I/O-BEARING BY DESIGN
    This module reads YAML; ``flags.py`` stays pure and is handed the already-resolved anchor. That
    separation is what lets the evaluator be unit-tested from synthetic dicts and lets the projector
    resolve the whole anchors plane once per build instead of once per question.

NO BUNDLE LITERALS IN THE CODE
    The only English strings this module matches on are the three demotion markers below, which
    are a documented convention of the anchors plane rather than a vocabulary of any one source.
    The ids quoted in this docstring are the measured evidence for the two-tier rule — historical
    record, not data: no code path reads them, and pointing this module at another bundle touches
    nothing here.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

# Where the anchors plane lives inside a bundle. One definition, used for both the scan and the
# bundle-relative `_file` path the UI turns into a link.
ANCHORS_SUBDIR = ("acceptance", "anchors")

# See the module docstring. Lowercased substrings; matched against the id's own scope only.
# DEMOTION-ONLY: a hit moves an anchor from graded to advisory and can never do the reverse.
VARIANT_MARKERS = ("variant", "instead of", "different")

# How strongly a link is evidenced, for resolving two anchors claiming the same question.
# An explicit key beats a trailing parenthetical beats an id mentioned mid-sentence.
_LINK_RANK = {"question_id": 2, "suffix": 1, "inline": 0}


def _id_pattern(corpus_ids) -> re.Pattern | None:
    """One alternation matching any corpus id as a whole token, or None when there are no ids.

    The lookarounds are what keep ``FPL_C1.1`` from matching inside ``FPL_C1.10``: a trailing
    digit, letter, underscore or dot after the candidate blocks the match, so the engine falls
    through to the longer alternative. Ids are sorted longest-first as well, so the intent is
    legible without relying on backtracking to rescue it.
    """
    ids = sorted(
        {i for i in (corpus_ids or []) if isinstance(i, str) and i.strip()},
        key=lambda s: (-len(s), s),
    )
    if not ids:
        return None
    body = "|".join(re.escape(i) for i in ids)
    return re.compile(r"(?<![A-Za-z0-9_.])(?:" + body + r")(?![A-Za-z0-9_.])")


def _paren_groups(text: str) -> list[tuple[int, int]]:
    """Half-open spans of the TOP-LEVEL parenthetical groups in ``text``, in order.

    Unbalanced input is tolerated: an unclosed ``(`` runs to the end of the string. Anchor prose is
    authored by hand and a stray bracket must not decide whether a number gets graded.
    """
    groups: list[tuple[int, int]] = []
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "(":
            if depth == 0:
                start = i
            depth += 1
        elif ch == ")" and depth > 0:
            depth -= 1
            if depth == 0:
                groups.append((start, i + 1))
    if depth > 0 and start >= 0:
        groups.append((start, len(text)))
    return groups


def _enclosing_paren(text: str, start: int) -> tuple[int, int] | None:
    """The span of the INNERMOST parenthetical enclosing ``text[start]``, or None.

    Scans back for the nearest unmatched ``(``, then forward to its partner — i.e. exactly "from
    the ``(`` preceding it to the matching ``)``".
    """
    depth = 0
    open_at = -1
    for i in range(start - 1, -1, -1):
        ch = text[i]
        if ch == ")":
            depth += 1
        elif ch == "(":
            if depth == 0:
                open_at = i
                break
            depth -= 1
    if open_at < 0:
        return None

    depth = 0
    for i in range(open_at + 1, len(text)):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                return (open_at, i + 1)
            depth -= 1
    return (open_at, len(text))  # unbalanced: the group runs to the end


def _scope_for(text: str, start: int, end: int) -> str:
    """The text the exclusion list is allowed to read for one id occurrence.

    The enclosing parenthetical when the id sits in one, otherwise the remainder of the string
    after it. NEVER the whole document — see the module docstring for the measured reason.
    """
    span = _enclosing_paren(text, start)
    if span is not None:
        return text[span[0] : span[1]]
    return text[end:]


def _classify(question: str, pattern: re.Pattern | None) -> tuple[list[str], str | None, bool]:
    """Inspect one anchor's free-text question.

    Returns ``(distinct ids found, link_mode or None, demoted_by_marker)``.

    ``link_mode`` is ``"suffix"`` when the id appears inside the LAST top-level parenthetical of
    the string (the trailing "(FPL_C1.1)" convention) and ``"inline"`` otherwise. It is only
    meaningful when exactly one distinct id was found.

    The exclusion list is evaluated over EVERY occurrence's scope and demotes if any of them
    matches. Checking all of them rather than the first is the conservative direction — the only
    effect is more anchors moving to advisory, never fewer.
    """
    if not isinstance(question, str) or pattern is None:
        return ([], None, False)

    matches = list(pattern.finditer(question))
    if not matches:
        return ([], None, False)

    seen: list[str] = []
    for m in matches:
        if m.group(0) not in seen:
            seen.append(m.group(0))
    if len(seen) != 1:
        # Several different questions named in one anchor: which one its number belongs to is
        # genuinely unknown, so it is displayed against all of them and grades none.
        return (seen, None, False)

    demoted = any(
        marker in _scope_for(question, m.start(), m.end()).lower()
        for m in matches
        for marker in VARIANT_MARKERS
    )

    groups = _paren_groups(question)
    last = groups[-1] if groups else None
    is_suffix = last is not None and any(
        last[0] <= m.start() and m.end() <= last[1] for m in matches
    )
    return (seen, "suffix" if is_suffix else "inline", demoted)


def build_index(bundle: Path, corpus_ids: list[str]) -> dict:
    """Resolve the bundle's anchors plane against the corpus.

    Returns::

        {
          "graded":   {question_id: anchor},    # at most ONE anchor per question id
          "advisory": {question_id: [anchor]},  # displayed beside the flag, NEVER graded
          "unlinked": [anchor_id],              # named so the authoring gap stays visible
          "count":    int,                      # anchor documents that entered the linker
          "errors":   [{"file": str, "error": str}],
        }

    ``count`` counts DISTINCT anchor documents that loaded as a mapping, so it always equals
    graded + (distinct anchors appearing in advisory) + unlinked. A file that failed to load is a
    finding in ``errors``, never a phantom in the total the dashboard prints.

    Each returned anchor is the parsed document plus injected keys::

        anchor["_anchor_id"]   = file stem
        anchor["_file"]        = bundle-relative path, for the UI's file link
        anchor["_link_mode"]   = "question_id" | "suffix" | "inline" | None
        anchor["_link_note"]   = why it is advisory, when it is (else absent)

    ``_link_mode`` is surfaced in the UI so an operator can see that a graded link rests on a
    parenthetical convention rather than an authored key. ``_link_note`` carries the demotion
    reason so an advisory anchor explains itself instead of just being quiet.

    A YAML or shape failure never stops the scan: the file lands in ``errors`` and the other
    twenty anchors keep working. One malformed anchor must not blank the value column of the whole
    board.
    """
    ids = [i for i in (corpus_ids or []) if isinstance(i, str) and i.strip()]
    id_set = set(ids)
    pattern = _id_pattern(ids)

    root = Path(bundle)
    directory = root.joinpath(*ANCHORS_SUBDIR)

    graded: dict[str, dict] = {}
    advisory: dict[str, list] = {}
    unlinked: list[str] = []
    errors: list[dict] = []
    count = 0

    # Sorted so the index — including which of two competing anchors is demoted — is reproducible.
    # rglob/iterdir order is filesystem order, not a contract.
    files = sorted(directory.glob("*.yaml")) if directory.is_dir() else []

    def rel(path: Path) -> str:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return path.as_posix()

    def add_advisory(qid: str, anchor: dict) -> None:
        bucket = advisory.setdefault(qid, [])
        if anchor not in bucket:
            bucket.append(anchor)

    for path in files:
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as err:
            errors.append({"file": rel(path), "error": " ".join(str(err).split())[:400]})
            continue
        if not isinstance(doc, dict):
            errors.append(
                {"file": rel(path), "error": f"expected a YAML mapping, got {type(doc).__name__}"}
            )
            continue

        count += 1
        anchor = dict(doc)
        anchor["_anchor_id"] = path.stem
        anchor["_file"] = rel(path)
        anchor["_link_mode"] = None

        # --- tier 1: an explicit authored key, when one day it exists ------------------------
        explicit = doc.get("question_id")
        if isinstance(explicit, str) and explicit in id_set:
            anchor["_link_mode"] = "question_id"
            _claim(graded, advisory, errors, explicit, anchor, add_advisory)
            continue

        # --- tier 2: the free-text convention ------------------------------------------------
        found, mode, demoted = _classify(doc.get("question"), pattern)

        if not found:
            unlinked.append(anchor["_anchor_id"])
            continue

        if len(found) > 1:
            anchor["_link_note"] = (
                "names several corpus questions; which one this number belongs to is ambiguous"
            )
            for qid in found:
                add_advisory(qid, anchor)
            continue

        qid = found[0]
        anchor["_link_mode"] = mode
        if demoted:
            anchor["_link_note"] = (
                "the anchor's own text says it is a variant of this question, so its number is "
                "shown beside the answer and never graded against it"
            )
            add_advisory(qid, anchor)
            continue

        _claim(graded, advisory, errors, qid, anchor, add_advisory)

    return {
        "graded": graded,
        "advisory": advisory,
        "unlinked": unlinked,
        "count": count,
        "errors": errors,
    }


def _claim(
    graded: dict, advisory: dict, errors: list, qid: str, anchor: dict, add_advisory
) -> None:
    """Award ``qid`` to ``anchor``, demoting whichever of the two claimants is weaker.

    At most one anchor may grade a question. Two graded links to one id would make the ``value``
    flag depend on directory order, so the stronger evidence wins (an authored key beats a
    trailing parenthetical beats a mid-sentence mention) and ties go to the lexically first anchor
    id. The demotion is reported in ``errors`` because it is a finding about the anchors plane
    that someone should resolve, not a silent tiebreak.
    """
    incumbent = graded.get(qid)
    if incumbent is None:
        graded[qid] = anchor
        return

    def strength(a: dict) -> tuple[int, str]:
        # Negated id so that, at equal rank, the lexically FIRST anchor id sorts strongest.
        return (_LINK_RANK.get(a.get("_link_mode"), -1), a.get("_anchor_id") or "")

    inc_rank, inc_id = strength(incumbent)
    new_rank, new_id = strength(anchor)
    challenger_wins = new_rank > inc_rank or (new_rank == inc_rank and new_id < inc_id)

    loser = incumbent if challenger_wins else anchor
    if challenger_wins:
        graded[qid] = anchor

    loser["_link_note"] = f"another anchor already grades {qid}; shown for comparison only"
    errors.append(
        {
            "file": loser.get("_file") or loser.get("_anchor_id") or "?",
            "error": f"duplicate graded link to {qid}",
        }
    )
    add_advisory(qid, loser)
