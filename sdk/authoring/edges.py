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
"""

from __future__ import annotations

from pathlib import Path

from jsonschema import validators as jsv

_ROOT = Path(__file__).resolve().parent.parent
from sdk.grammar.resolve import load_schema as _load_schema  # ONE schema home

_SCHEMA = _load_schema()
_EF = dict(_SCHEMA["$defs"]["EdgesFile"])
_EF["$defs"] = _SCHEMA["$defs"]
_EDGES_VALIDATOR = jsv.validator_for(_SCHEMA)(_EF)


def _bare(rel: str) -> str:
    return str(rel or "").split(".")[-1].strip()


def _edge_errors(obj) -> list:
    return sorted(_EDGES_VALIDATOR.iter_errors(obj), key=lambda e: list(e.path))


def _valid_edge(edge: dict) -> bool:
    """A single edge is valid iff a minimal EdgesFile carrying only it is grammar-clean."""
    return not _edge_errors({"edges": [edge]})


def physical_edges(datasets_info: list, concept_of: dict) -> list:
    """Lift declared foreign_keys into PHYSICAL foreign_key edges between concepts.

    datasets_info: [{relation_bare, produces_relation, foreign_keys:[{from_column,to_table,to_column}]}]
    concept_of:    bare relation/table name -> concept name (only authored concepts resolve)
    Endpoints reference the CONCEPTS; the physical join lives in join_rule. Unresolved endpoints
    (a FK to a table with no authored concept) are skipped. Deduped + individually validated.
    """
    edges, seen = [], set()
    for di in datasets_info:
        frm = concept_of.get(di["relation_bare"])
        if not frm:
            continue
        roles = di.get("roles") or {}
        for fk in di.get("foreign_keys", []) or []:
            # Orient fact -> dimension: emit only when the from-column is a genuine FK on THIS relation,
            # not the relation's OWN primary key. Dimensions sometimes declare a back-reference FK on
            # their PK to a fact — that reverse edge is the dimension's identity, not a reference; skip it
            # (the fact's real FK edge captures the same relationship in the correct direction).
            if roles.get(fk.get("from_column")) == "primary_key":
                continue
            to = concept_of.get(_bare(fk.get("to_table")))
            if not to or to == frm:
                continue
            eid = f"{di['relation_bare']}__{fk.get('from_column')}__to__{_bare(fk.get('to_table'))}"
            if eid in seen:
                continue
            edge = {
                "edge_id": eid,
                "level": "physical",
                "type": "foreign_key",
                "endpoints": {"from": {"concept": frm}, "to": {"concept": to}},
                "join_rule": f"{di['produces_relation']}.{fk.get('from_column')} = "
                f"{fk.get('to_table')}.{fk.get('to_column')}",
            }
            if _valid_edge(edge):
                seen.add(eid)
                edges.append(edge)
    return edges


def make_edges_file(edges: list, *, source: str) -> dict:
    """Assemble + validate the whole EdgesFile. Returns a persist-ready result dict.

    ``source`` is the source LABEL, REQUIRED and passed in by the caller (resolved from
    mac.project.yaml via sdk.project.source_ident) — this generic module carries no source
    literal of its own (de-FPL, Phase 6)."""
    obj = {
        "metadata": {
            "source": source,
            "schema_version": "0.1.13",
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
