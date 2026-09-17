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

#: register name -> (filename, env override[, directory]). The directory defaults to `sdk/gate`,
#: where the first three registers were born beside the gates that read them. A THIRD element names
#: a different home, and the tuple GREW AT THE END on purpose: `check_bundle_secrets` and
#: `check_source_coupling` both read `REGISTERS[name][1]` for the env var, so indices 0 and 1 had to
#: keep meaning what they meant.
REGISTERS = {
    "infra_handles": ("infra_handles.txt", "MAC_INFRA_HANDLES"),
    "source_tokens": ("source_tokens.txt", "MAC_SOURCE_TOKENS"),
    # The warehouse's SHARED/gold schemas — the ones no source may materialize into. A DIFFERENT
    # list from source_tokens: a source's own name is precisely what it SHOULD own a schema for.
    "shared_schemas": ("shared_schemas.txt", "MAC_SHARED_SCHEMAS"),
    # The estate's own VOCABULARY — the words its analysts use for its KPIs, and the source columns
    # that stamp WHEN a figure was published. Unlike the three above, these are not strings a gate
    # FORBIDS; they are strings framework HEURISTICS need in order to see anything. They lived as
    # literals in `sdk/project/questions.py` and two `tools/` checkers, where `check_mac_public`
    # found them as the last four leaks in this public repository (2026-09-17).
    #
    # It lives in `registers/`, not `sdk/gate/`, because its three consumers are not gates in
    # `sdk/gate/` — one is a projector under `sdk/project/`, two are checkers under `tools/` — and
    # `registers/` is already the home `check_mac_public` uses for the token register.
    #
    # ONE FILE, GROUPED BY PURPOSE, not one file per checker. Two of the four sites consume the SAME
    # fact (the local KPI word stems), so a per-checker register would put one vocabulary in two
    # homes that are free to disagree — which is precisely the defect `check_rule_reference_basis`
    # exists to catch between a rule's `binds:` and its prose. And an estate adopting MAC fills out
    # one file: three files are three chances to forget one, and a forgotten register is a heuristic
    # that silently stops looking.
    "estate_terms": ("estate_terms.txt", "MAC_ESTATE_TERMS", _HERE.parent / "registers"),
}


def register_path(name: str) -> Path:
    entry = REGISTERS[name]
    fn, env = entry[0], entry[1]
    base = entry[2] if len(entry) > 2 else _HERE / "gate"
    override = os.environ.get(env)
    return Path(override) if override else base / fn


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


def disclosed_path(name: str) -> str:
    """Where a register was looked for, in a form that is safe to PRINT and to COMMIT.

    MEASURED ON THE FIRST CUT OF THIS VERY CHANGE. The honest "no register at <path>" disclosures
    were built with `str(register_path(...))`, and the projected `questions_dashboard.json` — a file
    that is committed to bundle repositories and rendered in a browser — came out carrying
    `/Users/<the operator>/dev/...`. That is precisely the shape `check_mac_public`'s built-in rules
    flag as a leak, and the same string goes into CI logs, which its `--redact` mode exists because
    they are a publication. A disclosure that cannot be shown to anyone is not a disclosure.

    Repo-relative when the register sits inside the repository — the normal case, and the answer a
    reader can act on. Otherwise the bare file name and the env var that pointed at it, which is
    everything needed to act and nothing about whose machine it is.
    """
    p = register_path(name)
    try:
        return str(p.relative_to(_HERE.parent))
    except ValueError:
        return f"{p.name} (named by ${REGISTERS[name][1]}, outside the repository)"


def load_groups(name: str, path: Path | None = None) -> dict:
    """`{group: [value, ...]}` from a GROUPED register (`group | value` per line), or {} when none.

    A grouped register holds several vocabularies in one file, each named by the PURPOSE it serves
    rather than by the checker that reads it. `estate_terms` is the first: an estate's KPI surface
    names, its KPI word stems and its publication-cycle column names all live there, and three
    different tools read the group they need.

    WHY `group | value` AND NOT A YAML MAPPING. A register is edited by hand by whoever owns the
    estate's vocabulary, under a `#`-commented header that tells them what each group is for. One
    fact per line survives a careless edit: a broken line loses ONE term, whereas a mis-indented
    YAML block loses a whole group silently — and losing a whole group silently is the failure this
    register was created to stop being possible.

    A line with no `|` is IGNORED rather than guessed at: it is a term whose group the author forgot
    to name, and quietly filing it under some default group would give it behaviour nobody declared.
    Resolved at CALL time, like `load`, so an env override set after import is honoured.
    """
    p = path if path is not None else register_path(name)
    if not p.is_file():
        return {}
    out: dict = {}
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or "|" not in ln:
            continue
        g, v = ln.split("|", 1)
        g, v = g.strip(), v.strip()
        if g and v:
            out.setdefault(g, []).append(v)
    return out


def group(name: str, group_name: str, path: Path | None = None) -> list:
    """One vocabulary out of a grouped register, or [] when the register or the group is absent.

    THE EMPTY LIST IS A REAL ANSWER AND CALLERS MUST SAY SO. Every caller of this function is a
    heuristic whose reach shrinks when its vocabulary is empty, and a heuristic that shrinks in
    silence is the zero-denominator pass this estate keeps finding. So each one states the count in
    its verdict, and decides deliberately between could-not-run and a disclosed reduced scope.
    """
    return list(load_groups(name, path).get(group_name, []))


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
