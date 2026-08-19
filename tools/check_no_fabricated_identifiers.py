#!/usr/bin/env python3
"""MAC008 — an identifier a register declares may not be BUILT by string concatenation.

THE DEFECT, caught by the operator four times in one day on gaps/fpl2. Each time a declaration
existed and was not read; each time a plausible pattern was inferred instead:

  the cell key       five columns typed from what "a cell" felt like, against a declared seven
  the status list    three LIKE patterns from memory, against a declared enumeration of nineteen
  the brand letters  inferred from 2025 volumes, against data/lookups/brand.lookup.csv
  the market codes   BUILT as  brand_letter || '_' || 'INLAND',  against dim_country_register

The last is the one this gate is for, and it is the worst of the four because it produced a FALSE
ABSENCE THAT PASSED. M-BRAND-MARKET-01 concatenated 'C' with 'INLAND' and asked the fact whether
C_INLAND existed. It does not — Skoda's Germany is C_DEUTSCHLAN — so the property recorded
`code_exists = 0` and read that as "Skoda has no Germany" rather than "I invented this code". It
stayed green while never testing Skoda's German figure at all. A wrong answer errors; a fabricated
identifier just quietly finds nothing, and nothing finding nothing looks exactly like a clean result.

The register carries the mapping, per brand, and no two are alike:
    A_INLAND · N_INLAND · V_INLAND      C_DEUTSCHLAN      E_GERMANY · S_GERMANY
No pattern generalises from the three you happen to have looked at, which is precisely why the
inference felt safe.

WHAT IT CHECKS: any SQL concatenation (`a || b`, CONCAT(...)) whose result is compared against, or
joined to, a column that some register or foreign key declares as a key. Those identifiers must be
LOOKED UP, never assembled.

DELIBERATELY NOT FLAGGED, because concatenation is legitimate everywhere else: building a display
label, a composite sort key, a message, or a value compared only against another concatenation. The
gate fires on the join, not on the operator.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

try:
    import sqlglot
    from sqlglot import exp
except ImportError:  # pragma: no cover
    sqlglot = None
import yaml

DIALECT = "trino"


def declared_key_columns(root: str) -> dict[str, list[str]]:
    """column name -> the declarations that say it is a looked-up identifier."""
    out: dict[str, list[str]] = {}

    def add(col: str, why: str):
        out.setdefault(col, [])
        if why not in out[col]:
            out[col].append(why)

    for f in sorted(glob.glob(os.path.join(root, "data", "datasets", "*.yaml"))):
        doc = yaml.safe_load(open(f, encoding="utf-8")) or {}
        rel = os.path.relpath(f, root)
        for fk in (doc.get("foreign_keys") or []):
            if fk.get("from_column"):
                add(str(fk["from_column"]), f"{rel} declares FK -> {fk.get('to_table')}")
        # the grain key is the other place a column is stated to BE an identifier
        for c in ((doc.get("x-grain") or {}).get("cell_key") or []):
            add(str(c), f"{rel}#x-grain.cell_key")

    # a register's own key columns: any lookup csv header whose name also appears as a fact column
    for f in sorted(glob.glob(os.path.join(root, "data", "lookups", "*.csv"))):
        try:
            header = open(f, encoding="utf-8").readline().strip().split(",")
        except OSError:
            continue
        rel = os.path.relpath(f, root)
        for h in header[:1]:  # the first column is the register's key by convention
            if h:
                add(h.strip(), f"{rel} is the register keyed on it")
    return out


def concat_join_violations(sql: str, keys: dict[str, list[str]]) -> list[dict]:
    """Every place a concatenation is compared to a declared identifier column."""
    tree = sqlglot.parse_one(sql, read=DIALECT)
    found = []

    def is_concat(node) -> bool:
        return isinstance(node, (exp.DPipe, exp.Concat))

    def cols_of(node) -> set[str]:
        return {c.name for c in node.find_all(exp.Column)} if node is not None else set()

    for node in tree.find_all(exp.EQ, exp.In, exp.NEQ):
        left = node.this
        right = node.expression if not isinstance(node, exp.In) else None
        sides = [s for s in (left, right) if s is not None]
        if isinstance(node, exp.In):
            sides += list(node.expressions or [])
        cat = next((s for s in sides if is_concat(s)), None)
        if cat is None:
            continue
        other = next((s for s in sides if s is not cat), None)
        # a concatenation compared to ANOTHER concatenation is fine — neither is claimed to be real
        if other is None or is_concat(other):
            continue
        for name in cols_of(other):
            if name in keys:
                found.append({
                    "column": name,
                    "declared_by": keys[name],
                    "built_from": sorted(cols_of(cat)) or ["literals only"],
                    "sql": cat.sql(dialect=DIALECT)[:90],
                })
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if sqlglot is None:
        print("sqlglot is required", file=sys.stderr)
        return 2

    keys = declared_key_columns(a.root)
    findings, checked = [], 0
    acc = os.path.join(a.root, "acceptance")
    for fn in sorted(os.listdir(acc)) if os.path.isdir(acc) else []:
        if not fn.endswith(".yaml"):
            continue
        doc = yaml.safe_load(open(os.path.join(acc, fn), encoding="utf-8")) or {}
        if not isinstance(doc, dict):
            continue
        for p in (doc.get("properties") or []):
            if not p.get("sql"):
                continue
            checked += 1
            try:
                for v in concat_join_violations(p["sql"], keys):
                    findings.append({"where": f"acceptance/{fn}:{p.get('id')}", **v})
            except Exception as e:
                findings.append({"where": f"acceptance/{fn}:{p.get('id')}",
                                 "column": "?", "declared_by": [f"SQL did not parse: {e}"],
                                 "built_from": [], "sql": ""})

    if a.json:
        print(json.dumps({"checked": checked, "findings": findings}, indent=1, ensure_ascii=False))
        return 1 if findings else 0

    for f in findings:
        print(f"  [ERROR] {f['where']}")
        print(f"          builds {f['column']!r} as  {f['sql']}")
        print(f"          but it is a LOOKED-UP identifier: {'; '.join(f['declared_by'])}")
        print(f"          resolve it through the register instead of assembling it")
    if findings:
        print(f"\n✗ {len(findings)} fabricated identifier(s) over {checked} propert(ies) — a built key "
              f"that does not exist returns nothing, and nothing looks exactly like a clean result")
        return 1
    print(f"✓ OK — {checked} propert(ies); no declared identifier is built by concatenation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
