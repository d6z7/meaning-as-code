#!/usr/bin/env python3
"""unpack.py — untar+unzip a MAC Ontology Container .tar.gz into a directory for VS Code (full structure).

A container ships as a signed .tar.gz (portable, opaque). To SEE / EDIT the ontology in VS Code you unpack
it. This VALIDATES the container first (open_container: manifest + capabilities + integrity + secret gate),
then places its full tree DIRECTLY under <dest>/ (no <version>/ nesting), so `code <dest>` shows
ontology/ data/ runtime/ references/ etc. Round-trip: unpack -> edit in VS Code -> re-publish from the
edited tree to mint the next signed container.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from sdk.container.loader import open_container


def unpack(archive, dest, signing_key: str | None = None) -> dict:
    """Validate + unpack a container .tar.gz into <dest> (contents placed directly inside). Returns the mount report + unpacked_to."""
    dest = Path(dest)
    with tempfile.TemporaryDirectory(prefix="mac-unpack-") as tmp:
        r = open_container(archive, workspace=tmp, signing_key=signing_key)
        if not r.get("ok"):
            return r
        src = Path(r["content_root"])
        dest.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():  # flatten the <version>/ dir into dest/
            target = dest / item.name
            if target.exists():
                shutil.rmtree(target) if target.is_dir() else target.unlink()
            shutil.move(str(item), str(target))
        r["unpacked_to"] = str(dest)
        return r


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Unpack a MAC Ontology Container .tar.gz into a directory (for VS Code)."
    )
    ap.add_argument("archive", help="the container .tar.gz")
    ap.add_argument("dest", help="target directory (created; contents placed directly inside)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = unpack(a.archive, a.dest, signing_key=os.environ.get("MAC_SIGNING_KEY"))
    if a.json:
        print(json.dumps(r, default=str))
    elif r.get("ok"):
        print(
            f"unpacked {r.get('version')} ({r.get('trust')}) -> {r['unpacked_to']}  —  open it in VS Code"
        )
    else:
        print(f"REFUSED: {r.get('errors')}")
    sys.exit(0 if r.get("ok") else 1)
