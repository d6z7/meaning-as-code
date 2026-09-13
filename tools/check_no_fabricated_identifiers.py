#!/usr/bin/env python3
"""MAC008 — an identifier a register declares may not be BUILT by string concatenation.

THE DEFECT, caught by the operator four times in one day on <domain>/<dataset>. Each time a declaration
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


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _plugin  # noqa: E402  — the bundle-plugin seam, shared by five tools


def _resolver(root):
    """The bundle owns how its declarations resolve; this checker owns the analysis.

    Without it the SQL is parsed with `@cols:` slots still in it, every parse fails, and each
    failure is reported as a fabricated identifier — 3 findings became 56 the moment properties
    started RENDERING their value sets instead of typing them. A checker that punishes the correct
    pattern is worse than no checker.

    That is also why this may not fall back SILENTLY. It used to guard the import with
    `except Exception: pass` and degrade to identity, which reproduced the 56-finding state on any
    machine missing the plugin's dependencies — and `SystemExit`, which is what the plugin actually
    raises for a missing dependency, is not an Exception and escaped the guard entirely. The seam
    now lives in `_plugin`: declared-but-unusable is UNRUNNABLE, and only a bundle that declares no
    plugin gets identity. Raises PluginUnavailable; the caller turns that into exit 2.
    """
    return _plugin.optional(root, "resolve_declared", lambda x: x)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if sqlglot is None:
        print("sqlglot is required", file=sys.stderr)
        return 2

    # ------------------------------------------------------------------------------------------
    # A gate must never be able to pass having measured nothing. Run against a nonexistent
    # directory this printed a tick and exited 0; run against either of the framework's own
    # example bundles it examined ZERO properties and passed. Both are the failure this gate was
    # written to catch, committed by the gate. Each condition below is therefore COULD NOT RUN.
    # ------------------------------------------------------------------------------------------
    if not os.path.isdir(a.root):
        print(f"could not run: {a.root!r} is not a directory", file=sys.stderr)
        return 2

    keys = declared_key_columns(a.root)
    if not keys:
        # With no declared identifier there is nothing a concatenation could fabricate, so a pass
        # here would mean "found none" when it means "could not look".
        print(f"could not run: {a.root} declares no looked-up identifier — no foreign key, no "
              f"x-grain cell key and no register under data/lookups", file=sys.stderr)
        return 2

    acc = os.path.join(a.root, "acceptance")
    if not os.path.isdir(acc):
        print(f"could not run: {a.root} has no acceptance plane, so no SQL can be examined",
              file=sys.stderr)
        return 2

    findings, checked = [], 0
    try:
        _RESOLVE = _resolver(a.root)
    except _plugin.PluginUnavailable as exc:
        # NOT a finding: with slots unresolved every parse fails and each failure would read
        # as a fabricated identifier — a false report of an invariant breach.
        print(f"could not run: {a.root} {exc}", file=sys.stderr)
        return 2
    for fn in sorted(os.listdir(acc)):
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
                for v in concat_join_violations(_RESOLVE(p["sql"]), keys):
                    findings.append({"where": f"acceptance/{fn}:{p.get('id')}", **v})
            except Exception as e:
                findings.append({"where": f"acceptance/{fn}:{p.get('id')}",
                                 "column": "?", "declared_by": [f"SQL did not parse: {e}"],
                                 "built_from": [], "sql": ""})

    if not checked:
        print(f"could not run: {a.root} has an acceptance plane but no property carries SQL — "
              f"0 examined, which is not the same as clean", file=sys.stderr)
        return 2

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


# -------------------------------------------------------------------------------------------------
# self-test: one mutant per reject class, plus a clean fixture that must pass. The gate had none,
# and §6.4 of the review found it passing on a nonexistent directory and on both example bundles.
# Fixtures are domain-neutral on purpose: this repository is public.
# -------------------------------------------------------------------------------------------------

_DATASET = """\
name: sales_fact
foreign_keys:
  - from_column: region_code
    to_table: region_register
"""

_CLEAN_SQL = "SELECT n FROM sales_fact WHERE region_code = 'NORTH_A'"
_BUILT_SQL = "SELECT n FROM sales_fact WHERE region_code = country_code || '_' || 'NORTH'"


def _fixture(base: str, kind: str) -> str:
    """Seed one bundle. Returns its root. `kind` names the reject class being provoked."""
    root = os.path.join(base, kind)
    ds = os.path.join(root, "data", "datasets")
    acc = os.path.join(root, "acceptance")

    if kind != "not-a-directory":
        os.makedirs(ds, exist_ok=True)
        if kind != "no-declared-key":
            with open(os.path.join(ds, "sales_fact.yaml"), "w", encoding="utf-8") as fh:
                fh.write(_DATASET)
        else:
            # a dataset that declares no key at all
            with open(os.path.join(ds, "sales_fact.yaml"), "w", encoding="utf-8") as fh:
                fh.write("name: sales_fact\n")

    if kind not in ("not-a-directory", "no-acceptance-plane", "no-declared-key"):
        os.makedirs(acc, exist_ok=True)
        props = []
        if kind == "zero-properties-with-sql":
            props = [{"id": "P-NO-SQL", "note": "carries no sql key"}]
        elif kind == "fabricated-identifier":
            props = [{"id": "P-BUILT", "sql": _BUILT_SQL}]
        elif kind == "clean":
            props = [{"id": "P-LOOKED-UP", "sql": _CLEAN_SQL}]
        with open(os.path.join(acc, "properties.yaml"), "w", encoding="utf-8") as fh:
            yaml.safe_dump({"properties": props}, fh, sort_keys=False)
    elif kind == "no-acceptance-plane":
        os.makedirs(ds, exist_ok=True)
    return root


def _run(root: str) -> int:
    """Invoke main() exactly as a caller would, with argv swapped."""
    argv = sys.argv
    sys.argv = ["check_no_fabricated_identifiers.py", root]
    try:
        return main()
    finally:
        sys.argv = argv


#: reject class -> the exit code the contract requires
_EXPECT = {
    "not-a-directory":          2,
    "no-declared-key":          2,
    "no-acceptance-plane":      2,
    "zero-properties-with-sql": 2,
    "fabricated-identifier":    1,   # liveness: the gate must still FIRE on the real defect
    "clean":                    0,
}


def _self_test() -> int:
    import tempfile

    if sqlglot is None:
        print("FAIL: check_no_fabricated_identifiers self-test — sqlglot is required", file=sys.stderr)
        return 2

    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for kind, expect in _EXPECT.items():
            root = _fixture(tmp, kind)

            # A mutant that did not mutate passes for the wrong reason. Assert the seeding.
            seeded = os.path.isdir(root)
            if (kind == "not-a-directory") == seeded:
                failures.append(f"fixture {kind!r} was not seeded as intended")
                continue
            if kind == "no-acceptance-plane" and os.path.isdir(os.path.join(root, "acceptance")):
                failures.append("fixture 'no-acceptance-plane' has an acceptance plane")
                continue

            got = _run(root)
            if got != expect:
                failures.append(f"{kind}: expected exit {expect}, got {got}")

    total = len(_EXPECT) + 2
    if failures:
        print(f"FAIL: check_no_fabricated_identifiers self-test — "
              f"{len(failures)} of {total} assertions failed")
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"PASS: check_no_fabricated_identifiers self-test — {total}/{total} "
          f"({sum(1 for v in _EXPECT.values() if v == 2)} could-not-run classes refuse, "
          f"the fabrication still fires, the clean fixture passes, seeding asserted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test() if "--self-test" in sys.argv else main())
