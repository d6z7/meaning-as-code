#!/usr/bin/env python3
"""sdk.project.lineage_graph — THE ONE lineage artifact: `data/lineage/lineage.json`.

One graph of the whole bundle — every raw source, every value register, every dataset, every
concept, and the dependencies between them. DETERMINISTIC + IDEMPOTENT (no LLM, no AWS).

WHY THIS EXISTS
---------------
The enforced chain is `raw source → transformation → dataset → ontology concept`. Until this module
existed it was only ever shown ONE STRAND AT A TIME: a strip under the breadcrumb on a data page,
and — from the ontology end — one row per grounding on a concept's Chain tab. Both are honest and
both hide the shape.

Two things only the whole graph can show:

  1. CONVERGENCE. A concept grounded in three relations was drawn as three parallel chains that
     happen to end at the same name — three "Market" cells, i.e. three Markets. The truth is ONE
     concept ASSEMBLED FROM three places, and which part comes from where is the interesting fact.
     A DAG with the concept as a single sink states that; parallel strips actively contradict it.
  2. ORPHANS. A dataset served but bound by no concept, a concept grounded in nothing, a raw source
     feeding nothing, a register cut from nothing. The chain gate counts these; nothing ever SHOWED
     them.

ONE ARTIFACT, TWO PRODUCERS, DISJOINT OWNERSHIP
-----------------------------------------------
Operator, 2026-09-28: "why there are two lineage artfifacts? there should be only one --- SSOT",
then "its one too many !!!", then — twice more after a collapse that missed consumers — "btw. i
need to tell you that linenage is still not FIXED". Measured on contoso5 the same day, there were
THREE homes for the same graph, not two:

    objects.json#lineage_graph   124 199 B   written by this module
    lineage_graph.json             4 561 B   written by this module, read by NOTHING
    data/lineage/lineage.json     18 218 B   written by tools/mac_lineage.py

They disagreed on the node id scheme alone (`src:sales` vs `main.sales`), which is why nobody had
folded them: the same relation had two names.

The operator's earlier ruling on producers — "if they do different thing over same artifact - then
why not" — is the shape this file now enforces. There is ONE artifact. Two producers write it, and
each OWNS a disjoint slice; a producer REPLACES only what it owns and preserves the rest:

    tools/mac_lineage.py       MEASURES the warehouse: `information_schema.views.view_definition`
                               owns  nodes: source, dataset     edges: feeds, derives_from
                               owns  `columns` — the column-level origin, which no descriptor knows
    sdk/project/lineage_graph  READS the bundle's own descriptors (the objects list)
                               owns  nodes: lookup, concept      edges: cuts, seeded_by, grounds
                               owns  `issues` on every node, and `disagreements`

`counts` and `orphans` are DERIVED over the union by whichever producer wrote last, so they can
never describe half a graph.

THE DESCRIPTOR DOES NOT OUTVOTE THE MEASUREMENT. `dataset.inputs` is a CLAIM made by a transform
descriptor; `view_definition` is what the engine actually stored. Where a measurement exists the
measured edges are the drawn ones and the claim is COMPARED, never merged — a claim with no
measured counterpart lands in `disagreements.claimed_not_measured` where somebody can see it.
Merging them would have made a wrong descriptor indistinguishable from a right one.

THE TRANSFORMATION IS NOT A NODE. transformation:dataset is strictly 1:1 (decisions/0003), so it
folds into the dataset — carried as `transform` ON the dataset node, not drawn as a separate hop.
The transform's `.why.md` is the AUTHORED CAUSE and must stay reachable, so the node carries the
stem and the UI links to it; folding the node must not hide the rationale.
"""

from __future__ import annotations

import json
from pathlib import Path

#: Drawn in this order, left to right. A register sits between the source it was cut from and the
#: dataset it seeds, which is the order the chain actually runs in.
NODE_KINDS = ("source", "lookup", "dataset", "concept")
_PREFIX = {"source": "src", "lookup": "lk", "dataset": "ds", "concept": "con"}

#: THE ONE ARTIFACT. Not `lineage_graph.json`, not `objects.json#lineage_graph` — both of those
#: were homes for this same fact and both are retired (see the module docstring).
ARTIFACT = Path("data") / "lineage" / "lineage.json"

#: The SHAPE this module reads and writes. A document at any other shape is DISCARDED rather than
#: merged into: the retired one keyed its nodes by relation (`main.sales`, kind `view`/`table`)
#: while this one keys them by bundle id (`src:sales`, kind `source`/`dataset`), so an ownership
#: merge across the two would strip nothing and leave every stale node in place for ever. Both
#: producers rewrite their own half, and a half that has not re-run is VISIBLE — `measured: false`,
#: or a concept count of zero — which is the honest state, not a silent blend of two schemas.
SHAPE = 2

#: The ownership table the whole SSOT rests on. A producer replaces exactly these and nothing else.
#: Stated as data rather than as code branches so a checker can read it and so a third producer
#: cannot be added without declaring what it takes from the other two.
OWNERSHIP: dict[str, dict[str, tuple[str, ...]]] = {
    "mac_lineage.py": {
        "nodes": ("source", "dataset"),
        "edges": ("feeds", "derives_from"),
        "keys": ("columns", "schema", "observed"),
    },
    "sdk.project.lineage_graph": {
        "nodes": ("lookup", "concept"),
        "edges": ("cuts", "seeded_by", "grounds", "claims"),
        "keys": ("disagreements",),
    },
}

#: Which edge kind an input of each kind makes. `cuts` runs the other way round from the rest —
#: a register is cut FROM a source — and is therefore built where the lookup is, not here.
_INPUT_EDGE = {"source": "feeds", "dataset": "derives_from", "lookup": "seeded_by"}


# --------------------------------------------------------------------------------------------
# the artifact itself: read, write, and the merge that keeps one home
# --------------------------------------------------------------------------------------------
def load(root) -> dict:
    """The artifact as it stands, or an empty one. Never raises on a missing or corrupt file —
    a producer that cannot read the other half must still be able to write its own."""
    p = Path(root) / ARTIFACT
    if not p.is_file():
        return empty()
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — a half-written file is not a reason to lose a measurement
        return empty()
    if not isinstance(doc, dict) or doc.get("shape") != SHAPE:
        return empty()
    return doc


def empty() -> dict:
    return {"shape": SHAPE, "generated_by": [], "nodes": [], "edges": [], "columns": [],
            "counts": {}, "orphans": {}, "disagreements": {}}


def save(root, doc: dict) -> Path:
    p = Path(root) / ARTIFACT
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def merge(doc: dict, producer: str, nodes: list, edges: list, fallback_nodes=(), **keys) -> dict:
    """Fold one producer's contribution into the artifact, REPLACING only what it owns.

    This is the single mechanism that makes two producers safe over one file. It is deliberately
    not "update the dict": a producer that re-runs must be able to REMOVE a node it no longer
    measures, and a dict update leaves the stale one behind for ever.
    """
    own = OWNERSHIP.get(producer)
    if own is None:
        raise ValueError(
            f"{producer!r} is not in OWNERSHIP. A third producer of this artifact is the defect "
            f"this table exists to prevent; declare what it owns, or write through one of "
            f"{sorted(OWNERSHIP)}."
        )
    doc = dict(doc or empty())
    doc["shape"] = SHAPE
    kept = [n for n in (doc.get("nodes") or []) if n.get("kind") not in own["nodes"]]
    doc["nodes"] = kept + list(nodes)
    # THE FALLBACK CHANNEL — nodes for kinds this producer does NOT own, inserted only where the
    # owner supplied none. It exists for exactly one case and it is not hypothetical: a bundle that
    # binds a warehouse this machine cannot reach (an Athena connector without credentials) never
    # gets a measurement, and without this the projector could contribute `grounds` edges whose
    # dataset endpoints no producer had ever created. Measured 2026-09-28 on the two bundles in
    # the console that are NOT duckdb — the lineage view went blank the moment
    # `objects.json#lineage_graph` was retired, because the one artifact had nothing in it. A
    # census the bundle can state about itself is always available; the measurement is not.
    have = {n["id"] for n in doc["nodes"]}
    doc["nodes"] += [n for n in fallback_nodes if n["id"] not in have]
    doc["edges"] = [e for e in (doc.get("edges") or []) if e.get("kind") not in own["edges"]] + list(edges)
    for k, v in keys.items():
        if k not in own["keys"]:
            raise ValueError(f"{producer!r} does not own {k!r}; owned: {own['keys']}")
        doc[k] = v
    by = [g for g in (doc.get("generated_by") or []) if not g.startswith(producer)]
    doc["generated_by"] = sorted([*by, producer])
    return recompute(doc)


def recompute(doc: dict) -> dict:
    """counts + orphans over the UNION of both halves. Derived, never authored — so the artifact
    cannot carry a count that describes only the half its last writer knew about."""
    nodes = list(doc.get("nodes") or [])
    # a node named by an edge but described by nobody is DRAWN and MARKED, never dropped: an edge
    # silently discarded for a missing endpoint is the false-absence failure this estate keeps
    # tripping over.
    known = {n["id"] for n in nodes}
    _kind_of = {v: k for k, v in _PREFIX.items()}
    for e in list(doc.get("edges") or []):
        for side in ("from", "to"):
            if e[side] not in known:
                pfx, ref = e[side].split(":", 1)
                nodes.append({"id": e[side], "ref": ref, "kind": _kind_of.get(pfx, "dataset"),
                              "title": ref, "relation": None, "issues": 0, "undescribed": True})
                known.add(e[side])

    nodes.sort(key=lambda n: (NODE_KINDS.index(n["kind"]) if n["kind"] in NODE_KINDS else 9, n["id"]))
    # A MEASUREMENT ALWAYS BEATS A CLAIM, whatever order the producers ran in. `claims` is the
    # stand-in this module draws when NO warehouse measurement exists; the moment one does, the
    # claim is not a second opinion, it is a superseded guess — and a claim that the measurement
    # contradicts is already reported under `disagreements.claimed_not_measured`.
    #
    # THE ORDER-DEPENDENT VERSION SHIPPED AND PASSED ITS OWN CHECKLIST. `project` runs before
    # `lineage`, so the projector wrote 8 `claims` edges, `mac_lineage` then added the 8 measured
    # `feeds` edges, and this dedupe — keyed on (from, to) over a list sorted by kind — kept
    # whichever sorted FIRST: "claims" < "feeds". Measured on contoso5, 2026-09-28: the artifact
    # came out `measured: false` with `edges_by_kind {claims: 8, cuts: 48}` and ZERO feeds, while
    # T8 ("every served relation is traced") and T9 ("63 of 63 columns") both reported complete.
    # The checklist was reading the columns, which survived, over a graph that had thrown the
    # measurement away.
    _measured_pairs = {(e["from"], e["to"]) for e in (doc.get("edges") or [])
                       if e["kind"] in ("feeds", "derives_from")}
    _rank = {"claims": 1}          # everything else ranks 0 — i.e. wins
    seen, edges = set(), []
    for e in sorted(doc.get("edges") or [],
                    key=lambda e: (e["from"], e["to"], _rank.get(e["kind"], 0), e["kind"])):
        k = (e["from"], e["to"])
        if e["kind"] == "claims" and k in _measured_pairs:
            continue
        if k not in seen:
            seen.add(k)
            edges.append(e)

    # EACH CATEGORY TESTS THE EDGE KIND IT IS ABOUT, never "has any edge". Measured the hour the
    # `cuts` edge was added: every source and every dataset acquired an outgoing edge to a value
    # register, and `sources_feeding_nothing` and `datasets_bound_by_no_concept` both collapsed
    # from truthful lists to `[]`. contoso5's `orders` and `orderrows` feed no served relation —
    # a deliberate modelling decision that an operator must see and confirm — and an orphan
    # register that reports nothing because an unrelated edge kind was added is worse than absent:
    # it reads as a clean bill of health.
    _out = lambda kinds: {e["from"] for e in edges if e["kind"] in kinds}   # noqa: E731
    _in = lambda kinds: {e["to"] for e in edges if e["kind"] in kinds}      # noqa: E731
    FEEDS = ("feeds", "derives_from", "claims")
    fed_by = _in((*FEEDS, "seeded_by"))
    feeds_into = _out(FEEDS)
    grounds_out, grounds_in = _out(("grounds",)), _in(("grounds",))
    cut_in = _in(("cuts",))
    _ghost = {n["id"] for n in nodes if n.get("undescribed")}
    _from_undescribed = {e["to"] for e in edges if e["from"] in _ghost}
    _refs = lambda kind, pred: sorted(n["ref"] for n in nodes if n["kind"] == kind and pred(n))  # noqa: E731
    cols = list(doc.get("columns") or [])
    orphans = {
        "sources_feeding_nothing": _refs("source", lambda n: n["id"] not in feeds_into),
        "datasets_with_no_input": _refs("dataset", lambda n: n["id"] not in fed_by),
        "datasets_bound_by_no_concept": _refs("dataset", lambda n: n["id"] not in grounds_out),
        "concepts_grounded_in_nothing": _refs("concept", lambda n: n["id"] not in grounds_in),
        "lookups_cut_from_nothing": _refs("lookup", lambda n: n["id"] not in cut_in),
        # A REGISTER POINTING AT A RELATION THIS BUNDLE DOES NOT HAVE. It is not "cut from nothing"
        # — it names a source, and that is exactly why it needs its own category: it LOOKS traced.
        # Measured on contoso5 the day this was written, 24 of 72 registers named `d_product`,
        # `d_store`, `f_sales_line` and their siblings — the relation names from a superseded draft
        # of the served model. A stale register is a value domain quietly describing a table that
        # no longer exists, and nothing in the estate could see it.
        "registers_cut_from_an_unknown_relation": sorted(
            n["ref"] for n in nodes if n["kind"] == "lookup" and n["id"] in _from_undescribed
        ),
        "relations_named_but_not_described": sorted(
            n["ref"] for n in nodes if n.get("undescribed")
        ),
        "columns_with_no_traceable_source": sorted(
            f"{c['view']}.{c['column']}" for c in cols if not c.get("source_column")
        ),
    }

    counts = {k: sum(1 for n in nodes if n["kind"] == k) for k in NODE_KINDS}
    counts["edges"] = len(edges)
    counts["edges_by_kind"] = {k: sum(1 for e in edges if e["kind"] == k)
                               for k in sorted({e["kind"] for e in edges})}
    fan: dict[str, int] = {}
    for e in edges:
        if e["to"].startswith("con:"):
            fan[e["to"]] = fan.get(e["to"], 0) + 1
    # the single number that proves concepts are NOT a schema mirror
    counts["concepts_multi_grounded"] = sum(1 for v in fan.values() if v > 1)
    counts["columns"] = len(cols)
    counts["columns_with_a_stated_source"] = sum(1 for c in cols if c.get("source_column"))
    counts["columns_traced_through_a_transform"] = sum(
        1 for c in cols if c.get("source_column") and c.get("transform")
    )
    counts["columns_derived_from_several_or_none"] = len(orphans["columns_with_no_traceable_source"])

    # DERIVED, NOT STAMPED. `build()` used to set this and `mac_lineage` never touched it, so an
    # artifact carrying a full column measurement still said `measured: false` purely because the
    # projector wrote last. The artifact should answer "was the warehouse read?" from its own
    # contents, not from the order of its authors.
    doc["measured"] = bool(cols) or any(e["kind"] in ("feeds", "derives_from") for e in edges)
    doc["nodes"], doc["edges"], doc["counts"], doc["orphans"] = nodes, edges, counts, orphans
    return doc


# --------------------------------------------------------------------------------------------
# this producer's half: what the bundle's own descriptors know
# --------------------------------------------------------------------------------------------
def describe(objects: list) -> tuple[list, list, dict]:
    """(nodes, edges, disagreements-input) for the kinds THIS producer owns: lookups and concepts,
    plus the `cuts`/`seeded_by`/`grounds` edges. Built from the ALREADY-BUILT objects list rather
    than re-reading YAML: the objects are the single source of truth for the chain, so the graph
    cannot disagree with the pages it links to."""
    by_kind: dict[str, list] = {k: [] for k in NODE_KINDS}
    for o in objects or []:
        if o.get("kind") in by_kind:
            by_kind[o["kind"]].append(o)

    nodes, edges, census = [], [], []

    # WHAT THE BUNDLE KNOWS ABOUT ITSELF. Not owned — the warehouse measurement wins wherever it
    # exists — but a bundle that cannot be measured here must still draw its own chain.
    for o in by_kind["source"]:
        census.append({"id": f"src:{o['id']}", "ref": o["id"], "kind": "source",
                       "title": o.get("title") or o["id"], "relation": o.get("relation"),
                       "issues": len(o.get("quality") or []), "measured": False})
    for o in by_kind["dataset"]:
        census.append({"id": f"ds:{o['id']}", "ref": o["id"], "kind": "dataset",
                       "title": o.get("title") or o["id"], "relation": o.get("relation"),
                       "transform": o.get("transform"),
                       "issues": len(o.get("quality") or []), "measured": False})

    # A register is cut from whatever relation it names, and that relation may be a LANDING or a
    # SERVED VIEW — measured on contoso5, 72 registers name 24 distinct relations across both
    # planes. Resolve against the objects that exist rather than assuming a plane; a ref matching
    # nothing is still drawn, and `recompute` marks that node `undescribed` so a register pointing
    # at a relation this bundle no longer has is VISIBLE instead of silently rehomed.
    _plane_of = {o["id"]: "dataset" for o in by_kind["dataset"]}
    _plane_of.update({o["id"]: "source" for o in by_kind["source"]})

    for o in by_kind["lookup"]:
        nodes.append({"id": f"lk:{o['id']}", "ref": o["id"], "kind": "lookup",
                      "title": o.get("title") or o["id"], "relation": None,
                      "issues": len(o.get("quality") or [])})
        # WHERE THE REGISTER CAME FROM. A value register is CUT from a source column, and the CSV
        # says so in its own `source_schema`/`source_view` columns — so the provenance of a domain
        # is measured, not assumed. Without this edge contoso5's 72 registers sat in no graph at
        # all: present on disk, invisible to every lineage view, orphaned by nothing.
        cf = o.get("cut_from")
        if cf and cf.get("ref"):
            pfx = _PREFIX[_plane_of.get(cf["ref"], cf.get("kind") or "source")]
            edges.append({"from": f"{pfx}:{cf['ref']}", "to": f"lk:{o['id']}", "kind": "cuts"})

    for o in by_kind["concept"]:
        nodes.append({"id": f"con:{o['id']}", "ref": o["id"], "kind": "concept",
                      "title": o.get("title") or o["id"], "class": o.get("class"),
                      "issues": 0, "rules": len(o.get("rules") or [])})
        for g in o.get("grounds") or []:
            edges.append({"from": f"ds:{g['id']}", "to": f"con:{o['id']}", "kind": "grounds"})

    # EVERY input kind, not just raw sources: a transform also reads other DATASETS and the
    # ATTRIBUTED LOOKUPS (authored seeds) that carry how the values came to being. Only the LOOKUP
    # half is owned here — the source/dataset half is the warehouse's to measure — so the claimed
    # relation edges are collected for COMPARISON instead.
    claimed: set[tuple[str, str]] = set()
    for o in by_kind["dataset"]:
        for inp in o.get("inputs") or [{"kind": "source", "ref": s} for s in (o.get("sources") or [])]:
            kind, ref = inp.get("kind"), inp.get("ref")
            if kind == "lookup":
                edges.append({"from": f"lk:{ref}", "to": f"ds:{o['id']}", "kind": "seeded_by"})
            elif kind in _INPUT_EDGE:
                claimed.add((f"{_PREFIX[kind]}:{ref}", f"ds:{o['id']}"))

    # a register that seeds nothing and is cut from nothing is not part of any chain — drop it
    # from the DRAWING rather than float it, but `orphans.lookups_cut_from_nothing` still counts
    # it, so "dropped" never means "unreported".
    used = {e["from"] for e in edges} | {e["to"] for e in edges}
    nodes = [n for n in nodes if n["kind"] != "lookup" or n["id"] in used]
    return nodes, edges, {"claimed": claimed, "census": census}


def build(root, objects: list) -> dict:
    """Fold this producer's half into the ONE artifact and write it. Returns the whole document.

    Reads whatever `tools/mac_lineage.py` has already measured; a bundle that has never been
    measured gets the descriptors' own relation edges instead, MARKED as unmeasured rather than
    passed off as a measurement.
    """
    doc = load(root)
    nodes, edges, claim = describe(objects)
    measured = [(e["from"], e["to"]) for e in (doc.get("edges") or [])
                if e["kind"] in ("feeds", "derives_from")]
    claimed = claim["claimed"]

    if measured:
        dis = {
            "claimed_not_measured": sorted(f"{a} -> {b}" for a, b in claimed - set(measured)),
            "measured_not_claimed": sorted(f"{a} -> {b}" for a, b in set(measured) - claimed),
        }
    else:
        # NO MEASUREMENT AT ALL. Draw the claim so the bundle is not blank, and give it ITS OWN
        # EDGE KIND — `claims`, never `feeds`. Two reasons, and both are load-bearing: `feeds` is
        # owned by the measurement, so writing one here would put this producer inside the other's
        # slice and the next measured run would silently delete it; and a reader must be able to
        # tell "the engine says so" from "a descriptor says so" without reading the counts.
        edges += [{"from": a, "to": b, "kind": "claims"} for a, b in sorted(claimed)]
        dis = {"claimed_not_measured": [], "measured_not_claimed": [],
               "note": "no warehouse measurement on this bundle; relation edges are transform "
                       "descriptor CLAIMS (tools/mac_lineage.py has not run)"}

    return merge(doc, "sdk.project.lineage_graph", nodes, edges,
                 fallback_nodes=claim["census"], disagreements=dis)
