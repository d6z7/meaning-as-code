"""Is `Intent.confidence` worth gating on?

CATEGORY **RECOGNITION** (TESTING.md §2). PIPELINE_TESTING.md §3.1, third metric.

  SUBJECT  the interpreter's self-score
  CLAIM    a low confidence means a worse reading than a high one
  ORACLE   the ANCHORS — derived from the data by two routes, never from the engine

WHY NOW. `interpret_or_clarify` turns any Intent scoring below 0.50 into a clarification, and on
the 2026-09-24 board that was **15 of 77 questions** (self-scores 0.15–0.45). Nothing has ever
checked whether the number is informative. A threshold on an uncalibrated self-score is a
coin-flip with a parameter: if low-confidence readings are just as often right, the gate is
destroying a fifth of the board for nothing; if they are reliably wrong, the gate is earning its
place and should probably be higher.

METHOD. Interpret each question, then **plan and execute it regardless of the gate**, and compare
the number to its anchor. That is the only way to learn what the gated answers WOULD have been —
the gate discards the Intent before the planner ever sees it, and `Clarification` carries no
intent to recover it from.

IT DOES NOT WRITE THE BOARD. Running the corpus ungated and capturing it would leave the board
describing a configuration nobody runs in production. This writes its own report and touches
nothing else.

    python recognition/calibration.py --bundle <path> [--workers 3] [--limit N]
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import pathlib
import re
import sys
import time

import yaml

#: The gate this exists to judge (mac_runtime.interpret.gate.DEFAULT_LOW_CONFIDENCE_THRESHOLD).
GATE = 0.5

#: Reported bands. Deliberately coarse: with 77 questions, finer bands are noise.
BANDS = ((0.0, 0.3), (0.3, 0.5), (0.5, 0.8), (0.8, 1.01))


def _anchors(bundle: pathlib.Path) -> dict[str, float]:
    out: dict[str, float] = {}
    for f in sorted((bundle / "acceptance" / "anchors").glob("*.yaml")):
        doc = yaml.safe_load(f.read_text()) or {}
        m = re.search(r"\(([A-Za-z0-9_.-]+)\)\s*$", str(doc.get("question", "")))
        v = (doc.get("expected") or {}).get("value")
        if m and isinstance(v, (int, float)) and not isinstance(v, bool):
            out[m.group(1)] = float(v)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--model", default="sonnet")
    a = ap.parse_args(argv)
    bundle = pathlib.Path(a.bundle)

    sys.path.insert(0, str(bundle / "acceptance" / "tools"))
    import duckdb
    from intent_killtest import build
    from mac_runtime.interpret.claude_code import ClaudeCodeInterpreter
    from mac_runtime.interpret.vocabulary import Vocabulary
    from mac_runtime.models import Plan
    from mac_runtime.planner import plan as run_plan

    index, resolver = build()
    vocab = Vocabulary.from_index(index)
    try:
        object.__setattr__(vocab, "_index", index)
    except Exception:  # noqa: BLE001
        pass
    interpreter = ClaudeCodeInterpreter(model=a.model)
    anchors = _anchors(bundle)
    questions = yaml.safe_load((bundle / "acceptance/questions.yaml").read_text())[: a.limit or None]

    print(f"{len(questions)} questions, {len(anchors)} with an anchor, {a.workers} at a time\n",
          flush=True)
    con = duckdb.connect(str(bundle / "contoso.duckdb"), read_only=True)
    lock = __import__("threading").Lock()
    rows: list[dict] = []
    t0 = time.time()

    def one(q):
        qid, text = q["id"], q["question"]
        row = {"id": qid, "question": text, "anchor": anchors.get(qid)}
        try:
            intent = interpreter.interpret(text, capabilities=vocab)
        except Exception as exc:  # noqa: BLE001
            row["error"] = f"{type(exc).__name__}: {str(exc)[:70]}"
            return row
        row["confidence"] = float(intent.confidence)
        row["subject"] = intent.subject
        try:
            p = run_plan(intent, index, resolver)
        except Exception as exc:  # noqa: BLE001
            row["outcome"] = f"plan raised {type(exc).__name__}"
            return row
        if not isinstance(p, Plan):
            row["outcome"] = type(p).__name__.lower()
            return row
        sql = re.sub(r":([A-Za-z_]\w*)", r"$\1", p.sql_preview)
        try:
            with lock:
                res = con.execute(sql, dict(p.params or {})).fetchall()
        except Exception as exc:  # noqa: BLE001
            row["outcome"] = f"execute failed: {str(exc)[:50]}"
            return row
        row["outcome"] = "executed"
        for cell in (res[0] if res else []):
            if isinstance(cell, bool):
                continue
            try:
                row["value"] = float(cell)
                break
            except (TypeError, ValueError):
                continue
        return row

    with cf.ThreadPoolExecutor(max_workers=a.workers) as pool:
        for n, fut in enumerate(cf.as_completed([pool.submit(one, q) for q in questions]), 1):
            rows.append(fut.result())
            if n % 10 == 0:
                print(f"  {n}/{len(questions)}  ({time.time() - t0:.0f}s)", flush=True)

    # ---- grade against the anchors -------------------------------------------------------
    for r in rows:
        if r.get("anchor") is not None and r.get("value") is not None:
            r["correct"] = abs(r["value"] - r["anchor"]) < 1e-6
    graded = [r for r in rows if "correct" in r]
    got_conf = [r for r in rows if r.get("confidence") is not None]

    print(f"\n{'=' * 78}\nCALIBRATION — is `Intent.confidence` informative?\n{'=' * 78}")
    print(f"  interpreted {len(got_conf)} of {len(rows)} · "
          f"{len(graded)} gradeable against an anchor\n")
    print(f"  {'confidence':<14}{'n':>4}{'planned':>9}{'graded':>8}{'correct':>9}   gate")
    for lo, hi in BANDS:
        band = [r for r in got_conf if lo <= r["confidence"] < hi]
        if not band:
            continue
        g = [r for r in band if "correct" in r]
        ok = sum(1 for r in g if r["correct"])
        planned = sum(1 for r in band if r.get("outcome") == "executed")
        acc = f"{ok}/{len(g)}" if g else "—"
        print(f"  {lo:.2f}–{hi:.2f}    {len(band):>4}{planned:>9}{len(g):>8}{acc:>9}"
              f"   {'BLOCKED' if hi <= GATE else 'allowed'}")

    blocked = [r for r in got_conf if r["confidence"] < GATE]
    bg = [r for r in blocked if "correct" in r]
    print(f"\n  THE GATE'S VERDICT (threshold {GATE}):")
    print(f"    {len(blocked)} of {len(got_conf)} readings were BLOCKED in production")
    if bg:
        ok = sum(1 for r in bg if r["correct"])
        print(f"    of the {len(bg)} of those with an anchor, {ok} would have been RIGHT")
    allowed = [r for r in got_conf if r["confidence"] >= GATE and "correct" in r]
    if allowed:
        ok = sum(1 for r in allowed if r["correct"])
        print(f"    of the {len(allowed)} ALLOWED with an anchor, {ok} were right")

    out = pathlib.Path(__file__).resolve().parent / "calibration_last.json"
    out.write_text(json.dumps({"gate": GATE, "rows": rows}, indent=2, default=repr))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
