#!/usr/bin/env python3
"""project_concept_page.py — DERIVE one concept's read-view PAGE, on stdout, writing NOTHING.

A SEAM under `mac.seam/1`. The envelope, the closed status vocabulary, the exit-code law, the
input declaration and the degrade/refuse rule are SEAM_CONTRACT.md's, not this file's; the copy
that refuses is `tools/check_seam_contract.py`, which registers this tool as seam `concept-page`.

WHY THIS FILE EXISTS

The console's concept Page tab read `<bundle>/ontology/concepts/<stem>.md` through the bundle file
reader. That file is a BUILD ARTIFACT: it is written only by a projection run
(`sdk/project/mac_okf.py build`), so the page is exactly as old as the last run and says nothing
about it — and when the pages were taken OUT of a bundle, the tab went blank. The operator's
reply, verbatim: "ok ... i thought its being rendered on the fly". That is the requirement this
file exists to meet, and it is the FOURTH surface of one defect: the object index
(tools/project_objects.py), the edge index (tools/project_edges.py), and now the page.

ONE AUTHOR, AND THIS FILE IS NOT IT

The page's author is `sdk.project.mac_okf.concept_page` — the OKF head over the page's own
content, which lives in `sdk.project.concept_page_content` and is where `page_inputs` (the
whole-bundle context) now is too. They are the same two calls `mac_okf.build` makes for every
page it writes. Nothing here renders a heading, a field row, a relationship or a sentence. A page
re-implemented in the reader would be a SECOND AUTHOR for one artifact, which is how a graph and a
list came to disagree about one bundle, and it is the defect class this estate spends its time
removing. The arguments are not plumbing either: `rel_joins` IS the Relationships panel and
`col_desc` IS the Fields table, so they are taken from the builder's own `page_inputs` rather than
assembled a second time here.

WHY A SUBPROCESS, CITED CORRECTLY

`boundaries.yaml` lives at the HOST REPOSITORY ROOT — not under the console package — and the tree
the console lives in is named **`wiki`** (`role: gui`), not `console`. That tree is declared
`may_import: [wiki]`, `may_not_import: [sdk]`, `may_sys_path_mutate: false`: the in-process call is
forbidden and so is the workaround. (Every earlier revision of this docstring cited the right rule
under the name `console`, which the boundary file does not use, so the clause could not be looked
up. SEAM_CONTRACT.md §2.1 and §9 carry the same correction.) So this file is the seam — a thin
framework-side entry point that SUPPLIES the arguments, calls the one author, and prints what it
returned. Its own `sys.path` setup below is legal only because it runs on the framework side of
that line (§2.2 clause 2).

DOCUMENT MODE, AND THEREFORE REFUSAL — SEAM_CONTRACT.md §5

  `result` is ONE composed page, not a list of independently derived members, so there is no
  `returned of declared` to publish over it and this seam is `mode: "document"`. The rule then
  decides the whole of its failure behaviour, and nothing here is a preference: a document may be
  served only under `status: "derived"`. Half a page is a different page, not a partial one, so
  `partial` is `[]` on every exit and any declared input that will not parse REFUSES.

  That is a real behaviour change and it is the point of the exercise. Measured before it: the
  Fields table's descriptions and types come from `data/datasets/*.yaml` and `data/sources/*.yaml`
  through `_column_descriptions`, which SWALLOWED a failed parse — so corrupting any one of those
  files left this seam's answer byte-identical to a clean run (8 of 17 traced inputs, measured by
  the gate's corruption probe) and the page rendered as a complete derivation with a section of it
  silently short. The read site now reports what it could not read (`page_inputs` publishes
  `col_desc_unparsed`) and this seam refuses on it: `unparsed_input`, exit 3, empty `result`.

WHAT IT GUARANTEES

  * NOTHING IS WRITTEN. `build` is never called: it is the writing shell (it mkdirs the output,
    deletes the derived `rules/` subtree, unlinks orphan pages and writes every page and the
    index). This file calls only the two pure functions under it, and `--out` writes the CALLER's
    own file, never inside the bundle — refused with `bad_request` if the path resolves under the
    bundle root, and stdout carries the envelope either way (§2.2).
  * EVERY INPUT IS DECLARED, so the host's cache can watch them (§6.1). Four bundle planes and two
    framework-side data files, with a role each — and the gate does not take the list on trust: it
    traces the real opens with an audit hook and compares.
  * A FAILURE IS NAMED, NEVER SILENT, from the closed seam-minted vocabulary of §4.1 — and the
    envelope is printed on EVERY exit this seam is allowed to take, including the caller error.
  * IT COSTS NOTHING. Local YAML reads under the bundle plus the framework's own schema and
    VERSION. No connector, no warehouse, no model, no network.

THE STATUSES THIS SEAM CAN MINT, and what each means here (§4.1, §4.3)

  derived         0   the page is complete
  absent_input    3   there is no `ontology/concepts` directory: the plane that enumerates the
                      concepts is not there, so no page is knowable
  unparsed_input  3   a declared input exists and will not parse — this concept's YAML, a
                      SIBLING's (the builder loads the whole set to cross-link it), `edges.yaml`
                      (the Relationships panel's only input), or a data-plane descriptor (the
                      Fields table's descriptions and types)
  not_found       3   `--concept` names no member of the enumeration: the directory declares no
                      concept at all, no concept carries that stem, or the stem's YAML parses and
                      declares no `concept:` key — one token, three reasons (§4.2)
  author_failed   3   the one author raised; the traceback goes in `local`, never on the wire
  bad_request     2   a caller error before any derivation, and the envelope is still on stdout

  `degraded` is unreachable by construction: it is index mode only (§4.1).

NOT THIS SEAM'S TO FIX, recorded so it is not lost (§7.3.1): the host answers an unmatched GET with
200 and a self-naming body, and "no such route on this API" is manufactured client-side. Carrying
the host's own identity on a route that cannot be missing is the HOST's obligation — "this contract
states it; it does not build it" — and nothing framework-side can discharge it.

Usage:
  python3 tools/project_concept_page.py <bundle-root> --concept <stem> [--out PATH]

  (default)      print the `mac.seam/1` envelope as JSON on stdout
  --out PATH     ALSO write it to PATH (never inside the bundle); stdout still carries it

A bundle root laid out as this tool reads it:

  <root>/ontology/concepts/**.yaml    the concepts  (filed flat or by domain; both are read)
  <root>/ontology/edges.yaml          the relationships the page's panel names
  <root>/data/datasets/*.yaml         the Fields table's column descriptions and types
  <root>/data/sources/*.yaml          the same, for source-side relations
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
    # project_objects.py puts it there — helpers in here are imported by BARE NAME.
    if _p not in sys.path:
        sys.path.insert(0, _p)

import yaml  # noqa: E402

from sdk.grammar.resolve import schema_path  # noqa: E402
from sdk.project.concept_page_content import page_inputs  # noqa: E402
from sdk.project.mac_okf import concept_page, load_concepts  # noqa: E402

#: SEAM_CONTRACT.md §3 — the version of the contract this envelope is written against.
ENVELOPE = "mac.seam/1"
#: §5 — constant per seam, declared here and re-derived from the bytes by the gate.
MODE = "document"
SUBJECT_KIND = "concept"
TOOL = "project_concept_page.py"

#: §4.3 — the exit-code law. Every other seam-minted token is 3.
_EXIT = {"derived": 0, "bad_request": 2}

# The paths the author reads, relative to the bundle root. Named once, so `inputs[]` and the
# derivation cannot drift apart from what is actually opened.
_CONCEPTS_DIR = "ontology/concepts"
_EDGES_YAML = "ontology/edges.yaml"
_DATASETS_DIR = "data/datasets"
_SOURCES_DIR = "data/sources"


def _iso_now() -> str:
    # `_dt.timezone.utc`, not the `_dt.UTC` alias: that alias is 3.11+, and this tool is run by TWO
    # interpreters — the console's venv via `sys.executable`, and a bare `python3` from the usage
    # line above, which on a stock macOS is 3.9. The declared floor is a clause (§4.4), and the
    # gate runs this seam there as well as on `sys.executable`.
    return (
        _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


# ── THE FRAMEWORK-SIDE INPUTS, AND THE STAMP OVER THEM ───────────────────────────────────────────
# §6.1: a file read from the framework tree that is not this seam's own code is a DECLARED input
# with `role: "framework"`, because the host's fingerprint stats the BUNDLE only — edit the grammar
# and every answer changes while no cache key moves. Measured by the gate's audit trace before this
# was written: 1 of 1 framework-side data read (`mac.schema.json`, opened at import by
# `sdk.project.mac_okf`) was declared by nothing. `VERSION` is the second, and it is read HERE —
# `seam.version` has to come from somewhere, and an undeclared read for the stamp would reopen the
# same hole the stamp exists to close.
def _framework_files() -> list:
    """[(declared name, absolute path)] for every framework-side DATA file this seam reads."""
    files = [("VERSION", ROOT / "VERSION")]
    try:
        sp = schema_path().resolve()
    except Exception:  # noqa: BLE001 — resolution is fatal to the import above, never to this
        sp = (ROOT / "mac.schema.json").resolve()
    try:
        name = sp.relative_to(ROOT).as_posix()
    except ValueError:
        # An INSTALLED grammar, outside this tree. Its name still identifies it, and `code_id`
        # digests its bytes, which is the half that matters for staleness.
        name = sp.name
    return sorted(files + [(name, sp)], key=lambda x: x[0])


_FRAMEWORK_FILES = _framework_files()


def _seam_stamp() -> dict:
    """§3 `seam` — WHICH code answered. `code_id` digests this file plus every framework input.

    `framework_root` is a DIGEST of the framework root's absolute path, not the path: §3 makes
    `local` the only place an absolute filesystem path may appear, and the host drops `local` before
    the wire. The digest still does the job the field exists for — the host's locator prefers an
    installed framework root and silently falls back to a sibling checkout, so two trees answering
    the same question are two different tokens here instead of one unstated variable. The path
    itself is in `local.framework_root`, for a human reading a local run.
    """
    h = hashlib.sha256()
    h.update(Path(__file__).resolve().read_bytes())
    version = "unknown"
    for name, p in _FRAMEWORK_FILES:
        try:
            raw = p.read_bytes()
        except OSError:
            raw = b""
        h.update(name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        if name == "VERSION" and raw.strip():
            version = raw.decode("utf-8", "replace").strip()
    return {
        "tool": TOOL,
        "version": version,
        "framework_root": hashlib.sha256(str(ROOT).encode("utf-8")).hexdigest()[:12],
        "code_id": h.hexdigest()[:16],
    }


def _input(path: str, role: str, present: bool, parsed, count) -> dict:
    """One `inputs[]` record (§3, §6.1).

    `parsed` is TRISTATE and the third value is not a shrug: `null` means this run did not parse it
    — either it is not there, or the derivation refused before reaching it. `present` tells those
    two apart. A boolean here would make "not read" indistinguishable from "read and clean", which
    is the shape of the defect this contract exists to close.
    """
    return {"path": path, "role": role, "present": present, "parsed": parsed, "count": count}


def _framework_inputs() -> list:
    return [
        _input(f"framework:{name}", "framework", p.is_file(), True if p.is_file() else None, None)
        for name, p in _FRAMEWORK_FILES
    ]


def _yaml_files(d: Path) -> list:
    return sorted(d.glob("*.yaml")) if d.is_dir() else []


def _envelope(status: str, reason, *, result: str = "", subject=None, counts=None,
              inputs=None, aux=None, local=None) -> dict:
    """§3 — the reserved keys are INVARIANT: present on every exit, at their empty value.

    Thirteen keys, the same thirteen every time. `partial` is `[]` unconditionally because this is
    a document seam (§5.1), and `reason` is null exactly when the status is `derived` — the
    biconditional, so a consumer can never confuse "key absent" with "reason: null".
    """
    return {
        "envelope": ENVELOPE,
        "mode": MODE,
        "status": status,
        "reason": reason,
        "result": result,
        "counts": counts or {"returned": 0, "declared": 0},
        "inputs": list(inputs if inputs is not None else []),
        "partial": [],
        "seam": _seam_stamp(),
        "subject": subject,
        "derived_at": _iso_now(),
        "aux": aux or {},
        "local": local or {},
    }


def _scan(concepts_dir: Path):
    """Every concept YAML's PARSE STATE, before the builder is asked to load them.

    `load_concepts` calls `yaml.safe_load` unguarded, so ONE broken file raises and no page can be
    built — not even a page whose own file is perfectly good, because the builder loads the whole
    set to cross-link it. That is honest but mute: the caller would see an exception where the
    truth is "this named file, on this line". So the set is scanned first and the offenders are
    reported BY PATH.

    Returns (unparsed, declares, files) — `declares[stem]` is True when the file parses and carries
    a `concept:` key, False when it parses and does not. The second case is a real state: a file
    sitting in the concepts directory that the builder skips entirely.
    """
    unparsed: list = []
    declares: dict = {}
    files: list = sorted(concepts_dir.rglob("*.yaml"))
    for p in files:
        rel = p.relative_to(concepts_dir).as_posix()
        try:
            obj = yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001 — a state to report, not to raise
            unparsed.append({"path": f"{_CONCEPTS_DIR}/{rel}", "reason": f"{type(e).__name__}: {e}"})
            continue
        declares.setdefault(p.stem, isinstance(obj, dict) and "concept" in obj)
    return unparsed, declares, files


def _edges_state(root: Path) -> dict:
    """Whether `ontology/edges.yaml` can be read, as a state rather than an absence.

    `_edge_joins` reads it unguarded too, and it is the Relationships panel's only input. An
    ABSENT file is normal — the panel is simply empty, and that is a true statement about the
    bundle, so the page is still `derived`. An UNPARSEABLE one is not: the panel would be empty
    because the file could not be read, which is the lie §5.2 refuses. The same distinction the
    edge index already makes for its own spine, one plane over.
    """
    p = root / _EDGES_YAML
    if not p.exists():
        return {"present": False, "parse_error": None}
    try:
        yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"present": True, "parse_error": f"{type(e).__name__}: {e}"}
    return {"present": True, "parse_error": None}


def _inputs(root: Path, facts: dict) -> list:
    """§6.1 — every plane this seam opens, declared with its role, on EVERY exit.

    The roles are the closed four. `ontology/concepts` is the SPINE: it is the plane that
    enumerates the members `--concept` selects from. The other three DECORATE a member already
    enumerated — the Relationships panel and the Fields table — so they are `attribute`.

    Declared even on a path that refused before opening them, because the declaration is what the
    host's cache watches, not a log of this one run: a key that covered a different input set
    depending on which branch a request took would be the staleness hole with extra steps.
    """
    ds, sr = facts["datasets"], facts["sources"]
    edges = facts["edges"]
    return [
        _input(_CONCEPTS_DIR, "spine", facts["concepts_present"], facts["concepts_parsed"],
               facts["concepts_files"]),
        _input(_EDGES_YAML, "attribute", edges["present"],
               None if not edges["present"] else (edges["parse_error"] is None),
               1 if edges["present"] else 0),
        _input(_DATASETS_DIR, "attribute", (root / _DATASETS_DIR).is_dir(), ds["parsed"],
               ds["files"]),
        _input(_SOURCES_DIR, "attribute", (root / _SOURCES_DIR).is_dir(), sr["parsed"],
               sr["files"]),
    ] + _framework_inputs()


def derive(root: Path, concept: str, argv=None) -> tuple:
    """The whole derivation. Returns (envelope, exit_code). Raises nothing."""
    concepts_dir = root / _CONCEPTS_DIR
    subject = {"kind": SUBJECT_KIND, "id": concept}
    local = {"root": str(root), "argv": list(argv if argv is not None else sys.argv[1:]),
             "framework_root": str(ROOT)}
    facts = {
        "concepts_present": concepts_dir.is_dir(),
        "concepts_parsed": None,
        "concepts_files": 0,
        "edges": _edges_state(root),
        "datasets": {"parsed": None, "files": len(_yaml_files(root / _DATASETS_DIR))},
        "sources": {"parsed": None, "files": len(_yaml_files(root / _SOURCES_DIR))},
    }
    unparsed: list = []
    declared = 0
    descriptor_unparsed: list = []

    def out(status, reason, result="", returned=0, aux_extra=None):
        aux = {
            "concepts": {"declared": declared, "files": facts["concepts_files"],
                         "unparsed": unparsed},
            "edges": dict(facts["edges"]),
            "descriptors": {"datasets": facts["datasets"]["files"],
                            "sources": facts["sources"]["files"],
                            "unparsed": descriptor_unparsed},
        }
        aux.update(aux_extra or {})
        env = _envelope(status, reason, result=result, subject=subject,
                        counts={"returned": returned, "declared": declared},
                        inputs=_inputs(root, facts), aux=aux, local=local)
        return env, _EXIT.get(status, 3)

    if not facts["concepts_present"]:
        return out(
            "absent_input",
            f"this bundle has no {_CONCEPTS_DIR} directory, so it has no ontology plane to render "
            "a page from — the concepts have not been authored here yet",
        )

    unparsed, declares, files = _scan(concepts_dir)
    facts["concepts_files"] = len(files)
    facts["concepts_parsed"] = not unparsed
    declared = sum(1 for v in declares.values() if v)

    if unparsed:
        named = ", ".join(u["path"] for u in unparsed)
        # WHOSE FILE IS BROKEN MATTERS, and both answers block the page: the builder loads the
        # whole concept set to cross-link the pages, so a sibling's parse error stops this page too.
        own = any(u["path"].endswith(f"/{concept}.yaml") for u in unparsed)
        return out(
            "unparsed_input",
            (
                f"{concept}'s own YAML could not be parsed: "
                if own
                else "a concept YAML elsewhere in this bundle could not be parsed, and the page "
                "builder loads every concept to cross-link them, so no page can be derived until "
                "it is fixed: "
            )
            + named,
        )
    if facts["edges"]["parse_error"]:
        return out(
            "unparsed_input",
            f"{_EDGES_YAML} could not be parsed, and the page's Relationships panel is built from "
            f"it: {facts['edges']['parse_error']}",
        )
    if not declares:
        return out(
            "not_found",
            f"{_CONCEPTS_DIR} exists but holds no YAML at all, so this bundle declares no concept "
            "to render",
        )
    if concept not in declares:
        return out(
            "not_found",
            f"no concept named {concept!r} is declared in this bundle — {declared} concept(s) are",
        )
    if not declares[concept]:
        # PARSES, AND IS STILL NOT A CONCEPT. `load_concepts` keeps only documents carrying a
        # `concept:` key, so such a file is skipped in silence and the stem looks like a concept
        # that failed to render. §4.2: one token, a second reason.
        return out(
            "not_found",
            f"{_CONCEPTS_DIR}/{concept}.yaml parses but declares no `concept:` key, so the page "
            "builder does not treat it as a concept",
        )

    try:
        # THE ONE AUTHOR, AND THE ONLY TWO CALLS. Neither writes: `build` is the writing shell
        # around them, and it is deliberately not called here.
        concepts = load_concepts(concepts_dir)
        inputs = page_inputs(concepts_dir, concepts)
    except Exception as e:  # noqa: BLE001 — every failure is a state to report, not to raise
        local["traceback"] = traceback.format_exc(limit=6)
        return out("author_failed", f"the page context could not be built: {type(e).__name__}: {e}")

    # THE DATA PLANE WAS READ, AND WHAT COULD NOT BE READ IS NOW SAYABLE. `_column_descriptions`
    # used to swallow a failed parse with a bare `except`, so this was the silent quarter of the
    # Fields table; it now reports the files it dropped and this seam refuses on them (document
    # mode, §5). `col_desc_unparsed` is the read site's own fact — re-deriving it here would be the
    # second author this file exists to avoid.
    descriptor_unparsed = list(inputs.get("col_desc_unparsed") or [])
    ds_bad = [u for u in descriptor_unparsed if u["path"].startswith(_DATASETS_DIR + "/")]
    sr_bad = [u for u in descriptor_unparsed if u["path"].startswith(_SOURCES_DIR + "/")]
    facts["datasets"]["parsed"] = (not ds_bad) if facts["datasets"]["files"] else None
    facts["sources"]["parsed"] = (not sr_bad) if facts["sources"]["files"] else None
    if descriptor_unparsed:
        named = ", ".join(u["path"] for u in descriptor_unparsed)
        return out(
            "unparsed_input",
            "a data-plane descriptor could not be parsed, and the Fields table's descriptions and "
            "types are read from it — a page built over it would be short a section's content and "
            f"say nothing about it: {named}",
        )

    try:
        entry = next(e for e in concepts if e[0] == concept)
        name, path, obj, _raw = entry
        markdown = concept_page(name=name, path=path, obj=obj, inputs=inputs)
    except Exception as e:  # noqa: BLE001
        local["traceback"] = traceback.format_exc(limit=6)
        return out("author_failed", f"the page builder failed: {type(e).__name__}: {e}")
    return out("derived", None, result=markdown, returned=1)


class _ArgError(Exception):
    """argparse's own error path exits 2 with prose and NO envelope — §4.3 wants both."""


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _ArgError(message)


def _parser() -> argparse.ArgumentParser:
    ap = _Parser(description="Derive one concept's read-view page (read-only) and print it as "
                             "a mac.seam/1 envelope on stdout.")
    ap.add_argument("root", help="the bundle root (the directory holding mac.project.yaml)")
    ap.add_argument("--concept", required=True, metavar="STEM",
                    help="the concept's file stem, as the object index reports it")
    ap.add_argument("--out", metavar="PATH",
                    help="ALSO write the envelope here (never inside the bundle)")
    return ap


def _print(payload: dict, out_path=None) -> None:
    """§2.2 — stdout ALWAYS carries the envelope, `--out` or not.

    What went wrong without that clause: with `--out` set, nothing at all went to stdout, so a
    successful run and a failed one were indistinguishable over the host's `if out:` test.
    """
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    sys.stdout.write(text + "\n")


def main(argv=None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    local = {"root": None, "argv": raw, "framework_root": str(ROOT)}

    def refuse(reason, prose, subject=None) -> int:
        # stderr is prose for a human and never the answer (§2.2); the ANSWER is the envelope.
        print(f"ERROR: {prose}", file=sys.stderr)
        _print(_envelope("bad_request", reason, subject=subject, inputs=_framework_inputs(),
                         local=local))
        return 2

    try:
        a = _parser().parse_args(raw)
    except _ArgError as e:
        return refuse(f"the arguments could not be read: {e}", str(e))

    # A stem, never a path. The console passes an object id straight through, and a `..` or a
    # leading `/` in it must not be able to reach outside the concepts directory. This half of the
    # guard is the TRUST BOUNDARY (§2.2); the host's copy is a convenience.
    if "/" in a.concept or "\\" in a.concept or a.concept in ("", ".", ".."):
        return refuse(
            f"--concept takes a file stem, not a path: {a.concept!r}",
            f"--concept takes a file stem, not a path: {a.concept!r}",
        )
    subject = {"kind": SUBJECT_KIND, "id": a.concept}

    root = Path(a.root).expanduser().resolve()
    local["root"] = str(root)
    if not root.is_dir():
        return refuse(
            "the bundle root is not a directory — the path given is in `local.root`, which the "
            "host drops before the wire",
            f"not a directory: {root}",
            subject=subject,
        )

    out_path = None
    if a.out:
        out_path = Path(a.out).expanduser().resolve()
        try:
            out_path.relative_to(root)
        except ValueError:
            pass
        else:
            return refuse(
                "--out writes the CALLER's file and never one inside the bundle; the path given "
                "resolves under the bundle root",
                f"--out must not write inside the bundle: {out_path}",
                subject=subject,
            )

    payload, code = derive(root, a.concept, argv=raw)
    _print(payload, out_path)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
