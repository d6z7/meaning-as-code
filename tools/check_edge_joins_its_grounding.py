#!/usr/bin/env python3
"""check_edge_joins_its_grounding — the join must sit on the relations the CONCEPTS actually bind.

TWO LAYERS, ONE EDGE. An edge's endpoints are CONCEPTS and its cardinality is a claim about MEANING:
"a delivery relates to exactly one market". Its `join_rule` is PHYSICAL: `a.x = b.y` between stored
relations. Those are different planes, and the only thing connecting them is GROUNDING — the concept
declares which served relation it binds, and the join must sit on THAT relation.

WHAT GOES WRONG WITHOUT THIS. Measuring a join proves a fact about two TABLES. It proves the
ONTOLOGY claim only if those tables are the ones the two concepts bind. If they are not, the
measurement is true, precise, and about something else — and it is recorded as the edge's evidence,
so the edge reads PROVED.

MEASURED THE DAY THIS WAS WRITTEN: nine of eighteen predicates joined a relation the target concept
does not ground on. Every one measured 100% containment with fanout 1, and every one was written
into `verified_by`. The proofs happened to carry, because the joined relation and the grounded
relation were 1:1 — 1076 rows, 1076 codes, 1076 shared on both sides. NOTHING DECLARED THAT AND
NOTHING CHECKED IT. A true number stood in for a claim it was never about, and would have gone on
standing if the relations had drifted apart.

WHAT IT REFUSES TO DO. It does not judge an edge with no `join_rule` — a relationship realised by a
column or a rule is not making a claim about two relations, and `check_edge_joins_measured` reports
those separately. It does not require the two relations to be IDENTICAL to the grounding when a
concept grounds on several; binding any one of them is enough. What it refuses is a predicate whose
relations the endpoint concepts do not bind at all, because then the measurement is unattached.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mac_diag as D  # noqa: E402

UNATTACHED = "join-not-on-grounded-relation"
NO_GROUNDING = "endpoint-concept-grounds-on-nothing"

PREDICATE = re.compile(r"^\s*([\w.]+)\.(\w+)\s*=\s*([\w.]+)\.(\w+)\s*$")


def judge(rows: list[dict]) -> list[tuple[str, str]]:
    """PURE: [{edge, side, concept, relation, grounds}] -> [(class, sentence)].

    One row per SIDE of a predicate, because the two sides fail independently and naming which one
    broke is the difference between a repair and a hunt.
    """
    out: list[tuple[str, str]] = []
    for r in rows:
        grounds = list(r.get("grounds") or [])
        edge, side, concept, rel = r["edge"], r["side"], r["concept"], r["relation"]
        if not grounds:
            out.append(
                (
                    NO_GROUNDING,
                    f"{edge}: its {side} concept {concept!r} grounds on no served relation, so a "
                    f"join to {rel!r} cannot be attached to it at all",
                )
            )
        elif rel not in grounds:
            out.append(
                (
                    UNATTACHED,
                    f"{edge}: the {side} of its predicate is {rel!r}, but {concept!r} grounds on "
                    f"{', '.join(grounds)}. Measuring that join proves a fact about {rel!r} — not "
                    f"about {concept!r} — and recording it as this edge's evidence attributes the "
                    f"proof to a claim it was never about.",
                )
            )
    return out


def _load(p: pathlib.Path):
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    if "--self-test" in sys.argv[1:]:
        return self_test()
    a = ap.parse_args()
    root = pathlib.Path(a.root).resolve()

    edges_file = root / "ontology" / "edges.yaml"
    objects_file = root / "objects.json"
    if not edges_file.exists():
        return D.refuse_empty("check_edge_joins_its_grounding", edges_file, unit="edge")
    if not objects_file.exists():
        return D.refuse_empty("check_edge_joins_its_grounding", objects_file, unit="object")
    edges = _load(edges_file).get("edges") or []
    try:
        objects = json.loads(objects_file.read_text(encoding="utf-8")).get("objects") or []
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: check_edge_joins_its_grounding — objects.json unreadable: {str(e)[:90]}")
        return 1

    # KEYED BY THE CONCEPT'S DECLARED NAME, which is what an endpoint names — not by its title and
    # not by its stem. Matching an endpoint against a display title is how this estate lost 411
    # evidence attributions in a single projection.
    by_name = {
        str(o.get("name")): [g.get("id") for g in (o.get("grounds") or [])]
        for o in objects
        if o.get("kind") == "concept" and o.get("name")
    }
    if not by_name:
        return D.refuse_empty("check_edge_joins_its_grounding", objects_file, unit="concept")

    rows, skipped = [], 0
    for e in edges:
        pred = e.get("join_rule")
        if not isinstance(pred, str) or not pred.strip():
            skipped += 1
            continue
        m = PREDICATE.match(pred)
        if not m:
            skipped += 1
            continue
        lr, _lc, rr, _rc = m.groups()
        ep = e.get("endpoints") or {}
        for side, rel in (("from", lr), ("to", rr)):
            concept = (ep.get(side) or {}).get("concept")
            rows.append(
                {
                    "edge": str(e.get("edge_id")),
                    "side": side,
                    "concept": str(concept),
                    "relation": rel,
                    "grounds": by_name.get(str(concept), []),
                }
            )

    if not rows:
        return D.refuse_empty("check_edge_joins_its_grounding", edges_file, unit="join predicate")

    findings = judge(rows)
    bad_edges = {m.split(":")[0] for _, m in findings}

    if a.json:
        print(json.dumps({"edges": len(edges), "sides_checked": len(rows),
                          "unattached_edges": sorted(bad_edges),
                          "findings": [{"class": k, "msg": m} for k, m in findings]}, indent=1))
        return 1 if findings else 0

    for k, m in findings:
        print(f"  [{k}] {m}")
    tail = (
        f"{len(rows)} predicate side(s) over {len(rows) // 2} join(s) checked against "
        f"{len(by_name)} grounded concept(s); {skipped} edge(s) declare no join predicate"
    )
    if findings:
        print(
            f"FAIL: check_edge_joins_its_grounding — {len(bad_edges)} edge(s) join a relation "
            f"their concept does not bind — {tail}"
        )
        return 1
    print(f"PASS: check_edge_joins_its_grounding — {tail}")
    return 0


def self_test() -> int:
    """One mutant per way a predicate can float free of the meaning it claims to prove."""
    def row(**kw):
        base = {"edge": "a__of_b", "side": "to", "concept": "B",
                "relation": "dim_b", "grounds": ["dim_b"]}
        base.update(kw)
        return base

    cases = [
        ("a join on the grounded relation is not a finding", [row()], 0),
        ("grounding on several relations, binding one of them, is fine",
         [row(grounds=["dim_b", "dim_b_other"])], 0),
        # THE MEASURED DEFECT: the join lands on a relation the concept does not bind.
        ("a join on a relation the concept does not bind",
         [row(relation="dim_elsewhere")], 1),
        ("a concept grounding on nothing cannot anchor a join", [row(grounds=[])], 1),
        ("both sides wrong reports both",
         [row(side="from", concept="A", relation="x"), row(relation="y")], 2),
        # NEGATIVE CONTROLS.
        ("an empty population is not a finding", [], 0),
        ("one side wrong reports exactly one",
         [row(), row(side="from", concept="A", relation="nope", grounds=["fact"])], 1),
    ]
    bad = 0
    for name, rows, want in cases:
        got = len(judge(rows))
        if got != want:
            bad += 1
            print(f"  [SELF-TEST FAIL] {name}: {got} finding(s), expected {want}")
    n = len(cases)
    print(
        f"{'PASS' if not bad else 'FAIL'}: check_edge_joins_its_grounding self-test — {n - bad}/{n} "
        f"case(s): 3 mutant(s) of the rule (a join off the grounding, a concept grounding on "
        f"nothing, both sides at once) and 4 negative control(s) (a correct join, a concept with "
        f"several groundings, an empty population, and one-of-two wrong)"
    )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
