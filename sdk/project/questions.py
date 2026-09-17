"""sdk.project.questions — the Question Lighthouse projector (offline, deterministic, $0).

Reads a bundle's acceptance plane — the corpus (``acceptance/questions.yaml``), the authored
expectations (``acceptance/oracle/<id>.yaml``), the anchors plane (``acceptance/anchors/*.yaml``)
and the captured answers (``acceptance/answers/<id>.yaml``) — and emits
``acceptance/questions_dashboard.json``, schema ``mac.questions_dashboard/3``: the read view the
wiki's Question Lighthouse pane and its per-question result page render.

THIS MODULE IS THE SINGLE PLACE ANY ORACLE-RELATIVE VERDICT IS DERIVED.

    It used to be derived in three: ``run.py`` stamped a ``run_status`` and a grade into every
    answer document, this projector independently recomputed both, and the browser re-derived a
    third opinion from whichever legacy keys it happened to find. Nothing guarded the three against
    each other and they drifted. Now the answer document is pure EVIDENCE (it carries no judgement
    at all), ``sdk.acceptance.flags.evaluate`` is the one evaluator, ``grade.run_status`` is called
    exactly once — here — and the UI paints what it is given without computing a flag, a state or a
    verdict of its own. A second opinion in the browser is how the .xlsx export comes to disagree
    with the screen.

WHAT THIS PROJECTOR DOES NOT DO
    It adds nothing to a flag and rewrites no ``reason``. ``verdict``, ``flags``, ``warnings``,
    ``assertion_counts``, ``anchor_id`` and ``advisory_anchor_ids`` are copied straight out of
    ``flags.evaluate``. Likewise ``family``, ``oracle_class``, ``expected_outcome`` and
    ``expected_shape`` are copied VERBATIM off the oracle — the projector enumerates none of them,
    which is what keeps the UI's Group-by selector source-agnostic instead of encoding one bundle's
    taxonomy in framework code.

NO PERCENTAGES, ANYWHERE
    Every counter in ``stats`` is a count, read against the explicit ``total``. The board used to
    lead with ``pass_pct 4``, computed over the graded subset while 72 of 96 questions had never
    been run — the same denominator dishonesty in a headline position. ``pass_pct``,
    ``grade_status``, ``grade_statuses`` and ``by_grade_status`` are REMOVED, not deprecated in
    place: a consumer that still reads them must fail loudly rather than quietly render the old
    inverted labels.

THE ROW CARRIES NO ``value``
    ``answers[].result.value`` is the last numeric column of the first row of the last executed
    statement. On real captures it is measurably not the answer's number (a model count where the
    answer is a stock figure; a brand count where the answer is a total) and null on many more. It
    stays in the answer document, because that document is evidence of what the engine returned —
    but it is not projected, not displayed as an answer, and never graded. The number that answers
    the question exists only inside the markdown prose, and the ``value`` flag reads the answer's
    headline for it and says so.

CLI:
  python3 -m sdk.project.questions <bundle>              # positional
  python3 -m sdk.project.questions --bundle <bundle>     # equivalent (what console_api shells)
  ... [--print]                                          # also dump the whole dashboard as JSON
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

import yaml

from sdk.acceptance import anchors as _anchors
from sdk.acceptance import bundleio as _io  # atomic_write + the acceptance fingerprint
from sdk.acceptance import flags as _flags  # the ONE evaluator + the frozen vocabularies
from sdk.acceptance import grade as _grade  # run_status + RUN_STATUSES (Process A, oracle-free)
from sdk.acceptance import ontrules as _ontrules  # the ontology's never-clauses, read once

# The dashboard schema id. It moves whenever a vocabulary or the row shape moves, and the UI
# refuses to render a dashboard whose id it does not recognise rather than falling back to a legacy
# derivation — a server-only change that the browser silently papers over is the worst failure mode
# available, because it looks exactly like nothing happened.
#
# /4 (from /3): `flag_ids` gained a fourth member, `rules`. A /3 client renders three squares and
# drops the fourth silently — including, on a violating row, the only square that is red.
SCHEMA = "mac.questions_dashboard/4"

# Complexity tiers, lowest → highest. The classifier picks the HIGHEST matched tier.
TIER_ORDER = ["Low", "Low-Medium", "Medium", "High", "Very High"]
_TIER_RANK = {t: i for i, t in enumerate(TIER_ORDER)}

# (category, tier, compiled signal) — ordered low→high; the highest-tier hit wins, ties keep the
# earlier row. Signals match the question text (lowercased) OR a tag. Rubric = the bundle's own C1..C11 question taxonomy.
_RULES = [
    ("direct-retrieval", "Low", r"\b(what|how much)\b.*\b(did|was|is|have|had)\b"),
    (
        "meta",
        "Low-Medium",
        r"\b(how many|which)\b.*\b(concept|measure|dimension|model|market|serve|cover|catalog)\b",
    ),
    (
        "underspecified",
        "Low",
        r"\bunderspecified\b|\bunknown[ _]?market\b|\bunknown\b|\batlantis\b|\brefuse\b",
    ),
    (
        "aggregation",
        "Low-Medium",
        r"\b(total|sum|overall|aggregate|combined|per |by |breakdown|across all)\b",
    ),
    (
        "resolution",
        "Medium",
        # A TUPLE, NOT A FINISHED REGEX — this row's vocabulary is completed at call time from the
        # estate register's `kpi_surface_name` group, and these three are the part that is GENERIC:
        # they are question-FORM words ("which model", "disambiguat", "synonym"), the shape of an
        # ask, not any estate's KPI. They stay in code precisely because the register is gitignored,
        # so a fresh clone and CI have these and nothing else.
        #
        # WHY THE ESTATE WORDS MERGE INTO **THIS** ROW rather than becoming a tenth row of their
        # own. `classify` takes `max()` over the matched rows, and `max` keeps the EARLIEST maximum.
        # A tenth row appended after `comparison` (also Medium) would hand every question matching
        # both to `comparison` — a silent reclassification of exactly the questions this signal
        # exists to find. Same row, same position, same precedence.
        ("which model", "disambiguat", "synonym"),
    ),
    (
        "comparison",
        "Medium",
        r"\b(compare|versus|vs\.?|difference between|higher|lower|more than|less than|rank|top \d)\b",
    ),
    (
        "derived-kpi",
        "High",
        r"\b(market share|share of|ratio|reach|coverage|per 1000|per thousand|penetration|proportion)\b",
    ),
    (
        "cross-brand",
        "High",
        r"\b(every brand|each brand|across brands|all brands|per brand|brand[- ]?portab)\b",
    ),
    (
        "counterfactual",
        "Very High",
        r"\b(what if|would (the|it)|if .* (dropped|rose|increased|decreased|changed)|project(ed)?|forecast|counterfactual|simulate)\b",
    ),
]

# ─── the estate's own KPI surface words ───────────────────────────────────────────────────────────
#
# WHY THESE ARE NOT IN THIS FILE ANY MORE. The resolution row above used to read
# `\b(<three private KPI words>|which model|disambiguat|synonym)\b`. `meaning-as-code` is a PUBLIC
# repository and `tools/check_mac_public.py` reported that line as one of the last four real leaks in
# the tree (2026-09-17, rule `kpi-name-local`): an estate's KPI vocabulary, published inside the
# framework it was applied to.
#
# A RENAME WOULD NOT HAVE DONE, which is why this is a register and not a word swap. These words
# DRIVE BEHAVIOUR on a private corpus — measured on the bundle this instance guards, exactly one of
# 96 questions classifies as `resolution`/Medium, and it does so ONLY through these words. Remove
# them and that question reads a tier lower with nothing on the board to say why.
#
# ABSENT REGISTER: REDUCED SCOPE, DISCLOSED — NOT could-not-run. Justified, because the choice is
# not free either way:
#   · This module is a PROJECTOR, not a gate. Exit 2 means no `questions_dashboard.json` is written
#     at all, so the wiki's Question Lighthouse pane has nothing to render. Withdrawing the whole
#     board over one classifier signal costs an operator every other number on it — the run counts,
#     the verdicts, the flags, the warnings — none of which touch this register.
#   · The generic question-FORM signals stay in code, so the resolution tier is narrowed, not
#     switched off.
#   · But a narrowed heuristic that says nothing is the empty-population defect this estate keeps
#     finding, so the shortfall is stated in three places a reader cannot miss: the operator's
#     verdict line after every projection, the dashboard header (`estate_vocabulary`), and this
#     comment. A tier that reads Low because a register is missing must never be indistinguishable
#     from a tier that reads Low because the question is simple.
_ESTATE_REGISTER = "estate_terms"
_ESTATE_GROUP = "kpi_surface_name"

#: One entry, keyed on the register's identity+mtime+size, so an env override or an edit mid-session
#: is honoured while 96 questions in one projection do not re-read and re-compile the file 96 times.
#: NOT resolved at import: a module-level snapshot ignores an override set by a later import, which
#: is the bug `sdk.registers.load` documents and `Live` exists for.
_ESTATE_CACHE: dict = {}


def _compile_rules(estate: list) -> list:
    """The tier table, with `estate` merged into the row whose signal is declared as a tuple."""
    out = []
    for cat, tier, sig in _RULES:
        if isinstance(sig, tuple):
            alts = list(sig) + [t.lower() for t in estate]
            sig = r"\b(" + "|".join(re.escape(a) for a in alts) + r")\b"
        out.append((cat, tier, re.compile(sig, re.I)))
    return out


def _signals() -> tuple:
    """`(estate terms, compiled tier table)`, re-read whenever the register file changes."""
    from sdk import registers as _registers

    p = _registers.register_path(_ESTATE_REGISTER)
    try:
        st = p.stat()
        sig = (str(p), st.st_mtime_ns, st.st_size)
    except OSError:
        sig = (str(p), None, None)
    if sig not in _ESTATE_CACHE:
        _ESTATE_CACHE.clear()
        terms = _registers.group(_ESTATE_REGISTER, _ESTATE_GROUP)
        _ESTATE_CACHE[sig] = (terms, _compile_rules(terms))
    return _ESTATE_CACHE[sig]


def estate_vocabulary() -> dict:
    """What the classifier's estate-specific vocabulary actually amounts to, for the verdict line.

    `terms` is the DENOMINATOR: 0 means the resolution tier ran on the generic question-form words
    alone, and every consumer of this projection is entitled to be told so rather than left to
    assume the classifier saw everything it was designed to see.
    """
    from sdk import registers as _registers

    terms = _signals()[0]
    return {
        "group": _ESTATE_GROUP,
        # The path is rendered repo-relative, never absolute: this block is committed to bundle
        # repositories and rendered in a browser. See registers.disclosed_path.
        "register": _registers.disclosed_path(_ESTATE_REGISTER),
        "present": bool(terms),
        "terms": len(terms),
        # The words themselves are NEVER projected. This block travels into a JSON file that is
        # committed to bundle repositories and rendered in a browser; naming them here would put the
        # register's contents back into the artefacts the register exists to keep them out of.
        "reduced_scope": None
        if terms
        else (
            "the estate KPI surface vocabulary is EMPTY: name-resolution questions that turn on a "
            "local KPI word are classified by the generic question-form signals only, so such a "
            "question reads one complexity tier lower than it is. This is a REDUCED SCOPE, not a "
            "clean classification."
        ),
    }


def classify(question: str, tags: list[str] | None = None) -> dict:
    """Heuristic complexity: {category, tier, signals}. Highest-tier match wins."""
    hay = (question or "").lower() + " " + " ".join(tags or []).lower()
    hits = [(cat, tier) for cat, tier, rx in _signals()[1] if rx.search(hay)]
    if not hits:
        return {"category": "direct-retrieval", "tier": "Low", "signals": []}
    # direct-retrieval is the GENERIC fallback (nearly every "what was X" matches it) — a more specific
    # category wins even at the same tier. It never carries the top tier (always Low), so excluding it
    # from the max never lowers the tier.
    pool = [h for h in hits if h[0] != "direct-retrieval"] or hits
    best = max(pool, key=lambda ct: _TIER_RANK[ct[1]])
    return {"category": best[0], "tier": best[1], "signals": [c for c, _ in hits]}


def _resolved(q: dict) -> dict:
    """A question's effective category/tier: an author pin overrides the classifier."""
    auto = classify(q.get("question", ""), q.get("tags"))
    pin_tier = q.get("complexity")
    pin_cat = q.get("category")
    tier = pin_tier if pin_tier in _TIER_RANK else auto["tier"]
    cat = pin_cat if (pin_cat and pin_cat != "auto") else auto["category"]
    return {"category": cat, "tier": tier}


# --------------------------------------------------------------------------- #
# Loading the acceptance plane
# --------------------------------------------------------------------------- #


def _corpus(acc: Path) -> list:
    """``acceptance/questions.yaml`` as a list of mappings carrying an id; [] when absent.

    The corpus is the authority for a question's TEXT. The oracle's ``question.text`` has drifted
    on 16 files in the reference bundle and is never treated as the question — it is compared
    against this one and the disagreement is reported as a corpus-health warning.
    """
    p = acc / "questions.yaml"
    if not p.is_file():
        return []
    try:
        doc = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    except Exception:
        return []
    if not isinstance(doc, list):
        return []
    return [e for e in doc if isinstance(e, dict) and e.get("id")]


def _load_oracle_doc(acc: Path, qid: str) -> tuple:
    """``(oracle, oracle_error)`` in the shape ``flags.evaluate``'s precondition ladder expects.

    That ladder tests ``oracle is None`` BEFORE ``oracle_error is not None``, so a file that exists
    but cannot be read must come back as a non-None document ALONGSIDE its message — otherwise the
    parse failure is reported as "no oracle" and the real error is lost. An empty mapping is the
    honest value for "the oracle exists and we know nothing about it".

    SCHEMA-INCOMPLETENESS (``expected.outcome`` missing or not a string) is deliberately NOT
    restated here. ``flags.evaluate`` self-detects it and raises the identical ``oracle-error``
    verdict, because it is the one module that actually depends on the key — a second copy of that
    rule in the projector would be a second thing to drift, for no change in the emitted row.

    ``sdk.acceptance.run`` carries a near-twin of this loader for its ``--op explain``. The
    duplication is forced: ``run`` imports this module to re-project after every write, so this
    module cannot import ``run`` back. Consolidating both into ``bundleio`` is the right fix and is
    named in the handover.
    """
    # Containment before the filesystem is touched: a question id is a FILENAME here, and an id of
    # "../../../tmp/pwn" — which an operator's .xlsx can carry into the corpus — would otherwise
    # read outside the bundle. Treated as "no oracle", which is what an unusable id honestly is.
    if not _io.is_safe_qid(qid):
        return (None, None)
    p = acc / "oracle" / f"{qid}.yaml"
    if not p.is_file():
        return (None, None)
    try:
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as err:
        return ({}, f"{type(err).__name__}: {' '.join(str(err).split())[:300]}")
    if doc is None:
        return ({}, "the oracle file is empty")
    if not isinstance(doc, dict):
        return ({}, f"expected a YAML mapping, got {type(doc).__name__}")
    return (doc, None)


def _load_answer(acc: Path, qid: str):
    """The persisted capture, or None when the question has not been run.

    An unreadable capture is "not run" rather than an exception: one corrupt answer document must
    not blank the whole board, and the row it produces (``unrun``) is visibly wrong in a way an
    operator can act on.
    """
    if not _io.is_safe_qid(qid):
        return None
    p = acc / "answers" / f"{qid}.yaml"
    if not p.is_file():
        return None
    try:
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return doc if isinstance(doc, dict) else None


# --------------------------------------------------------------------------- #
# Capture-derived row glyphs (Process A: what the engine DID — no oracle involved)
# --------------------------------------------------------------------------- #

# Legacy captures — written before the answer document became pure evidence — stamped a verdict
# block. Current captures carry `route` instead. Both shapes are read so a board built over a
# half-migrated answers/ directory says the same thing about both halves.
_ROW_DISP = {"GOVERNED": "governed", "AI_ASSISTED": "ai-assisted", "GOVERNED_REFUSAL": "refusal"}


def _row_mode(ans: dict | None):
    """The execution mode the capture recorded, VERBATIM (e.g. ``llm-execute``), or None.

    Verbatim rather than mapped to a glyph token: the dashboard's job is to report what the engine
    was asked to do, and the wire value is the same string the run endpoint accepts, so a row and a
    re-run request cannot describe different things.
    """
    if not isinstance(ans, dict):
        return None
    eng = ans.get("engine")
    eng = eng if isinstance(eng, dict) else {}
    mode = eng.get("mode")
    if isinstance(mode, str) and mode.strip():
        return mode
    # Pre-`mode` documents recorded only the athena boolean. An execute run is the one thing that
    # flag can still prove; anything else is genuinely unknown and is left unknown.
    return "llm-execute" if eng.get("athena") else None


def _row_disposition(ans: dict | None, n_sql: int):
    """How the engine disposed of the question: governed | ai-assisted | refusal | None.

    Read off what the run path RECORDED — never by re-scanning the answer prose. That scan is the
    34-marker refusal test, and running it over a whole governed answer is exactly the false-refusal
    trap this redesign exists to remove (a commit that closes with "would you like a breakdown?"
    reads as a decline). ``flags`` narrows the same scan to the lead for its own purposes; here
    there is no need to guess at all, because the capture says.
    """
    if not isinstance(ans, dict):
        return None
    verdict = ans.get("verdict")
    legacy = verdict.get("disposition") if isinstance(verdict, dict) else None
    if legacy in _ROW_DISP:
        return _ROW_DISP[legacy]
    route = ans.get("route")
    if not isinstance(route, str) or not route.strip():
        return None
    if route == "refusal":
        return "refusal"
    # Governed = the engine emitted governed SQL for this question; an answer with none of it is
    # the wiki-only reasoned route.
    return "governed" if n_sql else "ai-assisted"


def _sql_statements(ans: dict | None) -> list:
    """The capture's non-empty SQL statements.

    Filtered EXACTLY as ``flags.evaluate`` filters them, so the row's ``sql_count`` and the
    ``outcome`` flag's ``n_sql`` can never tell an operator two different numbers about one run.
    """
    if not isinstance(ans, dict):
        return []
    return [s for s in (ans.get("sql") or []) if isinstance(s, str) and s.strip()]


def _oracle_facet(oracle: dict | None, *path):
    """A nested oracle value, copied VERBATIM, or None when any hop is missing or not a mapping.

    Verbatim is the whole point: ``family``, ``oracle_class``, ``expected_outcome`` and
    ``expected_shape`` become the Group-by axes in the UI, and the moment the projector normalises,
    defaults or enumerates any of them it has encoded one bundle's taxonomy into framework code and
    the next source renders wrong.
    """
    node = oracle
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


# --------------------------------------------------------------------------- #
# The projection
# --------------------------------------------------------------------------- #


def build(bundle: Path) -> dict:
    """Project a bundle's acceptance plane → the dashboard dict; also writes it to disk.

    One pass over the corpus. For each question: resolve its oracle (with its error, if any), its
    capture and its graded anchor, then call ``flags.evaluate`` ONCE and copy the six keys it
    returns straight into the row. ``run_status`` is computed here, once, by
    ``grade.run_status(answer)`` — the value that used to be stamped into the answer file is
    neither written nor read any more.

    Cost: ~96 rows x <=16 statements is under 600 sqlglot parses per projection, well under a
    second. No caching layer is required or wanted; a cache is one more thing that can be stale.

    The write goes through ``bundleio.atomic_write``: the UI polls this file every 2.5 s while a
    "Run all" has two processes rewriting it in turn, and a truncate-then-stream write hands that
    poll a short file and a ``JSON.parse`` throw.
    """
    root = Path(bundle)
    acc = root / "acceptance"

    corpus = _corpus(acc)
    ont_fp = _ontology_fingerprint(root)
    # The AUTHORED-acceptance hash (corpus + oracles + anchors). The ontology tree hash cannot see
    # an oracle edit, which is why every capture read "fresh" while the assertions it had been
    # judged against were rewritten under it.
    acc_fp = _io.acceptance_fingerprint(root)
    index = _anchors.build_index(root, [q["id"] for q in corpus])
    # The ontology's never-clauses, read ONCE for the whole build and handed to every row. Which of
    # them are bound to a given question is decided inside `flags.evaluate`, from the relations the
    # capture's SQL actually read — the projector holds no routing opinion of its own.
    ont_rules = _ontrules.build_index(root)

    rows: list[dict] = []
    for q in corpus:
        qid = q["id"]
        res = _resolved(q)
        oracle, oracle_error = _load_oracle_doc(acc, qid)
        answer = _load_answer(acc, qid)
        anchor = index["graded"].get(qid)
        advisory = index["advisory"].get(qid, [])

        ev = _flags.evaluate(
            corpus_row=q,
            oracle=oracle,
            oracle_error=oracle_error,
            answer=answer,
            anchor=anchor,
            advisory_anchors=advisory,
            acceptance_fingerprint=acc_fp,
            concept_rules=ont_rules["rules"],
        )

        sql = _sql_statements(answer)
        rows.append(
            {
                # --- authored corpus (questions.yaml is the authority for the TEXT) ---------------
                "id": qid,
                "question": q.get("question", ""),
                "tags": q.get("tags") or [],
                "complexity": q.get("complexity"),
                "tier": res["tier"],
                "category": res["category"],
                "regression": q.get("regression", "optional"),
                # --- copied VERBATIM off the oracle; the projector enumerates none of these -------
                "family": _oracle_facet(oracle, "about", "family"),
                "oracle_class": _oracle_facet(oracle, "question", "class"),
                "expected_outcome": _oracle_facet(oracle, "expected", "outcome"),
                "expected_shape": _oracle_facet(oracle, "expected", "shape"),
                # --- what the engine DID (Process A: no oracle involved) --------------------------
                "run_status": _grade.run_status(answer),
                "mode": _row_mode(answer),
                "disposition": _row_disposition(answer, len(sql)),
                "sql_valid": answer.get("sql_valid") if isinstance(answer, dict) else None,
                "sql_count": len(sql),
                "captured_at": answer.get("captured_at") if isinstance(answer, dict) else None,
                # --- what flags.evaluate ruled: copied straight through, nothing added ------------
                "verdict": ev["verdict"],
                "flags": ev["flags"],
                "warnings": ev["warnings"],
                "assertion_counts": ev["assertion_counts"],
                "anchor_id": ev["anchor_id"],
                "advisory_anchor_ids": ev["advisory_anchor_ids"],
                # --- the three files the detail page reads through the generic file endpoint ------
                # Null means "there is no such file", which is exactly what the page must render; a
                # path to a file that does not exist would be a 404 the operator has to interpret.
                "paths": {
                    "oracle": f"acceptance/oracle/{qid}.yaml" if oracle is not None else None,
                    "answer": f"acceptance/answers/{qid}.yaml" if answer is not None else None,
                    "anchor": (anchor or {}).get("_file"),
                },
            }
        )

    dash = {
        "schema": SCHEMA,
        "generated_at": _now(),
        "bundle": _bundle_label(root),
        "ontology_fingerprint": ont_fp,
        "acceptance_fingerprint": acc_fp,
        # The frozen vocabularies, shipped WITH the data. The UI mirrors them once for colour and
        # copy, but every rollup it draws is keyed off these lists, so a vocabulary that grows
        # renders on an unchanged client instead of silently dropping a bucket.
        "flag_ids": list(_flags.FLAG_IDS),
        "flag_states": list(_flags.FLAG_STATES),
        "verdicts": list(_flags.VERDICTS),
        "run_statuses": list(_grade.RUN_STATUSES),
        "warning_codes": list(_flags.WARNING_CODES),
        "anchors": _anchor_summary(index),
        # The rules plane's own header, for the same reason the anchors plane has one: the `rules`
        # flag reads mostly `unchecked`, and without these counts a reader cannot tell an ontology
        # that states nothing from a projector that failed to read it. `errors` names a concept file
        # that would not load — authored governance silently going unenforced.
        "ontology_rules": {
            "total": ont_rules["count"],
            "concepts": ont_rules["concepts"],
            "errors": list(ont_rules["errors"]),
        },
        # THE CLASSIFIER'S OWN DENOMINATOR, shipped with the data it classified. `category` and
        # `tier` on every row above are heuristic, and one of the heuristic's vocabularies lives in
        # a gitignored per-estate register — so on a fresh clone or in CI it is EMPTY, and the tiers
        # narrow without a single row looking any different. This block is how a reader tells the two
        # apart. It carries the count and never the terms: this file is committed to bundle
        # repositories and rendered in a browser.
        #
        # THE SCHEMA ID DELIBERATELY DOES NOT MOVE. The rule at the top of this module is that it
        # moves whenever a VOCABULARY or the ROW SHAPE moves, because a client then renders the wrong
        # thing — the `flag_ids`/3 case, where an old client drew three squares and dropped the only
        # red one. This key is a HEADER addition: no row shape changes, no frozen vocabulary grows,
        # and a /4 client that ignores it still paints every row correctly. Bumping to /5 would make
        # every existing board refuse to render in exchange for a disclosure that also reaches the
        # operator on the verdict line below.
        "estate_vocabulary": estate_vocabulary(),
        "stats": _stats(rows),
        "questions": rows,
    }

    acc.mkdir(parents=True, exist_ok=True)
    _io.atomic_write(acc / "questions_dashboard.json", json.dumps(dash, indent=2) + "\n")
    return dash


def _anchor_summary(index: dict) -> dict:
    """The anchors-plane header: how many anchors exist and how many can actually grade something.

    ``advisory`` counts DISTINCT anchor documents, not links: one anchor that names three questions
    is one advisory anchor shown against three rows, and counting it three times would make the
    header disagree with the directory. ``unlinked_ids`` is named rather than merely counted
    because an anchor nobody can link is authored ground truth going unused — the gap has to be
    visible to be closed.
    """
    graded_ids = {a.get("_anchor_id") for a in index["graded"].values() if isinstance(a, dict)}
    advisory_ids = {
        a.get("_anchor_id")
        for bucket in index["advisory"].values()
        for a in bucket
        if isinstance(a, dict)
    }
    advisory_ids -= graded_ids
    return {
        "total": index["count"],
        "graded": len(index["graded"]),
        "advisory": len(advisory_ids),
        "unlinked": len(index["unlinked"]),
        "unlinked_ids": list(index["unlinked"]),
        "errors": list(index["errors"]),
    }


def _stats(rows: list) -> dict:
    """Counts only. Every one of them is read against a total stated in this same block.

    NO PERCENTAGES. The headline used to be ``pass_pct``, computed over the graded subset while 72
    of 96 questions had never been run — a number that moved when the denominator moved and told an
    operator nothing about the corpus. Each bucket below is zero-filled across its full vocabulary
    so a state that is absent today renders as an explicit 0 rather than vanishing from the board.

    TWO DENOMINATORS, BOTH EXPLICIT, AND THEY ARE NOT THE SAME NUMBER.
        ``by_run_status`` and ``by_verdict`` are censuses of the whole corpus and sum to ``total``.
        ``by_flag`` is a census of the questions that were actually EVALUATED and sums to
        ``by_verdict``'s four gradeable buckets (proven + routed + unproven + failed) — which is
        why that total is present in the same block and needs no separate key.

        A row short-circuited by the precondition ladder (unrun, error, no-oracle, oracle-error)
        carries three ``na`` flags reading "not evaluated: <verdict>". Counting those would put 72
        contentless ``na``s into the ``value`` bucket on the reference corpus and bury the 14 that
        carry the finding that actually matters — questions that ran correctly and have no anchor
        capable of proving their number. The ladder rows are already counted, once, in
        ``by_verdict``; counting them twice tells nobody anything new.

        Membership is decided by the ``outcome`` flag, not by a second list of verdict names:
        ``outcome`` is the one check available on every graded row and is documented never to be
        ``na`` when an oracle and a capture both exist (§4.3.2). So ``outcome != "na"`` IS
        "this row reached the checks", with no vocabulary to keep in step.
    """
    by_run = dict.fromkeys(_grade.RUN_STATUSES, 0)
    by_verdict = dict.fromkeys(_flags.VERDICTS, 0)
    by_flag = {fid: dict.fromkeys(_flags.FLAG_STATES, 0) for fid in _flags.FLAG_IDS}
    by_warning = dict.fromkeys(_flags.WARNING_CODES, 0)
    warnings_total = 0
    anchored = 0

    for r in rows:
        by_run[r["run_status"]] = by_run.get(r["run_status"], 0) + 1
        by_verdict[r["verdict"]] = by_verdict.get(r["verdict"], 0) + 1
        states = {f["id"]: f["state"] for f in r["flags"]}
        if states.get("outcome") != "na":  # see the docstring: this row reached the checks
            for f in r["flags"]:
                bucket = by_flag.setdefault(f["id"], dict.fromkeys(_flags.FLAG_STATES, 0))
                bucket[f["state"]] = bucket.get(f["state"], 0) + 1
        for w in r["warnings"]:
            by_warning[w["code"]] = by_warning.get(w["code"], 0) + 1
            warnings_total += 1
        if r["anchor_id"]:
            anchored += 1

    return {
        "total": len(rows),
        "run": len(rows) - by_run.get("unrun", 0),
        "by_run_status": by_run,
        "by_verdict": by_verdict,
        "by_flag": by_flag,
        "by_warning": by_warning,
        "warnings_total": warnings_total,
        "anchored_questions": anchored,
    }


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _bundle_label(root: Path) -> str:
    """``<domain>/<dataset>`` — how the wiki addresses this source in its routes and its URLs."""
    parts = Path(root).resolve().parts
    return "/".join(parts[-2:]) if len(parts) >= 2 else (parts[-1] if parts else "")


def _ontology_fingerprint(bundle: Path) -> str | None:
    """Tree-hash of ontology/ (sorted path+bytes) — the fingerprint each capture records.

    Kept alongside the acceptance fingerprint rather than replaced by it: they answer two different
    questions. This one moves when the MODEL under test changes; the acceptance one moves when the
    ASSERTIONS change. A capture is stale against either, for different reasons.
    """
    import hashlib

    ont = Path(bundle) / "ontology"
    if not ont.is_dir():
        return None
    h = hashlib.sha256()
    for p in sorted(ont.rglob("*.yaml")):
        h.update(p.relative_to(ont).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _summary_lines(dash: dict) -> list:
    """The replay summary an operator reads after a projection. Counts, each against its total."""
    s = dash["stats"]
    total = s["total"]
    a = dash["anchors"]

    def counts(bucket: dict) -> str:
        # Only non-zero buckets are printed here (the JSON carries the zero-filled truth); a
        # terminal line listing eight zeroes hides the four numbers that matter.
        return "  ".join(f"{k}={v}" for k, v in bucket.items() if v) or "—"

    return [
        f"questions: {total}   run: {s['run']} of {total}   "
        f"anchored: {s['anchored_questions']} of {total}   "
        f"corpus warnings: {s['warnings_total']}",
        "  verdict: " + counts(s["by_verdict"]),
        "  run:     " + counts(s["by_run_status"]),
        "  flags:   "
        + "   ".join(f"{fid}[{counts(s['by_flag'][fid])}]" for fid in dash["flag_ids"]),
        "  warnings:" + " " + counts(s["by_warning"]),
        f"  anchors: {a['graded']} graded  {a['advisory']} advisory  {a['unlinked']} unlinked  "
        f"of {a['total']}" + (f"   errors: {len(a['errors'])}" if a["errors"] else ""),
        # UNCONDITIONAL, and it states the count even when it is healthy. A disclosure that appears
        # only when something is missing teaches a reader to skim past it; a denominator that is
        # always on the line is one a reader learns to read. `.get` because a dashboard projected by
        # an older build of this module has no such block, and a replay of one must not crash.
        _vocabulary_line(dash.get("estate_vocabulary") or {}),
    ]


def _vocabulary_line(v: dict) -> str:
    if not v:
        return "  vocabulary: (not recorded — dashboard projected before this was disclosed)"
    if v.get("present"):
        return f"  vocabulary: {v['terms']} estate KPI surface term(s) in the {v['group']} register"
    return (
        f"  vocabulary: 0 estate KPI surface term(s) — NO register at {v.get('register')}. "
        "The resolution tier ran on the generic question-form signals ALONE, so a question that "
        "turns on a local KPI word is classified one tier low. This is a REDUCED SCOPE, not a "
        "clean classification: copy registers/estate_terms.example.txt, or set $MAC_ESTATE_TERMS."
    )


# --------------------------------------------------------------------------- #
# self-test: one seeded mutant per reject class of the classifier's estate vocabulary
#
# Every term below is SYNTHETIC (`zz...`). The real register is gitignored, so a fresh checkout
# declares none: a self-test that read the real one would exercise this vocabulary against an empty
# list and pass, having checked nothing — the same defect this whole change is about. The register is
# handed to the code under test through its own `$MAC_ESTATE_TERMS` override, which is the mechanism
# an estate and a CI runner use, so the test exercises the seam rather than bypassing it.
# --------------------------------------------------------------------------- #

_SYN_TERM = "zzsynthkpizz"


def _self_test() -> int:
    import os
    import tempfile

    failures: list = []
    checks = 0

    def expect(cond, msg):
        nonlocal checks
        checks += 1
        if not cond:
            failures.append(msg)

    def with_register(text):
        """Point $MAC_ESTATE_TERMS at a register holding `text` (None = no file at all)."""
        if text is None:
            os.environ[_ENV] = str(Path(tmp) / "absent" / "estate_terms.txt")
        else:
            p = Path(tmp) / f"reg{len(os.listdir(tmp))}.txt"
            p.write_text(text, encoding="utf-8")
            os.environ[_ENV] = str(p)

    from sdk import registers as _registers

    _ENV = _registers.REGISTERS[_ESTATE_REGISTER][1]
    _saved = os.environ.get(_ENV)
    with tempfile.TemporaryDirectory() as tmp:
        try:
            # 1 - REGISTER PRESENT: a question carrying a declared surface word is a name-resolution
            #     question at Medium. This is the behaviour the three private words used to give.
            with_register(f"{_ESTATE_GROUP} | {_SYN_TERM}\n")
            c = classify(f"what was the {_SYN_TERM} last month")
            expect(
                c["category"] == "resolution" and c["tier"] == "Medium",
                f"mutant not caught: a declared surface term did not classify as resolution: {c}",
            )
            v = estate_vocabulary()
            expect(v["present"] and v["terms"] == 1, f"vocabulary block wrong when present: {v}")
            expect(
                _SYN_TERM not in json.dumps(v),
                "the vocabulary block ECHOES the register's terms — this block is committed to "
                "bundle repos and rendered in a browser, so it must carry the count only",
            )
            expect(
                "1 estate KPI surface term" in _vocabulary_line(v),
                f"the healthy verdict line omits its denominator: {_vocabulary_line(v)!r}",
            )
            # 1b - THE DISCLOSURE MUST NOT BE AN ABSOLUTE PATH, and this assertion exists because
            #      that defect was actually SHIPPED into this file once, mid-change, and caught by
            #      eye rather than by a test. The first cut built this block from
            #      `str(registers.register_path(...))` and the projected `questions_dashboard.json`
            #      — committed to bundle repositories and rendered in a browser — came out carrying
            #      `/Users/<the operator>/…`, which is the shape `check_mac_public` flags as a leak.
            #      `registers.disclosed_path()` was written to fix it, and NOTHING asserted the fix:
            #      reverting that one call left every self-test in this repository green, because
            #      each of them points $MAC_ESTATE_TERMS at a temp path whose absolute form is a
            #      perfectly plausible-looking string. One guard here covers all three consumers,
            #      since `check_rule_reference_basis` and `check_grain_declaration` render their own
            #      disclosures through the same function.
            expect(
                not os.path.isabs(v["register"]),
                f"the vocabulary block discloses an ABSOLUTE path ({v['register']!r}) — this block "
                "is committed to bundle repos and rendered in a browser, so the register must be "
                "named repo-relative (registers.disclosed_path), never as a filesystem path that "
                "carries the operator's home directory into a published artefact",
            )

            # 2 - PRECEDENCE. The same question ALSO matching `comparison` (also Medium) must still
            #     read resolution. A tenth rule row appended after `comparison` passes check 1 and
            #     fails this one, because `max()` keeps the EARLIEST maximum.
            c = classify(f"compare the {_SYN_TERM} across markets")
            expect(
                c["category"] == "resolution",
                f"mutant not caught: the estate signal lost its row precedence to comparison: {c}",
            )

            # 3 - REGISTER ABSENT: the tier DROPS (that is the honest consequence, not a bug) and the
            #     shortfall is disclosed — in the block and on the operator's line.
            with_register(None)
            c = classify(f"what was the {_SYN_TERM} last month")
            expect(
                c["category"] != "resolution",
                "the no-register path still matched an estate term — the register is not being read",
            )
            v = estate_vocabulary()
            expect(
                not v["present"] and v["terms"] == 0 and v["reduced_scope"],
                f"mutant not caught: no register, yet nothing disclosed: {v}",
            )
            line = _vocabulary_line(v)
            expect(
                "REDUCED SCOPE" in line and "0 estate KPI surface term" in line,
                f"the no-register verdict line does not state the shortfall plainly: {line!r}",
            )
            # The ABSENT path is the one that names a path most loudly ("NO register at …"), so it
            # is the one most likely to print an absolute one. Guarded on both paths, not just the
            # healthy one — see 1b.
            expect(
                not os.path.isabs(v["register"]),
                f"the no-register disclosure names an ABSOLUTE path ({v['register']!r}) — the "
                "verdict line and the dashboard header both carry it, and both are published",
            )

            # 4 - THE GENERIC SIGNALS STILL RUN WITH NO REGISTER. They are question-FORM words and
            #     live in code for exactly this checkout: a clone with no register must still
            #     classify a resolution question it can recognise generically.
            c = classify("which model does this disambiguate to")
            expect(
                c["category"] == "resolution",
                f"the generic question-form resolution signals stopped working without a register: {c}",
            )

            # 5 - AN EMPTY REGISTER IS NOT A DECLARED VOCABULARY. A file that exists and declares
            #     nothing used to be indistinguishable from a file full of terms.
            with_register("# nothing declared\n")
            expect(
                not estate_vocabulary()["present"],
                "mutant not caught: an EMPTY register reported itself as present",
            )

            # 6 - A LINE WITH NO GROUP IS IGNORED, not filed under a default group where it would
            #     acquire behaviour nobody declared.
            with_register(f"{_SYN_TERM}\n")
            expect(
                not estate_vocabulary()["present"],
                "a register line with no group name was silently given a group",
            )

            # 7 - THE GROUPS ARE SEPARATE. A term declared under another consumer's group must not
            #     leak into this classifier.
            with_register(f"kpi_surface_stem | {_SYN_TERM}\n")
            expect(
                not estate_vocabulary()["present"]
                and classify(f"the {_SYN_TERM} figure")["category"] != "resolution",
                "a term from another group leaked into the question classifier",
            )
        finally:
            if _saved is None:
                os.environ.pop(_ENV, None)
            else:
                os.environ[_ENV] = _saved
            _ESTATE_CACHE.clear()

    if failures:
        print(f"FAIL: questions self-test — {len(failures)} failure(s) over {checks} check(s)")
        for f in failures:
            print(f"  {f}")
        return 1
    print(
        f"PASS: questions self-test — {checks}/{checks} check(s) over the classifier's "
        f"{len(_RULES)} tier rule(s); the estate vocabulary is proven PRESENT, ABSENT, EMPTY and "
        f"MISGROUPED, each with its own disclosure"
    )
    return 0


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="Project a bundle's acceptance plane → questions_dashboard.json"
    )
    ap.add_argument("--self-test", action="store_true", help="seeded mutants of the classifier")
    # Both spellings are accepted on purpose: the wiki shells `--bundle` over the subprocess seam
    # (boundaries.yaml — wiki/ never imports sdk), while a replay by hand reads better positionally.
    ap.add_argument(
        "bundle_pos", nargs="?", metavar="BUNDLE", help="path to the <domain>/<dataset> bundle dir"
    )
    ap.add_argument("--bundle", help="same, named (what console_api passes)")
    ap.add_argument("--print", action="store_true", help="also dump the whole dashboard as JSON")
    a = ap.parse_args(argv)

    if a.self_test:
        return _self_test()

    bundle = a.bundle or a.bundle_pos
    if not bundle:
        ap.error("a bundle path is required (positionally or as --bundle)")
    if a.bundle and a.bundle_pos and a.bundle != a.bundle_pos:
        ap.error(f"two different bundles given: {a.bundle_pos!r} and {a.bundle!r}")

    dash = build(Path(bundle))
    for line in _summary_lines(dash):
        print(line)
    if a.__dict__["print"]:
        print(json.dumps(dash, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
