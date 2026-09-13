#!/usr/bin/env python3
"""check_reproduction — hold the RECORD and the ARTIFACTS to each other.

WHY THIS EXISTS
---------------
A bundle's process record is a set of CLAIMS: this stage is tool-authored, that one is hand-authored,
this command must never be run. Written as prose, none of them can be checked, and prose rots quietly
while continuing to read as authoritative.

Measured on <dataset>, 2026-08-18 — REPRODUCTION.md carried TWO false claims at the same time:

  * "Never run `harvest --mode concepts`" — true, and incomplete. `--mode onboard --accept` reaches
    the same function; its concepts stage is skipped ONLY when ontology/concepts/ is already
    populated, so on a NEW source it runs, billed, before any business document has been read. The
    prohibition named one of the two doors.
  * A gate block naming validate_schema + check_references + check_shapes — three of eleven, from
    before the compiler existed. Anyone following it would run a quarter of the gates and believe the
    bundle was checked.

Both were found by reading the code, which is exactly what a reader of the record does not do. So the
claims move into `mac.project.yaml#reproduction` as DATA, and this check evaluates them.

WHAT IT WOULD FALSELY FIRE ON, and the legitimate case that must not fire
------------------------------------------------------------------------
* `produces` globs matching nothing. A freshly scaffolded bundle has run no stage, so every glob is
  empty and every stage would look broken. LEGITIMATE CASE: fpl3 on day one. Hence a stage is only
  reported when SOME of its globs match and others do not — a partially-run stage is a real finding,
  an unrun one is not. Severity is warning, never error.
* `enforced_by` on provenance. A concept HARVESTED and then reworked by hand may legitimately keep
  `provenance: harvested` as its origin stamp. LEGITIMATE CASE: none in <dataset> that can be
  distinguished from a violation — and that is precisely the finding. The diagnostic therefore states
  the CONTRADICTION (the record forbids X; N artifacts claim X) rather than accusing anyone of having
  run the command, because the artifacts cannot tell those two apart. Resolving it is an operator act.

NOTHING HERE NAMES A BUNDLE. Every path, command and expression is read from the manifest.

WHAT WAS MISSING, found by the 2026-09-12 framework-gate review
-----------------------------------------------------------------
`main()` read `sys.argv[1]` with a bare `'.'` default and no existence check, and `_manifest()`
swallows every read failure into `{}` — the SAME empty document a bundle with no `reproduction:`
section produces. A nonexistent root, a root with no `mac.project.yaml`, and a real bundle that
declares no reproduction record all printed the identical "check_reproduction: no findings", exit 0.
There was no argparse, no `--self-test`, and no exit-2 path at all. `check_reproduction()` itself —
the function the compiler imports and calls directly — is unchanged; only the CLI wrapper below now
tells "could not find a bundle to evaluate" apart from "found one, and it declares nothing to check".
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import re
import sys

import mac_diag as D

NAME = "check_reproduction"

_EXPR = re.compile(r"^\s*(?P<glob>[^#]+?)\s*#\s*(?P<path>[A-Za-z_][\w.]*)\s*(?P<op>!=|==)\s*(?P<val>\S+)\s*$")


def _yaml_docs(root, glob_pat):
    """Every yaml under `root` matching a bundle-relative glob, as (relpath, parsed)."""
    import glob as _g
    try:
        import yaml
    except ImportError:                                            # pragma: no cover
        return []
    out = []
    for f in sorted(_g.glob(os.path.join(root, glob_pat), recursive=True)):
        if not f.endswith(('.yaml', '.yml')) or not os.path.isfile(f):
            continue
        try:
            out.append((os.path.relpath(f, root), yaml.safe_load(open(f, encoding='utf-8'))))
        except Exception:                                          # noqa: BLE001
            continue
    return out


def _dig(doc, dotted):
    cur = doc
    for part in dotted.split('.'):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _manifest(root):
    try:
        import yaml
        return yaml.safe_load(open(os.path.join(root, 'mac.project.yaml'), encoding='utf-8')) or {}
    except Exception:                                              # noqa: BLE001
        return {}


def check_reproduction(root) -> list:
    """Evaluate mac.project.yaml#reproduction against what is actually on disk."""
    repro = (_manifest(root).get('reproduction') or {})
    if not repro:
        return []
    out = []

    # 1) the narrative twin must exist — a record pointing at a missing file is not a record.
    nar = repro.get('narrative')
    if nar and not os.path.exists(os.path.join(root, nar)):
        out.append(D.Diagnostic(
            code="MAC008", severity=D.ERROR, source="check_reproduction",
            summary=f"reproduction.narrative names `{nar}`, which does not exist",
            witnesses=[D.Witness(file="mac.project.yaml", path="reproduction.narrative")]))

    # 2) PROHIBITIONS. Each carries a checkable consequence; evaluate it.
    # GROUPED BY CONSEQUENCE, not by command. Two doors onto the same forbidden behaviour share one
    # `enforced_by`, and the state on disk is ONE fact — emitting it once per door would report the
    # same 16 concepts twice, which is the fanout this toolchain collapses everywhere else.
    by_expr = {}
    for i, ban in enumerate(repro.get('prohibited') or []):
        expr = (ban.get('enforced_by') or '').strip()
        if expr:
            by_expr.setdefault(expr, []).append((i, ban.get('command', '?')))
    for expr, entries in by_expr.items():
        i, cmd = entries[0]
        cmds = ", ".join(f"`{c}`" for _, c in entries)
        m = _EXPR.match(expr)
        if not m:
            out.append(D.Diagnostic(
                code="MAC008", severity=D.WARNING, source="check_reproduction",
                summary=f"reproduction.prohibited[{i}].enforced_by is not an expression this check "
                        f"can evaluate, so the prohibition is unenforced",
                note="shape: <glob>#<dotted.path> (!=|==) <value>",
                witnesses=[D.Witness(file="mac.project.yaml",
                                     path=f"reproduction.prohibited[{i}].enforced_by",
                                     detail=expr)]))
            continue
        glob_pat, dotted, op, want = m['glob'], m['path'], m['op'], m['val']
        bad = []
        for rel, doc in _yaml_docs(root, glob_pat):
            got = _dig(doc, dotted)
            if got is None:
                continue
            violated = (str(got) == want) if op == '!=' else (str(got) != want)
            if violated:
                bad.append(D.Witness(file=rel, path=dotted, detail=f"{dotted} = {got}"))
        if bad:
            out.append(D.Diagnostic(
                code="MAC004", severity=D.ERROR, source="check_reproduction",
                summary=f"the record forbids {cmds}, and {len(bad)} artifact(s) carry the state "
                        f"those command(s) produce — the record and the bundle disagree",
                note="The artifacts cannot distinguish 'the command was run' from 'the stamp is "
                     "wrong'. Both are defects and both are the operator's to resolve: either the "
                     "objects were authored the forbidden way, or provenance is lying — and "
                     "provenance is the input to every claim-versus-evidence rule downstream.",
                witnesses=bad))

    # 3) STAGES. A PARTIALLY satisfied stage is a finding; an unrun one is not (see docstring).
    import glob as _g
    for st in (repro.get('stages') or []):
        pats = st.get('produces') or []
        if not pats:
            continue
        hit = [p for p in pats if _g.glob(os.path.join(root, p), recursive=True)]
        miss = [p for p in pats if p not in hit]
        if hit and miss:
            out.append(D.Diagnostic(
                code="MAC011", severity=D.WARNING, source="check_reproduction",
                summary=f"stage `{st.get('id')}` ran but did not produce everything it declares "
                        f"({len(miss)} of {len(pats)} output pattern(s) match nothing)",
                witnesses=[D.Witness(file="mac.project.yaml",
                                     path=f"reproduction.stages[{st.get('id')}].produces",
                                     detail=p) for p in miss]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()

    root = os.path.abspath(a.root)
    if not os.path.isdir(root):
        print(f"could not run: {root} is not a directory", file=sys.stderr)
        return 2
    if not os.path.isfile(os.path.join(root, "mac.project.yaml")):
        print(f"could not run: {root} has no mac.project.yaml, so there is no manifest to read a "
              f"reproduction record from", file=sys.stderr)
        return 2

    repro = _manifest(root).get("reproduction") or {}
    diags = check_reproduction(root)
    print(D.render(diags, root, show=D.INFO) or f"{NAME}: no findings")
    errs = sum(1 for d in diags if d.severity == D.ERROR)
    stages, prohibited = len(repro.get("stages") or []), len(repro.get("prohibited") or [])

    if not repro:
        print(f"PASS: {NAME} — mac.project.yaml declares no reproduction record under {root} — "
              f"0 stage(s), 0 prohibition(s) to check")
        return 0
    if errs:
        print(f"FAIL: {NAME} — {errs} defect(s) over {stages} stage(s), {prohibited} "
              f"prohibition(s) examined")
        return 1
    print(f"PASS: {NAME} — 0 defect(s) over {stages} stage(s), {prohibited} prohibition(s) examined")
    return 0


# ---------------------------------------------------------------------------------------------
# self-test: one mutant per reject class, plus a clean fixture that must pass and the liveness
# check that a real defect still fires. Fixtures are domain-neutral on purpose: this repo is public.
# ---------------------------------------------------------------------------------------------

_MANIFEST_NO_REPRO = "name: test-bundle\n"

_MANIFEST_WITH_REPRO = """\
name: test-bundle
reproduction:
  narrative: NARRATIVE.md
  stages: []
  prohibited:
    - command: harvest --mode concepts
      enforced_by: "ontology/concepts/*.yaml#provenance != generated"
"""


def _seed(root, *, manifest, narrative=True, concept_provenance=None) -> str:
    import pathlib as _pl

    r = _pl.Path(root)
    r.mkdir(parents=True, exist_ok=True)
    (r / "mac.project.yaml").write_text(manifest, encoding="utf-8")
    if narrative:
        (r / "NARRATIVE.md").write_text("# reproduction narrative\n", encoding="utf-8")
    if concept_provenance is not None:
        cdir = r / "ontology" / "concepts"
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "widget.yaml").write_text(f"provenance: {concept_provenance}\n", encoding="utf-8")
    return str(r)


def _run(root: str) -> int:
    argv = sys.argv
    sys.argv = ["check_reproduction.py", root]
    try:
        return main()
    finally:
        sys.argv = argv


def _self_test() -> int:
    import tempfile

    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, "cases")

        # 1 · not a directory at all.
        missing = os.path.join(tmp, "does-not-exist")
        got = _run(missing)
        if got != 2:
            failures.append(f"not-a-directory: expected exit 2, got {got}")

        # 2 · a real directory with no mac.project.yaml at all.
        no_manifest = os.path.join(base, "no-manifest")
        os.makedirs(no_manifest, exist_ok=True)
        got = _run(no_manifest)
        if got != 2:
            failures.append(f"no-manifest: expected exit 2, got {got}")

        # 3 · a manifest that declares NO reproduction record — a real, zero-denominator pass.
        no_repro = _seed(os.path.join(base, "no-repro"), manifest=_MANIFEST_NO_REPRO)
        got = _run(no_repro)
        if got != 0:
            failures.append(f"no-reproduction-record: expected exit 0, got {got}")

        # 4 · clean fixture: reproduction declared, narrative exists, provenance does not match the
        #     forbidden state.
        clean = _seed(os.path.join(base, "clean"), manifest=_MANIFEST_WITH_REPRO,
                      concept_provenance="hand-authored")
        got = _run(clean)
        if got != 0:
            failures.append(f"clean: expected exit 0, got {got}")

        # 5 · liveness: an artifact carries the exact state the prohibition forbids.
        drifted = _seed(os.path.join(base, "drifted"), manifest=_MANIFEST_WITH_REPRO,
                        concept_provenance="generated")
        if "generated" == "hand-authored":
            failures.append("fixture 'drifted' did not actually diverge from 'clean'")
        got = _run(drifted)
        if got != 1:
            failures.append(f"drifted: expected exit 1, got {got}")

    total = 5
    if failures:
        print(f"FAIL: {NAME} self-test — {len(failures)} of {total} assertions failed")
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(f"PASS: {NAME} self-test — {total}/{total} (not-a-directory and no-manifest both refuse, "
          f"no declared reproduction record is a real zero-denominator pass, a clean record passes, "
          f"a prohibited state still fires)")
    return 0


if __name__ == "__main__":                                         # pragma: no cover
    raise SystemExit(main())
