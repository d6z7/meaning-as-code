#!/usr/bin/env python3
"""regen_projections — config-driven regeneration of an applied ontology's projections.

The ontology is the source of truth; every projection (ER, lineage, graph, RDF, SHACL, the model
catalog, …) is a REGENERATED view of it. This runner reads `<root>/projections.yaml` — the list of
projections THIS source wants — and (re)generates exactly those, so the set is explicit and never
drifts from the ontology.

Two modes:
  (default)  regenerate every enabled projection into <root>/projections/
  --check    regenerate into a temp dir and DIFF against the committed projections; exit 1 if any is
             stale (the drift-gate — wire into a pre-push / CI so a stale projection can't be pushed).

  usage:  python3 tools/regen_projections.py <root> [--check] [--only id,id]

projections.yaml schema:
  name: <short>                         # display / filename prefix (default: metadata.source or dir name)
  projections:
    - id: er                            # unique id
      tool: mac_to_mermaid.py           # a tool in this same tools/ dir
      out: <name>.er.mmd                # output file under projections/  (mutually exclusive with out_dir)
      out_dir: true                     # tool writes multiple files into projections/ (e.g. project_model, okf)
      args: [--er]                      # extra CLI args
      needs: rdflib                     # optional python dep; skip-with-warning if missing
      enabled: true                     # default true
"""
from __future__ import annotations
import argparse, filecmp, importlib.util, shutil, subprocess, sys, tempfile
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
CHECK_SKIP_SUFFIXES = {".svg"}          # renders (need mmdc); regenerated when their .mmd changes — not drift-checked


def load_config(root: Path) -> dict:
    cfg = root / "projections.yaml"
    if not cfg.exists():
        sys.exit(f"ERROR: {cfg} not found — declare the projection set there (see tool docstring).")
    return yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}


def prefix(root: Path, cfg: dict) -> str:
    if cfg.get("name"):
        return str(cfg["name"])
    for p in sorted((root / "ontology" / "concepts").rglob("*.yaml")):
        d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        s = (d.get("metadata") or {}).get("source")
        if s:
            return str(s).lower()
    return root.name.lower()


def dep_missing(name: str | None) -> bool:
    return bool(name) and importlib.util.find_spec(name) is None


def run_one(proj: dict, root: Path, out_dir: Path, name: str) -> tuple[str, bool, str]:
    """Run one projection into out_dir. Returns (id, ok, message)."""
    pid = proj["id"]
    if proj.get("enabled") is False:
        return pid, True, "disabled"
    if dep_missing(proj.get("needs")):
        return pid, True, f"skipped (needs {proj['needs']})"
    tool = HERE / proj["tool"]
    if not tool.exists():
        return pid, False, f"tool not found: {proj['tool']}"
    cmd = [sys.executable, str(tool), str(root)]
    if proj.get("out_dir"):
        cmd += ["--out-dir", str(out_dir)]
    elif proj.get("out"):
        cmd += ["-o", str(out_dir / str(proj["out"]).replace("<name>", name))]
    cmd += [str(a) for a in (proj.get("args") or [])]
    r = subprocess.run(cmd, capture_output=True, text=True)
    # did it produce its declared output? (a projector may exit nonzero on a self-consistency WARNING
    # yet still write a valid projection — treat that as warn, not fail; only "no output" is a failure.)
    out_path = out_dir / str(proj.get("out") or "model.md").replace("<name>", name)
    wrote = out_path.exists()
    if r.returncode != 0:
        last = (r.stderr.strip().splitlines() or ["failed"])[-1].strip()
        if wrote:
            return pid, True, f"warn: {last}"
        return pid, False, last
    return pid, True, "ok"


def tree_diffs(a: Path, b: Path) -> list[str]:
    """Files present in `a` (freshly generated) that are missing or differ in `b` (committed)."""
    out = []
    for f in sorted(a.rglob("*")):
        if f.is_dir() or f.suffix in CHECK_SKIP_SUFFIXES:
            continue
        rel = f.relative_to(a)
        tgt = b / rel
        if not tgt.exists() or not filecmp.cmp(f, tgt, shallow=False):
            out.append(str(rel))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Config-driven regeneration of an ontology's projections.")
    ap.add_argument("root", help="applied-ontology repo root (contains ontology/ and projections.yaml)")
    ap.add_argument("--check", action="store_true", help="drift-gate: diff a fresh regen vs committed; exit 1 if stale")
    ap.add_argument("--only", help="comma-separated projection ids to run (default: all enabled)")
    a = ap.parse_args()

    root = Path(a.root).resolve()
    cfg = load_config(root)
    name = prefix(root, cfg)
    projs = cfg.get("projections") or []
    if a.only:
        want = set(a.only.split(","))
        projs = [p for p in projs if p["id"] in want]
    committed = root / "projections"

    target = Path(tempfile.mkdtemp(prefix="proj-check-")) if a.check else committed
    target.mkdir(parents=True, exist_ok=True)

    failures, skipped = [], []
    for p in projs:
        pid, ok, msg = run_one(p, root, target, name)
        mark = "✓" if ok else "✗"
        if msg not in ("ok",):
            print(f"  {mark} {pid:14} {msg}")
        else:
            print(f"  {mark} {pid:14} {p.get('out') or '(dir)'}")
        if not ok:
            failures.append(pid)
        if "skipped" in msg:
            skipped.append(pid)

    if a.check:
        stale = tree_diffs(target, committed)
        shutil.rmtree(target, ignore_errors=True)
        if failures:
            print(f"\n✗ {len(failures)} projector(s) errored: {', '.join(failures)}")
            return 1
        if stale:
            print(f"\n✗ {len(stale)} projection(s) STALE (regen differs from committed):")
            for s in stale:
                print(f"    {s}")
            print("  → run:  python3 tools/regen_projections.py " + str(root) + "   then commit projections/")
            return 1
        print(f"\n✓ projections fresh ({len(projs)-len(skipped)} checked, {len(skipped)} skipped)")
        return 0

    if failures:
        print(f"\n✗ {len(failures)} projector(s) errored: {', '.join(failures)}")
        return 1
    print(f"\n✓ regenerated {len(projs)-len(skipped)} projection(s) into {committed}"
          + (f"  ({len(skipped)} skipped: {', '.join(skipped)})" if skipped else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
