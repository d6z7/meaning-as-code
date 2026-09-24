"""encodability.py — can the MAC Intent express the QUESTIONS THIRD PARTIES ASK?

LEG C, STAGE 4 (PIPELINE_TESTING.md §8.2). The instrument behind claim **C1 EXPRESSIVENESS**,
and the thing that can kill it: a large fraction of an external corpus that no Intent can encode.

WHAT IT DOES. Parses each gold SQL of a third-party corpus and decides whether a query of that
SHAPE maps onto `Intent`'s fields — a single SELECT, at most one aggregate, plain grouping columns,
a conjunctive WHERE over the eight declared operators, one ordering key, a limit. Anything else is
BLOCKED and the blocking feature is named. The output is a rate with a denominator and a ranked
list of the features that cost us the most questions.

WHAT IT DELIBERATELY DOES NOT DO. It does not build an Intent. Constructing one needs a term
vocabulary — table -> concept, column -> term — which is a BUNDLE, and no bundle exists for BIRD or
Spider. That is stage 7. Separating them is what makes this number reachable today.

THE LIMIT, AND IT BOUNDS EVERY NUMBER THIS PRODUCES. A gold query is one IMPLEMENTATION of one
INTERPRETATION of the question. It is not the only SQL that answers it, and gold SQL is very often
written more elaborately than the question requires — a CTE where a GROUP BY would do. So a
BLOCKED verdict means "we could not express THIS query", never "we could not answer that question".
**The rate is therefore a LOWER BOUND on expressiveness, and the blocker histogram is the sound
part of the output**: if 13 % of gold queries need CASE WHEN, conditional aggregation is worth a
design conversation whether or not those questions have simpler answers.

Run:
    python benchmark/encodability.py <corpus.json|parquet> [--dialect sqlite] [--json out.json]
    python benchmark/encodability.py --self-test
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

import sqlglot
from sqlglot import exp

#: Verified against this sqlglot. The AST arg names are NOT stable across majors (see `cte` below);
#: node types are. Prefer `find_all` over `args.get` for anything this report depends on.
_SQLGLOT_VERIFIED = "30.18.0"

# --------------------------------------------------------------------------- #
# WHAT THE INTENT CAN CARRY — mirrored from mac_runtime.models.FilterOp.
# A spelling here that the runtime does not have is a lie the whole report rests on, so the
# self-test seeds a mutant for it (see _SELF_TEST).
# --------------------------------------------------------------------------- #

#: The eight declared comparison operators, as sqlglot node types.
_OPS_OK = (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.In)

#: BETWEEN desugars to two comparisons, so it costs nothing the Intent cannot carry.
_OPS_DESUGAR = (exp.Between,)

#: Blockers already DECLARED in grammar/query_grammar.yaml#not_expressible. Kept apart from the
#: rest so the report says which gaps we already knew about and which this run discovered.
#: FEATURES A BUNDLE ABSORBS, and the correction that produced this list.
#: The first cut of this classifier called these BLOCKED and was measuring the wrong system.
#: MAC never asks the Intent to carry a measure's arithmetic: a bundle DECLARES the measure --
#: Contoso's `net_sales_amount` is literally `Quantity * NetPrice` in a rule template -- and the
#: Intent only names the subject. So `Free Meal Count / Enrollment` is not a grammar gap, it is an
#: unwritten declaration, which is what ontology authoring IS.
#:
#: THIS BUCKET IS AN UPPER BOUND AND MUST BE READ AS ONE. It asserts that a rule COULD be written,
#: which only a real bundle can confirm -- and a rule template is fixed SQL, so a conditional whose
#: branch depends on a value named in the question may not be reachable. Verified at stage 7, not
#: here.
DECLARABLE = {
    "computed_select_column",     # arithmetic over columns -> a derived measure
    "arithmetic_over_aggregate",  # SUM(a)/SUM(b) -> `denominator`, or a rule
    "case_when",                  # conditional aggregation -> a rule template
    "outer_join",                 # rule templates already carry LEFT JOIN (net_revenue/refunds)
    "antijoin_except",            # EXCEPT -> the `exists` operation
}

DECLARED_GAPS = {
    "having": "having",
    "null_test": "null_test",
    "subquery_in_where": "correlated_subquery_filter",
    "negation_over_nullable": "negation_over_nullable",
}


def _blockers(tree: exp.Expression) -> list[str]:
    """Every reason a query of this shape cannot become an Intent. Empty list = encodable."""
    found: list[str] = []

    def add(name: str) -> None:
        if name not in found:
            found.append(name)

    # --- shape of the statement itself -------------------------------------
    if not isinstance(tree, exp.Select):
        # a set operation, or something that is not a query at all
        if isinstance(tree, exp.Except):
            add("antijoin_except")
        elif isinstance(tree, exp.SetOperation):
            add("set_operation")
        else:
            add("not_a_select")
        return found
    # NODE SEARCH, NOT AN ARG NAME. sqlglot 30 renamed `with` -> `with_` and `from` -> `from_`,
    # so `args.get("with")` reads None on every CTE and the classifier silently passed them.
    # Caught by the self-test, which is the whole reason it seeds one mutant per reject class.
    if list(tree.find_all(exp.With)):
        add("cte")
    # EXCEPT IS NOT A SET-OPERATION GAP. Spider writes "which X had no Y" as `A EXCEPT B`, and
    # that is exactly the Intent's `exists` operation (the planner emits NOT IN (SELECT ...)).
    # INTERSECT and UNION are genuinely beyond it: two independent row-sets combined on a key,
    # which no single Intent describes.
    for setop in tree.find_all(exp.SetOperation):
        add("antijoin_except" if isinstance(setop, exp.Except) else "set_operation")

    # a derived table in FROM, or any subquery anywhere
    for sub in tree.find_all(exp.Subquery):
        add("subquery_in_from" if isinstance(sub.parent, (exp.From, exp.Join)) else "subquery")
    where = tree.args.get("where")
    if where is not None and list(where.find_all(exp.Select)):
        add("subquery_in_where")

    # --- expressions the planner has no way to emit -------------------------
    if list(tree.find_all(exp.Window)):
        add("window_function")
    if list(tree.find_all(exp.Case)):
        add("case_when")
    if tree.args.get("having"):
        add("having")
    if list(tree.find_all(exp.Is)):
        add("null_test")
    if list(tree.find_all(exp.Like, exp.ILike)):
        add("like")

    # --- the SELECT list: at most ONE aggregate, plus plain grouping columns -
    aggs, plain, expr_cols = [], [], []
    for proj in tree.expressions:
        bare = proj.unalias() if isinstance(proj, exp.Alias) else proj
        inner = list(bare.find_all(exp.AggFunc))
        if inner:
            aggs.append(bare)
            if any(list(a.find_all(exp.AggFunc))[1:] for a in inner):
                add("nested_aggregate")
            # SUM(x)/SUM(y) is exactly the Intent's `denominator` (the planner renders
            # `x / NULLIF(y, 0)`), so it is ENCODABLE. But only when BOTH sides are bare
            # aggregates: `CAST(sum(a) AS REAL) * 100 / count(b)` also parses with Div on top and
            # is a different thing entirely. The first version tested `isinstance(bare, exp.Div)`
            # and waved that through -- caught by the seeded case below it.
            is_ratio = (
                isinstance(bare, exp.Div)
                and isinstance(bare.this, exp.AggFunc)
                and isinstance(bare.expression, exp.AggFunc)
            )
            if not isinstance(bare, exp.AggFunc) and not is_ratio:
                add("arithmetic_over_aggregate")
        elif isinstance(bare, exp.Column) or isinstance(bare, exp.Star):
            plain.append(bare)
        else:
            expr_cols.append(bare)
            add("computed_select_column")
    if len(aggs) > 1:
        add("multiple_aggregates")

    # --- WHERE must be a conjunction of comparisons -------------------------
    if where is not None:
        if list(where.find_all(exp.Or)):
            add("or_in_where")
        if list(where.find_all(exp.Not)):
            add("negation_over_nullable")
        # `exp.Binary` is a WIDE net -- Is and Like are Binary too, and the first version counted
        # them here AS WELL AS in their own categories. That inflated this bucket to 146 on BIRD
        # (102 Is + 38 Like) and made it look like the single largest gap when the distinct
        # residue is ~36. Both are excluded here and reported under their own names.
        for pred in where.find_all(exp.Binary, exp.Between):
            if isinstance(pred, (exp.And, exp.Or, exp.Connector, *_OPS_DESUGAR)):
                continue
            if isinstance(pred, _OPS_OK):
                continue
            if isinstance(pred, (exp.Is, exp.Like, exp.ILike)):
                continue  # counted as null_test / like
            add("expression_in_where")

    # --- ordering: the Intent carries ONE key -------------------------------
    order = tree.args.get("order")
    if order is not None and len(order.expressions) > 1:
        add("multi_key_ordering")

    # --- joins must be inner and on equality --------------------------------
    for join in tree.find_all(exp.Join):
        side = (join.side or "").upper()
        if side in {"LEFT", "RIGHT", "FULL"}:
            add("outer_join")
        on = join.args.get("on")
        if on is None and join.args.get("using") is None:
            add("cross_join")

    return found


def classify(sql: str, dialect: str = "sqlite") -> tuple[str, list[str]]:
    """(bucket, features). bucket is "encodable" | "declarable" | "blocked".

    ENCODABLE  the Intent's own fields cover this query shape, with no declaration beyond what any
               bundle has anyway.
    DECLARABLE nothing here is beyond the Intent -- the complexity sits in a measure a bundle would
               DECLARE. Upper bound: see `DECLARABLE`.
    BLOCKED    beyond the Intent and beyond any declaration. These are the real grammar gaps and
               the only bucket that should drive grammar work.
    """
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except Exception:
        return "blocked", ["parse_error"]
    if tree is None:
        return "blocked", ["parse_error"]
    feats = _blockers(tree)
    if not feats:
        return "encodable", []
    if all(f in DECLARABLE for f in feats):
        return "declarable", feats
    return "blocked", feats


# --------------------------------------------------------------------------- #
# Corpus loading — each returns [{question, sql, db, bucket}]
# --------------------------------------------------------------------------- #


def _load(path: pathlib.Path) -> list[dict]:
    if path.suffix == ".json":
        rows = json.loads(path.read_text())
        return [
            {
                "question": r.get("question", ""),
                "sql": r.get("SQL") or r.get("query") or "",
                "db": r.get("db_id", "?"),
                "bucket": r.get("difficulty", "-"),
            }
            for r in rows
        ]
    if path.suffix == ".parquet":
        import duckdb

        con = duckdb.connect()
        out = con.execute(
            f"select db_id, question, query from '{path}'"
        ).fetchall()
        return [{"db": d, "question": q, "sql": s, "bucket": "-"} for d, q, s in out]
    raise SystemExit(f"unknown corpus format: {path.suffix}")


# --------------------------------------------------------------------------- #
# THE INSTRUMENT'S OWN TEST — a gate that cannot go red is a green tick on nothing.
# One seeded case per reject class, plus one that MUST classify as encodable.
# --------------------------------------------------------------------------- #

_SELF_TEST = [
    # --- encodable: the Intent's own fields cover it -------------------------
    ("SELECT count(*) FROM t WHERE a = 1", "encodable", None),
    ("SELECT c, sum(x) FROM t JOIN u ON t.id = u.id WHERE a > 1 GROUP BY c ORDER BY sum(x) DESC LIMIT 5", "encodable", None),
    ("SELECT a FROM t WHERE b BETWEEN 1 AND 9", "encodable", None),
    # --- declarable: a bundle would declare the measure ----------------------
    ("SELECT a / b FROM t", "declarable", "computed_select_column"),
    ("SELECT sum(CASE WHEN a THEN 1 ELSE 0 END) FROM t", "declarable", "case_when"),
    # sum(a)/sum(b) is ENCODABLE, not declarable: it is exactly `Intent.denominator`, which the
    # planner renders as `x / NULLIF(y, 0)`. The first version of this case asserted otherwise and
    # the self-test caught the classifier being RIGHT and the expectation being wrong.
    ("SELECT sum(a) / sum(b) FROM t", "encodable", None),
    ("SELECT CAST(sum(a) AS REAL) * 100 / count(b) FROM t", "declarable", "arithmetic_over_aggregate"),
    ("SELECT a FROM t LEFT JOIN u ON t.id = u.id", "declarable", "outer_join"),
    ("SELECT a FROM t EXCEPT SELECT a FROM u", "declarable", "antijoin_except"),
    # --- blocked: beyond the Intent AND beyond any declaration ---------------
    ("WITH s AS (SELECT 1) SELECT * FROM s", "blocked", "cte"),
    ("SELECT a FROM t INTERSECT SELECT b FROM u", "blocked", "set_operation"),
    ("SELECT count(*) FROM (SELECT * FROM t) x", "blocked", "subquery_in_from"),
    ("SELECT a FROM t WHERE id IN (SELECT id FROM u)", "blocked", "subquery_in_where"),
    ("SELECT c, count(*) FROM t GROUP BY c HAVING count(*) > 5", "blocked", "having"),
    ("SELECT a, row_number() OVER (PARTITION BY b) FROM t", "blocked", "window_function"),
    ("SELECT a FROM t WHERE b IS NULL", "blocked", "null_test"),
    ("SELECT a FROM t WHERE b LIKE '%x%'", "blocked", "like"),
    ("SELECT a FROM t WHERE b = 1 OR c = 2", "blocked", "or_in_where"),
    ("SELECT count(*), sum(x) FROM t", "blocked", "multiple_aggregates"),
    ("SELECT a FROM t ORDER BY a, b", "blocked", "multi_key_ordering"),
    ("SELECT a FROM t WHERE x - y > 5", "blocked", "expression_in_where"),
    # Is/Like in WHERE must NOT also surface as expression_in_where -- they have their own names
    ("SELECT a FROM t WHERE b IS NULL AND c LIKE 'x%'", "blocked", "null_test"),
    # a DECLARABLE feature beside a BLOCKED one is blocked -- the bucket is the worst of them
    ("SELECT sum(CASE WHEN a THEN 1 END) FROM t GROUP BY c HAVING count(*) > 2", "blocked", "having"),
]


def _self_test() -> int:
    bad = 0
    for sql, want_bucket, want_feature in _SELF_TEST:
        bucket, feats = classify(sql)
        if bucket != want_bucket or (want_feature and want_feature not in feats):
            bad += 1
            print(f"  FAIL  {sql[:64]!r}")
            print(f"        wanted {want_bucket}/{want_feature}; got {bucket}/{feats}")
    n = len(_SELF_TEST)
    print(f"\n{'FAIL' if bad else 'OK'} — encodability self-test: {n - bad} of {n} seeded cases behaved")
    print("  (each reject class gets one mutant; a classifier that cannot reject cannot report)")
    return 1 if bad else 0


# --------------------------------------------------------------------------- #


def report(rows: list[dict], name: str, dialect: str) -> dict:
    total = len(rows)
    buckets: collections.Counter = collections.Counter()
    feat_hits: collections.Counter = collections.Counter()
    sole: collections.Counter = collections.Counter()
    by_db: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    by_bucket: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    examples: dict[str, str] = {}

    for r in rows:
        b, feats = classify(r["sql"], dialect)
        buckets[b] += 1
        by_db[r["db"]][b] += 1
        by_bucket[r["bucket"]][b] += 1
        for f in feats:
            feat_hits[f] += 1
            examples.setdefault(f, r["question"][:90])
        blocking = [f for f in feats if f not in DECLARABLE]
        if len(blocking) == 1:
            sole[blocking[0]] += 1

    enc, dec, blk = buckets["encodable"], buckets["declarable"], buckets["blocked"]
    pct = lambda n: 100.0 * n / total if total else 0.0
    print(f"\n{'=' * 80}\n{name}  —  {total} questions\n{'=' * 80}")
    print(f"  ENCODABLE   {enc:>5}  {pct(enc):>5.1f} %   the Intent's own fields cover it")
    print(f"  DECLARABLE  {dec:>5}  {pct(dec):>5.1f} %   + a measure a bundle would declare")
    print(f"  {'':<12}{'':>5}  {'':>5}     ---------------------------------")
    print(f"  reachable   {enc + dec:>5}  {pct(enc + dec):>5.1f} %   UPPER BOUND (see DECLARABLE)")
    print(f"  BLOCKED     {blk:>5}  {pct(blk):>5.1f} %   real grammar gaps")

    print("\n  GRAMMAR GAPS ONLY — 'sole' = questions this feature ALONE costs us:")
    print(f"    {'feature':<26}{'appears':>9}{'% corpus':>10}{'sole':>7}   declared?")
    for f, n in feat_hits.most_common():
        if f in DECLARABLE:
            continue
        mark = "yes: " + DECLARED_GAPS[f] if f in DECLARED_GAPS else "NO — new"
        print(f"    {f:<26}{n:>9}{pct(n):>9.1f}%{sole[f]:>7}   {mark}")

    print("\n  ABSORBED BY A DECLARATION (not grammar gaps):")
    for f, n in feat_hits.most_common():
        if f in DECLARABLE:
            print(f"    {f:<26}{n:>9}{pct(n):>9.1f}%")

    if any(k != "-" for k in by_bucket):
        print("\n  BY DIFFICULTY:      encodable  declarable   blocked")
        for b, c in sorted(by_bucket.items()):
            if b == "-":
                continue
            t = sum(c.values())
            print(f"    {b:<14}{c['encodable']:>8} {c['declarable']:>11} {c['blocked']:>9}"
                  f"   (n={t})")

    return {
        "corpus": name, "total": total,
        "encodable": enc, "declarable": dec, "blocked": blk,
        "rate_encodable": round(pct(enc), 2),
        "rate_reachable": round(pct(enc + dec), 2),
        "features": dict(feat_hits), "sole_blocker": dict(sole),
        "by_database": {k: dict(v) for k, v in by_db.items()},
        "by_bucket": {k: dict(v) for k, v in by_bucket.items() if k != "-"},
        "examples": examples,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("corpus", nargs="*", help="corpus file(s): .json (BIRD) or .parquet (Spider)")
    ap.add_argument("--dialect", default="sqlite")
    ap.add_argument("--json", help="write the full report here")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)

    if a.self_test:
        return _self_test()
    if not a.corpus:
        ap.error("a corpus path is required (or --self-test)")

    out = []
    for c in a.corpus:
        p = pathlib.Path(c)
        out.append(report(_load(p), p.stem, a.dialect))
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(out, indent=2))
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
