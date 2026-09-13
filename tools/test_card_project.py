#!/usr/bin/env python3
"""Project an acceptance property into a READABLE CARD — what it searches, with what parameters.

THE DEFECT THIS REPAIRS, measured on <domain>/<dataset>: 31 properties carried 5.161 words of `statement`
prose — median 96 words, worst 489, only 4 of 31 under 60. Asked what a test checks, a reader got an
essay. Operator, verbatim: "the prosa you provide in R-BRAND-02 is too long and unreadable ... this
shoudl be focused to the point what are you searchingi and with what parameters ... maybe in a table.
sql not interested on the surface ... but important for oracle or analysis."

THE FIX IS NOT BETTER PROSE. Almost everything a reader needs is already IN the SQL and IN the
recorded run, so it is DERIVED here rather than authored — which also means it cannot drift from the
query the way a hand-written paragraph does:

    parameters  <- literal bindings in every WHERE/JOIN in the tree (incl. inside CTEs)
    reads       <- every real table referenced
    asserted    <- assertion.columns, paired with the recorded result row
    also        <- the remaining projected columns — the controls and the context numbers

What stays AUTHORED is one line: `statement`, trimmed to its first sentence. Everything a card cannot
derive (why the ruling exists, what an SME must decide) belongs in the ontology or the DQ register,
not on the test surface.

NO NEW YAML. Reads the existing PropertiesFile slots (id/statement/assertion/sql) and the existing
run records. Emits text or --json for a renderer.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import sqlglot
    from sqlglot import exp
except ImportError:  # pragma: no cover - sqlglot ships with the framework
    sqlglot = None

import yaml

DIALECT = "trino"

# Columns whose literal bindings are the ones a reader recognises, in the order a person says them.
# Anything not listed still shows — this only fixes the ORDER, never the content.
#
# GENERIC NAMES ONLY. This list is MATCHED against real column names (`for key in PARAM_ORDER: if
# key in found`), so an entry that cannot equal a column name is dead weight that silently drops its
# parameter into the alphabetical tail. The token cleanse put four angle-bracket placeholders here —
# `<source>_date` can never match anything — and the entries that named one estate's columns were
# instance configuration in the generic instrument to begin with.
#
# An estate that wants its own columns ordered declares them in registers/card_param_order.txt;
# these are the names any bundle might carry.
PARAM_ORDER_GENERIC = [
    "role", "brand", "market", "region", "country",
    "kpi", "measure", "metric", "period", "month", "year", "date", "status",
]


def param_order() -> list:
    """The generic order, extended by whatever this estate declares. Estate entries come FIRST:
    a bundle's own column names are the ones its readers recognise."""
    import os
    from pathlib import Path as _P

    reg = _P(os.environ.get("MAC_CARD_PARAM_ORDER")
             or (_P(__file__).resolve().parent.parent / "registers" / "card_param_order.txt"))
    extra = []
    if reg.is_file():
        extra = [ln.strip() for ln in reg.read_text(encoding="utf-8").splitlines()
                 if ln.strip() and not ln.lstrip().startswith("#")]
    return extra + [k for k in PARAM_ORDER_GENERIC if k not in extra]


PARAM_ORDER = param_order()

# The de-DE display the operator requires everywhere numbers are shown.
def de(v):
    s = str(v)
    try:
        if re.fullmatch(r"-?\d+", s):
            n = int(s)
            return f"{n:,}".replace(",", ".")
        if re.fullmatch(r"-?\d+\.\d+", s):
            n = float(s)
            whole, frac = f"{n:,.4f}".split(".")
            return whole.replace(",", ".") + "," + frac.rstrip("0").ljust(1, "0")
    except (ValueError, OverflowError):
        pass
    return s


def _lit(node) -> str | None:
    """The literal value of a node, or None if it is not a literal."""
    if isinstance(node, exp.Literal):
        return node.this
    if isinstance(node, exp.Cast) and isinstance(node.this, exp.Literal):
        return node.this.this
    if isinstance(node, exp.Boolean):
        return str(node.this)
    # DATE '2025-01-31' parses as a typed literal in some dialects
    if isinstance(node, exp.DataType):
        return None
    return None


def _colname(node) -> str | None:
    return node.name if isinstance(node, exp.Column) else None


# Plumbing columns of the catalogue: real bindings, but they restate what READS already says.
CATALOGUE_COLS = {"table_name", "table_schema", "table_catalog"}


def _derived_names(tree) -> set[str]:
    """Names the query INVENTS — `expr AS x`. A binding on one of those is never a parameter.

    Three noise classes collapse into this single rule, which is why it is worth stating once:
    the latest-row pin (`rn = 1`, where rn is the ROW_NUMBER alias), the in-SQL vacuity guards
    (`CASE WHEN s_codes_in_dim_model = 0 …`, testing a count this query just computed), and any
    other self-reference. None of them pin what the test READ; they are the test's own arithmetic.
    """
    out = set()
    for a in tree.find_all(exp.Alias):
        if a.alias:
            out.add(a.alias)
    for w in tree.find_all(exp.Window):
        parent = w.parent
        if isinstance(parent, exp.Alias) and parent.alias:
            out.add(parent.alias)
    return out


def parameters(sql: str) -> list[tuple[str, str]]:
    """Every literal binding that PINNED WHAT THE TEST READ — top level, CTE, or subquery.

    Excluded on purpose, because a card that lists them buries the four bindings a reader came for:
      · comparisons between two columns          — those are joins, not parameters
      · bindings on a name the query itself derives — the test's own arithmetic (see _derived_names)
      · conditions inside CASE                   — a branch of a computation, not a filter
      · information_schema plumbing              — already stated by READS
    """
    tree = sqlglot.parse_one(sql, read=DIALECT)
    derived = _derived_names(tree)
    found: dict[str, list[str]] = {}

    def usable(node, name: str | None) -> bool:
        if not name or name in derived or name.lower() in CATALOGUE_COLS:
            return False
        anc = node.parent
        while anc is not None:
            if isinstance(anc, (exp.Case, exp.If)):
                return False
            anc = anc.parent
        return True

    def add(col: str, val: str):
        found.setdefault(col, [])
        if val not in found[col]:
            found[col].append(val)

    for node in tree.find_all(exp.EQ):
        col, other = node.this, node.expression
        if _colname(col) is None:
            col, other = other, col
        name, val = _colname(col), _lit(other)
        if usable(node, name) and val is not None:
            add(name, val)

    for node in tree.find_all(exp.In):
        name = _colname(node.this)
        vals = [_lit(e) for e in (node.expressions or [])]
        if usable(node, name) and vals and all(v is not None for v in vals):
            add(name, " · ".join(vals))

    for node in tree.find_all(exp.Between):
        name = _colname(node.this)
        lo, hi = _lit(node.args.get("low")), _lit(node.args.get("high"))
        if usable(node, name) and lo is not None and hi is not None:
            add(name, f"{lo} … {hi}")

    ordered = []
    for key in PARAM_ORDER:
        if key in found:
            ordered.append((key, " · ".join(found.pop(key))))
    for key in sorted(found):
        ordered.append((key, " · ".join(found[key])))
    return ordered


def columns(sql: str) -> set[str]:
    """Every column name the query references anywhere, minus the names it invents itself."""
    tree = sqlglot.parse_one(sql, read=DIALECT)
    derived = _derived_names(tree)
    return {c.name for c in tree.find_all(exp.Column) if c.name and c.name not in derived}


def selects(sql: str) -> dict:
    """WHAT THE QUERY IS ACTUALLY SELECTING — the disclosure a WHERE-clause list cannot give.

    Operator, on a card that rendered "Parameters: none" for a sweep:
      "i asked you to disclose what is your select statement!!! you said : parameters : none
       this cannot be ... the question is what are you selecting!?!?!?!"

    Correct. A test that pins nothing still SELECTS something, and for a grain test the whole claim
    lives in the GROUP BY — those columns ARE the cell whose uniqueness is being asserted. Showing
    only WHERE literals made the most important line of the query invisible and printed "none" over
    the top of it.
    """
    tree = sqlglot.parse_one(sql, read=DIALECT)
    derived = _derived_names(tree)
    out = {"groups": [], "partitions": [], "aggregates": []}

    for sel in tree.find_all(exp.Select):
        grp = sel.args.get("group")
        if not grp:
            continue
        proj = sel.expressions or []
        cols = []
        for e in (grp.expressions or []):
            if isinstance(e, exp.Literal) and e.is_int:
                i = int(e.this) - 1
                if 0 <= i < len(proj):
                    cols.append(proj[i].alias_or_name)
            elif isinstance(e, exp.Column):
                cols.append(e.name)
        if cols and cols not in out["groups"]:
            out["groups"].append(cols)

    for w in tree.find_all(exp.Window):
        cols = [c.name for c in (w.args.get("partition_by") or []) if isinstance(c, exp.Column)]
        order = [o.this.name for o in (w.args.get("order").expressions if w.args.get("order") else [])
                 if isinstance(o.this, exp.Column)]
        if cols and {"cols": cols, "order": order} not in out["partitions"]:
            out["partitions"].append({"cols": cols, "order": order})

    for f in tree.find_all(exp.AggFunc):
        name = f.sql(dialect=DIALECT)
        if len(name) < 60 and name not in out["aggregates"]:
            out["aggregates"].append(name)
    out["aggregates"] = out["aggregates"][:8]
    return out


def firing_rules(root: str, sql: str, params: list) -> list[dict]:
    """Which ontology rules this one test EXERCISES — derived, not declared.

    A rule already declares the columns it governs (`binds`). A test already touches columns and
    PINS some of them. So the link needs no new field and cannot go stale: a rule is exercised when
    every column it binds is present in the test's SQL, and PINNED when the test also fixes one of
    them to a literal. The distinction matters — 28 of 29 <dataset> rules bind `role` or a fact column,
    so an unranked overlap would name half the ontology for every test and mean nothing.

    Deliberately NOT claimed: that an exercised rule is a rule the test would CATCH the violation of.
    This says the test reads where the rule speaks. Proving a rule is defended needs the rule's own
    negative case, which is a different instrument.
    """
    import glob as _g
    cols = columns(sql)
    pinned = {k for k, _ in params}
    rels = set(relations(sql))
    # The kpi codes this test actually selected, if it selected any.
    pinned_kpi = {v.strip() for k, v in params if k == "kpi" for v in v.split("·")}
    out = []
    for f in sorted(_g.glob(os.path.join(root, "ontology", "concepts", "*.yaml"))):
        doc = yaml.safe_load(open(f, encoding="utf-8")) or {}
        concept = ((doc.get("concept") or {}).get("name")) or os.path.basename(f)[:-5]

        # GUARD 1 — the concept must be grounded in a relation this test reads. Column overlap
        # alone matched rules of concepts the test never touches.
        srcs = {str(s0.get("relation")) for s0 in ((doc.get("grounding") or {}).get("sources") or [])}
        if srcs and rels and not (srcs & rels):
            continue

        # GUARD 2 — a measure concept is keyed on a kpi code. If the test pinned kpi and this
        # concept's codes are not among them, its rules are not in play, however many columns
        # they share: one measure's rules were matching a test that reads only another's code.
        codes = set(((doc.get("values") or {}).get("aliases") or {}).get("map") or {})
        if pinned_kpi and codes and not (codes & pinned_kpi):
            continue

        for r in ((doc.get("contract") or {}).get("rules") or []):
            binds = set(r.get("binds") or [])
            if not binds or not binds <= cols:
                continue
            out.append({
                "id": r.get("id"), "concept": concept, "kind": r.get("kind"),
                "binds": sorted(binds),
                "pinned": sorted(binds & pinned),
                "state": "PINNED" if binds & pinned else "READ",
            })
    out.sort(key=lambda r: (r["state"] != "PINNED", -len(r["binds"]), r["id"] or ""))
    return out


def relations(sql: str) -> list[str]:
    """Every real table the query reads, catalogue-qualified, in first-seen order."""
    tree = sqlglot.parse_one(sql, read=DIALECT)
    ctes = {c.alias_or_name for c in tree.find_all(exp.CTE)}
    out: list[str] = []
    for t in tree.find_all(exp.Table):
        name = ".".join(p for p in (t.db, t.name) if p)
        if t.name in ctes or not name:
            continue
        if name not in out:
            out.append(name)
    return out


def outputs(sql: str) -> list[str]:
    """The final SELECT's projected column names, in projection order."""
    tree = sqlglot.parse_one(sql, read=DIALECT)
    sel = tree.find(exp.Select) if not isinstance(tree, exp.Select) else tree
    # The OUTERMOST select is the one whose columns reach the runner.
    for node in tree.walk():
        if isinstance(node, exp.Select) and node.parent is None:
            sel = node
            break
    return [e.alias_or_name for e in (sel.expressions or []) if e.alias_or_name]


# WHAT KIND OF CLAIM IS THIS? Operator: "are you testing fals positives , ... negatives ...
# positives ... or what — you have to communicate that". A reader shown "42 cases, 2 failed" cannot
# tell whether a number moved, an absence appeared, or the query was looking at nothing.
#
# DERIVED from the assertion, not declared, so it cannot drift from what the property actually does —
# and cross-checked against the KIND. heading the author writes, so a mismatch is a finding.
KIND_HINTS = {
    "NEGATIVE":  ("must_be_zero",),   # asserts an absence — "we searched and found nothing"
    "POSITIVE":  ("equals",),         # asserts a figure IS a named value
    "REGRESSION": ("min_value", "max_value"),  # asserts the WRONG reading stays materially different
}
# A column whose name says it exists to prove the search could have succeeded.
VACUITY_MARKERS = ("vacuity", "control", "populated", "not_vacuous", "anti_vacuity",
                   "cases_run", "_in_scope", "_present")


def declared_kind(statement: str) -> str | None:
    """The KIND. heading the author wrote, if any."""
    m = re.search(r"\bKIND\.\s*([A-Za-z\- ]+)", statement or "")
    return m.group(1).strip().upper().split()[0] if m else None


def derived_kind(prop: dict) -> dict:
    """What the assertion actually claims, and whether it carries an anti-vacuity guard."""
    at = ((prop.get("assertion") or {}).get("type")) or ""
    kind = next((k for k, types in KIND_HINTS.items() if at in types), "INVARIANT")
    sql = (prop.get("sql") or "").lower()
    cols = [c.lower() for c in ((prop.get("assertion") or {}).get("columns") or [])]
    guard = [m for m in VACUITY_MARKERS if any(m in c for c in cols)]
    # a marker in the projection but NOT asserted is a control the reader can see and the runner
    # ignores — worth distinguishing from one the assertion actually enforces
    watched = [m for m in VACUITY_MARKERS if m in sql and m not in guard]
    return {"kind": kind, "asserted_guard": guard, "unasserted_control": watched}


def _first_sentence(text: str) -> str:
    """The authored one-liner. Everything after the first sentence is prose the card replaces."""
    t = " ".join((text or "").split())
    # A leading ALL-CAPS title ("THE DEGENERATE BRAND.") is a label, not the sentence.
    m = re.match(r"^([A-Z][A-Z0-9 /\-]{6,}?)[.:]\s+(.*)$", t)
    if m:
        t = m.group(2)
    m = re.search(r"(?<=[.!?])\s+(?=[A-Z(])", t)
    return (t[: m.start()] if m else t).strip()


def card(prop: dict, result: dict | None, root: str = ".") -> dict:
    sql = prop.get("sql") or ""
    assertion = prop.get("assertion") or {}
    asserted = list(assertion.get("columns") or [])
    rows = (result or {}).get("rows") or []
    row = rows[0] if len(rows) == 1 else None

    proj = outputs(sql)
    known = set(asserted)
    params = parameters(sql)
    return {
        "selects": selects(sql),
        "kind": derived_kind(prop),
        "kind_declared": declared_kind(prop.get("statement", "")),
        "rules": firing_rules(root, sql, params),
        "id": prop.get("id"),
        "status": (result or {}).get("status", "NOT RUN"),
        "severity": prop.get("severity"),
        "purpose": _first_sentence(prop.get("statement", "")),
        "parameters": params,
        "reads": relations(sql),
        "assertion_type": assertion.get("type"),
        "tolerance": prop.get("tolerance"),
        "asserted": [(c, (row or {}).get(c)) for c in asserted],
        "also": [(c, (row or {}).get(c)) for c in proj if c not in known],
        "rows": rows,
        "n_rows": len(rows),
        "authored_words": len((prop.get("statement") or "").split()),
        # THE QUERY ITSELF. Operator, three times: "i asked you to disclose what is your select
        # statement!!!" / "the question is what are you selecting!?!?!?!" / "and you still do not
        # provide what kind of sql are you firing ?!?!". The brief was "sql not interested on the
        # surface ... but important for oracle or analysis" — which means COLLAPSED, not ABSENT. It
        # was absent.
        "sql": sql,
        "source": prop.get("source"),
        "validates": prop.get("validates") or [],
    }


# ── rendering ────────────────────────────────────────────────────────────────────────────────────
MARK = {"PASS": "✓", "FAIL": "✗", "ACCEPTED": "~", "ERROR": "!", "NOT RUN": "?"}


def render(c: dict, width: int = 84) -> str:
    L: list[str] = []
    k = c.get("kind") or {}
    tag = k.get("kind", "")
    if k.get("asserted_guard"):
        tag += " + anti-vacuity guard"
    head = f"{c['id']}  [{tag}]" if tag else f"{c['id']}"
    L.append(f"{head}  {'·' * max(1, width - len(head) - len(c['status']) - 4)}  {c['status']}")
    # A declared KIND that disagrees with what the assertion does is a finding, not a formatting nit:
    # it means the prose describes a different claim from the one the runner checks.
    if c.get("kind_declared") and c["kind_declared"] != k.get("kind"):
        L.append(f"  ! declared KIND {c['kind_declared']} but the assertion is {k.get('kind')}")
    if c["purpose"]:
        L.append(f"  {c['purpose']}")
    L.append("")

    L.append("  PARAMETERS")
    if c["parameters"]:
        w = max(len(k) for k, _ in c["parameters"])
        for k, v in c["parameters"]:
            L.append(f"    {k.ljust(w)}   {v}")
    else:
        # An empty block reads as "not derived". This test pinned NOTHING — it sweeps the whole
        # relation — and that is a stronger claim than any filter, so it is stated, not omitted.
        L.append("    (none — sweeps the entire relation, unfiltered)")
    if c["reads"]:
        L.append("")
        L.append("  READS")
        for r in c["reads"]:
            L.append(f"    {r}")

    sel = c.get("selects") or {}
    if sel.get("groups") or sel.get("partitions"):
        L.append("")
        L.append("  WHAT DEFINES A CELL  (this is what the query groups/partitions by)")
        for g in sel.get("groups", []):
            L.append(f"    GROUP BY      {', '.join(g)}   [{len(g)} col]")
        for pt in sel.get("partitions", []):
            L.append(f"    PARTITION BY  {', '.join(pt['cols'])}   [{len(pt['cols'])} col]")
            if pt["order"]:
                L.append(f"      ORDER BY    {', '.join(pt['order'])}")
    if sel.get("aggregates"):
        L.append(f"    COMPUTES      {' · '.join(sel['aggregates'])}")

    if c.get("rules"):
        L.append("")
        pin = [r for r in c["rules"] if r["state"] == "PINNED"]
        L.append(f"  RULES EXERCISED  ·  {len(c['rules'])}"
                 + (f", {len(pin)} pinned by this test" if pin else ""))
        w = max(len(r["id"] or "") for r in c["rules"])
        for r in c["rules"]:
            tag = "pins " + ", ".join(r["pinned"]) if r["pinned"] else "reads " + ", ".join(r["binds"])
            L.append(f"    {(r['id'] or '').ljust(w)}   {tag}")

    def block(title, pairs, mark=False):
        if not pairs:
            return
        L.append("")
        L.append(f"  {title}")
        w = max(len(k) for k, _ in pairs)
        for k, v in pairs:
            val = de(v) if v is not None else "—"
            tick = ""
            if mark and v is not None:
                tick = f"  {MARK.get(c['status'], '')}"
            L.append(f"    {k.ljust(w)}   {val.rjust(12)}{tick}")

    at = c["assertion_type"]
    title = (f"MUST BE {at.replace('must_be_', '').upper()}" if at and at.startswith("must_be_")
             else (at or "ASSERTED").upper())

    if c["n_rows"] > 1:
        L.append("")
        L.append(f"  {title}  ·  {de(c['n_rows'])} rows")
        cols = [k for k, _ in c["asserted"]] + [k for k, _ in c["also"]]
        cols = [k for k in cols if any(k in r for r in c["rows"])]
        vals = {k: [de(r.get(k)) if r.get(k) is not None else "—" for r in c["rows"]] for k in cols}
        w = {k: max(len(k), max((len(v) for v in vals[k]), default=0)) for k in cols}
        star = {k for k, _ in c["asserted"]}
        L.append("    " + "  ".join((("*" + k) if k in star else k).rjust(w[k] + (1 if k in star else 0))
                                    for k in cols))
        for i in range(c["n_rows"]):
            L.append("    " + "  ".join(vals[k][i].rjust(w[k] + (1 if k in star else 0)) for k in cols))
        L.append(f"    * = the asserted column ({at}"
                 + (f", tolerance {de(c['tolerance'])}" if c.get("tolerance") is not None else "") + ")")
        return "\n".join(L)

    block(title, c["asserted"], mark=True)
    block("ALSO MEASURED", c["also"])
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--id", action="append", help="only these property ids")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if sqlglot is None:
        print("sqlglot is required", file=sys.stderr)
        return 2

    acc = os.path.join(a.root, "acceptance")
    cards, failed = [], []
    listing = sorted(os.listdir(acc)) if os.path.isdir(acc) else []

    # ONE id -> result map over every recorded run. Deriving the run file from the suite file stem
    # is what made every tier-1 card read "NOT RUN": properties.yaml is recorded by
    # property_runs.json, singular. Ids are unique across suites, so the union is unambiguous.
    runs: dict = {}
    for fn in listing:
        if not fn.endswith("_runs.json"):
            continue
        doc = json.load(open(os.path.join(acc, fn), encoding="utf-8")) or {}
        for r in (doc.get("results") or []):
            if r.get("id"):
                runs[r["id"]] = r

    for fn in listing:
        if not fn.endswith(".yaml"):
            continue
        doc = yaml.safe_load(open(os.path.join(acc, fn), encoding="utf-8")) or {}
        if not isinstance(doc, dict) or not doc.get("properties"):
            continue
        for p in doc["properties"]:
            if a.id and p.get("id") not in a.id:
                continue
            try:
                cards.append(card(p, runs.get(p.get("id")), a.root))
            except Exception as e:  # a card that cannot be derived is REPORTED, never skipped
                failed.append({"id": p.get("id"), "error": f"{type(e).__name__}: {e}"})

    if a.json:
        print(json.dumps({"cards": cards, "underivable": failed}, indent=1, ensure_ascii=False))
        return 1 if failed else 0

    for c in cards:
        print(render(c))
        print()
    if failed:
        print(f"✗ {len(failed)} property/ies could not be projected:")
        for f in failed:
            print(f"    {f['id']}: {f['error']}")
        return 1
    words = sum(c["authored_words"] for c in cards)
    print(f"— {len(cards)} card(s) derived from SQL + run record; "
          f"{words} words of authored prose replaced by {sum(len(c['parameters']) for c in cards)} "
          f"parameter binding(s) and {sum(len(c['asserted']) + len(c['also']) for c in cards)} measured value(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
