#!/usr/bin/env python3
"""mac_measure_edges — count what every declared join predicate claims, and record it as evidence.

THE BOTTLENECK THIS REMOVES. `verified_by` on an edge points at an expectation a human wrote. That
is why one edge in thirty-two carried evidence: proving a relationship required somebody to author a
test for it. But an edge's two claims are pure counting — does every key resolve, and does it resolve
to at most one row — so the evidence can be GENERATED. This writes it.

IT DOES NOT WRITE THE ONTOLOGY. It writes `evidence/edge_measurements.json`, the way a suite run
writes its run record, and `check_edge_joins_measured` reads that. Recording a measurement as an
edge's `verified_by` is a change to meaning and belongs to whoever rules on meaning; this produces
the number that ruling needs, and stops.

WHY TWO NUMBERS AND NOT ONE. CONTAINMENT alone passes a predicate that multiplies every row it
touches — one measured at 215x in this estate, sitting under a declared cardinality of "1" for
months. FANOUT alone passes a predicate that matches nothing at all, which renders as an empty
result and reads as a clean zero. Each misses exactly what the other catches.

USAGE
    python3 tools/mac_measure_edges.py <bundle-root> [--dry-run]

Read-only. Every statement it issues is a SELECT of COUNTs over key columns.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import pathlib
import re
import sys

import yaml

PREDICATE = re.compile(r"^\s*([\w.]+)\.(\w+)\s*=\s*([\w.]+)\.(\w+)\s*$")


def _descriptors(root: pathlib.Path) -> dict[str, str]:
    """declared relation name -> physically qualified name, from the dataset descriptors."""
    out: dict[str, str] = {}
    for f in sorted((root / "data" / "datasets").glob("*.yaml")):
        d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        t = d.get("table") or {}
        name = t.get("name") or f.stem
        out[name] = ".".join(p for p in (t.get("schema"), t.get("name")) if p) or name
    return out


def _athena(root: pathlib.Path):
    """Borrow the bundle's own client so region, workgroup and profile come from one place."""
    rp = root / "tools" / "run_properties.py"
    if not rp.exists():
        raise SystemExit(f"REFUSED: no query runner at {rp}")
    spec = importlib.util.spec_from_file_location("rp", rp)
    m = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, ["x"]
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    finally:
        sys.argv = argv
    eng = (yaml.safe_load((root / "acceptance" / "properties.yaml").read_text()) or {})["engine"]
    return m.Athena(eng["profile"], eng["region"], eng["workgroup"], eng["database"])


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("root")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    root = pathlib.Path(a.root).resolve()

    edges = (yaml.safe_load((root / "ontology" / "edges.yaml").read_text()) or {}).get("edges") or []
    desc = _descriptors(root)

    # ONE MEASUREMENT PER DISTINCT PREDICATE, not per edge. Fourteen of this bundle's eighteen
    # declared predicates are the same two joins repeated across the measure concepts; measuring
    # each edge separately would issue the identical query seven times and invite the reader to
    # believe seven independent facts had been established.
    work: dict[tuple, list[str]] = {}
    unparseable: list[str] = []
    for e in edges:
        pred = e.get("join_rule")
        if not isinstance(pred, str) or not pred.strip():
            continue
        m = PREDICATE.match(pred)
        if not m:
            unparseable.append(str(e.get("edge_id")))
            continue
        lr, lc, rr, rc = m.groups()
        if lr not in desc or rr not in desc:
            unparseable.append(str(e.get("edge_id")))
            continue
        work.setdefault((desc[lr], lc, desc[rr], rc), []).append(str(e.get("edge_id")))

    print(f"  {len(edges)} edge(s); {sum(len(v) for v in work.values())} declare a parseable "
          f"predicate over {len(work)} DISTINCT join(s)")
    for (lp, lc, rp_, rc), eids in work.items():
        print(f"    {lp}.{lc} = {rp_}.{rc}   ({len(eids)} edge(s))")
    if unparseable:
        print(f"  REFUSED to measure {len(unparseable)}: {', '.join(unparseable)}")
    if a.dry_run:
        print("  DRY RUN — nothing executed")
        return 0
    if not work:
        print("REFUSED: no measurable predicate — nothing to record, and an empty record would "
              "read as a clean measurement")
        return 2

    ath = _athena(root)
    results = []
    for (lp, lc, rp_, rc), eids in work.items():
        sql = (
            f"SELECT (SELECT COUNT(DISTINCT {lc}) FROM {lp}) AS lhs, "
            f"(SELECT COUNT(*) FROM (SELECT DISTINCT {lc} v FROM {lp}) a "
            f"JOIN (SELECT DISTINCT {rc} k FROM {rp_}) b ON a.v = b.k) AS matched, "
            f"(SELECT COALESCE(MAX(c), 0) FROM (SELECT {rc}, COUNT(*) c FROM {rp_} GROUP BY 1)) "
            f"AS fanout"
        )
        rows, _ = ath.query(sql)
        r = rows[0]
        lhs, matched, fanout = int(r["lhs"]), int(r["matched"]), int(r["fanout"])
        pct = (100.0 * matched / lhs) if lhs else 0.0
        print(f"    {lp}.{lc:<28} {matched}/{lhs} resolve ({pct:.1f}%), max fanout {fanout}")
        for eid in eids:
            results.append({"edge": eid, "predicate": f"{lp}.{lc} = {rp_}.{rc}",
                            "lhs": lhs, "matched": matched, "fanout": fanout, "sql": sql})

    out = root / "evidence" / "edge_measurements.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    # STAGE THEN REPLACE. A redirect that opens the real file truncates it before the tool has
    # produced anything, and a failed run then leaves an empty record that reads as "measured, found
    # nothing" — this estate lost 3.5 MB of test lineage to exactly that once.
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(
            {
                "measured_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                "distinct_joins": len(work),
                "edges_covered": len(results),
                "unmeasurable": unparseable,
                "results": results,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    tmp.replace(out)
    print(f"  recorded {len(results)} edge measurement(s) over {len(work)} distinct join(s) "
          f"-> {out.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
