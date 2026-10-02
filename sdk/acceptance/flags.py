"""sdk.acceptance.flags — the per-question flag vocabulary and the pure flag evaluator.

This module replaces the single opaque ``grade_status`` with FOUR independently-stated,
independently-falsifiable claims about one captured answer. It exists because the machine it
replaces was measurably inverted: every COMMIT question fell into the refusal-gate branch of
``grade.numeric_verdict`` and was judged by case-insensitive substring matching of authored prose
justifications against the answer markdown — 1 hit in 121 applicable tokens across 24 real
captures, and that one hit was the bare five-letter word ``brand``. Twenty-two rows whose
``run_status`` was ``executed`` were labelled ``wrong-refusal``; the single green cell was the one
genuinely wrong behaviour in the corpus. We are deleting that machine, not tuning it.

WHY FOUR FLAGS AND NOT ONE STATUS
    A verdict that means "correct" has to be able to say WHICH of several different things it
    verified, because the four are not the same claim and are not available on the same
    questions. ``outcome`` is checkable on every graded row, ``pins`` only where SQL ran, and
    ``value`` only where an independently dual-derived anchor exists (14 of 96 today). Collapsing
    them into one label is what let a route-only pass be reported as a correct answer.

WHY ``rules`` IS A FOURTH FLAG AND NOT A WIDENING OF ``pins``
    The first three all check the ORACLE's assertions — an authored expectation about ONE question.
    Nothing checked whether the engine broke a rule the ONTOLOGY already states about the MODEL,
    for every question that touches it. That gap was measured, not supposed:
    ``product.resolve.by_code_not_name`` carries the never-clause "matching on the raw
    display name as the identity — name_key is the search key, acme_product_code is the stable
    identity", the engine filtered ``display_name = 'Aurora Large'`` in three statements of
    ``ACME_C1.1``, and the board called that question ``proven``. ``pins`` could not see it: the
    oracle's ``must_pin`` names axes to CONSTRAIN, and this is a prohibition on a column the oracle
    never mentions. Different authority, different claim, its own square.

    THE HONEST LIMIT, STATED UP FRONT: a never-clause is PROSE. Of the 83 clauses in the reference
    ontology, 9 reduce to a structural claim this module can decide against ``sqlfacts`` roles and
    74 do not ("confusing a delivery measure with a market-total measure", "inventing a model
    code"). Those 74 are reported as ``unchecked`` WITH the clause verbatim and the reason it
    could not be evaluated. They are never guessed at, never counted as covered, and no ``pass``
    claims them.

THE VOCABULARIES BELOW ARE A FROZEN CROSS-WORKSTREAM CONTRACT
    ``sdk/project/questions.py`` copies them into ``questions_dashboard.json`` (schema
    ``mac.questions_dashboard/4``); the UI mirrors them once, in
    ``mac-platform/packages/mac-console/src/mac_console/ui/src/components/questions/FlagStrip.jsx``, and paints what it is given. The browser
    computes no flag, no state and no verdict — grading logic on both sides of the wire is how the
    .xlsx export comes to disagree with the screen. If a name here changes, the dashboard schema id
    changes with it, in the same commit.

PURITY IS LOAD-BEARING
    ``evaluate`` is dict in, dict out: no filesystem, no network, no clock, no imports with side
    effects. Anchor and oracle READING lives in ``anchors.py`` / the projector; that separation is
    what keeps this module unit-testable from synthetic dicts and what lets the projector call it
    ~96 times per build without touching the disk again.

``na`` IS A RENDERED STATE WITH ITS REASON INLINE, NEVER COLLAPSED INTO ``pass``
    Showing green pins on a question that correctly refused and ran zero SQL is precisely the
    overclaim this model exists to prevent. Likewise a check that could not be decided is
    ``unchecked`` — never ``pass``, never ``fail``. An incomplete fact sheet cannot exonerate and
    cannot convict.
"""

from __future__ import annotations

import decimal
import re

# Both imports are PURE modules — no filesystem, no network, no clock — so importing them does not
# break this module's purity contract. `grade` is used for exactly two primitives: `_norm` (the
# whitespace normal form every text comparison in the acceptance plane shares) and the 34-marker
# refusal scan. Copying either here would be a second definition to drift; the refusal marker table
# in particular must have ONE home, because the run path and the flag path have to agree on what a
# withhold looks like.
from sdk.acceptance import grade as _grade
from sdk.acceptance import registers as _registers
from sdk.acceptance import sqlfacts as _sqlfacts

# --------------------------------------------------------------------------- #
# THE FROZEN VOCABULARIES  (spec §4.3; mirrored in the dashboard header §5.2)
# --------------------------------------------------------------------------- #

# The four graded flags, in the order they are always emitted and always rendered. The UI's flag
# strip draws exactly four squares in this order on every row, so the eye can scan one column
# down the whole corpus; a flag missing from the data renders `na`, never blank.
#
# `rules` is LAST on purpose: the first three are ordered by how much they claim (disposition ->
# axes -> the number), and the fourth is a claim of a different KIND — not "the oracle's assertion
# held" but "no prohibition the ontology already states was broken". Inserting it in the middle
# would move the value column, which is the one column an operator scans down all 96 rows.
FLAG_IDS = ("outcome", "pins", "value", "rules")

# What one flag may say about itself.
#   pass      — the check ran and the claim held.
#   fail      — the check ran and the claim did not hold.
#   na        — the check does not apply here (nothing to check, not "nothing was wrong").
#   unchecked — the check applies but could not be decided (SQL did not parse, no number in the
#               headline, locale-ambiguous formatting, sqlglot absent).
#   disputed  — a number was compared against an anchor that self-reports as unstable or
#               approximate. Never passes, never fails; rolls up to `unproven` so the measured
#               disagreement stays visible instead of hiding behind `na`.
FLAG_STATES = ("pass", "fail", "na", "unchecked", "disputed")

# The row-level rollup. The first four are gradeable outcomes; the last four mean "not gradeable"
# and are produced by the precondition ladder before any flag runs.
#   proven       — disposed of as the oracle rules, every named axis constrained in every
#                  answering statement, AND the number agrees with an independently dual-derived
#                  anchor. The ONLY verdict that may render emerald.
#   routed       — disposed of correctly, well-formed SQL, but THE NUMBER IS NOT PROVEN. Sky.
#   unproven     — nothing failed; at least one check could not be decided.
#   failed       — at least one deterministic check failed.
#   error / unrun / no-oracle / oracle-error — not gradeable at all.
VERDICTS = ("proven", "routed", "unproven", "failed", "error", "unrun", "no-oracle", "oracle-error")

# The oracle outcomes that rule "withhold rather than answer". The capture distinguishes only
# WITHHELD from COMMITTED — it cannot tell BLOCK from REFUSE from ASK — so a passing gate flag
# carries `subtype_verified: false` and the detail card says so in words rather than implying a
# sub-type was confirmed.
GATE_OUTCOMES = frozenset({"REFUSE", "DECLINE", "ASK", "CLARIFY", "BLOCK", "REJECT"})

# Corpus-health warning codes (spec §4.3.6). These are claims about the CORPUS, not about the
# engine: they never move a verdict. They live here rather than in the projector because the
# dashboard header (§5.2 `warning_codes`) and `evaluate`'s `warnings` list must not be able to
# drift apart — one vocabulary, one definition.
WARNING_CODES = (
    "question_text_drift",
    "outcome_contradiction",
    "shape_outcome_contradiction",
    "evidence_stale",
)


# --------------------------------------------------------------------------- #
# THE EVALUATOR
# --------------------------------------------------------------------------- #


def evaluate(
    *,
    corpus_row: dict,  # from questions.yaml: {id, question, tags, ...}
    oracle: dict | None,  # parsed oracle doc, or None
    oracle_error: str | None,  # YAML/schema error message, or None
    answer: dict | None,  # parsed answers/<id>.yaml, or None
    anchor: dict | None,  # graded anchor from anchors.build_index, or None
    advisory_anchors: list[dict],  # for display only — NEVER graded
    acceptance_fingerprint: str,  # current bundle value
    #: THE OTHER FINGERPRINT, and the one that was missing. `evidence_stale` compared only the
    #: acceptance plane, so a capture produced by an ontology that no longer exists graded as
    #: current. MEASURED 2026-10-01: all 83 captures carry ontology 306429bf9cdd8a02 while the
    #: bundle reads 3bc7b5d247d0eab2 -- the populations, the value_filter split and a deleted
    #: concept between them -- and the board raised ZERO warnings. An answer is evidence about the
    #: declarations that produced it; when those move, it is evidence about nothing.
    #:
    #: Optional, and `None` means "do not check": a caller that cannot supply it behaves exactly as
    #: before rather than raising a warning it has no basis for.
    ontology_fingerprint: str | None = None,
    concept_rules: list[dict],  # from ontrules.build_index(bundle)["rules"]
    #: THE BUNDLE ROOT, so the grader can READ the bundle's naming registers -- `name_register` is a
    #: closed vocabulary nothing consulted, and without it `US` and `United States` graded as two
    #: different answers (AGG-10, AGG-15: numbers agreeing to the cent). Optional: a caller that
    #: cannot supply it falls back to exact text comparison, which is the old behaviour.
    bundle_root: str | None = None,
    reference: dict | None = None,  # parsed reference/<id>.yaml — THE APPROVED ANSWER, or None
) -> dict:
    """Judge one question against one capture. Pure: dict in, dict out.

    RETURN SHAPE (frozen — the projector copies these six keys straight into the dashboard row
    and adds nothing to a flag, rewrites no ``reason``)::

        {
          "verdict": <one of VERDICTS>,
          "flags": [Flag, Flag, Flag, Flag],     # ALWAYS exactly 4, ALWAYS in FLAG_IDS order
          "warnings": [{"code": <one of WARNING_CODES>, "detail": str}],
          "assertion_counts": {"must_not": int, "must_surface_any": int, "must_pin": int},
          "anchor_id": str | None,
          "advisory_anchor_ids": [str],
        }

    ``Flag``::

        {
          "id":       <one of FLAG_IDS>,
          "state":    <one of FLAG_STATES>,
          "reason":   str,     # short human sentence, <= 120 chars, English, no markup
          "evidence": dict,    # flag-specific; rendered by the detail card, never by the row
        }

    ``reason`` is rendered VERBATIM in the row tooltip and as the flag-card headline, so it must
    never assert something the check did not verify. Numbers inside it are de-DE formatted
    (``1.234``, ``12,34 %``) because it is human-facing copy, not evidence.

    ARGUMENTS

    ``corpus_row``
        The entry from ``acceptance/questions.yaml`` — the authority for the question TEXT. The
        oracle's ``question.text`` has drifted on 16 files and is never treated as the question.

    ``oracle`` / ``oracle_error``
        Exactly one of these is meaningful. ``oracle_error`` also covers SCHEMA-INCOMPLETE, i.e.
        ``oracle["expected"]["outcome"]`` missing or not a string; the caller passes the message
        (e.g. ``"expected.outcome missing"``) and the verdict is ``oracle-error``.

    ``answer``
        The parsed ``acceptance/answers/<id>.yaml``, or ``None`` when the question has not been
        run. It is PURE EVIDENCE of what the engine did — it carries no verdict of its own. Four
        keys are optional because the already-committed captures predate them and must keep
        loading: ``acceptance_fingerprint``, ``sql_errors``, ``disclosures`` and
        ``result.sample_rows``. A missing ``acceptance_fingerprint`` raises ``evidence_stale``.

    ``anchor``
        At most one GRADED anchor, resolved by ``anchors.build_index``. Moves the ``value`` flag
        where no APPROVED REFERENCE does.

    ``reference``
        The parsed ``acceptance/reference/<id>.yaml`` — THE APPROVED ANSWER, or None where nobody
        has approved one. It OUTRANKS the oracle and the anchor as the ``value`` flag's target,
        because it is the only one of the three a person signed: guardrails/strategy.yaml stage 9
        (`answer-and-approve`) rules "the SME approves the answer; pass/fail is the only verdict,
        and the approved number is the reference".

        MEASURED 2026-09-30, and it is the operator's own report: RC01 on contoso5 had been run,
        read and approved, its reference carried `expected: 11` with `approved_by: operator`, the
        capture answered 11 — and the board said `unproven`, `value: na, "no independent anchor for
        this question"`. The approved plane existed, `check_answers.py` graded it, and the dashboard
        read neither. Operator: "dashboard should reflect the actual status".

    ``advisory_anchors``
        Anchors that name this question but are variants of it, or are ambiguous between several
        questions. They are DISPLAYED and never graded — a loose id search links more anchors but
        grades two of them against questions they explicitly differ from, which is a false green on
        the one axis that is supposed to be honest.

    ``acceptance_fingerprint``
        The bundle's current authored-acceptance hash (corpus + oracles + anchors). Compared with
        the value the capture recorded, to say whether the assertions have moved under it. The
        ontology tree hash cannot see this: it does not change when an oracle is edited.

    ``concept_rules``
        Every concept rule in the bundle's ontology that carries a ``never`` clause, as
        ``ontrules.build_index`` reads them. Handed in already resolved, exactly like ``anchor``:
        reading YAML is what would cost this module its purity, and the projector resolves the
        whole plane once per build instead of once per question. REQUIRED, with no default — a
        default of ``[]`` would let a caller that forgot the argument render a permanently `na`
        fourth square, which is indistinguishable on the board from a bundle that states no rules.

    PRECONDITION LADDER (spec §4.3.1) — evaluated FIRST, in this exact order, first match wins.
    Each returns four flags all in state ``na`` with reason ``"not evaluated: <verdict>"``:
        1. ``oracle is None``                                   -> ``no-oracle``
        2. ``oracle_error is not None``                          -> ``oracle-error``
        3. ``answer is None``                                    -> ``unrun``
        4. ``answer["error"]`` truthy, or
           ``answer["result"]["status"] == "error"``             -> ``error``

    VERDICT ROLLUP (spec §4.3.5) — after the ladder, in this exact order, first match wins:
        1. any flag ``state == "fail"``                     -> ``failed``
        2. any flag ``state in {"unchecked", "disputed"}``  -> ``unproven``
        3. ``value.state == "pass"``                        -> ``proven``
        4. otherwise (all pass-or-na, value na)             -> ``routed``

    The fourth flag joins that ladder with the SAME precedence as the other three and no special
    case: a broken never-clause makes the row ``failed`` however green the other squares are, which
    is the whole point — ``ACME_C1.1`` was ``proven`` on three passing flags while violating a rule
    the ontology states.

    The load-bearing invariant that falls out of it, and that a test pins: a question whose
    ``value`` flag is ``na`` can NEVER be ``proven``, for any combination of the other flags.
    ``routed`` means the question was routed correctly and nothing in the bundle can prove its
    number. That is an honest sky, not a stalled green.

    NOT CHECKED HERE, DELIBERATELY: ``expected.must_not`` and ``expected.must_surface_any`` are
    authored prose assertions. They are counted (``assertion_counts``) and rendered verbatim on the
    detail page under the heading "AUTHORED ASSERTIONS — NOT AUTOMATICALLY CHECKED", and nothing
    in this build claims they are covered, discharged, or partially graded by another flag.
    Substring-matching them is the exact defect being removed.
    """
    oracle = oracle if isinstance(oracle, dict) else None
    corpus_row = corpus_row if isinstance(corpus_row, dict) else {}
    advisory = [a for a in (advisory_anchors or []) if isinstance(a, dict)]
    anchor = anchor if isinstance(anchor, dict) else None

    expected = _expected(oracle)
    counts = {
        "must_not": len(_str_list(expected.get("must_not"))),
        "must_surface_any": len(_str_list(expected.get("must_surface_any"))),
        "must_pin": len(_str_list(expected.get("must_pin"))),
    }

    # SCHEMA-INCOMPLETE IS SELF-DETECTED AS WELL AS CALLER-REPORTED. Spec §4.3.1 asks the caller
    # to pass the message, but every branch below reads `expected.outcome` as a string, so a doc
    # that lost it would either crash the whole projection or be graded against `"NONE"`. Detecting
    # it here means the ONE module that depends on the key is the one that refuses to guess.
    if oracle is not None and oracle_error is None and not isinstance(expected.get("outcome"), str):
        oracle_error = "expected.outcome missing"

    warnings = _warnings(
        corpus_row, oracle, answer, acceptance_fingerprint, ontology_fingerprint
    )

    base = {
        "warnings": warnings,
        "assertion_counts": counts,
        "anchor_id": (anchor or {}).get("_anchor_id"),
        "advisory_anchor_ids": [a.get("_anchor_id") for a in advisory if a.get("_anchor_id")],
    }

    # --- PRECONDITION LADDER (§4.3.1) — first match wins, four `na` flags, no checks run -----
    #
    # ORDER IS THE SPEC'S, NOT A PREFERENCE. `oracle is None` before `oracle_error is not None`
    # means a loader that cannot parse an oracle must hand back a doc (an empty mapping is enough)
    # ALONGSIDE the message, or its failure is reported as "no oracle" and the parse error is lost.
    # `sdk.acceptance.run._load_oracle_doc` does exactly that.
    for condition, verdict in (
        (oracle is None, "no-oracle"),
        (oracle_error is not None, "oracle-error"),
        (not isinstance(answer, dict), "unrun"),
        (_is_error_capture(answer), "error"),
    ):
        if condition:
            detail = {"oracle_error": oracle_error} if verdict == "oracle-error" else {}
            return {
                "verdict": verdict,
                "flags": [
                    _flag(fid, "na", f"not evaluated: {verdict}", dict(detail)) for fid in FLAG_IDS
                ],
                **base,
            }

    # --- OBSERVABLES — computed from the CAPTURE only, never from the oracle (§4.3.2) --------
    #
    # The oracle says what SHOULD have happened; these say what DID. Deriving either from the
    # other is how a grader comes to agree with itself.
    sql = [s for s in (answer.get("sql") or []) if isinstance(s, str) and s.strip()]
    n_sql = len(sql)
    answer_text = answer.get("answer") or ""
    # DID THE ENGINE ANSWER AT ALL? A capture with no statements and no result value is a
    # clarification or a refusal -- see _flag_value 4.4.1b.
    _res = answer.get("result") if isinstance(answer, dict) else None
    produced_result = bool(n_sql) or (isinstance(_res, dict) and _res.get("value") is not None)

    # THE LEAD ONLY — first 400 whitespace-normalised characters. The refusal scan is a 34-marker
    # substring test including "would need", "no data" and "would you like". A governed answer that
    # ends "would you like a breakdown by market?" is not a refusal, and a "Defaults applied"
    # section noting that some dimension is "not served" is not one either — so scanning the whole
    # answer turns correct commits into false declines. Measured on the reference corpus: an answer
    # opening "Yes — with documented caveats." and containing zero markers in its lead carries
    # several further down; reporting that it declined would be a brand-new false assertion in
    # place of the one being removed.
    lead = _grade._norm(answer_text)[:400]
    markers = _grade.refusal_markers_in(lead)
    # `verdict.disposition` exists only on captures written BEFORE the answer document became pure
    # evidence; current captures carry no verdict at all and the lead scan is the whole signal.
    # Reading it when it is there costs nothing and honours what the run path observed at the time.
    stamped = (answer.get("verdict") or {}).get("disposition")
    declined = bool(stamped == "GOVERNED_REFUSAL" or markers)

    # PARSED ONCE, READ TWICE. `pins` and `rules` are two policies over ONE fact sheet, and two
    # parses of the same statements are two chances for them to disagree about what the SQL did
    # (as well as ~600 wasted sqlglot calls per projection). `sqlfacts.parse_statements` never
    # raises: an unparseable statement comes back `ok=False` and each flag degrades on its own.
    parsed = _sqlfacts.parse_statements(sql) if (sql and _sqlfacts.available()) else []

    flags = [
        _flag_outcome(expected, n_sql, declined, markers, lead, counts["must_pin"]),
        _flag_pins(expected, parsed, n_sql),
        _flag_value(
            expected, anchor, advisory, answer_text, produced_result, reference,
            result=(answer or {}).get("result"),
            bundle=bundle_root,
        ),
        _flag_rules(concept_rules, parsed, n_sql),
    ]
    return {"verdict": _rollup(flags), "flags": flags, **base}


# --------------------------------------------------------------------------- #
# FLAG 1 — outcome (§4.3.2): "disposed of as the oracle rules"
# --------------------------------------------------------------------------- #


def _flag_outcome(
    expected: dict, n_sql: int, declined: bool, markers: list, lead: str, n_pins: int
) -> dict:
    """The six rows of the §4.3.2 truth table, and nothing else.

    NEVER ``na``: when an oracle and a capture both exist, this flag always applies. It is the one
    check available on every graded row, which is why it is first and why the strip's first square
    is never hollow on a run question.
    """
    outcome = str(expected.get("outcome") or "").strip().upper()
    executed = n_sql > 0
    evidence = {
        "expected": outcome,
        "n_sql": n_sql,
        "executed": executed,
        "declined": declined,
        "refusal_markers": markers,
        "lead_excerpt": lead[:200],
        # THE CAPTURE CANNOT TELL BLOCK FROM REFUSE FROM ASK. The engine emits one withhold
        # disposition; 14 of 96 oracles assert a specific sub-type. Always false, always present,
        # so the detail card can say so in words instead of implying a sub-type was confirmed.
        # Parsing "(BLOCK)" out of answer prose would be the same prose lottery in a new costume.
        "subtype_verified": False,
    }

    if outcome in GATE_OUTCOMES:
        if declined or not executed:
            return _flag("outcome", "pass", f"withheld, as the oracle rules {outcome}", evidence)
        return _flag(
            "outcome",
            "fail",
            f"executed {_de(n_sql)} statements where the oracle rules {outcome}",
            evidence,
        )

    # The commit family. Any non-gate outcome is "the oracle rules an answer"; the literal string
    # is quoted back so the sentence stays true for a bundle whose outcome vocabulary differs.
    if declined:
        return _flag("outcome", "fail", f"declined where the oracle rules {outcome}", evidence)
    if executed:
        return _flag(
            "outcome", "pass", f"committed with {_de(n_sql)} executed statements", evidence
        )
    if n_pins:
        # Answered, did not decline, ran nothing — while the oracle names axes that only SQL could
        # have constrained. That is an ungoverned commit, and it is invisible on a board that only
        # asks "did it refuse?". The reason deliberately does NOT say "declined": it did not.
        return _flag(
            "outcome",
            "fail",
            f"answered without executing SQL; the oracle names {_de(n_pins)} axes to pin",
            evidence,
        )
    return _flag(
        "outcome", "unchecked", "answered without SQL; the oracle names no axes to verify", evidence
    )


# --------------------------------------------------------------------------- #
# FLAG 2 — pins (§4.3.3): "reading axes constrained in EVERY answering statement"
# --------------------------------------------------------------------------- #

# Which structural roles COUNT as constraining an axis. This is the policy `sqlfacts` deliberately
# refuses to hold: `aggregated` and `projected` are facts about a column but constrain nothing, so
# they are not here. Widening this set is the one direction that manufactures false confidence —
# every addition can only turn a red green — so an addition has to be argued here, in the open.
SATISFYING = frozenset({"filtered", "joined", "grouped", "collapsed"})


def _flag_pins(expected: dict, stmts: list, n_sql: int) -> dict:
    """UNIVERSAL over answering statements, EXISTENTIAL over satisfying forms.

    That asymmetry is the whole point. A probe that happens to constrain an axis cannot cover for
    an answering statement that does not (universal), while any ONE of the four prescribed pinning
    forms discharges the axis in the statement that used it (existential). A ``GROUP BY`` in a CTE
    feeding a ``SUM`` in a DIFFERENT statement is caught, because that other statement is scored on
    its own roles.

    ``stmts`` is the shared fact sheet ``evaluate`` parsed once (empty when there is no SQL or no
    parser); the two branches below still distinguish those cases from each other, because "no SQL
    ran" and "we could not read the SQL" are different findings and must never render alike.
    """
    pins = _str_list(expected.get("must_pin"), lower=True)
    evidence = {
        "pins": pins,
        "n_sql": n_sql,
        "answering_statements": [],
        "per_statement": [],
        "statements": [],
        "parse_errors": [],
    }

    if not pins:
        return _flag("pins", "na", "the oracle names no axes to pin", evidence)
    if not _sqlfacts.available():
        # NEVER `pass`, NEVER `fail`. Without the parser there is no fact sheet at all, and an
        # absent fact sheet can neither exonerate nor convict. `sqlglot` is declared in
        # requirements.txt precisely because this flag is graded, not decorative.
        return _flag("pins", "unchecked", "sqlglot unavailable; SQL not parsed", evidence)
    if n_sql == 0:
        # `na`, NOT `pass`. A question that ran no SQL constrained no axis; rendering that green
        # is the overclaim — four green pins on a correct refusal — this whole model exists to
        # prevent. It is also not a `fail`: a correct refusal SHOULD run nothing.
        return _flag("pins", "na", "no SQL executed", evidence)

    by_index = {s["index"]: s for s in stmts}
    bad = [s for s in stmts if not s.get("ok")]
    evidence["parse_errors"] = [{"stmt": s["index"], "error": s.get("error")} for s in bad]
    if bad:
        # A PARSE FAILURE YIELDS `unchecked`. Never pass, never fail. One statement we cannot read
        # means we do not know which axes the run constrained, and a partial fact sheet that
        # reported `pass` would be a green bought with ignorance.
        return _flag(
            "pins",
            "unchecked",
            f"{_de(len(bad))} of {_de(len(stmts))} statements did not parse",
            evidence,
        )

    answering = _sqlfacts.answering_indexes(stmts, pins)
    evidence["answering_statements"] = list(answering)
    # The fact chips the SQL section renders per statement (spec §7.5 g) come from here, so the
    # page never re-derives a role in JavaScript.
    evidence["statements"] = [
        {
            "stmt": s["index"],
            "answering": s["index"] in answering,
            "roles": s.get("roles") or {},
            "aggregates": s.get("aggregates") or [],
            "relations": s.get("relations") or [],
        }
        for s in stmts
    ]
    if not answering:
        return _flag("pins", "unchecked", "no answering statement identified", evidence)

    misses: list[dict] = []
    for i in answering:
        stmt = by_index.get(i) or {}
        roles = stmt.get("roles") or {}
        satisfied: dict[str, list] = {}
        missing: list[dict] = []
        for column in pins:
            found = set(roles.get(column) or [])
            hit = sorted(found & SATISFYING)
            if hit:
                satisfied[column] = hit
            else:
                # Carry what the statement DID do with the column (or nothing at all), so the
                # detail card can name what the statement did instead — "not constrained; the
                # statement restricted a neighbouring column to a literal list" — rather than
                # showing a bare cross with nothing behind it.
                entry = {"column": column, "roles_found": sorted(found)}
                missing.append(entry)
                misses.append({"column": column, "stmt": i})
        evidence["per_statement"].append({"stmt": i, "satisfied": satisfied, "missing": missing})

    if not misses:
        k = _de(len(pins))
        n = len(answering)
        return _flag(
            "pins",
            "pass",
            f"{k} of {k} axes constrained in {_de(n)} answering statement{'' if n == 1 else 's'}",
            evidence,
        )

    columns = sorted({m["column"] for m in misses})
    shown = ", ".join(columns[:3])
    if len(columns) > 3:
        shown += f" +{_de(len(columns) - 3)} more"
    hurt = len({m["stmt"] for m in misses})
    return _flag(
        "pins",
        "fail",
        f"{shown} not constrained in {_de(hurt)} of {_de(len(answering))} answering statements",
        evidence,
    )


# --------------------------------------------------------------------------- #
# FLAG 3 — value (§4.3.4 / §4.4.1-§4.4.6): "the number agrees with an independent anchor"
# --------------------------------------------------------------------------- #

# Grouped-number shapes, used ONCE per document to decide which separator is the decimal point.
# Deliberately NOT used to parse both readings: accepting both doubles the candidate set, and
# `27,441` read as de is `27.441`, which would pass a `27.44 ± 0.01` anchor. One locale, one
# reading, one answer.
_EN_GROUPED = re.compile(r"(?<![A-Za-z0-9])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![A-Za-z0-9])")
_DE_GROUPED = re.compile(r"(?<![A-Za-z0-9])\d{1,3}(?:\.\d{3})+(?:,\d+)?(?![A-Za-z0-9])")

# A number token in the headline. The `(?<![A-Za-z0-9])` guard is what stops `Q5` from
# contributing the candidate `5`, and a trailing-digit identifier from contributing its digits.
_TOKEN = re.compile(r"(?<![A-Za-z0-9])[+-]?\d+(?:[.,]\d+)*(?![A-Za-z0-9])")

# An approximate authored value: `~1500000`. The tilde is the author saying "this aggregate is
# live-volatile"; it is honoured as a `disputed` state, never silently rounded into a pass.
_APPROX = re.compile(r"^\s*~\s*[-+0-9]")

# Calendar years are excluded from the candidate set unless the target IS one — "December 2024" in
# a headline is a period, not a reading.
_YEAR_LO, _YEAR_HI = 1900, 2100


def _last_place(value) -> float | None:
    """Half a unit in the last decimal place the author WROTE — the precision of a written number.

    `218814471.66` -> 0.005, `11` -> 0.5, `1504.55` -> 0.005. Returns None for anything that is not
    a plain number, so the caller falls through to its own default. Uses the shortest round-trip
    spelling of the value, which is the one the author typed: `Decimal(str(x))` on a float parsed
    from YAML gives back the literal, not the binary expansion.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        exponent = decimal.Decimal(str(value).strip()).as_tuple().exponent
    except (decimal.InvalidOperation, ValueError):
        return None
    if not isinstance(exponent, int):
        return None
    return float(decimal.Decimal(1).scaleb(exponent) / 2)


def _compare_grid(
    target: dict, result: dict | None, tolerance: float, bundle: str | None = None
) -> tuple[str, str, dict]:
    """A BREAKDOWN REFERENCE against the grid the engine returned — `(state, note, evidence)`.

    WHY THIS EXISTS. Until 2026-10-02 any non-scalar reference returned `na`: "reference value is a
    dict; only scalar targets are graded". Six of the forty-six approved questions on the worked
    bundle are breakdowns, so an eighth of the board was not merely failing but UNMEASURED, and no
    amount of fixing the engine could move it.

    THE REFERENCE DECLARES ITS OWN CONTRACT and this reads it rather than inventing one.
    `{rows, cols, ordered, values}` -- measured on AGG-03, "Show net revenue by customer country":
    `rows: 8`, eight `[country, amount]` pairs, and `ordered: false`. The engine returned the same
    eight pairs in a different order with more decimal places (13360672.60516 against an approved
    13360672.61), which is an agreement and was reported as ungradeable.

    WHAT IS CHECKED, in order, stopping at the first real disagreement:
      * `rows`   -- the count, exactly. A breakdown with the wrong number of groups is wrong even
                    if every group it does return is right.
      * `values` -- every approved row must be PRESENT. Numbers compare within `tolerance`, so a
                    rounded reference matches full precision; everything else compares as folded
                    text. `ordered: true` compares position by position instead.
    An unexpected EXTRA row is a disagreement too: the engine returning nine groups where eight
    were approved is not a pass, and `rows` catches it.
    """
    ev: dict = {"compared": "grid", "tolerance": tolerance}
    rows_actual = (result or {}).get("sample_rows")
    want_rows = target.get("rows")
    if isinstance(want_rows, int):
        got = (result or {}).get("rows")
        ev["rows"] = {"approved": want_rows, "produced": got}
        if got != want_rows:
            return (
                "fail",
                f"the approved breakdown has {want_rows} row(s); the engine produced {got}",
                ev,
            )
    want_values = target.get("values")
    if not isinstance(want_values, list) or not want_values:
        # A row COUNT alone is a complete contract, and this is the only check it asks for.
        return ("pass", f"the approved breakdown's {want_rows} row(s) came back", ev)
    if not isinstance(rows_actual, list):
        return ("fail", "the approved breakdown lists values and the capture carries no rows", ev)

    def cell_eq(a, b) -> bool:
        na, nb = _num_or_none(a), _num_or_none(b)
        if na is not None and nb is not None:
            return abs(na - nb) <= max(tolerance, abs(na) * 5e-9)
        # A CODE AND ITS LABEL ARE ONE THING, and the bundle says which. `name_register` is a
        # closed vocabulary (`code | common | legal | long`) that nothing read until 2026-10-02.
        # MEASURED on AGG-10: approved `["US", 111862187.56]` against produced
        # `["United States", 111862187.56017]` -- the numbers agree to the cent, and
        # `country_name` is ruled `label_of: country_code` with `register: long` (operator ruling,
        # 2026-09-30), which the planner honours exactly by grouping on the code and DISPLAYING
        # the label. Engine right, reference right, grader blind.
        return _registers.same_thing(bundle, a, b) if bundle else (
            " ".join(str(a).split()).casefold() == " ".join(str(b).split()).casefold()
        )

    def row_eq(a, b) -> bool:
        return len(a) == len(b) and all(cell_eq(x, y) for x, y in zip(a, b, strict=False))

    if target.get("ordered"):
        for n, (want, got) in enumerate(zip(want_values, rows_actual, strict=False)):
            if not row_eq(list(want), list(got)):
                ev["first_mismatch"] = {"at": n, "approved": want, "produced": got}
                return ("fail", f"row {n} differs: approved {want}, produced {got}", ev)
        return ("pass", f"all {len(want_values)} approved row(s) matched, in order", ev)

    remaining = [list(r) for r in rows_actual]
    missing = []
    for want in want_values:
        hit = next((i for i, got in enumerate(remaining) if row_eq(list(want), got)), None)
        if hit is None:
            missing.append(want)
        else:
            remaining.pop(hit)
    if missing:
        ev["missing"] = missing[:5]
        return (
            "fail",
            f"{len(missing)} approved row(s) absent from the answer, first: {missing[0]}",
            ev,
        )
    return ("pass", f"all {len(want_values)} approved row(s) present (order not required)", ev)


def _flag_value(
    expected: dict,
    anchor: dict | None,
    advisory: list,
    answer_text: str,
    produced_result: bool = True,
    reference: dict | None = None,
    #: The capture's `result` block -- `{value, cols, rows, sample_rows, status}`. Needed because a
    #: BREAKDOWN reference is compared against the grid, and `answer_text` is only the headline.
    result: dict | None = None,
    #: The bundle root — needed to READ its naming registers, so a code and its label are not
    #: counted as two different answers. See `sdk/acceptance/registers.py`.
    bundle: str | None = None,
) -> dict:
    advisory_ids = [a.get("_anchor_id") for a in advisory if a.get("_anchor_id")]
    anchor_expected = (anchor or {}).get("expected") or {}
    evidence: dict = {
        "anchor_id": (anchor or {}).get("_anchor_id"),
        "anchor_file": (anchor or {}).get("_file"),
        "link_mode": (anchor or {}).get("_link_mode"),
        "advisory_anchor_ids": advisory_ids,
    }

    # --- 4.4.1 target selection -----------------------------------------------------------
    # THE APPROVED ANSWER IS THE FIRST TARGET, ahead of the oracle and the anchor. It is the only
    # one of the three that a PERSON signed, and guardrails/strategy.yaml stage 9 rules it the
    # verdict: "the SME approves the answer; pass/fail is the only verdict, and the approved number
    # is the reference". An oracle is derived and an anchor is independent; neither is authority.
    ref_value = (reference or {}).get("expected")
    raw = expected.get("value")
    if ref_value is not None:
        source, target_raw = "reference", ref_value
        tol_raw = (reference or {}).get("tolerance")
        # AN APPROVED NUMBER IS PRECISE TO THE PLACE IT WAS WRITTEN TO, and nothing else states
        # that. A person who approves `218814471.66` has approved every figure that rounds to it;
        # the warehouse's own value is 218814471.65866 and the anchor carries it in full. With an
        # absent tolerance read as EXACT, that approval failed against the number it approves — five
        # of them did on contoso5 (AGG-01, AGG-05, AGG-06, AGG-07, AGG-14, 2026-09-30), each
        # reporting `Δ 0,00`, which is a grader disagreeing with itself in print.
        #
        # So an absent tolerance on a REFERENCE means "to the last place written": half a unit in
        # it. `218814471.66` gives ±0.005, `11` gives ±0.5, and neither admits a wrong answer — the
        # colour disagreements on this board (RC03 17 vs 16, MQ-02 17 vs 21, MQ-06 1494.79 vs
        # 1504.55) all stay red. This is NOT the relative floor the note below refuses: it is the
        # precision the approver wrote, read off their own number, and it is recorded in evidence.
        evidence.update(
            reference_approved_by=(reference or {}).get("approved_by"),
            reference_approved_at=_plain((reference or {}).get("approved_at")),
        )
    elif _is_numeric_target(raw):
        source, target_raw = "oracle", raw
        tol_raw = expected.get("tolerance")
    elif anchor is not None and anchor_expected.get("value") is not None:
        # NOTE the asymmetry with the branch above, and keep it: the ORACLE is only consulted for a
        # scalar, but ANY authored anchor value is taken as the target so the shape gate below can
        # say `na` with the real reason. Skipping a dict/series anchor here instead would report
        # "no independent anchor" on a question that has one, and an empty-list anchor would
        # vacuously satisfy `all(...)` and PASS.
        source, target_raw = "anchor", anchor_expected.get("value")
        tol_raw = anchor_expected.get("tolerance")
    else:
        return _flag(
            "value",
            "na",
            "no approved reference and no independent anchor for this question",
            {**evidence, "source": None},
        )

    # --- 4.4.1b THERE MUST BE AN ANSWER TO GRADE ---------------------------------------------
    # A clarification's headline is PROSE, and this scans a headline for numbers. Measured
    # 2026-09-24: "I'm not confident I understood ... (self-score 0.30, threshold 0.50)" yielded
    # the candidate 0.50, which was then graded against the anchor and FAILED — three false value
    # failures on one board run, each reading "headline reads 0,50". The engine had not answered
    # at all; declining is the `outcome`/HUMILITY axis, and reporting it as a wrong NUMBER blames
    # it for a number it never produced.
    if not produced_result:
        return _flag(
            "value",
            "na",
            "the engine produced no result to grade (a clarification or refusal is scored on "
            "`outcome`, not here)",
            {**evidence, "source": source},
        )

    evidence["source"] = source
    tolerance = _num_or_none(tol_raw)
    # ABSENT TOLERANCE DEFAULTS TO 0 AND 0 MEANS EXACT. The deleted grader widened every band with
    # `max(tol, target * 0.005)`, which on a 5.000 anchor accepts a +25 error — a false green,
    # strictly worse than the false red it was covering for. There is no relative floor here and
    # none is to be reintroduced.
    evidence["tolerance_default"] = tolerance is None
    tolerance = 0.0 if tolerance is None else abs(tolerance)
    evidence["tolerance"] = tolerance

    # --- 4.4.2 target shape gate ------------------------------------------------------------
    # A BREAKDOWN IS COMPARED, NOT WAIVED. This returned `na` for every non-scalar reference, which
    # made six of the worked bundle's forty-six approved questions permanently unmeasurable -- see
    # `_compare_grid`, which reads the contract the reference itself declares.
    if isinstance(target_raw, dict) and ("rows" in target_raw or "values" in target_raw):
        state, note, grid_ev = _compare_grid(target_raw, result, tolerance, bundle)
        return _flag(
            "value",
            state,
            note,
            {**evidence, "target": None, "authored_value": _plain(target_raw), **grid_ev},
        )
    if isinstance(target_raw, (dict, list, tuple)):
        kind = "dict" if isinstance(target_raw, dict) else "series"
        return _flag(
            "value",
            "na",
            f"{source} value is a {kind} with neither `rows` nor `values`; nothing states what to "
            f"compare",
            {**evidence, "target": None, "authored_value": _plain(target_raw)},
        )

    approximate = False
    if isinstance(target_raw, str) and _APPROX.match(target_raw):
        approximate = True
        target = _num_or_none(target_raw.strip().lstrip("~").strip())
    else:
        target = _num_or_none(target_raw)

    if target is None:
        # A NON-NUMERIC APPROVED ANSWER IS STILL AN ANSWER, and until 2026-10-02 it was ungradeable
        # by construction: anything `_num_or_none` could not parse returned `na`, so a DATE, a name
        # or a code could never pass or fail.
        #
        # MEASURED on STORE-04, "When was the first store closed?": the operator approved
        # `2013-12-05` on 2026-09-30, the engine now answers `MIN(dim_store.close_date)` =
        # 2013-12-05, and the board said `value: na — reference value is not numeric`. Two identical
        # answers reported as not comparable.
        #
        # SO IT IS COMPARED AS TEXT, EXACTLY. The approved string must appear in the answer verbatim
        # once case and surrounding whitespace are folded -- no stemming, no date reformatting, no
        # partial credit. That keeps the comparison honest in both directions: an ISO date, a store
        # name or a country code either appears as approved or it does not, and `na` stops hiding a
        # question from the board. A bool target is still `na`: `True` is not an answer a reader
        # approved, and matching the word "true" in prose would be an accident.
        if isinstance(target_raw, bool) or not isinstance(target_raw, str) or not target_raw.strip():
            return _flag(
                "value",
                "na",
                f"{source} value is neither a number nor text that could be matched",
                {**evidence, "target": None, "authored_value": _plain(target_raw)},
            )
        wanted = " ".join(target_raw.split()).casefold()
        haystack = " ".join(str(answer_text or "").split()).casefold()
        found = wanted in haystack
        return _flag(
            "value",
            "pass" if found else "fail",
            (
                f"the approved {source} value {target_raw.strip()!r} appears in the answer"
                if found
                else f"the approved {source} value {target_raw.strip()!r} does not appear in the answer"
            ),
            {
                **evidence,
                "target": None,
                "authored_value": _plain(target_raw),
                "compared": "text",
                "matched": found,
            },
        )

    evidence["target"] = target
    evidence["approximate"] = approximate
    agree = ((anchor or {}).get("derivation") or {}).get("agree")
    evidence["agree"] = agree

    # --- 4.4.3 locale, resolved ONCE per document -------------------------------------------
    en_hits = len(_EN_GROUPED.findall(answer_text))
    de_hits = len(_DE_GROUPED.findall(answer_text))
    locale = "en" if en_hits > de_hits else "de" if de_hits > en_hits else "unknown"
    evidence.update(locale=locale, en_hits=en_hits, de_hits=de_hits)

    # --- 4.4.4 headline scope ---------------------------------------------------------------
    headline = _headline(answer_text)
    evidence["headline"] = headline

    # --- 4.4.5 candidates -------------------------------------------------------------------
    candidates, ambiguous = _candidates(headline, locale, target)
    evidence.update(candidates=candidates, ambiguous_skipped=ambiguous)

    # A COMPARISON CANNOT BE FINER THAN EITHER NUMBER IN IT. Both sides of this test are WRITTEN:
    # the target by whoever approved or derived it, the candidate by the presenter that put it in a
    # headline. Comparing them beyond the coarser of those two precisions asks a question neither
    # number can answer.
    #
    # MEASURED THREE TIMES IN ONE DAY, 2026-09-30, and the third is why this is now ONE rule over
    # BOTH sources instead of a special case per source:
    #   * AGG-01 and four others: reference 218814471.66, engine 218814471.65866, tolerance absent
    #     and read as EXACT -> five approvals failed against the figures they approve.
    #   * AGG-13: reference 1.0630080400657742, headline printed "1,06" -> failed on the presenter's
    #     rounding.
    #   * MQ-06: ANCHOR_18 derives 1 511,75 by `round(avg(...),2)` and DECLARES `tolerance: 0`; the
    #     engine answers 1 511,7543859649122. The board printed "headline reads 1.511,75; ANCHOR_18
    #     derives 1.511,75 (Δ 0,00)" and FAILED it. A declared 0 against a value rounded to cents is
    #     unsatisfiable by construction, so "exact" can only mean "exact at the precision written".
    #
    # NOT A RELATIVE FLOOR, and it cannot hide a wrong answer: the band is half a unit in the last
    # place someone actually wrote. A tighter DECLARED tolerance still wins where the target carries
    # the precision to support it (ANCHOR_01's 1e-05 against 218814471.65866 is untouched), and every
    # real disagreement on this board stays red with room to spare — 17 against 21, 1 494,79 against
    # 1 511,75, 0,11 against 11,26.
    written = [_last_place(target_raw)] + [_last_place(str(c)) for c in candidates]
    coarsest = max([p for p in written if p is not None] or [0.0])
    if coarsest > tolerance:
        evidence["tolerance_from"] = (
            f"the coarser of the two written precisions ({_de(coarsest)}): a comparison cannot be "
            f"finer than either number in it"
            + (f", where the declared tolerance is {_de(tolerance)}" if tolerance else "")
        )
        tolerance = coarsest
        evidence["tolerance"] = tolerance
    best = min(candidates, key=lambda c: abs(c - target)) if candidates else None
    delta = abs(best - target) if best is not None else None
    evidence["matched"] = None
    evidence["delta"] = delta

    # --- 4.4.6 verdict ----------------------------------------------------------------------
    if approximate or (anchor is not None and agree is not True):
        # DISPUTED: never pass, never fail, rolls up to `unproven`. The anchor self-reports that
        # its two derivations did not meet, or the author wrote the value as approximate. Rendering
        # that `na` would hide the corpus's most interesting measured disagreement; rendering it
        # `fail` would blame the engine for the anchor's own instability.
        if best is None:
            return _flag(
                "value",
                "disputed",
                "anchor self-reports as unstable; no number found in the answer headline",
                evidence,
            )
        return _flag(
            "value",
            "disputed",
            f"anchor self-reports as unstable; observed {_de(best)} vs anchor "
            f"{_de(target)} (Δ {_de(delta)})",
            evidence,
        )

    if not candidates and ambiguous:
        return _flag(
            "value", "unchecked", "number formatting in the answer is locale-ambiguous", evidence
        )
    if not candidates:
        # NOT `fail`. We could not find a number; that is not evidence the number is wrong. And
        # NOT `pass` on the strength of a number further down the page — the headline is the scope.
        return _flag("value", "unchecked", "no number found in the answer headline", evidence)

    hit = next((c for c in candidates if abs(c - target) <= tolerance), None)
    # WHAT IT COMPARED AGAINST, by name. This read `anchor_id or "the oracle"`, so an APPROVED
    # REFERENCE was reported as the oracle's doing or the anchor's — RC01 passed with "11 matches
    # the oracle" when what it matched was the operator's approval (2026-09-30).
    label = (
        f"the approved reference"
        + (f" ({evidence['reference_approved_by']})" if evidence.get("reference_approved_by") else "")
        if source == "reference"
        else (evidence["anchor_id"] or "the oracle")
    )
    if hit is not None:
        evidence["matched"] = hit
        evidence["delta"] = abs(hit - target)
        return _flag(
            "value", "pass", f"{_de(hit)} matches {label} (tolerance {_de(tolerance)})", evidence
        )
    return _flag(
        "value",
        "fail",
        f"headline reads {_de(best)}; {label} derives {_de(target)} (Δ {_de(delta)})",
        evidence,
    )


# --------------------------------------------------------------------------- #
# FLAG 4 — rules: "no never-clause the ONTOLOGY states was broken by this SQL"
# --------------------------------------------------------------------------- #
#
# WHAT THIS FLAG MAY AND MAY NOT CLAIM
#     A MAC rule is ``{id, subject, kind, binds, when, then, never}``. Only ``binds`` is
#     machine-readable — CONFORMANCE.md defines a typed rule as "anchored to the field(s) they
#     govern", and the framework shape ``rule-binds-grounded`` enforces cross-file that every bound
#     name is a column of the concept's grounded table. ``never`` is PROSE.
#
#     So this flag decides exactly one kind of question: does a BOUND COLUMN carry a structural
#     ROLE the clause forbids? Two clause forms reduce to that, and they are written out below as a
#     grammar rather than inferred. Everything else is `unchecked`, with the clause carried
#     verbatim into the evidence and a reason naming what could not be decided. Measured on the
#     reference ontology: 83 never-clauses, 9 checkable, 74 not.
#
#     A THIRD FORM WAS TRIED AND REJECTED: deriving the prohibition from `then` (the columns a rule
#     PRESCRIBES) and treating everything else in `binds` as forbidden. It is unsound — the rule
#     `product.read.flat_property` binds five property columns and its `then` names one, so
#     the other four would be reported as forbidden by a rule that exists to permit reading them.
#     Do not reintroduce it: this flag can only turn a green into a red, so every widening here has
#     to be argued in the open, and that one is wrong.

# The em dash separates the PROHIBITION from its rationale in every authored clause seen. Only the
# prohibition half is scanned for the forbidden thing; scanning the rationale would pick up columns
# an author named to explain the rule — which are, precisely, the SANCTIONED ones.
_EM_DASH = "—"

# FORM 1 — a key-use prohibition: "... as a join key", "... as the key", "... as the identity",
# "... as the primary identity source". Deliberately anchored on "as <article> ... key|identity":
# a looser trigger ("key" anywhere) fires on every rationale that explains what a key is.
_KEY_USE = re.compile(
    r"\bas\s+(?:a|an|the)\s+(?:[\w-]+\s+){0,3}(?:key|keys|identity|identifier)\b", re.I
)

# Whether that prohibition is qualified as a JOIN key specifically. It matters, and the ontology
# says so out loud: one rule forbids matching a label "as a join key" while its own `then` permits
# the same label as a "filter-by-code convenience". Reading the qualifier is the difference between
# checking what was authored and inventing a stricter rule than the author wrote.
_JOIN_QUALIFIED = re.compile(r"\bjoin(?:ing|ed)?[\s-]*key\b", re.I)

# FORM 2 — an aggregate-across prohibition: "SUMming value across role", "SUMming or AVERAGing X
# across Y". The measure is named before "across", the axes after it.
_AGG_WORD = re.compile(r"\b(?:sum|sums|summing|summed|averag(?:e|es|ed|ing)|avg)\b", re.I)
_ACROSS = re.compile(r"\bacross\b", re.I)

# Which structural roles amount to USING a column as a key. `grouped` and `collapsed` are NOT here:
# a GROUP BY on a display label is a breakdown, and `projected` is a column being SHOWN — reading a
# name out to a human is what display names are for, and no clause in the reference ontology
# forbids it. Only a predicate (`filtered`) or a join equality (`joined`) matches on a value.
KEY_ROLES = frozenset({"filtered", "joined"})
JOIN_ROLES = frozenset({"joined"})


def _clause_parts(never: str) -> tuple:
    """``(prohibition, rationale)`` — the clause split at its first em dash, whitespace-normalised."""
    text = " ".join(str(never or "").split())
    head, _, tail = text.partition(_EM_DASH)
    return head.strip(), tail.strip()


def _mentions(column: str, text: str) -> bool:
    """True when ``text`` names ``column`` as a whole identifier.

    The underscore guards are load-bearing: ``acme_raw_package_type`` must match inside "the
    acme_raw_package_type label string" and must NOT match inside ``acme_raw_package_type_id``, which is the
    column the same rule prescribes. A substring test would forbid the prescribed key.
    """
    if not column:
        return False
    return (
        re.search(rf"(?<![A-Za-z0-9_]){re.escape(column)}(?![A-Za-z0-9_])", text, re.I) is not None
    )


def _sanctions(column: str, text: str) -> bool:
    """True when ``text`` names ``column`` as a PERMITTED key: "<col> is the <...> key|identity"."""
    if not column:
        return False
    return (
        re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(column)}(?![A-Za-z0-9_])\s+is\s+(?:a|an|the)\s+"
            rf"(?:[\w-]+\s+){{0,3}}(?:key|identity)\b",
            text,
            re.I,
        )
        is not None
    )


def _classify_never(rule: dict) -> dict:
    """One rule -> what, if anything, its never-clause can be checked for. Pure, text in, dict out.

    Returns ``{"form": "identity"|"additivity"|None, "reason": str, ...}``. ``form is None`` means
    UNCHECKED and ``reason`` says why in words an operator can act on — that reason is rendered on
    the card, so "most of them are prose" is a visible measurement rather than a silent absence.
    """
    binds = [c for c in (rule.get("binds") or []) if isinstance(c, str) and c]
    prohibition, rationale = _clause_parts(rule.get("never"))

    if not binds:
        return {"form": None, "reason": "the rule binds no column, so no structural claim is made"}

    # --- FORM 1: key use ------------------------------------------------------------------
    key_use = _KEY_USE.search(prohibition)
    if key_use:
        # THE FORBIDDEN OPERAND PRECEDES THE KEY PHRASE, and only that span is scanned. What follows
        # it is a condition or an aside, and it routinely names the PRESCRIBED column: "matching on
        # the <label> string as a join key WHEN THE ID IS AVAILABLE". A bound column called `id`
        # would otherwise be swept into the forbidden set by the very clause that prescribes it, and
        # a legitimate join on it reported as a violation. Positional, not semantic.
        operand = prohibition[: key_use.start()]
        # The qualifier is read out of the MATCHED PHRASE, not the whole clause: "join" elsewhere in
        # a sentence says nothing about which key use this clause forbids.
        roles = JOIN_ROLES if _JOIN_QUALIFIED.search(key_use.group(0)) else KEY_ROLES
        named = [c for c in binds if _mentions(c, operand)]
        if named:
            return {
                "form": "identity",
                "basis": "named",
                "columns": named,
                "roles": sorted(roles),
                "sanctioned": [],
                "reason": "the clause names the column it forbids as a key",
            }

        # THE ONE INFERENCE THIS MODULE MAKES, AND IT IS LABELLED AS ONE. When the prohibition
        # names no column but the rationale enumerates the SANCTIONED ones ("name_key is the
        # search key, acme_product_code is the stable identity"), the governed set closes: `binds` is
        # by MAC's own definition the set of fields the rule governs, so a governed column the
        # clause does not sanction is not a sanctioned key under this rule. Evidence carries
        # `basis: "governed-set closure"` and the sanctioned list, so a reader can see the
        # reasoning and reject it without reading this file.
        sanctioned = [c for c in binds if _sanctions(c, rationale)]
        rest = [c for c in binds if c not in sanctioned]
        if sanctioned and rest:
            return {
                "form": "identity",
                "basis": "governed-set closure",
                "columns": rest,
                "roles": sorted(roles),
                "sanctioned": sanctioned,
                "reason": "the clause sanctions specific bound columns as keys; the rest of "
                "the governed set is not sanctioned",
            }
        return {
            "form": None,
            "reason": "the clause forbids a key use it describes in prose, naming no bound "
            "column and sanctioning none",
        }

    # --- FORM 2: aggregate across an axis --------------------------------------------------
    if _AGG_WORD.search(prohibition) and _ACROSS.search(prohibition):
        head, _, tail = re.split(r"(\bacross\b)", prohibition, maxsplit=1, flags=re.I)
        measures = [c for c in binds if _mentions(c, head)]
        axes = [c for c in binds if _mentions(c, tail)]
        if not axes:
            return {
                "form": None,
                "reason": "the clause forbids aggregating across an axis it names in prose, "
                "not as a bound column",
            }
        return {
            "form": "additivity",
            "basis": "named",
            "axes": axes,
            "measures": measures,
            "reason": "the clause names the axis it forbids aggregating across",
        }

    return {
        "form": None,
        "reason": "the clause is prose; it states no structural claim about a bound column",
    }


def _clause_violations(clause: dict, stmts: list) -> list:
    """Every statement in which ``clause``'s prohibition is broken. Facts only, no judgement.

    CHECKED OVER EVERY STATEMENT, NOT ONLY THE ANSWERING ONES — the opposite of ``pins``, and
    deliberately. ``pins`` asks whether the statement that COMPUTED the answer constrained the
    axes, so demanding it of a dimension probe would be nonsense. A never-clause is a prohibition:
    the ontology does not say "do not match the display name in the statement that answers", it
    says do not match it. ``ACME_C1.1`` breaks it in a CTE and in a probe, and both are the same
    defect.
    """
    out: list = []
    for stmt in stmts:
        if not stmt.get("ok"):
            continue
        roles = stmt.get("roles") or {}

        if clause["form"] == "identity":
            forbidden = frozenset(clause["roles"])
            for column in clause["columns"]:
                hit = sorted(set(roles.get(column) or []) & forbidden)
                if hit:
                    out.append({"stmt": stmt["index"], "column": column, "roles": hit})
            continue

        # additivity: the axis has to be constrained in any statement that aggregates a measure.
        axes = set(clause["axes"])
        measures = set(clause["measures"])
        aggs = [a for a in (stmt.get("aggregates") or []) if a.get("func") in ("SUM", "AVG")]
        if measures:
            firing = [a for a in aggs if measures & set(a.get("args") or [])]
        else:
            # The clause named the measure in prose ("SUMming value across role" on a rule that
            # binds only the axes). Fall back to the same test `sqlfacts.answering_indexes` already
            # uses for "this statement computes a measure": a SUM/AVG over something that is not
            # itself one of the axes. `SUM(<axis>)` and `SUM(1)` compute no measure.
            firing = [a for a in aggs if any(name not in axes for name in (a.get("args") or []))]
        if not firing:
            continue
        for column in clause["axes"]:
            if not (set(roles.get(column) or []) & SATISFYING):
                out.append(
                    {
                        "stmt": stmt["index"],
                        "column": column,
                        "roles": sorted(roles.get(column) or []),
                        "aggregates": sorted({a["func"] for a in firing}),
                    }
                )
    return out


def _flag_rules(concept_rules, stmts: list, n_sql: int) -> dict:
    """Did the executed SQL break a never-clause of a concept rule bound to this question's route?

    ROUTE BINDING IS STRUCTURAL: a rule is bound when the run READ a relation its concept is
    grounded on. A rule about a relation the query never touched cannot have been broken by it, and
    binding by anything softer (the question's text, the oracle's family) would be a second routing
    opinion computed in the grader.

    STATES
        ``na``        — nothing to check here: no rules in the ontology, no SQL executed, or no
                        concept grounded on the relations this run read. Never ``pass``: a question
                        that ran nothing broke nothing, and painting that green is the overclaim.
        ``unchecked`` — the check applies but could not be decided: no parser, a statement that did
                        not parse, or every bound clause is prose. An incomplete fact sheet can
                        neither exonerate nor convict.
        ``pass``      — at least one clause was decided and none was violated. The reason states
                        BOTH counts, so a green square never implies the prose clauses were covered.
        ``fail``      — a decided clause was violated, with the statement and the role that broke it.
    """
    rules = [r for r in (concept_rules or []) if isinstance(r, dict)]
    evidence: dict = {
        "n_sql": n_sql,
        "relations": [],
        "ontology_rules": len(rules),
        "bound": [],
        "checked": [],
        "unchecked": [],
        "violations": [],
    }

    if not rules:
        return _flag(
            "rules", "na", "the ontology states no concept rule with a never-clause", evidence
        )
    if n_sql == 0:
        return _flag(
            "rules", "na", "no SQL executed; no rule about reading the model applies", evidence
        )
    if not _sqlfacts.available():
        return _flag("rules", "unchecked", "sqlglot unavailable; SQL not parsed", evidence)

    bad = [s for s in stmts if not s.get("ok")]
    if bad:
        evidence["parse_errors"] = [{"stmt": s["index"], "error": s.get("error")} for s in bad]
        return _flag(
            "rules",
            "unchecked",
            f"{_de(len(bad))} of {_de(len(stmts))} statements did not parse",
            evidence,
        )

    relations = sorted({r for s in stmts for r in (s.get("relations") or [])})
    evidence["relations"] = relations
    bound = [r for r in rules if set(r.get("relations") or []) & set(relations)]
    evidence["bound"] = [r.get("id") for r in bound]
    if not bound:
        return _flag(
            "rules", "na", "no concept is grounded on the relations this run read", evidence
        )

    violations: list = []
    for rule in bound:
        clause = _classify_never(rule)
        card = {
            "rule": rule.get("id"),
            "concept": rule.get("concept"),
            "never": rule.get("never"),
            "binds": list(rule.get("binds") or []),
            "file": rule.get("file"),
            "reason": clause["reason"],
        }
        if clause["form"] is None:
            evidence["unchecked"].append(card)
            continue
        card.update(
            form=clause["form"],
            basis=clause.get("basis"),
            columns=clause.get("columns") or clause.get("axes") or [],
            roles=clause.get("roles") or sorted(SATISFYING),
            measures=clause.get("measures", []),
            sanctioned=clause.get("sanctioned", []),
        )
        broke = _clause_violations(clause, stmts)
        card["violations"] = broke
        evidence["checked"].append(card)
        for hit in broke:
            violations.append(
                {
                    **hit,
                    "rule": rule.get("id"),
                    "concept": rule.get("concept"),
                    "form": clause["form"],
                    "basis": clause.get("basis"),
                    "never": rule.get("never"),
                }
            )

    evidence["violations"] = violations
    n_checked, n_unchecked = len(evidence["checked"]), len(evidence["unchecked"])

    if violations:
        first = violations[0]
        return _flag(
            "rules",
            "fail",
            f"{_de(len(violations))} never-clause violations; "
            f"{first['rule']} broken by {first['column']}",
            evidence,
        )
    if not n_checked:
        # EVERY BOUND CLAUSE IS PROSE — `na`, because there is nothing here a machine can check, and
        # that is the same thing the three `na` branches above say. It was `unchecked`, on the
        # reasoning that "the check applies, we simply cannot decide it", and the cost of that word
        # was the whole board: `unchecked` vetoes a row's verdict, and a prose never-clause is
        # undecidable BY CONSTRUCTION — no bundle in this estate has ever had a machine-checkable
        # one. Measured on contoso5, 2026-09-30: 38 of 48 run rows carried this state, ALL of them
        # for this one reason and none for a parse failure, so no question could ever be `proven`
        # however many times a person ran it, read it and approved it. RC01 was approved at 11,
        # answered 11, matched its reference and the board said `unproven`. The operator, repeatedly:
        # "questions that were proven and verified are not marked properly".
        #
        # `unchecked` KEEPS ITS TEETH for the cases it was written for — no parser, or a statement
        # that did not parse — where something checkable went unchecked and the row SHOULD be held
        # back. Those are still above this branch, and they still veto.
        #
        # STILL NOT `pass`: nothing was verified, and the reason says so with both counts, so a grey
        # square never implies the prose clauses were covered.
        return _flag(
            "rules",
            "na",
            f"all {_de(n_unchecked)} bound never-clauses are prose; none is machine-checkable, so "
            f"there is nothing here a machine can decide",
            evidence,
        )
    return _flag(
        "rules",
        "pass",
        f"{_de(n_checked)} of {_de(n_checked + n_unchecked)} bound never-clauses "
        f"checked; none violated",
        evidence,
    )


# --------------------------------------------------------------------------- #
# ROLLUP (§4.3.5)
# --------------------------------------------------------------------------- #


def _rollup(flags: list) -> str:
    """First match wins, in this exact order.

    The load-bearing consequence, which a test pins: a question whose ``value`` flag is ``na`` can
    NEVER be ``proven``, for any combination of the others. ``proven`` requires ``value`` to have
    actually PASSED. Everything that merely routed correctly lands on ``routed`` — sky, never
    emerald, because nothing in the bundle can prove its number and saying otherwise is the
    overclaim.

    ``unchecked`` VETOES, AND IT IS MEANT TO: a square that could not be decided holds the row back,
    because a verdict over an incomplete fact sheet is an assertion nobody measured. That veto was
    right and its INPUT was wrong. Measured on contoso5, 2026-09-30: 38 of 48 run rows carried
    ``rules: unchecked``, every one of them because "all bound never-clauses are prose", which is
    true of every rule in every bundle in this estate — so no question could ever be ``proven``
    however many times a person ran it, read it and approved it. RC01 was approved at 11, answered
    11, matched its reference, and the board said ``unproven``. The operator, repeatedly: "questions
    that were proven and verified are not marked properly ... it is absolutely nerving not to have [a]
    functioning dashboard".

    THE FIX WAS IN THE SQUARE, NOT HERE, and the difference matters. Reordering this ladder so a
    matched number outranks an undecidable square would also have turned the board green — and would
    have hidden the cases the veto exists for: a missing parser, or a statement that did not parse,
    where something CHECKABLE went unchecked. `_flag_rules` now says ``na`` for prose (nothing a
    machine can decide) and keeps ``unchecked`` for those, so the veto still bites exactly where it
    should. Zero of the 38 rows were parse failures; had one been, the reorder would have painted it
    proven.
    """
    states = {f["id"]: f["state"] for f in flags}
    if "fail" in states.values():
        return "failed"
    if {"unchecked", "disputed"} & set(states.values()):
        return "unproven"
    if states.get("value") == "pass":
        return "proven"
    return "routed"


# --------------------------------------------------------------------------- #
# CORPUS-HEALTH WARNINGS (§4.3.6) — claims about the CORPUS, never about the engine
# --------------------------------------------------------------------------- #


def _warnings(
    corpus_row: dict,
    oracle: dict | None,
    answer,
    fingerprint: str,
    ontology_fingerprint: str | None = None,
) -> list:
    """The four contradiction/staleness findings. THEY NEVER MOVE A VERDICT.

    The corpus is mid-migration: one commit flipped 27 oracles' ``expected.outcome`` and
    ``route_reason`` while leaving ``must_surface_any``, ``must_not`` and ``question.text``
    asserting the previous ruling. These lighting up is CORRECT behaviour and the count is the
    measurement. Do not silence one by loosening a check.

    Computed OUTSIDE the precondition ladder on purpose: an unrun question still has a drifted
    oracle, and a board that only reports corpus health for rows that happen to have been captured
    reports the wrong number.
    """
    out: list[dict] = []
    if isinstance(oracle, dict):
        q = oracle.get("question") if isinstance(oracle.get("question"), dict) else {}
        expected = _expected(oracle)

        oracle_text = _grade._norm(q.get("text"))
        corpus_text = _grade._norm(corpus_row.get("question"))
        if oracle_text != corpus_text:
            out.append(
                {
                    "code": "question_text_drift",
                    "detail": f"the oracle judges “{_clip(oracle_text)}”; the corpus asks "
                    f"“{_clip(corpus_text)}”",
                }
            )

        stated = q.get("expected_outcome")
        ruled = expected.get("outcome")
        if stated != ruled:
            out.append(
                {
                    "code": "outcome_contradiction",
                    "detail": f"question.expected_outcome is {stated!r} while "
                    f"expected.outcome rules {ruled!r}",
                }
            )

        # A DIFFERENT contradiction family from the one above, and nothing else detects it: the
        # shape says "refusal" while the outcome commits, or the reverse.
        shape_refusal = expected.get("shape") == "refusal"
        outcome_gate = str(ruled or "").strip().upper() in GATE_OUTCOMES
        if shape_refusal != outcome_gate:
            out.append(
                {
                    "code": "shape_outcome_contradiction",
                    "detail": f"expected.shape is {expected.get('shape')!r} while "
                    f"expected.outcome is {ruled!r}",
                }
            )

    if isinstance(answer, dict):
        stamped = answer.get("acceptance_fingerprint")
        if not stamped:
            out.append(
                {
                    "code": "evidence_stale",
                    "detail": "the capture records no acceptance fingerprint, so what it was "
                    "judged against cannot be established",
                }
            )
        elif stamped != fingerprint:
            out.append(
                {
                    "code": "evidence_stale",
                    "detail": f"captured against acceptance {stamped}; the bundle now reads "
                    f"{fingerprint}",
                }
            )
        # AND THE ONTOLOGY, which is the half that was never compared. A capture is evidence about
        # the DECLARATIONS that produced it: change a population, a value_filter or a concept and
        # the same question would plan differently, so the stored answer is no longer evidence of
        # anything the bundle now says. Checked second so a capture stale on both planes reports
        # both, and skipped entirely when the caller supplies no fingerprint.
        if ontology_fingerprint:
            ont = answer.get("ontology_fingerprint")
            if not ont:
                out.append(
                    {
                        "code": "evidence_stale",
                        "detail": "the capture records no ontology fingerprint, so which "
                        "declarations produced it cannot be established",
                    }
                )
            elif ont != ontology_fingerprint:
                out.append(
                    {
                        "code": "evidence_stale",
                        "detail": f"captured against ontology {ont}; the bundle now reads "
                        f"{ontology_fingerprint} — re-run before trusting this verdict",
                    }
                )
    return out


# --------------------------------------------------------------------------- #
# Small pure helpers
# --------------------------------------------------------------------------- #


def _flag(fid: str, state: str, reason: str, evidence: dict) -> dict:
    """One flag, with its `reason` clipped to the 120-char contract the row tooltip renders."""
    return {"id": fid, "state": state, "reason": reason[:120], "evidence": evidence}


def _expected(oracle) -> dict:
    e = (oracle or {}).get("expected") if isinstance(oracle, dict) else None
    return e if isinstance(e, dict) else {}


def _str_list(value, *, lower: bool = False) -> list:
    """A YAML list reduced to non-blank strings, order preserved, duplicates kept.

    Duplicates are KEPT because `assertion_counts` counts what the author wrote, not what a
    de-duplicating reader wishes they had written.
    """
    if not isinstance(value, (list, tuple)):
        return []
    out = []
    for item in value:
        if not isinstance(item, str):
            continue
        s = item.strip()
        if s:
            out.append(s.lower() if lower else s)
    return out


def _is_error_capture(answer) -> bool:
    """Did this run ERROR? Read from the stages first, then the two legacy top-level keys.

    MEASURED 2026-09-25, and it is the first thing stage recording surfaced: **11 of 77 questions
    failed with a SQL Binder or Parser Error at the execute stage, and this returned False for
    every one of them.** `result.status` was `no_value` and `answer["error"]` was null, so the
    verdict rollup called them `unproven` and the page said "Product: no value returned." — a
    sentence that reads as "the query ran and found nothing" about a query that did not run.

    A PARSER ERROR MEANS WE EMITTED INVALID SQL. A binder error means we named something the
    warehouse does not have. Neither is an absent value, and a grader that cannot tell them apart
    reports our own defects as the data's silence.

    `stages` is the capture's record of what each stage DID, written by the pipeline itself. The
    two legacy keys stay, because captures taken before stages existed carry only those and must
    keep grading exactly as they did.
    """
    if not isinstance(answer, dict):
        return False
    for stage in answer.get("stages") or []:
        if isinstance(stage, dict) and stage.get("status") == "error":
            return True
    result = answer.get("result")
    result = result if isinstance(result, dict) else {}
    return bool(answer.get("error")) or result.get("status") == "error"


def _is_numeric_target(value) -> bool:
    """True for an oracle-authored value that selects the oracle as the target source (§4.4.1.1).

    A ``bool`` is excluded although Python calls it an ``int``: ``True`` is a ruling, not a
    reading. dict / list values fall through to the anchor branch, where the shape gate names them.
    """
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        return _num_or_none(value) is not None or bool(_APPROX.match(value))
    return False


def _num_or_none(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _plain(value):
    """A YAML value reduced to JSON-serialisable primitives for the evidence dict.

    Anchors carry ``datetime.date`` under ``expected.pinned`` and tuples nowhere, but an authored
    document is authored: whatever it holds has to survive `json.dumps` or the whole dashboard
    write fails on one odd key.
    """
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, bool) or value is None or isinstance(value, (int, float, str)):
        return value
    return str(value)


def _headline(text: str) -> str:
    """The FIRST bold span, else the first non-empty paragraph. Nothing else is ever searched.

    Headline-only is the guard that stops an accidental match inside a breakdown table. A committed
    answer typically prints the components of its total below the headline, and a whole-document
    scan would let any of those rows satisfy an anchor by coincidence. When the headline holds no
    candidate the flag is `unchecked` — never `fail` because we could not find a number, and never
    `pass` because one appeared further down.
    """
    body = str(text or "")
    bold = re.search(r"\*\*(.+?)\*\*", body, re.DOTALL)
    if bold:
        return bold.group(1).strip()
    for block in re.split(r"\n\s*\n", body):
        block = block.strip()
        if block:
            return block
    return ""


def _candidates(headline: str, locale: str, target: float) -> tuple[list, int]:
    """Numbers the headline offers, read in ONE locale, with years excluded.

    Returns ``(candidates, ambiguous_skipped)``. A token that cannot be read without knowing the
    document's locale is SKIPPED and counted — never guessed — so the flag reports
    ``unchecked``/locale-ambiguous rather than inventing a reading that might match.
    """
    target_is_year = _YEAR_LO <= target <= _YEAR_HI and float(target).is_integer()
    out: list[float] = []
    ambiguous = 0

    for token in _TOKEN.findall(headline):
        sign = -1.0 if token.startswith("-") else 1.0
        digits = token.lstrip("+-")
        parts = re.split(r"[.,]", digits)
        separators = [c for c in digits if c in ".,"]

        if not separators:
            value = _num_or_none(digits)
        elif locale == "en":
            value = _read(digits, group=",", decimal=".")
        elif locale == "de":
            value = _read(digits, group=".", decimal=",")
        elif len(separators) == 1 and len(parts[-1]) == 3:
            # `1,234` / `1.234` with the document's locale unknown: 1234 under one reading and
            # 1.234 under the other, a factor of a thousand apart. Guessing here is how a checker
            # manufactures agreement, so it is skipped and counted.
            ambiguous += 1
            continue
        elif len(separators) == 1:
            # One separator with 1, 2 or >=4 trailing digits cannot be a thousands group, so it is
            # a decimal point under either locale and reads the same both ways.
            value = _num_or_none(parts[0] + "." + parts[1])
        else:
            # Two or more separators with the locale unresolved. It is certainly grouped, but which
            # character groups and which (if any) is the decimal is exactly the question we could
            # not answer, so it joins the ambiguous count rather than being read.
            ambiguous += 1
            continue

        if value is None:
            continue
        value *= sign

        # YEAR EXCLUSION — "December 2024" in a headline is a period, not a reading. Lifted only
        # when the target itself is a year, so an anchor that really does derive 2024 can pass.
        if (not target_is_year) and float(value).is_integer() and _YEAR_LO <= value <= _YEAR_HI:
            continue
        out.append(value)

    return out, ambiguous


def _read(digits: str, *, group: str, decimal: str):
    return _num_or_none(digits.replace(group, "").replace(decimal, "."))


def _clip(text: str, limit: int = 90) -> str:
    text = str(text or "")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _de(value) -> str:
    """de-DE rendering of a number for HUMAN-FACING copy (grouping ``.``, decimal ``,``).

    A flag ``reason`` is read by an operator, and this codebase shows numbers de-DE everywhere a
    human reads them: ``1.234``, ``12,34 %``. Written out rather than taken from ``locale`` because
    ``locale.setlocale`` is process-global state and this module is pure — a formatter that mutates
    the interpreter is not a formatter. CAPTURED ANSWER PROSE IS NEVER REFORMATTED: it is evidence,
    it is rendered verbatim, and it will show en-US groupings. That is deliberate.
    """
    number = _num_or_none(value)
    if number is None:
        return "—"
    if float(number).is_integer():
        body = f"{int(number):,}".replace(",", ".")
    else:
        body = f"{number:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return body
