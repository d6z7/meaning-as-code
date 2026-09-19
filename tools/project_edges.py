#!/usr/bin/env python3
"""project_edges.py — DERIVE a bundle's edge index, on stdout, writing NOTHING.

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

This is the same defect tools/project_objects.py exists to fix one surface over, and this file is
modelled on it line for line.

WHY IT CALLS `edge_index` AND NOT `build_objects`

The objects precedent can call `build_objects(..., out_dir=None)` because the OBJECT index IS that
function's return value. The EDGE index is not: it is computed inside the write branch and goes
straight to disk, never into the returned `result`. So `build_objects(out_dir=None)` answers nothing
about edges. The edge index's one author is `sdk.project.objects._edge_index`, and
`sdk.project.objects.edge_index` is the public door onto it that this file was declared for. Both
of its inputs are local file reads, and the write that used to be the only way to see its output
belongs to its CALLER, not to it. Re-implementing an edge index in the reader would create a second
author for one artifact, which is the defect class this estate spends its time removing.

It cannot be called in-process by the console: boundaries.yaml gives that tree
`may_not_import: [sdk]` and `may_sys_path_mutate: false`. So this file is the seam — a thin
framework-side entry point that SUPPLIES the arguments, calls the one author, and prints what it
returned. The console runs it as a subprocess, exactly as it already runs project_objects.py.

WHAT IT GUARANTEES

  * NOTHING IS WRITTEN. `edge_index` takes no out_dir and has none to take: its whole body is two
    reads, a per-edge dict build, a sort and a return. The bundle it reads is, for the caller,
    immutable and frequently mid-ingestion. `--out` writes the caller's own file, never inside the
    bundle.
  * THE ARGUMENTS ARE SUPPLIED, and by name. `root` is the BUNDLE ROOT, not the data dir — the
    author resolves `<root>/evidence/edge_measurements.json` off it, so passing `<root>/data` would
    silently report every edge unproved.
  * A FAILURE IS NAMED, NEVER SILENT. A bundle mid-ingestion is the NORMAL input here, so nothing
    refuses. An absent `ontology/edges.yaml` is reported in `derivation.absent` so a zero reads as
    "not authored yet" rather than as a measurement; an UNPARSEABLE one is reported as
    `derivation.edges_yaml.parse_error`, because the framework's own loader swallows that and would
    otherwise render an unreadable file identically to one declaring no relationships; an absent
    `evidence/edge_measurements.json` is reported in `derivation.measurements`, because the author
    degrades every edge to `proof.state: "unproved"` when it is missing and a page showing 0 proved
    of 17 must be able to say which of the two happened. Only an outright failure of the author
    exits non-zero, and even then a structured reason goes to stdout so the caller can print it.
  * IT COSTS NOTHING. Two local file reads under the bundle. No connector, no warehouse, no model,
    no network. Measured at 0.126 s on a 71 KB edges.yaml with a 10 KB measurement record, against
    the console's own 30 s derivation wall.

Usage:
  python3 tools/project_edges.py <bundle-root> [--out PATH]

  (default)      print the index as JSON on stdout
  --out PATH     write it to PATH instead (never inside the bundle)

A bundle root laid out as this tool reads it:

  <root>/ontology/edges.yaml               the edge set   (alpha__joins__beta, ...)
  <root>/ontology/concepts/**.yaml         the concepts the endpoints name
  <root>/evidence/edge_measurements.json   what has counted each claim, if anything has
"""

from __future__ import annotations

import argparse
import datetime as _dt
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

from sdk.project.objects import edge_index, load_ont_edges  # noqa: E402

# The two files the author reads, relative to the bundle root. Named once, so `absent` and the
# per-file blocks below cannot drift apart from what is actually opened.
_EDGES_YAML = "ontology/edges.yaml"
_MEASUREMENTS = "evidence/edge_measurements.json"


def _iso_now() -> str:
    # `_dt.timezone.utc`, not the precedent's `_dt.UTC` alias: that alias is 3.11+, and this tool is
    # run by TWO interpreters — the console's venv (3.12) via `sys.executable`, and a bare `python3`
    # from the usage line above, which on a stock macOS is 3.9. Measured: the alias raises
    # AttributeError there, i.e. the seam would answer nothing on the very interpreter its own
    # docstring tells an operator to use.
    return (
        _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def _measurements(root: Path) -> dict:
    """What has counted anything in this bundle, as a state rather than an absence.

    `_edge_index` stamps `proof.state: "unproved"` on every edge when this record is missing, which
    is honest per edge and mute in aggregate: "0 of 17 proved" reads as a measured failure when the
    truth may be that nothing has measured anything yet. So the record's presence and its result
    count are reported, and a page can say the difference out loud.
    """
    p = root / _MEASUREMENTS
    if not p.exists():
        return {
            "present": False,
            "path": _MEASUREMENTS,
            "results": 0,
            "reason": (
                f"no {_MEASUREMENTS} in this bundle, so nothing has measured any edge claim yet — "
                "every edge reads unproved because none has been counted, not because one failed"
            ),
        }
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 — a state to report, not to raise
        return {
            "present": True,
            "path": _MEASUREMENTS,
            "results": 0,
            "reason": f"the measurement record could not be parsed: {type(e).__name__}: {e}",
        }
    results = (doc or {}).get("results") or []
    return {
        "present": True,
        "path": _MEASUREMENTS,
        "results": len(results) if isinstance(results, list) else 0,
        "reason": None,
    }


def _absent(root: Path) -> list[str]:
    """Inputs that are not there yet — so a count of zero can be read as "not authored" rather
    than as a measurement. A zero with no denominator is the shape of every defect in this
    estate."""
    return [rel for rel in (_EDGES_YAML, _MEASUREMENTS) if not (root / rel).exists()]


def derive(root: Path) -> tuple[dict, int]:
    """The whole derivation. Returns (payload, exit_code)."""
    concepts_dir = root / "ontology" / "concepts"
    # Read once here for the STATE of the file (does it parse?); `edge_index` reads it again for
    # its content. Two reads of a 71 KB file cost nothing measurable, and the alternative is
    # either a second author for the resolution or an index that cannot say why it is empty.
    _edges, parse_error = load_ont_edges(concepts_dir)
    edges_yaml = {
        "present": (root / _EDGES_YAML).exists(),
        "path": _EDGES_YAML,
        "parse_error": parse_error,
    }
    derivation = {
        "ok": True,
        "derived_at": _iso_now(),
        "root": str(root),
        "edges_yaml": edges_yaml,
        "measurements": _measurements(root),
        "absent": _absent(root),
    }
    try:
        # THE ONE AUTHOR, AND THE ONLY CALL. It has no write branch to skip: there is no out_dir
        # in its signature, so this derivation cannot touch the bundle it reads.
        payload = edge_index(root, concepts_dir)
    except Exception as e:  # noqa: BLE001
        derivation["ok"] = False
        derivation["reason"] = f"edge_index failed: {type(e).__name__}: {e}"
        derivation["traceback"] = traceback.format_exc(limit=6)
        return {
            "edges": [],
            "total": 0,
            "measured": 0,
            "unproved": 0,
            "derivation": derivation,
        }, 3
    # AN UNPARSEABLE EDGE FILE IS NOT AN EMPTY ONTOLOGY. The author cannot tell the difference —
    # it is handed a list — so the check belongs here, where the file's state is known.
    if parse_error:
        derivation["ok"] = False
        derivation["reason"] = f"{_EDGES_YAML} could not be parsed: {parse_error}"
    payload["derivation"] = derivation
    return payload, (3 if parse_error else 0)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Derive a bundle's edge index (read-only) and print it as JSON."
    )
    ap.add_argument("root", help="the bundle root (the directory holding mac.project.yaml)")
    ap.add_argument("--out", metavar="PATH", help="write the JSON here instead of stdout")
    a = ap.parse_args()
    root = Path(a.root).expanduser().resolve()
    if not root.is_dir():
        print(f"ERROR: not a directory: {root}", file=sys.stderr)
        return 2
    payload, code = derive(root)
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if a.out:
        outp = Path(a.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
