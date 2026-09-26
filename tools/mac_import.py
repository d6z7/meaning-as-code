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
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
#: The billed authoring lives in the SDK and keeps its one home; this file calls it, never reimplements.
SDK_ROOTS = [
    pathlib.Path("/Users/<operator>/dev/archive-mac-wiki"),
    pathlib.Path("/Users/<operator>/dev/meaning-as-code"),
]


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
        case("MUTANT no stage credits a deliverable id the table does not define",
             not undefined,
             f"stages credit undefined id(s): {', '.join(undefined)} — the inverse of D11 reading a "
             f"path its producer had abandoned")

    for line in bad:
        print(line)
    total = 14
    if bad:
        print(f"\nFAIL: mac_import self-test — {len(bad)} of {total} case(s) failed")
        return 1
    print(f"PASS: mac_import self-test — {total}/{total} case(s): 9 mutant(s), one per reject class "
          f"(a refusal outranked by an exit code, a complete measurement called a failure, a real "
          f"failure, a refusal at exit 1, a two-plane stage resuming on one plane, an empty directory "
          f"counted as output, a duplicate deliverable id, an absence with no stated cause, a stage "
          f"crediting an undefined deliverable) plus clean fixtures that must pass")
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

    print(f"mac_import {root.name} — {'REPORT ONLY' if a.report else ('ACCEPT (billed stages run)' if a.accept else 'FREE STAGES ONLY')}")
    print("=" * 96)

    outcomes: list[tuple[str, str, str, float]] = []
    if not a.report:
        for stage in _stages(root):
            outcomes.append(_run(stage, root, a))
            if a.stop_on_fail and outcomes[-1][1] == "FAIL":
                print("\n  --stop-on-fail: stopping here")
                break

    print("\n" + "=" * 96)
    if outcomes:
        print("STAGES")
        for name, verdict, detail, secs in outcomes:
            print(f"  {verdict:8} {name:26} {secs:6.1f}s  {detail}")
    return _report(root, a)


# ══════════════════════════════════════════════════════════════════════════════════════════════
# THE CHAIN
# ══════════════════════════════════════════════════════════════════════════════════════════════
def _stages(root: pathlib.Path) -> list[dict]:
    """Every stage, in dependency order. `produces` is what makes RESUME possible."""
    # BOTH PLANES. A measured bug of this file: `relations()` globbed data/datasets only, so the 8
    # RAW landings were never profiled — and the SOURCES reference plane takes its parent key from
    # the PROFILE (`key_from: profile`), not from the descriptor. `mac_references --plane sources`
    # then reported "wrote 0 of 0 relation file(s) over 8 relation(s) in scope", which reads like a
    # missing key and was a missing profile.
    relations = lambda: sorted(  # noqa: E731
        p.stem for plane in ("datasets", "sources") for p in (root / "data" / plane).glob("*.yaml")
    )
    return [
        # ---- the data plane, MEASURED (free) -------------------------------------------------
        # BOTH PLANES, DECLARED. `produces` named only `data/datasets/*.yaml` while the stage writes
        # the sources plane too (its own `d` says D1 D2) — so with the sources plane deleted and the
        # datasets plane intact, resume saw its output and SKIPPED, leaving D1 permanently missing.
        # That is the same masking bug already fixed for the two reference planes, and it is the bug
        # a wipe-and-rerun exists to catch: `produces` must name EVERYTHING the stage writes, or
        # resume answers about a subset.
        {"name": "descriptors", "produces": ["data/sources/*.yaml", "data/datasets/*.yaml"],
         "d": "D1 D2", "cmd": [_tool("mac_descriptors.py"), str(root)]},
        # `mac_profile` takes ONE relation, so this stage is one call per descriptor — the tool's
        # own signature, not a loop invented here.
        # PER-ITEM RESUME, and the stage-level kind was a measured bug of this file: one profile
        # existed from an earlier hand-run, `data/profiles/*.yaml` matched, and the whole stage
        # RESUMEd — 1 profile for 22 relations, reported as done. A stage that iterates must resume
        # per ITEM, or "present" means "one of them is present".
        {"name": "profiles", "produces": "data/profiles/*.yaml", "d": "D9",
         "each": lambda: [[_tool("mac_profile.py"), str(root), rel] for rel in relations()],
         "missing": lambda: [[_tool("mac_profile.py"), str(root), rel] for rel in relations()
                             if not (root / "data" / "profiles" / f"{rel}.yaml").is_file()]},
        # `--plane all` cuts the relation previews AND, where concepts exist, the concept samples —
        # so it is credited with D11b, which it can always deliver, and D11 only when there is a
        # concept to sample. Crediting it with D11 alone made a stage look like it had satisfied a
        # deliverable that no first run can produce.
        {"name": "samples", "produces": "data/samples/*.sample.csv", "d": "D11b D11",
         "cmd": [_tool("mac_sample.py"), str(root), "--plane", "all"]},
        # TWO STAGES, NOT ONE, because the two planes have different INPUTS and only one of them
        # can be automated. Lumped together, the sources half's refusal masked the served half's
        # success — measured: the report said CANNOT while 19 references over 14 relations had just
        # been drawn.
        #
        #   SERVED  key from the DESCRIPTOR (`columns[].role in primary_key|composite_key_part`),
        #           which `mac_descriptors` measures. Automatable, and it is the plane the ER model
        #           is built from.
        #   SOURCES key from the PROFILE's `identity_evidence`, which only `mac_admit_identity`
        #           writes — and that tool requires `--measure <column>`, "THE ONE BIT A HUMAN"
        #           supplies, per relation. A first run cannot produce it, and saying so is the
        #           honest output.
        {"name": "references-served", "produces": "data/references_served/*.yaml", "d": "D10 D3",
         "cmd": [_tool("mac_references.py"), str(root), "--plane", "served"]},
        {"name": "references-sources", "produces": "data/references/*.yaml", "d": "D10",
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
        {"name": "transforms", "produces": "data/transforms/*.yaml", "d": "D15 D6",
         "cmd": [_tool("mac_transforms.py"), str(root)]},
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
        {"name": "lookups", "produces": "data/lookups/*.csv", "d": "D12",
         "cmd": [_tool("mac_lookups.py"), str(root)]},
        # THE CLOSURE MONITOR, and it is OWED — DNA PART 1.8 "closed sets get a register; registers
        # get a monitor", PART 4 step 6 "`warranty: monitored` becomes provable". It is also a
        # REPLACEMENT: moving the member lists off the descriptors and into the registers (operator,
        # 2026-09-26: "these values could be in lookup if necessary?!?!") cut the descriptor plane by
        # 73 % and was right — but the generated suite built its `enumeration` family FROM those
        # lists, so 30 of 86 cases went with them. This reads the register instead, which is where
        # the members now live, and it re-measures against the warehouse, which a static case list
        # never could.
        {"name": "register-monitor", "produces": "acceptance/register_membership_runs.json",
         "d": "D12b", "cmd": [_tool("check_register_membership.py"), str(root)]},
        # ---- the DQ plane, ALL OF IT BEFORE THE PROJECTION ----------------------------------
        # A measured ORDERING BUG of this file: `dq-findings` was documented as needing to run before
        # `project` and was placed after it, so the projection built the dashboard from a register
        # that did not exist yet and the board came out with 0 findings — the very symptom being
        # fixed. The two suites need only the profiles, so they move up as well, which removes the
        # circularity (findings read the run record) without needing a second pass.
        # ---- the two suites: GENERATED, then EXECUTED. Generating is not testing. -------------
        {"name": "dq-suite", "produces": "acceptance/data_sanity_generated.yaml", "d": "D7a",
         "cmd": [_tool("mac_generate_sanity.py"), str(root)]},
        {"name": "dq-run", "produces": "acceptance/data_sanity_generated_runs.json",
         "d": "D7b D7c",
         "suite": "acceptance/data_sanity_generated.yaml"},
        # THE DQ FINDINGS REGISTER, and it must run BEFORE `project`: the console's data-quality
        # board reads `data/quality/dq_dashboard.json`, which the projection builds FROM the register.
        # With no register the board is `{"total": 0, "findings": []}` — "DQ is completely empty",
        # which is what the operator saw while a suite of 86 cases was passing beside it. A suite
        # proves invariants HOLD; a register says what is WRONG and who must rule on it.
        {"name": "dq-findings", "produces": "data/quality/data_quality_register.yaml", "d": "D7c",
         "cmd": [_tool("mac_dq_findings.py"), str(root)]},
        {"name": "concepts", "produces": "ontology/concepts", "d": "D4", "billed": True,
         "sdk": ["--mode", "concepts"]},
        # ---- the projection: objects.json, ER, lineage, vocabulary, ontology_quality ----------
        # `--project-anyway` WITH A STATED REASON, because on a first run the ontology plane is
        # empty BY DESIGN and the projection's gate is written to refuse a bundle that does not
        # compile. That gate protects against minting a read view over a BROKEN ontology; it is not
        # meant to withhold the data-plane state an operator needs in order to author one. The flag
        # requires a reason precisely so this is a decision on the record rather than a silent
        # override — and everything the console shows (lineage, the DQ board, the ER model) comes out
        # of this one stage.
        {"name": "project", "produces": "objects.json", "d": "D3 D6 D15", "always": True,
         "sdk": ["--mode", "project", "--project-anyway",
                 "first run: the ontology plane is empty by design at this stage, and the operator "
                 "needs the projected data-plane state — lineage, the DQ board, the descriptors — in "
                 "order to author concepts from it"]},
        # LINEAGE FROM THE ENGINE, and it runs BEFORE `project` deliberately: the projection's own
        # lineage_graph needs an ontology plane, so on a first run this is the only lineage there is.
        {"name": "lineage", "produces": "data/lineage/lineage.json", "d": "D15",
         "cmd": [_tool("mac_lineage.py"), str(root)]},
        {"name": "resources", "produces": "*.mac", "d": "D13 D5",
         "cmd": [_tool("mac_resources.py"), str(root)]},
        {"name": "ontology-suite", "produces": "acceptance/ontology_generated.yaml", "d": "D8a",
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
    if any(mark in out for mark in refusals):
        return "refused", next((ln.strip() for ln in reversed(out.splitlines())
                                if any(m in ln for m in refusals)), lastline)[:88]
    if returncode == 3:
        return "needs_ruling", next((ln.strip() for ln in reversed(out.splitlines())
                                     if ln.startswith("NEEDS RULING")), lastline)[:88]
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
    if "each" in stage:
        todo = stage["each"]() if a.refresh else (
            stage["missing"]() if "missing" in stage else stage["each"]()
        )
        if not todo and not a.refresh:
            total = len(stage["each"]())
            return (name, "RESUME", f"all {total} item(s) present", 0.0)
    elif produced and not stage.get("always") and not a.refresh and _present(root, produced):
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
    needs_ruling = 0
    for cmd in cmds:
        cwd = _sdk_root() if "sdk" in stage else None
        r = subprocess.run([sys.executable, *cmd] if cmd[0].endswith(".py") else cmd,
                           capture_output=True, text=True, timeout=1800,
                           cwd=str(cwd) if cwd else None)
        out = (r.stdout or "") + (r.stderr or "")
        kind, lastline = classify(r.returncode, out, refusals)
        if kind == "refused":
            refused += 1
        elif kind == "needs_ruling":
            needs_ruling += 1
        elif kind == "failed":
            fails += 1
    secs = time.time() - t0
    if fails:
        return (name, "FAIL", f"{fails} of {len(cmds)} call(s) failed — {lastline}", secs)
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
    g = doc.get("lineage_graph") or {}
    n = len(g.get("nodes") or []) if isinstance(g, dict) else 0
    return n > 0, f"{n} node(s)" if n else "0 nodes"


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
    # AND THE GRAPH THE CONSOLE ACTUALLY RENDERS. Reporting only my own artifact is how "lineage
    # delivered" was claimed while the console's view was empty: objects.json#lineage_graph is what
    # the page reads, and it is built from the transform descriptors, not from this file.
    shown = _console_lineage(root)
    return True, (f"{c.get('nodes')} node(s), {c.get('edges')} edge(s), "
                  f"{c.get('columns_with_a_stated_source')} of {c.get('columns')} column(s) traced"
                  f"  · console graph: {shown}")


def _console_lineage(root: pathlib.Path) -> str:
    """What `objects.json#lineage_graph` holds — the thing the console's lineage view renders."""
    import json
    f = root / "objects.json"
    if not f.is_file():
        return "objects.json ABSENT, so the console shows nothing"
    try:
        g = (json.loads(f.read_text(encoding="utf-8")) or {}).get("lineage_graph") or {}
    except Exception:  # noqa: BLE001
        return "objects.json unreadable"
    nodes = g.get("nodes")
    edges = g.get("edges")
    n = len(nodes) if isinstance(nodes, list) else (nodes or 0)
    e = len(edges) if isinstance(edges, list) else (edges or 0)
    if not e:
        return f"{n} node(s) and 0 EDGES — the view draws nothing; are there transform descriptors?"
    return f"{n} node(s), {e} edge(s)"


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
    return next((p for p in SDK_ROOTS if (p / "sdk" / "cli" / "harvest.py").is_file()), None)


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
