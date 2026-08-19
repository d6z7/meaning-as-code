#!/usr/bin/env python3
"""check_rule_reference_basis — a rule that NAMES another concept must have a reason to.

THE QUESTION THIS ANSWERS
-------------------------
Structure and cardinality are already checked: `binds` resolves to real columns
(rule-binds-grounded), pinned literals occur in the register they cite (MAC007), a shape written on
many concepts is reported (COOKBOOK C6). None of that can see whether a rule makes SENSE.

Measured case, gaps/fpl2. `order_intake.resolve.kpi_code` carried
"never confusing Order Intake with ... DtC (deliveries, not placements)". Structurally perfect.
Semantically vacuous: an order PLACED and a car DELIVERED are opposite ends of one lifecycle, and
nobody confuses them. It was machine-written (`provenance: harvested`) and self-stamped
`confidence: C`. Four of seven kpi_code rules warned against confusing something with deliveries —
a template reaching for a foil, not knowledge.

WHAT MAKES A REFERENCE LEGITIMATE
---------------------------------
A rule naming another concept is asserting a RELATIONSHIP with it. That assertion needs a basis the
ontology can show:

    an EDGE between the two                     the relationship is modelled
    THE SAME UNIT                               they measure the same kind of thing, so comparing,
                                                differencing or confusing them is meaningful
    a SHARED SURFACE TERM                       they answer to the same word (the residue the unit
                                                cannot settle — IstProd and DtC are both `vehicles`
                                                and still not confusable)

CO-GROUNDING IS NOT A BASIS, and this is the whole trick. 14 of fpl2's 22 concepts ground on
`v_fpl_kpi`; counting a shared fact table as a relationship makes every pair of measures look related
and hides exactly the case this check exists to find. An earlier cut did count it, and duly missed
the DtC reference that prompted the check.

WHAT IT WOULD FALSELY FIRE ON, and the legitimate case that must not fire
------------------------------------------------------------------------
* A REAL relationship that the edge layer has not modelled yet. LEGITIMATE and common — the first run
  found OBReach -> OrderBook (reach IS a property of the order book) and DtC -> TotalMarket (market
  share is their ratio), neither with an edge. These are findings about the EDGE layer, not about the
  rule, and the diagnostic says so: add the edge, or drop the reference.
* A concept name appearing as an ordinary English word. Guarded by requiring a word-boundary match on
  the concept NAME or its LABEL, not on fragments.
"""
from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

import mac_diag as D

_STOP = {"the", "and", "for", "with", "per", "not", "its"}


def _unit(concept: dict) -> str:
    """The measure's declared unit, normalised. THE PRIMARY BASIS — and it was sitting in
    `semantics.unit` on all 9 fpl2 measures while the first cut of this check scraped German nouns
    out of prose to guess the same thing, badly. MAC declared it; nothing read it."""
    u = ((concept.get("semantics") or {}).get("unit") or "")
    return re.sub(r"[^a-z0-9]", "", str(u).lower())


def _declared_aliases(doc: dict) -> set:
    """Every NL surface the concept DECLARES, from values.aliases.map[*].multilingual — the auditable
    trigger vocabulary (aliasBlock, mac.schema.json:840). Read before the prose heuristic below,
    because a declared surface is evidence and a scraped one is a guess."""
    out = set()
    for spec in (((doc.get("values") or {}).get("aliases") or {}).get("map") or {}).values():
        for arr in ((spec or {}).get("multilingual") or {}).values():
            if isinstance(arr, list):
                out |= {str(t) for t in arr}
        for arr in ((spec or {}).get("scope_relative") or {}).values():
            if isinstance(arr, list):
                out |= {str(t) for t in arr}
    return out


def _surface_terms(concept: dict, doc: dict) -> set:
    """Words this concept answers to: its DECLARED aliases first, then its name, label, german, and —
    only as a fallback — the capitalised German nouns its own prose uses.

    The prose scrape was written with the note "deliberately shallow — until `concept.aliases` exists
    these are scattered". They exist now: gaps/fpl2 declares 38 surfaces across 7 measures, sourced
    from the gold ontology's SME-ratified map. A declared surface is evidence; a scraped one is a
    guess that happened to work, and the scrape is kept only for concepts that declare none."""
    out = _declared_aliases(doc) | {str(concept.get("name") or ""), str(concept.get("label") or ""),
                                    str(concept.get("german") or "")}
    # CONTAINS, not endswith. German compounds put the stem anywhere: `Produktionsantrag` does not
    # end in "produktion" and an endswith filter dropped it, which lost the one overlap that makes
    # IstProd/Prodant a genuine confusion. The first cut of this check reported that real pair as
    # baseless for exactly that reason.
    blob = str(doc)
    for w in re.findall(r"\b([A-ZÄÖÜ][a-zäöüß]{5,})\b", blob):
        if any(s in w.lower() for s in ("bestand", "eingang", "lieferung", "produktion", "anteil")):
            out.add(w)
    return {o.lower() for o in out if o and o.lower() not in _STOP}


def _stems(terms: set) -> set:
    out = set()
    for t in terms:
        out.add(t)
        for s in ("bestand", "eingang", "lieferung", "produktion", "auftrag", "anteil"):
            if s in t:
                out.add(s)
    return out


def check_rule_reference_basis(root) -> list:
    import yaml
    R = Path(root)
    concepts = {}
    for f in sorted(glob.glob(str(R / "ontology" / "concepts" / "*.yaml"))):
        try:
            doc = yaml.safe_load(Path(f).read_text(encoding="utf-8")) or {}
        except Exception:                                               # noqa: BLE001
            continue
        c = doc.get("concept") or {}
        if c.get("name"):
            concepts[c["name"]] = {"doc": doc, "label": c.get("label"), "rel": str(Path(f).name),
                                   "unit": _unit(c),
                                   "surface": _stems(_surface_terms(c, doc))}
    edges = set()
    ef = R / "ontology" / "edges.yaml"
    if ef.exists():
        try:
            for x in ((yaml.safe_load(ef.read_text(encoding="utf-8")) or {}).get("edges") or []):
                ep = x.get("endpoints") or {}
                a, b = (ep.get("from") or {}).get("concept"), (ep.get("to") or {}).get("concept")
                if a and b:
                    edges.add(frozenset((a, b)))
        except Exception:                                               # noqa: BLE001
            pass

    # ── a surface term claimed by more than one code ─────────────────────────────────────────────
    # The aliasBlock contract is "a surface resolving to >1 code => ASK; never a silent bind". So a
    # collision is legal but expensive: every question using that token stalls for a disambiguation.
    # It is invisible without this check, because the two claims sit in two different files and
    # neither knows about the other — the exact cost of holding the map per-concept instead of in one
    # enumeration, and the reason that choice is affordable only with a gate on it.
    claims: dict = {}
    for name, info in concepts.items():
        for code, spec in ((((info["doc"].get("values") or {}).get("aliases") or {}).get("map")) or {}).items():
            for arr in ((spec or {}).get("multilingual") or {}).values():
                if isinstance(arr, list):
                    for term in arr:
                        claims.setdefault(str(term).strip().lower(), set()).add((name, code, info["rel"]))
    collisions = [D.Witness(
        file=f"ontology/concepts/{sorted(v)[0][2]}", path=f"values.aliases.map",
        detail=f"surface `{k}` is claimed by {len(v)} codes: "
               + ", ".join(f"{c} ({n})" for n, c, _ in sorted(v)))
        for k, v in sorted(claims.items()) if len({c for _, c, _ in v}) > 1]

    seen, unbased = set(), []
    for name, info in concepts.items():
        for r in ((info["doc"].get("contract") or {}).get("rules") or []):
            txt = " ".join(str(r.get(k) or "") for k in ("when", "then", "never"))
            for other, oi in concepts.items():
                if other == name:
                    continue
                lbl = oi["label"] or other
                if not (re.search(r"\b" + re.escape(other) + r"\b", txt)
                        or (lbl and re.search(r"\b" + re.escape(lbl) + r"\b", txt))):
                    continue
                key = (name, other, r.get("id"))
                if key in seen:
                    continue
                seen.add(key)
                same_unit = bool(info["unit"]) and info["unit"] == oi["unit"]
                if frozenset((name, other)) in edges or same_unit or (info["surface"] & oi["surface"]):
                    continue
                why = f"units differ ({info['unit'] or '?'} vs {oi['unit'] or '?'})" if (
                    info["unit"] or oi["unit"]) else "neither declares a unit"
                unbased.append(D.Witness(
                    file=f"ontology/concepts/{info['rel']}", path=str(r.get("id")),
                    detail=f"names {other} — no edge, {why}, no shared surface term"))
    out = []
    if collisions:
        out.append(D.Diagnostic(
            code="MAC003", severity=D.WARNING, source="check_rule_reference_basis",
            summary=f"{len(collisions)} alias surface(s) resolve to more than one code",
            note="The aliasBlock contract makes this legal — a surface hitting >1 code means ASK, "
                 "never a silent bind. But every question using that token then stalls for a "
                 "disambiguation, and the two claims live in different files, so nothing but this "
                 "check can see the pair. Either narrow one surface, or accept the ASK deliberately.",
            witnesses=collisions))
    if not unbased:
        return out
    return out + [D.Diagnostic(
        code="MAC008", severity=D.WARNING, source="check_rule_reference_basis",
        summary=f"{len(unbased)} rule reference(s) assert a relationship the ontology does not model",
        note="Each names another concept with no edge between them and no shared surface term. Two "
             "dispositions, and the ontology cannot tell them apart: the relationship is REAL and the "
             "edge layer is missing it (add the edge), or the reference is a machine-written foil "
             "(delete it). Co-grounding is deliberately NOT accepted as a basis — 14 fpl2 concepts "
             "share v_fpl_kpi, which would make every pair look related.",
        witnesses=unbased)]


def main() -> int:                                                      # pragma: no cover
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    d = check_rule_reference_basis(root)
    print(D.render(d, root, show=D.INFO) or "check_rule_reference_basis: no findings")
    return 0


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
