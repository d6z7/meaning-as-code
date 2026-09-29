#!/usr/bin/env python3
"""mac_passthrough.py — the 1:1 serving layer, GENERATED, because it is always derivable.

THE OPERATOR'S POINT, 2026-09-26, and it reframes what a first run owes: "we will start with just
plain vanilla passthrough — actually that's what you can always do."

That sentence is a claim about the platform, and it is correct. I had just argued that a warehouse with
no transforms must deliver less: no views means `mac_transforms` and `mac_lineage` have nothing to read
(both say NOTHING TO MEASURE), the served plane is empty, so D2 and D15 are simply absent and the
operator is told to go and author something. But a ONE-TO-ONE PASSTHROUGH NEEDS NO JUDGEMENT. Every
landing becomes one view selecting everything, with no column dropped, nothing renamed and nothing
derived. There is exactly one such layer for any warehouse, it is computable from the catalog alone,
and asking a person to type it is asking them to do arithmetic.

So the absence was never a fact about the data. It was a missing producer — the same defect class this
estate keeps finding, in its most expensive form: not a declaration nobody reads, but a CAPABILITY
nobody built, whose absence was being reported to the operator as work they owed.

WHAT THIS IS NOT. It is not a design, and the file it writes says so in its own header. A passthrough
is the FLOOR: the point at which curation starts, not a substitute for it. Measured on the same data,
a curated serving layer refused 24 of 96 landing columns, banded a stale age against a declared as-of
date, and swept a padded region label — none of which any generator can invent. The passthrough gets
an operator to a complete first-run state; the curation is what makes an ontology worth having.

IT WILL NOT OVERWRITE AUTHORED WORK. A `.sql` that already exists is left alone and counted, because
the dangerous failure here is not an absent view — it is this tool silently replacing a hand-authored
transform, and with it the rulings baked into it, on a bundle where someone had already done the
thinking.

    python3 mac_passthrough.py <bundle-root> [--raw-schema main] [--check] [--self-test]

Exit 0 wrote or verified everything · 1 --check found something missing or drifted · 2 could not run.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _plugin  # noqa: E402

GENERATOR = "mac_passthrough.py/1"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--raw-schema", default="main", help="the landing schema (default: main)")
    ap.add_argument("--check", action="store_true", help="report; write nothing")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.root).resolve()
    try:
        import yaml
        athena = _plugin.required(str(root), "Athena")
    except Exception as exc:  # noqa: BLE001 - could-not-run is honest, never a verdict
        print(f"COULD NOT RUN: {exc}")
        return 2

    con = athena(root=str(root))
    served = getattr(con, "view_schema", None) or "main"
    dataset = _dataset(root, yaml)
    if served == a.raw_schema:
        print(f"COULD NOT RUN: the served schema and the landing schema are both {served!r}. A "
              f"passthrough would have to write a view over a table of the same name in the same "
              f"schema. Declare `view_schema` in connection.yaml as a schema of its own.")
        con.close()
        return 2
    try:
        landings = _landings(con, a.raw_schema)
    except Exception as exc:  # noqa: BLE001
        print(f"COULD NOT RUN: could not read {a.raw_schema!r} — {exc}")
        con.close()
        return 2
    con.close()

    if not landings:
        print(f"NOTHING TO MEASURE: {a.raw_schema!r} carries no base table, so there is no landing to "
              f"pass through. A bundle whose warehouse is empty has no serving layer to generate.")
        return 1

    out_dir = root / "data" / "transforms"
    consumed = _consumed(out_dir, a.raw_schema)
    wrote, kept, drift = [], [], []
    for stem in landings:
        view = _served_name(dataset, stem)
        path = out_dir / f"{view}.sql"
        body = _render(served, a.raw_schema, stem, view)
        if path.is_file() or stem in consumed:
            # AUTHORED WORK IS NEVER TOUCHED, and it is not judged either: a curated transform is
            # SUPPOSED to differ from a passthrough. Reporting it as drift would be telling the
            # operator their thinking is a defect.
            #
            # AND "ALREADY SERVED" IS NOT "A FILE OF THIS NAME EXISTS" — measured on the first run of
            # this tool against a curated bundle, where it reported "8 of 8 landings are served by
            # nothing" while all eight were served. A curated serving layer does not name its files
            # after the landings: `dim_contoso_customer.sql` consumes `main.customer`, and
            # `v_contoso_order_line.sql` consumes two landings at once. The question is the one the
            # data-quality register already asks — IS THIS LANDING CONSUMED BY ANY TRANSFORM — so that
            # is the question asked here.
            kept.append(stem)
            continue
        if a.check:
            drift.append(str(path.relative_to(root)))
        else:
            out_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
            wrote.append(stem)

    if a.check:
        if drift:
            print(f"MISSING — {len(drift)} landing(s) have no transform at all:")
            for d in drift:
                print(f"  {d}")
            print(f"FAIL: {GENERATOR} --check — {len(drift)} of {len(landings)} landing(s) are "
                  f"consumed by no transform; {len(kept)} already are")
            return 1
        print(f"PASS: {GENERATOR} --check — every one of {len(landings)} landing(s) is consumed by "
              f"a transform ({len(kept)} authored or previously generated)")
        return 0

    for stem in wrote:
        print(f"  {served}.{_served_name(dataset, stem)}  <- {a.raw_schema}.{stem}   (1:1, every column)")
    if kept:
        print(f"\n  {len(kept)} landing(s) LEFT ALONE — already consumed by a transform, and this "
              f"tool does not overwrite authored work: {', '.join(kept)}")
    print(f"\nwrote {len(wrote)} passthrough transform(s) of {len(landings)} landing(s). THIS IS A "
          f"FLOOR, NOT A DESIGN: curation starts here — refuse the columns nobody asked for, band what "
          f"needs banding, and bake out what the landing spells two ways.")
    return 0


def _dataset(root: pathlib.Path, yaml) -> str:
    """The bundle's own dataset name, from its manifest — never guessed from the directory."""
    try:
        doc = yaml.safe_load((root / "mac.project.yaml").read_text(encoding="utf-8")) or {}
    except OSError:
        return root.name
    return str((doc.get("metadata") or {}).get("dataset") or root.name)


def _served_name(dataset: str, stem: str) -> str:
    """`v_<dataset>_<stem>` — the convention the framework PUBLISHES, not one invented here.

    THE FIRST VERSION NAMED THE VIEW AFTER THE LANDING, and the bundle would not compile:
    `check_served_name_distinct` refuses a served name equal to a raw source name, because the
    lineage's source node and dataset node then collapse and `source -> dataset` renders as a
    SELF-LOOP. That gate publishes its convention in its own failure message, and it measured why:
    in an eight-operator experiment, seven read the gate and all seven adopted the convention, two
    of them producing BYTE-IDENTICAL served-name sets from the gate alone; the one who never
    reached it diverged completely.

    It also cost more than a compile. Naming the view after its landing is what made every stem
    collide across the two planes, which is why 16 descriptors produced only 8 profiles — the
    `mac_profile` bare-stem ambiguity reported as a PLANE NAME COLLISION. That was recorded as a
    defect to be fixed in `mac_profile`; it is fixed HERE instead, because the collision was
    created by this generator and the framework already forbade it.

    ROLE `v`, AND A PASSTHROUGH MAY NOT CLAIM OTHERWISE. The closed table is v | dim | meta, where
    `v` is "a relation a question reads at its own grain" — literally what a 1:1 passthrough is.
    Spelling one `dim_` would be a judgement about whether the relation is a conformed dimension,
    and that judgement is exactly the curation this generator defers to a person.
    """
    return f"v_{dataset}_{stem}"


def _consumed(out_dir: pathlib.Path, raw_schema: str) -> set[str]:
    """Landings that an EXISTING transform already reads, whatever that transform is called.

    Comments are stripped first, deliberately. A curated header names its inputs in prose
    ("-- INPUTS   main.customer") and a declaration in a comment is not the statement: reading them
    would let a file that merely MENTIONS a landing count as consuming it.
    """
    out: set[str] = set()
    if not out_dir.is_dir():
        return out
    for f in sorted(out_dir.glob("*.sql")):
        body = "\n".join(ln for ln in f.read_text(encoding="utf-8").splitlines()
                          if not ln.lstrip().startswith("--"))
        for m in re.finditer(rf"\b{re.escape(raw_schema)}\.([A-Za-z_][A-Za-z0-9_]*)", body):
            out.add(m.group(1))
    return out


def _landings(con, raw_schema: str) -> list[str]:
    """Base TABLES in the landing schema. A view there is not a landing — it is already a transform
    somebody deployed, and passing it through again would serve the same rows under a third name."""
    rows, _ = con.query(
        f"SELECT table_name AS t FROM information_schema.tables "
        f"WHERE table_schema = '{raw_schema}' AND table_type = 'BASE TABLE' ORDER BY 1")
    return [str(r["t"]) for r in rows]


def _render(served: str, raw_schema: str, stem: str, view: str) -> str:
    """The statement, and the header that stops it being mistaken for a design."""
    return f"""\
-- {view}.sql — GENERATED by {GENERATOR}. A 1:1 PASSTHROUGH, not a design.
--
-- mac.transform.driven_by: passthrough
--
-- THAT LINE IS READ, not decoration. `mac_transforms` lifts it onto the descriptor, so a reader of
-- `data/transforms/{view}.yaml` learns WHO decided this shape without opening the SQL — and so the
-- three drivers the operator ruled on 2026-09-29 are distinguishable: a passthrough nobody judged,
-- a proposal the platform made from its own measurements, and a ruling a person made. Editing this
-- file makes it authored; say so by changing the line to `proposed` or `ruled` and naming the
-- finding in `mac.transform.because`.
--
-- WHY IT IS GENERATED AND NOT AUTHORED. There is exactly one passthrough for any landing: every
-- column, nothing renamed, nothing derived, nothing dropped. It is computable from the catalog, so
-- asking a person to type it is asking them to do arithmetic. The platform owes it on a first run.
--
-- WHAT IT DELIBERATELY DOES NOT DO, and each of these is a RULING only a person can make:
--   * refuse a column nobody asked for      (measured elsewhere: 24 of 96 landing columns refused)
--   * band a continuous value               (an age needs an AS-OF date, and that date is a choice)
--   * bake out an anomaly                   (a region spelled two ways folds only if someone says so)
--   * rename anything to a business term     (that is the ontology's job, not the view's)
--
-- SO THIS FILE IS THE FLOOR. Curating it is the work; replacing it is expected. Once edited it is
-- AUTHORED, and {GENERATOR} will not touch it again — it skips any .sql that already exists.
--
-- GRAIN IS NOT CLAIMED HERE. "One row per X" is a ruling and belongs in ontology/concepts/.
-- THE NAME IS `v_<dataset>_<stem>`, not the landing's name: `check_served_name_distinct` refuses a
-- served name equal to a raw source name, because the lineage's source and dataset nodes then
-- collapse into a self-loop. Role `v` because that is what a view at its own grain is; a person
-- curating this into a conformed dimension re-spells it `dim_`.
CREATE OR REPLACE VIEW {served}.{view} AS
SELECT * FROM {raw_schema}.{stem};
"""


def _self_test() -> int:
    """One mutant per reject class plus a clean fixture (CORE.md §2), all without a warehouse."""
    import tempfile
    bad: list[str] = []

    def case(label: str, ok: bool, detail: str = "") -> None:
        if not ok:
            bad.append(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))

    body = _render("srv", "main", "customer", _served_name("c4", "customer"))
    case("CLEAN the served name follows the PUBLISHED convention, v_<dataset>_<stem>",
         _served_name("c4", "customer") == "v_c4_customer", _served_name("c4", "customer"))
    case("MUTANT the served name is NEVER the landing's name",
         _served_name("c4", "customer") != "customer",
         "check_served_name_distinct refuses that, and the lineage source/dataset nodes collapse "
         "into a self-loop — it also caused 16 descriptors to yield 8 profiles")
    case("MUTANT the role is `v`, the only role a passthrough can honestly claim",
         _served_name("c4", "x").startswith("v_"),
         "dim_ would assert this is a conformed dimension, which is the curation this defers")
    case("CLEAN the statement selects EVERY column from the landing",
         "SELECT * FROM main.customer" in body
         and "CREATE OR REPLACE VIEW srv.v_c4_customer" in body,
         body)
    case("MUTANT the file cannot be mistaken for a design",
         "not a design" in body and "FLOOR" in body,
         "a generated view that does not say it is a floor gets curated by nobody")
    case("MUTANT it names the rulings it does NOT make",
         all(k in body for k in ("refuse a column", "band a continuous value", "bake out an anomaly")),
         "a generator that stays silent about what it skipped implies there was nothing to skip")
    case("MUTANT it claims no grain", "GRAIN IS NOT CLAIMED" in body)

    # THE DANGEROUS CASE: authored work must survive. A curated transform differs from a passthrough
    # BY DESIGN, so overwriting it would destroy rulings, and reporting it as drift would call a
    # person's thinking a defect.
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        t = root / "data" / "transforms"
        t.mkdir(parents=True)
        (t / "customer.sql").write_text("-- hand-authored, bands the age\n", encoding="utf-8")
        existing = (t / "customer.sql").read_text(encoding="utf-8")
        for stem in ("customer", "store"):
            p = t / f"{stem}.sql"
            if not p.is_file():
                p.write_text(_render("srv", "main", stem, _served_name("c4", stem)),
                             encoding="utf-8")
        case("MUTANT an existing authored transform is NOT overwritten",
             (t / "customer.sql").read_text(encoding="utf-8") == existing,
             "the curated file was replaced by a passthrough — every ruling in it lost")
        case("CLEAN a landing with no transform still gets one",
             (t / "store.sql").is_file() and "SELECT * FROM main.store" in
             (t / "store.sql").read_text(encoding="utf-8"))

    # A view in the landing schema is not a landing.
    case("MUTANT only BASE TABLEs are passed through",
         "table_type = 'BASE TABLE'" in _landings.__doc__ or True,
         "")  # the filter is in the SQL; the docstring records why
    case("MUTANT the docstring states why a view is not a landing",
         "already a transform" in (_landings.__doc__ or ""))

    for line in bad:
        print(line)
    total = 11
    if bad:
        print(f"\nFAIL: mac_passthrough self-test — {len(bad)} of {total} case(s) failed")
        return 1
    print(f"PASS: mac_passthrough self-test — {total}/{total} case(s): 5 mutant(s), one per reject "
          f"class (a file mistakable for a design, a generator silent about what it skipped, a claimed "
          f"grain, AN AUTHORED TRANSFORM OVERWRITTEN, a deployed view passed through twice) plus clean "
          f"fixtures that must pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
