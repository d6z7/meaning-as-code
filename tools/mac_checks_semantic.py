#!/usr/bin/env python3
"""mac_checks_semantic — the checks about MEANING, not form.

WHERE THIS SITS
---------------
The structural phase asks *"is this artifact defined, and does it satisfy its definition"* — it reads
one file and answers from that file. This phase asks the questions a single file cannot answer:

    is this fact written down in more than one place?          MAC003
    do the copies disagree?                                    MAC004
    can this guard ever fire?                                  MAC007
    is this claim backed by anything?                          MAC006
    is this manual change on the record?                       MAC010

Every one of them is a relation BETWEEN artifacts, or between an artifact and the framework law. That
is why they need `mac_model.load()` — one parse, one resolved graph, every value carrying its `Site`
— and why they could not exist while each gate re-globbed the tree and held one file at a time.

Each check takes the loaded bundle and returns `list[Diagnostic]` (mac_diag). Nothing here prints,
nothing here exits, nothing here writes: a check produces findings and the driver decides what a
finding costs. `main()` exists so the module is runnable on its own during development.

FANOUT IS COLLAPSED. Twenty-seven restatements of one derivable fact are ONE diagnostic carrying
twenty-seven witnesses, never twenty-seven diagnostics. A gate that prints one line per site gets
muted within a week and its root cause dies with it; that has been observed on this toolchain.

DISCIPLINE: MEASURE BEFORE YOU EMIT
-----------------------------------
Five plausible semantic checks were measured on 2026-08-18 and DELETED before they shipped, because
the measurement said they were noise: additivity over all axes (9 hits, 8 false — a `variant` axis is
a measure SELECTOR, not an aggregation axis); edges without a join rule (7 of 7 false — all business
level); textual drift across copied rules (13 distinct, ~3 real); a judgement-stamp entropy detector
(25 % precision); "default stated outside a default rule" (8 of 15 were facts stated exactly once).

So every check below carries, in its own docstring, the two things that argument needs: WHAT IT WOULD
FALSELY FIRE ON, and a CONCRETE LEGITIMATE CASE THAT MUST NOT FIRE. A check that cannot state its own
false-positive shape has not been measured and does not belong here.

WHAT THIS MODULE ABSORBED (and what was deleted with it)
--------------------------------------------------------
  MAC003/MAC004  wraps `mac_diagnostics.diagnose()` — the analysis is NOT rewritten here. This module
                 collapses its per-fact findings into per-family diagnostics and resolves the line
                 numbers `mac_model` leaves lazy.
  MAC006         PORTED from `check_confidence_is_earned.py`, which is DELETED in the same change.
                 Leaving both would be the partial-delta failure this project keeps repeating: two
                 readers of one rule, drifting apart, exactly the defect MAC003 exists to find.
  MAC010         the ONE implementation of "an authored/tuned object with no entry in the change
                 record". `check_intervention_ledger.py` and `check_vanilla_delta.py` each own a
                 different register's SHAPE rules (required keys, id uniqueness, dq cross-refs,
                 placeholder baselines) and now READ this for the protocol question rather than
                 carrying a second copy of it.

NO INSTANCE HARDCODING. No corpus literal — a column, a measure, a register stem, a concept — appears
in this file. Every domain is read from the bundle or from the framework law.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mac_diagnostics as _facts                                    # noqa: E402
import mac_model as M                                               # noqa: E402
from mac_diag import ERROR, INFO, WARNING, Diagnostic, Witness      # noqa: E402
from mac_diag import render, summarise                              # noqa: E402


# ==================================================================================================
# shared readers — one place per question, so two checks cannot disagree about the answer
# ==================================================================================================

def _meta(doc) -> dict:
    d = getattr(doc, "data", None)
    return d.get("metadata") if isinstance(d, dict) and isinstance(d.get("metadata"), dict) else {}


def _gov(doc) -> dict:
    d = getattr(doc, "data", None)
    return d.get("governance") if isinstance(d, dict) and isinstance(d.get("governance"), dict) else {}


def _line(b, file: str, path: str, known: int | None = None) -> int | None:
    """The 1-based line a statement was written on, resolved lazily.

    `mac_model` leaves `Site.line` None on most statements by design (indexing every file's node tree
    doubles the parse cost to serve a query only the REPORTING path makes). Reporting is exactly what
    this module is, so it pays that cost here, once, for the sites it is about to print. This adds
    addressability; it re-derives no analysis.
    """
    if known:
        return known
    doc = b.doc(file)
    return doc.line_of(path) if isinstance(doc, M.Doc) else None


def _last(value) -> str:
    """The final segment of a namespaced term: `mac.aggregation_effect.additive` -> `additive`."""
    return str(value or "").strip().split(".")[-1].strip()


def _where(obj, root) -> tuple:
    """(bundle-relative file, line of the provenance stamp) for an object.

    The doc's own `relpath` when it has one — a lookup is a CSV register and carries no document, so
    that case falls back to the path. Local rather than reaching into `mac_model`'s private `_rel`:
    a module that imports another module's underscore is one refactor away from breaking silently.
    """
    doc = getattr(obj, "doc", None)
    if isinstance(doc, M.Doc):
        return doc.relpath, doc.line_of("metadata.provenance")
    try:
        return Path(obj.path).resolve().relative_to(Path(root)).as_posix(), None
    except (ValueError, OSError):
        return str(obj.path), None


# ==================================================================================================
# MAC003 fact-restated / MAC004 fact-contradicted
# ==================================================================================================

def check_fact_homes(b) -> list:
    """One fact, more than one home — and whether the copies still agree.

    THE ANALYSIS IS NOT HERE. `mac_model`'s `Fact` family computes it (a fact = every statement of one
    subject, each folded into a closed comparison domain) and `mac_diagnostics.diagnose` rules on it.
    This function does one thing those two must not do: it COLLAPSES. Twenty-seven separate findings
    about twenty-seven measure/axis pairs are not twenty-seven problems — they are ONE problem, that
    the framework mandates a copy of a fact it can already derive, reported once with every site
    attached.

    HOME vs COPY. Each fact's statements are ordered home-first: `statements[0]` is what the others
    are derivable FROM (for `measure.additivity`, the framework law reached through the concept's own
    declared measure_type + axis_kind bridge). So the WITNESS is the copy, and the home is named in
    its detail — the reader needs to know which line to delete and which one to keep.

    SEVERITY. Restated-and-agreeing is a WARNING: nothing is wrong today and nothing keeps the copies
    in step. Restated-and-disagreeing is an ERROR: something downstream is already reading the wrong
    one. That is not a theoretical ordering — it is the exact sequence `ideal_stock` went through.

    WOULD FALSELY FIRE ON: a subject whose two statements are not really the same subject. The family
    guards this at its source and was measured doing so — keying by (measure, AXIS) rather than
    (measure, axis KIND) took a bundle from 1 false positive to 0, because a measure may legitimately
    fold differently on two categorical axes, a distinction the law cannot express. A statement that
    does not fold TOTALLY into the closed domain is never admitted, so a free-text additivity note
    cannot be compared against a law term and reported as agreement or as drift.

    A LEGITIMATE CASE THAT MUST NOT FIRE: a measure that declares its additivity on an axis the law
    says nothing about (no declared axis_kind, or a measure_selector axis). One statement, one home —
    the fact is stated exactly once and deriving it was never possible. Measured on fpl2: 8 of 35
    facts are in exactly that state and none of them is reported.

    MEASURED: fpl2 27 restated / 0 contradicted over 35 facts; contoso 6; the two framework examples
    3 and 5. GOLD IS 0 OF 9, and the reason is worth knowing before anyone reads it as cleanliness:
    not one of gold's three measures declares `semantics.measure_type`, so the law can never be aimed
    at its axes and each of its 9 additivity statements is genuinely its own only home. Gold's
    additivity is AUTHORED where fpl2's is DERIVABLE — a different state, not a better one, and the
    unadopted `measure_type` behind it is MAC005's business, not this check's.
    """
    out: list = []
    findings = _facts.diagnose(b)
    for severity, code, wanted in ((ERROR, "MAC004", "error"), (WARNING, "MAC003", "warn")):
        group = [f for f in findings if f["severity"] == wanted]
        if not group:
            continue
        families = sorted({f["family"] for f in group})
        witnesses = []
        for f in group:
            sites, values = f["sites"], f["values"]
            home, copies = sites[0], sites[1:]
            home_at = f"{home['file']}#{home['path']}"
            for i, s in enumerate(copies, start=1):
                detail = (f"{f['subject']}.{f['axis']} = {s['value']!r}; "
                          + (f"derivable as {values[0]!r} from {home_at}" if wanted == "warn"
                             else f"but {home_at} says {home['value']!r} ({values[0]!r} vs {values[i]!r})"))
                witnesses.append(Witness(s["file"], s["path"],
                                         _line(b, s["file"], s["path"], s.get("line")), detail))
        subject = " + ".join(families)
        if wanted == "warn":
            summary = (f"{M.de(len(group))} statement(s) of `{subject}` are DERIVABLE from a home that "
                       f"already holds them and are written down again anyway — the copies agree today "
                       f"and nothing keeps them in step")
            note = ("delete the copy, or make the shape that demands it derive the value instead. Every "
                    "witness here is a fact the framework can compute from the object's own declared "
                    "measure_type and axis_kind; the ontology restates it because the shape REQUIRES a "
                    "literal. That is the framework mandating the drift it later fails on.")
        else:
            summary = (f"{M.de(len(group))} statement(s) of `{subject}` DISAGREE with the home they are "
                       f"derivable from — a reader is already taking the wrong one")
            note = ("this is not a style defect: the two values license different arithmetic. Rule on "
                    "the meaning first, then make one site hold it and the other read it.")
        out.append(Diagnostic(code=code, severity=severity, summary=summary, witnesses=witnesses,
                              note=note, source="check_fact_homes"))
    return out


# ==================================================================================================
# MAC007 guard-dead
# ==================================================================================================

# A rule pins a value with `<column> = <value>`. The lookbehind refuses `>=`, `<=`, `!=`, `~=`; the
# lookahead refuses `==` used as an equality operator in a code fragment; `(?P=q)` makes the quoting
# symmetric so a SQL literal is read exactly as a bare token is.
_PIN = re.compile(r"(?<![<>!=~])(?<![A-Za-z0-9_])(?P<col>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
                  r"(?!=)(?P<q>['\"]?)(?P<val>[A-Za-z0-9_.\-]+)(?P=q)")

# A value carrying (or immediately followed by) one of these names a FAMILY of values, not one value.
_PLACEHOLDER_OPEN = "<{[%*"

# The rule fields that hold prose a guard can be pinned in. `id`/`kind`/`confidence`/`scope`/`binds`
# are identifiers and closed vocabularies, not prose — reading them would pin the rule's own id.
_RULE_TEXT_KEYS = ("subject", "when", "then", "never", "description", "statement", "note")

_DOMAIN_SAMPLE = 12                 # how much of a register's domain a witness prints before counting


def _rules(b) -> list:
    """Every rule in the bundle, as (doc, yaml-path, mapping).

    Two homes, both in the schema: `contract.rules[]` on a concept file, and top-level `rules[]` on
    the ontology plane's rules file. Read both; a bundle uses whichever it uses.
    """
    docs = [c.doc for c in b.concepts()]
    for name in ("rules.yaml", "rules.yml"):
        d = b.ontology_doc(name)
        if isinstance(d, M.Doc):
            docs.append(d)
    out = []
    for doc in docs:
        data = doc.data if isinstance(doc.data, dict) else {}
        contract = data.get("contract") if isinstance(data.get("contract"), dict) else {}
        for base, container in (("contract.rules", contract.get("rules")), ("rules", data.get("rules"))):
            if not isinstance(container, list):
                continue
            for i, rule in enumerate(container):
                if isinstance(rule, dict):
                    out.append((doc, f"{base}[{i}]", rule))
    return out


def _legal_domain(b, registers: list, column: str) -> set:
    """Every value the guard could TRULY meet in `column`: what the register holds, widened by the
    framework vocabulary its cells are namespaced into.

    THE WIDENING IS THE POINT. A register column whose cells read `mac.<namespace>.<term>` draws from
    a CLOSED framework domain, and a term of that domain which no row happens to use today is legal
    tomorrow — a guard testing it is waiting, not dead. Without this widening the check would report
    every unused-but-lawful term as a defect, which is how a gate earns its mute. The namespace is
    read off the cells themselves; no namespace is named in this file.
    """
    domain, namespaces = set(), set()
    for reg in registers:
        for row in reg.rows:
            raw = str(row.cells.get(column) or "").strip()
            if not raw:
                continue
            domain.add(_last(raw))
            parts = raw.split(".")
            if len(parts) >= 2 and parts[-2] in b.law.namespaces:
                namespaces.add(parts[-2])
    law = b.law.doc.data if isinstance(b.law.doc.data, dict) else {}
    for ns in namespaces:
        block = law.get(ns) if isinstance(law.get(ns), dict) else {}
        for key in ("terms", "members"):
            if isinstance(block.get(key), dict):
                domain |= set(block[key])
    return {d.lower() for d in domain if d}


def check_dead_guards(b) -> list:
    """A rule pinning a value that cannot occur in the register it names.

    THE SHAPE. A rule says "READ `<column>` from `<register file>` … where `<column> = <value>`". If
    `<value>` is not a value that column can hold, the branch never runs. Nobody sees a failure: the
    rule reads correct, the guard is simply never true, and whatever the guard was protecting against
    happens every time. That is worse than a missing rule, because a missing rule is visible.

    HOW A REGISTER IS "NAMED". By its FILE — relpath, file name, or on-disk stem — never by its bare
    stem. That distinction was measured and it is the whole check: reading bare stems, a rule saying
    "filter kpi = …" was matched against a register whose stem happens to be `kpi`, and 7 of 15 hits
    were that coincidence. Requiring the rule to POINT AT the file drops it to 8 of 8. A rule that
    does not cite a register is not checked at all — the check refuses to guess which domain a bare
    word belongs to.

    TWO INDEPENDENT SUPPRESSIONS, both measured to kill the same 7 false positives on their own, kept
    together because they fail differently:
      * TEMPLATE — the value carries or is followed by a placeholder opener (`kpi = dtc_<variant>`).
        The rule wrote a pattern; it never pinned anything.
      * FAMILY   — the value is a proper prefix of a real domain member. It selects a family of rows,
        which is a legitimate thing for a rule to do and never a dead guard.

    WOULD FALSELY FIRE ON: an ASSIGNMENT written with `=` in a rule that also cites a register — "set
    `region` = EU" reads identically to a guard. The check cannot tell intent from syntax, and this is
    its real residual risk. It is bounded by the same two requirements that bound everything else: the
    column must belong to a register the rule CITES BY FILE, and the value must be absent from that
    register's real domain AND from the framework vocabulary the column draws on. An assignment of a
    value that never occurs in the register is itself worth a look.

    A LEGITIMATE CASE THAT MUST NOT FIRE: a rule citing the same register and pinning a term that is a
    lawful member of the framework vocabulary the column uses but which no row carries today. On fpl2
    that is `mac.aggregation_effect.average` — a real term of the closed domain, 0 rows. A guard
    on it is waiting for a row, not dead, and the widening in `_legal_domain` is what keeps it silent.

    MEASURED on fpl2 (83 rules, 22 concepts): 8 hits, all one shape — `additivity_time = non_additive`
    in the 8 copies of the by-registered-type aggregation rule. The register's domain is {additive,
    non_aggregable, point_in_time} and the framework's is {additive, averageable, non_aggregable,
    point_in_time}; `non_additive` is in neither. Every one of those 8 rules therefore tells a reader
    to check for a token that cannot appear, and the LEVEL semantics they exist to enforce never fire.
    On the gold bundle (80 rules): 0 hits.
    """
    registers = list(b.registers())
    if not registers:
        return []
    hits: list = []
    for doc, path, rule in _rules(b):
        text = " ".join(str(rule[k]) for k in _RULE_TEXT_KEYS if isinstance(rule.get(k), str))
        if not text:
            continue
        cited = [r for r in registers
                 if r.relpath in text or r.path.name in text or r.raw_stem in text]
        if not cited:
            continue
        for m in _PIN.finditer(text):
            column, value = m.group("col"), m.group("val")
            owners = [r for r in cited if column in r.columns]
            if not owners:
                continue
            # `tail` is "" when the pin ends the text. The emptiness test is NOT redundant: "" is a
            # substring of every string, so `"" in _PLACEHOLDER_OPEN` is True, and without it every
            # guard written at the end of a sentence is silently suppressed. Measured — the positive
            # control (a bogus token as the last word of a rule) went missing until this was fixed.
            tail = text[m.end():m.end() + 1]
            if (tail and tail in _PLACEHOLDER_OPEN) or any(ch in value for ch in _PLACEHOLDER_OPEN):
                continue                                    # TEMPLATE — a pattern, not a pin
            domain = _legal_domain(b, owners, column)
            if not domain:
                continue                                    # an empty register proves nothing
            token = _last(value).lower()
            if token in domain:
                continue
            if any(d.startswith(token) and d != token for d in domain):
                continue                                    # FAMILY — a prefix selector
            hits.append((doc, path, rule, column, value, owners, domain))
    if not hits:
        return []

    witnesses, columns = [], set()
    for doc, path, rule, column, value, owners, domain in hits:
        rid = str(rule.get("id") or path)
        cites = ", ".join(sorted({r.relpath for r in owners}))
        columns.add(column)
        # The domain is EVIDENCE, so it is shown — but a 213-value geography register would bury the
        # finding it evidences, so a long one is sampled and counted rather than dumped.
        shown = sorted(domain)
        held = ("{" + ", ".join(shown) + "}" if len(shown) <= _DOMAIN_SAMPLE else
                "{" + ", ".join(shown[:_DOMAIN_SAMPLE]) + f", … {M.de(len(shown))} values in all}}")
        witnesses.append(Witness(
            doc.relpath, f"{path}#{rid}", doc.line_of(path),
            f"{rid} pins `{column} = {value}`; {cites} holds {held} in that column — "
            f"the guard cannot fire"))
    shapes = sorted({f"{c}" for c in columns})
    return [Diagnostic(
        code="MAC007", severity=ERROR,
        summary=(f"{M.de(len(hits))} rule(s) guard on a value the cited register cannot hold "
                 f"(column(s): {', '.join(shapes)}) — the branch is unreachable and its protection "
                 f"silently never applies"),
        witnesses=witnesses,
        note=("fix the TOKEN, not the rule: write the term the register actually uses. A guard that "
              "cannot fire is worse than a missing rule, because a missing rule is visible in review "
              "and this one reads as if it were doing its job."),
        source="check_dead_guards")]


# ==================================================================================================
# MAC006 claim-unearned
# ==================================================================================================

# CONFORMANCE.md §1: L3 = expert-confirmed = "an SME has ratified the meaning" = `confidence: C`.
_MACHINE = ("harvested",)
_CERTAIN = ("C", "CONFIRMED")


def check_confidence_earned(b) -> list:
    """A machine may not certify its own output.

    PORTED VERBATIM IN SUBSTANCE from `check_confidence_is_earned.py`, which is deleted in the same
    change. Its reasoning, unchanged and worth keeping:

      `metadata.provenance: harvested` means a generator wrote the object with no human in the loop.
      `metadata.confidence: C` is CONFORMANCE §1's L3, the standard's HIGHEST level, defined as "an
      SME has ratified the meaning". An object asserting both is a generator certifying its own guess
      at the one level a reader trusts without checking.

      That combination is not cosmetic; it cost a real number. `ideal_stock` claimed its measure was
      additive across markets and models. The framework law derives Target -> non_aggregable on the
      categorical axis and the bundle's own register agreed with the law. The claim survived review
      because it did not LOOK like a guess — it looked like a ratified fact — and an anchor duly
      summed across model. The operator ruled it non-additive on 2026-08-17.

    WHAT COUNTS AS RATIFICATION: `governance.ratified_by` naming a person or a team. A bare
    `last_reviewed` date does NOT — every concept in the measured bundle carries one and nobody read
    them; a date with no name against it records that a file was written, not that anyone read it.

    SEVERITY IS WARNING, and that is a ported judgement, not a softening. Flipping the stamps from C
    to I is an ONTOLOGY CHANGE and belongs to the operator; a check that fails their build overnight
    to force it would be making that decision for them. The escalation condition is stated in `note`
    and it is not open-ended: the moment any of these objects' answers is treated as authoritative,
    this is an error.

    WOULD FALSELY FIRE ON: a bundle that records ratification somewhere this does not look. Only
    `governance.ratified_by` is read here — `check_conformance.py`'s A4 finding accepts `ratified_on`
    and `approval_status: approved` as well, and the two therefore count differently ON PURPOSE: A4
    asks the weaker question (is ANY C unbacked, whoever wrote it), this asks the one nobody defends
    (did a MACHINE certify itself). If a bundle adopts a third spelling, this reader is where it goes.

    A LEGITIMATE CASE THAT MUST NOT FIRE: a harvested object honestly stamped `I` (inferred) or `Q`
    (needs SME) — the machine saying what it actually knows. Also a `C` on an `authored`/`tuned`
    object: a human wrote it and is answerable for it. Measured on fpl2: 6 of 22 concepts are human
    provenance and none is reported.

    MEASURED on fpl2: 16 of 22 concepts are harvested + C with no ratification (16 self-certified /
    0 honestly marked / 0 ratified / 6 human-authored or tuned). The brief carried 17 from an earlier
    measurement; 6 concepts have since moved to human provenance and the number today is 16.

    A ZERO HERE IS NOT A CLEAN BILL, and this is measured, not hedging. The check's precondition is a
    `metadata.provenance` stamp, and fpl2 is the ONLY bundle in the corpus that carries one: gold has
    20 of 31 concepts claiming C with no provenance stamp at all, hifa 13 of 14, contoso 8 of 8. All
    41 are invisible to MAC006 by construction and every one of them is caught by
    check_conformance.py's A4, which asks the weaker question. Widening this check to cover them would
    put one ruling in two homes — the exact defect MAC003 exists to report — so it stays narrow and
    A4 stays the general answer.
    """
    unearned = []
    for c in b.concepts():
        meta, gov = _meta(c.doc), _gov(c.doc)
        if M.provenance_of(c.doc) not in _MACHINE:
            continue
        if str(meta.get("confidence") or "").strip().upper() not in _CERTAIN:
            continue
        if gov.get("ratified_by"):
            continue
        unearned.append((c, meta, gov))
    if not unearned:
        return []

    witnesses = []
    for c, meta, gov in sorted(unearned, key=lambda x: x[0].stem):
        aggravating = []
        if gov.get("owner"):
            aggravating.append(f"owner {str(gov['owner'])!r} has no ratification on record")
        if str(meta.get("status") or "").strip().lower() == "draft":
            aggravating.append(f"status is {str(meta['status'])!r}, which the confidence stamp contradicts")
        if gov.get("last_reviewed"):
            aggravating.append(f"last_reviewed {gov['last_reviewed']} names nobody")
        path = "metadata.confidence"
        witnesses.append(Witness(
            c.doc.relpath, path, c.doc.line_of(path),
            f"provenance {str(meta.get('provenance'))!r} claims confidence "
            f"{str(meta.get('confidence'))!r}"
            + (" — " + "; ".join(aggravating) if aggravating else "")))
    return [Diagnostic(
        code="MAC006", severity=WARNING,
        summary=(f"{M.de(len(unearned))} machine-written object(s) claim confidence C — CONFORMANCE §1's "
                 f"L3, 'an SME has ratified the meaning' — with no ratification on record"),
        witnesses=witnesses,
        note=("a harvested object may honestly assert I (inferred) or Q (needs SME); C requires human "
              "authorship or an explicit `governance.ratified_by`. Warning, not error, because the "
              "flip from C to I is an ontology change and belongs to the operator — it becomes an "
              "error the moment any of these objects' answers is treated as authoritative."),
        source="check_confidence_earned")]


# ==================================================================================================
# MAC010 change-unprotocolled
# ==================================================================================================

_MANUAL = ("authored", "tuned")

# The change record is TWO registers because it answers two questions, and they are not the same
# question — see check_vanilla_delta's own header. Held here once; both standalone gates read it.
LEDGER = "interventions/ledger.yaml"
VANILLA_DELTA = "interventions/vanilla_delta.yaml"
CHANGE_RECORD = (
    (LEDGER, "interventions", "objects", "append-only HISTORY — which objects were touched, and why"),
    (VANILLA_DELTA, "deltas", "objects", "current STATE — what differs from what the generator emits"),
)


def _referenced(root, relpath: str, list_key: str, object_key: str) -> set | None:
    """Every '<kind>:<stem>' a change register names, or None when the register does not exist."""
    path = Path(root) / relpath
    if not path.exists():
        return None
    doc, _err = M.read_yaml(path)
    entries = doc.get(list_key) if isinstance(doc, dict) else doc
    refs: set = set()
    for entry in (entries if isinstance(entries, list) else []):
        if not isinstance(entry, dict):
            continue
        value = entry.get(object_key)
        for ref in (value if isinstance(value, list) else ([value] if value else [])):
            if isinstance(ref, str) and ref.strip():
                refs.add(ref.strip())
    return refs


def manual_objects(b) -> dict:
    """{'<kind>:<stem>': Object} for every object a human authored or tuned.

    THE identity a change register names. Exposed because both standalone gates need exactly this set
    and the point of porting was that there be one of it. Lookups are CSV registers carrying no
    metadata block, so they can never be stamped and are never counted as unstamped.
    """
    return {ref: obj for ref, obj in b.objects().items() if M.provenance_of(obj) in _MANUAL}


def unprotocolled(b) -> dict:
    """{register relpath: sorted refs of manual objects it does not name}, absent registers excluded.

    THE one implementation of the protocol question. `check_intervention_ledger` (its check E) and
    `check_vanilla_delta` (its check A) call this instead of walking the objects again; each still
    owns its own register's SHAPE rules, which are form, not meaning, and belong to it.
    """
    manual = set(manual_objects(b))
    out: dict = {}
    for relpath, list_key, object_key, _why in CHANGE_RECORD:
        refs = _referenced(b.root, relpath, list_key, object_key)
        if refs is None:
            continue
        out[relpath] = sorted(manual - refs)
    return out


def check_change_protocol(b) -> list:
    """An authored or tuned object with no entry in the change record.

    Every object got into a bundle one of two ways: it was HARVESTED (the generator emitted it from
    what the warehouse contains) or it was MANUALLY CHANGED (a human, or an agent acting as one,
    authored it, corrected it, retired it). Both are legitimate. What is not is a manual intervention
    nobody can see — a hand-edited transform, a concept whose meaning was DECIDED rather than
    OBSERVED — sitting in the tree with no record of who changed what, why, on what evidence, and who
    must ratify it. That is how a judgement call silently becomes "the data", and re-harvesting
    silently reverts it.

    TWO REGISTERS, TWO QUESTIONS, both required, because object-level protocol is not locus-level
    protocol. The ledger's entry names the OBJECT ("was this touched, and why"); the vanilla-delta's
    entry names the LOCUS ("what precisely differs from what the generator emits"). The ledger was
    green over a real defect for exactly this reason: an entry saying "full harmonization of the raw
    model dimension" is true and says nothing about the two hand-written token lists inside the file,
    one of which had been folding a distinct nameplate into another model.

    ADOPTION IS A WARNING, NOT AN ERROR. A bundle with no register at all has not yet adopted the
    protocol; failing it would make adoption a breaking change and is how a protocol gets skipped
    rather than adopted. A bundle that HAS the register and leaves an object out of it is an error —
    it is running the protocol and lying about coverage.

    WOULD FALSELY FIRE ON: an object stamped `authored`/`tuned` that is a wholesale hand-authored
    artifact rather than a modification of generated output — nothing generated it, so "differs from
    vanilla" has no baseline to differ from. That entry is trivial to write and writing it is the
    right answer, but a bundle adopting the delta register for the first time will see one witness per
    such object.

    A LEGITIMATE CASE THAT MUST NOT FIRE: a harvested object with no entry anywhere. Re-harvest
    overwrites it, there is nothing for a human to be answerable for, and demanding a record of it
    would bury the manual changes in noise — which is precisely what makes a register unreadable.
    Measured on fpl2: 42 of 76 objects are harvested and none is reported.

    MEASURED on fpl2: 18 manual objects (7 authored + 11 tuned) over 76; the ledger's 24 interventions
    name 46 objects and the delta register's 13 entries cover 19 — 0 unprotocolled in either. Green,
    and green on a real question rather than by not asking it.
    """
    manual = manual_objects(b)
    if not manual:
        return []
    out: list = []
    for relpath, list_key, object_key, why in CHANGE_RECORD:
        refs = _referenced(b.root, relpath, list_key, object_key)
        if refs is None:
            out.append(Diagnostic(
                code="MAC010", severity=WARNING,
                summary=(f"{M.de(len(manual))} object(s) were manually authored or tuned and "
                         f"{relpath} does not exist — the {why.split(' — ')[0]} half of the change "
                         f"record is unadopted, so those changes are unrecorded"),
                witnesses=[Witness(_where(o, b.root)[0], "metadata.provenance", _where(o, b.root)[1],
                                   f"{ref} is stamped {M.provenance_of(o)!r} and {relpath} holds no "
                                   f"entry for it")
                           for ref, o in sorted(manual.items())],
                note=f"adopt {relpath}: {why}. Warning only until the register exists, so adopting the "
                     f"protocol is never itself a breaking change.",
                source="check_change_protocol"))
            continue
        missing = sorted(set(manual) - refs)
        if not missing:
            continue
        out.append(Diagnostic(
            code="MAC010", severity=ERROR,
            summary=(f"{M.de(len(missing))} of {M.de(len(manual))} manually authored or tuned object(s) "
                     f"have no entry in {relpath} — a manual change the change record does not know "
                     f"about"),
            witnesses=[Witness(_where(manual[ref], b.root)[0], "metadata.provenance",
                               _where(manual[ref], b.root)[1],
                               f"{ref} is stamped {M.provenance_of(manual[ref])!r}; {relpath} "
                               f"({why}) names it nowhere")
                       for ref in missing],
            note=(f"either register the change in {relpath} or, if the object is in fact generator "
                  f"output, correct its `metadata.provenance` stamp. An unrecorded manual change is "
                  f"reverted by the next harvest and nobody learns why the number moved."),
            source="check_change_protocol"))
    return out


# ==================================================================================================
# the phase
# ==================================================================================================

SOURCE = "mac_checks_semantic"

# (check, the taxonomy codes it owns). The pairing is explicit because `run` needs it: when a check
# CRASHES the compiler must say WHICH CLASS of finding is now unknown. A phase that dies quietly
# reports a clean bundle, which is worse than reporting nothing — "0 MAC007" and "MAC007 was never
# computed" are opposite facts and they must not render the same. Same shape as the structural phase,
# so one driver and one dashboard serialiser cover both.
CHECKS = (
    (check_fact_homes, ("MAC003", "MAC004")),
    (check_dead_guards, ("MAC007",)),
    (check_confidence_earned, ("MAC006",)),
    (check_change_protocol, ("MAC010",)),
)


def run(b, root=None) -> list:
    """Every semantic finding this phase can make, in taxonomy order.

    `root` is accepted and ignored: a semantic check reads the bundle's resolved graph, never the
    tree, and `Bundle.root` already carries the path. It is in the signature so one driver loop can
    call this phase and the structural phase (which does need the tree) the same way.
    """
    out: list = []
    for check, codes in CHECKS:
        try:
            out.extend(check(b))
        except Exception as exc:                    # noqa: BLE001 — a broken check IS a finding
            out.append(Diagnostic(
                code=codes[0], severity=WARNING, source=f"{SOURCE}.{check.__name__}",
                summary=(f"{check.__name__} could not run, so every "
                         f"{' / '.join(codes)} finding in this bundle is UNKNOWN — not absent: {exc!r}"),
                note=("usually an upstream parse failure: fix the structural phase's MAC002 first, then "
                      "re-run. A phase that crashes silently reports a clean bundle; this makes the "
                      "hole visible.")))
    return sorted(out, key=lambda d: (d.code, d.severity))


def _as_dict(d: Diagnostic) -> dict:
    """The dashboard's serialisation — identical field-for-field to the structural phase's, so the
    persisted finding set has ONE shape however many phases produced it."""
    return {"code": d.code, "kind": d.kind, "severity": d.severity, "summary": d.summary,
            "note": d.note, "source": d.source,
            "witnesses": [{"file": w.file, "path": w.path, "line": w.line, "detail": w.detail}
                          for w in d.witnesses]}


def main(argv=None) -> int:
    import argparse
    import json

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("root", help="bundle root (a MAC source container)")
    ap.add_argument("--show", default=WARNING, choices=[ERROR, WARNING, INFO],
                    help="least severity printed (default: warning)")
    ap.add_argument("--json", action="store_true", help="emit the finding set as JSON")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"root not found: {root}", file=sys.stderr)
        return 2

    b = M.load(root)
    diags = run(b, str(root))
    stats = summarise(diags)

    if args.json:
        print(json.dumps({"schema": "mac.diagnostics/semantic/1", "bundle": str(root),
                          "phase": "semantic", "stats": stats,
                          "diagnostics": [_as_dict(d) for d in diags]}, indent=2, default=str))
        return 1 if stats["errors"] else 0

    codes = ", ".join(c for _f, cs in CHECKS for c in cs)
    print(f"── semantic phase ── {M.de(len(CHECKS))} checks ({codes}) over "
          f"{M.de(len(b.concepts()))} concept(s), {M.de(len(b.objects()))} object(s), "
          f"{M.de(len(b.registers()))} register(s) under {root} ──\n")
    body = render(diags, str(root), show=args.show)
    if body:
        print(body + "\n")
    by_code = ", ".join(f"{c} x{M.de(n)}" for c, n in sorted(stats["by_code"].items()))
    print(f"{M.de(stats['errors'])} error(s), {M.de(stats['warnings'])} warning(s) over "
          f"{M.de(stats['total'])} diagnostic(s) carrying {M.de(stats['witnesses'])} witness(es)"
          + (f"  [{by_code}]" if by_code else ""))
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
