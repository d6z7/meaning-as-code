#!/usr/bin/env python3
"""Generate a test FROM a rule, for every rule whose directive is machine-readable.

Coverage was 0 of 31 when this was written, and the ceiling is 8: SQL cannot be rendered from a
sentence, so only the rules carrying `realized_by` can be covered at all. Those 8 use just TWO canon
patterns, which is why two generators cover the whole current set.

── THE TWO PATTERNS NEED DIFFERENT INSTRUMENTS, and that is the important part ──────────────────
    resolve_by_register    a claim about WHAT THE WAREHOUSE CONTAINS — every code in the fact
                           resolves in the register, and the register's own key is unique.
                           Covered by a PROPERTY.

    refuse_measure_no_row  a claim about HOW AN ANSWER IS FORMED — where no row exists, REFUSE;
                           never return a zero, never substitute the confusable measure.
                           NO SQL CAN TEST THAT. Covered by a CORPUS QUESTION.

`ist_prod.exclusion.no_evidence` declares `confusable: [Prodant]`, and Bentley publishes neither. A
property proves the rows are absent; only asking the engine proves it says "not reported" rather than
handing back an empty result a reader takes for zero. That distinction is the whole reason the corpus
exists, and it is why measuring coverage in properties alone would report a comfortable lie.

── THE GENERATED CORPUS QUESTIONS NAME THEIR RULE ──────────────────────────────────────────────
Every one of the 96 hand-authored oracle files says what it exercises in a SENTENCE, so no rule can
know whether a question covers it. These carry `exercises: [<rule id>]` instead — the smallest change
that makes behavioural coverage countable, and the pattern the hand-authored ones should follow.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import pathlib

import yaml

GEN = "mac_generate_rule_tests.py/1"


def rules_of(root: pathlib.Path):
    out = []
    for f in sorted(glob.glob(str(root / "ontology" / "concepts" / "*.yaml"))):
        d = yaml.safe_load(pathlib.Path(f).read_text(encoding="utf-8")) or {}
        cn = (d.get("concept") or {}).get("name")
        for r in (d.get("contract") or {}).get("rules") or []:
            rb = r.get("realized_by")
            if isinstance(rb, dict) and rb.get("udf"):
                out.append((str(cn), r, rb["udf"], rb.get("params") or {}))
    return out


def register_property(concept, rule, p) -> dict | None:
    view, code = p.get("served_view"), p.get("code")
    fact_join = p.get("fact_join")
    if not view or not code:
        return None
    thing = p.get("thing", concept)
    return {
        "id": f"O-RULE-{rule['id'].replace('.', '-').upper()}",
        "family": "rule", "test_kind": "mac.test_kind.conformance", "severity": "blocker",
        "source": f"ontology rule {rule['id']}", "validates": [concept], "tolerance": 0,
        "statement": (
            f"Prove {rule['id']} still holds\n"
            f"QUESTION. The rule says a {thing} is resolved by its CODE against a register, never by "
            f"its label. Is the register still able to do that?\n"
            f"ANSWER. Every {code} in {view} must appear exactly once — a register that repeats its "
            f"own key cannot resolve anything.\n"
            f"RISK. If the key repeats, a lookup returns two rows and whichever the engine takes is "
            f"arbitrary; if a label is used instead, two places sharing a name collapse into one.\n---\n"
            f"HOW. Counts {code} values appearing more than once in the register. GENERATED FROM THE "
            f"RULE by {GEN} — the rule is the source, so changing it changes this test.\n"
            f"WHERE. {view}.{code}"
            + (f", joined to the fact on {fact_join}." if fact_join else ".")),
        "assertion": {"type": "must_be_zero", "columns": ["register_keys_that_repeat"]},
        "sql": (f"SELECT count(*) AS register_keys_that_repeat\n"
                f'FROM (SELECT "{code}" FROM {view}\n'
                f'      GROUP BY "{code}" HAVING count(*) > 1)'),
    }


def refusal_question(concept, rule, p) -> dict:
    conf = (p.get("confusable") or ["another measure"])[0]
    return {
        "question": {
            "id": f"RULE_{rule['id'].replace('.', '_').upper()}",
            "text": (f"What was {concept} for a brand and market that does not report it?"),
            "class": "REFUSAL", "expected_outcome": "REFUSE",
        },
        "kind": "route",
        "authority": "derived",
        "authority_note": (
            f"GENERATED FROM THE RULE by {GEN}. The rule {rule['id']} declares "
            f"mac.canon.refuse_measure_no_row: where no row exists the engine must REFUSE, not "
            f"return a zero, and must not substitute {conf!r}. No SQL can test that — a query "
            f"returning no rows and an engine saying 'not reported' are indistinguishable in the "
            f"data. Only the answer can be judged."),
        "expected": {
            "disposition": "REFUSE",
            "must_say": f"{concept} is not reported for that scope",
            "must_not": [f"return 0 or an empty result as if it were the answer",
                         f"answer with {conf} instead"],
        },
        "about": [concept],
        "exercises": [rule["id"]],
        "rationale": (
            f"MEASURED 2026-08-20: Bentley publishes no IstProd and no Prodant at all — zero rows "
            f"across every reporting cycle. Asked plainly, the warehouse returns nothing, and "
            f"nothing reads as zero. This is the shape of question that catches it."),
        "stable": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    root = pathlib.Path(a.root).resolve()

    props, questions, skipped = [], [], []
    for concept, rule, udf, params in rules_of(root):
        if udf.endswith("resolve_by_register"):
            q = register_property(concept, rule, params)
            (props.append(q) if q else skipped.append((rule["id"], "no served_view/code in params")))
        elif udf.endswith("refuse_measure_no_row"):
            questions.append((concept, rule, refusal_question(concept, rule, params)))
        else:
            skipped.append((rule["id"], f"no generator for {udf}"))

    print(f"  {len(props)} propert(ies) — data-shape rules, covered by SQL")
    for p in props:
        print(f"     {p['id']:<46}{p['source']}")
    print(f"\n  {len(questions)} corpus question(s) — behaviour rules, covered by asking the engine")
    for c, r, q in questions:
        print(f"     {q['question']['id']:<46}{r['id']}")
    if skipped:
        print(f"\n  {len(skipped)} rule(s) with no generator yet:")
        for rid, why in skipped:
            print(f"     {rid:<46}{why}")

    if not a.apply:
        print("\n  (report only — pass --apply)")
        return 0

    out = root / "acceptance" / "rules_generated.yaml"
    eng = (yaml.safe_load((root / "acceptance" / "properties.yaml").read_text(encoding="utf-8"))
           or {}).get("engine") or {}
    out.write_text(yaml.safe_dump({
        "suite": "fpl2-rules-generated", "version": "1.0",
        "purpose": ("DOES THE WAREHOUSE STILL SATISFY THE RULES THE ONTOLOGY DECLARES? Generated FROM "
                    "the rules, one property per machine-readable data-shape rule. Behaviour rules "
                    "cannot be tested here and are generated as corpus questions instead."),
        "generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "generated_by": GEN, "engine": eng, "properties": props,
    }, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    print(f"\n  -> {out.relative_to(root)}")

    qdir = root / "acceptance" / "oracle"
    for c, r, q in questions:
        f = qdir / f"{q['question']['id']}.yaml"
        f.write_text(yaml.safe_dump(q, sort_keys=False, allow_unicode=True, width=100),
                     encoding="utf-8")
    print(f"  -> {len(questions)} question(s) in {qdir.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
