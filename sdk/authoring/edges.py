#!/usr/bin/env python3
"""sdk.authoring.edges — derive ontology EDGES (relationships between concepts) from the data
transformation layer, validated against the MAC grammar (EdgesFile).

The concept harvest authors one concept per produced dataset. This module then LIFTS the data
layer's declared foreign_keys into semantic PHYSICAL edges between the concepts those datasets
realise — endpoints are CONCEPTS (never raw views), as the grammar requires. Each edge is
validated individually against mac.schema.json#EdgesFile; only grammar-clean edges are kept, and
the assembled EdgesFile is validated as a whole before persistence (via operations.persist_edges).

Physical `foreign_key` edges are generatable deterministically and grounded (they ARE the real
joins). Business (identity / shared_attribute) and federation edges additionally require
`realized_by` / `resolved_by` rule anchors — those are a follow-up layer, noted but not fabricated
here (an edge without a real anchor would fail the grammar, and we never write a lie).

CARDINALITY IS DECLARED AND NOT INVENTED (v0.1.18). The grammar now requires a cardinality at both
ends, so this generator MUST emit one — and it has measured nothing, so the only value it may write
is the one that CLAIMS NOTHING: `0..N` at both ends. That is the same rule as the paragraph above,
applied to a number instead of to an anchor. Sharpening an end to `1` or `0..1` is a MEASUREMENT
(`check_edge_joins_measured` / `mac_measure_edges` prove containment and fan-out, and the verdict is
cited in `verified_by`), never a guess a generator is entitled to make: a declared `1` whose
containment turns out partial is REFUSED at render time rather than quietly downgraded, so an
optimistic default here would manufacture refusals from data nobody had looked at. An explicit
`0..N` is strictly more than the absence it replaces — absence was indistinguishable from ignorance,
and `check_edge_claims_proved` now reports these as claiming-but-unproved rather than silently
skipping them.
"""

from __future__ import annotations

from sdk.authoring.authoring import schema_generation

from pathlib import Path

from jsonschema import validators as jsv

_ROOT = Path(__file__).resolve().parent.parent
from sdk.grammar.resolve import load_schema as _load_schema  # ONE schema home

#: THE ONE READER OF A COLUMN'S IDENTITY. `concept_index` chose BOTH endpoints of every physical edge
#: from the flat `identity:` key and from `concept.identity.canonical_key`, and both addresses are
#: gone — the first into `roles: {identity: ...}` on 2026-10-07 MORNING, the second out of
#: mac.schema.json entirely on 2026-10-05. The FIRST address itself then moved again that SAME
#: AFTERNOON, column_declaration.md rev 5: `identity` left `roles`/`offers` for the top-level
#: `references: <ConceptName>` key. MEASURED on `sdk/authoring/exemplars/bundle` against the first
#: move: 0 of 4 groundings yielded a canonical key and 0 reference columns were found, over a bundle
#: declaring 2 canonical columns and 6 references — so `physical_edges` skipped every foreign key as
#: `unclaimed` ("no concept declares it with `identity: reference`") and `make_edges_file` assembled
#: a GRAMMAR-CLEAN, EMPTY EdgesFile. That is the failure this module's own `concept_index` docstring
#: describes one layer up: both artifacts present, the file valid, and the checker passing on a
#: string. `mac_project.column_identity` is rewired for the second move too — it now RETURNS the
#: referenced concept's name instead of a literal `"reference"` string, so this module reads that
#: directly rather than guessing a target from a name match.
import sys as _sys
_sys.path.insert(0, str(_ROOT.parent / "tools"))
import mac_project as _P  # noqa: E402

_SCHEMA = _load_schema()
_EF = dict(_SCHEMA["$defs"]["EdgesFile"])
_EF["$defs"] = _SCHEMA["$defs"]
_EDGES_VALIDATOR = jsv.validator_for(_SCHEMA)(_EF)

#: The only cardinality a GENERATOR may write: the one that claims nothing. Verified against the
#: grammar's own closed set at import, so this module cannot drift from the standard silently — a
#: schema that dropped the value would break here, loudly, instead of emitting edges the validator
#: then refuses one at a time (and `_valid_edge` DROPS a refused edge, so the symptom would be an
#: empty edge list rather than an error).
UNMEASURED_CARDINALITY = "0..N"
_CARD_CLOSED = tuple(
    (_SCHEMA["$defs"]["EdgeEndpoint"]["properties"].get("cardinality") or {}).get("enum") or ())
if _CARD_CLOSED and UNMEASURED_CARDINALITY not in _CARD_CLOSED:
    raise ValueError(
        f"the grammar's closed cardinality set {list(_CARD_CLOSED)} no longer contains "
        f"{UNMEASURED_CARDINALITY!r}, which is the only value a generator that has measured nothing "
        f"is entitled to write. Pick the new claims-nothing token deliberately; do not default")


def _bare(rel: str) -> str:
    return str(rel or "").split(".")[-1].strip()


def _edge_errors(obj) -> list:
    return sorted(_EDGES_VALIDATOR.iter_errors(obj), key=lambda e: list(e.path))


def _valid_edge(edge: dict) -> bool:
    """A single edge is valid iff a minimal EdgesFile carrying only it is grammar-clean."""
    return not _edge_errors({"edges": [edge]})


def concept_index(concepts: list) -> dict:
    """bare relation -> [{name, canonical_key, references}] for every concept grounding on it.

    WHY A LIST AND NOT A NAME, which is the whole defect this repairs. `physical_edges` used to take
    `concept_of: dict[str, str]` — ONE concept per relation — and harvest.py built it with
    `concept_of[rel] = cn` inside a loop over concepts, its own comment reading "M:N — every relation
    maps to this notion" while the assignment kept only the last. MEASURED ON contoso4: four concepts
    ground on `v_contoso4_sales` (OrderLine, Order, SalesAmount, Currency), five on the customer
    relation and six on the product one, so all three delivered edges came out as

        Currency -> Region,  Currency -> Region,  Currency -> ProductColor

    with join_rules that were correct and endpoints that were nonsense. Both artifacts present, the
    file grammar-clean, and the checker's FK-EDGE invariant PASSED because it matched the edge_id
    string and never looked at the concepts.

    A relation genuinely backs many notions. The endpoint therefore cannot be chosen from the
    relation — it has to be chosen from the COLUMN, which is what the column map now makes possible.

    AND THE COLUMN MOVED TWICE ON ONE DAY, 2026-10-07, SO THE ENDPOINT CAME BACK EMPTY INSTEAD OF
    WRONG, TWICE. Morning: the flat `identity:` beside the retired scalar `role:` became
    `roles: {identity: ...}`, with `concept.identity.canonical_key` as the declared override removed
    from mac.schema.json the day before. Measured against that first shape on
    `sdk/authoring/exemplars/bundle`: 0 of 4 groundings produced a canonical key and 0 references
    were found, against 2 canonical columns and 6 declared references — every FK skipped
    `unclaimed`, a VALID EMPTY edges file, the same silence as the nonsense endpoints above, one
    address later. Afternoon: `identity` left the use set entirely (column_declaration.md rev 5) for
    the top-level `references: <ConceptName>` key, which is ALSO what the key now resolves to
    directly — `column_identity` returns the concept's name, not a sentinel string, so there is no
    more `== "reference"` to compare against.

    THE DECLARED OVERRIDE IS GONE WITH ITS KEY. There is nothing left to fall back to, and a branch
    reading a field no file may carry would only hide a real miss (the same ruling `mac_project`
    records against `canonical_key`). `source:` IS ALSO SINGULAR NOW (`sources:` as a list is a
    schema load error), so a concept contributes exactly one relation entry rather than one per
    source in a loop.
    """
    out: dict = {}
    for d in concepts or []:
        c = (d or {}).get("concept") or {}
        name = str(c.get("name") or "").strip()
        if not name:
            continue
        src = (d.get("grounding") or {}).get("source") or {}
        rel = _bare(src.get("relation"))
        if not rel:
            continue
        cols = src.get("columns")
        refs = set()
        # THE CANONICAL KEY IS THE SOURCE'S `key:`, not a column flag: `source.key` is REQUIRED by
        # mac.schema.json, so a bundle that validates always has one to read here.
        canon = _P.canonical_key({"grounding": {"source": src}}) or ""
        if isinstance(cols, dict):
            for cn, body in cols.items():
                # TRUTHY, NOT `== "reference"`. `column_identity` now returns the TARGET CONCEPT'S
                # NAME (or None) — the fact this index wants is "does this column point at a
                # concept", and the name itself is no longer guessed from it anywhere downstream.
                if isinstance(body, dict) and _P.column_identity(body):
                    refs.add(str(cn))
        out.setdefault(rel, []).append({"name": name, "canonical_key": canon, "references": refs})
    return out


def _claimants(cands: list, col: str) -> list:
    """EVERY concept on this relation that declares `col` as a reference. All of them are edges.

    THIS IS NOT AMBIGUITY AND MUST NOT BE REFUSED — the first version of this fix got that wrong.
    Measured on contoso4: OrderLine, Order and SalesAmount all ground on the sales relation and all
    three declare `CustomerKey: {references: Customer}`. An order has a customer, an order line has a
    customer, and an attributable amount has a customer: three true statements, so three edges. The
    FK is a property of the RELATION; the edge is a property of the CONCEPT, and one FK legitimately
    fans out to as many edges as there are notions that reference through it.
    """
    return sorted(c["name"] for c in cands if col in c["references"])


def _target(cands: list, col: str) -> tuple:
    """(concept_name, reason). The ONE concept whose canonical key is `col`, or nothing and why.

    THE TO-SIDE IS GENUINELY SINGULAR, unlike the from-side: a key resolves to the notion it
    identifies, and two notions claiming one canonical key would mean the key identifies two things —
    which is a defect in the concepts, not a fan-out. So this refuses, and the refusal names the
    claimants rather than choosing by iteration order (which is how `Currency -> Region` shipped).
    """
    hit = sorted(c["name"] for c in cands if c["canonical_key"] == col)
    if len(hit) == 1:
        return hit[0], ""
    if not hit:
        return None, (f"no concept on this relation takes {col!r} as its canonical key "
                      f"(candidates: {', '.join(sorted(c['name'] for c in cands)) or 'none'})")
    return None, (f"{len(hit)} concepts claim {col!r} as their canonical key — {', '.join(hit)} — so "
                  f"the key would identify two notions; a person must say which owns it")


def physical_edges(datasets_info: list, index: dict) -> tuple:
    """Lift declared foreign_keys into PHYSICAL foreign_key edges between concepts.

    datasets_info: [{relation_bare, produces_relation, foreign_keys:[{from_column,to_table,to_column}]}]
    index:         `concept_index(...)` — bare relation -> [{name, canonical_key, references}]

    Returns (edges, skipped). Endpoints reference the CONCEPTS; the physical join lives in join_rule.

    HOW AN ENDPOINT IS CHOSEN, and it is chosen from the COLUMN because a relation backs many notions:
      from — the concept on this relation declaring the FK column `references: <ConceptName>`
      to   — the concept on the target relation whose `source.key` names the target column
             (ITS canonical key, read through `canonical_key`)
    Exactly one candidate each, or the edge is SKIPPED WITH A REASON. See `concept_index` for the
    three nonsense edges this replaces.
    """
    edges, seen, skipped = [], set(), []
    for di in datasets_info:
        rel = di["relation_bare"]
        cands_from = index.get(rel) or []
        roles = di.get("roles") or {}
        for fk in di.get("foreign_keys", []) or []:
            col, to_tab, to_col = fk.get("from_column"), _bare(fk.get("to_table")), fk.get("to_column")
            eid = f"{rel}__{col}__to__{to_tab}"
            # Orient fact -> dimension: a dimension sometimes declares a back-reference FK on its own
            # PK; that reverse edge is identity, not reference, and the fact's FK says it correctly.
            if roles.get(col) == "primary_key":
                continue
            # STRUCTURAL, NOT A GAP: a relation no concept grounds on cannot carry an edge BETWEEN
            # concepts. On contoso4 that is the 6 raw-plane keys (concepts ground on the served plane)
            # and the 3 on relations the operator ruled `backs_no_notion`. Reported, and marked, so it
            # is not read as work.
            if not cands_from:
                skipped.append({"edge_id": eid, "kind": "structural",
                                "why": f"no authored concept grounds on {rel!r}"})
                continue
            froms = _claimants(cands_from, col)
            if not froms:
                # THE REASON NAMES THE ADDRESS, and it had to change with the declaration TWICE —
                # once to `roles: {identity: reference}`, once more to the top-level `references:`
                # key — so the one output that says WHAT TO DECLARE stays pinned to whichever the
                # standard currently admits, not a form the grammar already refuses.
                skipped.append({"edge_id": eid, "kind": "unclaimed",
                                "why": f"no concept on {rel!r} declares {col!r} with "
                                       f"`references: <ConceptName>`, so no notion references "
                                       f"through it"})
                continue
            cands_to = index.get(to_tab) or []
            if not cands_to:
                skipped.append({"edge_id": eid, "kind": "structural",
                                "why": f"no authored concept grounds on {to_tab!r}"})
                continue
            to, why = _target(cands_to, to_col)
            if not to:
                skipped.append({"edge_id": eid, "kind": "needs_ruling", "why": f"to-endpoint: {why}"})
                continue
            # ONE EDGE PER CLAIMANT. The edge_id carries the concept, because three edges over one FK
            # would otherwise collide on the relation-and-column name and two of the three would be
            # silently deduped away — which is the same class of loss as the endpoint bug.
            for frm in froms:
                if to == frm:
                    continue
                e_id = f"{frm}__{col}__to__{to}"
                if e_id in seen:
                    continue
                edge = {
                    "edge_id": e_id,
                    "level": "physical",
                    "type": "foreign_key",
                    # `0..N` BOTH ENDS, deliberately: the weakest true claim. Nothing here has measured
                    # containment or fan-out, and the grammar requires a value — so it gets the one
                    # that promises nothing and no measurement can contradict. See the docstring.
                    "endpoints": {"from": {"concept": frm, "cardinality": UNMEASURED_CARDINALITY},
                                  "to": {"concept": to, "cardinality": UNMEASURED_CARDINALITY}},
                    "join_rule": f"{di['produces_relation']}.{col} = {fk.get('to_table')}.{to_col}",
                }
                if _valid_edge(edge):
                    seen.add(e_id)
                    edges.append(edge)
                else:
                    skipped.append({"edge_id": e_id, "kind": "invalid",
                                    "why": "the assembled edge is not grammar-clean"})
    return edges, skipped


def make_edges_file(edges: list, *, source: str) -> dict:
    """Assemble + validate the whole EdgesFile. Returns a persist-ready result dict.

    ``source`` is the source LABEL, REQUIRED and passed in by the caller (resolved from
    mac.project.yaml via sdk.project.source_ident) — this generic module carries no source
    literal of its own (de-ACME, Phase 6)."""
    obj = {
        "metadata": {
            "source": source,
            "schema_version": schema_generation(),  # one home: mac.schema.json#version
            "status": "draft",
            "generated_by": "sdk.authoring.edges (physical foreign_key edges from the data layer)",
        },
        "edges": edges,
    }
    errs = _edge_errors(obj)
    return {
        "status": "valid" if not errs else "invalid",
        "obj": obj if not errs else None,
        "edges": len(edges),
        "errors": [
            f"{'/'.join(str(x) for x in e.path) or '(root)'}: {e.message[:160]}" for e in errs[:8]
        ],
    }
