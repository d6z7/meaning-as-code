#!/usr/bin/env python3
"""mac_transforms.py — write the TRANSFORM DESCRIPTORS by measuring the warehouse's view definitions.

THE MISSING LINK IN D15, and the operator found it the only way that counts: "i did not get lineage".
I had produced `data/lineage/lineage.json` — my own artifact, which nothing in the console reads —
and called lineage delivered. The console's lineage view reads `objects.json#lineage_graph`, written
at PROJECTION time, and the projection builds that graph from `data/transforms/*.yaml`.

With the .sql files present and no descriptors, the projection was explicit about it:

    projected read view: {'sources': 8, 'transforms': 0, 'datasets': 6}; lineage flows: 0
    lineage_graph: 14 nodes, 0 EDGES
      datasets_with_no_input:   all 6
      sources_feeding_nothing:  all 8
    check_ontology_grounds_on_datasets [ERROR] served dataset 'dim_contoso_store' is produced by no
      transformation — add data/transforms/dim_contoso_store.yaml; even a 1:1 passthrough must be
      declared

Fourteen nodes and nothing joining them. A `.sql` file is the RECIPE; the descriptor is the DECLARED
claim about what it consumes and produces, and only the second is read.

WHAT IT MEASURES — the same source as `mac_lineage`, projected into the shape the framework already
defines:
  * `produces.relation`  the view, schema-qualified
  * `produces.sql_file`  the .sql beside it, when the bundle holds one
  * `inputs[]`           every relation the view's own definition references, each with the
                         descriptor that describes it, so the chain raw -> transform -> dataset
                         closes and the projector can draw an edge

WHAT IT DOES NOT CLAIM. No grain, no default reading, no "one row per X". A grain is a RULING — the
descriptor generator states what the engine says and leaves the argument to ontology/concepts/. Where
contoso's hand-authored descriptors carry a `grain:` line, that line is a person's judgement and this
tool writes none.

    python3 mac_transforms.py <bundle-root> [--check]
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from datetime import UTC, datetime

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _plugin  # noqa: E402
from version import read as _mac_version  # noqa: E402  -- the stamp has ONE home

GENERATOR = "mac_transforms.py/1"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--check", action="store_true", help="report drift; write nothing")
    ap.add_argument("--self-test", action="store_true",
                    help="hold the driver marker; needs no bundle and no warehouse")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.root).resolve()
    try:
        import mac_lineage
        athena = _plugin.required(str(root), "Athena")
    except Exception as exc:  # noqa: BLE001 - could-not-run is honest, never a finding
        print(f"COULD NOT RUN: {exc}")
        return 2

    con = athena(root=str(root))
    schema = getattr(con, "view_schema", None) or "main"
    catalog = mac_lineage._catalog(con)
    views = mac_lineage._views(con, schema)
    if not views:
        print(f"NOTHING TO MEASURE: no view in {schema!r} carries a definition. A bundle whose served "
              f"relations are base TABLES has no transform to describe — its lineage lives in "
              f"whatever built them.")
        return 1

    observed = datetime.now(UTC).date().isoformat()
    drift, wrote, inputless = [], 0, []
    for view, sql in sorted(views.items()):
        refs = sorted(mac_lineage._refs(sql, catalog, schema, view))
        if not refs:
            inputless.append(view)
        body = _render(root, schema, view, refs, catalog, observed)
        out = root / "data" / "transforms" / f"{view}.yaml"
        if a.check:
            now = out.read_text(encoding="utf-8") if out.is_file() else ""
            if _without_date(now) != _without_date(body):
                drift.append(str(out.relative_to(root)))
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(body, encoding="utf-8")
            wrote += 1
            print(f"  {out.relative_to(root)}  <- {', '.join(refs) or 'NO INPUT MEASURED'}")
    con.close()

    if a.check:
        if drift:
            print(f"DRIFT — {len(drift)} transform descriptor(s) no longer match the warehouse:")
            for d in drift:
                print(f"  {d}")
            return 1
        print(f"OK — {len(views)} transform descriptors match the warehouse.")
        return 0
    if inputless:
        print(f"\n  {len(inputless)} view(s) reference no relation this warehouse knows: "
              f"{', '.join(inputless)}")
        print("  The projector draws no edge for those, and the lineage graph will show them as "
              "datasets with no input.")
    print(f"\nwrote {wrote} transform descriptors, measured {observed}")
    return 0


def _driver_lines(sql_path: pathlib.Path) -> list:
    """The metadata lines for a declared driver, and NOTHING when none is declared."""
    driven, because = driver_of(sql_path)
    out = []
    if driven:
        out.append(f"  driven_by: {driven}")
    if because:
        out.append(f"  because: {because}")
    return out


def driver_of(sql_path: pathlib.Path) -> tuple:
    """`(driven_by, because)` read from the .sql — WHO decided this transform's shape.

    THE .SQL IS THE AUTHORED ARTIFACT, so it is the only honest place this can come from. The
    descriptor beside it is re-derived from the warehouse's view definition on every run, so a fact
    written there would be erased by its own generator; and inferring it — "this one looks curated"
    — would be the guess this estate keeps paying for.

    Operator ruling, 2026-09-29: the first version is a 1:1 passthrough IF NO OTHER REGULATION
    APPLIES; where the profiling already shows something the platform PROPOSES an improvement; and
    an SME or data scientist drives the change after that, including during concept authoring.

    ABSENT IS NOT `ruled`. A transform with no marker is UNDECLARED — nobody recorded who drove it —
    and every curated transform in this estate is in that state today. Labelling them `ruled` would
    assert a ruling that is on no record, which is the same defect as a gate reporting PASS over a
    population it never enumerated.
    """
    if not sql_path.is_file():
        return None, None
    driven = because = None
    for line in sql_path.read_text(encoding="utf-8", errors="replace").splitlines():
        t = line.strip()
        if not t.startswith("--"):
            break          # the markers live in the banner, above the statement
        t = t.lstrip("-").strip()
        if t.startswith("mac.transform.driven_by:"):
            driven = t.split(":", 1)[1].strip() or None
        elif t.startswith("mac.transform.because:"):
            because = t.split(":", 1)[1].strip() or None
    return driven, because


def _render(root: pathlib.Path, schema: str, view: str, refs: list[str],
            catalog: dict[str, str], observed: str) -> str:
    sql_file = f"data/transforms/{view}.sql"
    has_sql = (root / sql_file).is_file()
    lines = [
        f"# GENERATED by {GENERATOR} from the warehouse's own view definition — do not edit;",
        "# re-run the generator.",
        "#",
        "# WHAT IT DECLARES: which relations this view CONSUMES and which it PRODUCES. That is what",
        "# closes the chain raw -> transform -> dataset, and it is what the projection reads to draw",
        "# the lineage graph the console shows. A `.sql` file alone is the recipe, and the projector",
        "# does not read it: measured on a bundle holding six .sql files and no descriptors, the graph",
        "# came back with 14 nodes and 0 EDGES.",
        "#",
        "# NO GRAIN IS CLAIMED HERE. 'One row per X' is a RULING and belongs in ontology/concepts/,",
        "# where a person argues for it.",
        "",
        "metadata:",
        f"  pipeline: {view}",
        "  layer: data-transformation",
        f"  schema_version: '{_mac_version()}'",
        "  status: draft",
        "  confidence: I",
        f"  observed: '{observed}'",
        f"  generated_by: {GENERATOR}",
        *_driver_lines(root / sql_file),
        "",
        "produces:",
        f"  relation: {schema}.{view}",
    ]
    if has_sql:
        lines.append(f"  sql_file: {sql_file}")
    lines.append("")
    if not refs:
        lines += ["# THE VIEW'S DEFINITION REFERENCES NO RELATION THIS WAREHOUSE KNOWS — a constant",
                  "# select, or a reference the catalog cannot confirm. Declared empty rather than",
                  "# guessed at.", "inputs: []"]
        return "\n".join(lines) + "\n"
    lines.append("inputs:")
    for ref in refs:
        kind = catalog.get(ref, "unknown")
        bare = ref.split(".")[-1]
        plane = "datasets" if kind == "view" else "sources"
        descriptor = f"data/{plane}/{bare}.yaml"
        lines += [
            f"  - relation: {ref}",
            f"    kind: {'served_dataset' if kind == 'view' else 'raw_source'}",
        ]
        if (root / descriptor).is_file():
            lines.append(f"    descriptor: {descriptor}")
        else:
            lines.append(f"    # no descriptor at {descriptor} — the chain does not close here")
    return "\n".join(lines) + "\n"


def _without_date(text: str) -> str:
    return "\n".join(ln for ln in text.splitlines() if "observed:" not in ln)


def _self_test() -> int:
    """The driver marker, held to real files. No bundle, no warehouse.

    IT LIVES HERE AND NOT IN A SCRATCH SCRIPT. Operator, 2026-09-29: "i am fine if you reuse the
    strategy/method which leads to the correct result. but i am not ok if you just copy result —
    because the method is what we are testing." A check that proves something once, in a temp file
    nobody runs again, proves it once.
    """
    import tempfile

    ok = [0, 0]

    def case(what, cond):
        ok[0] += 1
        ok[1] += bool(cond)
        print(("  ✓ " if cond else "  ✗ ") + what)

    with tempfile.TemporaryDirectory() as tmp:
        d = pathlib.Path(tmp)
        a = d / "a.sql"
        a.write_text("-- x.sql — GENERATED\n--\n-- mac.transform.driven_by: passthrough\n--\n"
                     "CREATE VIEW s.t AS SELECT 1;\n", encoding="utf-8")
        case("a stamped passthrough is read", driver_of(a) == ("passthrough", None))

        b = d / "b.sql"
        b.write_text("-- mac.transform.driven_by: proposed\n"
                     "-- mac.transform.because: DQ-DUP-ORDERROWS-SALES\n"
                     "CREATE VIEW s.t AS SELECT 1;\n", encoding="utf-8")
        case("a proposal carries the finding that motivated it",
             driver_of(b) == ("proposed", "DQ-DUP-ORDERROWS-SALES"))

        # ABSENT IS NOT A FOURTH TERM, and defaulting it to `ruled` would assert a ruling that is
        # on no record — every curated transform in this estate is in exactly that state.
        c = d / "c.sql"
        c.write_text("-- a curated banner, no marker\nCREATE VIEW s.t AS SELECT 1;\n",
                     encoding="utf-8")
        case("MUTANT an unmarked transform is UNDECLARED, never `ruled`", driver_of(c) == (None, None))
        case("...and emits no metadata line at all", _driver_lines(c) == [])

        # THE BANNER IS THE CONTRACT. Scanning the whole file would let a marker inside the SELECT
        # — or inside a string literal — decide who drove the transform.
        e = d / "e.sql"
        e.write_text("CREATE VIEW s.t AS SELECT 1;\n-- mac.transform.driven_by: ruled\n",
                     encoding="utf-8")
        case("MUTANT a marker BELOW the statement is not read", driver_of(e) == (None, None))
        case("a missing .sql is undeclared, not an error", driver_of(d / "nope.sql") == (None, None))

    print(("PASS" if ok[1] == ok[0] else "FAIL")
          + f": mac_transforms self-test — {ok[1]}/{ok[0]} case(s)")
    return 0 if ok[1] == ok[0] else 1


if __name__ == "__main__":
    sys.exit(main())
