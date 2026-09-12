#!/usr/bin/env python3
"""sdk.project.er_model — a real ENTITY-RELATIONSHIP model: entities with keys, relationships with
CARDINALITY, resolved to the exact join columns. DETERMINISTIC + IDEMPOTENT (no LLM, no AWS).

WHY THIS EXISTS
---------------
The ER view drew tables joined by "shared keys" — boxes and plain lines. That is a dependency picture
wearing ER clothes: it shows THAT two tables relate and says nothing an ER diagram exists to say —
which side is the one and which the many, whether the relationship is optional, and which columns
actually carry it.

All of that is already authored and was simply never projected:

  * dataset columns carry ``role`` — primary_key / foreign_key / composite_key_part / discriminator
  * ``ontology/edges.yaml`` physical edges carry ``cardinality`` on BOTH endpoints ("1", "0..N") and a
    ``join_rule`` naming the columns: ``v_acme_kpi.acme_brand_country_code_id = dim_brand_country_code.…``

So the crow's feet are not decoration and not inferred — they are the authored cardinality, rendered.
If a diagram shows "many DtC to one Market", that claim is `dtc__of_market` in edges.yaml, and it is
challengeable in the same place every other claim in this ontology is.

RESOLUTION. The join_rule names TABLES, so it identifies the entity pair directly — more reliable than
routing through concept groundings (a concept may ground several relations). Which side is `from` is
then decided by matching each side's table against the from-concept's grounded relations; when that is
ambiguous the edge is still emitted, flagged `side_inferred`, rather than dropped.
"""

from __future__ import annotations

import re

# The four classical crow's-foot terminals. `min` decides the inner mark (circle = optional, bar =
# mandatory); `max` decides the outer one (bar = one, crow = many).
CARDINALITY = {
    "1": {"min": "one", "max": "one", "label": "1"},
    "1..1": {"min": "one", "max": "one", "label": "1"},
    "0..1": {"min": "zero", "max": "one", "label": "0..1"},
    "1..N": {"min": "one", "max": "many", "label": "1..N"},
    "0..N": {"min": "zero", "max": "many", "label": "0..N"},
    "N": {"min": "zero", "max": "many", "label": "N"},
}
KEY_ROLES = ("primary_key", "composite_key_part", "foreign_key")

_SIDE = re.compile(r"([A-Za-z0-9_.]+)\.([A-Za-z0-9_]+)")


def _bare(rel: str) -> str:
    return str(rel or "").split(".")[-1]


def _parse_join(rule: str) -> list[dict]:
    """`a.x = b.y AND a.z = b.w` -> [{left:(a,x), right:(b,y)}, …]. Returns [] if unparseable."""
    out = []
    for clause in re.split(r"\s+AND\s+", str(rule or ""), flags=re.I):
        if "=" not in clause:
            continue
        lhs, rhs = clause.split("=", 1)
        lm, rm = _SIDE.search(lhs.strip()), _SIDE.search(rhs.strip())
        if lm and rm:
            out.append(
                {
                    "left": (_bare(lm.group(1)), lm.group(2)),
                    "right": (_bare(rm.group(1)), rm.group(2)),
                }
            )
    return out


def _entity_for(
    concept: str, grounded: dict, ds_relation: dict, prefer: str | None = None
) -> str | None:
    """The dataset entity a concept sits on. `prefer` (a transform's dataset) wins when it is one of
    the concept's grounded relations — that is the relation the rule actually operates on."""
    rels = grounded.get(concept) or set()
    known = {ds_relation.get(k, k) for k in ds_relation} | set(ds_relation.values())
    if prefer and prefer in rels:
        return prefer
    cands = [r for r in sorted(rels) if r in known]
    return cands[0] if cands else (sorted(rels)[0] if rels else None)


def _business_rel(e: dict, grounded: dict, ds_relation: dict, ds_by_transform: dict) -> dict | None:
    ep = e.get("endpoints") or {}
    f, t_ = ep.get("from") or {}, ep.get("to") or {}
    # `resolved_by`/`realized_by` names the transform that establishes the relationship; the dataset it
    # produces is where the relationship physically sits.
    anchor = str(e.get("resolved_by") or e.get("realized_by") or "")
    stem = anchor.split("#")[0].rsplit("/", 1)[-1].removesuffix(".yaml") if anchor else None
    prefer = ds_relation.get(stem) if stem else None
    fe = _entity_for(f.get("concept"), grounded, ds_relation, prefer)
    te = _entity_for(t_.get("concept"), grounded, ds_relation)
    if not fe or not te or fe == te:
        return None
    return {
        "id": e.get("edge_id"),
        "type": e.get("type"),
        "level": "business",
        "from": {
            "entity": fe,
            "concept": f.get("concept"),
            "columns": [],
            "cardinality": f.get("cardinality"),
            "crow": CARDINALITY.get(str(f.get("cardinality") or "").strip()),
        },
        "to": {
            "entity": te,
            "concept": t_.get("concept"),
            "columns": [],
            "cardinality": t_.get("cardinality"),
            "crow": CARDINALITY.get(str(t_.get("cardinality") or "").strip()),
        },
        "join_rule": None,
        "resolved_by": e.get("resolved_by") or e.get("realized_by"),
        "side_inferred": False,
        "dangling": [],
    }


def build(datasets: dict, concepts: dict, ont_edges: list, ds_relation: dict | None = None) -> dict:
    ds_relation = ds_relation or {}

    entities = []
    for stem, d in sorted((datasets or {}).items()):
        tbl = d.get("table") or {}
        cols = []
        for c in d.get("columns") or []:
            role = c.get("role")
            cols.append(
                {
                    "name": c.get("name"),
                    "type": c.get("type"),
                    "role": role,
                    "key": role in KEY_ROLES,
                    "description": c.get("description"),
                }
            )
        entities.append(
            {
                "id": ds_relation.get(stem, stem),
                "stem": stem,
                "title": tbl.get("name") or stem,
                "columns": cols,
                "keys": [
                    c["name"] for c in cols if c["role"] in ("primary_key", "composite_key_part")
                ],
            }
        )
    by_id = {e["id"]: e for e in entities}

    # which relations each concept grounds on — used only to orient from/to
    grounded: dict[str, set] = {}
    for stem, c in (concepts or {}).items():
        name = (c.get("concept") or {}).get("name") or stem
        grounded[name] = {
            _bare(s.get("relation"))
            for s in ((c.get("grounding") or {}).get("sources") or [])
            if isinstance(s, dict)
        }

    # dataset produced by a transform stem, so `resolved_by: data/transforms/dim_model.yaml#…` can be
    # resolved to the entity the business relationship actually lives on
    ds_by_transform = {v: k for k, v in (ds_relation or {}).items()}

    rels = []
    for e in ont_edges or []:
        # BUSINESS relationships belong in the diagram too — drawn as non-physical. Leaving them out
        # made five conformed attribute dimensions look ISOLATED when they are related, just not by a
        # foreign key: dim_model carries conformed ARRAYS, so an equality join would be a lie
        # (decisions/0006 §2). An ER diagram that shows only FKs silently claims they relate to
        # nothing, which is a worse error than showing the relationship with an honest style.
        if e.get("level") == "business":
            b = _business_rel(e, grounded, ds_relation, ds_by_transform)
            if b:
                rels.append(b)
            continue
        if e.get("level") != "physical":
            continue
        pairs = _parse_join(e.get("join_rule"))
        if not pairs:
            continue
        ep = e.get("endpoints") or {}
        f, t = ep.get("from") or {}, ep.get("to") or {}
        lt, rt = pairs[0]["left"][0], pairs[0]["right"][0]
        # orient: does the FROM concept ground the left table or the right one?
        fg = grounded.get(f.get("concept"), set())
        inferred = False
        if lt in fg and rt not in fg:
            flip = False
        elif rt in fg and lt not in fg:
            flip = True
        else:
            flip, inferred = False, True  # ambiguous — emit anyway, flagged
        fe, te = (rt, lt) if flip else (lt, rt)
        fcols = [p["right" if flip else "left"][1] for p in pairs]
        tcols = [p["left" if flip else "right"][1] for p in pairs]

        rels.append(
            {
                "id": e.get("edge_id"),
                "type": e.get("type"),
                "level": e.get("level"),
                "from": {
                    "entity": fe,
                    "concept": f.get("concept"),
                    "columns": fcols,
                    "cardinality": f.get("cardinality"),
                    "crow": CARDINALITY.get(str(f.get("cardinality") or "").strip()),
                },
                "to": {
                    "entity": te,
                    "concept": t.get("concept"),
                    "columns": tcols,
                    "cardinality": t.get("cardinality"),
                    "crow": CARDINALITY.get(str(t.get("cardinality") or "").strip()),
                },
                "join_rule": e.get("join_rule"),
                "side_inferred": inferred,
                # an edge whose tables are not projected entities still gets drawn, as a stub
                "dangling": [x for x in (fe, te) if x not in by_id],
            }
        )
    # ---- COLLAPSE TO TABLE GRAIN --------------------------------------------------------------
    # 25 concept-level edges (dtc__of_market, order_intake__of_market, …) are realized by only FIVE
    # distinct physical joins: they are the same columns on the same two tables. An ER diagram speaks
    # in TABLES, so drawing one line per concept edge draws the same relationship 11 times over. They
    # collapse into one relationship that REMEMBERS which concept edges realize it (`realized_by`), so
    # nothing is lost — the detail moves from the picture to the click.
    merged: dict = {}
    for r in rels:
        k = (
            r.get("level"),
            r["from"]["entity"],
            tuple(r["from"]["columns"]),
            r["to"]["entity"],
            tuple(r["to"]["columns"]),
        )
        m = merged.get(k)
        if m is None:
            r["realized_by"] = [
                {
                    "edge_id": r["id"],
                    "from_concept": r["from"]["concept"],
                    "to_concept": r["to"]["concept"],
                    "type": r["type"],
                }
            ]
            merged[k] = r
            continue
        m["realized_by"].append(
            {
                "edge_id": r["id"],
                "from_concept": r["from"]["concept"],
                "to_concept": r["to"]["concept"],
                "type": r["type"],
            }
        )
        # a disagreement across the group is a real modelling inconsistency, not something to average
        for side in ("from", "to"):
            if r[side]["cardinality"] != m[side]["cardinality"]:
                m.setdefault("cardinality_conflicts", []).append(
                    {
                        "side": side,
                        "edge_id": r["id"],
                        "cardinality": r[side]["cardinality"],
                        "vs": m[side]["cardinality"],
                    }
                )
    rels = []
    for k, r in merged.items():
        r["realized_by"].sort(key=lambda x: x["edge_id"] or "")
        # The synthetic id MUST be derived from the merge key, not from the entity pair alone: two
        # different joins can connect the same two tables (v_acme_kpi -> dim_brand_country_code on
        # acme_brand_country_code_id AND on brand_letter_id). Keying on the pair gave them the SAME id,
        # and a renderer that identifies edges by id then cannot tell them apart — one of them silently
        # stopped responding to selection.
        lvl, fe, fc, te, tc = k
        r["id"] = (
            r["realized_by"][0]["edge_id"]
            if len(r["realized_by"]) == 1
            else f"{lvl}:{fe}.{'+'.join(fc) or '_'}__{te}.{'+'.join(tc) or '_'}"
        )
        rels.append(r)
    rels.sort(key=lambda r: (r["from"]["entity"], r["to"]["entity"], r["id"] or ""))

    unknown = sorted(
        {
            str(c)
            for r in rels
            for c in (r["from"]["cardinality"], r["to"]["cardinality"])
            if c and str(c).strip() not in CARDINALITY
        }
    )
    return {
        "entities": entities,
        "relationships": rels,
        "counts": {
            "entities": len(entities),
            "relationships": len(rels),
            "concept_edges": sum(len(r.get("realized_by") or []) for r in rels),
            "cardinality_conflicts": sum(len(r.get("cardinality_conflicts") or []) for r in rels),
            "isolated_entities": len(
                [
                    e
                    for e in entities
                    if not any(e["id"] in (r["from"]["entity"], r["to"]["entity"]) for r in rels)
                ]
            ),
            "physical": sum(1 for r in rels if r.get("level") == "physical"),
            "business": sum(1 for r in rels if r.get("level") == "business"),
            "with_cardinality": sum(1 for r in rels if r["from"]["crow"] and r["to"]["crow"]),
            "side_inferred": sum(1 for r in rels if r["side_inferred"]),
        },
        # never silently swallow a cardinality the closed vocabulary does not know
        "unknown_cardinalities": unknown,
        # a renderer identifies relationships by id; a collision makes one of them unaddressable
        "duplicate_ids": sorted(
            {r["id"] for r in rels if [x["id"] for x in rels].count(r["id"]) > 1}
        ),
    }
