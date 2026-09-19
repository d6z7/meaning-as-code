#!/usr/bin/env python3
"""project_edges.py — DERIVE a bundle's edge index, on stdout, writing NOTHING. `mac.seam/1`.

WHY THIS FILE EXISTS

An operator asked, of the console's Edges page: "why is item edges showing only 6 edges". The page
was reading `<bundle>/ontology/edges.json`, and that file is a BUILD ARTIFACT — written only inside
`build_objects`' `if out_dir:` branch, i.e. only by a real projection run. So between two
projections the page is exactly as old as the last one and says nothing about it. Measured on one
bundle the day the question was asked: `ontology/edges.yaml` declared 17 edges (6 physical, 11
business) and had been edited at 23:11; the artifact held 6 (all physical, 0 proved) and had been
written at 21:43; the measurement record was newer than the artifact too, at 23:04. So the page
understated the edge set by 11 and the proofs by 16, and "6 edges, 0 of 6 proved" was a true
statement about a stale file and a false statement about the ontology.

WHY IT CALLS `edge_index` AND NOT `build_objects`

The objects precedent can call `build_objects(..., out_dir=None)` because the OBJECT index IS that
function's return value. The EDGE index is not: it is computed inside the write branch and goes
straight to disk, never into the returned `result`. So `build_objects(out_dir=None)` answers nothing
about edges. The edge index's one author is `sdk.project.objects._edge_index`, and
`sdk.project.objects.edge_index` is the public door onto it that this file was declared for. Both
of its inputs are local file reads, and the write that used to be the only way to see its output
belongs to its CALLER, not to it. Re-implementing an edge index in the reader would create a second
author for one artifact, which is the defect class this estate spends its time removing.

It cannot be called in-process by the console. The rule is in `boundaries.yaml` AT THE HOST
REPOSITORY ROOT — not under the console package — and the tree it constrains is named `wiki`
(`role: gui`), not `console`: `may_import: [wiki]`, `may_not_import: [sdk]`,
`may_sys_path_mutate: false`. (Cited by its real name deliberately. All three seams used to cite
this correct rule under a name the file does not use, which makes the clause unlookupable.) So the
transport is fixed by the boundary and not chosen: this file is a SUBPROCESS seam — argv in, one
JSON object on stdout, an exit code, prose on stderr.

WHAT IT GUARANTEES — and each of these is now a clause of SEAM_CONTRACT.md, not a habit

  * ONE ENVELOPE, ONE SHAPE, EVERY EXIT. 13 keys, present at the empty value of their own type on
    all four exits this seam can take. What went wrong without it: across the three seams written
    before the contract, one dropped 3 of its 6 top-level keys the moment its author raised, so a
    client reading one of those keys was reading a key that exists only when nothing went wrong.
  * THE STATUS IS A CLOSED TOKEN and the sentence beside it is open. `reason` is PRESENT always and
    null exactly when the status is `derived`, so "key absent" and "reason: null" are not the same
    byte on the wire.
  * INDEX MODE, AND IT IS THE PAYLOAD'S SHAPE, NOT A PREFERENCE. `result` is a list of
    independently derived members for which this seam can publish `returned of declared`, so
    SEAM_CONTRACT.md §5 makes it index mode, and index mode may serve an incomplete answer.
    THE SPINE IS `ontology/edges.yaml`: it ENUMERATES the members, so a failure of it refuses
    (`unparsed_input`, exit 3) — "0 rows" and "the list could not be read" have the same shape on
    a screen, and a degraded answer over an unreadable spine is a lie with a denominator of zero.
    THE MEASUREMENT RECORD IS AN ATTRIBUTE: membership survives it, only the per-member proof is
    unknown, so its absence or its corruption DEGRADES and `partial[]` names it. One seam, both
    sides of the rule, which is the evidence the rule is real rather than imposed.
  * EVERY INPUT IS DECLARED, with its role, so the host's cache knows what to watch. Including the
    framework-side read: the host's fingerprint stats the BUNDLE tree only, so an undeclared
    framework input is a key that never moves when the rules change.
  * DEGRADATION IS SIGNALLED. `_edge_index` reads `evidence/edge_measurements.json` under
    `except Exception: meas = {}` (sdk/project/objects.py:233-234) and a swallowed read there
    costs every proof in the answer while returning a structure identical to a clean run. This
    seam reads THE SAME FILE itself, before calling the author, and publishes its state as a
    declared input and — when it failed — as the one `partial[]` entry. That is the repair at the
    seam boundary: the swallow is left in place because `_edge_index`'s other caller
    (`build_objects`) is out of this change's scope, and a broad exception-handling refactor is a
    different act with a different risk. What is NOT left in place is the silence.
  * NOTHING IS WRITTEN. `edge_index` takes no out_dir and has none to take: its whole body is two
    reads, a per-edge dict build, a sort and a return. `--out` writes the CALLER's file, is
    REFUSED if it resolves inside the bundle, and stdout still carries the envelope either way —
    without that last clause a successful `--out` run is indistinguishable from a failure over a
    caller's `if out:` test.
  * THE ARGUMENTS ARE SUPPLIED, and by name. `root` is the BUNDLE ROOT, not the data dir — the
    author resolves `<root>/evidence/edge_measurements.json` off it, so passing `<root>/data` would
    silently report every edge unproved.
  * IT COSTS NOTHING. Two local file reads under the bundle and one `VERSION` read on the framework
    side. No connector, no warehouse, no model, no network. Measured at 0.126 s on a 71 KB
    edges.yaml with a 10 KB measurement record, against the console's own 30 s derivation wall.

KNOWN AND NOT DECIDED HERE

  * SEAM_CONTRACT.md §10.6 — `counts.declared` is only a fact if the spine parses STRICTLY, and
    `load_ont_edges` returns `[]` with no error for a document that parses as YAML but carries no
    `edges:` key. So a malformed-but-loadable spine publishes `0 of 0` under a clean status. §10
    lists this as awaiting an operator ruling and the fix belongs in the one author, not in a
    second copy of the parse here, so it is NAMED rather than silently patched.
  * On a refusing status the gate still requires `counts` to be two ints, while §3 only requires a
    denominator "under a serve-eligible status". `{returned: 0, declared: 0}` is therefore printed
    on `unparsed_input` and `bad_request`, where it is NOT a measurement — read `status`, which is
    not serve-eligible there, and the host will not put those counts on a page.

Usage:
  python3 tools/project_edges.py <bundle-root> [--out PATH]      (interpreter floor: 3.9)

  (default)      print the envelope as JSON on stdout
  --out PATH     ALSO write it to PATH (never inside the bundle; stdout is written regardless)

  exit 0  the status is serve-eligible for index mode: derived · degraded · absent_input
  exit 2  bad_request — a caller error before any derivation, envelope still on stdout
  exit 3  every other seam-minted token: unparsed_input · author_failed
  exit 1  RESERVED, never produced deliberately; a host reads it as `seam_failed`

A bundle root laid out as this tool reads it:

  <root>/ontology/edges.yaml               the edge set (the SPINE)      alpha__joins__beta, ...
  <root>/evidence/edge_measurements.json   what has counted each claim, if anything has (ATTRIBUTE)
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
    # `sdk.*` resolves from the framework root; tools/ is on the path for the same reason
    # project_objects.py puts it there — helpers in here are imported by BARE NAME. Legal only
    # because this file is on the FRAMEWORK side of the boundary: the host may not do this.
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sdk.project.objects import edge_index, load_ont_edges  # noqa: E402

ENVELOPE = "mac.seam/1"
MODE = "index"

#: The inputs, named ONCE, so `inputs[]` and the reads cannot drift apart. `role` is the contract's
#: closed four: the plane that ENUMERATES members is `spine`, a plane that decorates members
#: already enumerated is `attribute`, and anything read from the framework tree that is not this
#: seam's own code is `framework:<name>`.
_EDGES_YAML = "ontology/edges.yaml"
_MEASUREMENTS = "evidence/edge_measurements.json"
_VERSION = "VERSION"


def _iso_now() -> str:
    # `_dt.timezone.utc`, not the precedent's `_dt.UTC` alias: that alias is 3.11+, and this tool is
    # run by TWO interpreters — the console's venv (3.12) via `sys.executable`, and a bare `python3`
    # from the usage line above, which on a stock macOS is 3.9. Measured: the alias raises
    # AttributeError there, i.e. the seam would answer nothing on the very interpreter its own
    # docstring tells an operator to use.
    return (
        _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


# ── the seam's own identity ──────────────────────────────────────────────────────────────────────
_IDENTITY = None


def _identity() -> tuple:
    """(`seam` stamp, the framework input record). Computed once; VERSION is read once per process.

    WHY `framework_root` IS NOT A PATH. The host's locator prefers an installed framework root and
    silently falls back to a sibling checkout, so WHICH tree answered is an unstated variable and
    the cache key is unclosable without it. It has to be on the wire — and an absolute path may not
    be (§3: `local` is the only place one may appear). So the tree is identified by its directory
    name plus a digest of its resolved path: two checkouts are distinguishable, and neither
    publishes the operator's disk.

    `code_id` digests this file plus every `role: framework` input, which is the cross-check
    against the host's own framework fingerprint. Imported modules are covered by the same file's
    identity through the framework version, not listed one by one — §6.1 says so explicitly.
    """
    global _IDENTITY
    if _IDENTITY is not None:
        return _IDENTITY
    vp = ROOT / _VERSION
    try:
        raw = vp.read_bytes()
        version = raw.decode("utf-8", "replace").strip() or None
    except OSError:
        raw, version = None, None
    h = hashlib.sha256()
    try:
        h.update(Path(__file__).resolve().read_bytes())
    except OSError:  # pragma: no cover — the seam cannot read itself
        h.update(b"<seam source unreadable>")
    h.update(raw if raw is not None else b"<no VERSION>")
    stamp = {
        "tool": Path(__file__).name,
        "version": version or "unknown",
        "framework_root": (
            f"{ROOT.name}@{hashlib.sha256(str(ROOT).encode('utf-8')).hexdigest()[:12]}"
        ),
        "code_id": "sha256:" + h.hexdigest()[:16],
    }
    finput = {
        "path": "framework:" + _VERSION,
        "role": "framework",
        "present": raw is not None,
        "parsed": version is not None,
        "count": None,
    }
    _IDENTITY = (stamp, finput)
    return _IDENTITY


# ── the two bundle-side inputs, as STATES ────────────────────────────────────────────────────────
def _measurement_record(root: Path) -> dict:
    """What has counted anything in this bundle, as a state rather than an absence.

    `_edge_index` stamps `proof.state: "unproved"` on every edge when this record is missing, which
    is honest per edge and mute in aggregate: "0 of 17 proved" reads as a measured failure when the
    truth may be that nothing has measured anything yet. And when the record is PRESENT but broken,
    `_edge_index` swallows the failure (`except Exception: meas = {}`) and produces exactly the
    same structure as the absent case — so this read, here, is the only thing that can tell a
    reader which of the three happened.

    THE SHAPE IS CHECKED, NOT ASSUMED. `(doc or {}).get("results")` used to sit outside this
    function's own `try`, so a record that is a JSON LIST raised AttributeError and the seam exited
    1 with 0 bytes on stdout — the one failure no seam names.
    """
    p = root / _MEASUREMENTS
    if not p.exists():
        return {
            "present": False, "parsed": None, "count": None,
            "reason": (
                f"no {_MEASUREMENTS} in this bundle, so nothing has measured any edge claim "
                f"yet — every edge reads unproved because none has been counted, not because one "
                f"failed"
            ),
        }
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 — a state to report, not to raise
        return {
            "present": True, "parsed": False, "count": None,
            "reason": f"the measurement record could not be parsed: {type(e).__name__}: {e}",
        }
    if not isinstance(doc, dict):
        return {
            "present": True, "parsed": False, "count": None,
            "reason": (
                f"the measurement record is a JSON {type(doc).__name__}, not an object carrying "
                f"`results` — every edge reads unproved and the file is the reason"
            ),
        }
    results = doc.get("results")
    if results is None:
        results = []
    if not isinstance(results, list):
        return {
            "present": True, "parsed": False, "count": None,
            "reason": (
                f"the measurement record's `results` is a {type(results).__name__}, not a list "
                f"— nothing in it can be matched to an edge"
            ),
        }
    return {"present": True, "parsed": True, "count": len(results), "reason": None}


def _envelope(status, reason, result, counts, inputs, partial, aux, root,
              traceback_text=None) -> dict:
    """THE 13 KEYS, ALL OF THEM, ALWAYS — at the empty value of their own type where there is
    nothing to put in them. The keys that may legitimately vary live in `aux`, whose contract is
    that nothing in it may be relied on, and the one absolute path this process knows lives in
    `local`, which the host MUST drop before the wire."""
    return {
        "envelope": ENVELOPE,
        "mode": MODE,
        "status": status,
        "reason": reason,
        "result": result,
        "counts": counts,
        "inputs": inputs,
        "partial": partial,
        "seam": _identity()[0],
        "subject": None,
        "derived_at": _iso_now(),
        "aux": aux,
        "local": {
            "root": str(root) if root is not None else None,
            "argv": list(sys.argv[1:]),
            "traceback": traceback_text,
        },
    }


def _aux(total=0, measured=0, unproved=0) -> dict:
    """The proof-state aggregates, which have no reserved home. `total` duplicates
    `counts.declared` deliberately and only for the duration of the migration: the console's Edges
    page reads it today, and the reserved home for the denominator is `counts`."""
    return {"total": total, "measured": measured, "unproved": unproved}


def _bad_request(reason: str, root) -> dict:
    """A caller error BEFORE any derivation. `inputs[]` names only the framework material this seam
    read in order to stamp itself, because no bundle plane was ever addressed — an input list
    asserting `present: false` about files under a root that is not a directory would be a
    measurement nobody took."""
    return _envelope(
        status="bad_request", reason=reason, result=[],
        counts={"returned": 0, "declared": 0},
        inputs=[_identity()[1]], partial=[], aux=_aux(), root=root,
    )


def derive(root: Path) -> tuple:
    """The whole derivation. Returns (envelope, exit_code).

    The order of the branches IS the partial-result rule: the spine's states are answered before
    the author is called at all, because a spine that cannot be read makes the author's answer
    unknowable rather than empty.
    """
    concepts_dir = root / "ontology" / "concepts"
    spine_present = (root / _EDGES_YAML).exists()
    # Read once here for the STATE of the file (is it there, does it parse, how many does it
    # declare); `edge_index` reads it again for its content. Two reads of a 71 KB file cost nothing
    # measurable, and the alternative is either a second author for the resolution or an index that
    # cannot say why it is empty.
    ont_edges, parse_error = load_ont_edges(concepts_dir)
    rec = _measurement_record(root)
    finput = _identity()[1]

    def inputs(spine_parsed, spine_count):
        return [
            {"path": _EDGES_YAML, "role": "spine", "present": spine_present,
             "parsed": spine_parsed, "count": spine_count},
            {"path": _MEASUREMENTS, "role": "attribute", "present": rec["present"],
             "parsed": rec["parsed"], "count": rec["count"]},
            finput,
        ]

    if not spine_present:
        return _envelope(
            status="absent_input",
            reason=(
                f"no {_EDGES_YAML} in this bundle, so no relationship has been authored yet: "
                f"`0 of 0` is a measurement of an un-authored plane, not of an empty one"
                + ("" if rec["present"] else f" (and {_MEASUREMENTS} is not here either)")
            ),
            result=[], counts={"returned": 0, "declared": 0},
            inputs=inputs(None, None), partial=[], aux=_aux(), root=root,
        ), 0

    if parse_error:
        # THE SPINE REFUSES. The author cannot tell an unreadable edge file from one declaring no
        # relationships — it is handed a list either way — so the check belongs here, where the
        # file's state is known, and the answer is a refusal rather than a zero.
        return _envelope(
            status="unparsed_input",
            reason=(
                f"{_EDGES_YAML} exists and will not parse ({parse_error}), so the edge set is "
                f"UNKNOWN rather than empty: this file ENUMERATES the members, and a degraded "
                f"answer over it would be a lie with a denominator of zero. The `0 of 0` below is "
                f"not a measurement — the status is not serve-eligible"
            ),
            result=[], counts={"returned": 0, "declared": 0},
            inputs=inputs(False, None), partial=[], aux=_aux(), root=root,
        ), 3

    try:
        # THE ONE AUTHOR, AND THE ONLY CALL. It has no write branch to skip: there is no out_dir
        # in its signature, so this derivation cannot touch the bundle it reads.
        index = edge_index(root, concepts_dir)
    except Exception as e:  # noqa: BLE001
        return _envelope(
            status="author_failed",
            reason=f"the edge index's one author raised: {type(e).__name__}: {e}",
            result=[], counts={"returned": 0, "declared": len(ont_edges)},
            inputs=inputs(True, len(ont_edges)), partial=[], aux=_aux(), root=root,
            traceback_text=traceback.format_exc(limit=6),
        ), 3

    result = index.get("edges") or []
    partial = []
    if not rec["present"] or not rec["parsed"]:
        # DEGRADED, AND NAMED. Membership is intact; only a per-member attribute is unknown. The
        # host's old predicate inferred degradation from an empty result, and every path that
        # emptied the result also failed, so the branch was unreachable and this state had never
        # once shipped.
        partial.append({
            "input": _MEASUREMENTS,
            "role": "attribute",
            "effect": (
                "every edge is served with proof.state 'unproved' — an absence of counting, not a "
                "count that failed; the edge set itself is complete"
            ),
            "reason": rec["reason"],
        })
    status = "degraded" if partial else "derived"
    return _envelope(
        status=status,
        reason=(
            None if status == "derived" else
            "the edge set is complete and its proof state is not; partial[] names the record that "
            "could not be read"
        ),
        result=result,
        # `returned of declared`: `returned` is what the author produced, `declared` is what the
        # spine read above says the file holds. They are derived from two separate reads on
        # purpose — if they ever disagree, the pair says so on the wire rather than agreeing by
        # construction.
        counts={"returned": len(result), "declared": len(ont_edges)},
        inputs=inputs(True, len(ont_edges)), partial=partial,
        aux=_aux(index.get("total") or 0, index.get("measured") or 0, index.get("unproved") or 0),
        root=root,
    ), 0


def _print(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


class _Parser(argparse.ArgumentParser):
    """An argv failure SPEAKS. argparse's own `error` prints prose to stderr and exits 2 with 0
    bytes on stdout, which is exactly the state §4.3 names: a caller error is when a caller most
    needs the structured reason, and a host's `if out:` test cannot tell a silent success from a
    silent failure."""

    def error(self, message):
        _print(_bad_request(f"the arguments could not be read: {message}", None))
        raise SystemExit(2)


def main() -> int:
    ap = _Parser(description="Derive a bundle's edge index (read-only) and print it as JSON.")
    ap.add_argument("root", help="the bundle root (the directory holding mac.project.yaml)")
    ap.add_argument("--out", metavar="PATH", help="ALSO write the JSON here (never in the bundle)")
    a = ap.parse_args()
    root = Path(a.root).expanduser().resolve()
    if not root.is_dir():
        _print(_bad_request(
            "the bundle root is not a directory. This seam is handed the BUNDLE ROOT — the "
            "directory holding mac.project.yaml — never <root>/data: the author resolves the "
            "measurement record off the root, so the data dir would report every edge unproved "
            "and refuse nothing", root))
        return 2
    outp = None
    if a.out:
        outp = Path(a.out).expanduser().resolve()
        inside = True
        try:
            outp.relative_to(root)
        except ValueError:
            inside = False
        if inside:
            _print(_bad_request(
                "--out writes the CALLER's file and never one inside the bundle; the path given "
                "resolves under the bundle root. A seam writes nothing here: the bundle is "
                "immutable to it and frequently mid-ingestion", root))
            return 2
    payload, code = derive(root)
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if outp is not None:
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(text + "\n", encoding="utf-8")
    # STDOUT CARRIES THE ENVELOPE EITHER WAY (§2.2). With `--out` suppressing stdout, a successful
    # run and a failed one were the same 0 bytes to a caller branching on `if out:`.
    sys.stdout.write(text + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
