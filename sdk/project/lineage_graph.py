#!/usr/bin/env python3
"""sdk.project.lineage_graph — ONE graph of the whole bundle: every raw source, every dataset, every
concept, and the dependencies between them. DETERMINISTIC + IDEMPOTENT (no LLM, no AWS).

WHY THIS EXISTS
---------------
The enforced chain is `raw source → transformation → dataset → ontology concept`. Until now it was only
ever shown ONE STRAND AT A TIME: a strip under the breadcrumb on a data page, and — from the ontology
end — one row per grounding on a concept's Chain tab. Both are honest and both hide the shape.

Two things only the whole graph can show:

  1. CONVERGENCE. A concept grounded in three relations was drawn as three parallel chains that happen
     to end at the same name — three "Market" cells, i.e. three Markets. The truth is ONE concept
     ASSEMBLED FROM three places, and which part comes from where is the interesting fact (Market takes
     its identity from the register and its membership from the bucket table). A DAG with the concept
     as a single sink states that; parallel strips actively contradict it.
  2. ORPHANS. A dataset that is served but bound by no concept, a concept grounded in nothing, a raw
     source feeding nothing. The chain gate counts these; nothing ever SHOWED them.

THE TRANSFORMATION IS NOT A NODE. transformation:dataset is strictly 1:1 (decisions/0003), so it folds
into the dataset — carried as `transform` ON the dataset node, not drawn as a separate hop. The
transform's `.why.md` is the AUTHORED CAUSE and must stay reachable, so the node carries the stem and
the UI links to it; folding the node must not hide the rationale.

Built from the ALREADY-BUILT objects list rather than re-reading YAML: the objects are the single
source of truth for the chain, so the graph cannot disagree with the pages it links to.
"""

from __future__ import annotations

NODE_KINDS = ("source", "lookup", "dataset", "concept")
_PREFIX = {"source": "src", "lookup": "lk", "dataset": "ds", "concept": "con"}


def build(objects: list) -> dict:
    by_kind: dict[str, list] = {k: [] for k in NODE_KINDS}
    for o in objects or []:
        if o.get("kind") in by_kind:
            by_kind[o["kind"]].append(o)

    nodes, edges = [], []
    {o["id"] for o in by_kind["source"]}

    for o in by_kind["source"]:
        nodes.append(
            {
                "id": f"src:{o['id']}",
                "ref": o["id"],
                "kind": "source",
                "title": o.get("title") or o["id"],
                "relation": o.get("relation"),
                "issues": len(o.get("quality") or []),
            }
        )

    for o in by_kind["lookup"]:
        nodes.append(
            {
                "id": f"lk:{o['id']}",
                "ref": o["id"],
                "kind": "lookup",
                "title": o.get("title") or o["id"],
                "relation": None,
                "issues": 0,
            }
        )

    for o in by_kind["dataset"]:
        nodes.append(
            {
                "id": f"ds:{o['id']}",
                "ref": o["id"],
                "kind": "dataset",
                "title": o.get("title") or o["id"],
                "relation": o.get("relation"),
                # the transformation, FOLDED IN (1:1) — the node carries it, the graph does not
                # draw it as a hop; the UI links to its why-doc from here.
                "transform": o.get("transform"),
                "issues": len(o.get("quality") or []),
            }
        )
        # EVERY input kind, not just raw sources: a transform also reads other DATASETS and the
        # ATTRIBUTED LOOKUPS (authored seeds) that carry how the values came to being. Drawing only
        # source->dataset made dim_country_register look sourceless when it in fact reads a dataset
        # plus six reasoned lookups.
        for inp in o.get("inputs") or [
            {"kind": "source", "ref": s} for s in (o.get("sources") or [])
        ]:
            pfx = _PREFIX.get(inp.get("kind"))
            if pfx:
                edges.append(
                    {
                        "from": f"{pfx}:{inp['ref']}",
                        "to": f"ds:{o['id']}",
                        "kind": {
                            "source": "feeds",
                            "dataset": "derives_from",
                            "lookup": "seeded_by",
                        }.get(inp["kind"], "feeds"),
                    }
                )

    {o["id"] for o in by_kind["concept"]}
    for o in by_kind["concept"]:
        nodes.append(
            {
                "id": f"con:{o['id']}",
                "ref": o["id"],
                "kind": "concept",
                "title": o.get("title") or o["id"],
                "class": o.get("class"),
                "rules": len(o.get("rules") or []),
            }
        )
        for g in o.get("grounds") or []:
            edges.append({"from": f"ds:{g['id']}", "to": f"con:{o['id']}", "kind": "grounds"})

    # A grounding may name a relation that is not a projected dataset (an external or not-yet-described
    # relation). Draw it rather than dropping the edge — honest > hidden — but mark it.
    known = {n["id"] for n in nodes}
    _kind_of = {v: k for k, v in _PREFIX.items()}
    for e in edges:
        if e["from"] not in known:
            pfx, ref = e["from"].split(":", 1)
            nodes.append(
                {
                    "id": e["from"],
                    "ref": ref,
                    "kind": _kind_of.get(pfx, "dataset"),
                    "title": ref,
                    "relation": None,
                    "transform": None,
                    "issues": 0,
                    "undescribed": True,
                }
            )
            known.add(e["from"])
    # a lookup that seeds nothing is not part of the chain — drop it rather than draw a floating node
    edges = [e for e in edges if e["from"] in known]
    used = {e["from"] for e in edges} | {e["to"] for e in edges}
    nodes = [n for n in nodes if n["kind"] != "lookup" or n["id"] in used]

    nodes.sort(key=lambda n: (NODE_KINDS.index(n["kind"]), n["id"]))
    edges.sort(key=lambda e: (e["from"], e["to"]))
    seen_e, uniq = set(), []
    for e in edges:
        k = (e["from"], e["to"])
        if k not in seen_e:
            seen_e.add(k)
            uniq.append(e)
    edges = uniq

    # ---- the shapes worth naming: what the chain gate counts but nothing ever showed ----
    has_out = {e["from"] for e in edges}
    has_in = {e["to"] for e in edges}
    orphans = {
        "sources_feeding_nothing": sorted(
            n["ref"] for n in nodes if n["kind"] == "source" and n["id"] not in has_out
        ),
        "datasets_bound_by_no_concept": sorted(
            n["ref"] for n in nodes if n["kind"] == "dataset" and n["id"] not in has_out
        ),
        "datasets_with_no_input": sorted(
            n["ref"] for n in nodes if n["kind"] == "dataset" and n["id"] not in has_in
        ),
        "concepts_grounded_in_nothing": sorted(
            n["ref"] for n in nodes if n["kind"] == "concept" and n["id"] not in has_in
        ),
    }
    counts = {k: sum(1 for n in nodes if n["kind"] == k) for k in NODE_KINDS}
    counts["edges"] = len(edges)
    # how many concepts converge from more than one dataset — the case the old per-strand view drew wrong
    fan = {}
    for e in edges:
        if e["to"].startswith("con:"):
            fan[e["to"]] = fan.get(e["to"], 0) + 1
    counts["concepts_multi_grounded"] = sum(1 for v in fan.values() if v > 1)

    return {"nodes": nodes, "edges": edges, "counts": counts, "orphans": orphans}
