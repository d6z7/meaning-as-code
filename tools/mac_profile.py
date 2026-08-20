#!/usr/bin/env python3
"""Profile a relation and PERSIST the result into its descriptor.

THE PROFILE ALREADY EXISTED AND WAS THROWN AWAY. `sdk/authoring/data_plane.py:196 profile_table()`
runs one aggregate over every column of every relation — and line 330 returns only `row_count`. The
rest is rendered to markdown, pasted into an LLM prompt, and discarded. **The profile was not an
artifact**, which is why grain ended up hand-typed, hand-typed DIFFERENTLY in two planes, and why an
extension had to be invented to hold it. This does not add a scan; it keeps one already paid for.

WHAT IT WRITES, both machine-only:
    columns[].profile   {distinct, nulls, min, max}   the census
    profile             {measured_at, rows, newest_write, method, engine, scanned_bytes}

EXACT COUNTS, NOT SKETCHES. `approx_distinct` is HLL and was measured returning 803.502.276 distinct
values for an 800.821.485-row relation — an impossible answer — and claiming 1.091 model codes
against 1.090 ids where the exact check found no violation. A sketch can RANK candidate keys; it can
never decide uniqueness, and uniqueness is the question. Sampling is out for the same reason:
TABLESAMPLE destroys duplicates, so uniqueness is not sample-testable.

IDEMPOTENT BY CONSTRUCTION. Re-running against unchanged data must reproduce the file byte-for-byte
except `measured_at` — that is the exit test, and it is what makes a diff meaningful: if the numbers
move, the SOURCE moved.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

import yaml

TOOL = "mac_profile.py/3"

# A column with at most this many distinct values is treated as BOUNDED and its full value set is
# captured. Above it, membership is volume — a model-code list grows by design — and only the count
# is kept. The threshold is deliberately generous: 18 delivery statuses and 21 measures must fit,
# and enumerating 578 market codes is cheap insurance against a brand-scoped scheme changing.
BOUNDED_MAX = 600

# A column whose value is itself a collection. dim_model carries seven — brand, powertrains,
# body_styles and so on are array(string). CAST(array AS varchar) is a type error in Trino, and the
# first sweep failed on exactly that. They are still profiled: the count of distinct ARRAYS and the
# nulls are real facts. Only the value-set capture needs the array flattened to text first.
COMPLEX = ("array", "map", "row", "struct")


def _is_complex(c: dict) -> bool:
    return any(str(c.get("type", "")).lower().startswith(k) for k in COMPLEX)


def _as_text(name: str, complex_: bool) -> str:
    """Render a column as comparable text. An array becomes its sorted joined members, so two rows
    carrying the same set in a different order count as one value rather than two."""
    q = f'"{name}"'
    return (f"array_join(array_sort({q}), ',')" if complex_ else f"CAST({q} AS varchar)")

# Types worth a min/max. A min/max over a free-text column is noise, not a fact.
ORDERABLE = ("date", "time", "timestamp", "int", "bigint", "smallint", "tinyint",
             "double", "float", "real", "decimal", "numeric")


def profile_sql(relation: str, columns: list[dict]) -> str:
    """ONE scan. Exact distinct and exact nulls per column, min/max where ordering means something."""
    sel = ["count(*) AS n_rows"]
    for i, c in enumerate(columns):
        q = '"' + str(c["name"]).replace('"', "") + '"'
        sel.append(f"count(DISTINCT {q}) AS d{i}")
        sel.append(f"count(*) - count({q}) AS z{i}")
        if any(str(c.get("type", "")).lower().startswith(o) for o in ORDERABLE):
            sel.append(f"try_cast(min({q}) AS varchar) AS mn{i}")
            sel.append(f"try_cast(max({q}) AS varchar) AS mx{i}")
    return "SELECT " + ", ".join(sel) + f"\nFROM {relation}"


def watermark_sql(relation: str, columns: list[dict]) -> str | None:
    """The source's own high-water mark, if it has one. This is what dates the evidence."""
    names = {str(c["name"]).lower() for c in columns}
    for cand in ("fpl_created_at", "created_at", "loaded_at", "ingested_at", "updated_at"):
        if cand in names:
            return f"SELECT CAST(max({cand}) AS varchar) AS w FROM {relation}"
    return None


def bounded_values_sql(relation: str, cols: list[tuple[str, str]]) -> str:
    """ALL bounded columns in ONE scan. One query per column meant ~13 additional passes over an
    800-million-row table, ~10 GB each — the census itself costs 9,8 GB, so the value capture would
    have cost thirteen times the thing it decorates. array_agg(DISTINCT) collects every set in the
    same pass."""
    sel = [f"array_join(array_sort(array_agg(DISTINCT {expr})), chr(31)) AS v{i}"
           for i, (c, expr) in enumerate(cols)]
    return "SELECT " + ", ".join(sel) + f"\nFROM {relation}"


def apply(doc: dict, row: dict, columns: list[dict], meta: dict) -> dict:
    """Fold the measurement into the descriptor. Only ever writes the two machine-owned blocks."""
    n = int(row["n_rows"])
    for i, c in enumerate(columns):
        prof = {"distinct": int(row[f"d{i}"]), "nulls": int(row[f"z{i}"])}
        if f"mn{i}" in row:
            prof["min"], prof["max"] = row.get(f"mn{i}"), row.get(f"mx{i}")
        if c["name"] in (meta.get("bounded") or {}):
            prof["values"] = meta["bounded"][c["name"]]
        for target in doc.get("columns") or []:
            if target.get("name") == c["name"]:
                # preserve `determined_by` — it is written by the admission pass, not by the census
                keep = (target.get("profile") or {}).get("determined_by")
                if keep:
                    prof["determined_by"] = keep
                target["profile"] = prof
    doc["profile"] = {k: v for k, v in {
        "measured_at": meta["measured_at"], "rows": n, "newest_write": meta.get("newest_write"),
        "method": TOOL, "engine": meta.get("engine"), "scanned_bytes": meta.get("scanned_bytes"),
    }.items() if v is not None or k in ("newest_write",)}
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("dataset", help="descriptor stem under data/datasets or data/sources")
    ap.add_argument("--runner", default=None,
                    help="python module exposing query(sql)->(rows, meta); defaults to the bundle's "
                         "tools/run_properties.py Athena helper")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    root = pathlib.Path(a.root).resolve()
    cand = [root / "data" / d / f"{a.dataset}.yaml" for d in ("datasets", "sources")]
    path = next((p for p in cand if p.exists()), None)
    if path is None:
        print(f"no descriptor for {a.dataset!r} under data/datasets or data/sources", file=sys.stderr)
        return 2

    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tbl = doc.get("table") or {}
    relation = ".".join(x for x in (tbl.get("schema"), tbl.get("name")) if x)
    columns = [c for c in (doc.get("columns") or []) if c.get("name")]
    if not relation or not columns:
        print(f"{path.name}: needs table.name and columns[]", file=sys.stderr)
        return 2

    sql = profile_sql(relation, columns)
    if a.dry_run:
        print(sql)
        return 0

    sys.path.insert(0, str(root / "tools"))
    from run_properties import Athena  # the bundle owns the connection; MAC owns the algorithm
    eng = (yaml.safe_load((root / "acceptance" / "properties.yaml").read_text(encoding="utf-8"))
           or {}).get("engine") or {}
    ath = Athena(eng["profile"], eng["region"], eng["workgroup"], eng["database"])

    rows, meta = ath.query(sql)

    # SECOND PASS, only for columns small enough to enumerate. The census says HOW MANY; for a
    # bounded column the structure is WHICH, and a rename leaves the count untouched.
    want = [(str(c["name"]), _as_text(str(c["name"]), _is_complex(c)))
            for i, c in enumerate(columns) if 0 < int(rows[0][f"d{i}"]) <= BOUNDED_MAX]
    bounded = {}
    if want:
        vr, vmeta = ath.query(bounded_values_sql(relation, want))
        for i, (name, _) in enumerate(want):
            raw = vr[0].get(f"v{i}")
            bounded[name] = raw.split(chr(31)) if raw else []
        meta["bytes_scanned"] = (meta.get("bytes_scanned") or 0) + (vmeta.get("bytes_scanned") or 0)

    wm_sql = watermark_sql(relation, columns)
    newest = None
    if wm_sql:
        wr, _ = ath.query(wm_sql)
        newest = wr[0]["w"]

    doc = apply(doc, rows[0], columns, {
        "measured_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "newest_write": newest,
        "bounded": bounded,
        "engine": f"{eng.get('database')}@{eng.get('region')}",
        "scanned_bytes": meta.get("bytes_scanned"),
    })
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100),
                    encoding="utf-8")
    p = doc["profile"]
    print(f"  {relation}  {p['rows']:,}".replace(",", ".") + " rows · "
          f"{len(columns)} columns profiled · newest write {p.get('newest_write')}")
    print(f"  scanned {(p.get('scanned_bytes') or 0)/1e9:.1f} GB → {path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
