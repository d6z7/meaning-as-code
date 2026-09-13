"""sdk.acceptance.grade — the capture-side primitives of the acceptance plane (pure, no I/O).

WHAT THIS MODULE IS, AFTER THE FLAG REDESIGN

    Everything here describes what the ENGINE DID. Nothing here compares it to what an oracle
    RULED. That comparison lives in ``sdk.acceptance.flags``, once, and is expressed as three
    independently-falsifiable flags rather than a single opaque status.

    Four functions and one closed set survive:

      * ``_norm`` / ``_is_num`` / ``_num`` — the scalar + text normal forms the whole plane shares.
      * ``result_view(ask_result)``        — a ``local_ask`` return reduced to the compact result
                                             block the answer document stores as EVIDENCE.
      * ``validate_sql(sql_list)``         — offline sqlglot parse for the ``llm-validate`` backend.
      * ``disposition(ask_result)``        — GOVERNED / AI_ASSISTED / GOVERNED_REFUSAL.
      * ``run_status(answer)``             — the oracle-INDEPENDENT answering status (Process A).

WHAT WAS DELETED, AND WHY IT IS NOT COMING BACK  (spec §4.4)

    ``numeric_verdict`` / ``oracle_target`` / ``graded`` / ``grade_status`` / ``to_run_grade`` /
    ``meaning_verdict`` and their helpers are gone. Measured on the 24 committed captures of the
    reference corpus, that machine was INVERTED, not merely noisy:

      * every COMMIT question took the refusal-gate branch, because the branch fired on
        ``must_surface_any`` being present whenever no ``expected.value`` existed — 96 of 96
        oracles carry the first and 94 carry no second — so 22 rows whose ``run_status`` was
        ``executed`` were labelled ``wrong-refusal``;
      * the gate itself was case-insensitive SUBSTRING matching of 84-character authored prose
        justifications against answer markdown: 1 hit in 121 applicable tokens, and that hit was
        the bare five-letter word ``brand``;
      * ``graded``'s tolerance floor, ``max(tol, target * 0.005)``, widened 17 of 21 anchors and
        would accept a +25 error on an anchor authored ``tolerance: 0``.

    A prose grader that reports failure on correct work teaches an operator to ignore the board.
    ``flags.py`` replaces it with checks against the EXECUTED SQL and against independently
    dual-derived anchors, and says ``unchecked`` where it cannot decide. Nothing in this build
    substring-matches ``must_surface_any`` or ``must_not``; they are rendered verbatim for a human.

Every function is pure (dict in, dict out); persistence + projection live in
``sdk.acceptance.run`` and ``sdk.project.questions``.
"""

from __future__ import annotations

import re

# --------------------------------------------------------------------------- #
# Scalar + text normal forms
# --------------------------------------------------------------------------- #

_WS_RE = re.compile(r"\s+")


def _norm(s) -> str:
    """Collapse whitespace — the comparison normal form for SQL / answer / question text."""
    return _WS_RE.sub(" ", str(s or "")).strip()


def _num(v):
    """Parse a scalar to float, tolerating thousands separators. None on failure."""
    if v is None:
        return None
    if isinstance(v, bool):  # a bool is not a gradeable number
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    # Strip currency / unit noise, keep digits, separators, sign, exponent.
    s = re.sub(r"[^0-9,.\-+eE]", "", s)
    if not s:
        return None
    # Heuristic for European vs US grouping: if both separators appear, the LAST one is the
    # decimal; else a lone ',' with 1-2 trailing digits is a decimal comma, otherwise grouping.
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        frac = s.split(",")[-1]
        s = s.replace(",", ".") if len(frac) in (1, 2) else s.replace(",", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _is_num(x) -> bool:
    """Exactly ``_num(x) is not None`` — one definition of "this is a number", not two.

    It used to be a bare ``float(x)`` probe, which disagreed with ``_num`` in both directions:
    ``_is_num('~1624350')`` was False while ``_num`` of it is 1624350.0, and ``_is_num(True)`` was
    True while ``_num(True)`` is None. A caller that asked one and then used the other got a
    silently different answer, which is how a bool became a gradeable target.
    """
    return _num(x) is not None


# --------------------------------------------------------------------------- #
# Refusal signals
# --------------------------------------------------------------------------- #

_REFUSAL_MARKERS = (
    "cannot answer",
    "can't answer",
    "can not answer",
    "unable to",
    "i don't have",
    "we don't have",
    "i do not have",
    "no data",
    "not available",
    "doesn't cover",
    "does not cover",
    "not covered",
    "the wiki doesn't",
    "the wiki does not",
    "wiki doesn't",
    "wiki does not",
    "which market",
    "which country",
    "please specify",
    "could you clarify",
    "need to clarify",
    "underspecified",
    "unknown market",
    "no such",
    "i'm not able",
    "i am not able",
    "i cannot",
    "i can't",
    "refuse",
    "not in the wiki",
    "isn't served",
    "is not served",
    "not served",
    "would need",
    "would you like",
)


def refusal_markers_in(text: str) -> list:
    """Which refusal markers ``text`` contains, in table order.

    Exists so a flag can SHOW its working — "declined" is an accusation, and the detail card has to
    be able to print which words produced it. One scan, one table: a second copy of the marker list
    is a second thing to drift, and the run path and the flag path must agree on what a withhold
    looks like.

    CALLERS PASS THE LEAD ONLY. See ``_looks_refusal``.
    """
    t = _norm(text).lower()
    if not t:
        return []
    return [m for m in _REFUSAL_MARKERS if m in t]


def _looks_refusal(text: str) -> bool:
    """True when ``text`` reads as a refusal / clarification request.

    CONTRACT: **callers pass the LEAD only.** This is a 34-marker substring scan including
    "would need", "no data" and "would you like". Scanning a whole governed answer produces false
    refusals — a correct commit that closes with "would you like a breakdown by market?" trips it,
    and a "Defaults applied" section that notes a dimension is "not served" trips it too.
    ``flags._flag_outcome`` passes the first 400 normalised characters, and nothing else in this
    build passes more.
    """
    return bool(refusal_markers_in(text))


# --------------------------------------------------------------------------- #
# result normalisation — a local_ask result -> the answer doc's evidence block
# --------------------------------------------------------------------------- #


def result_view(ask_result: dict) -> dict:
    """Normalise a ``local_ask.ask`` return to the result block the answer yaml stores.

    ``{value, cols, rows (int count), sample_rows, status}`` with status ∈
    ``ok | partial | no_value | error | no_sql | no_ask``.

    ``sample_rows`` carries the first 50 rows VERBATIM. It exists because the detail page's answer
    grid branched on ``Array.isArray(result.rows)`` while ``rows`` is an integer count, so the grid
    was dead code and "row-level detail wasn't captured for this run" always fired. The rows were
    never captured at all; now they are.

    ``partial`` is a real state: a non-empty grid can coexist with ``sql_errors`` when the engine
    ran several statements and only some succeeded. Reporting that as ``ok`` hides a half-answered
    run behind a complete-looking one.

    ``value`` IS NOT THE ANSWER. It is the last numeric column of the first row of the LAST
    executed statement, which is measurably the wrong number on real captures (a model count where
    the answer is a stock figure, a brand count where the answer is a total) and null on many more.
    It is kept because the answer document is evidence and this is what the engine returned — but
    it is not projected into the dashboard row, not displayed as an answer, and NOT GRADED. The
    number that answers the question exists only inside the markdown prose; ``flags`` reads the
    answer's headline for it and says so.
    """
    if not ask_result:
        return {"value": None, "cols": [], "rows": 0, "sample_rows": [], "status": "no_ask"}
    grid = ask_result.get("result") or None
    errs = ask_result.get("sql_errors") or []
    sql = ask_result.get("sql") or []
    if isinstance(grid, dict) and grid.get("columns"):
        cols = list(grid.get("columns") or [])
        rows = list(grid.get("rows") or [])

        # The untrustworthy scalar, inlined rather than left as a shared helper: nothing else may
        # reach for it. A 1x1 cell, else the last numeric column of a lone row; None for a
        # multi-row grid (a breakdown is not a scalar).
        val = None
        if len(rows) == 1:
            row = rows[0]
            if not isinstance(row, dict):
                val = _num(row)
            elif len(cols) == 1:
                val = _num(row.get(cols[0]))
            else:
                for c in reversed(cols):
                    n = _num(row.get(c))
                    if n is not None:
                        val = n
                        break

        status = "partial" if errs and rows else "ok" if val is not None else "no_value"
        return {
            "value": val,
            "cols": cols,
            "rows": len(rows),
            "sample_rows": rows[:50],
            "status": status,
        }
    if errs:
        return {"value": None, "cols": [], "rows": 0, "sample_rows": [], "status": "error"}
    if not sql:
        return {"value": None, "cols": [], "rows": 0, "sample_rows": [], "status": "no_sql"}
    return {"value": None, "cols": [], "rows": 0, "sample_rows": [], "status": "no_value"}


# --------------------------------------------------------------------------- #
# disposition
# --------------------------------------------------------------------------- #


def disposition(ask_result: dict) -> str:
    """GOVERNED / AI_ASSISTED / GOVERNED_REFUSAL from the ask result: a refusal/clarify answer is
    a GOVERNED_REFUSAL; governed SQL emitted is GOVERNED; a wiki-only reasoned answer is
    AI_ASSISTED.

    This runs at CAPTURE time, against the answer the engine just produced, and its result is
    stamped into the answer document's ``route``. The flag evaluator does NOT rely on it: it
    re-derives the withhold signal from the answer's lead, because this scan reads the whole text.
    """
    ask_result = ask_result or {}
    answer = ask_result.get("answer") or ""
    sql = ask_result.get("sql") or []
    if _looks_refusal(answer):
        return "GOVERNED_REFUSAL"
    if sql:
        return "GOVERNED"
    return "AI_ASSISTED"


# --------------------------------------------------------------------------- #
# SQL validity — the `llm-validate` backend (offline, sqlglot, $0)
# --------------------------------------------------------------------------- #


def validate_sql(sql_list) -> dict:
    """Offline SQL validity for the ``llm-validate`` backend: parse each composed statement with
    sqlglot in the Trino dialect (the Athena engine). Returns ``{"sql_valid": bool, "errors": [...]}``:

      * ``sql_valid`` True  → every non-empty statement parsed.
      * ``sql_valid`` False → at least one statement failed to parse (or none was composed).
      * ``sql_valid`` None  → sqlglot itself is unavailable (never in the wiki venv).

    Pure + side-effect free — no execution, no network."""
    try:
        import sqlglot

        # ParseError (syntax) + TokenError (tokeniser) both subclass SqlglotError; catch the base
        # so we're robust across sqlglot versions (30.x renamed the token error class).
        from sqlglot.errors import ParseError, SqlglotError
    except Exception as e:
        return {"sql_valid": None, "errors": [f"sqlglot unavailable: {type(e).__name__}: {e}"]}
    sqls = [str(s) for s in (sql_list or []) if str(s).strip()]
    if not sqls:
        return {"sql_valid": False, "errors": ["no SQL composed to validate"]}
    errors: list[str] = []
    for i, s in enumerate(sqls):
        try:
            sqlglot.parse_one(s, read="trino")
        except (ParseError, SqlglotError) as pe:
            errors.append(f"stmt[{i}]: {_norm(str(pe))[:200]}")
        except Exception as e:
            errors.append(f"stmt[{i}]: {type(e).__name__}: {str(e)[:200]}")
    return {"sql_valid": not errors, "errors": errors}


# --------------------------------------------------------------------------- #
# The answering status (Process A) — oracle-INDEPENDENT by construction
#
# `RUN_STATUSES` is the closed set the dashboard renders against. It is derived in exactly ONE
# place now: `sdk.project.questions` calls `run_status(answer)` while building the row. The value
# is no longer stamped into the answer document, because a stamped status and a re-projected one
# drifted with nothing guarding them, and the answer document is EVIDENCE — it carries what the
# engine did, not a judgement about it.
# --------------------------------------------------------------------------- #

# `deferred` is gone: it was reserved for the PARKED governed composer and no code path could ever
# emit it, so every consumer carried a bucket that was 0 on every board ever built.
RUN_STATUSES = ("unrun", "answered", "composed", "executed", "refused", "error")


def run_status(answer: dict | None) -> str:
    """The answering status from a persisted answer doc (or None), oracle-independent.

    Priority: ``unrun`` → ``error`` → ``refused`` → ``executed`` → ``composed`` → ``answered``.
      * ``unrun``    — no answer captured.
      * ``error``    — ask threw, or SQL execution errored.
      * ``refused``  — a governed refusal / clarify.
      * ``executed`` — SQL ran live (execute mode / athena) with SQL or a returned value.
      * ``composed`` — the validate backend parsed composed SQL (invalid parse → ``error``).
      * ``answered`` — an LLM answer with no live/validated governed SQL.

    The ``error`` branch keys on the capture itself (``error`` / ``result.status``) rather than on
    a numeric verdict constant, because those constants are deleted and because an execution error
    is a fact about the run, not a grade.

    The ``refused`` branch reads whichever of the two shapes the document carries: ``route`` on
    documents written by the current run path, ``verdict.disposition`` on the captures already
    committed before the answer document became pure evidence. It deliberately does NOT re-scan the
    answer prose — that scan is the false-refusal trap, and here it would run against the whole text.
    """
    if not answer:
        return "unrun"
    result = answer.get("result") or {}
    sql = answer.get("sql") or []
    sql_valid = answer.get("sql_valid")
    eng = answer.get("engine") or {}
    mode = eng.get("mode")
    executed = (mode == "llm-execute") or bool(eng.get("athena"))
    legacy_disposition = (answer.get("verdict") or {}).get("disposition")
    if answer.get("error") or result.get("status") == "error":
        return "error"
    if answer.get("route") == "refusal" or legacy_disposition == "GOVERNED_REFUSAL":
        return "refused"
    if executed and (sql or result.get("value") is not None):
        return "executed"
    if mode == "llm-validate" and sql:
        return "error" if sql_valid is False else "composed"
    return "answered"
