#!/usr/bin/env python3
"""check_datasets_are_grounded — DOES ANYTHING ASK ABOUT THIS DATASET?

THE MISSING DIRECTION. This estate already gates the chain one way:

    check_ontology_grounds_on_datasets    concept -> dataset    every concept binds a real,
                                                                served, transform-produced relation

and gated it well. Nothing gated the other way. A dataset that NO concept binds is built, served,
profiled, checked for grain and vocabulary drift, and can never be asked about — it is work the
bundle performs for nobody, and every green it collects is green about a relation no question can
reach.

WHAT MADE IT VISIBLE, AND WHY THAT WAS NOT ENOUGH. `sdk/project/lineage_graph.py` already computes
this set and publishes it as `orphans.datasets_bound_by_no_concept`. The console draws it on the
Lineage coverage tab. So the bundle has KNOWN it had an ungrounded dataset for some time, and the
number sat on a page where it could be read and could not fail. It reached a person only because an
unrelated grain check on the same relation went red and someone followed it.

A figure nobody is obliged to act on is a decoration. This is the same figure with an exit code.

    operator: "do we measure if all datasets are grounded to ontology objects? ... we did not
               ground current table into ontology objects. this could be reason for warning"

READ FROM THE SSOT, NOT FROM THE PROJECTION. The orphan list in objects.json is the projector's own
output, and a gate that reads it agrees with the projector by construction: if the projector's
binding logic is wrong, or it was run through an entry point that dropped a field, this gate would
confirm the damage rather than catch it. Both halves are recomputed here from the authored files —
`data/datasets/*.yaml` for the population, `ontology/concepts/*.yaml#grounding.sources[].relation`
for what binds — so the two derivations can disagree, which is the only way either can be checked.

NOT A LINT. An ungrounded dataset is sometimes correct and the gate says which kind it is looking
at: a relation is EXEMPT when its descriptor declares `metadata.status: retired`, or names itself in
`mac.project.yaml#conformance.out_of_scope`. Exemptions are listed in the output, never silent — an
exemption nobody can see is indistinguishable from a rule nobody enforces.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mac_diag as D  # noqa: E402
import mac_project as P  # noqa: E402

UNGROUNDED = "ungrounded-dataset"


def _load(p: pathlib.Path) -> dict:
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def relation_of(doc: dict, stem: str) -> str:
    """The relation a dataset descriptor declares, schema-qualified when it says so."""
    t = doc.get("table") or {}
    name = str(t.get("name") or stem)
    schema = t.get("schema")
    return f"{schema}.{name}" if schema else name


def bound_relations(concepts: list[dict]) -> set[str]:
    """Every relation any concept declares it grounds on, bare name AND qualified, because a
    concept may write `mart.dim_thing` while a descriptor writes schema and name apart."""
    out: set[str] = set()
    for c in concepts:
        for s in ((c.get("grounding") or {}).get("sources") or []):
            rel = str(s.get("relation") or "").strip()
            if rel:
                out.add(rel)
                out.add(rel.split(".")[-1])
    return out


def judge(datasets: list[dict], bound: set[str], exempt: set[str]) -> list[tuple[str, str]]:
    """PURE: (population, what binds, what is excused) -> findings. Separated from the filesystem
    so the rule can be mutant-tested without a bundle on disk."""
    found: list[tuple[str, str]] = []
    for d in sorted(datasets, key=lambda x: x["relation"]):
        rel, stem = d["relation"], d["stem"]
        if stem in exempt or rel in exempt:
            continue
        if rel in bound or rel.split(".")[-1] in bound:
            continue
        found.append(
            (
                UNGROUNDED,
                f"{rel}: no concept names this relation in grounding.sources — it is served, "
                f"and no question can reach it",
            )
        )
    return found


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    # Parsed BEFORE argparse sees it: the self-test takes no bundle and argparse would reject the
    # flag as unknown, which is a gate refusing to prove it can still reject.
    if "--self-test" in sys.argv[1:]:
        return self_test()
    a = ap.parse_args()

    root = pathlib.Path(a.root).resolve()
    ds_dir, c_dir = root / "data" / "datasets", root / "ontology" / "concepts"

    datasets = [
        {"stem": p.stem, "relation": relation_of(_load(p), p.stem), "doc": _load(p)}
        for p in sorted(ds_dir.glob("*.yaml"))
    ]
    concepts = [_load(p) for p in sorted(c_dir.glob("*.yaml"))]

    # TWO POPULATIONS, REFUSED SEPARATELY. Zero datasets and zero concepts are different outages
    # and a caller needs to know which. Neither is a clean pass — an empty denominator has scored a
    # tick in this estate before, which is why every gate here refuses instead.
    if not datasets:
        return D.refuse_empty("check_datasets_are_grounded", ds_dir, unit="dataset")
    if not concepts:
        return D.refuse_empty("check_datasets_are_grounded", c_dir, unit="concept")

    exempt = set()
    for d in datasets:
        if str((d["doc"].get("metadata") or {}).get("status") or "").lower() == "retired":
            exempt.add(d["stem"])
    # out_of_scope CARRIES PATH GLOBS, NOT IDS. Its entries are {path, reason} scoping CONFORMANCE
    # to file trees ("acceptance/oracle/**"), a different vocabulary from a dataset name — and the
    # first draft read `e.get("id")`, which is absent, so every entry excused a dataset called
    # "None". An exemption nobody asked for, granted to nothing, printed as fact. Only an entry
    # whose path actually points into data/datasets/ can excuse a dataset.
    proj = _load(root / "mac.project.yaml")
    for e in ((proj.get("conformance") or {}).get("out_of_scope") or []):
        path = str(e.get("path") if isinstance(e, dict) else e)
        if "data/datasets/" in path:
            exempt.add(pathlib.PurePath(path).stem.replace("*", ""))

    bound = bound_relations(concepts)
    findings = judge(datasets, bound, exempt)

    if a.json:
        print(json.dumps(
            {"datasets": len(datasets), "concepts": len(concepts), "bound": len(bound),
             "exempt": sorted(exempt), "findings": [{"class": c, "msg": m} for c, m in findings]},
            indent=1))
        return 1 if findings else 0

    for _, msg in findings:
        print(f"  [{UNGROUNDED}] {msg}")
    for e in sorted(exempt):
        print(f"  [exempt] {e} — declared retired or out_of_scope; not judged")
    grounded = len(datasets) - len(findings) - len(exempt)
    tail = (
        f"{grounded} of {len(datasets)} served dataset(s) are bound by at least one of "
        f"{len(concepts)} concept(s)"
        + (f", {len(exempt)} exempt" if exempt else "")
    )
    if findings:
        print(f"FAIL: check_datasets_are_grounded — {len(findings)} ungrounded — {tail}")
        return 1
    print(f"PASS: check_datasets_are_grounded — {tail}")
    return 0


def self_test() -> int:
    """One mutant per way the rule can be broken, plus the controls that stop it over-firing."""
    DS = [
        {"stem": "dim_thing", "relation": "mart.dim_thing"},
        {"stem": "fact_event", "relation": "mart.fact_event"},
    ]
    cases = [
        ("every dataset bound", DS, {"mart.dim_thing", "mart.fact_event"}, set(), 0),
        ("one dataset bound by nothing", DS, {"mart.dim_thing"}, set(), 1),
        ("none bound at all", DS, set(), set(), 2),
        # The bare/qualified equivalence: a concept may write the relation either way.
        ("bare name counts as bound", DS, {"dim_thing", "fact_event"}, set(), 0),
        # Exemption works, and is the ONLY thing that silences a finding.
        ("retired is exempt", DS, {"mart.dim_thing"}, {"fact_event"}, 0),
        # NEGATIVE CONTROL: binding a relation that is not a dataset must not excuse a real orphan.
        ("an unrelated binding excuses nothing", DS, {"mart.something_else"}, set(), 2),
    ]
    bad = 0
    for name, ds, bound, exempt, want in cases:
        got = len(judge(ds, bound, exempt))
        if got != want:
            bad += 1
            print(f"  [SELF-TEST FAIL] {name}: {got} finding(s), expected {want}")
    total = len(cases)
    print(
        f"{'PASS' if not bad else 'FAIL'}: check_datasets_are_grounded self-test — "
        f"{total - bad}/{total} case(s): 3 mutant(s) of the rule, the bare/qualified equivalence, "
        f"the exemption path, and a negative control that an unrelated binding excuses nothing"
    )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
