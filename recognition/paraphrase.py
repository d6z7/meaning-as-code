"""C2 STABILITY — does the same question, asked differently, reach the same Intent?

CATEGORY **RECOGNITION** (TESTING.md §2). PIPELINE_TESTING.md §3.1 and §8.1.

  SUBJECT  the question
  CLAIM    k phrasings of one question produce equivalent Intents
  ORACLE   **none** — this is self-consistency, so it needs no gold intent, no anchor and no
           human ruling. That is what makes it the cheapest instrument in the estate.

WHY IT MATTERS HERE, CONCRETELY. STORE-01 ("still open", 58) and STORE-02 ("not closed", 59) were
found by hand to be two phrasings a reader hears as one question and the bundle answers with two
numbers. This finds that class automatically.

THE VARIANTS ARE GENERATED ONCE AND COMMITTED. A paraphrase set regenerated on every run is not a
benchmark — the measurement would move for reasons nobody could attribute. `--generate` writes
them; `--measure` replays them. Regenerating is a deliberate act that changes the denominator.

WHAT A DISAGREEMENT MEANS. That the interpreter read two phrasings differently — NOT that either
reading is wrong. Which is right is a TRUTH question and needs an anchor; several corpus questions
are genuinely ambiguous (SST-Q3), and for those a disagreement is the instrument working.

    python recognition/paraphrase.py --generate --bundle <path> [--k 2] [--limit N]
    python recognition/paraphrase.py --measure  --bundle <path> [--workers 6] [--limit N]
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import pathlib
import subprocess
import sys
import time
from typing import Any

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from intent_algebra import FIELDS, agreement, canon  # noqa: E402

VARIANTS_FILE = "acceptance/paraphrases.yaml"

_GEN_SCHEMA = {
    "type": "object",
    "properties": {
        "paraphrases": {"type": "array", "items": {"type": "string"}, "minItems": 1}
    },
    "required": ["paraphrases"],
    "additionalProperties": False,
}

_GEN_PROMPT = (
    "Rephrase this analytics question {k} different ways. Keep the MEANING identical — the same "
    "measure, the same filters, the same period, the same grain. Vary only the wording: synonyms, "
    "word order, active/passive, a more or less formal register. Do not add or remove any "
    "condition, and do not make it more specific or more general.\n\nQuestion: {q}"
)


def _claude(argv: list[str], timeout: int = 240) -> dict[str, Any]:
    proc = subprocess.run(
        argv, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {(proc.stderr or '')[:200]}")
    return json.loads(proc.stdout)


# --------------------------------------------------------------------------- generate


def generate(bundle: pathlib.Path, k: int, limit: int | None, model: str) -> int:
    questions = yaml.safe_load((bundle / "acceptance/questions.yaml").read_text())
    rows = [q for q in questions][: limit or None]
    out_path = bundle / VARIANTS_FILE
    existing = yaml.safe_load(out_path.read_text()) if out_path.exists() else {}
    existing = existing or {}

    todo = [q for q in rows if q["id"] not in existing]
    print(f"generating {k} variants for {len(todo)} question(s) "
          f"({len(rows) - len(todo)} already have them)")

    def one(q):
        env = _claude([
            "claude", "-p", _GEN_PROMPT.format(k=k, q=q["question"]),
            "--output-format", "json", "--json-schema", json.dumps(_GEN_SCHEMA),
            "--model", model,
        ])
        got = (env.get("structured_output") or {}).get("paraphrases") or []
        return q["id"], q["question"], [str(x) for x in got][:k]

    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        for fut in cf.as_completed([pool.submit(one, q) for q in todo]):
            try:
                qid, question, variants = fut.result()
            except Exception as exc:  # noqa: BLE001
                print(f"  generate failed: {exc}")
                continue
            existing[qid] = {"question": question, "variants": variants}
            print(f"  {qid:<10} {len(variants)} variant(s)", flush=True)

    out_path.write_text(yaml.safe_dump(existing, sort_keys=True, width=100, allow_unicode=True))
    print(f"\nwrote {out_path} — {len(existing)} question(s)")
    return 0


# --------------------------------------------------------------------------- measure


def measure(bundle: pathlib.Path, workers: int, limit: int | None, model: str) -> int:
    variants_path = bundle / VARIANTS_FILE
    if not variants_path.exists():
        raise SystemExit(f"no {VARIANTS_FILE} — run --generate first")
    sets = yaml.safe_load(variants_path.read_text()) or {}
    ids = sorted(sets)[: limit or None]

    # The interpreter, loaded once. The bundle's own vocabulary is what the prompt is built from.
    sys.path.insert(0, str(bundle / "acceptance/tools"))
    from intent_killtest import build  # noqa: E402
    from mac_runtime.interpret.claude_code import ClaudeCodeInterpreter  # noqa: E402
    from mac_runtime.interpret.vocabulary import Vocabulary  # noqa: E402

    index, resolver_for_plan = build()
    vocab = Vocabulary.from_index(index)
    try:
        object.__setattr__(vocab, "_index", index)
    except Exception:  # noqa: BLE001 - the prompt falls back to the vocabulary alone
        pass
    interpreter = ClaudeCodeInterpreter(model=model)

    jobs: list[tuple[str, int, str]] = []
    for qid in ids:
        entry = sets[qid]
        for i, phrasing in enumerate([entry["question"], *entry.get("variants", [])]):
            jobs.append((qid, i, phrasing))

    print(f"interpreting {len(jobs)} phrasing(s) of {len(ids)} question(s), "
          f"{workers} at a time\n", flush=True)
    results: dict[str, dict[int, Any]] = {}
    failures: dict[str, str] = {}
    t0 = time.time()

    def one(job):
        qid, i, phrasing = job
        return qid, i, interpreter.interpret(phrasing, capabilities=vocab)

    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(one, j) for j in jobs]
        for n, fut in enumerate(cf.as_completed(futs), 1):
            try:
                qid, i, intent = fut.result()
                results.setdefault(qid, {})[i] = intent
            except Exception as exc:  # noqa: BLE001
                failures[f"job{n}"] = f"{type(exc).__name__}: {str(exc)[:90]}"
            if n % 5 == 0:
                print(f"  {n}/{len(jobs)}  ({time.time() - t0:.0f}s)", flush=True)

    # ---- does resolution ABSORB the disagreement? -------------------------------------
    # AN UNSTABLE INTENT IS NOT AUTOMATICALLY A DEFECT, and the pilot proved it: two phrasings of
    # "how many customers are in Germany" gave `Country eq 'DE'` and `Country eq 'Germany'`, and
    # two of "how many stores are closed" gave the term as `Status` and `StoreStatus`. All four
    # plan to the same SQL and the same number — the register resolves the spelling, which is
    # precisely what a register is for. Reporting those as instability would indict the
    # interpreter for something the architecture handles.
    #
    # So there are TWO rates, and both are honest:
    #   intent-equivalent     the strict measure — did it read the question the same way
    #   answer-equivalent     what a user experiences — did it come back with the same number
    def _answer_of(intent):
        from mac_runtime.models import Plan
        from mac_runtime.planner import plan as run_plan
        try:
            p_ = run_plan(intent, index, resolver_for_plan)
        except Exception:  # noqa: BLE001
            return ("plan-raised",)
        if not isinstance(p_, Plan):
            return (type(p_).__name__,)
        return ("sql", " ".join(p_.sql_preview.split()), tuple(sorted((p_.params or {}).items())))


    # ---- report ----
    stable, unstable, incomplete = [], [], []
    field_counts: dict[str, int] = {}
    for qid in ids:
        got = results.get(qid, {})
        if len(got) < 2:
            incomplete.append(qid)
            continue
        ordered = [got[i] for i in sorted(got)]
        ok, counts = agreement(ordered)
        (stable if ok else unstable).append(qid)
        for f, c in counts.items():
            field_counts[f] = field_counts.get(f, 0) + c

    absorbed, consequential = [], []
    for qid in unstable:
        answers = {_answer_of(results[qid][i]) for i in sorted(results[qid])}
        (absorbed if len(answers) == 1 else consequential).append(qid)

    graded = len(stable) + len(unstable)
    rate = 100.0 * len(stable) / graded if graded else 0.0
    answer_stable = len(stable) + len(absorbed)
    arate = 100.0 * answer_stable / graded if graded else 0.0
    print(f"\n{'=' * 78}\nC2 STABILITY — {graded} questions graded\n{'=' * 78}")
    print(f"  INTENT-equivalent   {len(stable):>4} of {graded}  ({rate:.1f} %)   read the same way")
    print(f"  + absorbed by a register {len(absorbed):>+3}          "
          f"differently named, same plan")
    print(f"  ANSWER-equivalent   {answer_stable:>4} of {graded}  ({arate:.1f} %)   same number")
    print(f"  CONSEQUENTIAL       {len(consequential):>4}          a different answer")
    if incomplete:
        print(f"  ungraded (fewer than 2 phrasings interpreted): {len(incomplete)}")
    if failures:
        print(f"  interpretation failures: {len(failures)}")
        for k2, v in list(failures.items())[:4]:
            print(f"     {v}")
    if field_counts:
        print("\n  WHERE THEY DISAGREE — the field, not just the rate:")
        for f in FIELDS:
            if field_counts.get(f):
                print(f"    {f:<16}{field_counts[f]:>5}")
    if consequential:
        print(f"\n  CONSEQUENTIAL — these change the ANSWER ({len(consequential)}):")
        for qid in consequential[:10]:
            print(f"    {qid}: {sets[qid]['question'][:66]}")
    if unstable:
        print(f"\n  ALL UNSTABLE INTENTS ({len(unstable)}; "
              f"{len(absorbed)} absorbed by resolution):")
        for qid in unstable[:12]:
            ordered = [results[qid][i] for i in sorted(results[qid])]
            print(f"    {qid}: {sets[qid]['question'][:66]}")
            for i, intent in zip(sorted(results[qid]), ordered):
                c = canon(intent)
                print(f"       [{i}] subject={c['subject']} op={c['operation']} "
                      f"filters={c['filters']} period={c['period']}")

    out = bundle.parent / "meaning-as-code" / "recognition" / "stability_last.json"
    out.write_text(json.dumps(
        {
            "graded": graded, "stable": len(stable), "rate": round(rate, 2),
            "unstable": unstable, "absorbed": absorbed, "consequential": consequential,
            "answer_rate": round(arate, 2), "incomplete": incomplete,
            "field_counts": field_counts, "failures": failures,
            "canon": {q: {str(i): canon(v) for i, v in got.items()}
                      for q, got in results.items()},
        }, indent=2, default=repr))
    print(f"\nwrote {out}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--generate", action="store_true")
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--model", default="haiku")
    a = ap.parse_args(argv)
    bundle = pathlib.Path(a.bundle)
    if a.generate:
        return generate(bundle, a.k, a.limit, a.model)
    if a.measure:
        return measure(bundle, a.workers, a.limit, a.model)
    ap.error("pass --generate or --measure")


if __name__ == "__main__":
    sys.exit(main())
