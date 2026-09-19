#!/usr/bin/env python3
"""A SEAM must answer a host in ONE declared envelope — or be refused. SEAM_CONTRACT.md, enforced.

    python3 tools/check_seam_contract.py <fixture-bundle-root> [--json] [--self-test]
                                         [--seam ID] [--corruptions N] [--floor-python PATH]

WHAT FORCED THIS GATE
---------------------
Five incidents in one working day, every one the same act: a surface served a derivation it could
not vouch for, and nothing the reader saw said so. The repair was three framework-side tools —
`project_objects.py`, `project_edges.py`, `project_concept_page.py` — and each was written by
COPYING the previous one. On the host side each needed its own handler, its own cache, its own lock
table and its own fallback. That duplication IS the API being asked for, arrived at three times by
copy instead of once by design, and the copies do not agree with each other:

  * 6 top-level keys on success from one, 5 from another, 3 from the third — and the first drops to
    3 of its 6 on a failure exit, so a client reading one of those keys reads a key that exists only
    when nothing went wrong.
  * `absent[]` is the ONE field all three agree on the name of, and it enumerates 6 planes in one,
    2 files in another and 2 paths in the third: a bare `absent: []` carries three denominators and
    therefore none.
  * one fact, three spellings: `unparsed[].error`, `unparsed[].reason`, and a scalar parse-error
    folded into a per-file block.
  * 1 of 3 carries a `state` token at all — with 8 values in its code, 6 in its own docstring and 5
    in the host's comment about it.

Two more seams are queued. A contract written after five of them is a contract written after the
argument; this gate exists so the fourth is judged against the third's lessons rather than copied
from the third's code.

WHAT IT REFUSES TO DO, each a way to be green for the wrong reason
------------------------------------------------------------------
 1. never trust a DECLARATION it can measure. `inputs[]` is checked against a `sys.addaudithook`
    open-trace of the real run, because the measurement says authors forget: one seam enumerates 6
    planes in `absent[]` and parse-checks only 4 of them, and two framework readers swallow a failed
    parse with a bare `except`, so a truncated input can cost a whole view class while the payload
    stays byte-identical to a clean one. A manifest cannot catch what its author did not know he
    read (INPUT_UNDECLARED, FRAMEWORK_UNDECLARED, DEGRADE_UNSIGNALLED).
 2. never write inside the bundle it is pointed at. The corruption probe operates on a COPY in a
    temporary directory, made by this gate and deleted by it. The fixture the operator names is
    read-only to this gate, exactly as it is to the seams.
 3. never judge an empty population. A subject seam pointed at a bundle declaring 0 members REFUSES
    (exit 2) rather than reporting a green it measured nothing for.
 4. never silently exempt a clause it could not exercise. A clause that could not be judged — no
    floor interpreter on this machine, a probe that emitted no envelope — is PRINTED as not judged
    with its denominator. An exemption nobody can see is a hole.
 5. never repair a seam. This gate produces findings; the migration is a separate act with its own
    risk, and a gate that edited the thing it judges would be judging its own work.
 6. never restate the contract's registry twice. `SEAMS` below is the ONE home for the per-seam
    values; SEAM_CONTRACT.md declares the columns and lists no rows.

THE REJECT CLASSES (exit 1). One per contract clause, one seeded mutant each in --self-test.
    ENVELOPE_UNVERSIONED  no `envelope: "mac.seam/1"`. A host cannot refuse intelligibly against a
                          format it cannot name, and every field below moves under it.
    RESULT_UNKEYED        the principal result is not under the fixed key `result`. Three content
                          keys is three host literals for the empty payload and three emptiness
                          tests — four of the six per-seam values the host re-encodes today.
    MODE_UNDECLARED       no `mode`. The degrade/refuse decision is then the author's taste, and the
                          host infers it from an emptiness heuristic whose branch is unreachable.
    MODE_CONTRADICTED     `mode` declared and the payload says otherwise. The declaration is
                          re-derived from the bytes so taste cannot enter.
    STATUS_UNCLOSED       `status` absent or outside the closed seam-minted set. The estate's one
                          closed vocabulary is stated as 5, 6 and 8 in three files today.
    REASON_UNBOUND        `reason` is not present-and-null exactly when the status is `derived`. A
                          consumer cannot tell "key absent" from "reason: null".
    PARTIAL_UNBOUND       `partial != []` and `status == "degraded"` are not the same fact, or a
                          document-mode payload carries a partial. Today the host infers degradation
                          from emptiness, and across 2 index routes and 3 failure causes there are
                          0 reachable served-with-ok-false states: the degrade nobody ships.
    DENOMINATOR_MISSING   index mode without `counts.returned/declared`. A zero with no denominator
                          is incident one: "0 of ?" and "0 of 0" render identically.
    SHAPE_VARIES          the top-level key set is not the same on success and on failure.
    INPUT_UNDECLARED      the run OPENED a file under the bundle that `inputs[]` does not cover.
    FRAMEWORK_UNDECLARED  the run opened a framework-side DATA file that no `role: framework` input
                          declares. That is the cache hole: the host's key stats the bundle only, so
                          editing the framework changes every answer and moves no key.
    SEAM_UNSTAMPED        no `seam {tool, version, framework_root, code_id}`. Nothing in any payload
                          today names which framework tree answered, and the host's locator silently
                          prefers an installed root over a sibling checkout.
    PATH_LEAKED           an absolute filesystem path outside `local`. All three stamp the
                          operator's disk path today; only the host's wholesale drop keeps it off
                          the wire.
    ARGV_SILENT           exit 2 with an empty stdout. All three docstrings promise "even then a
                          structured reason goes to stdout"; measured, 3 of 3 print 0 bytes there.
    FLOOR_BROKEN          the seam does not run on its declared interpreter floor. Measured: 1 of 3
                          exits 1 with 0 bytes on the interpreter its own usage line documents, for
                          an alias two later seams carry an explicit comment about avoiding.
    DEGRADE_UNSIGNALLED   one traced input corrupted, and the answer did not change. The failure is
                          then invisible in the payload by construction, whichever side of the
                          degrade/refuse rule the seam is on.

EXIT CODES. 0 clean · 1 a finding about a seam · 2 could not run (root is not a directory, an empty
population, no seam registered). Every verdict line carries its denominator.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:                                                        # noqa: E402
    sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mac_diag as D                                                             # noqa: E402
import mac_project as P                                                          # noqa: E402

NAME = "check_seam_contract"
CONTRACT = "mac.seam/1"

ENVELOPE_UNVERSIONED = "ENVELOPE_UNVERSIONED"
RESULT_UNKEYED = "RESULT_UNKEYED"
MODE_UNDECLARED = "MODE_UNDECLARED"
MODE_CONTRADICTED = "MODE_CONTRADICTED"
STATUS_UNCLOSED = "STATUS_UNCLOSED"
REASON_UNBOUND = "REASON_UNBOUND"
PARTIAL_UNBOUND = "PARTIAL_UNBOUND"
DENOMINATOR_MISSING = "DENOMINATOR_MISSING"
SHAPE_VARIES = "SHAPE_VARIES"
INPUT_UNDECLARED = "INPUT_UNDECLARED"
FRAMEWORK_UNDECLARED = "FRAMEWORK_UNDECLARED"
SEAM_UNSTAMPED = "SEAM_UNSTAMPED"
PATH_LEAKED = "PATH_LEAKED"
ARGV_SILENT = "ARGV_SILENT"
FLOOR_BROKEN = "FLOOR_BROKEN"
DEGRADE_UNSIGNALLED = "DEGRADE_UNSIGNALLED"

CLASSES = (ENVELOPE_UNVERSIONED, RESULT_UNKEYED, MODE_UNDECLARED, MODE_CONTRADICTED, STATUS_UNCLOSED,
           REASON_UNBOUND, PARTIAL_UNBOUND, DENOMINATOR_MISSING, SHAPE_VARIES, INPUT_UNDECLARED,
           FRAMEWORK_UNDECLARED, SEAM_UNSTAMPED, PATH_LEAKED, ARGV_SILENT, FLOOR_BROKEN,
           DEGRADE_UNSIGNALLED)

#: SEAM_CONTRACT.md §4.1 — the closed set a SEAM may mint. The host-minted four (seam_missing,
#: seam_failed, seam_timeout, seam_unreadable) are deliberately NOT here: a seam that could not
#: speak cannot name its own failure, which is why the vocabulary is partitioned by emitter.
SEAM_MINTED = ("derived", "degraded", "absent_input", "unparsed_input", "not_found",
               "author_failed", "bad_request")
#: §5.1 — which tokens may be SERVED, per mode. This is the whole of the degrade/refuse rule.
SERVE_ELIGIBLE = {"index": {"derived", "degraded", "absent_input"}, "document": {"derived"}}
#: §3 — present on EVERY exit, at the empty value of their own type. `local` is the one optional.
RESERVED = ("envelope", "mode", "status", "reason", "result", "counts", "inputs", "partial",
            "seam", "subject", "derived_at", "aux")
SEAM_STAMP = ("tool", "version", "framework_root", "code_id")
INPUT_ROLES = ("spine", "row", "attribute", "framework")
#: Keys whose value moves between two runs of the same seam over the same bytes. Normalised out
#: before two payloads are compared, so DEGRADE_UNSIGNALLED measures MEANING, not the clock.
VOLATILE = ("derived_at", "at", "observed_at", "snapshot_at")


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE REGISTRY — the one home for the per-seam values. A seam that is not a row here is not judged,
# and that is the only way to be unjudged: SEAM_CONTRACT.md declares these COLUMNS and lists no rows.
# `floor` is the interpreter floor the seam promises (SEAM_CONTRACT.md §4.4) — a clause, not a habit.
# ══════════════════════════════════════════════════════════════════════════════════════════════════
class Seam:
    def __init__(self, sid, tool, subject=None, floor=(3, 9)):
        self.id, self.tool, self.subject, self.floor = sid, tool, subject, floor

    def argv(self, root, subject_id=None):
        a = [str(root)]
        if self.subject:
            a += [f"--{self.subject}", subject_id if subject_id is not None else ""]
        return a


SEAMS = (
    Seam("objects", "project_objects.py"),
    Seam("edges", "project_edges.py"),
    Seam("concept-page", "project_concept_page.py", subject="concept"),
)


class Finding:
    def __init__(self, cls, where, detail):
        self.cls, self.where, self.detail = cls, where, detail

    def __str__(self):
        return f"  [{self.cls:<20}] {self.where}\n          {self.detail}"

    def as_dict(self):
        return {"class": self.cls, "where": self.where, "detail": self.detail}


class Probe:
    """One invocation of one seam, with what it printed and what it OPENED."""

    def __init__(self, label, rc, stdout="", stderr="", bundle_opens=(), framework_opens=(),
                 interpreter="", argv=()):
        self.label, self.rc, self.stdout, self.stderr = label, rc, stdout, stderr
        self.bundle_opens = list(bundle_opens)
        self.framework_opens = list(framework_opens)
        self.interpreter, self.argv = interpreter, list(argv)
        self.payload, self.parse_error = None, None
        if stdout.strip():
            try:
                obj = json.loads(stdout)
                self.payload = obj if isinstance(obj, dict) else None
                if self.payload is None:
                    self.parse_error = f"stdout is a JSON {type(obj).__name__}, not one object"
            except Exception as exc:                                             # noqa: BLE001
                self.parse_error = str(exc)


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE JUDGE — PURE. No filesystem, no subprocess: it takes probes and returns findings, so every
# reject class is exercised offline against a seeded envelope in --self-test.
# ══════════════════════════════════════════════════════════════════════════════════════════════════
def _mode_of(payload):
    """The mode the payload DECLARES, or None. Never inferred — inference is what this replaces."""
    m = payload.get("mode")
    return m if m in ("index", "document") else None


def _walk_strings(node, path="$"):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk_strings(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_strings(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


_ABS = re.compile(r"^(?:/[^/\0]+){2,}/?$|^[A-Za-z]:[\\/]")


def _covers(declared, opened):
    """Does a declared input path cover an opened root-relative path? Exact, or a plane prefix."""
    d = declared.rstrip("/")
    return opened == d or opened.startswith(d + "/")


def _normalise(payload):
    """A payload with the clock removed, for comparing two runs over different bytes."""
    def strip(node):
        if isinstance(node, dict):
            return {k: strip(v) for k, v in sorted(node.items()) if k not in VOLATILE}
        if isinstance(node, list):
            return [strip(v) for v in node]
        return node
    return json.dumps(strip(payload), sort_keys=True, ensure_ascii=False)


def judge(seam, probes):
    """(seam spec, probes) -> (findings, verdict per class, counts). Pure."""
    findings, counts = [], Counter()
    verdict = {}

    def fail(cls, where, detail):
        findings.append(Finding(cls, where, detail))
        verdict[cls] = "FAIL"

    def ok(cls):
        verdict.setdefault(cls, "pass")

    def unjudged(cls, why):
        if verdict.get(cls) != "FAIL":
            verdict[cls] = f"not judged — {why}"

    by = {p.label: p for p in probes}
    main = by.get("derived")
    served = [p for p in probes if p.payload is not None]
    counts["probes"] = len(probes)
    counts["probes_with_envelope"] = len(served)
    counts["bundle_opens"] = len(main.bundle_opens) if main else 0
    counts["framework_opens"] = len(main.framework_opens) if main else 0

    if main is None or main.payload is None:
        for c in CLASSES:
            unjudged(c, "the derive probe emitted no envelope")
        if main is not None:
            fail(STATUS_UNCLOSED, f"{seam.id} · derive probe",
                 f"exit {main.rc} and stdout carries no JSON object "
                 f"({main.parse_error or f'{len(main.stdout)} byte(s)'}). A seam's answer is one "
                 f"JSON object on stdout on every exit it is allowed to take")
        return findings, verdict, counts

    pay = main.payload
    mode = _mode_of(pay)

    # 1 ENVELOPE_UNVERSIONED ────────────────────────────────────────────────────────────────────
    bad = [p.label for p in served if p.payload.get("envelope") != CONTRACT]
    counts["envelope_ok"] = len(served) - len(bad)
    if bad:
        fail(ENVELOPE_UNVERSIONED, f"{seam.id} · {len(bad)} of {len(served)} envelope(s)",
             f"no `envelope: {CONTRACT!r}` on probe(s) {bad}. The host cannot say WHICH contract it "
             f"is refusing against, so a field that moves reads to the client as a field that is "
             f"missing")
    else:
        ok(ENVELOPE_UNVERSIONED)

    # 2 RESULT_UNKEYED ──────────────────────────────────────────────────────────────────────────
    if "result" not in pay:
        fail(RESULT_UNKEYED, f"{seam.id} · derive probe",
             f"the principal result is not under `result`; the top-level keys are "
             f"{sorted(pay)}. Three seams with three content keys is three empty-payload literals "
             f"and three emptiness tests in the host, re-encoded per route")
    else:
        ok(RESULT_UNKEYED)

    # 3 MODE_UNDECLARED ─────────────────────────────────────────────────────────────────────────
    if mode is None:
        fail(MODE_UNDECLARED, f"{seam.id} · derive probe",
             f"declares no `mode` (index|document); found {pay.get('mode')!r}. Without it the "
             f"degrade/refuse decision is the author's taste on the day, and the host infers it "
             f"from `not result and ok is False` — a branch that is unreachable, because every "
             f"path that sets ok false also empties the result")
    else:
        ok(MODE_UNDECLARED)

    # 4 MODE_CONTRADICTED ───────────────────────────────────────────────────────────────────────
    if mode is None:
        unjudged(MODE_CONTRADICTED, "no mode is declared to contradict")
    else:
        res, why = pay.get("result"), []
        if mode == "index":
            if not isinstance(res, list):
                why.append(f"`result` is {type(res).__name__}, not a list")
            if not isinstance((pay.get("counts") or {}).get("declared"), int):
                why.append("`counts.declared` is not an int, so `N of M` cannot be published")
            if "partial" not in pay:
                why.append("no `partial[]`")
            roles = {i.get("role") for i in (pay.get("inputs") or []) if isinstance(i, dict)}
            if "spine" not in roles:
                why.append("no `inputs[]` entry carries role `spine`, so nothing says which input "
                           "ENUMERATES the members")
        else:
            if isinstance(res, list):
                why.append("`result` is a list — a collection is index mode, and index mode is the "
                           "only mode that may serve an incomplete answer")
            if pay.get("partial"):
                why.append("`partial` is non-empty in document mode; half a document is a "
                           "different document, not a partial one")
            if pay.get("status") == "degraded":
                why.append("`status: degraded` in document mode")
        if why:
            fail(MODE_CONTRADICTED, f"{seam.id} · declares mode {mode!r}", "; ".join(why))
        else:
            ok(MODE_CONTRADICTED)

    # 5 STATUS_UNCLOSED ─────────────────────────────────────────────────────────────────────────
    bad = [(p.label, p.payload.get("status")) for p in served
           if p.payload.get("status") not in SEAM_MINTED]
    counts["status_ok"] = len(served) - len(bad)
    if bad:
        fail(STATUS_UNCLOSED, f"{seam.id} · {len(bad)} of {len(served)} envelope(s)",
             f"`status` absent or outside the closed set {list(SEAM_MINTED)}: {bad}. A token exists "
             f"only where a caller BRANCHES; the sentence in `reason` stays open, but the host "
             f"cannot branch on prose and today reconstructs the distinction from an exit code it "
             f"already had")
    else:
        ok(STATUS_UNCLOSED)

    # 6 REASON_UNBOUND ──────────────────────────────────────────────────────────────────────────
    bad = []
    for p in served:
        q = p.payload
        if "reason" not in q:
            bad.append(f"{p.label}: key absent")
        elif (q.get("status") == "derived") != (q.get("reason") is None):
            bad.append(f"{p.label}: status={q.get('status')!r} reason={str(q.get('reason'))[:40]!r}")
    if bad:
        fail(REASON_UNBOUND, f"{seam.id} · {len(bad)} of {len(served)} envelope(s)",
             f"`reason` is required on EVERY exit and is null exactly when the status is `derived`: "
             f"{bad}. A key that is absent on success and present on failure cannot be told from "
             f"one that is null, and the sentence is the half a person acts on")
    else:
        ok(REASON_UNBOUND)

    # 7 PARTIAL_UNBOUND ─────────────────────────────────────────────────────────────────────────
    bad = []
    for p in served:
        q, m = p.payload, _mode_of(p.payload)
        if m == "index" and "partial" not in q:
            bad.append(f"{p.label}: index mode with no `partial[]`")
        elif bool(q.get("partial")) != (q.get("status") == "degraded"):
            bad.append(f"{p.label}: partial={len(q.get('partial') or [])} status={q.get('status')!r}")
        elif m == "document" and q.get("partial"):
            bad.append(f"{p.label}: document mode carries a partial")
    if bad:
        fail(PARTIAL_UNBOUND, f"{seam.id} · {len(bad)} of {len(served)} envelope(s)",
             f"`partial != []` and `status == degraded` must be ONE fact: {bad}. The host must "
             f"never have to guess from an empty result whether it is looking at a measurement or "
             f"at a failure — that guess is the whole of the five-incident class")
    else:
        ok(PARTIAL_UNBOUND)

    # 8 DENOMINATOR_MISSING ─────────────────────────────────────────────────────────────────────
    idx = [p for p in served if _mode_of(p.payload) == "index"
           or (mode is None and isinstance(p.payload.get("result"), list))]
    if not idx:
        unjudged(DENOMINATOR_MISSING,
                 "no probe declares index mode and none carries a list `result`")
    else:
        bad = []
        for p in idx:
            c = p.payload.get("counts")
            if not isinstance(c, dict) or not isinstance(c.get("declared"), int) \
                    or not isinstance(c.get("returned"), int):
                bad.append(f"{p.label}: counts={c!r}")
        if bad:
            fail(DENOMINATOR_MISSING, f"{seam.id} · {len(bad)} of {len(idx)} index envelope(s)",
                 f"no `counts {{returned, declared}}`: {bad}. A zero with no denominator is "
                 f"incident one: `0 of ?` (the plane could not be read) and `0 of 0` (nothing is "
                 f"authored) render as the same empty list on the same page")
        else:
            ok(DENOMINATOR_MISSING)

    # 9 SHAPE_VARIES ────────────────────────────────────────────────────────────────────────────
    shapes = {}
    for p in served:
        shapes.setdefault(tuple(sorted(p.payload)), []).append(f"{p.label}(exit {p.rc})")
    counts["shapes"] = len(shapes)
    exits = sorted({p.rc for p in served})
    if len(served) < 2:
        unjudged(SHAPE_VARIES, f"only {len(served)} probe(s) emitted an envelope, so no two key "
                               f"sets could be compared")
    elif not any(rc != 0 for rc in exits):
        # COMPARING SUCCESS TO SUCCESS PROVES NOTHING. The clause is about the key set holding
        # across success AND failure, and the one seam measured to drop 3 of its 6 keys does so
        # only when its author RAISES — a state no probe here reached. A pass over 23 successful
        # envelopes would be exactly the false green this gate exists to refuse.
        unjudged(SHAPE_VARIES,
                 f"every one of the {len(served)} envelope(s) came from exit 0 ({exits}); no probe "
                 f"reached a failure exit, so the success/failure comparison was not made")
    elif len(shapes) > 1:
        allk = set().union(*[set(s) for s in shapes])
        common = set.intersection(*[set(s) for s in shapes])
        fail(SHAPE_VARIES, f"{seam.id} · {len(shapes)} key set(s) over {len(served)} envelope(s)",
             f"{[f'{list(v)}: {list(k)}' for k, v in shapes.items()]}; the keys that come and go are "
             f"{sorted(allk - common)}. A reserved key is present on EVERY exit at its own empty "
             f"value, or a client is reading a key that exists only when nothing went wrong")
    else:
        ok(SHAPE_VARIES)

    # 10 INPUT_UNDECLARED — measured, not declared ─────────────────────────────────────────────
    declared = [i for i in (pay.get("inputs") or []) if isinstance(i, dict)]
    dpaths = [str(i.get("path") or "") for i in declared]
    bad_role = [i.get("role") for i in declared if i.get("role") not in INPUT_ROLES]
    uncovered = [o for o in main.bundle_opens
                 if not any(_covers(d, o) for d in dpaths if not d.startswith("framework:"))]
    counts["bundle_declared"] = len(main.bundle_opens) - len(uncovered)
    if uncovered or bad_role:
        head = f"{len(uncovered)} of {len(main.bundle_opens)} file(s) this run OPENED under the " \
               f"bundle are named by no `inputs[]` entry ({len(dpaths)} declared)"
        fail(INPUT_UNDECLARED, f"{seam.id} · derive probe",
             f"{head}: {sorted(uncovered)[:8]}{' …' if len(uncovered) > 8 else ''}"
             + (f"; role(s) outside {list(INPUT_ROLES)}: {bad_role}" if bad_role else "")
             + ". The trace is the judge here because a manifest cannot catch what its author did "
               "not know he read — measured today, one seam enumerates 6 planes and parse-checks 4")
    else:
        ok(INPUT_UNDECLARED)

    # 11 FRAMEWORK_UNDECLARED — the cache hole ──────────────────────────────────────────────────
    fdecl = [d.split(":", 1)[1] for d in dpaths if d.startswith("framework:")]
    funcov = [o for o in main.framework_opens if o not in fdecl and Path(o).name not in fdecl]
    counts["framework_declared"] = len(main.framework_opens) - len(funcov)
    if funcov:
        fail(FRAMEWORK_UNDECLARED, f"{seam.id} · derive probe",
             f"{len(funcov)} of {len(main.framework_opens)} framework-side DATA file(s) this run "
             f"opened are declared by no `framework:` input: {sorted(funcov)}. The host's cache key "
             f"stats the BUNDLE tree only, so editing one of these changes every answer and moves "
             f"no key — the console then serves payloads derived under rules that no longer exist")
    elif not main.framework_opens:
        unjudged(FRAMEWORK_UNDECLARED,
                 "this fixture caused 0 framework-side data reads; the trace is a LOWER BOUND "
                 "(one framework input is read only for some subjects)")
    else:
        ok(FRAMEWORK_UNDECLARED)

    # 12 SEAM_UNSTAMPED ─────────────────────────────────────────────────────────────────────────
    stamp = pay.get("seam")
    missing = [k for k in SEAM_STAMP if not isinstance(stamp, dict) or not stamp.get(k)]
    if missing:
        fail(SEAM_UNSTAMPED, f"{seam.id} · derive probe",
             f"no `seam {{{', '.join(SEAM_STAMP)}}}` (missing {missing}). Nothing in the payload "
             f"names which framework tree answered — and the host's locator prefers an installed "
             f"root and falls back to a sibling checkout without saying so, which makes the tree "
             f"that answered an unstated variable and the cache key unclosable")
    else:
        ok(SEAM_UNSTAMPED)

    # 13 PATH_LEAKED ────────────────────────────────────────────────────────────────────────────
    leaks = []
    for p in served:
        for where, val in _walk_strings({k: v for k, v in p.payload.items() if k != "local"}):
            if _ABS.match(val):
                leaks.append(f"{p.label} {where}")
    if leaks:
        fail(PATH_LEAKED, f"{seam.id} · {len(leaks)} value(s)",
             f"an absolute filesystem path outside `local`: {leaks[:6]}"
             f"{' …' if len(leaks) > 6 else ''}. A seam is answering about a BUNDLE, not about one "
             f"operator's disk; today the only thing keeping this off the wire is that the host "
             f"discards the whole block it sits in")
    else:
        ok(PATH_LEAKED)

    # 14 ARGV_SILENT ────────────────────────────────────────────────────────────────────────────
    ba = by.get("bad-argv")
    if ba is None:
        unjudged(ARGV_SILENT, "no bad-argv probe was run")
    elif ba.payload is None:
        fail(ARGV_SILENT, f"{seam.id} · bad-argv probe (exit {ba.rc})",
             f"{len(ba.stdout)} byte(s) on stdout"
             + (f" ({ba.parse_error})" if ba.parse_error else "")
             + ". All three seams promise in prose that `even then a structured reason goes to "
               "stdout`; a caller error is exactly when a caller needs the structured reason, and "
               "the host's `if out:` test cannot tell a silent success from a silent failure")
    elif ba.rc != 2 or ba.payload.get("status") != "bad_request":
        fail(ARGV_SILENT, f"{seam.id} · bad-argv probe",
             f"exit {ba.rc} with status {ba.payload.get('status')!r}; a caller error before any "
             f"derivation is exit 2 with `status: bad_request`")
    else:
        ok(ARGV_SILENT)

    # 15 FLOOR_BROKEN ───────────────────────────────────────────────────────────────────────────
    fl = by.get("floor")
    floor = ".".join(str(x) for x in seam.floor)
    if fl is None:
        unjudged(FLOOR_BROKEN, f"no interpreter at or near the declared floor {floor} on this "
                               f"machine, so the clause was not exercised")
    elif fl.payload is None or fl.rc == 1:
        tail = (fl.stderr.strip().splitlines() or [""])[-1][:120]
        fail(FLOOR_BROKEN, f"{seam.id} · floor {floor} ({fl.interpreter})",
             f"exit {fl.rc}, {len(fl.stdout)} byte(s) on stdout — {tail!r}. The seam does not run "
             f"on the interpreter its own usage line documents, and exit 1 with an empty stdout is "
             f"the one failure NO seam names: the promise `a failure is named, never silent` holds "
             f"only after import")
    else:
        ok(FLOOR_BROKEN)

    # 16 DEGRADE_UNSIGNALLED ────────────────────────────────────────────────────────────────────
    base = by.get("corrupt-baseline")
    corrupts = [p for p in probes if p.label.startswith("corrupt:")]
    if base is None or base.payload is None or not corrupts:
        unjudged(DEGRADE_UNSIGNALLED,
                 "no corruption probe was run (use --corruptions, and a baseline in the copy)")
    else:
        ref = _normalise(base.payload)
        silent = [p.label.split(":", 1)[1] for p in corrupts
                  if p.payload is not None and _normalise(p.payload) == ref]
        counts["corruptions"] = len(corrupts)
        counts["corruptions_signalled"] = len(corrupts) - len(silent)
        if silent:
            fail(DEGRADE_UNSIGNALLED,
                 f"{seam.id} · {len(silent)} of {len(corrupts)} traced input(s)",
                 f"corrupting the file changed NOTHING in the answer: {sorted(silent)[:8]}"
                 f"{' …' if len(silent) > 8 else ''}. Whichever side of the degrade/refuse rule "
                 f"this seam is on, a failure it cannot see is a failure it cannot name — the "
                 f"payload is byte-identical to a clean run, so the page reads as a clean "
                 f"derivation while a section of it is silently short")
        else:
            ok(DEGRADE_UNSIGNALLED)

    for c in CLASSES:
        verdict.setdefault(c, "not judged — no probe exercised it")
    return findings, verdict, counts


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE RUNNER. Every probe is a subprocess under an audit hook, so what a seam READ is measured
# rather than taken from its docstring — three of three docstrings disagree with their own code
# about their input set. The gate writes NOTHING inside the fixture: the corruption probe works on
# a copy in a temporary directory, and deletes it.
# ══════════════════════════════════════════════════════════════════════════════════════════════════
_TRACER = r'''
import json, os, runpy, sys
_seen, _out = [], os.environ["SEAM_TRACE_OUT"]
def _hook(ev, args):
    if ev == "open":
        try:
            _seen.append([str(args[0]), str(args[1])])
        except Exception:
            pass
sys.argv = sys.argv[1:]
_tool = sys.argv[0]
sys.addaudithook(_hook)
_rc = 0
try:
    runpy.run_path(_tool, run_name="__main__")
except SystemExit as e:
    _rc = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
except BaseException:
    import traceback
    traceback.print_exc()
    _rc = 1
try:
    with open(_out, "w") as fh:
        json.dump(_seen, fh)
except Exception:
    pass
sys.exit(_rc)
'''


def _classify(trace, bundle_root, framework_root):
    """(files read under the bundle, framework-side DATA files read) — both root-relative."""
    b, f = set(), set()
    for item in trace:
        try:
            raw, mode = item[0], item[1]
        except Exception:                                                        # noqa: BLE001
            continue
        if "r" not in mode:
            continue
        try:
            p = Path(raw).resolve()
        except Exception:                                                        # noqa: BLE001
            continue
        try:
            b.add(str(p.relative_to(bundle_root)))
            continue
        except ValueError:
            pass
        try:
            rel = p.relative_to(framework_root)
        except ValueError:
            continue
        if p.suffix in (".py", ".pyc") or "__pycache__" in rel.parts:
            continue                       # the CODE that answered is `seam.code_id`, not an input
        f.add(str(rel))
    return sorted(b), sorted(f)


def _probe(label, interp, tool, args, bundle_root, framework_root, timeout=120):
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td) / "_seam_trace_runner.py"
        tp.write_text(_TRACER, encoding="utf-8")
        op = Path(td) / "trace.json"
        env = dict(os.environ)
        env["SEAM_TRACE_OUT"] = str(op)
        env.pop("PYTHONPATH", None)
        try:
            pr = subprocess.run([interp, str(tp), str(tool), *args], capture_output=True,
                                text=True, env=env, timeout=timeout)
            rc, out, err = pr.returncode, pr.stdout, pr.stderr
        except subprocess.TimeoutExpired:
            rc, out, err = 124, "", f"timed out after {timeout}s"
        trace = []
        if op.exists():
            try:
                trace = json.loads(op.read_text(encoding="utf-8"))
            except Exception:                                                    # noqa: BLE001
                trace = []
    b, f = _classify(trace, bundle_root, framework_root)
    return Probe(label, rc, out, err, b, f, interpreter=interp, argv=list(args))


def _floor_interpreter(floor):
    """The LOWEST interpreter on this machine at or above the declared floor, or None.

    Running only on `sys.executable` is how the floor defect survived three seams: the host calls
    them with its own venv, and the interpreter the docstrings name is a different program.
    """
    want = ".".join(str(x) for x in floor)
    cands = [f"python{want}", f"/usr/bin/python{want}", "/usr/bin/python3",
             shutil.which(f"python{want}") or "", sys.executable]
    best = None
    for c in cands:
        if not c:
            continue
        exe = shutil.which(c) if not os.path.isabs(c) else (c if os.path.exists(c) else None)
        if not exe:
            continue
        try:
            v = subprocess.run([exe, "-c", "import sys;print('%d.%d' % sys.version_info[:2])"],
                               capture_output=True, text=True, timeout=30).stdout.strip()
            ver = tuple(int(x) for x in v.split("."))
        except Exception:                                                        # noqa: BLE001
            continue
        if ver >= tuple(floor) and (best is None or ver < best[1]):
            best = (exe, ver)
    return best


_CORRUPT = b"{{{ this file was corrupted by check_seam_contract -- not YAML, not JSON ]]]\n\t:- :\n"


def probes_for(seam, root, framework_root, subject_id, corruptions, floor_exe):
    """Every probe this gate makes of one seam. The fixture is never written to."""
    tool = Path(framework_root) / "tools" / seam.tool
    out = [_probe("derived", sys.executable, tool, seam.argv(root, subject_id), root,
                  framework_root)]
    with tempfile.TemporaryDirectory() as td:
        empty = Path(td) / "empty-bundle"
        empty.mkdir()
        out.append(_probe("empty-root", sys.executable, tool, seam.argv(empty, subject_id), empty,
                          framework_root))
        out.append(_probe("bad-argv", sys.executable, tool,
                          seam.argv(Path(td) / "no-such-root", subject_id), root, framework_root))
    if seam.subject:
        out.append(_probe("unknown-subject", sys.executable, tool,
                          seam.argv(root, "zzz-no-such-member-zzz"), root, framework_root))
    if floor_exe:
        out.append(_probe("floor", floor_exe, tool, seam.argv(root, subject_id), root,
                          framework_root))

    traced = list(out[0].bundle_opens)
    if corruptions != 0 and traced:
        if corruptions > 0:
            traced = traced[:corruptions]
        with tempfile.TemporaryDirectory() as td:
            copy = Path(td) / "bundle"
            shutil.copytree(root, copy, symlinks=True)
            out.append(_probe("corrupt-baseline", sys.executable, tool,
                              seam.argv(copy, subject_id), copy, framework_root))
            for rel in traced:
                target = copy / rel
                if not target.is_file():
                    continue
                keep = target.read_bytes()
                try:
                    target.write_bytes(_CORRUPT)
                    out.append(_probe(f"corrupt:{rel}", sys.executable, tool,
                                      seam.argv(copy, subject_id), copy, framework_root))
                finally:
                    target.write_bytes(keep)
    return out


def _subject_id(seam, root):
    """The member a subject seam is asked about, DISCOVERED from the fixture, never hardcoded."""
    if not seam.subject:
        return None
    stems = sorted(f.stem for f in P.concept_files(root))
    return stems[0] if stems else None


# ══════════════════════════════════════════════════════════════════════════════════════════════════
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", help="a FIXTURE bundle root; read-only to this gate")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--seam", action="append", help="judge only this seam id (repeatable)")
    ap.add_argument("--corruptions", type=int, default=-1,
                    help="how many traced inputs to corrupt, one at a time (-1 = all, 0 = none)")
    ap.add_argument("--floor-python", help="the interpreter to use for the floor probe")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    if not a.root:
        ap.error("a fixture bundle root is required")
    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"could not run: {root} is not a directory", file=sys.stderr)
        return 2

    seams = [s for s in SEAMS if not a.seam or s.id in a.seam]
    if not seams:
        print(f"could not run: no seam registered under {a.seam} (registered: "
              f"{[s.id for s in SEAMS]})", file=sys.stderr)
        return 2

    framework_root = Path(_REPO).resolve()
    missing = [s.tool for s in seams if not (framework_root / "tools" / s.tool).is_file()]
    if missing:
        print(f"could not run: registered seam(s) {missing} are not in tools/", file=sys.stderr)
        return 2

    subjects = {}
    for s in seams:
        if s.subject:
            sid = _subject_id(s, root)
            if sid is None:
                # AN EMPTY POPULATION IS NOT A PASS. A subject seam judged on a bundle declaring no
                # members would be green for the same reason incident one was: nothing measured.
                if a.json:
                    print(json.dumps({"state": "no-members", "measured_nothing": True,
                                      "seam": s.id, "root": str(root)}, indent=1))
                    return D.EMPTY_EXIT
                return D.refuse_empty(NAME, root, unit=f"{s.subject} for seam {s.id}")
            subjects[s.id] = sid

    results, all_findings = [], []
    for s in seams:
        floor = None
        if a.floor_python:
            floor = (a.floor_python, ())
        else:
            floor = _floor_interpreter(s.floor)
        pr = probes_for(s, root, framework_root, subjects.get(s.id), a.corruptions,
                        floor[0] if floor else None)
        findings, verdict, counts = judge(s, pr)
        all_findings += findings
        results.append((s, findings, verdict, counts, pr))

    judged = sum(1 for _s, _f, v, _c, _p in results for k in CLASSES if not v[k].startswith("not "))
    passed = sum(1 for _s, _f, v, _c, _p in results for k in CLASSES if v[k] == "pass")
    conform = sum(1 for _s, f, _v, _c, _p in results if not f)
    by_class = dict(sorted(Counter(x.cls for x in all_findings).items()))

    if a.json:
        print(json.dumps({
            "contract": CONTRACT,
            "seams": [{"id": s.id, "tool": s.tool, "floor": ".".join(map(str, s.floor)),
                       "probes": [{"label": p.label, "exit": p.rc, "stdout_bytes": len(p.stdout),
                                   "envelope": p.payload is not None} for p in pr],
                       "counts": dict(c), "verdict": v,
                       "findings": [x.as_dict() for x in f]}
                      for s, f, v, c, pr in results],
            "clauses": list(CLASSES), "by_class": by_class,
            "assertions": {"passed": passed, "judged": judged,
                           "total": len(CLASSES) * len(results)},
            "seams_conforming": conform, "seams_registered": len(SEAMS),
            "exit": 1 if all_findings else 0}, indent=1, ensure_ascii=False))
        return 1 if all_findings else 0

    for s, findings, verdict, counts, pr in results:
        env = counts.get("probes_with_envelope", 0)
        print(f"\n── seam {s.id} ({s.tool}) — {counts.get('probes', 0)} probe(s), {env} with an "
              f"envelope; {counts.get('bundle_declared', 0)} of {counts.get('bundle_opens', 0)} "
              f"traced bundle input(s) declared, {counts.get('framework_declared', 0)} of "
              f"{counts.get('framework_opens', 0)} framework input(s) declared")
        for x in findings:
            print(x)
        for k in CLASSES:
            if verdict[k].startswith("not "):
                print(f"  [not judged] {k}: {verdict[k][len('not judged — '):]}")
        p = sum(1 for k in CLASSES if verdict[k] == "pass")
        j = sum(1 for k in CLASSES if not verdict[k].startswith("not "))
        print(f"  {s.id}: {p} of {j} judged clause(s) pass ({len(CLASSES)} declared, "
              f"{len(CLASSES) - j} not judged) — {'CONFORMS' if not findings else 'DOES NOT CONFORM'}")

    tail = (f"{conform} of {len(results)} seam(s) conform, of {len(SEAMS)} registered; "
            f"{passed} of {judged} judged clause-check(s) pass over {len(CLASSES)} clause(s) × "
            f"{len(results)} seam(s) = {len(CLASSES) * len(results)} declared")
    if all_findings:
        print(f"\nFAIL: {NAME} — {len(all_findings)} finding(s) {by_class} — {tail}")
        return 1
    print(f"\nPASS: {NAME} — {tail}")
    return 0


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# --self-test — ONE MUTANT PER REJECT CLASS against the PURE judge, plus negative controls and the
# end-to-end refusals. Synthetic names only (alpha/beta); no bundle, no warehouse, no network.
# ══════════════════════════════════════════════════════════════════════════════════════════════════
_SEAM_INDEX = Seam("alpha-index", "seam_alpha.py")
_SEAM_DOC = Seam("beta-doc", "seam_beta.py", subject="member")

_GOOD_INDEX = {
    "envelope": CONTRACT, "mode": "index", "status": "derived", "reason": None,
    "result": [{"id": "alpha"}, {"id": "beta"}],
    "counts": {"returned": 2, "declared": 2},
    "inputs": [{"path": "ontology/spine.yaml", "role": "spine", "present": True, "parsed": True,
                "count": 2},
               {"path": "data/rows", "role": "row", "present": True, "parsed": True, "count": 2},
               {"path": "framework:grammar.json", "role": "framework", "present": True,
                "parsed": True, "count": None}],
    "partial": [], "seam": {"tool": "seam_alpha.py", "version": "0.0.0",
                            "framework_root": "fr0", "code_id": "c0"},
    "subject": None, "derived_at": "2026-01-01T00:00:00Z", "aux": {},
    "local": {"root": "/somewhere/on/this/disk", "argv": ["/somewhere/on/this/disk"]},
}
_GOOD_DOC = dict(_GOOD_INDEX, mode="document", result="# a page\n", counts={"returned": 1,
                 "declared": 1}, subject={"kind": "member", "id": "alpha"},
                 seam=dict(_GOOD_INDEX["seam"], tool="seam_beta.py"))
_BAD_ARGV = dict(_GOOD_INDEX, status="bad_request", reason="root is not a directory", result=[],
                 counts={"returned": 0, "declared": 0})


def _P(label, payload, rc=0, opens=("ontology/spine.yaml", "data/rows/one.yaml"),
       fopens=("grammar.json",), **kw):
    p = Probe(label, rc, json.dumps(payload) if payload is not None else kw.get("stdout", ""),
              kw.get("stderr", ""), opens, fopens, interpreter="py")
    return p


def _set(payload, **kw):
    q = json.loads(json.dumps(payload))
    for k, v in kw.items():
        if v is _DROP:
            q.pop(k, None)
        else:
            q[k] = v
    return q


class _Drop:
    pass


_DROP = _Drop()


def _probes(main_payload, seam=_SEAM_INDEX, **over):
    """A conforming probe SET, with one thing swapped. Every mutant is one keyword away."""
    default_bad = _BAD_ARGV if seam is _SEAM_INDEX else _set(
        _BAD_ARGV, mode="document", result="", subject={"kind": "member", "id": "alpha"},
        seam=dict(_GOOD_INDEX["seam"], tool="seam_beta.py"))
    ps = [_P("derived", main_payload),
          _P("bad-argv", over["bad_argv"] if "bad_argv" in over else default_bad, rc=2),
          _P("floor", over.get("floor", main_payload), rc=0),
          _P("corrupt-baseline", main_payload),
          _P("corrupt:data/rows/one.yaml",
             over.get("corrupt", _set(main_payload, status="degraded",
                                      partial=[{"input": "data/rows/one.yaml", "role": "row",
                                                "effect": "1 member lost", "reason": "will not parse"}],
                                      reason="1 input would not parse"))),
          ]
    if "extra" in over:
        ps += over["extra"]
    return ps


def _self_test() -> int:
    bad, cases = [], []

    def case(label, ok, why=""):
        cases.append(label)
        if not ok:
            bad.append(f"{label}  {why}")

    def classes(seam, probes):
        f, _v, _c = judge(seam, probes)
        return {x.cls for x in f}

    # ── NEGATIVE CONTROLS ──────────────────────────────────────────────────────────────────────
    case("NEGATIVE CONTROL a conforming index seam produces no finding",
         classes(_SEAM_INDEX, _probes(_GOOD_INDEX)) == set(),
         str(classes(_SEAM_INDEX, _probes(_GOOD_INDEX))))
    case("NEGATIVE CONTROL a conforming document seam produces no finding",
         classes(_SEAM_DOC, _probes(_GOOD_DOC, seam=_SEAM_DOC,
                                    corrupt=_set(_GOOD_DOC, status="unparsed_input",
                                                 reason="an input will not parse", result=""))) == set())
    case("NEGATIVE CONTROL an absolute path INSIDE `local` is not a leak",
         PATH_LEAKED not in classes(_SEAM_INDEX, _probes(_GOOD_INDEX)))
    case("NEGATIVE CONTROL a declared PLANE covers the files under it",
         INPUT_UNDECLARED not in classes(_SEAM_INDEX, _probes(_GOOD_INDEX)))
    case("NEGATIVE CONTROL index mode MAY serve a non-derived status",
         classes(_SEAM_INDEX, _probes(_set(_GOOD_INDEX, status="absent_input",
                                           reason="the plane is not there",
                                           result=[], counts={"returned": 0, "declared": 0}))) == set())
    case("NEGATIVE CONTROL a degraded index payload naming its partial is clean",
         classes(_SEAM_INDEX, _probes(_set(_GOOD_INDEX, status="degraded",
                                           reason="1 row could not be derived",
                                           partial=[{"input": "data/rows/one.yaml", "role": "row",
                                                     "effect": "1 lost", "reason": "unparsed"}]))) == set())

    # ── ONE MUTANT PER REJECT CLASS ────────────────────────────────────────────────────────────
    # Dropping a reserved key from ONE exit is two findings, deliberately: the key is gone AND the
    # shape now varies by exit. Asserted as a pair, because a mutant that produced only one of them
    # would mean a reserved key could quietly become optional on the failure path.
    case(f"MUTANT {ENVELOPE_UNVERSIONED}",
         classes(_SEAM_INDEX, _probes(_set(_GOOD_INDEX, envelope=_DROP)))
         == {ENVELOPE_UNVERSIONED, SHAPE_VARIES})
    case(f"MUTANT {ENVELOPE_UNVERSIONED} a WRONG version is also refused",
         ENVELOPE_UNVERSIONED in classes(_SEAM_INDEX,
                                         _probes(_set(_GOOD_INDEX, envelope="mac.seam/99"))))
    case(f"MUTANT {RESULT_UNKEYED}",
         RESULT_UNKEYED in classes(_SEAM_INDEX, _probes(_set(_GOOD_INDEX, result=_DROP))))
    case(f"MUTANT {MODE_UNDECLARED}",
         MODE_UNDECLARED in classes(_SEAM_INDEX, _probes(_set(_GOOD_INDEX, mode=_DROP))))
    case(f"MUTANT {MODE_UNDECLARED} a mode outside the two is undeclared",
         MODE_UNDECLARED in classes(_SEAM_INDEX, _probes(_set(_GOOD_INDEX, mode="partial"))))
    case(f"MUTANT {MODE_CONTRADICTED} document mode returning a list",
         MODE_CONTRADICTED in classes(_SEAM_DOC, _probes(_set(_GOOD_DOC, result=[1, 2]),
                                                         seam=_SEAM_DOC)))
    case(f"MUTANT {MODE_CONTRADICTED} index mode with no spine input",
         MODE_CONTRADICTED in classes(_SEAM_INDEX, _probes(_set(
             _GOOD_INDEX, inputs=[{"path": "data/rows", "role": "row", "present": True,
                                   "parsed": True, "count": 2},
                                  {"path": "ontology/spine.yaml", "role": "row", "present": True,
                                   "parsed": True, "count": 2},
                                  {"path": "framework:grammar.json", "role": "framework",
                                   "present": True, "parsed": True, "count": None}]))))
    case(f"MUTANT {MODE_CONTRADICTED} document mode carrying `degraded`",
         MODE_CONTRADICTED in classes(_SEAM_DOC, _probes(
             _set(_GOOD_DOC, status="degraded", reason="half of it",
                  partial=[{"input": "x", "role": "row", "effect": "y", "reason": "z"}]),
             seam=_SEAM_DOC)))
    case(f"MUTANT {STATUS_UNCLOSED}",
         STATUS_UNCLOSED in classes(_SEAM_INDEX, _probes(_set(_GOOD_INDEX, status="partly"))))
    case(f"MUTANT {STATUS_UNCLOSED} a HOST-minted token from a seam is refused",
         STATUS_UNCLOSED in classes(_SEAM_INDEX, _probes(_set(_GOOD_INDEX, status="seam_failed"))))
    case(f"MUTANT {REASON_UNBOUND} a reason on a derived payload",
         REASON_UNBOUND in classes(_SEAM_INDEX, _probes(_set(_GOOD_INDEX, reason="all fine"))))
    case(f"MUTANT {REASON_UNBOUND} no reason on a failure",
         REASON_UNBOUND in classes(_SEAM_INDEX, _probes(_set(_GOOD_INDEX, status="absent_input",
                                                             reason=None))))
    case(f"MUTANT {PARTIAL_UNBOUND} degraded with an empty partial",
         PARTIAL_UNBOUND in classes(_SEAM_INDEX, _probes(_set(_GOOD_INDEX, status="degraded",
                                                              reason="something", partial=[]))))
    case(f"MUTANT {PARTIAL_UNBOUND} a partial with no degraded",
         PARTIAL_UNBOUND in classes(_SEAM_INDEX, _probes(_set(
             _GOOD_INDEX, partial=[{"input": "x", "role": "row", "effect": "y", "reason": "z"}]))))
    case(f"MUTANT {DENOMINATOR_MISSING} declared is null",
         DENOMINATOR_MISSING in classes(_SEAM_INDEX, _probes(
             _set(_GOOD_INDEX, counts={"returned": 0, "declared": None}))))
    case(f"MUTANT {DENOMINATOR_MISSING} no counts at all",
         DENOMINATOR_MISSING in classes(_SEAM_INDEX, _probes(_set(_GOOD_INDEX, counts=_DROP))))
    case(f"MUTANT {SHAPE_VARIES} a key that exists only on success",
         SHAPE_VARIES in classes(_SEAM_INDEX, _probes(
             _GOOD_INDEX, bad_argv=_set(_BAD_ARGV, result=_DROP, counts=_DROP))))
    case(f"MUTANT {INPUT_UNDECLARED} a file opened and not declared",
         INPUT_UNDECLARED in classes(_SEAM_INDEX,
                                     [_P("derived", _GOOD_INDEX,
                                         opens=("ontology/spine.yaml", "data/rows/one.yaml",
                                                "data/quality/dashboard.json"))]))
    case(f"MUTANT {INPUT_UNDECLARED} a role outside the closed four",
         INPUT_UNDECLARED in classes(_SEAM_INDEX, _probes(_set(
             _GOOD_INDEX, inputs=[dict(_GOOD_INDEX["inputs"][0]),
                                  dict(_GOOD_INDEX["inputs"][1], role="context"),
                                  dict(_GOOD_INDEX["inputs"][2])]))))
    case(f"MUTANT {FRAMEWORK_UNDECLARED} a framework file read and not declared",
         FRAMEWORK_UNDECLARED in classes(_SEAM_INDEX,
                                         [_P("derived", _GOOD_INDEX,
                                             fopens=("grammar.json", "vocabulary.yaml"))]))
    case(f"MUTANT {SEAM_UNSTAMPED}",
         SEAM_UNSTAMPED in classes(_SEAM_INDEX, _probes(_set(_GOOD_INDEX, seam=_DROP))))
    case(f"MUTANT {SEAM_UNSTAMPED} a stamp missing code_id",
         SEAM_UNSTAMPED in classes(_SEAM_INDEX, _probes(_set(
             _GOOD_INDEX, seam={"tool": "t", "version": "v", "framework_root": "r"}))))
    case(f"MUTANT {PATH_LEAKED}",
         PATH_LEAKED in classes(_SEAM_INDEX, _probes(_set(
             _GOOD_INDEX, aux={"root": "/srv/alpha/beta-bundle"}))))
    case(f"MUTANT {ARGV_SILENT} exit 2 with an empty stdout",
         ARGV_SILENT in classes(_SEAM_INDEX, _probes(_GOOD_INDEX, bad_argv=None)))
    case(f"MUTANT {ARGV_SILENT} exit 2 with a status that is not bad_request",
         ARGV_SILENT in classes(_SEAM_INDEX, _probes(
             _GOOD_INDEX, bad_argv=_set(_BAD_ARGV, status="author_failed",
                                        reason="something else"))))
    case(f"MUTANT {FLOOR_BROKEN} exit 1 and nothing on stdout",
         FLOOR_BROKEN in classes(_SEAM_INDEX, [
             _P("derived", _GOOD_INDEX),
             Probe("floor", 1, "", "AttributeError: module 'datetime' has no attribute 'UTC'",
                   interpreter="python3.9")]))
    case(f"MUTANT {DEGRADE_UNSIGNALLED} a corrupted input changed nothing",
         DEGRADE_UNSIGNALLED in classes(_SEAM_INDEX, _probes(_GOOD_INDEX, corrupt=_GOOD_INDEX)))
    case(f"MUTANT {DEGRADE_UNSIGNALLED} the CLOCK moving is not a change",
         DEGRADE_UNSIGNALLED in classes(_SEAM_INDEX, _probes(
             _GOOD_INDEX, corrupt=_set(_GOOD_INDEX, derived_at="2099-12-31T23:59:59Z"))))

    # ── THE JUDGE'S OWN HONESTY ────────────────────────────────────────────────────────────────
    _f, v, _c = judge(_SEAM_INDEX, [_P("derived", _GOOD_INDEX, fopens=())])
    case("DISCLOSURE a fixture causing 0 framework reads is disclosed, never passed",
         v[FRAMEWORK_UNDECLARED].startswith("not judged"), v[FRAMEWORK_UNDECLARED])
    case("DISCLOSURE with no floor probe the floor clause is disclosed, never passed",
         v[FLOOR_BROKEN].startswith("not judged"), v[FLOOR_BROKEN])
    case("DISCLOSURE with one envelope the shape clause is disclosed, never passed",
         v[SHAPE_VARIES].startswith("not judged"), v[SHAPE_VARIES])
    _f, v, _c = judge(_SEAM_INDEX, [Probe("derived", 1, "", "boom")])
    case("DISCLOSURE a seam that cannot speak is one finding and 16 clauses not judged, never a pass",
         len(_f) == 1 and _f[0].cls == STATUS_UNCLOSED
         and all(v[k].startswith("not judged") for k in CLASSES if k != STATUS_UNCLOSED))
    case("DISCLOSURE every class in CLASSES has a verdict on every judgement",
         set(v) == set(CLASSES), sorted(set(CLASSES) ^ set(v)))

    # ── END TO END ─────────────────────────────────────────────────────────────────────────────
    def _run(*args):
        pr = subprocess.run([sys.executable, os.path.abspath(__file__), *args],
                            capture_output=True, text=True)
        return pr.returncode, pr.stdout + pr.stderr

    rc, out = _run("/not-a-directory-anywhere")
    case("END TO END a root that is not a directory could-not-run (exit 2)", rc == 2, f"exit {rc}")
    with tempfile.TemporaryDirectory() as td:
        rc, out = _run(td, "--seam", "concept-page")
        case("END TO END a bundle declaring 0 members REFUSES (exit 2), verbatim marker",
             rc == D.EMPTY_EXIT and D.empty_mark("concept for seam concept-page") in out,
             f"exit {rc}: {out.strip()[-160:]}")
        rc, out = _run(td, "--seam", "concept-page", "--json")
        case("END TO END --json parses on the refusal state too",
             rc == D.EMPTY_EXIT and json.loads(out).get("measured_nothing") is True,
             out.strip()[-160:])
    rc, out = _run("--seam", "no-such-seam", str(Path(_REPO)))
    case("END TO END an unregistered seam id could-not-run (exit 2), never a pass over zero",
         rc == 2 and "no seam registered" in out, f"exit {rc}")
    fixture = Path(_REPO) / "example_shop_ontology"
    if fixture.is_dir():
        rc, out = _run(str(fixture), "--seam", "edges", "--corruptions", "1")
        # RE-POINTED, NOT DELETED, AND THE REASON IS THE POINT. This case read "the real runner
        # FAILS the edge seam and names its classes" — measured true on 2026-09-19, when 0 of 3
        # seams conformed and the edge seam carried 9 findings over 13 judged clauses. The seam
        # was then migrated to mac.seam/1, so the claim became an assertion that a repaired defect
        # is still there, and a self-test that demands a FAIL is a self-test that forbids the
        # migration it exists to drive. What the case is FOR is that the end-to-end path — the
        # subprocess, the audit hook, the corruption copy on a temp bundle — reaches a real
        # verdict on a real seam. So it pins the verdict that is now true, with its denominators.
        case("END TO END the real runner judges the migrated edge seam and it CONFORMS",
             rc == 0 and "PASS: check_seam_contract" in out
             and "16 of 16 judged clause(s) pass" in out, f"exit {rc}: {out.strip()[-200:]}")
        case("END TO END the verdict line carries its denominators",
             "of 1 seam(s) conform, of 3 registered" in out
             and "judged clause-check(s) pass over 16 clause(s)" in out, out.strip()[-240:])
        # AND A FAIL IS STILL REACHABLE END TO END — asserted over the WHOLE registry rather than
        # over one named seam, so migrating the remaining seams cannot rot it either. The exit
        # code and the verdict word are ONE fact: a runner that printed FAIL and exited 0 would be
        # this gate's own subject matter, one plane up.
        rc, out = _run(str(fixture), "--corruptions", "0")
        case("END TO END the exit code and the verdict word are one fact over the registry",
             (rc == 1) == ("FAIL: check_seam_contract" in out)
             and (rc == 0) == ("PASS: check_seam_contract" in out)
             and f"of {len(SEAMS)} registered" in out, f"exit {rc}: {out.strip()[-200:]}")
        rc, out = _run(str(fixture), "--seam", "edges", "--corruptions", "0", "--json")
        case("END TO END --json parses on a real run and carries the clause list",
             json.loads(out)["clauses"] == list(CLASSES), out.strip()[:160])
    else:
        case("END TO END the public fixture bundle is present", False, f"no {fixture}")

    total = len(cases)
    if bad:
        print(f"FAIL: {NAME} self-test — {len(bad)} of {total} case(s) failed")
        for b in bad:
            print(f"  ✗ {b}", file=sys.stderr)
        return 1
    mut = len([c for c in cases if c.startswith("MUTANT")])
    neg = len([c for c in cases if c.startswith("NEGATIVE CONTROL")])
    nj = len([c for c in cases if c.startswith("DISCLOSURE")])
    e2e = len([c for c in cases if c.startswith("END TO END")])
    print(f"PASS: {NAME} self-test — {total}/{total} case(s): {mut} mutant(s) covering all "
          f"{len(CLASSES)} reject class(es) (no envelope, a wrong version, no result key, no mode, "
          f"a third mode, a document returning a list, an index with no spine, a document carrying "
          f"degraded, an invented status, a host-minted status, a reason on a derived payload, no "
          f"reason on a failure, degraded with no partial, a partial with no degraded, a null "
          f"denominator, no counts, a key that exists only on success, an undeclared open, an "
          f"undeclared role, an undeclared framework read, no seam stamp, a stamp with no code_id, "
          f"an absolute path outside local, a silent exit 2, a mis-tokened exit 2, exit 1 on the "
          f"floor, a corruption that changed nothing, a corruption that moved only the clock), "
          f"{neg} negative control(s) (a conforming index and document seam, a path inside local, "
          f"a plane covering its files, index mode serving a non-derived status, a named degrade), "
          f"{nj} disclosure case(s) (0 framework reads, no floor probe, one envelope, a seam that "
          f"cannot speak, every class has a verdict) and {e2e} end-to-end case(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
