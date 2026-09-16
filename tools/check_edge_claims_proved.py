#!/usr/bin/env python3
"""check_edge_claims_proved — an edge's cardinality is a CLAIM. Does anything prove it?

WHAT AN EDGE ASSERTS. `cardinality: "1"` on an endpoint is a statement about the warehouse: this
key identifies at most one row over there. It is exactly the claim a relational engine records as
a UNIQUE or FOREIGN KEY constraint — and an engine does NOT let such a claim stand unexamined. A
constraint added NOT VALID is enforced for new rows and unproven over existing ones, and
`pg_constraint.convalidated` SAYS SO, so the planner declines to rely on it. Unproven is a TYPE,
not a silence.

THE MEASURED GAP. This estate authored the vocabulary and skipped the proof. Edges declare
cardinality on both endpoints and most carry a literal join predicate, `verified_by` exists in the
schema expressly to prove such a claim, and it was used ZERO times. Meanwhile one bundle's
acceptance suite had ALREADY MEASURED one of those claims false — the cited expectation reported
twelve keys holding more than one row — and the edge went on reading `confidence: C` because
nothing joined the red to the claim.

WHY check_references.py IS NOT THIS GATE. It proves a `verified_by` pointer RESOLVES: the suite
exists, the id is in it. It never opens the run record, so an edge may cite an expectation that
FAILED, or one that has never been executed, and that gate stays green. A pointer whose target's
verdict nobody reads is a citation, not a proof.

WHAT THIS REFUSES TO DO. It does not judge an edge that makes no claim, and it does not treat a
missing `verified_by` as a failure — an unproved claim is a legitimate state, and reporting it is
the point. What it refuses is a claim whose own cited evidence CONTRADICTS it, or whose evidence
was never run, being carried as though it were established.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mac_diag as D  # noqa: E402

DISPROVED = "claim-disproved"
NEVER_RUN = "claim-never-run"
UNRESOLVABLE = "claim-unresolvable"

# Verdicts that leave a claim standing. FROZEN is a recorded deferral, not evidence, so it does not
# prove a claim — but it is a deliberate human act, so it is reported rather than failed.
PROVING = {"PASS"}
DEFERRING = {"FROZEN", "ACCEPTED"}


def _load(p: pathlib.Path):
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def runs_path_for(root: pathlib.Path, suite_rel: str) -> pathlib.Path:
    """The run record beside a suite file. `<stem>.yaml` -> `<stem>_runs.json`, with the two
    aliases this estate's writer uses."""
    stem = pathlib.PurePath(suite_rel).stem
    alias = {"properties": "property", "retrieval": "retrieval"}
    return root / "acceptance" / f"{alias.get(stem, stem)}_runs.json"


def verdict_of(root: pathlib.Path, ref: str) -> tuple[str | None, str]:
    """(verdict, note) for a `path/to/suite.yaml#ID` reference, read from the RUN RECORD.

    Returns verdict None when the claim cannot be judged, with a note saying which link broke —
    a missing suite, an id the suite does not declare, an absent run record, or an id the record
    does not carry. Each is a different repair and the caller should not have to guess.
    """
    if "#" not in ref:
        return None, f"reference carries no #id: {ref!r}"
    suite_rel, cid = ref.split("#", 1)

    # MEASURED EVIDENCE IS EVIDENCE. Until now `verified_by` could only cite an EXPECTATION someone
    # authored, which is why one edge of thirty-two carried any: proving a relationship required a
    # human to write a test for it. An edge's cardinality is pure counting, so mac_measure_edges can
    # record it without an author — and this resolves that record the same way it resolves a suite,
    # by reading the numbers and judging them, never by trusting the pointer's existence.
    if suite_rel.endswith("edge_measurements.json"):
        rec = root / suite_rel
        if not rec.exists():
            return None, f"cites a measurement at {suite_rel} which does not exist"
        try:
            results = json.loads(rec.read_text(encoding="utf-8")).get("results") or []
        except Exception as e:  # noqa: BLE001
            return None, f"{rec.name} is unreadable: {str(e)[:80]}"
        hit = [r for r in results if str(r.get("edge")) == cid]
        if not hit:
            return None, f"{rec.name} carries no measurement for {cid}"
        m = hit[0]
        lhs, matched, fan = int(m.get("lhs") or 0), int(m.get("matched") or 0), int(m.get("fanout") or 0)
        # The same two numbers check_edge_joins_measured judges. Stated here rather than imported so
        # a change to one gate cannot silently change the other's verdict.
        return ("PASS" if (lhs and matched == lhs and fan <= 1) else "FAIL"), ""

    suite = root / suite_rel
    if not suite.exists():
        return None, f"suite not found: {suite_rel}"
    declared = {
        str(p.get("id")) for p in (_load(suite).get("properties") or []) if isinstance(p, dict)
    }
    if cid not in declared:
        return None, f"{suite_rel} does not declare {cid}"
    rec = runs_path_for(root, suite_rel)
    if not rec.exists():
        return None, f"no run record at {rec.name} — {cid} is declared but has never been executed"
    try:
        results = json.loads(rec.read_text(encoding="utf-8")).get("results") or []
    except Exception as e:
        return None, f"{rec.name} is unreadable: {str(e)[:80]}"
    hit = [r for r in results if str(r.get("id")) == cid]
    if not hit:
        return None, f"{rec.name} carries no result for {cid} — cited but not in the last run"
    return str(hit[0].get("status") or "").upper(), ""


def judge(claims: list[dict]) -> list[tuple[str, str]]:
    """PURE: [{edge, ref, verdict, note}] -> [(reject_class, sentence)]. Separated from the
    filesystem so the rule can be mutant-tested without a bundle on disk."""
    out: list[tuple[str, str]] = []
    for c in claims:
        edge, ref, v, note = c["edge"], c["ref"], c.get("verdict"), c.get("note") or ""
        if v is None:
            out.append((UNRESOLVABLE, f"{edge}: cites {ref} — {note}"))
        elif v in PROVING:
            continue
        elif v in DEFERRING:
            continue  # reported by the caller, not a finding
        else:
            out.append(
                (
                    DISPROVED,
                    f"{edge}: its OWN cited evidence contradicts it — {ref} is {v}. "
                    f"The edge asserts a cardinality this expectation measured false.",
                )
            )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    if "--self-test" in sys.argv[1:]:
        return self_test()
    a = ap.parse_args()
    root = pathlib.Path(a.root).resolve()

    edges_file = root / "ontology" / "edges.yaml"
    if not edges_file.exists():
        return D.refuse_empty("check_edge_claims_proved", edges_file, unit="edge")
    edges = _load(edges_file).get("edges") or []
    if not edges:
        return D.refuse_empty("check_edge_claims_proved", edges_file, unit="edge")

    # THE CLAIMING POPULATION, not every edge. An edge that asserts no cardinality asserts nothing
    # to prove, and counting it would inflate the denominator with abstentions.
    claiming = [
        e
        for e in edges
        if any(
            (e.get("endpoints") or {}).get(side, {}).get("cardinality")
            for side in ("from", "to")
        )
    ]
    claims, unproved = [], []
    for e in claiming:
        ref = e.get("verified_by")
        if not isinstance(ref, str) or not ref.strip():
            unproved.append(str(e.get("edge_id")))
            continue
        v, note = verdict_of(root, ref)
        claims.append({"edge": str(e.get("edge_id")), "ref": ref, "verdict": v, "note": note})

    findings = judge(claims)
    deferred = [c for c in claims if c.get("verdict") in DEFERRING]
    proved = [c for c in claims if c.get("verdict") in PROVING]

    if a.json:
        print(json.dumps({"edges": len(edges), "claiming": len(claiming),
                          "proved": len(proved), "unproved": unproved,
                          "findings": [{"class": k, "msg": m} for k, m in findings]}, indent=1))
        return 1 if findings else 0

    for k, m in findings:
        print(f"  [{k}] {m}")
    for c in deferred:
        print(f"  [deferred] {c['edge']}: {c['ref']} is {c['verdict']} — a recorded deferral, "
              f"not evidence")
    # UNPROVED IS REPORTED, NEVER FAILED. This is the NOT VALID state: the claim stands, nothing
    # has examined it, and the bundle says so out loud instead of implying it was checked.
    if unproved:
        print(f"  [unproved] {len(unproved)} of {len(claiming)} claiming edge(s) cite no evidence: "
              f"{', '.join(unproved[:6])}{' …' if len(unproved) > 6 else ''}")
    tail = (f"{len(proved)} of {len(claiming)} cardinality claim(s) proved by a passing "
            f"expectation, {len(unproved)} unproved")
    if findings:
        print(f"FAIL: check_edge_claims_proved — {len(findings)} claim(s) contradicted or "
              f"unjudgeable — {tail}")
        return 1
    print(f"PASS: check_edge_claims_proved — {tail}")
    return 0


def self_test() -> int:
    """One mutant per way a claim can fail to stand, plus the controls that stop it over-firing."""
    cases = [
        ("a passing expectation proves it",
         [{"edge": "a__of_b", "ref": "s.yaml#X", "verdict": "PASS"}], 0),
        ("a FAILING expectation disproves it",
         [{"edge": "a__of_b", "ref": "s.yaml#X", "verdict": "FAIL"}], 1),
        ("an ERROR is not a proof",
         [{"edge": "a__of_b", "ref": "s.yaml#X", "verdict": "ERROR"}], 1),
        ("VACUOUS is not a proof — it judged nothing",
         [{"edge": "a__of_b", "ref": "s.yaml#X", "verdict": "VACUOUS"}], 1),
        ("cited but never run is unjudgeable, not proved",
         [{"edge": "a__of_b", "ref": "s.yaml#X", "verdict": None, "note": "no run record"}], 1),
        # NEGATIVE CONTROLS.
        ("FROZEN is a deferral, reported not failed",
         [{"edge": "a__of_b", "ref": "s.yaml#X", "verdict": "FROZEN"}], 0),
        ("no claims at all is not a finding",
         [], 0),
        ("one proved beside one disproved reports exactly one",
         [{"edge": "a", "ref": "s.yaml#P", "verdict": "PASS"},
          {"edge": "b", "ref": "s.yaml#F", "verdict": "FAIL"}], 1),
    ]
    bad = 0
    for name, claims, want in cases:
        got = len(judge(claims))
        if got != want:
            bad += 1
            print(f"  [SELF-TEST FAIL] {name}: {got} finding(s), expected {want}")
    n = len(cases)
    print(
        f"{'PASS' if not bad else 'FAIL'}: check_edge_claims_proved self-test — {n - bad}/{n} "
        f"case(s): 4 mutant(s) of the rule (FAIL, ERROR, VACUOUS, never-run), and 4 negative "
        f"control(s) (a pass, a deferral, an empty population, and a mixed set)"
    )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
