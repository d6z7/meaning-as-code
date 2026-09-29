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
import re
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
    findings += _identifying_columns(root, yaml)
    findings += _failing_cases(root)
    findings += _broken_references(root, yaml)
    findings += _ambiguous_references(root, yaml)
    findings += _dangling_keys(root, yaml)
    findings += _unclaimed_served(root, yaml)

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
            "finding": (f"{rows:,} rows harvested and never curated; no "
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
            if roles & {"primary_key"}:
                continue
            out.append({
                "id": f"DQ-NOKEY-{f.stem.upper()}",
                "title": f"`{f.stem}` carries no measured key",
                "severity": "high",
                "finding": ("no single column and no small tuple is unique AND non-null over "
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
                    "finding": (
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


def _ambiguous_references(root: pathlib.Path, yaml) -> list[dict]:
    """A column that includes PERFECTLY into two different keys, so value evidence cannot choose.

    THE MEASURER ALREADY REFUSES TO GUESS — it records `ambiguous_with` and `needs_ruling` rather than
    picking — but the record sat in a reference artifact that no board reads, so the decision was
    invisible and therefore never made. On a vanilla bundle there were 8 such entries; they are ONE
    question asked 8 times, and grouping them is the difference between a decision and a backlog.

    Severity is HIGH because the failure mode is a plausible number. Choosing the wrong side of an FX
    pair does not error — it converts by the reciprocal rate, and the total still looks like money.
    """
    fams: dict[tuple, dict] = {}
    for plane in ("references_served", "references"):
        for f in sorted((root / "data" / plane).glob("*.yaml")):
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            for r in (doc.get("references") or []):
                if not r.get("ambiguous_with"):
                    continue
                to = r.get("to") or {}
                col = str((r.get("from") or {}).get("column"))
                targets = tuple(sorted(set(r["ambiguous_with"]) |
                                       {f"{to.get('relation')}.{to.get('column')}"}))
                key = (col, targets)
                fam = fams.setdefault(key, {"col": col, "targets": list(targets), "seen": 0,
                                            "carriers": set()})
                fam["seen"] += 1
                fam["carriers"].add(str((r.get("from") or {}).get("relation")))
    out, emitted = [], set()
    for (col, targets), fam in sorted(fams.items()):
        n = fam["seen"]
        fid = f"DQ-AMBIGREF-{col.upper()}"
        if fid in emitted:
            continue          # one question, asked on both planes, is still ONE finding
        emitted.add(fid)
        out.append({
            "id": f"DQ-AMBIGREF-{col.upper()}",
            "title": f"`{col}` includes perfectly into {len(targets)} different keys — which is THE "
                     f"reference?",
            "severity": "high",
            "finding": (
                f"measured on {n} reference(s) across {len(fam['carriers'])} relation(s) "
                f"({', '.join(sorted(fam['carriers']))}): inclusion is 1.0 into every one of "
                f"{', '.join(targets)}, at the same key role and over the same rows. Value inclusion "
                f"CANNOT separate them, so neither was drawn as the sole reference."),
            "needs": (f"Which of {', '.join(targets)} is THE reference for {col}?  "
                      f"ANSWER ONE OF: {' | '.join(targets)} | both_are_real | neither.  "
                      f"No recommendation is offered from the data because the data cannot carry one."),
            "ruling": {
                "question": f"{col} includes perfectly into all of {', '.join(targets)}. Which is THE "
                            f"reference?",
                "answers": list(targets) + ["both_are_real", "neither"],
                "established": (
                    f"inclusion 1.0 into each candidate, same key role, {n} instance(s) over "
                    f"{len(fam['carriers'])} relation(s). The candidates are equally supported by "
                    f"every measurement this platform can make."),
                "for_the_human": (
                    "Nothing in the values distinguishes these. A pair of endpoints that both hold the "
                    "same domain — the two sides of a conversion, a ship-to and a bill-to, a parent and "
                    "a predecessor — are identical to a measurement and opposite in meaning. Only the "
                    "business's intent separates them.\n\n"
                    "AND THE SYMMETRY IS WHY THIS IS DANGEROUS RATHER THAN MERELY UNDECIDED. Measured "
                    "on a currency pair of this shape: every identity row carries rate 1.0, and "
                    "rate(A->B) x rate(B->A) = 1 for all 80,360 reciprocal rows to within 1.2e-5. The "
                    "table therefore serves BOTH directions equally correctly — so the wrong choice "
                    "raises no error, produces no orphan, and fails no referential case. It returns "
                    "the RECIPROCAL: a EUR amount multiplied by ~1.1 where ~0.9 was meant, a ~20 % "
                    "error that still looks like money."),
                "consequences": {
                    "one of the named targets": (
                        "that reference is drawn, the others are recorded as rejected-by-ruling, and "
                        "questions traverse the chosen direction. IF THE CHOICE IS WRONG THE NUMBERS "
                        "DO NOT ERROR — they come back transformed the wrong way and still look "
                        "plausible, which is the hardest defect to find later."),
                    "both_are_real": (
                        "two references are drawn and every traversal must say which it used; a "
                        "question that does not name a direction becomes ambiguous rather than wrong."),
                    "neither": (
                        f"{col} stays an attribute, no line is drawn, and no question can traverse "
                        f"from it — the join must be written by hand each time, where it is visible."),
                },
                # A RECOMMENDATION IS OWED EVEN WHERE THE VALUES DO NOT LEAN, and the first version of
                # this ruling got that wrong. It offered none, on the grounds that the measurement does
                # not separate the candidates — true, and beside the point. CORE.md §6 requires one "so
                # the cheapest reply is agreement", and a recommendation does not have to come from the
                # values: it can come from CONVENTION, as long as the basis is labelled so the operator
                # can overrule it in one word. "No recommendation" left the whole question on the
                # operator's desk, which is the waste §6 exists to prevent.
                "recommendation": "the endpoint the child is DENOMINATED IN — for an amount and an FX "
                                  "rate table, the child column is the `from` side",
                "because": (
                    "NOT FROM THE VALUES, WHICH DO NOT LEAN — this is domain convention, and it is "
                    "labelled as such so it costs one word to overrule. An amount is denominated in a "
                    "currency and a conversion runs FROM that currency to a reporting one, so the "
                    "column carrying an order's currency is the `from` endpoint. Where the pair is not "
                    "a currency conversion, read the same shape: the child names what the row IS, and "
                    "the reference points at the side that describes it."),
            },
        })
    return out


def _dangling_keys(root: pathlib.Path, yaml) -> list[dict]:
    """A key-shaped column with no parent relation in scope — and three different reasons why.

    The measurer reports these as `references_dangling` with `to: null`, correctly refusing to invent a
    parent. What it cannot do is say WHICH kind of absence it is, and the three kinds want opposite
    treatment. That distinction is computable from what is already measured, so the ruling arrives with
    a recommendation rather than a shrug:

      inline_dimension  a sibling column carries a label at the SAME cardinality, so the "parent" is
                        already on the row (product.CategoryKey 8 distinct, product.CategoryName 8)
      attribute_only    the information the key points at is already denormalised beside it
                        (customer.GeoAreaKey, next to Continent/Country/State/City/ZipCode/Lat/Long)
      missing_extract   neither — the dimension was genuinely not extracted, and anything grouped by
                        it can only report opaque keys
    """
    # KEYED BY (PLANE, STEM), NOT BY STEM. A 1:1 passthrough gives the served relation its landing's
    # name, so a stem-keyed map silently kept whichever plane was read last — the same collision that
    # costs `mac_profile` half its profiles, reproduced here in the code written to explain it. Columns
    # are MERGED across planes for the lookup because a same-named relation on both planes is the same
    # relation, and a curated one that was renamed cannot collide at all.
    desc: dict[str, dict[str, int]] = {}
    for plane in ("datasets", "sources"):
        for f in sorted((root / "data" / plane).glob("*.yaml")):
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            merged = desc.setdefault(f.stem, {})
            for c in (doc.get("columns") or []):
                if c.get("name") and c.get("distinct") is not None:
                    merged[str(c["name"])] = c["distinct"]
    fams: dict[str, dict] = {}
    for plane in ("references_served", "references"):
        for f in sorted((root / "data" / plane).glob("*.yaml")):
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            for r in (doc.get("references_dangling") or []):
                frm = r.get("from") or {}
                col, rel = str(frm.get("column")), str(frm.get("relation"))
                fam = fams.setdefault(col, {"seen": 0, "by_rel": {}})
                fam["seen"] += 1
                fam["by_rel"].setdefault(rel, {"distinct": None, "span": None})
                # THE KEY'S OWN CARDINALITY COMES FROM THE MEASURER, NOT THE DESCRIPTOR. First version
                # of this read it from `data/datasets/<rel>.yaml#columns[].distinct` and got None for
                # every key — the descriptor carries `distinct:` only where a value DOMAIN was
                # captured, and an integer surrogate never is. So the bijection test found no twin for
                # product.CategoryKey (8 distinct) beside product.CategoryName (8 distinct) and
                # recommended `missing_extract` with a confident sentence. A recommendation resting on
                # absent evidence is worse than none: it is wrong AND it looks reasoned.
                # PER CARRIER. Aggregating one number across carriers paired customer's name with
                # store's cardinality — GeoAreaKey reported 67 distinct (store) while the relation
                # named was customer (608). Evidence and the thing it is evidence about must travel
                # together.
                ev = r.get("evidence") or {}
                if ev.get("child_distinct") is not None:
                    fam["by_rel"][rel]["distinct"] = ev["child_distinct"]
                    if ev.get("min") is not None and ev.get("max") is not None:
                        fam["by_rel"][rel]["span"] = (ev["min"], ev["max"])
    out = []
    for col, fam in sorted(fams.items()):
        # THE TWIN TEST RUNS PER CARRIER, and the carrier it finds one on is the one reported.
        hit = None
        for rel_i in sorted(fam["by_rel"]):
            n_i = fam["by_rel"][rel_i]["distinct"]
            # EQUAL CARDINALITY IS NECESSARY AND NOT SUFFICIENT — the same lesson as this morning's
            # dense-integer references. store.GeoAreaKey has 67 distinct and so do store.Description
            # and store.State, over 74 rows; that is a COINCIDENCE, and recommending "the label already
            # travels with the key" from it would have been a confident wrong answer.
            #
            # A LABEL SHARES ITS KEY'S SUBJECT, so the second signal is the name stem: CategoryKey and
            # CategoryName both carry "Category". This does not make a NAME into a verdict — the
            # reference measurer's law still holds and no reference is drawn here. It selects a
            # RECOMMENDATION between answers a person will confirm, and without it the recommendation
            # was wrong on 1 of 3 cases measured.
            stem_i = re.sub(r"(?i)(key|id|code|no)$", "", col) or col
            tw = sorted(c for c, d in desc.get(rel_i, {}).items()
                        if c != col and n_i is not None and d == n_i
                        and stem_i.casefold() in c.casefold())
            if tw:
                hit = (rel_i, n_i, tw, fam["by_rel"][rel_i]["span"])
                break
        rel = hit[0] if hit else sorted(fam["by_rel"])[0]
        n = hit[1] if hit else fam["by_rel"][rel]["distinct"]
        twins = hit[2] if hit else []
        sp = (hit[3] if hit else fam["by_rel"][rel]["span"])
        span = f", dense over {sp[0]}..{sp[1]}" if sp and str(n) == str(sp[1]) else ""
        if twins:
            rec = "inline_dimension"
            why = (f"{rel}.{' / '.join(twins)} carries the SAME {n} distinct value(s) as {col}"
                   f"{span} — the label already travels with the key, so a concept grounds on {rel} "
                   f"and no parent relation is needed at all")
        else:
            # NO RECOMMENDATION, AND THE REASON IS STATED. Measurement separates inline_dimension from
            # the other two (a same-cardinality twin either exists or it does not). It CANNOT separate
            # attribute_only from missing_extract: whether the information the key points at is already
            # denormalised beside it is a question about MEANING, not cardinality —
            # customer.GeoAreaKey sits next to Continent/Country/State/City/ZipCode/Lat/Long, and no
            # count reveals that those describe the same thing the key does.
            rec = None
            why = (f"no column of {rel} shares {col}'s {n if n is not None else 'measured'} distinct "
                   f"value(s), so it is NOT an inline dimension. Between the remaining two answers the "
                   f"measurement does not lean: whether the absent parent's information is already "
                   f"denormalised beside this key is a question about meaning, not cardinality. What "
                   f"would settle it is a look at {rel}'s other columns — if they already describe what "
                   f"{col} points at, it is attribute_only; if nothing does, the extract is incomplete")
        out.append({
            "id": f"DQ-DANGLINGKEY-{col.upper()}",
            "title": f"`{col}` is key-shaped and no relation in scope carries it as a key",
            "severity": "medium",
            "finding": (
                f"reported on {fam['seen']} plane-relation(s) "
                f"({', '.join(f'{r} {v[chr(100)+chr(105)+chr(115)+chr(116)+chr(105)+chr(110)+chr(99)+chr(116)]} distinct' for r, v in sorted(fam['by_rel'].items()))}); "
                f"{n if n is not None else 'an unmeasured number of'} distinct value(s) on {rel}. It "
                f"follows this bundle's own key-naming convention and points at nothing."),
            "needs": (f"Is the parent MISSING from the extract, already INLINE on the row, or is {col} "
                      f"just an attribute?  ANSWER ONE OF: inline_dimension | attribute_only | "
                      f"missing_extract.  "
                      + (f"RECOMMENDED: {rec} — {why}" if rec else f"NO RECOMMENDATION — {why}")),
            "ruling": {
                "question": f"{col} is key-shaped with no parent in scope. Which absence is it?",
                "answers": ["inline_dimension", "attribute_only", "missing_extract"],
                "established": (
                    f"{n if n is not None else '?'} distinct value(s) on {rel}; no relation in scope "
                    f"declares {col} as a key; sibling column(s) at the same cardinality: "
                    f"{', '.join(twins) or 'none'}."),
                "for_the_human": (
                    "A measurement sees an absence; it cannot see whether the absence is a gap in the "
                    "extract or a modelling choice already made. Only someone who knows what was meant "
                    "to be delivered can say."),
                "consequences": {
                    "inline_dimension": (
                        "a concept is grounded on the carrying relation, using the key for identity and "
                        "its twin for the label; no parent relation is ever needed and no line is drawn"),
                    "attribute_only": (
                        f"{col} is an opaque identifier and nothing groups by it — questions use the "
                        f"denormalised attributes beside it instead"),
                    "missing_extract": (
                        "the extract is incomplete and it is recorded as such; until the dimension "
                        "arrives, anything grouped by this key can report only opaque values, and every "
                        "answer over it must say so"),
                },
                "recommendation": rec,
                "because": why,
            },
        })
    return out


def _is_served(raw_stem: str, served: set[str]) -> bool:
    """Is this raw landing served, under its own name or under the convention's served name?

    `v_<dataset>_<stem>` since v0.1.16, so an exact-name test answers False for every relation in a
    bundle that follows the convention the framework publishes.
    """
    return raw_stem in served or any(
        s == raw_stem or s.endswith(f"_{raw_stem}") for s in served)


def _unclaimed_served(root: pathlib.Path, yaml) -> list[dict]:
    """A served relation that no concept claims and nothing declines IN WRITING.

    THE DECLINE WAS MADE AND NEVER DELIVERED. `harvest --mode concepts` asks its planner to account for
    every relation as either a concept's grounding or an entry in `not_a_concept[]`, and it refuses a
    plan that skips one — so the decision is always taken. It is taken in the PLAN, which is a model
    completion in a gitignored cache, and no artifact on disk records it. Measured on contoso4: the plan
    declined `v_contoso4_orderrows` ("the operator ruled `sales` the fact of record") and
    `v_contoso4_orders` ("every one of its six columns is carried by `sales`"), both with reasons, and
    the bundle shows two served relations with no concept and no explanation.

    So `check_delivery_consistency`'s CONCEPT-RELATION invariant reports them, correctly and forever:
    from the delivered artifacts they are relations nobody decided about. Raising them here gives the
    decision the lifecycle every other ruling has — status, ruled_by, reason, carried across
    re-measurement — instead of leaving it in a cache nobody reads.
    """
    served = {f.stem for f in (root / "data" / "datasets").glob("*.yaml")}
    if not served:
        return []
    concepts = sorted((root / "ontology" / "concepts").glob("**/*.yaml"))
    if not concepts:
        return []                       # no ontology plane: nothing is owed yet
    claimed, by_rel = set(), {}
    for f in concepts:
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        name = ((doc.get("concept") or {}).get("name")) or f.stem
        for src in (doc.get("grounding") or {}).get("sources") or []:
            rel = str(src.get("relation") or "").split(".")[-1]
            if rel:
                claimed.add(rel)
                by_rel.setdefault(rel, []).append(name)
    out = []
    for rel in sorted(served - claimed):
        out.append({
            "id": f"DQ-UNCLAIMED-{rel.upper()}",
            "title": f"served relation `{rel}` is claimed by no concept",
            "severity": "medium",
            "finding": (
                f"{len(served)} relation(s) are served and {len(claimed)} are claimed by at least one "
                f"of {len(concepts)} concept(s); `{rel}` is claimed by none. A served relation is one "
                f"a question can read, so an unclaimed one is either a notion nobody modelled or a "
                f"relation that should not be served — and the delivered artifacts do not say which."),
            "needs": (f"Which is it?  ANSWER ONE OF: model_a_concept | stop_serving_it | "
                      f"backs_no_notion.  A decline is a legitimate answer and the reason is the "
                      f"deliverable — `backs_no_notion` with no reason leaves the next reader exactly "
                      f"where this finding found them."),
            "ruling": {
                "question": f"`{rel}` is served and claimed by no concept. Which is it?",
                "answers": ["model_a_concept", "stop_serving_it", "backs_no_notion"],
                "established": (
                    f"served: yes (data/datasets/{rel}.yaml). Claimed by: nothing. "
                    f"{len(claimed)} of {len(served)} served relations are claimed."),
                "for_the_human": (
                    "A measurement sees a relation with no concept. Whether that is a gap in the "
                    "ontology or a relation that should never have been served is a modelling "
                    "decision, and the planner's own decline lives only in a cached completion."),
                "consequences": {
                    "model_a_concept": "a concept grounds on it and the relation becomes answerable",
                    "stop_serving_it": (
                        "it leaves the served plane — which on a 1:1 passthrough means authoring a "
                        "transform, because a passthrough serves everything by construction"),
                    "backs_no_notion": (
                        "it stays served and is recorded as deliberately unmodelled, so the next "
                        "reader finds the decision instead of the gap"),
                },
                "recommendation": None,
                "because": (
                    "NO RECOMMENDATION FROM MEASUREMENT: nothing in the data distinguishes a notion "
                    "nobody has modelled yet from a relation that should not be served. The planner "
                    "may already have decided — check its `not_a_concept` reason before deciding "
                    "again."),
            },
        })
    return out


def _duplicate_landings(root: pathlib.Path, yaml) -> list[dict]:
    """Two raw relations that deliver ONE fact twice — and whether both are being SERVED.

    THE FIRST CONCEPT I TRIED TO AUTHOR RAN STRAIGHT INTO THIS, which is how the old version's three
    defects surfaced at once. It graded the case `low`, called it "one fact POSSIBLY shipped twice",
    and rested entirely on an equal row count — a coincidence-prone signal it admitted was not proof.

    Measured on the vanilla bundle: `orderrows` and `sales` both carry 223,974 rows, `sales` carries
    EVERY column of `orderrows` plus the header attributes (OrderDate, CustomerKey, StoreKey,
    CurrencyCode, ExchangeRate), all 223,974 keys align, all four measure columns agree row for row,
    and SUM(Quantity) is 703,621 on both. It is not possibly duplicated. It is the same fact twice.

    AND THE PASSTHROUGH SERVES BOTH, which is the part that makes it high rather than medium. A
    curated bundle ruled exactly this and served only one, recording why: "serving both would give
    every figure here two defensible answers and an engine would pick by accident." A 1:1 passthrough
    cannot make that ruling — it serves everything by construction — so the vanilla bundle needs the
    ruling MORE than a curated one, and had it graded lowest.

    COLUMN CONTAINMENT IS THE OFFLINE EVIDENCE. Equal row counts alone would fire on any two
    coincidentally-equal relations; containment of one column set in the other (allowing the key to be
    spelled differently on each side) is what distinguishes a re-delivery from a coincidence, and it is
    computable from the descriptors with no warehouse. Proving the ROWS agree needs SQL and belongs in
    the generated suite, not in this offline raiser.
    """
    served = {f.stem for f in (root / "data" / "datasets").glob("*.yaml")}
    rel: dict[str, dict] = {}
    for f in sorted((root / "data" / "sources").glob("*.yaml")):
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        rows = (doc.get("table") or {}).get("rows_measured")
        if isinstance(rows, int) and rows > 0:
            rel[f.stem] = {"rows": rows,
                           "cols": {str(c.get("name")) for c in (doc.get("columns") or [])
                                    if c.get("name")}}
    out = []
    stems = sorted(rel)
    for a in stems:
        for c in stems:
            if a >= c or rel[a]["rows"] != rel[c]["rows"]:
                continue
            # WHICH CONTAINS WHICH. The wider relation is the pre-joined re-delivery; the narrower one
            # is the normalised detail that needs a header to answer anything.
            wide, narrow = (c, a) if len(rel[c]["cols"]) >= len(rel[a]["cols"]) else (a, c)
            missing = rel[narrow]["cols"] - rel[wide]["cols"]
            # One column may be missing on each side and still be the same fact: a key spelled
            # differently (RowNumber / LineNumber). More than one, and this is not a re-delivery.
            if len(missing) > 1:
                continue
            extra = sorted(rel[wide]["cols"] - rel[narrow]["cols"])
            # WHICH EXTRA COLUMNS ARE GENUINELY UNREACHABLE BY THE OTHER ROUTE — computed, not picked.
            # The first version named the alphabetically-last extra column as the one "the normalised
            # route has NOWHERE to get", and named StoreKey: which `orders` carries, so it was reachable
            # and the claim was false. Third time in one session a recommendation rested on evidence
            # nobody had checked, so it is checked: an extra column is unreachable only if NO other
            # landing carries it.
            elsewhere = {c for st, v in rel.items() if st not in (wide, narrow) for c in v["cols"]}
            unreachable = [c for c in extra if c not in elsewhere]
            both_served = _is_served(narrow, served) and _is_served(wide, served)
            out.append({
                "id": f"DQ-DUP-{narrow.upper()}-{wide.upper()}",
                "title": (f"`{wide}` re-delivers every line of `{narrow}` — one fact, twice"
                          + (", and BOTH are served" if both_served else "")),
                "severity": "high" if both_served else "medium",
                "finding": (
                    f"{rel[narrow]['rows']:,} rows each. `{wide}` carries "
                    f"{'every' if not missing else 'all but ' + str(len(missing))} column of "
                    f"`{narrow}`"
                    + (f" ({', '.join(sorted(missing))} is spelled differently there)" if missing else "")
                    + f", plus {len(extra)}: {', '.join(extra)}. So `{wide}` answers at this grain with "
                      f"NO join, and `{narrow}` cannot answer at all without a header relation."
                    + (f" BOTH ARE SERVED, so every figure at this grain has two defensible answers and "
                       f"an engine picks by accident." if both_served else
                       f" Only one is served, so the ambiguity is latent rather than live.")),
                "needs": (f"Which is the FACT OF RECORD?  ANSWER ONE OF: {narrow} | {wide} | "
                          f"both_are_distinct_facts | neither_serve_a_transform.  "
                          f"RECOMMENDED: serve exactly ONE — see the ruling."),
                "ruling": {
                    "question": f"`{narrow}` and `{wide}` deliver the same {rel[narrow]['rows']:,} "
                                f"rows. Which is the fact of record?",
                    "answers": [narrow, wide, "both_are_distinct_facts",
                                "neither_serve_a_transform"],
                    "established": (
                        f"equal row counts; `{wide}`'s column set CONTAINS `{narrow}`'s"
                        + (f" apart from {', '.join(sorted(missing))}" if missing else "")
                        + f"; the {len(extra)} extra column(s) on `{wide}` are header attributes "
                          f"({', '.join(extra)}). Served: "
                        + (f"BOTH" if both_served else
                           f"{', '.join(sorted({narrow, wide} & served)) or 'neither'}")),
                    "for_the_human": (
                        "A measurement sees two relations delivering one fact. It cannot see which one "
                        "the business considers authoritative, and that is the whole of the question — "
                        "both are internally consistent, so no test distinguishes them."),
                    "consequences": {
                        narrow: (f"the normalised detail is the record, and every question at this grain "
                                 f"must JOIN a header relation to reach the attributes `{wide}` already "
                                 f"carries. `{wide}` must STOP being served, or the ambiguity remains "
                                 f"whatever is declared."),
                        wide: (f"the pre-joined relation is the record and answers with no join, "
                               f"including the {len(extra)} attributes the normalised route reaches only "
                               f"through a header. `{narrow}` must stop being served."),
                        "both_are_distinct_facts": (
                            "each is declared a fact in its own right, which requires a reason the "
                            "measurement contradicts — they agree row for row — and every total over "
                            "them becomes a sum a reader must know not to take twice."),
                        "neither_serve_a_transform": (
                            "a curated relation is authored over one of them and BOTH landings stop "
                            "being served — the route a curated bundle took, which is available here "
                            "and is what the passthrough cannot do for you."),
                    },
                    "recommendation": "serve exactly ONE of them",
                    "because": (
                        f"WHICH one is a convention; serving BOTH is the defect. On the evidence `{wide}` "
                        f"is the cheaper record — it answers at this grain with no join"
                        + (f", and carries {', '.join(unreachable)}, which NO other landing has, so the "
                           f"normalised route cannot reach it at all" if unreachable else
                           f", though every attribute it adds is reachable through a join, so this is "
                           f"convenience rather than capability")
                        + f". Against it: `{narrow}` is the normalised detail, and a bundle that "
                        f"prefers it keeps one spelling of each attribute instead of two. Either is "
                        f"defensible. Both is not."),
                },
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
                    "finding": f"{nulls:,} of {rows:,} rows null",
                    "needs": ("a ruling: drop the column, or state what its absence MEANS. A served "
                              "column with no value is declared and empty."),
                })
    return out


#: A column is IDENTIFYING when at least this share of its distinct values is held by exactly one
#: row. ZipCode on the curated customer dimension measures 0.72; contoso5's customer_name 0.95 and
#: city 0.62; its birth_date 0.06 and state 0.03 are not. Half is the honest cut between "a list of
#: people" and "an axis some of whose members happen to be small".
IDENTIFYING_SHARE = 0.5


def _identifying_columns(root: pathlib.Path, yaml) -> list[dict]:
    """A served dimension column most of whose values name exactly one row.

    Read from the profile's `singletons` (mac_profile.py/6, one GROUPING SETS scan); a profile made
    by an older method carries none and raises nothing here -- absent is not zero. Served relations
    only: the same column on the landing measures the same and would double the finding.

    WHY IT IS A DQ FINDING AND NOT A GATE. The number is a fact; whether the column may be an axis is
    a person's call -- `rulings.never_axis: privacy` on the concept's column, citing this id as
    `evidence` (reference_manual/column_rulings.md §4). Operator, 2026-09-29: that ruling is a MUST
    HAVE, and a prohibition without a measurement is a preference; this is the measurement."""
    served = {f.stem for f in (root / "data" / "datasets").glob("*.yaml")}
    out = []
    for f in sorted((root / "data" / "profiles").glob("*.yaml")):
        if f.stem not in served:
            continue
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        rows = (doc.get("profile") or {}).get("rows")
        for c in doc.get("columns") or []:
            single, distinct = c.get("singletons"), c.get("distinct")
            if not isinstance(single, int) or not isinstance(distinct, int) or distinct <= 0:
                continue
            share = single / distinct
            # A COLUMN 1:1 WITH THE ROW IS ANOTHER NAME FOR THE KEY, not a dimension that happens to
            # single people out -- that is the `label_of` constellation (column_rulings.md §1) and is
            # ruled there. Measured 2026-09-29: date_key 4,018 of 4,018, product_code and product_name
            # 2,517 of 2,517 all fired here before this line existed; customer_name (99,200 of 104,990
            # rows) and city did not stop being findings.
            if share < IDENTIFYING_SHARE or (isinstance(rows, int) and distinct >= rows):
                continue
            col = str(c.get("name"))
            out.append({
                "id": f"DQ-IDENTIFYING-{f.stem.upper()}-{col.upper()}",
                "title": f"`{f.stem}.{col}` names individuals — {single:,} of {distinct:,} values are held by exactly one row",
                "severity": "medium",
                "finding": (f"{single:,} of {distinct:,} distinct values ({share:.0%}) over {rows:,} rows are held "
                            f"by exactly one row (mac_profile.py/6, one GROUPING SETS scan). A column most of "
                            f"whose values name one row is an identifier wearing a dimension's role: GROUP BY it "
                            f"returns one row per person, and the query succeeds."),
                "needs": (f"a ruling on the concept that grounds `{f.stem}.{col}`: `rulings: {{never_axis: privacy, "
                          f"evidence: DQ-IDENTIFYING-{f.stem.upper()}-{col.upper()}}}` on the column, or a written "
                          f"reason the axis is safe to offer. Until then the planner has nothing to refuse with."),
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
            "finding": str(r.get("detail") or r.get("statement") or "")[:200],
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
            "finding": f["finding"],
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
            out.append({**prev, "finding": (prev.get("finding") or "")
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
