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
    {"id": "D11", "what": "sample per concept", "glob": "data/samples/concepts/*.csv"},
    {"id": "D12", "what": "value registers", "glob": "data/lookups/*.csv"},
    {"id": "D4", "what": "all concepts", "glob": "ontology/concepts/**/*.yaml"},
    {"id": "D4b", "what": "edges", "glob": "ontology/edges.yaml"},
    {"id": "D3", "what": "ER model (actual state)", "probe": "er"},
    {"id": "D6", "what": "lineage diagram", "probe": "lineage"},
    {"id": "D5", "what": "SME questions", "glob": "ontology/SME-QUESTIONS.md"},
    {"id": "D13", "what": "resource description", "glob": "*.mac"},
    {"id": "D7", "what": "data quality tests EXECUTED",
     "glob": "acceptance/data_sanity_generated_runs.json"},
    {"id": "D8", "what": "ontology quality tests EXECUTED",
     "glob": "acceptance/ontology_generated_runs.json"},
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root")
    ap.add_argument("--accept", action="store_true",
                    help="run the BILLED authoring stages too (concepts)")
    ap.add_argument("--report", action="store_true", help="produce nothing; print the state")
    ap.add_argument("--refresh", action="store_true", help="re-run stages whose output exists")
    ap.add_argument("--stop-on-fail", action="store_true")
    a = ap.parse_args(argv)

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
        {"name": "descriptors", "produces": "data/datasets/*.yaml", "d": "D1 D2",
         "cmd": [_tool("mac_descriptors.py"), str(root)]},
        # `mac_profile` takes ONE relation, so this stage is one call per descriptor — the tool's
        # own signature, not a loop invented here.
        # PER-ITEM RESUME, and the stage-level kind was a measured bug of this file: one profile
        # existed from an earlier hand-run, `data/profiles/*.yaml` matched, and the whole stage
        # RESUMEd — 1 profile for 22 relations, reported as done. A stage that iterates must resume
        # per ITEM, or "present" means "one of them is present".
        {"name": "profiles", "produces": "data/profiles/*.yaml", "d": "D9",
         "each": lambda: [[_tool("mac_profile.py"), str(root), rel] for rel in relations()
                          if not (root / "data" / "profiles" / f"{rel}.yaml").is_file()],
         "per_item": lambda: len(relations())},
        {"name": "samples", "produces": "data/samples/*.csv", "d": "D11",
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
        {"name": "lookups", "produces": "data/lookups/*.csv", "d": "D12",
         "sdk": ["--mode", "lookups"]},
        {"name": "concepts", "produces": "ontology/concepts", "d": "D4", "billed": True,
         "sdk": ["--mode", "concepts"]},
        # ---- the projection: objects.json, ER, lineage, vocabulary, ontology_quality ----------
        {"name": "project", "produces": "objects.json", "d": "D3 D6", "always": True,
         "sdk": ["--mode", "project"]},
        {"name": "resources", "produces": "*.mac", "d": "D13 D5",
         "cmd": [_tool("mac_resources.py"), str(root)]},
        # ---- the two suites: GENERATED, then EXECUTED. Generating is not testing. -------------
        {"name": "dq-suite", "produces": "acceptance/data_sanity_generated.yaml", "d": "D7",
         "cmd": [_tool("mac_generate_sanity.py"), str(root)]},
        {"name": "dq-run", "produces": "acceptance/data_sanity_generated_runs.json", "d": "D7",
         "suite": "acceptance/data_sanity_generated.yaml"},
        {"name": "ontology-suite", "produces": "acceptance/ontology_generated.yaml", "d": "D8",
         "cmd": [_tool("mac_generate_ontology_tests.py"), str(root)]},
        {"name": "ontology-run", "produces": "acceptance/ontology_generated_runs.json", "d": "D8",
         "suite": "acceptance/ontology_generated.yaml"},
    ]


def _run(stage: dict, root: pathlib.Path, a) -> tuple[str, str, str, float]:
    """One stage. RESUME when its output exists, SKIP when billed without --accept."""
    name, t0 = stage["name"], time.time()
    produced = stage.get("produces", "")
    # AN ITERATING STAGE ASKS ITS OWN ITEMS, never the shared glob. See the note on `profiles`.
    todo: list[list[str]] = []
    if "each" in stage and not a.refresh:
        todo = stage["each"]()
        total = stage["per_item"]() if "per_item" in stage else len(todo)
        if not todo:
            return (name, "RESUME", f"all {total} item(s) present", 0.0)
    elif produced and not stage.get("always") and not a.refresh and _present(root, produced):
        return (name, "RESUME", f"{produced} present", 0.0)
    if stage.get("billed") and not a.accept:
        return (name, "SKIP", "billed — re-run with --accept", 0.0)

    cmds: list[list[str]] = []
    if "cmd" in stage:
        cmds = [stage["cmd"]]
    elif "each" in stage:
        cmds = todo if not a.refresh else stage["each"]()
        if not cmds:
            return (name, "CANNOT", "nothing to iterate — the stage before it produced nothing",
                    time.time() - t0)
    elif "sdk" in stage:
        sdk = _sdk_root()
        if sdk is None:
            return (name, "CANNOT", "no sdk checkout found for the billed authoring",
                    time.time() - t0)
        cmds = [[sys.executable, "-m", "sdk.cli.harvest", "--content-root", str(root),
                 *stage["sdk"], *(["--accept"] if a.accept else [])]]
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
    for cmd in cmds:
        cwd = _sdk_root() if "sdk" in stage else None
        r = subprocess.run([sys.executable, *cmd] if cmd[0].endswith(".py") else cmd,
                           capture_output=True, text=True, timeout=1800,
                           cwd=str(cwd) if cwd else None)
        out = (r.stdout or "") + (r.stderr or "")
        tail = [ln for ln in out.splitlines() if ln.strip()]
        lastline = tail[-1][:88] if tail else ""
        if r.returncode != 0:
            if any(mark in out for mark in refusals):
                refused += 1
                lastline = next((ln.strip() for ln in reversed(out.splitlines())
                                 if any(m in ln for m in refusals)), lastline)[:88]
            else:
                fails += 1
    secs = time.time() - t0
    if fails:
        return (name, "FAIL", f"{fails} of {len(cmds)} call(s) failed — {lastline}", secs)
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
    if d["id"] == "D12" and not a.accept:
        return ("cutting a register READS the column's values, which is billed against a cloud "
                "warehouse — the stage ran DRY. Re-run with --accept.")
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
    if d["id"] == "D4b":
        return "edges are authored by the same billed stage as the concepts (see D4)."
    return "the stage above reported FAIL or CANNOT — its last line says why."


def _probe(root: pathlib.Path, kind: str) -> tuple[bool, str]:
    """Read what the projection actually produced, rather than trusting that it ran."""
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
def _tool(name: str) -> str:
    return str(HERE / name)


def _sdk_root() -> pathlib.Path | None:
    return next((p for p in SDK_ROOTS if (p / "sdk" / "cli" / "harvest.py").is_file()), None)


def _matches(root: pathlib.Path, pattern: str) -> list[pathlib.Path]:
    return [p for p in root.glob(pattern) if p.is_file()]


def _present(root: pathlib.Path, pattern: str) -> bool:
    if any(ch in pattern for ch in "*?"):
        return bool(_matches(root, pattern))
    p = root / pattern
    return p.is_dir() and any(p.iterdir()) if p.is_dir() else p.is_file()


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
