#!/usr/bin/env python3
"""check_reproduction — hold the RECORD and the ARTIFACTS to each other.

WHY THIS EXISTS
---------------
A bundle's process record is a set of CLAIMS: this stage is tool-authored, that one is hand-authored,
this command must never be run. Written as prose, none of them can be checked, and prose rots quietly
while continuing to read as authoritative.

Measured on fpl2, 2026-08-18 — REPRODUCTION.md carried TWO false claims at the same time:

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
  `provenance: harvested` as its origin stamp. LEGITIMATE CASE: none in fpl2 that can be
  distinguished from a violation — and that is precisely the finding. The diagnostic therefore states
  the CONTRADICTION (the record forbids X; N artifacts claim X) rather than accusing anyone of having
  run the command, because the artifacts cannot tell those two apart. Resolving it is an operator act.

NOTHING HERE NAMES A BUNDLE. Every path, command and expression is read from the manifest.
"""
from __future__ import annotations

import fnmatch
import os
import re

import mac_diag as D

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


def main():                                                        # pragma: no cover
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    diags = check_reproduction(root)
    print(D.render(diags, root, show=D.INFO) or "check_reproduction: no findings")
    return 1 if any(d.severity == D.ERROR for d in diags) else 0


if __name__ == "__main__":                                         # pragma: no cover
    raise SystemExit(main())
