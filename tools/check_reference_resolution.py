#!/usr/bin/env python3
"""check_reference_resolution.py — an AUTHORED `references:` must agree with what the DATA PLANE
measured, wherever the data plane can measure it at all.

THE TWO HOMES, AND WHY NEITHER ALONE IS ENOUGH. Since column_declaration.md rev 5 (2026-10-07), a
concept-plane column may carry `references: <ConceptName>` — a person's claim that this column's
values identify one row of that concept. The DATA PLANE carries its own, independently measured
foreign key, `columns[].references.to` (`<relation>.<column>`), on the descriptor —
`tools/mac_descriptors.py` writes it from the warehouse's own constraints, nobody types it. The two
are different claims: one is AUTHORED (a person names the concept), the other is MEASURED (the
warehouse names the relation and column). Nothing before this gate compared them, so an author could
name the wrong concept, or the right one on a stale descriptor, and no reader would ever say so.

THE TARGET OF A REFERENCE IS MEASURABLE IN MOST CASES, AND NOT ALL. MEASURED on contoso5, the day
this gate was built: 25 columns carry an authored `references:`; 22 resolve from the descriptor's
own `references.to`. The three that do not — `Brand.product_key`, `Color.product_key`,
`ProductCategory.product_key`, each `references: Product` — ground on `dim_product` and name its
OWN primary key (`role: primary_key`, no `references:` block at all in the descriptor): a pointer
inside ONE relation, from a member-set concept to the leaf concept it is a column of, which no
descriptor measurement can see because nothing about it is a foreign key. These three are legitimate
`n/a`, not a failure of either plane — the descriptor is not wrong for staying silent about a column
that is not a reference in the warehouse's own terms, and the concept is not wrong for saying that a
brand is one of a product's columns.

WHAT THIS GATE DOES NOT DO. It does not RESOLVE a reference `tools/mac_edges.py` could not already
resolve, and it does not write anything — `tools/check_physical_references.py` already holds the
data plane's OWN references family to its own contract (drawable, keyed, denominated); this gate
crosses the data plane's measurement against the CONCEPT plane's authored claim, which is a
different pair of files and a different question ("do the two planes agree", not "is one plane
internally consistent").

THE RESOLVER, restated so the three verdicts are legible without re-deriving them:
  1. Read the column's measured `references.to` (`<relation>.<column>`) from its OWN relation's
     descriptor (data/datasets or data/sources).
  2. If there is none — the column carries no measured FK at all — the comparison is `n/a`: the
     claim cannot be checked against this measurement, which is a fact about the warehouse, not a
     verdict on the claim.
  3. Otherwise, find every concept grounding on the TARGET relation (`<relation>`). If the authored
     `references: <ConceptName>` is one of them, the claim is `ok` — the measurement corroborates
     it, even if several concepts share that relation (a relation may back more than one concept,
     same as `sdk.authoring.edges.concept_index`). If it is not among them, the claim is a
     `violation`: the person named a concept the warehouse's own foreign key does not point at.

Usage:
  python3 tools/check_reference_resolution.py <bundle> [--enumerate]
  python3 tools/check_reference_resolution.py --self-test
Exit 0 every authored reference agrees with its measurement (or has none to agree with); 1 at least
one disagrees; 2 could not run (no bundle, no concept plane).
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mac_diag as D       # noqa: E402
import mac_project as P    # noqa: E402

NAME = "check_reference_resolution"
OK, VIOLATION, NA = "ok", "violation", "n/a"


def _i(subject: str, verdict: str, note: str = "") -> dict:
    return {"subject": subject, "verdict": verdict, "note": note}


def _load(path: pathlib.Path) -> dict:
    try:
        d = yaml.safe_load(path.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:                                             # noqa: BLE001
        return {}


def _descriptor_for(root: pathlib.Path, relation: str) -> dict | None:
    """The data-plane descriptor for a bare relation name — datasets (served) before sources (raw),
    matching every other reader in this estate's own precedence."""
    for plane in ("datasets", "sources"):
        f = root / "data" / plane / f"{relation}.yaml"
        if f.is_file():
            return _load(f)
    return None


def _concepts_by_relation(concepts: dict[str, dict]) -> dict[str, list[str]]:
    """bare relation -> every concept NAME grounding on it. A relation may back several concepts —
    the same fact `sdk.authoring.edges.concept_index` resolves endpoints against — so the authored
    claim is checked against the whole set, not against "the one concept this gate happened to
    visit first"."""
    out: dict[str, list[str]] = {}
    for stem, doc in concepts.items():
        src = (doc.get("grounding") or {}).get("source")
        if not isinstance(src, dict):
            continue
        rel = str(src.get("relation") or "").split(".")[-1]
        if not rel:
            continue
        name = (doc.get("concept") or {}).get("name") or stem
        out.setdefault(rel, []).append(name)
    return out


def scan(root: pathlib.Path) -> list[dict]:
    """Every authored `references:`, compared against its column's measured `references.to`."""
    concepts: dict[str, dict] = {}
    for f in P.concept_files(root):
        doc = _load(pathlib.Path(f))
        name = (doc.get("concept") or {}).get("name")
        if isinstance(name, str) and name.strip():
            concepts[pathlib.Path(f).stem] = doc
    by_relation = _concepts_by_relation(concepts)

    out: list[dict] = []
    for stem, doc in sorted(concepts.items()):
        name = (doc.get("concept") or {}).get("name") or stem
        src = (doc.get("grounding") or {}).get("source")
        if not isinstance(src, dict):
            continue
        rel = str(src.get("relation") or "").split(".")[-1]
        cols = src.get("columns")
        if not rel or not isinstance(cols, dict):
            continue
        descriptor = _descriptor_for(root, rel)
        desc_cols = {
            c.get("name"): c for c in ((descriptor or {}).get("columns") or [])
            if isinstance(c, dict) and c.get("name")
        }
        for col, spec in cols.items():
            authored = spec.get("references") if isinstance(spec, dict) else None
            if not isinstance(authored, str) or not authored.strip():
                continue
            authored = authored.strip()
            subject = f"{name}.{col} -> {authored}"
            dcol = desc_cols.get(col)
            measured = P.column_reference(dcol) if dcol else None
            if not measured or not measured.get("relation"):
                if descriptor is None:
                    out.append(_i(subject, NA,
                                  f"{rel!r} has no data-plane descriptor (data/datasets or "
                                  f"data/sources), so the claim cannot be measured at all"))
                else:
                    out.append(_i(subject, NA,
                                  f"{rel}.{col} carries no measured `references.to` in its "
                                  f"descriptor — a pointer this gate cannot see is not the same "
                                  f"as a pointer that does not exist (contoso5: Brand/Color/"
                                  f"ProductCategory's `product_key` names {rel}'s own primary key, "
                                  f"a conceptual pointer inside one relation)"))
                continue
            target_rel = measured["relation"]
            holders = sorted(by_relation.get(target_rel) or [])
            if authored in holders:
                out.append(_i(subject, OK,
                              f"{rel}.{col} measures `references.to: {measured['to']}`, and "
                              f"{authored!r} grounds on {target_rel!r} — the claim is corroborated"))
            else:
                out.append(_i(subject, VIOLATION,
                              f"{rel}.{col} measures `references.to: {measured['to']}` (relation "
                              f"{target_rel!r}), and the concept(s) grounding on {target_rel!r} are "
                              f"{', '.join(holders) or 'none'} — {authored!r} is not among them, so "
                              f"the authored reference names a concept the warehouse's own foreign "
                              f"key does not point at"))
    return out


def counts(items: list[dict]) -> tuple[int, int, int, int]:
    failed = sum(1 for i in items if i["verdict"] == VIOLATION)
    na = sum(1 for i in items if i["verdict"] == NA)
    return len(items), len(items) - failed - na, failed, na


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# --self-test — one bundle built in memory, one mutant per reject class
# ══════════════════════════════════════════════════════════════════════════════════════════════════

def _write_bundle(root: pathlib.Path, *, break_claim: bool = False, no_measurement: bool = False) -> None:
    (root / "ontology" / "concepts").mkdir(parents=True, exist_ok=True)
    (root / "data" / "datasets").mkdir(parents=True, exist_ok=True)
    # A MANIFEST IS REQUIRED for the two-plane layout `mac_project.resolve` is told to expect — no
    # manifest means FLAT (`concepts/` at the root, `tables/` for descriptors), and this fixture
    # would then look for its concepts one directory up from where it wrote them.
    (root / "mac.project.yaml").write_text(
        "planes:\n  data: data\n  ontology: ontology\ndescriptors: data/datasets\n",
        encoding="utf-8",
    )
    fact = """concept:
  name: Fact
  class: event
  definition: a fixture fact row.
grounding:
  source:
    relation: fact_rel
    key: fact_key
    columns:
      fact_key:
        offers: {}
      dim_key:
        offers: {axis: categorical}
        references: %s
""" % ("Nobody" if break_claim else "Dim")
    dim = """concept:
  name: Dim
  class: entity
  definition: a fixture dimension.
grounding:
  source:
    relation: dim_rel
    key: dim_key
    columns:
      dim_key:
        offers: {}
"""
    (root / "ontology" / "concepts" / "fact.yaml").write_text(fact, encoding="utf-8")
    (root / "ontology" / "concepts" / "dim.yaml").write_text(dim, encoding="utf-8")
    fact_desc_cols = """table:
  name: fact_rel
columns:
- name: fact_key
  type: integer
  role: primary_key
- name: dim_key
  type: integer
  role: foreign_key
"""
    if not no_measurement:
        fact_desc_cols += """  references:
    to: dim_rel.dim_key
    cardinality: {child: many, parent: one}
    participation: {child: mandatory, parent: optional}
"""
    (root / "data" / "datasets" / "fact_rel.yaml").write_text(fact_desc_cols, encoding="utf-8")
    (root / "data" / "datasets" / "dim_rel.yaml").write_text(
        "table:\n  name: dim_rel\ncolumns:\n- name: dim_key\n  type: integer\n  role: primary_key\n",
        encoding="utf-8",
    )


def _self_test() -> int:
    import tempfile

    cases = []

    def case(label, *, break_claim=False, no_measurement=False, want):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            _write_bundle(root, break_claim=break_claim, no_measurement=no_measurement)
            items = scan(root)
            got = sorted({i["verdict"] for i in items if i["subject"].startswith("Fact.dim_key")})
            ok = got == want
            cases.append((label, ok, got, want))

    case("CLEAN — the authored reference agrees with the measured FK", want=[OK])
    case("MUTANT a measured FK with no matching concept on the target relation",
         break_claim=True, want=[VIOLATION])
    case("a column with no measured `references.to` is n/a, not a silent pass",
         no_measurement=True, want=[NA])

    bad = [(l, g, w) for l, ok, g, w in cases if not ok]
    for l, g, w in bad:
        print(f"  FAIL  {l}\n        expected {w!r}, got {g!r}")
    n = len(cases)
    if bad:
        print(f"\nFAIL: {NAME} self-test — {len(bad)} of {n} case(s) failed")
        return 1
    print(f"PASS: {NAME} self-test — {n}/{n} case(s): a corroborated claim, a measured FK pointing "
          f"at a concept the author did not name, and a column with no measurement to check against "
          f"(reported n/a, never counted as a pass)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?")
    ap.add_argument("--enumerate", dest="enumerate_all", action="store_true",
                    help="print every subject, not only the failing ones")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    if not a.bundle:
        print(f"{NAME}: exit 2 — no bundle given", file=sys.stderr)
        return 2
    root = pathlib.Path(a.bundle).resolve()
    if not root.is_dir():
        print(f"{NAME}: exit 2 — {root} is not a directory", file=sys.stderr)
        return 2
    cdir = P.concepts_dir(root)
    if not P.concept_files(root):
        return D.refuse_empty(NAME, cdir)

    items = scan(root)
    enumerated, held, failed, na = counts(items)
    bad = [i for i in items if i["verdict"] == VIOLATION]
    mark = "PASS" if not bad else "FAIL"
    print(f"{mark}: {NAME} — {enumerated} authored reference(s): {held} corroborated by the data "
          f"plane's own measurement, {failed} disagree with it, {na} have no measurement to check "
          f"against")
    for i in items:
        if a.enumerate_all or i["verdict"] != OK:
            glyph = {"ok": "ok ", "violation": "!! ", "n/a": "-- "}[i["verdict"]]
            print(f"  {glyph} {i['subject']}")
            print(f"       {i['note']}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
