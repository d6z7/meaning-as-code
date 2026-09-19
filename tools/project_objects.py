#!/usr/bin/env python3
"""project_objects.py — DERIVE a bundle's object index as one `mac.seam/1` envelope on stdout.

WHY THIS FILE EXISTS, AND WHY IT IS HERE RATHER THAN IN THE CONSOLE

The console served its object index by reading `<bundle>/objects.json` off disk. That file is a
BUILD ARTIFACT: it is written only when the projector runs, so between two projections the page is
exactly as old as the last run and says nothing about it. Measured once: the file held 9 objects
while the bundle on disk had gained 6 dataset descriptors and 12 transform files, and the console
showed none of them for 46 minutes with no marker of any kind. An operator asked for the obvious
thing — "as soon as object gets created we should see it".

The index has ONE author, `sdk.project.objects.build_objects`, and it is pure: with `out_dir=None`
every write in it is skipped, so it can be called to ANSWER A QUESTION rather than to produce a
file. A live derivation must therefore call that function. Re-implementing an object index in the
reader would create a second author for one artifact, which is the defect class this estate spends
its time removing.

It cannot be called in-process by the reader, though: `boundaries.yaml` — at the HOST REPOSITORY
ROOT, governing the tree named `wiki` (`role: gui`), which is where the console lives — gives that
tree `may_not_import: [sdk]` and `may_sys_path_mutate: false`, and `sdk.project.objects.__main__`
refuses to be a CLI (correctly — its two optional arguments default to empty and produce a
complete-LOOKING index with two view classes silently missing). So this file is the seam: a thin
framework-side entry point that SUPPLIES BOTH of those arguments, calls the one author, and prints
what it returned. The console runs it as a subprocess, exactly as it already runs
tools/lineage_project.py.

  (The tree's name is load-bearing and this docstring used to get it wrong. It cited a real clause
  under the name `console`, which appears nowhere in that file, so the rule could not be looked up.
  See SEAM_CONTRACT.md §2.1 and §9.)

WHAT IT GUARANTEES — SEAM_CONTRACT.md `mac.seam/1`, and `tools/check_seam_contract.py` is the copy
that refuses

  * ONE ENVELOPE, ALWAYS THE SAME SHAPE. Every exit — success, degrade, refusal, caller error —
    prints one JSON object carrying the same reserved keys of §3 at the empty value of their own
    type. They are emitted by ONE builder (`_envelope`) precisely so no exit can grow or drop a
    key: 3 of the 6 top-level keys of the version before this one vanished on a failure exit, so a
    client reading one of them was reading a key that exists only when nothing went wrong.
  * INDEX MODE, DECLARED AND EARNED (§5). `result` is a list of independently derived members and
    this seam can publish `returned of declared`, so it MAY serve an incomplete answer — and does,
    as `status: degraded` with `partial[]` naming every piece that is missing. The denominator is
    the descriptor files the enumerating planes declare, counted with the SAME globs build_objects
    uses, never inferred from the members that happened to parse (§10.6).
  * NOTHING IS WRITTEN. `out_dir=None` is passed unconditionally and is the only call in this file.
    The bundle it reads is, for the caller, immutable and frequently mid-ingestion.
  * BOTH ARGUMENTS ARE SUPPLIED. `lineage=` is the flows list from the same lineage projector the
    supported path uses (sdk/cli/harvest.py `_lineage_flows`); `issues=` is the quality register,
    read the same way project_data.py reads it. Omitting the first flips `lineage: false` on every
    source and dataset and drops their Lineage tab; that regression has shipped twice and both
    times a person noticed, not a gate.
  * EVERY INPUT IS DECLARED, AND ITS FAILURE IS REPORTED (§6.1). `inputs[]` names every file this
    seam's run opens, root-relative, with its role — the plane that ENUMERATES members is `spine`,
    a file under it is a `row`, a file that decorates members already enumerated is an
    `attribute`, and a framework-side data file is `framework:<name>`. That list is what the host's
    cache watches; a read nobody declared is a cache that cannot know what to watch. It is checked
    against a measured open-trace, not believed.
  * A FAILURE IS NAMED, NEVER SILENT — including at exit. A caller error prints the envelope and
    exits 2 (§4.3); the promise "even then a structured reason goes to stdout" used to be false in
    the only place it mattered, measured at 0 bytes. And the seam runs on the interpreter its own
    usage line documents: `datetime.UTC` is 3.11+, and this file used to exit 1 with 0 bytes on
    `/usr/bin/python3` before it reached a line that could report anything (§4.4).
  * NO ABSOLUTE PATH LEAVES, except inside `local`, which the host drops before the wire (§3).
    Every sentence this seam publishes is scrubbed of both roots, because an exception's own
    message routinely names the file it choked on.
  * IT COSTS NOTHING. Local YAML/JSON/CSV reads under the bundle plus the framework's VERSION file.
    No connector, no warehouse, no model, no network.

Usage:
  python3 tools/project_objects.py <bundle-root> [--out PATH]

  (default)      print the envelope as JSON on stdout
  --out PATH     ALSO write it to PATH, which must be outside the bundle (§2.2). stdout still
                 carries the envelope — a run whose only output was a file was indistinguishable
                 from a silent failure over the host's `if out:` test.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools")):
    # `sdk.*` resolves from the framework root; `lineage_project`/`mac_project` are imported by
    # BARE NAME inside tools/ (that is how lineage_project already reaches mac_project), so both
    # directories have to be reachable when this file is executed by absolute path. Legal only
    # because this file lives on the FRAMEWORK side of the boundary (SEAM_CONTRACT.md §2.1).
    if _p not in sys.path:
        sys.path.insert(0, _p)

import yaml  # noqa: E402

# ONE LINE DELIBERATELY. mac-platform's test_objects_live.py asserts "one author, called not
# copied" by grepping this repository for the literal `from sdk.project.objects import
# build_objects`, so wrapping this import (ruff I001 wants to, at 95 chars) breaks a true assertion
# in the host repo. The claim is right and the grep is brittle; the cheap side of that trade is
# here.
from sdk.project.objects import build_objects, load_dq_findings, load_ont_edges  # noqa: E402

ENVELOPE = "mac.seam/1"
TOOL = "project_objects.py"
MODE = "index"

#: §6.1 — the planes that ENUMERATE members: one file here is one member of the index, and the
#: DIRECTORY LISTING is the enumeration. `(root-relative path, glob, recursive)`, each mirroring the
#: glob `build_objects` itself uses, because a denominator counted a second way is a second author.
#: `ontology/concepts` is recursive: a bundle that files its concepts by domain projected ZERO
#: concepts under a flat glob and nothing said so.
_SPINE_PLANES = (
    ("data/sources", "*.yaml", False),
    ("data/datasets", "*.yaml", False),
    ("data/lookups", "*.csv", False),
    ("ontology/concepts", "*.yaml", True),
)

#: §6.1 — a plane whose files DECORATE members already enumerated. A transform descriptor creates
#: no object of its own: it hangs a Cleaning page and a SQL view on the dataset of the same stem, so
#: it is an attribute of that dataset and not a row of the index. Measured on the public fixture:
#: 1 transform descriptor, 0 transform objects.
_ATTRIBUTE_PLANES = (("data/transforms", "*.yaml", False),)

#: Individual attribute FILES: `(path, what it decorates, is its ABSENCE a degrade?)`. Every one of
#: them is read by the derivation and every one of them was undeclared before this contract.
#:
#: THE THIRD COLUMN IS THE ONE JUDGEMENT IN THIS FILE, so it is written down rather than left to
#: the day. §5.2 says the edge seam DEGRADES when its measurement record is missing, "because
#: membership is intact and only a per-member attribute is unknown" — and `tools/project_edges.py`
#: implements exactly that, partialling on `not present or not parsed`. Applied flatly here it
#: would mark every bundle in the estate degraded forever, which names nothing. The line that
#: reproduces the sibling's ruling without that result:
#:
#:   an attribute's ABSENCE is UNKNOWN — a degrade — when the file is a DERIVED record of something
#:   the members already have; it is EMPTY — not a degrade — when the file is the SSOT and its
#:   absence means the decoration was never authored.
#:
#: The edge seam's measurement record is a proof RUN's output, which is why its absence is unknown
#: and why that seam is the precedent rather than the exception. An unparseable attribute degrades
#: in every row: that is a failure to read, never a measurement.
_ATTRIBUTE_FILES = (
    # The manifest is how column lineage is REACHED; the lineage itself is declared by the
    # transforms. With no manifest every source and dataset carries `lineage: false` in an index
    # that otherwise looks complete — the regression the framework refuses its own CLI over.
    ("mac.project.yaml",
     "column lineage, and with it the Lineage view on every source and dataset", True),
    # A BUILD ARTIFACT projected from the register: absent means the projection has not run, not
    # that no finding exists. Exactly the "as old as the last run" class this seam exists for.
    ("data/quality/dq_dashboard.json", "the Quality tab on every source", True),
    # SSOT planes. Absent means nobody authored one, which is a complete answer, not a gap.
    ("ontology/edges.yaml", "the Relationships panel on every concept", False),
    ("data/quality/data_quality_register.yaml",
     "the quality issues threaded onto every object", False),
    ("data/quality/impurity_resolution_map.yaml", "the Treats panel on every dataset", False),
)


def _iso_now() -> str:
    """ISO-8601 Z, second precision (§3).

    `datetime.UTC` is a 3.11+ alias and this seam declares a 3.9 floor (§4.4). Using it cost this
    file an `AttributeError` at the FIRST line of derivation on `/usr/bin/python3` — exit 1, zero
    bytes on stdout, the one failure no seam can name because it happens before any seam code that
    could name it. Two sibling seams carry an explicit comment about avoiding this alias and the
    fix was back-applied here zero times.
    """
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _scrub(text: object, root: Path | None) -> str:
    """Every sentence this seam publishes, with both roots removed.

    §3 allows an absolute filesystem path in exactly one place, `local`. An exception's own message
    routinely carries one — a YAML parse error names the file it choked on — so scrubbing has to
    happen where the sentence is made, not where it is printed.
    """
    s = str(text)
    for raw, token in ((str(root) if root else None, "<bundle>"), (str(ROOT), "<framework>")):
        if raw:
            s = s.replace(raw, token)
    return s


def _input(path: str, role: str, present: bool, parsed: bool | None, count: int | None) -> dict:
    """One `inputs[]` entry (§3). `parsed` is None for a file this seam lists but never opens."""
    return {"path": path, "role": role, "present": present, "parsed": parsed, "count": count}


def _partial(input_path: str, role: str, effect: str, reason: str) -> dict:
    """One `partial[]` entry (§3): WHICH input, what it cost the answer, and why."""
    return {"input": input_path, "role": role, "effect": effect, "reason": reason}


def _yaml_parses(p: Path) -> tuple[bool, str | None]:
    """(did it parse?, why not).

    The seam measures readability itself for the descriptor planes because `build_objects`' own
    `_load` returns None on a parse error and still emits a row titled by the filename stem — so
    "this file is unreadable" and "this file declares nothing" render identically. Mid-ingestion is
    the NORMAL input here, which is what makes the distinction worth paying for.
    """
    try:
        yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 — a state to report, not to raise
        return False, f"{type(e).__name__}: {e}"
    return True, None


def _plane(root: Path, rel: str, pattern: str, recursive: bool) -> tuple[str, list]:
    """(state, files) for one plane. state ∈ {absent, not_a_directory, ok}.

    `not_a_directory` is the one state in which the ENUMERATION cannot be read, which under §5 is
    the case that refuses in both modes: with the listing unavailable, M is unknown, and "0 members"
    and "the plane could not be read" are the same empty list on the page.
    """
    d = root / rel
    if not d.exists():
        return "absent", []
    if not d.is_dir():
        return "not_a_directory", []
    it = d.rglob(pattern) if recursive else d.glob(pattern)
    return "ok", sorted(p for p in it if p.is_file())


def _framework_version() -> tuple[str, dict, str]:
    """(version, its `inputs[]` entry, its raw bytes as text).

    §6.1 names the version file as a framework-side input and §3 wants it in the seam stamp. It is
    declared as `framework:VERSION` for the same reason the bundle files are declared: the host's
    cache key stats the BUNDLE tree only, so a framework-side file that changes the answer and
    moves no key is the staleness hole one plane up.
    """
    p = ROOT / "VERSION"
    if not p.exists():
        return "unknown", _input("framework:VERSION", "framework", False, None, None), ""
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as e:
        return (
            "unknown",
            _input("framework:VERSION", "framework", True, False, None),
            f"{type(e).__name__}",
        )
    return text.strip() or "unknown", _input("framework:VERSION", "framework", True, True, 1), text


def _code_id(version_text: str) -> str:
    """A digest of the CODE THAT ANSWERED: this file plus every framework-side module this run
    actually loaded, plus the framework inputs (§3).

    MEASURED FROM `sys.modules`, not from a hand-written list, for the same reason `inputs[]` is
    measured from a trace: a list of one's own imports rots, and the estate has the receipts. A run
    that takes a shorter path loads fewer modules and gets a different id — which is the truth,
    since the identity being stamped is the identity of the code that ran.
    """
    h = hashlib.sha256()
    files = {Path(__file__).resolve()}
    for mod in list(sys.modules.values()):
        f = getattr(mod, "__file__", None)
        if not f:
            continue
        try:
            p = Path(f).resolve()
            p.relative_to(ROOT)
        except (ValueError, OSError):
            continue
        files.add(p)
    for p in sorted(files):
        h.update(str(p.relative_to(ROOT)).encode("utf-8"))
        try:
            h.update(hashlib.sha256(p.read_bytes()).digest())
        except OSError:
            h.update(b"\0unreadable")
    h.update(version_text.encode("utf-8"))
    return h.hexdigest()[:16]


def _seam_stamp(version: str, version_text: str) -> dict:
    """§3 `seam {tool, version, framework_root, code_id}` — WHICH framework answered.

    `framework_root` NAMES the tree without leaking it: the host's locator prefers an installed
    framework root and silently falls back to a sibling checkout, so two trees can answer one route
    and nothing on the wire said which. The absolute path stays in `local`; what crosses is the
    directory name and a digest of it, which distinguishes the two checkouts without publishing one
    operator's disk (§3 `local`, §13 PATH_LEAKED).
    """
    return {
        "tool": TOOL,
        "version": version,
        "framework_root": f"{ROOT.name}@{hashlib.sha256(str(ROOT).encode()).hexdigest()[:12]}",
        "code_id": _code_id(version_text),
    }


def _flows(root: Path) -> tuple[list, bool, str | None]:
    """The column-level flows, from the framework's own lineage projector: (flows, ok, reason).

    Threaded into build_objects because it is NOT optional: without it every source and dataset
    comes back with `lineage: false` and no Lineage view, in an index that otherwise looks
    complete. Never raises — a bundle whose manifest has not been written yet is a legitimate
    state, and an absent manifest is reported as an absent INPUT rather than as a failure.
    """
    if not (root / "mac.project.yaml").exists():
        return [], False, None  # absent, not failed: the caller reads it off inputs[]
    try:
        from lineage_project import project  # the ONE author of flows

        model, _unclassifiable = project([str(root)])
        return list(model.get("flows") or []), True, None
    except Exception as e:  # noqa: BLE001 — every failure is a state to report, not to raise
        return [], False, _scrub(f"the lineage projector failed: {type(e).__name__}: {e}", root)


def _register(root: Path) -> tuple[list, bool, str | None]:
    """The data-quality register's issues: (issues, ok, reason).

    Read exactly as sdk/project/project_data.py reads it (`issues` or `findings`), so the Quality
    tabs a live index offers are the ones the projector would have offered.
    """
    p = root / "data" / "quality" / "data_quality_register.yaml"
    if not p.exists():
        return [], False, None
    try:
        reg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as e:  # noqa: BLE001
        return [], False, _scrub(f"{type(e).__name__}: {e}", root)
    issues = (
        (reg.get("issues") or reg.get("findings") or []) if isinstance(reg, dict) else (reg or [])
    )
    return list(issues), True, None


def _envelope(
    status: str,
    reason: str | None,
    *,
    result: list | None = None,
    counts: dict | None = None,
    inputs: list | None = None,
    partial: list | None = None,
    aux: dict | None = None,
    root: Path | None = None,
    traceback_text: str | None = None,
) -> dict:
    """THE ONE BUILDER OF THE ONE SHAPE (§3).

    Every exit this seam can take comes through here, so the reserved key set cannot vary by exit —
    which it did, and which is why a client could read a key that exists only on success. The
    reserved keys are present unconditionally, at the empty value of their own type; everything
    else this seam publishes goes in `aux`, whose contract is that nothing in it may be relied on;
    and `local` is the one block that may carry an absolute path, which the host drops.
    """
    version, version_input, version_text = _framework_version()
    declared = list(inputs or [])
    declared.append(version_input)
    return {
        "envelope": ENVELOPE,
        "mode": MODE,
        "status": status,
        "reason": None if status == "derived" else _scrub(reason, root),
        "result": list(result or []),
        "counts": dict(
            counts
            or {
                "returned": 0,
                "declared": 0,
                "declared_known": True,
                "composed": 0,
                "result_size": 0,
            }
        ),
        "inputs": declared,
        "partial": list(partial or []),
        "seam": _seam_stamp(version, version_text),
        "subject": None,
        "derived_at": _iso_now(),
        "aux": dict(aux or {}),
        # §3: THE ONLY PLACE AN ABSOLUTE PATH MAY APPEAR, and the host MUST drop the whole block
        # before the wire. §4.1 puts an author's traceback here too.
        "local": {
            "root": str(root) if root else None,
            "argv": list(sys.argv[1:]),
            "traceback": traceback_text,
        },
    }


def derive(root: Path) -> tuple[dict, int]:
    """The whole derivation. Returns (envelope, exit code)."""
    inputs: list = []
    partial: list = []
    enumerated: set = set()      # root-relative descriptor paths the spine planes DECLARE — the M
    unreadable_planes: list = []

    # ── THE SPINE: what the bundle DECLARES ─────────────────────────────────────────────────────
    for rel, pattern, recursive in _SPINE_PLANES:
        state, files = _plane(root, rel, pattern, recursive)
        inputs.append(_input(rel, "spine", state == "ok", None, len(files)))
        if state == "not_a_directory":
            unreadable_planes.append(rel)
            continue
        for f in files:
            frel = f.relative_to(root).as_posix()
            enumerated.add(frel)
            if f.suffix == ".yaml":
                parsed, why = _yaml_parses(f)
            else:
                # A lookup CSV is LISTED by build_objects and never opened by it, so this seam does
                # not claim to have read one either. `parsed: null` is the honest value.
                parsed, why = None, None
            inputs.append(_input(frel, "row", True, parsed, 1))
            if parsed is False:
                partial.append(
                    _partial(
                        frel,
                        "row",
                        "this member is indexed from its filename alone — every field, view and "
                        "grounding it declares is missing from the index",
                        _scrub(why, root),
                    )
                )

    # THE ENUMERATION ITSELF COULD NOT BE READ (§5). M is unknown, so there is no honest N of M and
    # index mode's licence to serve an incomplete answer does not apply: a plane that will not list
    # refuses in BOTH modes.
    if unreadable_planes:
        return (
            _envelope(
                "unparsed_input",
                f"{len(unreadable_planes)} of {len(_SPINE_PLANES)} enumerating plane(s) exist and "
                f"are not directories, so the number of members this bundle declares is UNKNOWN "
                f"rather than zero: {unreadable_planes}",
                inputs=inputs,
                counts={
                    "returned": 0,
                    "declared": 0,
                    # §10.6: the zeroes above satisfy the envelope's type, they are NOT a
                    # measurement. This status is not serve-eligible, so the host refuses.
                    "declared_known": False,
                    "composed": 0,
                    "result_size": 0,
                },
                root=root,
            ),
            3,
        )

    # ── THE ATTRIBUTE PLANES: what decorates members already enumerated ─────────────────────────
    for rel, pattern, recursive in _ATTRIBUTE_PLANES:
        state, files = _plane(root, rel, pattern, recursive)
        inputs.append(_input(rel, "attribute", state == "ok", None, len(files)))
        for f in files:
            frel = f.relative_to(root).as_posix()
            parsed, why = _yaml_parses(f)
            inputs.append(_input(frel, "attribute", True, parsed, 1))
            if parsed is False:
                partial.append(
                    _partial(
                        frel,
                        "attribute",
                        "the dataset of the same stem is served without its Cleaning page and "
                        "without the SQL view this descriptor realises",
                        _scrub(why, root),
                    )
                )

    # ── THE ATTRIBUTE FILES ─────────────────────────────────────────────────────────────────────
    effects = {rel: (what, absent_degrades) for rel, what, absent_degrades in _ATTRIBUTE_FILES}

    def attribute(rel: str, present: bool, ok: bool, count: int | None, why: str | None,
                  absent_unknown: bool | None = None) -> None:
        what, absent_degrades = effects[rel]
        if absent_unknown is not None:
            # A DERIVED RECORD IS ONLY `unknown` WHEN THE MATERIAL IT IS DERIVED FROM IS THERE.
            # Absent with nothing behind it is empty, and a bundle that has simply never been
            # projected must not read as damaged — those are the bundles the live derivation was
            # built for.
            absent_degrades = absent_degrades and absent_unknown
        inputs.append(_input(rel, "attribute", present, (ok if present else None), count))
        if present and not ok:
            partial.append(
                _partial(rel, "attribute", f"{what} is missing",
                         _scrub(why or "the file could not be used", root))
            )
        elif not present and absent_degrades and enumerated:
            # ONLY WHEN THERE IS MEMBERSHIP TO DEGRADE. §5.2's degrade is "membership is intact and
            # a per-member attribute is unknown", which presupposes members: a bundle that declares
            # none has nothing to decorate, and an alarm on it would name nothing.
            partial.append(
                _partial(rel, "attribute", f"{what} is missing",
                         "this file is not in the bundle, and it is a DERIVED record: its absence "
                         "means the decoration is unknown, not that there is none")
            )

    # mac.project.yaml — the lineage attribute.
    manifest = root / "mac.project.yaml"
    flows, lineage_ok, lineage_why = _flows(root)
    attribute(
        "mac.project.yaml",
        manifest.exists(),
        lineage_ok,
        len(flows),
        lineage_why or "column lineage could not be derived from this manifest",
    )

    # ontology/edges.yaml — through load_ont_edges, the ONE resolution of where that file lives and
    # the ONE report of whether it read. build_objects calls the same door, so this seam is not a
    # second author of either fact.
    edges_path = root / "ontology" / "edges.yaml"
    ont_edges, edges_error = load_ont_edges(root / "ontology" / "concepts")
    attribute("ontology/edges.yaml", edges_path.exists(), edges_error is None, len(ont_edges),
              edges_error)

    # data/quality/data_quality_register.yaml — read by this seam and threaded in as `issues=`.
    # READ BEFORE THE DASHBOARD, because the dashboard is projected FROM it: whether an absent
    # dashboard is UNKNOWN or merely EMPTY is a fact about this register.
    reg_path = root / "data" / "quality" / "data_quality_register.yaml"
    issues, reg_ok, reg_why = _register(root)
    attribute("data/quality/data_quality_register.yaml", reg_path.exists(), reg_ok, len(issues),
              reg_why)

    # data/quality/dq_dashboard.json — through load_dq_findings, for the same reason as edges and
    # because this read is THE measured case. Corrupting this file used to change the objects
    # payload NOT AT ALL: build_objects read it under `except Exception: pass`, so a truncated
    # dashboard and a dashboard with no findings produced byte-identical answers while every
    # source silently lost its Quality tab. Of 20 traced inputs it was the one that was invisible.
    # The swallow is now a returned error in sdk/project/objects.py, and this is its reporter.
    dash_path = root / "data" / "quality" / "dq_dashboard.json"
    q_by_table, dash_error = load_dq_findings(root / "data")
    attribute("data/quality/dq_dashboard.json", dash_path.exists(), dash_error is None,
              len(q_by_table), dash_error, absent_unknown=bool(issues))

    # data/quality/impurity_resolution_map.yaml — build_objects reads it under a bare `except` too
    # (the Treats panel). This seam claims only that the file is READABLE, which is a property of
    # the file rather than an interpretation of it, so measuring it here makes no second author of
    # its meaning. The swallow itself is out of this step's scope and is reported as such.
    imp_path = root / "data" / "quality" / "impurity_resolution_map.yaml"
    if imp_path.exists():
        imp_ok, imp_why = _yaml_parses(imp_path)
    else:
        imp_ok, imp_why = False, None
    attribute("data/quality/impurity_resolution_map.yaml", imp_path.exists(), imp_ok, None, imp_why)

    # ── THE ONE AUTHOR ──────────────────────────────────────────────────────────────────────────
    try:
        # out_dir=None: every write inside build_objects is guarded by `if out_dir:`, so this
        # derivation cannot touch the bundle it reads.
        built = build_objects(
            root / "data", root / "ontology" / "concepts", lineage=flows, issues=issues,
            out_dir=None,
        )
    except Exception as e:  # noqa: BLE001
        return (
            _envelope(
                "author_failed",
                f"build_objects failed: {type(e).__name__}: {e}",
                inputs=inputs,
                partial=[],
                counts={
                    "returned": 0,
                    "declared": len(enumerated),
                    "declared_known": True,
                    "composed": 0,
                    "result_size": 0,
                },
                root=root,
                traceback_text=traceback.format_exc(limit=6),
            ),
            3,
        )

    objects = list(built.get("objects") or [])

    # ── N OF M (§3 `counts`) ────────────────────────────────────────────────────────────────────
    # M is the descriptor files the enumerating planes DECLARE. N is how many of them produced a
    # member. The gap is real and reachable: the concept plane is keyed by filename STEM, so two
    # concepts filed under different domains with the same stem collide and one of them is dropped
    # with no error anywhere. A denominator that can never differ from its numerator measures
    # nothing, which is the whole complaint behind incident 1.
    backed: set = set()
    composed = 0
    for o in objects:
        paths = [v for v in (o.get("paths") or {}).values() if isinstance(v, str)]
        hits = {v for v in paths if v in enumerated}
        if hits:
            backed |= hits
        else:
            composed += 1
    lost = sorted(enumerated - backed)
    if lost:
        by_plane: dict = {}
        for rel in lost:
            plane = next((p for p, _g, _r in _SPINE_PLANES if rel.startswith(p + "/")), "")
            by_plane.setdefault(plane, []).append(rel)
        for plane, rels in sorted(by_plane.items()):
            partial.append(
                _partial(
                    plane or "(unplaced)",
                    "spine",
                    f"{len(rels)} of {len(enumerated)} declared descriptor(s) produced no member "
                    f"in the index",
                    f"enumerated but unindexed: {rels}",
                )
            )

    # ── THE VERDICT (§4.1, §5) ──────────────────────────────────────────────────────────────────
    counts = {
        "returned": len(backed),
        "declared": len(enumerated),
        "declared_known": True,
        "composed": composed,
        "result_size": len(objects),
    }
    # `aux` carries exactly what this seam publishes beyond the reserved keys — the per-kind counts
    # and the three whole-bundle projections. Declared optional AS A WHOLE (§3): no client may
    # treat a member of it as mandatory.
    aux = {
        "counts": built.get("counts") or {},
        "er_model": built.get("er_model"),
        "er_model_served": built.get("er_model_served"),
        "lineage_graph": built.get("lineage_graph"),
    }

    if partial:
        # `partial != []` IFF `status == degraded` (§3). Index mode may serve this; the membership
        # of the index is intact and a per-member attribute is not.
        heads = ", ".join(sorted({p["input"] for p in partial})[:4])
        more = "" if len(partial) <= 4 else f" (+{len(partial) - 4} more)"
        return (
            _envelope(
                "degraded",
                f"{len(partial)} declared input(s) could not be used, so the index is served "
                f"incomplete: {heads}{more}",
                result=objects, counts=counts, inputs=inputs, partial=partial, aux=aux, root=root,
            ),
            0,
        )

    if not enumerated and all(
        not (root / rel).exists() for rel, _g, _r in _SPINE_PLANES
    ):
        # M is knowably 0 because every enumerating plane is absent (§4.1 `absent_input`). This is
        # the state that used to be `result: []`, exit 0, indistinguishable from a bundle whose
        # planes are all there and all empty.
        return (
            _envelope(
                "absent_input",
                "every plane that enumerates members is absent from this bundle "
                f"({[rel for rel, _g, _r in _SPINE_PLANES]}), so the index declares 0 members "
                "rather than measuring 0",
                result=objects, counts=counts, inputs=inputs, aux=aux, root=root,
            ),
            0,
        )

    return (
        _envelope("derived", None, result=objects, counts=counts, inputs=inputs, aux=aux,
                  root=root),
        0,
    )


def _emit(payload: dict, out: str | None) -> None:
    """stdout ALWAYS carries the envelope; `--out` is an ADDITIONAL copy (§2.2).

    All three seams promised `--out PATH` wrote the caller's file, and with it set nothing at all
    went to stdout — so a successful `--out` run and a silent failure were the same thing over the
    host's `if out:` test. The trap was latent because 0 of 3 seam call sites passed the flag, and
    it armed the moment the call path was unified.
    """
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if out:
        outp = Path(out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(text + "\n", encoding="utf-8")
    sys.stdout.write(text + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Derive a bundle's object index (read-only) as one mac.seam/1 envelope."
    )
    ap.add_argument("root", help="the bundle root (the directory holding mac.project.yaml)")
    ap.add_argument("--out", metavar="PATH", help="ALSO write the envelope here (never in the bundle)")
    try:
        a = ap.parse_args()
    except SystemExit as e:
        # argparse's own refusal is exit 2 with prose on stderr and ZERO bytes on stdout — exactly
        # the shape §4.3 names. `--help` (code 0) is not a caller error and is left alone.
        if e.code == 0:
            raise
        _emit(
            _envelope(
                "bad_request",
                "the arguments could not be parsed; this seam takes a bundle root and an "
                "optional --out PATH",
            ),
            None,
        )
        return 2

    root = Path(a.root).expanduser().resolve()
    if not root.is_dir():
        _emit(
            _envelope(
                "bad_request",
                f"the bundle root is not a directory: {root.name!r} — a seam is handed the BUNDLE "
                f"ROOT, never the data directory and never a file",
                root=root,
            ),
            None,
        )
        return 2

    if a.out:
        # §2.2: `--out` writes the CALLER's file and never one inside the bundle. All three seams
        # promised this in prose and 0 of 3 validated the path.
        try:
            outp = Path(a.out).expanduser().resolve()
            inside = outp == root or root in outp.parents
        except OSError:
            inside = False
        if inside:
            _emit(
                _envelope(
                    "bad_request",
                    "--out names a path inside the bundle; a seam writes nothing into the bundle "
                    "it reads, and the caller's own file is the only file it may write",
                    root=root,
                ),
                None,
            )
            return 2

    payload, code = derive(root)
    _emit(payload, a.out)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
