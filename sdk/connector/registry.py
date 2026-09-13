#!/usr/bin/env python3
"""registry.py — resolve a connector id to a class. A PLAIN DICT, from a shipped index.

RECORD: §6.3 (the shipped index), §6.4 / §6.5 (what is NOT built), §11.2 (why this is the default).

WHAT THIS MODULE DELIBERATELY DOES NOT CONTAIN, AND UNDER WHICH RULING.
RULING 14 — whether third-party connectors are a requirement — IS UNANSWERED. So there are:

    NO entry points.          NO `importlib.metadata`.      NO import hooks.
    NO plugin loader.         NO `guarded_import`.          NO import deadline.
    NO SIGALRM.               NO distribution provenance.   NO squatting corroboration.

That is not a stub and it is not a fallback. §11.2, in the record's own words: "if Ruling 14 is 'no
third party now', B1-B2 collapse to what the first draft's own kill criterion 4 already prescribes:
a dict of two classes in sdk/connector/registry.py, resolved from the shipped index, at roughly
one-fifth the effort. That is not a fallback; on today's measurements it is the DEFAULT, and the
full plugin architecture is the exception requiring a ruling."

The measurement behind that: a `grep -rn` for `entry_points` and for `importlib.metadata` over this
repository returns ZERO hits each, and the served denominator for third-party connectors is
likewise zero -- so nothing is displaced by not building discovery, and nothing waits on it. Building
discovery now is a mechanism with no population, and every one of its failure modes (H1-H3, H7,
H12, ambiguity, squatting) is a failure mode that exists only because the mechanism does.

WHAT IS BUILT ANYWAY, SO THE SEAM IS FORWARD-COMPATIBLE: the id grammar, the refusal of an
unregistered `mac.*` id, the exit-code split between "your declaration is wrong" and "it is not
installed here", and `ConnectorAmbiguous` in the taxonomy. On the day Ruling 14 lands as "yes",
`resolve()` gains a second lookup AFTER the index and every caller stays as it is.

THERE IS NO MODULE-LEVEL CACHE, and that is a decision, not an omission. Record H13 seeds "a
resolve() that memoizes by id WITHOUT clearing on failure: after a broken connector, a second, good
connector must still resolve". The cheapest way to be immune to a class of bug is to not have the
state it lives in: this module holds one immutable dict read from a file, and `sys.modules` is
Python's import cache, which already behaves correctly on a failed import. tools/_plugin.py's
self-test found exactly this class of defect by seeding two roots and asserting the second is not
served the first's module.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Mapping

from sdk.connector.base import (
    Connector,
    ConnectorConfigError,
    ConnectorContractViolation,
    ConnectorUnavailable,
)

_HERE = Path(__file__).resolve().parent
_INDEX_FILE = _HERE / "index.json"

#: The namespace MAC reserves. An id under it is real ONLY if this repository's own shipped index
#: says so -- §6.5: "a mac.-prefixed id that is NOT a key in the shipped index is refused at
#: resolve". No allowlist of vendors is needed anywhere; that is the point of the namespace rule.
MAC_NAMESPACE = "mac.connector."


def load_index() -> Mapping[str, Mapping[str, Any]]:
    """The shipped index, as data. No imports, no classes, no driver.

    Keys beginning `_` are commentary (this file is JSON and JSON has no comments; the WHY still has
    to live beside the data, so it lives IN it and is filtered here).
    """
    try:
        raw = json.loads(_INDEX_FILE.read_text(encoding="utf-8"))
    except OSError as exc:
        # A missing shipped index is a broken installation, not a bundle finding -> exit 2.
        raise ConnectorUnavailable(f"connector index unreadable: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConnectorUnavailable(f"connector index is not valid JSON: {exc}") from exc
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def split_id(connector_id: str) -> tuple:
    """`"mac.connector.duckdb/1"` -> `("mac.connector.duckdb", "1")`. The id grammar, §6.1.

    A connector id is NEVER a path. `_plugin.py` learned this the expensive way: a name resolved off
    `sys.path` is a name whose winner is decided by path ORDER rather than by the thing asked for.
    """
    text = str(connector_id or "")
    if not text:
        raise ConnectorConfigError("connector id is empty")
    if "\\" in text or text.count("/") > 1 or text.startswith("/") or ".." in text:
        raise ConnectorContractViolation(f"connector id {text!r} is path-shaped")
    name, _, major = text.partition("/")
    return name, (major or "")


def config_schema_for(connector_id: str) -> Mapping[str, Any]:
    """The JSON Schema for an id's `config:` block, WITHOUT IMPORTING THE CONNECTOR.

    This is §6.3's mount tier, and it is the reason the index carries a schema path at all: a host
    can validate a bundle's declaration on a machine where no driver is installed and no connector
    module has ever been imported.

    IT SAYS WHICH TIER IT REACHED. A rule JSON Schema cannot express -- "output is required unless
    the workgroup carries a managed output location" -- is NOT silently skipped: it belongs to
    `validate_config()`, which is code and runs at publish and at answer. A caller that used only
    this function has validated the schema-expressible half and must say so.
    """
    entry = _entry(connector_id)
    rel = entry.get("config_schema")
    if not rel:
        raise ConnectorUnavailable(f"{connector_id}: the index declares no config schema")
    path = _HERE / rel
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConnectorUnavailable(
            f"{connector_id}: shipped config schema {rel!r} unreadable: {exc}"
        ) from exc


def _entry(connector_id: str) -> Mapping[str, Any]:
    """The index row for an id, or the right refusal for its absence.

    THE EXIT-CODE SPLIT, and it is the whole reason this is a function rather than a dict lookup:

      * a `mac.*` id that is NOT in this repository's index is a finding ABOUT THE BUNDLE -> exit 1.
        The index ships WITH MAC, so if MAC's own index does not name it, it is a typo or a squat --
        knowable offline, knowable for free, and knowably the declaration's fault.
      * any OTHER id is "not installed here" -> exit 2, could not run. It may be a perfectly real
        third-party connector on a machine that has it; this one does not, and discovery is Ruling
        14's to answer. Reporting that as a broken bundle is the precise damage _plugin.py exists to
        prevent.
    """
    name, major = split_id(connector_id)
    index = load_index()
    key = f"{name}/{major}" if major else name
    if key in index:
        return index[key]
    # Accept a bare id when exactly one major is shipped: a bundle that declares
    # `mac.connector.duckdb` without a major has not made an error, it has declined to pin one.
    candidates = [k for k in index if k.split("/")[0] == name]
    if len(candidates) == 1:
        return index[candidates[0]]
    if len(candidates) > 1:
        # Two shipped majors and no pin. Refused, never guessed -- tools/mac_resources.py's rule
        # about *.mac applied verbatim: "two is ambiguous and must be refused rather than guessed
        # at." A sort order here would make the winner a property of string collation.
        raise ConnectorConfigError(
            f"{connector_id!r} matches {len(candidates)} shipped majors ({sorted(candidates)}); "
            f"declare the major explicitly"
        )
    if name.startswith(MAC_NAMESPACE):
        raise ConnectorConfigError(
            f"{connector_id!r} is in the reserved namespace {MAC_NAMESPACE!r} but is not in this "
            f"distribution's shipped index. Known: {sorted(index)}"
        )
    raise ConnectorUnavailable(
        f"{connector_id!r} is not a first-party connector and nothing is installed to provide it. "
        f"Third-party connector discovery is not built: Ruling 14 is unanswered and on today's "
        f"measurements the default is this shipped index (record §11.2)."
    )


def resolve(connector_id: str, *, extra: Mapping[str, type] | None = None) -> type:
    """id -> the connector CLASS. One dict lookup and one ordinary import.

    `extra` is an EXPLICIT, PER-CALL injection for fixtures and tests -- the CSV-directory fixture,
    a hostile connector in a conformance run. It is a parameter rather than a module-level
    `register()` on purpose: a mutable global registry is shared state between callers, and shared
    state that a failed resolve can leave half-written is record H13's cache-poisoning class. With
    the mapping passed in, two callers in one process cannot see each other's registrations, which
    is the property _plugin.py's self-test had to be written to enforce.

    `extra` may NOT shadow a `mac.*` id: a fixture that can impersonate a first-party connector is a
    fixture that can make a conformance run pass for the wrong class.
    """
    if extra:
        for key in extra:
            if str(key).startswith(MAC_NAMESPACE):
                raise ConnectorContractViolation(
                    f"an injected connector may not claim the reserved id {key!r}"
                )
        if connector_id in extra:
            return _checked(connector_id, extra[connector_id])

    entry = _entry(connector_id)
    target = entry.get("target")
    if not target or ":" not in str(target):
        raise ConnectorUnavailable(
            f"{connector_id}: the index row declares no importable target"
        )
    module_name, _, attr = str(target).partition(":")
    try:
        module = importlib.import_module(module_name)
    except BaseException as exc:
        # BaseException, not Exception: issubclass(SystemExit, Exception) is FALSE, and a module that
        # calls sys.exit() at import would otherwise take the host's exit code with it. That is not
        # hypothetical in this estate -- a bundle's tools/run_properties.py:39 is literally
        # `sys.exit(f"missing dependency: {exc}...")`. Whatever happens in there, this is exit 2.
        extra_hint = entry.get("extra")
        hint = f"; try: pip install 'meaning-as-code[{extra_hint}]'" if extra_hint else ""
        raise ConnectorUnavailable(
            f"{connector_id}: importing {module_name!r} raised {type(exc).__name__}: {exc}{hint}"
        ) from exc
    try:
        cls = getattr(module, attr)
    except AttributeError as exc:
        raise ConnectorUnavailable(
            f"{connector_id}: {module_name!r} has no attribute {attr!r}"
        ) from exc
    return _checked(connector_id, cls)


def _checked(connector_id: str, cls: Any) -> type:
    """The class is a Connector and its DECLARATION is coherent, before anyone constructs it.

    Checked at resolve and not at first use, because every one of these is knowable offline and for
    free, and a declaration defect found at first use is found with a credential already resolved
    and a socket already open.
    """
    if not (isinstance(cls, type) and issubclass(cls, Connector)):
        raise ConnectorContractViolation(
            f"{connector_id}: {cls!r} is not a Connector subclass"
        )
    problems = cls.declaration_problems()
    if problems:
        raise ConnectorContractViolation(
            f"{connector_id}: declaration is incoherent: "
            + "; ".join(f"[{klass}] {msg}" for klass, msg in problems)
        )
    return cls


def first_party_ids() -> tuple:
    """Every id this distribution ships. The DENOMINATOR any gate over connectors must print."""
    return tuple(sorted(load_index()))


__all__ = [
    "MAC_NAMESPACE", "load_index", "split_id", "config_schema_for", "resolve", "first_party_ids",
]
