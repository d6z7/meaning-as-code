#!/usr/bin/env python3
"""
mac_project.py — resolve a MAC project's layout (flat, or the two-plane data/ontology split).

A MAC project either is FLAT (today's default — concepts/ tables/ edges.yaml rules.yaml at the root) or
declares a TWO-PLANE layout in `mac.project.yaml` (data plane + ontology plane, see reference_manual/data_plane.md).
This one resolver is the single place that knows the difference, so every gate and projector asks it for two
roots instead of hardcoding `concepts/` / `tables/`:

    from mac_project import resolve
    L = resolve(root)
    L.ontology     # dir holding concepts/, edges.yaml, rules.yaml   (flat: root; two-plane: root/ontology)
    L.descriptors  # dir holding TableFile descriptors                (flat: root/tables; two-plane: root/data/datasets)
    L.transforms   # dir holding TransformFile descriptors            (None unless declared: two-plane data/transforms)
    L.sources      # dir holding raw-input TableFile descriptors      (None unless declared: two-plane data/sources)
    L.planes       # {} when flat; {"data": "...", "ontology": "..."} when two-plane

The model already binds a concept to its descriptor by RELATION NAME, not by path, so nothing in the YAML
changes between layouts — only where the tools look.
"""
from pathlib import Path
from types import SimpleNamespace

try:
    import yaml
except ImportError:                      # resolver must not hard-depend on yaml for the flat default
    yaml = None

MANIFEST = "mac.project.yaml"


def resolve(root):
    """Return a layout for `root`. No manifest ⇒ flat (back-compatible)."""
    root = Path(root)
    mf = root / MANIFEST
    if mf.exists() and yaml is not None:
        m = yaml.safe_load(mf.read_text()) or {}
        planes = m.get("planes") or {}
        onto = root / (planes.get("ontology") or ".")
        desc = root / (m.get("descriptors") or "tables")
        # data-plane descriptor dirs — present only when declared (transforms + raw sources)
        tfm = (root / m["transforms"]).resolve() if m.get("transforms") else None
        srcs = (root / m["sources"]).resolve() if m.get("sources") else None
        return SimpleNamespace(root=root, ontology=onto.resolve(), descriptors=desc.resolve(),
                               transforms=tfm, sources=srcs, planes=planes, two_plane=bool(planes))
    return SimpleNamespace(root=root.resolve(), ontology=root.resolve(), descriptors=(root / "tables").resolve(),
                           transforms=None, sources=None, planes={}, two_plane=False)


def field_meaning(concept_doc):
    """Option B: a column's MEANING lives in the ontology, bound to the column via the concept's
    field-anchored contract.rules (not in the data-plane descriptor). Return {column -> directive text}
    for one concept, drawn from each rule's `then` (fallback `why`), keyed by the columns it `binds`."""
    c = concept_doc.get("contract") if isinstance(concept_doc, dict) else None
    rules = c.get("rules") if isinstance(c, dict) else None
    out = {}
    for r in (rules or []):
        if not isinstance(r, dict):
            continue
        txt = " ".join(str(r.get("then") or r.get("why") or "").split())
        if not txt:
            continue
        for col in (r.get("binds") or []):
            out.setdefault(col, []).append(txt)
    return {col: " ".join(txts) for col, txts in out.items()}


def meaning_by_table(concept_docs, ground_table_fn):
    """Aggregate field_meaning across ALL concepts, keyed by (table, column) — so a column's meaning is
    found wherever the column is emitted, even when the rule lives on a different concept grounding the
    same table (e.g. Revenue's rule on orders.gross_amount surfaces under the Order node)."""
    out = {}
    for d in concept_docs:
        tbl = ground_table_fn(d)
        if not tbl:
            continue
        for col, txt in field_meaning(d).items():
            out.setdefault((tbl, col), []).append(txt)
    return {k: " ".join(v) for k, v in out.items()}


def plane_prefixes(root):
    """The plane directory names to treat as transparent when deriving a single-source key
    (e.g. ['ontology', 'data'] so ontology/concepts/… and data/datasets/… share source '')."""
    L = resolve(root)
    return [str(v).strip("/").split("/")[0] for v in L.planes.values()] if L.two_plane else []
