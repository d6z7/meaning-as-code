#!/usr/bin/env python3
"""Per-estate registers: the instance-specific strings the gates need, kept OUT of this repository.

WHY THESE ARE NOT LISTS IN THE GATES. A detector that names what it forbids IS a register of those
things. `check_bundle_secrets` carried four literal production infra handles (one with a person's
name in it); `check_source_coupling` carried the instance names it exists to keep out of the
instrument. Both gates' own source was the densest concentration in the tree of exactly the strings
they police, and this repository is published.

THE RULE THIS ENFORCES: no instance specifics live in MAC. A gate belongs here; the values it hunts
for belong to the estate running it. That is the same split the integration kit already makes for
its own token register -- "a public method must not carry them".

Each register is a plain text file beside this module, gitignored, one entry per line, #-comments
and blanks ignored. Each has an env override so CI -- which has no gitignored file -- can name one
without committing it, and so tests can declare a synthetic entry rather than writing a real one
into a fixture.

AN EMPTY REGISTER IS NOT A CLEAN TREE. Callers must put the count in their verdict line: a gate that
examined zero declared values has measured nothing, and saying PASS without the denominator is the
zero-denominator pass this estate keeps finding.
"""

from __future__ import annotations

import os
from pathlib import Path

_HERE = Path(__file__).resolve().parent

#: register name -> (filename beside this module, env override)
REGISTERS = {
    "infra_handles": ("infra_handles.txt", "MAC_INFRA_HANDLES"),
    "source_tokens": ("source_tokens.txt", "MAC_SOURCE_TOKENS"),
    # The warehouse's SHARED/gold schemas — the ones no source may materialize into. A DIFFERENT
    # list from source_tokens: a source's own name is precisely what it SHOULD own a schema for.
    "shared_schemas": ("shared_schemas.txt", "MAC_SHARED_SCHEMAS"),
}


def register_path(name: str) -> Path:
    fn, env = REGISTERS[name]
    override = os.environ.get(env)
    return Path(override) if override else _HERE / "gate" / fn


def load(name: str, path: Path | None = None) -> list[str]:
    """The declared entries, or [] when none are declared. Resolved at CALL time, never at import:
    a module-level snapshot would ignore the env override in any process that imported first."""
    p = path if path is not None else register_path(name)
    if not p.is_file():
        return []
    return [
        ln.strip()
        for ln in p.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


class Live(list):
    """A list that re-reads its register on every use, so an env override set after import works."""

    def __init__(self, name: str):
        super().__init__()
        self._name = name

    def _live(self) -> list[str]:
        return load(self._name)

    def __iter__(self):
        return iter(self._live())

    def __len__(self):
        return len(self._live())

    def __contains__(self, x):
        return x in self._live()

    def __repr__(self):
        return repr(self._live())
