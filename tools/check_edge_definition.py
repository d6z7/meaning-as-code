#!/usr/bin/env python3
"""An edge must be FULLY DEFINED: named, and with a closed cardinality declared at BOTH ends.

    python3 tools/check_edge_definition.py <root> [--json] [--self-test]

WHAT FORCED THIS GATE
---------------------
The grammar declared an `EdgeEndpoint` with five properties and required exactly one of them,
`concept`. So an edge could name the two concepts it relates and promise NOTHING about how many
partners a row finds at either end, and validate. The operator's objection was precise: an edge's
end points are not fully defined without a cardinality, and the fault is in the STANDARD — nothing
told an author, or an agent, that the value was required, so under-specified edges were correct by
the only rule that existed.

`cardinality` being optional was not a documentation gap. It was already being paid for:

  * `tools/mac_to_shacl.py` maps the `to` cardinality to (minCount, maxCount) and DEFAULTS an
    unmapped or absent value to (0, 1). So a relationship nobody constrained ships as SHACL
    asserting `at most one` over it, indistinguishable from a measured claim.
  * `tools/mac_to_mermaid.py` defaults the terminals to `||` and `o{`. So an ER picture draws a
    crow's foot, or a bar, that no author put there and no measurement supports.
  * `sdk/project/er_model.py` is the one reader that handles it honestly — a value outside its map
    yields NO terminal, and `unknown_cardinalities` is projected rather than swallowed.

Two of the three consumers turn an absence into a claim, silently. That is this estate's recurring
defect (absence rendering as completeness) on the surface where a wrong answer is a wrong NUMBER:
the join type a query is rendered with comes from the declared cardinality.

THE VOCABULARY IS CLOSED, AND THE SET IS READ FROM THE GRAMMAR — never restated here. The gate
imports `$defs.EdgeEndpoint` from `mac.schema.json` through the one schema home
(`sdk.grammar.resolve`), so the judge and the standard cannot drift apart. A gate carrying its own
copy of a closed set is the two-homes-for-one-fact shape several gates in this tree exist to undo.

DO NOT CONFLATE THIS VOCABULARY WITH THE PHYSICAL PLANE'S. `data/references/*.yaml` declares
`cardinality: {child, parent}` over the MEASURED words `one`/`many`, checked by
`check_physical_references`. Those are a measurement; these are a notation. `sdk/project/er_model.py`
records why the two are deliberately separate: *"a measurer that emitted `0..N` would be deciding how
the picture reads."* An edge that says `many` has borrowed the other plane's word, and this gate says
so by name.

WHAT IT REFUSES TO DO, each a way to be green for the wrong reason:
  1. never repair an edge. Every write to `ontology/edges.yaml` is the operator's (decision 0018
     §5); this gate produces a finding for a human to act on, never a patched file.
  2. never judge an empty population. No edges file, or a file with no edges, REFUSES with exit 2.
     A PASS over zero edges is the false green that a denominator on every line exists to prevent.
  3. never hold `planned_edges` to the endpoint rules. A planned edge's whole content is that NO
     JOIN EXISTS TO DECLARE, so it carries no endpoints and no cardinality, deliberately. Only
     nameability carries across, because a candidate nothing can name is one nothing can promote.
  4. never silently exempt an endpoint it could not resolve. A `federation` edge may name a concept
     in another source, so those endpoints are excluded from the resolution class — and the count
     excluded is PRINTED, because an exemption nobody can see is a hole.
  5. never widen the closed set to make a bundle pass. `1..1` and `N` are refused deliberately (see
     the schema's own note): both are synonyms of a token already in the set, and both are silently
     mis-rendered rather than rejected by the two projectors above. They are admitted only together
     with the judges that would read them, which is the pending table-link proposal's C5.

THE ERROR CLASSES (exit 1)
    CARDINALITY_MISSING   an endpoint that names its concept and declares no cardinality. THE ONE
                          THE OPERATOR ASKED FOR, and the one the two projectors invent a value for.
    CARDINALITY_CLOSED    a cardinality outside the closed set the grammar declares — including the
                          legal-LOOKING synonyms, and including the physical plane's `one`/`many`.
    EDGE_UNNAMED          an edge with no `edge_id`. An edge nothing can name is an edge nothing can
                          cite: `@join:` dereferences `edge:<edge_id>`, and `protosql_render`'s
                          index DROPS an id-less edge, so the renderer then reports `edge-not-found`
                          and blames the caller for a defect in the edge.
    EDGE_ID_COLLISION     two edges sharing one id. THE SCHEMA CANNOT SEE THIS — JSON Schema has no
                          way to say "unique by this key" — so it exists here or nowhere. The
                          runtime already raises on it; this moves the refusal to where the author is.
    ENDPOINT_SHAPELESS    an `endpoints` block that is not {from, to}, an endpoint that is not a
                          mapping, an endpoint with no `concept`, or an endpoint carrying a key that
                          is not an `EdgeEndpoint` property. A join between stored relations that is
                          not a join between concepts is a pipeline transform, not an ontology edge.
    ENDPOINT_UNRESOLVED   an endpoint naming a concept no concept file in this bundle declares. The
                          edge then reads as wired and reaches nothing.
    PLANNED_UNNAMED       a planned edge with no `edge_id`.

EXIT CODES. 0 clean · 1 a finding about the bundle · 2 could not run (no edges file, an EMPTY
POPULATION, no grammar). Every verdict line carries its denominator.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:                                                        # noqa: E402
    sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mac_diag as D                                                             # noqa: E402
import mac_project as P                                                          # noqa: E402

NAME = "check_edge_definition"

CARDINALITY_MISSING = "CARDINALITY_MISSING"
CARDINALITY_CLOSED = "CARDINALITY_CLOSED"
EDGE_UNNAMED = "EDGE_UNNAMED"
EDGE_ID_COLLISION = "EDGE_ID_COLLISION"
ENDPOINT_SHAPELESS = "ENDPOINT_SHAPELESS"
ENDPOINT_UNRESOLVED = "ENDPOINT_UNRESOLVED"
PLANNED_UNNAMED = "PLANNED_UNNAMED"

#: A `federation` edge relates concepts in DIFFERENT sources, so its endpoints are not expected to
#: resolve in this bundle. Excluded from ENDPOINT_UNRESOLVED and counted out loud.
CROSS_SOURCE_LEVEL = "federation"

#: The physical plane's MEASURED cardinality words. Not interchangeable with this notation, and
#: named here only so the finding can say which plane a value was borrowed from.
MEASURED_WORDS = ("one", "many", "mandatory", "optional")


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE STANDARD IS READ, NOT RESTATED. One home for the closed set and the endpoint's shape: the
# grammar. If it cannot be resolved the gate REFUSES (exit 2) rather than judging against a guess.
# ══════════════════════════════════════════════════════════════════════════════════════════════════
def endpoint_contract(schema: dict | None = None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(the closed cardinality values, the legal EdgeEndpoint keys), both read off mac.schema.json."""
    if schema is None:
        from sdk.grammar.resolve import load_schema                              # noqa: PLC0415
        schema = load_schema()
    ep = (schema.get("$defs") or {}).get("EdgeEndpoint") or {}
    props = ep.get("properties") or {}
    values = tuple((props.get("cardinality") or {}).get("enum") or ())
    if not values:
        raise ValueError(
            "mac.schema.json declares no closed enum for EdgeEndpoint.cardinality. This gate judges "
            "against the grammar and has no second copy to fall back to")
    return values, tuple(props)


class Finding:
    def __init__(self, cls, where, detail):
        self.cls, self.where, self.detail = cls, where, detail

    def __str__(self):
        return f"  [{self.cls:<21}] {self.where}\n          {self.detail}"

    def as_dict(self):
        return {"class": self.cls, "where": self.where, "detail": self.detail}


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE JUDGE — PURE. Free of the filesystem so every branch can be exercised offline with a seeded
# edge dict, the same way protosql_render's join judge and check_edge_joins_measured's judge are.
# ══════════════════════════════════════════════════════════════════════════════════════════════════
def judge(edges: list, planned: list, concepts: set | None,
          values: tuple, keys: tuple) -> tuple[list, dict]:
    """(edges, planned_edges, declared concept names or None, closed set, legal keys) -> findings, counts.

    `concepts` is None when the bundle declares no concept file: the resolution class is then NOT
    JUDGED rather than silently green, and the caller prints that with its denominator.
    """
    findings: list[Finding] = []
    counts = Counter()
    homes: dict[str, list[int]] = defaultdict(list)

    for i, e in enumerate(edges):
        counts["edges"] += 1
        e = e if isinstance(e, dict) else {}
        eid = e.get("edge_id")
        where = f"edges[{i}]" + (f" {eid}" if isinstance(eid, str) and eid.strip() else "")
        if not (isinstance(eid, str) and eid.strip()):
            findings.append(Finding(
                EDGE_UNNAMED, where,
                "carries no `edge_id`. An edge nothing can name is an edge nothing can cite — a "
                "rule, a decision record and `@join:edge:<edge_id>` all refer to an edge by it, and "
                "the renderer's index DROPS an id-less edge, so the refusal surfaces as "
                "`edge-not-found` against the caller instead of against this edge"))
        else:
            homes[eid].append(i)
            counts["named"] += 1

        ep = e.get("endpoints")
        if not isinstance(ep, dict) or set(ep) != {"from", "to"}:
            findings.append(Finding(
                ENDPOINT_SHAPELESS, where,
                f"`endpoints` is {type(ep).__name__} with keys "
                f"{sorted(ep) if isinstance(ep, dict) else '—'}; an edge has exactly two ends, "
                f"`from` and `to`"))
            continue

        for side in ("from", "to"):
            counts["endpoints"] += 1
            w = f"{where}.endpoints.{side}"
            end = ep.get(side)
            if not isinstance(end, dict):
                findings.append(Finding(
                    ENDPOINT_SHAPELESS, w,
                    f"is {type(end).__name__}, not an EdgeEndpoint mapping. An endpoint is a "
                    f"{{{', '.join(keys)}}} object"))
                continue
            extra = sorted(set(end) - set(keys))
            if extra:
                findings.append(Finding(
                    ENDPOINT_SHAPELESS, w,
                    f"carries {extra}, which the grammar's EdgeEndpoint does not declare (legal: "
                    f"{list(keys)}). An endpoint keyed by a stored relation makes this a pipeline "
                    f"transform, not an ontology edge"))
            name = end.get("concept")
            if not (isinstance(name, str) and name.strip()):
                findings.append(Finding(
                    ENDPOINT_SHAPELESS, w,
                    "names no `concept`. An edge endpoint is a CONCEPT, never a raw view or table"))
            elif concepts is not None and e.get("level") != CROSS_SOURCE_LEVEL:
                if name not in concepts:
                    findings.append(Finding(
                        ENDPOINT_UNRESOLVED, w,
                        f"names concept {name!r}, which no concept file in this bundle declares "
                        f"({len(concepts)} declared). The edge reads as wired and reaches nothing"))
                else:
                    counts["endpoints_resolved"] += 1
            elif e.get("level") == CROSS_SOURCE_LEVEL:
                counts["endpoints_cross_source"] += 1

            card = end.get("cardinality")
            if card is None or (isinstance(card, str) and not card.strip()):
                findings.append(Finding(
                    CARDINALITY_MISSING, w,
                    f"declares no cardinality. An end point that promises nothing about how many "
                    f"partners a row finds is half an endpoint — and the projectors supply the "
                    f"other half themselves: mac_to_shacl ships (minCount 0, maxCount 1) and "
                    f"mac_to_mermaid draws a terminal, neither of which anybody authored. Declare "
                    f"one of {list(values)}, and CITE the measurement that says which"))
            elif str(card) not in values:
                borrowed = (" That is the PHYSICAL plane's measured word (data/references/*.yaml "
                            "speaks one/many over child/parent); this plane declares a notation, and "
                            "the two are deliberately not interchangeable."
                            if str(card).strip().lower() in MEASURED_WORDS else "")
                findings.append(Finding(
                    CARDINALITY_CLOSED, w,
                    f"cardinality is {card!r}, outside the closed set {list(values)} the grammar "
                    f"declares.{borrowed} A value nothing maps is not refused by the projectors — "
                    f"each falls back to its own default, so the drawn picture and the SHACL shape "
                    f"disagree about one edge with no error anywhere"))
            else:
                counts["cardinality_closed"] += 1

    for eid, at in sorted(homes.items()):
        if len(at) > 1:
            findings.append(Finding(
                EDGE_ID_COLLISION, eid,
                f"is the id of {len(at)} edges (at {at}). THE SCHEMA CANNOT SEE THIS — JSON Schema "
                f"cannot require uniqueness by a key — so an id-keyed reader silently keeps one and "
                f"discards the rest: `@join:` would resolve to whichever won, and the other edge "
                f"reads as declared while being unreachable"))

    for i, pe in enumerate(planned):
        counts["planned"] += 1
        pe = pe if isinstance(pe, dict) else {}
        pid = pe.get("edge_id")
        if not (isinstance(pid, str) and pid.strip()):
            findings.append(Finding(
                PLANNED_UNNAMED, f"planned_edges[{i}]",
                "carries no `edge_id`. The ENDPOINT rules deliberately stop at `edges[]` — a "
                "planned edge's content is that NO JOIN EXISTS to declare — but nameability does "
                "not: a candidate nothing can name is one nothing can promote, and the decision "
                "that promotes it could not say which one it promoted"))
        else:
            counts["planned_named"] += 1

    return findings, dict(counts)


def _load(p: Path):
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}, None
    except Exception as exc:                                                     # noqa: BLE001
        return {}, str(exc)


def concept_names(root: Path) -> set:
    """Declared concept names, through the LAYOUT RESOLVER — flat and foldered bundles alike.

    A hand-rolled `ontology/concepts/*.yaml` glob finds nothing on a foldered bundle and the gate
    would then report every endpoint unresolved, or (worse) exempt them all.
    """
    out = set()
    for f in P.concept_files(root):
        d, _err = _load(f)
        n = ((d.get("concept") or {}) if isinstance(d, dict) else {}).get("name")
        if isinstance(n, str) and n.strip():
            out.add(n)
    return out


def check(root: Path, schema: dict | None = None):
    values, keys = endpoint_contract(schema)
    f = P.resolve(root).ontology / "edges.yaml"
    if not f.exists():
        return None, None, f, values, keys
    doc, err = _load(f)
    if err:
        return [Finding(ENDPOINT_SHAPELESS, P.rel(root, f), f"is not readable YAML: {err}")], \
            {"edges": 0}, f, values, keys
    edges = doc.get("edges") or []
    if not edges:
        return None, None, f, values, keys
    declared = concept_names(root)
    findings, counts = judge(edges, doc.get("planned_edges") or [],
                             declared if declared else None, values, keys)
    counts["concepts_declared"] = len(declared)
    return findings, counts, f, values, keys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    if not a.root:
        ap.error("a bundle root is required")
    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"could not run: {root} is not a directory", file=sys.stderr)
        return 2
    try:
        findings, counts, f, values, _keys = check(root)
    except Exception as exc:                                                     # noqa: BLE001
        print(f"could not run: {exc}", file=sys.stderr)
        return 2

    if findings is None:
        # NO EDGES IS NOT A PASS. A bundle with no relationships has declared none, and a gate that
        # printed the same line as one judging 49 of them would be reporting absence as compliance.
        if a.json:
            print(json.dumps({"state": "no-edges", "measured_nothing": True,
                              "edges_file": str(f)}, indent=1))
            return D.EMPTY_EXIT
        return D.refuse_empty(NAME, f, unit="edge")

    by_class = dict(sorted(Counter(x.cls for x in findings).items()))
    if a.json:
        print(json.dumps({"closed_set": list(values), "counts": counts,
                          "by_class": by_class,
                          "findings": [x.as_dict() for x in findings],
                          "exit": 1 if findings else 0}, indent=1, ensure_ascii=False))
        return 1 if findings else 0

    for x in findings:
        print(x)

    # THE RESOLUTION CLASS, WITH ITS DENOMINATOR OR NOT AT ALL. A bundle with no concept files
    # cannot have its endpoints resolved; saying nothing would read as "they all resolved".
    if not counts.get("concepts_declared"):
        print(f"  [not judged] endpoint resolution: 0 concept file(s) declared under "
              f"{P.rel(root, P.concepts_dir(root))}/ — {counts.get('endpoints', 0)} endpoint(s) "
              f"were checked for shape and cardinality only. A bundle whose concepts cannot be "
              f"found has not had its endpoints resolved, and silence here would read as though "
              f"they all had")
    if counts.get("endpoints_cross_source"):
        print(f"  [excluded] {counts['endpoints_cross_source']} of {counts.get('endpoints', 0)} "
              f"endpoint(s) are on `{CROSS_SOURCE_LEVEL}` edges and name concepts in another "
              f"source, so they are not resolved against this bundle's "
              f"{counts.get('concepts_declared', 0)} concept(s)")

    tail = (f"{counts.get('cardinality_closed', 0)} of {counts.get('endpoints', 0)} endpoint(s) "
            f"declare a cardinality from the closed set {list(values)}; "
            f"{counts.get('named', 0)} of {counts.get('edges', 0)} edge(s) named; "
            f"{counts.get('endpoints_resolved', 0)} of {counts.get('endpoints', 0)} endpoint(s) "
            f"resolve to one of {counts.get('concepts_declared', 0)} declared concept(s); "
            f"{counts.get('planned_named', 0)} of {counts.get('planned', 0)} planned edge(s) named "
            f"(the endpoint rules do not apply to those)")
    if findings:
        print(f"FAIL: {NAME} — {len(findings)} finding(s) {by_class} — {tail}")
        return 1
    print(f"PASS: {NAME} — {tail}")
    return 0


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# --self-test — ONE MUTANT PER REJECT CLASS, attributed by class name, plus the negative controls.
# Synthetic names only (alpha/beta/gamma); no bundle, no warehouse, no network.
# ══════════════════════════════════════════════════════════════════════════════════════════════════
_SCHEMA_STUB = {"$defs": {"EdgeEndpoint": {"properties": {
    "source": {}, "concept": {}, "ref": {}, "role": {},
    "cardinality": {"enum": ["1", "0..1", "1..N", "0..N"]}}}}}

_CLEAN = {
    "edge_id": "alpha__to__beta",
    "level": "physical",
    "type": "foreign_key",
    "endpoints": {"from": {"concept": "Alpha", "cardinality": "0..N"},
                  "to": {"concept": "Beta", "cardinality": "1"}},
    "join_rule": "alpha.beta_key = beta.beta_key",
    "verified_by": "data/expectations/alpha__to__beta.yaml",
}
_CONCEPTS = {"Alpha", "Beta", "Gamma"}


def _j(edges, planned=(), concepts=_CONCEPTS):
    values, keys = endpoint_contract(_SCHEMA_STUB)
    return judge(list(edges), list(planned), concepts, values, keys)


def _mutate(**kw):
    import copy
    e = copy.deepcopy(_CLEAN)
    for k, v in kw.items():
        if k == "drop":
            e.pop(v, None)
        elif k.startswith("to_"):
            e["endpoints"]["to"][k[3:]] = v
        elif k.startswith("from_"):
            e["endpoints"]["from"][k[5:]] = v
        else:
            e[k] = v
    return e


def _self_test() -> int:
    import copy
    import subprocess
    import tempfile

    bad, cases = [], []

    def case(label, ok, why=""):
        cases.append(label)
        if not ok:
            bad.append(f"{label}: {why}")

    def expect(label, edges, want_class, planned=(), concepts=_CONCEPTS, n=1):
        f, _c = _j(edges, planned, concepts)
        got = sorted(Counter(x.cls for x in f).items())
        ok = len(f) == n and all(x.cls == want_class for x in f)
        case(label, ok, f"findings {got} (wanted {n}x {want_class})")

    # ── NEGATIVE CONTROLS ─────────────────────────────────────────────────────────────────────────
    f, c = _j([_CLEAN])
    case("NEGATIVE CONTROL a fully-specified edge passes", not f, f"{[x.cls for x in f]}")
    case("NEGATIVE CONTROL the clean edge counts 2 closed cardinalities of 2 endpoints",
         c.get("cardinality_closed") == 2 and c.get("endpoints") == 2 and c.get("named") == 1, c)
    case("NEGATIVE CONTROL the closed set is READ FROM THE GRAMMAR, not restated here",
         endpoint_contract(_SCHEMA_STUB)[0] == ("1", "0..1", "1..N", "0..N"),
         endpoint_contract(_SCHEMA_STUB)[0])
    f, _c = _j([_mutate(edge_id="alpha__to__gamma", to_concept="Gamma", to_cardinality="1..N"),
                _mutate(edge_id="beta__to__gamma", from_concept="Beta", to_concept="Gamma",
                        from_cardinality="0..1", to_cardinality="0..N")])
    case("NEGATIVE CONTROL every value in the closed set passes", not f, f"{[x.cls for x in f]}")

    # ── ONE MUTANT PER REJECT CLASS ───────────────────────────────────────────────────────────────
    nocard = _mutate()
    nocard["endpoints"]["to"].pop("cardinality")
    expect("MUTANT an endpoint with no cardinality is CARDINALITY_MISSING",
           [nocard], CARDINALITY_MISSING)
    expect("MUTANT an endpoint with an EMPTY cardinality is CARDINALITY_MISSING (not closed-set)",
           [_mutate(to_cardinality="  ")], CARDINALITY_MISSING)
    expect("MUTANT a cardinality of `many` is CARDINALITY_CLOSED",
           [_mutate(to_cardinality="many")], CARDINALITY_CLOSED)
    expect("MUTANT a cardinality of `*` is CARDINALITY_CLOSED",
           [_mutate(from_cardinality="*")], CARDINALITY_CLOSED)
    expect("MUTANT the legal-LOOKING synonym `1..1` is CARDINALITY_CLOSED",
           [_mutate(to_cardinality="1..1")], CARDINALITY_CLOSED)
    expect("MUTANT the legal-LOOKING synonym `N` is CARDINALITY_CLOSED",
           [_mutate(to_cardinality="N")], CARDINALITY_CLOSED)
    f, _c = _j([_mutate(to_cardinality="many")])
    case("MUTANT the `many` finding NAMES the physical plane it was borrowed from",
         "PHYSICAL plane's measured word" in f[0].detail, f[0].detail[:120])
    noid = _mutate()
    noid.pop("edge_id")
    expect("MUTANT an edge with no edge_id is EDGE_UNNAMED", [noid], EDGE_UNNAMED)
    expect("MUTANT an edge whose edge_id is blank is EDGE_UNNAMED",
           [_mutate(edge_id="   ")], EDGE_UNNAMED)
    expect("MUTANT two edges sharing an id is EDGE_ID_COLLISION",
           [_CLEAN, copy.deepcopy(_CLEAN)], EDGE_ID_COLLISION)
    expect("MUTANT an endpoint naming an undeclared concept is ENDPOINT_UNRESOLVED",
           [_mutate(to_concept="Omega")], ENDPOINT_UNRESOLVED)
    expect("MUTANT an endpoint that is not a mapping at all is ENDPOINT_SHAPELESS",
           [_mutate(endpoints={"from": {"concept": "Alpha", "cardinality": "0..N"},
                               "to": "Beta"})], ENDPOINT_SHAPELESS)
    expect("MUTANT an endpoint keyed BY RELATION is ENDPOINT_SHAPELESS",
           [_mutate(to_relation="raw.beta")], ENDPOINT_SHAPELESS)
    expect("MUTANT an endpoint with no concept is ENDPOINT_SHAPELESS",
           [_mutate(endpoints={"from": {"concept": "Alpha", "cardinality": "0..N"},
                               "to": {"ref": "beta.yaml#concept", "cardinality": "1"}})],
           ENDPOINT_SHAPELESS)
    expect("MUTANT an endpoints block with three ends is ENDPOINT_SHAPELESS",
           [_mutate(endpoints={"from": {"concept": "Alpha", "cardinality": "0..N"},
                               "to": {"concept": "Beta", "cardinality": "1"},
                               "via": {"concept": "Gamma", "cardinality": "1"}})],
           ENDPOINT_SHAPELESS)
    expect("MUTANT a planned edge with no edge_id is PLANNED_UNNAMED", [_CLEAN],
           PLANNED_UNNAMED, planned=[{"status": "planned", "blocked_by": "no served gamma"}])

    # ── THE EXEMPTIONS AND THE ABSTENTIONS, EACH SEEDED ───────────────────────────────────────────
    f, c = _j([_CLEAN], planned=[{"edge_id": "gamma__in__delta", "status": "planned"}])
    case("NEGATIVE CONTROL a planned edge with NO endpoints and no cardinality passes — the "
         "endpoint rules stop at edges[]",
         not f and c.get("planned_named") == 1 and c.get("planned") == 1,
         f"{[x.cls for x in f]} {c}")
    f, c = _j([_mutate(level="federation", to_concept="Omega")])
    case("NEGATIVE CONTROL a federation endpoint naming another source's concept is EXEMPT, and "
         "the exemption is COUNTED",
         not f and c.get("endpoints_cross_source") == 2, f"{[x.cls for x in f]} {c}")
    f, c = _j([_mutate(to_concept="Omega")], concepts=None)
    case("MUTANT with NO concept files the resolution class is NOT JUDGED, not silently green",
         not f and c.get("endpoints_resolved", 0) == 0, f"{[x.cls for x in f]} {c}")

    # ── TWO CLASSES ON ONE ENDPOINT ARE TWO FINDINGS, not one collapsed into the other ────────────
    f, _c = _j([_mutate(to_concept="Omega", to_cardinality="many")])
    case("MUTANT a wrong concept AND a wrong cardinality on one endpoint is TWO findings",
         sorted(x.cls for x in f) == [CARDINALITY_CLOSED, ENDPOINT_UNRESOLVED],
         sorted(x.cls for x in f))

    # ── THE GRAMMAR IS NOT OPTIONAL ───────────────────────────────────────────────────────────────
    try:
        endpoint_contract({"$defs": {"EdgeEndpoint": {"properties": {"cardinality": {}}}}})
        case("MUTANT a grammar with no closed enum RAISES rather than judging against a guess",
             False, "it returned instead of raising")
    except ValueError:
        case("MUTANT a grammar with no closed enum RAISES rather than judging against a guess", True)

    # ── END TO END over a seeded bundle on disk: the PASS line, its denominators, the refusals ────
    def _seed(root: Path, edges, planned=None, concepts=("Alpha", "Beta"), omit_edges=False):
        (root / "ontology" / "concepts").mkdir(parents=True, exist_ok=True)
        # A MANIFEST, because the gate finds the edges file through the layout resolver and a
        # fixture with no manifest would exercise the flat branch that no real bundle uses.
        (root / "mac.project.yaml").write_text(yaml.safe_dump(
            {"metadata": {"project": "selftest"},
             "planes": {"ontology": "ontology", "data": "data"}}, sort_keys=False),
            encoding="utf-8")
        for n in concepts:
            (root / "ontology" / "concepts" / f"{n.lower()}.yaml").write_text(
                yaml.safe_dump({"concept": {"name": n, "class": "entity"}}, sort_keys=False),
                encoding="utf-8")
        if not omit_edges:
            doc = {"metadata": {"source": "SELFTEST"}, "edges": edges}
            if planned is not None:
                doc["planned_edges"] = planned
            (root / "ontology" / "edges.yaml").write_text(
                yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        return root

    def _run(root, *args):
        p = subprocess.run([sys.executable, os.path.abspath(__file__), str(root), *args],
                           capture_output=True, text=True)
        return p.returncode, p.stdout + p.stderr

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        rc, out = _run(_seed(base / "clean", [_CLEAN],
                             planned=[{"edge_id": "gamma__in__delta"}]))
        case("END TO END a clean bundle exits 0 with a PASS line",
             rc == 0 and "PASS: check_edge_definition" in out, f"exit {rc}: {out.strip()[-200:]}")
        case("END TO END the PASS line carries EVERY denominator",
             "2 of 2 endpoint(s) declare a cardinality" in out
             and "1 of 1 edge(s) named" in out
             and "2 of 2 endpoint(s) resolve" in out
             and "1 of 1 planned edge(s) named" in out, out.strip()[-320:])
        rc, out = _run(_seed(base / "nocard", [nocard]))
        case("END TO END a missing cardinality exits 1 and names its class",
             rc == 1 and CARDINALITY_MISSING in out, f"exit {rc}: {out.strip()[-200:]}")
        rc, out = _run(_seed(base / "empty", []))
        case("END TO END a file with zero edges REFUSES (exit 2), verbatim marker",
             rc == D.EMPTY_EXIT and D.empty_mark("edge") in out, f"exit {rc}: {out.strip()[-200:]}")
        rc, out = _run(_seed(base / "noedges", [], omit_edges=True))
        case("END TO END no edges file at all REFUSES (exit 2), not PASS",
             rc == D.EMPTY_EXIT and D.empty_mark("edge") in out, f"exit {rc}: {out.strip()[-200:]}")
        rc, out = _run(base / "not-a-directory-at-all")
        case("END TO END a root that is not a directory could-not-run (exit 2)", rc == 2,
             f"exit {rc}")
        ok_json = True
        for r in (base / "clean", base / "nocard", base / "empty", base / "noedges"):
            _rc, o = _run(r, "--json")
            try:
                json.loads(o)
            except Exception:                                                    # noqa: BLE001
                ok_json = False
        case("END TO END --json parses on every state, refusal included", ok_json)

    total = len(cases)
    if bad:
        print(f"FAIL: {NAME} self-test — {len(bad)} of {total} case(s) failed")
        for b in bad:
            print(f"  ✗ {b}", file=sys.stderr)
        return 1
    mut = len([c for c in cases if c.startswith("MUTANT")])
    neg = len([c for c in cases if "NEGATIVE CONTROL" in c])
    e2e = len([c for c in cases if c.startswith("END TO END")])
    print(f"PASS: {NAME} self-test — {total}/{total} case(s): {mut} mutant(s) covering all 7 reject "
          f"class(es) (no cardinality, an empty cardinality, `many`, `*`, the synonyms `1..1` and "
          f"`N`, a borrowed-plane message, no edge_id, a blank edge_id, two edges sharing an id, an "
          f"undeclared concept, an endpoint that is not a mapping, an endpoint keyed by relation, an "
          f"endpoint with no concept, three ends, a planned edge with no id, a bundle with no "
          f"concept files, two classes on one endpoint, a grammar with no closed enum), {neg} "
          f"negative control(s) (a fully-specified edge, its counts, the set read from the grammar, "
          f"every value in the set, a planned edge with no endpoints, a counted federation "
          f"exemption) and {e2e} end-to-end case(s) (PASS with every denominator, a finding, zero "
          f"edges, no edges file, a non-directory root, --json on every state)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
