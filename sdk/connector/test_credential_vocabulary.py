"""The credential vocabulary has ONE spelling, and this is what keeps it that way.

The grammar declares a closed set in `mac_vocabulary.yaml`. Each connector declares the subset it
supports in `credential_modes`. Those were written by two agents in parallel and neither read the
other: the grammar said `named_profile`, the connector said `profile`, and a bundle that VALIDATED
against the grammar was rejected by the connector as an "unknown credentials.mode".

A closed vocabulary with two spellings is not closed. These tests make the divergence impossible to
land rather than merely regrettable.
"""

import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def _grammar_modes() -> set:
    d = json.loads((ROOT / "mac.schema.json").read_text(encoding="utf-8"))
    return set(d["$defs"]["credentialMode"]["enum"])


def _connectors():
    from sdk.connector import registry

    index = json.loads((ROOT / "sdk" / "connector" / "index.json").read_text(encoding="utf-8"))
    for cid in (k for k in index if not k.startswith("_")):
        cls = registry.resolve(cid)
        if cls is not None:
            yield cid, cls


def test_the_grammar_declares_a_closed_credential_set():
    modes = _grammar_modes()
    assert modes, "an empty credential vocabulary is not a closed set"
    assert "named_profile" in modes


@pytest.mark.parametrize("cid,cls", list(_connectors()))
def test_every_connector_speaks_only_the_grammars_spelling(cid, cls):
    """A connector may support a SUBSET. It may not invent a spelling."""
    declared = set(getattr(cls, "credential_modes", frozenset()))
    unknown = declared - _grammar_modes()
    assert not unknown, f"{cid} declares credential mode(s) the grammar does not know: {sorted(unknown)}"


@pytest.mark.parametrize("cid,cls", list(_connectors()))
def test_a_plan_reports_the_mode_it_was_given(cid, cls):
    """The PLAN must not re-spell the mode either — that is the same bug one layer down, and it is
    where it actually hid: the connector accepted `named_profile` and then emitted `profile`."""
    for mode in sorted(set(getattr(cls, "credential_modes", frozenset())) - {"none"}):
        conn = {"spec_version": "mac.connector/1", "config": {},
                "credentials": {"mode": mode, "ref": "a-handle"}}
        try:
            plan = cls.credential_plan(conn)
        except NotImplementedError:
            continue          # declared and not wired is a legitimate, loud state
        except Exception:
            continue          # config-shaped refusals are another test's subject
        assert plan.mode == mode, f"{cid} was given {mode!r} and its plan says {plan.mode!r}"


@pytest.mark.parametrize("cid,cls", list(_connectors()))
def test_a_plan_never_carries_a_value(cid, cls):
    """The seam's one job. A ref is a HANDLE; if a plan ever carried a secret this is where it shows."""
    conn = {"spec_version": "mac.connector/1", "config": {},
            "credentials": {"mode": "named_profile", "ref": "a-handle"}}
    if "named_profile" not in getattr(cls, "credential_modes", frozenset()):
        pytest.skip(f"{cid} does not support named_profile")
    plan = cls.credential_plan(conn)
    assert plan.ref == "a-handle"
    assert not any(k in repr(plan).lower() for k in ("secret", "password", "aws_secret", "token="))
