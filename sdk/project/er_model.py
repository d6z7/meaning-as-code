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
If a diagram shows "many KPI rows to one Market", that claim is `kpi__of_market` in edges.yaml, and
challengeable in the same place every other claim in this ontology is.

RESOLUTION. The join_rule names TABLES, so it identifies the entity pair directly — more reliable than
routing through concept groundings (a concept may ground several relations). Which side is `from` is
then decided by matching each side's table against the from-concept's grounded relations; when that is
ambiguous the edge is still emitted, flagged `side_inferred`, rather than dropped.

WHAT THIS MODEL USED TO LEAVE UNSAID, and why each silence was a defect rather than a simplification:

  1. THE EDGES IT CANNOT DRAW. An edge realised by a column CARRIED ON THE FACT is not a key equality:
     there is no second box, so no crow's foot can carry it. Measured on a live bundle: 8 of 32 concept
     edges are realised that way and the projector simply `continue`d past them. The diagram then
     showed 24 relationships and said nothing about the other 8 — an absence rendering as completeness,
     which is this estate's recurring defect. Undrawable is correct; SILENT is not. They now leave here
     as `unrealised_edges`, each carrying the reason it cannot be a line, and the counts reconcile
     against the edge total so a future silence shows up as an `accounting_error` instead of a gap.

  2. THE PROOF STATE. `cardinality` was carried and `verified_by` + `confidence` were dropped, so a
     relationship the warehouse has been measured to satisfy drew IDENTICALLY to one nobody checked.
     A crow's foot reads as a fact about the data, so rendering an unproved claim as a proved one is
     the most expensive silence in the set. Both now travel, per concept edge and rolled up per line.

  3. CONNECTED COMPONENTS. `isolated_entities` counts entities of degree ZERO and was reported as 0 —
     truthfully — while the relationship graph had THREE disconnected islands (sizes 5, 6 and 2). An
     island of six has no degree-zero member, so the one metric a reader would have checked could not
     see the thing an operator saw immediately. `components` is that metric.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

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

# ---- PROOF STATE, READ AND NOT RE-DERIVED --------------------------------------------------------
# An endpoint cardinality is a CLAIM about the warehouse and `verified_by` is the evidence that
# settles it. This projector carried the claim and dropped the evidence, so the view had no way to
# draw a measured relationship differently from an unexamined one.
#
# READ THE VERDICT, DO NOT RE-DERIVE IT. check_edge_claims_proved.py records what happened the last
# time a consumer recomputed the verdict from lhs/matched/fanout: the day the measurer learned to
# count a column and a conformed list those fields were absent, `lhs` read 0, and fourteen edges
# whose claims HOLD were reported CONTRADICTED. Three consumers each kept a copy of that arithmetic.
# This is the fourth consumer of the same record and it keeps none — the measurer decides `holds`
# once, and everything here only reads it.
PROVED, DISPROVED, UNPROVED, UNRESOLVED = "proved", "disproved", "unproved", "unresolved"
# A recorded deferral is a deliberate human act and still is not evidence, so it ranks BELOW proved
# and above the states where nobody said anything. check_edge_claims_proved.DEFERRING is its home.
DEFERRED = "deferred"

# WEAKEST WINS when a drawn line realises several concept edges. One physical join here realises
# SEVEN of them, and a measured business line realises two whose authored confidence DISAGREES (C and
# I). Rolling up to the best member would print a fully-proved line over a claim whose weakest member
# is inferred — the same substitution of the strongest reading for the true one that this whole
# change exists to stop. `min` over these ranks is therefore deliberate, not a convenience.
PROOF_RANK = {DISPROVED: 0, UNRESOLVED: 1, UNPROVED: 2, DEFERRED: 3, PROVED: 4}
# The framework's trust tier (mac.schema.json $defs/confidence): C confirmed, I inferred, Q needs-SME.
# An absent or unknown tier ranks BELOW Q: unknown trust is not a middling amount of trust.
CONFIDENCE_RANK = {"Q": 0, "I": 1, "C": 2}
MEASUREMENT_FILE = "edge_measurements.json"
# The numeric fields a measurement may carry. Which ones are present depends on its `kind`
# (join_predicate / column_presence / value_uniqueness / list_conformance), so they are copied by
# INTERSECTION rather than by a per-kind schema: a new kind then shows its numbers instead of
# vanishing, and no arithmetic is performed on any of them here.
MEASUREMENT_NUMBERS = (
    "lhs", "matched", "fanout", "population", "violations", "rows", "missing",
    "keys", "keys_with_many", "keys_with_none", "values", "conforming",
)

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


def _measurements(root) -> dict[str, dict]:
    """{edge_id: measurement} from ``<root>/evidence/edge_measurements.json``.

    An unreadable or absent record yields {} — and then EVERY edge citing it resolves to UNRESOLVED
    below, which is what the view renders. It must never collapse into "proved": a projector that
    reports green because nobody measured is the empty-denominator defect wearing a projector's
    clothes, and this estate has shipped that shape repeatedly.
    """
    if not root:
        return {}
    rec_path = Path(root) / "evidence" / MEASUREMENT_FILE
    try:
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — absent, unreadable and malformed are all "cannot resolve"
        return {}
    return {
        str(m.get("edge")): m
        for m in (rec.get("results") or [])
        if isinstance(m, dict) and m.get("edge")
    }


def _claims_gate():
    """``check_edge_claims_proved.verdict_of`` — the framework's ONE home for turning an edge's
    ``verified_by`` reference into a verdict.

    WHY THIS IS IMPORTED AND NOT REIMPLEMENTED. `verified_by` has two target shapes: a measurement
    record (`evidence/edge_measurements.json#<edge>`, verdict = `holds`) and an acceptance property
    (`acceptance/<suite>.yaml#<ID>`, verdict = the recorded `status` in `<suite>_runs.json`). A first
    cut of this projector read only the first shape and reported the second as UNRESOLVED — so a line
    realising seven edges read "not proved" because ONE of them cited a suite this file declined to
    open, while the gate reported 32 of 32 proved. Manufacturing red is the same class of error as
    manufacturing green. ontology_quality.py states the rule for exactly this situation: the logic
    "has ONE home in meaning-as-code/tools, and a dashboard that re-derived it would be a second".

    Loaded by path, not by sys.path: this module is imported from several roots (the SDK package, the
    console's projector, a bare `import er_model` in objects.py) and only its own location is
    reliable. None -> every edge resolves UNRESOLVED and says why, which is the honest reading.
    """
    import importlib.util

    src = Path(__file__).resolve().parents[2] / "tools" / "check_edge_claims_proved.py"
    try:
        spec = importlib.util.spec_from_file_location("_mac_check_edge_claims_proved", src)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:  # noqa: BLE001 — a missing/unloadable gate is reported per edge, not raised
        return None


def _proof(e: dict, root, measured: dict, gate) -> dict:
    """The evidence an edge CITES, resolved to a state — never to a bare "has a pointer".

    A `verified_by` pointer whose target nobody opens is a citation, not a proof: check_references.py
    proves such a pointer RESOLVES and never reads the verdict, so an edge could cite evidence that
    FAILED and still carry `confidence: C`. Five states, because five different repairs:

      proved      the cited evidence's recorded verdict is PASS
      disproved   the cited evidence CONTRADICTS the edge — its own citation measured the claim false
      deferred    the verdict is a recorded human deferral (FROZEN / ACCEPTED). A deliberate act, and
                  still not evidence — so it must not draw like a proof
      unproved    the edge cites nothing. A legitimate state, and saying so is the whole point
      unresolved  something cited cannot be opened or carries no verdict — a broken link, not a result

    `numbers` is copied off the measurement for DISPLAY only. No verdict is computed from it here;
    see the PROOF_RANK block for what happened the last time a consumer did that.
    """
    ref = str(e.get("verified_by") or "").strip()
    if not ref:
        return {"state": UNPROVED, "ref": None, "why": "cites no evidence"}
    if gate is None or root is None:
        return {
            "state": UNRESOLVED,
            "ref": ref,
            "why": "no bundle root or no check_edge_claims_proved to resolve the citation with — "
            "run the gate for the verdict",
        }
    try:
        verdict, note = gate.verdict_of(Path(root), ref)
    except Exception as exc:  # noqa: BLE001
        return {"state": UNRESOLVED, "ref": ref, "why": f"resolving the citation raised {exc!r}"}

    if verdict is None:
        state, why = UNRESOLVED, note
    elif verdict in getattr(gate, "PROVING", {"PASS"}):
        state, why = PROVED, ""
    elif verdict in getattr(gate, "DEFERRING", {"FROZEN", "ACCEPTED"}):
        state, why = DEFERRED, f"verdict {verdict} — a recorded deferral, not evidence"
    else:
        state, why = DISPROVED, f"its own cited evidence is {verdict}"

    m = measured.get(str(ref.split("#", 1)[-1])) or {}
    out = {"state": state, "ref": ref, "why": why or str(m.get("note") or "")}
    if m:
        out["kind"] = m.get("kind")
        out["realisation"] = m.get("realisation")
        out["numbers"] = {k: m[k] for k in MEASUREMENT_NUMBERS if k in m}
    return out


def _member(e: dict, root, measured: dict, gate) -> dict:
    """One concept edge as it appears on the line that draws it: the claim AND its proof state.

    `confidence` and `verified_by` live here rather than only on the rolled-up line because a merged
    line's members disagree — reading the roll-up alone cannot tell you WHICH of seven edges is the
    weak one, and that is the only question a reader has once the line is marked unproved.
    """
    ep = e.get("endpoints") or {}
    return {
        "edge_id": e.get("edge_id"),
        "from_concept": (ep.get("from") or {}).get("concept"),
        "to_concept": (ep.get("to") or {}).get("concept"),
        "type": e.get("type"),
        "confidence": e.get("confidence"),
        "verified_by": e.get("verified_by"),
        "proof": _proof(e, root, measured, gate),
    }


def _roll_up(members: list[dict]) -> tuple[dict, str | None]:
    """(proof, confidence) for a line, taken from its WEAKEST member. See PROOF_RANK."""
    weakest = min(members, key=lambda m: PROOF_RANK.get(m["proof"]["state"], 0))
    weakest_conf = min(members, key=lambda m: CONFIDENCE_RANK.get(str(m.get("confidence") or ""), -1))
    proof = dict(weakest["proof"])
    proof["from_edge"] = weakest["edge_id"]
    # The denominator, always. "proved" over a line realising seven edges means all seven; printing
    # the fraction is what stops a reader reading one measured edge as seven measured edges.
    proof["members"] = len(members)
    proof["members_proved"] = sum(1 for m in members if m["proof"]["state"] == PROVED)
    return proof, weakest_conf.get("confidence")


def _why_undrawable(e: dict) -> str:
    """Why a PHYSICAL edge yields no line. Three different states, never one number.

    check_edge_joins_measured.py already learned this lesson on its own output: reporting every
    predicate-less edge as one count "was this gate's own version of the defect it exists to catch".
    """
    rule = str(e.get("join_rule") or "").strip()
    if rule:
        return (
            f"declares a join_rule this projector cannot read as `table.col = table.col`: {rule[:140]}"
        )
    realised = str(e.get("realized_by") or e.get("resolved_by") or "").strip()
    if realised:
        # THE MEASURED CASE — 8 of 32 edges on a live bundle. The realisation names a column CARRIED
        # ON THE FACT ROW ("…grouping by it is a GROUP BY, not a join"), so there is no key equality
        # and no second entity box. Drawing a crow's foot would assert a join the warehouse does not
        # have — and on this bundle that exact join was DELETED by decision for multiplying every
        # fact row 215x. So the absence of a line is CORRECT. The absence of a statement is not.
        return (
            f"realised without a join — {realised[:200]} — there is no key equality between two "
            f"entities, so no line can carry it"
        )
    return "declares NO realisation at all — not a join, not a rule, not a column"


def _undrawable(e: dict, root, measured: dict, gate, why: str) -> dict:
    ep = e.get("endpoints") or {}
    f, t = ep.get("from") or {}, ep.get("to") or {}
    m = _member(e, root, measured, gate)
    return {
        **m,
        "level": e.get("level"),
        "from_cardinality": f.get("cardinality"),
        "to_cardinality": t.get("cardinality"),
        "reason": why,
        "realized_by": e.get("realized_by"),
        "resolved_by": e.get("resolved_by"),
    }


def _components(entities: list, rels: list) -> list[list[str]]:
    """The relationship graph's CONNECTED COMPONENTS, as sorted entity-id groups.

    WHY THIS IS NOT `isolated_entities`. That counts entities of degree ZERO. It read 0 — truthfully
    — on a bundle whose graph was three separate islands, because an island of six tables has no
    degree-zero member. An operator saw the three groups at a glance; the one number that would have
    corroborated them was structurally unable to. More than one component is not a layout accident
    and not necessarily a fault: it is a statement about the model that the diagram must make out
    loud, so the reader knows the gap between two clusters is the model and not the renderer.
    """
    parent = {e["id"]: e["id"] for e in entities}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for r in rels:
        a, b = r["from"]["entity"], r["to"]["entity"]
        if a not in parent or b not in parent:
            continue  # a dangling endpoint is already reported as `dangling` on the relationship
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    groups: dict[str, list[str]] = {}
    for e in entities:
        groups.setdefault(find(e["id"]), []).append(e["id"])
    return sorted((sorted(g) for g in groups.values()), key=lambda g: (-len(g), g[0]))


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


def _business_rel(
    e: dict, grounded: dict, ds_relation: dict, ds_by_transform: dict
) -> tuple[dict | None, str | None]:
    """(relationship, None) or (None, why it cannot be drawn).

    It used to return a bare None, and the caller dropped it without a word. Three quite different
    situations collapsed into that silence — an ungrounded from-concept, an ungrounded to-concept, and
    a relationship whose two ends land on the SAME table — and each needs a different repair.
    """
    ep = e.get("endpoints") or {}
    f, t_ = ep.get("from") or {}, ep.get("to") or {}
    # `resolved_by`/`realized_by` names the transform that establishes the relationship; the dataset it
    # produces is where the relationship physically sits.
    anchor = str(e.get("resolved_by") or e.get("realized_by") or "")
    stem = anchor.split("#")[0].rsplit("/", 1)[-1].removesuffix(".yaml") if anchor else None
    prefer = ds_relation.get(stem) if stem else None
    fe = _entity_for(f.get("concept"), grounded, ds_relation, prefer)
    te = _entity_for(t_.get("concept"), grounded, ds_relation)
    if not fe:
        return None, (
            f"its from-concept {f.get('concept')!r} grounds on no relation, so it has no entity box"
        )
    if not te:
        return None, (
            f"its to-concept {t_.get('concept')!r} grounds on no relation, so it has no entity box"
        )
    if fe == te:
        return None, (
            f"both endpoints resolve to the same entity ({fe}) — a self-relation, and this diagram "
            f"draws a line between two boxes"
        )
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
    }, None


def build(
    datasets: dict,
    concepts: dict,
    ont_edges: list,
    ds_relation: dict | None = None,
    root=None,
) -> dict:
    """`root` is the bundle root, read ONLY to resolve each edge's cited evidence into a proof
    state (see `_measurements`). Optional and additive: without it every edge resolves to
    UNRESOLVED and the view says so, which is the honest reading of "nobody supplied the
    evidence record" — never a silent pass."""
    ds_relation = ds_relation or {}
    measured = _measurements(root)
    gate = _claims_gate()

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

    # Every concept edge leaves here either as a drawn line or as an `unrealised_edges` entry with
    # the reason. The two lists must account for all of `ont_edges`; `accounting_error` below is the
    # guard that a future `continue` cannot quietly re-open the hole this list exists to close.
    rels, undrawable = [], []
    for e in ont_edges or []:
        # BUSINESS relationships belong in the diagram too — drawn as non-physical. Leaving them out
        # made five conformed attribute dimensions look ISOLATED when they are related, just not by a
        # foreign key: dim_model carries conformed ARRAYS, so an equality join would be a lie
        # (decisions/0006 §2). An ER diagram that shows only FKs silently claims they relate to
        # nothing, which is a worse error than showing the relationship with an honest style.
        if e.get("level") == "business":
            b, why = _business_rel(e, grounded, ds_relation, ds_by_transform)
            if b:
                b["member"] = _member(e, root, measured, gate)
                rels.append(b)
            else:
                undrawable.append(_undrawable(e, root, measured, gate, why))
            continue
        if e.get("level") != "physical":
            # `federation` is the third level the schema allows. It is a relationship BETWEEN
            # bundles, so this single-bundle diagram has no far box for it — say that, do not skip it.
            undrawable.append(
                _undrawable(
                    e,
                    root,
                    measured,
                    gate,
                    f"level {e.get('level')!r} is not an intra-bundle entity relationship, so this "
                    f"diagram has no second box to draw it to",
                )
            )
            continue
        pairs = _parse_join(e.get("join_rule"))
        if not pairs:
            undrawable.append(_undrawable(e, root, measured, gate, _why_undrawable(e)))
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
                "member": _member(e, root, measured, gate),
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
            # The member was built from the EDGE, so it carries that edge's confidence, its
            # verified_by and the resolved proof state. Rebuilding it here from `r` — as this did —
            # could only ever restate what the picture already shows, which is how the evidence came
            # to be dropped in the first place.
            r["realized_by"] = [r.pop("member")]
            merged[k] = r
            continue
        m["realized_by"].append(r.pop("member"))
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
        # acme_brand_country_code_id AND on brand_code_id). Keying on the pair gave them the SAME id,
        # and a renderer that identifies edges by id then cannot tell them apart — one of them silently
        # stopped responding to selection.
        lvl, fe, fc, te, tc = k
        r["id"] = (
            r["realized_by"][0]["edge_id"]
            if len(r["realized_by"]) == 1
            else f"{lvl}:{fe}.{'+'.join(fc) or '_'}__{te}.{'+'.join(tc) or '_'}"
        )
        r["proof"], r["confidence"] = _roll_up(r["realized_by"])
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
    comps = _components(entities, rels)
    drawn_edges = sum(len(r.get("realized_by") or []) for r in rels)
    members = [m for r in rels for m in (r.get("realized_by") or [])]
    return {
        "entities": entities,
        "relationships": rels,
        # THE EDGES THIS DIAGRAM CANNOT DRAW, named rather than skipped. See the module docstring §1.
        "unrealised_edges": undrawable,
        # More than one group means the graph really is in pieces; the view states the number so a
        # reader is never left deciding whether the gap is the model or the renderer.
        "components": comps,
        "counts": {
            "entities": len(entities),
            "relationships": len(rels),
            "concept_edges": drawn_edges,
            # DENOMINATORS. `concept_edges` alone reads as completeness: 24 drawn edges over an
            # unstated total of 32. Both halves and the total now travel together, and they must add
            # up (see `accounting_error`).
            "concept_edges_total": len(ont_edges or []),
            "concept_edges_undrawable": len(undrawable),
            "cardinality_conflicts": sum(len(r.get("cardinality_conflicts") or []) for r in rels),
            "isolated_entities": len(
                [
                    e
                    for e in entities
                    if not any(e["id"] in (r["from"]["entity"], r["to"]["entity"]) for r in rels)
                ]
            ),
            # `isolated_entities: 0` was TRUE while the graph stood in three pieces. See _components.
            "components": len(comps),
            "physical": sum(1 for r in rels if r.get("level") == "physical"),
            "business": sum(1 for r in rels if r.get("level") == "business"),
            "with_cardinality": sum(1 for r in rels if r["from"]["crow"] and r["to"]["crow"]),
            "side_inferred": sum(1 for r in rels if r["side_inferred"]),
            # PROOF, counted at both grains, because they answer different questions: how many LINES
            # a reader may rely on, and how many CLAIMS stand behind them.
            "proved": sum(1 for r in rels if r["proof"]["state"] == PROVED),
            "not_proved": sum(1 for r in rels if r["proof"]["state"] != PROVED),
            "disproved": sum(1 for r in rels if r["proof"]["state"] == DISPROVED),
            "concept_edges_proved": sum(1 for m in members if m["proof"]["state"] == PROVED),
            "undrawable_proved": sum(
                1 for u in undrawable if u["proof"]["state"] == PROVED
            ),
        },
        # A COUNT THAT DOES NOT RECONCILE IS A BUG, NOT A NUMBER. Every concept edge must leave here
        # as a drawn line's member or as an unrealised_edges entry. A non-empty value here means a
        # code path swallowed one, which is precisely the failure this change repaired — so it is
        # projected rather than asserted, and the view shows it.
        "accounting_error": (
            ""
            if drawn_edges + len(undrawable) == len(ont_edges or [])
            else (
                f"{len(ont_edges or [])} concept edge(s) in, {drawn_edges} drawn + "
                f"{len(undrawable)} reported undrawable = {drawn_edges + len(undrawable)}"
            )
        ),
        # never silently swallow a cardinality the closed vocabulary does not know
        "unknown_cardinalities": unknown,
        # a renderer identifies relationships by id; a collision makes one of them unaddressable
        "duplicate_ids": sorted(
            {r["id"] for r in rels if [x["id"] for x in rels].count(r["id"]) > 1}
        ),
    }
