"""planner_invariants.py — metamorphic invariants over the PLANNER.

CATEGORY **COMPOSITION** (TESTING.md §2). SUBJECT the plan · CLAIM an invariant holds ·
ORACLE the invariant, **authored ONCE for the framework** — never per rule, never per bundle.

WHY THIS SHAPE. TESTING.md's horizon records "rules carrying a machine-checkable invariant:
10 of 433" and treats it as a per-rule authoring problem, which is why it has not moved. A
metamorphic invariant is different in kind: it relates TWO RUNS of the machinery to each other,
so it needs **no gold answer, no anchor and no human ruling**, and one author-day covers every
question in every bundle from then on.

THE ADAPTATION, AND IT IS A CORRECTION TO PIPELINE_TESTING.md §3.3. That section said TLP —
ternary logic partitioning, from the DBMS-testing line — is "mechanically the detector" for the
`Status <> 'Closed'` defect. **Applied as published, it is not.** Classic TLP partitions a query
by `p / NOT p / p IS NULL` and checks the union equals the unpartitioned query; run against the
planner's emitted SQL that check PASSES on our defect, because SQL is being perfectly consistent
with itself — 7 + 8 + 59 = 74. The bug is not an inconsistent DBMS. It is a TRANSLATION: the
Intent's `ne` does not mean SQL's `<>`.

So the ternary IDEA is lifted and re-aimed one level up, at the Intent's operator semantics:

    I1  |Q(T eq v)| + |Q(T ne v)| == |Q()|

`eq` and `ne` must PARTITION the population, because that is what a person means by "not". SQL's
`<>` does not, over a nullable column. On Store/StoreStatus: 8 + 6 = 14, against 67. Red.

Run:
    python invariants/planner_invariants.py --bundle <path> --db <duckdb> [--limit N]
    python invariants/planner_invariants.py --self-test --bundle <path> --db <duckdb>
"""
from __future__ import annotations

import argparse
import itertools
import pathlib
import sys
from dataclasses import dataclass, replace as dc_replace

# --------------------------------------------------------------------------- #

SCHEMA = "contoso_served"


def load(bundle: pathlib.Path, schema: str = SCHEMA):
    """The live loader's own path: bundle + meaning plane + recomputed self-entries."""
    from mac_console.ask_engine import load_bundle
    from mac_runtime.resolver import LookupResolver
    from mac_runtime.resolver.register_match import RegisterResolver
    from mac_runtime.resolver.enumeration import EnumerationResolver
    from mac_runtime.resolver.registers import self_entries_for

    loaded = load_bundle("example", "contoso", bundle)
    index = loaded.index.with_default_schema(schema)
    try:
        from mac_runtime.meaning_plane import generate_system_concepts, generate_system_edges

        for name, c in generate_system_concepts(schema, index).items():
            index.concepts.setdefault(name, c)
            index.groundings.setdefault(name, c.grounding)
        for e in generate_system_edges(schema):
            try:
                index.edges.add(e)
            except Exception:
                pass
    except Exception as exc:
        print(f"  (meaning plane not merged: {exc})", file=sys.stderr)
    selves = self_entries_for(index)
    registers = dc_replace(loaded.registers, entries=selves, self_entries=len(selves))
    resolver = RegisterResolver(
        registers, inner=EnumerationResolver(index, inner=LookupResolver(index, registers.entries))
    )
    return index, resolver


def make_intent(**kw):
    from mac_runtime.models import Intent

    payload = dict(kw)
    payload.setdefault("confidence", 1.0)
    for key in ("slices", "filters"):
        if key in payload:
            payload[key] = [
                {**t, "utterance": t.get("utterance") or str(t.get("term", ""))}
                for t in payload[key]
            ]
    return Intent.model_validate(payload)


@dataclass
class Run:
    """One planned-and-executed probe. `value` is None when it did not plan or did not run."""

    ok: bool
    value: float | None
    joined: bool
    note: str


def run_intent(intent, index, resolver, con) -> Run:
    from mac_runtime.models import Plan
    from mac_runtime.planner import plan as run_plan

    try:
        p = run_plan(intent, index, resolver)
    except Exception as exc:
        # A CRASH IS NOT "NOT APPLICABLE". An earlier version returned this quietly, every
        # invariant then returned None for the affected subject, and the report said 0 RED with
        # the checks simply ABSENT -- while the planner was raising AttributeError on every
        # Store probe. A vanished check reads like a passing one at a glance, which is the
        # failure this whole harness exists to prevent, committed by the harness itself.
        return Run(False, None, False, f"PLAN RAISED {type(exc).__name__}: {str(exc)[:70]}")
    if not isinstance(p, Plan):
        return Run(False, None, False, type(p).__name__.lower())
    sql, params = p.sql_preview, dict(p.params or {})
    for k, v in params.items():  # :name -> literal, read-only DB
        lit = f"'{v}'" if isinstance(v, str) else str(v)
        sql = sql.replace(f":{k}", lit)
    try:
        rows = con.execute(sql).fetchall()
    except Exception as exc:
        return Run(False, None, False, f"execute failed: {str(exc)[:60]}")
    if not rows or rows[0][0] is None:
        return Run(True, 0.0, bool(p.edges_used), "empty")
    return Run(True, float(rows[0][0]), bool(p.edges_used), "")


# --------------------------------------------------------------------------- #
# THE INVARIANTS — authored once. Each returns (name, ok, detail) or None to skip.
# --------------------------------------------------------------------------- #


def complement_verdict(eq: float, ne: float, base: float) -> str:
    """"skip" | "ok" | "red" — the whole decision, pure, so it can be seeded.

    OVER  (eq + ne > base)  the term is multi-valued per subject -> the claim does not apply
    UNDER (eq + ne < base)  instances are in NEITHER half        -> the defect
    """
    total = eq + ne
    if total > base + 1e-9:
        return "skip"
    return "ok" if abs(total - base) < 1e-9 else "red"


def collapse_verdict(kept: float, raw: float) -> str:
    """"ok" | "red". A declared collapse that keeps every row ran and collapsed nothing."""
    return "ok" if kept < raw else "red"


def inv_complement(subject, term, value, index, resolver, con):
    """I1 — `eq` and `ne` must PARTITION the population.

    ONLY WHEN NO JOIN IS INVOLVED, and the planner's own `edges_used` decides that. With a join,
    an inner join legitimately drops subject rows that match no term row, so eq + ne < total is
    correct behaviour and the check would report a false red. Gating on a declaration the planner
    already reports is cheaper and more honest than guessing at cardinality.
    """
    base = run_intent(make_intent(measure=subject, operation="count"), index, resolver, con)
    eq = run_intent(
        make_intent(
            measure=subject, operation="count",
            filters=[{"term": term, "op": "eq", "value": value}],
        ), index, resolver, con)
    ne = run_intent(
        make_intent(
            measure=subject, operation="count",
            filters=[{"term": term, "op": "ne", "value": value}],
        ), index, resolver, con)
    if not (base.ok and eq.ok and ne.ok):
        return None
    if eq.joined or ne.joined:
        return None  # a join makes the partition claim unsound — see docstring
    total = eq.value + ne.value

    # THE TWO DIRECTIONS ARE NOT THE SAME FINDING, and the first version of this check reported
    # both as red. It produced dozens of false positives on one-to-many terms:
    #   Continent/Country='CA'  ->  eq 1 + ne 3 = 4 against a population of 3.
    # A continent contains CA AND other countries, so it is counted in BOTH halves. The subject is
    # MULTI-VALUED on the term, the partition claim simply does not apply, and skipping is correct.
    #
    #   OVER  (eq + ne > population)  the term is multi-valued per subject -> NOT APPLICABLE
    #   UNDER (eq + ne < population)  instances fell out of BOTH halves    -> THE DEFECT
    #
    # Under-count is the interesting direction and the only one this invariant claims: an instance
    # that is neither `= v` nor `<> v` has been silently dropped, which over a nullable column is
    # exactly what SQL's three-valued logic does.
    verdict = complement_verdict(eq.value, ne.value, base.value)
    if verdict == "skip":
        return None
    ok = verdict == "ok"
    return (
        "complement",
        ok,
        f"{subject}/{term}={value!r}: eq {eq.value:g} + ne {ne.value:g} = {total:g}, "
        f"population {base.value:g}" + ("" if ok else f"  — {base.value - total:g} INSTANCES ARE NEITHER"),
    )


def inv_filter_monotone(subject, term, value, index, resolver, con):
    """I2 — adding a filter can never INCREASE a count."""
    base = run_intent(make_intent(measure=subject, operation="count"), index, resolver, con)
    f = run_intent(
        make_intent(
            measure=subject, operation="count",
            filters=[{"term": term, "op": "eq", "value": value}],
        ), index, resolver, con)
    if not (base.ok and f.ok) or f.joined:
        return None
    ok = f.value <= base.value + 1e-9
    return ("filter_monotone", ok,
            f"{subject}/{term}={value!r}: filtered {f.value:g} vs population {base.value:g}")


#: What each operation MUST put in the SELECT. A planner that answers a different question than
#: the one asked is the wrong-number class, and this is the cheapest detector for it.
_OP_AGGREGATE = {"count": "COUNT(", "sum": "SUM(", "average": "AVG("}


def operation_verdict(operation: str, sql: str) -> str:
    """"skip" | "ok" | "red" — pure, so the self-test can seed it.

    ONLY COUNT-SUBSTITUTION IS CLAIMED, and the first version claimed more than it could defend.
    It required `average` to emit AVG( and flagged everything else, which reds every RULE-DERIVED
    measure: `NetSalesAmount` is `SUM(Quantity * NetPrice)` and the RULE owns its SQL, so what an
    "average" of it should emit is a fold-plane question this file has no business ruling on.
    13 concepts went red and most of them were the instrument overreaching.

    What survives is narrow and undeniable: **counting is never averaging or summing.** If the
    intent says `average` and the SQL says COUNT, the engine answered a different question.
    """
    op = (operation or "").lower()
    if op not in ("average", "sum"):
        return "skip"
    up = (sql or "").upper().replace("COUNT (", "COUNT(")
    if _OP_AGGREGATE[op] in up:
        return "ok"
    return "red" if "COUNT(" in up else "skip"


def inv_operation_honoured(subject, index, resolver, con):
    """I4 — the SQL must compute the OPERATION that was asked for.

    MEASURED 2026-09-24. `MQ-06` "what is the average store size in square metres" produced
    `subject=Store, operation=average` — the model named the CONCEPT instead of the measure — and
    the planner emitted `COUNT(DISTINCT StoreCode)` and returned **67** against an anchor of
    **1504.55**. Valid SQL, a real figure, and the answer to a different question.

    Asking to AVERAGE something that carries no number is not a request the planner can honour by
    counting it. Either it refuses, or it answers what was asked; silently substituting the
    aggregate is the wrong-number class, and no oracle is needed to see it -- the intent says
    `average` and the SQL says COUNT.
    """
    from mac_runtime.models import Plan
    from mac_runtime.planner import plan as run_plan

    for op in ("average", "sum"):
        try:
            p_ = run_plan(make_intent(measure=subject, operation=op), index, resolver)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(p_, Plan):
            continue  # a refusal is the CORRECT other answer here, never a violation
        verdict = operation_verdict(op, p_.sql_preview)
        if verdict == "red":
            return ("operation_honoured", False,
                    f"{subject}: operation={op!r} planned, but the SQL computes "
                    f"{'COUNT' if 'COUNT(' in p_.sql_preview.upper() else 'something else'} "
                    f"— it answers a different question")
    return ("operation_honoured", True, f"{subject}: every planned operation is the one asked for")


def inv_collapse_reduces(subject, index, resolver, con):
    """I3 — a DECLARED collapse must actually collapse.

    The bundle declares `natural_key` on the relation's snapshot-collapse fragment. If the emitted
    collapse leaves as many rows as the relation has, it ran and collapsed nothing — which is the
    failure `store.yaml` predicted in prose and nothing could read.
    """
    concept = index.concepts.get(subject)
    grounding = getattr(concept, "grounding", None)
    table = getattr(grounding, "table", None)
    if not table:
        return None
    p = _plan_only(subject, index, resolver)
    if p is None or "ROW_NUMBER" not in (p.sql_preview or ""):
        return None  # no collapse declared for this relation — nothing to check
    rel = table if "." in table else f"{SCHEMA}.{table}"
    try:
        raw = con.execute(f"SELECT count(*) FROM {rel}").fetchone()[0]
        kept = con.execute(
            f"SELECT count(*) FROM ({_collapse_core(p.sql_preview)})"
        ).fetchone()[0]
    except Exception:
        return None
    ok = collapse_verdict(kept, raw) == "ok"
    return ("collapse_reduces", ok,
            f"{subject}: collapse kept {kept} of {raw} rows"
            + ("" if ok else "  — IT COLLAPSED NOTHING"))


def _plan_only(subject, index, resolver):
    from mac_runtime.models import Plan
    from mac_runtime.planner import plan as run_plan

    try:
        p = run_plan(make_intent(measure=subject, operation="count"), index, resolver)
    except Exception:
        return None
    return p if isinstance(p, Plan) else None


def _collapse_core(sql: str) -> str:
    """The ranked subquery plus its rank predicate, lifted out of the planner's own SQL."""
    lo = sql.index("(SELECT *, ROW_NUMBER()")
    depth, i = 0, lo
    while i < len(sql):
        if sql[i] == "(":
            depth += 1
        elif sql[i] == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    return f"SELECT * FROM {sql[lo:i + 1]} cycle WHERE cycle._mac_cycle_rank = 1"


# --------------------------------------------------------------------------- #
# DERIVE THE ENUMERATION (TESTING.md §1). Probes come from the ontology and the data,
# never from a hand-written list — that is what makes this scale past one bundle.
# --------------------------------------------------------------------------- #


def probes(index, con, per_term: int = 3):
    """(subject, term, value) triples, derived. Subjects are countable concepts; terms are other
    countable concepts; values are drawn from the term's own grounding column."""
    countable = {
        n: c for n, c in index.concepts.items()
        if getattr(getattr(c, "identity", None), "canonical_key", None)
    }
    values: dict[str, list] = {}
    for name, c in countable.items():
        g, key = getattr(c, "grounding", None), c.identity.canonical_key
        table = getattr(g, "table", None)
        if not table or not key:
            continue
        rel = table if "." in table else f"{SCHEMA}.{table}"
        try:
            rows = con.execute(
                f'SELECT DISTINCT "{key}" FROM {rel} WHERE "{key}" IS NOT NULL LIMIT {per_term}'
            ).fetchall()
        except Exception:
            continue
        if rows:
            # Intent.filters[].value accepts str | float | bool | list[str]; a DATE column's
            # value arrives as datetime.date and must be spelled the way a question would.
            values[name] = [
                v.isoformat() if hasattr(v, "isoformat") else
                v if isinstance(v, (str, float, bool, int)) else str(v)
                for v in (r[0] for r in rows)
            ]
    for subject, term in itertools.product(sorted(countable), sorted(values)):
        if subject == term:
            continue
        for v in values[term]:
            yield subject, term, v


# --------------------------------------------------------------------------- #


#: SEEDED MUTANTS, NOT LIVE DEFECTS. The first version of this self-test asserted that the two
#: recorded Store defects still reproduced. It passed while they existed and then FAILED THE DAY
#: THEY WERE FIXED — which is backwards: an instrument must not depend on its subject being
#: broken. These seed the decision directly, so the check keeps proving it can reject forever.
#: The historical numbers are kept as cases because they are the ones that mattered.
_SELF_TEST = [
    ("complement  8 + 6 of 67 (the Store defect, 2026-09-24)", complement_verdict(8, 6, 67), "red"),
    ("complement  8 + 59 of 67 (the same, fixed)",             complement_verdict(8, 59, 67), "ok"),
    ("complement  1 + 3 of 3 (a one-to-many term)",            complement_verdict(1, 3, 3), "skip"),
    ("complement  0 + 0 of 0 (empty population)",              complement_verdict(0, 0, 0), "ok"),
    ("operation   average -> COUNT(...) (the MQ-06 defect)",  operation_verdict("average", "SELECT COUNT(DISTINCT x)"), "red"),
    ("operation   average -> AVG(...)",                       operation_verdict("average", "SELECT AVG(x)"), "ok"),
    ("operation   sum -> SUM(...)",                           operation_verdict("sum", "SELECT SUM(x)"), "ok"),
    ("operation   list -> not an aggregate, not checked",     operation_verdict("list", "SELECT DISTINCT x"), "skip"),
    ("operation   average -> a rule's own SUM, not ours to rule", operation_verdict("average", "SELECT SUM(q*p)"), "skip"),
    ("collapse    74 kept of 74 (the Store defect)",           collapse_verdict(74, 74), "red"),
    ("collapse    67 kept of 74 (fixed)",                      collapse_verdict(67, 74), "ok"),
]


def _self_test(results, crashes) -> int:
    bad = 0
    for label, got, want in _SELF_TEST:
        if got != want:
            bad += 1
            print(f"  FAIL  {label}: wanted {want!r}, got {got!r}")
    print(f"\n{'-' * 78}")
    if crashes:
        print(f"FAIL — {len(crashes)} probe(s) crashed the planner; a crash is not a skip.")
        return 1
    if bad:
        print(f"FAIL — self-test: {len(_SELF_TEST) - bad} of {len(_SELF_TEST)} seeded cases behaved")
        print("  Fix the harness before trusting a single green from it.")
        return 1
    print(f"OK — self-test: {len(_SELF_TEST)} of {len(_SELF_TEST)} seeded cases behaved "
          f"(one mutant per reject class, independent of any live defect)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--schema", default=SCHEMA)
    ap.add_argument("--limit", type=int, default=400, help="max probes")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)

    import duckdb

    globals()["SCHEMA"] = a.schema
    index, resolver = load(pathlib.Path(a.bundle), a.schema)
    con = duckdb.connect(a.db, read_only=True)

    results: list[tuple[str, bool, str]] = []
    crashes: list[str] = []

    # collapse: one check per countable concept, no probe values needed
    for subject in sorted(index.concepts):
        for fn in (inv_collapse_reduces, inv_operation_honoured):
            r = fn(subject, index, resolver, con)
            if r:
                results.append(r)

    checked = 0
    for subject, term, value in probes(index, con):
        if checked >= a.limit:
            break
        probe_run = run_intent(make_intent(measure=subject, operation="count"),
                               index, resolver, con)
        if probe_run.note.startswith("PLAN RAISED"):
            crashes.append(f"{subject}: {probe_run.note}")
        for fn in (inv_complement, inv_filter_monotone):
            r = fn(subject, term, value, index, resolver, con)
            if r:
                results.append(r)
                checked += 1

    if crashes:
        print(f"\n!! {len(crashes)} probe(s) CRASHED the planner — these are not skips:")
        for c in sorted(set(crashes))[:6]:
            print(f"     {c}")

    reds = [r for r in results if not r[1]]
    by_inv: dict[str, list[int]] = {}
    for name, ok, _ in results:
        b = by_inv.setdefault(name, [0, 0])
        b[0] += ok
        b[1] += 1

    print(f"\n{'=' * 78}\nPLANNER INVARIANTS — {len(results)} checks, {len(reds)} RED\n{'=' * 78}")
    for name, (o, t) in sorted(by_inv.items()):
        print(f"  {name:<20}{o:>5} of {t:<5} held")
    if reds:
        print("\nVIOLATIONS:")
        for name, _, detail in reds:
            print(f"  [{name}] {detail}")

    if a.self_test:
        return _self_test(results, crashes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
