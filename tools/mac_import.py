#!/usr/bin/env python3
"""mac_import.py — ONE RUN, THE FULL STATE. The import an operator performs once per source.

THE CONTRACT: decisions/DELIVERABLES-2026-09-26_first-run-state.md. The operator, 2026-09-26:

    our FIRST DELIVERABLE is PLATFORM and not ontology. platform must deliver as much as possible of
    sound ontology in the first run!!! ... EXPECTATION: FULL STATE FROM WHICH OPERATOR CAN CONTINUE
    TUNING ONTOLOGY. so dont give me this shit over and over where i have to ask for functionality
    here and there

WHY IT EXISTS. The platform had ~30 producers and 63 gates and NOTHING that ran them in order.
`harvest --mode onboard` covered four stages; `mac_profile`, `mac_sample`, `mac_references`,
`mac_generate_sanity`, `mac_generate_ontology_tests`, `run_suite` and `mac_resources` were referenced
by it ZERO times each. Every one of them worked. A bundle recorded them as `reproduction.stages` — a
list of commands a PERSON ran, one at a time — which is exactly why each artifact arrived as a
request from the operator instead of as output.

WHAT IT IS NOT. It is not a new producer. Every stage below is an existing tool called with its real
arguments; this file owns the ORDER, the RESUME, and the REPORT, and nothing else. A stage that
belongs to `harvest` is invoked as `harvest`, so the billed authoring keeps its one home.

THE ORDER IS A DEPENDENCY ORDER, AND EACH LINK WAS LEARNED BY IT BREAKING:
    descriptors  ->  profiles      `mac_profile` refuses a relation with no descriptor
    descriptors  ->  references    it READS the declared key and will not derive one; without a key
                                   a relation is not a parent endpoint
    references   ->  ER            `er_model` comes back `entities=0` and says nothing about why
    profiles     ->  DQ suite      "generate the data-sanity suite FROM the profile"
    concepts     ->  ontology suite, concept samples, the ER's concept layer

THE STATE REPORT IS THE DELIVERABLE THAT MAKES THE OTHERS CHECKABLE (D14). Per deliverable: what was
produced, with a count; what was not, with the REASON. A run that cannot do something says so, which
is the only way "the operator had to ask" stops happening.

    python3 mac_import.py <bundle-root>              # everything free; billed stages reported
    python3 mac_import.py <bundle-root> --accept      # including the billed authoring
    python3 mac_import.py <bundle-root> --report       # produce nothing; just the state
"""

from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
#: WHERE THE BILLED AUTHORING STAGE IS LOOKED FOR: THIS checkout, then $MAC_SDK_ROOTS. It used to
#: prefer a reference-only checkout nobody may write to, and the two copies of harvest.py drifted
#: 415 lines apart; order is the fix, and `_sdk_root` SKIPS a frozen root so it cannot recur.
SDK_ROOTS = [HERE.parent, *(pathlib.Path(p) for p in
                            os.environ.get("MAC_SDK_ROOTS", "").split(os.pathsep) if p.strip())]


# ══════════════════════════════════════════════════════════════════════════════════════════════
# THE DELIVERABLES, as data. Each one knows how to see ITSELF, so the report is a measurement of
# the bundle and not a memory of what this process did.
# ══════════════════════════════════════════════════════════════════════════════════════════════
DELIVERABLES: list[dict] = [
    {"id": "D1", "what": "all data sources", "glob": "data/sources/*.yaml"},
    {"id": "D2", "what": "all data assets", "glob": "data/datasets/*.yaml"},
    {"id": "D9", "what": "measurement plane (profiles)", "glob": "data/profiles/*.yaml"},
    {"id": "D10", "what": "referential structure", "glob": "data/references*/*.yaml"},
    # D11 PROBED AN ABANDONED HOME. The glob was `data/samples/concepts/*.csv`; `mac_sample` moved
    # the concept sample OUT of the data plane on purpose (CONCEPT_SAMPLE_DIR = "samples", relative to
    # the ontology plane) because a concept sample is an ontology artifact — its population comes from
    # the concept's discriminator and its columns from the concept's declarations, so nothing in
    # `data/` can say what it is. This consumer kept reading the old path: a LATENT defect, masked
    # only because the no-concepts-yet cause fires first. The moment --accept authors a concept, D11
    # would have reported absent with no cause at all.
    {"id": "D11", "what": "sample per concept", "glob": "ontology/samples/*.sample.csv"},
    # RELATION PREVIEWS ARE THEIR OWN DELIVERABLE, and conflating them with D11 let the `samples`
    # stage claim a deliverable it structurally CANNOT satisfy: it previews relations, which exist on
    # a first run, while a concept sample needs a concept.
    {"id": "D11b", "what": "relation previews", "glob": "data/samples/*.sample.csv"},
    {"id": "D12", "what": "value registers", "glob": "data/lookups/*.csv"},
    {"id": "D12b", "what": "closure monitor executed",
     "glob": "acceptance/register_membership_runs.json"},
    {"id": "D4", "what": "all concepts", "glob": "ontology/concepts/**/*.yaml"},
    {"id": "D4b", "what": "edges", "glob": "ontology/edges.yaml"},
    {"id": "D3", "what": "ER model (actual state)", "probe": "er"},
    # LINEAGE IS ITS OWN DELIVERABLE, added 2026-09-26 on the operator's instruction. It was folded
    # into "all diagrams", which is the wrong category: a diagram is a RENDERING, lineage is a
    # measured claim about where a column came from, and it is what an operator follows when a
    # number is wrong.
    {"id": "D15", "what": "lineage (engine + the console's graph)", "probe": "lineage_measured"},
    {"id": "D6", "what": "diagrams (mermaid / graph)", "glob": "ontology/*.mmd"},
    {"id": "D5", "what": "SME questions", "glob": "ontology/SME-QUESTIONS.md"},
    {"id": "D13", "what": "resource description", "glob": "*.mac"},
    # DQ IS THREE DELIVERABLES, NOT ONE. The old single row was satisfied by the FILE EXISTING,
    # which is the defect it exists to prevent: generating is not testing, and executing is not
    # reporting. Measured on contoso, the run record carries 71 per-case results and a tally — a
    # report saying "1 file" while 3 cases fail has told the operator nothing.
    {"id": "D7a", "what": "DQ test cases", "probe": "dq_cases"},
    {"id": "D7b", "what": "DQ tests executed", "glob": "acceptance/data_sanity_generated_runs.json"},
    {"id": "D7c", "what": "DQ results (per case + findings)", "probe": "dq_results"},
    {"id": "D8a", "what": "ontology test cases", "probe": "ont_cases"},
    {"id": "D8b", "what": "ontology tests executed + results", "probe": "ont_results"},
]


def _self_test() -> int:
    """One mutant per reject class plus a clean fixture (CORE.md §2).

    THIS TOOL HAD NO SELF-TEST, in violation of the framework's own law 12, and it is the tool where
    that mattered most: it is the one an operator runs, and eight of the thirteen defects found in one
    session were in its reporting — a deliverable probing a path its producer had abandoned, a stage
    declaring one of the two planes it writes, a complete measurement rendered FAIL, a refusal rendered
    NEEDS YOU. None of those needed a warehouse to catch. Every case below runs without a connector, a
    bundle, or a clock.
    """
    import tempfile
    bad: list[str] = []

    def case(label: str, ok: bool, detail: str = "") -> None:
        if not ok:
            bad.append(f"  FAIL  {label}" + (f"\n        {detail}" if detail else ""))

    # ── the verdict precedence, which was wrong twice in one hour ──────────────────────────────────
    refusals = ("could not run", "--project-anyway", "REFUSED:", "SKIP:", "NOTHING TO MEASURE")
    case("CLEAN a zero exit is ok",
         classify(0, "PASS: wrote 6 of 6\n", refusals)[0] == "ok")
    case("MUTANT a stated refusal OUTRANKS exit 3",
         classify(3, "could not run: the suite declares 0 cases\n", refusals)[0] == "refused",
         "getting this order wrong asked the operator to rule on something no ruling can change")
    case("MUTANT exit 3 with no refusal is a RULING, not a failure",
         classify(3, "NEEDS RULING: mac_references — wrote 5 of 5\n", refusals)[0] == "needs_ruling",
         "a complete measurement carrying a finding was rendered FAIL on a healthy first run")
    case("MUTANT exit 1 is a failure",
         classify(1, "Traceback (most recent call last)\n", refusals)[0] == "failed")
    # EXIT 2 IS A CONTRACT, NOT A PHRASE, and the cases above tested 0, 1 and 3 and never it — which
    # is exactly the gap that bit. `mac_sample --plane concepts` on a bundle with no ontology exits 2
    # saying "✗ NOT RUN ... its verdict is UNKNOWN — not absent": a textbook refusal, in words this
    # tuple does not carry, and the first full from-scratch import of contoso3 reported it as FAIL.
    case("MUTANT exit 2 is a REFUSAL even when its words are not in the refusal list",
         classify(2, "\u2717 NOT RUN — found no concept, so it measured NOTHING\n",
                  refusals)[0] == "refused",
         "an empty population reported as a failure teaches an operator to ignore the word")
    case("MUTANT exit 2 still reports the sentence the tool actually printed",
         "NOT RUN" in classify(2, "\u2717 NOT RUN — found no concept\n", refusals)[1])
    case("MUTANT a missing dependency is UNAVAILABLE, not a failure",
         classify(1, "Traceback...\nModuleNotFoundError: No module named 'langchain_aws'\n",
                  refusals)[0] == "unavailable",
         "'fix your bundle' and 'install a dependency' send an operator to different places")
    case("an unavailable stage reports WHAT is missing",
         "langchain_aws" in classify(1, "ModuleNotFoundError: No module named 'langchain_aws'\n",
                                     refusals)[1])
    case("MUTANT a refusal at exit 1 is still a refusal",
         classify(1, "REFUSED: no yaml module\n", refusals)[0] == "refused")
    case("a needs_ruling line is the NEEDS RULING line, not merely the last line",
         classify(3, "NEEDS RULING: the real sentence\ntrailing noise\n",
                  refusals)[1].startswith("NEEDS RULING"),
         "the operator must be shown the sentence that explains the verdict")

    # ── `produces` over several planes is ALL, never ANY ───────────────────────────────────────────
    with tempfile.TemporaryDirectory() as td:
        r = pathlib.Path(td)
        (r / "data" / "datasets").mkdir(parents=True)
        (r / "data" / "datasets" / "x.yaml").write_text("a: 1", encoding="utf-8")
        both = ["data/sources/*.yaml", "data/datasets/*.yaml"]
        case("MUTANT a stage writing two planes is NOT present when one is missing",
             _present(r, both) is False,
             "with ANY, the descriptors stage resumed on a bundle whose sources plane was deleted "
             "and left D1 missing for the whole run")
        (r / "data" / "sources").mkdir(parents=True)
        (r / "data" / "sources" / "y.yaml").write_text("a: 1", encoding="utf-8")
        case("CLEAN both planes present is present", _present(r, both) is True)
        case("MUTANT an empty directory is not presence",
             _present(r, "data/empty") is False)
        # A DIRECTORY HOLDING ONLY A GENERATED READ-VIEW IS NOT THE DELIVERABLE. This is why the
        # concepts stage declares `ontology/concepts/**/*.yaml` and not the directory: index.md is
        # written there by the projection, and as a bare-directory predicate it resumed the billed
        # authoring stage forever after one failed attempt.
        (r / "ontology" / "concepts").mkdir(parents=True)
        (r / "ontology" / "concepts" / "index.md").write_text("# read view", encoding="utf-8")
        case("MUTANT a concepts dir holding only index.md is NOT concepts present",
             _present(r, "ontology/concepts/**/*.yaml") is False,
             "a failed authoring attempt must not block every retry")
        (r / "ontology" / "concepts" / "customer.yaml").write_text("name: x", encoding="utf-8")
        case("CLEAN one authored concept IS concepts present",
             _present(r, "ontology/concepts/**/*.yaml") is True)

    # ── the deliverables table's own integrity ─────────────────────────────────────────────────────
    ids = [d["id"] for d in DELIVERABLES]
    case("MUTANT no duplicate deliverable id", len(ids) == len(set(ids)),
         f"duplicates: {[i for i in ids if ids.count(i) > 1]}")
    case("every deliverable declares a probe or a glob, never neither",
         all(("probe" in d) != ("glob" in d) for d in DELIVERABLES),
         str([d["id"] for d in DELIVERABLES if ("probe" in d) == ("glob" in d)]))
    case("every deliverable declares what it IS, for the operator's report",
         all(d.get("what") for d in DELIVERABLES))

    # ── EVERY ABSENCE MUST NAME ITS CAUSE. This is the promise the report makes in its own words:
    #    "so none of them has to be asked for". On an empty bundle every deliverable is absent, so
    #    every cause branch is exercised at once.
    with tempfile.TemporaryDirectory() as td:
        r = pathlib.Path(td)
        args = argparse.Namespace(accept=False, refresh=False, report=True, root=str(r))
        causeless = [d["id"] for d in DELIVERABLES if not (_why(r, d, args) or "").strip()]
        case("MUTANT every absent deliverable states a CAUSE on an empty bundle",
             not causeless,
             f"{len(causeless)} deliverable(s) would be reported absent with no reason: "
             f"{', '.join(causeless)} — the report's whole promise is that none has to be asked for")

    # ── every stage credits deliverables that exist ────────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as td:
        r = pathlib.Path(td)
        undefined = sorted({d for st in _stages(r) for d in str(st.get("d", "")).split()
                            if d and d not in set(ids)})
        # D11 IS THE CONCEPT DRAW, SO ITS PRODUCER MUST FOLLOW THE CONCEPTS STAGE. Stated as an
        # invariant because the old order made D11 unreachable and no test noticed: a deliverable whose
        # input is produced later in the same run can only ever be reported absent.
        names = [st["name"] for st in _stages(r)]
        credits = {st["name"]: str(st.get("d", "")).split() for st in _stages(r)}
        d11 = [n for n, cs in credits.items() if "D11" in cs]
        case("MUTANT every D11 producer runs AFTER the concepts stage",
             all(names.index(n) > names.index("concepts") for n in d11),
             f"D11 is credited to {d11}; concepts is stage {names.index('concepts') + 1} and a "
             f"producer before it cannot see a concept, so D11 would be unreachable in one pass")
        case("MUTANT no stage credits a deliverable id the table does not define",
             not undefined,
             f"stages credit undefined id(s): {', '.join(undefined)} — the inverse of D11 reading a "
             f"path its producer had abandoned")

    for line in bad:
        print(line)
    total = 19
    if bad:
        print(f"\nFAIL: mac_import self-test — {len(bad)} of {total} case(s) failed")
        return 1
    print(f"PASS: mac_import self-test — {total}/{total} case(s): 9 mutant(s), one per reject class "
          f"(a refusal outranked by an exit code, a complete measurement called a failure, a real "
          f"failure, a refusal at exit 1, a two-plane stage resuming on one plane, an empty directory "
          f"counted as output, a duplicate deliverable id, an absence with no stated cause, a stage "
          f"crediting an undefined deliverable, a missing dependency called a failure, a generated read-view counted as the "
          f"deliverable it sits beside, a D11 producer running before the concepts exist) plus clean fixtures that must pass")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    # `root` IS OPTIONAL ONLY SO THAT --self-test NEEDS NOTHING. A self-test that requires a bundle
    # is a self-test nobody runs in CI, and this one deliberately touches no warehouse.
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--accept", action="store_true",
                    help="run the BILLED authoring stages too (concepts)")
    ap.add_argument("--report", action="store_true", help="produce nothing; print the state")
    ap.add_argument("--self-test", action="store_true",
                    help="seed a mutant per reject class; needs no bundle and no warehouse")
    ap.add_argument("--refresh", action="store_true", help="re-run stages whose output exists")
    # THE DATA PLANE IS TWO DELIVERIES (operator, 2026-09-28: "split data plane delivery in two
    # parts: data sources and datasets ... have checklist for each one of them"). A part runs ONLY
    # the stages tagged with it and reports ONLY its own checklist, because a part that quietly ran
    # shared stages would be the whole import wearing a narrower name, and a checklist covering both
    # planes cannot say which half is short.
    ap.add_argument("--part", choices=("sources", "datasets", "all"), default="all",
                    help="which delivery to run and report on (default: all). `sources` = the "
                         "landing plane; `datasets` = the served plane")
    ap.add_argument("--stop-on-fail", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.root).resolve()
    if not root.is_dir():
        print(f"REFUSED: {root} is not a directory")
        return 2
    missing_input = [f for f in ("mac.project.yaml", "connection.yaml") if not (root / f).is_file()]
    if missing_input:
        print(f"REFUSED: {root.name} is missing {', '.join(missing_input)}.\n"
              f"  Those two are the operator's INPUT — where the data is, and what this bundle is\n"
              f"  called. Everything else on the deliverables list is this command's OUTPUT.")
        return 2

    part = f" — PART: {a.part.upper()}" if a.part != "all" else ""
    print(f"mac_import {root.name}{part} — {'REPORT ONLY' if a.report else ('ACCEPT (billed stages run)' if a.accept else 'FREE STAGES ONLY')}")
    if a.part != "all":
        ran = [st["name"] for st in _stages(root) if st.get("part") in (a.part, "both")]
        held = [st["name"] for st in _stages(root) if st.get("part") not in (a.part, "both")]
        print(f"  running {len(ran)} stage(s): {', '.join(ran)}")
        print(f"  HOLDING {len(held)} stage(s) that belong to another part or to no part: "
              f"{', '.join(held)}")
    print("=" * 96)

    outcomes: list[tuple[str, str, str, float]] = []
    if not a.report:
        for stage in _stages(root):
            if a.part != "all" and stage.get("part") not in (a.part, "both"):
                continue
            outcomes.append(_run(stage, root, a))
            if a.stop_on_fail and outcomes[-1][1] == "FAIL":
                print("\n  --stop-on-fail: stopping here")
                break

    print("\n" + "=" * 96)
    if outcomes:
        print("STAGES")
        for name, verdict, detail, secs in outcomes:
            print(f"  {verdict:8} {name:26} {secs:6.1f}s  {detail}")
    if a.part != "all":
        # THE PART REPORTS ITS OWN CHECKLIST, not the whole-bundle state. A part that printed the
        # full deliverables table would say NO against seven things it was never asked to produce.
        rc = _print_checklist(root, a.part)
        print(f"\n  the other part's stages were HELD, so this says nothing about them. "
              f"Run `--part {'datasets' if a.part == 'sources' else 'sources'}` for that checklist.")
        return rc
    return _report(root, a)


# ══════════════════════════════════════════════════════════════════════════════════════════════
# THE CHAIN
# ══════════════════════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════════════════════
# THE TWO CHECKLISTS. One per delivery, because the operator ruled the data plane is two deliveries
# and "have checklist for each one of them" (2026-09-28).
#
# EVERY ITEM CARRIES ITS DENOMINATOR. The estate's standing lesson is that a green tick over an
# unstated population says nothing — a gate reported PASS having examined zero files, and a stage
# reported done having profiled 1 relation of 22. So an item here answers "n of m", and m is the
# POPULATION the item is about, derived from the plane itself rather than from what happened to be
# produced. `0 of 0` is reported as EMPTY and never as complete: nothing to check is not a pass.
# ══════════════════════════════════════════════════════════════════════════════════════════════
def _stems(root: pathlib.Path, *rel: str) -> list[str]:
    return sorted(p.stem for p in (root.joinpath(*rel)).glob("*.yaml"))


def _per_relation(root, plane, produced, suffix=".yaml"):
    """One expected artifact per relation OF THIS PLANE — the honest denominator for a per-item stage."""
    want = _stems(root, "data", plane)
    have = [r for r in want if (root / "data" / produced / f"{r}{suffix}").is_file()]
    return have, want


CHECKLISTS: dict[str, list[dict]] = {
    "sources": [
        {"id": "S1", "what": "every landed relation is described",
         "probe": lambda r: (_stems(r, "data", "sources"), _stems(r, "data", "sources")),
         "where": "data/sources/*.yaml"},
        {"id": "S2", "what": "every landed relation is profiled",
         "probe": lambda r: _per_relation(r, "sources", "profiles"),
         "where": "data/profiles/<relation>.yaml"},
        # `.src.sample.csv` — THE SUFFIX IS THE CONVENTION AND THE PROBE HAS TO KNOW IT. Written
        # `.sample.csv` first, this item reported 0 of 7 against a plane that had all seven: a
        # checklist that does not encode the naming rule raises a false alarm, which costs more
        # trust than no checklist at all. `mac_sample` disambiguates the planes this way because a
        # 1:1 passthrough bundle has the same stem on both.
        {"id": "S3", "what": "every landed relation has a preview",
         "probe": lambda r: _per_relation(r, "sources", "samples", ".src.sample.csv"),
         "where": "data/samples/<relation>.src.sample.csv"},
        {"id": "S4", "what": "referential structure measured on the landing plane",
         "probe": lambda r: _per_relation(r, "sources", "references"),
         "where": "data/references/<relation>.yaml"},
        # ── THE PAGES. A DESCRIPTOR IS NOT A DELIVERABLE TO A PERSON. Operator, 2026-09-28: "there is
        #    one thing which is for sure missing - page overview on all sources ... i want to have
        #    control mechanism which will report missing or make sure that it gets delivered".
        #
        #    Measured when these two items were added: contoso5, whose sources checklist read 4 of 4,
        #    carried ZERO .md files. Every machine-readable artifact was present and nothing a person
        #    opens was. The checklist said complete because it only ever asked about YAML — which is
        #    the same defect class as a gate reporting PASS over a population it never looked at, one
        #    level up: the ITEMS were the narrow thing, not the counts.
        {"id": "S5", "what": "every landed relation has a rendered page",
         "probe": lambda r: _per_relation(r, "sources", "sources", ".md"),
         "where": "data/sources/<relation>.md"},
        {"id": "S6", "what": "the landing plane has an overview page over ALL of its relations",
         "probe": lambda r: (["data/sources/index.md"] if (r / "data" / "sources" / "index.md").is_file()
                             else [],
                             ["data/sources/index.md"] if _stems(r, "data", "sources") else []),
         "where": "data/sources/index.md"},
    ],
    "datasets": [
        {"id": "T1", "what": "every served relation is described",
         "probe": lambda r: (_stems(r, "data", "datasets"), _stems(r, "data", "datasets")),
         "where": "data/datasets/*.yaml"},
        {"id": "T2", "what": "every served relation is profiled",
         "probe": lambda r: _per_relation(r, "datasets", "profiles"),
         "where": "data/profiles/<relation>.yaml"},
        {"id": "T3", "what": "every served relation has a preview",
         "probe": lambda r: _per_relation(r, "datasets", "samples", ".sample.csv"),
         "where": "data/samples/<relation>.sample.csv"},
        {"id": "T4", "what": "referential structure measured on the served plane",
         "probe": lambda r: _per_relation(r, "datasets", "references_served"),
         "where": "data/references_served/<relation>.yaml"},
        {"id": "T5", "what": "every served relation has a transform descriptor",
         "probe": lambda r: _per_relation(r, "datasets", "transforms"),
         "where": "data/transforms/<relation>.yaml"},
        {"id": "T6", "what": "every served relation has a rendered page",
         "probe": lambda r: _per_relation(r, "datasets", "datasets", ".md"),
         "where": "data/datasets/<relation>.md"},
        # IF YOU HAVE A DATASET YOU MUST HAVE LINEAGE — the operator's rule, 2026-09-28, enforced at
        # the two grains it can fail at. T8 asks whether the RELATION is traced at all; T9 asks
        # whether every COLUMN of it is, which is the grain that actually answers "where did this
        # number come from". A relation can be traced while a column it computed is not.
        {"id": "T8", "what": "every served relation is traced in the lineage",
         "probe": lambda r: ([s for s in _stems(r, "data", "datasets") if _lineage_index(r).get(s)],
                             _stems(r, "data", "datasets")),
         "where": "data/lineage/lineage.json"},
        {"id": "T9", "what": "every served COLUMN has a source or a stated expression",
         "probe": lambda r: _traced_columns(r),
         "where": "data/lineage/lineage.json#columns[]"},
        {"id": "T7", "what": "the served plane has an overview page over ALL of its relations",
         "probe": lambda r: (["data/datasets/index.md"]
                             if (r / "data" / "datasets" / "index.md").is_file() else [],
                             ["data/datasets/index.md"] if _stems(r, "data", "datasets") else []),
         "where": "data/datasets/index.md"},
    ],
}


def _traced_columns(root):
    """(traced, all) served columns — the denominator is every column the descriptors declare."""
    import yaml as _yaml
    idx = _lineage_index(root)
    have, want = [], []
    d = pathlib.Path(root) / "data" / "datasets"
    if not d.is_dir():
        return have, want
    for f in sorted(d.glob("*.yaml")):
        try:
            doc = _yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except _yaml.YAMLError:
            continue
        for c in (doc.get("columns") or []):
            if not isinstance(c, dict) or not c.get("name"):
                continue
            key = f"{f.stem}.{c['name']}"
            want.append(key)
            if (idx.get(f.stem) or {}).get(str(c["name"])):
                have.append(key)
    return have, want


def _lineage_index(root) -> dict:
    """`{relation_stem: {column: entry}}` from data/lineage/lineage.json.

    A COLUMN COUNTS AS TRACED IF IT NAMES A SOURCE **OR** CARRIES AN EXPRESSION. Those are the two
    honest answers: it came from there, or it was computed and here is the arithmetic. A column with
    neither is one nobody can explain, which is what this rule exists to find.
    """
    import json as _json
    f = pathlib.Path(root) / "data" / "lineage" / "lineage.json"
    if not f.is_file():
        return {}
    try:
        doc = _json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    # KEYED BY BOTH THE STEM AND THE DECLARED table.name, because they are not always the same string
    # and a probe that assumes one of them reports a false gap. contoso4's lineage names its views
    # `contoso_served.currencyexchange` while its descriptor stem is `v_contoso4_currencyexchange`;
    # matching only the stem would have called a bundle untraced for a naming difference rather than
    # for the real defect, which is that all 96 of its columns carry neither a source nor an
    # expression.
    import yaml as _yaml
    alias: dict = {}
    dd = pathlib.Path(root) / "data" / "datasets"
    if dd.is_dir():
        for f in sorted(dd.glob("*.yaml")):
            try:
                doc2 = _yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            except _yaml.YAMLError:
                continue
            name = str(((doc2.get("table") or {}).get("name")) or "").split(".")[-1]
            if name:
                alias[name] = f.stem
    out: dict = {}
    for c in (doc.get("columns") or []):
        if not isinstance(c, dict):
            continue
        view = str(c.get("view") or "").split(".")[-1]
        stem = alias.get(view, view)
        col = c.get("column")
        if stem and col and (c.get("source_column") or c.get("expression")):
            out.setdefault(stem, {})[str(col)] = c
    return out


def _print_checklist(root: pathlib.Path, part: str) -> int:
    """The checklist, PROJECTED from mac_artifacts.yaml — not written here.

    IT WAS FIFTEEN HAND-WRITTEN LAMBDAS, and that is how a whole deliverable went missing while this
    function printed `6 of 6` and `9 of 9`: the data-quality assessment was in no item, so no item
    could be short. A hand-written list checks what somebody remembered to write down, and the defect
    this whole change answers is that I do not remember reliably.

    Projected from three DECLARED fields — `phase`, `path`, `population` — it went from 15 items to
    40 on the same bundle without anyone writing the extra 25. The old list is kept below as
    `CHECKLISTS` and used only as a FALLBACK when the registry cannot be read, so a framework
    without a manifest still reports something rather than nothing.
    """
    items, projected = _projected_checklist(root, part), True
    if not items:
        items, projected = [dict(it, na=None) for it in CHECKLISTS.get(part, [])], False
    src = "projected from mac_artifacts.yaml" if projected else "the hand-written fallback"
    print(f"\nCHECKLIST — {part.upper()} ({len(items)} item(s), {src})\n")
    short = 0
    for it in items:
        if it.get("na"):
            print(f"  [n/a  ] {it['id']:26} {it['na']}")
            continue
        if projected:
            have, want = it["have"], it["want"]
        else:
            have, want = it["probe"](root)
        n, m = len(have), len(want)
        if it.get("optional") and n == 0:
            # `empty_is: OK` — absence is the NORMAL state for this kind. `sme_thread_log` is
            # written by the console when somebody comments, never by an import; reporting it
            # SHORT on every delivery makes "not complete" mean nothing.
            mark, note = "OK   ", ""
        elif m == 0:
            if it.get("empty_is") == "OK":
                mark, note = "OK   ", ""
            else:
                mark, note = "EMPTY", "nothing to check — 0 of 0 is not a pass, it is an empty population"
        elif n == m:
            mark, note = "OK   ", ""
        else:
            mark, note = "SHORT", "missing: " + ", ".join(str(x) for x in want if x not in have)
        if mark != "OK   ":
            short += 1
        print(f"  [{mark}] {str(it['id']):26} {str(it['what'])[:46]:46} {n} of {m:<3} {it['where']}")
        if note:
            print(f"                {note}")
    print(f"\n  {len(items) - short} of {len(items)} item(s) complete"
          + ("" if not short else f"; {short} NOT complete"))
    return 1 if short else 0


def _projected_checklist(root: pathlib.Path, part: str) -> list:
    """The manifest's own answer, or [] when it cannot be read — never a guess."""
    try:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        import mac_manifest as M
        fw = pathlib.Path(__file__).resolve().parent.parent
        # EVERY DECLARATION, not just the big file. When the phase-1 kinds moved into guardrails/
        # this read `declared_kinds` — mac_artifacts.yaml alone — and a delivery owing 29 items
        # printed a checklist of 6 leftovers and called it `6 of 6 complete`.
        kinds = M.declared_items(fw)
        return M.checklist(root, part, kinds) if kinds else []
    except Exception as exc:                                             # noqa: BLE001
        print(f"  (the manifest could not be projected: {exc}; falling back to the written list)")
        return []


def _stages(root: pathlib.Path) -> list[dict]:
    """Every stage, in dependency order. `produces` is what makes RESUME possible."""
    # BOTH PLANES. A measured bug of this file: `relations()` globbed data/datasets only, so the 8
    # RAW landings were never profiled — and the SOURCES reference plane takes its parent key from
    # the PROFILE (`key_from: profile`), not from the descriptor. `mac_references --plane sources`
    # then reported "wrote 0 of 0 relation file(s) over 8 relation(s) in scope", which reads like a
    # missing key and was a missing profile.
    # AND A STEM IS NOT A RELATION WHEN BOTH PLANES CARRY IT. `mac_profile` is addressed by bare
    # stem and resolves it by searching data/datasets BEFORE data/sources, so when a served relation
    # has the same name as its landing the SOURCES one is never profiled — it profiles the served
    # relation twice, to the same file, silently.
    #
    # Invisible on every bundle until a VANILLA one existed: a curated serving layer renames
    # (dim_contoso_store <- store) and collides with nothing, so 14 descriptors gave 14 profiles. A
    # 1:1 passthrough shares every name, and 16 descriptors gave 8 profiles. Benign there — the two
    # relations are byte-identical by construction — and LATENTLY WRONG the moment anybody curates
    # one, because the sources reference plane takes its parent key from the profile.
    #
    # NOT FIXED HERE, and deliberately not: the fix is an interface change to `mac_profile` plus a
    # naming scheme, and six consumers read `data/profiles/<stem>.yaml` — a `.src` suffix breaks stem
    # matching in `mac_references`. Guessing at it while shipping would be the defect class this
    # estate keeps paying for. So it is made LOUD, which is what a first run can honestly do about it.
    def relations(*planes):
        """The relation stems of the named planes — BOTH when none is named.

        A PART PROFILES ITS OWN PLANE. Splitting the data-plane delivery in two (operator,
        2026-09-28) means the sources part must not profile the served relations and call itself
        done, so the plane is a parameter rather than a fixed pair. The collision note above still
        stands and gets LOUDER under the split, not quieter: `mac_profile` is addressed by bare stem
        and searches data/datasets before data/sources, so on a 1:1 passthrough bundle a
        sources-plane profile call still lands on the served relation. contoso3 renames every served
        relation (dim_port <- port), so it has no collision to hide behind.
        """
        return sorted(pp.stem for plane in (planes or ("datasets", "sources"))
                      for pp in (root / "data" / plane).glob("*.yaml"))
    return [
        # ---- the data plane, MEASURED (free) -------------------------------------------------
        # BOTH PLANES, DECLARED. `produces` named only `data/datasets/*.yaml` while the stage writes
        # the sources plane too (its own `d` says D1 D2) — so with the sources plane deleted and the
        # datasets plane intact, resume saw its output and SKIPPED, leaving D1 permanently missing.
        # That is the same masking bug already fixed for the two reference planes, and it is the bug
        # a wipe-and-rerun exists to catch: `produces` must name EVERYTHING the stage writes, or
        # resume answers about a subset.
        # ONE STAGE PER PLANE. This wrote both from a single call, which is precisely what made the
        # two deliveries impossible to sign off separately: a checklist covering D1 and D2 at once
        # cannot say which half is short, and a resume that saw either plane skipped the other.
                # `always`, LIKE ITS PROMOTE SIBLING. Both stages write `data/sources/*.yaml` and only the
        # promotion carried the flag — which the manifest gate could not see while it unioned
        # `always` across every writer of a glob. A descriptor measured from the warehouse is
        # `re-derived` by declaration, and one writer willing to skip is all a stale artifact needs.
{"name": "descriptors-sources", "part": "sources", "always": True, "produces": "data/sources/*.yaml",
         "d": "D1", "cmd": [_tool("mac_descriptors.py"), str(root), "--plane", "sources"]},
                # `always`, LIKE ITS PROMOTE SIBLING. Both stages write `data/sources/*.yaml` and only the
        # promotion carried the flag — which the manifest gate could not see while it unioned
        # `always` across every writer of a glob. A descriptor measured from the warehouse is
        # `re-derived` by declaration, and one writer willing to skip is all a stale artifact needs.
        # APPLY BEFORE MEASURING, because the served plane does not exist until something makes
        # it. Operator, 2026-09-29: "you apply sql ... always !!! all communication to the data and
        # DB goes through you."
        #
        # THE CHAIN HAD A HOLE IN THE MIDDLE. `transform_sql` declared its applier as "«the
        # warehouse», role: build.sh applies it" — a bundle-local shell script outside the
        # pipeline — so GENERATE -> APPLY -> MEASURE was only ever two thirds wired. Measured
        # 2026-09-29: a regenerated bundle carried eight `.sql` describing eight views that were
        # never created, while the warehouse still held the eight whose `.sql` had been deleted.
        # Ten files, eight views, and the delivery reported 39 of 39 complete over the mismatch.
        #
        # `always`, because its output is the WAREHOUSE and no file on disk records whether the
        # views match the statements that claim to create them. There is nothing to resume on.
        {"name": "apply-transforms", "part": "datasets", "always": True, "d": "D2",
         "cmd": [_tool("mac_apply_transforms.py"), str(root)]},
        {"name": "descriptors-datasets", "part": "datasets", "always": True, "produces": "data/datasets/*.yaml",
         "d": "D2", "cmd": [_tool("mac_descriptors.py"), str(root), "--plane", "datasets"]},
        # `mac_profile` takes ONE relation, so this stage is one call per descriptor — the tool's
        # own signature, not a loop invented here.
        # PER-ITEM RESUME, and the stage-level kind was a measured bug of this file: one profile
        # existed from an earlier hand-run, `data/profiles/*.yaml` matched, and the whole stage
        # RESUMEd — 1 profile for 22 relations, reported as done. A stage that iterates must resume
        # per ITEM, or "present" means "one of them is present".
        # `always`, ON THE MANIFEST'S RULING. `mac_artifacts.yaml` declares this kind `re-derived`:
        # a pure function of the warehouse, whose stale copy is indistinguishable from a fresh one
        # by its presence. `check_artifact_conformance#PHASED` holds the stage to that declaration,
        # and it found this one resuming. Measured 2026-09-28, the same defect three times: the DQ
        # stages resumed on phase 1's output and left the served plane with 0 of 8 relations
        # assessed; `lineage` resumed after a rename and the checklist read T8 0 of 8; and the
        # transform descriptors resumed on views that no longer existed.
        {"name": "profiles-sources", "part": "sources", "always": True, "produces": "data/profiles/*.yaml", "d": "D9",
         "each": lambda: [[_tool("mac_profile.py"), str(root), r] for r in relations("sources")],
         "missing": lambda: [[_tool("mac_profile.py"), str(root), r] for r in relations("sources")
                             if not (root / "data" / "profiles" / f"{r}.yaml").is_file()]},
        # `always`, ON THE MANIFEST'S RULING. `mac_artifacts.yaml` declares this kind `re-derived`:
        # a pure function of the warehouse, whose stale copy is indistinguishable from a fresh one
        # by its presence. `check_artifact_conformance#PHASED` holds the stage to that declaration,
        # and it found this one resuming. Measured 2026-09-28, the same defect three times: the DQ
        # stages resumed on phase 1's output and left the served plane with 0 of 8 relations
        # assessed; `lineage` resumed after a rename and the checklist read T8 0 of 8; and the
        # transform descriptors resumed on views that no longer existed.
        {"name": "profiles-datasets", "part": "datasets", "always": True, "produces": "data/profiles/*.yaml", "d": "D9",
         "each": lambda: [[_tool("mac_profile.py"), str(root), r] for r in relations("datasets")],
         "missing": lambda: [[_tool("mac_profile.py"), str(root), r] for r in relations("datasets")
                             if not (root / "data" / "profiles" / f"{r}.yaml").is_file()]},

        # TWO STAGES, NOT ONE, because the two planes have different INPUTS and only one of them
        # can be automated. Lumped together, the sources half's refusal masked the served half's
        # success — measured: the report said CANNOT while 19 references over 14 relations had just
        # been drawn.
        #
        #   SERVED  key from the DESCRIPTOR (`columns[].role == primary_key`),
        #           which `mac_descriptors` measures. Automatable, and it is the plane the ER model
        #           is built from.
        #   SOURCES key from the PROFILE's `identity_evidence`, which only `mac_admit_identity`
        #           writes — and that tool requires `--measure <column>`, "THE ONE BIT A HUMAN"
        #           supplies, per relation. A first run cannot produce it, and saying so is the
        #           honest output.
        # `always`, ON THE MANIFEST'S RULING. `mac_artifacts.yaml` declares this kind `re-derived`:
        # a pure function of the warehouse, whose stale copy is indistinguishable from a fresh one
        # by its presence. `check_artifact_conformance#PHASED` holds the stage to that declaration,
        # and it found this one resuming. Measured 2026-09-28, the same defect three times: the DQ
        # stages resumed on phase 1's output and left the served plane with 0 of 8 relations
        # assessed; `lineage` resumed after a rename and the checklist read T8 0 of 8; and the
        # transform descriptors resumed on views that no longer existed.
        {"name": "references-datasets", "part": "datasets", "always": True,
         "produces": "data/references_served/*.yaml", "d": "D10 D3",
         "cmd": [_tool("mac_references.py"), str(root), "--plane", "served"]},
        # `always`, ON THE MANIFEST'S RULING. `mac_artifacts.yaml` declares this kind `re-derived`:
        # a pure function of the warehouse, whose stale copy is indistinguishable from a fresh one
        # by its presence. `check_artifact_conformance#PHASED` holds the stage to that declaration,
        # and it found this one resuming. Measured 2026-09-28, the same defect three times: the DQ
        # stages resumed on phase 1's output and left the served plane with 0 of 8 relations
        # assessed; `lineage` resumed after a rename and the checklist read T8 0 of 8; and the
        # transform descriptors resumed on views that no longer existed.
        {"name": "references-sources", "part": "sources", "always": True,
         "produces": "data/references/*.yaml", "d": "D10",
         "needs_human": ("the SOURCES plane takes its key from the profile's identity_evidence, "
                         "which only mac_admit_identity writes — and it needs --measure <column> "
                         "per relation, which is a human's call"),
         "cmd": [_tool("mac_references.py"), str(root), "--plane", "sources"]},
        # ---- the ontology plane (concepts are BILLED) -----------------------------------------
        # TRANSFORM DESCRIPTORS, and they are what the console's LINEAGE VIEW ultimately needs. The
        # projection builds `objects.json#lineage_graph` from `data/transforms/*.yaml`, NOT from the
        # .sql: measured 2026-09-26 on a bundle holding six .sql files and no descriptors, the graph
        # came back with 14 nodes and 0 EDGES, every dataset "with no input". The operator's report
        # was simply "i did not get lineage".
        # `always`, ON THE MANIFEST'S RULING. `mac_artifacts.yaml` declares this kind `re-derived`:
        # a pure function of the warehouse, whose stale copy is indistinguishable from a fresh one
        # by its presence. `check_artifact_conformance#PHASED` holds the stage to that declaration,
        # and it found this one resuming. Measured 2026-09-28, the same defect three times: the DQ
        # stages resumed on phase 1's output and left the served plane with 0 of 8 relations
        # assessed; `lineage` resumed after a rename and the checklist read T8 0 of 8; and the
        # transform descriptors resumed on views that no longer existed.
        {"name": "transforms", "part": "datasets", "always": True, "produces": "data/transforms/*.yaml", "d": "D15 D6",
         "cmd": [_tool("mac_transforms.py"), str(root)]},
        # AFTER `transforms`, NOT BEFORE IT — moved 2026-09-26, found by deleting a bundle and
        # re-ingesting it from its 12 inputs. `mac_sample` names the TRANSFORM that produces a relation,
        # and as stage 3 (with transforms at stage 6) there were no transform descriptors to read yet, so
        # a FIRST run recorded "no transform descriptor; relation read from table.*" for every relation
        # while a --refresh over the same bundle resolved them all. The first run produced the WORSE
        # artifact, and only a from-scratch rebuild could show it: every bundle in the estate had been
        # refreshed at least once, so every samples.run.json on disk was the good version.
        #
        # Nothing depends on samples running early: it needs the descriptors, which precede it either
        # way, and concept samples need concepts, which come later regardless.        # `--plane all` cuts the relation previews AND, where concepts exist, the concept samples —
        # so it is credited with D11b, which it can always deliver, and D11 only when there is a
        # concept to sample. Crediting it with D11 alone made a stage look like it had satisfied a
        # deliverable that no first run can produce.
        # `produces` MUST NAME EXACTLY WHAT THE STAGE WRITES — not less, and not more. The comment on
        # `descriptors` above records the first direction: a glob naming only one of two planes let
        # resume skip while the other was missing. This is the SECOND direction, measured on the very
        # first split run (2026-09-28): both sample stages claimed `data/samples/*.sample.csv`, so
        # with the sources previews deleted and the served ones intact, `samples-sources` matched its
        # sibling's output and RESUMEd — 0 of 7 landed relations previewed, reported as done. The
        # checklist caught what resume got wrong, which is the whole reason a part has one.
        # `always`, ON THE MANIFEST'S RULING. `mac_artifacts.yaml` declares this kind `re-derived`:
        # a pure function of the warehouse, whose stale copy is indistinguishable from a fresh one
        # by its presence. `check_artifact_conformance#PHASED` holds the stage to that declaration,
        # and it found this one resuming. Measured 2026-09-28, the same defect three times: the DQ
        # stages resumed on phase 1's output and left the served plane with 0 of 8 relations
        # assessed; `lineage` resumed after a rename and the checklist read T8 0 of 8; and the
        # transform descriptors resumed on views that no longer existed.
        {"name": "samples-sources", "part": "sources", "always": True, "produces": "data/samples/*.src.sample.csv",
         "d": "D11b", "cmd": [_tool("mac_sample.py"), str(root), "--plane", "sources"]},
        # PER-ITEM RESUME, because a GLOB CANNOT SEPARATE THE TWO PLANES HERE: served previews are
        # `<stem>.sample.csv` and landed ones `<stem>.src.sample.csv`, and the first pattern matches
        # the second. Found by a full from-scratch import 2026-09-28 — `samples-sources` ran, and
        # `samples-datasets` then RESUMED on its sibling's seven files and wrote none of its own five.
        # This is the third instance of one bug: `produces` must answer for THIS stage's output alone.
        # `produces` WAS ABSENT, so the served preview measured as a phase-1-only artifact even
        # though this stage is what writes it. A stage that declares nothing produces nothing as far
        # as every reader of this table is concerned.
        # `always`, ON THE MANIFEST'S RULING. `mac_artifacts.yaml` declares this kind `re-derived`:
        # a pure function of the warehouse, whose stale copy is indistinguishable from a fresh one
        # by its presence. `check_artifact_conformance#PHASED` holds the stage to that declaration,
        # and it found this one resuming. Measured 2026-09-28, the same defect three times: the DQ
        # stages resumed on phase 1's output and left the served plane with 0 of 8 relations
        # assessed; `lineage` resumed after a rename and the checklist read T8 0 of 8; and the
        # transform descriptors resumed on views that no longer existed.
        {"name": "samples-datasets", "part": "datasets", "always": True, "d": "D11b",
         "produces": "data/samples/*.sample.csv",
         "each": lambda: [[_tool("mac_sample.py"), str(root), "--plane", "datasets"]],
         "missing": lambda: ([[_tool("mac_sample.py"), str(root), "--plane", "datasets"]]
                             if any(not (root / "data" / "samples" / f"{r}.sample.csv").is_file()
                                    for r in relations("datasets")) else [])},
        # `--accept` ON THE LOOKUP CUTTER IS NOT A BILLING DECISION. harvest's help says
        # "materialize/lookups create the own-schema views + name->code registers (DRY-RUN by
        # default, --accept to run the DDL/profiling live)" — the flag means RUN THE PROFILING, and
        # on a local DuckDB file that costs nothing. Treating it as billed left D12 empty on every
        # free run, which the operator saw as "no lookups in console".
        #
        # SO IT IS PASSED ONLY WHEN THE WAREHOUSE IS LOCAL, decided from the bundle's own manifest
        # by the same test the framework's DuckDB seam uses. Against a cloud warehouse the profiling
        # IS billed and the stage stays dry until the operator says otherwise.
        # THE FRAMEWORK'S OWN CUTTER, not harvest's. `harvest --mode lookups` profiles through AWS
        # and on a local DuckDB bundle dies with `botocore NoCredentialsError: Unable to locate
        # credentials` — measured. It predates the connector seam. `mac_lookups` projects the value
        # domains `mac_profile` ALREADY captured onto the descriptors, so it needs no second scan and
        # works for any engine the seam answers for.
        # ONE PER PART, because this stage CONSUMES a hand-off the profiling stage in the SAME part
        # wrote. Tagged datasets-only, `--part sources` ran `mac_profile` (which writes `values:` onto
        # the descriptor) and never the stage that cuts them into a register and pops them — leaving 7
        # of 7 contoso3 source descriptors carrying member lists, one 120 values long. A part that
        # writes a transient must also consume it, or the part cannot be delivered on its own.
        {"name": "lookups-sources", "part": "sources", "produces": "data/lookups/*.csv", "d": "D12",
         "always": True,
         "cmd": [_tool("mac_lookups.py"), str(root), "--plane", "sources"]},
        # `always`, for the same reason its sibling is: BOTH planes cut into data/lookups/, so the glob
        # cannot answer for one of them and this stage resumed on the other's output. Re-cutting is
        # cheap and idempotent — it reads domains already measured onto the descriptors.
        {"name": "lookups-datasets", "part": "datasets", "produces": "data/lookups/*.csv", "d": "D12",
         "always": True,
         "cmd": [_tool("mac_lookups.py"), str(root), "--plane", "datasets"]},
        # ── THE PROMOTION PASS. `mac_descriptors` derives foreign keys from data/references*/ and
        # register pointers from data/lookups/, and BOTH are measured after it first runs — so a
        # single-pass pipeline can never declare them. Its own docstring said "the import pipeline
        # measures references and re-runs this, which REBUILDS them"; the pipeline never did, and the
        # result was that the declared FK set depended on how many times you had run the importer.
        # Measured 2026-09-28: 26 references on contoso4 built incrementally, ZERO from scratch, with
        # `customs_declaration.hs_code -> tariff_schedule.hs_code` measured `real`/`identity`/many:one
        # and declared nowhere.
        #
        # SAFE ONLY BECAUSE EVERY FACT IS NOW RE-DERIVABLE from its own home — roles and keys from the
        # warehouse, FKs from data/references*/, registers from data/lookups/, cardinality from
        # data/profiles/. That was the precondition: a regeneration that WIPED an enrichment is how the
        # register pointers were lost once already, and adding a second pass before closing that hole
        # would have re-created the same defect one stage later.
        #
        # `always`, because its output exists by definition on the second pass.
        {"name": "promote-sources", "part": "sources", "always": True, "d": "D1",
         "produces": "data/sources/*.yaml",
         "cmd": [_tool("mac_descriptors.py"), str(root), "--plane", "sources"]},
        {"name": "promote-datasets", "part": "datasets", "always": True, "d": "D2",
         "produces": "data/datasets/*.yaml",
         "cmd": [_tool("mac_descriptors.py"), str(root), "--plane", "datasets"]},
        # THE CLOSURE MONITOR, and it is OWED — DNA PART 1.8 "closed sets get a register; registers
        # get a monitor", PART 4 step 6 "`warranty: monitored` becomes provable". It is also a
        # REPLACEMENT: moving the member lists off the descriptors and into the registers (operator,
        # 2026-09-26: "these values could be in lookup if necessary?!?!") cut the descriptor plane by
        # 73 % and was right — but the generated suite built its `enumeration` family FROM those
        # lists, so 30 of 86 cases went with them. This reads the register instead, which is where
        # the members now live, and it re-measures against the warehouse, which a static case list
        # never could.
        # BOTH PARTS, because EITHER part can cut a register and DNA 1.8 says a closed set gets a
        # monitor. Tagged datasets-only, the sources part cut 18 registers on contoso3 and monitored
        # none of them — REGISTER-MONITOR went red with "18 register(s) are delivered and
        # acceptance/register_membership_runs.json does not exist". The monitor reads the register
        # directory, which both parts write into, so running it from either is correct and idempotent.
        {"name": "register-monitor", "part": "both", "always": True,
         "produces": "acceptance/register_membership_runs.json",
         "d": "D12b", "cmd": [_tool("check_register_membership.py"), str(root)]},
        # ---- the DQ plane, ALL OF IT BEFORE THE PROJECTION ----------------------------------
        # A measured ORDERING BUG of this file: `dq-findings` was documented as needing to run before
        # `project` and was placed after it, so the projection built the dashboard from a register
        # that did not exist yet and the board came out with 0 findings — the very symptom being
        # fixed. The two suites need only the profiles, so they move up as well, which removes the
        # circularity (findings read the run record) without needing a second pass.
        # ---- the two suites: GENERATED, then EXECUTED. Generating is not testing. -------------
        # `always`, FOR THE SAME REASON `lineage` CARRIES IT: this is a pure RE-DERIVATION over the
        # descriptor planes on disk, and a stale register is indistinguishable from a fresh one by
        # its presence. Measured on contoso5, 2026-09-28, on the first two-part run where DQ was
        # tagged at all: phase 2 RESUMED all three stages on phase 1's output, so the served plane
        # got ZERO properties (0 of 8 relations) and the register still carried eight
        # `DQ-ORPHAN-<landing>` findings saying each landing "is consumed by no transformation" —
        # eight transformations later. Both halves wrong, and the checklist could not see it.
        # DQ BELONGS TO EVERY DELIVERY, NOT TO "ALL". These three carried NO `part`, so `--part
        # sources` AND `--part datasets` both HELD them and the data-quality assessment ran only
        # under `--part all` — which the operator's delivery rule forbids ("1. data sources - FULL
        # COMPLETE APPROVED / 2. datasets - FULL COMPLETE APPROVED"). Measured on contoso5,
        # 2026-09-28: a two-part delivery finished 6 of 6 and 9 of 9 with `data/quality/` ABSENT
        # and `issues: 0`, because no checklist item asks about DQ either. Operator: "where the
        # fuck is now DQ assessment".
        #
        # This is the SECOND stage to be lost this way — `lineage` was untagged for the same reason
        # and the same operator caught it the same day ("if you have dataset then you must have
        # lineage"). An untagged stage is not neutral, it is held by every part that exists.
        #
        # `both`, like `project` and `delivery-check`: the tools enumerate whatever descriptor
        # planes are ON DISK (`for plane in ("datasets", "sources")`), so part 1 assesses the
        # landing plane because that is all there is, and part 2 re-runs over both. Idempotent, so
        # the plane a part did not touch is re-assessed identically.
        {"name": "dq-suite", "part": "both", "always": True, "produces": "acceptance/data_sanity_generated.yaml", "d": "D7a",
         "cmd": [_tool("mac_generate_sanity.py"), str(root)]},
        {"name": "dq-run", "part": "both", "always": True, "produces": "acceptance/data_sanity_generated_runs.json",
         "d": "D7b D7c",
         "suite": "acceptance/data_sanity_generated.yaml"},
        # THE DQ FINDINGS REGISTER, and it must run BEFORE `project`: the console's data-quality
        # board reads `data/quality/dq_dashboard.json`, which the projection builds FROM the register.
        # With no register the board is `{"total": 0, "findings": []}` — "DQ is completely empty",
        # which is what the operator saw while a suite of 86 cases was passing beside it. A suite
        # proves invariants HOLD; a register says what is WRONG and who must rule on it.
        {"name": "dq-findings", "part": "both", "always": True, "produces": "data/quality/data_quality_register.yaml", "d": "D7c",
         "cmd": [_tool("mac_dq_findings.py"), str(root)]},
        # THE MANIFEST'S OWN ACCEPTANCE TEST, and it runs on every delivery deliberately. It seeds
        # each of the five losses of 2026-09-28 as a mutant and asserts a named invariant refuses
        # it. It needs no bundle and no warehouse — it is a guard on the GUARD. `NAME-MATCHES`
        # shipped as a tautology and reported PASS over two deliberately-broken files for as long
        # as it existed; nothing in the estate would have noticed if this had gone the same way.
        {"name": "manifest-acceptance", "part": "both", "always": True, "d": "D1",
         "cmd": [_tool("check_manifest_catches_yesterday.py")]},
        {"name": "delivery-check", "part": "both", "always": True,
         "produces": "acceptance/delivery_consistency_runs.json", "d": "D7c",
         "cmd": [_tool("check_delivery_consistency.py"), str(root)]},
        # `produces` IS THE DELIVERABLE'S OWN SHAPE, not the directory that holds it. As
        # `ontology/concepts` it was satisfied by ANY file in that directory — and the projection
        # writes `ontology/concepts/index.md` there, a generated read-view. Measured on the first
        # --accept ever attempted: the authoring call could not start (a missing model client), the
        # projection ran anyway and wrote index.md, and from then on the stage reported
        # `RESUME — ontology/concepts present` while the same report said `NO D4 all concepts`. One
        # failed attempt permanently blocked every retry, and the contradiction was printed in two
        # lines of the same screen.
        {"name": "concepts", "produces": "ontology/concepts/**/*.yaml", "d": "D4", "billed": True,
         "sdk": ["--mode", "concepts"]},
        # THE CONCEPT DRAW IS ITS OWN STAGE, AND IT RUNS HERE — after the concepts exist.
        #
        # It used to be folded into `samples` at stage 6 as `--plane all`, six stages BEFORE `concepts`,
        # so a concept sample could never be cut in one pass: D11 was structurally unreachable and
        # reported absent on every run with the honest-but-incomplete cause "there are no concepts yet".
        # Found by the operator on a bundle that HAD 19 concepts and no samples: "i have noticed that in
        # the previous version you did not deliver samples".
        #
        # AND IT IS THE DNA'S STEP ZERO, which is what makes the ordering a real defect rather than a
        # tidiness point. PART 4 opens: "Cut a sample per concept BEFORE reviewing a single declaration
        # (P9) ... it is the only artifact that shows what a concept CONTAINS, and on 2026-09-26 it would
        # have caught three wrong declarations that re-reading the YAML did not. Step zero because every
        # step below is a claim about values, and this is the step that shows the values." A pipeline that
        # cannot reach its own step zero in one pass cannot perform the review it prescribes — and the
        # 19 concepts written without it carried 141 inert tokens that reading the YAML did not reveal.
        #
        # It precedes `project` deliberately: the ER model (step 0b) is read AFTER the values are on the
        # table, not before.
        {"name": "concept-samples", "produces": "ontology/samples/*.sample.csv", "d": "D11",
         "cmd": [_tool("mac_sample.py"), str(root), "--plane", "concepts"]},
        # ---- the projection: objects.json, ER, lineage, vocabulary, ontology_quality ----------
        # `--project-anyway` WITH A STATED REASON, because on a first run the ontology plane is
        # empty BY DESIGN and the projection's gate is written to refuse a bundle that does not
        # compile. That gate protects against minting a read view over a BROKEN ontology; it is not
        # meant to withhold the data-plane state an operator needs in order to author one. The flag
        # requires a reason precisely so this is a decision on the record rather than a silent
        # override — and everything the console shows (lineage, the DQ board, the ER model) comes out
        # of this one stage.
        # A PAGE IS PART OF THE DELIVERY, NOT A LATER FAVOUR. Operator, 2026-09-28: "there is one thing
        # which is for sure missing - page overview on all sources" and then "page must be generated
        # alonside ingestion". This stage renders every data-plane page, and it belonged to NEITHER part
        # — so a part could report its checklist complete while the bundle held no readable page at all.
        # Measured on contoso5: the sources checklist read 4 of 4 with ZERO .md files in the bundle. The
        # machine-readable half was delivered and the half a person opens was not.
        #
        # `part: "both"`, because the projector renders the whole data plane from whatever is on disk and
        # is idempotent: the plane a part did not touch re-renders identically. Scoping it per plane would
        # mean splitting a 1050-line renderer, and a second renderer for the same page is the drift this
        # estate keeps paying for.
        # LINEAGE FROM THE ENGINE, AND IT RUNS BEFORE `project`. The comment here said exactly that
        # while the entry sat AFTER it in this list, and the order is the one that executes.
        # Measured on contoso5, 2026-09-28, on a clean two-part delivery: `project` rendered every
        # served page from the lineage of the PREVIOUS part (0 columns), so `data/datasets/*.md`
        # came out with NO lineage section at all, and the projector's own `claims` edges then
        # outranked the 8 measured `feeds` edges this stage wrote a moment later. T8 and T9 both
        # reported complete over that artifact. The projection RENDERS lineage, so lineage has to
        # exist first; and `lineage_graph`'s own precedence rule now makes the outcome independent
        # of this order rather than dependent on it — a defect this deep should not be held shut
        # by a list position alone.
        # LINEAGE IS PART OF THE DATASETS DELIVERY. Operator, 2026-09-28: "if you have dataset then
        # you must have lineage". It was tagged to NO part, so `--part datasets` HELD it and a
        # datasets-only delivery produced a served plane with no column-level provenance at all —
        # the one artifact that answers "where did this number come from". It is a fact about
        # transforms feeding served relations, so it belongs to the part that produces them.
        # `always`, because the artifact is a pure RE-DERIVATION from the warehouse and the transforms,
        # and a stale one is indistinguishable from a fresh one by its presence. Measured 2026-09-28:
        # after the served views were renamed, this stage RESUMED on the old file and the checklist
        # read T8 0 of 8 — the fourth time today a stage skipped on the existence of output that no
        # longer described the bundle.
        {"name": "lineage", "part": "datasets", "always": True,
         "produces": "data/lineage/lineage.json", "d": "D15",
         "cmd": [_tool("mac_lineage.py"), str(root)]},
        # `produces` NAMES EVERYTHING THE PROJECTOR WRITES, not just its headline artifact. It
        # declared `objects.json` alone while also writing every relation page, both plane
        # overviews, the DQ pages, the register pages, the reference projections and the bundle
        # index — so the manifest measured `relation_page` and `plane_overview` as belonging to NO
        # delivery. An under-declared `produces` hides a whole artifact class from the phase it is
        # owed by; an over-declared one lets a stage resume on a sibling's output. Both have
        # happened here, which is why this is a list.
        {"name": "project", "part": "both", "d": "D3 D6 D15", "always": True,
         "produces": ["objects.json", "index.md", "compile.json",
                      "data/sources/*.md", "data/datasets/*.md", "data/transforms/*.md",
                      "data/sources/index.md", "data/datasets/index.md",
                      "data/lookups/*.lookup.md",
                      "data/quality/*.md", "data/quality/dq_dashboard.json",
                      "references/usage_guardrails.md", "references/known_issues/*.md",
                      "ontology/diagnostics.json"],
         "sdk": ["--mode", "project", "--project-anyway",
                 "first run: the ontology plane is empty by design at this stage, and the operator "
                 "needs the projected data-plane state — lineage, the DQ board, the descriptors — in "
                 "order to author concepts from it"]},
        # IT RUNS AFTER `project`, WHICH IS WHAT WRITES THE PAGES. Placed before it, this judged
        # the PREVIOUS run's output: the stage reported PASS and the same command run by hand a
        # minute later refused three pages. That is the fourth ordering defect of this shape in
        # this file — a stage reading what a later stage produces — and the third I have made.
        # THE PAGE'S SHAPE, HELD TO ITS DECLARATION — and it runs on every delivery, which is the
        # difference between doing a thing once and doing it every time. Operator, 2026-09-29:
        # "my question is not if you can do it ONCE ... the question is if you can do it EVERY
        # TIME". Demonstrated the same day: with the renderer deliberately broken,
        # `check_pages_current` reported 9 of 9 pages current and this refused 4 sections.
        {"name": "page-shape", "part": "both", "always": True, "d": "D6",
         "cmd": [_tool("check_page_shape.py"), str(root)]},
        # IT RUNS AFTER `project`, WHICH IS WHAT WRITES THE PAGES IT COUNTS. Placed before it, this
        # measured the PREVIOUS run's output and wrote that into `acceptance/manifest_runs.json`.
        # Invisible on a re-run, because the pages were already there from last time; exposed the
        # first time the bundle was rebuilt from true inputs only — the record claimed
        # `register_page have: 21, missing: [country_name, day_of_week, month_name, year_month]`
        # while all 25 sat on disk. Those four are exactly the registers the DATASETS delivery cut,
        # so the record was one stage stale and said so only on a clean build.
        #
        # THAT IS THE FIFTH ORDERING DEFECT OF THIS SHAPE in this file — a stage reading what a
        # later stage produces — and the operator named the reason it kept hiding: reusing a
        # previous result masks the method that was supposed to produce it.

        # AFTER dq-findings, NOT BEFORE IT. This gate READS the data-quality register —
        # CONCEPT-RELATION asks whether a served relation nobody claims has been DECLINED there — so
        # placed earlier it measured a bundle whose register did not exist yet and reported an
        # inconsistency that was gone by the end of the same run. Measured on contoso3's first full
        # from-scratch import, 2026-09-28: FAIL during the run, 0 failures immediately after it. A gate
        # whose verdict depends on where in the chain it runs is not yet a gate.
        #
        # THE RUN RECORD IS EVIDENCE OF DELIVERY, so the delivery produces it. Found by redeploying
        # contoso5 from nothing: `acceptance/delivery_consistency_runs.json` did not come back, because
        # it is written by `check_delivery_consistency` and NO stage ran it — the file was only ever on
        # disk because a person ran the gate by hand, and the console's Delivery tab reads it.
        # CONFORMANCE RUNS WITH THE DELIVERY, NOT AT COMPILE TIME. Operator, 2026-09-28, on my habit
        # of inventing a convention when I cannot find one: "i cannot stop you doing that. but i can
        # ask you to make checker if for specifig object standard notations and declarations have
        # strictly been followd. if not you have to do it in the second round."
        #
        # THE TIMING IS THE POINT. The served-name rule existed all along and `check_served_name_distinct`
        # enforced it — but only at `project`, so an invented `d_`/`f_`/`b_` scheme survived being
        # designed, built, measured, committed and reported before anything objected. A rule that fires
        # after the work is a record of a mistake; one that fires during it is a guard.
        # A GATE PRODUCES NOTHING, and claiming otherwise is not harmless. This declared
        # `produces: data/datasets/*.yaml` while being strictly read-only, so the served descriptor
        # appeared to have four writers — three real collaborators and a checker. `produces` is the
        # field the manifest derives PHASE from, and a false claim in it puts a kind in a delivery
        # that does not write it.
        {"name": "conformance", "part": "both", "always": True, "d": "D1 D2",
         "cmd": [_tool("check_artifact_conformance.py"), str(root)]},

        # `both`: the bundle resource file describes WHATEVER has been delivered, so each part
        # leaves one that matches its own state. Untagged, it was held by both parts exactly like
        # the DQ stages above.
        # ALWAYS, BECAUSE ITS OUTPUT IS A SUMMARY OF EVERYTHING ELSE. `.mac` describes what the
        # bundle CONTAINS, so it goes stale the moment any other stage writes — and `produces:
        # "*.mac"` made it resume on its own earlier output. Measured 2026-09-29 on a two-part
        # run: the sources delivery wrote 38 components, the datasets delivery then RESUMED on that
        # file ("*.mac present") and the bundle shipped claiming 38 where the real answer was 69 —
        # 8 datasets, 8 transforms and 9 more registers missing from its own description.
        #
        # AND THE CHECKLIST CALLED IT COMPLETE: `resource_description 1 of 1 [OK]`. Presence is not
        # currency, and a stage whose output summarises its siblings can never be judged by whether
        # the file is there.
        {"name": "resources", "part": "both", "produces": "*.mac", "d": "D13 D5", "always": True,
         "cmd": [_tool("mac_resources.py"), str(root)]},
        # ALWAYS, for the same reason `resources` is: the kind declares `lifecycle: re-derived`
        # and a re-derived artifact whose stage RESUMES is a contradiction — a stale suite and a
        # fresh one are indistinguishable by presence. Caught by PHASED the hour the conformance
        # gate started reading the real registry instead of six kinds.
        {"name": "ontology-suite", "produces": "acceptance/ontology_generated.yaml", "d": "D8a",
         "always": True,
         "cmd": [_tool("mac_generate_ontology_tests.py"), str(root)]},
        {"name": "ontology-run", "produces": "acceptance/ontology_generated_runs.json",
         "d": "D8b",
         "suite": "acceptance/ontology_generated.yaml"},
    ]


def classify(returncode: int, out: str, refusals: tuple[str, ...]) -> tuple[str, str]:
    """(kind, line) for ONE call. PURE, and extracted because this precedence is the thing that was
    got wrong twice in one hour.

    First a complete measurement carrying a finding was rendered FAIL — `mac_references` wrote 5 of 5
    files, drew 2 references and reported one relation whose composite key no measurement can declare,
    and the operator's first-run report said FAIL. Then, fixing that, the exit-3 test was placed ahead
    of the refusal test, and `ontology-run`'s "could not run" came back as NEEDS YOU: asking for a
    ruling no decision can give, because the suite declares 0 cases.

    THE PRECEDENCE, and each step earns its place:
      refused       a STATED refusal outranks any exit code — the tool said, in words, what it could
                    not do, and that sentence is better than an integer
      needs_ruling  exit 3: measured completely, and something needs the operator
      failed        anything else non-zero: the tool could not do its job
      ok            zero
    Inline, none of this was reachable from a self-test; every branch here now is.
    """
    tail = [ln for ln in out.splitlines() if ln.strip()]
    lastline = tail[-1][:88] if tail else ""
    if returncode == 0:
        return "ok", lastline
    # EXIT 2 IS THE ESTATE'S OWN WORD FOR "COULD NOT RUN", and it outranks a string match because it
    # is a contract rather than a phrase. `mac-integration-kit/run_gates.sh` states it, every gate in
    # this repo returns it for an empty population, and matching only on WORDS meant a tool that used
    # different ones was called a failure: measured on contoso3's first full from-scratch import,
    # `mac_sample --plane concepts` exited 2 saying "✗ NOT RUN — found no concept ... its verdict is
    # UNKNOWN — not absent", which is a textbook refusal, and the run reported FAIL. A bundle with no
    # ontology cannot sample concepts; that is not a failure, it is the absence of a population.
    if returncode == 2:
        return "refused", next((ln.strip() for ln in reversed(out.splitlines()) if ln.strip()),
                               lastline)[:88]
    if any(mark in out for mark in refusals):
        return "refused", next((ln.strip() for ln in reversed(out.splitlines())
                                if any(m in ln for m in refusals)), lastline)[:88]
    if returncode == 3:
        return "needs_ruling", next((ln.strip() for ln in reversed(out.splitlines())
                                     if ln.startswith("NEEDS RULING")), lastline)[:88]
    # A MISSING DEPENDENCY IS "COULD NOT RUN", NOT "FAILED", and the difference is the operator's next
    # action. Measured on the first --accept ever attempted: the concepts stage reported
    # `FAIL — ModuleNotFoundError: No module named 'langchain_aws'`, which reads as a defect in the
    # bundle or in the stage. Nothing failed. The tool never started, because this machine cannot run
    # it: the authoring path needs a model client that is not installed. "Fix your bundle" and "install
    # a dependency" are different instructions, and a report that gives the first for the second sends
    # an operator looking in the wrong place.
    if any(m in out for m in ("ModuleNotFoundError", "ImportError:", "No module named")):
        missing = next((ln.strip() for ln in reversed(out.splitlines())
                        if "ModuleNotFoundError" in ln or "No module named" in ln), lastline)
        return "unavailable", missing[:88]
    return "failed", lastline


def _run(stage: dict, root: pathlib.Path, a) -> tuple[str, str, str, float]:
    """One stage. RESUME when its output exists, SKIP when billed without --accept."""
    name, t0 = stage["name"], time.time()
    produced = stage.get("produces", "")
    # AN ITERATING STAGE ASKS ITS OWN ITEMS, never the shared glob. See the note on `profiles`.
    # --refresh MEANS ALL ITEMS, and treating it as "still filter to the missing ones" was a
    # measured bug: descriptors were rewritten, every profile already existed, the filter returned
    # an empty list, and the stage reported "nothing to iterate — the stage before it produced
    # nothing". Worse, `mac_profile` is what ADDS the value domains to a descriptor, so the register
    # cutter downstream then wrote 0 registers from descriptors that had just been reset.
    todo: list[list[str]] = []
    # `always` MUST BE HONOURED ON BOTH BRANCHES, and it was honoured on only one. The `elif` below
    # consults it; this branch never did — so every ITERATING stage (`profiles-*`, `samples-*`,
    # `references-*`, `descriptors-*`) silently ignored the flag. Measured 2026-09-29: seven stages
    # were marked `always: True` to stop them serving stale artifacts, the gate confirmed the flag
    # was set, and five of them resumed anyway on the very next run. A flag that is set, reported,
    # and not read is worse than an absent one: everything says the fix is in.
    force = bool(a.refresh or stage.get("always"))
    if "each" in stage:
        todo = stage["each"]() if force else (
            stage["missing"]() if "missing" in stage else stage["each"]()
        )
        if not todo and not force:
            total = len(stage["each"]())
            return (name, "RESUME", f"all {total} item(s) present", 0.0)
    elif produced and not force and _present(root, produced):
        seen = ", ".join(produced) if isinstance(produced, (list, tuple)) else produced
        return (name, "RESUME", f"{seen} present", 0.0)
    if stage.get("billed") and not a.accept:
        return (name, "SKIP", "billed — re-run with --accept", 0.0)

    cmds: list[list[str]] = []
    if "cmd" in stage:
        cmds = [stage["cmd"]]
    elif "each" in stage:
        cmds = todo
        if not cmds:
            return (name, "CANNOT", "nothing to iterate — the stage before it produced nothing",
                    time.time() - t0)
    elif "sdk" in stage:
        sdk = _sdk_root()
        if sdk is None:
            return (name, "CANNOT", "no sdk checkout found for the billed authoring",
                    time.time() - t0)
        accept = a.accept or (stage.get("free_when_local") and _is_local(root))
        cmds = [[sys.executable, "-m", "sdk.cli.harvest", "--content-root", str(root),
                 *stage["sdk"], *(["--accept"] if accept else [])]]
    elif "suite" in stage:
        suite = root / stage["suite"]
        if not suite.is_file():
            return (name, "CANNOT", f"{stage['suite']} was not generated", time.time() - t0)
        db = _duckdb_file(root)
        if db is None:
            return (name, "CANNOT", "the suite needs an engine and this bundle declares no "
                                    "DuckDB database", time.time() - t0)
        cmds = [[_tool("run_suite.py"), "--bundle", str(root), "--suite", stage["suite"],
                 "--engine", "duckdb", "--db", str(db)]]

    #: A TOOL THAT REFUSES IS NOT A TOOL THAT BROKE, and the report must not conflate them. Each
    #: of these is a producer declining for a STATED reason, and every one was met on a real run:
    #:
    #:   "could not run"      the ontology suite declares 0 properties, because it is generated FROM
    #:                        the concepts and there are none — "0 declared is not 0 failures", which
    #:                        is this estate's own rule about a PASS without its denominator
    #:   "--project-anyway"   the projection gate refusing a non-conformant bundle: correct while the
    #:                        ontology plane is still empty
    #:   "REFUSED:" / "SKIP:" a gate saying it has nothing to judge
    #:
    #: Calling any of them FAIL would teach an operator to ignore the word.
    refusals = ("could not run", "--project-anyway", "REFUSED:", "SKIP:", "NOTHING TO MEASURE")
    fails, refused, lastline = 0, 0, ""
    needs_ruling = unavailable = 0
    for cmd in cmds:
        cwd = _sdk_root() if "sdk" in stage else None
        r = subprocess.run([sys.executable, *cmd] if cmd[0].endswith(".py") else cmd,
                           capture_output=True, text=True, timeout=1800,
                           cwd=str(cwd) if cwd else None)
        out = (r.stdout or "") + (r.stderr or "")
        kind, lastline = classify(r.returncode, out, refusals)
        if kind == "unavailable":
            unavailable += 1
        elif kind == "refused":
            refused += 1
        elif kind == "needs_ruling":
            needs_ruling += 1
        elif kind == "failed":
            fails += 1
    secs = time.time() - t0
    if fails:
        return (name, "FAIL", f"{fails} of {len(cmds)} call(s) failed — {lastline}", secs)
    if unavailable:
        return (name, "CANNOT", f"this machine cannot run the stage — {lastline}", secs)
    if needs_ruling:
        return (name, "NEEDS YOU", lastline, secs)
    if refused:
        return (name, "NEEDS YOU" if stage.get("needs_human") else "CANNOT",
                stage.get("needs_human") or lastline, secs)
    return (name, "OK", lastline, secs)


# ══════════════════════════════════════════════════════════════════════════════════════════════
# THE STATE REPORT — D14
# ══════════════════════════════════════════════════════════════════════════════════════════════
def _report(root: pathlib.Path, a) -> int:
    print("\nSTATE — what an operator can continue tuning from\n")
    _warn_plane_collision(root)
    absent = []
    for d in DELIVERABLES:
        if "probe" in d:
            got, note = _probe(root, d["probe"])
        else:
            files = _matches(root, d["glob"])
            got, note = bool(files), f"{len(files)} file(s)" if files else ""
        mark = "YES" if got else "NO "
        print(f"  {mark}  {d['id']:4} {d['what']:34} {note}")
        if not got:
            absent.append(d)

    if not absent:
        print("\n  FULL STATE — every deliverable is present.")
        return 0
    print(f"\n  {len(absent)} DELIVERABLE(S) ABSENT, and the reason for each — so none of them has "
          f"to be asked for:\n")
    for d in absent:
        print(f"    {d['id']:4} {d['what']}\n         {_why(root, d, a)}")
    return 1


def _warn_plane_collision(root: pathlib.Path) -> None:
    """Say it out loud when a stem names a relation on BOTH planes.

    `mac_profile` resolves a bare stem by searching data/datasets before data/sources, so a collision
    means the SOURCES relation is never profiled and D9 silently reports half the descriptors' worth.
    Measured on the first vanilla bundle: 16 descriptors, 8 profiles. A wrong number an operator cannot
    see is worse than a missing one.
    """
    served = {p.stem for p in (root / "data" / "datasets").glob("*.yaml")}
    sources = {p.stem for p in (root / "data" / "sources").glob("*.yaml")}
    both = sorted(served & sources)
    if not both:
        return
    prof = {p.stem for p in (root / "data" / "profiles").glob("*.yaml")}
    print(f"  ! PLANE NAME COLLISION — {len(both)} stem(s) name a relation on BOTH planes: "
          f"{', '.join(both[:6])}{' …' if len(both) > 6 else ''}\n"
          f"    `mac_profile` is addressed by bare stem and searches data/datasets first, so for each "
          f"of these the SOURCES relation is NOT profiled: "
          f"{len(served) + len(sources)} descriptor(s) -> {len(prof)} profile(s).\n"
          f"    Harmless where the two are a 1:1 passthrough (identical by construction); WRONG the "
          f"moment one is curated, because the sources reference plane reads its key from the profile.\n")


def _why(root: pathlib.Path, d: dict, a) -> str:
    """The REASON a deliverable is absent. Naming it is the whole point of the report."""
    if d["id"] == "D4" and not a.accept:
        return ("concept authoring is BILLED and --accept was not passed. It searches the whole "
                "relation inventory for business notions (M:N, never per table) and writes "
                "status: draft.")
    if d["id"] in ("D3", "D6") and not _matches(root, "data/references*/*.yaml"):
        return ("the ER model is projected FROM the referential structure, and no reference was "
                "measured — check that descriptors declare a key (mac_references READS the key "
                "and will not derive one).")
    if d["id"] in ("D8", "D11") and not _matches(root, "ontology/concepts/**/*.yaml"):
        return "generated from the concepts, and there are none yet (see D4)."
    if d["id"] == "D7" and not _matches(root, "data/profiles/*.yaml"):
        return "generated FROM the profile, and the measurement plane is empty (see D9)."
    if d["id"] == "D9" and not _matches(root, "data/datasets/*.yaml"):
        return "a profile needs a descriptor to profile against (see D2)."
    if d["id"] == "D12":
        if not _matches(root, "data/datasets/*.yaml"):
            return "a register is cut from a descriptor's captured domain, and there are none (D2)."
        return ("no column carries a captured value domain: `mac_profile` captures one only for a "
                "column that is BOUNDED and ENUMERABLE, so a bundle of continuous measures has no "
                "register to cut.")
    if d["id"] in ("D3", "D6"):
        if not _matches(root, "ontology/concepts/**/*.yaml"):
            return ("the projection GATE refuses a bundle with no ontology plane, which is correct "
                    "while there are no concepts: it will not mint a read view over a bundle that "
                    "does not compile. Both come with D4.")
        return ("the projection refused — run it directly to see the compiler's findings: "
                "python -m sdk.cli.harvest --content-root <root> --mode project")
    if d["id"] == "D5":
        return ("the SME ledger is projected from the questions the ONTOLOGY raises "
                "(concept open_questions + the data-quality register), so it is empty until D4 "
                "exists and the register has been reconciled.")
    if d["id"] in ("D8a", "D8b") and not _matches(root, "ontology/concepts/**/*.yaml"):
        return ("the ontology suite is RENDERED from the concepts, so it declares 0 cases and "
                "run_suite refuses it — \"0 declared is not 0 failures\". Comes with D4.")
    if d["id"] == "D7c":
        return ("the run record carries no per-case results, or the findings register has not been "
                "projected — `project` writes data/quality/dq_dashboard.json from the register.")
    if d["id"] == "D6":
        return ("mac_to_mermaid.py / mac_to_graph.py are not yet stages of this run — the ER (D3) "
                "and lineage (D15) projections are.")
    if d["id"] == "D15":
        return ("`mac_lineage` reads the warehouse's own view definitions — if it found none, the "
                "served relations are base TABLES and their lineage lives in the transforms that "
                "built them, not in the engine.")
    if d["id"] == "D4b":
        return "edges are authored by the same billed stage as the concepts (see D4)."
    return "the stage above reported FAIL or CANNOT — its last line says why."


def _probe(root: pathlib.Path, kind: str) -> tuple[bool, str]:
    """Read what was actually produced, rather than trusting that a stage ran.

    THE SUITE PROBES COME FIRST, and that ordering is a measured bug of this file: they were placed
    AFTER the `objects.json` guard below, so on a bundle whose projection had refused they returned
    "absent" without ever looking. The report then said D7a NO — 0 cases — for a suite holding 10
    properties with a tally of 10 PASS. A probe that answers about a file it never opened is worse
    than no probe: every other line of this report would have been believed too.
    """
    if kind == "lineage_measured":
        return _lineage(root)
    if kind in ("dq_cases", "ont_cases"):
        return _suite_cases(root, kind)
    if kind in ("dq_results", "ont_results"):
        return _suite_results(root, kind)
    import json
    f = root / "objects.json"
    if not f.is_file():
        return False, ""
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False, "objects.json is unreadable"
    if kind == "er":
        best = 0
        for key in ("er_model", "er_model_served"):
            m = doc.get(key) or {}
            best = max(best, len((m.get("entities") or [])))
        return best > 0, f"{best} entit(ies)" if best else "0 entities — projected but EMPTY"
    # THE ONE ARTIFACT, not `objects.json#lineage_graph` — retired 2026-09-28 as the third home
    # for this graph. A probe still reading the retired address reports "0 nodes" on a bundle whose
    # chain is complete, which is a false NOT-DELIVERED and exactly the failure mode this whole
    # collapse was about.
    import json as _j
    f = root / "data" / "lineage" / "lineage.json"
    if not f.is_file():
        return False, "data/lineage/lineage.json absent"
    try:
        g = _j.loads(f.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return False, "the lineage artifact is unreadable"
    n, e = len(g.get("nodes") or []), len(g.get("edges") or [])
    return bool(n and e), (f"{n} node(s), {e} edge(s)" if n and e
                           else f"{n} node(s) and {e} edge(s) — projected but EMPTY")


# ══════════════════════════════════════════════════════════════════════════════════════════════
#: The two generated suites, by deliverable prefix.
_SUITES = {
    "dq": ("acceptance/data_sanity_generated.yaml", "acceptance/data_sanity_generated_runs.json"),
    "ont": ("acceptance/ontology_generated.yaml", "acceptance/ontology_generated_runs.json"),
}


def _lineage(root: pathlib.Path) -> tuple[bool, str]:
    """The lineage MEASURED from the warehouse, plus the projection's own graph when it exists."""
    import json
    f = root / "data" / "lineage" / "lineage.json"
    if not f.is_file():
        return False, ""
    try:
        c = (json.loads(f.read_text(encoding="utf-8")) or {}).get("counts") or {}
    except Exception:  # noqa: BLE001
        return False, "the lineage artifact is unreadable"
    if not c.get("edges"):
        return False, "0 edges — measured but EMPTY"
    # ONE ARTIFACT, SO ONE REPORT. This used to read `objects.json#lineage_graph` as well and print
    # both — "console graph: N nodes, M edges" — because the console rendered a DIFFERENT file from
    # the one measured here, and reporting only this one was how "lineage delivered" got claimed
    # over an empty view. That second home is retired; the console reads this file now, so a second
    # figure would be the same figure twice.
    #
    # WHICH HALVES ARE PRESENT IS THE THING WORTH SAYING. Both producers write here and either may
    # not have run: a `measured` of False means the warehouse was never read, and a `grounds` count
    # of zero on a bundle with concepts means the projector has not folded them in.
    by_kind = c.get("edges_by_kind") or {}
    halves = ", ".join(f"{k} {v}" for k, v in sorted(by_kind.items())) or "no edge kinds"
    return True, (f"{c.get('source')} source(s), {c.get('lookup')} register(s), "
                  f"{c.get('dataset')} dataset(s), {c.get('concept')} concept(s); "
                  f"{c.get('edges')} edge(s) [{halves}]; "
                  f"{c.get('columns_with_a_stated_source')} of {c.get('columns')} column(s) traced")


def _suite_cases(root: pathlib.Path, kind: str) -> tuple[bool, str]:
    """HOW MANY CASES the suite declares. A suite with none has asserted nothing, and "the file
    exists" is exactly the answer this estate refuses elsewhere: never a PASS without its
    denominator."""
    import yaml
    suite = root / _SUITES[kind.split("_")[0]][0]
    if not suite.is_file():
        return False, ""
    try:
        doc = yaml.safe_load(suite.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return False, "the suite is unreadable"
    n = len(doc.get("properties") or [])
    return n > 0, f"{n} case(s)" if n else "0 cases — GENERATED BUT EMPTY, so it can prove nothing"


def _suite_results(root: pathlib.Path, kind: str) -> tuple[bool, str]:
    """WHAT THE RUN FOUND, per case — the tally, not the file. Plus the DQ findings register, which
    is the artifact an operator actually acts on."""
    import json
    prefix = kind.split("_")[0]
    rec = root / _SUITES[prefix][1]
    if not rec.is_file():
        return False, ""
    try:
        doc = json.loads(rec.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False, "the run record is unreadable"
    results = doc.get("results") or []
    tally = doc.get("tally") or {}
    if not results:
        return False, "the record carries NO per-case results — it ran and found nothing to say"
    worst = ", ".join(f"{k} {v}" for k, v in sorted(tally.items()) if v) or f"{len(results)} cases"
    extra = ""
    if prefix == "dq":
        reg = root / "data" / "quality" / "data_quality_register.yaml"
        dash = root / "data" / "quality" / "dq_dashboard.json"
        extra = "  · " + _dq_board(reg, dash)
    return True, f"{len(results)} case(s) · {worst}{extra}"


def _dq_board(register: pathlib.Path, dashboard: pathlib.Path) -> str:
    """What the console's data-quality board will SHOW. The register is the source; the dashboard is
    what the page reads, and a register the projection has not picked up yet shows as empty."""
    import json
    if not register.is_file():
        return "NO findings register — the DQ board will be empty"
    if not dashboard.is_file():
        return "register present, DASHBOARD NOT PROJECTED — the board reads the dashboard"
    try:
        stats = (json.loads(dashboard.read_text(encoding="utf-8")) or {}).get("stats") or {}
    except Exception:  # noqa: BLE001
        return "the dashboard is unreadable"
    total = stats.get("total") or 0
    if not total:
        return "dashboard projected with 0 findings — re-project after raising them"
    sev = stats.get("by_severity") or {}
    return (f"board: {total} finding(s) ("
            + ", ".join(f"{v} {k}" for k, v in sev.items() if v) + ")")


def _tool(name: str) -> str:
    return str(HERE / name)


def _sdk_root() -> pathlib.Path | None:
    """The first LIVE checkout carrying the authoring CLI. A frozen repository is never chosen.

    A frozen repo is one whose own pre-commit hook refuses writes, which is how this estate marks a
    checkout as reference-only after migrating its contents away. Running a billed stage out of one
    means running code nobody can fix, and the drift it caused is measurable: 415 lines between the
    two copies of harvest.py.
    """
    for p in SDK_ROOTS:
        if not (p / "sdk" / "cli" / "harvest.py").is_file():
            continue
        if _frozen(p):
            print(f"  ! SKIPPING {p.name}: its pre-commit hook declares it REFERENCE ONLY, so the "
                  f"code there is code nobody can fix. Looking for a live checkout instead.")
            continue
        return p
    return None


def _frozen(repo: pathlib.Path) -> bool:
    hook = repo / ".git" / "hooks" / "pre-commit"
    if not hook.is_file():
        return False
    try:
        return "REFERENCE ONLY" in hook.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def _matches(root: pathlib.Path, pattern: str) -> list[pathlib.Path]:
    return [p for p in root.glob(pattern) if p.is_file()]


def _present(root: pathlib.Path, pattern: str | list[str]) -> bool:
    """Is a stage's output there? A STAGE THAT WRITES SEVERAL PLANES IS PRESENT ONLY WHEN ALL OF THEM
    ARE — `all`, never `any`. With `any`, a stage whose sources plane was deleted and whose datasets
    plane survived reported RESUME and left D1 missing for the rest of the run: resume answered about
    a subset and said nothing about it. This is the same shape as the reference-plane masking bug."""
    if isinstance(pattern, (list, tuple)):
        return all(_present(root, one) for one in pattern)
    if any(ch in pattern for ch in "*?"):
        return bool(_matches(root, pattern))
    p = root / pattern
    return p.is_dir() and any(p.iterdir()) if p.is_dir() else p.is_file()


def _is_local(root: pathlib.Path) -> bool:
    """Is this bundle's warehouse a LOCAL file? Then profiling it is free.

    Decided from the bundle's own manifest, by the same test the framework's DuckDB seam uses — not
    from a list of connector names kept here, which would go stale the day a second local engine
    appears.
    """
    try:
        sys.path.insert(0, str(HERE))
        import duckdb_seam
        return duckdb_seam.connection_of(root) is not None
    except Exception:  # noqa: BLE001 - unable to tell means NOT free
        return False


def _duckdb_file(root: pathlib.Path) -> pathlib.Path | None:
    try:
        import yaml
        doc = yaml.safe_load((root / "connection.yaml").read_text(encoding="utf-8")) or {}
        db = (doc.get("config") or {}).get("database")
        if not db:
            return None
        got = (root / str(db)).resolve()
        return got if got.is_file() else None
    except Exception:  # noqa: BLE001
        return None


if __name__ == "__main__":
    sys.exit(main())
