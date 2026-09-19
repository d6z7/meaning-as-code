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
import collections
import datetime as dt
import glob
import os
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mac_project as P                         # noqa: E402  flat AND foldered concept planes
from mac_profile import _as_text, _is_complex   # ONE definition, not a second CAST

GEN = "mac_generate_sanity.py/5"
DATEY = ("date", "timestamp", "time")


def _q(v) -> str:
    return "'" + str(v).replace("'", "''") + "'"


def concepts_on(root: pathlib.Path, stem: str) -> list[str]:
    """The concepts grounding on this relation. `validates` takes a concept.name, and this generator
    wrote the DATASET STEM into it for 206 properties — a name no concept has, so the attribution
    resolved to nothing and the third rung of the trust gradient could not be measured for any object.
    The field validated fine, because a stem is a string like any other.

    AND THEN IT GLOBBED AT DEPTH 0. `ontology/concepts/*.yaml` matches a FLAT plane only. Measured on
    a live two-plane bundle, whose 17 concepts are filed under subject folders: the glob returned 0
    files, so every one of the 67 projected properties carried `validates: []` — and the suite still
    read 67 of 67 PASS. `mac.schema.json:2608` requires `validates[]` precisely because without it
    "FRAMEWORK.md §8's third rung cannot be measured for any object", and an EMPTY LIST satisfies a
    required field. So the attribution was absent, required, and green.

    Both sibling generators already resolve through `mac_project.concept_files`, which walks flat AND
    foldered layouts; this one was the last holdout. It is the same depth-0 defect that has bitten
    eight gates in this estate."""
    out = set()
    for f in P.concept_files(root):
        d = yaml.safe_load(open(f, encoding="utf-8")) or {}
        name = ((d.get("concept") or {}).get("name"))
        if not name:
            continue
        for src in ((d.get("grounding") or {}).get("sources") or []):
            if str(src.get("relation") or "").split(".")[-1] == stem:
                out.add(str(name))
    return sorted(out)


def for_relation(path: pathlib.Path, root: pathlib.Path) -> list[dict]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    # TWO PLANES since v0.1.14: the descriptor holds meaning + the value DOMAIN, data/profiles/ holds
    # the census. A generator that reads only one of them silently emits half a suite.
    ppath = root / "data" / "profiles" / f"{path.stem}.yaml"
    pdoc = yaml.safe_load(ppath.read_text(encoding="utf-8")) if ppath.exists() else {}
    prof = (pdoc or {}).get("profile")
    if not prof:
        return []
    census = {str(c["name"]): c for c in (pdoc.get("columns") or [])}
    for c in doc.get("columns") or []:
        merged = dict(census.get(str(c["name"])) or {})
        if c.get("values") is not None:
            merged["values"] = c["values"]
        if merged:
            c["profile"] = merged        # in-memory only; neither file is rewritten
    tbl = doc.get("table") or {}
    rel = ".".join(x for x in (tbl.get("schema"), tbl.get("name")) if x)
    stem = path.stem
    validates = concepts_on(root, stem)
    src = f"{ppath.relative_to(root)}#profile (measured {prof.get('measured_at','?')})"
    cols = [c for c in (doc.get("columns") or []) if c.get("profile")]
    out: list[dict] = []

    # ── 1. THE SHAPE ITSELF. A column vanishing or being renamed upstream is the loudest possible
    #       structural change and the cheapest to check.
    names = sorted(str(c["name"]) for c in cols)
    out.append({
        "id": f"G-{stem}-COLUMNS", "family": "shape", "test_kind": "mac.test_kind.ground_truth",
        "severity": "blocker", "source": src, "validates": validates,
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
    #
    # THE EMPTY IS A MEMBER OF THE DOMAIN, AND FOR 28 CHECKS IT WAS INVISIBLE. `today` was
    # `SELECT DISTINCT CAST(col AS varchar)`, which emits a NULL ROW whenever the column holds an
    # empty, while `recorded` is the profile's value list — and the profile excludes nulls BY
    # CONSTRUCTION (`array_agg(DISTINCT …)` drops them, so does `count(DISTINCT …)`). SQL's
    # three-valued logic did the rest: `x NOT IN (set)` is UNKNOWN, never TRUE, when x IS NULL.
    #
    #   * `vanished` was PINNED AT 0. One null row in `today` makes every
    #     `recorded.v NOT IN (SELECT v FROM today)` evaluate UNKNOWN, so a value that really had
    #     disappeared was counted zero times. Half of the check was dead, silently, and it would
    #     have died the same way on a clean column the day an empty first arrived in it.
    #   * an arriving empty could never count as `appeared` either, because NULL matches nothing.
    #
    # Measured on this estate before the repair: 28 of 115 enumeration checks were in that state,
    # all 28 recording PASS, and the biconditional `profile nulls > 0  <=>  values_today =
    # distinct + 1` held on 115 of 115 — the surplus was the null row being counted as a value.
    #
    # THE CHOICE, and the two claims are NOT the same claim. Nulls are excluded from BOTH sides, so
    # `appeared`/`vanished` say something about VALUES and an empty is not a value. The empty is
    # then compared EXPLICITLY, as its own asserted column, NAMED FOR THE DIRECTION THE PROFILE
    # ACTUALLY MEASURED:
    #
    #     recorded nulls == 0  →  `empty_appeared`   "this column was total, and still is"
    #     recorded nulls  > 0  →  `empty_vanished`   "empties are still allowed here"
    #
    # ONE column, never both, because the other direction would be a literal in the SELECT list and
    # an assertion over a literal is exactly the vacuity this suite is being cleaned of. Naming the
    # direction keeps the claim legible where it matters: the run record says which claim broke,
    # not merely that something about nulls changed.
    #
    # `empty_appeared` deliberately overlaps G-<stem>-NULLS. That check asks the relation-wide
    # question — did ANY always-filled column start arriving empty — and answers with a count;
    # this one names the COLUMN, and it rides the scan the value-set check is already paying for.
    # `empty_vanished` overlaps nothing: G-<stem>-NULLS covers only columns measured at zero, so
    # for a column that already held empties nothing else was watching its domain at all.
    for c in cols:
        vals = (c["profile"] or {}).get("values")
        if not vals:
            continue
        n = str(c["name"])
        had_empties = bool((c["profile"] or {}).get("nulls"))
        empties_now = "(SELECT count(*) FROM today WHERE v IS NULL)"
        empty_col = "empty_vanished" if had_empties else "empty_appeared"
        empty_sql = f"CASE WHEN {empties_now} = 0 THEN 1 ELSE 0 END" if had_empties else empties_now
        empty_claim = (
            "empties were recorded in this column, so the check asserts they are STILL ALLOWED — "
            "an empty leaving the domain is a change of domain like any other, and nothing else "
            "watches it, because the always-filled check covers only columns measured at zero"
            if had_empties else
            "no empties were recorded in this column, so the check asserts NONE HAS ARRIVED")
        out.append({
            "id": f"G-{stem}-{n.upper()}-VALUES", "family": "enumeration",
            "test_kind": "mac.test_kind.ground_truth", "severity": "major",
            "source": src, "validates": validates,
            "statement": (
                f"Prove {n} still holds exactly the {len(vals)} values we found\n"
                f"QUESTION. Has anything appeared, vanished or been renamed in this list?\n"
                f"ANSWER. {len(vals)} values were recorded, and "
                f"{'empties were recorded alongside them' if had_empties else 'no empties were recorded'}.\n"
                f"RISK. A new value is silently excluded by every filter written before it existed; "
                f"a renamed one takes its data with it. Neither changes the COUNT, so counting "
                f"would miss both.\n---\n"
                f"HOW. Compares today's distinct values against the recorded set in both "
                f"directions — appeared, and vanished — over NON-EMPTY values on both sides, "
                f"because the recorded list excludes empties by construction. The empty is a "
                f"member of this domain too and is compared on its own, as {empty_col}: "
                f"{empty_claim}. It cannot be compared inside the value set: 'x NOT IN (set)' is "
                f"UNKNOWN and never TRUE when x is empty, which pinned vanished at 0 for every "
                f"column that held one. GENERATED by {GEN}.\n"
                f"WHERE. {rel}.{n}. Recorded because the column is small enough to enumerate; a "
                f"column that grows by design is volume, not structure, and carries no such check."),
            "assertion": {"type": "must_be_zero",
                          "columns": ["appeared", "vanished", empty_col]},
            "tolerance": 0,
            "sql": (f"WITH recorded (v) AS (VALUES {', '.join('(' + _q(v) + ')' for v in vals)}),\n"
                    f"today AS (SELECT DISTINCT {_as_text(n, _is_complex(c))} AS v FROM {rel}),\n"
                    f"present AS (SELECT v FROM today WHERE v IS NOT NULL)\n"
                    f"SELECT (SELECT count(*) FROM present  WHERE v NOT IN (SELECT v FROM recorded)) AS appeared,\n"
                    f"       (SELECT count(*) FROM recorded WHERE v NOT IN (SELECT v FROM present))  AS vanished,\n"
                    f"       {empty_sql} AS {empty_col},\n"
                    f"       (SELECT count(*) FROM recorded) AS values_recorded,\n"
                    f"       (SELECT count(*) FROM present)  AS values_today"),
        })

    # ── 3. NEVER-NULL STAYS NEVER-NULL. Only for columns measured at zero: promoting a column that
    #       already has nulls to "must have none" would be inventing a standard, not recording one.
    never_null = [str(c["name"]) for c in cols if (c["profile"] or {}).get("nulls") == 0]
    if never_null:
        out.append({
            "id": f"G-{stem}-NULLS", "family": "completeness",
            "test_kind": "mac.test_kind.ground_truth", "severity": "major",
            "source": src, "validates": validates,
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
            "source": src, "validates": validates,
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
    # Internal only, stripped before the file is written: who this check is about, and which of the
    # four checks it is. The mirror pass needs both and must not re-derive them by parsing ids back.
    for p in out:
        p["_stem"], p["_rel"] = stem, rel
        p["_suffix"] = p["id"][len(f"G-{stem}-"):]
    return out


def _blank(sql: str, rel: str) -> str:
    """This check's SQL with its OWN relation blanked out — schema, table and the dotted pair.

    So two checks that make the same claim about the same rows compare EQUAL when one of them reads
    the rows through a second name, and two checks over genuinely different relations never do,
    however alike their payloads look. The shape check spells the schema and the table separately,
    inside quotes, which is why all three forms are substituted and the longest goes first.
    """
    schema, _, name = rel.rpartition(".")
    out = sql.replace(rel, "<relation>")
    if name:
        out = out.replace(_q(name), "<table>")
    if schema:
        out = out.replace(_q(schema), "<schema>")
    return out


def _fingerprint(root: pathlib.Path, stem: str):
    """What a relation MEASURED. Two names over one set of rows produce the same fingerprint.

    The row count plus the column-NAME set, both read from the census — and the width of that rule
    is the whole judgement, so both edges are recorded here:

      NOT STRICTER than this. One mirror pair on this estate agrees on 14 of its 15 columns and
      differs on the 15th only because the two sides TYPE it differently — one reports 6 distinct
      values with min '49.0', the other 5 with min '49'. A rule strict enough to reject that pair
      is a rule that lets the pair through, and 12 duplicate checks with it.

      NOT LOOSER than this. One pair on this estate carries the SAME COLUMN NAMES and is not a
      mirror at all: the two sides disagree on the row count, one carrying about a fifth fewer rows,
      because one filters. Five of their checks render identical payloads over those different rows, so a rule
      that compared payloads alone would delete real coverage — the failure this rule exists to
      avoid, and the reason the row count is half the fingerprint.
    """
    p = yaml.safe_load((root / "data" / "profiles" / f"{stem}.yaml").read_text(encoding="utf-8")) or {}
    return ((p.get("profile") or {}).get("rows"),
            tuple(sorted(str(c["name"]) for c in (p.get("columns") or []))))


def _drop_mirrors(props: list[dict], planes: dict[str, str], root: pathlib.Path) -> list[dict]:
    """Delete the checks that are one relation's checks wearing a second relation's name.

    WHY THEY EXIST. Nine of this estate's relations are profiled twice: once as the served dataset
    and once as the raw source it is a view over. The generator cannot tell from one descriptor
    that another descriptor names the same rows, so it emitted both — 55 checks that scan the same
    bytes, assert the same numbers and can only ever agree. A suite that runs them reports a
    denominator it has not earned, and it pays Athena twice for one answer.

    WHICH SIDE SURVIVES. The served one — the name in the project's own database, the name a
    concept grounds on and therefore the name a human looks under. The twin is reached through a
    federated catalogue and carries no concept attribution at all; keeping it and dropping the
    served name would leave every `validates` on this relation pointing at a deleted check.

    WHAT IS NEVER DROPPED. A check is deleted only when the SAME SUFFIX exists on the surviving
    side AND its SQL is identical once the relation is blanked AND the assertion and tolerance
    match. A column only the raw side exposes keeps its check; so does a check whose claim differs
    even by one recorded value. Two relations that merely share a payload are not mirrors and never
    reach this function — see `_fingerprint`.
    """
    groups: dict[tuple, list[str]] = collections.defaultdict(list)
    for stem in planes:
        groups[_fingerprint(root, stem)].append(stem)

    by_stem: dict[str, dict[str, dict]] = collections.defaultdict(dict)
    for p in props:
        by_stem[p["_stem"]][p["_suffix"]] = p

    drop: set[str] = set()
    also: dict[str, tuple[dict, set[str], set[str]]] = {}
    for fp, members in sorted(groups.items(), key=lambda kv: sorted(kv[1])):
        if len(members) < 2 or fp[0] is None:
            continue
        served = sorted(s for s in members if planes[s] == "datasets")
        if len(served) != 1:
            print(f"  ! {len(members)} relations share a fingerprint and {len(served)} of them are "
                  f"served — no side wins, all kept: {sorted(members)}")
            continue
        keep = served[0]
        for stem in sorted(members):
            if stem == keep:
                continue
            for sx, p in sorted(by_stem[stem].items()):
                twin = by_stem[keep].get(sx)
                if twin is None:
                    continue                 # only the raw side has it — keep it, it is coverage
                if (_blank(p["sql"], p["_rel"]) != _blank(twin["sql"], twin["_rel"])
                        or p["assertion"] != twin["assertion"]
                        or p["tolerance"] != twin["tolerance"]):
                    continue                 # aligned by name, NOT the same claim — keep both
                drop.add(p["id"])
                rec = also.setdefault(twin["id"], (twin, set(), set()))
                rec[1].add(p["_rel"])
                rec[2].add(p["id"])

    # EVERY DELETED ID KEEPS A SURVIVING TWIN THAT NAMES IT. A deletion nobody can trace back is
    # indistinguishable from a check that was never written.
    for twin, rels, ids in also.values():
        twin["notes"] = (
            f"Also covers {', '.join(sorted(rels))} — profiled as the same rows (same row count, "
            f"same columns) and generating an identical check, dropped as "
            f"{', '.join(sorted(ids))} by {GEN}.")

    if drop:
        print(f"  {len(drop)} mirror duplicate(s) dropped, each with a surviving twin:")
        for twin, rels, ids in sorted(also.values(), key=lambda r: r[0]["id"]):
            print(f"     {', '.join(sorted(ids)):<62} -> {twin['id']}")
    return [p for p in props if p["id"] not in drop]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out", default="acceptance/data_sanity_generated.yaml")
    a = ap.parse_args()
    root = pathlib.Path(a.root).resolve()

    props, seen, planes = [], 0, {}
    for d in ("datasets", "sources"):
        for f in sorted(glob.glob(str(root / "data" / d / "*.yaml"))):
            got = for_relation(pathlib.Path(f), root)
            if got:
                seen += 1
                planes[pathlib.Path(f).stem] = d     # which plane a relation was declared on
            props.extend(got)

    props = _drop_mirrors(props, planes, root)
    props = [{k: v for k, v in p.items() if not k.startswith("_")} for p in props]

    eng = (yaml.safe_load((root / "acceptance" / "properties.yaml").read_text(encoding="utf-8"))
           or {}).get("engine") or {}
    out = root / a.out
    out.write_text(yaml.safe_dump({
        # DERIVED FROM THE BUNDLE, not typed. Every suite in an acceptance/ directory is named
        # `<bundle>-<suite>`, and this literal held the bundle token — so the public copy of this
        # file has it scrubbed to a placeholder and a regeneration RENAMES the suite out from under
        # its own run record and its history. A name a tool writes about a bundle is the bundle's
        # to supply.
        "suite": f"{root.name}-data-sanity-generated",
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
