#!/usr/bin/env python3
"""
test_concept_page_seam.py — the CONCEPT PAGE seam, pinned. `tools/project_concept_page.py` derives
one concept's read-view page live, so the console can render the Page tab from the ontology instead
of fetching `ontology/concepts/<stem>.md` — a BUILD ARTIFACT, exactly as old as the last projection
run, and blank once the pages leave the repo. Operator, verbatim: "ok ... i thought its being
rendered on the fly".

  P1 ONE AUTHOR                 — the seam's markdown is BYTE-IDENTICAL to what `mac_okf.build`
                                  writes for the same concept. This is the whole design claim: a
                                  page rendered a second time in the reader is how a list and a
                                  graph came to disagree about one bundle, and only byte equality
                                  can catch a second author that is merely SIMILAR
  P2 THE ARGUMENTS ARE SUPPLIED — the Fields table's descriptions and the Relationships panel come
                                  from the data plane and edges.yaml, which the builder resolves
                                  RELATIVE to the concepts directory. A seam that passed the bundle
                                  root instead would still emit a complete-LOOKING page with both
                                  sections silently empty, and P1 alone would not catch it if the
                                  comparison ran through the same wrong argument
  P3 LIVE                       — an edited concept YAML changes the page with NO projection run
                                  and no file written. The requirement, measured
  P4 NOTHING IS WRITTEN         — every file under the fixture bundle is stat-snapshotted, the
                                  derivation runs, and the snapshot must be identical with no new
                                  file of any kind. The purity the live route depends on
  P5 EVERY FAILURE IS NAMED     — a missing concept, an unparseable concept, an unparseable
                                  sibling, an unparseable edges.yaml, a YAML that is not a concept
                                  and a bundle with no ontology plane are SIX reported failures
                                  with six reasons — never a traceback, never an empty string, and
                                  never one another. Under `mac.seam/1` they are minted from the
                                  CLOSED vocabulary of §4.1, so two of the six now share a token
                                  and are told apart by the sentence, which is the contract's own
                                  rule (§4.2: a token exists only where a caller BRANCHES)
  P6 A STEM, NOT A PATH         — the console passes an object id straight through, so `../` in it
                                  is refused rather than resolved

And, since the seam was brought to SEAM_CONTRACT.md (`mac.seam/1`) — the clauses the gate
`tools/check_seam_contract.py` judges, pinned here too so a regression is caught by the test suite
and not only by the gate:

  P7 THE ENVELOPE IS INVARIANT  — 13 reserved keys, the SAME key set on exit 0, exit 2 and exit 3;
                                  a versioned envelope; `mode: document`; a status from the closed
                                  seam-minted seven; `reason` null exactly when `derived`;
                                  `partial` always `[]`; a complete `seam` stamp
  P8 EVERY INPUT IS DECLARED    — the four bundle planes and the two framework-side data files,
                                  with roles from the closed four and exactly one `spine`. The
                                  host's cache key stats the bundle only, so an undeclared
                                  framework read is a payload derived under rules that moved
  P9 A SWALLOWED READ IS A LIE  — corrupting a data-plane descriptor must CHANGE the answer.
                                  Measured before this: 8 of 17 traced inputs corrupted with the
                                  payload byte-identical to a clean run, because
                                  `_column_descriptions` swallowed the parse error with a bare
                                  `except`. The read site now reports what it dropped and the seam
                                  refuses on it — document mode may not serve an incomplete answer
  P10 NO PATH LEAVES `local`    — an absolute filesystem path appears in exactly one block, and
                                  the host drops that block before the wire
  P11 ARGV FAILURES SPEAK       — exit 2 carries the envelope on stdout, with `bad_request`.
                                  Measured before this: 3 of 3 seams printed 0 bytes there
  P12 `--out` STILL PRINTS      — and never writes inside the bundle

The fixture bundle is written by this file into a temp dir and is generic (alpha/beta over
rel_alpha/rel_beta). No project, customer, brand or source specifics.

Usage:  python3 tests/test_concept_page_seam.py   ·   Exit: 0 = all assertions passed · 1 = a failure
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
TOOLS = REPO / "tools"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(TOOLS))

from sdk.project.concept_page_content import page_inputs  # noqa: E402
from sdk.project.mac_okf import build, load_concepts  # noqa: E402

fails = 0

# ── the contract, restated only as the shapes this test reads ────────────────────────────────────
# SEAM_CONTRACT.md §3 / §4.1. Duplicated here deliberately and minimally: a test that imported the
# gate's constants would pass whenever the gate and the seam drifted TOGETHER.
ENVELOPE = "mac.seam/1"
RESERVED = ("aux", "counts", "derived_at", "envelope", "inputs", "local", "mode", "partial",
            "reason", "result", "seam", "status", "subject")
SEAM_MINTED = ("derived", "degraded", "absent_input", "unparsed_input", "not_found",
               "author_failed", "bad_request")
INPUT_ROLES = ("spine", "row", "attribute", "framework")
SEAM_STAMP = ("tool", "version", "framework_root", "code_id")
#: the gate's own absolute-path test, so this file refuses exactly what the gate refuses
_ABS = re.compile(r"^(?:/[^/\0]+){2,}/?$|^[A-Za-z]:[\\/]")
#: the gate's VOLATILE set — two runs over the same bytes differ only by the clock
_VOLATILE = ("derived_at", "at", "observed_at", "snapshot_at")


def ok(cond, msg):
    global fails
    print(("  ✓ " if cond else "  ✗ ") + msg)
    fails += 0 if cond else 1


def _strings(node, path="$"):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _strings(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _strings(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


def _without_clock(payload):
    def strip(node):
        if isinstance(node, dict):
            return {k: strip(v) for k, v in sorted(node.items()) if k not in _VOLATILE}
        if isinstance(node, list):
            return [strip(v) for v in node]
        return node
    return json.dumps(strip(payload), sort_keys=True, ensure_ascii=False)


def _declared(payload, path):
    for i in payload.get("inputs") or []:
        if i.get("path") == path:
            return i
    return None


# ── the fixture bundle ───────────────────────────────────────────────────────────────────────────
# TWO CONCEPTS AND ONE EDGE, because a one-concept fixture cannot catch the argument this seam is
# most likely to get wrong: the Relationships panel is projected from `ontology/edges.yaml`, which
# the builder resolves as `<concepts dir>/../edges.yaml`, and a page with no peer to join renders
# identically whether that file was found or not.

_MANIFEST = """\
spec_version: mac.container/1
metadata:
  project: alpha/beta
  label: Alpha Beta
  data_domain: alpha
  dataset: beta
planes:
  data: data
  ontology: ontology
"""

_EDGES = """\
edges:
  - edge_id: alpha__joins__beta
    level: physical
    type: foreign_key
    join_rule: "rel_alpha.beta_key = rel_beta.beta_key"
    endpoints:
      from: { concept: Alpha, cardinality: "0..N", role: joinsBeta }
      to: { concept: Beta, cardinality: "1" }
"""

# A DATASET DESCRIPTOR, so the Fields table has something to say. `_column_descriptions` reads the
# data plane at `<concepts dir>/../../data`, which is the second relative resolution a wrong `src`
# would break.
_DATASET = """\
table:
  name: rel_alpha
columns:
  - name: alpha_key
    type: varchar
    description: the identifying column, described in the data plane
  - name: beta_key
    type: varchar
    description: the column this concept joins its peer on
"""

#: what the gate writes over a traced input to see whether the answer moves
_CORRUPT = "{{{ this file was corrupted by the test -- not YAML, not JSON ]]]\n\t:- :\n"


def _concept(name: str, relation: str, definition: str) -> str:
    return (
        "spec_version: mac.concept/1\n"
        "concept:\n"
        f"  name: {name}\n"
        f"  label: {name.upper()}\n"
        "  class: entity\n"
        f"  definition: {definition}\n"
        "metadata:\n"
        "  confidence: I\n"
        "grounding:\n"
        "  sources:\n"
        f"    - relation: {relation}\n"
        f"      key: {relation.split('_')[-1]}_key\n"
        "      columns:\n"
        f"        - {relation.split('_')[-1]}_key\n"
        "        - beta_key\n"
        "  field_roles:\n"
        f"    {relation.split('_')[-1]}_key: identifier\n"
    )


def _bundle(root: Path, edges_text: str | None = _EDGES) -> Path:
    """A whole MAC container on disk: manifest, data plane, ontology plane, two concepts."""
    (root / "ontology" / "concepts" / "domain").mkdir(parents=True, exist_ok=True)
    (root / "data" / "datasets").mkdir(parents=True, exist_ok=True)
    (root / "mac.project.yaml").write_text(_MANIFEST, encoding="utf-8")
    (root / "data" / "datasets" / "rel_alpha.yaml").write_text(_DATASET, encoding="utf-8")
    (root / "ontology" / "concepts" / "alpha.yaml").write_text(
        _concept("Alpha", "rel_alpha", "The first concept, as authored."), encoding="utf-8"
    )
    # FILED BY DOMAIN, not flat — `load_concepts` is recursive and a seam that globbed one level
    # would answer "no such concept" for every bundle that files its ontology by subject area.
    (root / "ontology" / "concepts" / "domain" / "beta.yaml").write_text(
        _concept("Beta", "rel_beta", "The second concept, one directory down."), encoding="utf-8"
    )
    if edges_text is not None:
        (root / "ontology" / "edges.yaml").write_text(edges_text, encoding="utf-8")
    return root


def _run(*args) -> tuple[dict, int, str]:
    """Run the seam THE WAY THE CONSOLE RUNS IT — as a subprocess, reading stdout. An in-process
    call would not catch an import that only resolves because this test put the repo on sys.path."""
    r = subprocess.run(
        [sys.executable, str(TOOLS / "project_concept_page.py"), *[str(a) for a in args]],
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(r.stdout)
    except ValueError:
        payload = {}
    return payload, r.returncode, r.stderr


def _seam(root: Path, concept: str) -> tuple[dict, int, str]:
    return _run(root, "--concept", concept)


def _snapshot(root: Path) -> dict:
    return {
        str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime_ns)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = _bundle(Path(td) / "bundle")

        print("P1 ONE AUTHOR — the seam's page is byte-identical to the builder's")
        out = Path(td) / "built"
        build(root / "ontology" / "concepts", out)  # the writing path, into a throwaway directory
        for stem in ("alpha", "beta"):
            payload, code, err = _seam(root, stem)
            written = (out / f"{stem}.md").read_text(encoding="utf-8")
            ok(code == 0, f"the seam exits 0 for {stem} (got {code}; stderr: {err.strip()[:120]})")
            ok(
                payload.get("result") == written,
                f"{stem}: derived markdown == the page `build` writes, byte for byte",
            )
        ok(
            _seam(root, "alpha")[0].get("status") == "derived",
            "and the payload STAMPS itself derived, so the caller never has to guess",
        )

        print("P2 THE ARGUMENTS ARE SUPPLIED — both relative planes actually reached the page")
        page = _seam(root, "alpha")[0].get("result") or ""
        ok(
            "described in the data plane" in page,
            "the Fields table carries the data plane's column description (data/ was resolved)",
        )
        ok("## Relationships" in page, "the Relationships panel is present (edges.yaml was read)")
        ok("BETA" in page, "and it names the peer concept the edge joins to")

        print("P3 LIVE — an edited concept changes the page, with no projection and no file written")
        before_page = _seam(root, "alpha")[0].get("result") or ""
        cy = root / "ontology" / "concepts" / "alpha.yaml"
        cy.write_text(
            cy.read_text(encoding="utf-8").replace(
                "The first concept, as authored.", "The first concept, edited in place."
            ),
            encoding="utf-8",
        )
        md_before_derive = sorted(p.name for p in (root / "ontology" / "concepts").glob("*.md"))
        after_page = _seam(root, "alpha")[0].get("result") or ""
        ok(after_page != before_page, "the derived page CHANGED after the YAML was edited")
        ok("edited in place" in after_page, "and it carries the edited definition")
        ok(
            md_before_derive == sorted(p.name for p in (root / "ontology" / "concepts").glob("*.md"))
            == [],
            "with no .md in the bundle at any point — nothing was projected to produce it",
        )

        print("P4 NOTHING IS WRITTEN — the purity the live route depends on")
        before = _snapshot(root)
        _seam(root, "alpha")
        _seam(root, "beta")
        after = _snapshot(root)
        ok(before == after, f"all {len(before)} fixture files unchanged in size and mtime")
        ok(
            not list(root.rglob("*.md")),
            "and no page was produced on disk — the derivation answers a question, it does not build",
        )

        print("P5 EVERY FAILURE IS NAMED — six failures, six reasons, never a traceback")
        payload, code, err = _seam(root, "gamma")
        ok(payload.get("status") == "not_found",
           f"an unknown concept -> not_found ({payload.get('status')})")
        ok(code == 3, f"and exits 3 (got {code})")
        ok(payload.get("result") == "", "with an EMPTY page rather than a half-rendered one")
        ok("2 concept(s) are" in (payload.get("reason") or ""),
           "and the reason carries the denominator")
        ok("Traceback" not in err, "nothing was raised at the operator")

        broken = _bundle(Path(td) / "broken")
        (broken / "ontology" / "concepts" / "alpha.yaml").write_text(
            "concept:\n  name: Alpha\n   bad indent: [\n", encoding="utf-8"
        )
        payload, code, _ = _seam(broken, "alpha")
        ok(payload.get("status") == "unparsed_input",
           f"an unparseable concept -> unparsed_input ({payload.get('status')})")
        ok(
            any("alpha.yaml" in u["path"]
                for u in ((payload.get("aux") or {}).get("concepts") or {}).get("unparsed") or []),
            "and the offending file is named by path",
        )
        # THE SIBLING CASE, WHICH IS NOT THE SAME FINDING. `load_concepts` loads the whole set to
        # cross-link the pages, so one broken file stops a page whose own YAML is perfect — and the
        # reason has to say so, or the operator edits the wrong file.
        payload, code, _ = _seam(broken, "beta")
        ok(payload.get("status") == "unparsed_input", "a broken SIBLING also blocks beta's page")
        ok(
            "cross-link" in (payload.get("reason") or ""),
            "and the reason says WHY a sibling's parse error stops this page",
        )

        bad_edges = _bundle(Path(td) / "bad-edges", edges_text="edges:\n  - [unclosed\n")
        payload, code, _ = _seam(bad_edges, "alpha")
        ok(payload.get("status") == "unparsed_input",
           f"an unparseable edges.yaml -> unparsed_input ({payload.get('status')})")
        ok(_EDGES_IN := (_declared(payload, "ontology/edges.yaml") or {}),
           "and edges.yaml is a declared input on that exit")
        ok(_EDGES_IN.get("present") is True and _EDGES_IN.get("parsed") is False,
           "reported PRESENT and NOT PARSED — it exists, it is unreadable, and the two never render alike")

        not_concept = _bundle(Path(td) / "not-concept")
        (not_concept / "ontology" / "concepts" / "notes.yaml").write_text(
            "title: a note\nbody: this declares no concept key\n", encoding="utf-8"
        )
        payload, code, _ = _seam(not_concept, "notes")
        ok(payload.get("status") == "not_found",
           f"a YAML with no `concept:` -> not_found ({payload.get('status')})")
        ok(
            "no `concept:` key" in (payload.get("reason") or ""),
            "and the REASON distinguishes it from a stem that is not there at all — §4.2, one "
            "token where the caller does not branch, two sentences where the operator does",
        )

        empty = Path(td) / "empty"
        (empty / "data").mkdir(parents=True, exist_ok=True)
        payload, code, _ = _seam(empty, "alpha")
        ok(payload.get("status") == "absent_input",
           f"a bundle with no ontology plane -> absent_input ({payload.get('status')})")
        ok(code == 3, f"and a document seam REFUSES it rather than serving an empty page (exit {code})")
        spine = _declared(payload, "ontology/concepts") or {}
        ok(spine.get("present") is False and spine.get("count") == 0,
           "and the spine is declared PRESENT: false with a count of 0, so the zero has a denominator")

        # ── P7 ───────────────────────────────────────────────────────────────────────────────────
        print("P7 THE ENVELOPE IS INVARIANT — one key set across exit 0, 2 and 3")
        derived, dcode, _ = _seam(root, "alpha")
        refused, rcode, _ = _seam(root, "gamma")
        badreq, bcode, _ = _run(Path(td) / "no-such-root-at-all", "--concept", "alpha")
        trio = (("derived", derived, dcode), ("not_found", refused, rcode),
                ("bad_request", badreq, bcode))
        ok([dcode, rcode, bcode] == [0, 3, 2], f"the three exits are 0/3/2 (got {[dcode, rcode, bcode]})")
        for label, p, _c in trio:
            ok(tuple(sorted(p)) == RESERVED,
               f"{label}: the top-level key set is the 13 reserved keys "
               f"({sorted(set(RESERVED) ^ set(p)) or 'exact'})")
        ok(len({tuple(sorted(p)) for _l, p, _c in trio}) == 1,
           "and it is the SAME key set on all three — a client never reads a key that exists only "
           "when nothing went wrong")
        for label, p, _c in trio:
            ok(p.get("envelope") == ENVELOPE, f"{label}: envelope == {ENVELOPE!r}")
            ok(p.get("mode") == "document", f"{label}: mode == 'document'")
            ok(p.get("status") in SEAM_MINTED, f"{label}: status {p.get('status')!r} is seam-minted")
            ok((p.get("status") == "derived") == (p.get("reason") is None),
               f"{label}: `reason` is null exactly when the status is derived")
            ok(p.get("partial") == [], f"{label}: `partial` is [] — a document is never degraded")
            ok(isinstance(p.get("result"), str),
               f"{label}: `result` is a string, not a list (a list would be index mode)")
            ok(isinstance((p.get("counts") or {}).get("declared"), int),
               f"{label}: counts.declared is an int")
            ok(all((p.get("seam") or {}).get(k) for k in SEAM_STAMP),
               f"{label}: the seam stamp carries {list(SEAM_STAMP)}")
        ok(derived.get("subject") == {"kind": "concept", "id": "alpha"},
           "the subject is {kind, id}, so the host has one cache-key element and not a hand-built string")
        ok(derived.get("counts") == {"returned": 1, "declared": 2},
           f"and a served page counts 1 of 2 (got {derived.get('counts')})")
        ok((_seam(root, "alpha")[0].get("seam") or {}).get("code_id")
           == (derived.get("seam") or {}).get("code_id") != None,
           "`code_id` is stable over two runs of the same tree")
        ok((derived.get("seam") or {}).get("version")
           == (REPO / "VERSION").read_text(encoding="utf-8").strip(),
           "and `seam.version` is the framework's own VERSION, read rather than hardcoded")

        # ── P8 ───────────────────────────────────────────────────────────────────────────────────
        print("P8 EVERY INPUT IS DECLARED — with a role the cache can watch")
        paths = [i["path"] for i in (derived.get("inputs") or [])]
        for want in ("ontology/concepts", "ontology/edges.yaml", "data/datasets", "data/sources"):
            ok(want in paths, f"the bundle plane {want} is declared")
        ok("framework:VERSION" in paths and "framework:mac.schema.json" in paths,
           f"and BOTH framework-side data files are declared (got {[p for p in paths if p.startswith('framework:')]}) "
           "— the host's key stats the bundle only, so an undeclared framework read is the cache hole")
        ok(bool(derived.get("inputs")) and all(i["role"] in INPUT_ROLES for i in derived["inputs"]),
           f"every role is one of the closed four {list(INPUT_ROLES)}")
        spines = [i["path"] for i in (derived.get("inputs") or []) if i["role"] == "spine"]
        ok(spines == ["ontology/concepts"],
           f"exactly one input is the SPINE and it is the plane that enumerates the members ({spines})")
        ok(bool(derived.get("inputs")) and all(
               set(i) == {"path", "role", "present", "parsed", "count"}
               for i in derived["inputs"]),
           "and every record carries {path, role, present, parsed, count}")
        ok((_declared(derived, "data/datasets") or {}).get("parsed") is True,
           "the data-plane descriptors are declared PARSED on a clean bundle")
        ok(bool(derived.get("inputs"))
           and len(refused.get("inputs") or []) == len(derived["inputs"]),
           "the input set is declared on a REFUSAL too — the cache watches the seam's inputs, not "
           "the branch one request happened to take")

        # ── P9 ───────────────────────────────────────────────────────────────────────────────────
        print("P9 A SWALLOWED READ IS A LIE — a corrupted descriptor must change the answer")
        # THE DESCRIPTOR THIS CONCEPT DOES NOT GROUND ON, which is the measured case and not the
        # easy one: corrupting `rel_alpha.yaml` visibly empties two description cells, so even the
        # swallowing version changed its answer. The gate's 8 of 17 silent inputs were all files
        # whose content never reached the page it was asked for — so the payload was byte-identical
        # to a clean run while the bundle underneath it was broken. A test that only corrupted the
        # referenced descriptor would have been green against the defect.
        deg = _bundle(Path(td) / "degrade")
        unref = deg / "data" / "datasets" / "rel_unreferenced.yaml"
        unref.write_text(_DATASET.replace("rel_alpha", "rel_unreferenced"), encoding="utf-8")
        clean, _c, _e = _seam(deg, "alpha")
        unref.write_text(_CORRUPT, encoding="utf-8")
        dirty, dirty_code, _e = _seam(deg, "alpha")
        ok(_without_clock(clean) != _without_clock(dirty),
           "corrupting a descriptor THIS PAGE DOES NOT READ FROM still changes the payload "
           "(modulo the clock) — measured before this fix: 8 of 17 traced inputs changed it not at all")
        ok(dirty.get("status") == "unparsed_input",
           f"and the seam refuses: unparsed_input (got {dirty.get('status')})")
        ok(dirty_code == 3 and dirty.get("result") == "",
           f"exit 3 with an empty page — document mode may not serve an incomplete one (exit {dirty_code})")
        ok("data/datasets/rel_unreferenced.yaml" in (dirty.get("reason") or ""),
           "the reason names the file, root-relative, so the operator knows which one to fix")
        ok((_declared(dirty, "data/datasets") or {}).get("parsed") is False,
           "and the declared input records it as NOT PARSED")
        # the read site's own fact, asserted where it is produced — the seam reads it, it does not
        # re-derive it, because a second author for `what could not be read` is the same defect one
        # plane down
        src = deg / "ontology" / "concepts"
        pi = page_inputs(src, load_concepts(src))
        ok([u["path"] for u in (pi.get("col_desc_unparsed") or [])]
           == ["data/datasets/rel_unreferenced.yaml"],
           "`page_inputs` publishes `col_desc_unparsed` naming the descriptor it could not read")
        src_clean = root / "ontology" / "concepts"
        ok(page_inputs(src_clean, load_concepts(src_clean)).get("col_desc_unparsed") == [],
           "and it is EMPTY on a clean bundle — the negative control, so the refusal is not a constant")

        # ── P10 ──────────────────────────────────────────────────────────────────────────────────
        print("P10 NO ABSOLUTE PATH LEAVES `local`")
        for label, p, _c in trio + (("unparsed_input", dirty, 3),):
            leaks = [w for w, v in _strings({k: v for k, v in p.items() if k != "local"})
                     if _ABS.match(v)]
            ok(not leaks, f"{label}: no absolute path outside `local` ({leaks[:4]})")
        ok(_ABS.match((derived.get("local") or {}).get("root") or "") is not None,
           "and `local.root` does carry it, which is the one block the host drops before the wire")
        ok(_ABS.match((derived.get("local") or {}).get("framework_root") or "") is not None,
           "`local.framework_root` too — `seam.framework_root` is its DIGEST, which identifies the "
           "tree that answered without publishing one operator's disk")

        # ── P11 ──────────────────────────────────────────────────────────────────────────────────
        print("P11 ARGV FAILURES SPEAK — exit 2 with the envelope on stdout, not 0 bytes")
        ok(badreq.get("status") == "bad_request" and bcode == 2,
           f"a root that is not a directory -> bad_request, exit 2 (got {badreq.get('status')}, {bcode})")
        ok(_ABS.match(badreq.get("reason") or "") is None
           and "local.root" in (badreq.get("reason") or ""),
           "and the reason points at `local.root` instead of printing the operator's disk path")
        p6, c6, e6 = _run(root, "--concept", "../../etc/passwd")
        ok(c6 == 2 and p6.get("status") == "bad_request",
           f"a path-shaped concept is refused with exit 2 and an envelope (got {c6}, {p6.get('status')})")
        ok("file stem" in e6, "with prose on stderr for the human")
        ok(p6.get("subject") is None,
           "and NO subject is claimed — there is no member named by an argument that was refused")
        p7, c7, _e = _run(root)
        ok(c7 == 2 and p7.get("status") == "bad_request",
           f"a MISSING --concept also speaks: argparse's own silent exit 2 is intercepted (got {c7}, "
           f"{p7.get('status')})")
        ok(tuple(sorted(p7)) == RESERVED, "and it is the same 13-key envelope")

        # ── P12 ──────────────────────────────────────────────────────────────────────────────────
        print("P12 `--out` STILL PRINTS, AND NEVER WRITES INSIDE THE BUNDLE")
        target = Path(td) / "caller" / "page.json"
        pout, cout, _e = _run(root, "--concept", "alpha", "--out", target)
        ok(cout == 0 and pout.get("status") == "derived",
           f"stdout STILL carries the envelope with --out set (exit {cout}) — a successful --out run "
           "used to be indistinguishable from a failure over the host's `if out:` test")
        ok(target.is_file()
           and json.loads(target.read_text(encoding="utf-8")).get("result") == pout.get("result")
           and pout.get("result"), "and the file holds the same answer")
        inside = root / "ontology" / "stolen.json"
        pin, cin, _e = _run(root, "--concept", "alpha", "--out", inside)
        ok(cin == 2 and pin.get("status") == "bad_request",
           f"an --out INSIDE the bundle is refused (exit {cin}, {pin.get('status')})")
        ok(not inside.exists(), "and nothing was written there")

    print()
    print(("FAIL: %d assertion(s)" % fails) if fails else "PASS: all assertions")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
