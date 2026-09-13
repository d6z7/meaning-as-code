#!/usr/bin/env python3
"""export.py — package a source's PINNED, drift-verified artifact into a portable .tar.gz.

Goal-3 (save/export so the process can be reproduced). This does NOT re-derive anything — it exports the
already-published, signed artifact so a consumer can carry the full ontology + data + reports + answering
config + connection contract elsewhere. Before packaging it:
  1. resolves the version (— --version, else the wiki pin for this domain/dataset, else artifacts/LATEST),
  2. RE-VERIFIES the artifact tree hash against its MANIFEST.json (fail-closed on any tamper/drift),
  3. RE-RUNS the bundle-secret gate (never export a credential/handle leak),
then writes a deterministic tar.gz (sorted entries, fixed mtime).

The .tar.gz itself is NOT content-addressed (tar/gzip carry metadata) — the stable identity is the
MANIFEST tree_hash recorded in artifacts/LEDGER.jsonl. Read-only; never mutates the artifact.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import yaml

from sdk.cli.publish import (
    _tree_manifest,
)
from sdk.gate import check_bundle_secrets


def _pinned_version(content_root: Path) -> str | None:
    """The version the wiki pins for this content root's domain/dataset (wiki/pins.yaml), if any."""
    dd, ds = content_root.parent.name, content_root.name
    pins = (
        content_root.parents[2] / "wiki" / "pins.yaml"
    )  # sources/<d>/<ds> -> repo root -> wiki/pins.yaml
    if pins.exists():
        try:
            p = (yaml.safe_load(pins.read_text()) or {}).get("pins") or {}
            pin = p.get(f"{dd}/{ds}")
            return (
                pin.get("version") if isinstance(pin, dict) else pin
            )  # bare string OR {version, tree_hash}
        except Exception:
            pass
    return None


def _resolve_version(content_root: Path, version: str | None) -> str | None:
    art = content_root / "artifacts"
    if version:
        return version
    return _pinned_version(content_root) or (
        (art / "LATEST").read_text().strip() if (art / "LATEST").exists() else None
    )


def export(content_root: Path, version: str | None, out: Path | None) -> dict:
    """Verify + package the pinned artifact. Returns a result dict (ok/version/tree_hash/path/error)."""
    art = content_root / "artifacts"
    ver = _resolve_version(content_root, version)
    if not ver:
        return {"ok": False, "error": "no version to export (pass --version, or pin/publish first)"}
    adir = art / ver
    manifest_p = adir / "MANIFEST.json"
    if not manifest_p.exists():
        return {
            "ok": False,
            "version": ver,
            "error": f"no artifact at {adir} (MANIFEST.json missing)",
        }

    # 1. drift-verify: the recomputed tree hash MUST equal the recorded one.
    manifest = json.loads(manifest_p.read_text())
    _, tree = _tree_manifest(adir)
    if tree != manifest.get("tree_hash"):
        return {
            "ok": False,
            "version": ver,
            "error": "TAMPER: recomputed tree hash != MANIFEST",
            "recomputed": tree,
            "manifest": manifest.get("tree_hash"),
        }

    # 2. secret gate: never export a leak (defense in depth — publish already gated at freeze).
    leaks = check_bundle_secrets.check(adir)
    if leaks:
        return {
            "ok": False,
            "version": ver,
            "error": f"{len(leaks)} secret/handle leak(s) in the artifact",
            "leaks": [f"{rel}:{ln} [{kind}] {m}" for rel, ln, kind, m in leaks[:10]],
        }

    # 3. deterministic tar.gz (sorted entries, fixed mtime; gzip mtime pinned to 0).
    out = out or (art / f"{ver}.tar.gz")
    files = sorted(p for p in adir.rglob("*") if p.is_file())
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for p in files:
            ti = tarfile.TarInfo(name=f"{ver}/{p.relative_to(adir)}")
            data = p.read_bytes()
            ti.size, ti.mtime, ti.mode = len(data), 0, 0o644
            tar.addfile(ti, io.BytesIO(data))
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(buf.getvalue())
    return {
        "ok": True,
        "version": ver,
        "tree_hash": tree,
        "files": len(files),
        "signed": bool(manifest.get("signature")),
        "path": str(out),
        "bytes": out.stat().st_size,
    }


def main():
    ap = argparse.ArgumentParser(
        description="Export a pinned, drift-verified artifact as a portable tar.gz."
    )
    ap.add_argument("--content-root", required=True, help="a sources/<domain>/<dataset> dir")
    ap.add_argument(
        "--version", default=None, help="version to export (default: the wiki pin, else LATEST)"
    )
    ap.add_argument(
        "--out", default=None, help="output .tar.gz path (default: artifacts/<version>.tar.gz)"
    )
    ap.add_argument(
        "--json", action="store_true", help="print the result as JSON (for the wiki /export route)"
    )
    a = ap.parse_args()
    r = export(Path(a.content_root).resolve(), a.version, Path(a.out) if a.out else None)
    if a.json:
        print(json.dumps(r))
    elif r["ok"]:
        print(
            f"exported {r['version']} — {r['files']} files, tree {r['tree_hash'][:12]} "
            f"{'(signed)' if r['signed'] else '(UNSIGNED)'} -> {r['path']}"
        )
        print(
            f"  identity = MANIFEST tree_hash {r['tree_hash']}  (the .tar.gz bytes are NOT the identity)"
        )
    else:
        print(f"REFUSE to export — {r['error']}")
        for l in r.get("leaks", []):
            print(f"  {l}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
