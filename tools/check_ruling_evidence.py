#!/usr/bin/env python3
"""check_ruling_evidence — a suppression that cites a measurement must cite one that EXISTS.

WHAT THIS GUARDS, and it is the only place in the estate where a hazard is both registered AND
enforced. `offers.suppressed` is the pattern: a measurement raises a DQ finding, the finding's own
`needs` field PRESCRIBES the declaration that would enforce it, a person writes that declaration on the
column, and the refusal a reader eventually sees carries the finding's id back to them:

    Customer.city offers `axis` and is declared `suppressed: DQ-IDENTIFYING-DIM_CUSTOMER-CITY`. This
    is the bundle's ruling from a measurement, not a runtime limit; the refusal carries the evidence
    so a reader can challenge it.

REWIRED 2026-10-07 AFTERNOON (column_declaration.md rev 5). The pattern was `rulings: {never_axis,
evidence}` — two keys in a `rulings` block whose every OTHER member (`label_of`, `finer_than`,
`scoped_by`) names ANOTHER column, which `never_axis` never did; it named a judgement about THIS
column, which is what `offers` is for. Both keys folded into the single `offers.suppressed`, whose
value IS the finding id directly — one key where there were two, and a `dependentRequired: axis` in
the schema takes over "a prohibition is a judgement on top of what the column IS" from the pairing
`never_axis` + `evidence` used to assert in prose alone.

THE BRIDGE IS AN UNCHECKED STRING. `offers.suppressed`'s own schema description requires only that it
be non-empty. Measured 2026-10-06, against the THEN-current `rulings.evidence`: no tool in this
directory resolved it against `issues[].id`, so `evidence: DQ-TOTALLY-MADE-UP` loaded, planned, and
produced a refusal citing nothing. The sentence a reader is given to challenge the ruling with pointed
at a finding that does not exist. The same gap exists at the new address until this gate moves with it.

That matters more than a dangling pointer usually does, because the whole claim of the pattern is that
a prohibition WITHOUT a measurement is a preference -- the runtime says exactly that when it refuses a
real axis with no `suppressed` at all. A citation that resolves to nothing is the same preference
wearing a reference.

BOTH DIRECTIONS, because the interesting number is the second one. A dangling citation is a defect and
gates. A register finding that NOTHING cites is not a defect -- a finding may legitimately await a
ruling, which is what `status: open` means -- but it is the backlog, and it is invisible unless counted.

Measured on contoso5 2026-10-06, against `rulings.evidence`: 10 findings, **2 cited**, 8 by none. The
address has since moved to `offers.suppressed`; the same two columns (Customer.city,
Customer.customer_name) still carry the same two citations, now at the new address, so the count is
unchanged — it is the READER that had stopped seeing them. A third id appears in a rule's `why:`
prose, and this gate deliberately does not count that -- prose is not a citation anything resolves,
which is the whole distinction the estate is working through.

WHAT IT DOES NOT DO. It does not judge whether the ruling is the RIGHT answer to the finding, or
whether `status` has been kept current. Both need a person. It asks only whether the two halves of the
bridge reach each other.

Usage:  python3 tools/check_ruling_evidence.py <bundle-root> [--self-test]
        exit 0 = every citation resolves · 1 = at least one does not · 2 = could not run
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mac_project as P  # noqa: E402  — ONE home for where a bundle keeps its concepts

#: Where the authored register lives. One path, because `references/known_issues/*.md` and
#: `data/quality/*.md` are both PROJECTIONS of it (`sdk/project/references.py` rmtree's the first), and
#: a gate that read a projection would agree with it by construction.
REGISTER_REL = pathlib.Path("data") / "quality" / "data_quality_register.yaml"


def _citations(root: pathlib.Path) -> list[tuple[str, str, str, str]]:
    """(file, concept, column, cited_id) for every `offers.suppressed` citation.

    `offers.suppressed` IS THE ONE HOME since 2026-10-07 afternoon — it was `rulings.evidence`
    (paired with `rulings.never_axis`) before that; both are gone from the column body
    (`additionalProperties: false`), so there is nothing left to read at the old address.
    """
    import yaml
    out: list[tuple[str, str, str, str]] = []
    for f in P.concept_files(root):
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:                                                # noqa: BLE001
            continue
        name = str(((doc.get("concept") or {}).get("name")) or f.stem)
        src = (doc.get("grounding") or {}).get("source")
        if not isinstance(src, dict):
            continue
        cols = src.get("columns") or {}
        #: THE MAP FORM AND THE LIST FORM. A bundle may spell columns either way and the estate
        #: has both; reading only the map would silently measure zero on half of them.
        items = cols.items() if isinstance(cols, dict) else (
            ((c or {}).get("name"), c) for c in cols)
        for col, body in items:
            offers = (body or {}).get("offers") or {}
            if not isinstance(offers, dict):
                continue
            cited = str(offers.get("suppressed") or "").strip()
            if cited:
                out.append((P.rel(root, f), name, str(col), cited))
    return out


def _register_ids(root: pathlib.Path) -> tuple[set[str], str | None]:
    """(every `issues[].id`, or a refusal reason). An unreadable register is never an empty set."""
    import yaml
    path = root / REGISTER_REL
    if not path.is_file():
        return set(), f"no {REGISTER_REL} — nothing declares the findings a ruling could cite"
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:                                             # noqa: BLE001
        return set(), f"{REGISTER_REL} could not be parsed: {type(exc).__name__}: {exc}"
    issues = doc.get("issues")
    if not isinstance(issues, list):
        return set(), f"{REGISTER_REL} declares no `issues:` list"
    return {str((i or {}).get("id")) for i in issues if (i or {}).get("id")}, None


def check(root: pathlib.Path) -> int:
    cites = _citations(root)
    ids, refusal = _register_ids(root)
    if refusal is not None:
        #: REFUSED, NOT PASSED. A citation cannot be judged against a register that could not be read,
        #: and reporting that as clean is how an unchecked bridge stays unchecked.
        print(f"REFUSED: {refusal}")
        return 2

    dangling = [c for c in cites if c[3] not in ids]
    cited = {c[3] for c in cites} & ids
    uncited = sorted(ids - cited)

    for f, concept, col, bad in dangling:
        print(f"  [dangling-evidence] {f}  {concept}.{col} cites {bad!r}")
        print(f"      no such finding in {REGISTER_REL}. A prohibition without a measurement is a "
              f"preference; a citation that resolves to nothing is the same preference wearing a "
              f"reference.")
    if uncited:
        #: NOT A DEFECT, AND SAID SO. A finding may legitimately await a ruling — that is what
        #: `status: open` means. It is printed because it is the backlog, and a backlog nobody counts
        #: is a backlog nobody works.
        print(f"  [uncited-finding] {len(uncited)} of {len(ids)} register finding(s) are cited by no "
              f"ruling: {', '.join(uncited)}")
        print(f"      not a defect — a finding may await a ruling. Each one is a measured hazard that "
              f"no declaration acts on yet.")

    verdict = "FAIL" if dangling else "PASS"
    print(f"{verdict}: check_ruling_evidence — {len(dangling)} dangling citation(s) over "
          f"{len(cites)} citation(s) on {len(P.concept_files(root))} concept(s); "
          f"{len(cited)} of {len(ids)} register finding(s) cited")
    return 1 if dangling else 0


def _self_test() -> int:
    """Both directions, on a bundle built here — never on the real one."""
    import tempfile

    import yaml
    bad = []
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root / "data" / "quality").mkdir(parents=True)
        (root / "mac.project.yaml").write_text("metadata: {}\n", encoding="utf-8")
        #: ASK THE HELPER WHERE CONCEPTS GO, never assume a layout. The first cut wrote them to
        #: `ontology/concepts/` while `mac_project.resolve` — given a project file that declares no
        #: ontology plane — resolves the plane to the ROOT, so `concepts_dir` was `<root>/concepts`
        #: and every assertion measured an empty bundle. A self-test that builds its fixture in the
        #: wrong place proves nothing about the gate, and it fails in the direction that looks like
        #: the gate being broken.
        cdir = P.concepts_dir(root)
        cdir.mkdir(parents=True, exist_ok=True)
        (root / REGISTER_REL).write_text(yaml.safe_dump(
            {"issues": [{"id": "DQ-REAL-ONE", "title": "t", "finding": "f"},
                        {"id": "DQ-NOBODY-CITES-ME", "title": "t", "finding": "f"}]}),
            encoding="utf-8")

        def concept(stem: str, cited: str) -> None:
            (cdir / f"{stem}.yaml").write_text(yaml.safe_dump(
                {"concept": {"name": stem.title()},
                 "grounding": {"source": {"relation": "r", "key": "c", "columns": {
                     "c": {"offers": {"axis": "categorical", "suppressed": cited}}}}}}),
                encoding="utf-8")

        concept("good", "DQ-REAL-ONE")
        cites = _citations(root)
        ids, refusal = _register_ids(root)
        if refusal or ids != {"DQ-REAL-ONE", "DQ-NOBODY-CITES-ME"}:
            bad.append(f"register not read: {refusal or ids}")
        if len(cites) != 1 or cites[0][3] != "DQ-REAL-ONE":
            bad.append(f"a resolving citation was not collected: {cites}")
        if [c for c in cites if c[3] not in ids]:
            bad.append("a REAL citation was reported dangling")

        concept("wrong", "DQ-DOES-NOT-EXIST")
        cites = _citations(root)
        if not [c for c in cites if c[3] not in ids]:
            bad.append("a DANGLING citation was not caught — the gate is inert")
        if len(cites) != 2:
            bad.append(f"expected 2 citations across 2 concepts, got {len(cites)}")

        #: THE UNCITED DIRECTION, which is the number this gate exists to surface.
        if (ids - {c[3] for c in cites}) != {"DQ-NOBODY-CITES-ME"}:
            bad.append("the uncited finding was not identified")

        #: AND A MISSING REGISTER MUST REFUSE, never pass.
        (root / REGISTER_REL).unlink()
        _ids2, refusal2 = _register_ids(root)
        if refusal2 is None:
            bad.append("a missing register did not refuse — that is a PASS over nothing")

    for b in bad:
        print(f"  FAIL  {b}")
    print(f"{'FAIL' if bad else 'OK'} — self-test: {len(bad)} failure(s) over 6 assertion(s)")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", help="the bundle root (the directory holding mac.project.yaml)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()
    if not a.root:
        print("REFUSED: a bundle root is required.")
        return 2
    root = pathlib.Path(a.root).resolve()
    if not P.concept_files(root):
        print(f"SKIP: no concept under {P.concepts_dir(root)} — nothing declares a ruling")
        return 0
    return check(root)


if __name__ == "__main__":
    sys.exit(main())
