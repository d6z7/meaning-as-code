#!/usr/bin/env python3
"""check_concepts_not_per_table.py — A CONCEPT IS A BUSINESS NOTION, NOT A TABLE.

THE OPERATOR, 2026-09-26: "datasets DO NEVER MATCH CONCEPTS 1:1 — concepts must SEARCH for business
LOGIC in data and create it independent of physical layer objects."

WHY A GATE AND NOT A PROMPT LINE. The prompt already says it ("A CONCEPT IS A BUSINESS NOTION, NOT A
TABLE. The mapping between concepts and relations is M:N"), and a bundle came out at exactly 20
concepts over 20 datasets anyway — because the DRIVER called the model once per dataset and named
each file after the dataset stem. Three independent enforcements of the same wrong shape, one of
which was a sentence asking for the opposite. A shape that can be produced by a loop has to be
refused by a check, not requested by a paragraph.

AND THE OLD "FIX" WAS WORSE. The pipeline stopped authoring concepts at all, citing that 20-from-20
count as its reason. That left the per-table driver unfixed and moved the cost to the operator, who
then had to ask for concepts — so the instruction was deleted 2026-09-26 and this gate replaces it.
Refusing the wrong SHAPE is what the count was evidence for; refusing the whole STAGE was not.

WHAT A PER-TABLE MIRROR LOOKS LIKE, and each clause is measurable:
  1. as many concepts as datasets, AND
  2. every concept grounded on exactly one relation, AND
  3. no relation backing two concepts, AND
  4. no relation backing none.

All four together is a schema mirror wearing an ontology's file layout. Any ONE of them absent means
a judgement was made somewhere, and this gate says so rather than insisting on a ratio.

WHAT IT NEVER DOES. It does not demand fewer concepts, or more, or a particular number. A source
whose notions genuinely align with its relations is legitimate — what is not legitimate is
ARRIVING there without having looked. So the four clauses are about the SHAPE of the mapping, and
the report prints the M:N evidence either way: notions spanning several relations, relations serving
several notions, and relations declined.

Exit 0 when the mapping shows a judgement, 1 on a per-table mirror, 2 when the bundle cannot be read.
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _neighbours  # noqa: E402  — ONE home for the sibling runtime's location


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.bundle).resolve()
    if not (root / "ontology" / "concepts").is_dir():
        print(f"SKIP: {root.name} has no ontology/concepts/ yet")
        return 0
    try:
        _neighbours.ensure_runtime_on_path()
        from mac_runtime.ontology import OntologyIndex
    except ImportError as exc:
        print(f"REFUSED: cannot import what this gate needs ({exc})")
        return 2
    try:
        index = OntologyIndex.from_directory(str(root))
    except Exception as exc:  # noqa: BLE001 - an unreadable bundle is REFUSED, never passed
        print(f"REFUSED: {type(exc).__name__}: {str(exc)[:160]}")
        return 2

    datasets = sorted(p.stem for p in (root / "data" / "datasets").glob("*.yaml"))
    concepts = sorted(index.concepts)
    if not datasets:
        print("SKIP: no data/datasets/*.yaml to compare against")
        return 0

    # ---- the mapping, both ways -------------------------------------------------------------
    per_concept: dict[str, set[str]] = {}
    per_relation: dict[str, set[str]] = collections.defaultdict(set)
    for name, c in index.concepts.items():
        rels = {s for s in ([c.grounding.table] if c.grounding.table else [])}
        per_concept[name] = rels
        for r in rels:
            per_relation[r].add(name)

    spanning = {n: r for n, r in per_concept.items() if len(r) > 1}
    shared = {r: c for r, c in per_relation.items() if len(c) > 1}
    declined = [d for d in datasets if d not in per_relation]
    single = [n for n, r in per_concept.items() if len(r) == 1]

    print(f"CONCEPT:RELATION MAPPING — {root.name}")
    print(f"  {len(concepts)} concept(s) over {len(datasets)} dataset(s)\n")
    print(f"  notions spanning SEVERAL relations : {len(spanning)}"
          + (f"  ({', '.join(sorted(spanning)[:4])})" if spanning else ""))
    print(f"  relations backing SEVERAL notions  : {len(shared)}"
          + (f"  ({', '.join(sorted(shared)[:4])})" if shared else ""))
    print(f"  relations backing NO notion        : {len(declined)}"
          + (f"  ({', '.join(declined[:6])})" if declined else ""))

    mirror = (
        len(concepts) == len(datasets)
        and len(single) == len(concepts)
        and not shared
        and not declined
    )
    if not mirror:
        print("\nOK — the mapping is M:N: a judgement was made about what the notions are.")
        return 0

    print(
        "\nA PER-TABLE MIRROR, NOT AN ONTOLOGY:\n"
        f"  {len(concepts)} concepts, {len(datasets)} datasets, every concept on exactly one\n"
        "  relation, no relation shared, no relation declined. All four at once is the shape a\n"
        "  per-dataset authoring loop produces, and it cannot express what an ontology is for:\n"
        "  a notion spanning two relations, a relation serving two notions, or a bridge table\n"
        "  that is no notion at all.\n"
        "\n  The operator's rule: datasets DO NEVER MATCH CONCEPTS 1:1 — concepts must SEARCH for\n"
        "  business logic in the data, independent of the physical layer.\n"
        "\n  Author over the WHOLE inventory in one pass (sdk/authoring PLAN pass), not per table."
    )
    return 1


def _self_test() -> int:
    """All four clauses together is a mirror; any one absent is a judgement."""
    # (n_concepts, n_datasets, all_single, shared, declined) -> is a mirror
    cases = [
        ("20 concepts / 20 datasets, all 1:1, none shared or declined -> MIRROR",
         20, 20, True, False, False, True),
        ("one notion spans two relations                              -> judgement",
         20, 20, False, False, False, False),
        ("one relation backs two notions                              -> judgement",
         20, 20, True, True, False, False),
        ("a bridge table backs no notion                              -> judgement",
         19, 20, True, False, True, False),
        ("fewer concepts than datasets, nothing declined              -> judgement",
         13, 20, True, False, False, False),
    ]
    bad = 0
    for label, nc, nd, all_single, shared, declined, want in cases:
        got = nc == nd and all_single and not shared and not declined
        if got != want:
            bad += 1
            print(f"  FAIL  {label}")
    n = len(cases)
    print(f"\n{'FAIL' if bad else 'OK'} — self-test: {n - bad} of {n} seeded cases behaved")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
