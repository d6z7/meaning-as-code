#!/usr/bin/env python3
"""
test_edge_index.py — the EDGE INDEX's one author, pinned. `sdk.project.objects._edge_index` is the
only thing in this estate that resolves an edge's realisation and its proof, and until this file it
had no test anywhere: a grep over sdk/, tools/ and tests/ for `_edge_index` or `edge_index` hit
only objects.py itself. It is now read live by the console's /edges route, so its first test must
not be an operator's eye — which is how the defect this route exists to fix arrived.

  E1 the whole set, both planes  — 1 physical + 1 business edge index as 2, and `level` survives
  E2 unmeasured is UNPROVED      — an edge nothing has counted says so; it is never blank
  E3 measured is PROVED, with its detail in the vocabulary of what was counted
  E4 no measurement record       — every edge unproved, and the SEAM reports which of the two
                                   happened (`degraded` + a `partial[]` entry naming the record),
                                   because "nothing has measured anything yet" and "17 claims were
                                   counted and failed" are different findings that read
                                   identically per edge
  E5 unparseable edges.yaml      — `unparsed_input` at exit 3, NOT an empty edge list. The
                                   framework's own `_load` swallows the parse error, so an
                                   unreadable file otherwise renders as one declaring no
                                   relationships
  E6 absent inputs are NAMED     — the `inputs[]` row for the path it looked at carries
                                   `present: false` beside a `0 of 0`, so a zero reads as "not
                                   authored yet" rather than as a measurement
  E7 NOTHING IS WRITTEN          — the purity guarantee the console's live route depends on,
                                   measured rather than read off a docstring: every file under the
                                   fixture bundle is stat-snapshotted, the derivation runs, and the
                                   snapshot must be identical with no new file of any kind

AND THE SEAM'S SIDE OF `mac.seam/1` (SEAM_CONTRACT.md), which is a different subject from the
author's: E1–E3 and E7 judge `_edge_index`, C1–C10 judge the ENVELOPE the console is handed. They
are in one file because a seam that answers correctly in a shape nobody can branch on is the whole
five-incident class, and splitting them would let one be green while the other rots.

  C1 the key set is INVARIANT    — the 13 declared keys, identical on all four exits this seam can
                                   take (degraded 0, absent_input 0, unparsed_input 3,
                                   bad_request 2). A reserved key that exists only when nothing
                                   went wrong is a key a client reads and a failure hides
  C2 every INPUT is declared     — measured with the same `sys.addaudithook` open-trace the gate
                                   uses, not read off the docstring: 0 files opened under the
                                   bundle may be missing from `inputs[]`, because a cache that
                                   cannot see a plane cannot know when to drop
  C3 DEGRADATION IS SIGNALLED    — `_edge_index` reads the measurement record under
                                   `except Exception: meas = {}` (sdk/project/objects.py:233-234),
                                   so a corrupt record costs every proof and changes nothing it
                                   returns. The seam's own read of the SAME file is what makes it
                                   visible: `status: degraded` + one `partial[]` entry naming it
  C4 a record of the WRONG SHAPE — a JSON list where an object belongs is `parsed: false`, not an
                                   AttributeError: the old `(doc or {}).get("results")` raised
                                   OUTSIDE its own try and the seam exited 1 with 0 bytes
  C5 the SPINE refuses           — an unparseable edges.yaml is `unparsed_input` at exit 3, never a
                                   degraded zero: when the enumerating input cannot be read, "0
                                   rows" and "the list could not be read" have one shape on screen
  C6 an absent spine is a STATE  — `absent_input` at exit 0 with `counts: 0 of 0`, which index mode
                                   may serve; the denominator is what makes the zero readable
  C7 argv failures SPEAK         — a caller error prints the envelope on stdout and exits 2. All
                                   three seams promised this in prose and printed 0 bytes
  C8 no absolute path LEAKS      — every string outside `local` is free of the operator's disk
  C9 the seam STAMPS itself      — tool, version, framework_root, code_id, so WHICH framework tree
                                   answered is on the wire rather than an unstated variable
  C10 `--out` is validated       — it writes the CALLER's file, refuses a path inside the bundle,
                                   and stdout still carries the envelope (a silent `--out` run was
                                   indistinguishable from a failure over the host's `if out:`)

The fixture bundle is written by this file into a temp dir and is generic (alpha/beta/gamma over
rel_alpha/rel_beta/rel_gamma). No project, customer, brand or source specifics.

Usage:  python3 tests/test_edge_index.py     ·     Exit: 0 = all assertions passed · 1 = a failure
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
TOOLS = REPO / "tools"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(TOOLS))

from sdk.project.objects import edge_index, load_ont_edges  # noqa: E402

fails = 0


def ok(cond, msg):
    global fails
    print(("  ✓ " if cond else "  ✗ ") + msg)
    fails += 0 if cond else 1


# ── the fixture bundle ───────────────────────────────────────────────────────────────────────────
# TWO EDGES, ONE PER PLANE, because the whole point of the surface being wired is that the two are
# different claims: a physical edge is a foreign key in the warehouse, a business edge is a
# relationship between business objects on a different layer. An index that reports 2 but flattens
# both to one plane would pass a count assertion and still be the defect.
_EDGES_YAML = """\
edges:
  - edge_id: alpha__joins__beta
    level: physical
    type: foreign_key
    join_rule: "rel_alpha.beta_key = rel_beta.beta_key"
    verified_by: "measurement:alpha__joins__beta"
    confidence: C1
    endpoints:
      from: { concept: Alpha, cardinality: "0..N", role: joinsBeta }
      to: { concept: Beta, cardinality: "1" }
  - edge_id: alpha__shares__gamma
    level: business
    type: shared_attribute
    resolved_by: "register:gamma_code"
    endpoints:
      from: { concept: Alpha, cardinality: "0..N", role: sharesGamma }
      to: { concept: Gamma, cardinality: "0..1" }
"""

# ONE RESULT, COVERING ONE OF THE TWO. So "proved" and "unproved" are both exercised over one
# index — a fixture in which everything is measured cannot tell whether the unproved branch works.
_MEASUREMENTS = {
    "results": [
        {
            "edge": "alpha__joins__beta",
            "kind": "join_predicate",
            "holds": True,
            "matched": 120,
            "lhs": 120,
            "fanout": 1,
        }
    ]
}


def _concept(name: str, relation: str) -> str:
    return (
        "concept:\n"
        f"  name: {name}\n"
        f"  label: {name}\n"
        "  class: entity\n"
        "grounding:\n"
        f"  table: {relation}\n"
    )


def _bundle(root: Path, edges_text: str = _EDGES_YAML, measurements=_MEASUREMENTS) -> Path:
    cdir = root / "ontology" / "concepts"
    cdir.mkdir(parents=True, exist_ok=True)
    for nm, rel in (("Alpha", "rel_alpha"), ("Beta", "rel_beta"), ("Gamma", "rel_gamma")):
        (cdir / f"{nm.lower()}.yaml").write_text(_concept(nm, rel), encoding="utf-8")
    if edges_text is not None:
        (root / "ontology" / "edges.yaml").write_text(edges_text, encoding="utf-8")
    if measurements is not None:
        (root / "evidence").mkdir(parents=True, exist_ok=True)
        (root / "evidence" / "edge_measurements.json").write_text(
            json.dumps(measurements), encoding="utf-8"
        )
    (root / "mac.project.yaml").write_text("project: edge_index_lab\n", encoding="utf-8")
    return root


def _snapshot(root: Path) -> dict:
    return {
        p.relative_to(root).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _run(*argv) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOLS / "project_edges.py"), *[str(x) for x in argv]],
        capture_output=True,
        text=True,
    )


def _seam(root: Path, *extra) -> tuple[dict, int]:
    """The seam as the console runs it: a subprocess, stdout parsed as JSON."""
    r = _run(root, *extra)
    try:
        return json.loads(r.stdout), r.returncode
    except ValueError:
        print("    stdout was not JSON:", (r.stdout or "")[:400])
        print("    stderr:", " ".join((r.stderr or "").split())[-400:])
        return {}, r.returncode


# ── the contract's own vocabulary, restated ONCE here so an assertion cannot drift from it ──────
_RESERVED = (
    "envelope", "mode", "status", "reason", "result", "counts", "inputs", "partial",
    "seam", "subject", "derived_at", "aux", "local",
)
_SEAM_MINTED = ("derived", "degraded", "absent_input", "unparsed_input", "not_found",
                "author_failed", "bad_request")

#: The same open-trace the gate runs: a seam is judged on what it OPENED, not on what it says it
#: reads. Run in a child so the hook sees the real process, exactly as check_seam_contract.py does.
_TRACER = r'''
import json, os, runpy, sys
_seen, _out = [], os.environ["EDGE_TRACE_OUT"]
sys.argv = sys.argv[1:]
_tool = sys.argv[0]
sys.addaudithook(lambda ev, a: _seen.append(str(a[0])) if ev == "open" else None)
_rc = 0
try:
    runpy.run_path(_tool, run_name="__main__")
except SystemExit as e:
    _rc = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
except BaseException:
    import traceback; traceback.print_exc(); _rc = 1
open(_out, "w").write(json.dumps(_seen))
sys.exit(_rc)
'''


def _traced_opens(root: Path) -> tuple[list, dict]:
    """(files the run opened UNDER the bundle, root-relative · the payload it printed)."""
    with tempfile.TemporaryDirectory() as td:
        runner = Path(td) / "_trace.py"
        runner.write_text(_TRACER, encoding="utf-8")
        out = Path(td) / "trace.json"
        env = dict(os.environ)
        env["EDGE_TRACE_OUT"] = str(out)
        r = subprocess.run(
            [sys.executable, str(runner), str(TOOLS / "project_edges.py"), str(root)],
            capture_output=True, text=True, env=env, check=False,
        )
        seen = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    under = set()
    for raw in seen:
        try:
            under.add(Path(raw).resolve().relative_to(Path(root).resolve()).as_posix())
        except (ValueError, OSError):
            continue
    try:
        payload = json.loads(r.stdout)
    except ValueError:
        payload = {}
    return sorted(under), payload


def _covered(declared: list, opened: str) -> bool:
    for d in declared:
        d = str(d or "").rstrip("/")
        if d.startswith("framework:"):
            continue
        if opened == d or opened.startswith(d + "/"):
            return True
    return False


def _strings(node, path="$"):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _strings(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _strings(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


def _without_clock(payload: dict) -> str:
    def strip(n):
        if isinstance(n, dict):
            return {k: strip(v) for k, v in sorted(n.items()) if k != "derived_at"}
        if isinstance(n, list):
            return [strip(v) for v in n]
        return n
    return json.dumps(strip(payload), sort_keys=True, ensure_ascii=False)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = _bundle(Path(td) / "bundle")

        print("E1 the whole set, both planes")
        ix = edge_index(root, root / "ontology" / "concepts")
        ok(ix["total"] == 2, f"total is 2 of 2 declared (got {ix['total']})")
        by_id = {e["edge_id"]: e for e in ix["edges"]}
        ok(set(by_id) == {"alpha__joins__beta", "alpha__shares__gamma"}, "both edges are indexed")
        ok(
            by_id["alpha__joins__beta"]["level"] == "physical",
            "the physical edge keeps level=physical",
        )
        ok(
            by_id["alpha__shares__gamma"]["level"] == "business",
            "the business edge keeps level=business — the plane is not flattened",
        )
        ok(
            by_id["alpha__shares__gamma"]["type"] == "shared_attribute",
            "a shared_attribute edge is not reported as a foreign key",
        )
        ok(
            by_id["alpha__joins__beta"]["realisation"] == "join_rule"
            and by_id["alpha__shares__gamma"]["realisation"] == "resolved_by",
            "each edge names WHICH of the three realisations reaches it",
        )
        ok(
            by_id["alpha__joins__beta"]["cardinality_from"] == "0..N"
            and by_id["alpha__joins__beta"]["cardinality_to"] == "1",
            "both cardinality ends survive, separately",
        )

        print("E2 an edge nothing has counted reads UNPROVED, not blank")
        p = by_id["alpha__shares__gamma"]["proof"]
        ok(p.get("state") == "unproved", f"proof.state is 'unproved' (got {p.get('state')!r})")
        ok("state" in p, "proof is a block with a state, never an absent key")

        print("E3 a measured edge reads PROVED, with the detail of what was counted")
        p = by_id["alpha__joins__beta"]["proof"]
        ok(p.get("state") == "proved", f"proof.state is 'proved' (got {p.get('state')!r})")
        ok(
            p.get("detail") == "120/120 resolve, max fanout 1",
            f"the detail is in the vocabulary of the kind counted (got {p.get('detail')!r})",
        )
        ok(ix["measured"] == 1 and ix["unproved"] == 1, "the counts agree: 1 proved of 2, 1 unproved")

        print("E4 no measurement record at all — a state, not a silent zero")
        bare = _bundle(Path(td) / "unmeasured", measurements=None)
        ixb = edge_index(bare, bare / "ontology" / "concepts")
        ok(
            ixb["total"] == 2 and ixb["measured"] == 0,
            "the edges still index; nothing is proved because nothing was counted",
        )
        payload, code = _seam(bare)
        ok(code == 0, f"the seam exits 0 — an unmeasured bundle is a normal input (got {code})")
        ok(
            payload.get("status") == "degraded",
            f"membership is intact and only a per-member ATTRIBUTE is unknown, so index mode "
            f"degrades rather than refusing (status {payload.get('status')!r})",
        )
        par = payload.get("partial") or []
        ok(
            len(par) == 1
            and par[0].get("input") == "evidence/edge_measurements.json"
            and par[0].get("role") == "attribute",
            f"1 partial[] entry names the record by path AND role, so the degrade is not inferred "
            f"from an empty anything (got {par})",
        )
        ok(
            "nothing has measured any edge claim" in ((par[0] if par else {}).get("reason") or ""),
            "and says so in words, so '0 proved' cannot be read as a measured failure",
        )
        mi = [i for i in (payload.get("inputs") or [])
              if i.get("path") == "evidence/edge_measurements.json"]
        ok(
            len(mi) == 1 and mi[0].get("present") is False,
            f"the absent input is DECLARED with present:false — the cache's list of what to watch "
            f"has to hold a plane that is not there yet (got {mi})",
        )
        ok(
            (payload.get("counts") or {}).get("declared") == 2
            and (payload.get("counts") or {}).get("returned") == 2,
            f"and the count is still 2 of 2: a degrade is not a shortfall in MEMBERSHIP "
            f"(got {payload.get('counts')!r})",
        )

        print("E5 an unparseable edges.yaml is NOT an ontology declaring no relationships")
        broken = _bundle(Path(td) / "broken", edges_text="edges:\n  - [unclosed\n")
        edges, err = load_ont_edges(broken / "ontology" / "concepts")
        ok(edges == [], "load_ont_edges yields no edges, as the old inline resolution did")
        ok(bool(err), f"AND it returns the parse error rather than swallowing it (got {err!r})")
        payload, code = _seam(broken)
        ok(code == 3, f"the seam exits non-zero on an unreadable edge file (got {code})")
        ok(
            payload.get("status") == "unparsed_input",
            f"C5 the SPINE refuses: `unparsed_input`, never a degraded zero (got "
            f"{payload.get('status')!r})",
        )
        sp = [i for i in (payload.get("inputs") or []) if i.get("role") == "spine"]
        ok(
            len(sp) == 1 and sp[0].get("present") is True and sp[0].get("parsed") is False,
            f"the spine is declared PRESENT and NOT parsed — it exists, it is unreadable, and the "
            f"two are different findings (got {sp})",
        )
        ok(payload.get("result") == [], "the result is the empty value of its own type")
        ok(
            payload.get("partial") == [],
            "and partial[] is EMPTY: a refusal is not a degrade, and `partial != []` iff "
            "`status == degraded` is one fact, not two",
        )
        ok(
            "will not parse" in (payload.get("reason") or ""),
            "with a structured reason still on stdout, so the caller can print it",
        )

        print("E6 an absent edges.yaml is named, so its zero has a denominator")
        none = _bundle(Path(td) / "noedges", edges_text=None, measurements=None)
        payload, code = _seam(none)
        ok(code == 0, f"the seam exits 0 — an un-authored bundle is a normal input (got {code})")
        ok(
            payload.get("status") == "absent_input",
            f"C6 an absent spine is a STATE index mode may serve, not a failure (got "
            f"{payload.get('status')!r})",
        )
        ok(
            payload.get("counts") == {"returned": 0, "declared": 0},
            f"and the zero carries its DENOMINATOR — `0 of 0` (nothing authored) and `0 of ?` (the "
            f"plane could not be read) render identically without it (got {payload.get('counts')!r})",
        )
        sp = [i for i in (payload.get("inputs") or []) if i.get("role") == "spine"]
        ok(
            len(sp) == 1 and sp[0].get("path") == "ontology/edges.yaml"
            and sp[0].get("present") is False,
            f"the spine is named by path with present:false, so the zero reads as 'not authored "
            f"yet' rather than as a measurement (got {sp})",
        )
        ok(
            payload.get("partial") == [],
            "partial[] is empty: two absent inputs are still not a degrade — the status says "
            "absent_input and the reason says which",
        )

        print("E7 NOTHING IS WRITTEN — the purity the live route depends on")
        before = _snapshot(root)
        edge_index(root, root / "ontology" / "concepts")
        _seam(root)
        after = _snapshot(root)
        ok(before == after, f"all {len(before)} fixture files unchanged in size and mtime")
        ok(
            not (root / "ontology" / "edges.json").exists(),
            "and no edges.json was produced — the derivation answers a question, it does not build",
        )

        # ── mac.seam/1 — the ENVELOPE, which is a different subject from the author ────────────
        print("C1 the 13-key envelope is INVARIANT across every exit this seam can take")
        exits = {}
        for label, args, want in (
            ("degraded (exit 0)", (bare,), 0),
            ("absent_input (exit 0)", (none,), 0),
            ("unparsed_input (exit 3)", (broken,), 3),
            ("bad_request (exit 2)", (Path(td) / "no-such-root-at-all",), 2),
        ):
            pay, code = _seam(*args)
            exits[label] = (pay, code)
            ok(code == want, f"{label}: the exit code is {want} (got {code})")
        shapes = {label: tuple(sorted(p)) for label, (p, _c) in exits.items()}
        ok(
            len(set(shapes.values())) == 1,
            f"one key set over all {len(shapes)} exits — a reserved key that vanishes on failure "
            f"is a key a client reads and a failure hides (got {sorted(set(shapes.values()))})",
        )
        ok(
            set(next(iter(shapes.values()))) == set(_RESERVED),
            f"and it is exactly the declared set (got {sorted(next(iter(shapes.values())))})",
        )
        ok(
            all(p.get("envelope") == "mac.seam/1" for p, _c in exits.values()),
            "every exit names the contract it answers under, so a host refuses intelligibly "
            "instead of raising KeyError on a key that moved",
        )
        ok(
            all(p.get("status") in _SEAM_MINTED for p, _c in exits.values()),
            f"every status is one of the 7 SEAM-minted tokens (got "
            f"{[p.get('status') for p, _c in exits.values()]})",
        )
        ok(
            all((p.get("reason") is None) == (p.get("status") == "derived")
                and "reason" in p for p, _c in exits.values()),
            "`reason` is PRESENT on every exit and null exactly when the status is `derived`, so "
            "`key absent` and `reason: null` cannot be confused",
        )
        ok(
            all(p.get("mode") == "index" for p, _c in exits.values()),
            "and the mode is declared `index` on every one of them — the seam's answer is a list "
            "of independently derived members for which it can publish `returned of declared`",
        )

        print("C2 every input the run OPENS is declared — measured, not remembered")
        opened, traced_payload = _traced_opens(root)
        declared = [i.get("path") for i in (traced_payload.get("inputs") or [])]
        undeclared = [o for o in opened if not _covered(declared, o)]
        ok(
            opened and not undeclared,
            f"0 of {len(opened)} traced bundle open(s) are undeclared ({len(declared)} declared: "
            f"{declared}); undeclared: {undeclared}",
        )
        roles = {i.get("role") for i in (traced_payload.get("inputs") or [])}
        ok(
            roles and roles <= {"spine", "row", "attribute", "framework"} and "spine" in roles,
            f"every role is one of the closed four and one input is the SPINE — nothing else says "
            f"which plane ENUMERATES the members (got {sorted(roles)})",
        )
        ok(
            any(str(i.get("path")).startswith("framework:")
                for i in (traced_payload.get("inputs") or [])),
            "and the FRAMEWORK-side read is declared too — the host's fingerprint stats the bundle "
            "tree only, so an undeclared framework input is a cache that never drops",
        )

        print("C3 a corrupt measurement record is SIGNALLED, not swallowed")
        clean, _c = _seam(root)
        rotten = _bundle(Path(td) / "rotten")
        (rotten / "evidence" / "edge_measurements.json").write_text("{not json", encoding="utf-8")
        pay, code = _seam(rotten)
        ok(code == 0, f"index mode still serves — membership is intact (exit {code})")
        ok(
            pay.get("status") == "degraded",
            f"the status changes to `degraded` (got {pay.get('status')!r})",
        )
        par = pay.get("partial") or []
        ok(
            len(par) == 1 and par[0].get("input") == "evidence/edge_measurements.json",
            f"partial[] names the file that could not be read (got {par})",
        )
        mi = [i for i in (pay.get("inputs") or [])
              if i.get("path") == "evidence/edge_measurements.json"]
        ok(
            len(mi) == 1 and mi[0].get("present") is True and mi[0].get("parsed") is False,
            f"declared present AND not parsed — a file that exists and will not read is not an "
            f"absent one (got {mi})",
        )
        ok(
            _without_clock(pay) != _without_clock(clean),
            "and the payload DIFFERS from the clean run modulo the clock: `_edge_index` swallows "
            "this read under `except Exception: meas = {}`, so without the seam's own read the "
            "answer would be byte-identical while every proof was lost",
        )

        print("C4 a record of the wrong SHAPE is a state, not an AttributeError")
        wrong = _bundle(Path(td) / "wrongshape", measurements=["not", "an", "object"])
        pay, code = _seam(wrong)
        ok(code == 0, f"the seam still answers (exit {code}, was exit 1 with 0 bytes)")
        ok(
            pay.get("status") == "degraded" and (pay.get("partial") or []),
            f"a JSON list where an object belongs degrades and names itself (got "
            f"{pay.get('status')!r})",
        )

        print("C7 a caller error SPEAKS on stdout")
        r = _run(Path(td) / "no-such-root-at-all")
        ok(r.returncode == 2, f"exit 2 (got {r.returncode})")
        ok(
            len(r.stdout) > 0,
            f"{len(r.stdout)} byte(s) on stdout — the promise 'even then a structured reason goes "
            f"to stdout' was false in the only place it matters",
        )
        badpay = json.loads(r.stdout) if r.stdout.strip() else {}
        ok(
            badpay.get("status") == "bad_request",
            f"with the closed token for a caller error before any derivation (got "
            f"{badpay.get('status')!r})",
        )
        r = _run(root, "--no-such-flag")
        ok(
            r.returncode == 2 and r.stdout.strip()
            and json.loads(r.stdout).get("status") == "bad_request",
            f"and a BAD FLAG speaks too, rather than argparse's bare exit 2 (exit {r.returncode}, "
            f"{len(r.stdout)} byte(s) on stdout)",
        )

        print("C8 no absolute filesystem path outside `local`")
        for label, (pay, _c) in exits.items():
            leaks = [
                w for w, v in _strings({k: v for k, v in pay.items() if k != "local"})
                if v.startswith("/") and v.count("/") >= 2 and " " not in v
            ]
            ok(not leaks, f"{label}: no operator disk path on the wire (got {leaks[:4]})")
        ok(
            isinstance((clean.get("local") or {}).get("root"), str),
            "and `local.root` still carries it, for the operator's log and for the host to drop",
        )

        print("C9 the seam stamps WHICH framework answered")
        st = clean.get("seam") or {}
        ok(
            all(st.get(k) for k in ("tool", "version", "framework_root", "code_id")),
            f"all four stamp fields are present and non-empty (got {st})",
        )
        ok(
            st.get("tool") == "project_edges.py",
            f"the stamp names this tool (got {st.get('tool')!r})",
        )
        ok(
            st.get("framework_root") and not str(st["framework_root"]).startswith("/"),
            f"and `framework_root` identifies the tree WITHOUT publishing the disk path — the "
            f"host's locator silently prefers an installed root over a sibling checkout, so the "
            f"tree that answered has to be on the wire (got {st.get('framework_root')!r})",
        )

        print("C10 `--out` writes the caller's file and stdout still carries the envelope")
        dest = Path(td) / "elsewhere" / "edges.json"
        r = _run(root, "--out", dest)
        ok(dest.is_file(), "the caller's file is written")
        ok(
            r.stdout.strip() and json.loads(r.stdout).get("envelope") == "mac.seam/1",
            f"AND stdout still carries the envelope — with nothing there, a successful --out run "
            f"is indistinguishable from a failure over the host's `if out:` test (got "
            f"{len(r.stdout)} byte(s))",
        )
        r = _run(root, "--out", root / "ontology" / "edges.json")
        ok(
            r.returncode == 2
            and (json.loads(r.stdout).get("status") if r.stdout.strip() else None)
            == "bad_request",
            f"an --out INSIDE the bundle is refused — 0 of 3 seams validated this path and the "
            f"bundle a seam reads is immutable to it (exit {r.returncode})",
        )
        ok(
            not (root / "ontology" / "edges.json").exists(),
            "and nothing was written inside the bundle",
        )

    print()
    print(("FAIL: %d assertion(s)" % fails) if fails else "PASS: all assertions")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
