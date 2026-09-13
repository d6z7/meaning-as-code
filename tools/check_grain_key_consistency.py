#!/usr/bin/env python3
"""MAC008 — every consumer that collapses a fact relation must use its DECLARED cell key.

THE DEFECT, hit twice on <domain>/<dataset> and reverted once already. The measured key states the column
tuple at which exactly one row of a fact relation exists. Eight `snapshot_rule` bindings dereference
it (`params_from: profile#identity_evidence.key`) and cannot drift. Every OTHER consumer retypes it —
and a retyped key is a key that is wrong eventually:

  INT-0029    a canon binding partitioned on FOUR columns against the verified seven; the rendered
              SQL collapsed Group and the five brand roles into one arbitrary row. Reverted INT-0030.
  P-GRAIN-01  the grain property itself grouped by FIVE, named six in its prose, and called the
  P-VINT-01   result "a fully pinned cell". Both were rewritten 2026-08-19.

The comment left behind in gross_stock.yaml after the first one — "Retyping it is how INT-0029 passed
a four-column partition against a seven-column key" — did not prevent the second. A comment is not a
check. This is the check.

WHY THIS IS NOT SOLVED BY MOVING THE KEY. The obvious repair is to declare the columns somewhere more
central. It is already central: the key is a property of the RELATION and eight concepts ground on
that one relation, so hoisting it onto the ontology object would make eight copies of one fact — the
drift, restated. The gap is that a test's SQL is a static string and cannot dereference anything. So
the key stays single-homed and the CONSUMERS get compared to it.

AND A SINGLE SOURCE IS ONLY AS GOOD AS THE FACT IN IT: measured 2026-08-19, `brand_code` and
`<source>_plan_level` add ZERO discrimination to v_<source>_kpi's declared seven — grouping by five
yields the identical 12.345.147 groups. Propagating a key perfectly would have propagated two dead
columns with more confidence, which is why the key itself now carries a property (P-GRAIN-01).

SEVERITY IS ASYMMETRIC, on purpose:
  ERROR   a consumer's key is a strict SUBSET of the declared one — it collapses rows that are
          genuinely distinct, and every SUM over the result silently double-counts.
  WARNING a consumer's key is a strict SUPERSET — over-partitioning collapses nothing, so it cannot
          double-count; it can only fail to collapse. Loud enough to see, not a build-stopper.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import sqlglot
    from sqlglot import exp
except ImportError:  # pragma: no cover
    sqlglot = None
import yaml

DIALECT = "trino"


def declared_keys(root: str) -> dict[str, tuple[str, set[str]]]:
    """relation -> (descriptor path, declared cell key). Keyed on the physical relation name."""
    out = {}
    for f in sorted(glob.glob(os.path.join(root, "data", "datasets", "*.yaml"))):
        doc = yaml.safe_load(open(f, encoding="utf-8")) or {}
        stem = os.path.basename(f)[:-5]
        key = _measured_key(root, stem)
        if not key:
            continue
        names = {stem}
        tbl = ((doc.get("table") or {}).get("name"))
        sch = ((doc.get("table") or {}).get("schema")) or ""
        if tbl:
            names |= {tbl, f"{sch}.{tbl}" if sch else tbl}
        names |= {f"{sch}.{stem}"} if sch else set()
        for n in names:
            out[n] = (os.path.relpath(f, root), set(key))
    return out


def _resolve_group_by(sel) -> set[str]:
    """The columns a SELECT groups by — resolving positional ordinals against its projection.

    `GROUP BY 1,2,3,4,5` is how both drifted properties were written, so a checker that only reads
    named GROUP BY columns would have seen nothing wrong with either.
    """
    grp = sel.args.get("group")
    if not grp:
        return set()
    proj = sel.expressions or []
    cols: set[str] = set()
    for e in (grp.expressions or []):
        if isinstance(e, exp.Literal) and e.is_int:
            i = int(e.this) - 1
            if 0 <= i < len(proj):
                cols.add(proj[i].alias_or_name)
        elif isinstance(e, exp.Column):
            cols.add(e.name)
    return cols


def collapse_keys(sql: str) -> list[tuple[str, set[str], set[str]]]:
    """Every collapse in the query: (kind, key columns, relations in scope).

    A collapse is a window PARTITION BY (the latest-vintage pin) or a GROUP BY (the grain count).
    """
    tree = sqlglot.parse_one(sql, read=DIALECT)
    ctes = {c.alias_or_name for c in tree.find_all(exp.CTE)}

    def rels_in(node) -> set[str]:
        out = set()
        scope = node
        while scope is not None and not isinstance(scope, (exp.Select, exp.Subquery)):
            scope = scope.parent
        for t in (scope or tree).find_all(exp.Table):
            if t.name in ctes:
                continue
            out.add(".".join(p for p in (t.db, t.name) if p))
            out.add(t.name)
        # a CTE-fed collapse still reads whatever the CTEs read
        if not out:
            for t in tree.find_all(exp.Table):
                if t.name not in ctes:
                    out.add(".".join(p for p in (t.db, t.name) if p))
                    out.add(t.name)
        return out

    found = []
    for w in tree.find_all(exp.Window):
        cols = {c.name for c in (w.args.get("partition_by") or []) if isinstance(c, exp.Column)}
        if cols:
            found.append(("PARTITION BY", cols, rels_in(w)))
    for s in tree.find_all(exp.Select):
        cols = _resolve_group_by(s)
        # A GROUP BY is only a GRAIN CLAIM when the query then counts the group's SIZE. Without
        # this, `GROUP BY kpi` to take a MAX — an ordinary aggregate that says nothing about the
        # cell key — is judged as a collapse that dropped six columns. First pass reported 42
        # errors, of which the grain claims were 5; the rest were arithmetic.
        counted = {e.alias_or_name for e in (s.expressions or [])
                   if any(isinstance(f, exp.Count) and isinstance(f.this, exp.Star)
                          for f in e.find_all(exp.Count))}
        # ...and that count must be COMPARED AGAINST 1 somewhere. Counting rows per group is
        # ordinary arithmetic; asserting the count is 1 is the uniqueness claim. Requiring only the
        # COUNT(*) still flagged `GROUP BY kpi` reading rows-per-measure — 15 findings, 5 real.
        claims_unique = any(
            isinstance(n, (exp.GT, exp.EQ, exp.LTE, exp.GTE, exp.NEQ))
            and {c.name for c in n.find_all(exp.Column)} & counted
            and any(l.is_int and int(l.this) == 1 for l in n.find_all(exp.Literal) if l.is_int)
            for n in tree.walk() if isinstance(n, exp.Condition))
        if cols and counted and claims_unique:
            found.append(("GROUP BY", cols, rels_in(s)))
    return found



def _measured(root, stem):
    """The relation's measured key, shaped like the block these gates used to read. ONE reader, so
    the two gates cannot disagree about where the key lives."""
    import pathlib as _pl
    p = _pl.Path(root) / "data" / "profiles" / f"{stem}.yaml"
    if not p.exists():
        return None
    d = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("identity_evidence") or {}
    return {"cell_key": d.get("key"), "key": d.get("key")} if d.get("key") else None


def _measured_key(root, stem):
    m = _measured(root, stem)
    return (m or {}).get("key") or []

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()
    if sqlglot is None:
        print("sqlglot is required", file=sys.stderr)
        return 2

    if not os.path.isdir(a.root):
        print(f"could not run: {a.root!r} is not a directory", file=sys.stderr)
        return 2

    keys = declared_keys(a.root)
    if not keys:
        # This WAS a tick and exit 0, with the adjacent text admitting the gate "went green by
        # losing its subject once already, when x-grain was retired out from under it". A pass with
        # no subject is the zero-denominator pass this estate's denominator rule exists to catch —
        # sitting inside the gate that guards double-counting. It is could-not-run.
        print("could not run: no relation in this bundle carries a measured key, so no collapse "
              "can be judged — run mac_admit_identity.py. This gate lost its subject once before, "
              "when x-grain was retired out from under it, and reported a tick.", file=sys.stderr)
        return 2

    findings, checked, attempted = [], 0, 0
    acc = os.path.join(a.root, "acceptance")
    if not os.path.isdir(acc):
        print(f"could not run: {a.root} has no acceptance plane, so no SQL can be examined",
              file=sys.stderr)
        return 2
    for fn in sorted(os.listdir(acc)):
        if not fn.endswith(".yaml"):
            continue
        doc = yaml.safe_load(open(os.path.join(acc, fn), encoding="utf-8")) or {}
        if not isinstance(doc, dict):
            continue
        for p in (doc.get("properties") or []):
            sql = p.get("sql") or ""
            if not sql:
                continue
            attempted += 1
            try:
                collapses = collapse_keys(sql)
            except Exception as e:
                # Its OWN class, with its OWN denominator. Lumped in with narrower-key collapses
                # this produced "62 collapse(s) use a key NARROWER than the declared cell key over
                # 11 collapse(s) examined" — a numerator five times its denominator, because 55 of
                # the 62 were properties whose SQL never parsed. A property the gate could not read
                # is not a property that double-counts, and every review that quoted the 62 as
                # grain errors inherited the conflation.
                findings.append({"severity": "ERROR", "kind": "unparseable",
                                 "where": f"acceptance/{fn}:{p.get('id')}",
                                 "msg": f"SQL does not parse: {type(e).__name__}: {e}"})
                continue
            for kind, cols, rels in collapses:
                # sorted(), because `rels` is a set[str] and set iteration order over
                # strings is HASH-SEEDED. Taking hit[0] from it made this gate report 62
                # narrower-key collapses under PYTHONHASHSEED=2 and 66 under 0/1/3/7/11 —
                # same commit, same input, different verdict, and which relation got blamed
                # varied too. A gate whose count moves between runs cannot be ratcheted,
                # cited in a record, or used as an admission criterion.
                hit = sorted(((r, keys[r]) for r in rels if r in keys), key=lambda x: x[0])
                if not hit:
                    continue
                rel, (desc, key) = hit[0]
                checked += 1
                if cols == key:
                    continue
                missing, extra = sorted(key - cols), sorted(cols - key)
                # A collapse that names none of the key's columns is doing something else entirely
                # (counting distinct markets, say) — not a grain claim. Only judge overlapping ones.
                if not (cols & key):
                    continue
                sev = "ERROR" if missing else "WARNING"
                findings.append({
                    "severity": sev, "kind": "narrower-key",
                    "where": f"acceptance/{fn}:{p.get('id')}",
                    "msg": (f"{kind} over {rel} uses {len(cols)} column(s); the measured key "
                            f"declares {len(key)}"
                            + (f" — MISSING {', '.join(missing)}" if missing else "")
                            + (f" — EXTRA {', '.join(extra)}" if extra else "")),
                })

    unparseable = [f for f in findings if f.get("kind") == "unparseable"]
    grain = [f for f in findings if f.get("kind") == "narrower-key"]

    if a.json:
        print(json.dumps({"attempted": attempted, "checked": checked,
                          "unparseable": len(unparseable), "findings": findings}, indent=1))
    else:
        for f in findings:
            print(f"  [{f['severity']:<7}] {f['where']}\n            {f['msg']}")
        errs = sum(1 for f in grain if f["severity"] == "ERROR")
        warns = sum(1 for f in grain if f["severity"] != "ERROR")
        # CORE §2 wants ONE PASS:/FAIL: line carrying its denominator. This gate printed a ✗/✓
        # glyph and a numerator with nothing to divide by, so the share of affected collapses could
        # not be computed from its own output — an arithmetic several reviews attempted anyway.
        if not checked and not findings:
            print(f"could not run: {a.root} — 0 collapse(s) landed on a declared cell key, so "
                  f"nothing was judged", file=sys.stderr)
            return 2
        # Two populations, two denominators. Reported on one line so neither can be quoted
        # without the other.
        census = (f"{errs} narrower over {checked} collapse(s) examined, "
                  f"{len(unparseable)} unreadable over {attempted} propert(ies) attempted")
        if errs or unparseable:
            print(f"\nFAIL: check_grain_key_consistency — {census} "
                  f"({warns} warning(s)); a narrower key double-counts, an unreadable property is "
                  f"UNKNOWN rather than clean")
        else:
            print(f"\nPASS: check_grain_key_consistency — 0 narrower over {checked} collapse(s) "
                  f"examined, 0 unreadable over {attempted} propert(ies) ({warns} warning(s))")
    if not checked and not findings:
        return 2
    return 1 if any(f["severity"] == "ERROR" for f in findings) else 0

# ---------------------------------------------------------------------------------------------
# self-test: one mutant per reject class, plus the determinism property this gate lacked.
# ---------------------------------------------------------------------------------------------

_DATASET = """\
table:
  name: sales_fact
  schema: warehouse
columns:
  - { name: region_code, type: string }
  - { name: period,      type: string }
  - { name: amount,      type: double }
"""

_PROFILE = """\
identity_evidence:
  key: [region_code, period]
"""

# A GROUP BY is only a GRAIN CLAIM here when it counts the group's size AND compares that count
# against 1 -- see collapse_keys. A plain `SUM(...) GROUP BY ...` says nothing about the cell key,
# and the first draft of these fixtures used exactly that, so collapse_keys returned [] and every
# case came back "could not run". The fixtures must speak the gate's language.
#
# NOTE, and it is a real gap: the claim is only recognised when HAVING references the COUNT's
# ALIAS (`HAVING n > 1`). The idiomatic `HAVING COUNT(*) > 1` carries no Column node, so the
# `cols & counted` test cannot match and the gate is blind to it. Widening that is a BEHAVIOUR
# change that would move this gate's finding count, so it is recorded rather than slipped in here.
#: a uniqueness probe over BOTH declared key columns -- consistent with the measured key
_SQL_OK = ("SELECT region_code, period, COUNT(*) AS n FROM warehouse.sales_fact "
           "GROUP BY region_code, period HAVING n > 1")
#: the same probe over ONE of the two -- narrower, so it collapses rows it should not
_SQL_NARROW = ("SELECT region_code, COUNT(*) AS n FROM warehouse.sales_fact "
               "GROUP BY region_code HAVING n > 1")


def _seed(root, sql: str, *, with_profile: bool = True) -> str:
    import pathlib as _pl

    r = _pl.Path(root)
    (r / "data" / "datasets").mkdir(parents=True, exist_ok=True)
    (r / "data" / "datasets" / "sales_fact.yaml").write_text(_DATASET, encoding="utf-8")
    if with_profile:
        (r / "data" / "profiles").mkdir(parents=True, exist_ok=True)
        (r / "data" / "profiles" / "sales_fact.yaml").write_text(_PROFILE, encoding="utf-8")
    (r / "acceptance").mkdir(parents=True, exist_ok=True)
    (r / "acceptance" / "properties.yaml").write_text(
        yaml.safe_dump({"properties": [{"id": "P-1", "sql": sql}]}, sort_keys=False),
        encoding="utf-8")
    return str(r)


def _run(root: str) -> int:
    import contextlib
    import io as _io

    argv = sys.argv
    sys.argv = ["check_grain_key_consistency.py", root]
    buf = _io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            return main()
    finally:
        sys.argv = argv


def _self_test() -> int:
    import subprocess
    import tempfile

    if sqlglot is None:
        print("could not run: sqlglot is required for the self-test", file=sys.stderr)
        return 2

    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        cases = {
            # name                        (seeder, expected exit)
            "clean-consistent-collapse":  (lambda d: _seed(d, _SQL_OK), 0),
            "narrower-than-declared-key": (lambda d: _seed(d, _SQL_NARROW), 1),
            "unparseable-sql":            (lambda d: _seed(d, "SELECT FROM FROM"), 1),
            # the class that used to print a tick: no measured key anywhere
            "no-declared-key-at-all":     (lambda d: _seed(d, _SQL_OK, with_profile=False), 2),
        }
        for name, (seed, expect) in cases.items():
            root = os.path.join(tmp, name)
            os.makedirs(root, exist_ok=True)
            seed(root)
            # prove the fixture really seeded what the class needs
            has_key = bool(declared_keys(root))
            if (name == "no-declared-key-at-all") == has_key:
                failures.append(f"fixture {name!r} was not seeded as intended")
                continue
            got = _run(root)
            if got != expect:
                failures.append(f"{name}: expected exit {expect}, got {got}")

        # THE property this gate lacked: the same input must give the same answer. Run in
        # subprocesses, because PYTHONHASHSEED is fixed at interpreter start.
        root = os.path.join(tmp, "determinism")
        os.makedirs(root, exist_ok=True)
        _seed(root, _SQL_NARROW)
        seen = set()
        for sd in ("0", "1", "2", "3", "7"):
            env = {**os.environ, "PYTHONHASHSEED": sd}
            r = subprocess.run([sys.executable, os.path.abspath(__file__), root],
                               capture_output=True, text=True, env=env)
            seen.add((r.returncode, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""))
        if len(seen) != 1:
            failures.append(f"non-deterministic across PYTHONHASHSEED: {len(seen)} distinct "
                            f"verdicts — {sorted(v[1][:60] for v in seen)}")

    total = len(_FIX_TOTAL := 4) + 1 + 1 if False else 4 + 4 + 1
    if failures:
        print(f"FAIL: check_grain_key_consistency self-test — {len(failures)} of {total} failed")
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"PASS: check_grain_key_consistency self-test — {total}/{total} "
          f"(4 reject classes incl. the lost-subject refusal, 4 seeding assertions, and the same "
          f"verdict under 5 hash seeds)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
