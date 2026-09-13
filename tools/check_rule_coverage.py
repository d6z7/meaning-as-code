#!/usr/bin/env python3
"""How much of the ONTOLOGY is actually under test — counted by RULE, not by property.

Operator: *"the coverage of real ontology cases is still very low … how much is still open to audit,
review, and semantically confirm these which we have — that they follow ontology and are sound?"*

The property count answers none of that. Measured on <dataset> the day this was written: 288 properties,
of which ONE composes an ontology fragment and 54 render any value from a declaration. So 234 of them
contain no reference to the model at all — they are SQL that happens to live in a bundle.

The proof it matters: 49 properties violated an operator ruling on plan_stage, all 49 PASSED, and no
gate noticed. The rule was correct, in the ontology, and had zero effect on any test. Separately the
collapse rule was replaced and nine properties still implement the retired design.

    A RULE IS COVERED WHEN SOMETHING COMPOSES IT AND CAN FAIL.

── TWO INSTRUMENTS, AND A RULE MAY NEED EITHER ─────────────────────────────────────────────────
    DATA SHAPE       a claim about what the warehouse contains        -> a PROPERTY
    ENGINE BEHAVIOUR a claim about how an answer is FORMED            -> a CORPUS QUESTION

`refuse_measure_no_row` says: where no row exists, REFUSE — never a zero, never the confusable
measure. A property can prove the rows are absent. Only asking the engine proves it says "not
reported" rather than handing back an empty result a reader takes for zero.

── WHY THE CORPUS COLUMN READS `unmeasurable` ──────────────────────────────────────────────────
Every oracle file declares `exercises`, and every one of the 96 is a SENTENCE — "Whether an
unbranded Stock question defaults to the Group consolidated perspective..." — not a rule id. So a
rule cannot know whether any question covers it, and a question cannot know which rule it proves.
That is the same defect as a rule stating its directive in prose, in the other plane. Naming rule ids
in `exercises` is the smallest change that makes behavioural coverage countable at all.

── THE CEILING, STATED UP FRONT ────────────────────────────────────────────────────────────────
Coverage cannot exceed the number of rules carrying a MACHINE-READABLE directive, because SQL cannot
be rendered from a sentence. Converting rules is therefore the gating work, not the finishing work.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import pathlib
import re

import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mac_diag as D          # noqa: E402
import mac_project as P       # noqa: E402

GENERATORS: set[str] = set()


def generators_available() -> set[str]:
    """The canon udfs a generator can actually turn into a test.

    17 canons are registered; two have generators. The rest are TRANSFORM canons — they rewrite a
    sql string — so binding a rule to one produces no test at all."""
    src = (pathlib.Path(__file__).parent / "mac_generate_rule_tests.py").read_text(encoding="utf-8")
    return set(re.findall(r'udf\.endswith\("(\w+)"\)', src))


def rules_of(root: pathlib.Path) -> list[dict]:
    out = []
    # DISCOVERY GOES THROUGH THE LAYOUT RESOLVER — flat and foldered concepts, in whichever plane
    # the project declares (mac_project.concept_files).
    for f in P.concept_files(root):
        d = yaml.safe_load(pathlib.Path(f).read_text(encoding="utf-8")) or {}
        cn = (d.get("concept") or {}).get("name")
        for r in (d.get("contract") or {}).get("rules") or []:
            rb = r.get("realized_by") or {}
            out.append({
                "id": str(r.get("id")), "concept": str(cn),
                "kind": str(r.get("kind", "")).split(".")[-1],
                "udf": str((rb or {}).get("udf") or "") if isinstance(rb, dict) else "",
                # NOT the mere presence of the key. As first written this counted any rule
                # carrying `realized_by`, so binding a rule to a canon with no generator moved the
                # headline 8 -> 9 while `covered` stayed 8 — the metric was easiest to move by
                # adding nothing that can fail. A rule is testable only if its udf has a generator.
                "declares_directive": bool(r.get("realized_by") or r.get("enforced_by")),
                "machine_readable": str((rb or {}).get("udf") or "").split(".")[-1] in GENERATORS
                                    if isinstance(rb, dict) else False,
            })
    return out


def fragments_realizing(root: pathlib.Path) -> dict[str, set[str]]:
    """fragment id -> the canon udfs / rule ids it realizes, so a composing property counts."""
    out: dict[str, set[str]] = {}
    for f in glob.glob(str(root / "ontology" / "**" / "protosql" / "*.yaml"), recursive=True):
        d = yaml.safe_load(pathlib.Path(f).read_text(encoding="utf-8")) or {}
        r = d.get("rule") or {}
        fid = str(r.get("id") or (d.get("metadata") or {}).get("id") or "")
        if not fid:
            continue
        # A fragment credited a rule ONLY when the fragment id equalled the rule id, so
        # snapshot.as_of_cycle — a fragment, not a concept rule — could never credit anything, and
        # `composed` was pinned at 0 no matter how many properties composed it. A fragment now
        # declares what it realizes; without that it credits only itself, as before.
        out[fid] = {fid} | {str(x) for x in (r.get("realizes") or [])}
    return out


def properties_of(root: pathlib.Path) -> list[dict]:
    out = []
    for f in sorted(glob.glob(str(root / "acceptance" / "*.yaml"))):
        d = yaml.safe_load(pathlib.Path(f).read_text(encoding="utf-8"))
        if not isinstance(d, dict) or not d.get("properties"):
            continue
        for p in d["properties"]:
            if isinstance(p, dict):
                out.append({"id": str(p.get("id")), "suite": os.path.basename(f)[:-5],
                            "sql": str(p.get("sql") or ""), "source": str(p.get("source") or ""),
                            "statement": str(p.get("statement") or "")})
    return out


def corpus_of(root: pathlib.Path) -> list[dict]:
    out = []
    for f in sorted(glob.glob(str(root / "acceptance" / "oracle" / "*.yaml"))):
        d = yaml.safe_load(pathlib.Path(f).read_text(encoding="utf-8")) or {}
        out.append({"file": os.path.basename(f), "exercises": str(d.get("exercises") or "")})
    return out


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return P.selftest_discovery(__file__)
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", metavar="PATH", help="also write the report for the wiki")
    a = ap.parse_args()
    root = pathlib.Path(a.root).resolve()

    global GENERATORS
    GENERATORS = generators_available()
    # ZERO IS NOT A SCORE. The verdict below is `covered == len(rules)`, which is TRUE of an empty
    # rule set: on a foldered bundle this gate found no concept, therefore no rule, and reported
    # complete coverage of nothing at exit 0.
    if not P.concept_files(root):
        return D.refuse_empty("check_rule_coverage", P.concepts_dir(root))
    rules, props, corpus = rules_of(root), properties_of(root), corpus_of(root)
    if not rules:
        return D.refuse_empty("check_rule_coverage", P.concepts_dir(root),
                              unit="contract rule on any concept")
    frags = fragments_realizing(root)
    rows = []
    for r in rules:
        composed = [p["id"] for p in props
                    if any(f"@frag:{fid}" in p["sql"] for fid in frags if r["id"] in frags[fid])
                    or (r["udf"] and r["udf"] in p["sql"])]
        # TWO GRADES, and rounding them together would flatter the number.
        #   COMPOSED  the property reads the rule AT RUN TIME (@frag:, @cols:concept:). Change the
        #             rule and the test changes with it, with no step in between.
        #   DERIVED   the property was GENERATED FROM the rule. Change the rule and the test changes
        #             on the next regeneration — real coverage, one step weaker, and the step is a
        #             place where someone can forget.
        # Anything else that merely mentions the id is NAMED, which is not coverage at all: R-VAR-01
        # names a rule in its prose and would not move if that rule were deleted.
        derived = [p["id"] for p in props if p["source"] == f"ontology rule {r['id']}"]
        named = [p["id"] for p in props
                 if r["id"] in p["source"] or r["id"] in p["statement"] or r["id"] in p["sql"]]
        by_corpus = [c["file"] for c in corpus if r["id"] in c["exercises"]]
        rows.append({**r, "composed_by": composed, "derived_by": derived,
                     "named_by": named, "corpus": by_corpus,
                     "covered": bool(composed or derived or by_corpus)})

    covered = sum(1 for r in rows if r["covered"])
    comp_n = sum(1 for r in rows if r["composed_by"])
    deriv  = sum(1 for r in rows if r["derived_by"] and not r["composed_by"])
    behav  = sum(1 for r in rows if r["corpus"])
    named = sum(1 for r in rows if r["named_by"] and not (r["composed_by"] or r["derived_by"]))
    mr = sum(1 for r in rows if r["machine_readable"])
    # corpus linkage: a rule id appearing in an `exercises` field
    linked = sum(1 for c in corpus if any(r["id"] in c["exercises"] for r in rules))

    print(f"  {len(rules)} rules declared · {len(props)} properties · {len(corpus)} corpus questions\n")
    print(f"     {'rule':<46}{'kind':<12}{'directive':<10}{'covered by'}")
    print("     " + "-" * 92)
    for r in sorted(rows, key=lambda x: (not x["covered"], not x["machine_readable"], x["id"])):
        how = (f"composed · {', '.join(r['composed_by'])}" if r["composed_by"]
               else f"derived · {', '.join(r['derived_by'])}" if r["derived_by"]
               else f"corpus · {', '.join(r['corpus'])}" if r["corpus"]
               else f"named only by {', '.join(r['named_by'])}" if r["named_by"]
               else "—")
        print(f"     {r['id']:<46}{r['kind']:<12}"
              f"{'machine' if r['machine_readable'] else 'prose':<10}{how[:44]}")

    print(f"\n  COVERED                                     {covered:>3} of {len(rules)}")
    print(f"     composed — reads the rule at run time     {comp_n:>3}")
    print(f"     derived  — generated from the rule        {deriv:>3}")
    print(f"     corpus   — a question names the rule      {behav:>3}")
    print(f"  named only, which is not coverage            {named:>3}")
    decl = sum(1 for r in rows if r["declares_directive"])
    print(f"  CEILING — rules a generator can turn into a test {mr:>3} of {len(rules)}")
    if decl > mr:
        print(f"     ({decl} declare a directive; {decl - mr} name a canon with NO generator, so")
        print(f"      binding them would move nothing that can fail)")
    print(f"\n  corpus questions naming a rule id            {linked:>3} of {len(corpus)}")
    if linked < len(corpus):
        print(f"     the other {len(corpus) - linked} say what they exercise in a SENTENCE, so no rule can")
        print(f"     know whether they cover it. Behavioural coverage counts only the linked ones.")

    if a.json:
        pathlib.Path(a.json).write_text(json.dumps({
            "rules": len(rules), "properties": len(props), "corpus": len(corpus),
            "covered": covered, "composed": comp_n, "derived": deriv, "behavioural": behav,
            "named_only": named, "machine_readable": mr,
            "corpus_linked": linked, "detail": rows,
        }, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"\n  json -> {a.json}")
    return 0 if covered == len(rules) else 1


if __name__ == "__main__":
    raise SystemExit(main())
