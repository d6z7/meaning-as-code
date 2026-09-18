#!/usr/bin/env python3
"""sdk.project.er_model — the PHYSICAL entity-relationship model, MEASURED from the warehouse.

WHAT THIS DRAWS, AND WHAT IT REFUSES TO READ
--------------------------------------------
Relations, columns, keys, references, cardinality and participation — the DATA plane's own picture,
built from `data/references/*.yaml` (measured through the connector seam by
`tools/mac_references.py`), `data/sources/*.yaml` (the columns) and `data/profiles/*.yaml` (the
measured key). It reads NOTHING under `ontology/`. There is no fallback to `ontology/edges.yaml`
and there must not be one.

That fallback is the defect being removed. An ontology edge relates BUSINESS OBJECTS; a physical
reference relates RELATIONS AND COLUMNS; they look alike and are not the same claim. One artifact
was carrying both: twenty-five entries on a live bundle declared `level: physical, type:
foreign_key` while being keyed by `endpoints.from.concept`, with the relations and columns
flattened into a `join_rule` STRING that the projector re-parsed with a regular expression. So:

  * a bundle with no ontology drew NO physical diagram at all, however completely its warehouse had
    been measured — a foreign key needed a concept to exist first;
  * every crow's foot was an AUTHORED claim, so an optional relationship and a mandatory one drew
    identically wherever nobody had thought about participation;
  * a reference whose two columns are spelled differently was unreachable, because a concept-keyed
    entry is written by somebody who already believes the two things are one thing.

The old builder is kept, unwired, in `er_model_from_ontology.py` — it is the ONTOLOGY diagram's
machinery, and that is a different diagram with a different nav entry. Nothing here imports it.

A BUNDLE WITH NO MEASURED ARTIFACT GETS AN EMPTY MODEL AND A REASON — `unavailable`, naming what is
missing and the command that would produce it. NOT the ontology's relationships under a physical
heading. An empty measured model is the correct answer to "what does the warehouse say"; eleven
authored lines is a different question's answer wearing this one's label.

WHERE EACH RENDERED FACT COMES FROM, so nothing on the page is unattributable:
  box               one per `data/references/<stem>.yaml` — the relations the measurer could READ.
                    Not the descriptors it could not, and not the served datasets: this is the
                    physical plane, and a relation the catalog does not have has no physical box.
  column + type     `data/sources/<stem>.yaml#columns[]`, verbatim.
  PK badge          `data/profiles/<stem>.yaml#identity_evidence.key` — the MEASURED key, read and
                    never re-derived. The role is OVERLAID here rather than written back into the
                    descriptor: the descriptor's own note calls `role: value` "the NEUTRAL physical
                    role and not a ruling", and a source file should not claim a role that a
                    measurement, not the catalog, established.
  FK badge          any column named on the `from` side of a measured reference. Same overlay.
  crow's foot       CARDINALITY + PARTICIPATION, measured. The terminal AT a box says how many rows
                    of THAT relation relate to one row of the other: `max` from the measured maximum
                    rows per value, `min` from the measured participation. That is the whole reason
                    the picture is called an ER diagram, and it is the half a key cannot supply —
                    on the reference bundle three references are all one-to-many while one parent
                    has 10 of 74 rows never referenced, another 52,801 of 104,990 and a third 0 of
                    2,517. Keys alone draw all three identically mandatory.
  proof glyph       the measurement itself. `why` carries the denominator in words.
  dangling panel    `references_dangling` — a column that references NOTHING. It CANNOT be a
                    relationship: the renderer drops any line whose endpoint is not a box, with no
                    error and no mark, so emitting it as a line would make it VANISH. It leaves here
                    as a disclosure entry instead.
"""

from __future__ import annotations

import glob
from pathlib import Path

try:
    import yaml
except ImportError:                                                     # pragma: no cover
    yaml = None

# The four classical crow's-foot terminals. `min` decides the inner mark (circle = optional, bar =
# mandatory); `max` decides the outer one (bar = one, crow = many). CLOSED: a value outside this map
# yields no terminal at all, which is an ER diagram that has stopped saying the one thing it exists
# to say — so `unknown_cardinalities` is projected rather than swallowed.
CARDINALITY = {
    "1": {"min": "one", "max": "one", "label": "1"},
    "1..1": {"min": "one", "max": "one", "label": "1"},
    "0..1": {"min": "zero", "max": "one", "label": "0..1"},
    "1..N": {"min": "one", "max": "many", "label": "1..N"},
    "0..N": {"min": "zero", "max": "many", "label": "0..N"},
    "N": {"min": "zero", "max": "many", "label": "N"},
}
KEY_ROLES = ("primary_key", "composite_key_part", "foreign_key")

PROVED, DISPROVED, UNPROVED, UNRESOLVED, DEFERRED = (
    "proved", "disproved", "unproved", "unresolved", "deferred")

REFS_DIR = "data/references"
#: The command that produces the artifact. Named in the empty state, because "this is missing" is
#: half an answer and the other half is what to run.
PRODUCER = "python3 meaning-as-code/tools/mac_references.py <bundle root>"


def _load(path: Path) -> dict:
    if yaml is None:                                                    # pragma: no cover
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:                                                   # noqa: BLE001
        return {}


# ---- CARDINALITY + PARTICIPATION -> one closed-vocabulary string per end -------------------------
# The artifact speaks MEASUREMENT (one/many, mandatory/optional); this speaks DIAGRAM. Keeping the
# two vocabularies apart is deliberate: "0..N" is a notation, and a measurer that emitted it would be
# deciding how the picture reads.
#
# WHICH END GETS WHICH. The terminal drawn at entity X states the multiplicity of X. So:
#   the CHILD end (the FK carrier) gets `cardinality.child` for its max — one parent row has many
#     child rows — and `participation.parent` for its min: if some parent rows are referenced by NO
#     child row, the child end is OPTIONAL (0..N), else MANDATORY (1..N).
#   the PARENT end gets `cardinality.parent` for its max — an identity key matches one row, a key
#     PART matches a value set — and `participation.child` for its min: if some child rows carry no
#     value, the parent end is optional (0..1).
_MAX = {"one": ("1", "0..1"), "many": ("1..N", "0..N")}


def _card(max_word: str, participation: str) -> str | None:
    pair = _MAX.get(str(max_word or ""))
    if pair is None:
        return None
    return pair[0] if participation == "mandatory" else pair[1]


def _proof_of(e: dict) -> dict:
    """A measured reference's own numbers, as the five-state proof channel the view already draws.

    It is PROVED because it was MEASURED — the `why` carries the denominator in words, so a reader
    who clicks the line gets the arithmetic and not an adjective. A reference the measurer could not
    put a denominator under is `unproved` and says which number is missing; nothing here invents one.
    """
    ev = e.get("evidence") or {}
    nn, orph = ev.get("child_nonnull"), ev.get("orphan_rows")
    if nn is None or orph is None:
        return {"state": UNPROVED, "ref": f"{REFS_DIR}/{e['from']['relation']}.yaml#{e.get('id')}",
                "why": "the measurement carries no child_nonnull/orphan_rows denominator",
                "members": 1, "members_proved": 0}
    why = (f"{nn - orph:,} of {nn:,} row(s) matched, {orph:,} orphan row(s) over "
           f"{ev.get('orphan_distinct', 0):,} orphan value(s)")
    part = e.get("participation") or {}
    if part.get("parent_unreferenced"):
        why += (f"; {part['parent_unreferenced']:,} of {ev.get('parent_distinct', 0):,} parent key "
                f"value(s) are referenced by NO row — participation, not cardinality")
    if e.get("ambiguous_with"):
        why += (f"; AMBIGUOUS — {', '.join(e['ambiguous_with'])} measure(s) identically and value "
                f"inclusion cannot separate them. Neither is chosen; this needs a ruling")
    return {"state": PROVED, "ref": f"{REFS_DIR}/{e['from']['relation']}.yaml#{e.get('id')}",
            "why": why, "members": 1, "members_proved": 1,
            "numbers": {k: v for k, v in ev.items() if isinstance(v, (int, float))}}


def _entities(root: Path, refs: dict, fk_columns: dict) -> list:
    """One box per MEASURED relation, with the descriptor's columns and the profile's key."""
    out = []
    for stem in sorted(refs):
        src = _load(root / "data" / "sources" / f"{stem}.yaml")
        prof = _load(root / "data" / "profiles" / f"{stem}.yaml")
        key = list(((prof.get("identity_evidence") or {}).get("key")) or [])
        keyset = set(key)
        fks = fk_columns.get(stem, set())
        cols = []
        for c in src.get("columns") or []:
            name = c.get("name")
            # THE ROLE IS OVERLAID, NOT WRITTEN BACK. See the module header: the descriptor's own
            # note calls `role: value` the neutral physical role and not a ruling, and the key was
            # established by a MEASUREMENT rather than by the catalog. Writing it into the file
            # would also move the data-plane approval digest for a fact no engine can observe.
            if name in keyset:
                role = "primary_key" if len(key) == 1 else "composite_key_part"
            elif name in fks:
                role = "foreign_key"
            else:
                role = c.get("role") or "value"
            cols.append({"name": name, "type": c.get("type"), "role": role,
                         "key": role in KEY_ROLES, "description": c.get("description")})
        out.append({
            "id": stem,
            "stem": stem,
            "title": (refs[stem].get("relation") or stem).split(".")[-1],
            "relation": refs[stem].get("relation"),
            "columns": cols,
            "keys": list(key),
        })
    return out


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
            continue
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    groups: dict[str, list[str]] = {}
    for e in entities:
        groups.setdefault(find(e["id"]), []).append(e["id"])
    return sorted((sorted(g) for g in groups.values()), key=lambda g: (-len(g), g[0]))


def _unavailable(root, reason: str) -> dict:
    """The honest empty state. An empty model that SAYS WHY, never the other plane's data."""
    return {
        "plane": "physical",
        "entities": [], "relationships": [], "unrealised_edges": [], "components": [],
        "counts": {"entities": 0, "relationships": 0, "physical": 0, "business": 0,
                   "concept_edges": 0, "concept_edges_total": 0, "with_cardinality": 0,
                   "components": 0, "isolated_entities": 0,
                   "proved": 0, "not_proved": 0, "disproved": 0},
        "accounting_error": "",
        "unknown_cardinalities": [],
        "duplicate_ids": [],
        "unavailable": {
            "reason": reason,
            "how": PRODUCER,
            "note": ("This diagram is the PHYSICAL plane and is measured from the warehouse through "
                     "the connector seam. It does not fall back to ontology/edges.yaml: an ontology "
                     "edge relates business objects, not relations and columns, and drawing one "
                     "under a physical heading is the conflation this view was rebuilt to remove. "
                     "The ontology's relationships are a DIFFERENT diagram."),
        },
    }


def build(root=None, **_legacy) -> dict:
    """The measured physical ER model for a bundle root, or an explicitly-empty one with a reason.

    `**_legacy` swallows the old ontology-era positional arguments if any caller still passes them:
    they are NOT read, and a caller that supplies `ont_edges` gets a physical model built without it
    rather than a silent ontology diagram.
    """
    if not root:
        return _unavailable(root, "no bundle root was supplied to the projector, so the measured "
                                  "reference artifact could not be located")
    root = Path(root)
    files = sorted(glob.glob(str(root / REFS_DIR / "*.yaml")))
    if not files:
        n_src = len(glob.glob(str(root / "data" / "sources" / "*.yaml")))
        return _unavailable(
            root,
            f"this bundle carries NO measured reference artifact: {REFS_DIR}/ holds no file, over "
            f"{n_src} declared source relation(s). Nothing has measured how its relations point at "
            f"each other, so this diagram has nothing to draw and will not borrow another plane's "
            f"relationships to fill the page")

    refs, entries, dangling = {}, [], []
    for fp in files:
        doc = _load(Path(fp))
        stem = doc.get("of") or Path(fp).stem
        refs[stem] = doc
        entries += [e for e in (doc.get("references") or []) if e.get("drawn")]
        dangling += list(doc.get("references_dangling") or [])

    fk_columns: dict[str, set] = {}
    for e in entries:
        fk_columns.setdefault(e["from"]["relation"], set()).add(e["from"]["column"])
    entities = _entities(root, refs, fk_columns)
    by_id = {e["id"] for e in entities}

    rels, unknown = [], set()
    for e in sorted(entries, key=lambda x: str(x.get("id"))):
        fe, te = e["from"]["relation"], e["to"]["relation"]
        card, part = e.get("cardinality") or {}, e.get("participation") or {}
        fc = _card(card.get("child"), part.get("parent"))
        tc = _card(card.get("parent"), part.get("child"))
        for c in (fc, tc):
            if c is None:
                unknown.add(f"{e.get('id')}: cardinality {card} + participation {part}")
        if fe not in by_id or te not in by_id:
            # A LINE WITH NO BOX DOES NOT DRAW AND DOES NOT WARN — the renderer returns null for it
            # with no error and no callback. So it is DISCLOSED here instead of emitted as a
            # relationship that would silently vanish.
            dangling.append({
                "id": e.get("id"),
                "from": e.get("from"), "to": e.get("to"),
                "verdict": "unresolved_endpoint",
                "basis": "entity_population",
                "evidence": e.get("evidence") or {},
                "note": (f"one of its endpoints ({fe} -> {te}) is not a measured relation in this "
                         f"bundle, so this diagram has no box for it. Drawn as a line it would "
                         f"disappear without a mark, so it is reported here instead"),
            })
            continue
        rels.append({
            "id": e.get("id"),
            "level": "physical",
            "from": {"entity": fe, "columns": [e["from"]["column"]],
                     "cardinality": fc, "crow": CARDINALITY.get(str(fc))},
            "to": {"entity": te, "columns": [e["to"]["column"]],
                   "cardinality": tc, "crow": CARDINALITY.get(str(tc))},
            # The columns the line joins, for the click detail bar. A pair of {relation, column}
            # rendered for a human to read — NOT a field anything parses. That direction is the
            # whole point: the payload carries the columns as fields and renders the sentence.
            "join_rule": f"{fe}.{e['from']['column']} = {te}.{e['to']['column']}",
            "parent_key_role": e.get("parent_key_role"),
            "name_match": e.get("name_match"),
            "ambiguous_with": e.get("ambiguous_with") or [],
            "needs_ruling": e.get("needs_ruling"),
            "participation": part,
            "proof": _proof_of(e),
            "confidence": "C",
            "realized_by": [],
        })

    undrawable = []
    for d in sorted(dangling, key=lambda x: str(x.get("id"))):
        frm = d.get("from") or {}
        ev = d.get("evidence") or {}
        also = ev.get("also_carried_by") or []
        reason = d.get("note") or ""
        if d.get("verdict") == "dangling":
            reason = (
                f"{frm.get('relation')}.{frm.get('column')} carries "
                f"{ev.get('child_distinct', '?')} distinct value(s) and NO relation in this bundle "
                f"has it as a key column"
                + (f" (also carried by {', '.join(a['relation'] for a in also)})" if also else "")
                + f". {d.get('basis_detail') or ''}")
        undrawable.append({
            "id": d.get("id"),
            "from_relation": frm.get("relation"),
            "from_columns": [frm.get("column")] if frm.get("column") else [],
            "to_relation": (d.get("to") or {}).get("relation") if d.get("to") else None,
            "to_columns": [(d.get("to") or {}).get("column")] if d.get("to") else [],
            "verdict": d.get("verdict"),
            "confidence": "C" if d.get("verdict") == "unresolved_endpoint" else "I",
            "reason": " ".join(str(reason).split()),
            # A dangling reference is measured EVIDENCE about the columns and a self-calibrated
            # INFERENCE about the missing parent — weaker than a reference that could be measured
            # against one, because there is no parent to measure against. It must not draw as proved.
            "proof": {"state": UNPROVED if d.get("verdict") == "dangling" else UNRESOLVED,
                      "ref": f"{REFS_DIR}/{frm.get('relation')}.yaml#{d.get('id')}",
                      "why": (d.get("basis_detail") or d.get("note") or ""),
                      "members": 1, "members_proved": 0},
        })

    comps = _components(entities, rels)
    ids = [r["id"] for r in rels]
    return {
        # THE DISCRIMINATOR. One field, read by the three places the view still has to choose a word.
        "plane": "physical",
        "entities": entities,
        "relationships": rels,
        # Named rather than skipped: a reference this diagram cannot draw is a fact about the
        # warehouse, and silence about it is the absence-as-completeness defect.
        "unrealised_edges": undrawable,
        "components": comps,
        "counts": {
            "entities": len(entities),
            "relationships": len(rels),
            "physical": len(rels),
            "business": 0,
            # Held at zero so the header's ontology sentence cannot render. There are no concept
            # edges on this plane — that is the point — and the field travels as an explicit 0
            # rather than being omitted, because an omitted count paints an amber "unknown".
            "concept_edges": 0,
            "concept_edges_total": 0,
            "concept_edges_undrawable": 0,
            "with_cardinality": sum(1 for r in rels if r["from"]["crow"] and r["to"]["crow"]),
            "components": len(comps),
            "isolated_entities": len([
                e for e in entities
                if not any(e["id"] in (r["from"]["entity"], r["to"]["entity"]) for r in rels)]),
            "references_measured": sum(len(d.get("references") or []) for d in refs.values()),
            "candidates_rejected": sum(len(d.get("candidates_rejected") or [])
                                       for d in refs.values()),
            "ambiguous": sum(1 for r in rels if r["ambiguous_with"]),
            "dangling": len(undrawable),
            # PRESENT INTEGERS, ALWAYS. An omitted `not_proved` paints "proof state unknown — re-run
            # the projector" over a fully measured diagram.
            "proved": sum(1 for r in rels if r["proof"]["state"] == PROVED),
            "not_proved": sum(1 for r in rels if r["proof"]["state"] != PROVED),
            "disproved": sum(1 for r in rels if r["proof"]["state"] == DISPROVED),
        },
        # Every drawn reference in the artifact must leave here as a line or as a disclosure entry.
        "accounting_error": (
            "" if len(rels) + len([u for u in undrawable if u["verdict"] == "unresolved_endpoint"])
            == len(entries)
            else (f"{len(entries)} drawn reference(s) in, {len(rels)} line(s) + "
                  f"{len(undrawable)} disclosed")),
        "unknown_cardinalities": sorted(unknown),
        "duplicate_ids": sorted({i for i in ids if ids.count(i) > 1}),
    }
