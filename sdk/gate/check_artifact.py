#!/usr/bin/env python3
"""check_artifact.py — fail-closed drift-guard over a published artifact.

Recomputes the artifact's tree hash and compares it to (1) the bundled MANIFEST and (2) the
append-only LEDGER. Any mismatch = tamper/drift -> FAIL (the wiki must REFUSE to serve).
Also surfaces pin-behind-LATEST as a distinct, non-fatal NOTE (a self-consistency guard
cannot see staleness — both sides of a superseded-but-consistent artifact agree).

Usage: check_artifact.py --content-root sources/<d>/<ds> [--version vXXX]
The wiki calls verify() on load with its pinned version. Exit 0 clean, 1 on drift. Stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

from sdk.gate import contract

_MANIFEST_EXCLUDE = {"MANIFEST.json", "VERSION"}


def _tree_hash(root: Path) -> str:
    files = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name not in _MANIFEST_EXCLUDE:
            files[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashlib.sha256(
        "\n".join(f"{k}:{v}" for k, v in sorted(files.items())).encode()
    ).hexdigest()


def verify(content_root: Path, version: str | None = None) -> int:
    art = content_root / "artifacts"
    latest = (art / "LATEST").read_text().strip() if (art / "LATEST").exists() else None
    ver = version or latest
    if not ver:
        # Was `return 1`. Nothing published is not artifact DRIFT — it is the gate having no
        # subject. A caller that treats 1 as "this artifact is corrupt" would refuse to serve an
        # artifact that simply does not exist yet.
        print(
            "could not run: no version given and no LATEST pointer — nothing is published",
            file=sys.stderr,
        )
        return 2
    dest = art / ver
    man_path = dest / "MANIFEST.json"
    if not man_path.exists():
        print(
            f"could not run: no artifacts/{ver}/MANIFEST.json — there is nothing to verify against",
            file=sys.stderr,
        )
        return 2
    man = json.loads(man_path.read_text())
    actual = _tree_hash(dest)
    ok = True
    if actual != man["tree_hash"]:
        print(f"DRIFT — recomputed tree {actual[:12]} != MANIFEST {man['tree_hash'][:12]}")
        ok = False
    ledger = art / "LEDGER.jsonl"
    led = {}
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            r = json.loads(line)
            led[r["version"]] = r["tree_hash"]
    if led.get(ver) != man["tree_hash"]:
        print(f"DRIFT — MANIFEST tree hash != LEDGER for {ver} (forged manifest?)")
        ok = False
    sig, key = man.get("signature"), os.environ.get("MAC_SIGNING_KEY")
    if sig and key:
        if hmac.new(key.encode(), man["tree_hash"].encode(), hashlib.sha256).hexdigest() != sig:
            print("FORGERY — MANIFEST signature invalid")
            ok = False
    elif sig:
        print("WARN — artifact is signed but MAC_SIGNING_KEY unset; signature unverified")
    else:
        print(
            "NOTE — artifact is unsigned (set MAC_SIGNING_KEY at publish for an out-of-band signature)"
        )
    if ver != latest:
        print(f"NOTE — pinned {ver} is BEHIND LATEST {latest} (newer content available)")
    declared = man.get("count")
    recomputed = sum(1 for q in dest.rglob("*") if q.is_file() and q.name not in _MANIFEST_EXCLUDE)
    if declared is not None and declared != recomputed:
        # The denominator is itself a finding here: a manifest that under-declares its own file
        # count is how an ADDED file hides. Recomputed, never trusted from the manifest.
        print(f"DRIFT — MANIFEST declares {declared} file(s), tree holds {recomputed}")
        ok = False
    if recomputed == 0:
        print(
            f"could not run: artifacts/{ver} holds no file — 0 examined is not intact",
            file=sys.stderr,
        )
        return 2
    if ok:
        print(
            f"PASS: check_artifact — artifact {ver} intact over {recomputed} file(s) "
            f"recomputed (tree {actual[:12]})"
        )
        return 0
    print(
        f"FAIL: check_artifact — artifact {ver} drifted over {recomputed} file(s) recomputed; "
        f"a host must REFUSE to serve it"
    )
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--content-root")
    ap.add_argument("--version", default=None)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return _self_test()
    if not a.content_root:
        return contract.could_not_run("check_artifact", "--content-root is required")
    root = Path(a.content_root).resolve()
    if not root.is_dir():
        return contract.could_not_run("check_artifact", f"{root} is not a directory")
    return verify(root, a.version)


# -------------------------------------------------------------------------------------------------
# self-test
# -------------------------------------------------------------------------------------------------

_VER = "v000000000001"


def _seal(root: Path) -> None:
    """Publish a tiny artifact the honest way: content first, then the manifest and ledger that
    describe it. Sealing by hand is the only way to get a fixture whose hash is really its name."""
    dest = root / "artifacts" / _VER
    contract.write(dest / "ontology" / "concept.yaml", "concept:\n  name: Thing\n")
    contract.write(dest / "README.md", "an artifact\n")
    th = _tree_hash(dest)
    count = sum(1 for q in dest.rglob("*") if q.is_file() and q.name not in _MANIFEST_EXCLUDE)
    contract.write(
        dest / "MANIFEST.json",
        json.dumps({"tree_hash": th, "count": count, "version": _VER}, indent=1),
    )
    contract.write(
        root / "artifacts" / "LEDGER.jsonl", json.dumps({"version": _VER, "tree_hash": th}) + "\n"
    )
    contract.write(root / "artifacts" / "LATEST", _VER + "\n")


def _ca_run(root: Path):
    import contextlib
    import io as _io

    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        code = verify(root, None)
    dest = root / "artifacts" / _VER
    n = (
        sum(1 for q in dest.rglob("*") if q.is_file() and q.name not in _MANIFEST_EXCLUDE)
        if dest.is_dir()
        else 0
    )
    return contract.Outcome(1 if code else 0, n)


def _self_test() -> int:
    def _tamper(root: Path) -> Path:
        p = root / "artifacts" / _VER / "README.md"
        p.write_text("an artifact, edited\n", encoding="utf-8")
        return p

    def _add(root: Path) -> Path:
        # The class a declared count catches and a tree hash alone can miss if the manifest is
        # regenerated: a file ADDED after sealing.
        return contract.write(root / "artifacts" / _VER / "extra.md", "smuggled\n")

    def _forge(root: Path) -> Path:
        dest = root / "artifacts" / _VER
        man = json.loads((dest / "MANIFEST.json").read_text())
        man["tree_hash"] = _tree_hash(dest)
        return contract.write(dest / "MANIFEST.json", json.dumps(man, indent=1))

    c = contract.GateContract(
        name="check_artifact",
        clean=_seal,
        mutants={
            "content-edited-after-sealing": _tamper,
            "file-added-after-sealing": _add,
            # A manifest re-hashed to match tampered content still disagrees with the LEDGER.
            "manifest-forged-to-match-tampered-content": lambda r: (_tamper(r), _forge(r))[1],
        },
        run=_ca_run,
    )
    return contract.run_self_test(c)


if __name__ == "__main__":
    sys.exit(main())
