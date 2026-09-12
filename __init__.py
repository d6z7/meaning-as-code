"""meaning-as-code — the MAC framework.

This file makes the framework importable and, more importantly, *locatable*. Consumers must never
hardcode a sibling-directory path to find the schema and checkers; they call `framework_root()`.

The repo is deliberately flat: the checkers in `tools/` resolve their own data with
`Path(__file__).resolve().parent.parent`, i.e. each assumes it sits directly beside
`mac.schema.json`. Packaging maps this directory as the package itself, so that assumption holds
identically in a source checkout and in an installed wheel. Nothing moved; see
`decisions/2026-09-10_packaging-and-release-surface.md` (option C).
"""
from __future__ import annotations

import os
import pathlib

__all__ = ["__version__", "framework_root", "schema_path", "MEANING_AS_CODE_ENV"]

MEANING_AS_CODE_ENV = "MEANING_AS_CODE"

_HERE = pathlib.Path(__file__).resolve().parent


def _read_version() -> str:
    try:
        return (_HERE / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0+unknown"


__version__ = _read_version()


def _pep440(version: str) -> str:
    """Map the framework's own version string onto a PEP 440 release identifier.

    VERSION is the single home for "which generation is this" and it uses the estate's grammar:
    `0.1.14-develop` on develop, `0.1.13` on main (tools/version.py documents the discipline).
    PEP 440 rejects `-develop`, so packaging needs `0.1.14.dev0`. This is a DERIVATION, not a
    second home — nothing else may assert a version, or the version gate has one more claim to
    keep in sync.
    """
    base = version.strip()
    if base.endswith("-develop"):
        return base[: -len("-develop")] + ".dev0"
    return base


__pep440_version__ = _pep440(__version__)


def framework_root() -> pathlib.Path:
    """The directory holding mac.schema.json, the closed vocabularies and tools/.

    Resolution order, deliberately explicit so a wrong answer is loud rather than silent:
      1. $MEANING_AS_CODE, if set — a developer checkout wins, which is how the estate already
         overrides the framework (run_checks.sh honours the same variable).
      2. This installed package.
    Raises RuntimeError if the resolved directory does not actually carry the payload, rather
    than returning a plausible-looking path that fails later inside a checker.
    """
    override = os.environ.get(MEANING_AS_CODE_ENV)
    root = pathlib.Path(override).expanduser().resolve() if override else _HERE
    if not (root / "mac.schema.json").is_file():
        source = f"${MEANING_AS_CODE_ENV}={override}" if override else f"the installed package at {root}"
        raise RuntimeError(
            f"meaning-as-code payload not found: {source} does not contain mac.schema.json. "
            f"Unset {MEANING_AS_CODE_ENV} to use the installed framework, or point it at a checkout."
        )
    return root


def schema_path(name: str = "mac.schema.json") -> pathlib.Path:
    """Absolute path to one of the framework's schema or vocabulary files."""
    path = framework_root() / name
    if not path.is_file():
        raise FileNotFoundError(f"no such framework file: {name} (looked in {framework_root()})")
    return path
