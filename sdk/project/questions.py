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
        r"\b(gesamtmarkt|auftragsbestand|auslieferung|which model|disambiguat|synonym)\b",
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
_COMPILED = [(cat, tier, re.compile(rx, re.I)) for cat, tier, rx in _RULES]


def classify(question: str, tags: list[str] | None = None) -> dict:
    """Heuristic complexity: {category, tier, signals}. Highest-tier match wins."""
    hay = (question or "").lower() + " " + " ".join(tags or []).lower()
    hits = [(cat, tier) for cat, tier, rx in _COMPILED if rx.search(hay)]
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
    ]


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="Project a bundle's acceptance plane → questions_dashboard.json"
    )
    # Both spellings are accepted on purpose: the wiki shells `--bundle` over the subprocess seam
    # (boundaries.yaml — wiki/ never imports sdk), while a replay by hand reads better positionally.
    ap.add_argument(
        "bundle_pos", nargs="?", metavar="BUNDLE", help="path to the <domain>/<dataset> bundle dir"
    )
    ap.add_argument("--bundle", help="same, named (what console_api passes)")
    ap.add_argument("--print", action="store_true", help="also dump the whole dashboard as JSON")
    a = ap.parse_args(argv)

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
