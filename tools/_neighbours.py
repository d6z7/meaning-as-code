#!/usr/bin/env python3
"""_neighbours.py — WHERE THE CHECKOUTS BESIDE THIS REPOSITORY ARE, declared ONCE.

WHY THIS EXISTS. Eleven tools held the sibling runtime's location as an absolute path under one
operator's home directory:

    MAC_RUNTIME_SRC = "<one operator's home>/dev/mac-platform/packages/mac-runtime/src"

One fact, typed eleven times. Every copy was two defects at once: an identity leak in a PUBLIC
repository (`tools/check_mac_public.py` reported each one twice, as a home path and as a user id),
and a gate that could not run on any machine but one — with no message saying why, because the
import simply failed.

THE ORDER, AND WHY. `$MAC_RUNTIME_SRC` wins, because an operator who sets it knows where their
checkout is. Otherwise the repositories sit beside each other, so the location is DERIVED from this
file and names no home. Last, an already-importable `mac_runtime` (installed, or a venv) needs no
path at all. When none of the three holds, the caller gets an error that NAMES the variable to set;
callers already print that as REFUSED or could-not-run, which is the honest verdict for a gate that
cannot load the thing it judges.

THE WORKED BUNDLE is the same shape of fact: a checkout beside this one, found rather than named.
Its repository name is itself an estate identity, so it is never written here.
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import sys

ENV_RUNTIME = "MAC_RUNTIME_SRC"
ENV_BUNDLES = "MAC_WORKED_BUNDLES"

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
#: Derived, not typed: the neighbouring platform checkout carries the runtime package under `src/`.
SIBLING_RUNTIME = REPO.parent / "mac-platform" / "packages" / "mac-runtime" / "src"


class RuntimeMissing(ImportError):
    """`mac_runtime` is neither configured, nor beside us, nor importable.

    An ImportError on purpose: every caller already guards its runtime imports with `except
    ImportError` and prints REFUSED, so the actionable message arrives where the diagnosis belongs.
    """


def runtime_src() -> pathlib.Path | None:
    """The directory CONTAINING the `mac_runtime` package, or None if nothing holds it."""
    for cand in (os.environ.get(ENV_RUNTIME), SIBLING_RUNTIME):
        if cand and (pathlib.Path(cand) / "mac_runtime").is_dir():
            return pathlib.Path(cand).resolve()
    return None


def runtime_package() -> pathlib.Path | None:
    """The `mac_runtime` package directory itself — for a tool that READS it as files."""
    src = runtime_src()
    return (src / "mac_runtime") if src else None


def ensure_runtime_on_path() -> pathlib.Path | None:
    """Make `import mac_runtime` work. Returns where it was found; None = already importable.

    Raises `RuntimeMissing` with the variable to set. Call it inside the try/except a caller
    already has around its runtime imports.
    """
    src = runtime_src()
    if src is not None:
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))
        return src
    try:
        if importlib.util.find_spec("mac_runtime") is not None:
            return None
    except (ImportError, ValueError):
        pass
    raise RuntimeMissing(
        f"mac_runtime not found. Set ${ENV_RUNTIME} to the directory containing the `mac_runtime` "
        f"package, put the platform checkout beside this repository (tried {SIBLING_RUNTIME}), or "
        f"install it so `import mac_runtime` works."
    )


def worked_bundles() -> list[pathlib.Path]:
    """Bundle roots on THIS machine beyond the in-repo exemplars, best last.

    `$MAC_WORKED_BUNDLES` (os.pathsep-separated) when set, else any sibling checkout holding
    `example/<name>/mac.project.yaml`. Empty on a machine that carries none, which is not a failure.
    """
    env = os.environ.get(ENV_BUNDLES, "")
    if env.strip():
        return [pathlib.Path(p) for p in env.split(os.pathsep) if p.strip()]
    return sorted(p.parent for p in REPO.parent.glob("*/example/*/mac.project.yaml"))
