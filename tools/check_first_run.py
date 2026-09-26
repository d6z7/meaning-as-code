#!/usr/bin/env python3
"""check_first_run.py — a bundle's FIRST-RUN STATE against the contract it declares.

WHY THIS EXISTS, in one sentence: until now "the import delivered" was a sentence I wrote, and the
operator's only way to check it was to read my prose.

THE MEASUREMENT THAT MADE IT NECESSARY. Two bundles, contoso2 and contoso3, each delivered 13 of 20
deliverables from a manifest and a connection. That result was reported in prose, and in the same
session thirteen defects were found in the reporting layer itself — a deliverable probing a path its
producer had abandoned, a stage declaring one of the two planes it writes, a count of 22 registers
printed beside 17 files, "no column is bounded and enumerable" printed beside 17 registers, a complete
measurement reported as FAIL. Every one of those was a claim about the state that did not match the
state. A gate is the only thing that closes that gap, and CORE.md §2 says why:

    "A check that cannot fail is a report, not a gate. A gate that passes having measured nothing is
     worse than none — it is a green that means 'did not run'."

THE CONTRACT IS AUTHORED, NOT DERIVED, AND THAT IS DELIBERATE. CORE.md §7 prefers derived tests —
"a test generated from the artifact it tests cannot drift from it" — and this gate is the exception it
names in the next breath: "Authored tests are for the claims no derivation can reach, and those are
exactly the ones needing a human authority stamp." An expected-state file regenerated from the run
would re-record whatever happened and prove nothing. `acceptance/expected_first_run.yaml` is written
once, stamped by the operator, and frozen.

WHAT IT COMPARES. Every probe comes from `mac_import` itself — DELIVERABLES, `_probe`, `_matches` —
so a deliverable has exactly ONE definition of how it sees itself, and this file cannot drift from the
report the operator reads:

    MISSING          a deliverable the contract requires, absent from the bundle
    UNEXPECTED       a deliverable the contract says is absent, now present -> the contract is STALE,
                     which is a finding about the contract, not about the bundle
    COUNT            a deliverable present at the wrong size (7 sources where 8 are owed)
    FINDING LOST     a data-quality finding the contract requires, no longer raised. THE MOST
                     IMPORTANT CLASS: it means the platform stopped detecting a defect it once caught.
    FINDING EXTRA    a finding the contract does not list. A FALSE-POSITIVE REGRESSION, and this class
                     is not hypothetical: a change to the reference measurer raised six absurd
                     findings on contoso2 (square metres referencing a product key) against one true
                     positive, and re-running that bundle is what caught it.

Exit 0 when the bundle matches its contract, 1 on any difference, 2 when there is no contract to
check against — which is not a verdict.

    python3 check_first_run.py <bundle-root> [--self-test]
"""

from __future__ import annotations

import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

CONTRACT = "acceptance/expected_first_run.yaml"

#: The shape printed on refusal. CORE.md §2: "on refusal, print the accepted shape, not only the
#: objection" — measured, seven of eight operators adopted a convention they learned from a gate's
#: failure message while a prose document describing it de-converged them.
ACCEPTED_SHAPE = """\
# acceptance/expected_first_run.yaml — AUTHORED ONCE AND FROZEN. Not generated: a contract derived
# from the run it checks would re-record whatever happened (CORE.md §7).
expected:
  present:  [D1, D2, D9, D10]      # deliverable ids that MUST be there
  absent:   [D4, D4b]              # ids that must NOT be, each for a reason the report states
  counts:   {D1: 7, D2: 5}         # optional, only where the SIZE is part of the contract
  findings: [DQ-NOKEY-SOME_VIEW]   # data-quality ids that MUST be raised
  dq_cases: 55                     # optional, the generated suite's case count
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.bundle).resolve()
    try:
        import yaml
    except ImportError as exc:
        print(f"COULD NOT RUN: {exc}")
        return 2

    path = root / CONTRACT
    if not path.is_file():
        print(f"COULD NOT RUN: {root.name} declares no first-run contract at {CONTRACT}, so there is "
              f"nothing to check the state AGAINST. This is not a pass.\n\nThe accepted shape:\n\n"
              f"{ACCEPTED_SHAPE}")
        return 2
    try:
        want = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("expected") or {}
    except Exception as exc:  # noqa: BLE001
        print(f"COULD NOT RUN: {CONTRACT} does not parse — {exc}\n\nThe accepted shape:\n\n"
              f"{ACCEPTED_SHAPE}")
        return 2
    if not want.get("present"):
        print(f"COULD NOT RUN: {CONTRACT} names no `expected.present`, so it asserts nothing. A "
              f"contract that cannot fail is not a contract.\n\nThe accepted shape:\n\n"
              f"{ACCEPTED_SHAPE}")
        return 2

    state, ids = _state(root)
    unknown = [i for i in list(want.get("present") or []) + list(want.get("absent") or [])
               if i not in ids]
    if unknown:
        print(f"COULD NOT RUN: {CONTRACT} names deliverable id(s) this framework does not define: "
              f"{', '.join(unknown)}. Known ids: {', '.join(ids)}")
        return 2

    diffs = compare(want, state, _findings(root, yaml), _dq_cases(root, yaml))
    for kind, detail in diffs:
        print(f"  {kind:14} {detail}")
    n = len(diffs)
    if n:
        print(f"\nFAIL: check_first_run — {root.name} differs from its own contract in {n} way(s) "
              f"over {len(ids)} deliverable(s); {CONTRACT} is the authority and was not met")
        return 1
    print(f"\nPASS: check_first_run — {root.name} matches {CONTRACT}: "
          f"{len(want.get('present') or [])} deliverable(s) present as required, "
          f"{len(want.get('absent') or [])} absent as required, "
          f"{len(want.get('findings') or [])} required finding(s) raised, over "
          f"{len(ids)} deliverable(s) defined")
    return 0


def compare(want: dict, state: dict[str, tuple[bool, int]], findings: set[str],
            dq_cases: int | None) -> list[tuple[str, str]]:
    """The whole verdict, PURE — so every reject class is reachable from the self-test with no bundle,
    no warehouse and no clock."""
    out: list[tuple[str, str]] = []
    for i in want.get("present") or []:
        if not state.get(i, (False, 0))[0]:
            out.append(("MISSING", f"{i} is required by the contract and is NOT present"))
    for i in want.get("absent") or []:
        if state.get(i, (False, 0))[0]:
            out.append(("UNEXPECTED", f"{i} is declared absent and IS present — the contract is "
                                      f"STALE, which is a finding about the contract"))
    for i, n in (want.get("counts") or {}).items():
        got = state.get(i, (False, 0))[1]
        if got != n:
            out.append(("COUNT", f"{i} holds {got} where the contract requires {n}"))
    for f in want.get("findings") or []:
        if f not in findings:
            out.append(("FINDING LOST", f"{f} is required and is NO LONGER RAISED — the platform "
                                        f"stopped detecting a defect it once caught"))
    extra = sorted(findings - set(want.get("findings") or []))
    for f in extra:
        out.append(("FINDING EXTRA", f"{f} is raised and the contract does not list it — a "
                                     f"false-positive regression until the contract says otherwise"))
    if want.get("dq_cases") is not None and dq_cases != want["dq_cases"]:
        out.append(("COUNT", f"the generated suite declares {dq_cases} case(s) where the contract "
                             f"requires {want['dq_cases']}"))
    return out


def _state(root: pathlib.Path) -> tuple[dict[str, tuple[bool, int]], list[str]]:
    """{id: (present, count)} — measured by `mac_import`'s OWN probes.

    NOT REIMPLEMENTED HERE, and that is the point. A deliverable already knows how to see itself; a
    second definition in this file would be free to drift from the report the operator reads, which is
    the exact defect class this gate exists to catch.
    """
    import mac_import as mi
    out: dict[str, tuple[bool, int]] = {}
    for d in mi.DELIVERABLES:
        if "probe" in d:
            got, _ = mi._probe(root, d["probe"])
            out[d["id"]] = (bool(got), 1 if got else 0)
        else:
            files = mi._matches(root, d["glob"])
            out[d["id"]] = (bool(files), len(files))
    return out, [d["id"] for d in mi.DELIVERABLES]


def _findings(root: pathlib.Path, yaml) -> set[str]:
    path = root / "data" / "quality" / "data_quality_register.yaml"
    if not path.is_file():
        return set()
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = doc.get("issues") or doc.get("findings") or []
    if isinstance(items, dict):
        items = list(items.values())
    return {str(f.get("id")) for f in items if f.get("id")}


def _dq_cases(root: pathlib.Path, yaml) -> int | None:
    path = root / "acceptance" / "data_sanity_generated.yaml"
    if not path.is_file():
        return None
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return len(doc.get("cases") or doc.get("properties") or [])


def _self_test() -> int:
    """One mutant per reject class plus a clean fixture (CORE.md §2).

    Every case drives `compare()`, which is pure — so the reject classes are proved without a bundle,
    a warehouse or a connector, and a failure here is never an environment problem.
    """
    want = {"present": ["D1", "D2"], "absent": ["D4"], "counts": {"D1": 7},
            "findings": ["DQ-NOKEY-V"], "dq_cases": 55}
    clean = {"D1": (True, 7), "D2": (True, 5), "D4": (False, 0)}
    cases = [
        ("CLEAN FIXTURE must pass", want, clean, {"DQ-NOKEY-V"}, 55, []),
        ("MUTANT a required deliverable is absent", want,
         {**clean, "D2": (False, 0)}, {"DQ-NOKEY-V"}, 55, ["MISSING"]),
        ("MUTANT a deliverable declared absent is present -> STALE CONTRACT", want,
         {**clean, "D4": (True, 3)}, {"DQ-NOKEY-V"}, 55, ["UNEXPECTED"]),
        ("MUTANT a present deliverable is the wrong size", want,
         {**clean, "D1": (True, 6)}, {"DQ-NOKEY-V"}, 55, ["COUNT"]),
        ("MUTANT a required finding is no longer raised", want, clean, set(), 55,
         ["FINDING LOST"]),
        ("MUTANT an unlisted finding appears -> FALSE POSITIVE REGRESSION", want, clean,
         {"DQ-NOKEY-V", "DQ-BROKENREF-SQUAREMETERS"}, 55, ["FINDING EXTRA"]),
        ("MUTANT the generated suite changed size", want, clean, {"DQ-NOKEY-V"}, 42, ["COUNT"]),
        # THE REGRESSION THAT MOTIVATED THIS GATE, in its measured shape: six false findings against
        # one true positive. A gate that reported only the first difference would have shown one.
        ("MUTANT six false positives are reported as SIX, not one", want, clean,
         {"DQ-NOKEY-V", "A", "B", "C", "D", "E", "F"}, 55,
         ["FINDING EXTRA"] * 6),
    ]
    bad = []
    for label, w, st, fnd, cases_n, expect in cases:
        got = [k for k, _ in compare(w, st, fnd, cases_n)]
        if sorted(got) != sorted(expect):
            bad.append(f"  FAIL  {label}\n        expected {expect}, got {got}")
    for line in bad:
        print(line)
    n = len(cases)
    if bad:
        print(f"\nFAIL: check_first_run self-test — {len(bad)} of {n} case(s) failed")
        return 1
    print(f"PASS: check_first_run self-test — {n}/{n} case(s): 7 mutant(s), one per reject class "
          f"(a required deliverable absent, a stale contract, a wrong size, a finding lost, a "
          f"false-positive regression, a resized suite, and six false positives counted as six) "
          f"plus a clean fixture that must pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
