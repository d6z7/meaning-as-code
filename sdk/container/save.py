#!/usr/bin/env python3
"""save.py — save_container: the versioned Save contract for a MAC Ontology Container (ADR 2026-08-13).

Two honest modes — Save NEVER overwrites a version, it mints the next one:

  snapshot     package the current PINNED/published version as a portable .tar.gz (a copy to hand off).
               Pure re-verify + package (delegates to sdk.cli.export). No new version.

  materialize  COMMIT the current authored SSOT as the NEXT immutable version: deterministic re-project
               -> publish -> v(N+1). This is "Save my changes as a new version." The changes themselves
               (folding approved plane-3 rulings into the SSOT) are the UPSTREAM dual-key step
               (execute-the-ruling), done by a developer under the gate — save does NOT self-apply
               annotations (an agent cannot mint an SSOT change). Save just seals whatever the SSOT
               currently says as the next signed, content-addressed version.

Immutability reconciliation (ADR): Open opens version N; the annotation store is the dirty buffer;
materialize commits it as N+1; LEDGER.jsonl is the history. Never an in-place overwrite.
"""

from __future__ import annotations

import os
from pathlib import Path


def save_container(
    content_root,
    mode: str = "snapshot",
    *,
    version: str | None = None,
    out=None,
    signing_key: str | None = None,
) -> dict:
    cr = Path(content_root).resolve()
    if mode == "snapshot":
        from sdk.cli.export import export

        return export(cr, version, Path(out) if out else None)

    if mode == "materialize":
        # 1. deterministic re-projection of the served read-view (single lineage-safe path).
        #    GATED: project_source compiles the bundle first and REFUSES a non-conformant one, so Save
        #    cannot mint an immutable version over a bundle that does not compile. There is NO override
        #    here on purpose — a version is permanent and signed, and the operator who wants one anyway
        #    can run the projection themselves with harvest --project-anyway "<reason>" first, which
        #    puts the admission in compile.json where the sealed version will carry it.
        from sdk.cli.harvest import CompileRefused, project_source

        try:
            project_source(cr)
        except CompileRefused as e:
            return {
                "ok": False,
                "mode": mode,
                "error": f"projection refused — bundle does not "
                f"compile; no version was minted\n{e}",
            }
        # 2. seal the current SSOT as the next content-addressed version
        from sdk.cli import publish as _pub

        if signing_key:
            os.environ["MAC_SIGNING_KEY"] = signing_key  # publish reads it from env
        rc = _pub.publish(cr, version)
        if rc != 0:
            return {"ok": False, "mode": mode, "error": "publish refused (gate red — see output)"}
        ver = (cr / "artifacts" / "LATEST").read_text().strip()
        return {
            "ok": True,
            "mode": mode,
            "version": ver,
            "note": "minted the next immutable version from the current SSOT (annotation fold is the "
            "upstream dual-key step, not automated here)",
        }

    return {"ok": False, "error": f"unknown save mode {mode!r} (use snapshot|materialize)"}


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(
        description="Save a MAC Ontology Container (snapshot | materialize)."
    )
    ap.add_argument("--content-root", required=True)
    ap.add_argument("--mode", choices=["snapshot", "materialize"], default="snapshot")
    ap.add_argument("--version", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = save_container(
        a.content_root,
        a.mode,
        version=a.version,
        out=a.out,
        signing_key=os.environ.get("MAC_SIGNING_KEY"),
    )
    print(json.dumps(r, default=str) if a.json else r)
