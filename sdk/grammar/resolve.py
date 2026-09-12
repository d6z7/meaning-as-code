#!/usr/bin/env python3
"""One grammar governs this process, and there is no second copy to fall back to.

WHAT THIS USED TO BE. `sdk/` lived in a different repository from the grammar it validates against,
so it had to FIND that repository at runtime. It guessed a sibling checkout. When the packages
layout absorbed the SDK the guess became a path that does not exist, resolution fell through **in
silence** to a vendored fork of the schema, and the numbers were:

    fork       sdk/grammar/mac.schema.json      25 $defs  ->  22 of 22 reference concepts FAIL
    framework  meaning-as-code/mac.schema.json  37 $defs  ->   0 of 22 fail

The authoring path could not validate the bundle it had itself produced, and nothing said which
schema had judged it.

WHY THE FORK IS GONE. It existed for exactly one reason: a checkout of the SDK might not have the
framework beside it. Now that `sdk/` lives INSIDE the framework repository, that cannot happen --
there is no resolution step to fall through, and nothing to vendor from, because the grammar is
already on the path. The drift this module used to report is now structurally impossible rather than
detected after the fact. `check_grammar_home` proves the invariant (exactly ONE grammar in this
tree) instead of policing a fallback.

RESOLUTION ORDER. Declaration first, position last, and position is only admissible because it is no
longer a GUESS ACROSS REPOSITORIES -- it is a fact within one repository that a gate verifies.

    1. $MAC_SCHEMA          explicit override of the schema file itself
    2. $MEANING_AS_CODE     explicit override of the framework root
    3. meaning_as_code.framework_root()      the packaged resolver, when installed
    4. this tree            sdk/grammar/resolve.py -> ../../mac.schema.json

There is no step 5. If none of those resolve, this RAISES. A build that cannot find its grammar must
stop, not quietly validate against something else -- that is the whole lesson of the fork.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

#: The repo root: sdk/grammar/resolve.py -> sdk/grammar -> sdk -> <root>. One tree, one grammar.
_TREE_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_NAME = "mac.schema.json"


class GrammarNotFound(RuntimeError):
    """No grammar resolved. Deliberately fatal -- see the module docstring."""


def _framework_schema() -> Path | None:
    """The framework's own grammar, by declaration then by tree. Never a fork."""
    env_root = os.environ.get("MEANING_AS_CODE")
    if env_root:
        cand = Path(env_root) / SCHEMA_NAME
        if cand.exists():
            return cand
    try:
        from meaning_as_code import framework_root
    except ImportError:
        pass
    else:
        # Deliberately NOT wrapped: framework_root() raises on a bad override, and a bad override
        # must be heard rather than swallowed.
        cand = framework_root() / SCHEMA_NAME
        if cand.exists():
            return cand
    cand = _TREE_ROOT / SCHEMA_NAME
    return cand if cand.exists() else None


def schema_path() -> Path:
    """The governing schema for this process, or a fatal error. See the resolution order above."""
    env = os.environ.get("MAC_SCHEMA")
    if env and Path(env).exists():
        return Path(env)
    fw = _framework_schema()
    if fw is None:
        raise GrammarNotFound(
            f"no {SCHEMA_NAME} resolved. Looked at: $MAC_SCHEMA, $MEANING_AS_CODE, the installed "
            f"meaning_as_code package, and this tree ({_TREE_ROOT}). There is no vendored fallback "
            f"by design -- a fork of the grammar is a second home for the standard, and the last "
            f"one drifted to the point that 22 of 22 reference concepts failed under it."
        )
    return fw


#: Kept as a name because `authoring.py:453` imports it. It reports whichever grammar governs.
def __getattr__(name: str):
    if name == "FRAMEWORK":
        return schema_path()
    raise AttributeError(name)


def load_schema() -> dict:
    return json.loads(schema_path().read_text(encoding="utf-8"))


def grammar_sha() -> str:
    """sha256 (12) of the governing grammar -- what grammar_id is built over."""
    return hashlib.sha256(schema_path().read_bytes()).hexdigest()[:12]
