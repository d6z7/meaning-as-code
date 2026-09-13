#!/usr/bin/env python3
"""loader.py — open_container: mount-and-validate a MAC Ontology Container (ADR 2026-08-13).

The ONE Open primitive every host (wiki / VS Code / runtime) calls. Accepts a directory OR a .tar.gz;
unpacks a tarball SAFELY (rejects zip-slip + link members), validates the manifest + capabilities +
integrity (sdk.container.spec), and re-runs the secret gate. Returns a Mount dict (content_root, version,
trust, capabilities, errors) the host serves from — never trusting an archive it hasn't verified.
"""

from __future__ import annotations

import os
import tarfile
import tempfile
from pathlib import Path

from sdk.container import spec as _spec
from sdk.gate import check_bundle_secrets

_ARCHIVE_SUFFIXES = (".tar.gz", ".tgz", ".tar")


def _safe_extract(tar: tarfile.TarFile, dest: Path) -> None:
    """Extract with a zip-slip + link guard: every member must resolve INSIDE dest, and no sym/hard links."""
    dest = dest.resolve()
    for m in tar.getmembers():
        if m.issym() or m.islnk():
            raise ValueError(f"refusing link member in archive: {m.name!r}")
        target = (dest / m.name).resolve()
        if target != dest and not str(target).startswith(str(dest) + os.sep):
            raise ValueError(f"unsafe path in archive (zip-slip): {m.name!r}")
    # filter="data" (py3.12+) is the belt to our suspenders: it strips absolute paths / links / device
    # nodes on top of the explicit guard above.
    try:
        tar.extractall(dest, filter="data")
    except TypeError:  # older pythons without the filter kwarg
        tar.extractall(dest)


# trust ordering (weakest -> strongest) so a host can demand a floor via require_trust.
#: The fixed extension of a container's resource description (`mac_resources.py`). The basename
#: beside it is the author's; this is what a host globs for and what a file dialog offers.
RESOURCES_EXT = ".mac"

_TRUST_RANK = {"unverified": 0, "unpublished-ssot": 1, "tree-verified": 2, "signed-verified": 3}


def open_container(
    path, workspace=None, signing_key: str | None = None, require_trust: str | None = None
) -> dict:
    """Mount a container from a directory or .tar.gz. Returns a Mount dict; ok=False if it fails to verify.

    require_trust: minimum trust level to accept ('signed-verified' | 'tree-verified' | ...). A host that
    ANSWERS from a container should pass require_trust='signed-verified' — an unsigned/tampered/unchecked
    container is refused (ok=False), never silently served. Integrity is a full-tree-hash recompute; the
    signature (currently HMAC — see ADR: asymmetric is the hardening) authenticates the author."""
    p = Path(path)
    content_root, unpacked_to = p, None

    # A RESOURCE DESCRIPTION names its own container. `<name>.mac` is the project-file convention —
    # arbitrary basename, fixed extension, at the bundle root — so a file dialog hands back the .mac
    # and the container is the directory holding it. Without this, picking the file a user can SEE
    # fails with "no mac.project.yaml at .../<name>.mac", which tells them nothing about what to do.
    if p.is_file() and p.suffix == RESOURCES_EXT:
        content_root = p.parent
        p = content_root

    if p.is_file() and str(p).endswith(_ARCHIVE_SUFFIXES):
        ws = Path(workspace) if workspace else Path(tempfile.mkdtemp(prefix="mac-container-"))
        ws.mkdir(parents=True, exist_ok=True)
        with tarfile.open(p, "r:*") as tar:
            _safe_extract(tar, ws)
        unpacked_to = ws
        # publish/export pack a single top-level <version>/ dir; descend into it unless the manifest is flat.
        if not (ws / "mac.project.yaml").exists():
            tops = [c for c in ws.iterdir() if c.is_dir()]
            content_root = tops[0] if len(tops) == 1 else ws
        else:
            content_root = ws
    elif not p.exists():
        return {
            "ok": False,
            "content_root": str(p),
            "errors": [f"no such container: {p}"],
            "warnings": [],
            "unpacked_to": None,
        }

    result = _spec.validate(content_root, signing_key=signing_key)
    leaks = check_bundle_secrets.check(content_root)
    trust = result.get("trust")
    below_floor = bool(
        require_trust and _TRUST_RANK.get(trust, 0) < _TRUST_RANK.get(require_trust, 99)
    )

    # READING a container is not ANSWERING from one, and this function used to apply
    # answering-grade strictness to every mount. Measured on the reference bundle: capabilities
    # `readable` and `renderable` are BOTH backed, `answerable` is NOT — so the bundle is perfectly
    # inspectable and unfit to answer from, and collapsing that into one `ok=False` made it
    # impossible to open an ontology in order to LOOK at it. The `require_trust` parameter already
    # existed to express the difference; it just was not governing anything but the trust rank.
    #
    # So: a caller that names a trust floor is an ANSWERING host and gets the strict reading — a
    # leaked infra handle or a false capability claim refuses the mount. A caller that names none is
    # a READER, and those become warnings it can see and decide about. The account-id class is NOT
    # softened: `check_bundle_secrets` forbids account ids everywhere, including config, and this
    # code cannot reach past that.
    answering = require_trust is not None
    leak_lines = [f"secret leak {rel}:{ln} [{k}]" for rel, ln, k, _ in leaks[:10]]
    hard_leaks = [ln for ln in leak_lines if "aws_account_id" in ln]
    soft_leaks = [ln for ln in leak_lines if "aws_account_id" not in ln]

    errors = (
        list(result["errors"])
        if answering
        else [e for e in result["errors"] if "claimed but NOT backed" not in str(e)]
    )
    warnings = list(result.get("warnings", []))

    errors += hard_leaks  # a VALUE, never permitted, at any strictness
    if answering:
        errors += soft_leaks
    else:
        warnings += [f"{ln} — not blocking a read-only mount" for ln in soft_leaks]
        warnings += [
            f"{e} — not blocking a read-only mount"
            for e in result["errors"]
            if "claimed but NOT backed" in str(e)
        ]

    if below_floor:
        errors.append(
            f"trust {trust!r} is below the required floor {require_trust!r} — refusing to mount"
        )
    return {
        "ok": not errors and (bool(result["ok"]) or not answering),
        "readable": bool((result.get("capabilities") or {}).get("backed", {}).get("readable")),
        "content_root": str(content_root),
        "unpacked_to": str(unpacked_to) if unpacked_to else None,
        "version": result.get("version"),
        "tree_hash": (result.get("integrity") or {}).get("tree_hash"),  # the full-hash identity
        "spec_version": result.get("spec_version"),
        "trust": trust,
        "integrity": result.get("integrity"),
        "capabilities": result.get("capabilities"),
        "metadata": (result.get("manifest") or {}).get("metadata"),
        "errors": errors,
        "warnings": warnings,
    }


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Open (mount + validate) a MAC Ontology Container.")
    ap.add_argument("path", nargs="?", default=".", help="a container dir or .tar.gz")
    ap.add_argument(
        "--workspace", default=None, help="where to unpack a tarball (default: a temp dir)"
    )
    ap.add_argument("--require-trust", default=None, help="minimum trust floor to accept")
    ap.add_argument("--json", action="store_true", help="single-line JSON (for callers)")
    a = ap.parse_args()
    r = open_container(
        a.path,
        workspace=a.workspace,
        signing_key=os.environ.get("MAC_SIGNING_KEY"),
        require_trust=a.require_trust,
    )
    print(json.dumps(r, default=str) if a.json else json.dumps(r, indent=2, default=str))
