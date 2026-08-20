#!/usr/bin/env python3
"""MAC008 — every consumer that collapses a fact relation must use its DECLARED cell key.

THE DEFECT, hit twice on gaps/fpl2 and reverted once already. The measured key states the column
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

AND A SINGLE SOURCE IS ONLY AS GOOD AS THE FACT IN IT: measured 2026-08-19, `brand_letter` and
`fpl_plan_level` add ZERO discrimination to v_fpl_kpi's declared seven — grouping by five yields the
identical 12.345.147 groups. Propagating a key perfectly would have propagated two dead columns with
more confidence, which is why the key itself now carries a property (P-GRAIN-01).

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
    a = ap.parse_args()
    if sqlglot is None:
        print("sqlglot is required", file=sys.stderr)
        return 2

    keys = declared_keys(a.root)
    if not keys:
        print("✓ OK — no relation carries a measured key yet; nothing to check.\n  (If that is a surprise, run mac_admit_identity.py — this gate went green by losing its\n   subject once already, when x-grain was retired out from under it.)")
        return 0

    findings, checked = [], 0
    acc = os.path.join(a.root, "acceptance")
    for fn in sorted(os.listdir(acc)) if os.path.isdir(acc) else []:
        if not fn.endswith(".yaml"):
            continue
        doc = yaml.safe_load(open(os.path.join(acc, fn), encoding="utf-8")) or {}
        if not isinstance(doc, dict):
            continue
        for p in (doc.get("properties") or []):
            sql = p.get("sql") or ""
            if not sql:
                continue
            try:
                collapses = collapse_keys(sql)
            except Exception as e:
                findings.append({"severity": "ERROR", "where": f"acceptance/{fn}:{p.get('id')}",
                                 "msg": f"SQL does not parse: {type(e).__name__}: {e}"})
                continue
            for kind, cols, rels in collapses:
                hit = [(r, keys[r]) for r in rels if r in keys]
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
                    "severity": sev, "where": f"acceptance/{fn}:{p.get('id')}",
                    "msg": (f"{kind} over {rel} uses {len(cols)} column(s); the measured key "
                            f"declares {len(key)}"
                            + (f" — MISSING {', '.join(missing)}" if missing else "")
                            + (f" — EXTRA {', '.join(extra)}" if extra else "")),
                })

    if a.json:
        print(json.dumps({"checked": checked, "findings": findings}, indent=1))
    else:
        for f in findings:
            print(f"  [{f['severity']:<7}] {f['where']}\n            {f['msg']}")
        errs = sum(1 for f in findings if f["severity"] == "ERROR")
        warns = len(findings) - errs
        if errs:
            print(f"\n✗ {errs} collapse(s) use a key NARROWER than the declared cell key "
                  f"— every SUM over them double-counts ({warns} warning(s))")
        else:
            print(f"\n✓ OK — {checked} collapse(s) over a declared cell key, all consistent "
                  f"({warns} warning(s))")
    return 1 if any(f["severity"] == "ERROR" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
