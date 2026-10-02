#!/usr/bin/env python3
"""check_question_shape_reachable.py — A MEASURED JOIN WITH NO DECLARED EDGE IS AN ANSWER NOBODY CAN REACH.

THE GAP THIS CLOSES, measured on contoso5 2026-10-01. The `Sale` concept was deleted and its nine
edges were triaged by TARGET: seven looked like duplicates because some other concept already reached
Customer, Store, Product, Currency and the calendar. `Order`, which inherited Sale's role as the
event, was left reaching five of the six dimensions — Product was simply absent. `mac_compile`
reported COMPILES with zero errors, twenty-four of twenty-four checkers passed, and
`check_er_projection` said "all 39 declared edges are realized and grounded", which asserts nothing
about an edge that is ABSENT. The hole surfaced fifty-three minutes into a model run, as two corpus
questions falling from proven to failed, and a person spotted the missing edge before any gate did.

THE TEST. The served plane's MEASURED references (`data/references_served/*.yaml`) are the physical
truth: which column of which relation actually resolves into which other. For every such reference,
every concept grounded on the parent relation must declare an edge to every concept grounded on the
child relation. Per CONCEPT, not per relation — that is the whole point. A relation-level test passes
as soon as ANY concept on the fact reaches the dimension, which is exactly how six measures covered
for `Order` and hid the hole.

WHY MEASURED AND NOT DECLARED. A declared edge list cannot audit itself; the reference measurement
comes from the warehouse through the connector and knows nothing about the ontology's opinions.

Usage:  python3 tools/check_question_shape_reachable.py <bundle-root>
        exit 0 = every measured join is declared between every concept pair it joins
             1 = at least one pair can be joined physically and cannot be traversed
             2 = the bundle cannot be read
        --self-test proves both verdicts against a synthetic bundle.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import yaml


def _concepts_by_relation(ontology: pathlib.Path) -> dict[str, list[str]]:
    """relation -> the concepts grounded on it."""
    out: dict[str, list[str]] = {}
    for path in sorted((ontology / "concepts").glob("*.yaml")):
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        name = ((doc.get("concept") or {}).get("name")) or path.stem
        for src in ((doc.get("grounding") or {}).get("sources") or []):
            rel = str((src or {}).get("relation") or "").strip()
            if rel:
                out.setdefault(rel, []).append(str(name))
    return out


def _adjacency(ontology: pathlib.Path) -> dict[str, set[str]]:
    """The UNDIRECTED concept graph the declared edges form. Direction is not the question: a join is
    traversable either way, and an edge declared one way is not a second hole."""
    try:
        doc = yaml.safe_load((ontology / "edges.yaml").read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    adj: dict[str, set[str]] = {}
    for edge in doc.get("edges") or []:
        ends = edge.get("endpoints") or {}
        a = ((ends.get("from") or {}).get("concept"))
        b = ((ends.get("to") or {}).get("concept"))
        if a and b:
            adj.setdefault(str(a), set()).add(str(b))
            adj.setdefault(str(b), set()).add(str(a))
    return adj


def _connected(adj: dict[str, set[str]], a: str, b: str) -> bool:
    """Is there a PATH, at any hop count? A DIRECT edge is not the test and demanding one is wrong:
    `GrossRevenue` reaches `Brand` through `Product`, which is a legitimate two-hop traversal, and the
    first cut of this gate reported 60-odd such pairs as holes. What makes a hole is a join the
    warehouse can perform that the ontology cannot traverse AT ALL."""
    if a == b:
        return True
    seen, queue = {a}, [a]
    while queue:
        node = queue.pop()
        for nxt in adj.get(node, ()):  # noqa: SIM118
            if nxt == b:
                return True
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return False


def _declared_pairs_unused(ontology: pathlib.Path) -> set[frozenset[str]]:
    """Retained only so the shape of the first cut is visible in history; `_connected` replaced it."""
    try:
        doc = yaml.safe_load((ontology / "edges.yaml").read_text(encoding="utf-8")) or {}
    except Exception:
        return set()
    pairs = set()
    for edge in doc.get("edges") or []:
        ends = edge.get("endpoints") or {}
        a = ((ends.get("from") or {}).get("concept"))
        b = ((ends.get("to") or {}).get("concept"))
        if a and b:
            pairs.add(frozenset((str(a), str(b))))
    return pairs


def _measured_joins(refs_dir: pathlib.Path) -> list[tuple[str, str, str]]:
    """(parent_relation, child_relation, reference_id) for every measured reference."""
    out = []
    for path in sorted(refs_dir.glob("*.yaml")):
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        for ref in doc.get("references") or []:
            frm = (ref or {}).get("from") or {}
            to = (ref or {}).get("to") or {}
            a, b = str(frm.get("relation") or ""), str(to.get("relation") or "")
            if a and b and a != b:
                out.append((a, b, str((ref or {}).get("id") or f"{a}->{b}")))
    return out


def findings(root: pathlib.Path) -> tuple[list[str], int]:
    ontology = root / "ontology"
    refs = root / "data" / "references_served"
    if not (ontology / "edges.yaml").is_file() or not refs.is_dir():
        return [], 0
    by_rel = _concepts_by_relation(ontology)
    adj = _adjacency(ontology)
    out, checked = [], 0
    seen: set[tuple[str, str, str]] = set()
    for parent, child, ref_id in _measured_joins(refs):
        for a in by_rel.get(parent, []):
            for b in by_rel.get(child, []):
                if a == b:
                    continue
                key = (a, b, ref_id)
                if key in seen:
                    continue
                seen.add(key)
                checked += 1
                if not _connected(adj, a, b):
                    out.append(
                        f"{a} cannot reach {b} by any declared edge path, yet the warehouse joins "
                        f"their relations ({ref_id}) — a question needing both refuses, and nothing "
                        f"else says so"
                    )
    return sorted(set(out)), checked


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    if not a.root:
        print("usage: check_question_shape_reachable.py <bundle-root>")
        return 2
    root = pathlib.Path(a.root).resolve()
    if not root.is_dir():
        print(f"root not found: {root}")
        return 2
    holes, checked = findings(root)
    print(f"── question-shape reachability ── {checked} concept pair(s) a measured join connects ──\n")
    if not checked:
        print("✓ OK — no measured served references in this bundle (nothing to reach across)")
        return 0
    for h in holes:
        print(f"  [ERROR] {h}")
    if holes:
        print(f"\n✗ {len(holes)} of {checked} joinable concept pair(s) have no declared edge")
        return 1
    print(f"✓ OK — all {checked} joinable concept pair(s) are declared")
    return 0


def _self_test() -> int:
    import tempfile

    def bundle(d: pathlib.Path, edges: list[dict]) -> pathlib.Path:
        (d / "ontology" / "concepts").mkdir(parents=True, exist_ok=True)
        (d / "data" / "references_served").mkdir(parents=True, exist_ok=True)
        for name, rel in (("Fact", "f_line"), ("Dim", "d_thing")):
            (d / "ontology" / "concepts" / f"{name.lower()}.yaml").write_text(
                yaml.safe_dump({"concept": {"name": name},
                                "grounding": {"sources": [{"relation": rel}]}}), encoding="utf-8")
        (d / "ontology" / "edges.yaml").write_text(yaml.safe_dump({"edges": edges}), encoding="utf-8")
        (d / "data" / "references_served" / "f_line.yaml").write_text(yaml.safe_dump(
            {"references": [{"id": "f_line.k__d_thing.k",
                             "from": {"relation": "f_line", "column": "k"},
                             "to": {"relation": "d_thing", "column": "k"}}]}), encoding="utf-8")
        return d

    fails = 0
    with tempfile.TemporaryDirectory() as tmp:
        a = bundle(pathlib.Path(tmp) / "missing", [])
        holes, checked = findings(a)
        ok = checked == 1 and len(holes) == 1
        print(("  ok    " if ok else "  FAIL  ") + "a measured join with NO edge is a hole")
        fails += 0 if ok else 1

        b = bundle(pathlib.Path(tmp) / "present", [
            {"edge_id": "fact__of__dim",
             "endpoints": {"from": {"concept": "Fact"}, "to": {"concept": "Dim"}}}])
        holes, checked = findings(b)
        ok = checked == 1 and not holes
        print(("  ok    " if ok else "  FAIL  ") + "the same join WITH an edge is clean")
        fails += 0 if ok else 1

        c = bundle(pathlib.Path(tmp) / "reversed", [
            {"edge_id": "dim__of__fact",
             "endpoints": {"from": {"concept": "Dim"}, "to": {"concept": "Fact"}}}])
        holes, checked = findings(c)
        ok = checked == 1 and not holes
        print(("  ok    " if ok else "  FAIL  ") + "an edge declared the other way round still counts")
        fails += 0 if ok else 1

    if fails:
        print(f"\nFAIL: check_question_shape_reachable self-test — {fails} of 3 case(s)")
        return 1
    print("\nPASS: check_question_shape_reachable self-test — 3/3 case(s): a measured join with no "
          "edge is a hole, with an edge is clean, and direction does not matter")
    return 0


if __name__ == "__main__":
    sys.exit(main())
