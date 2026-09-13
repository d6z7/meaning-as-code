#!/usr/bin/env python3
"""check_ontology_grounds_on_datasets.py — the ARCHITECTURAL CHAIN gate.

Meaning is built in ONE direction, and every link must exist:

    raw source  ->  transformation  ->  dataset  ->  ontology

The ontology may bind ONLY to a SERVED dataset (data/datasets/*). It must never bind a raw landing
(data/sources/*) — a raw table is observed, not curated: its shape is the source system's, its defects
are undissolved, and a concept grounded there silently inherits both. And a dataset must never appear
out of nowhere: even a 1:1 passthrough goes through a declared transformation (data/transforms/*), so
the "how did this served relation come to be" question always has a written answer.

This gate makes a broken chain impossible to ship:
  A. ERROR — a concept grounding relation that resolves to NO served dataset (dangling binding).
             Relations naming an authored `data/lookups/*.csv` register are allowed (reference data),
             but WARN: that is a hand-authored table, not a transformed dataset.
  B. ERROR — a grounding relation that names a RAW source. Either the ontology binds raw directly, or
             the served dataset carries the raw's physical name so the binding is AMBIGUOUS (nothing on
             disk proves the concept reads the curated relation) — see check_served_name_distinct.py.
  C. ERROR — a served dataset that no transformation produces (an unexplained relation).
  D. ERROR — a transformation whose produces.relation has no dataset descriptor (it builds nothing served).
  E. WARN  — a raw source consumed by no transformation (an orphan landing: harvested, never used).

OFFLINE + pure-structural (files on disk, no AWS).
Usage:  python3 tools/check_ontology_grounds_on_datasets.py <bundle-root>
        exit 0 = the chain is whole ; exit 1 = a broken or short-circuited link.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML required: pip install pyyaml")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mac_project import resolve  # noqa: E402


def _load(p: Path) -> dict:
    try:
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return doc if isinstance(doc, dict) else {}


def _plane(layout_dir, root: Path, fallback: str) -> Path:
    """The declared plane dir (mac.project.yaml) when it exists, else the conventional layout."""
    declared = Path(layout_dir) if layout_dir else None
    if declared and declared.is_dir():
        return declared
    fb = root / fallback
    return fb if fb.is_dir() else (declared or fb)


def _rel(p: Path, root: Path) -> str:
    """A path shown relative to the bundle root when it lives inside it."""
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


def _leaf(rel: str) -> str:
    """The bare relation name — '<dataset>.dim_model' -> 'dim_model'."""
    return str(rel).strip().split(".")[-1]


def _is_lookup(rel: str) -> bool:
    r = str(rel).strip()
    return "data/lookups/" in r and r.endswith(".csv")


def _grounding_relations(doc: dict):
    """[(relation, key)] declared by a concept's grounding.sources[]."""
    g = doc.get("grounding")
    if not isinstance(g, dict):
        c = doc.get("concept")
        g = c.get("grounding") if isinstance(c, dict) else None
    if not isinstance(g, dict):
        return []
    out = []
    for s in (g.get("sources") or []):
        rel = s.get("relation") if isinstance(s, dict) else s
        if isinstance(rel, str) and rel.strip():
            out.append(rel.strip())
    return out


def main(argv) -> int:
    if len(argv) != 2:
        print("usage: check_ontology_grounds_on_datasets.py <bundle-root>")
        return 2
    root = Path(argv[1]).resolve()
    if not root.is_dir():
        print(f"root not found: {root}", file=sys.stderr)
        return 2

    L = resolve(root)
    ds_dir = _plane(L.descriptors, root, "data/datasets")
    tf_dir = _plane(L.transforms, root, "data/transforms")
    src_dir = _plane(L.sources, root, "data/sources")
    concepts_dir = _plane(Path(L.ontology) / "concepts", root, "ontology/concepts")

    ds_files = sorted(ds_dir.glob("*.yaml")) if ds_dir.is_dir() else []
    if not ds_files:
        print(f"── ontology-grounds-on-datasets gate ── no served datasets under {root} (skipped) ──")
        return 0

    # ---- index the three data planes -------------------------------------------------------------
    ds_qual: dict[str, str] = {}   # "<schema>.<table.name>" -> stem
    ds_leaf: dict[str, str] = {}   # bare name / stem        -> stem
    for p in ds_files:
        doc = _load(p)
        tbl = doc.get("table") if isinstance(doc.get("table"), dict) else {}
        name = str(tbl.get("name") or p.stem).strip()
        schema = str(tbl.get("schema") or "").strip()
        if schema:
            ds_qual[f"{schema}.{name}"] = p.stem
        ds_leaf.setdefault(name, p.stem)
        ds_leaf.setdefault(p.stem, p.stem)

    src_files = sorted(src_dir.glob("*.yaml")) if src_dir.is_dir() else []
    raw_qual: dict[str, str] = {}
    raw_leaf: dict[str, str] = {}
    for p in src_files:
        doc = _load(p)
        tbl = doc.get("table") if isinstance(doc.get("table"), dict) else {}
        name = str(tbl.get("name") or p.stem).strip()
        schema = str(tbl.get("schema") or "").strip()
        if schema:
            raw_qual[f"{schema}.{name}"] = p.stem
        raw_leaf.setdefault(name, p.stem)
        raw_leaf.setdefault(p.stem, p.stem)

    tf_files = sorted(tf_dir.glob("*.yaml")) if tf_dir.is_dir() else []
    produced_qual: dict[str, str] = {}    # produces.relation      -> transform stem
    produced_leaf: dict[str, str] = {}    # bare produced relation -> transform stem
    consumed_sources: set[str] = set()    # source stems any transform reads
    for p in tf_files:
        doc = _load(p)
        prod = doc.get("produces") if isinstance(doc.get("produces"), dict) else {}
        rel = str(prod.get("relation") or "").strip()
        if rel:
            produced_qual.setdefault(rel, p.stem)
            produced_leaf.setdefault(_leaf(rel), p.stem)
        for inp in (doc.get("inputs") or []):
            if not isinstance(inp, dict):
                continue
            desc = str(inp.get("descriptor") or "").strip()
            if desc.endswith(".yaml") and "/sources/" in desc:
                consumed_sources.add(Path(desc).stem)
            irel = str(inp.get("relation") or "").strip()
            if irel and _leaf(irel) in raw_leaf:
                consumed_sources.add(raw_leaf[_leaf(irel)])

    # rglob: a concepts plane may be flat (<dataset>) or foldered by domain (the gold: concepts/brand/brand.yaml)
    concept_files = sorted(concepts_dir.rglob("*.yaml")) if concepts_dir.is_dir() else []

    errors: list[str] = []
    warnings: list[str] = []

    # ---- A + B : the ontology binds served datasets, never raw -----------------------------------
    # Aggregate per RELATION (not per concept) so one bad relation is one finding, however many
    # concepts ground on it.
    dangling: dict[str, list[str]] = {}
    binds_raw: dict[str, list[str]] = {}
    ambiguous: dict[str, list[str]] = {}
    on_lookup: dict[str, list[str]] = {}
    n_relations = 0
    for p in concept_files:
        doc = _load(p)
        for rel in _grounding_relations(doc):
            n_relations += 1
            if _is_lookup(rel):
                on_lookup.setdefault(rel, []).append(p.stem)
                continue
            served = rel in ds_qual or _leaf(rel) in ds_leaf
            raw = rel in raw_qual or _leaf(rel) in raw_leaf
            if served and raw:
                ambiguous.setdefault(rel, []).append(p.stem)
            elif raw:
                binds_raw.setdefault(rel, []).append(p.stem)
            elif not served:
                dangling.setdefault(rel, []).append(p.stem)

    def _who(stems: list[str]) -> str:
        s = sorted(set(stems))
        head = ", ".join(s[:4]) + (f", +{len(s) - 4} more" if len(s) > 4 else "")
        return f"{len(s)} concept(s): {head}"

    for rel, who in sorted(binds_raw.items()):
        errors.append(f"grounding relation '{rel}' names a RAW source (data/sources/{raw_leaf.get(_leaf(rel), '?')}"
                      f".yaml) and no served dataset — the ontology must never bind raw; bind the dataset "
                      f"produced from it [{_who(who)}]")
    for rel, who in sorted(ambiguous.items()):
        errors.append(f"grounding relation '{rel}' is BOTH a served dataset (data/datasets/"
                      f"{ds_qual.get(rel) or ds_leaf.get(_leaf(rel))}.yaml) and a raw source "
                      f"(data/sources/{raw_qual.get(rel) or raw_leaf.get(_leaf(rel))}.yaml) — the binding is "
                      f"ambiguous: nothing on disk proves the concept reads the CURATED relation. Give the "
                      f"served view a distinct clean name (see check_served_name_distinct.py) [{_who(who)}]")
    for rel, who in sorted(dangling.items()):
        errors.append(f"grounding relation '{rel}' resolves to no served dataset "
                      f"(dangling binding — nothing in {_rel(ds_dir, root)}/ declares it) [{_who(who)}]")
    for rel, who in sorted(on_lookup.items()):
        target = root / rel
        note = "" if target.is_file() else " — and the file does not exist"
        warnings.append(f"grounding relation '{rel}' is an authored lookup register, not a transformed "
                        f"dataset — reference data is allowed but carries no lineage{note} [{_who(who)}]")

    # ---- C : every served dataset is produced by a transformation ---------------------------------
    for p in ds_files:
        doc = _load(p)
        tbl = doc.get("table") if isinstance(doc.get("table"), dict) else {}
        name = str(tbl.get("name") or p.stem).strip()
        schema = str(tbl.get("schema") or "").strip()
        qual = f"{schema}.{name}" if schema else name
        if (tf_dir / f"{p.stem}.yaml").is_file():
            continue
        if qual in produced_qual or name in produced_leaf or p.stem in produced_leaf:
            continue
        errors.append(f"served dataset '{p.stem}' ({qual}) is produced by no transformation — add "
                      f"data/transforms/{p.stem}.yaml; even a 1:1 passthrough must be declared")

    # ---- D : every transformation produces a declared dataset ------------------------------------
    for p in tf_files:
        doc = _load(p)
        prod = doc.get("produces") if isinstance(doc.get("produces"), dict) else {}
        rel = str(prod.get("relation") or "").strip()
        if not rel:
            errors.append(f"transform '{p.stem}' declares no produces.relation — it builds nothing nameable")
            continue
        if rel in ds_qual or _leaf(rel) in ds_leaf:
            continue
        errors.append(f"transform '{p.stem}' produces '{rel}' — no dataset descriptor declares that "
                      f"relation (add data/datasets/{_leaf(rel)}.yaml)")

    # ---- E : orphan raw landings -----------------------------------------------------------------
    for p in src_files:
        if p.stem not in consumed_sources:
            warnings.append(f"raw source '{p.stem}' is consumed by no transformation (orphan landing — "
                            f"harvested but never curated)")

    print(f"── ontology-grounds-on-datasets gate ── chain: {len(src_files)} source(s) → {len(tf_files)} "
          f"transform(s) → {len(ds_files)} dataset(s) → {len(concept_files)} concept(s) "
          f"({n_relations} grounding relation(s)) under {root} ──\n")
    for w in warnings:
        print(f"  [WARN]  {w}")
    for e in errors:
        print(f"  [ERROR] {e}")
    print()
    if errors:
        print(f"✗ {len(errors)} broken link(s) in the raw → transform → dataset → ontology chain "
              f"({len(warnings)} warning(s))")
        return 1
    print("✓ OK — every concept binds a served dataset, every dataset is produced by a transformation"
          + (f" ({len(warnings)} warning(s))" if warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
