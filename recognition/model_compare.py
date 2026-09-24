"""Do two models read the same question the same way?

CATEGORY **RECOGNITION** (TESTING.md §2). The operator's question: *"compare opus vs sonnet — if
they will produce different answers."*

  SUBJECT  the question
  CLAIM    the reading is a property of the QUESTION and the ONTOLOGY, not of the model
  ORACLE   none for agreement (self-consistency across models) · the ANCHORS where they disagree

WHY IT IS NOT THE SAME AS PARAPHRASE STABILITY. That varies the WORDING and holds the model fixed;
this varies the MODEL and holds the wording fixed. They fail for different reasons and a system can
pass either while failing the other.

WHY IT MATTERS MORE THAN IT LOOKS. The whole design says everything after the Intent is
deterministic — so if two models produce equivalent Intents, the engine's answer is a property of
the ontology and swapping models is safe. Every disagreement is a place where the answer depends on
which model was configured, which is the thing a semantic layer is supposed to remove.

THE SAME THREE TIERS AS THE PARAPHRASE HARNESS, and for the same reason: an intent-level
disagreement that the REGISTER resolves away is not a defect. Only a different ANSWER is.

    python recognition/model_compare.py --bundle <path> --a opus --b sonnet [--limit N]
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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from intent_algebra import FIELDS, canon, diff  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--a", default="opus")
    ap.add_argument("--b", default="sonnet")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int)
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
    interp = {m: ClaudeCodeInterpreter(model=m) for m in (a.a, a.b)}
    con = duckdb.connect(str(bundle / "contoso.duckdb"), read_only=True)
    lock = __import__("threading").Lock()
    questions = yaml.safe_load((bundle / "acceptance/questions.yaml").read_text())[: a.limit or None]

    def answer_of(intent):
        """What the engine would SAY — the tier that decides whether a difference matters."""
        try:
            p = run_plan(intent, index, resolver)
        except Exception as exc:  # noqa: BLE001
            return f"plan-raised:{type(exc).__name__}"
        if not isinstance(p, Plan):
            return f"refused:{type(p).__name__.lower()}"
        sql = re.sub(r":([A-Za-z_]\w*)", r"$\1", p.sql_preview)
        try:
            with lock:
                rows = con.execute(sql, dict(p.params or {})).fetchall()
        except Exception:  # noqa: BLE001
            return "execute-failed"
        for cell in (rows[0] if rows else []):
            if isinstance(cell, bool):
                continue
            try:
                return f"value:{float(cell):.4f}"
            except (TypeError, ValueError):
                continue
        return f"rows:{len(rows)}"

    def one(q):
        row = {"id": q["id"], "question": q["question"]}
        for m in (a.a, a.b):
            try:
                it = interp[m].interpret(q["question"], capabilities=vocab)
                row[m] = {"intent": canon(it), "confidence": float(it.confidence),
                          "answer": answer_of(it)}
            except Exception as exc:  # noqa: BLE001
                row[m] = {"error": f"{type(exc).__name__}: {str(exc)[:60]}"}
        return row

    print(f"{len(questions)} questions x 2 models ({a.a} vs {a.b}), {a.workers} at a time\n",
          flush=True)
    rows, t0 = [], time.time()
    with cf.ThreadPoolExecutor(max_workers=a.workers) as pool:
        for n, fut in enumerate(cf.as_completed([pool.submit(one, q) for q in questions]), 1):
            rows.append(fut.result())
            if n % 5 == 0:
                print(f"  {n}/{len(questions)}  ({time.time() - t0:.0f}s)", flush=True)

    same_intent, absorbed, consequential, errored = [], [], [], []
    field_counts: dict[str, int] = {}
    for r in rows:
        ra, rb = r.get(a.a) or {}, r.get(a.b) or {}
        if "error" in ra or "error" in rb:
            errored.append(r["id"])
            continue
        if ra["intent"] == rb["intent"]:
            same_intent.append(r["id"])
            continue
        for f in FIELDS:
            if ra["intent"].get(f) != rb["intent"].get(f):
                field_counts[f] = field_counts.get(f, 0) + 1
        (absorbed if ra["answer"] == rb["answer"] else consequential).append(r["id"])

    graded = len(same_intent) + len(absorbed) + len(consequential)
    pct = lambda n: 100.0 * n / graded if graded else 0.0
    print(f"\n{'=' * 78}\nMODEL COMPARISON — {a.a} vs {a.b}, {graded} questions\n{'=' * 78}")
    print(f"  SAME INTENT        {len(same_intent):>4}  {pct(len(same_intent)):>5.1f} %")
    print(f"  + absorbed         {len(absorbed):>4}  {pct(len(absorbed)):>5.1f} %   different intent, same answer")
    print(f"  {'':<18}{'':>4}  {'':>5}     -----------------------------------")
    print(f"  SAME ANSWER        {len(same_intent) + len(absorbed):>4}  "
          f"{pct(len(same_intent) + len(absorbed)):>5.1f} %   <- the one that matters")
    print(f"  CONSEQUENTIAL      {len(consequential):>4}  {pct(len(consequential)):>5.1f} %   "
          f"the model changed the answer")
    if errored:
        print(f"  errored            {len(errored):>4}")
    if field_counts:
        print("\n  WHERE THE READINGS DIVERGE:")
        for f in FIELDS:
            if field_counts.get(f):
                print(f"    {f:<16}{field_counts[f]:>4}")
    if consequential:
        print(f"\n  THE ANSWER DEPENDS ON WHICH MODEL IS CONFIGURED ({len(consequential)}):")
        for qid in consequential[:12]:
            r = next(x for x in rows if x["id"] == qid)
            print(f"    {qid}: {r['question'][:60]}")
            print(f"       {a.a:<8} {r[a.a]['answer']:<24} {r[a.a]['intent']['subject']}/"
                  f"{r[a.a]['intent']['operation']}")
            print(f"       {a.b:<8} {r[a.b]['answer']:<24} {r[a.b]['intent']['subject']}/"
                  f"{r[a.b]['intent']['operation']}")

    out = pathlib.Path(__file__).resolve().parent / f"model_compare_{a.a}_vs_{a.b}.json"
    out.write_text(json.dumps({"a": a.a, "b": a.b, "rows": rows}, indent=2, default=repr))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
