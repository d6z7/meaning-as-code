#!/usr/bin/env python3
"""check_lineage_coverage.py — the LINEAGE-COVERAGE gate.

The enforced chain is  raw source -> transformation -> dataset -> ontology concept.  A served dataset
only earns its place in that chain if its output columns are EXPLAINED: each column either descends from
an upstream column (an EDGE projected from the transform's `inputs[].consumes` map) or is a DECLARED
derivation (`derived[]` — a const/seed column).

Counting "explained" columns alone has no teeth, because `derived` is the projector's automatic FALLBACK:
a column with no incoming edge lands there by construction, so a naive count is 100% even for a view that
explains NOTHING. The real signal is therefore COVERAGE — the fraction of a dataset's columns carrying at
least one REAL incoming edge:

    coverage(dataset) = |{columns with >= 1 incoming edge}| / |columns|

  [ERROR]  coverage == 0 on a view that DECLARES a lineage parent (a raw_source|dataset input). This is
           the degenerate failure mode: a transform whose inputs[] are MIS-DECLARED (wrong `kind`, wrong
           `descriptor`, a `consumes` map that names columns the upstream descriptor does not have, or no
           `consumes` at all) makes the whole flow silently collapse to edges=0 and every column falls
           back to derived/const. The lineage still renders — it just says nothing. Nothing else in the
           stack catches that.
  [WARN]   0 < coverage < MIN_COVERAGE_WARN — thin lineage; likely an under-declared `consumes` map.
  [WARN]   coverage == 0 on a SEED-ONLY view (authored_seed/external inputs only). A view assembled purely
           from a hand-authored register has no upstream column to descend from BY CONSTRUCTION — every
           column is a legitimate declared seed — so it is reported, never failed.
  [ERROR]  a column that is NEITHER edge-covered NOR present in derived[] — an unaccounted output column.

Coverage BELOW 100% is legitimate and deliberately NOT an error: pivots, computed/aggregate columns,
literal per-branch constants and seed-joined columns are genuinely const/derived, not descended from a
single upstream column. This gate does not ask a view to be fully traceable — it asks it to explain
SOMETHING, and prints the per-dataset table so a human can see the weak spots.

The coverage model is the ONE lineage artifact (data/lineage/lineage.json via mac_lineage.flows),
so this gate is OFFLINE
and pure-structural: it reads the governed YAML descriptors (data/sources, data/transforms,
data/datasets) and never touches the warehouse.

THE UPSTREAM END, added 2026-09-30. Everything above is the DOWNSTREAM question — does a served
dataset explain its columns. The chain has another end, and a relation can fall out of it there: a
LANDED relation that no transform consumes. `mac_lineage` measures those into
`orphans.sources_feeding_nothing` and, until this, nothing read the key. MEASURED on contoso5:
`orderrows` (223,974 rows) and `orders` (93,470) had fed nothing since the plane was first delivered,
each carried an OPEN finding in the DQ register asking whether it is out of scope, and every gate in
the chain passed green over both. The loss was found by a person reading the graph, which is the
definition of untracked.

  [ERROR]  a source feeding nothing that NO issue in the DQ register is ABOUT. Naming the relation in
           passing does not count: DQ-AMBIGREF-CURRENCYCODE lists `orders` among two relations while
           asking about a currency code, and the first cut of this check credited it. The issue's text
           must speak to the orphan condition (ORPHAN_SIGNAL).
  [WARN]   a source feeding nothing whose issue is OPEN — tracked, awaiting the ruling its own `needs`
           asks for. Accounting is this gate's test; RULING is the person's, so an open finding never
           fails here.

This half runs even when the bundle has NO flows, which is where an orphan is likeliest to hide.

Usage:  python3 tools/check_lineage_coverage.py <bundle-root>
        exit 0 = every served dataset explains at least one column AND every orphaned source is
        accounted for ; exit 1 = an unexplained view, or a source that left the chain unannounced.

Wire into your bundle's offline gate chain (guarded on the two-plane data layout):
    if [ -d "$SOURCE_ROOT/data/transforms" ]; then
      echo "▶ lineage coverage (check_lineage_coverage.py $SOURCE_ROOT)"
      "$PY" "$FW/tools/check_lineage_coverage.py" "$SOURCE_ROOT" || rc=1
    fi
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mac_lineage import flows as _flows  # noqa: E402

# ── thresholds ──────────────────────────────────────────────────────────────────────────────────────
# A dataset at or below this coverage is an ERROR: it explains NOTHING (the degenerate collapse).
MAX_COVERAGE_ERROR = 0.0
# A dataset below this coverage is a WARN: thin lineage, probably an under-declared `consumes` map.
MIN_COVERAGE_WARN = 0.50


#: WHAT MAKES AN ISSUE ABOUT AN ORPHAN, as the raiser words it. `mac_dq_findings.py` writes "consumed by
#: no transformation" in the title and "never curated; no data/transforms/*.yaml declares it as an input"
#: in the finding, and asks in `needs` whether the relation is OUT OF SCOPE.
ORPHAN_SIGNAL = re.compile(r"consumed by no|feeds? nothing|never curated|no data/transforms|out of scope",
                           re.I)


def orphan_rows(root: Path):
    """One row per RAW SOURCE THAT FEEDS NOTHING: (relation, issue_id, status).

    THE OTHER END OF THE CHAIN. `coverage_rows` asks whether a served dataset explains its columns --
    the DOWNSTREAM question. This asks the UPSTREAM one: a landed relation that no transform consumes
    has fallen out of the chain entirely, and a bundle that loses one loses it SILENTLY, because the
    measured artifact records it in `orphans.sources_feeding_nothing` and nothing read that key.
    MEASURED on contoso5, 2026-09-30: `orderrows` (223,974 rows) and `orders` (93,470) had fed nothing
    since the plane was first delivered, both carried an open DQ finding asking for a ruling, and every
    gate in the chain passed green over them.

    Accounting is the test, never resolution. The gate asks whether a person has been TOLD -- an issue
    in the DQ register naming the relation -- and leaves the ruling where it belongs, with the person
    the issue's own `needs` addresses."""
    lj = root / "data" / "lineage" / "lineage.json"
    if not lj.is_file():
        return []
    orphans = ((json.loads(lj.read_text(encoding="utf-8")) or {}).get("orphans")
               or {}).get("sources_feeding_nothing") or []
    reg = root / "data" / "quality" / "data_quality_register.yaml"
    issues = []
    if reg.is_file():
        issues = (yaml.safe_load(reg.read_text(encoding="utf-8")) or {}).get("issues") or []
    rows = []
    for rel in sorted(str(o) for o in orphans):
        rx = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(rel)}(?![A-Za-z0-9_])", re.I)
        named = [i for i in issues
                 if rx.search(" ".join(str(i.get(k) or "") for k in ("id", "title", "finding")))]
        # NAMING A RELATION IS NOT BEING ABOUT IT. First cut took the first issue that mentioned the
        # relation and credited `orders` to DQ-AMBIGREF-CURRENCYCODE, whose finding merely lists
        # "2 relation(s) (orders, sales)" while asking about a currency code. That is the same
        # collision that let a docstring about `values.aliases` certify `edges[].aliases` as read.
        # The issue must be ABOUT the orphan condition, so the text has to say so.
        about = [i for i in named
                 if ORPHAN_SIGNAL.search(" ".join(str(i.get(k) or "") for k in ("title", "finding", "needs")))]
        hit = about[0] if about else None
        rows.append({"relation": rel,
                     "issue": str(hit.get("id")) if hit else None,
                     "status": str(hit.get("status") or "?") if hit else None,
                     "mentioned_by": [str(i.get("id")) for i in named] if not hit else []})
    return rows


def coverage_rows(model):
    """One row per flow: (dataset, covered, total, coverage, derived_n, parents, unaccounted[])."""
    rows = []
    for flow in model.get("flows", []):
        cols = [c["name"] for c in (flow.get("dataset") or {}).get("columns", []) if c.get("name")]
        to_cols = {e.get("to_col") for e in flow.get("edges", [])}
        declared = {d.get("to_col") for d in flow.get("derived", [])}
        covered = [c for c in cols if c in to_cols]
        unaccounted = [c for c in cols if c not in to_cols and c not in declared]
        total = len(cols)
        rows.append({
            "dataset": flow.get("transform") or (flow.get("dataset") or {}).get("name") or "?",
            "covered": len(covered),
            "total": total,
            "coverage": (len(covered) / total) if total else 0.0,
            "derived": len(flow.get("derived", [])),
            # declared lineage PARENTS (raw_source|dataset inputs). Zero ⇒ a seed-only view, which has
            # nothing to descend from by construction and so is never failed for zero coverage.
            "parents": len(flow.get("sources") or []),
            "unaccounted": unaccounted,
        })
    rows.sort(key=lambda r: (r["coverage"], r["dataset"]))
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Lineage-coverage gate: every served dataset must explain "
                                             "at least one of its output columns")
    ap.add_argument("root", help="bundle root (a MAC source container)")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"root not found: {root}", file=sys.stderr)
        return 2

    # ONE ARTIFACT. This called lineage_project([root]) — the second producer, which builds column
    # edges from `data/transforms/*.yaml#inputs[].consumes`, a map `mac_transforms` does not generate.
    # So it found no edges, fell back to calling every column a derived const, and this gate scored
    # every bundle 0 % against a model that could not see a column. The gate was right about the
    # number and wrong about the cause. It now reads the measured artifact, like everything else.
    model = {"flows": _flows(root)}
    unclassifiable = []
    rows = coverage_rows(model)

    print(f"── lineage-coverage gate ── {len(rows)} flow(s) under {root} ──\n")

    errors: list[str] = []
    warnings: list[str] = []

    # THE UPSTREAM CHECK RUNS EVEN WITH ZERO FLOWS, and that is the whole point. A bundle with no
    # transforms is the case where a landed relation is MOST likely to have fallen out of the chain,
    # and the first cut of this section sat after the early return below, so the one shape it was
    # written for skipped it (MEASURED against a synthetic bundle, 2026-09-30).
    orphans = orphan_rows(root)
    if orphans:
        print(f"  raw source(s) feeding nothing: {len(orphans)}")
        for o in orphans:
            if o["issue"] is None:
                also = (f"; mentioned only by {', '.join(o['mentioned_by'])}, which "
                        f"{'is' if len(o['mentioned_by']) == 1 else 'are'} about something else"
                        if o["mentioned_by"] else "")
                print(f"    {o['relation']:<24s} ← ERROR (no DQ finding is about it; lineage lost silently)")
                errors.append(f"raw source '{o['relation']}' feeds nothing and no issue in "
                              f"data/quality/data_quality_register.yaml is ABOUT that{also} — a relation "
                              f"cannot leave the chain unannounced")
            elif o["status"] == "open":
                print(f"    {o['relation']:<24s} ← WARN  ({o['issue']}, open — awaiting a ruling)")
                warnings.append(f"raw source '{o['relation']}' feeds nothing; {o['issue']} is OPEN and "
                                f"asks whether the relation is out of scope or a served relation is missing")
            else:
                print(f"    {o['relation']:<24s} ok    ({o['issue']}, {o['status']})")
        print()

    if not rows:
        for w in warnings:
            print(f"  [WARN]  {w}")
        for e in errors:
            print(f"  [ERROR] {e}")
        if errors:
            print(f"\n✗ {len(errors)} raw source(s) left the chain unannounced")
            return 1
        print("✓ OK — no transform flows in this bundle (no data plane to cover)"
              + (f" ({len(warnings)} warning(s) — orphaned source)" if warnings else ""))
        return 0

    for r in rows:
        if r["total"] == 0:
            errors.append(f"{r['dataset']} : the produced dataset declares NO columns — "
                          f"no data/datasets descriptor to explain (check produces.relation)")
            continue
        if r["coverage"] <= MAX_COVERAGE_ERROR and r["parents"] == 0:
            warnings.append(f"{r['dataset']} : seed-only view — no raw_source|dataset parent, so all "
                            f"{r['total']} column(s) are declared seeds/consts, not descended columns")
        elif r["coverage"] <= MAX_COVERAGE_ERROR:
            errors.append(f"{r['dataset']} : ZERO of {r['total']} column(s) descend from an upstream "
                          f"column although the transform declares {r['parents']} lineage parent(s) — "
                          f"the view explains nothing. Check the transform's inputs[]: a raw_source|"
                          f"dataset input needs a `consumes` map naming columns its descriptor actually "
                          f"declares, and the rules' `sql` must resolve them onto the served column names")
        elif r["coverage"] < MIN_COVERAGE_WARN:
            warnings.append(f"{r['dataset']} : thin lineage — only {r['covered']}/{r['total']} column(s) "
                            f"({r['coverage']:.0%}) descend from an upstream column; the other "
                            f"{r['total'] - r['covered']} fall back to derived/const")
        if r["unaccounted"]:
            errors.append(f"{r['dataset']} : column(s) {r['unaccounted']} are neither edge-covered nor "
                          f"declared in derived[] — unaccounted output column")

    # per-dataset coverage table — the human-readable weak-spot map (weakest first)
    width = max(len(r["dataset"]) for r in rows)
    print(f"  {'coverage':>8s}  {'edges':>7s}  {'derived':>7s}  {'parents':>7s}  dataset")
    for r in rows:
        flag = ""
        if r["total"] == 0:
            flag = "  ← ERROR (no columns declared)"
        elif r["coverage"] <= MAX_COVERAGE_ERROR:
            flag = "  ← WARN (seed-only)" if r["parents"] == 0 else "  ← ERROR (explains nothing)"
        elif r["coverage"] < MIN_COVERAGE_WARN:
            flag = "  ← WARN (thin)"
        cov = f"{r['coverage']:.0%}"
        print(f"  {cov:>8s}  {r['covered']:>3d}/{r['total']:<3d}  {r['derived']:>7d}  {r['parents']:>7d}  "
              f"{r['dataset']:<{width}s}{flag}")
    print()

    for u in unclassifiable:
        warnings.append(f"{u[0]} : consumes column '{u[1]}' names rule '{u[2]}' — {u[3]} "
                        f"(the column produces no edge)")

    for w in warnings:
        print(f"  [WARN]  {w}")
    for e in errors:
        print(f"  [ERROR] {e}")
    if warnings or errors:
        print()

    covered_total = sum(r["covered"] for r in rows)
    col_total = sum(r["total"] for r in rows)
    overall = (covered_total / col_total) if col_total else 0.0
    if errors:
        print(f"✗ {len(errors)} unexplained dataset(s) — a served view whose columns descend from nothing "
              f"({len(warnings)} warning(s)); overall coverage {covered_total}/{col_total} ({overall:.0%})")
        return 1
    print(f"✓ OK — all {len(rows)} served dataset(s) explain at least one column; overall coverage "
          f"{covered_total}/{col_total} ({overall:.0%})"
          + (f" ({len(warnings)} warning(s) — thin lineage)" if warnings else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
