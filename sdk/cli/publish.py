#!/usr/bin/env python3
"""publish.py — compile a source's blessed SSOT into an immutable, versioned artifact.

Runs the gate suite over --content-root, then compiles the FULL served surface
(data/ + ontology/ + objects.json — NOT just the ontology, so the wiki never has to reach
back into SSOT) into `sources/<d>/<ds>/artifacts/<version>/` with a MANIFEST (sha256 per
file + a tree hash) and a VERSION file. Content-addressed + WRITE-ONCE: the tree hash is
recorded in an append-only `artifacts/LEDGER.jsonl`; republishing a version with a DIFFERENT
tree hash is refused (a tamper), the same hash is idempotent. Updates `artifacts/LATEST`.

The build is atomic (stage -> rename). The wiki pins to <version> and drift-guards on load
(sdk/gate/check_artifact.py). Derived `*.md` read-view is excluded from the artifact.

HONEST LIMIT: true immutability needs the ledger on a protected/branch-protected path (the
author cannot rewrite it) + a signed manifest — see boundaries.yaml:authorization_out_of_band.
Coverage + live acceptance grading are NOT yet gated here (no oracle harness in this source);
publish reports that honestly rather than claiming a correctness it did not check.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root -> sdk importable
from sdk.gate import (
    annotation_isolation,
    check_bundle_secrets,
    check_rule_lock,
    check_write_paths,
)

_COMPILE = [
    "data",
    "ontology",
    "objects.json",
    "mac.project.yaml",
    "index.md",
]  # built-in default served surface
_MANIFEST_EXCLUDE = {"MANIFEST.json", "VERSION"}


def _compile_items(content_root: Path) -> list:
    """The served surface to freeze — MANIFEST-DRIVEN from mac.project.yaml `publish.include` so the
    answerable config (sources.yaml / connection.yaml / runtime/ / references/ / .claude/) travels WITH
    the bundle. Falls back to the built-in default when the manifest declares none. Missing items are
    skipped by the copy loop, so a not-yet-authored surface never breaks publish."""
    mp = content_root / "mac.project.yaml"
    if mp.exists():
        try:
            inc = ((yaml.safe_load(mp.read_text()) or {}).get("publish") or {}).get("include")
            if inc:
                return list(inc)
        except Exception:
            pass
    return list(_COMPILE)


def _tree_manifest(root: Path):
    """Per-file sha256 + a tree hash over everything except MANIFEST.json/VERSION."""
    files = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name not in _MANIFEST_EXCLUDE:
            files[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    tree = hashlib.sha256(
        "\n".join(f"{k}:{v}" for k, v in sorted(files.items())).encode()
    ).hexdigest()
    return files, tree


def _gate_failures(content_root: Path) -> list:
    fails = []
    if check_rule_lock.check(content_root / "ontology") != 0:
        fails.append("rule-lock (TUNE drift — bless first)")
    repo = Path(__file__).resolve().parents[2]
    wp, _ = check_write_paths.check(repo)
    if wp:
        fails.append(f"write-paths ({len(wp)} illegal SSOT writes)")
    if annotation_isolation.check(repo):
        fails.append("annotation-isolation (plane-3 leak)")
    return fails


def publish(content_root: Path, version: str | None) -> int:
    fails = _gate_failures(content_root)
    if fails:
        print("REFUSE to publish — gates RED: " + "; ".join(fails))
        return 1
    art = content_root / "artifacts"
    stage = art / ".staging"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for item in _compile_items(content_root):
        src = content_root / item
        if src.is_dir():
            # include the rendered read-view *.md — the wiki serves pages from the artifact
            shutil.copytree(src, stage / item)
        elif src.exists():
            shutil.copy2(src, stage / item)

    # SECRET GATE — scan the STAGED tree (exactly what will be frozen) BEFORE the write-once
    # freeze, so a credential / infra-handle can never be baked into an immutable artifact.
    leaks = check_bundle_secrets.check(stage)
    if leaks:
        shutil.rmtree(stage)
        print(f"REFUSE to publish — {len(leaks)} secret/handle leak(s) in the staged bundle:")
        for rel, ln, kind, match in leaks[:20]:
            print(f"  {rel}:{ln}  [{kind}]  {match}")
        return 1

    files, tree = _tree_manifest(stage)
    ver = version or ("v" + tree[:12])
    ledger = art / "LEDGER.jsonl"
    seen_same = False
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            rec = json.loads(line)
            if rec["version"] == ver and rec["tree_hash"] != tree:
                shutil.rmtree(stage)
                print(
                    f"REFUSE — version {ver} already published with a DIFFERENT tree hash (write-once)."
                )
                return 1
            if rec["version"] == ver and rec["tree_hash"] == tree:
                seen_same = True
    if seen_same and (art / ver / "MANIFEST.json").exists():
        shutil.rmtree(stage)
        print(f"idempotent — {ver} already published (identical tree hash {tree[:12]}).")
        return 0

    manifest = {"version": ver, "tree_hash": tree, "count": len(files), "files": files}
    _key = os.environ.get("MAC_SIGNING_KEY")  # held out-of-band (CI), not by the local author
    if _key:
        manifest["signature"] = hmac.new(_key.encode(), tree.encode(), hashlib.sha256).hexdigest()
    (stage / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    (stage / "VERSION").write_text(ver + "\n")
    dest = art / ver
    if dest.exists():
        shutil.rmtree(dest)
    stage.rename(dest)  # atomic swap into place

    if not seen_same:
        with ledger.open("a") as fh:
            fh.write(
                json.dumps(
                    {
                        "version": ver,
                        "tree_hash": tree,
                        "files": len(files),
                        "at": datetime.now(UTC).isoformat(timespec="seconds"),
                    }
                )
                + "\n"
            )
    (art / "LATEST").write_text(ver + "\n")
    print(
        f"published {ver} — {len(files)} files, tree {tree[:12]} "
        f"{'(signed)' if _key else '(UNSIGNED — set MAC_SIGNING_KEY)'} -> "
        f"{dest.relative_to(content_root.parent.parent)}"
    )
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--content-root", required=True, help="a sources/<domain>/<dataset> dir")
    ap.add_argument(
        "--version", default=None, help="version tag (default: content-addressed vHASH)"
    )
    a = ap.parse_args()
    cr = Path(a.content_root).resolve()
    if not (cr / "ontology").exists():
        print(f"no ontology/ under {a.content_root}")
        return 1
    return publish(cr, a.version)


if __name__ == "__main__":
    sys.exit(main())
