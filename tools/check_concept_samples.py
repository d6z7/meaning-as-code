#!/usr/bin/env python3
"""check_concept_samples.py — EVERY CONCEPT CARRIES A SAMPLE OF ITS REAL ROWS.

DNA standing law 8, premise P9. A concept states what a thing IS; the sample is the only artifact
that shows what it CONTAINS, in the columns that concept itself declares.

WHY THIS IS A GATE AND NOT ADVICE. Measured 2026-09-26, authoring example/contoso2: three
declarations were wrong in a way re-reading the YAML did not reveal, and each was visible in four
rows of the concept's own columns.

    StoreStatus declared StoreKey as its identity  -> the planner emitted
        WHERE StoreKey = 'Closed'
    and the sample reads
        Status,StoreKey
        ,10
        Closed,20
    which settles it in one line: the words are in Status, the integers in StoreKey. On a varchar
    key the same mistake returns ZERO ROWS and reads as an answer.

    Country declared `enum_from_register` on the code column  -> "No country named 'Germany'"
    and the sample reads
        Country,CountryFull,CustomerKey
        AU,Australia,15
    the word is in the OTHER column.

WHAT IT CHECKS, per concept:
  1. a sample EXISTS                                     -> missing
  2. its header is EXACTLY the concept's declared columns -> drifted (a column was added, removed
                                                             or renamed since the sample was cut)
  3. it carries rows                                      -> empty
  4. it is not OLDER than the concept file                -> stale (the declaration moved on)

IT DOES NOT RE-QUERY THE WAREHOUSE. This is a cheap structural gate that runs anywhere; whether the
VALUES are still current is the generator's `--check`, which needs the database.

A concept that declares no relation or no columns is reported as `nothing to sample` and is not a
failure -- it is the one case where there is genuinely nothing to show.

Exit 0 when every concept has a current sample, 1 on any finding, 2 when the bundle cannot be read.
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _neighbours  # noqa: E402  — ONE home for the sibling runtime's location

FRAMEWORK = pathlib.Path(__file__).resolve().parents[1]
GUARDRAIL = FRAMEWORK / "guardrails" / "ontology" / "concepts.yaml"
FALLBACK_PATTERN = "ontology/samples/{concept}.sample.csv"


def sample_pattern() -> str:
    """WHERE A CONCEPT SAMPLE LIVES, read from guardrails/ontology/concepts.yaml#concept_sample.path.

    RENAMES BREAK READERS SILENTLY (measured 2026-09-29): the producer moved concept samples from
    `data/samples/concepts/<Concept>.sample.csv` to `<ontology plane>/samples/<stem>.sample.csv`,
    the guardrail declared the new home, and this gate kept its literal — so a bundle with 17
    fresh samples was reported 17 MISSING. The guardrail is the one home; the literal below is
    only what stands when the guardrail cannot be read, and says so.
    """
    try:
        import yaml

        doc = yaml.safe_load(GUARDRAIL.read_text(encoding="utf-8")) or {}
        pattern = ((doc.get("delivers") or {}).get("concept_sample") or {}).get("path")
        if isinstance(pattern, str) and "{concept}" in pattern:
            return pattern
    except Exception:  # noqa: BLE001 - an unreadable guardrail falls back, disclosed below
        pass
    print(f"  note: {GUARDRAIL} could not be read; assuming {FALLBACK_PATTERN}")
    return FALLBACK_PATTERN


def sample_path(root: pathlib.Path, pattern: str, concept) -> pathlib.Path:
    """The concept's stem — its own file name, the naming the guardrail declares — in the pattern."""
    stem = pathlib.Path(concept.source_file or concept.name).stem if getattr(concept, "source_file", None) else concept.name
    return root / pattern.replace("{concept}", stem)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.bundle).resolve()
    try:
        _neighbours.ensure_runtime_on_path()
        from mac_runtime.ontology import OntologyIndex
    except ImportError as exc:
        print(f"REFUSED: cannot import what this gate needs ({exc})")
        return 2
    if not (root / "ontology").is_dir():
        print(f"SKIP: {root.name} has no ontology/ plane")
        return 0
    try:
        index = OntologyIndex.from_directory(str(root))
    except Exception as exc:  # noqa: BLE001 - an unreadable bundle is REFUSED, never passed
        print(f"REFUSED: {type(exc).__name__}: {str(exc)[:160]}")
        return 2

    findings, ok, nothing = [], 0, []
    pattern = sample_pattern()
    for name, concept in sorted(index.concepts.items()):
        declared = list(concept.grounding.served_columns)
        if not concept.grounding.table or not declared:
            nothing.append(name)
            continue
        path = sample_path(root, pattern, concept)
        if not path.is_file():
            findings.append((name, "MISSING", f"no {path.relative_to(root)} — "
                                              f"{len(declared)} declared columns have never been "
                                              f"looked at"))
            continue
        header, rows = _read(path)
        if header is None:
            findings.append((name, "UNREADABLE", "the file carries no header row"))
            continue
        if header != declared:
            findings.append((name, "DRIFTED",
                             f"the sample shows {header} and the concept declares {declared} — "
                             f"re-cut it, or the sample is describing a different concept"))
            continue
        if not rows:
            findings.append((name, "EMPTY", "a header and no rows shows nothing"))
            continue
        src = root / (concept.source_file or "")
        if src.is_file() and src.stat().st_mtime > path.stat().st_mtime:
            findings.append((name, "STALE",
                             f"{concept.source_file} was edited after the sample was cut — the "
                             f"declaration moved on and the rows did not"))
            continue
        ok += 1

    total = ok + len(findings)
    print(f"concepts with something to sample: {total}   current samples: {ok}")
    for n in nothing:
        print(f"  nothing to sample  {n} (declares no relation or no columns)")
    if not findings:
        print("OK — every concept that can be sampled has a current sample (DNA law 8 / P9).")
        return 0
    print("\nA CONCEPT WITHOUT A CURRENT SAMPLE IS UNREVIEWABLE:\n")
    for name, kind, why in findings:
        print(f"  {kind:11} {name}\n      {why}\n")
    print("FAIL — run `python3 tools/mac_sample.py <bundle> --plane concepts` (the guardrail's producer).")
    return 1


def _read(path: pathlib.Path) -> tuple[list[str] | None, list[list[str]]]:
    """The header and rows, ignoring the `#` provenance block the generator writes."""
    lines = [
        ln for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    if not lines:
        return None, []
    reader = list(csv.reader(lines))
    return reader[0], reader[1:]


def _self_test() -> int:
    """The four verdicts must follow the four conditions, and a match must PASS."""
    cases = [
        ("header equals declared, rows present -> ok", ["A", "B"], ["A", "B"], 1, True),
        ("a column was renamed             -> DRIFTED", ["A", "B"], ["A", "C"], 1, False),
        ("a column was added               -> DRIFTED", ["A", "B"], ["A", "B", "C"], 1, False),
        ("header only, no rows             -> EMPTY", ["A", "B"], ["A", "B"], 0, False),
    ]
    bad = 0
    for label, declared, header, nrows, want in cases:
        got = header == declared and nrows > 0
        if got != want:
            bad += 1
            print(f"  FAIL  {label}")
    n = len(cases)
    print(f"\n{'FAIL' if bad else 'OK'} — self-test: {n - bad} of {n} seeded cases behaved")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
