#!/usr/bin/env python3
"""mac_compile — THE MAC COMPILER. One invocation, one finding list, one verdict.

WHAT THIS IS, AND WHY IT EXISTS
-------------------------------
The operator asked five times for the thing a C or Java compiler gives you: not "does this one file
parse", but the COMPLETE list of violations over the whole program — what is defined, what is defined
redundantly, what is not defined, on every criterion the standard has. Five times the answer was
another gate: another invocation, another output format, another exit code, another green tick that
told you about the part it happened to look at. Eleven gates is not a compiler; it is eleven opinions
you have to hold in your head at once, and nobody does, which is why 156 undefined artifacts sat in
this bundle while every gate was green.

This is the front end. It:

  1. LOADS THE BUNDLE ONCE and hands the same parsed object to every check — `mac_model.load`'s memo,
     `validate_schema`'s enumeration cache, the conformance `Bundle` and the framework introspection
     are built once and shared, instead of once per gate.
     MEASURED on fpl2 (218 yaml / 641 files), counting real file opens per run, one process each:
        nine gates, nine processes ................ 2.356 opens
        the three native phases, three processes .. 1.272 opens
        THIS COMPILER, three native phases ........ 1.104 opens   (-168, -13 %)
     The saving on the native path is real but small, and saying otherwise would be the kind of claim
     this toolchain gets wrong: the re-walking that is left lives in the SIX WRAPPED GATES, which are
     still subprocesses and still open 1.088 files between them. Porting them is what collapses it —
     which is exactly why the report prints the wrapped list on every single compile.
  2. RUNS EVERY NATIVE CHECK and collects `Diagnostic`s (the frozen contract, `mac_diag.py`).
  3. WRAPS THE GATES THAT ARE NOT YET NATIVE as subprocesses, maps a non-zero exit to one Diagnostic
     carrying the gate's own output as witnesses, and LABELS THEM AS WRAPPED IN THE REPORT ITSELF.
     A wrapped gate is debt. Debt you can see shrinks; debt you cannot see is why this file is late.
  4. RENDERS ONE REPORT sorted by severity, with ONE summary line, and returns ONE exit code.
  5. `--json` persists the whole finding set, so after any compile the complete state is readable at
     any later point, by anyone, without re-running it. That is the dashboard's input.

THERE IS NO SECOND OUTPUT FORMAT. The terminal report and the JSON are the same finding set serialised
twice; neither is computed differently from the other, and no check is run twice to produce them.

FANOUT IS COLLAPSED, ALWAYS — inherited from the contract and enforced here for the wrapped gates too:
a gate that prints 40 failing lines becomes ONE diagnostic with 40 witnesses, never 40 diagnostics. A
report that emits one line per file is muted within a week and its root cause dies with it. That has
happened on this toolchain, and it is the single design constraint everything here obeys.

WHAT THIS FILE DOES NOT DO
--------------------------
It contains NO analysis. Not one rule about concepts, registers, rules, lineage or vocabulary lives
here — every finding is produced by a check module and this file only sequences, merges, renders and
scores. That is deliberate: a driver that grew its own check would be a second home for a fact
(MAC003), which is precisely the defect the taxonomy exists to name. If you find yourself wanting to
special-case a bundle here, the special case belongs in a check, behind a measurement.

NO INSTANCE HARDCODING. No corpus literal — no concept, column, measure, register or bundle name —
appears in this file. The only names in it are MAC's own module names.

Usage:  mac_compile.py <bundle-root> [--show error|warning|info] [--json <path>] [--no-legacy]
Exit:   0 = compiles (no error-severity finding) · 1 = does not conform · 2 = setup error
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mac_checks_adoption as ADOPTION            # noqa: E402
import check_reproduction as REPRO
import check_vocabulary_drift as VOCAB
import check_canon_binding as CANONB
import check_common_rules as COMMON
import check_cookbook_smells as COOKBOOK
import mac_checks_semantic as SEMANTIC            # noqa: E402
import mac_checks_structure as STRUCTURE          # noqa: E402
import mac_model as M                             # noqa: E402
from mac_diag import CODES, ERROR, INFO, ORDER, WARNING, Diagnostic, Witness, render, summarise  # noqa: E402

SOURCE = "mac_compile"
SCHEMA_ID = "mac.diagnostics/compile/1"

# THE OUTAGE MARKER. When a check cannot run, every module on this toolchain emits a diagnostic whose
# summary contains this phrase verbatim — because "MAC007: 0 findings" and "MAC007 was never computed"
# are OPPOSITE facts and a report that renders them the same is lying by omission. The compiler needs
# to distinguish them for its footer, and the phrase is the one signal the frozen `Diagnostic` shape
# carries for it (adding a field would be a contract change, which is not on the table). If the phrase
# is ever reworded in a check module, this footer degrades in the SAFE direction: it reports a code as
# clean that is actually unknown — so the phrase is treated as part of the convention, not as prose.
UNKNOWN_MARK = "UNKNOWN — not absent"
MAC_ROOT = Path(__file__).resolve().parent.parent
TOOLS = MAC_ROOT / "tools"
de = M.de


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE PHASE REGISTER — native checks
# ══════════════════════════════════════════════════════════════════════════════════════════════════
# (name, codes it owns, what it needs, runner). The CODES are declared, not inferred from the findings:
# the report must be able to say "MAC007: 0 findings" and "MAC007: never computed" differently, and it
# can only do that if it knows in advance which phase owed which code. A phase that dies is charged
# with its own codes going UNKNOWN — the check modules already do this internally per check; this
# register is the same guarantee one level up, for the case where the phase itself cannot be entered.

PHASES = (
    ("structure", ("MAC001", "MAC002", "MAC009", "MAC008", "MAC011"), "model",
     "what is defined, and does it satisfy its definition"),
    ("semantic", ("MAC003", "MAC004", "MAC007", "MAC006", "MAC010"), "model",
     "what is stated twice, contradicted, unwarranted, dead, or off the record"),
    ("adoption", ("MAC005",), "conformance",
     "what MAC offers and the bundle does not take"),
    ("reproduction", ("MAC004", "MAC008", "MAC011"), "root",
     "whether the process RECORD still agrees with the artifacts"),
    ("vocabulary", ("MAC008",), "root",
     "whether the FRAMEWORK's own code still agrees with its closed vocabularies"),
    ("canon_binding", ("MAC004", "MAC008"), "root",
     "whether a bound rule's prose still says what its canon renders"),
    ("common_rules", ("MAC003", "MAC005", "MAC008"), "root",
     "whether a concept restates a law MAC already states for its class"),
    ("cookbook", ("MAC003",), "root",
     "the MODELLERS_COOKBOOK Part-C anti-patterns, enforced rather than described"),
)


def _run_phase(name: str, bundle_model, bundle_conf, framework, root: str) -> list:
    """One native phase. A phase that raises is itself a finding — a compiler that dies quietly
    reports a CLEAN bundle, which is strictly worse than reporting nothing."""
    if name == "structure":
        return STRUCTURE.run(bundle_model, root)
    if name == "semantic":
        return SEMANTIC.run(bundle_model, root)
    if name == "adoption":
        return ADOPTION.check(root, fw=framework, bundle=bundle_conf)
    if name == "reproduction":
        return REPRO.check_reproduction(root)
    if name == "vocabulary":
        return VOCAB.check_vocabulary_drift(root)
    if name == "canon_binding":
        return CANONB.check_canon_binding(root)
    if name == "common_rules":
        return COMMON.check_common_rules(root)
    if name == "cookbook":
        return COOKBOOK.check_cookbook_smells(root)
    raise KeyError(name)                                     # PROGRAMMER error, not bundle content


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE WRAPPED GATES — not yet native, and said so out loud
# ══════════════════════════════════════════════════════════════════════════════════════════════════
# Each entry: module stem → (taxonomy code its failures belong under, why that code, argv style).
#
# THE CODE IS DECLARED, NOT GUESSED. A wrapped gate's output is prose; the compiler cannot read it and
# decide what class of defect it found. So the mapping is made once, here, by the subject the gate is
# ABOUT — and it is printed in the inventory so it can be argued with. When a gate is ported, its row
# moves from WRAPPED to NATIVE and this entry is deleted; the code it owned does not change, which is
# what makes the port a no-op for anything downstream that counts by code.
#
# WHAT A WRAPPED FINDING IS AND IS NOT: it is ONE diagnostic per GATE, carrying that gate's own output
# as witnesses. It is NOT parsed into per-object findings — parsing another tool's prose into
# addressable findings is exactly the re-implementation that porting it properly will delete, and a
# half-parse that silently drops a line is worse than an honest blob.

LEGACY = {
    "check_shapes": ("MAC002",
                     "a shape IS a definition; a concept failing it has a definition it does not satisfy"),
    "check_references": ("MAC008",
                         "its whole subject is a reference that resolves to nothing"),
    "check_enumeration_closure": ("MAC006",
                                  "a set CLAIMED closed while holding an unconfirmed member is a claim "
                                  "with no warrant behind it"),
    "check_lineage_coverage": ("MAC011",
                               "a served dataset that explains none of its columns is a completeness "
                               "the bundle does not reach"),
    "check_lookups": ("MAC008",
                      "a cited lookup that is missing or empty is a reference resolving to nothing"),
    "check_measure_additivity_registry": ("MAC004",
                                          "a registry row that is not an exact projection of the "
                                          "framework law is two statements of one fact disagreeing"),
    # ADDED 2026-08-18 after an adversarial pass found EIGHT gates the compiler neither ran nor named —
    # one of them (check_mac_public) FAILING on fpl2 at the time. The verdict line is the whole product
    # of this file: "DOES NOT COMPILE" was trustworthy only by luck, and a future "COMPILES" would have
    # been a lie while a red gate sat outside the inventory. A gate that exists and is not listed is
    # worse than a wrapped one, because the report's silence reads as coverage.
    "check_dq_resolution_sync": ("MAC010",
                                 "an impurity rule that dissolves a defect without declaring it "
                                 "resolves that defect is a change with no protocol behind it"),
    "check_ontology_grounds_on_datasets": ("MAC011",
                                           "the raw->transform->dataset->ontology chain is a "
                                           "completeness requirement over the whole bundle"),
    "check_schema_isolation": ("MAC008",
                               "a grounding aimed at another source's schema resolves outside the "
                               "relation it claims"),
    "check_relation_identity": ("MAC008",
                                "a relation that is not identifiable is a reference nothing can resolve"),
    "check_served_name_distinct": ("MAC002",
                                   "a served name equal to its raw source violates the definition of "
                                   "what a served relation is"),
    "check_transform_sql_extracted": ("MAC011",
                                      "a transform whose SQL is not extracted leaves the chain "
                                      "incomplete at the step that does the work"),
    # check_mac_public is DELIBERATELY NOT HERE. It is a gate on the FRAMEWORK repo — "meaning-as-code
    # is a PUBLIC framework repo: it must never carry a VW / GAPS / FPL / source-specific token" — and
    # it defaults to MAC's own root. Wrapping it and aiming it at a customer bundle made it fail on the
    # bundle's own domain vocabulary, which is what a bundle is FOR. That was a category error (added
    # and removed 2026-08-18): a gate's SCOPE is part of its contract, and adding gates to this table
    # without reading what each one is about produced exactly the false error the compiler exists to
    # eliminate. It belongs in MAC's own CI, run against MAC.
}

# Gates that are NOT wrapped, and why — printed in the inventory, because a compiler that silently
# omits a gate is the thing this file exists to end. These are ABSORBED: a native check reads them or
# has taken over their question, and running them again would state one fact in two homes (MAC003) —
# the compiler committing the defect it reports.
ABSORBED = {
    "validate_schema": "structure — its enumeration + per-file validation ARE the MAC001/MAC002 checks",
    "mac_diagnostics": "semantic — its fact analysis IS the MAC003/MAC004 check",
    "check_conformance": "adoption — its bundle loader + framework introspection ARE the MAC005 check",
    "check_intervention_ledger": "semantic MAC010 owns the protocol question; this gate's REMAINING "
                                 "register-shape rules (required keys, id uniqueness, dq cross-refs) "
                                 "are NOT yet covered by any native check — a known hole, not a claim",
    "check_vanilla_delta": "semantic MAC010 owns the protocol question; its REMAINING delta-register "
                           "shape rules (placeholder baselines, ratification state) are NOT yet "
                           "covered by any native check — a known hole, not a claim",
}

_PATHISH = re.compile(r"[A-Za-z0-9_./\-]+\.(?:yaml|yml|json|csv|md|sql|py)")
# A gate line worth keeping as a witness. Kept deliberately loose: over-selecting costs a truncated
# witness list (the renderer shows twelve), under-selecting LOSES the finding, and losing findings is
# the failure mode this whole file is a response to.
_INTERESTING = re.compile(r"\[(?:ERROR|FAIL|WARN|WARNING)\]|^\s*[✗x×]\s|\berror\b|\bfailed\b", re.I)


def _witnesses_from_output(text: str, gate: str, root: str) -> list:
    """A gate's stdout, collapsed into witnesses. Where a line names a bundle file, the witness is
    ADDRESSABLE at that file; otherwise it is addressed to the gate, which is the honest answer —
    the gate knew where the defect was and did not say."""
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    picked = [ln for ln in lines if _INTERESTING.search(ln)]
    if not picked:                       # a gate that failed without a line we recognise: keep it all
        picked = lines
    out, seen = [], set()
    for ln in picked[:200]:
        if ln in seen:
            continue
        seen.add(ln)
        file = f"tools/{gate}.py"
        for cand in _PATHISH.findall(ln):
            rel = cand.lstrip("./")
            if (Path(root) / rel).exists():
                file = rel
                break
        out.append(Witness(file=file, detail=" ".join(ln.split())))
    if len(picked) > 200:
        out.append(Witness(file=f"tools/{gate}.py",
                           detail=f"… {de(len(picked) - 200)} further output line(s) not carried"))
    return out


def run_legacy(root: str, timeout: int = 300) -> tuple:
    """Every not-yet-native gate, as a subprocess. Returns (diagnostics, per-gate status rows).

    A gate is run with the SAME interpreter that is running the compiler, so a gate cannot silently
    pass because it found a different environment than the phases did."""
    diags, rows = [], []
    for gate in sorted(LEGACY):
        code, why = LEGACY[gate]
        script = TOOLS / f"{gate}.py"
        t0 = time.perf_counter()
        if not script.exists():
            rows.append((gate, code, "MISSING", 0.0))
            diags.append(Diagnostic(
                code=code, severity=WARNING, source=f"{SOURCE}.legacy",
                summary=(f"wrapped gate `{gate}` is not on disk, so every {code} finding it owns in "
                         f"this bundle is {UNKNOWN_MARK}"),
                witnesses=[Witness(file=f"tools/{gate}.py", detail="expected here, not found")],
                note="either the gate was deleted without porting its question, or this register is stale"))
            continue
        try:
            p = subprocess.run([sys.executable, str(script), root], capture_output=True, text=True,
                               timeout=timeout, cwd=str(MAC_ROOT))
            rc, out = p.returncode, (p.stdout or "") + (p.stderr or "")
        except subprocess.TimeoutExpired:
            rc, out = -1, f"gate did not finish within {de(timeout)} s"
        except OSError as exc:                                          # noqa: BLE001
            rc, out = -1, f"could not be executed: {exc!r}"
        dt = time.perf_counter() - t0
        rows.append((gate, code, "PASS" if rc == 0 else f"EXIT {rc}", dt))
        if rc == 0:
            continue
        # exit 2 is a SETUP failure by this toolchain's convention — the gate did not judge the bundle,
        # so the finding class is unknown, not violated. Reporting that as an error would be a lie in
        # the other direction: it would fail a bundle nobody checked.
        sev = WARNING if rc == 2 else ERROR
        verdict = (f"could not run, so every {code} finding it owns is {UNKNOWN_MARK}" if sev == WARNING
                   else "reports that the bundle does not satisfy its rule set")
        diags.append(Diagnostic(
            code=code, severity=sev, source=f"{SOURCE}.legacy[{gate}]",
            summary=(f"wrapped gate `{gate}` {verdict} (exit {rc}) — NOT YET NATIVE, its output is "
                     f"carried below verbatim rather than as addressable findings"),
            witnesses=_witnesses_from_output(out, gate, root),
            note=(f"mapped to {code} because {why}. This gate is WRAPPED, not integrated: the compiler "
                  f"cannot attribute its lines to objects, so fanout is collapsed to one finding. "
                  f"Porting it into a native check is what removes this caveat")))
    return diags, rows


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# the report
# ══════════════════════════════════════════════════════════════════════════════════════════════════

def _as_dict(d: Diagnostic) -> dict:
    """Field-for-field the serialisation the phase modules already use, so the persisted finding set
    has ONE shape however many phases produced it."""
    return {"code": d.code, "kind": d.kind, "severity": d.severity, "summary": d.summary,
            "note": d.note, "source": d.source,
            "witnesses": [{"file": w.file, "path": w.path, "line": w.line, "detail": w.detail}
                          for w in d.witnesses]}


def unknown_codes(diags, no_legacy: bool) -> set:
    """The codes this compile did NOT establish an answer for.

    Two ways a code goes unknown: a check that owns it CRASHED (the check module says so, in its own
    finding, carrying `UNKNOWN_MARK`), or a check that owns it was SKIPPED (`--no-legacy`). Both must
    be reported separately from "0 findings", because a green line for a check that never ran is
    exactly how 156 undefined artifacts stayed invisible while every gate was green.

    An outage finding is filed under ONE code — a Diagnostic has one — but a crashed check often owed
    SEVERAL, and it names every one of them in its summary. So the codes are read from the summary,
    not from `d.code`. MEASURED: without this, a simulated `mac_checks_structure` outage reported
    MAC009 as clean while the phase that owns it had not run at all."""
    out = set()
    for d in diags:
        if UNKNOWN_MARK in d.summary:
            out.add(d.code)
            out |= {c for c in re.findall(r"MAC\d{3}", d.summary) if c in CODES}
    if no_legacy:
        out |= {code for code, _why in LEGACY.values()}
    return out


def inventory(rows, no_legacy: bool) -> str:
    """WHICH CHECKS RAN, AND HOW. The gap between native and wrapped is printed on every compile so it
    is impossible to forget it exists — that is the only mechanism that has ever made it shrink."""
    out = ["  CHECK INVENTORY — what ran, and how integrated it is",
           f"    {'CHECK':<36} {'CODES':<34} INTEGRATION"]
    for name, codes, _need, what in PHASES:
        out.append(f"    {('mac_checks_' + name):<36} {' '.join(codes):<34} NATIVE — {what}")
    if no_legacy:
        out.append(f"    {'(' + de(len(LEGACY)) + ' wrapped gates)':<36} "
                   f"{'-':<34} SKIPPED — --no-legacy: their codes are UNKNOWN, not clean")
    else:
        for gate, code, status, dt in rows:
            out.append(f"    {gate:<36} {code:<34} WRAPPED (not yet native) — {status}, {de(dt, 2)} s")
    for gate, why in sorted(ABSORBED.items()):
        out.append(f"    {gate:<36} {'—':<34} ABSORBED — {why}")
    return "\n".join(out)


def payload(root: str, diags: list, rows: list, timings: dict, *, started, duration: float,
            no_legacy: bool = False, extra: dict | None = None) -> dict:
    """THE PERSISTED FINDING SET — one home for its shape.

    The operator's second requirement, alongside the list itself: the report must PERSIST, so that
    after any compile the complete state is readable at any later point, by anyone, without re-running
    it. This function is what a dashboard reads.

    It is a FUNCTION and not inline in `main` because `main` is not the only caller any more: a
    downstream projector runs the compiler as a gate (WIKI `sdk/cli/harvest.py`) and writes the same
    record. Two writers building the same document by hand is a fact in two homes — MAC003, the defect
    this taxonomy exists to name — so the shape is single-homed here and both call it.

    `extra` is merged at the top level for a caller that must record something ABOUT the compile that
    the compile itself cannot know — above all, that a human overrode the refusal, with their reason.
    It can add keys; it is applied first, so it can never overwrite a finding."""
    stats = summarise(diags)
    unknown = unknown_codes(diags, no_legacy)
    doc = dict(extra or {})
    doc.update({
        "schema": SCHEMA_ID,
        "bundle": root,
        "generated_at": started.isoformat(),
        "duration_s": round(duration, 3),
        "verdict": "DOES_NOT_COMPILE" if stats["errors"] else "COMPILES",
        "summary": stats,
        "checks": {
            "native": [{"check": f"mac_checks_{n}", "codes": list(c), "what": w}
                       for n, c, _r, w in PHASES],
            "wrapped": [{"gate": g, "code": c, "status": s, "duration_s": round(t, 3),
                         "why_this_code": LEGACY[g][1]} for g, c, s, t in rows],
            "absorbed": [{"gate": g, "by": w} for g, w in sorted(ABSORBED.items())],
            "skipped_legacy": bool(no_legacy),
        },
        # every code in the closed taxonomy, whether or not it fired — a dashboard must be able to
        # render "MAC010: clean" and "MAC010: never computed" as different things without guessing
        "codes": {c: {"kind": k, "meaning": m, "count": stats["by_code"].get(c, 0),
                      "computed": c not in unknown}
                  for c, (k, m) in CODES.items()},
        "timings_s": {k: round(v, 3) for k, v in timings.items()},
        "diagnostics": [_as_dict(d) for d in diags],
    })
    return doc


def compile_bundle(root: str, *, no_legacy: bool = False) -> tuple:
    """Load once, run everything, return (diagnostics, inventory rows, timings). No printing."""
    timings: dict = {}
    t0 = time.perf_counter()
    bundle_model = M.load(root)
    timings["load.model"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    bundle_conf = ADOPTION.load_bundle(Path(root))
    framework = ADOPTION.introspect_framework()
    timings["load.conformance+framework"] = time.perf_counter() - t0

    diags: list = []
    for name, codes, _need, _what in PHASES:
        t0 = time.perf_counter()
        try:
            diags += _run_phase(name, bundle_model, bundle_conf, framework, root)
        except Exception as exc:                                        # noqa: BLE001
            diags.append(Diagnostic(
                code=codes[0], severity=WARNING, source=f"{SOURCE}.{name}",
                summary=(f"the {name} phase could not be entered, so every "
                         f"{' / '.join(codes)} finding in this bundle is {UNKNOWN_MARK}: {exc!r}"),
                note=("a phase that dies quietly reports a clean bundle. Fix the structural MAC002 "
                      "parse errors first — they are the usual cause — then re-compile")))
        timings[f"phase.{name}"] = time.perf_counter() - t0

    rows: list = []
    if not no_legacy:
        t0 = time.perf_counter()
        ld, rows = run_legacy(root)
        diags += ld
        timings["legacy"] = time.perf_counter() - t0
    return diags, rows, timings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("root", help="bundle root (a MAC source container)")
    ap.add_argument("--show", default=WARNING, choices=[ERROR, WARNING, INFO],
                    help="least severity PRINTED (default: warning). Never changes what is COMPUTED, "
                         "never changes the exit code, never changes what --json persists")
    ap.add_argument("--no-persist", action="store_true",
                    help="do NOT write the finding set (default is <root>/compile.json — the "
                         "dashboard's input, so a stale one shows a verdict that is no longer true)")
    ap.add_argument("--json", metavar="PATH", default=None,
                    help="persist the complete finding set here — the dashboard's input")
    ap.add_argument("--no-legacy", action="store_true",
                    help="skip the not-yet-native gates. Their codes are then UNKNOWN, not clean, and "
                         "the report says so")
    args = ap.parse_args(argv)

    root = str(Path(args.root).resolve())
    if not os.path.isdir(root):
        print(f"root not found: {root}", file=sys.stderr)
        return 2

    started = datetime.now(timezone.utc)
    wall = time.perf_counter()
    diags, rows, timings = compile_bundle(root, no_legacy=args.no_legacy)
    wall = time.perf_counter() - wall
    stats = summarise(diags)

    # ── header ────────────────────────────────────────────────────────────────────────────────────
    b = M.load(root)                                     # memoized — this is the same object as above
    en = STRUCTURE.enumeration(root)                     # cached — same enumeration the checks used
    n_wrapped = 0 if args.no_legacy else len(LEGACY)
    print(f"── MAC compiler ── {root} ── {started.strftime('%Y-%m-%d %H:%M:%S')} UTC ──")
    print(f"   {de(len(en.all_yaml))} yaml enumerated: {de(len(en.routed))} carry a MAC definition, "
          f"{de(len(en.unknown))} carry none, {de(len(en.waived))} declared out of scope")
    print(f"   {de(len(b.concepts()))} concept(s) · {de(len(b.objects()))} object(s) · "
          f"{de(len(b.registers()))} register(s) · {de(len(PHASES))} native phase(s) + "
          f"{de(n_wrapped)} wrapped gate(s) · {de(wall, 2)} s\n")
    print(inventory(rows, args.no_legacy) + "\n")

    # ── the findings ──────────────────────────────────────────────────────────────────────────────
    body = render(diags, root, show=args.show)
    print(body + "\n" if body else "  (no finding at or above "
                                   f"{args.show} severity)\n")

    # ── ONE summary line ──────────────────────────────────────────────────────────────────────────
    by_code = " ".join(f"{c}x{de(n)}" for c, n in sorted(stats["by_code"].items()))
    print(f"{de(stats['errors'])} error(s), {de(stats['warnings'])} warning(s), "
          f"{de(stats['by_severity'].get(INFO, 0))} info over {de(stats['total'])} diagnostic(s) "
          f"carrying {de(stats['witnesses'])} witness(es)  [{by_code or 'none'}]")

    unknown = unknown_codes(diags, args.no_legacy)
    clean = sorted(c for c in CODES if not stats["by_code"].get(c) and c not in unknown)
    hidden = [d for d in diags if ORDER.get(d.severity, 2) > ORDER.get(args.show, 1)]
    if hidden:
        print(f"  {de(len(hidden))} finding(s) below --show {args.show} are counted above and persisted "
              f"in --json, not printed")
    if clean:
        print(f"  clean: {' '.join(clean)} — computed over this bundle, no finding")
    print(f"  not computed: {' '.join(sorted(unknown))} — a check that owns these did not run, so they "
          f"are UNKNOWN, not clean" if unknown
          else "  not computed: none — every check that owns a code ran to completion")

    # ── persistence ───────────────────────────────────────────────────────────────────────────────
    # ALWAYS, to <root>/compile.json unless --json redirects it. It used to persist only when --json
    # was passed, so a run that printed COMPILES left the previous verdict on disk — and that file is
    # what the wiki's Compiler Report reads. Observed 2026-08-19: the dashboard showed an error that
    # had been fixed two hours earlier, because every compile since had been run without the flag.
    # A record that updates only when you remember a flag is a record nobody can trust.
    if not args.no_persist:
        doc = payload(root, diags, rows, timings, started=started, duration=wall,
                      no_legacy=args.no_legacy)
        out = Path(args.json) if args.json else Path(root) / "compile.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"  finding set persisted → {out}  ({de(out.stat().st_size / 1024, 1)} kB)")

    verdict = "DOES NOT COMPILE" if stats["errors"] else "COMPILES"
    print(f"\n{verdict} — {de(stats['errors'])} error(s). "
          + ("Nothing may run on this bundle until they are cleared."
             if stats["errors"] else "No error-severity finding."))
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
