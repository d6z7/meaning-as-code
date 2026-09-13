"""sdk.authoring.operations — the SOLE write path to the ontology SSOT (sources/**).

Every mutation of planes 1-2 goes through an allowed operation here. Each op VALIDATES
(status gate) before writing and REFUSES to persist anything that is not gate-clean
(status not in {valid, fixed}) — so an out-of-grammar / invalid candidate produces ZERO
files on disk. Harvest and every other authoring caller MUST route through these
functions; no other module may call a write primitive against sources/** (enforced by
sdk/gate/check_write_paths.py).

Closes adversary finding #1 ("harvest bulk-author writes out-of-grammar YAML regardless
of validation status"): the `if obj is not None: write` branch is gone — persistence is
conditioned on the validation status, here, at the single writer.
"""

from __future__ import annotations

from pathlib import Path

import yaml

# The only statuses an authored object may carry and still be persisted.
PERSISTABLE = {"valid", "fixed"}


class Refused(Exception):
    """A write was refused because the object is not gate-clean or is out of bounds."""


def _assert_in_sources(path: Path) -> Path:
    """Containment guard: every SSOT write target must resolve inside a DECLARED bundle.

    It used to test whether any path component CONTAINS the substring "sources". That passed for
    one bundle because its repository happens to be NAMED for the word, and REFUSED two others that
    are equally legitimate -- the public example bundle among them. A guard whose verdict depends on
    what a checkout was called is not a containment guard; it is a coincidence.

    The declaration is what a bundle actually has: `mac.project.yaml` at its root. Walk up from the
    target and accept when an ancestor carries one. Same property, stated by the thing itself, and
    it holds whatever anyone named the directory.
    """
    p = path.resolve()
    for ancestor in (p, *p.parents):
        if (ancestor / "mac.project.yaml").is_file():
            return p
    raise Refused(
        f"refusing to write outside a declared bundle: {p} — no ancestor carries mac.project.yaml"
    )


def _write_ssot(path: Path, text: str) -> Path:
    """THE single low-level SSOT write. All persisted planes-1-2 bytes flow through here."""
    p = _assert_in_sources(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def write_lookup_csv(path: Path, text: str) -> Path:
    """A generated lookup register, persisted as SSOT.

    Named rather than generic: `materialize.py` used to write this itself with a bare
    `.write_text()`, which is how the sole-writer rule acquired a second implementation. Routing it
    here puts it behind the containment guard like every other persisted plane-1-2 byte.
    """
    return _write_ssot(Path(path), text)


def persist_concept(concepts_dir, stem: str, result: dict) -> dict:
    """author-concept: persist a validated concept YAML. Refuse unless gate-clean.

    `result` is the dict returned by sdk.authoring.authoring.process().
    """
    status = result.get("status")
    if status not in PERSISTABLE or result.get("obj") is None:
        return {
            "op": "author-concept",
            "stem": stem,
            "written": False,
            "status": status,
            "reason": f"status={status!r} not in {sorted(PERSISTABLE)}",
        }
    path = _write_ssot(Path(concepts_dir) / f"{stem}.yaml", result["yaml"])
    return {
        "op": "author-concept",
        "stem": stem,
        "written": True,
        "status": status,
        "path": str(path),
    }


def _extract_transform_sql(data_dir, stem: str, obj: dict, sql_body) -> str | None:
    """Move the transform's materializable view BODY into a sibling data/transforms/<stem>.sql and
    leave ONLY a `produces.sql_file: <stem>.sql` pointer in the YAML — never a multi-line inline
    `sql:` scalar (that is the read/lint/diff/run bug + double-maintenance). This mirrors how the
    gold ships it (dim_country.yaml + dim_country.sql) and lets the materialize step run the `.sql`
    directly. `sql_body` is the out-of-band body lifted by the data-plane author (top-level
    `transform_sql`); as a fallback we also drain any inline `sql`/`x-sql` the object still carries.
    Returns the written SQL text, or None when there is nothing to extract."""
    produces = obj.get("produces") if isinstance(obj, dict) else None
    body = sql_body
    if isinstance(produces, dict):
        for k in ("sql", "x-sql"):  # defensive: never persist an inline body
            leaked = produces.pop(k, None)
            if not body and leaked:
                body = leaked
    for k in ("sql", "x-sql"):  # also drain a top-level inline body
        leaked = obj.pop(k, None) if isinstance(obj, dict) else None
        if not body and leaked:
            body = leaked
    if not body or not str(body).strip():
        return None
    text = str(body)
    if not text.endswith("\n"):
        text += "\n"
    _write_ssot(Path(data_dir) / "transforms" / f"{stem}.sql", text)
    if isinstance(produces, dict):
        produces["sql_file"] = f"{stem}.sql"  # canonical pointer == the stem
    return text


def persist_descriptors(data_dir, stem: str, files: dict, statuses: dict) -> dict:
    """author-source-descriptor / propose-transform / build-served-view: persist the
    source|transform|dataset descriptors for one table. Each file is persisted only if
    ITS OWN status is gate-clean; a bad one is skipped — never a half-written lie.

    When the transform is persisted, its realizing view body is EXTRACTED to a sibling
    data/transforms/<stem>.sql and the YAML keeps only a `produces.sql_file` pointer (never an
    inline multi-line `sql:` scalar). `files['transform']` may carry a `sql_body` (the body the
    data-plane author lifted from the top-level `transform_sql`).
    """
    out = {"op": "author-descriptors", "stem": stem, "written": [], "refused": [], "sql_files": []}
    for kind, sub in (("source", "sources"), ("transform", "transforms"), ("dataset", "datasets")):
        f = files.get(kind)
        if not f or f.get("obj") is None:
            continue
        st = (statuses or {}).get(kind)
        if st not in PERSISTABLE:
            out["refused"].append({"kind": kind, "status": st})
            continue
        obj = f["obj"]
        if kind == "transform":
            sqlf = _extract_transform_sql(data_dir, stem, obj, f.get("sql_body"))
            if sqlf is not None:
                out["sql_files"].append(f"{stem}.sql")
        text = yaml.safe_dump(obj, sort_keys=False, allow_unicode=True)
        _write_ssot(Path(data_dir) / sub / f"{stem}.yaml", text)
        out["written"].append(kind)
    return out


def persist_edges(ontology_dir, result: dict) -> dict:
    """author-edges: persist a validated EdgesFile to <ontology>/edges.yaml. Refuse unless
    gate-clean (status ∈ {valid, fixed}) — an out-of-grammar edge set produces ZERO files.

    `result` is the dict returned by sdk.authoring.edges.make_edges_file().
    """
    status = result.get("status")
    if status not in PERSISTABLE or result.get("obj") is None:
        return {
            "op": "author-edges",
            "written": False,
            "status": status,
            "reason": f"status={status!r} not in {sorted(PERSISTABLE)}",
        }
    text = yaml.safe_dump(result["obj"], sort_keys=False, allow_unicode=True)
    path = _write_ssot(Path(ontology_dir) / "edges.yaml", text)
    return {
        "op": "author-edges",
        "written": True,
        "status": status,
        "path": str(path),
        "edges": len(result["obj"].get("edges", [])),
    }


def persist_register(data_dir, register: dict) -> dict:
    """Persist the aggregate DQ register (not per-table). Refuse if empty/malformed.

    IDEMPOTENCY: issues are sorted by id before dump, so a re-harvest's Glue table-scan order
    cannot move the register bytes (same findings -> same file -> same publish tree hash)."""
    if not isinstance(register, dict) or not register.get("issues"):
        return {"op": "persist-register", "written": False, "reason": "empty/invalid register"}
    register = {
        **register,
        "issues": sorted(
            register["issues"], key=lambda i: str(i.get("id") or i.get("finding_id") or "")
        ),
    }
    text = yaml.safe_dump(register, sort_keys=False, allow_unicode=True)
    path = _write_ssot(Path(data_dir) / "quality" / "data_quality_register.yaml", text)
    return {
        "op": "persist-register",
        "written": True,
        "path": str(path),
        "issues": len(register["issues"]),
    }


def capture_oracle_from_ruling(acceptance_dir, ruling: dict, executor, *, tolerance=None) -> dict:
    """capture-oracle-from-ruling: turn a plane-3 RULING into an acceptance oracle — but
    RE-DERIVE the value by EXECUTING the ruling's `sql_contains` (never copy the SME's scalar).

    Adversary finding (critical, no-hallucination): a `ruling` may carry a fabricated number;
    if the developer transcribed it verbatim, a model/human-prose value would become acceptance
    truth. So this op DUAL-KEYS: it stores the SME-asserted value (advisory) AND the executed
    value (authoritative), and REFUSES to write the oracle if they diverge beyond tolerance —
    the operator must adjudicate. `executor(sql) -> value` is injected (Athena at build time).
    """
    r = (ruling or {}).get("ruling") or {}
    sql = r.get("sql_contains")
    if not sql:
        return {
            "op": "capture-oracle",
            "written": False,
            "reason": "ruling has no sql_contains to execute",
        }
    asserted = r.get("expected_value")
    tol = tolerance if tolerance is not None else (r.get("tolerance") or 0)
    executed = executor(sql)  # independent, executed result
    diverged = (
        asserted is not None
        and isinstance(executed, (int, float))
        and isinstance(asserted, (int, float))
        and abs(executed - asserted) > (tol or 0)
    )
    oracle = {
        "id": ruling.get("id"),
        "from_ruling": ruling.get("id"),
        "expected": {
            "outcome": r.get("expected_outcome"),
            "value": executed,  # AUTHORITATIVE = executed
            "value_col": r.get("value_col"),
            "tolerance": tol,
        },
        "provenance": {
            "sql": sql,
            "sme_asserted_value": asserted,  # advisory only
            "executed_value": executed,
            "diverged": bool(diverged),
        },
    }
    if diverged:
        return {
            "op": "capture-oracle",
            "written": False,
            "oracle": oracle,
            "reason": f"DIVERGENCE: SME asserted {asserted} but SQL executed {executed} "
            f"(> tolerance {tol}) — operator must adjudicate; oracle NOT written",
        }
    text = yaml.safe_dump(oracle, sort_keys=False, allow_unicode=True)
    path = _write_ssot(Path(acceptance_dir) / "oracle" / f"{ruling.get('id')}.yaml", text)
    return {"op": "capture-oracle", "written": True, "path": str(path), "executed_value": executed}
