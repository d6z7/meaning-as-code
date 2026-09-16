#!/usr/bin/env python3
"""mac_measure_edges — count what every declared REALISATION claims, and record it as evidence.

THE BOTTLENECK THIS REMOVES. `verified_by` on an edge points at an expectation a human wrote. That
is why one edge in thirty-two carried evidence: proving a relationship required somebody to author a
test for it. But an edge's claims are pure counting — so the evidence can be GENERATED. This writes it.

WHY IT NOW MEASURES THREE KINDS AND NOT ONE. This tool used to know only how to measure a JOIN
PREDICATE. That was not a statement about the ontology, it was a statement about the tool — and the
ontology inherited it: 18 of 32 edges read "proved" and the other 14 read "unproved" purely because
`join_rule` was the one realisation it could count. All 14 declared a realisation. None had ever been
counted. A tool that measures 18 of 32 and prints a success is the empty-denominator defect this
estate keeps finding, wearing a measurement's clothes.

Schema v0.1.18 requires a physical edge to declare ONE of three realisations, and each one makes a
different countable claim:

  join_rule    `a.x = b.y`      -> CONTAINMENT (does every key resolve) and FANOUT (to at most one).
  realized_by  a column on the  -> "1"    : COLUMN PRESENCE — every row carries a value, so the count
               fact, or a          of NULL/empty must be 0.
               key -> value      -> "0..1": VALUE UNIQUENESS — at most one distinct value per key, so
               pair on one          the count of keys carrying two must be 0.
               relation
  resolved_by  a rule pointing  -> VALUE UNIQUENESS, against the column the rule BINDS.
               at a shared
               column
  resolved_by  a transform      -> LIST CONFORMANCE — every value in the array column must be present
               producing a         in the target dimension's column. Measured by UNNEST, not asserted.
               conformed array

WHY TWO NUMBERS AND NOT ONE, on a join. CONTAINMENT alone passes a predicate that multiplies every
row it touches — one measured at 215x in this estate, sitting under a declared cardinality of "1" for
months. FANOUT alone passes a predicate that matches nothing at all, which renders as an empty
result and reads as a clean zero. Each misses exactly what the other catches.

EVERY MEASUREMENT IS DERIVED FROM THE DECLARATIONS, never from a list of edge ids or column names.
A tool carrying a hardcoded roster measures the roster, not the ontology: it goes stale the day an
edge is added and reports the staleness as a pass. `plan()` below reads the edge's realisation, walks
the `#`-refs the edge already declares into the concept and transform files, and derives the relation,
the key, the column and the target dimension from what those files say about themselves.

AND WHERE IT CANNOT DERIVE, IT SAYS SO. An edge whose target column cannot be reached from the
declarations is recorded in `unmeasurable` WITH THE REASON — an unmeasurable edge is a reportable
state, not a silent skip. Same for a realisation that declares more than one clause and only one of
them is countable: the measured clause is recorded, and the rest is recorded as NOT measured.

IT DOES NOT WRITE THE ONTOLOGY. It writes `evidence/edge_measurements.json`, the way a suite run
writes its run record, and `check_edge_joins_measured` reads that. Recording a measurement as an
edge's `verified_by` is a change to meaning and belongs to whoever rules on meaning; this produces
the number that ruling needs, and stops.

THE RECORD'S SHAPE. Every entry in `results` carries `kind` — one of `join_predicate`,
`column_presence`, `value_uniqueness`, `list_conformance` — so a reader can tell WHICH claim was
counted rather than inferring it from which fields happen to be present. Join entries are otherwise
byte-identical to the ones this tool has always written. The three new kinds also carry `population`
(the denominator) and `violations` (the count that must be 0), so a reader can scan one pair of
fields across kinds without knowing each kind's vocabulary.

USAGE
    python3 tools/mac_measure_edges.py <bundle-root> [--dry-run]
    python3 tools/mac_measure_edges.py --self-test

Read-only. Every statement it issues is a SELECT of COUNTs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import pathlib
import re
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mac_diag as D  # noqa: E402

PREDICATE = re.compile(r"^\s*([\w.]+)\.(\w+)\s*=\s*([\w.]+)\.(\w+)\s*$")

# `realized_by` is a declared string, and it declares one of two shapes. These parse the SHAPE, which
# is part of the declaration; they do not pattern-match a known edge.
#   "v_fact_kpi.seller_code - carried on the fact; ..."   a column carried on the fact
COLUMN_REF = re.compile(r"^\s*(\w+)\.(\w+)\b")
#   "dim_territory_register.territory_code -> dim_territory_register.place_code (place_class=single_place)"
KEY_VALUE_REF = re.compile(
    r"^\s*(\w+)\.(\w+)\s*->\s*(\w+)\.(\w+)\s*(?:\(\s*(\w+)\s*=\s*([\w:\- ]+?)\s*\))?\s*$"
)
# The conformance transform declares each conformed list in its own SQL expression:
#   array_distinct(array_agg(CASE WHEN dim_power_code IS NOT NULL THEN value ...)) AS power_types
# The DIMENSION COLUMN being conformed against and the ARRAY COLUMN produced are both named there,
# which is what makes the pairing derivable instead of guessable.
#
# THREE THINGS ARE CAPTURED, AND THE FIRST IS WHY. Group 1 is the aggregate WRAPPING the CASE. The
# same transform emits `max(CASE WHEN dim_tier_code IS NOT NULL ...) AS tier_group` — a
# SCALAR, because positioning is fixed by the brand — right next to four array_agg lists. Only the
# aggregate tells them apart, and UNNESTing a scalar is a query error, not a finding.
#
# MATCHED OVER THE WHOLE STRING, NOT PER LINE, AND NON-GREEDILY. `sql:` here is a FOLDED yaml scalar
# (`>`), so the five expressions arrive as ONE line — a line-wise pass anchored at `$` paired the
# first CASE with the LAST alias in the block and derived `power_types -> seller_long`, measuring a
# real array column against the wrong dimension and reporting it as a clean 4/4. Non-greedy `.*?`
# binds each WHEN to the NEXT `AS`, which is the alias of the expression it sits in, folded or not.
CONFORMED_LIST = re.compile(
    r"\b(\w+)\s*\(\s*CASE\s+WHEN\s+(\w+)\s+IS\s+NOT\s+NULL\b.*?\bAS\s+(\w+)\b", re.I | re.S
)

# An endpoint cardinality is a promise about how many partners a row finds. Same vocabulary as
# check_edge_joins_measured, and deliberately the same words: the measurement and the judge disagreeing
# about what "0..1" means would be worse than neither existing.
EXACTLY_ONE = "1"
AT_MOST_ONE = ("1", "0..1")


# ── derivation: pure, so it is testable without a bundle and without a warehouse ──────────────────


def _split_ref(ref: str) -> tuple[str, str]:
    """"path/to/file.yaml#a.b.c" -> ("path/to/file.yaml", "a.b.c")."""
    path, _, anchor = str(ref or "").partition("#")
    return path.strip(), anchor.strip()


def _deref(doc: dict, anchor: str):
    """Walk a dotted anchor into a parsed document, LIST-AWARE.

    `contract.rules.grouping.resolve.brand_invariant_column` is not five nested keys: `rules` is a LIST
    and `grouping.resolve.brand_invariant_column` is one element's `id`, dots and all. A plain dotted
    walk returns None here and a tool that treated None as "nothing declared" would report a fully
    declared edge as unrealised — the exact misreport this file exists to stop. So at every list we
    try the REMAINING path, rejoined, against the elements' ids.
    """
    node = doc
    parts = [p for p in str(anchor or "").split(".") if p]
    i = 0
    while i < len(parts):
        if isinstance(node, list):
            rest = ".".join(parts[i:])
            for el in node:
                if isinstance(el, dict) and str(el.get("id")) == rest:
                    return el
            return None
        if not isinstance(node, dict) or parts[i] not in node:
            return None
        node = node[parts[i]]
        i += 1
    return node


def _sources(doc: dict) -> list[dict]:
    """The grounding sources of a concept document, normalised to {relation, key, columns}."""
    out = []
    for s in ((doc or {}).get("grounding") or {}).get("sources") or []:
        if not isinstance(s, dict):
            continue
        key = s.get("key")
        out.append(
            {
                "relation": str(s.get("relation") or ""),
                "key": list(key) if isinstance(key, list) else ([key] if key else []),
                "columns": [str(c) for c in (s.get("columns") or [])],
            }
        )
    return out


def _source_with(doc: dict, column: str, hint: str = "") -> dict | None:
    """The grounding source that DECLARES `column`. `hint` only breaks ties.

    WHY THE HINT IS NOT AUTHORITATIVE. `reach__of_seller` declares
    `realized_by: v_fact_kpi.seller_code`, but the Reach concept grounds on fact_reach_kpi — the
    prose names the wrong fact. Measuring the relation the prose names would count 817M rows of a
    table this edge's concept does not bind and file the result as this edge's evidence: a proof
    about two TABLES, attributed to a claim it was never about. That is the finding
    check_edge_joins_its_grounding already raised nine times against this bundle. So the CONCEPT'S
    GROUNDING decides which relation is measured, and the hint is consulted only when the concept
    grounds on more than one relation carrying the column.
    """
    cands = [s for s in _sources(doc) if column in s["columns"]]
    if not cands:
        return None
    if len(cands) > 1 and hint:
        exact = [s for s in cands if s["relation"].split(".")[-1] == hint]
        if len(exact) == 1:
            return exact[0]
    return cands[0] if len(cands) == 1 else None


def _q(relation: str, descriptors: dict[str, str]) -> str:
    """A grounding relation is already schema-qualified; a descriptor name is not."""
    return relation if "." in relation else descriptors.get(relation, relation)


def _sql_presence(rel: str, col: str) -> str:
    # EMPTY STRING COUNTS AS MISSING. A conformance pipeline that writes '' where it has nothing is
    # indistinguishable from one that writes a value, if you only test IS NULL — and "every row
    # carries a brand" is a claim about a VALUE, not about a non-null cell.
    return (
        f"SELECT COUNT(*) AS population, SUM(CASE WHEN {col} IS NULL OR "
        f"CAST({col} AS VARCHAR) = '' THEN 1 ELSE 0 END) AS missing FROM {rel}"
    )


def _sql_uniqueness(rel: str, key: str, col: str, where: str = "") -> str:
    # keys_with_none IS COUNTED TOO, and not only keys_with_many. "0..1" forbids the second value;
    # "1" forbids the second AND the zeroth, and a measurement that only ever counted duplicates
    # could never contradict a declared "1". Counting both makes the record judgeable under either
    # cardinality instead of under the one the measuring run happened to see.
    w = f" WHERE {where}" if where else ""
    return (
        f"SELECT COUNT(*) AS population, SUM(CASE WHEN c > 1 THEN 1 ELSE 0 END) AS keys_with_many, "
        f"SUM(CASE WHEN c = 0 THEN 1 ELSE 0 END) AS keys_with_none "
        f"FROM (SELECT {key}, COUNT(DISTINCT {col}) c FROM {rel}{w} GROUP BY 1)"
    )


def _sql_conformance(rel: str, col: str, tgt_rel: str, tgt_col: str) -> str:
    # UNNEST, NOT A LIKE OR A CARDINALITY. The claim is that each MEMBER of the list is a member of
    # the dimension; a test on the array as a whole cannot see the one orphan inside it, which is
    # precisely the value the transform's own quarantine marker exists to expose.
    src = f"SELECT DISTINCT v FROM {rel} CROSS JOIN UNNEST({col}) AS t(v) WHERE v IS NOT NULL"
    return (
        f"SELECT (SELECT COUNT(*) FROM ({src})) AS population, "
        f"(SELECT COUNT(*) FROM ({src}) a JOIN (SELECT DISTINCT {tgt_col} k FROM {tgt_rel}) b "
        f"ON a.v = b.k) AS conforming"
    )


def plan(edges: list[dict], docs: dict[str, dict], descriptors: dict[str, str] | None = None):
    """PURE: edges + the documents their refs point at -> (measurements, unmeasurable).

    `docs` is {bundle-relative path: parsed yaml}. Taking the documents rather than reading them is
    what keeps this rule exercisable offline in full — an instrument that can only be tested by the
    warehouse it queries cannot be shown to work before it is trusted.

    A measurement is {kind, key, edges, realisation, sql, ...kind-specific fields}. `key` de-duplicates:
    fourteen of this bundle's eighteen predicates are the same two joins repeated across the measure
    concepts, and seven edges carry the identical brand column on the identical fact. Issuing the same
    query seven times invites the reader to believe seven independent facts were established.
    """
    descriptors = descriptors or {}
    by_key: dict[tuple, dict] = {}
    unmeasurable: list[dict] = []

    def cannot(edge, realisation, reason, partial=False):
        # `measured_in_part` EXISTS BECAUSE child__of_place IS BOTH. Its realisation declares a
        # single_place clause this tool counts and a multi_place clause it does not, so the edge
        # appears in `results` AND here. A reader who saw only the id in one list would draw the
        # opposite conclusion from a reader who saw the other; the flag says which it is.
        unmeasurable.append({"edge": edge, "realisation": realisation, "reason": reason,
                             "measured_in_part": partial})

    def add(dedup, m, eid):
        # THE DEDUP TUPLE IS NAMED `dedup`, NOT `key`. It was `key`, and it silently overwrote the
        # `key` COLUMN a value-uniqueness measurement carries — the record then named a Python tuple
        # as the column to GROUP BY. Caught by the self-test; two different things wearing one name
        # is the same defect class this file exists to report.
        by_key.setdefault(dedup, {**m, "dedup": dedup, "edges": []})["edges"].append(eid)

    for e in edges:
        eid = str(e.get("edge_id"))
        ep = e.get("endpoints") or {}
        card = str((ep.get("to") or {}).get("cardinality") or "")
        from_doc = docs.get(_split_ref((ep.get("from") or {}).get("ref") or "")[0]) or {}
        to_doc = docs.get(_split_ref((ep.get("to") or {}).get("ref") or "")[0]) or {}

        pred = e.get("join_rule")
        if isinstance(pred, str) and pred.strip():
            m = PREDICATE.match(pred)
            if not m:
                cannot(eid, "join_rule", f"join_rule {pred.strip()[:60]!r} is not `a.x = b.y`")
                continue
            lr, lc, rr, rc = m.groups()
            if lr not in descriptors or rr not in descriptors:
                missing = [r for r in (lr, rr) if r not in descriptors]
                cannot(eid, "join_rule",
                       f"no dataset descriptor for {', '.join(missing)} — the predicate names a "
                       f"relation this bundle does not describe")
                continue
            lp, rp_ = descriptors[lr], descriptors[rr]
            add((lp, lc, rp_, rc),
                {"kind": "join_predicate", "realisation": "join_rule",
                 "predicate": f"{lp}.{lc} = {rp_}.{rc}",
                 "sql": (f"SELECT (SELECT COUNT(DISTINCT {lc}) FROM {lp}) AS lhs, "
                         f"(SELECT COUNT(*) FROM (SELECT DISTINCT {lc} v FROM {lp}) a "
                         f"JOIN (SELECT DISTINCT {rc} k FROM {rp_}) b ON a.v = b.k) AS matched, "
                         f"(SELECT COALESCE(MAX(c), 0) FROM (SELECT {rc}, COUNT(*) c FROM {rp_} "
                         f"GROUP BY 1)) AS fanout")},
                eid)
            continue

        rb = e.get("realized_by")
        if isinstance(rb, str) and rb.strip():
            # A realisation may declare SEVERAL clauses — child__of_place declares one for
            # single_place markets and another for the multi_place buckets. Measuring the first
            # and saying nothing about the rest would report a partially-measured edge as measured.
            clauses = [c.strip() for c in rb.split(";") if c.strip()]
            head, tail = clauses[0], clauses[1:]
            kv = KEY_VALUE_REF.match(head)
            if kv:
                krel, kcol, vrel, vcol, fcol, fval = kv.groups()
                if krel != vrel:
                    cannot(eid, "realized_by",
                           f"key and value are declared on different relations ({krel}, {vrel}) — "
                           f"that is a join, not a column the row carries")
                    continue
                src = _source_with(from_doc, kcol, krel)
                if not src or vcol not in src["columns"]:
                    cannot(eid, "realized_by",
                           f"the from-concept's grounding declares no single relation carrying both "
                           f"{kcol} and {vcol} — the relation to measure cannot be derived")
                    continue
                if fcol and fcol not in src["columns"]:
                    cannot(eid, "realized_by",
                           f"the declared filter column {fcol} is not a column of "
                           f"{src['relation']} — the scope of the claim cannot be derived")
                    continue
                if card not in AT_MOST_ONE:
                    cannot(eid, "realized_by",
                           f"cardinality {card!r} constrains nothing, so a key->value declaration "
                           f"makes no claim that counting could contradict")
                    continue
                rel = _q(src["relation"], descriptors)
                where = f"{fcol} = '{fval}'" if fcol else ""
                add((rel, kcol, vcol, where),
                    {"kind": "value_uniqueness", "realisation": "realized_by",
                     "relation": rel, "key": kcol, "column": vcol, "filter": where,
                     "cardinality": card, "sql": _sql_uniqueness(rel, kcol, vcol, where),
                     "note": (f"declares {len(tail)} further clause(s) NOT measured here: "
                              f"{'; '.join(tail)}" if tail else "")},
                    eid)
                if tail:
                    cannot(eid, "realized_by",
                           f"{len(tail)} further clause(s) of the realisation name a different "
                           f"relation and were NOT measured: {'; '.join(tail)}", partial=True)
                continue

            cr = COLUMN_REF.match(head)
            if not cr:
                cannot(eid, "realized_by",
                       f"realized_by {head[:60]!r} names neither `rel.col` nor `rel.k -> rel.v`")
                continue
            hint, col = cr.groups()
            src = _source_with(from_doc, col, hint)
            if not src:
                cannot(eid, "realized_by",
                       f"no grounding source of the from-concept declares column {col!r} — the "
                       f"relation carrying it cannot be derived (the reference names {hint!r})")
                continue
            rel = _q(src["relation"], descriptors)
            if card == EXACTLY_ONE:
                add((rel, col),
                    {"kind": "column_presence", "realisation": "realized_by",
                     "relation": rel, "column": col, "cardinality": card,
                     "sql": _sql_presence(rel, col),
                     "note": (f"realized_by names {hint}; measured against {rel}, the relation the "
                              f"from-concept actually grounds on" if rel.split(".")[-1] != hint
                              else "")},
                    eid)
            elif card in AT_MOST_ONE:
                cannot(eid, "realized_by",
                       f"cardinality {card!r} claims AT MOST one PER KEY, and the declaration names "
                       f"a column but no key column to group by")
            else:
                cannot(eid, "realized_by",
                       f"cardinality {card!r} constrains nothing — a carried column cannot "
                       f"contradict it")
            continue

        sb = e.get("resolved_by")
        if isinstance(sb, str) and sb.strip():
            path, anchor = _split_ref(sb)
            target = docs.get(path)
            if target is None:
                cannot(eid, "resolved_by", f"resolved_by points at {path!r}, which was not loaded")
                continue
            node = _deref(target, anchor)
            if not isinstance(node, dict):
                cannot(eid, "resolved_by",
                       f"anchor {anchor!r} resolves to nothing in {path} — the rule or transform "
                       f"that realises this edge is not there")
                continue

            if node.get("binds"):
                # A RESOLUTION RULE names the columns it binds. The claim is about the column the
                # rule shares, so the column must be one the rule's OWN concept grounds on —
                # otherwise the rule binds a name and the measurement guesses a table.
                bound = [b for b in node["binds"] if _source_with(target, str(b))]
                if len(bound) != 1:
                    cannot(eid, "resolved_by",
                           f"rule {anchor} binds {len(bound)} column(s) reachable from its concept's "
                           f"grounding ({', '.join(map(str, node['binds']))}) — the shared column "
                           f"cannot be derived unless exactly one is")
                    continue
                col = str(bound[0])
                src = _source_with(target, col)
                if not src["key"]:
                    cannot(eid, "resolved_by",
                           f"{src['relation']} declares no key in its grounding, so 'at most one "
                           f"{col} per key' has no key to group by")
                    continue
                if card not in AT_MOST_ONE:
                    cannot(eid, "resolved_by",
                           f"cardinality {card!r} constrains nothing — a shared column value cannot "
                           f"contradict it")
                    continue
                rel, key = _q(src["relation"], descriptors), src["key"][0]
                add((rel, key, col, ""),
                    {"kind": "value_uniqueness", "realisation": "resolved_by",
                     "relation": rel, "key": key, "column": col, "filter": "",
                     "cardinality": card, "sql": _sql_uniqueness(rel, key, col), "note": ""},
                    eid)
                continue

            if node.get("sql"):
                # A CONFORMANCE TRANSFORM produces one array column per dimension it conforms
                # against, and names BOTH in the same SQL expression. The edge's TO concept says
                # which dimension this edge is about; that picks the expression, which yields the
                # array column. Nothing here knows an edge id or a column name in advance.
                tgt_cols = {c for s in _sources(to_doc) for c in s["columns"]}
                hits = [
                    (dim, arr) for agg, dim, arr in
                    (m.groups() for m in CONFORMED_LIST.finditer(str(node["sql"])))
                    if dim in tgt_cols and "array" in agg.lower()
                ]
                if len(hits) != 1:
                    cannot(eid, "resolved_by",
                           f"transform {anchor} produces {len(hits)} conformed list(s) against the "
                           f"to-concept's columns — the array column to unnest cannot be derived")
                    continue
                dim_col, arr_col = hits[0]
                src = _source_with(from_doc, arr_col)
                tgt = _source_with(to_doc, dim_col)
                if not src or not tgt:
                    cannot(eid, "resolved_by",
                           f"no grounding source declares "
                           f"{'the list column ' + arr_col if not src else 'the dimension column ' + dim_col}"
                           f" — the relation to measure cannot be derived")
                    continue
                rel, tgt_rel = _q(src["relation"], descriptors), _q(tgt["relation"], descriptors)
                add((rel, arr_col, tgt_rel, dim_col),
                    {"kind": "list_conformance", "realisation": "resolved_by",
                     "relation": rel, "column": arr_col,
                     "target_relation": tgt_rel, "target_column": dim_col,
                     "sql": _sql_conformance(rel, arr_col, tgt_rel, dim_col), "note": ""},
                    eid)
                continue

            cannot(eid, "resolved_by",
                   f"anchor {anchor} resolves to neither a rule (no `binds`) nor a transform "
                   f"(no `sql`) — nothing there states what to count")
            continue

        cannot(eid, "none",
               "declares NO realisation — not a join, not a rule, not a column. Nobody has said how "
               "this relationship is reached, so there is nothing to count")

    return list(by_key.values()), unmeasurable


# ── the bundle side: reads files, issues SELECTs ───────────────────────────────────────────────────


def _descriptors(root: pathlib.Path) -> dict[str, str]:
    """declared relation name -> physically qualified name, from the dataset descriptors."""
    out: dict[str, str] = {}
    for f in sorted((root / "data" / "datasets").glob("*.yaml")):
        d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        t = d.get("table") or {}
        name = t.get("name") or f.stem
        out[name] = ".".join(p for p in (t.get("schema"), t.get("name")) if p) or name
    return out


def _refs(edges: list[dict]) -> set[str]:
    """Exactly the documents the edges point at — loaded because an edge NAMED them, not by sweeping
    a directory. A sweep would quietly widen what a derivation can reach and make a mis-derivation
    look like a lucky hit on some unrelated file."""
    out: set[str] = set()
    for e in edges:
        for side in ("from", "to"):
            r = ((e.get("endpoints") or {}).get(side) or {}).get("ref")
            if r:
                out.add(_split_ref(r)[0])
        for k in ("resolved_by", "realized_by"):
            v = e.get(k)
            if isinstance(v, str) and "#" in v:
                out.add(_split_ref(v)[0])
    return {p for p in out if p}


def _athena(root: pathlib.Path):
    """Borrow the bundle's own client so region, workgroup and profile come from one place."""
    rp = root / "tools" / "run_properties.py"
    if not rp.exists():
        raise SystemExit(f"REFUSED: no query runner at {rp}")
    spec = importlib.util.spec_from_file_location("rp", rp)
    m = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, ["x"]
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    finally:
        sys.argv = argv
    eng = (yaml.safe_load((root / "acceptance" / "properties.yaml").read_text()) or {})["engine"]
    return m.Athena(eng["profile"], eng["region"], eng["workgroup"], eng["database"])


def holds(entry: dict) -> bool:
    """Does this measurement SATISFY the claim it counted? THE ONE PLACE THIS IS DECIDED.

    WHY IT LIVES HERE. Three surfaces read these records — the claims gate, the object projection and
    the concept page — and each had its own copy of the arithmetic. That is not redundancy, it is a
    fault line: the copies all judged by the JOIN criteria, so the day this tool learned to measure a
    column and a conformed list, all three read `lhs = 0` and reported fourteen edges as
    CONTRADICTED. Fourteen claims that HOLD, rendered as measurably false, which is worse than the
    unproved they replaced.

    So the measurer decides, once, and writes the verdict into the record. A consumer reads one
    field. There is no arithmetic left to drift.
    """
    k = str(entry.get("kind") or "")
    if k == "join_predicate":
        # BOTH HALVES. Containment alone passes a predicate that multiplies every row it touches
        # (one sat at 215x under a declared "1"); fanout alone passes one that matches nothing.
        lhs, matched, fan = int(entry.get("lhs") or 0), int(entry.get("matched") or 0), int(entry.get("fanout") or 0)
        return lhs > 0 and matched == lhs and fan <= 1
    # Every other kind states its own denominator and its own count of breaches, so the rule is the
    # same shape for all of them: something was examined, and nothing broke.
    pop, viol = int(entry.get("population") or 0), int(entry.get("violations") or 0)
    return pop > 0 and viol == 0


def _record(m: dict, row: dict, eid: str) -> dict:
    """One measurement + one result row -> the entry written for one edge, keyed by KIND.

    `population` and `violations` are carried on every non-join kind so a reader can scan two fields
    across all of them; the kind-specific counts are kept alongside because "3 violations" without
    "3 of what" is the denominator-free number this estate has been burned by repeatedly.
    """
    base = {"edge": eid, "kind": m["kind"], "realisation": m["realisation"]}
    if m["kind"] == "join_predicate":
        # UNCHANGED, DELIBERATELY. check_edge_joins_measured reads lhs/matched/fanout by those names.
        return {**base, "predicate": m["predicate"], "lhs": int(row["lhs"]),
                "matched": int(row["matched"]), "fanout": int(row["fanout"]), "sql": m["sql"]}
    if m["kind"] == "column_presence":
        pop, missing = int(row["population"]), int(row["missing"] or 0)
        return {**base, "relation": m["relation"], "column": m["column"],
                "cardinality": m["cardinality"], "population": pop, "violations": missing,
                "rows": pop, "missing": missing, "note": m.get("note", ""), "sql": m["sql"]}
    if m["kind"] == "value_uniqueness":
        pop = int(row["population"])
        many, none = int(row["keys_with_many"] or 0), int(row["keys_with_none"] or 0)
        # "1" forbids the zeroth value as well as the second; "0..1" forbids only the second.
        viol = many + (none if m["cardinality"] == EXACTLY_ONE else 0)
        return {**base, "relation": m["relation"], "key": m["key"], "column": m["column"],
                "filter": m["filter"], "cardinality": m["cardinality"], "population": pop,
                "violations": viol, "keys": pop, "keys_with_many": many, "keys_with_none": none,
                "note": m.get("note", ""), "sql": m["sql"]}
    pop, conf = int(row["population"]), int(row["conforming"])
    return {**base, "relation": m["relation"], "column": m["column"],
            "target_relation": m["target_relation"], "target_column": m["target_column"],
            "population": pop, "violations": pop - conf, "values": pop, "conforming": conf,
            "note": m.get("note", ""), "sql": m["sql"]}


def _stamp(entry: dict) -> dict:
    """Every record carries its own verdict. Written at the one exit through which all four kinds
    pass, so a new kind cannot be added without one."""
    return {**entry, "holds": holds(entry)}


def _line(m: dict, row: dict) -> str:
    if m["kind"] == "join_predicate":
        lhs, matched = int(row["lhs"]), int(row["matched"])
        pct = (100.0 * matched / lhs) if lhs else 0.0
        return (f"{m['predicate'].split(' = ')[0]:<52} {matched}/{lhs} resolve ({pct:.1f}%), "
                f"max fanout {row['fanout']}")
    if m["kind"] == "column_presence":
        return (f"{m['relation'] + '.' + m['column']:<52} {row['population']} row(s), "
                f"{row['missing']} without a value")
    if m["kind"] == "value_uniqueness":
        where = f" [{m['filter']}]" if m["filter"] else ""
        return (f"{m['relation'] + '.' + m['key'] + '->' + m['column']:<52} "
                f"{row['population']} key(s){where}, {row['keys_with_many']} carrying more than one, "
                f"{row['keys_with_none']} carrying none")
    return (f"{m['relation'] + '.' + m['column']:<52} {row['conforming']}/{row['population']} "
            f"conform to {m['target_relation']}.{m['target_column']}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--dry-run", action="store_true")
    if "--self-test" in sys.argv[1:]:
        return self_test()
    a = ap.parse_args()
    root = pathlib.Path(a.root).resolve()

    edges_file = root / "ontology" / "edges.yaml"
    if not edges_file.exists():
        return D.refuse_empty("mac_measure_edges", edges_file, unit="edge")
    edges = (yaml.safe_load(edges_file.read_text(encoding="utf-8")) or {}).get("edges") or []
    if not edges:
        return D.refuse_empty("mac_measure_edges", edges_file, unit="edge")

    docs: dict[str, dict] = {}
    for rel_path in _refs(edges):
        f = root / rel_path
        if f.exists():
            try:
                docs[rel_path] = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            except Exception as ex:  # noqa: BLE001
                print(f"  REFUSED to read {rel_path}: {str(ex)[:80]}")

    work, unmeasurable = plan(edges, docs, _descriptors(root))

    kinds: dict[str, int] = {}
    for m in work:
        kinds[m["kind"]] = kinds.get(m["kind"], 0) + len(m["edges"])
    covered = sum(len(m["edges"]) for m in work)
    print(f"  {len(edges)} edge(s); {covered} measurable over {len(work)} DISTINCT measurement(s)")
    for k in sorted(kinds):
        print(f"    {k:<18} {kinds[k]} edge(s)")
    for m in sorted(work, key=lambda m: m["kind"]):
        head = m.get("predicate") or (
            f"{m['relation']}.{m['key']}->{m['column']}" if m.get("key")
            else f"{m['relation']}.{m['column']}")
        print(f"      [{m['kind']}] {head}   ({len(m['edges'])} edge(s))")
    # NAMED, NOT COUNTED. "2 unmeasurable" tells a reader a number; it does not tell them which claim
    # nobody has counted, and a number with no names is what lets an unmeasured edge sit for months.
    for u in unmeasurable:
        how = "PARTLY MEASURED" if u["measured_in_part"] else "CANNOT MEASURE"
        print(f"  {how} {u['edge']} ({u['realisation']}): {u['reason']}")
    nothing = sorted({u["edge"] for u in unmeasurable if not u["measured_in_part"]})
    print(f"  {covered} of {len(edges)} edge(s) carry at least one measurement; "
          f"{len(nothing)} carry none{': ' + ', '.join(nothing) if nothing else ''}")
    if a.dry_run:
        print("  DRY RUN — nothing executed")
        return 0
    if not work:
        # NEVER RECORD A CLEAN NOTHING. An empty record reads as "measured, found no problem", which
        # is the empty-denominator defect; a setup failure must be a setup failure.
        return D.refuse_empty("mac_measure_edges", edges_file, unit="measurable realisation")

    ath = _athena(root)
    results, failed = [], []
    for m in work:
        try:
            rows, _ = ath.query(m["sql"])
        except Exception as ex:  # noqa: BLE001
            # A QUERY THAT FAILED IS NOT A MEASUREMENT THAT PASSED. Recording nothing for it and
            # carrying on would hand the reader a record whose `results` silently omits the edges
            # the warehouse refused — the same 18-of-32 misread, one layer down.
            reason = f"the measurement query failed: {str(ex)[:120]}"
            print(f"  QUERY FAILED [{m['kind']}] {', '.join(m['edges'])}: {str(ex)[:120]}")
            failed.extend({"edge": e, "realisation": m["realisation"], "reason": reason}
                          for e in m["edges"])
            continue
        row = rows[0]
        print(f"    [{m['kind']}] {_line(m, row)}")
        results.extend(_stamp(_record(m, row, eid)) for eid in m["edges"])
    unmeasurable.extend(failed)

    if not results:
        return D.refuse_empty("mac_measure_edges", edges_file, unit="completed measurement")

    out = root / "evidence" / "edge_measurements.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    # STAGE THEN REPLACE. A redirect that opens the real file truncates it before the tool has
    # produced anything, and a failed run then leaves an empty record that reads as "measured, found
    # nothing" — this estate lost 3.5 MB of test lineage to exactly that once.
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(
            {
                "measured_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                "edges": len(edges),
                "distinct_joins": sum(1 for m in work if m["kind"] == "join_predicate"),
                "distinct_measurements": len(work),
                "edges_covered": len(results),
                "by_kind": {k: sum(1 for r in results if r["kind"] == k)
                            for k in sorted({r["kind"] for r in results})},
                "unmeasurable": unmeasurable,
                "results": results,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    tmp.replace(out)
    print(f"  recorded {len(results)} of {len(edges)} edge measurement(s) over {len(work)} distinct "
          f"measurement(s), {len(unmeasurable)} unmeasurable -> {out.relative_to(root)}")
    return 0


def self_test() -> int:
    """One mutant per way the DERIVATION can go wrong, and the controls that stop it over-firing.

    The rule under test is `plan`: given what the edges and their documents declare, WHICH claim is
    counted, against which relation and column — and where that cannot be derived, is it RECORDED.
    The mutants are seeded by breaking one declaration at a time, because that is how these break in
    practice: a column renamed, a concept re-grounded, an anchor left pointing at a rule that moved.
    """
    fact = {"grounding": {"sources": [
        {"relation": "warehouse.v_fact_kpi", "key": ["k"], "columns": ["k", "seller_code"]}]}}
    dim = {"grounding": {"sources": [
        {"relation": "warehouse.dim_seller_territory", "key": ["seller_key"],
         "columns": ["seller_key"]}]}}
    register = {"grounding": {"sources": [
        {"relation": "warehouse.dim_territory_register", "key": ["territory_code"],
         "columns": ["territory_code", "place_code", "place_class", "grouping"]}]},
        "contract": {"rules": [{"id": "grouping.resolve.brand_invariant_column", "binds": ["grouping"]}]}}
    model = {"grounding": {"sources": [
        {"relation": "warehouse.dim_item", "key": ["item_key"],
         "columns": ["item_key", "power_types"]}]}}
    fuel = {"grounding": {"sources": [
        {"relation": "warehouse.dim_power", "key": ["power_key"],
         "columns": ["power_key", "dim_power_code"]}]}}
    # FOLDED ONTO ONE LINE, exactly as `sql: >` delivers it, and carrying a SCALAR max(CASE ...) over
    # a column the to-concept also grounds — the two shapes that between them produced the
    # power_types->seller_long misderivation. Split across lines, this fixture cannot see either.
    xform = {"transforms": [{"id": "conform-or-quarantine-attributes", "sql":
             "array_distinct(array_agg(CASE WHEN dim_power_code IS NOT NULL THEN value END)) "
             "AS power_types, max(CASE WHEN power_key IS NOT NULL THEN value END) "
             "AS fuel_group, array_distinct(array_agg(CASE WHEN x IS NOT NULL THEN value END)) "
             "AS seller_long\n"}]}
    DOCS = {"f.yaml": fact, "b.yaml": dim, "market.yaml": register, "grouping.yaml": register,
            "model.yaml": model, "fuel.yaml": fuel, "data/transforms/dim_item.yaml": xform}
    DESC = {"v_fact_kpi": "warehouse.v_fact_kpi", "dim_seller_territory": "warehouse.dim_seller_territory"}

    def edge(**kw):
        base = {"edge_id": "e1", "endpoints": {"from": {"ref": "f.yaml#concept"},
                                               "to": {"ref": "b.yaml#concept", "cardinality": "1"}}}
        base.update(kw)
        return base

    def card(e, c):
        e = json.loads(json.dumps(e))
        e["endpoints"]["to"]["cardinality"] = c
        return e

    join = edge(join_rule="v_fact_kpi.k = dim_seller_territory.seller_key")
    carried = edge(realized_by="v_fact_kpi.seller_code - carried on the fact")
    kv = card(edge(endpoints={"from": {"ref": "market.yaml#concept"},
                              "to": {"ref": "b.yaml#concept", "cardinality": "0..1"}},
                   realized_by="dim_territory_register.territory_code -> dim_territory_register.place_code "
                               "(place_class=single_place)"), "0..1")
    shared = card(edge(endpoints={"from": {"ref": "market.yaml#concept"},
                                  "to": {"ref": "grouping.yaml#concept", "cardinality": "0..1"}},
                       resolved_by="grouping.yaml#contract.rules.grouping.resolve."
                                   "brand_invariant_column"), "0..1")
    conform = card(edge(endpoints={"from": {"ref": "model.yaml#concept"},
                                   "to": {"ref": "fuel.yaml#concept", "cardinality": "0..N"}},
                        resolved_by="data/transforms/dim_item.yaml#transforms."
                                    "conform-or-quarantine-attributes"), "0..N")

    def kinds(es):
        w, _ = plan(es, DOCS, DESC)
        return sorted(m["kind"] for m in w for _ in m["edges"])

    def whynot(es):
        _, u = plan(es, DOCS, DESC)
        return len(u)

    def only(es):
        w, _ = plan(es, DOCS, DESC)
        return w[0] if w else {}

    cases = [
        # ── the four claims are DERIVED, each from its own declaration ────────────────────────────
        ("a join predicate still derives a join measurement",
         kinds([join]) == ["join_predicate"]),
        ("a carried column under '1' derives a presence measurement",
         kinds([carried]) == ["column_presence"]),
        ("a key->value realisation under '0..1' derives a uniqueness measurement",
         kinds([kv]) == ["value_uniqueness"]),
        ("a rule binding a shared column derives a uniqueness measurement",
         kinds([shared]) == ["value_uniqueness"]),
        ("a conformance transform derives a list-conformance measurement",
         kinds([conform]) == ["list_conformance"]),
        ("all five kinds coexist in one plan, none swallowing another",
         kinds([join, carried, kv, shared, conform]) ==
         sorted(["join_predicate", "column_presence", "value_uniqueness", "value_uniqueness",
                 "list_conformance"])),
        # ── the derived TARGET is the declared one, not a guess ───────────────────────────────────
        ("presence measures the from-concept's grounded relation and the named column",
         only([carried]).get("relation") == "warehouse.v_fact_kpi"
         and only([carried]).get("column") == "seller_code"),
        ("THE reach DEFECT: the grounding wins over a realized_by naming another fact",
         only([edge(endpoints={"from": {"ref": "model.yaml#concept"},
                               "to": {"ref": "b.yaml#concept", "cardinality": "1"}},
                    realized_by="some_other_fact.power_types - carried")]).get("relation")
         == "warehouse.dim_item"),
        ("the key->value filter is carried into the SQL, so the claim keeps its scope",
         "place_class = 'single_place'" in only([kv]).get("sql", "")),
        ("the shared-column rule's dotted id is found inside a LIST of rules",
         only([shared]).get("column") == "grouping"
         and only([shared]).get("key") == "territory_code"),
        ("conformance pairs the array column with the to-concept's dimension column",
         only([conform]).get("column") == "power_types"
         and only([conform]).get("target_column") == "dim_power_code"
         and only([conform]).get("target_relation") == "warehouse.dim_power"),
        ("identical measurements de-duplicate but keep both edge ids",
         len(plan([carried, {**carried, "edge_id": "e2"}], DOCS, DESC)[0]) == 1
         and only([carried, {**carried, "edge_id": "e2"}])["edges"] == ["e1", "e2"]),
        # ── MUTANTS: one broken declaration each; every one must be RECORDED, never skipped ───────
        ("MUTANT no realisation at all is recorded, not ignored",
         whynot([edge()]) == 1 and kinds([edge()]) == []),
        ("MUTANT a column the from-concept does not ground is recorded",
         whynot([edge(realized_by="v_fact_kpi.no_such_column - carried")]) == 1),
        ("MUTANT a join naming an undescribed relation is recorded",
         whynot([edge(join_rule="not_a_dataset.k = dim_seller_territory.seller_key")]) == 1),
        ("MUTANT an unparseable predicate is recorded",
         whynot([edge(join_rule="a.b = c.d = e.f")]) == 1),
        ("MUTANT an anchor pointing at a rule that is not there is recorded",
         whynot([card(edge(endpoints={"from": {"ref": "market.yaml#concept"},
                                      "to": {"ref": "grouping.yaml#concept", "cardinality": "0..1"}},
                           resolved_by="grouping.yaml#contract.rules.grouping.resolve.moved"),
                      "0..1")]) == 1),
        ("MUTANT a transform whose lists conform to no column of the to-concept is recorded",
         whynot([card(edge(endpoints={"from": {"ref": "model.yaml#concept"},
                                      "to": {"ref": "b.yaml#concept", "cardinality": "0..N"}},
                           resolved_by="data/transforms/dim_item.yaml#transforms."
                                       "conform-or-quarantine-attributes"), "0..N")]) == 1),
        ("MUTANT a key->value split across two relations is a join, and is recorded as unmeasurable",
         whynot([card(edge(endpoints={"from": {"ref": "market.yaml#concept"},
                                      "to": {"ref": "b.yaml#concept", "cardinality": "0..1"}},
                           realized_by="dim_territory_register.territory_code -> other.place_code"),
                      "0..1")]) == 1),
        ("MUTANT a carried column under '0..1' has no key to group by, and is recorded",
         whynot([card(carried, "0..1")]) == 1 and kinds([card(carried, "0..1")]) == []),
        ("MUTANT the unmeasured second clause of a realisation is recorded alongside the first",
         whynot([card({**kv, "realized_by": kv["realized_by"]
                       + "; country_bucket_membership.member_place for multi_place"}, "0..1")]) == 1
         and kinds([card({**kv, "realized_by": kv["realized_by"]
                          + "; country_bucket_membership.member_place for multi_place"}, "0..1")])
         == ["value_uniqueness"]),
        # ── NEGATIVE CONTROLS: correctly-declared shapes that must NOT be reported unmeasurable ───
        ("a holding join is not reported unmeasurable", whynot([join]) == 0),
        ("a holding carried column is not reported unmeasurable", whynot([carried]) == 0),
        ("a holding key->value is not reported unmeasurable", whynot([kv]) == 0),
        ("a holding shared column is not reported unmeasurable", whynot([shared]) == 0),
        ("a holding conformance transform is not reported unmeasurable", whynot([conform]) == 0),
        ("an empty edge list plans nothing and blames nobody",
         plan([], DOCS, DESC) == ([], [])),
        ("a scalar CASE over a to-concept column is not mistaken for a conformed LIST",
         only([conform]).get("column") == "power_types"),
        ("THE FOLDED-SQL DEFECT: the CASE binds to its OWN alias, not the last one in the block",
         only([conform]).get("column") == "power_types"
         and only([conform]).get("target_column") == "dim_power_code"),
        # THE SQL IS PART OF THE RULE. A measurement whose SQL does not test what its kind claims is
        # a mislabelled number, and mislabelled numbers are what this whole file is against.
        ("presence SQL tests empty string as well as NULL",
         "IS NULL OR" in only([carried])["sql"] and "= ''" in only([carried])["sql"]),
        ("uniqueness SQL counts keys with none as well as keys with many",
         "keys_with_none" in only([shared])["sql"]
         and "keys_with_many" in only([shared])["sql"]),
        ("conformance SQL unnests the list rather than testing the array whole",
         "UNNEST(power_types)" in only([conform])["sql"]),
        ("every measurement issues a read-only SELECT",
         all(m["sql"].lstrip().upper().startswith("SELECT")
             for m in plan([join, carried, kv, shared, conform], DOCS, DESC)[0])),
    ]
    bad = [n for n, ok in cases if not ok]
    for n in bad:
        print(f"  [SELF-TEST FAIL] {n}")
    n = len(cases)
    print(
        f"{'PASS' if not bad else 'FAIL'}: mac_measure_edges self-test — {n - len(bad)}/{n} "
        f"case(s): 9 mutant(s) of the derivation (no realisation, ungrounded column, undescribed "
        f"relation, unparseable predicate, dangling anchor, transform matching no target column, "
        f"key->value across two relations, a column with no key under '0..1', an unmeasured second "
        f"clause) and 8 negative control(s) (one holding shape per kind, an empty population, a "
        f"scalar CASE that must not read as a list, a folded SQL block whose CASE must bind to its "
        f"own alias)"
    )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
