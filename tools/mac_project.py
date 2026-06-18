#!/usr/bin/env python3
"""
mac_project.py — resolve a MAC project's layout (flat, or the two-plane data/ontology split).

A MAC project either is FLAT (today's default — concepts/ tables/ edges.yaml rules.yaml at the root) or
declares a TWO-PLANE layout in `mac.project.yaml` (data plane + ontology plane, see design/two-plane-layout.md).
This one resolver is the single place that knows the difference, so every gate and projector asks it for two
roots instead of hardcoding `concepts/` / `tables/`:

    from mac_project import resolve
    L = resolve(root)
    L.ontology     # dir holding concepts/, edges.yaml, rules.yaml   (flat: root; two-plane: root/ontology)
    L.descriptors  # dir holding TableFile descriptors                (flat: root/tables; two-plane: root/data/datasets)
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
        return SimpleNamespace(root=root, ontology=onto.resolve(), descriptors=desc.resolve(),
                               planes=planes, two_plane=bool(planes))
    return SimpleNamespace(root=root, ontology=root, descriptors=root / "tables",
                           planes={}, two_plane=False)


def plane_prefixes(root):
    """The plane directory names to treat as transparent when deriving a single-source key
    (e.g. ['ontology', 'data'] so ontology/concepts/… and data/datasets/… share source '')."""
    L = resolve(root)
    return [str(v).strip("/").split("/")[0] for v in L.planes.values()] if L.two_plane else []
