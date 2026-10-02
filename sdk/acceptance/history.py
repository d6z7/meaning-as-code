"""Per-question verdict history — one append-only record per question per run.

WHY THIS EXISTS. Operator, 2026-10-02: "we need per unit test the history of fails or passes",
after "two three other went from passed to fail!!! and this is exactly the problem with your vibe
coding". Every board all day was reported as TOTALS -- 25 pass, 27, 29, 30 -- and a total that
improves hides any number of questions breaking: +3 fixed and -2 broken reads as +1. When a
regression was alleged, the only per-question snapshot in existence was eleven hours old, so the
window that mattered could neither be confirmed nor denied. That is not a disagreement about
numbers; it is an absence of evidence.

WHAT A RECORD CARRIES, and why each field is here:

  at                      when the run happened, UTC -- the axis of the history
  question                the id
  agrees                  yes | no | ungradeable | null  -- the verdict the board shows
  why                     the grader's own sentence, so a flip is readable without re-running
  run_status              executed | refused | error | ...  -- a question can regress by ceasing
                          to run at all, which `agrees` alone does not distinguish from a wrong
                          number
  interpret               live | replay -- a flip between a frozen and a live run is a different
                          event from a flip between two runs of the same kind, and conflating them
                          wasted an hour on 2026-10-02
  ontology_fingerprint    WHICH DECLARATIONS produced it, so a regression is attributable rather
  acceptance_fingerprint  than merely visible, and WHICH ORACLE judged it -- a verdict can flip
                          because the reference was re-approved, which is not a defect

APPEND-ONLY, AND ONE FILE. `history.jsonl` under `acceptance/`, never rewritten and never pruned by
this module: the value of a history is precisely that nothing in the system may tidy it. One line
per question per run keeps a flip greppable (`grep '"STORE-04"' history.jsonl`) without loading the
whole board, which is 732 kB.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FILE = "history.jsonl"


def path_for(bundle: Path) -> Path:
    return Path(bundle) / "acceptance" / FILE


def append(bundle: Path, dashboard: dict[str, Any], *, interpret: str | None = None) -> int:
    """Append one record per question in ``dashboard``. Returns how many were written."""
    rows = []
    at = datetime.now(UTC).isoformat(timespec="seconds")
    for q in dashboard.get("questions") or []:
        qid = q.get("id")
        if not qid:
            continue
        ont = q.get("ontology") or {}
        # ONLY WHAT WAS ACTUALLY RUN. A question the batch did not touch keeps whatever verdict it
        # had, and writing that again would invent a measurement -- the history would then show a
        # pass at a time nothing was measured, which is worse than a gap.
        if not q.get("captured_at"):
            continue
        rows.append(
            {
                "at": at,
                "question": qid,
                "agrees": ont.get("agrees"),
                "why": ont.get("why"),
                "run_status": q.get("run_status"),
                "interpret": interpret,
                "captured_at": q.get("captured_at"),
                "ontology_fingerprint": q.get("ontology_fingerprint"),
                "acceptance_fingerprint": q.get("acceptance_fingerprint"),
            }
        )
    if not rows:
        return 0
    p = path_for(bundle)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    return len(rows)


def read(bundle: Path, question: str | None = None) -> dict[str, list[dict]]:
    """``{question_id: [record, ...]}`` in file order, optionally for one question."""
    p = path_for(bundle)
    out: dict[str, list[dict]] = defaultdict(list)
    if not p.is_file():
        return {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:  # noqa: BLE001 - a corrupt line must not hide the rest of the history
            continue
        qid = r.get("question")
        if qid and (question is None or qid == question):
            out[qid].append(r)
    return dict(out)


def flips(bundle: Path) -> list[dict]:
    """Every point a question's verdict CHANGED, newest first — the regression list.

    `was`/`now` plus both fingerprints, so a flip can be read as "this declaration change did it"
    or "the oracle was re-approved" without re-running anything.
    """
    out = []
    for qid, records in read(bundle).items():
        for prev, cur in zip(records, records[1:], strict=False):
            if prev.get("agrees") != cur.get("agrees"):
                out.append(
                    {
                        "question": qid,
                        "at": cur.get("at"),
                        "was": prev.get("agrees"),
                        "now": cur.get("agrees"),
                        "why": cur.get("why"),
                        "regressed": prev.get("agrees") == "yes" and cur.get("agrees") != "yes",
                        "ontology_fingerprint": [
                            prev.get("ontology_fingerprint"),
                            cur.get("ontology_fingerprint"),
                        ],
                        "acceptance_fingerprint": [
                            prev.get("acceptance_fingerprint"),
                            cur.get("acceptance_fingerprint"),
                        ],
                    }
                )
    return sorted(out, key=lambda r: str(r.get("at")), reverse=True)


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bundle")
    ap.add_argument("--question", help="one question's trajectory")
    ap.add_argument("--flips", action="store_true", help="every verdict change, newest first")
    a = ap.parse_args(argv)
    bundle = Path(a.bundle)

    if a.flips:
        rows = flips(bundle)
        bad = [r for r in rows if r["regressed"]]
        print(f"{len(rows)} verdict change(s), {len(bad)} of them regressions\n")
        for r in rows:
            mark = "REGRESSED" if r["regressed"] else "         "
            print(f"  {mark} {r['at']}  {r['question']:10s} {r['was']} -> {r['now']}")
            if r["why"]:
                print(f"            {str(r['why'])[:100]}")
        return 1 if bad else 0

    hist = read(bundle, a.question)
    if not hist:
        print("no history yet — it is written by a run")
        return 0
    for qid in sorted(hist):
        rows = hist[qid]
        marks = "".join(
            {"yes": "P", "no": "F", "ungradeable": "u"}.get(str(r.get("agrees")), "·")
            for r in rows
        )
        print(f"  {qid:10s} {marks}   ({len(rows)} run(s), newest last)")
        if a.question:
            for r in rows:
                print(
                    f"      {r['at']}  {str(r.get('agrees')):12s} {str(r.get('interpret') or '-'):7s} "
                    f"ont={str(r.get('ontology_fingerprint'))[:12]}  {str(r.get('why'))[:70]}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
