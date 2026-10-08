#!/usr/bin/env python3
"""check_er_projection.py — PROJECT THE ER MODEL, AND REFUSE AN EDGE THAT JOINS NOTHING.

DNA standing law 9, premise P10. A sample shows what one concept CONTAINS; the ER model shows what
the ontology CONNECTS, and it is the only artifact in which an edge that realizes nothing is
visible.

WHY THIS IS A GATE. Measured 2026-09-26, authoring example/contoso2. Thirteen edges were declared:
three fact-to-dimension with a `join_rule`, and ten same-table ones. All thirteen parsed. All
thirteen read as edges. TEN WERE INERT, because a same-table edge needs
`realized_by: "<relation>.<column>"` to name the column that realizes it, and none had one. Nothing
said so until a question failed:

    PlannerTemplateError: the qualifier(s) dim_contoso_customer are bound by nothing in its
    FROM/JOIN clauses, which bind f

"Net revenue in Germany" needs the two-hop path fact -> Customer -> Country; the second hop could
not be traversed, so the dimension was never joined. An ER projection draws 3 edges where the
ontology claims 13, and the gap IS the defect -- obvious in a picture, invisible in thirteen
correct-looking YAML blocks.

WHAT IT CHECKS
  1. every declared edge carries a realization -- a `join_rule` (two relations) or a `realized_by`
     (one relation, the column that realizes it)                               -> INERT
  2. both endpoints name concepts the ontology defines                          -> DANGLING
  3. an edge declared `foreign_key` actually carries a join predicate           -> MISLABELLED
  4. a same-table edge's `realized_by` names a column its endpoints declare     -> UNGROUNDED

WHAT IT PRINTS. The projection itself: every realized edge, grouped by whether it crosses relations
or sits inside one, with the realization that carries it. That listing IS the ER model in text --
there is no image to go stale, and a reader can see the shape and the count in one screen.

Exit 0 when every edge is realized and grounded, 1 on any finding, 2 when the bundle cannot be read.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _neighbours  # noqa: E402  — ONE home for the sibling runtime's location


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.bundle).resolve()
    try:
        _neighbours.ensure_runtime_on_path()
        from mac_runtime.ontology import OntologyIndex
    except ImportError as exc:
        print(f"REFUSED: cannot import what this gate needs ({exc})")
        return 2
    if not (root / "ontology").is_dir():
        print(f"SKIP: {root.name} has no ontology/ plane")
        return 0
    try:
        index = OntologyIndex.from_directory(str(root))
    except Exception as exc:  # noqa: BLE001 - an unreadable bundle is REFUSED, never passed
        print(f"REFUSED: {type(exc).__name__}: {str(exc)[:160]}")
        return 2

    edges = _edges(index)
    if not edges:
        print("SKIP: this bundle declares no edges")
        return 0

    findings, crossing, inside, by_rule = [], [], [], []
    for e in edges:
        eid = getattr(e, "edge_id", "?")
        frm, to = e.from_.concept, e.to.concept
        join = (getattr(e, "join_rule", None) or "").strip()
        realized = _realization(e)
        kind = getattr(e, "type", None) or ""

        missing_ends = [c for c in (frm, to) if c not in index.concepts]
        if missing_ends:
            findings.append((eid, "DANGLING", f"names {', '.join(missing_ends)}, which this "
                                              f"ontology does not define"))
            continue
        # A RULE IS THE THIRD REALIZATION, and it is not a loophole. Measured on example/contoso:
        # `order_line__converts_at__exchange_rate` carries no `join_rule` DELIBERATELY, and the
        # bundle says why -- the relationship is a three-clause conditioned join, and the single
        # equality a gate could measure (OrderDate = Date) returns 25 quotes for every one of the
        # 223 974 lines, a 25x fan-out that would write the exact defect the ExchangeRate concept's
        # own rule forbids. So the realization is the RULE that resolves it. Refusing that shape
        # would make this gate demand a predicate the bundle is right not to declare.
        resolved = _resolution(e)
        if not join and not realized and not resolved:
            # THE MESSAGE NAMES EVERY SHAPE THIS GATE LOOKED FOR. It used to name three while
            # reading three, and the key the bundle actually used — `resolved_by_construction` —
            # was not among them, so the finding sent its reader hunting a key that was never
            # missing. A gate's refusal has to be falsifiable from its own text.
            findings.append((eid, "INERT", f"{frm} -> {to} carries no `join_rule`, no "
                                           f"`realized_by`, no `resolved_by` and no "
                                           f"`resolved_by_construction`, so it joins nothing. A "
                                           f"question needing this hop is refused with an unbound "
                                           f"qualifier, not with this edge's name"))
            continue
        if kind == "foreign_key" and not join:
            findings.append((eid, "MISLABELLED", "declared `foreign_key` with no `join_rule` — a "
                                                 "foreign key IS a predicate between two relations"))
            continue
        if join:
            crossing.append((eid, frm, to, join))
            continue
        if not realized and resolved:
            by_rule.append((eid, frm, to, resolved))
            continue
        # A same-table edge: the column it names must be one its endpoints declare.
        col = realized.rsplit(".", 1)[-1]
        declared = set(index.concepts[frm].grounding.served_columns) | set(
            index.concepts[to].grounding.served_columns
        )
        if declared and col not in declared:
            findings.append((eid, "UNGROUNDED", f"`realized_by: {realized}` names a column neither "
                                                f"{frm} nor {to} declares"))
            continue
        inside.append((eid, frm, to, realized))

    # ---- the projection, printed. THIS IS THE ER MODEL -- no image to go stale. --------------
    print(f"ER PROJECTION — {root.name}: "
          f"{len(crossing) + len(inside) + len(by_rule)} realized of {len(edges)} declared\n")
    if crossing:
        print(f"  ACROSS RELATIONS ({len(crossing)}) — a real join predicate:")
        for eid, frm, to, join in sorted(crossing):
            print(f"    {frm:20} --> {to:20}  {join}")
    if inside:
        print(f"\n  WITHIN ONE RELATION ({len(inside)}) — no join; the column that realizes it:")
        for eid, frm, to, realized in sorted(inside):
            print(f"    {frm:20} --> {to:20}  {realized}")

    if by_rule:
        print(f"\n  REALIZED BY A RULE ({len(by_rule)}) — the predicate is conditioned, so a rule "
              f"carries it:")
        for eid, frm, to, resolved in sorted(by_rule):
            print(f"    {frm:20} --> {to:20}  {resolved}")

    if not findings:
        print(f"\nOK — all {len(edges)} declared edges are realized and grounded "
              f"(DNA law 9 / P10).")
        return 0
    print("\n\nAN EDGE THAT JOINS NOTHING LOOKS EXACTLY LIKE AN EDGE:\n")
    for eid, kind, why in findings:
        print(f"  {kind:12} {eid}\n      {why}\n")
    print(f"FAIL — {len(findings)} of {len(edges)} declared edges realize nothing the planner can "
          f"use.")
    return 1


def _realization(edge) -> str:
    """The edge's realization, WHICHEVER OF ITS TWO SHAPES the bundle used.

    `realized_by` is typed by the grammar as a CANON BINDING, and the parser says so at its own
    read site: "typed by the grammar as a canon binding, but bundles also write it as a [ref]". A
    plain `"dim_contoso_customer.Country"` therefore parses to an EMPTY tuple of bindings and the
    string lands in `realized_by_ref` instead.

    MEASURED 2026-09-26: reading only `realized_by`, this gate reported 10 of 13 edges INERT on a
    bundle whose every question passes — the ten same-table edges the planner was demonstrably
    using. A gate that fails a working bundle is worse than no gate, because the next person
    silences it. Read both shapes.
    """
    bindings = getattr(edge, "realized_by", None) or ()
    if bindings:
        return ", ".join(getattr(b, "udf", None) or str(b) for b in bindings)
    ref = getattr(edge, "realized_by_ref", None)
    return ref.strip() if isinstance(ref, str) else ""


def _resolution(edge) -> str:
    """The RULE that realizes this edge, when a predicate cannot carry it.

    BY CONSTRUCTION IS THE FOURTH SHAPE, and it is a BOOLEAN CLAIM rather than a pointer — which is
    why reading only the two `resolved_by*` attributes missed it. Schema v0.1.19 admitted
    `resolved_by_construction: true` as the third way a `shared_attribute` edge may say what
    computes it, beside a resolution rule and a canon binding: where the target is an enumeration
    whose canonical column IS the shared column, the register's membership already is the set, and
    there is no join to declare because BOTH ENDS SIT ON ONE RELATION.

    MEASURED ON contoso5, 2026-10-08. This gate reported `FAIL — 3 of 38 declared edges realize
    nothing the planner can use`, naming product__sold_under__brand, __belongs_to__product_category
    and __comes_in__color as INERT, while `check_edge_definition` reported `3 of 3 by-construction
    claim(s) proven against the columns` over the same three. Two gates, opposite verdicts, same
    subject. Product, Brand, Color and ProductCategory are ALL grounded on `dim_product` — Brand is
    a COLUMN OF THE PRODUCT ROW — so "revenue by brand" groups by `dim_product.brand` after the one
    join that already exists. There is nothing to join, the declaration is correct, and the FAIL was
    this gate's.

    THE DOCSTRING ABOVE `_realization` ALREADY ARGUED THIS CASE, one key earlier: "MEASURED
    2026-09-26: reading only `realized_by`, this gate reported 10 of 13 edges INERT on a bundle
    whose every question passes ... A gate that fails a working bundle is worse than no gate,
    because the next person silences it. Read both shapes." Same failure, one key later. The
    standing lesson is that WHAT COUNTS AS A REALIZATION has two authors — this gate's tuple and
    `check_edge_definition`'s reader — and until that set has one home a third shape will do this
    again.
    """
    if getattr(edge, "resolved_by_construction", None) is True:
        return "by construction (the column resolves it; both ends share one relation)"
    for attr in ("resolved_by_ref", "resolved_by"):
        got = getattr(edge, attr, None)
        if isinstance(got, str):
            # A WHITESPACE-ONLY REF IS NOT A RESOLUTION, and it used to be one. The empty-string
            # guard sat on the FIRST branch only, so `"  "` failed `got.strip()`, fell through to
            # `if got:` — where a non-empty whitespace string is TRUTHY — and came back as the
            # resolution `"  "`. The gate then counted the edge as REALIZED BY A RULE and printed a
            # blank rule name. Found by this gate's own self-test the moment it was rewritten to
            # call this function instead of re-deriving the answer inline.
            got = got.strip()
            return got.rsplit("#", 1)[-1] if got else ""
        if got:
            return str(got)
    return ""


def _edges(index) -> list:
    """Every declared edge, through the Graph's own accessors.

    `index.edges` is a `Graph`, NOT a mapping: it has `edge_ids()` and `get_edge()` and no
    `.values()`. A first version duck-typed its way through `all`/`values`/`edges` and iteration,
    found none of them, and printed "this bundle declares no edges" for a bundle with thirteen --
    a gate reporting SKIP where it should report FAIL, which is the one failure mode a gate must
    not have. Ask the object what it actually offers.
    """
    graph = getattr(index, "edges", None)
    if graph is None:
        return []
    try:
        return [graph.get_edge(eid) for eid in graph.edge_ids()]
    except AttributeError:
        return []


class _StubEdge:
    """The attributes `_realization` and `_resolution` actually read, and nothing else.

    A STUB RATHER THAN A `Graph`, because the two functions under test take an EDGE. Building a
    whole index to exercise two getattr chains would test the loader instead.
    """

    def __init__(self, **kw):
        self.join_rule = kw.get("join_rule")
        self.realized_by = kw.get("realized_by", ())
        self.realized_by_ref = kw.get("realized_by_ref")
        self.resolved_by = kw.get("resolved_by", ())
        self.resolved_by_ref = kw.get("resolved_by_ref")
        self.resolved_by_construction = kw.get("resolved_by_construction", False)


def _self_test() -> int:
    """Is an edge REALIZED, and by which of the four shapes?

    IT CALLS `_realization` AND `_resolution`. The previous version did not: it computed
    `bool(join.strip() or realized.strip())` inline and compared that to its own expectation, so
    every case was an assertion about the test's own arithmetic. It passed 4 of 4 while this gate
    was reporting FAIL on three correct edges, and it would have passed 4 of 4 with the gate's
    reader deleted. A self-test that cannot fail when the subject breaks is not evidence.

    THE FOURTH CASE-GROUP IS THE ONE THAT WAS MISSING — `resolved_by_construction`. A shape no case
    covers is a shape the gate may stop recognising silently, which is how the 2026-10-08
    contradiction with `check_edge_definition` reached a live bundle.
    """
    #: (label, edge, wants_realized)
    cases = [
        ("join_rule present                 -> realized",
         _StubEdge(join_rule="a.x = b.y"), True),
        ("realized_by_ref present           -> realized",
         _StubEdge(realized_by_ref="rel.Col"), True),
        ("resolved_by_ref present           -> realized",
         _StubEdge(resolved_by_ref="file#contract.rules.r"), True),
        ("resolved_by_construction: true    -> realized",
         _StubEdge(resolved_by_construction=True), True),
        ("resolved_by_construction: false   -> INERT",
         _StubEdge(resolved_by_construction=False), False),
        ("the STRING 'true' is not the claim -> INERT",
         _StubEdge(resolved_by_construction="true"), False),
        ("nothing at all                    -> INERT",
         _StubEdge(), False),
        ("whitespace is not a predicate      -> INERT",
         _StubEdge(join_rule="   ", realized_by_ref="  ", resolved_by_ref=" "), False),
    ]
    bad = 0
    for label, edge, want in cases:
        join = (getattr(edge, "join_rule", None) or "").strip()
        got = bool(join or _realization(edge) or _resolution(edge))
        if got != want:
            bad += 1
            print(f"  FAIL  {label}   (realized={got}, expected {want})")
    n = len(cases)
    print(f"\n{'FAIL' if bad else 'OK'} — self-test: {n - bad} of {n} seeded cases behaved")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
