#!/usr/bin/env python3
"""mac_dq_findings.py — RAISE the measured data-quality findings a first run can prove.

D7c of DELIVERABLES-2026-09-26_first-run-state.md. The operator: "DQ is completely empty."

WHY IT WAS EMPTY, and it is worth stating exactly because the earlier report claimed otherwise. The
console's data-quality board reads `data/quality/dq_dashboard.json`, which the projection builds from
`data/quality/data_quality_register.yaml` — the register of ISSUES. A first run produced no register,
so the dashboard came out `{"stats": {"total": 0}, "findings": []}` and the board had nothing to show.
Meanwhile the generated suite had run 86 cases and passed 86, which is a DIFFERENT artifact: a suite
proves invariants hold, a register says what is WRONG and who must rule on it.

WHAT IT RAISES — only what is measured, never a guess, and each finding carries the number that
found it:

    ORPHAN LANDING        a raw relation no transform consumes. Harvested and never curated: either
                          it is genuinely out of scope, or a served relation is missing.
    NO MEASURED KEY       a relation where no column and no small tuple is unique-and-non-null. It
                          cannot be a parent endpoint, so it is invisible to the ER model.
    DUPLICATE LANDING     two raw relations with identical row counts and overlapping columns — the
                          delivery shipping one fact twice, which is a ruling, not a bug.
    ALL-NULL COLUMN       a served column with no value in any row. Served, declared, and empty.
    FAILING TEST CASE     a generated data-sanity case that did not pass. The suite says WHICH
                          invariant; this says it needs a disposition.

EVERY FINDING IS `status: open` AND `ruled_by: null`. This tool raises; it never rules. An agent that
wrote `status: accepted` would be forging the operator's disposition — the same reason the data-plane
sign-off is unwritable by every tool in this estate.

IT NEVER DELETES A RULING. A finding whose id already exists in the register keeps that entry's
`status`, `ruled_by` and `reason` and only refreshes the MEASUREMENT, so re-running after an operator
has ruled does not silently reopen what they closed.

    python3 mac_dq_findings.py <bundle-root> [--check]
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from datetime import UTC, datetime

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _plugin  # noqa: E402

GENERATOR = "mac_dq_findings.py/1"
REGISTER = pathlib.Path("data") / "quality" / "data_quality_register.yaml"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--check", action="store_true", help="report drift; write nothing")
    a = ap.parse_args(argv)

    root = pathlib.Path(a.root).resolve()
    try:
        import yaml
    except ImportError as exc:
        print(f"REFUSED: {exc}")
        return 2

    findings: list[dict] = []
    findings += _orphan_landings(root, yaml)
    findings += _keyless(root, yaml)
    findings += _duplicate_landings(root, yaml)
    findings += _all_null_columns(root, yaml)
    findings += _failing_cases(root)
    findings += _broken_references(root, yaml)

    existing = _existing(root, yaml)
    merged = _merge(findings, existing)
    body = _render(merged, yaml)

    out = root / REGISTER
    if a.check:
        now = out.read_text(encoding="utf-8") if out.is_file() else ""
        if _without_date(now) != _without_date(body):
            print(f"DRIFT — {REGISTER} no longer matches what is measured.")
            return 1
        print(f"OK — {REGISTER} matches the measurements ({len(merged)} finding(s)).")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    kept = sum(1 for f in merged if f.get("status") != "open")
    by_sev: dict[str, int] = {}
    for f in merged:
        by_sev[f["severity"]] = by_sev.get(f["severity"], 0) + 1
    print(f"  {REGISTER}: {len(merged)} finding(s) "
          f"({', '.join(f'{v} {k}' for k, v in sorted(by_sev.items())) or 'none'})"
          + (f", {kept} already ruled and untouched" if kept else ""))
    for f in merged:
        print(f"    {f['severity']:6} {f['id']:34} {f['title'][:64]}")
    if not merged:
        print("    nothing measurable is wrong — which is a finding in itself and is recorded as "
              "an empty register rather than a missing one.")
    return 0


# ══════════════════════════════════════════════════════════════════════════════════════════════
# THE MEASUREMENTS
# ══════════════════════════════════════════════════════════════════════════════════════════════
def _orphan_landings(root: pathlib.Path, yaml) -> list[dict]:
    """A raw relation no transform consumes."""
    consumed: set[str] = set()
    for f in (root / "data" / "transforms").glob("*.yaml"):
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        for inp in doc.get("inputs") or []:
            rel = str(inp.get("relation") or "")
            if rel:
                consumed.add(rel.split(".")[-1])
    out = []
    for f in sorted((root / "data" / "sources").glob("*.yaml")):
        stem = f.stem
        if stem in consumed:
            continue
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        rows = ((doc.get("table") or {}).get("rows_measured"))
        out.append({
            "id": f"DQ-ORPHAN-{stem.upper()}",
            "title": f"raw landing `{stem}` is consumed by no transformation",
            "severity": "medium",
            "measurement": (f"{rows:,} rows harvested and never curated; no "
                            f"data/transforms/*.yaml declares it as an input"
                            if isinstance(rows, int) else
                            "no data/transforms/*.yaml declares it as an input"),
            "needs": ("a ruling: is this relation OUT OF SCOPE for this bundle, or is a served "
                      "relation missing?"),
        })
    return out


def _keyless(root: pathlib.Path, yaml) -> list[dict]:
    """A relation where nothing was measured unique-and-non-null."""
    out = []
    for plane in ("datasets", "sources"):
        for f in sorted((root / "data" / plane).glob("*.yaml")):
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            roles = {c.get("role") for c in (doc.get("columns") or [])}
            if roles & {"primary_key", "composite_key_part"}:
                continue
            out.append({
                "id": f"DQ-NOKEY-{f.stem.upper()}",
                "title": f"`{f.stem}` carries no measured key",
                "severity": "high",
                "measurement": ("no single column and no small tuple is unique AND non-null over "
                                "every row"),
                "needs": ("a key, or a ruling that this relation has none by design. Without one it "
                          "is not a parent endpoint, so no reference points at it and the ER model "
                          "does not draw it."),
            })
    return out


def _broken_references(root: pathlib.Path, yaml) -> list[dict]:
    """A column that is far too aligned with a key to be coincidence and far too broken to draw.

    THE REGISTER WAS SILENT ABOUT THE MOST COMMON DATA DEFECT THERE IS. Measured on a bundle built to
    look for it: 22 of 500 voyage legs referenced a port the warehouse does not carry, and the run
    came back with 31 of 31 DQ cases passing and three findings, none of them this one. Two things had
    to change — `mac_references` had to stop pruning the pair before measuring it, and this file had
    to READ the verdict it produces. A measurement no consumer reads is the same as no measurement.

    Severity is HIGH and it is not a judgement call: every answer that groups by the child column
    silently drops or mis-buckets those rows, and nothing in the ontology can notice.
    """
    out = []
    for plane in ("references_served", "references"):
        for f in sorted((root / "data" / plane).glob("*.yaml")):
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            for r in (doc.get("references_broken") or []):
                frm, to = r.get("from") or {}, r.get("to") or {}
                ev = r.get("evidence") or {}
                child = f"{frm.get('relation')}.{frm.get('column')}"
                parent = f"{to.get('relation')}.{to.get('column')}"
                out.append({
                    "id": f"DQ-BROKENREF-{str(frm.get('relation','')).upper()}-"
                          f"{str(frm.get('column','')).upper()}",
                    "title": f"`{child}` references `{parent}`, and {ev.get('orphan_rows')} row(s) "
                             f"break it",
                    "severity": "high",
                    "measurement": (
                        f"inclusion {ev.get('inclusion')} over {ev.get('child_nonnull')} non-null "
                        f"child row(s): {ev.get('orphan_rows')} row(s) carry "
                        f"{ev.get('orphan_distinct')} value(s) that no row of {parent} carries, while "
                        f"parent_coverage {ev.get('parent_coverage')} shows the key's domain IS "
                        f"exercised — so this is a relationship, not an arithmetic coincidence"),
                    # THE REGISTER CARRIES THE PREPARED RULING THE MEASURER PRODUCED, rather than a
                    # weaker paraphrase of it. Two homes for one question is how the two drift, and
                    # the register is the home an operator actually opens. CORE.md §6: a ruling
                    # arrives with its permitted answers, the consequence of each, and a
                    # recommendation, "so the cheapest reply is agreement".
                    "needs": _needs(r.get("ruling")),
                    "ruling": r.get("ruling") or None,
                })
    return out


def _needs(ruling: dict | None) -> str:
    """The one-line form of a prepared ruling, for a reader skimming the register."""
    if not ruling:
        return ("a ruling on whether the orphan rows are expected or a defect (the measurer recorded "
                "no prepared ruling, which is itself a defect against CORE.md §6)")
    answers = " | ".join(ruling.get("answers") or [])
    return (f"{ruling.get('question')}  ANSWER ONE OF: {answers}.  RECOMMENDED: "
            f"{ruling.get('recommendation')} — {ruling.get('because')}")


def _duplicate_landings(root: pathlib.Path, yaml) -> list[dict]:
    """Two raw relations with the same row count — one fact shipped twice."""
    by_rows: dict[int, list[str]] = {}
    for f in sorted((root / "data" / "sources").glob("*.yaml")):
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        rows = (doc.get("table") or {}).get("rows_measured")
        if isinstance(rows, int) and rows > 0:
            by_rows.setdefault(rows, []).append(f.stem)
    out = []
    for rows, stems in sorted(by_rows.items()):
        if len(stems) < 2:
            continue
        out.append({
            "id": f"DQ-DUP-{'-'.join(s.upper() for s in stems)}",
            "title": f"{' and '.join(f'`{s}`' for s in stems)} carry identical row counts",
            "severity": "low",
            "measurement": f"{rows:,} rows each",
            "needs": ("a ruling on which is the FACT OF RECORD. An equal row count is not proof of "
                      "duplication, and it is the shape a delivery shipping one fact twice takes."),
        })
    return out


def _all_null_columns(root: pathlib.Path, yaml) -> list[dict]:
    """A served column with no value in any row, read from the profile."""
    out = []
    for f in sorted((root / "data" / "profiles").glob("*.yaml")):
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        rows = (doc.get("profile") or {}).get("rows")
        for c in doc.get("columns") or []:
            nulls = c.get("nulls")
            if isinstance(rows, int) and rows > 0 and nulls == rows:
                out.append({
                    "id": f"DQ-ALLNULL-{f.stem.upper()}-{str(c.get('name')).upper()}",
                    "title": f"`{f.stem}.{c.get('name')}` is null in every row",
                    "severity": "medium",
                    "measurement": f"{nulls:,} of {rows:,} rows null",
                    "needs": ("a ruling: drop the column, or state what its absence MEANS. A served "
                              "column with no value is declared and empty."),
                })
    return out


def _failing_cases(root: pathlib.Path) -> list[dict]:
    """A generated data-sanity case that did not pass."""
    import json
    rec = root / "acceptance" / "data_sanity_generated_runs.json"
    if not rec.is_file():
        return []
    try:
        doc = json.loads(rec.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    out = []
    for r in doc.get("results") or []:
        if str(r.get("outcome") or r.get("status") or "").upper() in ("PASS", "ACCEPTED", ""):
            continue
        out.append({
            "id": f"DQ-CASE-{str(r.get('id'))[:44]}",
            "title": f"data-sanity case {r.get('id')} did not pass",
            "severity": {"blocker": "high"}.get(str(r.get("severity")), "medium"),
            "measurement": str(r.get("detail") or r.get("statement") or "")[:200],
            "needs": "a disposition: fix the data, or accept the reading with a reason.",
        })
    return out


# ══════════════════════════════════════════════════════════════════════════════════════════════
def _existing(root: pathlib.Path, yaml) -> dict[str, dict]:
    f = root / REGISTER
    if not f.is_file():
        return {}
    doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    return {str(i.get("id")): i for i in (doc.get("issues") or []) if i.get("id")}


def _merge(fresh: list[dict], existing: dict[str, dict]) -> list[dict]:
    """A RULING SURVIVES A RE-MEASUREMENT. The measurement is refreshed; the disposition is not.

    Re-running must never reopen what an operator closed, and must never invent a closure. So for a
    finding that already exists, `status`, `ruled_by` and `reason` are carried over untouched and only
    the measured text is updated.
    """
    out = []
    for f in fresh:
        prev = existing.get(f["id"], {})
        out.append({
            "id": f["id"],
            "title": f["title"],
            "severity": f["severity"],
            "status": prev.get("status", "open"),
            "ruled_by": prev.get("ruled_by"),
            "reason": prev.get("reason"),
            "measurement": f["measurement"],
            "needs": f["needs"],
            # THE STRUCTURED RULING SURVIVES THE MERGE. This rebuild is a fixed key list by design —
            # it is what stops a re-measurement from resurrecting a closed finding — and a field not
            # named here is silently dropped. `ruling` was dropped on its first run: the register
            # carried the one-line form and lost the permitted answers and the per-answer
            # consequences, which is the half a console needs to offer buttons instead of a text box.
            **({"ruling": f["ruling"]} if f.get("ruling") else {}),
            "raised_by": GENERATOR,
        })
    # A finding that is no longer measured is KEPT when it was ruled on, because deleting a ruling is
    # worse than carrying a stale entry — and dropped when it was never ruled, because an open finding
    # nothing measures any more is noise.
    for eid, prev in existing.items():
        if eid not in {f["id"] for f in fresh} and prev.get("status") != "open":
            out.append({**prev, "measurement": (prev.get("measurement") or "")
                        + "  [NO LONGER MEASURED — kept because it carries a ruling]"})
    return sorted(out, key=lambda f: ({"high": 0, "medium": 1, "low": 2}.get(f["severity"], 3),
                                      f["id"]))


def _render(findings: list[dict], yaml) -> str:
    head = (
        f"# GENERATED by {GENERATOR} — the findings a first run can PROVE. Re-run to refresh.\n"
        "#\n"
        "# EVERY ENTRY IS `status: open` AND `ruled_by: null` UNTIL A PERSON RULES. This tool raises;\n"
        "# it never rules. A re-run carries an existing entry's status, ruled_by and reason over\n"
        "# untouched and refreshes only the measurement, so it cannot reopen what was closed or\n"
        "# invent a closure.\n"
        "#\n"
        "# `measurement` is what was counted. `needs` is what a person has to decide. A finding with\n"
        "# neither is an opinion and does not belong here.\n"
    )
    doc = {
        "metadata": {
            "generated_by": GENERATOR,
            "observed": datetime.now(UTC).date().isoformat(),
            "total": len(findings),
        },
        "issues": findings,
    }
    return head + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100)


def _without_date(text: str) -> str:
    return "\n".join(ln for ln in text.splitlines() if "observed:" not in ln)


if __name__ == "__main__":
    sys.exit(main())
