#!/usr/bin/env python3
"""mac_edges.py — REBUILD ontology/edges.yaml FROM WHAT IS ON DISK. No model, no cache, no billing.

WHY THIS EXISTS. `physical_edges` had only one caller — the harvest pipeline — so the only way to
regenerate edges was to re-run concept authoring, which reads completions out of
`.harvest_cache/<sha256>.txt` keyed on the prompt. That is backlog item 1's complaint exactly: a
bundle whose concepts are already authored and correct on disk could not have its edges rebuilt
without re-entering the authoring path. Fixing the endpoint resolver was therefore un-testable on a
real bundle until this existed.

IT READS THREE THINGS AND WRITES ONE:
    ontology/concepts/*.yaml       the concepts, for endpoint resolution by COLUMN
    data/references*/*.yaml        the measured foreign keys (columns[].references)
    data/sources, data/datasets    the descriptors, for column roles
  -> ontology/edges.yaml           physical foreign_key edges between concepts

THE DEFECT IT WAS BUILT TO REPAIR, measured on contoso4 2026-09-27: all THREE delivered edges
carried the endpoints `Currency -> Region`, `Currency -> Region`, `Currency -> ProductColor`, with
join_rules that were correct. A relation backs many concepts — four ground on the sales relation —
and the old resolver kept one per relation, last write winning. The checker's FK-EDGE invariant
passed anyway, because it matched the edge_id string and never read the endpoints.

A SKIPPED EDGE IS PRINTED WITH ITS REASON and never dropped in silence; --strict makes any skip a
failure, for a bundle that claims every measured FK is modelled.
"""

from __future__ import annotations

import argparse
import glob
import pathlib
import sys
import mac_project as P

# The REPO ROOT, not sdk/: sdk.authoring.edges imports itself as `sdk.authoring.authoring`.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

ACCEPTED_SHAPE = """\
ACCEPTED SHAPE — a bundle root holding:
  ontology/concepts/*.yaml      at least one authored concept
  data/sources/*.yaml           descriptors carrying columns[].references
usage: mac_edges.py [bundle] [--strict] [--dry-run]
"""


def _load_all(pattern: str, yaml) -> list:
    out = []
    for f in sorted(glob.glob(pattern, recursive=True)):
        try:
            d = yaml.safe_load(pathlib.Path(f).read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if isinstance(d, dict):
            out.append(d)
    return out


def datasets_info(root: pathlib.Path, yaml) -> list:
    """The measured FK set, in the shape `physical_edges` reads, taken from the DESCRIPTORS.

    `columns[].references` is the ONE HOME the operator ruled for a foreign key on 2026-09-27
    ("i think columns block is better"), so this reads that and nothing else — no `foreign_keys:`
    block, which 0 of 8 descriptors were ever measured to carry.
    """
    out = []
    for d in _load_all(str(root / "data" / "*" / "*.yaml"), yaml):
        tbl = (d.get("table") or {})
        stem = str(tbl.get("name") or (d.get("metadata") or {}).get("table") or "").strip()
        if not stem:
            continue
        cols = d.get("columns")
        if not isinstance(cols, list):
            continue
        fks, roles = [], {}
        for c in cols:
            if not isinstance(c, dict):
                continue
            name = str(c.get("name") or "")
            roles[name] = str(c.get("role") or "")
            ref = c.get("references")
            if not ref:
                continue
            # THE SHAPE GREW AND THIS READER GOES THROUGH THE RESOLVER. `references` may be a bare
            # target string or a mapping carrying `to` + cardinality + participation; `column_reference`
            # normalises both, and takes the relation from the SECOND-TO-LAST segment so a schema-
            # qualified `main.customer.CustomerKey` no longer yields the table `main`.
            _r = P.column_reference(c)
            if not _r:
                continue
            to_tab, to_col = _r["relation"], (_r["column"] or name)
            fks.append({"from_column": name, "to_table": to_tab, "to_column": to_col})
        if fks:
            out.append({"relation_bare": stem, "produces_relation": stem,
                        "foreign_keys": fks, "roles": roles})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--strict", action="store_true", help="fail if any measured FK yields no edge")
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    try:
        import yaml
        from sdk.authoring import edges, operations
    except ImportError as exc:
        print(f"COULD NOT RUN: {exc}\n\n{ACCEPTED_SHAPE}")
        return 2
    root = pathlib.Path(a.bundle).resolve()
    concepts = _load_all(str(root / "ontology" / "concepts" / "**" / "*.yaml"), yaml)
    if not concepts:
        print(f"COULD NOT RUN: {root.name} has no ontology/concepts/*.yaml, so an edge between "
              f"concepts cannot be resolved. This is not a pass.\n\n{ACCEPTED_SHAPE}")
        return 2
    idx = edges.concept_index(concepts)
    di = datasets_info(root, yaml)
    measured = sum(len(x["foreign_keys"]) for x in di)
    built, skipped = edges.physical_edges(di, idx)
    print(f"  EDGES — {root.name}\n"
          f"  {len(concepts)} concept(s) over {len(idx)} relation(s); {measured} measured foreign key(s)\n")
    for e in built:
        ep = e["endpoints"]
        print(f"  [ok  ] {ep['from']['concept']} -> {ep['to']['concept']:22} {e['edge_id']}")
    for sk in skipped:
        print(f"  [--  ] {'(no edge)':<28} {sk['edge_id']}\n           {sk['why']}")
    source = str((_load_all(str(root / "mac.project.yaml"), yaml) or [{}])[0]
                 .get("identity", {}).get("label") or root.name.upper())
    ef = edges.make_edges_file(built, source=source)
    if a.dry_run:
        print(f"\nDRY RUN: {ef['edges']} edge(s) would be written, {len(skipped)} skipped")
        return 0
    pe = operations.persist_edges(root / "ontology", ef)
    if not pe.get("written"):
        print(f"\nFAIL: mac_edges — edges.yaml REFUSED: {pe.get('reason') or ef.get('errors')}")
        return 1
    if a.strict and skipped:
        print(f"\nFAIL: mac_edges — {ef['edges']} edge(s) written and {len(skipped)} measured foreign "
              f"key(s) yielded none; --strict treats an unmodelled reference as a defect")
        return 1
    tail = f"; {len(skipped)} measured FK(s) yielded no edge, each named above" if skipped else ""
    print(f"\nPASS: mac_edges — {ef['edges']} edge(s) of {measured} measured foreign key(s){tail}")
    return 0


def _self_test() -> int:
    """Endpoint resolution, which is the whole point: chosen by COLUMN, and refused when unclear.

    THE FIXTURE IS REWIRED 2026-10-07 for column_declaration.md rev 5, the SAME DAY it was last
    touched for the `roles: {identity: ...}` shape: `grounding.sources` (list) -> `grounding.source`
    (singular); the canonical key moves from a column flag to `source.key`; `identity: reference`
    moves from the column's use-map to the top-level `references: <ConceptName>` key. Every `refs=`
    column in this fixture resolves to "Customer" — every case here means it that way — so the
    target name is fixed rather than threaded through as another parameter nothing varies.
    """
    from sdk.authoring import edges
    C = lambda n, rel, canon=None, refs=(): {
        "concept": {"name": n},
        "grounding": {"source": {
            "relation": rel,
            **({"key": canon} if canon else {}),
            "columns": {
                **({canon: {"offers": {}}} if canon else {}),
                **{r: {"offers": {}, "references": "Customer"} for r in refs},
            }}}}
    di = [{"relation_bare": "sales", "produces_relation": "v_sales", "roles": {},
           "foreign_keys": [{"from_column": "CustomerKey", "to_table": "customer",
                             "to_column": "CustomerKey"}]}]
    cases = []
    def case(label, cond):
        cases.append((label, bool(cond)))

    # THE MEASURED DEFECT: four concepts on one relation. The old resolver kept the last and shipped
    # `Currency -> Region`; this must pick by the column and get OrderLine -> Customer.
    idx = edges.concept_index([
        C("OrderLine", "sales", refs=("CustomerKey",)), C("Order", "sales"),
        C("SalesAmount", "sales"), C("Currency", "sales"),
        C("Customer", "customer", canon="CustomerKey"), C("Region", "customer", canon="State"),
        C("Continent", "customer", canon="Continent")])
    built, skipped = edges.physical_edges(di, idx)
    ep = built[0]["endpoints"] if built else {}
    case("4 concepts on one relation still resolve to the RIGHT pair",
         len(built) == 1 and ep["from"]["concept"] == "OrderLine" and ep["to"]["concept"] == "Customer")
    case("nothing is skipped when both ends resolve", not skipped)

    # TWO concepts claiming one reference column: ambiguous, so REFUSE with a reason naming both.
    built, skipped = edges.physical_edges(di, edges.concept_index([
        C("OrderLine", "sales", refs=("CustomerKey",)), C("Order", "sales", refs=("CustomerKey",)),
        C("Customer", "customer", canon="CustomerKey")]))
    # TWO CONCEPTS CLAIMING ONE FK COLUMN IS FAN-OUT, NOT AMBIGUITY, and the first version of this fix
    # refused it. Both statements are true -- an order has a customer and so does an order line -- so
    # both are edges, and the ids must differ or one is silently deduped away.
    built, skipped = edges.physical_edges(di, edges.concept_index([
        C("OrderLine", "sales", refs=("CustomerKey",)), C("Order", "sales", refs=("CustomerKey",)),
        C("Customer", "customer", canon="CustomerKey")]))
    case("two concepts claiming one FK column yield TWO edges, not a refusal",
         len(built) == 2 and not skipped)
    case("each edge names its own concept in the id, so neither is deduped away",
         sorted(e["edge_id"] for e in built) == ["OrderLine__CustomerKey__to__Customer",
                                                "Order__CustomerKey__to__Customer"][::-1]
         or sorted(e["edge_id"] for e in built) == sorted(["OrderLine__CustomerKey__to__Customer",
                                                           "Order__CustomerKey__to__Customer"]))
    case("both edges point at the same target concept",
         {e["endpoints"]["to"]["concept"] for e in built} == {"Customer"})

    # No concept declares the column as a reference -> no edge, and the reason says so.
    built, skipped = edges.physical_edges(di, edges.concept_index([
        C("OrderLine", "sales"), C("Customer", "customer", canon="CustomerKey")]))
    case("an unclaimed FK column yields no edge and says why",
         not built and skipped and skipped[0]["kind"] == "unclaimed")

    # The target concept must own the TARGET COLUMN as its canonical key, not merely sit on the table.
    built, skipped = edges.physical_edges(di, edges.concept_index([
        C("OrderLine", "sales", refs=("CustomerKey",)), C("Region", "customer", canon="State")]))
    case("a target concept keyed on another column is not an endpoint",
         not built and skipped and "canonical key" in skipped[0]["why"])

    # TWO concepts claiming one CANONICAL KEY is a real defect: the key would identify two notions.
    built, skipped = edges.physical_edges(di, edges.concept_index([
        C("OrderLine", "sales", refs=("CustomerKey",)),
        C("Customer", "customer", canon="CustomerKey"), C("Buyer", "customer", canon="CustomerKey")]))
    case("two concepts claiming one canonical key NEEDS A RULING",
         not built and skipped and skipped[0]["kind"] == "needs_ruling"
         and "Buyer" in skipped[0]["why"] and "Customer" in skipped[0]["why"])

    # A relation no concept grounds on is STRUCTURAL, not work -- the raw plane, and ruled declines.
    built, skipped = edges.physical_edges(di, edges.concept_index([
        C("Customer", "customer", canon="CustomerKey")]))
    case("a relation backing no concept is marked structural",
         not built and skipped and skipped[0]["kind"] == "structural")

    # A dimension's back-reference on its own primary key is identity, not a reference.
    built, _ = edges.physical_edges(
        [{**di[0], "roles": {"CustomerKey": "primary_key"}}],
        edges.concept_index([C("OrderLine", "sales", refs=("CustomerKey",)),
                             C("Customer", "customer", canon="CustomerKey")]))
    case("a FK on the relation's own primary key emits nothing", not built)

    case("an empty index yields no edges and one reason per FK",
         edges.physical_edges(di, {})[0] == [] and len(edges.physical_edges(di, {})[1]) == 1)

    bad = [l for l, ok in cases if not ok]
    for l in bad:
        print(f"  FAIL  {l}")
    n = len(cases)
    if bad:
        print(f"\nFAIL: mac_edges self-test — {len(bad)} of {n} case(s) failed")
        return 1
    print(f"PASS: mac_edges self-test — {n}/{n} case(s): an endpoint is chosen by COLUMN and never by "
          f"iteration order, ambiguity and absence are both REFUSED with a reason that names the "
          f"claimants; a FK claimed by several concepts FANS OUT to one edge each with distinct ids; "
          f"a back-reference on a primary key emits nothing; and an empty index invents no edge")
    return 0


if __name__ == "__main__":
    sys.exit(main())
