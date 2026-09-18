#!/usr/bin/env python3
"""project_objects.py — DERIVE a bundle's object index, on stdout, writing NOTHING.

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

It cannot be called in-process by the reader, though: boundaries.yaml gives the console tree
`may_not_import: [sdk]` and `may_sys_path_mutate: false`, and `sdk.project.objects.__main__`
refuses to be a CLI (correctly — its two optional arguments default to empty and produce a
complete-LOOKING index with two view classes silently missing). So this file is the seam: a thin
framework-side entry point that SUPPLIES BOTH of those arguments, calls the one author, and prints
what it returned. The console runs it as a subprocess, exactly as it already runs
tools/lineage_project.py.

WHAT IT GUARANTEES

  * NOTHING IS WRITTEN. `out_dir=None` is passed unconditionally and is the only call in this file.
    The bundle it reads is, for the caller, immutable and frequently mid-ingestion.
  * BOTH ARGUMENTS ARE SUPPLIED. `lineage=` is the flows list from the same lineage projector the
    supported path uses (sdk/cli/harvest.py `_lineage_flows`); `issues=` is the quality register,
    read the same way project_data.py reads it. Omitting the first flips `lineage: false` on every
    source and dataset and drops their Lineage tab; that regression has shipped twice and both
    times a person noticed, not a gate.
  * A FAILURE IS NAMED, NEVER SILENT. A bundle mid-ingestion is the NORMAL input here, so nothing
    refuses: flows that cannot be computed are reported as `derivation.lineage.ok: false` with a
    reason and the index is still emitted; descriptors that will not parse are listed by name in
    `derivation.unparsed` (build_objects' own `_load` swallows the parse error, so an unreadable
    file would otherwise be indistinguishable from an under-declared one); planes that are absent
    are listed in `derivation.absent`, so a zero count can be read as "not authored yet" rather
    than as a measurement. Only an outright failure of build_objects itself exits non-zero, and
    even then a structured reason goes to stdout so the caller can print it.
  * IT COSTS NOTHING. Local YAML/JSON/MD reads under the bundle plus the framework's own
    vocabulary file. No connector, no warehouse, no model, no network.

Usage:
  python3 tools/project_objects.py <bundle-root> [--out PATH]

  (default)      print the index as JSON on stdout
  --out PATH     write it to PATH instead (never inside the bundle)
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
    # `sdk.*` resolves from the framework root; `lineage_project`/`mac_project` are imported by
    # BARE NAME inside tools/ (that is how lineage_project already reaches mac_project), so both
    # directories have to be reachable when this file is executed by absolute path.
    if _p not in sys.path:
        sys.path.insert(0, _p)

import yaml  # noqa: E402

from sdk.project.objects import build_objects  # noqa: E402

# The descriptor planes whose files are parsed independently below. build_objects' `_load` returns
# None on a parse error, so a half-written descriptor still yields a row titled by its filename
# stem — "unreadable" and "declares nothing" render identically. Mid-ingestion is the normal case
# for this tool, so the two are separated here and reported by name.
_YAML_PLANES = (("data", "sources"), ("data", "transforms"), ("data", "datasets"))


def _iso_now() -> str:
    return _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _flows(root: Path) -> tuple[list, dict]:
    """The column-level flows, from the framework's own lineage projector.

    Threaded into build_objects because it is NOT optional: without it every source and dataset
    comes back with `lineage: false` and no Lineage view, in an index that otherwise looks
    complete. Returns (flows, status) and never raises — a bundle whose manifest has not been
    written yet is a legitimate state, and the caller is told which one it got.
    """
    manifest = root / "mac.project.yaml"
    if not manifest.exists():
        return [], {
            "ok": False,
            "flows": 0,
            "reason": f"no {manifest.name} in this bundle yet, so column lineage could not be derived",
        }
    try:
        from lineage_project import project  # the ONE author of flows

        model, _unclassifiable = project([str(root)])
        flows = model.get("flows") or []
        return flows, {"ok": True, "flows": len(flows), "reason": None}
    except Exception as e:  # noqa: BLE001 — every failure is a state to report, not to raise
        return [], {
            "ok": False,
            "flows": 0,
            "reason": f"the lineage projector failed: {type(e).__name__}: {e}",
        }


def _register(root: Path) -> tuple[list, dict]:
    """The data-quality register's issues, read exactly as sdk/project/project_data.py reads it
    (`issues` or `findings`), so the Quality tabs a live index offers are the ones the projector
    would have offered."""
    p = root / "data" / "quality" / "data_quality_register.yaml"
    if not p.exists():
        return [], {"present": False, "issues": 0, "path": None, "reason": None}
    try:
        reg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as e:  # noqa: BLE001
        return [], {
            "present": True,
            "issues": 0,
            "path": "data/quality/data_quality_register.yaml",
            "reason": f"the register could not be parsed: {type(e).__name__}: {e}",
        }
    issues = (
        (reg.get("issues") or reg.get("findings") or []) if isinstance(reg, dict) else (reg or [])
    )
    return list(issues), {
        "present": True,
        "issues": len(issues),
        "path": "data/quality/data_quality_register.yaml",
        "reason": None,
    }


def _unparsed(root: Path) -> list[dict]:
    """Descriptors that do not parse, by name. See _YAML_PLANES."""
    out = []
    cand: list[Path] = []
    for parts in _YAML_PLANES:
        d = root.joinpath(*parts)
        if d.is_dir():
            cand += sorted(d.glob("*.yaml"))
    cdir = root / "ontology" / "concepts"
    if cdir.is_dir():
        cand += sorted(cdir.rglob("*.yaml"))  # RECURSIVE: concepts may be filed by domain
    for p in cand:
        try:
            yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            out.append(
                {"path": p.relative_to(root).as_posix(), "error": f"{type(e).__name__}: {e}"}
            )
    return out


def _absent(root: Path) -> list[str]:
    """Input planes that are not there yet — so a count of zero can be read as "not authored"
    rather than as a measurement. A zero with no denominator is the shape of every defect in this
    estate."""
    planes = (
        "data/sources",
        "data/transforms",
        "data/datasets",
        "data/lookups",
        "ontology/concepts",
        "data/quality",
    )
    return [rel for rel in planes if not (root / rel).exists()]


def derive(root: Path) -> tuple[dict, int]:
    """The whole derivation. Returns (payload, exit_code)."""
    data_dir = root / "data"
    concepts_dir = root / "ontology" / "concepts"
    flows, lineage_status = _flows(root)
    issues, register_status = _register(root)
    unparsed = _unparsed(root)
    absent = _absent(root)
    derivation = {
        "ok": True,
        "derived_at": _iso_now(),
        "root": str(root),
        "lineage": lineage_status,
        "register": register_status,
        "unparsed": unparsed,
        "absent": absent,
    }
    try:
        # THE ONE AUTHOR, AND THE ONLY CALL. out_dir=None: every write inside build_objects is
        # guarded by `if out_dir:`, so this derivation cannot touch the bundle it reads.
        result = build_objects(
            data_dir, concepts_dir, lineage=flows, issues=issues, out_dir=None
        )
    except Exception as e:  # noqa: BLE001
        derivation["ok"] = False
        derivation["reason"] = f"build_objects failed: {type(e).__name__}: {e}"
        derivation["traceback"] = traceback.format_exc(limit=6)
        return {"objects": [], "counts": {}, "derivation": derivation}, 3
    # A COMPLETE-LOOKING INDEX WITH A VIEW CLASS MISSING is the regression sdk.project.objects
    # refuses its own CLI over, so it is checked here rather than assumed: every relation with a
    # flow must come back carrying lineage. A mismatch is reported, not hidden.
    flagged = sum(1 for o in result.get("objects", []) if o.get("lineage"))
    if flows and flagged == 0:
        derivation["lineage"]["reason"] = (
            f"{len(flows)} flow(s) were derived but no object carries lineage — "
            "the Lineage view tab is missing from every source and dataset"
        )
        derivation["lineage"]["ok"] = False
    derivation["lineage"]["objects_flagged"] = flagged
    result["derivation"] = derivation
    return result, 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Derive a bundle's object index (read-only) and print it as JSON."
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
