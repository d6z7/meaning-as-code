#!/usr/bin/env python3
"""check_rule_consulted.py — a declaration that was IN PLAY and was never asked.

WHY THIS EXISTS. `check_plan_replay` reports capability LOST and cannot see a plan that still
succeeds and answers differently. `check_canon_implemented` reports a canon nothing can call.
`check_declarations_read` reports a declaration nothing in the runtime spells. None of the three can
see the defect this gate is built for: a rule that is written, bound, hooked, reachable, and simply
NOT CONSULTED on a question it governs — because the planner looked for it in the wrong place.

THE CASE THAT PRODUCED IT, measured 2026-10-06. `country.default.a_sales_question_means_the_store_
country` is bound to `mac.canon.path_select`, whose reader is imported by `planner/joins.py` and
fires on 13 of the 15 questions where Country is in play. On the other two it is never asked, because
`_ruled_path` interrogates the join's TARGET and both questions make Country the ANCHOR — ADV-09
("Countries where average order value exceeds 500") puts its measure in a `having` clause, and RC02
("List all countries where we have customers") is a bare list. ADV-09 answers against the ruling.
**RC02 answers WITH the ruling by coincidence** — unweighted BFS broke the tie on a line number that
happens to favour the customer, which is what the question meant. A right answer for no reason is the
more dangerous of the two, and no other instrument in the estate can tell it from a ruled one.

HOW IT KNOWS — and it is the reason the disclosure had to be built first. The oracle is NOT
`Plan.rules_used`: measured over the frozen corpus, that field is empty on 80 of 80 questions and
would mark every rule unconsulted, working ones included. The oracle is the DISCLOSURE. A selector
that fires names its own rule in the sentence it owes the reader ("...declared by <rule id>"), so a
rule that cites itself on one question has PROVED it can be observed, and silence on another question
it governs is a finding rather than an unknown.

SO THE GATE CALIBRATES ITSELF, which is what keeps it free of the false findings that make a gate
skimmable. A rule that never names itself anywhere is NOT OBSERVABLE — unbound, or bound to a canon
with no hook, or bound to one that owes no disclosure — and is excluded from the verdict and reported
with its reason. Only a rule that demonstrably discloses is held to disclosing everywhere.

IN PLAY means both of two things, and the conjunction is what makes it precise: the rule's subject
concept appears in the question's `concepts`, AND at least one column the rule `binds` appears in the
question's SQL. One alone is not enough — a concept can be touched without its ruled column being
read, and a column name can appear for another concept's reasons.

    python3 tools/check_rule_consulted.py <bundle>
    python3 tools/check_rule_consulted.py <bundle> --json
    python3 tools/check_rule_consulted.py --self-test

Contract: one PASS:/FAIL: line, exit 0 or 1, exit 2 when it could not run, denominators printed, and
`--self-test` with one mutant per class.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mac_project as P  # noqa: E402  — ONE home for where a bundle keeps its concepts

#: The frozen per-question behaviour `check_rule_baseline` writes. This gate READS that freeze rather
#: than planning anything itself: the freeze is already the estate's record of what each question did,
#: and re-planning here would be a second answer to a question one tool already owns.
BASELINE = "acceptance/rule_baseline.json"

#: THE RATCHET. Every entry is a declaration the planner failed to consult on a question it governs.
#: It may only go DOWN. Raising it means a rule stopped being asked, which is a wrong answer waiting
#: for the question that exposes it.
FLOOR = 0

#: THE CANONS WHOSE SILENCE PROVES NON-CONSULTATION, and the list is short on purpose.
#:
#: `path_select` decides WHICH EDGE, and a ruled path and a searched path are THE SAME TYPE — both are
#: `ontology.graph.JoinPath`, both land in `edges_used`, and the edge BFS picks is itself one of the
#: declared readings. So the artifact carries no evidence of which one decided, and the disclosure is
#: the only trace there is: no caveat means the ruling was not asked. That is exactly how ADV-09 and
#: RC02 were found, and why RC02 is the more dangerous of the two — it answers through the customer,
#: which is what the question meant, by an unweighted tie-break on a line number in edges.yaml.
#:
#: EVERY OTHER FAMILY LEAVES A SECOND TRACE, so silence there does NOT prove non-consultation and is
#: not reported as one. MEASURED 2026-10-06 on the frozen corpus: RC08 ("how many stores are closed?")
#: renders `close_date IS NOT NULL` and STORE-03 ("restructured") renders `status_annotation =
#: :pop_store_status_annotation`. Both populations WERE applied — by name, through filter resolution —
#: and neither disclosed, because a reading the question itself named is not a choice the engine made.
#: An early cut of this gate counted those 8 as findings and was 8/10 wrong; the operator's rule is to
#: expose granularity the ENGINE chose, not to narrate the question back.
STRICT_CANONS = ("path_select",)


def rules_of(root: pathlib.Path) -> list[dict]:
    """Every contract rule in the bundle as `{id, subject, binds, bound}`."""
    out: list[dict] = []
    cdir = P.concepts_dir(root)
    for f in sorted(cdir.glob("*.yaml")):
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        concept = (doc.get("concept") or {}).get("name") or f.stem
        for rule in ((doc.get("contract") or {}).get("rules") or []):
            if not isinstance(rule, dict) or not rule.get("id"):
                continue
            raw = rule.get("realized_by") or ()
            items = [raw] if isinstance(raw, dict) else list(raw)
            canons = [str((b or {}).get("udf") or "").rsplit(".", 1)[-1]
                      for b in items if isinstance(b, dict)]
            out.append({
                "id": str(rule["id"]),
                "subject": str(rule.get("subject") or concept),
                "binds": [str(b) for b in (rule.get("binds") or [])],
                "bound": bool(rule.get("realized_by")),
                "canons": [c for c in canons if c],
                "file": f.name,
            })
    return out


def _in_play(rule: dict, record: dict) -> bool:
    """The rule GOVERNS this question: its subject was touched and a column it binds was read."""
    if rule["subject"] not in (record.get("concepts") or []):
        return False
    sql = record.get("sql") or ""
    return any(col and col in sql for col in rule["binds"])


def _names_itself(rule_id: str, record: dict) -> bool:
    return any(rule_id in str(c) for c in (record.get("caveats") or []))


def audit(root: pathlib.Path) -> dict:
    behaviour = json.loads((root / BASELINE).read_text(encoding="utf-8")).get("behaviour") or {}
    rows: list[dict] = []
    for rule in rules_of(root):
        in_play = [q for q, rec in behaviour.items() if _in_play(rule, rec)]
        named = [q for q in in_play if _names_itself(rule["id"], behaviour[q])]
        rows.append({
            **rule,
            "in_play": sorted(in_play),
            "named": sorted(named),
            # OBSERVABLE only once it has disclosed at least once. Without that proof, silence says
            # nothing about consultation — which is why this is a reason and not a finding.
            "observable": bool(named),
            "silent": sorted(set(in_play) - set(named)),
            #: STRICT when the canon leaves no trace but the disclosure — see STRICT_CANONS.
            "strict": any(c in STRICT_CANONS for c in rule["canons"]),
        })
    return {"questions": len(behaviour), "rules": rows}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.bundle).resolve()
    if not (root / BASELINE).is_file():
        print(f"could not run: no {BASELINE} under {root} — run check_rule_baseline --capture first")
        return 2
    if not P.concepts_dir(root).is_dir():
        print(f"could not run: no concept documents under {P.concepts_dir(root)}")
        return 2

    report = audit(root)
    if a.json:
        print(json.dumps(report, indent=1))
        return 0

    rows = report["rules"]
    observable = [r for r in rows if r["observable"]]
    findings = [r for r in observable if r["silent"] and r["strict"]]
    undisclosed = [r for r in observable if r["silent"] and not r["strict"]]
    n_silent = sum(len(r["silent"]) for r in findings)
    n_undisclosed = sum(len(r["silent"]) for r in undisclosed)

    for r in sorted(observable, key=lambda x: x["id"]):
        mark = ("NOT CONSULTED" if r["strict"] else "undisclosed") if r["silent"] else "ok"
        print(f"  {mark:>13}  {r['id'][:58]:<58} in play {len(r['in_play']):>2} · "
              f"disclosed {len(r['named']):>2}" + (f" · silent on {', '.join(r['silent'])}" if r["silent"] else ""))
    if undisclosed:
        # NOT a finding. The reading was applied by name through filter resolution, which leaves its
        # own trace in the SQL; a reading the question itself named is not a choice the engine made.
        print(f"\n  undisclosed but applied ({n_undisclosed} question(s)): the question NAMED the "
              f"reading, so nothing was chosen to expose. Not counted — see STRICT_CANONS.")
    unobservable = [r for r in rows if not r["observable"]]
    if unobservable:
        # NOT a pass and NOT a finding: a rule that has never disclosed cannot be held to disclosing.
        # The reason matters, so it is printed rather than counted.
        print(f"\n  not observable — never disclosed on any question, so consultation cannot be "
              f"measured ({len(unobservable)} of {len(rows)}):")
        for r in sorted(unobservable, key=lambda x: x["id"]):
            why = "binds no canon" if not r["bound"] else "bound, but owes no disclosure or has no hook"
            print(f"      {r['id'][:58]:<58} in play {len(r['in_play']):>2}  — {why}")

    denom = (f"{len(rows)} rule(s) over {report['questions']} question(s); "
             f"{len(observable)} observable, {len(unobservable)} not, "
             f"{sum(1 for r in rows if r['strict'])} strict")
    print()
    if n_silent > FLOOR:
        print(f"FAIL: check_rule_consulted — {n_silent} question(s) where a rule that GOVERNS them was "
              f"never consulted, over {denom}. The planner looked somewhere this declaration was not; "
              f"an answer that comes out right anyway is right by accident.")
        return 1
    print(f"PASS: check_rule_consulted — every rule whose silence would prove non-consultation was "
          f"consulted on every question it governs, over {denom}")
    return 0


def _self_test() -> int:
    """One mutant per class, on a bundle BUILT for it so the right answer is known before it runs."""
    import tempfile

    bad: list[str] = []

    def expect(ok: bool, name: str) -> None:
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}")
        if not ok:
            bad.append(name)

    def build(tmp: pathlib.Path, behaviour: dict, canon: str = "path_select") -> pathlib.Path:
        """`canon` decides whether silence is a finding — see STRICT_CANONS."""
        root = tmp / "bundle"
        (root / "acceptance").mkdir(parents=True)
        P_dir = root / "ontology" / "concepts"
        P_dir.mkdir(parents=True)
        (root / "mac.project.yaml").write_text("planes:\n  ontology: ontology\n", encoding="utf-8")
        (P_dir / "thing.yaml").write_text(
            "concept:\n  name: Thing\n"
            "contract:\n"
            "  rules:\n"
            "    - id: thing.default.pick_a\n"
            "      subject: Thing\n"
            "      binds: [thing_code]\n"
            "      realized_by:\n"
            f"        - udf: mac.canon.{canon}\n"
            "          params: {default: a}\n",
            encoding="utf-8")
        (root / BASELINE).write_text(json.dumps({"behaviour": behaviour}), encoding="utf-8")
        return root

    RID = "thing.default.pick_a"
    GOVERNED = {"concepts": ["Thing"], "sql": "SELECT thing_code FROM t", "caveats": []}
    with tempfile.TemporaryDirectory() as t:
        # consulted on the one question it governs -> PASS
        b = {"Q1": {**GOVERNED, "caveats": [f"[declared default] Thing read by {RID}."]}}
        expect(main([str(build(pathlib.Path(t), b))]) == 0, "a rule consulted where it governs passes")
    with tempfile.TemporaryDirectory() as t:
        # governs two, discloses on one -> for a STRICT canon the silent one is a FINDING
        b = {"Q1": {**GOVERNED, "caveats": [f"[declared default] Thing read by {RID}."]},
             "Q2": dict(GOVERNED)}
        expect(main([str(build(pathlib.Path(t), b))]) == 1,
               "a STRICT canon silent on a question it governs REJECTS")
    with tempfile.TemporaryDirectory() as t:
        # THE SAME SILENCE, a non-strict canon -> not a finding. This is the 8-of-10 false-positive
        # case: the reading was applied by name and left its own trace in the SQL.
        b = {"Q1": {**GOVERNED, "caveats": [f"[declared default] Thing read by {RID}."]},
             "Q2": dict(GOVERNED)}
        expect(main([str(build(pathlib.Path(t), b, canon="population_select"))]) == 0,
               "the same silence on a NON-strict canon is undisclosed, not a finding")
    with tempfile.TemporaryDirectory() as t:
        # never discloses anywhere -> NOT OBSERVABLE, not a finding
        b = {"Q1": dict(GOVERNED), "Q2": dict(GOVERNED)}
        expect(main([str(build(pathlib.Path(t), b))]) == 0,
               "a rule that never disclosed anywhere is not observable, not a finding")
    with tempfile.TemporaryDirectory() as t:
        # the subject is touched but the bound COLUMN is not read -> not in play, no finding
        b = {"Q1": {**GOVERNED, "caveats": [f"declared by {RID}"]},
             "Q2": {"concepts": ["Thing"], "sql": "SELECT other FROM t", "caveats": []}}
        expect(main([str(build(pathlib.Path(t), b))]) == 0,
               "a concept touched without its bound column is NOT in play")
    with tempfile.TemporaryDirectory() as t:
        # the column is read but the subject concept is absent -> not in play
        b = {"Q1": {**GOVERNED, "caveats": [f"declared by {RID}"]},
             "Q2": {"concepts": ["Other"], "sql": "SELECT thing_code FROM t", "caveats": []}}
        expect(main([str(build(pathlib.Path(t), b))]) == 0,
               "a bound column read without its subject concept is NOT in play")
    with tempfile.TemporaryDirectory() as t:
        root = pathlib.Path(t) / "empty"
        root.mkdir()
        expect(main([str(root)]) == 2, "a bundle with no freeze refuses, not passes")
    print()
    if bad:
        print(f"FAIL: check_rule_consulted self-test — {len(bad)} of 7 failed: {'; '.join(bad)}")
        return 1
    print("PASS: check_rule_consulted self-test — 7/7: consulted, strict silence, non-strict "
          "silence, not observable, both halves of IN PLAY, and the refusal")
    return 0


if __name__ == "__main__":
    sys.exit(main())
