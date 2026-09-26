#!/usr/bin/env python3
"""check_meaning_plane_not_imported.py — A BUNDLE MUST NOT IMPORT AN ONTOLOGY'S MEANING PLANE.

THE OPERATOR, 2026-09-26, reading a fresh bundle's descriptors: "you meta classes are populated from
WHICH ontology?!?!?! this cannot be ... please delete content".

WHAT HAPPENED. A bundle was pointed at a warehouse that already carried ANOTHER ontology's meaning
plane — the eight `meta_*` relations `mac_runtime.meaning_plane` emits so a planner can answer
questions ABOUT an ontology. The import measured them like any other relation and produced 32
artifacts across four planes:

    data/datasets/meta_concept.yaml         a descriptor for someone else's concept catalogue
    data/profiles/meta_field_role.yaml      a census of 137 of their field-role rows
    data/references_served/meta_*.yaml      their internal keys, drawn as this bundle's structure
    data/samples/meta_concept.sample.csv    rows reading ('AgeBand','enumeration') — ANOTHER
                                            BUNDLE'S CONCEPT NAMES, presented as this one's data

AND THE WORST OUTCOME WAS STILL AHEAD. The billed concept stage authors over the whole relation
inventory. With `meta_concept` in it, the model would have been asked what business notion that
relation represents — and the honest answer is "a concept", so the bundle would have grown an
ontology ABOUT an ontology, with every gate passing.

WHY A GATE AND NOT ONLY THE EXCLUSION. `mac_descriptors` now skips them at the entry point, but four
other producers read the warehouse directly, a bundle may be authored by hand, and a warehouse may
grow a meaning plane AFTER an import. The exclusion stops it happening; this notices it happened.

ONE HOME FOR THE NAMES. They come from `mac_runtime.meaning_plane._META_DEFS`, which is what EMITS
them, so a ninth relation is covered the day it is added. The literal fallback in
`mac_descriptors.meaning_plane_tables` is compared against it here — two derivations that can
disagree is the only arrangement in which either can be checked.

Exit 0 when no plane of the bundle mentions a meaning-plane relation, 1 on any artifact, 2 when the
bundle cannot be read.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

#: The planes an import writes, and what a hit in each one means.
_PLANES = {
    "data/datasets": "a descriptor for another ontology's catalogue",
    "data/sources": "a landing descriptor for another ontology's catalogue",
    "data/profiles": "a census of another ontology's declaration rows",
    "data/references": "another ontology's internal keys, as this bundle's structure",
    "data/references_served": "another ontology's internal keys, as this bundle's structure",
    "data/samples": "another bundle's CONCEPT NAMES, presented as this bundle's data",
    "data/lookups": "a register cut from another ontology's declarations",
    "ontology/concepts": "A CONCEPT ABOUT A CONCEPT — an ontology of an ontology",
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.bundle).resolve()
    if not root.is_dir():
        print(f"REFUSED: {root} is not a directory")
        return 2
    plane = _plane_names()
    if not plane:
        print("REFUSED: cannot determine the meaning-plane relation names")
        return 2

    findings: list[tuple[str, str, str]] = []
    for rel_dir, why in _PLANES.items():
        d = root / rel_dir
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*")):
            if not f.is_file():
                continue
            stem = f.name.split(".")[0]
            if stem in plane:
                findings.append((str(f.relative_to(root)), stem, why))

    checked = sum(1 for d in _PLANES if (root / d).is_dir())
    print(f"meaning-plane relations: {len(plane)}   planes present in this bundle: {checked}")
    if not findings:
        print("OK — no plane of this bundle carries an ontology's own declarations.")
        return 0

    print(f"\nTHIS BUNDLE IMPORTED {len(findings)} ARTIFACT(S) OF ANOTHER ONTOLOGY'S MEANING "
          f"PLANE:\n")
    for path, stem, why in findings:
        print(f"  {path}\n      {stem} — {why}")
    print("\nFAIL — delete them, and re-run the import: `mac_descriptors` excludes these relations\n"
          "       at the entry point, so a re-measured bundle will not carry them again.")
    return 1


def _plane_names() -> frozenset[str]:
    """The relation names, from the module that EMITS them — with the fallback CHECKED against it."""
    try:
        from mac_descriptors import _MEANING_PLANE_FALLBACK, meaning_plane_tables
    except Exception as exc:  # noqa: BLE001
        print(f"REFUSED: cannot import the exclusion list ({exc})")
        return frozenset()
    live = meaning_plane_tables()
    if live and _MEANING_PLANE_FALLBACK and live != _MEANING_PLANE_FALLBACK:
        # TWO DERIVATIONS THAT DISAGREE is the whole reason to keep both: the runtime grew or lost a
        # relation and the literal did not follow. Reported, and the UNION is used, because the
        # safer error is to exclude one relation too many.
        print(f"  DRIFT between the runtime's meaning plane and the literal fallback:\n"
              f"    only in the runtime: {sorted(live - _MEANING_PLANE_FALLBACK) or '—'}\n"
              f"    only in the literal: {sorted(_MEANING_PLANE_FALLBACK - live) or '—'}\n"
              f"  Using the union. Update `_MEANING_PLANE_FALLBACK` in mac_descriptors.py.")
        return live | _MEANING_PLANE_FALLBACK
    return live


def _self_test() -> int:
    """A name in the plane is a finding wherever it sits; a business relation never is."""
    from mac_descriptors import meaning_plane_tables
    plane = meaning_plane_tables()
    cases = [
        ("meta_concept in data/datasets      -> finding", "meta_concept", True),
        ("meta_field_role in data/samples    -> finding", "meta_field_role", True),
        ("dim_contoso_store                  -> fine", "dim_contoso_store", False),
        ("metadata_report (not a meta_ rel)  -> fine", "metadata_report", False),
    ]
    bad = 0
    for label, stem, want in cases:
        if (stem in plane) != want:
            bad += 1
            print(f"  FAIL  {label}")
    n = len(cases)
    print(f"\n{'FAIL' if bad else 'OK'} — self-test: {n - bad} of {n} seeded cases behaved "
          f"({len(plane)} meaning-plane relations known)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
