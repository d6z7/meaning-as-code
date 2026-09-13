#!/usr/bin/env python3
"""spec.py — the MAC Ontology Container FORMAT + its validator (ADR 2026-08-13).

A container is a directory whose root ``mac.project.yaml`` is the manifest. ``validate()`` checks, in
order: the manifest parses and its ``spec_version`` is recognised; the declared plane roots exist; each
declared ``capability`` is BACKED by real contents (a claim the container can't back is an error, so
capabilities are enforceable, not decorative); and — if the container is published — the integrity anchor
holds (recomputed tree-hash == ``MANIFEST.json``, and the HMAC signature is reported honestly).

Pure + read-only. The tree-hash is imported from the publisher so it is byte-for-byte the SAME hash the
artifact was sealed with (a re-implementation could drift and silently break integrity).
"""

from __future__ import annotations

import hmac
import json
from pathlib import Path

import yaml

from sdk.cli.publish import _tree_manifest  # THE canonical tree-hash — do not re-implement

KNOWN_SPECS = {"mac.container/1"}
# capabilities whose truth we can positively check against the container's contents:
_CHECKABLE = {"readable", "renderable", "answerable"}


def _read_yaml(p: Path) -> dict:
    try:
        return yaml.safe_load(p.read_text()) or {}
    except Exception:
        return {}


def _nonempty(p: Path) -> bool:
    """A file that exists and carries something. EXISTENCE IS NOT CONTENT.

    `answerable` was backed by `.exists()` alone, so a ZERO-BYTE connection.yaml backed
    `answerable: true` — the capability system's own version of the zero-denominator pass this estate
    keeps finding elsewhere. A capability is a claim about what a container can DO; a filename is not
    evidence for it.
    """
    try:
        return p.is_file() and p.stat().st_size > 0
    except OSError:
        return False


def _backed_capabilities(cr: Path, m: dict) -> dict:
    """What the container's CONTENTS actually support — the ground truth capabilities are checked against.

    WHAT `answerable` MEANS, and it is narrower than it sounds: this container CARRIES what answering
    needs — an interpreter, and a declared connection. It is checked OFFLINE and it costs nothing.

    It does NOT mean the warehouse answers. That is a claim about the world, it is billed, and it is
    established once when a runtime spawns and then held — never re-tested per question, and never on
    a page load. Two different claims, two different lifecycles; conflating them is how a browse
    becomes a bill.

    THE FILENAME FALLBACK IS GONE. `rt.get("connection") or "connection.yaml"` meant an UNDECLARED
    file silently became the container's connection — which is how a manifest came to declare a
    connection whose value was byte-identical to the fallback, a declaration carrying no information.
    A connection must now be DECLARED to count.
    """
    planes = m.get("planes") or {}
    onto = cr / (planes.get("ontology") or "ontology")
    data = cr / (planes.get("data") or "data")
    rt = m.get("runtime") or {}
    interp = rt.get("interpreter")
    conn = rt.get("connection")                       # no fallback: undeclared is undeclared
    return {
        "readable": onto.is_dir() and data.is_dir(),
        "renderable": _nonempty(cr / "objects.json"),
        "answerable": bool(interp) and _nonempty(cr / str(interp))
        and bool(conn) and _nonempty(cr / str(conn)),
        "annotatable": True,  # a container can always receive plane-3 annotations (stored outside it)
    }


def validate(container_dir, signing_key: str | None = None) -> dict:
    """Validate a mounted container directory. Returns a structured result (ok/errors/warnings/…)."""
    cr = Path(container_dir)
    errors: list[str] = []
    warnings: list[str] = []
    mp = cr / "mac.project.yaml"
    if not mp.exists():
        return {
            "ok": False,
            "errors": [f"not a container — no mac.project.yaml at {cr}"],
            "warnings": [],
            "manifest": {},
            "spec_version": None,
            "version": None,
            "integrity": {"published": False},
            "capabilities": {},
        }
    m = _read_yaml(mp)

    spec = m.get("spec_version")
    if spec not in KNOWN_SPECS:
        # not fatal for legacy containers, but flag loudly — a host may refuse an unknown format.
        (errors if spec else warnings).append(
            f"spec_version {spec!r} not in {sorted(KNOWN_SPECS)}"
            if spec
            else "no spec_version (legacy/pre-container manifest)"
        )

    # declared plane roots must exist
    for k, sub in (m.get("planes") or {}).items():
        if not (cr / str(sub)).exists():
            errors.append(f"declared plane {k!r} -> {sub!r} does not exist")

    # capabilities: every checkable claim must be backed by real contents
    declared = m.get("capabilities") or {}
    backed = _backed_capabilities(cr, m)
    for cap in _CHECKABLE:
        if declared.get(cap) and not backed.get(cap):
            errors.append(f"capability {cap!r} claimed but NOT backed by contents")
    if declared.get("account_portable"):
        # we cannot positively verify portability; the known limit is that the data plane is account-pinned.
        warnings.append(
            "capability 'account_portable: true' cannot be verified (data plane is account-coupled)"
        )

    # integrity — only if this is a PUBLISHED container (has a MANIFEST.json)
    integ: dict = {"published": False, "tree_ok": None, "signature": "unsigned", "tree_hash": None}
    mf = cr / "MANIFEST.json"
    version = None
    vfile = cr / "VERSION"
    if vfile.exists():
        version = vfile.read_text().strip()
    if mf.exists():
        integ["published"] = True
        manifest = json.loads(mf.read_text())
        version = version or manifest.get("version")
        _, tree = _tree_manifest(cr)
        integ["tree_hash"] = (
            tree  # the FULL hash — the identity a pin should compare (v<12> is a label)
        )
        integ["tree_ok"] = tree == manifest.get("tree_hash")
        if not integ["tree_ok"]:
            errors.append(
                f"integrity: recomputed tree {tree[:12]} != MANIFEST {str(manifest.get('tree_hash'))[:12]}"
            )
        sig = manifest.get("signature")
        if sig and signing_key:
            good = hmac.compare_digest(
                sig, hmac.new(signing_key.encode(), tree.encode(), "sha256").hexdigest()
            )
            integ["signature"] = "signed-verified" if good else "signed-bad"
            if not good:
                errors.append("integrity: signature present but does NOT verify with the given key")
        elif sig:
            integ["signature"] = "signed-unverified"  # signed, but no key supplied to check it
    # trust level a host can gate on
    if integ["signature"] == "signed-verified":
        trust = "signed-verified"
    elif integ.get("tree_ok"):
        trust = "tree-verified"
    elif not integ["published"]:
        trust = "unpublished-ssot"
    else:
        trust = "unverified"

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "manifest": m,
        "spec_version": spec,
        "version": version,
        "integrity": integ,
        "trust": trust,
        "capabilities": {"declared": declared, "backed": backed},
    }


if __name__ == "__main__":
    import sys

    print(json.dumps(validate(sys.argv[1] if len(sys.argv) > 1 else "."), indent=2, default=str))
