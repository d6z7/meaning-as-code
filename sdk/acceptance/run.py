"""sdk.acceptance.run — the sdk-side Question Lighthouse orchestrator (build-time, sdk-only).

Four ops, each driven from a JSON ``--input`` file. The wiki calls these over a subprocess seam
(boundaries.yaml: the wiki never imports sdk), handing over what only it can produce — the
live ``/ask`` captures — and letting sdk own the SSOT write + the deterministic projection.

  * ``--op grade-batch`` — persist each capture as ``acceptance/answers/<id>.yaml`` and re-project.
    THE NAME IS HISTORICAL: this op no longer grades anything. It stamps provenance
    (captured_at, the ontology fingerprint, the acceptance fingerprint, engine, route) around
    the engine's own output and writes it down. The answer document is EVIDENCE; the judgement
    is derived once, at projection time, by ``sdk.acceptance.flags``. Prints {ran, dashboard}.

  * ``--op upsert`` — UPSERT ``acceptance/questions.yaml`` from parsed spreadsheet rows
    (add new ids, update text/tags/complexity/category/regression; drop absent ids only under
    ``--full-replace``), then re-project. Prints {imported, total, dashboard}.

  * ``--op patch`` — set NAMED KEYS of exactly ONE corpus entry, changing nothing else. This is
    the write path behind the UI's add/edit dialog, and it exists precisely because ``upsert``
    normalises: upsert force-sets ``complexity``, forces ``regression`` non-empty and POPS
    ``category`` when the incoming value is blank — so a form round-trip through it silently
    strips an author's pinned category. Prints {ok, id, created, changed}.

  * ``--op explain`` — READ-ONLY. Resolve one question exactly as the projector does (corpus row +
    oracle + capture + anchors index) and print ``flags.evaluate``'s result as pretty JSON. Costs
    nothing: no Athena, no model, no write. This is the primary debugging tool for the flag model.

Two invariants hold across every op, both enforced through ``sdk.acceptance.bundleio``:

  * CONTAINMENT — a question id is a FILENAME (``oracle/<id>.yaml``, ``answers/<id>.yaml``), so
    every id that arrives from outside is checked against ``QID_RE`` before it can name a path.
    An id of ``../../../tmp/pwn``, which an operator's .xlsx can carry in, wrote outside the
    bundle before this existed.
  * ATOMICITY — every write goes through ``bundleio.atomic_write`` (temp file in the same
    directory + ``os.replace``). The UI polls the projected dashboard every 2.5 s while these ops
    rewrite it; a truncate-then-stream write hands that poll a partial file.

CLI:
  python3 -m sdk.acceptance.run --op grade-batch --bundle <root> --input captures.json
  python3 -m sdk.acceptance.run --op upsert --bundle <root> --input rows.json [--full-replace]
  python3 -m sdk.acceptance.run --op patch --bundle <root> --input row.json
  python3 -m sdk.acceptance.run --op explain --bundle <root> --input id.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

import yaml

from sdk.acceptance import anchors as _anchors
from sdk.acceptance import bundleio as _io
from sdk.acceptance import flags as _flags
from sdk.acceptance import grade as _grade
from sdk.acceptance import ontrules as _ontrules
from sdk.project import questions as _q

_TIERS = set(_q.TIER_ORDER)

# Re-exported so this module has the module-level QID_RE the spec asks for, while the ONE
# definition stays in bundleio — a question id is a filename (acceptance/oracle/<id>.yaml,
# acceptance/answers/<id>.yaml), and two copies of the containment rule is two things to drift.
QID_RE = _io.QID_RE


class Refused(ValueError):
    """A payload was refused BEFORE anything was written (containment / validation failure)."""


class RefusedCode(Refused):
    """A refusal the HTTP layer maps to a specific status, so it carries a stable machine code.

    ``console_api`` turns ``exists`` into 409 and ``missing`` into 404. Those two words are the
    wire contract; the human sentence rides along in ``detail`` and may be reworded freely.
    """

    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(detail)


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds")


def _provider_of(model: str) -> str:
    m = (model or "").lower()
    return (
        "openai"
        if (m.startswith("gpt") or "openai" in m or m.startswith("o1") or m.startswith("o3"))
        else "bedrock"
    )


def _load_oracle(acc: Path, qid: str):
    # Containment before the filesystem is touched at all: an id that is not a plain path segment
    # reads outside the bundle ("../../../tmp/pwn" leaves acceptance/ entirely). Treated as
    # "no oracle" rather than raising, because a caller that already refuses unsafe ids at its own
    # gate should not be able to reach this branch anyway — this is the backstop, not the gate.
    if not _io.is_safe_qid(qid):
        return None
    p = acc / "oracle" / f"{qid}.yaml"
    if not p.exists():
        return None
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return None


def _load_oracle_doc(acc: Path, qid: str) -> tuple:
    """``(oracle, oracle_error)`` in the shape ``flags.evaluate``'s precondition ladder expects.

    The ladder tests ``oracle is None`` BEFORE ``oracle_error is not None``, so a file that exists
    but cannot be read must come back as a non-None document ALONGSIDE its message — otherwise the
    parse failure is reported as "no oracle" and the real error is lost. An empty mapping is the
    honest value for "the oracle exists and we know nothing about it".

    Schema-incompleteness (``expected.outcome`` missing or not a string) is reported here too, so
    the message names the key rather than leaving ``flags`` to invent one.
    """
    if not _io.is_safe_qid(qid):
        return (None, None)
    p = acc / "oracle" / f"{qid}.yaml"
    if not p.exists():
        return (None, None)
    try:
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as err:
        return ({}, f"{type(err).__name__}: {' '.join(str(err).split())[:300]}")
    if doc is None:
        return ({}, "the oracle file is empty")
    if not isinstance(doc, dict):
        return ({}, f"expected a YAML mapping, got {type(doc).__name__}")
    expected = doc.get("expected")
    if not isinstance(expected, dict) or not isinstance(expected.get("outcome"), str):
        return (doc, "expected.outcome missing")
    return (doc, None)


def _load_answer(acc: Path, qid: str):
    """The persisted capture, or None when the question has not been run."""
    if not _io.is_safe_qid(qid):
        return None
    p = acc / "answers" / f"{qid}.yaml"
    if not p.exists():
        return None
    try:
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return doc if isinstance(doc, dict) else None


def _corpus(acc: Path) -> list:
    """``acceptance/questions.yaml`` as a list of mappings; [] when absent."""
    p = acc / "questions.yaml"
    if not p.exists():
        return []
    doc = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    return [e for e in doc if isinstance(e, dict) and e.get("id")]


_MODES = ("llm-answer", "llm-validate", "llm-execute")
_ROUTE_BY_MODE = {
    "llm-answer": "wiki-only",
    "llm-validate": "validate",
    "llm-execute": "wiki+athena",
}


def op_grade_batch(bundle: Path, payload: dict) -> dict:
    """Persist each capture as EVIDENCE + re-project. ``payload`` = {items:[{id, question, ask}],
    mode, engine:{model, effort, provider?}}.

    ``mode`` ∈ {llm-answer, llm-validate, llm-execute} (legacy ``athena:bool`` maps
    true→llm-execute). For ``llm-validate`` the composed SQL is parsed offline (sqlglot) to a
    ``sql_valid`` bool — no execution, no numeric value.

    THIS OP NO LONGER GRADES, AND THE DOCUMENT IT WRITES CARRIES NO VERDICT.

        The answer document is a record of what the engine did: its prose, its statements, its
        result grid, its own disclosures, and the provenance needed to say what it was judged
        against. Every oracle-relative claim is derived ONCE, at projection time, by
        ``sdk.acceptance.flags``. It used to be derived in three places — stamped here,
        recomputed in the projector, re-derived a third time in JavaScript — and all three drifted
        with nothing guarding them.

    Four keys are NEW and every reader must treat them as optional, because the captures already
    committed predate them: ``acceptance_fingerprint`` (a missing one raises the ``evidence_stale``
    corpus-health warning), ``sql_errors`` and ``disclosures`` (both produced by ``local_ask`` and
    previously dropped on the floor), and ``result.sample_rows``.

    Returns ``{ok, ran, rejected, dashboard}``. ``rejected`` carries the captures whose id failed
    the containment check — they name no file and are persisted not at all."""
    acc = bundle / "acceptance"
    (acc / "answers").mkdir(parents=True, exist_ok=True)
    fp = _q._ontology_fingerprint(bundle)
    # The AUTHORED-acceptance hash (corpus + oracles + anchors), computed once per batch. The
    # ontology fingerprint above cannot see an oracle edit, which is why every capture read "fresh"
    # while the assertions it was judged against were being rewritten under it.
    acc_fp = _io.acceptance_fingerprint(bundle)
    eng = payload.get("engine") or {}
    model = eng.get("model") or ""
    effort = eng.get("effort") or ""
    provider = eng.get("provider") or _provider_of(model)
    mode = payload.get("mode") or ("llm-execute" if payload.get("athena") else "llm-answer")
    if mode not in _MODES:
        mode = "llm-answer"
    athena = mode == "llm-execute"

    ran: list[str] = []
    rejected: list[dict] = []
    for item in payload.get("items") or []:
        qid = item.get("id")
        if not qid:
            continue
        # THE containment gate for this op: the id becomes the path of the answers/<id>.yaml write
        # below, so it is checked once, here, before that happens. A poisoned capture is DROPPED
        # and reported rather than failing the whole batch — the model spend for the good captures
        # in the same batch has already happened.
        if not _io.is_safe_qid(qid):
            rejected.append({"id": str(qid)[:120], "error": "invalid question id"})
            print(f"refusing capture with unsafe question id: {qid!r}", file=sys.stderr)
            continue
        ask = item.get("ask") or {}

        res_view = _grade.result_view(ask)
        answer_text = ask.get("answer") or ""
        disp = _grade.disposition(ask)
        sqls = list(ask.get("sql") or [])

        # `llm-validate` backend: parse the composed SQL offline (sqlglot). None when the mode
        # isn't validate OR nothing was composed (nothing to validate → not an invalidity).
        sql_valid = None
        if mode == "llm-validate" and sqls:
            sql_valid = _grade.validate_sql(sqls)["sql_valid"]

        route = "refusal" if disp == "GOVERNED_REFUSAL" else _ROUTE_BY_MODE[mode]
        doc = {
            "id": qid,
            "captured_at": item.get("captured_at") or _now(),
            "ontology_fingerprint": fp,
            "acceptance_fingerprint": acc_fp,
            "engine": {
                "provider": provider,
                "model": model,
                "effort": effort,
                "mode": mode,
                "athena": athena,
            },
            "route": route,
            "answer": answer_text,
            "sql": sqls,
            "sql_valid": sql_valid,
            "sql_errors": list(ask.get("sql_errors") or []),
            "disclosures": list(ask.get("disclosures") or []),
            "result": res_view,
            "error": (str(item["error"])[:500] if item.get("error") else None),
        }
        _io.atomic_write(
            acc / "answers" / f"{qid}.yaml",
            yaml.safe_dump(doc, sort_keys=False, allow_unicode=True),
        )
        ran.append(qid)

    dash = _q.build(bundle)
    return {"ok": True, "ran": ran, "rejected": rejected, "dashboard": dash}


def op_upsert(bundle: Path, payload: dict, *, full_replace: bool) -> dict:
    """UPSERT questions.yaml from parsed rows, then re-project. ``payload`` = {rows:[{id, question,
    tags[], complexity, category, regression}]}."""
    acc = bundle / "acceptance"
    acc.mkdir(parents=True, exist_ok=True)
    corpus_path = acc / "questions.yaml"
    existing = []
    if corpus_path.exists():
        existing = yaml.safe_load(corpus_path.read_text(encoding="utf-8")) or []
    by_id: dict = {}
    order: list[str] = []
    for e in existing:
        if isinstance(e, dict) and e.get("id"):
            by_id[e["id"]] = dict(e)
            order.append(e["id"])

    rows = payload.get("rows") or []

    # THE containment gate for this op, run over the WHOLE payload before a single byte is
    # written. An id imported here is not a path today — it lands in questions.yaml as text — but
    # it becomes one the moment the corpus is run or projected (answers/<id>.yaml). So the poison
    # is refused at the door, and refused wholesale: a half-imported spreadsheet leaves the
    # operator with no way to tell which rows made it in. This is the sdk-side backstop for the
    # .xlsx import parser, which validates wiki-side and cannot be trusted to (boundaries.yaml:
    # the wiki never imports sdk, so that check is a separate copy).
    bad: list[str] = []
    for r in rows:
        raw = r.get("id") if isinstance(r, dict) else None
        qid = raw.strip() if isinstance(raw, str) else ""
        if qid and not _io.is_safe_qid(qid):
            bad.append(qid[:120])
    if bad:
        raise Refused(
            f"refusing to import {len(bad)} row(s) with an invalid question id "
            f"(a question id names a file under acceptance/): {', '.join(bad[:5])}"
        )

    seen: list[str] = []
    for r in rows:
        qid = (r.get("id") or "").strip()
        if not qid:
            continue
        seen.append(qid)
        entry = by_id.get(qid, {})
        entry["id"] = qid
        if r.get("question"):
            entry["question"] = r["question"]
        if r.get("tags") is not None:
            entry["tags"] = list(r["tags"])
        cx = r.get("complexity")
        entry["complexity"] = cx if (cx in _TIERS) else "auto"
        cat = r.get("category")
        if cat and cat != "auto":
            entry["category"] = cat
        elif "category" in entry and (not cat or cat == "auto"):
            entry.pop("category", None)
        entry["regression"] = r.get("regression") or entry.get("regression") or "optional"
        if qid not in by_id:
            order.append(qid)
        by_id[qid] = entry

    if full_replace:
        keep = set(seen)
        order = [i for i in order if i in keep]

    out_list = [by_id[i] for i in order if i in by_id]
    _io.atomic_write(corpus_path, yaml.safe_dump(out_list, sort_keys=False, allow_unicode=True))
    dash = _q.build(bundle)
    return {"ok": True, "imported": len(seen), "total": len(out_list), "dashboard": dash}


# Keys `--op patch` will write into a corpus entry. Anything else in the payload row is IGNORED
# rather than stored: the corpus is authored content and an endpoint that accepts arbitrary keys is
# an endpoint that will one day be handed a `grade_status`.
_PATCHABLE = ("question", "tags", "complexity", "category", "regression")

# PyYAML's emitter wraps long scalars at `width` (default 80), and the corpus on disk was dumped at
# a different one. MEASURED on the reference corpus: rewriting it at the default width reflows 115
# lines belonging to rows nobody touched — which is precisely the "never re-normalize, reorder, or
# rewrite untouched entries" rule this op exists to honour, broken by a formatting default rather
# than by any decision. The right width is not knowable a priori and is NOT a per-bundle constant
# to hardcode, so it is RECOVERED from the document we just read: the width that reproduces the
# file byte-for-byte is the width that leaves everyone else's rows alone. None -> PyYAML's default,
# which is the honest answer for a file we cannot reproduce (a hand-authored or newly created one).
_WIDTH_SEARCH = range(80, 201)


def _dump_width(previous_text: str, previous_data) -> int | None:
    if not previous_text:
        return None
    for width in _WIDTH_SEARCH:
        if (
            yaml.safe_dump(previous_data, sort_keys=False, allow_unicode=True, width=width)
            == previous_text
        ):
            return width
    return None


def op_patch(bundle: Path, payload: dict) -> dict:
    """Set NAMED KEYS of exactly one corpus entry. Everything else stays byte-identical.

    ``payload`` = ``{"rows": [ {...} ], "create_only": bool, "require_exists": bool}``.

    WHY THIS EXISTS ALONGSIDE ``op_upsert``. Upsert is built for the .xlsx import, which always
    sends every column, so it NORMALISES: it force-sets ``complexity`` to ``"auto"`` unless the
    value exactly matches a tier, forces ``regression`` non-empty, and POPS ``category`` when the
    incoming value is blank or ``"auto"``. Round-tripping a four-field edit form through that
    silently strips an author's pinned category and rewrites two fields the operator never touched.
    Patch performs NO NORMALIZATION OF ANY KIND — a key absent from the row is a key left exactly
    as it was.

    ``yaml.safe_dump`` is safe HERE AND ONLY HERE. ``questions.yaml`` has zero comment lines and is
    already machine-dumped, so a round-trip loses nothing. Every oracle, by contrast, carries an
    authored comment header and prose rationale that safe_dump destroys — NEVER route an oracle
    through this writer.
    """
    rows = payload.get("rows") or []
    if len(rows) != 1:
        raise Refused(f"patch expects exactly one row, got {len(rows)}")
    row = rows[0]
    if not isinstance(row, dict):
        raise Refused("patch expects a row object")

    qid = row.get("id")
    qid = qid.strip() if isinstance(qid, str) else ""
    # Containment: the id addresses acceptance/oracle/<id>.yaml and acceptance/answers/<id>.yaml
    # the moment this row is run or projected, so it is refused at the door even though this op
    # only ever writes questions.yaml.
    if not _io.is_safe_qid(qid):
        raise Refused(f"invalid question id: {str(row.get('id'))[:120]!r}")

    acc = bundle / "acceptance"
    acc.mkdir(parents=True, exist_ok=True)
    corpus_path = acc / "questions.yaml"
    previous_text = ""
    existing = []
    if corpus_path.exists():
        previous_text = corpus_path.read_text(encoding="utf-8")
        existing = yaml.safe_load(previous_text) or []
    entries = [dict(e) for e in existing if isinstance(e, dict)]
    width = _dump_width(previous_text, existing)

    index = next((i for i, e in enumerate(entries) if e.get("id") == qid), None)
    exists = index is not None

    if payload.get("create_only") and exists:
        raise RefusedCode("exists", f"a question with id {qid} already exists")
    if payload.get("require_exists") and not exists:
        raise RefusedCode("missing", f"no question with id {qid}")

    if exists:
        entry = entries[index]
    else:
        # A new id APPENDS. Existing ids keep their position, because the corpus order is authored
        # (it groups the classes) and a writer that reorders makes every diff unreadable.
        entry = {"id": qid}
        entries.append(entry)
        index = len(entries) - 1

    changed: list[str] = []
    for key in _PATCHABLE:
        if key not in row:
            continue
        value = row[key]
        if key == "tags" and isinstance(value, (list, tuple)):
            value = [str(t) for t in value]
        if entry.get(key) != value or key not in entry:
            entry[key] = value
            changed.append(key)
    entries[index] = entry

    _io.atomic_write(
        corpus_path,
        yaml.safe_dump(entries, sort_keys=False, allow_unicode=True, width=width)
        if width
        else yaml.safe_dump(entries, sort_keys=False, allow_unicode=True),
    )
    return {"ok": True, "id": qid, "created": not exists, "changed": changed}


def op_explain(bundle: Path, payload: dict) -> dict:
    """READ-ONLY: resolve one question exactly as the projector does and return its evaluation.

    Loads the corpus row, the oracle (with its error, if any), the capture, and the anchors index,
    then calls ``flags.evaluate``. No Athena, no model, no write — this is the zero-cost way to ask
    the grader why a row reads the way it does, and it is the tool a disagreement about a verdict
    should be settled with rather than by tuning the grader until the board looks nicer.
    """
    qid = payload.get("id")
    qid = qid.strip() if isinstance(qid, str) else ""
    if not _io.is_safe_qid(qid):
        raise Refused(f"invalid question id: {str(payload.get('id'))[:120]!r}")

    acc = bundle / "acceptance"
    corpus = _corpus(acc)
    row = next((e for e in corpus if e.get("id") == qid), None)
    if row is None:
        raise Refused(f"no question with id {qid} in acceptance/questions.yaml")

    oracle, oracle_error = _load_oracle_doc(acc, qid)
    answer = _load_answer(acc, qid)
    index = _anchors.build_index(bundle, [e["id"] for e in corpus])
    fingerprint = _io.acceptance_fingerprint(bundle)

    result = _flags.evaluate(
        corpus_row=row,
        oracle=oracle,
        oracle_error=oracle_error,
        answer=answer,
        anchor=index["graded"].get(qid),
        advisory_anchors=index["advisory"].get(qid, []),
        acceptance_fingerprint=fingerprint,
        concept_rules=_ontrules.build_index(bundle)["rules"],
    )
    return {
        "ok": True,
        "id": qid,
        "question": row.get("question"),
        "acceptance_fingerprint": fingerprint,
        "run_status": _grade.run_status(answer),
        "oracle_error": oracle_error,
        **result,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Question Lighthouse orchestrator (grade-batch / upsert / patch / explain)"
    )
    ap.add_argument("--op", required=True, choices=["grade-batch", "upsert", "patch", "explain"])
    ap.add_argument("--bundle", required=True, help="path to the <domain>/<dataset> bundle dir")
    ap.add_argument("--input", required=True, help="path to the JSON payload")
    ap.add_argument(
        "--full-replace", action="store_true", help="upsert: drop ids absent from the sheet"
    )
    a = ap.parse_args(argv)
    bundle = Path(a.bundle)
    payload = json.loads(Path(a.input).read_text(encoding="utf-8"))
    try:
        if a.op == "grade-batch":
            out = op_grade_batch(bundle, payload)
        elif a.op == "upsert":
            out = op_upsert(bundle, payload, full_replace=a.__dict__["full_replace"])
        elif a.op == "patch":
            out = op_patch(bundle, payload)
        else:
            # PRETTY, MULTI-LINE, and deliberately outside the last-stdout-line JSON convention the
            # other ops follow: explain is a human debugging tool read in a terminal, and the wiki
            # never calls it. Anything that DOES need to parse it should read the whole stream.
            print(
                json.dumps(
                    op_explain(bundle, payload),
                    indent=2,
                    ensure_ascii=False,
                    sort_keys=False,
                    default=str,
                )
            )
            return 0
    except Refused as e:
        # The wiki parses the LAST stdout line as JSON and maps a falsy `ok` to HTTP 500 with this
        # message; a bare traceback on stderr would surface as "produced no JSON" and tell the
        # operator nothing about which id was refused. A RefusedCode additionally carries the
        # stable word the HTTP layer switches on (`exists` -> 409, `missing` -> 404).
        code = getattr(e, "code", None)
        body = {"ok": False, "error": code or str(e)}
        if code:
            body["detail"] = str(e)
        print(json.dumps(body))
        return 2
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
