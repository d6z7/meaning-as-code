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
     MEASURED on <dataset> (218 yaml / 641 files), counting real file opens per run, one process each:
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
import check_answerability as ANSWER              # noqa: E402
import check_reproduction as REPRO
import check_vocabulary_drift as VOCAB
import check_canon_binding as CANONB
import check_common_rules as COMMON
import check_cookbook_smells as COOKBOOK
import check_rule_reference_basis as REFBASIS
import check_framework_selfconform as SELFCONF
import mac_checks_semantic as SEMANTIC            # noqa: E402
import mac_checks_structure as STRUCTURE          # noqa: E402
import mac_model as M                             # noqa: E402
from mac_diag import (CODES, ERROR, INFO, ORDER, UNKNOWN_MARK, WARNING, Diagnostic, Witness,  # noqa: E402
                      render, summarise)

SOURCE = "mac_compile"
SCHEMA_ID = "mac.diagnostics/compile/1"

# THE OUTAGE MARKER. When a check cannot run, every module on this toolchain emits a diagnostic whose
# summary contains this phrase verbatim — because "MAC007: 0 findings" and "MAC007 was never computed"
# are OPPOSITE facts and a report that renders them the same is lying by omission. The compiler needs
# to distinguish them for its footer, and the phrase is the one signal the frozen `Diagnostic` shape
# carries for it (adding a field would be a contract change, which is not on the table). If the phrase
# is ever reworded in a check module, this footer degrades in the SAFE direction: it reports a code as
# clean that is actually unknown — so the phrase is treated as part of the convention, not as prose.
# UNKNOWN_MARK is IMPORTED from mac_diag (above), where the contract it belongs to lives — it used
# to be declared here while every check module spelled the same phrase by hand.
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
    # MAC009 was owned here until it was RETIRED (see RETIRED, below). It is removed from the
    # ownership tuple deliberately: a phase that still CLAIMS a withdrawn code would have the footer
    # report it as "clean — computed over this bundle, no finding", which is a green tick for a
    # question nobody is asking any more.
    ("structure", ("MAC001", "MAC002", "MAC008", "MAC011"), "model",
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
    ("reference_basis", ("MAC008", "MAC003", "MAC002"), "root",
     "whether a rule's references — to a concept, a column, a relation — resolve and are declared"),
    ("answerability", ("MAC011",), "root",
     "whether each concept's answer path DERIVES, or is only sworn to in prose"),
    ("selfconform", ("MAC001", "MAC002"), "root",
     "whether the FRAMEWORK satisfies the rules it enforces on every bundle"),
)


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE RETIRED CODES — withdrawn, never reassigned
# ══════════════════════════════════════════════════════════════════════════════════════════════════
# A closed taxonomy can retire a code. It may NEVER reuse one: suppressions, dashboards and estate
# counts are keyed on the string, so re-pointing `MAC009` at a future defect would silently change the
# meaning of every number already recorded under it.
#
# MAC009 (undeclared-extension) asked whether an `x-` key was DECLARED in `mac.project.yaml#profile`,
# and its remedy was to declare it. That remedy ratified the construct MAC012 prohibits outright, so
# the framework was shipping two opposite policies on one key and a bundle heard both. MEASURED on a
# 15-site example bundle before this change: THREE diagnostics under TWO codes about the same fifteen
# keys — one MAC002 (the schema rejecting them, `^x-` having been closed in v0.1.14) and two MAC009
# telling the bundle to declare them. MAC012, the code that says prohibited, was wired into this file
# nowhere at all and never ran.
#
# WHY WITHDRAWN AND NOT RE-POINTED. Re-pointing MAC009's sites at MAC012 would carry its MESSAGE —
# "declare each in mac.project.yaml#profile.x_keys" — under the prohibition's number: the same
# contradiction wearing a new code. And it is unnecessary, because MAC009's subject is a strict SUBSET
# of MAC012's: MAC009 read schema-routed files only, `check_extension_keys` walks every YAML in the
# bundle. Withdrawing it loses no coverage and removes one contradiction. CONFORMANCE.md §5.1.
#
# WHERE THE WITHDRAWAL BITES. The emitter still lives in `mac_checks_structure.check_undeclared_
# extensions`, which this file does not own. So the withdrawal is enforced HERE, at the boundary every
# finding passes through — and it is enforced LOUDLY: the count is printed in the inventory on every
# compile, never dropped in silence. Deleting the emitter upstream makes this a no-op, which is the
# intended end state.
RETIRED = {
    "MAC009": ("MAC012",
               "undeclared-extension — its remedy was to DECLARE an `x-` key, which MAC012 prohibits "
               "outright; its subject is a strict subset of MAC012's"),
}

# ── WITHDRAWN OFFERS — a capability MAC no longer offers cannot be "unadopted" ────────────────────
# MAC005 (capability-unadopted) reports what MAC OFFERS and the bundle does not take. The `x-`
# extension profile was such an offer, and `mac_checks_adoption._prose_offers` still makes it — citing
# CONFORMANCE.md §2 as the offerer, by name, in its `offered_by`. §2 has since WITHDRAWN it. So the
# offer is stale by construction: it quotes a sentence that no longer exists, and it was measured
# doing so on an example bundle AFTER MAC009 was retired — a third code, telling the bundle to adopt
# the construct the other two had just prohibited.
#
# An offer nobody makes cannot be refused, so the finding is withdrawn on the same terms as a retired
# code. Matched on the offer's own KEY, which is the stable identifier the adoption check builds each
# Offer from — not on the sentence around it. Deleting the offer upstream makes this a no-op, and that
# is the intended end state; this is the boundary holding the ruling until it lands.
WITHDRAWN_OFFERS = {
    "x- extension profile": ("MAC005",
                             "the `x-` extension profile, withdrawn by CONFORMANCE.md §2 — the very "
                             "section this offer cites as its offerer"),
}

# ── THE CONTRADICTION GUARD ───────────────────────────────────────────────────────────────────────
# The operator's ruling is that a framework must NOT encode opposite policies, and that where two
# rules contradict, the contradiction is a DEFECT to be intercepted and removed rather than documented
# and lived with. Removing the two known sites is not the same as removing the contradiction: a third
# can be reworded back in tomorrow, in a file this one does not own, and nothing would notice.
#
# So the ruling is ENFORCED, not merely applied. Any surviving finding that routes an operator back to
# declaring an `x-` key — whatever code it carries, whichever check emitted it — is collapsed into ONE
# framework-directed diagnostic naming the offenders. The phrases are the REMEDY wordings the withdrawn
# construct used; they are matched case-insensitively over summary and note.
#
# It is WARNING and not error on purpose, and the subject is stated in the note: the defect belongs to
# MAC, not to the bundle being compiled, and failing somebody's bundle for the framework's own
# contradiction is a lie in the other direction — the same principle this file already applies to a
# gate that could not run.
_RATIFIES_EXTENSION = (
    "profile.x_keys",
    "declare each in",
    "undeclared debt, not license",
    "invent under `x-`",
    "promotion candidate",
    "x- extension profile",
    "x- extension namespace",
)


def contradiction_guard(diags: list) -> list:
    """ONE diagnostic if anything still tells a bundle it may DECLARE an `x-` key."""
    offenders = []
    for d in diags:
        blob = f"{d.summary} {d.note or ''}".lower()
        if any(ph in blob for ph in _RATIFIES_EXTENSION):
            offenders.append(d)
    if not offenders:
        return []
    seen, witnesses = set(), []
    for d in offenders:
        stem = str(d.source).split("[")[0].split(".")[0]
        cand = f"tools/{stem}.py"
        file = cand if (MAC_ROOT / cand).exists() else "CONFORMANCE.md"
        phrase = next(ph for ph in _RATIFIES_EXTENSION
                      if ph in f"{d.summary} {d.note or ''}".lower())
        if (file, d.code, phrase) in seen:
            continue
        seen.add((file, d.code, phrase))
        witnesses.append(Witness(file=file, detail=f"{d.code} still says {phrase!r}"))
    return [Diagnostic(
        code="MAC012", severity=WARNING, source=f"{SOURCE}.contradiction_guard",
        summary=(f"the FRAMEWORK still encodes the opposite policy on `x-` keys in "
                 f"{de(len(witnesses))} place(s): a finding survives that routes the operator back to "
                 f"DECLARING an extension, which CONFORMANCE.md §2 prohibits outright"),
        witnesses=witnesses,
        note=("THE SUBJECT OF THIS FINDING IS MAC, NOT THIS BUNDLE — which is why it is a warning and "
              "not an error; a bundle is not failed for the framework's own contradiction. Two rules "
              "that disagree are a defect to be removed, not a nuance to document: delete the remedy "
              "at the site named above, or withdraw it here (RETIRED / WITHDRAWN_OFFERS). MAC009 and "
              "the §2 extension profile were removed this way; this guard is what keeps a third from "
              "being worded back in unnoticed"))]


# Set by `compile_bundle`, read by `inventory`/`main`. A module-level recorder rather than a fourth
# return value ON PURPOSE: `compile_bundle` has a second caller outside this file (a downstream
# projector runs it as a gate), and widening its contract to carry a transitional count would break
# that caller for a line of report text.
_WITHDRAWN: dict = {}


def withdraw_retired(diags: list) -> list:
    """Drop findings under a retired code, recording how many, under which code, and what replaced it.

    A withdrawn finding is not a suppressed one: the question it asked has been deleted, not silenced.
    The distinction is why this records rather than merely filters — a reader who remembers MAC009
    must be told it is gone and what says the thing now, not shown a list with a hole in it."""
    _WITHDRAWN.clear()
    kept = []
    for d in diags:
        if d.code in RETIRED:
            _WITHDRAWN[d.code] = _WITHDRAWN.get(d.code, 0) + 1
            continue
        offer = next((k for k in WITHDRAWN_OFFERS if k.lower() in d.summary.lower()
                      and d.code == WITHDRAWN_OFFERS[k][0]), None)
        if offer:
            _WITHDRAWN[f"{d.code} / {offer}"] = _WITHDRAWN.get(f"{d.code} / {offer}", 0) + 1
            continue
        kept.append(d)
    return kept


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
    if name == "answerability":
        return ANSWER.check_answerability(root)
    if name == "cookbook":
        return COOKBOOK.check_cookbook_smells(root)
    if name == "reference_basis":
        return REFBASIS.check_rule_reference_basis(root)
    if name == "selfconform":
        return SELFCONF.check_framework_selfconform(root)
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
    # one of them (check_mac_public) FAILING on <dataset> at the time. The verdict line is the whole product
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
    # ADDED with the x- ruling. This gate EXISTED, exited non-zero, and was in neither the phase
    # register nor this table — so the one check that says "an `x-` key is prohibited" never ran on a
    # bundle the compiler judged, while the retired MAC009 told those same bundles to declare it. A
    # gate outside the inventory is worse than a wrapped one: the report's silence reads as coverage.
    "check_extension_keys": ("MAC012",
                             "an `x-` key sits by construction outside every gate MAC has, so what it "
                             "holds is a completeness the bundle cannot reach — and it is now the "
                             "single voice on the subject, MAC009 having been withdrawn"),
    "check_served_name_distinct": ("MAC002",
                                   "a served name equal to its raw source violates the definition of "
                                   "what a served relation is"),
    "check_transform_sql_extracted": ("MAC011",
                                      "a transform whose SQL is not extracted leaves the chain "
                                      "incomplete at the step that does the work"),
    # check_mac_public is DELIBERATELY NOT HERE. It is a gate on the FRAMEWORK repo — "meaning-as-code
    # is a PUBLIC framework repo: it must never carry a VW / GAPS / <SOURCE> / source-specific token" — and
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
    # A RETIRED code is not UNKNOWN. "Not computed" means a question nobody answered; a withdrawn
    # code has no question left to answer. Reporting it as unknown would put it in the headline's
    # hole-count and make every compile read as incomplete, permanently.
    return out - set(RETIRED)


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
    # RETIRED CODES, ON EVERY COMPILE. A code that vanishes from a report without a word looks like a
    # code that came up clean, and the two are opposite facts — the same confusion the UNKNOWN marker
    # exists to prevent, one level up at the taxonomy rather than at the check.
    for code, (replacement, why) in sorted(RETIRED.items()):
        n = _WITHDRAWN.get(code, 0)
        seen = (f"{de(n)} finding(s) withdrawn on this bundle" if n
                else "no finding raised under it on this bundle")
        out.append(f"    {'(retired ' + code + ')':<36} {'-> ' + replacement:<34} RETIRED — {why}; "
                   f"{seen}")
    for offer, (code, why) in sorted(WITHDRAWN_OFFERS.items()):
        n = _WITHDRAWN.get(f"{code} / {offer}", 0)
        seen = (f"{de(n)} finding(s) withdrawn on this bundle" if n
                else "not offered against this bundle")
        out.append(f"    {'(withdrawn offer)':<36} {code:<34} WITHDRAWN — {why}; {seen}")
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
        # The bundle's NAME, never its path. `root` is an ABSOLUTE path on whoever ran the compile,
        # and compile.json is a COMMITTED artifact — it put an author's home directory into every
        # bundle's compile record, including bundles in public repositories. The name is the identity
        # a reader needs; the path is the operator's, not the bundle's. Same defect, same fix, as
        # ontology/diagnostics.json.
        "bundle": Path(root).name,
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
        # A dashboard must be able to render "clean", "never computed" and "retired" as three
        # different things. `retired` names the code that replaced it, so a stored finding set from
        # before the withdrawal stays readable: the reader is told where the question went.
        "codes": {c: {"kind": k, "meaning": m, "count": stats["by_code"].get(c, 0),
                      "computed": c not in unknown and c not in RETIRED,
                      "retired": RETIRED[c][0] if c in RETIRED else None}
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
    # LAST, over everything: a retired code is retired whoever raised it — a native phase, a wrapped
    # gate, or a check ported between the two after this line was written. The guard runs on what
    # SURVIVES, so a withdrawal is a fix and not an offence.
    kept = withdraw_retired(diags)
    return kept + contradiction_guard(kept), rows, timings


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
    clean = sorted(c for c in CODES if not stats["by_code"].get(c) and c not in unknown
                   and c not in RETIRED)
    hidden = [d for d in diags if ORDER.get(d.severity, 2) > ORDER.get(args.show, 1)]
    if hidden:
        print(f"  {de(len(hidden))} finding(s) below --show {args.show} are counted above and persisted "
              f"in --json, not printed")
    if clean:
        print(f"  clean: {' '.join(clean)} — computed over this bundle, no finding")
    print(f"  not computed: {' '.join(sorted(unknown))} — a check that owns these did not run, so they "
          f"are UNKNOWN, not clean" if unknown
          else "  not computed: none — every check that owns a code ran to completion")
    if RETIRED:
        # THREE STATES, NOT TWO. Clean / not computed / retired — printed separately because a reader
        # who remembers a code needs to be told it was withdrawn and what says the thing now, rather
        # than reading its absence as a pass.
        print("  retired: " + " ".join(f"{c} -> {r}" for c, (r, _w) in sorted(RETIRED.items()))
              + " — withdrawn from the taxonomy (CONFORMANCE.md §5.1), never reassigned"
              + (f"; {de(sum(_WITHDRAWN.get(c, 0) for c in RETIRED))} finding(s) withdrawn on this "
                 f"bundle" if any(c in _WITHDRAWN for c in RETIRED) else ""))
    if WITHDRAWN_OFFERS:
        print("  withdrawn offers: "
              + " ".join(f"{c}/{o!r}" for o, (c, _w) in sorted(WITHDRAWN_OFFERS.items()))
              + " — MAC no longer offers these, so a bundle cannot be charged with not adopting them")

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

    # THE HEADLINE CARRIES THE HOLE. "COMPILES — 0 error(s)" is a claim about codes that were
    # COMPUTED, and the footer above has always distinguished those from the ones nobody established
    # — but a reader who reads one line read the wrong one. MEASURED: on a bundle whose concepts a
    # gate could not find, four codes went unknown under an unqualified COMPILES.
    # The EXIT CODE is deliberately unchanged (0 = no error-severity finding, this file's contract):
    # a bundle nobody checked must not be failed as if it had been judged and found wanting.
    # `unknown` is the set computed for the footer above — READ, not recomputed.
    verdict = "DOES NOT COMPILE" if stats["errors"] else (
        "COMPILES, WITH HOLES" if unknown else "COMPILES")
    print(f"\n{verdict} — {de(stats['errors'])} error(s). "
          + ("Nothing may run on this bundle until they are cleared."
             if stats["errors"] else "No error-severity finding.")
          + (f" {de(len(unknown))} code(s) were NOT COMPUTED ({' '.join(sorted(unknown))}) — "
             f"UNKNOWN, not clean." if unknown else ""))
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
