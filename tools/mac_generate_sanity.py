#!/usr/bin/env python3
"""Generate the data-sanity suite FROM the profile. Nobody authors these.

Operator: *"i would EXPECT actually REQUIRE that you in parallel to discovered data model being
protocolled in table.yaml format immediately start writing data sanity unit tests"* and *"data
sanity is what our understanding of the data tells regardless of ontology"*.

Every profiled fact is already an assertion. `role` has these 6 values → *still these 6*. `nulls: 0`
on a key column → *still none*. So a data-sanity test is not written, it is PROJECTED — which means
it cannot be skipped and cannot invent a standard. Both failure modes have happened: a suite whose
tests were never written, and a suite whose numbers were typed by hand.

── VOLUME IS NOT STRUCTURE, and this is the whole judgement ────────────────────────────────────
Operator: *"you can exepct that the volume od data will grow over time. this we dont need to
provfile or monitor. we need to monitor structural changes."*

So the census records everything and the GENERATOR decides what may fail. Asserting a row count
would fire on every load and be switched off within a week, taking the real checks with it.

  ASSERTED — structure                      RECORDED, NEVER ASSERTED — volume
    a bounded column's VALUE SET              row count
    a never-null column staying never-null    high-cardinality distinct counts
    the EARLIEST value of a date domain       the LATEST value of a date domain
    every declared column still present       anything that grows by design

THE VALUE SET, NOT ITS SIZE. `role: 6 distinct` cannot tell a seventh perspective appearing from one
being RENAMED — both leave the count at 6. For a bounded column the membership IS the structure.

THE EARLIEST DATE, NOT THE LATEST. The max moving forward is a load. The MIN moving forward means
history was dropped, silently, and no row count would show it.

Generated properties are `ground_truth`: they measure the world and compare it against what was
measured before. They never read the ontology — a data-sanity property that needs the model to state
its claim is not data sanity (R5), and this generator has no access to it by construction.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import os
import pathlib
import sys

import yaml

GEN = "mac_generate_sanity.py/1"
DATEY = ("date", "timestamp", "time")


def _q(v) -> str:
    return "'" + str(v).replace("'", "''") + "'"


def for_relation(path: pathlib.Path, root: pathlib.Path) -> list[dict]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    prof = doc.get("profile")
    if not prof:
        return []
    tbl = doc.get("table") or {}
    rel = ".".join(x for x in (tbl.get("schema"), tbl.get("name")) if x)
    stem = path.stem
    src = f"{path.relative_to(root)}#profile (measured {prof.get('measured_at','?')})"
    cols = [c for c in (doc.get("columns") or []) if c.get("profile")]
    out: list[dict] = []

    # ── 1. THE SHAPE ITSELF. A column vanishing or being renamed upstream is the loudest possible
    #       structural change and the cheapest to check.
    names = sorted(str(c["name"]) for c in cols)
    out.append({
        "id": f"G-{stem}-COLUMNS", "family": "shape", "test_kind": "mac.test_kind.ground_truth",
        "severity": "blocker", "source": src, "validates": [stem],
        "statement": (
            f"Prove {rel} still has every column we recorded\n"
            f"QUESTION. Is this table still shaped the way we found it?\n"
            f"ANSWER. {len(names)} columns were recorded and are expected to still be there.\n"
            f"RISK. A renamed or dropped column makes every question about it return nothing, "
            f"which reads as 'no business happened'.\n---\n"
            f"HOW. Asks the warehouse catalogue which columns the table has and counts the recorded "
            f"ones it can no longer find. GENERATED from the profile by {GEN} — nothing here is "
            f"typed by hand.\n"
            f"WHERE. {rel}. Column ADDITIONS are not a failure: a source may gain a column without "
            f"breaking anything we read."),
        "assertion": {"type": "must_be_zero", "columns": ["recorded_columns_now_missing"]},
        "tolerance": 0,
        "sql": (f"SELECT count(*) AS recorded_columns_now_missing,\n"
                f"       {len(names)} AS columns_recorded\n"
                f"FROM (VALUES {', '.join('(' + _q(n) + ')' for n in names)}) AS t(col)\n"
                f"WHERE col NOT IN (SELECT column_name FROM information_schema.columns\n"
                f"                  WHERE table_schema = {_q(tbl.get('schema'))} "
                f"AND table_name = {_q(tbl.get('name'))})"),
    })

    # ── 2. BOUNDED VALUE SETS. Membership, not size.
    for c in cols:
        vals = (c["profile"] or {}).get("values")
        if not vals:
            continue
        n = str(c["name"])
        out.append({
            "id": f"G-{stem}-{n.upper()}-VALUES", "family": "enumeration",
            "test_kind": "mac.test_kind.ground_truth", "severity": "major",
            "source": src, "validates": [stem],
            "statement": (
                f"Prove {n} still holds exactly the {len(vals)} values we found\n"
                f"QUESTION. Has anything appeared, vanished or been renamed in this list?\n"
                f"ANSWER. {len(vals)} values were recorded.\n"
                f"RISK. A new value is silently excluded by every filter written before it existed; "
                f"a renamed one takes its data with it. Neither changes the COUNT, so counting "
                f"would miss both.\n---\n"
                f"HOW. Compares today's distinct values against the recorded set in both "
                f"directions — appeared, and vanished. GENERATED by {GEN}.\n"
                f"WHERE. {rel}.{n}. Recorded because the column is small enough to enumerate; a "
                f"column that grows by design is volume, not structure, and carries no such check."),
            "assertion": {"type": "must_be_zero", "columns": ["appeared", "vanished"]},
            "tolerance": 0,
            "sql": (f"WITH recorded (v) AS (VALUES {', '.join('(' + _q(v) + ')' for v in vals)}),\n"
                    f"today AS (SELECT DISTINCT CAST(\"{n}\" AS varchar) AS v FROM {rel})\n"
                    f"SELECT (SELECT count(*) FROM today  WHERE v NOT IN (SELECT v FROM recorded)) AS appeared,\n"
                    f"       (SELECT count(*) FROM recorded WHERE v NOT IN (SELECT v FROM today))   AS vanished,\n"
                    f"       (SELECT count(*) FROM recorded) AS values_recorded,\n"
                    f"       (SELECT count(*) FROM today)    AS values_today"),
        })

    # ── 3. NEVER-NULL STAYS NEVER-NULL. Only for columns measured at zero: promoting a column that
    #       already has nulls to "must have none" would be inventing a standard, not recording one.
    never_null = [str(c["name"]) for c in cols if (c["profile"] or {}).get("nulls") == 0]
    if never_null:
        out.append({
            "id": f"G-{stem}-NULLS", "family": "completeness",
            "test_kind": "mac.test_kind.ground_truth", "severity": "major",
            "source": src, "validates": [stem],
            "statement": (
                f"Prove the {len(never_null)} always-filled columns are still always filled\n"
                f"QUESTION. Has anything started arriving empty?\n"
                f"ANSWER. {len(never_null)} of {len(cols)} columns held no empties when recorded.\n"
                f"RISK. An empty in a column used to identify or join means the row quietly drops "
                f"out of every answer that needs it.\n---\n"
                f"HOW. Counts empties in each column that had none, and reports the total. "
                f"GENERATED by {GEN}; only columns measured at zero are covered, because requiring "
                f"zero of a column that already had empties would be inventing a standard rather "
                f"than recording one.\n"
                f"WHERE. {rel}. The other {len(cols) - len(never_null)} columns are not checked here."),
            "assertion": {"type": "must_be_zero", "columns": ["columns_that_started_arriving_empty"]},
            "tolerance": 0,
            "sql": ("SELECT " + " + ".join(f'CASE WHEN count(*) - count("{n}") > 0 THEN 1 ELSE 0 END'
                                           for n in never_null)
                    + " AS columns_that_started_arriving_empty,\n       "
                    + f"{len(never_null)} AS columns_checked,\n       count(*) AS rows_examined\n"
                    + f"FROM {rel}"),
        })

    # ── 4. THE EARLIEST DATE. The max is a load; the min moving forward is lost history.
    for c in cols:
        p = c["profile"] or {}
        if p.get("min") is None or not any(str(c.get("type", "")).lower().startswith(d) for d in DATEY):
            continue
        n = str(c["name"])
        out.append({
            "id": f"G-{stem}-{n.upper()}-HISTORY", "family": "history",
            "test_kind": "mac.test_kind.ground_truth", "severity": "major",
            "source": src, "validates": [stem],
            "statement": (
                f"Prove no history was dropped from {n}\n"
                f"QUESTION. Does this table still go back as far as it did?\n"
                f"ANSWER. The earliest recorded is {p['min']}.\n"
                f"RISK. If the start moves forward, older periods stop being answerable and every "
                f"total over them silently shrinks. Row counts would not show it — the table is "
                f"growing at the other end.\n---\n"
                f"HOW. Compares the earliest value today against the earliest recorded. The LATEST "
                f"is deliberately not checked: it moves forward on every load, which is volume, not "
                f"structure. GENERATED by {GEN}.\n"
                f"WHERE. {rel}.{n}."),
            "assertion": {"type": "equals", "expect": {"earliest_today": str(p["min"])}},
            "tolerance": 0,
            "sql": (f"SELECT CAST(min(\"{n}\") AS varchar) AS earliest_today,\n"
                    f"       {_q(p['min'])} AS earliest_recorded,\n"
                    f"       CAST(max(\"{n}\") AS varchar) AS latest_today_not_asserted\n"
                    f"FROM {rel}"),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out", default="acceptance/data_sanity_generated.yaml")
    a = ap.parse_args()
    root = pathlib.Path(a.root).resolve()

    props, seen = [], 0
    for d in ("datasets", "sources"):
        for f in sorted(glob.glob(str(root / "data" / d / "*.yaml"))):
            got = for_relation(pathlib.Path(f), root)
            if got:
                seen += 1
            props.extend(got)

    eng = (yaml.safe_load((root / "acceptance" / "properties.yaml").read_text(encoding="utf-8"))
           or {}).get("engine") or {}
    out = root / a.out
    out.write_text(yaml.safe_dump({
        "suite": "fpl2-data-sanity-generated",
        "version": "1.0",
        "generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "generated_by": GEN,
        "engine": eng,
        "properties": props,
    }, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    print(f"  {len(props)} properties from {seen} profiled relation(s) → {out.relative_to(root)}")
    from collections import Counter
    for fam, n in Counter(p["family"] for p in props).most_common():
        print(f"     {fam:<14} {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
