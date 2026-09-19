#!/usr/bin/env python3
"""check_data_plane_approved.py — the DATA→ONTOLOGY handoff gate, and the ONE decision function.

THE RULING THIS IMPLEMENTS. A bundle may declare TWO pipelines, both started manually:

    reproduction:
      pipelines:
        data:     { entry: <command>, exit: { register: data/quality/data_quality_register.yaml } }
        ontology: { entry: <command>, requires: { pipeline: data } }

The DATA pipeline's declared exit is not "the files exist". It is ITS OWN REGISTER, FULLY
DISPOSITIONED: every registered issue carrying a TERMINAL `mac.dq_status` term (`accepted`,
`wont_fix` or `resolved`) with that term's own `requires:` met — which, for the two terms that claim
a human acted, means a `ruled_by` name and a `reason`. An `open` issue closes the pipeline. The
ONTOLOGY pipeline may not start until that exit is reached — and then it runs INDEPENDENTLY: its own
command, its own clock, no warehouse, no billed call, no data stage chained into it.

WHAT CHANGED ON 2026-09-18, AND THE HONEST ACCOUNTING OF WHAT IT COST
--------------------------------------------------------------------
Until that day the exit was a SEPARATE FILE, `governance/data_plane_approval.yaml`, and this gate
refused until a named human saved one. The operator refused the artifact — "i dont want to sign of
anything !!!" — and asked, in the same breath, when the ontology would start. Both are answered by
the same change, and it is a SIMPLIFICATION rather than a weakening of what they actually asked
for, which was, verbatim and earlier: "we cannot automatically proceed with creating ontology as
long as we did not approve the configuration of datasets in full amount. this means we did not
reduce the # of issues to the acceptable minimum."

THAT CONDITION LIVES IN THE REGISTER. It is where the reduction is recorded, one argued disposition
at a time, each with its own `ruled_by` and its own `reason`. The separate file duplicated it in a
LESS informative form — one date and one name against N individually-argued dispositions — so the
duplicate goes and the register is the exit. The sign-off was the BUILD'S design choice; it was
never the operator's requirement.

THE PRICE, WRITTEN INTO THE GATE RATHER THAN GLOSSED. The sign-off existed to be the one artifact
an agent provably cannot write: the guard denies that path unconditionally, marker or not. The
register IS agent-writable — deliberately, and the guard's own self-test asserts it — and in fact an
agent typed the `ruled_by: operator` lines on a live register on the operator's conversational
instruction. So collapsing the exit onto the register drops the guarantee from PREVENTION to
ATTRIBUTION: git blame, the named ruler, the reason text and the decision record, not a token the
agent cannot reach. That is not a regression being hidden. It is the ceiling this estate had already
reached and recorded — see "WHAT THIS GATE DOES NOT CLAIM" below, whose own words are "Real
authorization is out-of-band … and in a single-identity self-merge estate there is no second party
to hold that token. The honest claim, in the estate's own words, is DETECTED-AND-BLOCKED,
AUTHORIZED OUT-OF-BAND." A ceremony that buys nothing the operator wants is worse than an honest
ceiling. The refusal text below says so, and so does the known-gap list in
mac-integration-kit/ontology/planes/PIPELINES.md §8.

AN APPROVAL FILE THAT IS PRESENT IS STILL HONOURED, NEVER IGNORED. `approval_missing` is retired —
no sign-off is required and none will be asked for — but every other `approval_*` reject class stays
live over a file that EXISTS: unreadable, unratified, agent-stamped, `covers:` incomplete or
dangling, digest stale. A bundle that carries a sign-off must not silently lose it, and the only way
to make that true is for the file to keep being able to FAIL. `resolved_on_non_defect` stays too: it
is the one guard against the one disposition a machine can write naming nobody.

WHAT THIS REPLACES, AND WHY. The old mechanism was a blanket path lock: every path under a bundle's
`ontology/` was denied unless the operator had touched an unlock marker. Measured 2026-09-18 10:09,
that lock did not protect meaning on a FIRST INGESTION — it diverted the pipeline's output. A
concept-authoring agent's first Write was refused, the agent read the guard, searched for an unlock
marker, found none, and wrote its concepts into a TEMP DIRECTORY, where the ontology would never see
them. The lock was standing in for a gate it could not express: the operator's actual reason was
that A HUMAN HAD NOT YET APPROVED THE DATASET CONFIGURATION. So the blanket goes and something
stricter and better-aimed replaces it — this gate, which a human and only a human can open.

THE THRESHOLD IS NOT A NUMBER ANYBODY INVENTED. "The acceptable minimum of issues" is per-issue
DISPOSITION: every id in the register — `NS-` disclosure and `DQ-` defect alike — must carry a
terminal `mac.dq_status` term whose own `requires:` list is met. The count of undispositioned ids
must be 0, and it cannot move unless a person rules on the specific thing and says why.

SEVERITY IS NEVER READ — not weighted, not thresholded, not reported by this gate. Two reasons, and
the second is measured. (a) `severity` is machine-authored, capped at `confidence: I` by CORE.md §4,
so a gate reading it grades the machine against its own opinion. (b) MEASURED 2026-09-18: a live
register's entry was edited from `severity: high` to `severity: low` and from `status: open` to
`status: resolved`, its own inline comment naming the coming gate as the reason — "this entry at
`high` would have blocked the ontology on bookkeeping rather than on data". A machine-writable
grading field was changed because a gate was about to read one, hours after such a gate was
proposed. This gate reads none, so a non-defect parked at the worst grade clears in one human act
and nobody is ever paid to downgrade it.

THE TWO KINDS OF REGISTER ENTRY are the estate's own convention, not a coinage here. The register's
header defines `NS-<AREA>-<nn>` as "a relation … MEASURED and deliberately NOT SERVED" and
`DQ-<AREA>-<nn>` as "a data DEFECT, graded and dispositioned"; the console already splits them the
same way (mac_console/ingest_progress.py filters `id.startswith("DQ-")` at :799 and `NS-` at :800,
its docstring recording the bug that taught it to). BOTH KINDS NOW NEED A DISPOSITION, and that is
what widened on 2026-09-18: an `NS-` id used to need only to be NAMED in the sign-off, because
acknowledging a disclosure is a different act from dispositioning a defect — and the sign-off was
where that acknowledgement lived. With the sign-off retired there is nowhere else for it to be
recorded, so it is recorded in the register like everything else. The prefix still matters for one
thing and one thing only: `resolved` is refused on an `NS-` id, because no transform dissolved a
relation that was deliberately not served.

WHY ONE ARTIFACT AND NOT TWO, NOW. The register both DESCRIBES and DISPOSITIONS, and it is
agent-writable. The old arrangement put the authorising half in a file the guard denies
unconditionally, so an agent could fake a disposition and not the approval, and faking one bought
nothing; and because the register sits INSIDE the digest, a disposition written after the sign-off
staled the approval it was meant to satisfy. That ladder is gone with the second artifact, and what
replaces it is weaker and is named as weaker: per-issue ATTRIBUTION (`ruled_by`, `reason`, git
blame, the decision record) and `resolved_on_non_defect` standing over the one spelling a machine
can write naming nobody. Staleness is no longer a concept on this path, and that is not a loss: the
register IS the live state and is re-read on every run, so there is no signed snapshot left to go
out of date.

WHAT THIS GATE DOES NOT CLAIM. No file-based mechanism is un-forgeable against an agent with
unrestricted shell access. The guard's Bash matcher DETECTS the obvious shell writes and a
constructed or base64'd path walks past it; the installed `permissions.deny` block raises that cost
again and does not close the class. The git-trailer check is evidence after the fact and `git -c
user.name=…` defeats it. Real authorization is out-of-band — CODEOWNERS on the sign-off path plus a
review the agent holds no token for — and in a single-identity self-merge estate there is no second
party to hold that token. The honest claim, in the estate's own words, is DETECTED-AND-BLOCKED,
AUTHORIZED OUT-OF-BAND. What this gate buys is that the agent must type a lie that is also TRUE
(the digest is recomputed and the register recounted) and ATTRIBUTABLE (git blame, the decision
record, the ledger entry). See the known-gap list in ontology/PIPELINES.md.

Usage
    python3 tools/check_data_plane_approved.py <bundle-root>
    python3 tools/check_data_plane_approved.py <bundle-root> --json
    python3 tools/check_data_plane_approved.py <bundle-root> --print-ruling     # CORE.md §6
    python3 tools/check_data_plane_approved.py <bundle-root> --print-approval   # RETIRED — a note
    python3 tools/check_data_plane_approved.py <bundle-root> --agree [--guard PATH]
    python3 tools/check_data_plane_approved.py --self-test

    exit 0 = the ontology pipeline may start (or the gate does not apply to this bundle)
    exit 1 = it may not, and every blocker is named with its denominator
    exit 2 = could not run, which is not a verdict

THIS TOOL WRITES NO FILE, and there is deliberately no `--approve`, no `--rule` and no
`--ratify-anyway`. `--project-anyway` exists elsewhere because it overrides a MACHINE finding and
records its reason; a flag that writes a HUMAN's disposition is an agent forging consent, and any
agent that can type a command can pass a flag. `--print-approval` is RETIRED to a note: it used to
emit the sign-off block for a human to save, and there is no longer a sign-off to save. It keeps its
name so no caller breaks, and prints what the exit is instead.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

_ROOT = Path(__file__).resolve().parent.parent
VOCABULARY = _ROOT / "mac_vocabulary.yaml"

EXIT_PASS, EXIT_FAIL, EXIT_COULD_NOT_RUN = 0, 1, 2

# The register is the DATA pipeline's exit. A bundle names its own in the manifest
# (reproduction.pipelines.data.exit.register); this is the conventional path every tool in the
# estate already hardcodes, so it is also the default.
REGISTER_REL = "data/quality/data_quality_register.yaml"

# The OPTIONAL sign-off's default home, kept because a bundle that carries one must keep working.
# NOT REQUIRED and never asked for: `approval_missing` is retired. A bundle may still name its own
# path in `reproduction.pipelines.data.exit.approval`, and if a file exists there it is validated
# exactly as before — honoured, never ignored.
DEFAULT_APPROVAL = "governance/data_plane_approval.yaml"

# The reserved sign-off id. `s.` is the sign-off prefix the estate's question ledger already uses.
SIGN_OFF_ID = "s.data-plane.approved"


# ======================================================================== the digest surface
#
# THE SURFACE THE ONTOLOGY BINDS TO. Its patterns live HERE, in framework code, and not in a
# per-bundle manifest key, so a bundle cannot shrink the surface to quiet the gate. Only a framework
# edit can — and `sdk/gate/check_seam_agreement.py` asserts the surface still covers every plane the
# manifest declares, so that edit shows up as a FAIL rather than as a cleanup.
#
# INCLUDED, because changing one of these changes what a concept MEANS:
_SURFACE = (
    ("data/datasets", (".yaml",)),      # the seam itself — the served descriptors
    ("data/transforms", (".yaml", ".sql")),  # how a served relation is made; a rule edit is a meaning edit
    ("data/sources", (".yaml",)),       # what was landed
    ("data/profiles", (".yaml",)),      # what was measured
    ("data/lookups", (".csv",)),        # the value registers a concept delegates to
)
_SURFACE_SINGLETONS = (REGISTER_REL, "mac.project.yaml")
#
# EXCLUDED, each with its reason, because getting this wrong is the single most likely way the
# design fails in practice — a digest that churns teaches operators to re-sign reflexively, and a
# gate nobody reads is worse than no gate:
#   • the `.md` twins beside every descriptor, `index.md`, `objects.json`, `compile.json`,
#     `references/`, `.harvest/` — PROJECTION OUTPUTS. Consequences of the ontology, not inputs to
#     it, and rewritten by every `--mode project`. Hashing them means every projection invalidates
#     the approval.
#   • `data/samples/**` — previews, re-cut mechanically. A preview row does not change meaning.
#   • `connection.yaml` — the manifest itself says it is OVERRIDABLE by a gitignored local file and
#     by $DEPLOYMENT_CONFIG, so hashing it fails the gate on a local override.
#   • `acceptance/**` — the testing plane tests the bundle; it is not what the ontology binds to.


def _normalise(path: Path) -> bytes:
    """Content, with the churn taken out — and with the residue DISCLOSED.

    Line endings are normalised and trailing whitespace stripped. For YAML, whole-line comments and
    blank lines are dropped as well: the estate's registers carry long explanatory comment blocks
    that are edited constantly, and hashing those would stale an approval every time somebody
    improved a paragraph. Full YAML normalisation (parse, canonical dump) is NOT used, because the
    guard must compute this same roll-up with the standard library alone — see its docstring.

    WHAT STILL COUNTS, said out loud: a trailing comment on the same line as a value, and a
    re-indentation. Both move the digest. That is the price of an algorithm two independent
    implementations can agree on byte-for-byte, and `check_seam_agreement` is what proves they do.
    """
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    if path.suffix.lower() in (".yaml", ".yml"):
        keep = [ln.rstrip() for ln in raw.split(b"\n")
                if ln.strip() and not ln.lstrip().startswith(b"#")]
        return b"\n".join(keep) + b"\n"
    return b"\n".join(ln.rstrip() for ln in raw.split(b"\n"))


def surface_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for rel, suffixes in _SURFACE:
        d = root / rel
        if d.is_dir():
            files += sorted(p for p in d.iterdir()
                            if p.is_file() and p.suffix.lower() in suffixes)
    for rel in _SURFACE_SINGLETONS:
        p = root / rel
        if p.is_file():
            files.append(p)
    return sorted(files, key=lambda q: str(q.relative_to(root)))


def data_plane_digest(root: Path) -> tuple[str, list[str]]:
    """(roll-up, bundle-relative paths). A sha256 over per-file sha256s, path-ordered."""
    files = surface_files(root)
    roll = hashlib.sha256()
    rels = []
    for p in files:
        rel = str(p.relative_to(root))
        rels.append(rel)
        roll.update(rel.encode())
        roll.update(hashlib.sha256(_normalise(p)).digest())
    return "sha256:" + roll.hexdigest(), rels


def per_file_digests(root: Path) -> dict:
    return {str(p.relative_to(root)): hashlib.sha256(_normalise(p)).hexdigest()
            for p in surface_files(root)}


# ======================================================================== the flat micro-parser
#
# The sign-off is restricted to FLAT `key: value` scalars for one reason: the PreToolUse guard must
# read it, the guard is copied into `.claude/hooks/` with no import path, and it FAILS CLOSED on a
# protected path — its own docstring records that a missing script denies every edit in the repo. A
# PyYAML import in the guard would brick nine repositories on a bad dependency. So both sides read
# the file with the same ~20 lines of standard library, and a seam detector proves this parser and
# `yaml.safe_load` agree over every sign-off in the estate.

class FlatParseError(ValueError):
    def __init__(self, lineno: int, text: str):
        self.lineno, self.text = lineno, text
        super().__init__(f"line {lineno}: {text}")


def parse_flat(text: str) -> dict:
    """Flat `key: value` scalars only. Anything else is a parse error naming its line."""
    out: dict = {}
    for i, raw in enumerate(text.split("\n"), start=1):
        line = raw.split("#", 1)[0].rstrip() if not raw.lstrip().startswith("#") else ""
        if not line.strip():
            continue
        if line[:1] in (" ", "\t", "-"):
            raise FlatParseError(i, "nested or list content — the sign-off must be flat scalars")
        if ":" not in line:
            raise FlatParseError(i, "not a `key: value` pair")
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip()
        if not k:
            raise FlatParseError(i, "empty key")
        if v[:1] in ("[", "{", "|", ">", "&", "*"):
            raise FlatParseError(i, f"unsupported value form {v[:1]!r} — flat scalars only")
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        out[k] = v
    return out


# ======================================================================== findings

@dataclass
class Finding:
    code: str            # a mac.data_plane_gate term
    sentence: str        # rendered to a human as-is
    act: str             # the exact command or edit the operator performs
    evidence: str        # a bundle-relative path or an id a human can open


@dataclass
class State:
    root: Path
    declared: int = 1                     # how many pipelines the manifest declares
    findings: list = field(default_factory=list)
    approval: dict = field(default_factory=dict)
    approval_path: str = DEFAULT_APPROVAL
    approval_present: bool = False        # a sign-off EXISTS, so it is validated. Never required.
    register_path: str = REGISTER_REL     # the DATA pipeline's declared exit
    issues_total: int = 0
    issues_dq: int = 0
    issues_ns: int = 0
    ruled: list = field(default_factory=list)          # ids at a terminal term with its evidence
    undispositioned: list = field(default_factory=list)  # ids that leave the exit unreached
    covered: list = field(default_factory=list)
    uncovered: list = field(default_factory=list)
    datasets: int = 0
    digest_now: str = ""
    digest_files: int = 0
    moved_files: list = field(default_factory=list)
    unreachable: str = ""

    @property
    def approved(self) -> bool:
        return self.declared >= 2 and not self.findings

    @property
    def applies(self) -> bool:
        return self.declared >= 2

    @property
    def blocking(self) -> list:
        return list(self.findings)


def _terms() -> dict:
    """The closed code set, READ from mac_vocabulary.yaml#data_plane_gate. Never restated."""
    if yaml is None or not VOCABULARY.is_file():
        return {}
    doc = yaml.safe_load(VOCABULARY.read_text(encoding="utf-8")) or {}
    return ((doc.get("data_plane_gate") or {}).get("terms") or {})


def _dq_law() -> dict:
    """Per-term evidence burden, READ from mac_vocabulary.yaml#dq_status."""
    if yaml is None or not VOCABULARY.is_file():
        return {}
    doc = yaml.safe_load(VOCABULARY.read_text(encoding="utf-8")) or {}
    return ((doc.get("dq_status") or {}).get("terms") or {})


# ======================================================================== the decision

def approval_state(root: Path, *, vocabulary: Path | None = None) -> State:
    """THE ONE DECISION FUNCTION. The guard, the CLI and the console all resolve to this verdict.

    The guard cannot import it (no import path in `.claude/hooks/`, and PyYAML would brick the
    repo), so it inlines an equivalent; `--agree` asserts the two reach the same verdict ON THE
    LIVE BUNDLE, and `check_seam_agreement` proves the parsers agree over the estate. Two
    derivations that can disagree is the only arrangement in which either can be checked.
    """
    root = Path(root)
    st = State(root=root)
    if yaml is None:
        st.unreachable = "PyYAML is not importable, so the manifest cannot be read"
        st.findings.append(Finding("gate_unreachable", st.unreachable,
                                   "install the framework's dependencies", "tools/"))
        return st

    manifest_path = root / "mac.project.yaml"
    if not manifest_path.is_file():
        st.unreachable = f"no mac.project.yaml at {root}"
        st.findings.append(Finding(
            "gate_unreachable",
            f"There is no manifest at {root}, so nothing declares how this bundle is built and the "
            f"gate cannot judge it. Unreachable means unknown means refuse.",
            "scaffold the bundle, or point the gate at a bundle root", "mac.project.yaml"))
        return st
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        st.unreachable = f"mac.project.yaml is unreadable: {exc}"
        st.findings.append(Finding("gate_unreachable", st.unreachable,
                                   "fix the manifest", "mac.project.yaml"))
        return st

    repro = (manifest.get("reproduction") or {}) if isinstance(manifest, dict) else {}
    pipelines = repro.get("pipelines") or {}
    if not pipelines:
        st.declared = 1
        return st           # not_declared — the one member that is a PASS
    st.declared = 2

    # A half-migrated manifest must not read as complete.
    for stage in (repro.get("stages") or []):
        if isinstance(stage, dict) and not stage.get("pipeline"):
            st.findings.append(Finding(
                "stage_unassigned",
                f"This bundle declares two pipelines and the stage `{stage.get('id', '?')}` does not "
                f"say which one it belongs to, so the record is half-migrated and cannot be read as "
                f"complete.",
                f"add `pipeline: data` or `pipeline: ontology` to the `{stage.get('id', '?')}` stage",
                "mac.project.yaml#reproduction.stages"))

    # THE DECLARED EXIT. `register` is the shape since 2026-09-18; `approval` is the older one and
    # is still read, so a bundle that names a sign-off keeps naming one. Neither key being present
    # is legal and means the conventional register path: an exit nobody declared is still an exit.
    exit_decl = ((pipelines.get("data") or {}).get("exit") or {})
    st.register_path = exit_decl.get("register") or REGISTER_REL
    st.approval_path = exit_decl.get("approval") or DEFAULT_APPROVAL

    # ---- the data plane as it stands
    descriptors = manifest.get("descriptors") or "data/datasets"
    dd = root / descriptors
    st.datasets = len(list(dd.glob("*.yaml"))) if dd.is_dir() else 0
    st.digest_now, rels = data_plane_digest(root)
    st.digest_files = len(rels)

    # ---- the register: THE DECLARED EXIT ITSELF, not a thing the exit refers to
    reg_path = root / st.register_path
    issues: list = []
    if not reg_path.is_file():
        st.findings.append(Finding(
            "gate_unreachable",
            f"The data-quality register is absent, and it IS this pipeline's declared exit — so "
            f"there is nothing to disposition and nothing to count. A bundle with {st.datasets} "
            f"served dataset(s) and no register has not finished its data pipeline.",
            "python -m sdk.cli.harvest --content-root <root> --mode onboard --accept",
            st.register_path))
    else:
        try:
            reg = yaml.safe_load(reg_path.read_text(encoding="utf-8")) or {}
            issues = [r for r in (reg.get("issues") or []) if isinstance(r, dict)]
        except Exception as exc:
            st.findings.append(Finding(
                "gate_unreachable", f"The register cannot be parsed: {exc}",
                "fix the register", st.register_path))
    ids = [str(r.get("id", "")).strip() for r in issues if str(r.get("id", "")).strip()]
    st.issues_total = len(ids)
    st.issues_dq = sum(1 for i in ids if i.startswith("DQ-"))
    st.issues_ns = sum(1 for i in ids if i.startswith("NS-"))

    if st.datasets == 0:
        st.findings.append(Finding(
            "no_datasets",
            "Nothing is served from this bundle, so there is nothing for an ontology to bind to and "
            "nothing to approve.",
            "python -m sdk.cli.harvest --content-root <root> --mode onboard --accept",
            descriptors))
    elif reg_path.is_file() and st.issues_total == 0:
        st.findings.append(Finding(
            "register_unrun",
            f"{st.datasets} dataset(s) are served and the data-quality register holds 0 issues. That "
            f"is a step that did not run, not a clean bill of health, so the data plane cannot be "
            f"approved from it.",
            "python -m sdk.cli.harvest --content-root <root> --mode onboard --accept",
            st.register_path))

    # ---- THE EXIT CONDITION: the disposition law, applied to EVERY registered entry.
    #
    # WIDENED 2026-09-18 from `DQ-` ids to every id. Before, an `NS-` disclosure needed only to be
    # NAMED in a separate sign-off — acknowledging a disclosure is a different act from
    # dispositioning a defect, and the sign-off was where the acknowledgement lived. The sign-off is
    # retired, so there is nowhere else for it to be recorded and it is recorded here, like
    # everything else. The prefix still decides one thing: `resolved` is refused on an `NS-` id.
    law = _dq_law() if vocabulary is None else (
        ((yaml.safe_load(Path(vocabulary).read_text(encoding="utf-8")) or {}).get("dq_status") or {})
        .get("terms") or {})
    terminal = [t for t in law if t != "open"]
    for r in issues:
        rid = str(r.get("id", "")).strip()
        status = str(r.get("status", "") or "").strip()
        if rid.startswith("NS-") and status == "resolved":
            # THE CATEGORY ERROR, and THE ONE REJECT CLASS THAT EXISTS BECAUSE THE EXIT IS NOW A
            # FILE AN AGENT CAN WRITE. `resolved` requires nothing, and both the register and the
            # resolution map are agent-writable, so it is the one spelling that would let a machine
            # clear the register with no human name anywhere. It is why NS-ORDERS-01 on the live
            # register is `accepted` and not `resolved`.
            st.findings.append(Finding(
                "resolved_on_non_defect",
                f"{rid} is marked `resolved`, and it is not a defect: an `NS-` entry is a "
                f"relation measured and deliberately not served, so no transform dissolved it. "
                f"`resolved` is the one disposition `mac.dq_status` lets a machine write without "
                f"naming anybody, which is why it is refused here — and with the register as this "
                f"pipeline's exit, it is the only thing standing between a machine and the gate. "
                f"The honest disposition of a non-promotion is `accepted` or `wont_fix`, and both "
                f"name a ruler.",
                f"set {rid} to `accepted` (or `wont_fix`) with `ruled_by:` and `reason:`",
                f"{st.register_path}#{rid}"))
            st.undispositioned.append(rid)
            continue
        kind = "a graded defect" if rid.startswith("DQ-") else \
               "a relation measured and deliberately not served" if rid.startswith("NS-") else \
               "a registered issue"
        if status not in terminal:
            st.findings.append(Finding(
                "issue_undispositioned",
                f"{rid} is {kind} whose status is "
                f"{'`' + status + '`' if status else 'absent'} — nobody has ruled on it, so this "
                f"bundle's DATA pipeline has not reached its declared exit. The closed set is "
                f"mac.dq_status; `open` means recorded and undispositioned, and it is the honest "
                f"default rather than a failure to write.",
                f"give {rid} a terminal disposition (`accepted`, `wont_fix` or `resolved`) with "
                f"`ruled_by:` and `reason:`",
                f"{st.register_path}#{rid}"))
            st.undispositioned.append(rid)
            continue
        missing = [k for k in (law.get(status, {}).get("requires") or [])
                   if not str(r.get(k, "") or "").strip()]
        if missing:
            st.findings.append(Finding(
                "issue_undispositioned",
                f"{rid} is `{status}`, which claims a human acted, and it is missing "
                f"{', '.join('`' + m + '`' for m in missing)}. mac.dq_status requires those on that "
                f"term because it is the term that makes the claim — and since the exit collapsed "
                f"onto this file, that name IS the attribution the gate rests on.",
                f"add {', '.join(missing)} to {rid}", f"{st.register_path}#{rid}"))
            st.undispositioned.append(rid)
        else:
            st.ruled.append(rid)

    # ---- the OPTIONAL sign-off. NOT the exit any more, and its absence is NOT a finding: the
    # retired `approval_missing` class carries the reason and what the retirement cost. What is
    # still true is that a file which EXISTS is validated exactly as before — honoured, never
    # ignored — so a bundle that carries a sign-off cannot silently lose it by having the exit move
    # out from under it, and every `approval_*` class below can still turn a green bundle red.
    st.uncovered = list(st.undispositioned)
    ap_path = root / st.approval_path
    if not ap_path.is_file():
        return st
    st.approval_present = True

    try:
        st.approval = parse_flat(ap_path.read_text(encoding="utf-8"))
    except FlatParseError as exc:
        st.findings.append(Finding(
            "approval_unreadable",
            f"The data-plane sign-off cannot be read ({exc}). The bundle is treated as not approved "
            f"until the operator fixes it — no agent may edit that file, so only you can.",
            f"fix {st.approval_path} at line {exc.lineno}", st.approval_path))
        return st

    ap = st.approval
    if (ap.get("status") != "applied" or ap.get("verdict") != "confirmed"
            or ap.get("outcome") != "ratified"):
        st.findings.append(Finding(
            "approval_unratified",
            f"A data-plane sign-off exists at {st.approval_path} and it does not ratify: status="
            f"{ap.get('status')!r}, verdict={ap.get('verdict')!r}, outcome={ap.get('outcome')!r}. A "
            f"draft is not an approval.",
            f"set status: applied · verdict: confirmed · outcome: ratified in {st.approval_path}",
            st.approval_path))
    if ap.get("submitted_via") != "human" or ap.get("identity_basis") not in (
            "verified", "local-declared"):
        st.findings.append(Finding(
            "approval_agent_stamped",
            f"The sign-off's write stamp does not name a human act: submitted_via="
            f"{ap.get('submitted_via')!r}, identity_basis={ap.get('identity_basis')!r}. An agent may "
            f"write a description; only a human may write a disposition. `verified` means a signed-in "
            f"identity; `local-declared` means the identity the person who started the local server "
            f"declared, which is weaker and is shown as weaker.",
            f"the sign-off must carry submitted_via: human and a verified or local-declared identity",
            st.approval_path))
    if not str(ap.get("by", "") or "").strip():
        st.findings.append(Finding(
            "approval_unratified",
            "The sign-off names nobody. A disposition that claims a human acted must name the human "
            "— never \"the team\", never a tool.",
            f"add `by: <a named person or role>` to {st.approval_path}", st.approval_path))
    decision = str(ap.get("decision", "") or "").strip()
    if not decision or not (root / decision).is_file():
        st.findings.append(Finding(
            "approval_unratified",
            f"The sign-off cites no durable decision record"
            f"{f' — {decision} does not exist' if decision else ''}. A ruling recorded only as a "
            f"YAML field cannot be revisited honestly.",
            "write decisions/NNNN-<slug>.md and name it in the sign-off's `decision:` field",
            decision or "decisions/"))

    # ---- per-issue coverage. THE THRESHOLD, and nobody invented a number.
    covers = [c.strip() for c in re.split(r"[,\s]+", str(ap.get("covers", "") or "")) if c.strip()]
    st.covered = covers
    unnamed = [i for i in ids if i not in covers]
    # THE BLOCKING SET IS THE UNION, because the two questions are different. `undispositioned` is
    # the EXIT (every issue ruled); `unnamed` is a defect in a sign-off that EXISTS and claims to
    # cover this register. A page or a verdict that showed only one would report a closed pipeline
    # with nothing listed against it.
    st.uncovered = st.undispositioned + [i for i in unnamed if i not in st.undispositioned]
    dangling = [c for c in covers if c not in ids]
    if unnamed:
        st.findings.append(Finding(
            "issue_uncovered",
            f"This bundle carries a sign-off and that sign-off does not cover its register: "
            f"{len(unnamed)} of {len(ids)} registered issues are not named in it "
            f"({', '.join(unnamed)}). A sign-off is no longer required — but one that is present is "
            f"honoured rather than ignored, and a present sign-off that covers only part of the "
            f"register is a half-finished human act, not a passing one. Delete it or complete it.",
            f"name each id in the sign-off's `covers:` field in {st.approval_path}, or delete the "
            f"sign-off: the exit is {st.register_path} and the register alone can satisfy it",
            st.approval_path))
    if dangling:
        st.findings.append(Finding(
            "coverage_dangling",
            f"The sign-off names {len(dangling)} id(s) the register no longer holds "
            f"({', '.join(dangling)}). Somebody approved something that has since been renamed or "
            f"deleted, which is the opposite failure from an issue nobody saw.",
            f"reconcile `covers:` in {st.approval_path} against the register, then re-sign",
            st.approval_path))

    # ---- the digest. What stops the ontology disagreeing with datasets that moved.
    signed = str(ap.get("digest", "") or "").strip()
    if not signed:
        st.findings.append(Finding(
            "approval_unratified",
            "The sign-off carries no digest, so it does not say WHICH data plane was approved. An "
            "approval without one is a permanent licence rather than a statement about one state.",
            f"python3 tools/check_data_plane_approved.py <root> --print-approval", st.approval_path))
    elif signed != st.digest_now:
        st.moved_files = _moved(root, ap)
        moved = f"{len(st.moved_files)} of {st.digest_files}" if st.moved_files else \
                f"some of {st.digest_files}"
        st.findings.append(Finding(
            "plane_moved",
            f"The ontology pipeline is closed: the data plane moved after it was approved. The "
            f"sign-off of {ap.get('at', '<undated>')} by {ap.get('by', '<unnamed>')} covers a plane "
            f"whose digest no longer matches — {moved} data-plane files changed"
            f"{': ' + ', '.join(st.moved_files[:6]) if st.moved_files else ''}. The ontology already "
            f"authored is untouched and still answerable; renewing the sign-off reopens the pipeline.",
            f"review the change, then re-sign {st.approval_path} with the new digest",
            st.approval_path))

    # ---- provenance, as EVIDENCE and never as authorization
    who = _introducing_commit(root, st.approval_path)
    if who and "claude" in who.lower():
        st.findings.append(Finding(
            "approval_agent_stamped",
            f"The commit that introduced the sign-off is attributed to an agent ({who}). This is "
            f"evidence after the fact, not authorization: `git -c user.name=…` defeats it, and it is "
            f"reported for exactly what it is.",
            f"the sign-off must be committed by the human who made it", st.approval_path))
    return st


def _moved(root: Path, ap: dict) -> list:
    """Which files moved since the sign-off — from its per-file lock sibling when one exists.

    The lock is EVIDENCE, never AUTHORITY: it lives outside the protected set and is agent-writable
    by design, because it is the reviewable artifact the operator diffs. Forging it buys nothing —
    the gate computes the roll-up from the FILES and compares it to the sign-off, so the lock is
    never the compared value. Absent, the gate can still say the plane moved; it just cannot name
    which files, and says so rather than guessing.
    """
    lock = root / str(ap.get("lock", "") or "data/data_plane.lock")
    if not lock.is_file():
        return []
    try:
        was = json.loads(lock.read_text(encoding="utf-8")).get("files") or {}
    except Exception:
        return []
    now = per_file_digests(root)
    return sorted(set(k for k in set(was) | set(now) if was.get(k) != now.get(k)))


def _introducing_commit(root: Path, rel: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "log", "--follow", "--format=%an|%ae|%b", "--", rel],
            capture_output=True, text=True, timeout=10)
        return (out.stdout or "").strip().split("\n")[-1] if out.returncode == 0 else ""
    except Exception:
        return ""


# ======================================================================== the console contract

def console_block(root: Path) -> dict:
    """The `gate` block the console page renders. NO CONSOLE CODE IS WRITTEN BY THIS BUILD.

    This function is the contract's single home, so the page CALLS it rather than restating its
    field names — the two-homes-for-one-fact defect the seam gates exist to catch. Read-only, never
    bills, and a missing input is a normal state with a sentence rather than an exception.
    Documented field by field in mac-integration-kit/ontology/PIPELINES.md §console contract.
    """
    st = approval_state(root)
    ap = st.approval
    pipeline = ("unknown" if st.unreachable else
                "not_applicable" if not st.applies else
                "ontology" if st.approved else "data")
    return {
        "pipelines": {
            "declared": st.declared,
            "current": pipeline,
            # `kind` CHANGED FROM "approval" TO "register" on 2026-09-18 and `ref` with it, so a
            # page that renders the exit names the file the operator actually has to work in. The
            # retired sign-off keeps a home of its own below (`data_plane.approval_*`) rather than
            # being deleted from the contract: a bundle that carries one still shows it.
            "data": {"exit": {"kind": "register", "ref": st.register_path,
                              "satisfied": st.approved,
                              "guarantee": "attribution",
                              "ruled": len(st.ruled), "of": st.issues_total}},
            "ontology": {"requires": {"pipeline": "data", "satisfied": st.approved},
                         "blocked": st.applies and not st.approved},
        },
        "data_plane": {
            "approved": st.approved,
            # A SIGN-OFF IS OPTIONAL SINCE 2026-09-18. `approval_present: false` with
            # `approved: true` is now a NORMAL state and the page must not paint it as missing
            # evidence — the evidence is per-issue, in `issues.ruled`.
            "approval_present": st.approval_present,
            "approval_required": False,
            # NEVER a restatement of the file's own `status:` field — recomputed from the plane.
            "approved_by_role": (ap.get("role") or None),
            "approved_at": (ap.get("at") or None),
            "identity_basis": (ap.get("identity_basis") or None),
            "digest_signed": (ap.get("digest") or "")[:19] or None,
            "digest_current": st.digest_now[:19] or None,
            "digest_matches": (bool(ap) and ap.get("digest") == st.digest_now) if ap else None,
            "digest_files": st.digest_files,
            "moved_files": st.moved_files,
        },
        "issues": {
            "register": st.register_path,
            "total": st.issues_total,
            "defects": st.issues_dq,
            "non_promotions": st.issues_ns,
            # `ruled` IS THE EXIT'S NUMERATOR — ids at a terminal term with that term's evidence.
            # `covered_by_approval` remains the OPTIONAL sign-off's own list, and is empty when no
            # sign-off exists; a page must read `ruled` for the gate and never `covered_by_approval`.
            "ruled": st.ruled,
            "undispositioned": st.undispositioned,
            "covered_by_approval": st.covered,
            "uncovered": st.uncovered,
            # by_severity IS DELIBERATELY ABSENT. A page that paints severities beside a closed gate
            # teaches operators to downgrade one, and that already happened on a live register.
        },
        "ontology": {
            # TWO permissions, shown separately, because they are now two different things.
            "authorable": st.approved,
            "mutable": (root / ".ontology-unlocked").exists(),
            "concepts": len(list((root / "ontology" / "concepts").glob("*.yaml")))
            if (root / "ontology" / "concepts").is_dir() else 0,
        },
        "blocking": [{"code": f.code, "sentence": f.sentence, "act": f.act, "evidence": f.evidence}
                     for f in st.blocking],
        "evidence": {"approval": st.approval_path, "register": REGISTER_REL,
                     "manifest": "mac.project.yaml"},
    }


# ======================================================================== the prepared ruling

def print_ruling(st: State) -> None:
    """CORE.md §6 — the ruling arrives PREPARED, so the cheapest reply is agreement."""
    print("PREPARED RULING — the data plane's approval")
    print("=" * 78)
    print(f"THE CLOSED QUESTION: may the ontology pipeline start over this data plane?")
    print(f"PERMITTED ANSWERS:   approve (sign off) · rule differently on an issue · decline")
    print()
    print(f"WHAT IS ESTABLISHED: {st.datasets} dataset(s) served · {st.issues_total} registered "
          f"issue(s) ({st.issues_dq} graded defect(s), {st.issues_ns} non-promotion(s)) · "
          f"{st.digest_files} file(s) in the data-plane digest.")
    print(f"WHAT IS NOT ESTABLISHED, and is yours to settle: whether these datasets are configured "
          f"as you intend, and whether each registered issue is acceptable.")
    print()
    if st.undispositioned:
        print("PER ISSUE — each needs a terminal disposition with its named ruler and reason:")
        for i in st.undispositioned:
            print(f"  · {i}")
        print()
    print("CONSEQUENCE OF RULING:     the ontology pipeline opens and concepts may be authored.")
    print("CONSEQUENCE OF DECLINING:  the data plane stays open to change; no concept is authored.")
    print("NOTE: this gate reads NO severity field. A non-defect graded `high` blocks nothing.")
    print("NOTE: THERE IS NO SEPARATE SIGN-OFF TO WRITE. The exit is the register itself, so what")
    print("      it buys is ATTRIBUTION — a named ruler and a reason per issue — and not")
    print("      PREVENTION: the register is a file an agent can write. That is the ceiling this")
    print("      estate already had; a second artifact saying the same thing did not raise it.")
    print()
    print(f"RECOMMENDATION: rule on each issue above in {st.register_path} —")
    print("  status: accepted | wont_fix | resolved   ·   ruled_by: <a named person or role>")
    print("  reason: <why it is real, and why it is being lived with>")


def print_approval(st: State) -> None:
    """RETIRED 2026-09-18 — a NOTE, and no longer a block to save.

    This used to emit `governance/data_plane_approval.yaml` for a human to save and commit. There is
    nothing to save any more: the DATA pipeline's exit is the register, and the operator who was
    meant to sign this refused it — having already ruled on every issue in that register, one at a
    time, each with its own recorded argument.

    The flag KEEPS ITS NAME so no caller, doc or refusal message breaks on it, and prints what the
    exit actually is. A tool that silently did nothing would be worse than one that says so.
    """
    print("RETIRED — there is no sign-off block to save, and none is required.")
    print("=" * 78)
    print(f"THE DATA PIPELINE'S EXIT IS ITS REGISTER: {st.register_path}")
    print("Every registered issue must carry a TERMINAL mac.dq_status term with that term's own")
    print("evidence — `accepted` and `wont_fix` require `ruled_by` and `reason`; `resolved` is")
    print("evidenced structurally and is refused on an `NS-` id. An `open` issue closes the")
    print("pipeline. Nothing else is asked of you.")
    print()
    print("WHY THIS WENT AWAY. The separate file duplicated the register in a LESS informative")
    print(f"form: one date and one name against {st.issues_total} individually-argued dispositions.")
    print("It was this build's design choice and never the operator's requirement, whose actual")
    print("words were that the ontology may not proceed until the number of issues is reduced to an")
    print("acceptable minimum — which is recorded in the register, per issue, with a reason.")
    print()
    print("WHAT IT COST, AND IT IS NOT NOTHING. The sign-off was the one artifact an agent provably")
    print("cannot write: the guard denies that path unconditionally, marker or not. The register is")
    print("agent-writable. So this exit rests on ATTRIBUTION — a named ruler, a reason, git blame,")
    print("the decision record — and not on PREVENTION. In a single-identity self-merge estate")
    print("there is no second party to hold a token anyway; the honest claim, in the estate's own")
    print("words, is DETECTED-AND-BLOCKED, AUTHORIZED OUT-OF-BAND. See PIPELINES.md §8 gap 11.")
    print()
    if st.approval_present:
        print(f"THIS BUNDLE DOES CARRY A SIGN-OFF at {st.approval_path}, and it is still HONOURED:")
        print("every approval reject class is live over it, so it can still fail. Completing it or")
        print("deleting it are both valid; ignoring it is not.")
    else:
        print(f"No sign-off exists at {st.approval_path} and none will be asked for. If one is")
        print("present in some bundle it is still validated — honoured, never ignored.")
    print()
    print("  python3 tools/check_data_plane_approved.py <root> --print-ruling   # the prepared ruling")


# ======================================================================== guard agreement

def guard_agrees(root: Path, st: State, guard: Path) -> tuple:
    """Two callers, one decision — asserted ON THE LIVE BUNDLE, not on a fixture pair."""
    if not guard or not Path(guard).is_file():
        return None, f"the guard is not at {guard}"
    probe = str(Path(root) / "ontology" / "concepts" / "_gate_probe.yaml")
    try:
        proc = subprocess.run(
            [sys.executable, str(guard), "--explain", probe],
            capture_output=True, text=True, timeout=20)
    except Exception as exc:
        return None, f"the guard could not be run: {exc}"
    allowed = proc.returncode == 0
    want = st.approved if st.applies else None
    if want is None:
        return None, "the bundle declares one pipeline, so the guard's verdict is the legacy one"
    if allowed == want:
        return True, (f"guard agrees: it would "
                      f"{'ALLOW' if allowed else 'DENY'} a write to the ontology plane")
    return False, (f"guard DISAGREES: the gate says {'approved' if want else 'blocked'} and the "
                   f"guard would {'ALLOW' if allowed else 'DENY'}. One fact, two verdicts.")


# ======================================================================== verdict line

def verdict_line(st: State) -> str:
    if st.unreachable:
        return (f"could not run: check_data_plane_approved — {st.unreachable} "
                f"(exit 2 is not a verdict)")
    if not st.applies:
        return ("PASS: check_data_plane_approved — 1 pipeline declared; the two-pipeline gate does "
                "not apply to this bundle. Its ontology plane is governed by the operator's unlock "
                "marker alone, unchanged.")
    if st.approved:
        ap = st.approval
        # THE DENOMINATOR IS THE RULED COUNT OVER THE REGISTERED COUNT, because the register is the
        # exit. The sign-off, when one exists, is reported as the SECOND clause — present and
        # honoured, never the thing that opened the gate.
        signed = (f"; a sign-off is also present at {st.approval_path} and was honoured: by "
                  f"{ap.get('by')} on {ap.get('at')} (role {ap.get('role')}, identity "
                  f"{ap.get('identity_basis')}, {ap.get('decision')}), digest matches over "
                  f"{st.digest_files} data-plane file(s)") if st.approval_present else \
                 (f"; no sign-off file exists and none is required — the exit is the register, and "
                  f"what it buys is ATTRIBUTION (`ruled_by` per issue), not PREVENTION")
        return (f"PASS: check_data_plane_approved — the DATA pipeline has reached its declared exit "
                f"({st.register_path}): {len(st.ruled)} of {st.issues_total} registered issue(s) "
                f"carry a terminal disposition with its required evidence ({st.issues_dq} graded "
                f"defect(s), {st.issues_ns} non-promotion(s)); 0 open{signed}. The ontology pipeline "
                f"may be started manually. Severity was not read.")
    classes = sorted({f.code for f in st.findings})
    return (f"FAIL: check_data_plane_approved — the ontology pipeline is CLOSED: "
            f"{len(st.findings)} blocker(s) in {len(classes)} class(es) [{', '.join(classes)}] over "
            f"{st.issues_total} registered issue(s) ({st.issues_dq} graded defect(s), "
            f"{st.issues_ns} non-promotion(s)) in {st.register_path} and {st.digest_files} "
            f"data-plane file(s); {len(st.uncovered)} of {st.issues_total} issue(s) unresolved "
            f"({len(st.undispositioned)} undispositioned)")


# ======================================================================== self-test

def _seed(tmp: Path, name: str, *, pipelines=True, issues=True, concepts=0) -> Path:
    b = tmp / name
    (b / "data" / "datasets").mkdir(parents=True, exist_ok=True)
    (b / "data" / "quality").mkdir(parents=True, exist_ok=True)
    (b / "decisions").mkdir(parents=True, exist_ok=True)
    repro = ("""
reproduction:
  pipelines:
    data:
      entry: harvest --mode onboard --accept
      exit:
        register: data/quality/data_quality_register.yaml
    ontology:
      entry: harvest --mode ontology
      requires:
        pipeline: data
  stages:
  - id: measure
    authoring: tool
    pipeline: data
""" if pipelines else """
reproduction:
  stages:
  - id: measure
    authoring: tool
""")
    (b / "mac.project.yaml").write_text(
        f"spec_version: mac.container/1\nmetadata:\n  project: example/{name}\n"
        f"descriptors: data/datasets\n{repro}", encoding="utf-8")
    # EVERY PLANE THE SURFACE COVERS gets a file, so the roll-up is exercised over the whole
    # enumeration rather than over one directory. Without this, dropping a plane from the surface
    # changes no fixture's digest and the seam gate catches the shrink only by enumeration —
    # measured, when a mutant that deleted `data/transforms` from the surface left every fixture
    # roll-up identical.
    (b / "data" / "datasets" / "v_example_one.yaml").write_text("dataset: v_example_one\n",
                                                                encoding="utf-8")
    (b / "data" / "datasets" / "v_example_one.md").write_text("# projected twin — never hashed\n",
                                                              encoding="utf-8")
    for rel, body in (("data/transforms/v_example_one.yaml", "transform: v_example_one\n"),
                      ("data/transforms/v_example_one.sql", "-- v_example_one\nSELECT 1;\n"),
                      ("data/sources/one.yaml", "source: one\n"),
                      ("data/profiles/one.yaml", "profile: one\nrows: 1\n"),
                      ("data/lookups/colours.lookup.csv", "name,code\nred,R\n")):
        q = b / rel
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_text(body, encoding="utf-8")
    reg = ("metadata:\n  status: draft\nissues:\n"
           "  - id: NS-ALPHA-01\n    severity: high\n    status: open\n    confidence: I\n"
           "    finding: synthetic\n"
           "  - id: DQ-ALPHA-01\n    severity: low\n    status: open\n    confidence: I\n"
           "    finding: synthetic\n") if issues else "metadata:\n  status: draft\nissues: []\n"
    (b / "data" / "quality" / "data_quality_register.yaml").write_text(reg, encoding="utf-8")
    (b / "decisions" / "0001-approve-the-data-plane.md").write_text(
        "**Status:** ACCEPTED 2026-09-18 (operator)\n", encoding="utf-8")
    for i in range(concepts):
        (b / "ontology" / "concepts").mkdir(parents=True, exist_ok=True)
        (b / "ontology" / "concepts" / f"t{i}.yaml").write_text("concept: t\n", encoding="utf-8")
    return b


def _rule(b: Path, *, ns="accepted", dq="accepted") -> None:
    p = b / "data" / "quality" / "data_quality_register.yaml"
    p.write_text(
        "metadata:\n  status: draft\nissues:\n"
        f"  - id: NS-ALPHA-01\n    severity: high\n    status: {ns}\n    confidence: C\n"
        "    ruled_by: A. Operator\n    reason: identical values; the pair is the fact of record\n"
        "    finding: synthetic\n"
        f"  - id: DQ-ALPHA-01\n    severity: low\n    status: {dq}\n    confidence: C\n"
        "    ruled_by: A. Operator\n    reason: measured, real, tolerated for this release\n"
        "    finding: synthetic\n", encoding="utf-8")


def _sign(b: Path, **over) -> None:
    d, _ = data_plane_digest(b)
    f = {"id": SIGN_OFF_ID, "kind": "sign_off", "plane": "data", "status": "applied",
         "verdict": "confirmed", "outcome": "ratified",
         "covers": "NS-ALPHA-01, DQ-ALPHA-01", "register": REGISTER_REL, "digest": d,
         "decision": "decisions/0001-approve-the-data-plane.md", "rev": "1", "at": "'2026-09-18'",
         "by": "A. Operator", "role": "operator", "identity_basis": "local-declared",
         "submitted_via": "human"}
    f.update(over)
    p = b / "governance" / "data_plane_approval.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(f"{k}: {v}\n" for k, v in f.items()), encoding="utf-8")


def _self_test() -> int:
    fails, n = [], 0

    def want(name, got, expect):
        nonlocal n
        n += 1
        if got != expect:
            fails.append(f"{name}: got {got!r}, want {expect!r}")

    def codes(st):
        return sorted({f.code for f in st.findings})

    terms = _terms()
    if not terms:
        print("could not run: check_data_plane_approved self-test — "
              "mac_vocabulary.yaml#data_plane_gate is unreadable")
        return EXIT_COULD_NOT_RUN

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # CLEAN 1 — a bundle declaring ONE pipeline: the gate does not apply. Exit 0, not a block.
        st = approval_state(_seed(tmp, "legacy", pipelines=False, concepts=22))
        want("not_declared passes", st.approved, False)
        want("not_declared does not apply", st.applies, False)
        want("not_declared has no blockers", codes(st), [])

        # CLEAN 2 — THE WHOLE HAPPY PATH, AND IT IS THE ONE THAT CHANGED. A first ingestion whose
        # register is fully ruled, with NO SIGN-OFF FILE ANYWHERE. This assertion used to require
        # `_sign(b)` as well; the sign-off was retired on 2026-09-18 (see the module docstring and
        # mac_vocabulary.yaml#data_plane_gate.approval_missing) and the register is the exit.
        b = _seed(tmp, "beta"); _rule(b)
        st = approval_state(b)
        want("a fully-ruled register alone opens the pipeline",
             (st.approved, codes(st)), (True, []))
        want("…and no sign-off file was involved", st.approval_present, False)
        want("…and every registered id counts as ruled", len(st.ruled), st.issues_total)

        # CLEAN 3 — A BUNDLE THAT DOES CARRY A SIGN-OFF STILL WORKS. Honoured, never ignored.
        b = _seed(tmp, "beta_signed"); _rule(b); _sign(b)
        st = approval_state(b)
        want("a ruled register plus a valid sign-off is approved",
             (st.approved, codes(st)), (True, []))
        want("…and the sign-off is reported as present", st.approval_present, True)

        # RETIRED CLASS — an absent sign-off is NO LONGER A FINDING. The mutant that used to seed
        # `approval_missing` (a bundle with no sign-off) now seeds `issue_undispositioned`, because
        # its register is unruled; that is the exit doing the work the ceremony used to do.
        st = approval_state(_seed(tmp, "m_missing"))
        want("approval_missing is retired and never emitted",
             "approval_missing" in codes(st), False)
        want("an unruled register closes the pipeline instead",
             "issue_undispositioned" in codes(st), True)
        b = _seed(tmp, "m_missing_ruled"); _rule(b)
        want("and an absent sign-off over a RULED register is no finding at all",
             codes(approval_state(b)), [])

        b = _seed(tmp, "m_unreadable"); _rule(b); _sign(b)
        p = b / "governance" / "data_plane_approval.yaml"
        p.write_text(p.read_text() + "nested:\n  deep: 1\n", encoding="utf-8")
        want("approval_unreadable", codes(approval_state(b)), ["approval_unreadable"])

        b = _seed(tmp, "m_unratified"); _rule(b); _sign(b, verdict="rejected")
        want("approval_unratified", "approval_unratified" in codes(approval_state(b)), True)

        b = _seed(tmp, "m_agent"); _rule(b); _sign(b, submitted_via="agent")
        want("approval_agent_stamped", "approval_agent_stamped" in codes(approval_state(b)), True)
        b = _seed(tmp, "m_imported"); _rule(b); _sign(b, identity_basis="imported")
        want("imported identity is agent_stamped", "approval_agent_stamped" in codes(approval_state(b)), True)

        b = _seed(tmp, "m_uncovered"); _rule(b); _sign(b, covers="NS-ALPHA-01")
        want("issue_uncovered", "issue_uncovered" in codes(approval_state(b)), True)

        b = _seed(tmp, "m_undisp"); _sign(b)
        want("issue_undispositioned", "issue_undispositioned" in codes(approval_state(b)), True)
        b = _seed(tmp, "m_norules"); _rule(b, dq="accepted")
        p = b / "data" / "quality" / "data_quality_register.yaml"
        # Strip `ruled_by` from the DEFECT only — an `accepted` that claims a human acted and names
        # nobody. The non-promotion above it keeps its namer, so the mutant is one class, not two.
        p.write_text(p.read_text().replace(
            "    status: accepted\n    confidence: C\n    ruled_by: A. Operator\n"
            "    reason: measured, real, tolerated for this release\n",
            "    status: accepted\n    confidence: C\n"
            "    reason: measured, real, tolerated for this release\n"), encoding="utf-8")
        _sign(b)
        want("a terminal term missing its `requires` is undispositioned",
             "issue_undispositioned" in codes(approval_state(b)), True)

        # THE CATEGORY ERROR — the one spelling a machine can write with no human name anywhere.
        b = _seed(tmp, "m_resolved"); _rule(b, ns="resolved"); _sign(b)
        want("resolved_on_non_defect", "resolved_on_non_defect" in codes(approval_state(b)), True)

        b = _seed(tmp, "m_dangling"); _rule(b); _sign(b, covers="NS-ALPHA-01, DQ-ALPHA-01, DQ-GONE-99")
        want("coverage_dangling", "coverage_dangling" in codes(approval_state(b)), True)

        b = _seed(tmp, "m_moved"); _rule(b); _sign(b, digest="sha256:" + "0" * 64)
        want("plane_moved", "plane_moved" in codes(approval_state(b)), True)

        b = _seed(tmp, "m_unrun", issues=False); _sign(b, covers="")
        want("register_unrun", "register_unrun" in codes(approval_state(b)), True)

        b = _seed(tmp, "m_nodata"); _rule(b)
        os.remove(b / "data" / "datasets" / "v_example_one.yaml"); _sign(b)
        want("no_datasets", "no_datasets" in codes(approval_state(b)), True)

        b = _seed(tmp, "m_stage"); _rule(b)
        mp = b / "mac.project.yaml"
        # Anchored on the newline: `pipelines.ontology.requires.pipeline: data` is indented 8 and
        # would otherwise match as a substring, breaking the manifest instead of seeding the mutant.
        mp.write_text(mp.read_text().replace("\n    pipeline: data\n", "\n"), encoding="utf-8")
        _sign(b)
        want("stage_unassigned", "stage_unassigned" in codes(approval_state(b)), True)

        st = approval_state(tmp / "does-not-exist")
        want("gate_unreachable", codes(st), ["gate_unreachable"])

        # NEGATIVE CONTROL 1 — SEVERITY IS INERT. The non-defect stays at `high` and passes; move
        # the grade in either direction and the verdict must not move. Any future edit that starts
        # reading severity turns this red.
        for sev in ("low", "medium", "high"):
            b = _seed(tmp, f"neg_sev_{sev}"); _rule(b)
            p = b / "data" / "quality" / "data_quality_register.yaml"
            p.write_text(p.read_text().replace("severity: high", f"severity: {sev}"),
                         encoding="utf-8")
            _sign(b)
            want(f"severity {sev} does not move the verdict", approval_state(b).approved, True)

        # INVERTED 2026-09-18, DELIBERATELY, AND THIS IS THE ASSERTION THAT ENCODES THE NEW EXIT.
        # This used to be a NEGATIVE CONTROL reading "an acknowledged NS- id at `open` does not
        # block": an `NS-` disclosure needed only to be NAMED in the sign-off, because acknowledging
        # a disclosure is a different act from dispositioning a defect — and the sign-off was where
        # the acknowledgement lived. With the sign-off retired there is nowhere else to record it,
        # so it is recorded in the register like everything else, and `open` closes the pipeline.
        # The control is kept as its inverse rather than deleted, so the change is visible here.
        b = _seed(tmp, "neg_ns_open"); _rule(b, ns="open"); _sign(b)
        st = approval_state(b)
        want("an NS- id at `open` now BLOCKS — the register is the exit", st.approved, False)
        want("…as issue_undispositioned", "issue_undispositioned" in codes(st), True)
        want("…naming that id", st.undispositioned, ["NS-ALPHA-01"])
        # …and the same id at a terminal term with its evidence clears, sign-off or no sign-off.
        b = _seed(tmp, "neg_ns_wont_fix"); _rule(b, ns="wont_fix")
        want("`wont_fix` is terminal and clears with a namer and a reason",
             approval_state(b).approved, True)

        # AN `accepted` THAT NAMES NOBODY BLOCKS ON EITHER KIND OF ID. `ruled_by` IS the attribution
        # the exit now rests on, so a terminal word without one is not a disposition.
        for kind, rid in (("non-promotion", "NS-ALPHA-01"), ("graded defect", "DQ-ALPHA-01")):
            b = _seed(tmp, f"m_anon_{rid}"); _rule(b)
            p = b / "data" / "quality" / "data_quality_register.yaml"
            lines, inside, keep = p.read_text(encoding="utf-8").split("\n"), False, []
            for ln in lines:
                if ln.strip().startswith("- id:"):
                    inside = rid in ln
                if inside and ln.strip().startswith("ruled_by:"):
                    continue
                keep.append(ln)
            p.write_text("\n".join(keep), encoding="utf-8")
            st = approval_state(b)
            want(f"an `accepted` {kind} naming nobody blocks", st.approved, False)
            want(f"…and {rid} is the id reported", st.undispositioned, [rid])

        # NEGATIVE CONTROL 3 — the projected twins and the preview plane must NOT move the digest,
        # or every projection invalidates the approval and operators learn to re-sign reflexively.
        b = _seed(tmp, "neg_churn"); _rule(b); _sign(b)
        (b / "data" / "datasets" / "v_example_one.md").write_text("# twin\n", encoding="utf-8")
        (b / "data" / "samples").mkdir(parents=True, exist_ok=True)
        (b / "data" / "samples" / "one.sample.csv").write_text("k\n1\n", encoding="utf-8")
        (b / "connection.yaml").write_text("host: elsewhere\n", encoding="utf-8")
        (b / "compile.json").write_text("{}\n", encoding="utf-8")
        want("projection, previews and connection.yaml do not stale the approval",
             approval_state(b).approved, True)
        # …and a COMMENT REFLOW on a hashed file must not stale it either.
        reg = b / "data" / "quality" / "data_quality_register.yaml"
        reg.write_text("# a long new explanatory comment\n#\n" + reg.read_text(), encoding="utf-8")
        want("a comment reflow does not stale the approval", approval_state(b).approved, True)
        # …but a VALUE change must.
        reg.write_text(reg.read_text().replace("status: accepted", "status: open", 1),
                       encoding="utf-8")
        want("a disposition written after the sign-off STALES it",
             "plane_moved" in codes(approval_state(b)), True)

        # EVERY CODE EMITTED IS A DECLARED MEMBER — the law is read, never restated.
        emitted = set()
        for name in os.listdir(td):
            emitted |= {f.code for f in approval_state(tmp / name).findings}
        undeclared = sorted(emitted - set(terms))
        want("every emitted code is a mac.data_plane_gate member", undeclared, [])

    if fails:
        for f in fails:
            sys.stderr.write(f"  {f}\n")
        print(f"FAIL: check_data_plane_approved self-test — {len(fails)} of {n} assertions failed")
        return EXIT_FAIL
    # THE BLOCKING COUNT IS DERIVED FROM `blocks:`, NOT FROM `len(terms) - 1`. It was that
    # arithmetic until 2026-09-18, when a SECOND non-blocking member appeared (`approval_missing`,
    # retired) and the subtraction quietly over-counted by one. A denominator computed by guessing
    # how many exceptions there are is a denominator that lies the first time there are two.
    blocking = sorted(t for t, v in terms.items() if (v or {}).get("blocks"))
    print(f"PASS: check_data_plane_approved self-test — {n}/{n} assertions: one mutant per each of "
          f"{len(blocking)} blocking reject class(es), plus the {len(terms) - len(blocking)} "
          f"non-blocking member(s) ({', '.join(t for t in terms if t not in blocking)}) asserted "
          f"NOT to block, and 8 negative controls (severity inert at low/medium/high, a ruled "
          f"register with no sign-off anywhere, a ruled register WITH one, `wont_fix` as terminal, "
          f"projection and preview churn, comment reflow) — severity is on no code path the verdict "
          f"depends on, and the exit is {REGISTER_REL}")
    return EXIT_PASS


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", help="bundle root")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--json", action="store_true", help="print the console `gate` contract block")
    ap.add_argument("--print-ruling", action="store_true", help="the prepared ruling (CORE.md §6)")
    ap.add_argument("--print-approval", action="store_true",
                    help="the sign-off block, to STDOUT, for the human to save — writes no file")
    ap.add_argument("--agree", action="store_true",
                    help="also assert the installed guard reaches the same verdict on this bundle")
    ap.add_argument("--guard", default=None, help="path to ontology_guard.py for --agree")
    a = ap.parse_args()

    if a.self_test:
        return _self_test()
    if not a.root:
        ap.print_usage()
        return EXIT_COULD_NOT_RUN
    root = Path(a.root)
    if not root.is_dir():
        print(f"could not run: check_data_plane_approved — no such bundle root: {root}")
        return EXIT_COULD_NOT_RUN

    if a.json:
        print(json.dumps(console_block(root), indent=2))
        return EXIT_PASS

    st = approval_state(root)
    if a.print_ruling:
        print_ruling(st)
        return EXIT_PASS
    if a.print_approval:
        print_approval(st)
        return EXIT_PASS

    for f in st.findings:
        print(f"  [{f.code}] {f.sentence}")
        print(f"      ACT:      {f.act}")
        print(f"      EVIDENCE: {f.evidence}")

    rc = EXIT_COULD_NOT_RUN if st.unreachable else (EXIT_PASS if not st.applies or st.approved
                                                    else EXIT_FAIL)
    if a.agree:
        guard = Path(a.guard) if a.guard else (root / ".claude" / "hooks" / "ontology_guard.py")
        ok, note = guard_agrees(root, st, guard)
        print(f"  {note}")
        if ok is False:
            print(f"FAIL: check_data_plane_approved — {note}")
            return EXIT_FAIL
    print(verdict_line(st))
    return rc


if __name__ == "__main__":
    sys.exit(main())
