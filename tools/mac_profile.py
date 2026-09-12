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

import os
import argparse
import datetime as dt
import json
import pathlib
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _plugin  # noqa: E402  — the bundle-plugin seam, shared by five tools

SCHEMA_VERSION = "0.1.14-develop"

TOOL = "mac_profile.py/5"

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


# BOUNDED IS NOT THE SAME AS ENUMERABLE, and the first sweep conflated them. Under 600 distinct
# values it captured the full domain of `fpl_date` (348 dates), `fpl_created_at` (310 load stamps)
# and `config_key` (392 concatenated surrogates) — 56,6 % of all captured domain bytes, inlined into
# every request, telling an engine nothing it could act on. Those columns are bounded only
# ACCIDENTALLY, because this data happens to hold few values; none of them is a category a question
# ever names. The domain is worth keeping when someone would FILTER by naming one of its members.
def _enumerable(c: dict, cols: list[dict], excluded: set[str]) -> bool:
    t = str(c.get("type", "")).lower()
    n = str(c.get("name"))
    if any(t.startswith(x) for x in ORDERABLE):
        return False              # a continuum: min/max IS its domain, and the census already has it
    if c.get("role") == "audit":
        return False              # a load stamp is machinery, never an answer
    if n in excluded:
        return False              # held out of the key search as a surrogate (identity_evidence)
    if n.endswith("_id") and any(str(o.get("name")) == n[:-3] for o in cols):
        return False              # the label twin carries the meaning; the id is plumbing
    return True


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
    # DERIVED, NOT LISTED. This carried a hardcoded candidate list beginning with one source's
    # column name — a source bleeding into the framework, which is the one thing the framework may
    # not do. A write timestamp is something the DESCRIPTOR already describes: role `audit` on a
    # time-typed column. A bundle that marks its audit columns gets a watermark; one that does not
    # gets None and says so, rather than being guessed at through another source's vocabulary.
    audit = [c for c in columns
             if c.get("role") == "audit"
             and any(str(c.get("type", "")).lower().startswith(k)
                     for k in ("timestamp", "date", "time"))]
    if not audit:
        return None
    col = str(audit[0]["name"])
    return f'SELECT CAST(max("{col}") AS varchar) AS w FROM {relation}'


def bounded_values_sql(relation: str, cols: list[tuple[str, str]]) -> str:
    """ALL bounded columns in ONE scan. One query per column meant ~13 additional passes over an
    800-million-row table, ~10 GB each — the census itself costs 9,8 GB, so the value capture would
    have cost thirteen times the thing it decorates. array_agg(DISTINCT) collects every set in the
    same pass."""
    sel = [f"array_join(array_sort(array_agg(DISTINCT {expr})), chr(31)) AS v{i}"
           for i, (c, expr) in enumerate(cols)]
    return "SELECT " + ", ".join(sel) + f"\nFROM {relation}"


def apply(doc: dict, row: dict, columns: list[dict], meta: dict) -> tuple[dict, dict]:
    """Fold the measurement into (descriptor, profile).

    TWO FILES, because they have two lifecycles. The descriptor keeps the value DOMAIN — the one
    measured fact a reader needs, and whose absence let an engine invent 'C_INLAND' by concatenation.
    Everything counted goes to data/profiles/, where `measured_at` can move on every run without
    invalidating a prompt cache keyed on descriptor mtime."""
    n = int(row["n_rows"])
    prev = {c.get("name"): c for c in (meta.get("prev_profile") or {}).get("columns") or []}
    census = []
    for i, c in enumerate(columns):
        cell = {"name": str(c["name"]), "distinct": int(row[f"d{i}"]), "nulls": int(row[f"z{i}"])}
        if f"mn{i}" in row:
            cell["min"], cell["max"] = row.get(f"mn{i}"), row.get(f"mx{i}")
        # `determined_by` is written by the ADMISSION pass, not the census — carry it, never clear it
        keep = (prev.get(str(c["name"])) or {}).get("determined_by")
        if keep:
            cell["determined_by"] = keep
        census.append(cell)
        for target in doc.get("columns") or []:
            if target.get("name") == c["name"]:
                if c["name"] in (meta.get("bounded") or {}):
                    target["values"] = meta["bounded"][c["name"]]
                else:
                    target.pop("values", None)   # no longer bounded: the old domain is now a lie
                target.pop("profile", None)      # pre-split residue
    doc.pop("profile", None)
    prof = {
        "metadata": {"schema_version": SCHEMA_VERSION, "generated_by": TOOL},
        "of": meta["stem"], "relation": meta["relation"],
        "profile": {k: v for k, v in {
            "measured_at": meta["measured_at"], "rows": n, "newest_write": meta.get("newest_write"),
            "method": TOOL, "engine": meta.get("engine"), "scanned_bytes": meta.get("scanned_bytes"),
        }.items() if v is not None or k in ("newest_write",)},
        "columns": census,
    }
    ie = (meta.get("prev_profile") or {}).get("identity_evidence")
    if ie:
        prof["identity_evidence"] = ie          # the admission pass owns it; the census must not drop it
    return doc, prof


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

    # The bundle owns the connection; MAC owns the algorithm. Declared-but-unusable must exit 2
    # rather than let the bundle's SystemExit become this tool's verdict. See tools/_plugin.py.
    try:
        Athena = _plugin.required(root, "Athena")
    except _plugin.PluginUnavailable as exc:
        print(f"could not run: {root} {exc}", file=sys.stderr)
        return 2
    eng = (yaml.safe_load((root / "acceptance" / "properties.yaml").read_text(encoding="utf-8"))
           or {}).get("engine") or {}
    ath = Athena(eng["profile"], eng["region"], eng["workgroup"], eng["database"])

    rows, meta = ath.query(sql)

    # SECOND PASS, only for columns small enough to enumerate. The census says HOW MANY; for a
    # bounded column the structure is WHICH, and a rename leaves the count untouched.
    excluded = set(((prev_peek := yaml.safe_load(
        (root / "data" / "profiles" / f"{a.dataset}.yaml").read_text(encoding="utf-8"))
        if (root / "data" / "profiles" / f"{a.dataset}.yaml").exists() else {}) or {})
        .get("identity_evidence", {}).get("excluded") or [])
    want = [(str(c["name"]), _as_text(str(c["name"]), _is_complex(c)))
            for i, c in enumerate(columns)
            if 0 < int(rows[0][f"d{i}"]) <= BOUNDED_MAX and _enumerable(c, columns, excluded)]
    skipped = [str(c["name"]) for i, c in enumerate(columns)
               if 0 < int(rows[0][f"d{i}"]) <= BOUNDED_MAX and not _enumerable(c, columns, excluded)]
    if skipped:
        print(f"  bounded but not enumerable, no domain captured: {', '.join(skipped)}")
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

    ppath = root / "data" / "profiles" / f"{a.dataset}.yaml"
    prev = yaml.safe_load(ppath.read_text(encoding="utf-8")) if ppath.exists() else {}
    doc, prof = apply(doc, rows[0], columns, {
        "measured_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "newest_write": newest,
        "bounded": bounded,
        "stem": a.dataset,
        "relation": relation,
        "prev_profile": prev,
        "engine": f"{eng.get('database')}@{eng.get('region')}",
        "scanned_bytes": meta.get("bytes_scanned"),
    })
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100),
                    encoding="utf-8")
    ppath.parent.mkdir(parents=True, exist_ok=True)
    ppath.write_text(yaml.safe_dump(prof, sort_keys=False, allow_unicode=True, width=100),
                     encoding="utf-8")
    p = prof["profile"]
    print(f"  {relation}  {p['rows']:,}".replace(",", ".") + " rows · "
          f"{len(columns)} columns profiled · newest write {p.get('newest_write')}")
    print(f"  scanned {(p.get('scanned_bytes') or 0)/1e9:.1f} GB → {ppath.relative_to(root)}"
          f" (+ domains on {path.relative_to(root)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
