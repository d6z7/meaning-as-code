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
                                   happened (`measurements.present: false`), because "nothing has
                                   measured anything yet" and "17 claims were counted and failed"
                                   are different findings that read identically per edge
  E5 unparseable edges.yaml      — surfaces `edges_yaml.parse_error`, NOT an empty edge list. The
                                   framework's own `_load` swallows the parse error, so an
                                   unreadable file otherwise renders as one declaring no
                                   relationships
  E6 absent inputs are NAMED     — `derivation.absent` lists the path it looked at, so a zero reads
                                   as "not authored yet" rather than as a measurement
  E7 NOTHING IS WRITTEN          — the purity guarantee the console's live route depends on,
                                   measured rather than read off a docstring: every file under the
                                   fixture bundle is stat-snapshotted, the derivation runs, and the
                                   snapshot must be identical with no new file of any kind

The fixture bundle is written by this file into a temp dir and is generic (alpha/beta/gamma over
rel_alpha/rel_beta/rel_gamma). No project, customer, brand or source specifics.

Usage:  python3 tests/test_edge_index.py     ·     Exit: 0 = all assertions passed · 1 = a failure
"""
import json
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


def _seam(root: Path) -> tuple[dict, int]:
    """The seam as the console runs it: a subprocess, stdout parsed as JSON."""
    r = subprocess.run(
        [sys.executable, str(TOOLS / "project_edges.py"), str(root)],
        capture_output=True,
        text=True,
    )
    try:
        return json.loads(r.stdout), r.returncode
    except ValueError:
        print("    stdout was not JSON:", (r.stdout or "")[:400])
        print("    stderr:", " ".join((r.stderr or "").split())[-400:])
        return {}, r.returncode


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
        m = (payload.get("derivation") or {}).get("measurements") or {}
        ok(code == 0, f"the seam exits 0 — an unmeasured bundle is a normal input (got {code})")
        ok(m.get("present") is False, "the seam reports measurements.present: false")
        ok(
            "nothing has measured any edge claim yet" in (m.get("reason") or ""),
            "and says so in words, so '0 proved' cannot be read as a measured failure",
        )
        ok(
            "evidence/edge_measurements.json" in ((payload.get("derivation") or {}).get("absent") or []),
            "the absent input is named by path",
        )

        print("E5 an unparseable edges.yaml is NOT an ontology declaring no relationships")
        broken = _bundle(Path(td) / "broken", edges_text="edges:\n  - [unclosed\n")
        edges, err = load_ont_edges(broken / "ontology" / "concepts")
        ok(edges == [], "load_ont_edges yields no edges, as the old inline resolution did")
        ok(bool(err), f"AND it returns the parse error rather than swallowing it (got {err!r})")
        payload, code = _seam(broken)
        ey = (payload.get("derivation") or {}).get("edges_yaml") or {}
        ok(bool(ey.get("parse_error")), "the seam surfaces derivation.edges_yaml.parse_error")
        ok(ey.get("present") is True, "and still reports the file as PRESENT — it exists, it is unreadable")
        ok(code == 3, f"the seam exits non-zero on an unreadable edge file (got {code})")
        ok(
            "could not be parsed" in ((payload.get("derivation") or {}).get("reason") or ""),
            "with a structured reason still on stdout, so the caller can print it",
        )

        print("E6 an absent edges.yaml is named, so its zero has a denominator")
        none = _bundle(Path(td) / "noedges", edges_text=None, measurements=None)
        payload, code = _seam(none)
        d = payload.get("derivation") or {}
        ok(payload.get("total") == 0, "total is 0")
        ok(
            "ontology/edges.yaml" in (d.get("absent") or []),
            "and `absent` names ontology/edges.yaml, so the zero reads as 'not authored yet'",
        )
        ok((d.get("edges_yaml") or {}).get("present") is False, "edges_yaml.present is false")
        ok(code == 0, f"the seam exits 0 — an un-authored bundle is a normal input (got {code})")

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

    print()
    print(("FAIL: %d assertion(s)" % fails) if fails else "PASS: all assertions")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
