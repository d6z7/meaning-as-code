#!/usr/bin/env python3
"""
check_relation_identity.py — the CROSS-REFERENCE (canonical relation name) gate.

The right-first-time harvest invariant #2 (docs/HARVEST_RIGHT_FIRST_TIME.md): for every serving
relation there is exactly ONE name in all five places —
  1. the data/datasets/<name>.yaml  FILE STEM
  2. its  table.name
  3. its physical view   (<view_schema>.<name>)                     [live; not checked here — see materialize step]
  4. the concept  grounding.sources[].relation  TAIL
  5. any lookup's  source_view
The name is the raw table's base name, with NO `_clean`/`clean_` prefix or suffix (the source's own
schema already separates serving from raw). A divergence — e.g. stem `v_<source>_gold_layer_kpi` vs
table.name `v_<source>_gold_layer_kpi_clean` — is the cross-reference break this gate reds on.

This gate is OFFLINE and pure-structural (no AWS): it asserts the NAMES agree across files. Whether the
physical view actually exists live is the harvest's materialize step, NOT a gate (gates stay AWS-free).

Checks (each divergence reported as file:field):
  A. every  data/datasets/<stem>.yaml :  stem == table.name
  B. every concept  grounding.sources[].relation  tail that names a KNOWN physical view (a dataset's
     table.name) instead of the canonical stem
  C. every lookup CSV  source_view  value that names a KNOWN physical view instead of the canonical stem
A tail/source_view that resolves to no dataset at all is left to check_references.py (dangling-ref gate);
this gate is specifically about NAME DIVERGENCE among relations that DO exist.

Usage:  python3 tools/check_relation_identity.py <bundle-root>
        exit 0 = all relation names aligned ; exit 1 = at least one divergence.

Wire into your bundle's offline gate chain, guarded on the two-plane
data layout so it is a no-op for flat sources:
    if [ -d "$SOURCE_ROOT/data/datasets" ]; then
      echo "▶ relation-identity (check_relation_identity.py $SOURCE_ROOT)"
      "$PY" "$FW/tools/check_relation_identity.py" "$SOURCE_ROOT" || rc=1
    fi
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mac_project import resolve  # noqa: E402

LOOKUP_CSV_RE = re.compile(r"data/lookups/[\w./-]+?\.csv")


def load(p: Path):
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return e


def tail(name: str) -> str:
    return str(name).split(".")[-1]


def grounding_relations(doc: dict):
    """Every relation a concept grounds to, across all grounding forms (mirrors check_references)."""
    if not isinstance(doc, dict):
        return []
    c = doc.get("concept") if isinstance(doc.get("concept"), dict) else {}
    g = c.get("grounding") or doc.get("grounding")
    if not isinstance(g, dict):
        return []
    out = []
    if isinstance(g.get("table"), str):
        out.append(g["table"])
    for key in ("tables", "primary_tables"):
        for t in (g.get(key) or []):
            if isinstance(t, dict) and t.get("name"):
                out.append(t["name"])
            elif isinstance(t, str):
                out.append(t)
    for s in (g.get("sources") or []):
        if isinstance(s, dict) and isinstance(s.get("relation"), str):
            out.append(s["relation"])
    return out


def no_probe_text(doc: dict) -> str:
    if not isinstance(doc, dict):
        return ""
    for holder in (doc.get("contract"), (doc.get("concept") or {}).get("contract") if isinstance(doc.get("concept"), dict) else None):
        if isinstance(holder, dict) and isinstance(holder.get("no_probe_guarantee"), str):
            return holder["no_probe_guarantee"]
    return ""


def source_view_values(csv_path: Path):
    """Distinct non-empty values of a `source_view` column, if the CSV declares one."""
    try:
        import csv
        with csv_path.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
    except Exception:  # noqa: BLE001
        return set()
    if not rows or "source_view" not in rows[0]:
        return set()
    return {r["source_view"].strip() for r in rows if (r.get("source_view") or "").strip()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cross-reference (canonical relation name) gate")
    ap.add_argument("root", help="bundle root (a MAC source container)")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"root not found: {root}", file=sys.stderr)
        return 2

    L = resolve(root)
    ds_dir = L.descriptors
    if not ds_dir or not Path(ds_dir).is_dir():
        print(f"── relation-identity ── {root} ──\n  no data/datasets descriptor dir — nothing to check (skip)")
        return 0

    findings: list[str] = []

    # -- build the dataset identity map: stem -> table.name --------------------------------
    stems: set[str] = set()
    physical_to_stem: dict[str, str] = {}     # table.name -> stem (only when they differ)
    for p in sorted(Path(ds_dir).glob("*.yaml")):
        stem = p.stem
        stems.add(stem)
        doc = load(p)
        if isinstance(doc, Exception):
            findings.append(f"data/datasets/{p.name} :: YAML parse error: {doc}")
            continue
        tbl = doc.get("table") if isinstance(doc, dict) else None
        name = tbl.get("name") if isinstance(tbl, dict) else None
        if not name:
            findings.append(f"data/datasets/{p.name} : table.name — missing (cannot verify identity)")
            continue
        # A. intra-file identity: file stem == table.name
        if name != stem:
            findings.append(
                f"data/datasets/{p.name} : table.name '{name}' != file stem '{stem}' "
                f"— canonicalize to one name (drop the _clean/clean_ divergence)")
        physical_to_stem[name] = stem

    def flag_divergent(where: str, ref: str, kind: str):
        t = tail(ref)
        if t in stems:
            return                                        # names the canonical stem — aligned
        if t in physical_to_stem and physical_to_stem[t] != t:
            findings.append(
                f"{where} : {kind} '{ref}' names the physical view '{t}'; "
                f"the canonical relation name is the dataset stem '{physical_to_stem[t]}'")
        # else: resolves to no dataset — a dangling ref, owned by check_references.py (not this gate)

    # -- B. concept groundings --------------------------------------------------------------
    concepts_dir = Path(L.ontology) / "concepts"
    if concepts_dir.is_dir():
        for p in sorted(concepts_dir.rglob("*.yaml")):
            doc = load(p)
            if isinstance(doc, Exception) or not isinstance(doc, dict):
                continue
            rel = p.relative_to(root)
            for r in grounding_relations(doc):
                flag_divergent(f"{rel} grounding", r, "grounding.sources[].relation")

    # -- C. lookup source_view --------------------------------------------------------------
    lk_dir = root / "data" / "lookups"
    if lk_dir.is_dir():
        for csv_path in sorted(lk_dir.glob("*.csv")):
            for v in sorted(source_view_values(csv_path)):
                flag_divergent(f"data/lookups/{csv_path.name}", v, "source_view")

    # -- report -----------------------------------------------------------------------------
    print(f"── relation-identity gate ── {len(stems)} dataset(s) under {root} ──")
    for f in findings:
        print(f"  [ERROR] {f}")
    if findings:
        print(f"\n✗ {len(findings)} relation-name divergence(s) — one name in stem == table.name == "
              f"grounding tail == source_view")
        return 1
    print("\n✓ OK — every relation name is aligned across stem/table.name/grounding/source_view")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
