#!/usr/bin/env python3
"""The admission test — classify every column DEAD / IDENTITY / COLLAPSIBLE, and record WHY.

A relation's grain is not a ruling and not a guess. It is measured — but measuring only ONE thing
gets it wrong, and this tool exists because that happened.

── TWO PROBES, NOT ONE ─────────────────────────────────────────────────────────────────────────
DISCRIMINATION (leave-one-out): drop a column from the candidate key and see whether the group count
moves. It answers *does this column split anything*.

DEPENDENCE (functional): is this column determined by some other column? It answers *why not*.

Running only the first is what produced today's near-miss. A one-letter brand code (`brand_code`)
splits NOTHING — 5 columns and 7 columns give the identical 12.345.252 groups — so a
discrimination-only profiler drops it, measurably justified and semantically wrong. The dependence
probe says why: it is determined TWICE over, by two different kinds of fact.

MEASURED 2026-08-20 on v_<source>_kpi, and it corrected the guess this file was first written around.
`brand_code` is determined by `<source>_model_code_id` ALONE. It is NOT determined by `role` — Group
spans nine codes — and, against the standing assumption, NOT by `market` either, so the "578 market
codes each belong to exactly one brand" convention DOES NOT HOLD as a functional dependency in this
relation. The distinction the probe exists to draw is still the right one:

    redundant by LAW          a structural determinant; a key may drop the dependent column
    redundant by CONVENTION   a naming scheme that happens to hold today; if it ever stops holding,
                              a key without the dependent column silently merges two things

but which columns fall on which side is measured here, not asserted. No discrimination test can tell
them apart, which is the entire reason this file carries two probes.

── THE OTHER TRAP: UNIQUE IS NOT RIGHT ─────────────────────────────────────────────────────────
Adding config_data_status makes v_<source>_kpi unique — and DOUBLES the figure count, 12,3 Mio to 24,0
Mio. That is the tell: it stopped identifying a FIGURE and started identifying a DELIVERY OF a
figure. A minimal-unique-subset search lands there and declares victory.

So a column is only admitted as identity if removing it makes the MEASURE DISAGREE. Splitting groups
is not enough — a delivery axis splits groups too, and the two halves agree, because they are the
same figure twice.

    DEAD          removing it changes nothing at all              -> auto-excluded
    IDENTITY      removing it makes the measure disagree a lot    -> auto-included
    COLLAPSIBLE   removing it splits, but the halves AGREE        -> a human decides, once

MEASURED on v_<source>_kpi: `role` (identity) scores 0,000 % disagreement and `config_data_status`
(delivery) scores 0,016 %. Four significant figures apart. NO STATISTIC SEPARATES THEM, because the
difference is what the business MEANS by the two columns. The tool reduces twenty columns to two
closed questions and refuses to answer those itself.
"""
from __future__ import annotations

import os
import argparse
import datetime as dt
import pathlib
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _plugin  # noqa: E402  — the bundle-plugin seam, shared by five tools

TOOL = "mac_admit_identity.py/1"
IDENTITY_AT = 0.10      # removing it makes the measure disagree in >=10 % of collapsed groups
COLLAPSIBLE_UNDER = 0.01


def _q(c: str) -> str:
    return f'"{c}"'


def _qs(v: str) -> str:
    return "'" + str(v).replace("'", "''") + "'"


def load_profile(root: pathlib.Path, stem: str) -> dict:
    """The measurement plane for one descriptor. Split out at v0.1.14 — see ProfileFile."""
    p = root / "data" / "profiles" / f"{stem}.yaml"
    return (yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}) or {}


def candidates(doc: dict) -> list[str]:
    """Columns worth testing: not the measure, not free-form, and actually discriminating something.

    Uses the census the profiler already wrote — a column with one distinct value cannot be part of
    any key, and one distinct per row is a row id, not a business identity."""
    rows = (doc.get("_profile") or {}).get("rows") or 0
    out = []
    for c in doc.get("columns") or []:
        p = c.get("profile") or {}
        d = p.get("distinct")
        if not d or d <= 1 or (rows and d >= rows):
            continue
        out.append(str(c["name"]))
    return out


def _key_expr(cols: list[str]) -> str:
    """A candidate key as one comparable string. chr(1) separates, chr(2) stands in for NULL so two
    rows differing only by a null are not silently merged."""
    parts = ", ".join(f"coalesce(CAST({_q(c)} AS varchar), chr(2))" for c in cols)
    return f"concat_ws(chr(1), {parts})"


def grow_sql(relation: str, have: list[str], tryout: list[str], stratum: str | None) -> str:
    """ONE scan evaluating have∪{c} for EVERY candidate c. O(depth) scans, never 2^n."""
    where = f"\n  WHERE {stratum}" if stratum else ""
    sel = [f"count(DISTINCT {_key_expr(have + [c])}) AS g{i}" for i, c in enumerate(tryout)]
    return "SELECT " + ", ".join(sel) + f"\nFROM {relation}{where}"


def shrink_sql(relation: str, key: list[str], stratum: str | None) -> str:
    r"""ONE scan evaluating key minus {c} for every c. Removal that changes NOTHING means dead."""
    where = f"\n  WHERE {stratum}" if stratum else ""
    sel = [f"count(DISTINCT {_key_expr([x for x in key if x != c])}) AS g{i}"
           for i, c in enumerate(key)]
    return "SELECT " + ", ".join(sel) + f"\nFROM {relation}{where}"


def admission_sql(relation: str, basis: list[str], measure: str, stratum: str | None) -> str:
    """ONE scan. Full-basis groups, plus leave-one-out for every candidate, plus disagreement."""
    where = f"\n  WHERE {stratum}" if stratum else ""
    full = ", ".join(_q(c) for c in basis)
    parts = [f"""SELECT 'ALL' AS omitted,
       count(*) AS groups,
       sum(CASE WHEN n > 1 THEN 1 ELSE 0 END) AS split,
       sum(CASE WHEN dv > 1 THEN 1 ELSE 0 END) AS disagree
FROM (SELECT count(*) AS n, count(DISTINCT {_q(measure)}) AS dv
      FROM {relation}{where} GROUP BY {full})"""]
    for c in basis:
        rest = [x for x in basis if x != c] or ["1"]
        g = ", ".join(_q(x) if x != "1" else "1" for x in rest)
        parts.append(f"""SELECT '{c}' AS omitted,
       count(*) AS groups,
       sum(CASE WHEN n > 1 THEN 1 ELSE 0 END) AS split,
       sum(CASE WHEN dv > 1 THEN 1 ELSE 0 END) AS disagree
FROM (SELECT count(*) AS n, count(DISTINCT {_q(measure)}) AS dv
      FROM {relation}{where} GROUP BY {g})""")
    return "\nUNION ALL\n".join(parts) + "\nORDER BY 1"


def dependence_sql(relation: str, determinants: list[str], dependents: list[str],
                   stratum: str | None) -> str:
    """Which columns FUNCTIONALLY DETERMINE which. One grouped pass per determinant, unioned.

    a -> b holds when no single value of `a` ever carries two different values of `b`. This is the
    probe no group count can stand in for, and the reason it exists is a near-miss: `brand_code`
    splits nothing, so discrimination alone drops it. Dependence says WHY — determined by `role` for
    the five brand perspectives (a LAW), and separately by the market code because 578 codes each
    belong to one brand (a CONVENTION). Redundant-by-convention must stay in a key; redundant-by-law
    need not. Only single-column determinants are tested; a composite determinant reads as absent
    here, so the block understates dependence rather than inventing it."""
    where = f"\n  WHERE {stratum}" if stratum else ""
    parts = []
    for a in determinants:
        per = ", ".join(f"count(DISTINCT {_q(b)}) AS d{j}" for j, b in enumerate(dependents))
        mx = ", ".join(f"max(d{j}) AS m{j}" for j, _ in enumerate(dependents))
        parts.append(f"SELECT {_qs(a)} AS determinant, {mx}\n"
                     f"FROM (SELECT {per} FROM {relation}{where} GROUP BY {_q(a)})")
    return "\nUNION ALL\n".join(parts)


def doc_role(doc: dict, name: str) -> str | None:
    """The role already on the column — a previous human ruling, which the machine must not overwrite."""
    for c in doc.get("columns") or []:
        if str(c.get("name")) == name:
            return c.get("role")
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("dataset")
    ap.add_argument("--measure", required=True,
                    help="the column agreement is tested on. THE ONE BIT A HUMAN SUPPLIES — if it is "
                         "wrong, every classification below it is confidently wrong with full "
                         "evidence attached.")
    ap.add_argument("--rule", action="append", default=[], metavar="COL=identity|delivery",
                    help="record a HUMAN's ruling on a COLLAPSIBLE column. The tool measures and "
                         "refuses to decide; this is how the decision comes back in, through the same "
                         "tool, so the design fact and the evidence that prompted it stay together. "
                         "Repeatable. Only the column ROLE is written — the ruling's provenance "
                         "belongs in interventions/ledger.yaml, which is the change protocol.")
    ap.add_argument("--exclude", default="",
                    help="comma-separated columns kept OUT of the key search. Use it for a column "
                         "already ruled a DELIVERY axis: a concatenated surrogate wins every greedy "
                         "step by construction and makes every atomic axis it encodes read DEAD.")
    ap.add_argument("--stratum", default=None,
                    help="SQL predicate confining the test to one republication round, e.g. "
                         "\"config_reporting_month = DATE '2026-08-31'\"")
    ap.add_argument("--write", action="store_true", help="record roles and determined_by")
    a = ap.parse_args()

    root = pathlib.Path(a.root).resolve()
    path = next((root / "data" / d / f"{a.dataset}.yaml" for d in ("datasets", "sources")
                 if (root / "data" / d / f"{a.dataset}.yaml").exists()), None)
    if path is None:
        print(f"no descriptor for {a.dataset!r}", file=sys.stderr)
        return 2
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not doc.get("profile"):
        print(f"{path.name}: profile it first — mac_profile.py", file=sys.stderr)
        return 2
    tbl = doc.get("table") or {}
    rel = ".".join(x for x in (tbl.get("schema"), tbl.get("name")) if x)
    basis = [c for c in candidates(doc) if c != a.measure]
    if not basis:
        print(f"{path.name}: no candidate columns", file=sys.stderr)
        return 2

    # An AUTHOR tool may hard-require the bundle's warehouse connection — the bundle owns the
    # connection, MAC owns the algorithm — but it must then exit 2, not propagate the bundle's
    # own SystemExit as this tool's verdict. See tools/_plugin.py.
    try:
        Athena = _plugin.required(root, "Athena")
    except _plugin.PluginUnavailable as exc:
        print(f"could not run: {root} {exc}", file=sys.stderr)
        return 2
    eng = (yaml.safe_load((root / "acceptance" / "properties.yaml").read_text(encoding="utf-8"))
           or {}).get("engine") or {}
    ath = Athena(eng["profile"], eng["region"], eng["workgroup"], eng["database"])

    # ── GROW A MINIMAL KEY FIRST ───────────────────────────────────────────────────────────────
    # Leave-one-out over ALL candidate columns is useless and the first run proved it: with
    # config_key and <source>_created_at in the basis every row is already unique, so omitting any
    # single column changes nothing and all 19 report DEAD. The basis must be a MINIMAL key, grown,
    # not the full column list.
    drop = {x.strip() for x in a.exclude.split(",") if x.strip()}
    if drop:
        basis = [c for c in basis if c not in drop]
        print(f"  excluded from the key search: {', '.join(sorted(drop))}")
    remaining, key, groups = list(basis), [], 0
    print(f"  growing a minimal key over {len(basis)} candidates…")
    while remaining:
        gr, _ = ath.query(grow_sql(rel, key, remaining, a.stratum))
        gains = [(int(gr[0][f"g{i}"]), c) for i, c in enumerate(remaining)]
        best_g, best_c = max(gains)
        if best_g <= groups:                       # nothing left that refines anything
            break
        key.append(best_c)
        remaining.remove(best_c)
        gain = best_g - groups
        groups = best_g
        print(f"     + {best_c:<26} {best_g:,}".replace(",", ".") + f"  (+{gain:,})".replace(",", "."))
        if gain / max(best_g, 1) < 0.0005:         # the last addition bought almost nothing
            key.pop(); groups = best_g - gain
            print("       (dropped again — refined by less than 0,05 %)")
            break

    if not key:
        print("  no column refines anything — nothing to admit", file=sys.stderr)
        return 2

    # ── SHRINK-CONFIRM ────────────────────────────────────────────────────────────────────────
    sr, _ = ath.query(shrink_sql(rel, key, a.stratum))
    dead = [c for i, c in enumerate(key) if int(sr[0][f"g{i}"]) == groups]
    if dead:
        print(f"  shrink: {', '.join(dead)} removable without changing the group count")
    basis = [c for c in key if c not in dead]
    print(f"  minimal key: {len(basis)} columns — {', '.join(basis)}\n")

    rows, meta = ath.query(admission_sql(rel, basis, a.measure, a.stratum))
    by = {r["omitted"]: r for r in rows}
    allr = by.pop("ALL")
    full_groups = int(allr["groups"])

    print(f"  {rel} · measure {a.measure} · basis {len(basis)} columns"
          + (f" · stratum {a.stratum}" if a.stratum else ""))
    print(f"  full basis: {full_groups:,}".replace(",", ".") + " groups, "
          + f"{int(allr['split']):,}".replace(",", ".") + " split, "
          + f"{int(allr['disagree']):,}".replace(",", ".") + " disagree\n")
    print("   %-26s %14s %14s %14s  %-12s %s" % ("omit", "groups", "split", "disagree", "class", "ratio"))
    print("   " + "-" * 96)

    verdict = {}
    for c in basis:
        r = by.get(c)
        if not r:
            continue
        g, sp, dg = int(r["groups"]), int(r["split"]), int(r["disagree"])
        if g == full_groups:
            cls, ratio = "DEAD", "—"
        else:
            frac = (dg / sp) if sp else 0.0
            cls = ("IDENTITY" if frac >= IDENTITY_AT
                   else "COLLAPSIBLE" if frac < COLLAPSIBLE_UNDER else "UNCLEAR")
            ratio = f"{frac*100:.4f} %".replace(".", ",")
        verdict[c] = cls
        de = lambda v: f"{v:,}".replace(",", ".")
        print("   %-26s %14s %14s %14s  %-12s %s" % (c, de(g), de(sp), de(dg), cls, ratio))

    already = {x.partition("=")[0].strip() for x in a.rule}
    collapsible = [c for c, v in verdict.items()
                   if v in ("COLLAPSIBLE", "UNCLEAR") and c not in already]
    print()
    if collapsible:
        print("  THE IRREDUCIBLE RESIDUE — no statistic decides these, because the difference is what")
        print("  the business MEANS. One closed question each, answered once:\n")
        for c in collapsible:
            col = next((x for x in doc["columns"] if x["name"] == c), {})
            vals = (col.get("profile") or {}).get("values")
            print(f"    {c} — {len(vals) if vals else (col.get('profile') or {}).get('distinct')} values"
                  + (f": {', '.join(map(str, vals[:4]))}{'…' if vals and len(vals) > 4 else ''}" if vals else ""))
            print(f"      Does a different {c} make it a DIFFERENT FIGURE, or the SAME FIGURE "
                  f"DELIVERED AGAIN?   [identity | delivery]\n")
    # ── DEPENDENCE. Runs whenever we are recording, because `determined_by` must be MEASURED. An
    #    earlier draft wrote the literal string "(measured dead — see admission)" into this field:
    #    a fabricated value in a machine field, which is the defect this phase exists to remove.
    fd: dict[str, list[str]] = {}
    probed: set[str] = set()
    # An EXCLUDED column is unruled BY CONSTRUCTION — held out on a hypothesis, not a ruling. If it
    # still declares an identity role, the measurement neither supports nor refutes that role, and
    # the gap must be visible. SURFACED, never rewritten: a role is a design fact.
    for c in sorted(drop):
        r = doc_role(doc, c)
        if r in ("primary_key", "composite_key_part"):
            print(f"  SURFACED — {c} declares role: {r}, but it was held OUT of the key search on a")
            print(f"     hypothesis. The measurement neither supports nor refutes it. Not rewritten.\n")

    if a.write:
        dependents = [c for c in candidates(doc) if c not in basis]
        if dependents and basis:
            print(f"  dependence: {len(basis)} determinants x {len(dependents)} dependents…")
            # A column with ONE value in this slice is determined by everything, trivially and
            # falsely — config_reporting_month is pinned BY the stratum, not by the key. Measure
            # which are constant here rather than inferring it, and say so.
            cw = f"\n  WHERE {a.stratum}" if a.stratum else ""
            cr, _ = ath.query("SELECT " + ", ".join(
                f"count(DISTINCT {_q(b)}) AS c{j}" for j, b in enumerate(dependents))
                + f"\nFROM {rel}{cw}")
            const = [b for j, b in enumerate(dependents) if int(cr[0][f"c{j}"]) <= 1]
            if const:
                print(f"     constant in this slice, so determined by nothing: {', '.join(const)}")
            probed = set(dependents)          # everything re-measured this run, constants included
            dependents = [b for b in dependents if b not in const]
            dr, _ = ath.query(dependence_sql(rel, basis, dependents, a.stratum))
            for row in dr:
                det = row["determinant"]
                for j, b in enumerate(dependents):
                    if int(row[f"m{j}"]) == 1:          # never two values of b under one value of a
                        fd.setdefault(b, []).append(det)
            for b, dets in sorted(fd.items()):
                print(f"     {b:<26} determined by {', '.join(sorted(dets))}")
            undet = [b for b in dependents if b not in fd]
            if undet:
                print(f"     no single-column determinant: {', '.join(undet)}")

        stamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        # What the evidence is TRUE OF. Not wrapped in a bare except: a proof that quietly loses
        # its watermark is exactly the stale-but-confident artifact this block exists to prevent.
        source_watermark = _plugin.required(root, "source_watermark")
        wm = (source_watermark(ath, [rel]).get(rel) or {}).get("newest_write")

        ruled = {}
        for spec in a.rule:
            c, _, how = spec.partition("=")
            if how not in ("identity", "delivery"):
                print(f"  --rule {spec}: expected identity or delivery", file=sys.stderr)
                return 2
            if verdict.get(c.strip()) not in ("COLLAPSIBLE", "UNCLEAR"):
                # Ruling a column the measurement already settled would let a human quietly overturn
                # evidence through a flag meant for the residue. The residue is the only thing open.
                print(f"  --rule {c.strip()}: not in the residue (measured "
                      f"{verdict.get(c.strip(), 'not a candidate')}) — refusing", file=sys.stderr)
                return 2
            ruled[c.strip()] = how

        for col in doc.get("columns") or []:
            n = str(col["name"])
            v = verdict.get(n)
            if n in ruled:
                col["role"] = "composite_key_part" if ruled[n] == "identity" else "delivery_axis"
                print(f"  RULED — {n}: {ruled[n]} → role: {col['role']}")
            elif v == "IDENTITY":
                col["role"] = "composite_key_part"
            # COLLAPSIBLE is deliberately NOT written. It is the residue, and a residue the machine
            # settles is not a residue. The column keeps whatever role it has — 'unknown' is already
            # forbidden in production files, so the existing gate holds the line until a human rules.
            if n in fd:
                col.setdefault("profile", {})["determined_by"] = sorted(fd[n])
            elif n in probed and (col.get("profile") or {}).get("determined_by"):
                del col["profile"]["determined_by"]
                print(f"     cleared a determinant list no longer measured: {n}")

        doc["identity_evidence"] = {
            "measured_at": stamp,
            "source_watermark": wm,
            "method": TOOL,
            "measure": a.measure,
            "stratum": a.stratum,
            "excluded": sorted(drop) or None,
            # The key is what the MEASUREMENT settled PLUS what a human ruled into it. Writing only
            # the measured half left `key` disagreeing with the column roles in the same file — the
            # two-numbers-for-one-fact defect, reappearing inside the tool built to end it.
            "key": [c for c in basis
                    if verdict.get(c) == "IDENTITY" or ruled.get(c) == "identity"],
            "delivery_axes": [c for c in basis if ruled.get(c) == "delivery"] or None,
            "ruled": sorted(ruled) or None,
            "full_groups": full_groups,
            "columns": [{"name": c, "groups": int(by[c]["groups"]), "split": int(by[c]["split"]),
                         "disagree": int(by[c]["disagree"]), "verdict": verdict[c]}
                        for c in basis if c in by],
        }
        doc["identity_evidence"] = {k: v for k, v in doc["identity_evidence"].items()
                                    if v is not None or k in ("source_watermark", "stratum")}
        path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100),
                        encoding="utf-8")
        print(f"\n  written → {path.relative_to(root)}")
        if collapsible:
            print(f"  {len(collapsible)} column(s) left UNRULED on purpose — the residue is a human's")
    else:
        print("  (dry run — pass --write to record)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
