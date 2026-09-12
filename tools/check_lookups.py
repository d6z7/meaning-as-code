#!/usr/bin/env python3
"""
check_lookups.py — the LOOKUPS-plane integrity gate.

Right-first-time harvest invariant #3 (docs/HARVEST_RIGHT_FIRST_TIME.md): a concept resolves names to
codes through a build-time lookup register (data/lookups/<x>.csv) so the runtime answers inline instead of
re-deriving by probing the raw EAV. This gate proves that plane is WHOLE:

  A. every  data/lookups/<x>.csv  cited in a concept's  contract.no_probe_guarantee  exists AND is
     non-empty (a header plus at least one data row).
  B. every lookup CSV that declares a  source_view  column: each distinct value resolves to a real
     data/datasets relation (by dataset STEM or by its declared table.name) — a dangling source_view reds.
     (Whether that source_view uses the canonical stem vs the physical _clean name is
     check_relation_identity.py's job; this gate only asks that it names a relation that EXISTS.)

This gate is OFFLINE and pure-structural (no AWS): it checks files on disk, never the warehouse.

Usage:  python3 tools/check_lookups.py <bundle-root>
        exit 0 = lookups plane whole ; exit 1 = a missing/empty lookup or a dangling source_view.

Wire into your bundle's offline gate chain (guarded on the two-plane data layout):
    if [ -d "$SOURCE_ROOT/data/datasets" ]; then
      echo "▶ lookups plane (check_lookups.py $SOURCE_ROOT)"
      "$PY" "$FW/tools/check_lookups.py" "$SOURCE_ROOT" || rc=1
    fi
"""
from __future__ import annotations
import argparse
import csv
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


def no_probe_text(doc: dict) -> str:
    if not isinstance(doc, dict):
        return ""
    holders = [doc.get("contract")]
    if isinstance(doc.get("concept"), dict):
        holders.append(doc["concept"].get("contract"))
    for h in holders:
        if isinstance(h, dict) and isinstance(h.get("no_probe_guarantee"), str):
            return h["no_probe_guarantee"]
    return ""


def csv_nonempty(p: Path) -> bool:
    """True when the CSV has a header plus at least one non-blank data row."""
    try:
        lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except Exception:  # noqa: BLE001
        return False
    return len(lines) >= 2


def source_view_values(p: Path):
    try:
        with p.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
    except Exception:  # noqa: BLE001
        return set()
    if not rows or "source_view" not in rows[0]:
        return set()
    return {r["source_view"].strip() for r in rows if (r.get("source_view") or "").strip()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Lookups-plane integrity gate")
    ap.add_argument("root", help="bundle root (a MAC source container)")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"root not found: {root}", file=sys.stderr)
        return 2

    L = resolve(root)
    lk_dir = root / "data" / "lookups"
    concepts_dir = Path(L.ontology) / "concepts"

    # real relations = dataset stems ∪ their declared table.names (identity divergence is a separate gate)
    real_relations: set[str] = set()
    ds_dir = L.descriptors
    if ds_dir and Path(ds_dir).is_dir():
        for p in sorted(Path(ds_dir).glob("*.yaml")):
            real_relations.add(p.stem)
            doc = load(p)
            tbl = doc.get("table") if isinstance(doc, dict) else None
            if isinstance(tbl, dict) and isinstance(tbl.get("name"), str):
                real_relations.add(tbl["name"].strip())

    findings: list[str] = []

    # A. every lookup cited in a no_probe_guarantee must exist + be non-empty
    cited = 0
    if concepts_dir.is_dir():
        for p in sorted(concepts_dir.rglob("*.yaml")):
            doc = load(p)
            if isinstance(doc, Exception) or not isinstance(doc, dict):
                continue
            txt = no_probe_text(doc)
            if not txt:
                continue
            rel = p.relative_to(root)
            for m in sorted(set(LOOKUP_CSV_RE.findall(txt))):
                cited += 1
                target = root / m
                if not target.is_file():
                    findings.append(f"{rel} no_probe_guarantee : cites '{m}' — file does not exist")
                elif not csv_nonempty(target):
                    findings.append(f"{rel} no_probe_guarantee : cites '{m}' — file is empty "
                                    f"(needs a header + at least one data row)")

    # B. every lookup's declared source_view must resolve to a real data/datasets relation
    checked_sv = 0
    if lk_dir.is_dir():
        for csv_path in sorted(lk_dir.glob("*.csv")):
            for v in sorted(source_view_values(csv_path)):
                checked_sv += 1
                if v.split(".")[-1] not in real_relations:
                    findings.append(
                        f"data/lookups/{csv_path.name} : source_view '{v}' resolves to no "
                        f"data/datasets relation (dangling)")

    print(f"── lookups gate ── {cited} cited lookup(s), {checked_sv} source_view value(s) under {root} ──")
    for f in findings:
        print(f"  [ERROR] {f}")
    if findings:
        print(f"\n✗ {len(findings)} lookup-plane defect(s) — a no-probe guarantee that cites an absent "
              f"register, or a dangling source_view")
        return 1
    print("\n✓ OK — every cited lookup exists + is non-empty, every source_view resolves to a real relation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
