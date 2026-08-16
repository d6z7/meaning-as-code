#!/usr/bin/env python3
"""check_served_name_distinct.py — the SERVED-NAME-DISTINCT gate.

A served/curated dataset (data/datasets/*) must carry a CLEAN name DISTINCT from its raw source
(data/sources/*) — like the gold: raw ``dim_fpl_lm_model`` → served ``dim_model``. When the served
view is named the SAME as its raw source, the lineage's source node and dataset node collapse into one
→ the "source → dataset" (A→B) transformation renders as a SELF-LOOP and reads as flawed.

This gate makes that impossible to ship: a served dataset whose name equals any raw source name is an
ERROR — rename the served view to its clean business name (strip the source-system infix: ``fpl_lm_``,
``gold_layer_``, …). The internal identity rule (stem == table.name == view == grounding == source_view)
still holds; this only forbids the served name from COLLIDING with a raw source name.

OFFLINE + pure-structural (files on disk, no AWS).
Usage:  python3 tools/check_served_name_distinct.py <bundle-root>
        exit 0 = every served name is distinct from the raw sources ; exit 1 = a collision.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml


def _names(d: Path) -> dict:
    """{stem: table.name} for every descriptor in a plane dir (stem is the fallback name)."""
    out = {}
    if not d.exists():
        return out
    for p in sorted(d.glob("*.yaml")):
        try:
            doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            doc = {}
        tbl = (doc.get("table") or {}) if isinstance(doc, dict) else {}
        out[p.stem] = str(tbl.get("name") or p.stem)
    return out


def main(argv) -> int:
    if len(argv) != 2:
        print("usage: check_served_name_distinct.py <bundle-root>")
        return 2
    root = Path(argv[1]).resolve()
    data = root / "data"
    sources = _names(data / "sources")
    datasets = _names(data / "datasets")
    if not datasets:
        print(f"── served-name-distinct gate ── no data/datasets under {root} (skipped) ──")
        return 0

    # The lineage self-loops only when the served view's PHYSICAL name (table.name — the relation it
    # materializes to) equals a raw source's physical name. The file STEM matching raw is fine (the gold
    # does it: stem dim_fpl_lm_brand_country_code, table.name clean_dim_fpl_lm_brand_country_code — the
    # `clean_` keeps the RELATION distinct, so no self-loop). So we check table.name, not the stem.
    raw_tokens = set(sources.keys()) | set(sources.values())
    print(f"── served-name-distinct gate ── {len(datasets)} served dataset(s) vs {len(sources)} raw "
          f"source(s) under {root} ──\n")
    errors = []
    for stem, name in datasets.items():
        if name in raw_tokens:
            suggest = name.replace("fpl_lm_", "").replace("gold_layer_", "").replace("__", "_")
            errors.append(f"served dataset '{stem}' materializes to physical name '{name}', which equals "
                          f"a raw source name — the lineage self-loops. Rename the served view (table.name) "
                          f"to a distinct clean name (e.g. '{suggest}')")
    for e in errors:
        print(f"  [ERROR] {e}")
    print()
    if errors:
        print(f"✗ {len(errors)} served view(s) share a name with their raw source — the lineage "
              f"self-loops; rename to clean, distinct names (see served-view-name-distinct rule)")
        return 1
    print("✓ OK — every served dataset name is clean + distinct from the raw sources")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
