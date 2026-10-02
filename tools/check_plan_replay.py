#!/usr/bin/env python3
"""check_plan_replay.py — REPLAY every captured intent through the planner, offline, and report what
the current ontology can no longer plan.

WHY THIS EXISTS. On 2026-10-01 the `Sale` concept was deleted. `mac_compile` reported COMPILES with
zero errors, twenty-five gates passed, and two corpus questions silently stopped being answerable:
"how many distinct products were sold in 2023" and its France/Q1 sibling both fell from PROVEN to
FAILED. The only thing that caught it was re-running 76 questions against a live model, which took
fifty-three minutes and cost 76 invocations. By then the change was four edits old.

THE INSIGHT THAT MAKES IT CHEAP. Each `acceptance/answers/<id>.yaml` already records the INTENT the
interpreter produced — subject, operation, slices, filters, period. An intent is the expensive half.
Replaying it through `plan()` needs no model, no warehouse and no network: it is the deterministic
half of the pipeline, and it is where a deleted concept or a dropped edge shows up. So this gate asks
the one question a compile cannot: of everything this bundle could plan last time, what can it still
plan now?

WHAT IT IS NOT. It does not judge answers, values or oracles — `check_answers.py` owns that. A plan is
not a result. This gate reports only the transition PLANNED -> REFUSED, which is a capability the
bundle used to have and does not.

RESOLVER-DEPENDENT REFUSALS ARE NOT JUDGED. Replaying offline means no register is loaded, so a filter
naming a value ("Germany") cannot resolve and the planner refuses for a reason that says nothing about
the ontology. Those are counted and reported separately, never as regressions. The signal lives in
the intents whose plan is purely structural.

Usage:  python3 tools/check_plan_replay.py <bundle-root>
        exit 0 = nothing that planned before refuses now
             1 = at least one capability was lost
             2 = the bundle or the sibling runtime cannot be read
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import yaml

HERE = pathlib.Path(__file__).resolve().parent

sys.path.insert(0, str(HERE))
import _neighbours  # noqa: E402  — ONE home for the sibling runtime's location

#: Refusal reasons that depend on a LOADED RESOLVER, not on the ontology. Replaying offline cannot
#: resolve a name to a code, so these say nothing about a lost capability.
_RESOLVER_REASONS = {"unresolved_term", "no_evidence_name", "ambiguous_value"}


class _NullResolver:
    """The fallback when the bundle's registers cannot be loaded. Every lookup declines, and the gate
    discounts the refusals that causes rather than pretending they are findings."""

    def __getattr__(self, _name):
        return lambda *a, **k: None


def _resolver_for(root, index):
    """A REAL resolver, built from the bundle's own register files — no warehouse, no network.

    The first cut used a null resolver and discounted 39 of 74 intents as unjudgeable, which is more
    than half the corpus unexamined. The registers are CSV in `data/lookups/`, so `load_registers`
    reads them from disk: a question filtering "Germany" resolves exactly as it does live, and the
    gate judges the plan rather than shrugging at it. Returns (resolver, how_many_registers)."""
    from mac_runtime.resolver.enumeration import EnumerationResolver
    from mac_runtime.resolver.lookup import LookupResolver
    from mac_runtime.resolver.register_match import RegisterResolver
    from mac_runtime.resolver.registers import load_registers

    # THE SAME THREE LAYERS THE LIVE PIPELINE BUILDS (`mac_runtime/pipeline.py`), in the same order.
    # Mirrored rather than invented: a replay resolving differently from the real one would report
    # findings about itself. The first cut used `RegisterResolver(load)` alone and resolved NOTHING —
    # contoso5 declares no register through the canon, so the concept routing is empty and every name
    # fell through to an absent `inner`. The 427 values live in `entries`, which is what
    # `LookupResolver` reads.
    load = load_registers(root, index)
    resolver = RegisterResolver(
        load,
        inner=EnumerationResolver(index, inner=LookupResolver(index, load.entries)),
    )
    return resolver, len(getattr(load, "entries", ()) or ())


def _recorded(answers_dir: pathlib.Path) -> list[tuple[str, dict, str]]:
    """(question_id, intent_dict, recorded_route) for every capture that recorded an intent."""
    out = []
    for path in sorted(answers_dir.glob("*.yaml")):
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        intent = None
        for stage in doc.get("stages") or []:
            if (stage or {}).get("stage") == "interpret":
                intent = ((stage or {}).get("detail") or {}).get("intent")
        if isinstance(intent, dict) and intent.get("subject"):
            out.append((str(doc.get("id") or path.stem), intent, str(doc.get("route") or "")))
    return out


def replay(root: pathlib.Path):
    _neighbours.ensure_runtime_on_path()
    from mac_runtime.models import Intent
    from mac_runtime.ontology.index import OntologyIndex
    from mac_runtime.planner.plan import plan

    # `from_directory`, NOT the bare constructor. It builds the edge Graph and parses the declaration
    # planes; handing the constructor the parser's raw edge dict yields an index whose `edges` is a
    # dict, and the planner dies on `find_join_path` the moment a question needs a join. MEASURED
    # 2026-10-01: the bare constructor turned 25 of 74 replays into AttributeError rather than a
    # verdict, and every probe written against it could only ever exercise join-free questions.
    index = OntologyIndex.from_directory(root)
    resolver, n_registers = _resolver_for(root, index)

    planned, refused, discounted, unreadable = [], [], [], []
    for qid, raw, route in _recorded(root / "acceptance" / "answers"):
        try:
            intent = Intent(**{k: v for k, v in raw.items() if v is not None})
        except Exception as exc:
            unreadable.append((qid, f"{type(exc).__name__}: {exc}"))
            continue
        try:
            out = plan(intent, index, resolver)
        except Exception as exc:
            unreadable.append((qid, f"plan raised {type(exc).__name__}: {exc}"))
            continue
        kind = type(out).__name__
        if kind == "Plan":
            planned.append(qid)
        else:
            reason = str(getattr(out, "reason_code", "") or "")
            reason = reason.rsplit(".", 1)[-1].lower()
            why = " ".join(str(getattr(out, "human_reason", "") or "").split())
            (discounted if reason in _RESOLVER_REASONS else refused).append((qid, reason, why))
    return planned, refused, discounted, unreadable, n_registers


#: WHERE THE FLOOR LIVES. A decision to carry a state, beside the corpus it is about.
BASELINE_REL = pathlib.Path("acceptance") / "plan_baseline.json"


def _load_baseline(root: pathlib.Path) -> dict:
    path = root / BASELINE_REL
    if not path.is_file():
        return {}
    import json

    try:
        return (json.loads(path.read_text(encoding="utf-8")) or {}).get("plans") or {}
    except Exception:
        return {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root")
    ap.add_argument("--all", action="store_true", help="also list what still plans")
    ap.add_argument("--approve", action="store_true",
                    help="record what plans TODAY as the floor; thereafter only a LOSS exits 1")
    a = ap.parse_args(argv)
    root = pathlib.Path(a.root).resolve()
    if not (root / "acceptance" / "answers").is_dir():
        print(f"could not run: no acceptance/answers under {root}")
        return 2
    try:
        _neighbours.ensure_runtime_on_path()
    except _neighbours.RuntimeMissing as exc:
        print(f"could not run: {exc}")
        return 2

    planned, refused, discounted, unreadable, n_registers = replay(root)
    total = len(planned) + len(refused) + len(discounted) + len(unreadable)
    print(f"── plan replay ── {total} captured intent(s), {n_registers} register(s) loaded ──\n")
    print(f"  plans now            : {len(planned)}")
    print(f"  REFUSES structurally : {len(refused)}")
    print(f"  discounted (resolver): {len(discounted)}")
    print(f"  unreadable           : {len(unreadable)}\n")
    for qid, reason, why in refused:
        print(f"  [ERROR] {qid}: {reason or 'refused'} — {why[:150]}")
    for qid, reason, why in discounted:
        print(f"  [skip ] {qid}: {reason} — needs a loaded register, not judged")
    for qid, why in unreadable:
        print(f"  [warn ] {qid}: {why[:120]}")
    if a.all:
        print("\n  still plans: " + ", ".join(planned))
    print()
    # ONLY NEWS EXITS 1 — the estate's standing discipline for a carried red. Without a baseline every
    # structural refusal is news, which is the right default for a bundle that has never approved one.
    # With a baseline, a refusal that was already there is carried and a LOSS is what fails: a question
    # that planned when the floor was set and refuses now. MEASURED 2026-10-01: deleting one concept
    # cost RC11 and RC15 their plans, `mac_compile` stayed green, twenty-four gates passed, and the loss
    # surfaced fifty-three minutes into a live corpus run. This is the guard for exactly that.
    import json

    baseline = _load_baseline(root)
    now = {q: "plans" for q in planned}
    now.update({q: "refuses" for q, _r, _w in refused})

    if a.approve:
        (root / BASELINE_REL).write_text(
            json.dumps({"recorded": __import__("datetime").date.today().isoformat(),
                        "plans": now}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        p_n = sum(1 for v in now.values() if v == "plans")
        print(f"floor recorded: {p_n} planning, {len(now) - p_n} refusing -> {BASELINE_REL}")
        return 0

    if not baseline:
        if refused:
            print(f"✗ {len(refused)} captured intent(s) refuse and no floor is recorded — approve one "
                  f"with --approve, or fix them")
            return 1
        print(f"✓ OK — all {len(planned)} structurally-plannable intent(s) plan; no floor recorded")
        return 0

    lost = sorted(q for q, was in baseline.items() if was == "plans" and now.get(q) == "refuses")
    gained = sorted(q for q, state in now.items() if state == "plans" and baseline.get(q) == "refuses")
    absent = sorted(q for q in baseline if q not in now)
    for q in gained:
        print(f"  [gain ] {q}: refused at the floor, plans now — re-approve to make it the new floor")
    for q in absent:
        print(f"  [stale] {q}: in the floor and no longer captured")
    if lost:
        for q in lost:
            print(f"  [LOST ] {q}: planned at the floor and refuses now")
        print(f"\n✗ {len(lost)} capability(ies) lost against the floor in {BASELINE_REL}")
        return 1
    print(f"✓ OK — nothing that planned at the floor refuses now ({len(gained)} gained, "
          f"{len(baseline)} in the floor)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
