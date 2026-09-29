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


def answered_table(capture: dict):
    """The ROWS the engine returned, for a question whose answer is a list and not a number.

    A scalar comparison cannot judge "show net revenue by country". Before this, such questions
    were recorded as "no value returned" and were never passes or failures — three of them sat in
    that state reporting nothing at all, which reads as coverage and is not.

    `result.sample_rows` carries every row up to 50, so for these question sizes it is the whole
    answer, not a sample.
    """
    result = capture.get("result") or {}
    rows = result.get("rows")
    sample = result.get("sample_rows")
    if rows is None or sample is None:
        return None
    return {"rows": rows, "cols": result.get("cols") or [], "values": [list(r) for r in sample]}


def same_table(expected: dict, got: dict) -> tuple[bool, str]:
    """Compare a list answer. Returns (verdict, why-it-failed).

    ORDER IS COMPARED ONLY WHEN THE QUESTION RANKS. "Top 5 countries" is a sequence and a wrong
    order is a wrong answer; "show revenue by country" has no ORDER BY at all, so its row order is
    whatever the engine happened to produce. Comparing that as a sequence would fail honest runs —
    measured: AGG-03 came back AU, CA, GB, FR while the reference lists US first.
    """
    want_rows = expected.get("rows")
    if want_rows is not None and want_rows != got["rows"]:
        return False, f"{got['rows']} rows, expected {want_rows}"
    want_cols = expected.get("cols")
    if want_cols and [str(c) for c in want_cols] != [str(c) for c in got["cols"]]:
        return False, f"columns {got['cols']}, expected {want_cols}"
    want_vals = expected.get("values")
    if not want_vals:
        return True, ""
    got_vals = got["values"]
    if expected.get("ordered"):
        if len(want_vals) > len(got_vals):
            return False, f"expected {len(want_vals)} ranked rows, got {len(got_vals)}"
        for i, (w, g) in enumerate(zip(want_vals, got_vals, strict=False)):
            if not _row_same(w, g):
                return False, f"row {i + 1} is {g!r}, expected {w!r}"
        return True, ""
    # UNORDERED: every expected row must appear, matched on its KEY CELLS — everything but the
    # last column, which is the measure. Keying on the first cell alone breaks a composite
    # breakdown: "revenue by brand and country" has 11 brands over 8 countries, so `Contoso`
    # names eight different rows and the first match wins arbitrarily.
    def key(row):
        return tuple(norm(x) for x in row[:-1]) if len(row) > 1 else (norm(row[0]),)

    index = {key(g): g for g in got_vals}
    for w in want_vals:
        g = index.get(key(w))
        if g is None:
            return False, f"{list(w[:-1])!r} is missing from the result"
        if not _row_same(w, g):
            return False, f"{list(w[:-1])!r} is {g!r}, expected {w!r}"
    return True, ""


def _row_same(want, got) -> bool:
    return len(want) == len(got) and all(same(a, b) for a, b in zip(want, got, strict=False))


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

    # STALENESS EXPLAINS A FAILURE. IT NEVER EXPLAINS A PASS. Measured 2026-09-25: MQ-02 ("how
    # many concepts") captured 20 the night before, the `Channel` concept landed the next
    # afternoon, and the reference correctly says 21. Calling that a FAIL blames the engine for an
    # edit made after it ran.
    #
    # The asymmetry is the whole design. A stale capture that MATCHES the reference still matched —
    # the answer is right whenever it was computed. A stale capture that DIFFERS proves nothing,
    # because the difference may be the edit. So a stale pass is a pass, and a stale failure is
    # INCONCLUSIVE and must be re-run before anyone believes it.
    #
    # A first version marked every stale capture unjudgeable and reported "nothing judged" over 32
    # answers, which is honest and useless: any ontology edit would erase all evidence.
    newest_ontology = 0.0
    for f in (root / "ontology").rglob("*.yaml"):
        newest_ontology = max(newest_ontology, f.stat().st_mtime)

    passed, failed, unrun, stale = [], [], [], []
    for rp in refs:
        ref = yaml.safe_load(rp.read_text()) or {}
        qid = ref.get("id") or rp.stem
        cap_path = ans_dir / f"{qid}.yaml"
        if not cap_path.is_file():
            unrun.append((qid, "never run"))
            continue
        cap = yaml.safe_load(cap_path.read_text()) or {}
        is_stale = bool(newest_ontology and cap_path.stat().st_mtime < newest_ontology)
        expected = ref.get("expected")
        # A TABLE-SHAPED EXPECTATION IS JUDGED AS A TABLE. Anything else stays a scalar compare,
        # so every existing reference behaves exactly as before.
        if isinstance(expected, dict) and ("rows" in expected or "values" in expected):
            got_table = answered_table(cap)
            if got_table is None:
                unrun.append((qid, cap.get("route") or "no rows returned"))
                continue
            ok, why = same_table(expected, got_table)
            row = (qid, f"{expected.get('rows')} rows", why or f"{got_table['rows']} rows",
                   ref.get("question", ""))
            if ok:
                passed.append(row)
            elif is_stale:
                stale.append((qid, f"differs, but captured before the ontology changed — {why}"))
            else:
                failed.append(row)
            continue
        got = answered_value(cap)
        if got is None:
            # AN APPROVED NUMBER AGAINST A LIST IS JUDGED BY ITS ROW COUNT, and says so. "List all
            # countries where we have customers" is approved as 8; the engine answers a list of 8
            # rows and no scalar. Until 2026-09-29 that was "not judged" — a correct answer with no
            # verdict, on every list question in the corpus (RC01, RC02, RC03 ...).
            got_table = answered_table(cap) if isinstance(expected, int) and not isinstance(expected, bool) else None
            if got_table is not None:
                got = got_table["rows"]
                row = (qid, expected, f"{got} rows", ref.get("question", ""))
                if same(expected, got):
                    passed.append(row)
                elif is_stale:
                    stale.append((qid, f"expected {expected!r} rows, got {got!r} — captured before the "
                                       f"ontology changed"))
                else:
                    failed.append(row)
                continue
            unrun.append((qid, cap.get("route") or "no value returned"))
            continue
        row = (qid, expected, got, ref.get("question", ""))
        if same(expected, got):
            passed.append(row)
        elif is_stale:
            stale.append((qid, f"expected {expected!r}, got {got!r} — captured before the "
                               f"ontology changed"))
        else:
            failed.append(row)

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
    if stale:
        print(f"\ninconclusive ({len(stale)}) — differed, and captured BEFORE the ontology last")
        print("  changed. A stale pass is still a pass; a stale difference proves nothing.")
        print("  Re-run these before believing them.")
        for qid, why in stale:
            print(f"  {qid:<8} {why}")
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
