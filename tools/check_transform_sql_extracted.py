#!/usr/bin/env python3
"""
check_transform_sql_extracted.py — the SQL-extraction gate for transform descriptors.

Right-first-time harvest invariant #7 (docs/HARVEST_RIGHT_FIRST_TIME.md): a transform's SQL BODY lives in
a sibling `data/transforms/<name>.sql` file; the `data/transforms/<name>.yaml` carries a `sql_file:`
pointer + prose (impurity_class / rule / guarantee), NOT the SQL body inline. This is exactly how the gold
ships it (dim_country.yaml + dim_country.sql). Inline multi-line SQL is hard to read / lint / diff and the
materialize step cannot run it directly.

A transform is COMPLIANT when it carries a `sql_file:` pointer to an existing sibling `.sql`. The gold's
transform YAMLs additionally quote short illustrative SQL fragments alongside the pointer — that is
documentation, not the body, so a present-and-resolvable `sql_file:` makes the descriptor pass regardless
of those fragments (mirrors the operator's exemplar; the pointer proves extraction happened).

RED conditions (each reported file:field):
  A. NO `sql_file:` pointer AND the descriptor embeds a SUBSTANTIAL inline SQL scalar
     (a `sql:` / `transforms[].sql:` value containing a newline or > 120 chars) — the body is trapped
     inline, un-extracted.
  B. a `sql_file:` pointer whose target sibling `.sql` does not exist (a dangling pointer).

This gate is OFFLINE and pure-structural (no AWS). It parses the YAML with a real loader, so a trailing
`# comment` on the `sql_file:` scalar is correctly stripped (not treated as part of the filename).

Usage:  python3 tools/check_transform_sql_extracted.py <bundle-root>
        exit 0 = every transform's SQL is extracted ; exit 1 = inline body or dangling pointer.

Wire into your bundle's offline gate chain (guarded on the transforms dir):
    if [ -d "$SOURCE_ROOT/data/transforms" ]; then
      echo "▶ transform-sql-extracted (check_transform_sql_extracted.py $SOURCE_ROOT)"
      "$PY" "$FW/tools/check_transform_sql_extracted.py" "$SOURCE_ROOT" || rc=1
    fi
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mac_project import resolve  # noqa: E402

MAX_INLINE = 120


def load(p: Path):
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return e


def walk(node, key: str, prefix=""):
    """Yield (jsonpath, value) for every mapping entry whose key == `key`, at any depth."""
    if isinstance(node, dict):
        for k, v in node.items():
            cur = f"{prefix}.{k}"
            if k == key:
                yield cur, v
            yield from walk(v, key, cur)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, key, f"{prefix}[{i}]")


def substantial(sql) -> bool:
    return isinstance(sql, str) and ("\n" in sql or len(sql) > MAX_INLINE)


def dangling_sql_targets(root: Path) -> list[str]:
    """Every `produces.sql_file` naming a file the bundle does not carry.

    THE FRAMEWORK'S ONE RESOLVER, not a rule private to this gate. It reads the AUTHORED YAML, not
    the emitted graph: a gate that reads the projection agrees with it by construction and could
    never catch a bug in it ("READ FROM THE SSOT, NOT FROM THE PROJECTION",
    check_datasets_are_grounded.py). What is shared is HOW a pointer resolves; what is not shared
    is the question each gate asks on top of it.
    """
    import mac_pointers as mp                                        # noqa: PLC0415
    idx = mp.resolve(root, mp.load_registry())
    return [f"{r.src_path}#{r.src_locator} : sql_file {r.raw_value!r} — {r.resolution_basis}"
            for r in idx.refs
            if r.reference_kind == "transform_produces_sql" and r.resolution == "dangling"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Transform SQL-extraction gate")
    ap.add_argument("root", help="bundle root (a MAC source container)")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"root not found: {root}", file=sys.stderr)
        return 2

    L = resolve(root)
    tdir = L.transforms
    if not tdir or not Path(tdir).is_dir():
        print(f"── transform-sql-extracted ── {root} ──\n  no data/transforms dir — nothing to check (skip)")
        return 0
    tdir = Path(tdir)

    # ── RESOLUTION IS SHARED, THE QUESTION IS NOT ───────────────────────────────────────────
    # One resolver for the whole estate (meaning-as-code/tools/mac_pointers.py), reading the
    # authored YAML — NOT the emitted graph, which a gate must never read: it would agree with the
    # projection by construction and could never catch a bug in it.
    #
    # The gate keeps its own question, which is the half no resolver can answer: a SUBSTANTIAL
    # INLINE SQL BODY WITH NO POINTER AT ALL. There is nothing to resolve there — the finding is
    # the absence of a pointer, and that is this gate's and nobody else's.
    findings: list[str] = []
    for _f in dangling_sql_targets(root):
        findings.append(_f)
    n = 0
    for p in sorted(tdir.glob("*.yaml")):
        n += 1
        doc = load(p)
        rel = p.relative_to(root)
        if isinstance(doc, Exception):
            findings.append(f"{rel} :: YAML parse error: {doc}")
            continue
        if not isinstance(doc, dict):
            continue

        sql_files = [(jp, v) for jp, v in walk(doc, "sql_file") if isinstance(v, str) and v.strip()]
        inline = [(jp, v) for jp, v in walk(doc, "sql") if substantial(v)]

        if sql_files:
            # B. POINTER PRESENT — the target must exist, and WHETHER IT DOES IS NOT THIS GATE'S
            #    QUESTION. It is `transform_produces_sql` in mac_pointers.yaml, resolved once by
            #    mac_pointers.resolve() for the whole bundle (see `dangling_sql_targets` below).
            #    This gate used to answer it itself, with a private rule that also accepted a BARE
            #    filename relative to data/transforms/ — a form the catalogue does not recognise,
            #    so such a pointer passed here and was invisible to every other reader. Measured on
            #    contoso5: 8 of 8 sql_file values are root-relative, so nothing changes today and
            #    the bare form becomes a finding rather than a silent divergence.
            pass
        elif inline:
            # A. no pointer + a substantial inline body — trapped inline, not extracted
            for jp, v in inline:
                why = "multi-line" if "\n" in v else f">{MAX_INLINE} chars"
                findings.append(
                    f"{rel}{jp} : inline SQL body ({why}) with no sql_file: pointer — "
                    f"extract it to a sibling data/transforms/{p.stem}.sql and reference it via sql_file:")

    print(f"── transform-sql-extracted gate ── {n} transform descriptor(s) under {root} ──")
    for f in findings:
        print(f"  [ERROR] {f}")
    if findings:
        print(f"\n✗ {len(findings)} un-extracted / dangling transform SQL reference(s)")
        return 1
    print("\n✓ OK — every transform's SQL body is extracted to a sibling .sql (or short-inline prose only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
