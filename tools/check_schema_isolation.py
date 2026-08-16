#!/usr/bin/env python3
"""
check_schema_isolation.py — the OWN-SCHEMA isolation gate (prevents the shared-schema collision).

Right-first-time harvest invariant #5 (docs/HARVEST_RIGHT_FIRST_TIME.md): a source's serving relations
live in the source's OWN dedicated schema, NEVER another source's schema. The incident this guards
against: fpl2's views were written into gold's shared `fpl` schema and overwrote gold's dim_country /
dim_model. The rule: every schema-qualified relation this source binds to must carry THIS bundle's own
`view_schema` (from connection.yaml) — a foreign schema prefix is a collision waiting to happen.

This gate is OFFLINE and pure-structural (no AWS): it compares declared schema PREFIXES against the
bundle's own declared view_schema. It does NOT connect to the warehouse (the live SHOW TABLES
collision-check is the harvest's materialize step, NOT a gate).

Own view_schema is read from the first present of:
  connection.yaml · connection.local.yaml · deployment.local.yaml · deployment.yaml ·
  deployment.example.yaml · connection.example.yaml   (key `view_schema`, fallback `view_database`)
If none declares one, the gate SKIPS (exit 0, note) — it cannot judge isolation without an own-schema.

Checks (RED on any foreign schema):
  A. every concept  grounding.sources[].relation  whose schema prefix != own view_schema
  B. every  data/datasets/<x>.yaml  table.schema  != own view_schema  (the collision point itself)
A bare (unqualified) relation carries no foreign-schema risk and passes.

Usage:  python3 tools/check_schema_isolation.py <bundle-root>
        exit 0 = all groundings/descriptors target the own schema ; exit 1 = a foreign schema found.

Wire into cap-ontology-workbench/tools/check_all.sh (guarded on the two-plane data layout):
    if [ -d "$SOURCE_ROOT/data/datasets" ]; then
      echo "▶ schema-isolation (check_schema_isolation.py $SOURCE_ROOT)"
      "$PY" "$FW/tools/check_schema_isolation.py" "$SOURCE_ROOT" || rc=1
    fi
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mac_project import resolve  # noqa: E402

CONN_CANDIDATES = [
    "connection.yaml", "connection.local.yaml",
    "deployment.local.yaml", "deployment.yaml",
    "deployment.example.yaml", "connection.example.yaml",
]


def load(p: Path):
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return e


def own_view_schema(root: Path):
    """(schema, source_file) for the bundle's own view_schema, or (None, None) if none declared."""
    for name in CONN_CANDIDATES:
        p = root / name
        if not p.is_file():
            continue
        doc = load(p)
        if not isinstance(doc, dict):
            continue
        vs = doc.get("view_schema") or doc.get("view_database")
        if isinstance(vs, str) and vs.strip():
            return vs.strip(), name
    return None, None


def schema_prefix(relation: str):
    """The leftmost qualifier of a `schema.relation` (or `catalog.schema.relation`) reference.
    None when the relation is bare (unqualified) — no foreign-schema risk."""
    r = str(relation)
    return r.split(".")[0] if "." in r else None


def grounding_relations(doc: dict):
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Own-schema isolation gate")
    ap.add_argument("root", help="bundle root (a MAC source container)")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"root not found: {root}", file=sys.stderr)
        return 2

    L = resolve(root)
    own, src_file = own_view_schema(root)
    if not own:
        print(f"── schema-isolation ── {root} ──\n  no view_schema declared "
              f"({'/'.join(CONN_CANDIDATES[:3])}…) — cannot judge isolation (skip)")
        return 0

    findings: list[str] = []

    # A. concept groundings
    concepts_dir = Path(L.ontology) / "concepts"
    if concepts_dir.is_dir():
        for p in sorted(concepts_dir.rglob("*.yaml")):
            doc = load(p)
            if isinstance(doc, Exception) or not isinstance(doc, dict):
                continue
            rel = p.relative_to(root)
            for r in grounding_relations(doc):
                pfx = schema_prefix(r)
                if pfx is not None and pfx != own:
                    findings.append(
                        f"{rel} grounding : relation '{r}' targets schema '{pfx}', "
                        f"not this source's own view_schema '{own}' — foreign-schema collision risk")

    # B. dataset descriptors — the point where a shared-schema write actually collides
    ds_dir = L.descriptors
    if ds_dir and Path(ds_dir).is_dir():
        for p in sorted(Path(ds_dir).glob("*.yaml")):
            doc = load(p)
            if isinstance(doc, Exception) or not isinstance(doc, dict):
                continue
            tbl = doc.get("table")
            sch = tbl.get("schema") if isinstance(tbl, dict) else None
            if isinstance(sch, str) and sch.strip() and sch.strip() != own:
                findings.append(
                    f"data/datasets/{p.name} : table.schema '{sch}' != own view_schema '{own}' "
                    f"— a served relation must live in the source's OWN schema")

    print(f"── schema-isolation gate ── own view_schema '{own}' (from {src_file}) ── {root} ──")
    for f in findings:
        print(f"  [ERROR] {f}")
    if findings:
        print(f"\n✗ {len(findings)} foreign-schema reference(s) — isolate this source to schema '{own}'")
        return 1
    print(f"\n✓ OK — every grounding/descriptor targets the own schema '{own}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
