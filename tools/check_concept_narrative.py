#!/usr/bin/env python3
"""check_concept_narrative — the prose document and the declaration must still describe one thing.

PROPOSED-2026-10-05_prose-formal-separation.md Phase 1, and it is deliberately run BEFORE any prose
moves. The plan separates a concept's narrative from its declaration: the `.md` holds the authored
account, read whole; the `.yaml` holds skeleton, bindings and parameters, read second and compared
against that account. Both are produced in one act from the VS Code + LLM dialog.

THAT IS A PROPERTY OF THE FIRST WRITE AND NOT OF THE PAIR OVER TIME. One artifact gets edited alone
and the two stop describing the same thing, silently, because nothing reads them together. A model
producing both makes it likelier, not less: measured in the PCA spike, 6 of 59 generated rule
functions invented a `raise` their source rule never had, so two artifacts can agree with each other
and both be wrong.

COVERAGE, NEVER STRING SIMILARITY. check_canon_binding records why, with the measurement: across
thirteen copies of one law the mean string fit to the canon's render was 0,88, and chasing it higher
made things WORSE -- reordering one clause to match another dropped a third from 0,93 to 0,77. A gate
on similarity fires on rewording as loudly as on redefinition. So this asks only whether each side
MENTIONS what the other DECLARES, in both directions.

THE SEAMS ARE THE CONSOLE'S, NOT INVENTED HERE. mac_console/console_api.py serves
`ontology/concepts/*.md` as one seam and `ontology/concepts/rules/*.md` as another, with the comment
that a glob "must not cross a `/`, or `ontology/concepts/*.md` would silently swallow
`ontology/concepts/rules/*.md`, which is a rule page and a different seam's". Both already reach the
console's side panel. This gate holds the pairs those two seams imply.

Reject classes:
  unpaired-concept      a concept declaration with no narrative, or a narrative with no declaration
  unpaired-rule         a `contract.rules[].id` with no rule page, or a rule page naming no rule
  uncovered-declaration a declared column or rule id that no narrative mentions
  phantom-reference     ADVISORY, never a failure — a column the narrative names that this concept
                        does not declare. Reported because it is where a rename shows up first, and
                        not gated because it cannot be decided from prose: measured twice on
                        contoso5, both attempts were ALL false positives. The broad test read
                        relation names (`v_contoso5_sales_line`, `dim_store`) and framework slots
                        (`label_of`, `value_filter`) as columns; the narrowed test then read
                        order.md's "the six measures ... are all keyed on `order_key` and
                        `line_number`" as a claim about Order, when the sentence correctly
                        attributes that column to the MEASURES. Telling "this concept has X" from
                        "those concepts are keyed on X" needs to know which concept a sentence is
                        about, which no reader here does.

Contract: one PASS:/FAIL: line, exit 0 or 1, exit 2 when it could not run, denominators printed,
and `--self-test` with one mutant per reject class.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mac_project as P  # noqa: E402  — ONE home for where a bundle keeps its concepts

#: A `[[WikiLink]]`, which is how these narratives already cross-reference a concept.
_WIKI = re.compile(r"\[\[([A-Za-z0-9_ .-]+)\]\]")


class Reject:
    __slots__ = ("cls", "where", "detail")

    def __init__(self, cls: str, where: str, detail: str) -> None:
        self.cls, self.where, self.detail = cls, where, detail


def _declared(doc: dict) -> tuple[set[str], set[str]]:
    """(columns, rule ids) a concept document declares."""
    cols: set[str] = set()
    rules: set[str] = set()
    for src in ([_s] if isinstance(_s := ((doc).get("grounding") or {}).get("source"), dict) else []):
        if not isinstance(src, dict):
            continue
        c = src.get("columns")
        if isinstance(c, dict):
            cols |= {str(k) for k in c}
        elif isinstance(c, list):
            cols |= {str(x) for x in c if isinstance(x, str)}
    for r in ((doc.get("contract") or {}).get("rules") or []):
        if isinstance(r, dict) and r.get("id"):
            rules.add(str(r["id"]))
    return cols, rules


def check(root: pathlib.Path) -> tuple[list[Reject], dict[str, int]]:
    import yaml

    rejects: list[Reject] = []
    #: Every concept identity a `[[WikiLink]]` may legally name — `concept.name` and
    #: `concept.label`, collected in the same pass that reads the declarations.
    concept_names: set = set()
    warnings: list[Reject] = []
    files = list(P.concept_files(root))
    cdir = P.concepts_dir(root)
    rules_dir = cdir / "rules"

    narratives = {p.stem: p for p in cdir.glob("*.md") if p.stem != "index"}
    rule_pages = {p.stem: p for p in rules_dir.glob("*.md")} if rules_dir.is_dir() else {}

    seen_rules: set[str] = set()
    n_cols = n_rules = 0

    #: EVERY COLUMN AND RELATION THE BUNDLE DECLARES, gathered first, because the phantom-reference
    #: test below is "a column of another concept" and cannot be answered one concept at a time.
    bundle_cols: set[str] = set()
    relations: set[str] = set()
    for f in files:
        try:
            d0 = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:                                                  # noqa: BLE001
            continue
        c0, _ = _declared(d0)
        bundle_cols |= c0
        for src in ([_s] if isinstance(_s := ((d0).get("grounding") or {}).get("source"), dict) else []):
            if isinstance(src, dict) and src.get("relation"):
                rel = str(src["relation"])
                relations.add(rel)
                relations.add(rel.rsplit(".", 1)[-1])

    for f in files:
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # noqa: BLE001
            rejects.append(Reject("unreadable", f.name, str(exc)[:120]))
            continue
        cols, rules = _declared(doc)
        c = doc.get("concept") or {}
        concept_names |= {str(c[k]) for k in ("name", "label") if c.get(k)}
        n_cols += len(cols)
        n_rules += len(rules)
        seen_rules |= rules

        page = narratives.get(f.stem)
        if page is None:
            rejects.append(Reject("unpaired-concept", f.name,
                                  f"declares {len(cols)} column(s) and {len(rules)} rule(s) and has "
                                  f"no narrative beside it"))
            continue
        prose = page.read_text(encoding="utf-8")

        # ── coverage: the narrative must MENTION what the declaration declares ──────────────
        #    A rule id is checked against the concept narrative OR its own rule page: the plan puts
        #    a rule's argument on `rules/<id>.md`, so requiring it in both would force a restatement
        #    — the second home this whole separation exists to remove.
        for rid in sorted(rules):
            own = rule_pages.get(rid)
            if rid in prose:
                continue
            if own is not None and rid in own.read_text(encoding="utf-8"):
                continue
            rejects.append(Reject("uncovered-declaration", f"{page.name}:{rid}",
                                  "the rule is declared and no narrative mentions it"))
        for col in sorted(cols):
            if not re.search(rf"\b{re.escape(col)}\b", prose):
                rejects.append(Reject("uncovered-declaration", f"{page.name}:{col}",
                                      "the column is declared and the narrative does not name it"))

        # ── the other direction, NARROWED BY MEASUREMENT ────────────────────────────────────
        #    The first cut judged any backticked lowercase token with an underscore as a column
        #    claim. Run on contoso5 it produced 23 rejects and EVERY ONE WAS A FALSE POSITIVE:
        #    relation names (`v_contoso5_sales_line`, `dim_store`, `dim_product`) and framework slot
        #    names (`label_of`, `value_filter`). A narrative legitimately backticks both.
        #
        #    So a token is a column claim only when it IS a column OF THIS BUNDLE and is NOT a
        #    column of THIS concept — i.e. the narrative names another concept's column as if it
        #    were this one's, which is exactly what a rename or a moved column produces.
        #
        #    WHAT THIS NO LONGER CATCHES, stated rather than hidden: a wholly INVENTED column name,
        #    one that belongs to no concept in the bundle. The broad test caught that and was
        #    unusable; catching it properly needs the relation's real column list, which lives on the
        #    Physical descriptor and is a different reader's job.
        for tok in set(re.findall(r"`([a-z][a-z0-9_]{2,})`", prose)):
            if tok in cols or tok in relations or tok not in bundle_cols:
                continue
            warnings.append(Reject("phantom-reference", f"{page.name}:{tok}",
                                   f"named as a column of {f.stem}; declared by another concept. "
                                   f"Advisory — a sentence about another concept reads the same way"))

    # ── `[[WikiLink]]` -> a concept this bundle declares ────────────────────────────────────
    #    A SECOND PASS, because `concept_names` is only complete once every declaration is read;
    #    checking inside the loop above would judge the first page against a set of one.
    #
    #    THIS ONE GATES, where the column phantom above only advises, and the difference is
    #    inference. Deciding whether a backticked token is a claim about THIS concept needs to know
    #    what a sentence is about — no reader here does, and both attempts were 23/23 then 1/1 false
    #    positives. A `[[Name]]` needs nothing: it either names a declared concept or it does not.
    #    That is why `_WIKI` was compiled at the top of this file and then referenced by nothing but
    #    its own definition — the ADR's clause "every `[[Concept]]` the narrative names exists in the
    #    YAML" had no code behind it. Measured on contoso5 2026-10-06 before adding it: 9 distinct
    #    targets over 42 links, all 9 resolving, so this starts green and catches the next rename.
    for page in sorted(set(narratives.values()) | set(rule_pages.values())):
        for target in sorted(set(_WIKI.findall(page.read_text(encoding="utf-8")))):
            if target not in concept_names:
                rejects.append(Reject(
                    "dangling-wikilink", f"{page.name}:[[{target}]]",
                    f"names no concept this bundle declares; a `[[link]]` is a pointer, and "
                    f"{len(concept_names)} identities are declared"))

    for stem, page in sorted(narratives.items()):
        if stem not in {f.stem for f in files}:
            rejects.append(Reject("unpaired-concept", page.name,
                                  "a narrative with no concept declaration"))
    for rid, page in sorted(rule_pages.items()):
        if rid not in seen_rules:
            rejects.append(Reject("unpaired-rule", f"rules/{page.name}",
                                  "a rule page naming no rule any concept declares"))

    return rejects, warnings, {"concepts": len(files), "narratives": len(narratives),
                               "rule_pages": len(rule_pages), "columns": n_cols, "rules": n_rules}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.bundle).resolve()
    try:
        import yaml  # noqa: F401
    except ImportError:
        print("REFUSED: cannot import pyyaml")
        return 2
    try:
        rejects, warns, n = check(root)
    except Exception as exc:  # noqa: BLE001
        print(f"REFUSED: could not read {root}: {exc}")
        return 2
    # ZERO IS NOT A SCORE — a run that found no concept has verified no pair.
    if not n["concepts"]:
        print(f"REFUSED: no concept document under {P.concepts_dir(root)} — nothing to pair")
        return 2

    denom = (f"{n['concepts']} concept(s), {n['narratives']} narrative(s), "
             f"{n['rule_pages']} rule page(s), {n['columns']} declared column(s), "
             f"{n['rules']} declared rule(s)")
    for w in warns[:20]:
        print(f"  [WARNING] {w.where} — {w.detail}")
    if len(warns) > 20:
        print(f"  … {len(warns) - 20} more warning(s)")
    if rejects:
        by: dict[str, int] = {}
        for r in rejects:
            by[r.cls] = by.get(r.cls, 0) + 1
        for r in rejects[:40]:
            print(f"  [{r.cls}] {r.where} — {r.detail}")
        if len(rejects) > 40:
            print(f"  … {len(rejects) - 40} more")
        print(f"\nFAIL: check_concept_narrative — {len(rejects)} reject(s) "
              f"({', '.join(f'{k} {v}' for k, v in sorted(by.items()))}) over {denom}, "
              f"{len(warns)} advisory")
        return 1
    print(f"PASS: check_concept_narrative — every pair agrees over {denom}; "
          f"{len(warns)} advisory phantom-reference(s), which do not gate")
    return 0


def _self_test() -> int:
    checks = 0
    bad: list[str] = []

    def expect(cond, msg):
        nonlocal checks
        checks += 1
        if not cond:
            bad.append(msg)

    YAML = """\
concept:
  name: Thing
grounding:
  source:
    relation: v_thing
    key: thing_code
    columns:
      thing_code: {offers: {}}
      close_date: {offers: {axis: time, extremum: [min, max]}}
contract:
  rules:
    - id: thing.default.open
      kind: mac.concept.rule.default
"""
    GOOD = (
        "A Thing is identified by `thing_code` and closes when `close_date` is set. "
        "The rule thing.default.open takes the open ones.\n"
    )

    def build(tmp, yaml_text=YAML, md_text=GOOD, rule_page=True):
        # THE FIXTURE DECLARES ITS PLANE, because mac_project.resolve falls back to the bundle ROOT
        # when there is no manifest -- so `ontology/concepts/` is invisible to the resolver without
        # one, and the first cut of this self-test built a tree the gate could not see. contoso5's
        # own manifest records the same trap: "without it every tool reading `concepts_dir` looks in
        # `<root>/concepts`, which does not exist -- so check_grain_declaration and
        # check_concept_columns_exist both reported NOT RUN over ten concepts sitting in
        # ontology/concepts/." A fixture that cannot represent the layout tests nothing.
        root = pathlib.Path(tmp)
        (root / "mac.project.yaml").write_text("planes:\n  ontology: ontology\n", encoding="utf-8")
        c = root / "ontology" / "concepts"
        c.mkdir(parents=True, exist_ok=True)
        (c / "thing.yaml").write_text(yaml_text, encoding="utf-8")
        if md_text is not None:
            (c / "thing.md").write_text(md_text, encoding="utf-8")
        if rule_page:
            (c / "rules").mkdir(exist_ok=True)
            (c / "rules" / "thing.default.open.md").write_text("thing.default.open\n", encoding="utf-8")
        return root

    def classes(root) -> set:
        """The reject CLASSES one run produces.

        A VERDICT-ONLY ASSERTION (`main(...) == 1`) DOES NOT SAY WHICH RULE REJECTED, and this
        self-test has already been fooled by exactly that: when `thing_code` joined the YAML
        fixture on 2026-10-07 the advisory arm began exiting 1 on `uncovered-declaration` — a
        class it was not testing — and the phantom it exists for was never the reason.
        MEASURED on a probe copy of this file with the base narrative broken the same way (it no
        longer names `thing_code`): the three arms below stayed GREEN on the wrong class, and
        only "a pair that agrees must pass" and the advisory CONTROL went red. So each arm now
        names the class it is testing, and names it EXACTLY — a superset is a second rule firing
        on the same fixture, which is the shape the probe produced.
        """
        rejects, _warns, _n = check(root)
        return {r.cls for r in rejects}

    with tempfile.TemporaryDirectory() as t:
        expect(main([str(build(t))]) == 0, "a pair that agrees must pass")
    with tempfile.TemporaryDirectory() as t:
        root = build(t, md_text=None)
        expect(main([str(root)]) == 1 and classes(root) == {"unpaired-concept"},
               f"unpaired-concept must reject, as THAT class: got {classes(root)}")
    with tempfile.TemporaryDirectory() as t:
        root = build(t, md_text="Thing is a thing. thing.default.open applies.\n")
        expect(main([str(root)]) == 1 and classes(root) == {"uncovered-declaration"},
               f"a declared column no narrative names must reject, as THAT class: "
               f"got {classes(root)}")
    with tempfile.TemporaryDirectory() as t:
        # ADVISORY, so it must NOT change the verdict. The mutant names a column of another
        # concept — the only form the narrowed test judges — and the gate must still pass.
        #
        # RUN TWICE OVER ONE TREE, control first, because "it did not fail" is the verdict a
        # fixture that mentions no phantom AT ALL also produces, and this arm could therefore
        # pass having exercised nothing. The only difference between the two runs is the sentence
        # in thing.md. MEASURED here: control -> 0 reject(s), 0 warning(s); mutant -> 0 reject(s),
        # exactly 1 `phantom-reference` on `thing.md:other_key`, both over the same denominators
        # (2 concepts, 2 narratives, 1 rule page, 3 declared columns, 1 declared rule).
        root = build(t)                                       # build() writes the GOOD narrative
        c = root / "ontology" / "concepts"
        (c / "other.yaml").write_text(
            "concept:\n  name: Other\ngrounding:\n  source:\n    relation: v_other\n"
            "    key: other_key\n    columns:\n      other_key: {offers: {}}\n", encoding="utf-8")
        # `ghost_code` IS THE DECLARED BLIND SPOT, not a phantom this gate reports. The docstring
        # says so in full -- "WHAT THIS NO LONGER CATCHES ... a wholly INVENTED column name, one
        # that belongs to no concept in the bundle" -- because the narrowed reader only judges a
        # token that IS a column of this bundle. It is in the fixture to PIN that: if someone
        # broadens the reader back to the shape that scored 23/23 false positives on contoso5,
        # the control assertion below goes red and the docstring must be rewritten with it.
        (c / "other.md").write_text("Other keys on `other_key`, not on `ghost_code`.\n",
                                    encoding="utf-8")
        _, warns0, n0 = check(root)
        expect(main([str(root)]) == 0 and not warns0,
               f"CONTROL: the same tree with NO phantom sentence must be silent -- 0 advisory, "
               f"and `ghost_code` (a column of no concept) is the documented blind spot, not a "
               f"finding. Got {[w.where for w in warns0]}")
        expect((n0["concepts"], n0["narratives"]) == (2, 2),
               f"CONTROL: both concepts must be DISCOVERED, or the phantom below is measured "
               f"against a bundle_cols set that never held `other_key` and the advisory arm is "
               f"vacuous. Got {n0}")
        # THE MUTANT: one sentence names ANOTHER concept's column as if it were Thing's. The
        # narrative must still name every column Thing declares -- `thing_code` and `close_date`
        # -- or this arm fails on `uncovered-declaration` and never reaches the advisory. That is
        # what it did when `thing_code` joined the YAML fixture: 1 reject, exit 1, and the
        # phantom it was written for was never the reason.
        (c / "thing.md").write_text(
            "A Thing is identified by `thing_code` and closes when `close_date` is set; "
            "[[Other]] keys on `other_key`. The rule thing.default.open takes the open ones.\n",
            encoding="utf-8")
        _, warns, _ = check(root)
        expect(main([str(root)]) == 0, "an advisory phantom-reference must not fail the gate")
        expect([w.where for w in warns if w.cls == "phantom-reference"] == ["thing.md:other_key"],
               f"the advisory must still be reported, and ON THE PAGE THAT CLAIMS THE COLUMN: "
               f"got {[(w.cls, w.where) for w in warns]}")
    with tempfile.TemporaryDirectory() as t:
        root = build(t)
        (root / "ontology" / "concepts" / "rules" / "thing.default.gone.md").write_text("x\n",
                                                                                        encoding="utf-8")
        expect(main([str(root)]) == 1 and classes(root) == {"unpaired-rule"},
               f"unpaired-rule must reject, as THAT class: got {classes(root)}")
    with tempfile.TemporaryDirectory() as t:
        root = pathlib.Path(t)
        (root / "mac.project.yaml").write_text("planes:\n  ontology: ontology\n", encoding="utf-8")
        (root / "ontology" / "concepts").mkdir(parents=True)
        expect(main([str(root)]) == 2, "an empty population must refuse, not pass")

    if bad:
        for b in bad:
            print(f"  [SELF-TEST] {b}")
        print(f"FAIL: check_concept_narrative self-test — {len(bad)} of {checks} failed")
        return 1
    print(f"PASS: check_concept_narrative self-test — {checks}/{checks} check(s) "
          f"over 4 reject class(es) + the refusal")
    return 0


if __name__ == "__main__":
    sys.exit(main())
