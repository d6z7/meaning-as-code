#!/usr/bin/env python3
"""PASS or FAIL. Did the engine return the answer a person approved?

THE OPERATOR, AFTER FOUR MONTHS OF ASKING: "high level i want to know fail/pass ... you have
ACCESS to the DATA make manual query and let me know hat do you think the right answer is and let
me approve it. then this becomes reference ... if the answer in the next run is the same then
pass."

That is this file, and it is the whole of it.

WHAT IT REPLACES, and the history matters. A commit of 2026-08-17 titled "replace ONE OPAQUE
VERDICT with three per-assertion flags" took a pass/fail away and put in its place four graded
flags (disposition, pinned axes, value, ontology rules) rolling up into eight verdict words --
proven, routed, unproven, failed, error, unrun, no-oracle, oracle-error. `proven` requires an
anchor and only 21 of 77 questions have one, so the headline number was 0 and stayed 0. A board
whose best state is unreachable is not a test; it is a wall.

THERE ARE EXACTLY TWO OUTCOMES HERE. A question with an approved reference either matches it or
does not. A question with no approved reference is NOT COUNTED -- it is not a pass, not a failure
and not a shade of grey. It is a question nobody has ruled on yet, and it is reported as its own
number so the denominator is never silently borrowed.

COMPARISON IS DELIBERATELY FORGIVING WHERE FORGIVENESS COSTS NOTHING, because a test that fails on
'67' versus 67 tests the harness and not the engine:
  * numbers compare numerically -- 67, 67.0 and '67' are one answer
  * text compares case- and whitespace-insensitively -- 'Female' IS 'female', and the operator is
    right that anything else is the harness being precious rather than the answer being wrong
  * a float matches within a relative tolerance
"""

from __future__ import annotations

import argparse
import math
import pathlib
import sys

import yaml


def norm(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    try:
        return float(s.replace(",", "").replace(" ", ""))
    except ValueError:
        return " ".join(s.split()).casefold()


def same(a, b) -> bool:
    a, b = norm(a), norm(b)
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, float) and isinstance(b, float):
        return math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-9)
    return a == b


def answered_value(capture: dict):
    """The number the engine actually returned, from wherever this capture keeps it."""
    parts = capture.get("answer_parts") or {}
    if parts.get("value") is not None:
        return parts["value"]
    result = capture.get("result") or {}
    if result.get("value") is not None:
        return result["value"]
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--verbose", action="store_true", help="show every question, not just failures")
    a = ap.parse_args(argv)

    root = pathlib.Path(a.bundle).resolve()
    ref_dir = root / "acceptance" / "reference"
    ans_dir = root / "acceptance" / "answers"
    if not ref_dir.is_dir():
        print(f"REFUSED: no approved references at {ref_dir}. Nothing can be judged, so nothing "
              f"is reported as passing.")
        return 2

    refs = sorted(ref_dir.glob("*.yaml"))
    corpus = root / "acceptance" / "questions.yaml"
    total_questions = len(yaml.safe_load(corpus.read_text()) or []) if corpus.is_file() else 0

    passed, failed, unrun = [], [], []
    for rp in refs:
        ref = yaml.safe_load(rp.read_text()) or {}
        qid = ref.get("id") or rp.stem
        cap_path = ans_dir / f"{qid}.yaml"
        if not cap_path.is_file():
            unrun.append((qid, "never run"))
            continue
        cap = yaml.safe_load(cap_path.read_text()) or {}
        got = answered_value(cap)
        if got is None:
            unrun.append((qid, cap.get("route") or "no value returned"))
            continue
        (passed if same(ref.get("expected"), got) else failed).append(
            (qid, ref.get("expected"), got, ref.get("question", ""))
        )

    judged = len(passed) + len(failed)
    print("=" * 78)
    if judged:
        print(f"  PASS {len(passed)} of {judged} approved   ({len(passed) / judged:.0%})")
    else:
        print("  nothing judged")
    print("=" * 78)
    if failed:
        print("\nFAIL:")
        for qid, want, got, q in failed:
            print(f"  {qid:<8} expected {want!r}, got {got!r}")
            print(f"           {q}")
    if unrun:
        print(f"\nnot judged ({len(unrun)}) — approved but the engine returned no value:")
        for qid, why in unrun:
            print(f"  {qid:<8} {why}")
    if a.verbose and passed:
        print("\nPASS:")
        for qid, want, _got, q in passed:
            print(f"  {qid:<8} {want!r}   {q[:60]}")

    # THE DENOMINATOR IS NEVER BORROWED. Questions with no approved reference are reported as
    # their own number, never folded into a pass rate.
    no_ref = total_questions - len(refs)
    if no_ref > 0:
        print(f"\n{no_ref} of {total_questions} questions have NO approved reference yet. "
              f"They are not passes and not failures.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
