#!/usr/bin/env python3
"""check_cards_match_runs — the card and the run record must not disagree about the same check.

TWO ARTIFACTS, ONE FACT. `acceptance/test_cards.json` is a PROJECTION: it restates, per check, what
was asked, what SQL ran, what came back, and what the verdict was. The verdict's source of truth is
the run record beside the suite (`<suite>_runs.json`), written by the runner at execution time. The
card is derived; the record is evidence. When a derived artifact and its source disagree, the
derived one is wrong by definition — and every consumer reads the derived one.

THE MEASURED FAILURE. `D-TYPE-ENCODING`, severity blocker, sat at FAIL on its card carrying its
pre-fix measurement (542,221 rows contradicting a specification) while the run record recorded PASS
ten minutes after the corrected view was deployed. The card projection had simply not been re-run.
Every surface that reads cards — including a per-concept page whose entire purpose is to say what
has and has not been proved — reported a contradiction that no longer existed. An operator acting
on it would have spent the morning re-fixing a closed bug.

WHY A GATE AND NOT A CONVENTION. Nothing about a stale card looks stale. It is well-formed, it
carries real SQL and real numbers, and those numbers were true when they were taken. Staleness has
no appearance; it is only visible by comparison, and nothing was comparing.

WHAT IT REFUSES TO DO. It does not judge whether a verdict is correct — that is the suite's job. It
does not require every card to have a run (a declared-but-never-executed check is a legitimate
state, reported here rather than failed). It refuses exactly one thing: a card asserting a verdict
its own run record contradicts.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mac_diag as D  # noqa: E402

DISAGREES = "card-contradicts-run"

# A stale FAIL and a stale PASS are both wrong, and they are NOT equally dangerous. A card showing
# FAIL over a fixed check wastes a morning; a card showing PASS over a broken one ships the break.
# Both are reported, and the sentence says which way it fell.
WORSE = "the card hides a failure the run recorded"
BETTER = "the card reports a failure the run has since cleared"


def judge(pairs: list[dict]) -> list[tuple[str, str]]:
    """PURE: [{id, card, run, record}] -> [(class, sentence)]. Filesystem-free so the rule can be
    mutant-tested without a bundle."""
    out: list[tuple[str, str]] = []
    for p in pairs:
        card, run = str(p.get("card") or ""), str(p.get("run") or "")
        if not run or card == run:
            continue
        drift = WORSE if (card == "PASS" and run != "PASS") else BETTER
        out.append(
            (
                DISAGREES,
                f"{p['id']}: card says {card}, {p.get('record','the run record')} says {run} — "
                f"{drift}. The card is a projection of the record; re-project it.",
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

    cards_file = root / "acceptance" / "test_cards.json"
    if not cards_file.exists():
        return D.refuse_empty("check_cards_match_runs", cards_file, unit="card")
    try:
        cards = json.loads(cards_file.read_text(encoding="utf-8")).get("cards") or []
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: check_cards_match_runs — {cards_file.name} unreadable: {str(e)[:100]}")
        return 1
    if not cards:
        return D.refuse_empty("check_cards_match_runs", cards_file, unit="card")

    records = sorted((root / "acceptance").glob("*_runs.json"))
    if not records:
        return D.refuse_empty("check_cards_match_runs", root / "acceptance", unit="run record")

    runs: dict[str, tuple[str, str]] = {}
    for p in records:
        try:
            results = json.loads(p.read_text(encoding="utf-8")).get("results") or []
        except Exception:  # noqa: BLE001
            continue
        for r in results:
            runs[str(r.get("id"))] = (str(r.get("status") or ""), p.name)

    pairs, never_run = [], []
    for c in cards:
        cid = str(c.get("id"))
        if cid not in runs:
            never_run.append(cid)
            continue
        status, record = runs[cid]
        pairs.append({"id": cid, "card": str(c.get("status") or ""), "run": status, "record": record})

    findings = judge(pairs)

    if a.json:
        print(
            json.dumps(
                {
                    "cards": len(cards),
                    "records": len(records),
                    "compared": len(pairs),
                    "never_run": never_run,
                    "findings": [{"class": k, "msg": m} for k, m in findings],
                },
                indent=1,
            )
        )
        return 1 if findings else 0

    for k, m in findings:
        print(f"  [{k}] {m}")
    # REPORTED, NOT FAILED. A card with no run is declared-but-unexecuted — a real state, and one
    # this gate must not push anyone to hide by deleting the card.
    if never_run:
        print(
            f"  [no-run] {len(never_run)} card(s) appear in no run record: "
            f"{', '.join(never_run[:6])}{' …' if len(never_run) > 6 else ''}"
        )
    tail = (
        f"{len(pairs)} of {len(cards)} card(s) compared against {len(records)} run record(s); "
        f"{len(never_run)} never executed"
    )
    if findings:
        print(f"FAIL: check_cards_match_runs — {len(findings)} card(s) contradict their run — {tail}")
        return 1
    print(f"PASS: check_cards_match_runs — {tail}")
    return 0


def self_test() -> int:
    """One mutant per direction of drift, plus the controls that stop it over-firing."""
    cases = [
        ("agreement is not a finding", [{"id": "A", "card": "PASS", "run": "PASS"}], 0),
        # THE MEASURED DEFECT: a fixed check still carried as failing.
        ("a stale FAIL over a cleared run", [{"id": "A", "card": "FAIL", "run": "PASS"}], 1),
        # THE DANGEROUS DIRECTION: a break the card hides.
        ("a stale PASS over a failing run", [{"id": "A", "card": "PASS", "run": "FAIL"}], 1),
        ("drift between two non-PASS states still counts",
         [{"id": "A", "card": "FROZEN", "run": "FAIL"}], 1),
        ("several drifts report once each",
         [{"id": "A", "card": "FAIL", "run": "PASS"}, {"id": "B", "card": "PASS", "run": "FAIL"}], 2),
        # NEGATIVE CONTROLS.
        ("a card with no run is not a finding", [{"id": "A", "card": "FAIL", "run": ""}], 0),
        ("an empty comparison set is not a finding", [], 0),
        ("agreement on a non-PASS state is not a finding",
         [{"id": "A", "card": "FAIL", "run": "FAIL"}], 0),
    ]
    bad = 0
    for name, pairs, want in cases:
        got = len(judge(pairs))
        if got != want:
            bad += 1
            print(f"  [SELF-TEST FAIL] {name}: {got} finding(s), expected {want}")
    n = len(cases)
    print(
        f"{'PASS' if not bad else 'FAIL'}: check_cards_match_runs self-test — {n - bad}/{n} "
        f"case(s): 4 mutant(s) of the rule (stale FAIL, stale PASS, non-PASS drift, several at "
        f"once), and 4 negative control(s) (a card never run, an empty set, and agreement on both "
        f"a passing and a failing state)"
    )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
