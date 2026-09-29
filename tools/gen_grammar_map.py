#!/usr/bin/env python3
"""
gen_grammar_map.py — render reference_manual/grammar_map.html: THREE grammars, one shape.

THE OPERATOR'S QUESTION, and this file is the answer: "is the ruling and folding also part of
grammar?" Folding is, by the estate's own naming — FOLD_GRAMMAR.md, which QUERY_GRAMMAR.md calls
"the orthogonal axis". Rulings are not named as a grammar anywhere, and they have the same three
parts as one: a closed vocabulary of words, a composition that says what each word contributes, and
an outcome. So all three are drawn in the same three lanes, and THE DIFFERENCE IS THE MIDDLE LANE:

    QUERY    the Intent          ->  one SELECT skeleton, 7 slots   ->  mac.outcome_class
    FOLD     the declarations    ->  5 guards + a 25-cell LAW       ->  a fold op, or a refusal
    RULINGS  the measurement     ->  A PERSON                       ->  block, ask, or a relabel

That third middle lane is why `rulings.evidence` is required and the fold law needs no evidence at
all: a 25-cell lookup is a law nobody authors, and a prohibition a person made without a
measurement is a preference. The shape of the three planes states that, rather than asserting it.

WHAT IS READ, AND FROM WHERE. Nothing here is retyped:

  grammar/query_grammar.yaml    the query law — 9 operations, 9 declaration states, the projection
                                plane, the not-expressible ledger with its measured sole-counts.
  <runtime>/models.py           OperationKind, Intent, FilterOp — READ AS TEXT via ast, never
                                imported, which is check_query_grammar.py's own discipline: the gate
                                must run in a checkout that cannot import the runtime.
  <runtime>/planner/*.py        how many times the planner reads each Intent field.
  <runtime>/foldplane/          the fold law: 5 QuantityKinds x 5 GrainSemantics = 25 cells, 10
                                operators over 4 stages, the G1-G5 guards. LOADED IN ISOLATION --
                                see load_fold_law() for why that is neither an import nor a
                                re-encoding.
  reference_manual/column_effects.yaml  the rulings plane, already the home of what each ruling
                                does and whether anything reads it.
  mac_vocabulary.yaml           every closed term list: outcome_class, diagnostic_code,
                                column.ruling, column.measure_type, aggregation_effect.

Usage:
  python3 tools/gen_grammar_map.py [--runtime <path to mac_runtime>]
  python3 tools/gen_grammar_map.py --check
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
GRAMMAR = ROOT / "grammar" / "query_grammar.yaml"
VOCAB = ROOT / "mac_vocabulary.yaml"
EFFECTS = ROOT / "reference_manual" / "column_effects.yaml"
TEMPLATE = ROOT / "tools" / "grammar_map_template.html"
OUT = ROOT / "reference_manual" / "grammar_map.html"

SLOTS = ["SELECT", "FROM", "JOIN", "WHERE", "GROUP BY", "ORDER BY", "LIMIT"]
SLOT_OF = {"select": "SELECT", "from": "FROM", "join": "JOIN", "where": "WHERE",
           "group_by": "GROUP BY", "order_by": "ORDER BY", "limit": "LIMIT"}
NOT_GRAMMAR = {"stage", "confidence"}


class Fail(SystemExit):
    def __init__(self, msg: str) -> None:
        super().__init__(f"gen_grammar_map: {msg}")


# =========================================================================== inputs

def runtime_root(explicit: str | None) -> pathlib.Path:
    for cand in (explicit, os.environ.get("MAC_RUNTIME"),
                 ROOT.parent / "mac-platform/packages/mac-runtime/src/mac_runtime"):
        if cand and pathlib.Path(cand).is_dir():
            return pathlib.Path(cand)
    raise Fail("no runtime found — pass --runtime <path to mac_runtime>")


def runtime_facts(root: pathlib.Path) -> dict:
    """OperationKind, Intent, FilterOp and the planner's read counts — as TEXT, never imported."""
    tree = ast.parse((root / "models.py").read_text(encoding="utf-8"))
    enums: dict[str, list[str]] = {}
    intent_fields: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name in ("OperationKind", "FilterOp", "DenominatorScope"):
            enums[node.name] = [str(s.value.value) for s in node.body
                                if isinstance(s, ast.Assign) and isinstance(s.value, ast.Constant)]
        if node.name == "Intent":
            intent_fields += [s.target.id for s in node.body
                              if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)]
    if not enums.get("OperationKind") or not intent_fields:
        raise Fail("could not read OperationKind / Intent from models.py")

    planner = "\n".join(p.read_text(encoding="utf-8") for p in sorted((root / "planner").glob("*.py")))
    named = {m.lower() for m in re.findall(r"(?:OperationKind|_OpK2?)\.([A-Z_]+)", planner)}
    non_fold = sorted(x.lower() for x in re.findall(r"\.([A-Z_]+)", m.group(1))) \
        if (m := re.search(r"_NON_FOLD_OPS\s*=\s*\{([^}]*)\}", planner)) else []
    return {
        "operations": enums["OperationKind"],
        "filter_ops": enums.get("FilterOp", []),
        "intent_fields": intent_fields,
        "branched_by_name": sorted(named & set(enums["OperationKind"])),
        "non_fold_ops": non_fold,
        "planner_reads": {f: len(re.findall(rf"\.{f}\b", planner)) for f in intent_fields},
        "root": str(root),
    }


def load_fold_law(root: pathlib.Path) -> dict:
    """The 25-cell law, the 10 operators and the G1-G5 guards, from the module that holds them.

    WHY THIS IS EXECUTED AND NOT PARSED. `LAW` is built by loops, so reading it as text would mean
    RECONSTRUCTING the law here — a second encoding of the very table the estate forbids restating
    ("an applied ontology references these members; it never re-encodes the matrix"). Parsing the
    loop and replaying it is the same thing wearing a regex.

    WHY THIS IS NOT "IMPORTING THE RUNTIME". `foldplane/vocabulary.py` imports `dataclasses` and
    `enum` and nothing else — measured, and asserted below. It is executed in a bare namespace with
    no package `__init__`, so no runtime side effect runs and no venv is required. If that file ever
    grows a third-party import, the assertion fails loudly rather than quietly pulling one in.

    The guards are read as TEXT, because they are comments on code and there is nothing to execute.
    """
    src = (root / "foldplane" / "vocabulary.py").read_text(encoding="utf-8")
    imports = {n.split()[1].split(".")[0] for n in re.findall(r"^(?:from|import) \S+", src, re.M)}
    if not imports <= {"__future__", "dataclasses", "enum"}:
        raise Fail(f"foldplane/vocabulary.py now imports {sorted(imports - {'__future__','dataclasses','enum'})}"
                   " — it can no longer be loaded in isolation; read the law another way")
    # Loaded under its own module name so `@dataclass` can resolve the string annotations that
    # `from __future__ import annotations` produces — it looks the class's module up in sys.modules.
    # This is a single-FILE load: no package `__init__` runs, and mac_runtime is never imported.
    import importlib.util
    name = "_mac_foldplane_vocabulary"
    spec = importlib.util.spec_from_file_location(name, root / "foldplane" / "vocabulary.py")
    if spec is None or spec.loader is None:
        raise Fail("could not load foldplane/vocabulary.py in isolation")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(name, None)
    ns = vars(mod)

    LAW, OPS = ns["LAW"], ns["OPS"]
    kinds = [k.value for k in ns["QuantityKind"]]
    grains = [g.value for g in ns["GrainSemantics"]]
    if len(LAW) != len(kinds) * len(grains):
        raise Fail(f"the law has {len(LAW)} cells, not {len(kinds)}x{len(grains)}")

    law_txt = (root / "foldplane" / "law.py").read_text(encoding="utf-8")
    guards = [{"id": g, "title": t.strip().rstrip("."), "why": w.strip()}
              for g, t, w in re.findall(r"#\s+(G[1-5])\s+([A-Z][A-Z\- ]+)\.\s*(.*?)(?=\n\s*#\s*G[1-5]\b|\n\n)",
                                        law_txt, re.S)]
    return {
        "kinds": kinds,
        "grains": grains,
        "cells": {f"{g}|{k}": {"op": LAW[(ns['GrainSemantics'](g), ns['QuantityKind'](k))][0],
                               "sub": LAW[(ns['GrainSemantics'](g), ns['QuantityKind'](k))][1]}
                  for g in grains for k in kinds},
        "ops": {n: {"stage": o.stage, "composes": o.composes, "operands": list(o.operands)}
                for n, o in OPS.items()},
        "stages": {0: "collapse", 1: "resolve", 2: "grain expression", 3: "aggregate"},
        "tiers": [t.value for t in ns["Tier"]],
        "guards": guards,
        "cell_count": len(LAW),
    }


def measure_permissions(root: pathlib.Path) -> dict:
    """The role tuples the planner ACTUALLY branches on, so the permission law is checked, not claimed.

    TWO OF THE THREE OPERATIONS ARE ROLE-GATED IN CODE and can be verified:
      group   `plan.py` lists the roles a concept may be grouped by — and prints that same list back
              inside the POLICY_DENIED refusal, so it is the runtime's own answer to "what is an axis".
      filter  `sql.py` places a predicate only on these roles.
    THE THIRD CANNOT BE. Measured 2026-09-27: `resolver/` reads `field_roles` twice and both times
    for its KEYS (which columns exist), never for its values. Resolution is gated by registers, so
    the `resolve` column of the law has no role-reader to check against — which is itself the
    finding, and is reported rather than papered over with a guess.
    """
    planner = "\n".join(f.read_text(encoding="utf-8") for f in sorted((root / "planner").glob("*.py")))
    resolver = "\n".join(f.read_text(encoding="utf-8") for f in sorted((root / "resolver").glob("*.py")))

    def tuple_after(pattern: str) -> list[str]:
        m = re.search(pattern, planner)
        return sorted(re.findall(r'"(\w+)"', m.group(1))) if m else []

    # The period column binds through its OWN path, never the generic predicate tuple: the planner
    # looks a period column up BY ROLE and binds `Intent.period` to it. Measured here so the
    # verifier does not report a spurious disagreement for a cell served by a different reader.
    period_gate = bool(re.search(r'for role in \("period"', planner)) and \
        len(re.findall(r"\.period\b", planner)) > 0

    group_roles = tuple_after(r'declared\.rsplit\("\.", 1\)\[-1\] in \(([^)]*)\)')
    filter_roles = tuple_after(r'anchor_fr\[col\]\.rsplit\("\.", 1\)\[-1\] in \(([^)]*)\)')

    # `field_roles` touched for its KEYS vs for its VALUES — the distinction the finding rests on.
    key_reads = len(re.findall(r"field_roles", resolver))
    value_reads = len(re.findall(r'field_roles[^\n]*rsplit|roles\[[^\]]+\]\s*==\s*"', resolver))
    return {
        "group_roles": group_roles,
        "filter_roles": filter_roles,
        "refusal_role": "attribute" if re.search(r'!= "attribute"', planner) else None,
        "period_gate": period_gate,
        "period_reads": len(re.findall(r"\.period\b", planner)),
        "resolver_field_roles_mentions": key_reads,
        "resolver_role_value_reads": value_reads,
        "measured_from": str(root),
    }


def verify_permissions(perms: dict, measured: dict) -> dict:
    """Each `group`/`filter` cell against the planner's tuple. Disagreement is reported per cell."""
    out: dict[str, dict] = {}
    for role, ops in perms["roles"].items():
        out[role] = {}
        for op, cell in ops.items():
            runtime, reader = None, None
            if op == "group":
                runtime = "yes" if role in measured["group_roles"] else "no"
                reader = f"the planner's groupable tuple {tuple(measured['group_roles'])}"
            elif op == "filter":
                if role == "period" and measured["period_gate"]:
                    # Served by the period gate, not by predicate placement — a different reader,
                    # not a missing permission.
                    runtime, reader = "yes", (f"the period gate — the planner looks the period column "
                                              f"up by role and binds Intent.period "
                                              f"({measured['period_reads']} reads)")
                else:
                    runtime = "yes" if role in measured["filter_roles"] else "no"
                    reader = f"the planner's predicate tuple {tuple(measured['filter_roles'])}"
            declared = str(cell["v"])
            agrees = None if runtime is None or declared == "undeclared" else (declared == runtime)
            out[role][op] = {"declared": declared, "runtime": runtime, "agrees": agrees,
                             "reader": reader, "why": cell.get("why", "")}
    return out


def load_vocabulary() -> dict:
    raw = yaml.safe_load(VOCAB.read_text(encoding="utf-8")) or {}
    out: dict[str, dict] = {}
    for ns in ("outcome_class", "diagnostic_code", "concept.column.ruling", "concept.column.measure_type", "concept.aggregation_effect"):
        spec = raw.get(ns) or {}
        body = spec.get("terms") or spec.get("members") or {}
        out[ns] = {}
        for name, v in body.items():
            # TWO SHAPES, and reading only one is how a generator renders an empty list: a term is
            # either a map (outcome_class, column.measure_type) or a bare string (column.ruling,
            # aggregation_effect). mac_vocabulary.yaml uses both, deliberately.
            if isinstance(v, dict):
                d = v.get("description") or v.get("definition") or ""
                extra = {k: x for k, x in v.items() if k not in ("description", "definition")}
            else:
                d, extra = v or "", {}
            out[ns][name] = {"description": " ".join(str(d).split()), **extra}
    if not out["outcome_class"]:
        raise Fail("mac.outcome_class rendered empty")
    return out


# =========================================================================== the query plane

def query_plane(grammar: dict, rt: dict, vocab: dict) -> tuple[dict, list[str]]:
    fields = [f for f in rt["intent_fields"] if f not in NOT_GRAMMAR]
    drifts: list[str] = []

    # The structural edges: always there, whatever the operation. Declared in the projection plane.
    base = [("field:subject", "slot:FROM"), ("field:slices", "slot:GROUP BY"),
            ("field:slices", "slot:SELECT"), ("field:filters", "slot:WHERE"),
            ("field:period", "slot:WHERE"), ("field:join_filters", "slot:JOIN")]

    def cases_for(source: str) -> dict:
        out = {}
        for op in grammar["operations"]:
            name = op["name"]
            claimed = bool(op.get("branches_in_runtime"))
            measured = name in rt["branched_by_name"]
            branches = claimed if source == "law" else measured
            slots = [SLOT_OF[k] for k in (op.get("contributes") or {}) if k in SLOT_OF]
            if bad := [k for k in (op.get("contributes") or {}) if k not in SLOT_OF]:
                raise Fail(f"{name} contributes to unknown slot(s) {bad}")
            via = [f for f in fields if re.search(rf"\b{re.escape(f)}\b", op.get("emerges_from") or "")]

            edges = [{"from": "sel:" + name, "to": "slot:" + s, "kind": "own"} for s in slots] \
                if (branches or not via) else []
            edges += [{"from": "field:" + f, "to": "slot:" + s, "kind": "via"}
                      for f in via for s in slots]
            edges += [{"from": a, "to": b, "kind": "base"} for a, b in base]

            detail = [{"t": "asks", "v": op.get("asks")},
                      {"t": "requires — what must be DECLARED",
                       "v": " ".join(f"<code>{r}</code>" for r in (op.get("requires") or [])) or "—"},
                      {"t": "contributes to the skeleton",
                       "v": " ".join(f"<code>{k}: {v}</code>" for k, v in (op.get("contributes") or {}).items()) or "—"},
                      {"t": "refuses when", "v": op.get("refuses_when") or "the grammar states no refusal for this word"}]
            if op.get("emerges_from"):
                detail.append({"t": "emerges from", "v": op["emerges_from"]
                               + (f" — edges drawn from {', '.join('<code>'+v+'</code>' for v in via)}" if via else "")})
            if op.get("branches"):
                detail.append({"t": "runtime branches", "v": " ".join(f"<code>{b}</code>" for b in op["branches"])})

            callouts = []
            if claimed != measured:
                callouts.append({"kind": "bad", "h": "This word is a live drift.",
                                 "p": [f"The law claims <code>branches_in_runtime: {str(claimed).lower()}</code>. "
                                       f"The planner {'does' if measured else 'does not'} test for it by name, and "
                                       f"<code>check_query_grammar.py</code> reds on it (R2). Switch the source to "
                                       f"{'RUNTIME' if source == 'law' else 'LAW'} to see the other wiring."]})
            for k, h in (("open_question", "Open question, marked in the YAML."),
                         ("history", "Declared and read by nothing, until it was not."),
                         ("note", "Note.")):
                if op.get(k):
                    callouts.append({"kind": "bad" if k == "history" else "note", "h": h, "p": [op[k]]})

            out[name] = {
                "id": name, "label": name, "badge": "BRANCHES" if branches else "EMERGES",
                "drift": claimed != measured, "edges": edges, "detail": detail, "callouts": callouts,
                "self_node": {
                    "label": f"operation: {name}",
                    "sub": ("branches in the runtime — the planner tests for this word by name, so the edge starts here"
                            if branches else
                            "contributes no edge of its own — the skeleton already had this shape, and the edges start at the fields below"),
                    "empty": not branches,
                },
                "outcome": "COMMIT", "alt_outcome": "REFUSE" if op.get("refuses_when") else None,
            }
            if source == "law" and claimed != measured:
                drifts.append(f"R2 {name!r} claims branches_in_runtime={claimed} and the planner disagrees")
        return out

    for missing in sorted(set(rt["operations"]) - {o["name"] for o in grammar["operations"]}):
        drifts.append(f"R1 the runtime has operation {missing!r} and the grammar does not describe it")

    plane = {
        "id": "query", "title": "The query grammar",
        "subtitle": "how a question becomes SQL",
        "middle": "one SELECT skeleton",
        "thesis": "The middle lane is a SKELETON. Every operation contributes to the same SELECT and "
                  "contributes nothing else, so the word is mostly not what decides the SQL.",
        "skeleton": grammar.get("skeleton"),
        "sources": {"law": "what grammar/query_grammar.yaml claims",
                    "runtime": "what check_query_grammar.py measures in the planner"},
        "lanes": {
            "left": {"label": "the intent · the grammar's classes",
                     "nodes": [{"id": "field:" + f, "label": f,
                                "meta": f"{rt['planner_reads'].get(f,0)} planner reads"
                                        if f not in NOT_GRAMMAR else "not grammar",
                                "faint": f in NOT_GRAMMAR} for f in rt["intent_fields"]]},
            "middle": {"label": "the skeleton · seven slots",
                       "nodes": [{"id": "slot:" + s, "label": s} for s in SLOTS]},
            "right": {"label": "the outcome · mac.outcome_class",
                      "nodes": [{"id": "out:" + k, "label": k, "meta": _outcome_hint(k)}
                                for k, v in vocab["outcome_class"].items() if v.get("status") == "canonical"]},
        },
        "selector_label": "nine words",
        "cases": {"law": cases_for("law"), "runtime": cases_for("runtime")},
        "counts": {"operations": len(grammar["operations"]),
                   "branch_claimed": sum(1 for o in grammar["operations"] if o.get("branches_in_runtime")),
                   "branch_measured": len(rt["branched_by_name"]),
                   "fields": len([f for f in rt["intent_fields"] if f not in NOT_GRAMMAR]),
                   "filter_ops": len(rt["filter_ops"]), "slots": len(SLOTS)},
    }
    return plane, drifts


def _outcome_hint(k: str) -> str:
    return {"COMMIT": "every declaration it rests on resolved",
            "ASK": "a required dimension was underspecified",
            "REFUSE": "the evidence is absent, and it can say what",
            "BLOCK": "outside what the ontology governs"}.get(k, "")


# =========================================================================== the fold plane

def fold_plane(fold: dict, vocab: dict) -> dict:
    """25 cells, and one case per cell. The selector IS the law's own 5x5 shape.

    A matrix is the wrong form for the query grammar — its own file says so — and the RIGHT form
    here, because this law is literally indexed by two vocabularies. The grid selects; the lanes
    then show what one cell does.
    """
    # THE MEMBER EACH CELL REPLACES, keyed by the vocabulary's OWN spelling and held to it. Until
    # 2026-09-29 the keys were `Flow`/`Stock`/… — the retired capitalised `mac.MeasureType` spelling
    # that raises KeyError in the runtime's fold-law drift test (check_column_planes.py says so) — and
    # although `vocab` was passed in, this plane never consulted it, so a renamed or added term could
    # not fail here. Now a map that is not exactly the vocabulary's terms is a failure with both sides.
    member_to_cell = {"flow": ("event", "extensive"), "stock": ("observation", "extensive"),
                      "intensive": ("event", "intensive"), "precomputed": ("precomputed", "extensive"),
                      "target": ("plan", "extensive")}
    declared = set(vocab["concept.column.measure_type"])
    if set(member_to_cell) != declared:
        raise Fail(f"fold plane: member_to_cell is keyed {sorted(member_to_cell)} but "
                   f"mac_vocabulary.yaml#concept.column.measure_type declares {sorted(declared)} — "
                   f"the map must carry exactly the vocabulary's terms")
    cell_to_member = {f"{g}|{k}": m for m, (g, k) in member_to_cell.items()}

    decls = [("quantity_kind", "column", "what kind of number this is — one word from five"),
             ("grain_semantics", "relation", "how its rows came to exist — one word from five"),
             ("per", "column", "what an intensive quantity is per"),
             ("denominated_by", "column", "the column naming the unit, when rows differ"),
             ("counts_as", "concept", "what one of these IS — SME only; the law refuses to pick"),
             ("modality", "concept", "observed, or planned"),
             ("sentinel", "axis", "one member that is not a value")]

    cases = {}
    for key, cell in fold["cells"].items():
        grain, kind = key.split("|")
        op, sub = cell["op"], cell["sub"]
        refuses = op == "refuse"
        spec = fold["ops"].get(op, {})
        guard = None
        if kind in ("ordinal", "identifier"):
            guard = "G2"
        elif grain == "UNKNOWN":
            guard = "G1"
        elif grain == "precomputed":
            guard = "G3"

        lit_left = ["decl:quantity_kind", "decl:grain_semantics"]
        if kind == "intensive":
            lit_left += ["decl:per", "decl:denominated_by"]
        if grain == "plan":
            lit_left += ["decl:modality"]

        detail = [
            {"t": "the cell", "v": f"<code>LAW[({grain}, {kind})]</code> → <code>{op}"
                                   + (f" · {sub}" if sub else "") + "</code>"},
            {"t": "the operator", "v": f"stage {spec.get('stage','?')} "
                                       f"({fold['stages'].get(spec.get('stage'), '?')}) · operands "
                                       + " ".join(f"<code>{o}</code>" for o in spec.get("operands", []))
                                       + (" · <b>composes</b>" if spec.get("composes") else
                                          " · <b>DOES NOT COMPOSE</b>")},
            {"t": "consulted on", "v": "the axes the question did NOT name — "
                                       "<code>FOLDED = every axis − (grouped + pinned)</code>"},
        ]
        if key in cell_to_member:
            detail.append({"t": "this cell replaces", "v":
                           f"<code>mac.concept.column.measure_type.{cell_to_member[key]}</code> — the member is this "
                           f"(relation fact, column fact) PAIR, which is the split the new law argues for"})
        callouts = []
        if guard:
            g = next((x for x in fold["guards"] if x["id"] == guard), None)
            if g:
                callouts.append({"kind": "warn", "h": f"{g['id']} {g['title']} preempts the table here.",
                                 "p": [g["why"], "A guard OVERRIDES the law, never re-tabulates it — which is "
                                                 "why the law has no axis dimension."]})
        if op == "mean":
            callouts.append({"kind": "bad", "h": "This operator does not compose.",
                             "p": ["A breakdown and a grand total disagree. Measured, and recorded on the "
                                   "operator itself as <code>composes: False</code>."]})
        cases[key] = {
            "id": key, "label": f"{grain} × {kind}",
            "badge": "REFUSE" if refuses else op.upper(),
            "drift": False,
            "edges": [{"from": "decl:quantity_kind", "to": "mid:law", "kind": "own"},
                      {"from": "decl:grain_semantics", "to": "mid:law", "kind": "own"}]
                     + ([{"from": "mid:guard:" + guard, "to": "mid:law", "kind": "via"}] if guard else [])
                     + [{"from": "mid:law", "to": "mid:op:" + op, "kind": "own"},
                        {"from": "mid:op:" + op, "to": "out:" + ("REFUSE" if refuses else "COMMIT"), "kind": "own"}]
                     + [{"from": d, "to": "mid:law", "kind": "base"} for d in lit_left
                        if d not in ("decl:quantity_kind", "decl:grain_semantics")],
            "detail": detail, "callouts": callouts,
            "self_node": {"label": f"cell: {grain} × {kind}",
                          "sub": (f"the law refuses — <code>{sub}</code>" if refuses
                                  else f"the law licenses <code>{op}</code> on every folded axis"),
                          "empty": refuses},
            "outcome": "REFUSE" if refuses else "COMMIT", "alt_outcome": None,
        }

    return {
        "id": "fold", "title": "The fold grammar",
        "subtitle": "what a number means, and which fold is legal",
        "middle": f"a {fold['cell_count']}-cell law + 5 guards",
        "thesis": "The middle lane is a LAW. Nobody authors it: it ships with the runtime as "
                  f"{fold['cell_count']} cells, and five guards can preempt the table but never re-tabulate it.",
        "skeleton": "FOLDED = every axis of the fact  −  (the ones grouped by  +  the ones pinned by a filter)",
        "sources": None,
        "lanes": {
            "left": {"label": "the declarations · four levels",
                     "nodes": [{"id": "decl:" + n, "label": n, "meta": lvl, "sub": why}
                               for n, lvl, why in decls]},
            "middle": {"label": f"the law · {fold['cell_count']} cells, 10 operators, 4 stages",
                       "nodes": [{"id": "mid:guard:" + g["id"], "label": g["id"] + " " + g["title"].lower()}
                                 for g in fold["guards"]]
                                + [{"id": "mid:law", "label": f"LAW[grain × kind] — {fold['cell_count']} cells"}]
                                + [{"id": "mid:op:" + n, "label": n,
                                    "meta": f"stage {o['stage']}" + ("" if o["composes"] else " · no compose")}
                                   for n, o in sorted(fold["ops"].items(), key=lambda x: x[1]["stage"])]},
            "right": {"label": "the outcome · mac.outcome_class",
                      "nodes": [{"id": "out:" + k, "label": k, "meta": _outcome_hint(k)}
                                for k, v in vocab["outcome_class"].items() if v.get("status") == "canonical"]},
        },
        "selector_label": f"{fold['cell_count']} cells — the law's own shape",
        "grid": {"rows": fold["grains"], "cols": fold["kinds"],
                 "cells": {k: v["op"] for k, v in fold["cells"].items()}},
        "cases": {"law": cases},
        "counts": {"cells": fold["cell_count"], "kinds": len(fold["kinds"]),
                   "grains": len(fold["grains"]), "ops": len(fold["ops"]),
                   "guards": len(fold["guards"]), "tiers": len(fold["tiers"])},
        "bridge": {m: f"{g} × {k}" for m, (g, k) in member_to_cell.items()},
    }


# =========================================================================== the rulings plane

def rulings_plane(effects: dict, vocab: dict) -> dict:
    """The plane whose middle lane is a PERSON.

    The words and what each does come from column_effects.yaml, which is already their home. The
    constellation that makes each a CANDIDATE is measurement; the step from candidate to ruling is
    not, and that is the whole reason `evidence:` exists.
    """
    keys = {k["key"]: k for k in effects["keys"]}
    tests = {
        "label_of": ("a = b = pairs",
                     "whether the two names denote ONE thing or two. 1:1 gets you to the door. Contoso "
                     "and Contoso AG are one company in two registers; Northwind AG and Contoso are two "
                     "companies, and that pair would be one-to-many — a key pointing at a parent."),
        "finer_than": ("pairs = a, and a > b", None),
        "scoped_by": ("pairs > a AND pairs > b", None),
        "never_axis": ("cardinality approaches the row count",
                       "whether the identification MATTERS. The ratio is a measurement; that grouping "
                       "on it names individuals is a judgement, and the ruling must carry the DQ id "
                       "that measured it."),
    }
    safe = {
        "finer_than": "Safe to read off the data — pairs = finer_distinct proves every child has "
                      "exactly one parent, so the roll-up cannot double-count.",
        "scoped_by": "Also safe, once collisions WITHIN versus ACROSS the parent are checked. Zero "
                     "within and many across is the signature.",
    }
    key_of = {"label_of": "rulings.label_of", "finer_than": "rulings.finer_than",
              "scoped_by": "placement.scoped_by", "never_axis": "rulings.never_axis"}

    # THE VOCABULARY DRIVES THE LOOP and the rows above are keyed by hand. A term the vocabulary
    # declares and no row names is a FINDING that carries the term, not a KeyError three frames deep.
    unrowed = [t for t in vocab["concept.column.ruling"] if t not in tests or t not in key_of]
    if unrowed:
        raise Fail(f"rulings plane: mac_vocabulary.yaml#concept.column.ruling declares {unrowed} and "
                   f"this plane has no `tests`/`key_of` row for it — add the row")
    cases = {}
    for term, spec in vocab["concept.column.ruling"].items():
        k = keys.get(key_of[term], {})
        test, cant = tests[term]
        needs_evidence = term == "never_axis"
        outs = k.get("outcomes") or []
        primary = "BLOCK" if "BLOCK" in outs else ("ASK" if "ASK" in outs else "COMMIT")

        edges = [{"from": "m:a_distinct", "to": "mid:constellation", "kind": "own"},
                 {"from": "m:b_distinct", "to": "mid:constellation", "kind": "own"},
                 {"from": "m:pairs", "to": "mid:constellation", "kind": "own"}]
        if term == "never_axis":
            edges = [{"from": "m:a_distinct", "to": "mid:constellation", "kind": "own"},
                     {"from": "m:rows", "to": "mid:constellation", "kind": "own"}]
        edges += [{"from": "mid:constellation", "to": "mid:person", "kind": "own"},
                  {"from": "mid:person", "to": "mid:ruling", "kind": "own"}]
        if needs_evidence:
            edges += [{"from": "m:dq", "to": "mid:person", "kind": "via"},
                      {"from": "mid:person", "to": "out:LOAD", "kind": "via"}]
        edges += [{"from": "mid:ruling", "to": "out:" + o, "kind": "own"} for o in outs]
        edges += [{"from": "mid:ruling", "to": "out:GATE", "kind": "base"}]

        detail = [
            {"t": "the constellation that makes it a candidate", "v": f"<code>{test}</code>"},
            {"t": "what the ruling does", "v": k.get("effect") or spec.get("description", "")},
            {"t": "declared as", "v": f"<code>{key_of[term]}</code> · status "
                                      f"<b>{k.get('status','?')}</b> · reader {k.get('reader','none')}"},
            {"t": "evidence", "v": "<b>required</b> — a DQ register id. A prohibition without a "
                                   "measurement is a preference." if needs_evidence
                                   else "not required — the constellation is the evidence"},
        ]
        callouts = []
        if cant:
            callouts.append({"kind": "warn", "h": "What measurement cannot tell you.", "p": [cant]})
        if term in safe:
            callouts.append({"kind": "note", "h": "This one the data can settle.", "p": [safe[term]]})
        if k.get("frontier_note"):
            callouts.append({"kind": "bad", "h": "Frontier.", "p": [k["frontier_note"]]})

        cases[term] = {
            "id": term, "label": term, "badge": primary, "drift": False, "edges": edges,
            "detail": detail, "callouts": callouts,
            "self_node": {"label": f"ruling: {term}",
                          "sub": "a judgement a person makes on top of a measurement — the constellation "
                                 "narrows it to a candidate and stops there",
                          "empty": False},
            "outcome": primary, "alt_outcome": None,
        }

    return {
        "id": "rulings", "title": "The rulings",
        "subtitle": "what a person decided about an axis",
        "middle": "a person",
        "thesis": "The middle lane is A PERSON — which is why this one is not called a grammar, and why "
                  "it is the only plane that demands evidence. The measurement narrows four closed "
                  "words to a candidate; it cannot pick one.",
        "skeleton": "SELECT count(DISTINCT a), count(DISTINCT b), count(DISTINCT (a,b)) FROM <relation>",
        "sources": None,
        "lanes": {
            "left": {"label": "the measurement · the profile plane",
                     "nodes": [{"id": "m:a_distinct", "label": "count(DISTINCT a)", "meta": "measured"},
                               {"id": "m:b_distinct", "label": "count(DISTINCT b)", "meta": "measured"},
                               {"id": "m:pairs", "label": "count(DISTINCT (a,b))", "meta": "measured"},
                               {"id": "m:rows", "label": "rows in the relation", "meta": "measured"},
                               {"id": "m:dq", "label": "a DQ register id", "meta": "authored",
                                "sub": "the only input a person supplies"}]},
            "middle": {"label": "the judgement · not a law",
                       "nodes": [{"id": "mid:constellation", "label": "the constellation",
                                  "meta": "mechanical", "sub": "narrows four words to a candidate"},
                                 {"id": "mid:person", "label": "A PERSON RULES", "meta": "not mechanical",
                                  "sub": "cardinality cannot tell you which you have"},
                                 {"id": "mid:ruling", "label": "the ruling", "meta": "mac.concept.column.ruling",
                                  "sub": "4 closed words"}]},
            "right": {"label": "the outcome",
                      "nodes": [{"id": "out:" + k, "label": k, "meta": _outcome_hint(k)}
                                for k, v in vocab["outcome_class"].items() if v.get("status") == "canonical"]
                               + [{"id": "out:LOAD", "label": "LOAD · refused",
                                   "meta": "never_axis without evidence", "plane_outcome": True},
                                  {"id": "out:GATE", "label": "CHECK · red",
                                   "meta": "the ruling claims what the data denies", "plane_outcome": True}]},
        },
        "selector_label": "four words · mac.concept.column.ruling",
        "cases": {"law": cases},
        "counts": {"words": len(vocab["concept.column.ruling"]),
                   "enforced": sum(1 for t in vocab["concept.column.ruling"]
                                   if (keys.get(key_of[t], {}).get("status")) == "enforced"),
                   "designed": sum(1 for t in vocab["concept.column.ruling"]
                                   if (keys.get(key_of[t], {}).get("status")) == "designed")},
    }


# =========================================================================== build

def sole_count(measured) -> int | None:
    if not measured:
        return None
    m = re.match(r"\s*([\d\s]+?)\s*(?:questions|sole)", str(measured))
    return int(m.group(1).replace(" ", "")) if m else None


def stale_gaps(grammar: dict, rt: dict) -> list[dict]:
    closes = {"having": ["having"], "disjunctive_filter": ["any_of"], "set_operation": ["all_of"]}
    out = []
    for gap in grammar["not_expressible"]:
        for f in closes.get(gap["id"], []):
            if f in rt["intent_fields"] and rt["planner_reads"].get(f, 0) > 0:
                out.append({"gap": gap["id"], "field": f, "reads": rt["planner_reads"][f]})
    return out


def reachability() -> dict:
    text = GRAMMAR.read_text(encoding="utf-8")
    g = lambda p: (m.group(1) if (m := re.search(p, text)) else None)  # noqa: E731
    return {"today": g(r"Reachable today is ([\d.]+)\s*%"),
            "after_five": g(r"closing the first five takes it to ([\d.]+)\s*%"),
            "corpus_questions": g(r"against ([\d\s]+) third-party questions"),
            "corpus_databases": g(r"questions over ([\d\s]+) databases")}


def build(rt_path: str | None) -> tuple[dict, list[str]]:
    grammar = yaml.safe_load(GRAMMAR.read_text(encoding="utf-8")) or {}
    effects = yaml.safe_load(EFFECTS.read_text(encoding="utf-8")) or {}
    root = runtime_root(rt_path)
    rt = runtime_facts(root)
    fold = load_fold_law(root)
    vocab = load_vocabulary()

    perms = effects["permissions"]
    measured = measure_permissions(root)
    verified = verify_permissions(perms, measured)

    qp, drifts = query_plane(grammar, rt, vocab)
    planes = [qp, fold_plane(fold, vocab), rulings_plane(effects, vocab)]

    gaps = [{**g, "sole": sole_count(g.get("measured")),
             "stale": next((s for s in stale_gaps(grammar, rt) if s["gap"] == g["id"]), None)}
            for g in grammar["not_expressible"]]

    data = {
        "generated_by": "tools/gen_grammar_map.py",
        "metadata": grammar.get("metadata", {}),
        "planes": planes,
        "declaration_states": grammar["declaration_states"],
        "projection": grammar["projection"],
        "gaps": gaps,
        "stale_gaps": stale_gaps(grammar, rt),
        "reachability": reachability(),
        "vocabulary": vocab,
        "fold": fold,
        "permissions": {**perms, "measured": measured, "verified": verified},
        "runtime": {k: rt[k] for k in ("operations", "filter_ops", "branched_by_name",
                                       "non_fold_ops", "root")},
        "drifts": drifts,
        "counts": {"planes": len(planes), "gaps": len(gaps),
                   "projection_gaps": len(grammar["projection"]["gaps"]),
                   "stale": len(stale_gaps(grammar, rt)),
                   "cases": sum(len(c) for p in planes for c in p["cases"].values()),
                   "perm_cells": sum(len(v) for v in perms["roles"].values())
                                 + sum(len(v) for v in perms["rulings"].values()),
                   "perm_undeclared": sum(1 for r in perms["roles"].values()
                                          for c in r.values() if c["v"] == "undeclared"),
                   "perm_disagree": sum(1 for r in verified.values()
                                        for c in r.values() if c["agrees"] is False)},
    }
    return data, drifts


def render(data: dict) -> str:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    if "/*__DATA__*/" not in tpl:
        raise Fail(f"{TEMPLATE.name} has no /*__DATA__*/ slot")
    return tpl.replace("/*__DATA__*/", json.dumps(data, ensure_ascii=False, indent=1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runtime")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    data, drifts = build(args.runtime)
    html = render(data)
    out = pathlib.Path(args.out)
    c = data["counts"]

    if args.check:
        # THE LAW-VS-RUNTIME DRIFTS ARE THIS PAGE'S SUBJECT, NOT ITS DEFECT.
        # check_query_grammar.py owns R1-R3 and reds on them; a gate that re-derives its subject
        # cannot fail, and failing here would mean the page may not be published until the law it
        # documents is already correct.
        findings = ([f"{out.name} is stale — regenerate with tools/gen_grammar_map.py"]
                    if (not out.exists() or out.read_text(encoding="utf-8") != html) else [])
        print(f"check_grammar_map: {'FAIL' if findings else 'PASS'} — {c['planes']} planes, "
              f"{c['cases']} cases, {c['gaps']} gaps ({c['stale']} stale), "
              f"{len(drifts)} law-vs-runtime drifts reported (check_query_grammar.py gates them)")
        for f in findings:
            print(f"  - {f}")
        return 1 if findings else 0

    out.write_text(html, encoding="utf-8")
    print(f"gen_grammar_map: wrote {out}")
    for p in data["planes"]:
        print(f"  {p['id']:8} middle lane = {p['middle']:32} "
              f"{len(next(iter(p['cases'].values())))} cases · {p['counts']}")
    print(f"  {c['gaps']} gaps ({c['stale']} stale) · {len(drifts)} law-vs-runtime drifts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
