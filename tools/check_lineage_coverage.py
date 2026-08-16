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

The coverage model is the lineage projection itself (tools/lineage_project.py), so this gate is OFFLINE
and pure-structural: it reads the governed YAML descriptors (data/sources, data/transforms,
data/datasets) and never touches the warehouse.

Usage:  python3 tools/check_lineage_coverage.py <bundle-root>
        exit 0 = every served dataset explains at least one column ; exit 1 = an unexplained view.

Wire into cap-ontology-workbench/tools/check_all.sh (guarded on the two-plane data layout):
    if [ -d "$SOURCE_ROOT/data/transforms" ]; then
      echo "▶ lineage coverage (check_lineage_coverage.py $SOURCE_ROOT)"
      "$PY" "$FW/tools/check_lineage_coverage.py" "$SOURCE_ROOT" || rc=1
    fi
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lineage_project import project  # noqa: E402

# ── thresholds ──────────────────────────────────────────────────────────────────────────────────────
# A dataset at or below this coverage is an ERROR: it explains NOTHING (the degenerate collapse).
MAX_COVERAGE_ERROR = 0.0
# A dataset below this coverage is a WARN: thin lineage, probably an under-declared `consumes` map.
MIN_COVERAGE_WARN = 0.50


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

    model, unclassifiable = project([str(root)])
    rows = coverage_rows(model)

    print(f"── lineage-coverage gate ── {len(rows)} flow(s) under {root} ──\n")
    if not rows:
        print("✓ OK — no transform flows in this bundle (no data plane to cover)")
        return 0

    errors: list[str] = []
    warnings: list[str] = []

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
